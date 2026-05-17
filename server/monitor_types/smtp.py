from __future__ import annotations

import asyncio

from .monitor_type import MonitorType
from .utils import exception_message


class Smtp(MonitorType):
    """Check connectivity to an SMTP service."""

    name = "smtp"

    async def check(self, monitor, heartbeat, server=None):
        """Connect to an SMTP server and send ``QUIT``.

        This lightweight implementation only verifies that a TCP connection can
        be established and that the server responds with a ``220`` greeting.
        """

        host = getattr(monitor, "hostname", None)
        port = getattr(monitor, "port", 25)
        timeout = getattr(monitor, "timeout", 10)

        if not host:
            raise ValueError("Monitor must define a hostname")

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=timeout
            )
            greeting = await asyncio.wait_for(reader.readline(), timeout=timeout)
            heartbeat.msg = greeting.decode().strip()
            writer.write(b"QUIT\r\n")
            await asyncio.wait_for(writer.drain(), timeout=timeout)
            writer.close()
            await writer.wait_closed()

            if heartbeat.msg.startswith("220"):
                heartbeat.status = 1
            else:
                heartbeat.status = 0
        except Exception as exc:  # pragma: no cover - network issues possible
            heartbeat.status = 0
            heartbeat.msg = exception_message(exc)
