from __future__ import annotations

import asyncio
import re
import shutil

from .monitor_type import MonitorType
from .utils import exception_message


_TAILSCALE_PING_TIME_RE = re.compile(r"\bin\s+(\d+(?:\.\d+)?)\s*ms\b")


class TailscalePing(MonitorType):
    """Ping a host via the local tailscale client."""

    name = "tailscale-ping"

    async def check(self, monitor, heartbeat, server=None):
        host = getattr(monitor, "hostname", None)
        timeout = getattr(monitor, "timeout", 10)

        if not host:
            raise ValueError("Monitor must define a hostname")

        if not shutil.which("tailscale"):
            heartbeat.status = 0
            heartbeat.msg = "tailscale command not found"
            return

        try:
            proc = await asyncio.create_subprocess_exec(
                "tailscale",
                "ping",
                "--c",
                "1",
                host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                heartbeat.status = 0
                heartbeat.msg = "Timeout"
                return

            output = (stdout or b"").decode().strip()
            if proc.returncode != 0:
                raise RuntimeError(stderr.decode().strip() or "Ping failed")

            for line in output.splitlines():
                if "pong from" in line:
                    heartbeat.status = 1
                    match = _TAILSCALE_PING_TIME_RE.search(line)
                    heartbeat.ping = int(float(match.group(1))) if match else None
                    heartbeat.msg = "OK"
                    return
                if "timed out" in line:
                    raise RuntimeError(f"Ping timed out: '{line}'")
                if "no matching peer" in line:
                    raise RuntimeError(f"Nonexistant or inaccessible due to ACLs: '{line}'")
                if "is local Tailscale IP" in line:
                    raise RuntimeError(f"Tailscale only works if used on other machines: '{line}'")
                if line:
                    raise RuntimeError(f"Unexpected output: '{line}'")
            raise RuntimeError("No output from tailscale")
        except Exception as exc:  # pragma: no cover - system issues possible
            heartbeat.status = 0
            heartbeat.msg = exception_message(exc)
