from __future__ import annotations

from .monitor_type import MonitorType


class Group(MonitorType):
    """Monitor type used for grouping other monitors."""

    name = "group"

    async def check(self, monitor, heartbeat, server=None):
        # Group monitors do not perform checks themselves.
        heartbeat.status = 1
        heartbeat.msg = "OK"
