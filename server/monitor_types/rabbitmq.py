from __future__ import annotations

import base64
import json
import httpx
from urllib.parse import urljoin

from .monitor_type import MonitorType
from .utils import exception_message


class Rabbitmq(MonitorType):
    """Check RabbitMQ management API."""

    name = "rabbitmq"

    async def check(self, monitor, heartbeat, server=None):
        nodes_cfg = getattr(monitor, "rabbitmqNodes", "[]")
        username = getattr(monitor, "rabbitmqUsername", "")
        password = getattr(monitor, "rabbitmqPassword", "")
        timeout = getattr(monitor, "timeout", 10)

        try:
            nodes = json.loads(nodes_cfg)
            if not isinstance(nodes, list):
                nodes = [nodes]
        except Exception:
            nodes = [nodes_cfg] if nodes_cfg else []

        if not nodes:
            raise ValueError("Monitor must define rabbitmqNodes")

        last_error = "Unable to connect"
        auth_header = "Basic " + base64.b64encode(f"{username or ''}:{password or ''}".encode()).decode()
        for node in nodes:
            if not node.endswith("/"):
                node += "/"
            url = urljoin(node, "api/health/checks/alarms/")
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    res = await client.get(
                        url,
                        headers={
                            "Accept": "application/json",
                            "Authorization": auth_header,
                        },
                        follow_redirects=True,
                        validate_status=lambda s: s in (200, 503),
                    )
                if res.status_code == 200:
                    heartbeat.status = 1
                    heartbeat.msg = "OK"
                    return
                elif res.status_code == 503:
                    last_error = res.json().get("reason", "Service unavailable")
                else:
                    last_error = f"{res.status_code} - {res.reason_phrase}"
            except Exception as exc:  # pragma: no cover - network errors possible
                last_error = exception_message(exc)

        heartbeat.status = 0
        heartbeat.msg = last_error
