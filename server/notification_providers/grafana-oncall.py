from __future__ import annotations
from typing import Any, Dict

import httpx

from .base import NotificationProvider
from server.notifications.message_formatter import build_status_message


def _resolve(notification: Dict[str, Any], *keys: str, default: str = "") -> str:
    for k in keys:
        v = notification.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default


def _alert_uid(monitor: Dict[str, Any]) -> str:
    """Stable per-monitor identifier so OnCall auto-resolves on the next 'ok'."""
    mid = monitor.get("id")
    if mid is None:
        return "observer-test"
    return f"observer-monitor-{mid}"


class GrafanaOncallProvider(NotificationProvider):
    name = "grafana-oncall"

    async def send(self, notification, message, monitor=None, heartbeat=None):
        # Frontend stores the integration URL under `url`. Accept the
        # webhook-shaped variants too for direct API users.
        webhook_url = _resolve(
            notification, "url", "webhook_url", "oncall_url"
        )
        if not webhook_url:
            raise ValueError(
                "'url' is required for Grafana OnCall notifications"
            )

        event = heartbeat.get("event") if heartbeat else None
        if not event and heartbeat:
            event = "up" if heartbeat.get("status") in (1, "up", True) else "down"
        event = event or "down"

        fmt = build_status_message(
            event=event, monitor=monitor or {}, heartbeat=heartbeat or {}
        )

        # 'ok' clears the matching alerting incident in OnCall via alert_uid;
        # everything else (down / paused / resumed / test) keeps it open.
        state = "ok" if event in ("up", "resumed") else "alerting"

        payload: Dict[str, Any] = {
            "alert_uid": _alert_uid(monitor or {}),
            "title": fmt["title"],
            "state": state,
            "message": fmt["error_msg"] or fmt["text"],
            "source": "Observer",
            "monitor_name": fmt["monitor_name"],
            "event": event,
        }
        if fmt["url"]:
            payload["link_to_upstream_details"] = fmt["url"]
        if fmt["type_label"]:
            payload["monitor_type"] = fmt["type_label"]
        if fmt["response_ms"] is not None:
            payload["response_ms"] = fmt["response_ms"]

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(webhook_url, json=payload)
                resp.raise_for_status()
        except Exception as exc:
            self.throw_general_http_error(exc)
        return "Sent Successfully."
