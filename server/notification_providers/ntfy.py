from __future__ import annotations
from typing import Any, Dict

import httpx

from .base import NotificationProvider
from server.notifications.message_formatter import build_status_message


# Higher number = noisier on the device. ntfy uses 1=min, 5=max; 3 is default.
_PRIORITY_FOR_EVENT = {
    "down": "5",
    "up": "3",
    "paused": "2",
    "resumed": "3",
    "test": "3",
}

# Comma-separated tag list rendered as inline emojis in the ntfy client.
_TAGS_FOR_EVENT = {
    "down": "rotating_light",
    "up": "white_check_mark",
    "paused": "pause_button",
    "resumed": "arrow_forward",
    "test": "bell",
}


def _resolve(notification: Dict[str, Any], *keys: str, default: str = "") -> str:
    """Return the first non-empty value for any of the candidate keys."""
    for k in keys:
        v = notification.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default


class NtfyProvider(NotificationProvider):
    name = "ntfy"

    async def send(self, notification, message, monitor=None, heartbeat=None):
        # Frontend stores `ntfyserverurl` / `ntfytopic`. Keep the snake_case
        # variants as fallbacks for anyone hitting the API directly.
        server_url = _resolve(
            notification,
            "ntfyserverurl",
            "ntfy_server_url",
            "server_url",
            default="https://ntfy.sh",
        ).rstrip("/")
        topic = _resolve(notification, "ntfytopic", "ntfy_topic", "topic")
        if not topic:
            raise ValueError("'topic' is required for ntfy notifications")

        event = heartbeat.get("event") if heartbeat else None
        if not event and heartbeat:
            event = "up" if heartbeat.get("status") in (1, "up", True) else "down"
        event = event or "down"

        fmt = build_status_message(
            event=event, monitor=monitor or {}, heartbeat=heartbeat or {}
        )

        # Body is the multi-line text minus the leading title line (ntfy
        # renders its own bold title from the Title header).
        body_lines = fmt["text"].splitlines()
        body = "\n".join(body_lines[1:]) if len(body_lines) > 1 else fmt["text"]

        headers: Dict[str, str] = {
            "Title": fmt["title"],
            "Priority": _PRIORITY_FOR_EVENT.get(event, "3"),
            "Tags": _TAGS_FOR_EVENT.get(event, "bell"),
        }
        if fmt["url"]:
            # Tap the notification to open the monitor's URL.
            headers["Click"] = fmt["url"]

        # Optional bearer auth (self-hosted ntfy with access tokens).
        token = _resolve(notification, "access_token", "ntfytoken")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"{server_url}/{topic}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, content=body.encode("utf-8"), headers=headers)
                resp.raise_for_status()
        except Exception as exc:
            self.throw_general_http_error(exc)
        return "Sent Successfully."
