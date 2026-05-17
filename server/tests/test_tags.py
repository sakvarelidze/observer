import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from server.server import create_app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    if db_path.is_absolute():
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
    else:
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    app = create_app()
    with TestClient(app) as c:
        token = c.post(
            "/api/setup", json={"username": "admin", "password": "admin"}
        ).json()["token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def test_tags_crud(client):
    res = client.get("/api/tags")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["tags"] == []

    payload = {"name": "prod", "color": "#ff0000"}
    res = client.post("/api/tags", json=payload)
    assert res.status_code == 200
    tag_id = res.json()["tag"]["id"]

    res = client.get("/api/tags")
    tags = res.json()["tags"]
    assert any(t["id"] == tag_id for t in tags)

    edit_payload = {"name": "production", "color": "#00ff00"}
    res = client.post(f"/api/tags/{tag_id}", json=edit_payload)
    assert res.status_code == 200

    res = client.get("/api/tags")
    tags = res.json()["tags"]
    assert any(t["name"] == "production" and t["color"] == "#00ff00" for t in tags)

    res = client.delete(f"/api/tags/{tag_id}")
    assert res.status_code == 200

    res = client.get("/api/tags")
    assert all(t["id"] != tag_id for t in res.json()["tags"])


def test_monitor_tag_endpoints(client):
    # create a monitor
    monitor = {"id": 1, "name": "A", "url": "http://example.com", "push_token": "tok"}
    res = client.post("/api/monitors", json=monitor)
    assert res.status_code == 200

    # create a tag
    tag_payload = {"name": "prod", "color": "#ff0000"}
    res = client.post("/api/tags", json=tag_payload)
    tag_id = res.json()["tag"]["id"]

    # assign tag to monitor
    res = client.post("/api/monitor-tags", json={"tagId": tag_id, "monitorId": 1, "value": ""})
    assert res.status_code == 200

    res = client.get("/api/monitor/1")
    assert res.status_code == 200
    data = res.json()["monitor"]
    assert any(t["tag_id"] == tag_id for t in data["tags"])

    # remove tag
    res = client.delete(f"/api/monitor-tags", params={"tag_id": tag_id, "monitor_id": 1, "value": ""})
    assert res.status_code == 200

    res = client.get("/api/monitor/1")
    assert res.status_code == 200
    data = res.json()["monitor"]
    assert not data["tags"]


def test_duplicate_monitor_tag_rejected(client):
    monitor = {"id": 1, "name": "A", "url": "http://example.com", "push_token": "tok"}
    client.post("/api/monitors", json=monitor)
    tag_payload = {"name": "prod", "color": "#ff0000"}
    res = client.post("/api/tags", json=tag_payload)
    tag_id = res.json()["tag"]["id"]

    payload = {"tagId": tag_id, "monitorId": 1, "value": ""}
    res = client.post("/api/monitor-tags", json=payload)
    assert res.status_code == 200

    res = client.post("/api/monitor-tags", json=payload)
    assert res.status_code == 200

    res = client.get("/api/monitor/1")
    assert res.status_code == 200
    data = res.json()["monitor"]
    assert sum(1 for t in data["tags"] if t["tag_id"] == tag_id) == 1
