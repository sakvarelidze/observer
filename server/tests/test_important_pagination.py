import os
import sys
import asyncio
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from server.server import create_app
from server.db import models


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    if db_path.is_absolute():
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
    else:
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    app = create_app()
    with TestClient(app) as c:
        token = c.post("/api/setup", json={"username": "admin", "password": "admin"}).json()["token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def _seed_events(monitor_id: int, count: int):
    async def _inner():
        from server.db.database import async_session_maker
        async with async_session_maker() as session:
            for i in range(count):
                session.add(models.ImportantHeartbeat(monitor_id=monitor_id, message=f"evt{i}"))
            await session.commit()
    asyncio.run(_inner())


def test_important_pagination_and_count(client, monkeypatch):
    # add_monitor schedules an async _run_single_check that records an
    # initial-probe ImportantHeartbeat; suppress it so the seeded event
    # count and ordering are deterministic.
    import server.routers.api as api_mod

    async def _noop(monitor_id):
        return None

    monkeypatch.setattr(api_mod, "_run_single_check", _noop)

    monitor = {"id": 1, "name": "A", "url": "http://example.com", "push_token": "tok"}
    client.post("/api/monitors", json=monitor)
    _seed_events(1, 5)

    res = client.get("/api/monitors/1/important-heartbeats", params={"offset": 1, "limit": 2})
    assert res.status_code == 200
    data = res.json()["data"]
    assert [d["message"] for d in data] == ["evt1", "evt2"]

    res = client.get("/api/monitors/1/important-heartbeats/count")
    assert res.status_code == 200
    assert res.json()["count"] == 5

    res = client.get("/api/important-heartbeats/count")
    assert res.status_code == 200
    assert res.json()["count"] == 5

