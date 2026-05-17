from .monitor_type import MonitorType

class Manual(MonitorType):
    name = "manual"

    async def check(self, monitor, heartbeat, server=None):
        """Set heartbeat status based on ``monitor.manual_status``.

        ``monitor`` is expected to expose a ``manual_status`` attribute. If it
        is ``None`` the heartbeat is marked as ``pending`` with a default
        message. Otherwise ``manual_status`` should be ``1`` for up or ``0`` for
        down and the message will reflect the state.
        """

        status = getattr(monitor, "manual_status", None)
        if status is None:
            heartbeat.status = 2  # pending
            heartbeat.msg = "Manual monitoring - No status set"
            return

        heartbeat.status = status
        if status == 1:
            heartbeat.msg = "Up"
        elif status == 0:
            heartbeat.msg = "Down"
        else:
            heartbeat.msg = "Pending"
