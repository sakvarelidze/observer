from __future__ import annotations
from typing import Any, Dict, List

import httpx

from .base import NotificationProvider
from server.notifications.message_formatter import build_status_message


def _build_blocks(fmt: Dict) -> List[Dict[str, Any]]:
    """Compose Slack Block Kit elements from the formatter primitives."""
    blocks: List[Dict[str, Any]] = []

    header_text = f"{fmt['glyph']} {fmt['title']}".strip()
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": header_text, "emoji": True},
    })

    if fmt["event"] == "test":
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "_This is a sample notification — real alerts will include "
                    "the monitor name, type, response details, and any error "
                    "message._"
                ),
            },
        })
        return blocks

    fields: List[Dict[str, str]] = []
    if fmt["type_label"]:
        fields.append({"type": "mrkdwn", "text": f"*Type*\n{fmt['type_label']}"})
    if fmt["url"]:
        fields.append({"type": "mrkdwn", "text": f"*URL*\n<{fmt['url']}>"})
    if fmt["response_ms"] is not None:
        fields.append({"type": "mrkdwn", "text": f"*Response*\n{fmt['response_ms']}ms"})
    if fields:
        blocks.append({"type": "section", "fields": fields})

    if fmt["error_msg"]:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"_{fmt['error_msg']}_"}],
        })

    return blocks


class SlackProvider(NotificationProvider):
    name = "slack"

    async def send(self, notification, message, monitor=None, heartbeat=None):
        webhook_url = (
            notification.get("webhook_url")
            or notification.get("slackwebhook_url")
        )
        if not webhook_url:
            raise ValueError("'webhook_url' is required for Slack notifications")

        event = heartbeat.get("event") if heartbeat else None
        if not event and heartbeat:
            event = "up" if heartbeat.get("status") in (1, "up", True) else "down"
        fmt = build_status_message(
            event=event or "down", monitor=monitor or {}, heartbeat=heartbeat or {}
        )

        # Use the legacy `attachments` envelope so Slack draws the coloured
        # vertical stripe to the left of the card. Block Kit on its own
        # has no native color affordance.
        data = {
            "text": fmt["text"],  # fallback for clients that don't render blocks
            "attachments": [{
                "color": fmt["color_hex"],
                "blocks": _build_blocks(fmt),
            }],
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=data)
                resp.raise_for_status()
        except Exception as exc:
            self.throw_general_http_error(exc)
        return "Sent Successfully."
