from __future__ import annotations
from typing import Any, Dict

import httpx

from .base import NotificationProvider
from server.notifications.message_formatter import build_status_message


_API_BASE = "https://api.twilio.com/2010-04-01"


# Plain-text status tag used on the SMS body. We avoid emoji here — they
# trigger UCS-2 encoding on most carriers, halving the per-segment char
# budget (and Twilio bills per segment).
_STATUS_TAG = {
    "down": "[DOWN]",
    "up": "[UP]",
    "paused": "[PAUSED]",
    "resumed": "[RESUMED]",
    "test": "[TEST]",
}


def _resolve(notification: Dict[str, Any], *keys: str, default: str = "") -> str:
    for k in keys:
        v = notification.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default


def _build_sms_body(fmt: Dict, event: str) -> str:
    """Compose a compact one-segment-friendly SMS body."""
    tag = _STATUS_TAG.get(event, "[ALERT]")
    name = fmt["monitor_name"] or "Monitor"

    if event == "test":
        return f"{tag} Observer test alert. This channel is wired up correctly."

    parts = [f"{tag} {name}"]
    if fmt["error_msg"]:
        parts.append(fmt["error_msg"])
    elif fmt["response_ms"] is not None:
        parts.append(f"{fmt['response_ms']}ms")
    return " — ".join(parts)


class TwilioProvider(NotificationProvider):
    name = "twilio"

    async def send(self, notification, message, monitor=None, heartbeat=None):
        account_sid = _resolve(notification, "account_sid", "twilio_account_sid")
        auth_token = _resolve(notification, "auth_token", "twilio_auth_token")
        from_number = _resolve(notification, "from_number", "twilio_from_number")
        to_number = _resolve(notification, "to_number", "twilio_to_number")

        missing = [
            n for n, v in (
                ("account_sid", account_sid),
                ("auth_token", auth_token),
                ("from_number", from_number),
                ("to_number", to_number),
            ) if not v
        ]
        if missing:
            raise ValueError(
                f"Missing required Twilio fields: {', '.join(missing)}"
            )

        event = heartbeat.get("event") if heartbeat else None
        if not event and heartbeat:
            event = "up" if heartbeat.get("status") in (1, "up", True) else "down"
        event = event or "down"

        fmt = build_status_message(
            event=event, monitor=monitor or {}, heartbeat=heartbeat or {}
        )

        body = _build_sms_body(fmt, event)
        url = f"{_API_BASE}/Accounts/{account_sid}/Messages.json"
        data = {"From": from_number, "To": to_number, "Body": body}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, data=data, auth=(account_sid, auth_token)
                )
                resp.raise_for_status()
        except Exception as exc:
            self.throw_general_http_error(exc)
        return "Sent Successfully."
