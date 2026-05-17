import types
import pytest

import server.monitor_types.mongodb as mongodb_mod
from server.monitor_types.mongodb import Mongodb


class FakeDatabase:
    def __init__(self, response):
        self.response = response
        self.last_command = None

    def command(self, command):
        self.last_command = command
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeMongoClient:
    last_instance = None

    def __init__(self, conn, serverSelectionTimeoutMS=None, response=None):
        self.conn = conn
        self.timeout_ms = serverSelectionTimeoutMS
        self._db = FakeDatabase(response if response is not None else {"ok": 1.0})
        self.closed = False
        FakeMongoClient.last_instance = self

    def get_database(self):
        return self._db

    def close(self):
        self.closed = True


@pytest.fixture
def fake_client(monkeypatch):
    def factory(response):
        def _client(conn, serverSelectionTimeoutMS=None):
            return FakeMongoClient(conn, serverSelectionTimeoutMS, response=response)
        monkeypatch.setattr(mongodb_mod, "MongoClient", _client)
        return _client
    return factory


@pytest.mark.asyncio
async def test_mongodb_monitor_success(fake_client):
    fake_client({"ok": 1.0})
    monitor = types.SimpleNamespace(databaseConnectionString="mongodb://localhost:27017")
    hb = types.SimpleNamespace(status=None, msg=None)
    await Mongodb().check(monitor, hb)
    assert hb.status == 1
    assert "successfully" in hb.msg
    assert FakeMongoClient.last_instance.closed is True
    assert FakeMongoClient.last_instance._db.last_command == {"ping": 1}


@pytest.mark.asyncio
async def test_mongodb_monitor_missing_conn():
    monitor = types.SimpleNamespace(databaseConnectionString=None)
    hb = types.SimpleNamespace(status=None, msg=None)
    with pytest.raises(ValueError):
        await Mongodb().check(monitor, hb)


@pytest.mark.asyncio
async def test_mongodb_monitor_invalid_query():
    monitor = types.SimpleNamespace(
        databaseConnectionString="mongodb://localhost:27017",
        databaseQuery="not-json",
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    with pytest.raises(ValueError):
        await Mongodb().check(monitor, hb)


@pytest.mark.asyncio
async def test_mongodb_monitor_command_failure(fake_client):
    fake_client(RuntimeError("connection refused"))
    monitor = types.SimpleNamespace(databaseConnectionString="mongodb://localhost:27017")
    hb = types.SimpleNamespace(status=None, msg=None)
    await Mongodb().check(monitor, hb)
    assert hb.status == 0
    assert "connection refused" in hb.msg
    assert FakeMongoClient.last_instance.closed is True


@pytest.mark.asyncio
async def test_mongodb_monitor_custom_query(fake_client):
    fake_client({"version": "7.0.0"})
    monitor = types.SimpleNamespace(
        databaseConnectionString="mongodb://localhost:27017",
        databaseQuery='{"serverStatus": 1}',
    )
    hb = types.SimpleNamespace(status=None, msg=None)
    await Mongodb().check(monitor, hb)
    assert hb.status == 1
    assert FakeMongoClient.last_instance._db.last_command == {"serverStatus": 1}
