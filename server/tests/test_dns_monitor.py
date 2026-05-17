import types
import socket
from contextlib import closing

import pytest
from dnslib.server import DNSServer, BaseResolver
from dnslib import RR, QTYPE, A

from server.monitor_types.dns import Dns


def _free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class StaticResolver(BaseResolver):
    def resolve(self, request, handler):
        reply = request.reply()
        qname = request.q.qname
        reply.add_answer(RR(qname, QTYPE.A, rdata=A('1.2.3.4')))
        return reply


@pytest.mark.asyncio
async def test_dns_monitor_success():
    port = _free_port()
    server = DNSServer(StaticResolver(), port=port, address='127.0.0.1')
    server.start_thread()
    monitor = types.SimpleNamespace(
        hostname='example.com',
        dns_resolve_server='127.0.0.1',
        dns_resolve_type='A',
        port=port,
    )
    heartbeat = types.SimpleNamespace(status=None, msg=None)
    try:
        await Dns().check(monitor, heartbeat)
        assert heartbeat.status == 1
        assert '1.2.3.4' in heartbeat.msg
    finally:
        server.stop()


@pytest.mark.asyncio
async def test_dns_monitor_failure():
    port = _free_port()
    monitor = types.SimpleNamespace(
        hostname='example.com',
        dns_resolve_server='127.0.0.1',
        dns_resolve_type='A',
        port=port,
    )
    heartbeat = types.SimpleNamespace(status=None, msg=None)
    await Dns().check(monitor, heartbeat)
    assert heartbeat.status == 0
