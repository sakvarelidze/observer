import asyncio
import importlib
import shutil
import types
import pytest


tailscale_mod = importlib.import_module("server.monitor_types.tailscale-ping")
TailscalePing = tailscale_mod.TailscalePing


class DummyProcess:
    def __init__(self, stdout=b"", stderr=b"", returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.killed = False

    async def communicate(self):
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True


def _patch_exec(monkeypatch, process):
    async def fake_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)


@pytest.mark.asyncio
async def test_tailscale_ping_missing_binary(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    monitor = types.SimpleNamespace(hostname="100.64.0.1")
    hb = types.SimpleNamespace(status=None, msg=None, ping=None)
    await TailscalePing().check(monitor, hb)
    assert hb.status == 0
    assert "tailscale command not found" in hb.msg


@pytest.mark.asyncio
async def test_tailscale_ping_missing_host():
    monitor = types.SimpleNamespace(hostname=None)
    hb = types.SimpleNamespace(status=None, msg=None, ping=None)
    with pytest.raises(ValueError):
        await TailscalePing().check(monitor, hb)


@pytest.mark.asyncio
async def test_tailscale_ping_success_no_space(monkeypatch):
    """Real tailscale output: `in 23ms` (no space between number and unit)."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/tailscale")
    output = b"pong from server-1 (100.64.0.1) via DERP(sfo) in 23ms\n"
    _patch_exec(monkeypatch, DummyProcess(stdout=output, returncode=0))
    monitor = types.SimpleNamespace(hostname="100.64.0.1")
    hb = types.SimpleNamespace(status=None, msg=None, ping=None)
    await TailscalePing().check(monitor, hb)
    assert hb.status == 1
    assert hb.msg == "OK"
    assert hb.ping == 23


@pytest.mark.asyncio
async def test_tailscale_ping_success_with_space(monkeypatch):
    """Defensive: also accept `in 23 ms` if a future tailscale build adds the space."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/tailscale")
    output = b"pong from server-1 (100.64.0.1) via DERP(sfo) in 23 ms\n"
    _patch_exec(monkeypatch, DummyProcess(stdout=output, returncode=0))
    monitor = types.SimpleNamespace(hostname="100.64.0.1")
    hb = types.SimpleNamespace(status=None, msg=None, ping=None)
    await TailscalePing().check(monitor, hb)
    assert hb.status == 1
    assert hb.ping == 23


@pytest.mark.asyncio
async def test_tailscale_ping_success_fractional_ms(monkeypatch):
    """Fractional milliseconds should truncate to int, not crash."""
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/tailscale")
    output = b"pong from server-1 (100.64.0.1) via DERP(sfo) in 12.5ms\n"
    _patch_exec(monkeypatch, DummyProcess(stdout=output, returncode=0))
    monitor = types.SimpleNamespace(hostname="100.64.0.1")
    hb = types.SimpleNamespace(status=None, msg=None, ping=None)
    await TailscalePing().check(monitor, hb)
    assert hb.status == 1
    assert hb.ping == 12


@pytest.mark.asyncio
async def test_tailscale_ping_timed_out(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/tailscale")
    output = b"ping timed out\n"
    _patch_exec(monkeypatch, DummyProcess(stdout=output, returncode=0))
    monitor = types.SimpleNamespace(hostname="100.64.0.1")
    hb = types.SimpleNamespace(status=None, msg=None, ping=None)
    await TailscalePing().check(monitor, hb)
    assert hb.status == 0
    assert "timed out" in hb.msg


@pytest.mark.asyncio
async def test_tailscale_ping_no_peer(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/tailscale")
    output = b"no matching peer\n"
    _patch_exec(monkeypatch, DummyProcess(stdout=output, returncode=0))
    monitor = types.SimpleNamespace(hostname="100.64.0.1")
    hb = types.SimpleNamespace(status=None, msg=None, ping=None)
    await TailscalePing().check(monitor, hb)
    assert hb.status == 0
    assert "inaccessible" in hb.msg


@pytest.mark.asyncio
async def test_tailscale_ping_nonzero_exit(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/tailscale")
    _patch_exec(monkeypatch, DummyProcess(stdout=b"", stderr=b"not logged in", returncode=1))
    monitor = types.SimpleNamespace(hostname="100.64.0.1")
    hb = types.SimpleNamespace(status=None, msg=None, ping=None)
    await TailscalePing().check(monitor, hb)
    assert hb.status == 0
    assert "not logged in" in hb.msg
