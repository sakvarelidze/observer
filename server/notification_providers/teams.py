from __future__ import annotations
from typing import Any, Dict, List

import httpx

from .base import NotificationProvider
from server.notifications.message_formatter import build_status_message


def _build_section(fmt: Dict) -> Dict[str, Any]:
    """Compose the single section of the MessageCard from formatter output.

    Teams renders activityTitle/activitySubtitle in the header zone, facts
    as a key/value list below, and `text` as a free-form description.
    """
    section: Dict[str, Any] = {
        "activityTitle": f"{fmt['glyph']} **{fmt['title']}**".strip(),
    }

    if fmt["event"] == "test":
        section["text"] = (
            "This is a sample notification — real alerts will include the "
            "monitor name, type, response details, and any error message."
        )
        return section

    if fmt["url"]:
        section["activitySubtitle"] = f"[{fmt['url']}]({fmt['url']})"
    elif fmt["type_label"]:
        section["activitySubtitle"] = fmt["type_label"]

    facts: List[Dict[str, str]] = []
    if fmt["type_label"] and fmt["url"]:
        # Subtitle already shows the URL — keep type as a fact for scannability.
        facts.append({"name": "Type", "value": fmt["type_label"]})
    if fmt["response_ms"] is not None:
        facts.append({"name": "Response", "value": f"{fmt['response_ms']}ms"})
    if facts:
        section["facts"] = facts

    if fmt["error_msg"]:
        section["text"] = fmt["error_msg"]

    return section


class TeamsProvider(NotificationProvider):
    name = "teams"

    async def send(self, notification, message, monitor=None, heartbeat=None):
        webhook_url = notification.get("webhook_url")
        if not webhook_url:
            raise ValueError("'webhook_url' is required for Teams notifications")

        event = heartbeat.get("event") if heartbeat else None
        if not event and heartbeat:
            event = "up" if heartbeat.get("status") in (1, "up", True) else "down"
        fmt = build_status_message(
            event=event or "down", monitor=monitor or {}, heartbeat=heartbeat or {}
        )

        # Teams `themeColor` is a hex string without the leading '#'.
        theme_color = fmt["color_hex"].lstrip("#")

        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": theme_color,
            "summary": fmt["title"],
            "sections": [_build_section(fmt)],
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=payload)
                resp.raise_for_status()
        except Exception as exc:
            self.throw_general_http_error(exc)
        return "Sent Successfully."
