from __future__ import annotations
from typing import Any, Dict

import httpx

from .base import NotificationProvider
from server.notifications.message_formatter import build_status_message


# PagerDuty Events API v2 endpoint for triggering / resolving incidents.
_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"

# Map our event vocabulary to PagerDuty severities. Test alerts use
# severity=info so they don't page on-call rotations even though they
# still create a (manually resolvable) incident.
_SEVERITY_FOR_EVENT = {
    "down": "error",
    "up": "info",
    "paused": "info",
    "resumed": "info",
    "test": "info",
}


def _resolve(notification: Dict[str, Any], *keys: str, default: str = "") -> str:
    for k in keys:
        v = notification.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default


def _dedup_key(monitor: Dict[str, Any]) -> str:
    """Stable key per monitor so a later 'up' resolves the open incident."""
    mid = monitor.get("id")
    if mid is None:
        return "observer-test"
    return f"observer-monitor-{mid}"


class PagerdutyProvider(NotificationProvider):
    name = "pagerduty"

    async def send(self, notification, message, monitor=None, heartbeat=None):
        # Frontend stores `pagerdutyIntegrationKey`. After backend snake_case
        # conversion that's `pagerduty_integration_key`. Also accept the bare
        # `integration_key` for direct API users.
        integration_key = _resolve(
            notification,
            "pagerduty_integration_key",
            "integration_key",
            "routing_key",
        )
        if not integration_key:
            raise ValueError(
                "'pagerduty_integration_key' is required for PagerDuty notifications"
            )

        event = heartbeat.get("event") if heartbeat else None
        if not event and heartbeat:
            event = "up" if heartbeat.get("status") in (1, "up", True) else "down"
        event = event or "down"

        fmt = build_status_message(
            event=event, monitor=monitor or {}, heartbeat=heartbeat or {}
        )

        # 'up' resolves the existing incident (matched by dedup_key) instead
        # of opening a new one. Everything else triggers.
        action = "resolve" if event in ("up", "resumed") else "trigger"

        custom_details: Dict[str, Any] = {}
        if fmt["type_label"]:
            custom_details["type"] = fmt["type_label"]
        if fmt["url"]:
            custom_details["url"] = fmt["url"]
        if fmt["error_msg"]:
            custom_details["message"] = fmt["error_msg"]
        if fmt["response_ms"] is not None:
            custom_details["response_ms"] = fmt["response_ms"]

        payload: Dict[str, Any] = {
            "routing_key": integration_key,
            "event_action": action,
            "dedup_key": _dedup_key(monitor or {}),
        }
        if action == "trigger":
            payload["payload"] = {
                "summary": fmt["title"],
                "severity": _SEVERITY_FOR_EVENT.get(event, "error"),
                "source": fmt["monitor_name"] or "Observer",
                "custom_details": custom_details,
            }
            if fmt["url"]:
                payload["client_url"] = fmt["url"]
                payload["client"] = "Observer"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(_EVENTS_URL, json=payload)
                resp.raise_for_status()
        except Exception as exc:
            self.throw_general_http_error(exc)
        return "Sent Successfully."
