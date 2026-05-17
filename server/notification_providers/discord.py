from __future__ import annotations
from typing import Any, Dict, List

from .base import NotificationProvider
from server.notifications.message_formatter import build_status_message


def _hex_to_int(hex_color: str) -> int:
    """'#E81123' -> 15147299. Discord embeds want a decimal int."""
    return int(hex_color.lstrip("#"), 16)


def _build_embed(fmt: Dict) -> Dict[str, Any]:
    embed: Dict[str, Any] = {
        "title": f"{fmt['glyph']} {fmt['title']}".strip(),
        "color": _hex_to_int(fmt["color_hex"]),
    }

    if fmt["event"] == "test":
        embed["description"] = (
            "This is a sample notification — real alerts will include the "
            "monitor name, type, response details, and any error message."
        )
        return embed

    if fmt["url"]:
        # Discord renders the title as a link to embed.url.
        embed["url"] = fmt["url"]
    if fmt["error_msg"]:
        embed["description"] = fmt["error_msg"]

    fields: List[Dict[str, Any]] = []
    if fmt["type_label"]:
        fields.append({"name": "Type", "value": fmt["type_label"], "inline": True})
    if fmt["response_ms"] is not None:
        fields.append({"name": "Response", "value": f"{fmt['response_ms']}ms", "inline": True})
    if fields:
        embed["fields"] = fields

    return embed


class DiscordProvider(NotificationProvider):
    name = "discord"

    async def send(self, notification, message, monitor=None, heartbeat=None):
        """Send a message to a Discord webhook."""
        import httpx

        # Support legacy "discord_webhook_url" key for backward compatibility
        webhook_url = notification.get("webhook_url") or notification.get("discord_webhook_url")
        if not webhook_url:
            raise ValueError("'webhook_url' is required for Discord notifications")

        event = heartbeat.get("event") if heartbeat else None
        if not event and heartbeat:
            event = "up" if heartbeat.get("status") in (1, "up", True) else "down"
        fmt = build_status_message(
            event=event or "down", monitor=monitor or {}, heartbeat=heartbeat or {}
        )

        data = {
            "username": notification.get("username", "Observer"),
            "embeds": [_build_embed(fmt)],
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=data)
                resp.raise_for_status()
        except Exception as exc:
            self.throw_general_http_error(exc)
        return "Sent Successfully."
