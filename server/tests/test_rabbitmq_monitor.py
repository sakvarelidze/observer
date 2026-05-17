import json
import types
import pytest
import httpx

import server.monitor_types.rabbitmq as rabbitmq_mod
from server.monitor_types.rabbitmq import Rabbitmq


class DummyResponse:
    def __init__(self, status_code, payload=None, reason_phrase=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.reason_phrase = reason_phrase

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self, responses):
        # `responses` is a list of DummyResponse keyed by call order
        self._responses = list(responses)
        self.last_url = None
        self.last_headers = None
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, headers=None, follow_redirects=False, validate_status=None):
        self.last_url = url
        self.last_headers = headers
        self.requests.append({"url": url, "headers": headers})
        if not self._responses:
            raise RuntimeError("No more dummy responses")
        return self._responses.pop(0)


@pytest.fixture
def dummy_clients(monkeypatch):
    """Patch httpx.AsyncClient to return a queue of dummy clients (one per node).

    Returns the list of created DummyClient instances for assertion access; the
    pop happens against a separate internal queue so the returned list is stable.
    """

    def make_factory(responses_per_call):
        created = [DummyClient(r) for r in responses_per_call]
        queue = list(created)

        def factory(*a, **k):
            return queue.pop(0)

        monkeypatch.setattr(rabbitmq_mod.httpx, "AsyncClient", factory)
        return created

    return make_factory


@pytest.mark.asyncio
async def test_rabbitmq_monitor_success(dummy_clients):
    clients = dummy_clients([[DummyResponse(200, {})]])
    monitor = types.SimpleNamespace(
        rabbitmqNodes=json.dumps(["http://rabbit.local:15672"]),
        rabbitmqUsername="guest",
        rabbitmqPassword="guest",
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    await Rabbitmq().check(monitor, hb)
    assert hb.status == 1
    assert hb.msg == "OK"
    assert clients[0].last_url == "http://rabbit.local:15672/api/health/checks/alarms/"
    assert clients[0].last_headers["Authorization"].startswith("Basic ")


@pytest.mark.asyncio
async def test_rabbitmq_monitor_503_reason(dummy_clients):
    dummy_clients([[DummyResponse(503, {"reason": "resource alarm"})]])
    monitor = types.SimpleNamespace(
        rabbitmqNodes=json.dumps(["http://rabbit.local:15672/"]),
        rabbitmqUsername="u",
        rabbitmqPassword="p",
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    await Rabbitmq().check(monitor, hb)
    assert hb.status == 0
    assert hb.msg == "resource alarm"


@pytest.mark.asyncio
async def test_rabbitmq_monitor_falls_through_to_second_node(dummy_clients):
    clients = dummy_clients(
        [
            [DummyResponse(503, {"reason": "first node alarm"})],
            [DummyResponse(200, {})],
        ]
    )
    monitor = types.SimpleNamespace(
        rabbitmqNodes=json.dumps(["http://a:15672", "http://b:15672"]),
        rabbitmqUsername="u",
        rabbitmqPassword="p",
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    await Rabbitmq().check(monitor, hb)
    assert hb.status == 1
    assert hb.msg == "OK"
    assert clients[1].last_url == "http://b:15672/api/health/checks/alarms/"


@pytest.mark.asyncio
async def test_rabbitmq_monitor_missing_nodes():
    monitor = types.SimpleNamespace(
        rabbitmqNodes="[]",
        rabbitmqUsername="",
        rabbitmqPassword="",
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    with pytest.raises(ValueError):
        await Rabbitmq().check(monitor, hb)


@pytest.mark.asyncio
async def test_rabbitmq_monitor_connection_failure(monkeypatch):
    def failing_factory(*a, **k):
        class Boom:
            async def __aenter__(self):
                raise RuntimeError("connection refused")

            async def __aexit__(self, *a):
                return None

        return Boom()

    monkeypatch.setattr(rabbitmq_mod.httpx, "AsyncClient", failing_factory)
    monitor = types.SimpleNamespace(
        rabbitmqNodes=json.dumps(["http://rabbit.local:15672"]),
        rabbitmqUsername="u",
        rabbitmqPassword="p",
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    await Rabbitmq().check(monitor, hb)
    assert hb.status == 0
    assert "connection refused" in hb.msg
