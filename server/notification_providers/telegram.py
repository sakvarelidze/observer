from __future__ import annotations
import httpx
from typing import Any, Dict
from .base import NotificationProvider
from server.notifications.message_formatter import build_status_message

class TelegramProvider(NotificationProvider):
    name = "telegram"

    async def send(
        self,
        notification: Dict[str, Any],
        message: str,
        monitor: Dict[str, Any] | None = None,
        heartbeat: Dict[str, Any] | None = None,
    ) -> str:
        server_url = notification.get("server_url", "https://api.telegram.org")
        token = notification["bot_token"]
        chat_id = notification["chat_id"]

        event = heartbeat.get("event") if heartbeat else None
        if not event and heartbeat:
            event = "up" if heartbeat.get("status") in (1, "up", True) else "down"
        fmt = build_status_message(
            event=event or "down", monitor=monitor or {}, heartbeat=heartbeat or {}
        )

        params = {
            "chat_id": chat_id,
            "text": fmt["html"],
            "parse_mode": "HTML",
            # Suppress the auto-generated link preview card so a "site went
            # DOWN" alert doesn't render the dead site's last cached preview.
            "disable_web_page_preview": True,
        }
        verify = not notification.get("ignore_tls", False)
        try:
            async with httpx.AsyncClient(verify=verify) as client:
                r = await client.get(
                    f"{server_url}/bot{token}/sendMessage", params=params
                )
                r.raise_for_status()
        except Exception as exc:
            self.throw_general_http_error(exc)
        return "Sent Successfully."
