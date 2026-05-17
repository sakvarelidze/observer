import types
import pytest
import httpx
import asyncio
import shutil
import platform

from server.monitor_types import HTTPMonitor
from server.monitor_types.manual import Manual

class DummyResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code
        from datetime import timedelta
        self.elapsed = timedelta(milliseconds=100)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

class DummyClient:
    def __init__(self, response):
        self.response = response
        self.requested_url = None
        self.requested_method = None
        self.headers = None
        self.content = None
        self.auth = None
        self.verify = None
        self.proxies = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def request(self, method, url, headers=None, content=None, timeout=None, auth=None):
        self.requested_method = method
        self.requested_url = url
        self.headers = headers
        self.content = content
        self.auth = auth
        return self.response

@pytest.mark.asyncio
async def test_http_monitor_up(monkeypatch):
    monitor = types.SimpleNamespace(url="http://example.com")
    heartbeat = types.SimpleNamespace(status=None, msg=None, ping=None)
    dummy = DummyClient(DummyResponse(200))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    await HTTPMonitor().check(monitor, heartbeat)
    assert heartbeat.status == 1
    assert heartbeat.msg == "HTTP 200"
    assert dummy.requested_url == "http://example.com"
    assert dummy.requested_method == "GET"

@pytest.mark.asyncio
async def test_http_monitor_ignore_tls(monkeypatch):
    monitor = types.SimpleNamespace(url="https://example.com", ignore_tls=True)
    heartbeat = types.SimpleNamespace(status=None, msg=None, ping=None)
    dummy = DummyClient(DummyResponse(200))
    def factory(*a, **k):
        dummy.verify = k.get("verify")
        return dummy
    monkeypatch.setattr(httpx, "AsyncClient", factory)
    await HTTPMonitor().check(monitor, heartbeat)
    assert dummy.verify is False

@pytest.mark.asyncio
async def test_manual_monitor_pending():
    monitor = types.SimpleNamespace(manual_status=None)
    heartbeat = types.SimpleNamespace(status=None, msg=None)
    await Manual().check(monitor, heartbeat)
    assert heartbeat.status == 2
    assert "No status" in heartbeat.msg


@pytest.mark.asyncio
async def test_http_monitor_not_accepted(monkeypatch):
    monitor = types.SimpleNamespace(url="http://example.com", accepted_statuscodes=["200-201"])
    heartbeat = types.SimpleNamespace(status=None, msg=None, ping=None)
    dummy = DummyClient(DummyResponse(404))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    await HTTPMonitor().check(monitor, heartbeat)
    assert heartbeat.status == 0
    assert heartbeat.msg == "HTTP 404"


@pytest.mark.asyncio
async def test_http_monitor_custom_range(monkeypatch):
    monitor = types.SimpleNamespace(url="http://example.com", accepted_statuscodes=["500-502"])
    heartbeat = types.SimpleNamespace(status=None, msg=None, ping=None)
    dummy = DummyClient(DummyResponse(500))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    await HTTPMonitor().check(monitor, heartbeat)
    assert heartbeat.status == 1
    assert heartbeat.msg == "HTTP 500"


@pytest.mark.asyncio
async def test_http_monitor_custom_method(monkeypatch):
    monitor = types.SimpleNamespace(
        url="http://example.com", method="POST", body="data", headers={"X-Test": "1"}
    )
    heartbeat = types.SimpleNamespace(status=None, msg=None, ping=None)
    dummy = DummyClient(DummyResponse(200))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    await HTTPMonitor().check(monitor, heartbeat)
    assert dummy.requested_method == "POST"
    assert dummy.content == "data"
    assert dummy.headers == {"X-Test": "1"}


@pytest.mark.asyncio
async def test_http_monitor_basic_auth(monkeypatch):
    monitor = types.SimpleNamespace(
        url="http://example.com", basic_auth_user="u", basic_auth_pass="p"
    )
    heartbeat = types.SimpleNamespace(status=None, msg=None, ping=None)
    dummy = DummyClient(DummyResponse(200))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    await HTTPMonitor().check(monitor, heartbeat)
    assert dummy.auth == ("u", "p")


@pytest.mark.asyncio
async def test_http_monitor_proxy(monkeypatch):
    proxy = types.SimpleNamespace(
        protocol="http",
        host="proxy.local",
        port=8080,
        auth=True,
        username="a",
        password="b",
        active=True,
    )
    monitor = types.SimpleNamespace(url="http://example.com", proxy=proxy)
    heartbeat = types.SimpleNamespace(status=None, msg=None, ping=None)
    dummy = DummyClient(DummyResponse(200))

    def factory(*a, **k):
        dummy.proxies = k.get("proxy")
        return dummy

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    await HTTPMonitor().check(monitor, heartbeat)
    assert dummy.proxies == "http://a:b@proxy.local:8080"

from server.monitor_types.group import Group
from server.monitor_types.ping import Ping


@pytest.mark.asyncio
async def test_group_monitor_returns_ok():
    monitor = types.SimpleNamespace()
    heartbeat = types.SimpleNamespace(status=None, msg=None)
    await Group().check(monitor, heartbeat)
    assert heartbeat.status == 1
    assert heartbeat.msg == "OK"


@pytest.mark.asyncio
async def test_ping_monitor_success():
    monitor = types.SimpleNamespace(
        hostname="127.0.0.1",
        ping_count=1,
        ping_per_request_timeout=1,
        packet_size=16,
        ping_numeric=True,
        timeout=5,
    )
    heartbeat = types.SimpleNamespace(status=None, msg=None, ping=None)
    await Ping().check(monitor, heartbeat)
    assert heartbeat.status == 1
    assert heartbeat.msg == "OK"
    assert heartbeat.ping is not None


@pytest.mark.asyncio
async def test_ping_monitor_windows_output(monkeypatch):
    monitor = types.SimpleNamespace(
        hostname="example.com",
        ping_count=1,
        ping_per_request_timeout=1,
        packet_size=16,
        timeout=5,
    )
    heartbeat = types.SimpleNamespace(status=None, msg=None, ping=None)

    windows_output = (
        "Ping statistics for 123.123.123.123:\r\n"
        "    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),\r\n"
        "Approximate round trip times in milli-seconds:\r\n"
        "    Minimum = 14ms, Maximum = 14ms, Average = 14ms\r\n"
    ).encode()

    class DummyProcess:
        def __init__(self, stdout):
            self._stdout = stdout
            self.returncode = 0

        async def communicate(self):
            return self._stdout, b""

    async def fake_exec(*args, **kwargs):
        return DummyProcess(windows_output)

    monkeypatch.setattr(shutil, "which", lambda cmd: "/bin/ping")
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    await Ping().check(monitor, heartbeat)
    assert heartbeat.status == 1
    assert heartbeat.msg == "OK"
    assert heartbeat.ping == 14.0
