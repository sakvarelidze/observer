import asyncio
import socket
from contextlib import closing
import types

import pytest

from server.monitor_types.smtp import Smtp


def _free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DummySMTP:
    def __init__(self, port: int):
        self.port = port
        self._server = None

    async def __aenter__(self):
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", self.port)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._server.close()
        await self._server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        writer.write(b"220 local\r\n")
        await writer.drain()
        while True:
            data = await reader.readline()
            if not data:
                break
            cmd = data.decode().strip().upper()
            if cmd == "QUIT":
                writer.write(b"221 bye\r\n")
                await writer.drain()
                break
            else:
                writer.write(b"250 OK\r\n")
                await writer.drain()
        writer.close()


@pytest.mark.asyncio
async def test_smtp_monitor_success():
    port = _free_port()
    async with DummySMTP(port):
        monitor = types.SimpleNamespace(hostname="127.0.0.1", port=port)
        hb = types.SimpleNamespace(status=None, msg=None)
        await Smtp().check(monitor, hb)
        assert hb.status == 1
        assert hb.msg.startswith("220")


@pytest.mark.asyncio
async def test_smtp_monitor_failure():
    port = _free_port()
    monitor = types.SimpleNamespace(hostname="127.0.0.1", port=port)
    hb = types.SimpleNamespace(status=None, msg=None)
    await Smtp().check(monitor, hb)
    assert hb.status == 0
