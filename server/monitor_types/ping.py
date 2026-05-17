from __future__ import annotations

import asyncio
import shutil
import platform

from .monitor_type import MonitorType
from .utils import exception_message


class Ping(MonitorType):
    """Ping a host using the system ping command."""

    name = "ping"

    async def check(self, monitor, heartbeat, server=None):
        host = getattr(monitor, "hostname", None)
        timeout = getattr(monitor, "timeout", 10)
        count = getattr(monitor, "ping_count", 3)
        per_request = getattr(monitor, "ping_per_request_timeout", 2)
        packet_size = getattr(monitor, "packet_size", 56)

        if not host:
            raise ValueError("Monitor must define a hostname")
        host = str(host)

        if not shutil.which("ping"):
            heartbeat.status = 0
            heartbeat.msg = "ping command not found"
            return

        args = ["ping"]
        system = platform.system().lower()
        if system == "windows":
            # Windows ping uses different flags and units
            args += [
                "-n",
                str(max(1, int(count))),
                "-w",
                str(max(0, int(per_request)) * 1000),
                "-l",
                str(max(1, int(packet_size))),
                host,
            ]
        else:
            args += [
                "-c",
                str(max(1, int(count))),
                "-W",
                str(max(0, int(per_request))),
                "-s",
                str(max(1, int(packet_size))),
                host,
            ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
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

            output = (stdout or b"").decode()
            if proc.returncode != 0:
                raise RuntimeError(stderr.decode().strip() or output.strip() or "Ping failed")

            heartbeat.status = 1
            heartbeat.msg = "OK"
            # parse avg ping from statistics line
            for line in output.splitlines():
                line = line.strip()
                if "min/avg" in line:
                    try:
                        stats = line.split("=")[1].strip().split()[0]
                        heartbeat.ping = float(stats.split("/")[1])
                    except Exception:
                        heartbeat.ping = None
                    break
                if "average" in line.lower():
                    try:
                        part = line.lower().split("average")[-1]
                        heartbeat.ping = float(part.split("=")[-1].strip().split()[0].replace("ms", ""))
                    except Exception:
                        heartbeat.ping = None
                    break
        except Exception as exc:  # pragma: no cover - system issues possible
            heartbeat.status = 0
            heartbeat.msg = exception_message(exc)
