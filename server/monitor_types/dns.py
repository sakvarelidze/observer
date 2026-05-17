from __future__ import annotations

import dns.asyncresolver

from .monitor_type import MonitorType
from .utils import exception_message


class Dns(MonitorType):
    """Resolve a DNS record using a specific nameserver and record type."""

    name = "dns"

    async def check(self, monitor, heartbeat, server=None):
        hostname = getattr(monitor, "hostname", None)
        rrtype = getattr(monitor, "dns_resolve_type", "A")
        resolver_addr = getattr(monitor, "dns_resolve_server", None)
        port = getattr(monitor, "port", 53)

        if not hostname:
            raise ValueError("Monitor must define a hostname")

        resolver = dns.asyncresolver.Resolver()
        if resolver_addr:
            resolver.nameservers = [resolver_addr]
        resolver.port = port

        try:
            answer = await resolver.resolve(hostname, rdtype=rrtype)
            result = ", ".join(r.to_text() for r in answer)
            heartbeat.status = 1
            heartbeat.msg = result
        except Exception as exc:  # pragma: no cover - network errors are possible
            heartbeat.status = 0
            heartbeat.msg = exception_message(exc)

        if hasattr(monitor, "dns_last_result"):
            monitor.dns_last_result = heartbeat.msg
