from __future__ import annotations
from jinja2 import Template
from typing import Any, Dict

class NotificationProvider:
    name: str = "base"
    registry: Dict[str, type] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "name", None) and cls.name != "base":
            NotificationProvider.registry[cls.name] = cls

    async def send(
        self,
        notification: Dict[str, Any],
        message: str,
        monitor: Dict[str, Any] | None = None,
        heartbeat: Dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    def extract_address(self, monitor: Dict[str, Any] | None) -> str:
        """Return an address string used in templates."""
        if not monitor:
            return ""
        if monitor.get("type") == "push":
            return "Heartbeat"
        if monitor.get("hostname"):
            host = monitor["hostname"]
            if monitor.get("port"):
                return f"{host}:{monitor['port']}"
            return host
        return monitor.get("url", "")

    def throw_general_http_error(self, exc: Exception) -> None:
        raise RuntimeError(f"Error: {exc}")

    async def render_template(
        self,
        template_str: str,
        message: str,
        monitor: Dict[str, Any] | None = None,
        heartbeat: Dict[str, Any] | None = None,
    ) -> str:
        template = Template(template_str)
        context = {
            "msg": message,
            "monitor": monitor or {},
            "heartbeat": heartbeat or {},
        }
        return template.render(**context)
