import os
import sys
import asyncio
import pytest
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from fastapi.testclient import TestClient
from server.server import create_app
from server.notification_providers import get_provider
from server.db import init_db, database, models


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

class DummyClient:
    def __init__(self, *args, **kwargs):
        self.url = None
        self.params = None
        self.verify = kwargs.get("verify", True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def get(self, url, params=None):
        self.url = url
        self.params = params
        class Res:
            def raise_for_status(self):
                pass
        return Res()

class DummyPostClient(DummyClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = None
        self.headers = None
        self.data = None
        self.auth = None

    async def post(self, url, json=None, content=None, headers=None, data=None, auth=None):
        self.url = url
        self.params = json
        self.content = content
        self.headers = headers
        self.data = data
        self.auth = auth
        class Res:
            def raise_for_status(self):
                pass
        return Res()

@pytest.mark.asyncio
async def test_telegram_send(monkeypatch):
    provider = get_provider("telegram")
    dummy = DummyClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    res = await provider.send({"server_url": "http://test", "bot_token": "t", "chat_id": 1}, "hi")
    assert res == "Sent Successfully."
    assert dummy.url.endswith("/bott/sendMessage")

@pytest.mark.asyncio
async def test_telegram_send_ignore_tls(monkeypatch):
    provider = get_provider("telegram")
    captured = {}

    class CaptureClient(DummyClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured["verify"] = kwargs.get("verify")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: CaptureClient(*a, **k))

    await provider.send({"server_url": "http://test", "bot_token": "t", "chat_id": 1, "ignore_tls": True}, "hi")
    assert captured["verify"] is False

@pytest.mark.asyncio
async def test_discord_send(monkeypatch):
    provider = get_provider("discord")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    res = await provider.send({"webhook_url": "http://discord"}, "hello")
    assert res == "Sent Successfully."
    assert dummy.url == "http://discord"
    assert "embeds" in dummy.params
    embed = dummy.params["embeds"][0]
    assert embed["title"] == "🔴 Monitor went DOWN"
    assert embed["color"] == int("E81123", 16)


@pytest.mark.asyncio
async def test_discord_send_legacy_key(monkeypatch):
    provider = get_provider("discord")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    res = await provider.send({"discord_webhook_url": "http://discord"}, "hello")
    assert res == "Sent Successfully."
    assert dummy.url == "http://discord"
    embed = dummy.params["embeds"][0]
    assert embed["title"] == "🔴 Monitor went DOWN"


@pytest.mark.asyncio
async def test_discord_send_with_monitor(monkeypatch):
    provider = get_provider("discord")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "BPN", "type": "http", "url": "https://www.bpn.ge/"}
    heartbeat = {"event": "down", "msg": "Connection refused", "ping": 3000}
    await provider.send({"webhook_url": "http://discord"}, "hi", monitor, heartbeat)
    embed = dummy.params["embeds"][0]
    assert embed["title"] == "🔴 BPN went DOWN"
    assert embed["url"] == "https://www.bpn.ge/"
    assert embed["description"] == "Connection refused"
    field_names = {f["name"] for f in embed["fields"]}
    assert {"Type", "Response"} == field_names

@pytest.mark.asyncio
async def test_discord_missing_webhook(monkeypatch):
    provider = get_provider("discord")
    with pytest.raises(ValueError) as exc:
        await provider.send({}, "hello")
    assert "webhook_url" in str(exc.value)


@pytest.mark.asyncio
async def test_teams_send(monkeypatch):
    provider = get_provider("teams")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    res = await provider.send({"webhook_url": "http://teams"}, "hi")
    assert res == "Sent Successfully."
    assert dummy.url == "http://teams"
    assert dummy.params["@type"] == "MessageCard"
    assert dummy.params["themeColor"] == "E81123"
    assert dummy.params["summary"] == "Monitor went DOWN"
    section = dummy.params["sections"][0]
    assert section["activityTitle"] == "🔴 **Monitor went DOWN**"


@pytest.mark.asyncio
async def test_teams_send_with_status(monkeypatch):
    provider = get_provider("teams")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "Demo"}
    heartbeat = {"status": 1}
    res = await provider.send({"webhook_url": "http://teams"}, "Up", monitor, heartbeat)
    assert res == "Sent Successfully."
    assert dummy.params["themeColor"] == "16C60C"
    section = dummy.params["sections"][0]
    assert section["activityTitle"] == "🟢 **Demo came back UP**"


@pytest.mark.asyncio
async def test_teams_send_paused(monkeypatch):
    provider = get_provider("teams")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "Demo"}
    heartbeat = {"event": "paused"}
    res = await provider.send({"webhook_url": "http://teams"}, "Paused", monitor, heartbeat)
    assert res == "Sent Successfully."
    assert dummy.params["themeColor"] == "FFB900"
    section = dummy.params["sections"][0]
    assert section["activityTitle"] == "⏸ **Demo was PAUSED**"


@pytest.mark.asyncio
async def test_teams_send_with_monitor(monkeypatch):
    provider = get_provider("teams")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "BPN", "type": "http", "url": "https://www.bpn.ge/"}
    heartbeat = {"event": "down", "msg": "Connection refused", "ping": 3000}
    await provider.send({"webhook_url": "http://teams"}, "hi", monitor, heartbeat)
    section = dummy.params["sections"][0]
    assert section["activitySubtitle"] == "[https://www.bpn.ge/](https://www.bpn.ge/)"
    assert section["text"] == "Connection refused"
    fact_names = {f["name"] for f in section["facts"]}
    assert {"Type", "Response"} == fact_names


@pytest.mark.asyncio
async def test_slack_send_blocks(monkeypatch):
    provider = get_provider("slack")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "BPN", "type": "http", "url": "https://www.bpn.ge/"}
    heartbeat = {"event": "down", "msg": "Connection refused", "ping": 3000}
    res = await provider.send({"webhook_url": "http://slack"}, "hi", monitor, heartbeat)
    assert res == "Sent Successfully."
    assert dummy.url == "http://slack"
    assert dummy.params["text"].startswith("🔴 BPN went DOWN")
    attach = dummy.params["attachments"][0]
    assert attach["color"] == "#E81123"
    blocks = attach["blocks"]
    assert blocks[0]["type"] == "header"
    assert blocks[0]["text"]["text"] == "🔴 BPN went DOWN"
    section = next(b for b in blocks if b["type"] == "section" and "fields" in b)
    field_text = "\n".join(f["text"] for f in section["fields"])
    assert "*Type*" in field_text and "HTTP" in field_text
    assert "*Response*" in field_text and "3000ms" in field_text
    context = next(b for b in blocks if b["type"] == "context")
    assert "Connection refused" in context["elements"][0]["text"]


@pytest.mark.asyncio
async def test_slack_send_test_event(monkeypatch):
    provider = get_provider("slack")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "Observer", "type": "http", "url": ""}
    heartbeat = {"event": "test", "status": 1}
    await provider.send({"webhook_url": "http://slack"}, "Test", monitor, heartbeat)
    attach = dummy.params["attachments"][0]
    assert attach["color"] == "#3B82F6"
    blocks = attach["blocks"]
    assert blocks[0]["text"]["text"].startswith("🔔 Observer test alert")
    # No fields/context block in test mode — just header + sample-message section
    assert all(b.get("type") != "context" for b in blocks)


@pytest.mark.asyncio
async def test_ntfy_send(monkeypatch):
    provider = get_provider("ntfy")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "BPN", "type": "http", "url": "https://www.bpn.ge/"}
    heartbeat = {"event": "down", "msg": "Connection refused", "ping": 3000}
    res = await provider.send(
        {"ntfyserverurl": "https://ntfy.sh", "ntfytopic": "alerts"},
        "hi", monitor, heartbeat,
    )
    assert res == "Sent Successfully."
    assert dummy.url == "https://ntfy.sh/alerts"
    assert dummy.headers["Title"] == "BPN went DOWN"
    assert dummy.headers["Priority"] == "5"
    assert dummy.headers["Tags"] == "rotating_light"
    assert dummy.headers["Click"] == "https://www.bpn.ge/"
    body = dummy.content.decode("utf-8") if isinstance(dummy.content, bytes) else dummy.content
    assert "Connection refused" in body
    assert "Response: 3000ms" in body


@pytest.mark.asyncio
async def test_ntfy_missing_topic(monkeypatch):
    provider = get_provider("ntfy")
    with pytest.raises(ValueError) as exc:
        await provider.send({"ntfyserverurl": "https://ntfy.sh"}, "hi")
    assert "topic" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_ntfy_test_event(monkeypatch):
    provider = get_provider("ntfy")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "Observer", "type": "http", "url": ""}
    heartbeat = {"event": "test", "status": 1}
    await provider.send(
        {"ntfyserverurl": "https://ntfy.sh", "ntfytopic": "alerts"},
        "Test", monitor, heartbeat,
    )
    assert dummy.headers["Priority"] == "3"
    assert dummy.headers["Tags"] == "bell"
    assert dummy.headers["Title"] == "Observer test alert"
    # No URL → no Click header
    assert "Click" not in dummy.headers


@pytest.mark.asyncio
async def test_pagerduty_trigger_on_down(monkeypatch):
    provider = get_provider("pagerduty")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"id": 42, "name": "BPN", "type": "http", "url": "https://www.bpn.ge/"}
    heartbeat = {"event": "down", "msg": "Connection refused", "ping": 3000}
    res = await provider.send(
        {"pagerduty_integration_key": "rk-secret"}, "hi", monitor, heartbeat,
    )
    assert res == "Sent Successfully."
    assert dummy.url == "https://events.pagerduty.com/v2/enqueue"
    assert dummy.params["routing_key"] == "rk-secret"
    assert dummy.params["event_action"] == "trigger"
    assert dummy.params["dedup_key"] == "observer-monitor-42"
    pl = dummy.params["payload"]
    assert pl["summary"] == "BPN went DOWN"
    assert pl["severity"] == "error"
    assert pl["source"] == "BPN"
    assert pl["custom_details"]["message"] == "Connection refused"
    assert pl["custom_details"]["response_ms"] == 3000


@pytest.mark.asyncio
async def test_pagerduty_resolve_on_up(monkeypatch):
    provider = get_provider("pagerduty")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"id": 42, "name": "BPN"}
    heartbeat = {"event": "up", "status": 1, "ping": 142}
    await provider.send(
        {"pagerduty_integration_key": "rk-secret"}, "hi", monitor, heartbeat,
    )
    assert dummy.params["event_action"] == "resolve"
    assert dummy.params["dedup_key"] == "observer-monitor-42"
    # 'resolve' actions don't carry a payload block.
    assert "payload" not in dummy.params


@pytest.mark.asyncio
async def test_pagerduty_test_uses_info_severity(monkeypatch):
    provider = get_provider("pagerduty")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "Observer", "type": "http", "url": ""}
    heartbeat = {"event": "test", "status": 1}
    await provider.send(
        {"pagerduty_integration_key": "rk-secret"}, "Test", monitor, heartbeat,
    )
    assert dummy.params["event_action"] == "trigger"
    # Info severity so the test doesn't page on-call.
    assert dummy.params["payload"]["severity"] == "info"


@pytest.mark.asyncio
async def test_pagerduty_missing_key(monkeypatch):
    provider = get_provider("pagerduty")
    with pytest.raises(ValueError) as exc:
        await provider.send({}, "hi")
    assert "integration_key" in str(exc.value)


@pytest.mark.asyncio
async def test_twilio_send(monkeypatch):
    provider = get_provider("twilio")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "BPN", "type": "http", "url": "https://www.bpn.ge/"}
    heartbeat = {"event": "down", "msg": "Connection refused", "ping": 3000}
    res = await provider.send(
        {
            "account_sid": "AC123",
            "auth_token": "secret",
            "from_number": "+15550000001",
            "to_number": "+15550000002",
        },
        "hi", monitor, heartbeat,
    )
    assert res == "Sent Successfully."
    assert dummy.url == "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"
    assert dummy.auth == ("AC123", "secret")
    assert dummy.data["From"] == "+15550000001"
    assert dummy.data["To"] == "+15550000002"
    body = dummy.data["Body"]
    assert body.startswith("[DOWN] BPN")
    assert "Connection refused" in body


@pytest.mark.asyncio
async def test_twilio_test_event_body(monkeypatch):
    provider = get_provider("twilio")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "Observer", "type": "http", "url": ""}
    heartbeat = {"event": "test", "status": 1}
    await provider.send(
        {
            "account_sid": "AC123",
            "auth_token": "secret",
            "from_number": "+15550000001",
            "to_number": "+15550000002",
        },
        "Test", monitor, heartbeat,
    )
    body = dummy.data["Body"]
    assert body.startswith("[TEST]")
    assert "Observer" in body


@pytest.mark.asyncio
async def test_twilio_missing_fields(monkeypatch):
    provider = get_provider("twilio")
    with pytest.raises(ValueError) as exc:
        await provider.send({"account_sid": "AC123"}, "hi")
    msg = str(exc.value)
    assert "auth_token" in msg
    assert "from_number" in msg
    assert "to_number" in msg


@pytest.mark.asyncio
async def test_grafana_oncall_alerting_on_down(monkeypatch):
    provider = get_provider("grafana-oncall")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"id": 42, "name": "BPN", "type": "http", "url": "https://www.bpn.ge/"}
    heartbeat = {"event": "down", "msg": "Connection refused", "ping": 3000}
    res = await provider.send(
        {"url": "https://oncall.grafana.com/integrations/v1/abc/"},
        "hi", monitor, heartbeat,
    )
    assert res == "Sent Successfully."
    assert dummy.url == "https://oncall.grafana.com/integrations/v1/abc/"
    assert dummy.params["alert_uid"] == "observer-monitor-42"
    assert dummy.params["state"] == "alerting"
    assert dummy.params["title"] == "BPN went DOWN"
    assert dummy.params["message"] == "Connection refused"
    assert dummy.params["link_to_upstream_details"] == "https://www.bpn.ge/"
    assert dummy.params["monitor_type"] == "HTTP"
    assert dummy.params["response_ms"] == 3000


@pytest.mark.asyncio
async def test_grafana_oncall_resolves_on_up(monkeypatch):
    provider = get_provider("grafana-oncall")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"id": 42, "name": "BPN"}
    heartbeat = {"event": "up", "status": 1, "ping": 142}
    await provider.send(
        {"url": "https://oncall.grafana.com/integrations/v1/abc/"},
        "hi", monitor, heartbeat,
    )
    assert dummy.params["state"] == "ok"
    assert dummy.params["alert_uid"] == "observer-monitor-42"


@pytest.mark.asyncio
async def test_grafana_oncall_test_event(monkeypatch):
    provider = get_provider("grafana-oncall")
    dummy = DummyPostClient()
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: dummy)
    monitor = {"name": "Observer", "type": "http", "url": ""}
    heartbeat = {"event": "test", "status": 1}
    await provider.send(
        {"url": "https://oncall.grafana.com/integrations/v1/abc/"},
        "Test", monitor, heartbeat,
    )
    assert dummy.params["state"] == "alerting"
    assert dummy.params["title"] == "Observer test alert"
    assert dummy.params["alert_uid"] == "observer-test"


@pytest.mark.asyncio
async def test_grafana_oncall_missing_url(monkeypatch):
    provider = get_provider("grafana-oncall")
    with pytest.raises(ValueError) as exc:
        await provider.send({}, "hi")
    assert "url" in str(exc.value).lower()


def _set_db_url(tmp_path, name):
    """Pin DATABASE_URL to a fresh sqlite file for an async test."""
    db_path = tmp_path / name
    if db_path.is_absolute():
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
    else:
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"


@pytest.mark.asyncio
async def test_heartbeat_pruner_deletes_old_rows(tmp_path):
    """Rows older than keepDataPeriodDays are pruned; recent rows stay."""
    import datetime
    from sqlalchemy import select as _select
    from server.server import _prune_old_heartbeats

    _set_db_url(tmp_path, "prune.db")
    await init_db()

    async with database.async_session_maker() as session:
        session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
        now = datetime.datetime.utcnow()
        # 10 days old (kept), 200 days old (pruned at default 180-day retention)
        session.add(models.Heartbeat(monitor_id=1, status=1, time=now - datetime.timedelta(days=10), msg="recent"))
        session.add(models.Heartbeat(monitor_id=1, status=0, time=now - datetime.timedelta(days=200), msg="ancient"))
        await session.commit()

    deleted = await _prune_old_heartbeats()
    assert deleted == 1

    async with database.async_session_maker() as session:
        res = await session.execute(_select(models.Heartbeat))
        rows = [r.msg for r in res.scalars().all()]
    assert rows == ["recent"]


@pytest.mark.asyncio
async def test_heartbeat_pruner_honors_setting(tmp_path):
    """Custom keepDataPeriodDays is read from the settings table."""
    import datetime, json as _json
    from server.server import _prune_old_heartbeats

    _set_db_url(tmp_path, "prune2.db")
    await init_db()

    async with database.async_session_maker() as session:
        session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
        session.add(models.Setting(key="keepDataPeriodDays", value=_json.dumps(7)))
        now = datetime.datetime.utcnow()
        # With a 7-day window, the 10-day-old row should now be pruned.
        session.add(models.Heartbeat(monitor_id=1, status=1, time=now - datetime.timedelta(days=2), msg="kept"))
        session.add(models.Heartbeat(monitor_id=1, status=0, time=now - datetime.timedelta(days=10), msg="pruned"))
        await session.commit()

    assert await _prune_old_heartbeats() == 1


@pytest.mark.asyncio
async def test_heartbeat_pruner_zero_days_is_noop(tmp_path):
    """A nonsensical retention value doesn't wipe everything."""
    import datetime, json as _json
    from server.server import _prune_old_heartbeats

    _set_db_url(tmp_path, "prune3.db")
    await init_db()

    async with database.async_session_maker() as session:
        session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
        session.add(models.Setting(key="keepDataPeriodDays", value=_json.dumps(0)))
        now = datetime.datetime.utcnow()
        session.add(models.Heartbeat(monitor_id=1, status=1, time=now, msg="now"))
        session.add(models.Heartbeat(monitor_id=1, status=0, time=now - datetime.timedelta(days=10000), msg="ancient"))
        await session.commit()

    assert await _prune_old_heartbeats() == 0


@pytest.mark.asyncio
async def test_load_last_heartbeats_returns_latest_per_monitor(tmp_path):
    """The greatest-time-per-group query returns the most recent
    heartbeat per monitor in a single round-trip — replacing the old N+1
    `SELECT … LIMIT 1` per monitor."""
    import datetime
    from server.server import _load_last_heartbeats

    _set_db_url(tmp_path, "lhb.db")
    await init_db()

    async with database.async_session_maker() as session:
        for mid, name in [(1, "a"), (2, "b"), (3, "c")]:
            session.add(models.Monitor(id=mid, name=name, type="http", url="http://x", interval=60))
        now = datetime.datetime.utcnow()

        # Monitor 1: three heartbeats — newest is "1-newest"
        session.add(models.Heartbeat(monitor_id=1, status=1, time=now - datetime.timedelta(minutes=10), msg="1-old"))
        session.add(models.Heartbeat(monitor_id=1, status=0, time=now - datetime.timedelta(minutes=5), msg="1-mid"))
        session.add(models.Heartbeat(monitor_id=1, status=1, time=now, msg="1-newest"))

        # Monitor 2: one heartbeat
        session.add(models.Heartbeat(monitor_id=2, status=1, time=now - datetime.timedelta(seconds=30), msg="2-only"))

        # Monitor 3: no heartbeats — should NOT appear in the result
        await session.commit()

        out = await _load_last_heartbeats(session, [1, 2, 3])

    assert set(out.keys()) == {1, 2}
    assert out[1].msg == "1-newest"
    assert out[2].msg == "2-only"


@pytest.mark.asyncio
async def test_load_last_heartbeats_empty_input(tmp_path):
    """Short-circuits to {} when no monitor IDs are passed."""
    from server.server import _load_last_heartbeats

    _set_db_url(tmp_path, "lhb_empty.db")
    await init_db()

    async with database.async_session_maker() as session:
        out = await _load_last_heartbeats(session, [])
        assert out == {}


@pytest.mark.asyncio
async def test_load_last_heartbeats_tiebreaks_on_id(tmp_path):
    """Two heartbeats sharing an exact time pick the one with the
    higher id (most recent insert)."""
    import datetime
    from server.server import _load_last_heartbeats

    _set_db_url(tmp_path, "lhb_tie.db")
    await init_db()

    async with database.async_session_maker() as session:
        session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
        ts = datetime.datetime.utcnow()
        # Two rows with the same exact time.
        session.add(models.Heartbeat(monitor_id=1, status=1, time=ts, msg="first"))
        session.add(models.Heartbeat(monitor_id=1, status=0, time=ts, msg="second"))
        await session.commit()

        out = await _load_last_heartbeats(session, [1])

    # Higher id (= second insert) wins.
    assert out[1].msg == "second"


def _ping_stats_test_setup(tmp_path, name):
    """Boot a fresh app, create the admin, return an authenticated TestClient."""
    from server.server import create_app
    from fastapi.testclient import TestClient

    db_path = tmp_path / name
    if db_path.is_absolute():
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
    else:
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    client = TestClient(create_app())
    client.__enter__()
    token = client.post("/api/setup", json={"username": "a", "password": "b"}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_ping_stats_buckets_default_24h(tmp_path):
    """Endpoint returns 144 ten-minute buckets for the 24h view, with
    sparse data populating the buckets that contain probes."""
    import datetime

    client = _ping_stats_test_setup(tmp_path, "ping_stats.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
                now = datetime.datetime.utcnow()
                # 3 probes inside the last 10-min bucket, 2 inside the
                # 50-60-min-ago window (separate bucket).
                for offset_min, ping in [(2, 100), (3, 200), (4, 150), (52, 300), (55, 400)]:
                    session.add(models.Heartbeat(
                        monitor_id=1, status=1, ping=ping,
                        time=now - datetime.timedelta(minutes=offset_min),
                    ))
                await session.commit()

        asyncio.run(seed())
        body = client.get("/api/monitors/1/ping-stats").json()
    finally:
        client.__exit__(None, None, None)

    assert body["ok"] is True
    assert body["period"] == "24h"
    assert body["bucket_seconds"] == 600
    assert len(body["buckets"]) == 144

    # Last bucket (most recent 10 minutes) contains the 3 fresh probes.
    last = body["buckets"][-1]
    assert last["count"] == 3
    assert last["avg"] == 150
    assert last["max"] == 200

    # Aggregate summary covers all 5 probes.
    assert body["summary"]["count"] == 5
    assert body["summary"]["max"] == 400


def test_ping_stats_unknown_period_falls_back_to_24h(tmp_path):
    client = _ping_stats_test_setup(tmp_path, "ping_stats_fb.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
                await session.commit()
        asyncio.run(seed())
        body = client.get("/api/monitors/1/ping-stats?period=garbage").json()
    finally:
        client.__exit__(None, None, None)
    assert body["period"] == "24h"
    assert len(body["buckets"]) == 144


def test_uptime_daily_buckets(tmp_path):
    """Daily uptime endpoint returns one bucket per day with uptime%
    computed over status=1 / total probes."""
    import datetime

    client = _ping_stats_test_setup(tmp_path, "uptime_daily.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
                now = datetime.datetime.utcnow()
                # Today: 4 probes, 3 up = 75% uptime
                for offset_min, status in [(2, 1), (3, 1), (4, 1), (5, 0)]:
                    session.add(models.Heartbeat(
                        monitor_id=1, status=status, ping=100,
                        time=now - datetime.timedelta(minutes=offset_min),
                    ))
                # 1 day ago: 2 probes, 2 up = 100% uptime
                yesterday = now - datetime.timedelta(days=1)
                session.add(models.Heartbeat(monitor_id=1, status=1, ping=100, time=yesterday))
                session.add(models.Heartbeat(monitor_id=1, status=1, ping=100, time=yesterday - datetime.timedelta(minutes=1)))
                await session.commit()
        asyncio.run(seed())
        body = client.get("/api/monitors/1/uptime-daily?days=7").json()
    finally:
        client.__exit__(None, None, None)

    assert body["ok"] is True
    assert len(body["buckets"]) == 7
    # Last bucket is today
    today = body["buckets"][-1]
    assert today["uptime"] == 75.0
    assert today["probes"] == 4
    assert today["down"] == 1
    # Day-2 from end is yesterday
    yesterday = body["buckets"][-2]
    assert yesterday["uptime"] == 100.0
    assert yesterday["probes"] == 2
    # Earlier days have null uptime
    assert body["buckets"][0]["uptime"] is None
    assert body["buckets"][0]["probes"] == 0
    # Summary covers all probes (6 total, 5 up)
    assert body["summary"]["probes"] == 6
    assert body["summary"]["down"] == 1


def test_slow_message_format_includes_threshold():
    """Formatter recognises event='slow' and surfaces the configured
    threshold alongside the actual response time."""
    from server.notifications.message_formatter import build_status_message

    fmt = build_status_message(
        event="slow",
        monitor={"name": "BPN", "type": "http", "url": "https://www.bpn.ge/"},
        heartbeat={"event": "slow", "ping": 5234, "threshold_ms": 1000, "msg": ""},
    )
    assert fmt["title"] == "BPN responding slowly"
    assert fmt["color_hex"] == "#FFB900"  # amber
    assert "Response: 5234ms" in fmt["text"]
    assert "Threshold: 1000ms" in fmt["text"]


def test_incidents_groups_consecutive_down_runs(tmp_path):
    """Two separated DOWN runs produce two distinct incidents; the
    closing UP probe of each run becomes its ended_at."""
    import datetime

    client = _ping_stats_test_setup(tmp_path, "incidents.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
                base = datetime.datetime.utcnow() - datetime.timedelta(hours=4)
                # UP UP DOWN DOWN DOWN UP UP DOWN DOWN UP — two incidents.
                seq = [
                    (0, 1), (1, 1),
                    (2, 0), (3, 0), (4, 0),       # incident A: 2 min long
                    (5, 1), (6, 1),
                    (7, 0), (8, 0),                # incident B: 1 min long
                    (9, 1),
                ]
                for offset, status in seq:
                    session.add(models.Heartbeat(
                        monitor_id=1, status=status, ping=100,
                        msg=("oops" if status == 0 else "ok"),
                        time=base + datetime.timedelta(minutes=offset),
                    ))
                await session.commit()
        asyncio.run(seed())
        body = client.get("/api/monitors/1/incidents?period=24h").json()
    finally:
        client.__exit__(None, None, None)

    assert body["ok"] is True
    incs = body["incidents"]
    # Newest first.
    assert len(incs) == 2
    assert incs[0]["ongoing"] is False
    assert incs[1]["ongoing"] is False
    # Older incident has 3 down probes (2-3-4 min offsets), newer has 2.
    older = incs[1]
    newer = incs[0]
    assert older["probe_count"] == 3
    assert newer["probe_count"] == 2
    # Duration is end-of-down → start-of-down, in seconds. Older: 5 - 2 = 3 min.
    assert older["duration_seconds"] == 180
    assert newer["duration_seconds"] == 120
    # Error message captured from the first DOWN probe of the run.
    assert older["msg"] == "oops"
    # Summary aggregates total downtime across both incidents.
    assert body["summary"]["count"] == 2
    assert body["summary"]["total_downtime_seconds"] == 300
    assert body["summary"]["ongoing"] is False


def test_incidents_pending_does_not_split_a_run(tmp_path):
    """A PENDING probe in the middle of a DOWN run is ignored — the
    incident stays as one continuous run, not two."""
    import datetime

    client = _ping_stats_test_setup(tmp_path, "incidents_pending.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
                base = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
                # UP DOWN PENDING DOWN UP — one incident, not two.
                seq = [
                    (0, 1), (1, 0), (2, 2), (3, 0), (4, 1),
                ]
                for offset, status in seq:
                    session.add(models.Heartbeat(
                        monitor_id=1, status=status, ping=100,
                        time=base + datetime.timedelta(minutes=offset),
                    ))
                await session.commit()
        asyncio.run(seed())
        body = client.get("/api/monitors/1/incidents?period=24h").json()
    finally:
        client.__exit__(None, None, None)

    incs = body["incidents"]
    assert len(incs) == 1
    assert incs[0]["probe_count"] == 2  # only the two DOWNs counted, PENDING ignored


def test_incidents_ongoing_is_marked(tmp_path):
    """A DOWN run with no closing UP shows up as ongoing with no ended_at."""
    import datetime

    client = _ping_stats_test_setup(tmp_path, "incidents_ongoing.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
                base = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
                # UP DOWN DOWN — still down at request time.
                seq = [(0, 1), (1, 0), (2, 0)]
                for offset, status in seq:
                    session.add(models.Heartbeat(
                        monitor_id=1, status=status, ping=100, msg="boom",
                        time=base + datetime.timedelta(minutes=offset),
                    ))
                await session.commit()
        asyncio.run(seed())
        body = client.get("/api/monitors/1/incidents?period=24h").json()
    finally:
        client.__exit__(None, None, None)

    incs = body["incidents"]
    assert len(incs) == 1
    assert incs[0]["ongoing"] is True
    assert incs[0]["ended_at"] is None
    assert incs[0]["probe_count"] == 2
    assert body["summary"]["ongoing"] is True


def test_uptime_badge_renders_svg_with_correct_color(tmp_path):
    """Badge endpoint returns an SVG without auth, colour-banded by
    uptime percentage."""
    import datetime
    from server.badges import COLOR_OK, COLOR_DEGRADED, COLOR_DOWN, COLOR_UNKNOWN

    client = _ping_stats_test_setup(tmp_path, "badge.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                # Three monitors at different uptime bands.
                session.add(models.Monitor(id=1, name="ok", type="http", url="http://x", interval=60))
                session.add(models.Monitor(id=2, name="degraded", type="http", url="http://x", interval=60))
                session.add(models.Monitor(id=3, name="down", type="http", url="http://x", interval=60))
                session.add(models.Monitor(id=4, name="empty", type="http", url="http://x", interval=60))
                now = datetime.datetime.utcnow()
                # Monitor 1: 100/100 = 100% (OK)
                for i in range(100):
                    session.add(models.Heartbeat(monitor_id=1, status=1, ping=100,
                        time=now - datetime.timedelta(minutes=i)))
                # Monitor 2: 96/100 = 96% (DEGRADED)
                for i in range(96):
                    session.add(models.Heartbeat(monitor_id=2, status=1, ping=100,
                        time=now - datetime.timedelta(minutes=i)))
                for i in range(96, 100):
                    session.add(models.Heartbeat(monitor_id=2, status=0, ping=100,
                        time=now - datetime.timedelta(minutes=i)))
                # Monitor 3: 50/100 = 50% (DOWN)
                for i in range(50):
                    session.add(models.Heartbeat(monitor_id=3, status=1, ping=100,
                        time=now - datetime.timedelta(minutes=i)))
                for i in range(50, 100):
                    session.add(models.Heartbeat(monitor_id=3, status=0, ping=100,
                        time=now - datetime.timedelta(minutes=i)))
                # Monitor 4 has no probes (UNKNOWN)
                await session.commit()
        asyncio.run(seed())

        # Drop auth — badges must work for unauth'd embedders.
        client.headers.pop("Authorization", None)

        for mid, expected_color, expected_value in [
            (1, COLOR_OK, "100.0%"),
            (2, COLOR_DEGRADED, "96.0%"),
            (3, COLOR_DOWN, "50.0%"),
            (4, COLOR_UNKNOWN, "no data"),
        ]:
            r = client.get(f"/api/badges/{mid}.svg")
            assert r.status_code == 200, f"monitor {mid} → {r.status_code}"
            assert r.headers["content-type"] == "image/svg+xml"
            assert "max-age" in r.headers.get("cache-control", "")
            body = r.text
            assert "<svg" in body
            assert expected_color in body, f"monitor {mid} should be {expected_color}"
            assert expected_value in body, f"monitor {mid} should show {expected_value}"
    finally:
        client.__exit__(None, None, None)


def test_uptime_badge_label_override(tmp_path):
    """`?label=foo` overrides the default 'uptime' label."""
    import datetime

    client = _ping_stats_test_setup(tmp_path, "badge_label.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
                session.add(models.Heartbeat(monitor_id=1, status=1, ping=100,
                    time=datetime.datetime.utcnow()))
                await session.commit()
        asyncio.run(seed())
        client.headers.pop("Authorization", None)
        r = client.get("/api/badges/1.svg?label=availability")
        assert r.status_code == 200
        assert "availability" in r.text
    finally:
        client.__exit__(None, None, None)


def test_uptime_badge_unknown_period_falls_back_to_24h(tmp_path):
    client = _ping_stats_test_setup(tmp_path, "badge_period.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
                await session.commit()
        asyncio.run(seed())
        client.headers.pop("Authorization", None)
        r = client.get("/api/badges/1.svg?period=garbage")
        assert r.status_code == 200
        # No data → grey badge with "no data" value.
        from server.badges import COLOR_UNKNOWN
        assert COLOR_UNKNOWN in r.text
    finally:
        client.__exit__(None, None, None)


def test_uptime_daily_excludes_pending_and_maintenance(tmp_path):
    """Regression: pending (status=2) and maintenance (status=3) probes
    used to count toward the 'down' bucket, dragging uptime down on
    healthy monitors with an in-flight probe."""
    import datetime

    client = _ping_stats_test_setup(tmp_path, "uptime_excludes.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
                now = datetime.datetime.utcnow()
                # Today: 4 UP, 1 PENDING, 1 MAINTENANCE — only the
                # four UPs are valid up/down samples, so uptime is 100%.
                for offset_min, status in [(2, 1), (3, 1), (4, 1), (5, 1), (6, 2), (7, 3)]:
                    session.add(models.Heartbeat(
                        monitor_id=1, status=status, ping=100,
                        time=now - datetime.timedelta(minutes=offset_min),
                    ))
                await session.commit()
        asyncio.run(seed())
        body = client.get("/api/monitors/1/uptime-daily?days=7").json()
    finally:
        client.__exit__(None, None, None)

    today = body["buckets"][-1]
    assert today["uptime"] == 100.0
    assert today["probes"] == 4
    assert today["down"] == 0
    assert body["summary"]["probes"] == 4
    assert body["summary"]["uptime"] == 100.0


def test_uptime_daily_clamps_days(tmp_path):
    client = _ping_stats_test_setup(tmp_path, "uptime_clamp.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
                await session.commit()
        asyncio.run(seed())
        # 999 days clamped to 365
        body = client.get("/api/monitors/1/uptime-daily?days=999").json()
        assert len(body["buckets"]) == 365
        # 0 / negative clamped to 1
        body = client.get("/api/monitors/1/uptime-daily?days=0").json()
        assert len(body["buckets"]) == 1
    finally:
        client.__exit__(None, None, None)


def test_ping_stats_30d_uses_8h_buckets(tmp_path):
    client = _ping_stats_test_setup(tmp_path, "ping_stats_30d.db")
    try:
        async def seed():
            async with database.async_session_maker() as session:
                session.add(models.Monitor(id=1, name="m", type="http", url="http://x", interval=60))
                await session.commit()
        asyncio.run(seed())
        body = client.get("/api/monitors/1/ping-stats?period=30d").json()
    finally:
        client.__exit__(None, None, None)
    assert body["period"] == "30d"
    assert body["bucket_seconds"] == 28800
    assert len(body["buckets"]) == 90
    # Empty DB → every bucket null but with a timestamp.
    assert all(b["count"] == 0 for b in body["buckets"])
    assert all(b["avg"] is None for b in body["buckets"])


@pytest.mark.asyncio
async def test_dispatch_notification_async_does_not_block(monkeypatch):
    """A slow webhook must not block the runner — verify the helper
    returns synchronously while the send is still in flight."""
    import time
    from server.server import _dispatch_notification_async, _pending_notification_tasks

    started = asyncio.Event()
    finished = asyncio.Event()

    class Slow:
        async def send(self, *args, **kwargs):
            started.set()
            await asyncio.sleep(0.2)
            finished.set()
            return "ok"

    fake_provider = Slow()
    from server.notification_providers import providers as registry
    monkeypatch.setitem(registry, "fake-slow", fake_provider)

    class FakeNotif:
        type = "fake-slow"
        name = "slow-channel"
        config = "{}"

    t0 = time.monotonic()
    _dispatch_notification_async(FakeNotif(), "msg", {"id": 1}, {})
    elapsed = time.monotonic() - t0
    # Returned synchronously well before the 0.2s sleep finished.
    assert elapsed < 0.05
    # Task is tracked so it isn't garbage-collected mid-flight.
    assert any(not t.done() for t in _pending_notification_tasks)

    # Yield so the spawned task gets a chance to run.
    await started.wait()
    await finished.wait()


def test_notification_test_endpoint(client, monkeypatch):
    from server.notification_providers import teams

    async def fake_send(self, notification, message, monitor=None, heartbeat=None):
        return "ok"

    monkeypatch.setattr(teams.TeamsProvider, "send", fake_send)
    payload = {"name": "Teams", "type": "teams", "config": {"webhook_url": "x"}}
    res = client.post("/api/notifications/test", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True

def test_notification_payload_without_config(client, monkeypatch):
    from server.notification_providers import teams

    async def fake_send(self, notification, message, monitor=None, heartbeat=None):
        assert notification["webhook_url"] == "x"
        return "ok"

    monkeypatch.setattr(teams.TeamsProvider, "send", fake_send)
    payload = {"name": "Teams", "type": "teams", "webhookUrl": "x"}
    res = client.post("/api/notifications/test", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_discord_notification_payload_without_config(client, monkeypatch):
    from server.notification_providers import discord

    async def fake_send(self, notification, message, monitor=None, heartbeat=None):
        assert notification["webhook_url"] == "x"
        return "ok"

    monkeypatch.setattr(discord.DiscordProvider, "send", fake_send)
    payload = {"name": "Discord", "type": "discord", "webhookUrl": "x"}
    res = client.post("/api/notifications/test", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_discord_notification_legacy_payload(client, monkeypatch):
    from server.notification_providers import discord

    async def fake_send(self, notification, message, monitor=None, heartbeat=None):
        assert notification["webhook_url"] == "x"
        return "ok"

    monkeypatch.setattr(discord.DiscordProvider, "send", fake_send)
    payload = {"name": "Discord", "type": "discord", "discordWebhookUrl": "x"}
    res = client.post("/api/notifications/test", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_notification_invalid_url(client, monkeypatch):
    """Errors from the provider should be returned as a 400 response."""
    from server.notification_providers import teams

    async def fake_send(self, notification, message, monitor=None, heartbeat=None):
        raise RuntimeError("invalid url")

    monkeypatch.setattr(teams.TeamsProvider, "send", fake_send)
    payload = {"name": "Teams", "type": "teams", "config": {"webhook_url": "x"}}
    res = client.post("/api/notifications/test", json=payload)
    assert res.status_code == 400
    assert "invalid url" in res.json()["detail"]


def test_notification_missing_discord_webhook(client):
    payload = {"name": "Discord", "type": "discord"}
    res = client.post("/api/notifications/test", json=payload)
    assert res.status_code == 400
    assert (
        res.json()["detail"]
        == "'webhook_url' is required for Discord notifications"
    )


def test_teams_notification_webhook_url_normalization(client):
    payload = {"name": "TeamsNorm", "type": "teams", "config": {"webhookURL": "url"}}
    res = client.post("/api/notifications", json=payload)
    assert res.status_code == 200
    res = client.get("/api/notifications")
    cfg = next(n["config"] for n in res.json() if n["name"] == "TeamsNorm")
    assert cfg["webhook_url"] == "url"


def test_teams_notification_config_string(client):
    payload = {"name": "TeamsStr", "type": "teams", "config": "{\"webhook_url\":\"foo\"}"}
    res = client.post("/api/notifications", json=payload)
    assert res.status_code == 200
    res = client.get("/api/notifications")
    cfg = next(n["config"] for n in res.json() if n["name"] == "TeamsStr")
    assert cfg["webhook_url"] == "foo"


def test_repair_webhook_u_r_l(tmp_path):
    db_path = tmp_path / "test.db"
    if db_path.is_absolute():
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
    else:
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    asyncio.run(init_db())

    async def populate():
        async with database.async_session_maker() as session:
            n = models.Notification(
                name="Broken",
                type="teams",
                active=True,
                is_default=False,
                config='{"webhook_u_r_l":"bar"}',
            )
            session.add(n)
            await session.commit()

    asyncio.run(populate())

    app = create_app()
    with TestClient(app) as c:
        token = c.post("/api/setup", json={"username": "admin", "password": "admin"}).json()["token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        res = c.get("/api/notifications")
        cfg = res.json()[0]["config"]
        assert cfg["webhook_url"] == "bar"
