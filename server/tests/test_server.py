import os
import sys
import shutil
import asyncio
import asyncio
import datetime
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
import pyotp
from fastapi import Request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from server.server import create_app
import server.routers.api as api
from server.settings import DEFAULT_INTERVAL_SECONDS
from ldap3.core.exceptions import LDAPBindError, LDAPException


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    if db_path.is_absolute():
        os.environ["DATABASE_URL"] = (
            "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
        )
    else:
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    app = create_app()
    with TestClient(app) as c:
        token = c.post(
            "/api/setup", json={"username": "admin", "password": "admin"}
        ).json()["token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


@pytest.fixture
def anon_client(tmp_path):
    db_path = tmp_path / "test.db"
    if db_path.is_absolute():
        os.environ["DATABASE_URL"] = (
            "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
        )
    else:
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_login_success(anon_client):
    anon_client.post(
        "/api/setup", json={"username": "admin", "password": "admin"}
    )
    res = anon_client.post(
        "/api/login", json={"username": "admin", "password": "admin"}
    )
    assert res.status_code == 200
    token = res.json()["token"]
    assert isinstance(token, str) and token


def test_login_failure(anon_client):
    anon_client.post(
        "/api/setup", json={"username": "admin", "password": "admin"}
    )
    res = anon_client.post(
        "/api/login", json={"username": "foo", "password": "bar"}
    )
    assert res.status_code == 401


def test_twofa_flow(tmp_path):
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}" if not db_path.is_absolute() else (
        "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
    )

    app = create_app()
    with TestClient(app) as client:
        setup_res = client.post(
            "/api/setup", json={"username": "admin", "password": "admin"}
        )
        token = setup_res.json()["token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

        res = client.get("/api/twofa/status")
        assert res.status_code == 200
        assert res.json()["status"] is False

        res = client.post(
            "/api/twofa/prepare", json={"currentPassword": "wrong"}
        )
        assert res.status_code == 403
        assert res.json()["detail"] == "invalidCurrentPassword"

        res = client.post(
            "/api/twofa/prepare", json={"currentPassword": "admin"}
        )
        assert res.status_code == 200
        uri = res.json()["uri"]
        secret = parse_qs(urlparse(uri).query)["secret"][0]
        totp = pyotp.TOTP(secret)

        token_code = totp.now()
        res = client.post(
            "/api/twofa/verify",
            json={"currentPassword": "admin", "token": token_code},
        )
        assert res.status_code == 200
        assert res.json()["valid"] is True

        res = client.post(
            "/api/twofa/enable",
            json={"currentPassword": "admin", "token": totp.now()},
        )
        assert res.status_code == 200
        assert res.json()["ok"] is True
        assert res.json()["msgi18n"] == "twoFAEnabledSuccess"

        res = client.get("/api/twofa/status")
        assert res.status_code == 200
        assert res.json()["status"] is True

        client.headers.pop("Authorization", None)

        res = client.post(
            "/api/login", json={"username": "admin", "password": "admin"}
        )
        assert res.status_code == 403
        assert res.json()["detail"] == "tokenRequired"

        res = client.post(
            "/api/login",
            json={"username": "admin", "password": "admin", "token": "000000"},
        )
        assert res.status_code == 403
        assert res.json()["detail"] == "invalidTwoFAToken"

        valid_login = client.post(
            "/api/login",
            json={"username": "admin", "password": "admin", "token": totp.now()},
        )
        assert valid_login.status_code == 200
        new_token = valid_login.json()["token"]
        assert isinstance(new_token, str) and new_token

        client.headers.update({"Authorization": f"Bearer {new_token}"})
        res = client.post(
            "/api/twofa/disable", json={"currentPassword": "admin"}
        )
        assert res.status_code == 200
        assert res.json()["ok"] is True
        assert res.json()["msgi18n"] == "twoFADisabledSuccess"

        res = client.get("/api/twofa/status")
        assert res.status_code == 200
        assert res.json()["status"] is False


def test_login_rate_limit_after_repeated_failures(anon_client):
    """Per-IP rate limiter trips after _LOGIN_MAX_FAILURES bad attempts."""
    from server.routers import api as api_module

    anon_client.post("/api/setup", json={"username": "admin", "password": "admin"})
    # Reset between tests — the limiter is module-global state.
    api_module._login_failures.clear()

    # The TestClient uses the same client IP for every request, so all
    # failures land in the same bucket.
    for _ in range(api_module._LOGIN_MAX_FAILURES):
        res = anon_client.post(
            "/api/login", json={"username": "admin", "password": "wrong"}
        )
        assert res.status_code == 401  # individual attempts still 401

    # The next attempt should be rate-limited regardless of credentials.
    res = anon_client.post(
        "/api/login", json={"username": "admin", "password": "admin"}
    )
    assert res.status_code == 429
    assert res.json()["detail"] == "tooManyLoginAttempts"
    assert "Retry-After" in res.headers


def test_login_rate_limit_clears_on_success(anon_client):
    """Successful login resets the failure counter for that IP."""
    from server.routers import api as api_module

    anon_client.post("/api/setup", json={"username": "admin", "password": "admin"})
    api_module._login_failures.clear()

    # 3 failed attempts (well under the limit).
    for _ in range(3):
        anon_client.post(
            "/api/login", json={"username": "admin", "password": "wrong"}
        )

    # Successful login.
    res = anon_client.post(
        "/api/login", json={"username": "admin", "password": "admin"}
    )
    assert res.status_code == 200

    # Counter should now be empty — verified by reaching past the previous
    # 3-attempt count without tripping the limit.
    for _ in range(api_module._LOGIN_MAX_FAILURES - 1):
        anon_client.post(
            "/api/login", json={"username": "admin", "password": "wrong"}
        )
    # Still under limit, so next legit login still works.
    res = anon_client.post(
        "/api/login", json={"username": "admin", "password": "admin"}
    )
    assert res.status_code == 200


def test_login_username_enumeration_timing_uniform(anon_client):
    """A request for a non-existent user should take a similar amount
    of time as a request for an existing user (bcrypt verify runs in
    both cases). This guards against username enumeration via timing."""
    from server.routers import api as api_module
    import time

    anon_client.post("/api/setup", json={"username": "admin", "password": "admin"})
    api_module._login_failures.clear()

    def time_login(username):
        t0 = time.perf_counter()
        anon_client.post(
            "/api/login", json={"username": username, "password": "wrong"}
        )
        return time.perf_counter() - t0

    # Warm up so first-request overhead doesn't dominate.
    time_login("warmup-user")
    api_module._login_failures.clear()

    existing = time_login("admin")
    api_module._login_failures.clear()
    nonexistent = time_login("does-not-exist-anywhere")

    # Both should be dominated by bcrypt time. With the dummy hash in
    # place they're within an order of magnitude. Without the fix, the
    # nonexistent path used to skip bcrypt entirely and was 10-100x
    # faster, so this ratio is the regression guard.
    ratio = max(existing, nonexistent) / max(min(existing, nonexistent), 1e-6)
    assert ratio < 5, (
        f"username enumeration via timing — existing={existing:.3f}s, "
        f"nonexistent={nonexistent:.3f}s, ratio={ratio:.2f}"
    )


def test_setup_database_wizard_flow(tmp_path, monkeypatch):
    """End-to-end: bootstrap mode → wizard test → wizard apply →
    real database is in use afterwards."""
    import json as _json
    from server.db import database as db_mod

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db_mod, "DB_CONFIG_PATH", tmp_path / "db.config.json")
    bootstrap = tmp_path / "_bootstrap.db"
    monkeypatch.setattr(
        db_mod,
        "BOOTSTRAP_DATABASE_URL",
        f"sqlite+aiosqlite:///{bootstrap.as_posix()}",
    )

    target = tmp_path / "real.db"

    app = create_app()
    with TestClient(app) as c:
        # Bootstrap → wizard reports needed.
        r = c.get("/api/setup-database-info")
        assert r.status_code == 200 and r.json()["needsDbSetup"] is True

        # Other admin paths blocked while bootstrapping.
        r = c.get("/api/monitors")
        assert r.status_code == 403
        assert r.json()["detail"] == "dbSetupNeeded"

        # Test endpoint validates without persisting.
        r = c.post(
            "/api/setup-database/test",
            json={"type": "sqlite", "path": str(target)},
        )
        assert r.status_code == 200 and r.json()["ok"] is True

        # Apply.
        r = c.post(
            "/api/setup-database",
            json={"type": "sqlite", "path": str(target)},
        )
        assert r.status_code == 200 and r.json()["ok"] is True

        # Wizard no longer needed; admin paths reachable again.
        assert c.get("/api/setup-database-info").json()["needsDbSetup"] is False
        assert c.get("/api/setup-needed").status_code == 200

        # Config file persisted with the chosen URL.
        cfg = _json.loads((tmp_path / "db.config.json").read_text())
        assert cfg["url"].startswith("sqlite+aiosqlite:///")
        assert str(target) in cfg["url"]


def test_setup_database_rejects_when_already_configured(tmp_path, monkeypatch):
    """Wizard apply after the engine is already configured returns 400."""
    import json as _json
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from server.db import database as db_mod
    monkeypatch.setattr(db_mod, "DB_CONFIG_PATH", tmp_path / "db.config.json")

    (tmp_path / "db.config.json").write_text(
        _json.dumps({"url": f"sqlite+aiosqlite:///{(tmp_path / 'pre.db').as_posix()}"})
    )

    app = create_app()
    with TestClient(app) as c:
        assert c.get("/api/setup-database-info").json()["needsDbSetup"] is False
        r = c.post("/api/setup-database", json={"type": "sqlite", "path": str(tmp_path / "x.db")})
        assert r.status_code == 400
        assert r.json()["detail"] == "alreadySetup"


def test_setup_database_rejects_invalid_type(tmp_path, monkeypatch):
    """Unknown engine type → 400."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from server.db import database as db_mod
    monkeypatch.setattr(db_mod, "DB_CONFIG_PATH", tmp_path / "db.config.json")
    monkeypatch.setattr(
        db_mod,
        "BOOTSTRAP_DATABASE_URL",
        f"sqlite+aiosqlite:///{(tmp_path / '_bootstrap.db').as_posix()}",
    )

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/api/setup-database/test",
            json={"type": "oracle", "hostname": "x", "username": "y", "database": "z"},
        )
        assert r.status_code == 400


def test_login_2fa_fails_closed_when_secret_missing(tmp_path):
    """Regression: a user with two_fa_enabled=True but a null
    two_fa_secret used to fall through and issue a token without
    verifying the second factor. Now it must fail."""
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}" if not db_path.is_absolute() else (
        "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
    )

    app = create_app()
    with TestClient(app) as client:
        client.post("/api/setup", json={"username": "admin", "password": "admin"})

        # Manually flip 2FA on with no secret — simulates DB tampering.
        async def corrupt():
            from server.db import database, models
            from sqlalchemy import select
            async with database.async_session_maker() as session:
                res = await session.execute(
                    select(models.User).where(models.User.username == "admin")
                )
                user = res.scalar_one()
                user.two_fa_enabled = True
                user.two_fa_secret = None
                await session.commit()
        asyncio.run(corrupt())

        res = client.post(
            "/api/login", json={"username": "admin", "password": "admin"}
        )
        # Failed-closed: login refused, no token in response.
        assert res.status_code != 200
        assert "token" not in res.json()


def test_login_ldap_invalid_credentials(monkeypatch, anon_client):
    monkeypatch.setenv("LDAP_URL", "ldap://example.com")
    monkeypatch.setenv(
        "LDAP_DN_TEMPLATE", "uid={username},ou=users,dc=example,dc=com"
    )

    def fake_conn(server, dn, password, auto_bind=True):
        raise LDAPBindError("invalid credentials")

    monkeypatch.setattr(api, "Connection", fake_conn)
    monkeypatch.setattr(api, "Server", lambda *a, **kw: object())

    res = anon_client.post(
        "/api/login", json={"username": "foo", "password": "bar"}
    )
    assert res.status_code == 401


def test_login_ldap_connection_failure(monkeypatch, anon_client):
    monkeypatch.setenv("LDAP_URL", "ldap://example.com")
    monkeypatch.setenv(
        "LDAP_DN_TEMPLATE", "uid={username},ou=users,dc=example,dc=com"
    )

    def fake_conn(server, dn, password, auto_bind=True):
        raise LDAPException("connection failed")

    monkeypatch.setattr(api, "Connection", fake_conn)
    monkeypatch.setattr(api, "Server", lambda *a, **kw: object())

    res = anon_client.post(
        "/api/login", json={"username": "foo", "password": "bar"}
    )
    assert res.status_code == 500
    assert res.json()["detail"] == "ldapConnectionFailed"


def test_user_crud(client):
    res = client.post("/api/users", json={"username": "alice", "password": "secret"})
    assert res.status_code == 200
    user_id = res.json()["id"]
    assert isinstance(user_id, int)

    res = client.get("/api/users")
    assert res.status_code == 200
    names = [u["username"] for u in res.json()]
    assert "alice" in names

    res = client.post("/api/login", json={"username": "alice", "password": "secret"})
    assert res.status_code == 200


def test_username_unique(client):
    client.post("/api/users", json={"username": "same", "password": "x"})
    res = client.post("/api/users", json={"username": "same", "password": "y"})
    assert res.status_code == 400
    assert res.json()["detail"] == "usernameTaken"


def test_user_deactivate_delete(client):
    client.post(
        "/api/users",
        json={"username": "admin", "password": "admin", "is_admin": True},
    )
    res = client.post("/api/users", json={"username": "bob", "password": "pwd"})
    user_id = res.json()["id"]

    res = client.post(f"/api/users/{user_id}/deactivate", json={"adminPassword": "admin"})
    assert res.status_code == 200

    res = client.post("/api/login", json={"username": "bob", "password": "pwd"})
    assert res.status_code == 401

    res = client.request("DELETE", f"/api/users/{user_id}", json={"adminPassword": "admin"})
    assert res.status_code == 200

    res = client.get("/api/users")
    names = [u["username"] for u in res.json()]
    assert "bob" not in names


def test_delete_user_multiple_admins(client):
    client.post(
        "/api/users",
        json={"username": "admin1", "password": "a1", "is_admin": True},
    )
    client.post(
        "/api/users",
        json={"username": "admin2", "password": "a2", "is_admin": True},
    )
    res = client.post("/api/users", json={"username": "bob", "password": "pwd"})
    user_id = res.json()["id"]

    res = client.request("DELETE", f"/api/users/{user_id}", json={"adminPassword": "a2"})
    assert res.status_code == 200


def test_change_password(client):
    client.post(
        "/api/users",
        json={"username": "admin", "password": "admin", "is_admin": True},
    )
    payload = {"currentPassword": "admin", "newPassword": "newpass"}
    res = client.post("/api/change-password", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["msgi18n"] == "successAuthChangePassword"

    res = client.post("/api/login", json={"username": "admin", "password": "newpass"})
    assert res.status_code == 200


def test_change_password_invalid_current(client):
    client.post(
        "/api/users",
        json={"username": "admin", "password": "admin", "is_admin": True},
    )
    payload = {"currentPassword": "wrong", "newPassword": "newpass"}
    res = client.post("/api/change-password", json=payload)
    assert res.status_code == 400
    assert res.json()["detail"] == "invalidCurrentPassword"


def test_entry_page(client):
    res = client.get("/api/entry-page")
    assert res.status_code == 200
    assert res.json() == {"type": "entryPage", "entryPage": None}


def test_monitors_crud(client):
    res = client.get("/api/monitors")
    assert res.status_code == 200
    assert res.json() == []

    monitor = {
        "id": 1,
        "name": "Test",
        "url": "http://example.com",
        "push_token": "abc",
        "cache_bust": True,
        "upside_down": True,
        "ignore_tls": True,
        "expiry_notification": True,
    }
    res = client.post("/api/monitors", json=monitor)
    assert res.status_code == 200

    res = client.get("/api/monitors")
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["name"] == "Test"
    assert data[0]["active"] is True
    assert data[0]["cacheBust"] is True
    assert data[0]["upsideDown"] is True
    assert data[0]["ignoreTls"] is True
    assert data[0]["expiryNotification"] is True
    assert data[0]["tls_verify_mode"] == "system"
    assert data[0]["custom_ca_subject"] is None
    assert data[0]["custom_ca_issuer"] is None
    assert data[0]["custom_ca_sha256"] is None


def test_delete_monitor(client):
    payload = {
        "id": 1,
        "name": "Del",
        "url": "http://example.com",
        "push_token": "abc",
    }
    client.post("/api/monitors", json=payload)
    res = client.delete("/api/monitors/1")
    assert res.status_code == 200
    res = client.get("/api/monitors")
    assert res.json() == []


def test_monitor_extra_flags(client):
    payload = {
        "id": 1,
        "name": "Extras",
        "url": "http://example.com",
        "push_token": "tok",
        "invert_keyword": True,
        "expiry_notification": True,
        "cache_bust": True,
        "ping_numeric": False,
    }
    res = client.post("/api/monitors", json=payload)
    assert res.status_code == 200

    res = client.get("/api/monitors")
    data = res.json()[0]
    assert data["invertKeyword"] is True
    assert data["expiryNotification"] is True
    assert data["cacheBust"] is True
    assert data["pingNumeric"] is False


def test_update_http_monitor_flags(client):
    """HTTP monitor checkboxes should persist after editing."""
    base = {
        "id": 1,
        "name": "Test",
        "url": "http://example.com",
        "push_token": "tok",
    }
    client.post("/api/monitors", json=base)

    edit = base | {
        "ignore_tls": True,
        "expiry_notification": True,
        "cache_bust": True,
        "upside_down": True,
    }
    res = client.post("/api/monitor/1", json=edit)
    assert res.status_code == 200

    res = client.get("/api/monitor/1")
    data = res.json()["monitor"]
    assert data["ignoreTls"] is True
    assert data["expiryNotification"] is True
    assert data["cacheBust"] is True
    assert data["upsideDown"] is True


def test_setup_toggle(anon_client):
    res = anon_client.get("/api/setup-needed")
    assert res.json()["needSetup"] is True

    res = anon_client.get("/api/monitors")
    assert res.status_code == 403

    res = anon_client.post(
        "/api/setup", json={"username": "admin", "password": "admin"}
    )
    data = res.json()
    assert data["ok"] is True
    assert "token" in data

    res = anon_client.get("/api/setup-needed")
    assert res.json()["needSetup"] is False


def test_persistence(tmp_path):
    db_path = tmp_path / "test.db"
    if db_path.is_absolute():
        os.environ["DATABASE_URL"] = (
            "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
        )
    else:
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    app1 = create_app()
    with TestClient(app1) as c1:
        token = c1.post(
            "/api/setup", json={"username": "admin", "password": "admin"}
        ).json()["token"]
        c1.headers.update({"Authorization": f"Bearer {token}"})
        c1.post(
            "/api/monitors",
            json={"id": 1, "name": "A", "url": "x", "push_token": "tok"},
        )

    app2 = create_app()
    with TestClient(app2) as c2:
        token = c2.post(
            "/api/login", json={"username": "admin", "password": "admin"}
        ).json()["token"]
        c2.headers.update({"Authorization": f"Bearer {token}"})
        res = c2.get("/api/monitors")
        data = res.json()
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert data[0]["name"] == "A"
        assert data[0]["active"] is True


def test_push_and_heartbeat(client):
    monitor = {
        "id": 1,
        "name": "Test",
        "url": "http://example.com",
        "push_token": "abc",
        "type": "push",
    }
    client.post("/api/monitors", json=monitor)
    client.post("/api/status-page", json={"title": "Main", "slug": "default"})

    # Initial fetch should return the single placeholder heartbeat with a pending status
    res = client.get("/api/status-page/heartbeat/default")
    assert res.status_code == 200
    data = res.json()
    beats = data["heartbeatList"].get("1")
    assert beats and len(beats) == 1 and beats[0]["status"] == 2

    res = client.post("/api/push/abc", params={"status": "up", "msg": "OK", "ping": 42})
    assert res.status_code == 200
    assert res.json()["ok"] is True

    # After pushing a new heartbeat, the status page should expose both records
    res = client.get("/api/status-page/heartbeat/default")
    assert res.status_code == 200
    data = res.json()
    beats = data["heartbeatList"].get("1")
    assert beats and len(beats) == 2 and beats[1]["status"] == 1


def test_settings_roundtrip(client):
    res = client.get("/api/settings")
    assert res.status_code == 200
    assert res.json() == {"data": {"setup_done": True}}

    payload = {"settings": {"foo": "bar"}}
    res = client.post("/api/settings", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True

    res = client.get("/api/settings")
    assert res.status_code == 200
    assert res.json() == {"data": {"setup_done": True, "foo": "bar"}}


def test_ldap_settings(client):
    payload = {
        "settings": {
            "ldapURL": "ldap://example.com",
            "ldapDNTemplate": "uid={username},ou=users,dc=example,dc=com",
        }
    }
    res = client.post("/api/settings", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True

    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["ldapURL"] == "ldap://example.com"
    assert data["ldapDNTemplate"] == "uid={username},ou=users,dc=example,dc=com"


def test_status_page_crud(client):
    # create
    res = client.post("/api/status-page", json={"title": "Main", "slug": "abc"})
    assert res.status_code == 200
    assert res.json()["slug"] == "abc"

    # get
    res = client.get("/api/status-page/abc")
    assert res.status_code == 200
    assert res.json()["config"]["icon"] == "/icon.svg"

    # update
    res = client.post("/api/status-page/abc", json={"config": "{}"})
    assert res.status_code == 200

    # delete
    res = client.delete("/api/status-page/abc")
    assert res.status_code == 200

    # ensure gone
    res = client.get("/api/status-page/abc")
    assert res.status_code == 404

    # list
    res = client.get("/api/status-page")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_status_page_incident(client):
    client.post("/api/status-page", json={"title": "Main", "slug": "demo"})

    payload = {"title": "Outage", "content": "Down", "style": "danger"}
    res = client.post("/api/status-page/demo/incident", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    incident_id = data["incident"]["id"]

    res = client.get("/api/status-page/demo")
    assert res.status_code == 200
    assert res.json()["incident"]["id"] == incident_id

    res = client.post("/api/status-page/demo/unpin-incident")
    assert res.status_code == 200

    res = client.get("/api/status-page/demo")
    assert res.status_code == 200
    assert res.json()["incident"] is None


def test_create_status_page_with_monitors(client):
    m1 = {"id": 1, "name": "A", "url": "http://a", "type": "http"}
    m2 = {"id": 2, "name": "B", "url": "http://b", "type": "http"}
    client.post("/api/monitors", json=m1)
    client.post("/api/monitors", json=m2)
    res = client.post(
        "/api/status-page",
        json={"title": "Main", "slug": "withmon", "monitors": [1, 2]},
    )
    assert res.status_code == 200
    res = client.get("/api/status-page/withmon")
    assert res.status_code == 200
    data = res.json()
    assert len(data["publicGroupList"]) == 1
    ids = {m["id"] for m in data["publicGroupList"][0]["monitorList"]}
    assert ids == {1, 2}
    assert set(data["config"]["monitorList"].keys()) == {"1", "2"}


def test_create_status_page_with_monitor_names(client):
    m1 = {"id": 1, "name": "A", "url": "http://a", "type": "http"}
    m2 = {"id": 2, "name": "B", "url": "http://b", "type": "http"}
    client.post("/api/monitors", json=m1)
    client.post("/api/monitors", json=m2)
    res = client.post(
        "/api/status-page",
        json={"title": "Main", "slug": "withname", "monitors": ["A", "B"]},
    )
    assert res.status_code == 200
    res = client.get("/api/status-page/withname")
    assert res.status_code == 200
    data = res.json()
    ids = {m["id"] for m in data["publicGroupList"][0]["monitorList"]}
    assert ids == {1, 2}


def test_create_status_page_with_monitor_names_whitespace(client):
    m1 = {
        "id": 3,
        "name": "Alibaba Cloud",
        "url": "http://a",
        "type": "http",
    }
    m2 = {
        "id": 4,
        "name": "[PROD] Some Service Local Name",
        "url": "http://b",
        "type": "http",
    }
    client.post("/api/monitors", json=m1)
    client.post("/api/monitors", json=m2)
    res = client.post(
        "/api/status-page",
        json={
            "title": "Main",
            "slug": "withspaces",
            "monitors": [
                "  alibaba cloud  ",
                " [prod] some service local name ",
            ],
        },
    )
    assert res.status_code == 200
    res = client.get("/api/status-page/withspaces")
    assert res.status_code == 200
    data = res.json()
    ids = {m["id"] for m in data["publicGroupList"][0]["monitorList"]}
    assert ids == {3, 4}


def test_create_status_page_with_unknown_monitor_name(client):
    m1 = {"id": 1, "name": "A", "url": "http://a", "type": "http"}
    client.post("/api/monitors", json=m1)
    res = client.post(
        "/api/status-page",
        json={"title": "Main", "slug": "badname", "monitors": ["A", "X"]},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "monitorNameNotFound"


def test_status_page_public_access(client, anon_client):
    client.post(
        "/api/status-page",
        json={"title": "Public", "slug": "pub", "public": True},
    )
    client.post(
        "/api/status-page",
        json={"title": "Private", "slug": "priv", "public": False},
    )

    res = anon_client.get("/api/status-page/pub")
    assert res.status_code == 200
    res = anon_client.get("/api/status-page/heartbeat/pub")
    assert res.status_code == 200

    res = anon_client.get("/api/status-page/priv")
    assert res.status_code == 403
    res = anon_client.get("/api/status-page/heartbeat/priv")
    assert res.status_code == 403


def test_important_heartbeat_endpoints(client):
    monitor = {"id": 1, "name": "A", "url": "http://example.com", "push_token": "tok"}
    client.post("/api/monitors", json=monitor)

    # Insert some important heartbeats directly
    from server.db import models
    from server.db.database import async_session_maker
    import asyncio

    async def _insert():
        async with async_session_maker() as session:
            session.add(models.ImportantHeartbeat(monitor_id=1, message="one"))
            session.add(models.ImportantHeartbeat(monitor_id=1, message="two"))
            await session.commit()

    asyncio.run(_insert())

    res = client.get("/api/monitors/1/important-heartbeats/count")
    assert res.status_code == 200
    assert res.json()["count"] == 2

    res = client.get(
        "/api/important-heartbeats/paged", params={"offset": 0, "limit": 1}
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1


def _seed_event_heartbeats(monitor_id: int):
    """Helper: seed the monitor with three important beats (up @ -3min,
    down @ -2min, up @ -1min) plus one non-important up @ -30s, so tests
    can assert ordering, filtering, and the important-only constraint."""
    from server.db import database, models

    async def _insert():
        async with database.async_session_maker() as session:
            await session.execute(
                delete(models.Heartbeat).where(models.Heartbeat.monitor_id == monitor_id)
            )
            now = datetime.datetime.utcnow()
            session.add_all([
                models.Heartbeat(
                    monitor_id=monitor_id,
                    status=1,
                    important=True,
                    msg="up #1",
                    time=now - datetime.timedelta(minutes=3),
                ),
                models.Heartbeat(
                    monitor_id=monitor_id,
                    status=0,
                    important=True,
                    msg="connection refused",
                    time=now - datetime.timedelta(minutes=2),
                ),
                models.Heartbeat(
                    monitor_id=monitor_id,
                    status=1,
                    important=True,
                    msg="recovered",
                    time=now - datetime.timedelta(minutes=1),
                ),
                models.Heartbeat(
                    monitor_id=monitor_id,
                    status=1,
                    important=False,
                    msg="ok",
                    time=now - datetime.timedelta(seconds=30),
                ),
            ])
            await session.commit()

    asyncio.run(_insert())


def test_events_returns_only_important_newest_first(client):
    res = client.post(
        "/api/monitors",
        json={"id": 1, "name": "site", "url": "http://example.com"},
    )
    monitor_id = res.json()["monitorID"]

    _seed_event_heartbeats(monitor_id)

    res = client.get("/api/events")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True

    events = body["events"]
    # Three important beats, the non-important one excluded.
    assert len(events) == 3
    # Newest first.
    statuses = [e["status"] for e in events]
    assert statuses == [1, 0, 1]
    msgs = [e["msg"] for e in events]
    assert msgs == ["recovered", "connection refused", "up #1"]
    # Each row carries the joined monitor metadata so the client doesn't
    # have to do an extra round-trip.
    assert all(e["monitorID"] == monitor_id for e in events)
    assert all(e["monitorName"] == "site" for e in events)


def test_events_status_filter(client):
    res = client.post(
        "/api/monitors",
        json={"id": 1, "name": "site", "url": "http://example.com"},
    )
    monitor_id = res.json()["monitorID"]

    _seed_event_heartbeats(monitor_id)

    res = client.get("/api/events", params={"status": "down"})
    assert res.status_code == 200
    events = res.json()["events"]
    assert len(events) == 1
    assert events[0]["status"] == 0
    assert events[0]["msg"] == "connection refused"

    res = client.get("/api/events", params={"status": "up"})
    events = res.json()["events"]
    assert len(events) == 2
    assert all(e["status"] == 1 for e in events)


def test_events_pagination(client):
    res = client.post(
        "/api/monitors",
        json={"id": 1, "name": "site", "url": "http://example.com"},
    )
    monitor_id = res.json()["monitorID"]

    _seed_event_heartbeats(monitor_id)

    page1 = client.get("/api/events", params={"limit": 2, "offset": 0}).json()
    page2 = client.get("/api/events", params={"limit": 2, "offset": 2}).json()

    assert page1["total"] == 3
    assert len(page1["events"]) == 2
    assert page1["events"][0]["msg"] == "recovered"
    assert page1["events"][1]["msg"] == "connection refused"

    assert len(page2["events"]) == 1
    assert page2["events"][0]["msg"] == "up #1"


def test_clear_endpoints(client):
    monitor = {"id": 1, "name": "A", "url": "http://example.com", "push_token": "tok"}
    client.post("/api/monitors", json=monitor)

    from server.db import models
    from server.db.database import async_session_maker
    from sqlalchemy import select, func
    import asyncio

    async def _insert():
        async with async_session_maker() as session:
            session.add(models.Heartbeat(monitor_id=1, status=1))
            session.add(models.ImportantHeartbeat(monitor_id=1, message="evt"))
            await session.commit()

    asyncio.run(_insert())

    res = client.post("/api/monitors/1/clear-heartbeats")
    assert res.status_code == 200
    assert res.json()["ok"] is True

    res = client.post("/api/monitors/1/clear-events")
    assert res.status_code == 200
    assert res.json()["ok"] is True

    async def _count():
        async with async_session_maker() as session:
            hb_count = await session.scalar(select(func.count(models.Heartbeat.id)))
            ev_count = await session.scalar(
                select(func.count(models.ImportantHeartbeat.id))
            )
            return hb_count, ev_count

    counts = asyncio.run(_count())
    assert counts == (0, 0)


def test_monitor_advanced_fields(client):
    payload = {
        "id": 1,
        "name": "Adv",
        "url": "http://example.com",
        "accepted_statuscodes": ["200-204"],
        "maxredirects": 5,
        "maxretries": 2,
        "retryInterval": 30,
        "resendInterval": 1,
        "ignore_tls": True,
        "expiry_notification": True,
    }
    res = client.post("/api/monitors", json=payload)
    assert res.status_code == 200
    monitor_id = res.json()["monitorID"]

    res = client.get(f"/api/monitor/{monitor_id}")
    assert res.status_code == 200
    data = res.json()["monitor"]
    assert data["accepted_statuscodes"] == ["200-204"]
    assert data["maxredirects"] == 5
    assert data["ignoreTls"] is True


def test_dns_monitor_fields(client):
    payload = {
        "id": 1,
        "name": "DNS",
        "type": "dns",
        "url": "http://example.com",
        "hostname": "example.com",
        "dns_resolve_server": "1.1.1.1",
        "dns_resolve_type": "A",
        "port": 5300,
    }
    res = client.post("/api/monitors", json=payload)
    assert res.status_code == 200
    res = client.get("/api/monitors")
    data = res.json()[0]
    assert data["hostname"] == "example.com"
    assert data["dnsResolveServer"] == "1.1.1.1"
    assert data["dnsResolveType"] == "A"
    assert data["port"] == 5300


def test_certificate_expiry_check(client, monkeypatch):
    from server.monitor_types import http as http_mod

    async def fake_days(monitor, url):
        return 42

    monkeypatch.setattr(
        http_mod.HTTPMonitor,
        "_cert_expiry_days",
        lambda self, monitor, url: fake_days(monitor, url),
    )

    payload = {
        "id": 2,
        "name": "Cert",
        "url": "https://example.com",
        "expiry_notification": True,
    }
    res = client.post("/api/monitors", json=payload)
    assert res.status_code == 200
    monitor_id = res.json()["monitorID"]

    # Trigger monitor runner manually
    from server.monitor_types.http import HTTPMonitor
    from server.db import models
    from server.db.database import async_session_maker
    import asyncio

    async def _run():
        async with async_session_maker() as session:
            m = await session.get(models.Monitor, monitor_id)
            hb = models.Heartbeat(monitor_id=monitor_id)
            await HTTPMonitor().check(m, hb)
            return hb.cert_expire

    cert_days = asyncio.run(_run())
    assert cert_days == 42


def test_notifications_crud(client):
    payload = {"name": "Teams", "type": "teams", "webhookUrl": "http://teams"}
    res = client.post("/api/notifications", json=payload)
    assert res.status_code == 200
    notif_id = res.json()["id"]

    res = client.get("/api/notifications")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == notif_id
    assert data[0]["config"]["webhook_url"] == "http://teams"

    edit_payload = {"name": "Teams", "type": "teams", "webhookUrl": "http://new"}
    res = client.post(f"/api/notifications/{notif_id}", json=edit_payload)
    assert res.status_code == 200

    res = client.get("/api/notifications")
    assert res.status_code == 200
    data = res.json()
    assert data[0]["config"]["webhook_url"] == "http://new"

    res = client.delete(f"/api/notifications/{notif_id}")
    assert res.status_code == 200


def test_heartbeats_endpoints(client):
    monitor = {"id": 1, "name": "A", "url": "http://example.com", "push_token": "tok"}
    client.post("/api/monitors", json=monitor)

    from server.db import models
    from server.db.database import async_session_maker
    import asyncio

    async def _insert():
        async with async_session_maker() as session:
            session.add(models.Heartbeat(monitor_id=1, status=1, msg="one"))
            session.add(models.Heartbeat(monitor_id=1, status=0, msg="two"))
            await session.commit()

    asyncio.run(_insert())

    res = client.get("/api/monitors/1/heartbeats/count")
    assert res.status_code == 200
    # 1 heartbeat is created when the monitor is added
    assert res.json()["count"] == 3

    res = client.get(
        "/api/monitors/1/heartbeats", params={"offset": 0, "limit": 2}
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 2
    assert data[0]["msg"] == "two"
    assert data[1]["msg"] == "one"


def test_maintenance_create_and_get(client):
    """Ensure maintenance creation endpoint works."""
    res = client.post("/api/maintenance", json={"data": "{}"})
    assert res.status_code == 200
    maint_id = res.json()["maintenanceID"]

    res = client.get(f"/api/maintenance/{maint_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["maintenance"]["id"] == maint_id


def test_maintenance_associations(client):
    """Assign monitors and status pages to a maintenance record."""
    # create supporting objects
    client.post("/api/monitors", json={"id": 1, "name": "A", "url": "http://example.com"})
    client.post("/api/status-page", json={"title": "Main", "slug": "default"})

    res = client.post("/api/maintenance", json={"data": "{}"})
    maint_id = res.json()["maintenanceID"]

    # attach monitor
    res = client.post(
        f"/api/maintenance/{maint_id}/monitors",
        json={"monitors": [{"id": 1}]},
    )
    assert res.status_code == 200

    # attach status page
    res = client.post(
        f"/api/maintenance/{maint_id}/status-pages",
        json={"statusPages": [{"id": "default"}]},
    )
    assert res.status_code == 200

    res = client.get(f"/api/maintenance/{maint_id}/monitors")
    assert res.status_code == 200
    monitors = res.json()["monitors"]
    assert monitors[0]["id"] == 1

    res = client.get(f"/api/maintenance/{maint_id}/status-pages")
    assert res.status_code == 200
    pages = res.json()["statusPages"]
    assert pages[0]["id"] == "default"


def test_maintenance_list(client):
    """Ensure maintenance list endpoint returns created record."""
    res = client.post("/api/maintenance", json={"data": "{}"})
    maint_id = res.json()["maintenanceID"]

    res = client.get("/api/maintenance")
    assert res.status_code == 200
    ids = [m["id"] for m in res.json()]
    assert maint_id in ids


def test_status_change_creates_important_event(client):
    """Heartbeat status changes should create important events."""
    monitor = {
        "id": 1,
        "name": "Imp",
        "url": "http://example.com",
        "push_token": "tok",
        "type": "push",
    }
    client.post("/api/monitors", json=monitor)

    client.post("/api/push/tok", params={"status": "up", "msg": "UP"})
    client.post("/api/push/tok", params={"status": "down", "msg": "DOWN"})
    client.post("/api/push/tok", params={"status": "down", "msg": "still"})
    client.post("/api/push/tok", params={"status": "up", "msg": "ok"})

    res = client.get("/api/monitors/1/important-heartbeats/count")
    assert res.status_code == 200
    assert res.json()["count"] == 3


def test_legacy_db_conversion(tmp_path, monkeypatch):
    """Legacy Node.js database should be upgraded on startup."""
    src = Path(__file__).resolve().parents[2] / "db" / "kuma.db"
    db_path = tmp_path / "legacy.db"
    shutil.copy(src, db_path)
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{db_path.as_posix()}"
    )
    from server.db import database
    asyncio.run(database.init_db())
    import sqlite3
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "monitors" in tables
    cols = {r[1] for r in conn.execute("PRAGMA table_info(monitors)")}
    assert "ignore_tls" in cols
    assert "tls_verify_mode" in cols


def test_api_key_permissions(client):
    read_key = client.post(
        "/api/api-keys", json={"name": "rk", "role": "read"}
    ).json()["key"]
    write_key = client.post(
        "/api/api-keys", json={"name": "wk", "role": "write"}
    ).json()["key"]

    client.headers.pop("Authorization", None)

    res = client.get("/api/monitors", headers={"X-API-Key": read_key})
    assert res.status_code == 200
    res = client.post(
        "/api/monitors",
        headers={"X-API-Key": read_key},
        json={"id": 1, "name": "A", "url": "http://example.com"},
    )
    assert res.status_code == 403

    res = client.post(
        "/api/monitors",
        headers={"X-API-Key": write_key},
        json={"id": 1, "name": "A", "url": "http://example.com"},
    )
    assert res.status_code == 200


def test_status_page_uptime_one_down_in_window(client):
    """1 down + 100 ups inside the 24h window → 100/(101) = 99.0099%."""
    from server.db import database, models

    res = client.post(
        "/api/monitors",
        json={"id": 1, "name": "m", "url": "http://example.com"},
    )
    monitor_id = res.json()["monitorID"]

    async def setup():
        async with database.async_session_maker() as s:
            await s.execute(
                delete(models.Heartbeat).where(models.Heartbeat.monitor_id == monitor_id)
            )
            now = datetime.datetime.utcnow()
            base = now - datetime.timedelta(minutes=220)
            beats = [models.Heartbeat(monitor_id=monitor_id, status=0, time=base)]
            for i in range(100):
                beats.append(
                    models.Heartbeat(
                        monitor_id=monitor_id,
                        status=1,
                        time=base + datetime.timedelta(minutes=120 + i),
                    )
                )
            s.add_all(beats)
            await s.commit()

    asyncio.run(setup())

    res = client.get("/api/status-page/heartbeat/test")
    uptime = res.json()["uptimeList"][f"{monitor_id}_24"]
    assert uptime == pytest.approx(100 / 101 * 100, abs=0.01)


def test_status_page_uptime_window_excludes_older_beats(client):
    """A down beat at -25h is outside the 24h window; only the -23h up
    beat counts → 1/1 = 100%."""
    from server.db import database, models

    res = client.post(
        "/api/monitors",
        json={"id": 1, "name": "m", "url": "http://example.com"},
    )
    monitor_id = res.json()["monitorID"]

    async def setup():
        async with database.async_session_maker() as s:
            await s.execute(
                delete(models.Heartbeat).where(models.Heartbeat.monitor_id == monitor_id)
            )
            now = datetime.datetime.utcnow()
            beats = [
                models.Heartbeat(
                    monitor_id=monitor_id,
                    status=0,
                    time=now - datetime.timedelta(hours=25),
                ),
                models.Heartbeat(
                    monitor_id=monitor_id,
                    status=1,
                    time=now - datetime.timedelta(hours=23),
                ),
            ]
            s.add_all(beats)
            await s.commit()

    asyncio.run(setup())

    res = client.get("/api/status-page/heartbeat/test")
    uptime = res.json()["uptimeList"][f"{monitor_id}_24"]
    assert uptime == 100.0


def test_status_page_pending_excluded_from_uptime(client):
    """Pending (status=2) beats are transitional and don't count toward
    uptime — neither numerator nor denominator. 1 up + 1 pending → 100%
    (the lone up beat establishes the monitor as healthy; the pending
    beat is "we don't know yet", not "down")."""
    from server.db import database, models

    res = client.post(
        "/api/monitors",
        json={"id": 1, "name": "m", "url": "http://example.com"},
    )
    monitor_id = res.json()["monitorID"]

    async def setup():
        async with database.async_session_maker() as s:
            await s.execute(
                delete(models.Heartbeat).where(models.Heartbeat.monitor_id == monitor_id)
            )
            now = datetime.datetime.utcnow()
            beats = [
                models.Heartbeat(
                    monitor_id=monitor_id,
                    status=1,
                    time=now - datetime.timedelta(hours=2),
                ),
                models.Heartbeat(
                    monitor_id=monitor_id,
                    status=2,
                    time=now - datetime.timedelta(hours=1),
                ),
            ]
            s.add_all(beats)
            await s.commit()

    asyncio.run(setup())

    res = client.get("/api/status-page/heartbeat/test")
    uptime = res.json()["uptimeList"][f"{monitor_id}_24"]
    assert uptime == 100.0


def test_status_page_new_monitor_pending_then_up_is_full_uptime(client):
    """The fresh-monitor case the original report fixed: a brand-new
    monitor whose first beat was `pending` and whose first real check
    came back `up` should display 100%, not 50%. Previously the
    pending beat was counted in the denominator and the percentage
    sat at 99.x% as the pending sample aged out of the 24h window."""
    from server.db import database, models

    res = client.post(
        "/api/monitors",
        json={"id": 1, "name": "m", "url": "http://example.com"},
    )
    monitor_id = res.json()["monitorID"]

    async def setup():
        async with database.async_session_maker() as s:
            await s.execute(
                delete(models.Heartbeat).where(models.Heartbeat.monitor_id == monitor_id)
            )
            monitor = await s.get(models.Monitor, monitor_id)
            interval = monitor.interval or DEFAULT_INTERVAL_SECONDS
            now = datetime.datetime.utcnow()
            beats = [
                models.Heartbeat(
                    monitor_id=monitor_id,
                    status=2,
                    time=now - datetime.timedelta(seconds=interval + 2),
                ),
                models.Heartbeat(
                    monitor_id=monitor_id,
                    status=1,
                    time=now - datetime.timedelta(seconds=interval),
                ),
            ]
            s.add_all(beats)
            await s.commit()

    asyncio.run(setup())

    res = client.get("/api/status-page/heartbeat/test")
    uptime = res.json()["uptimeList"][f"{monitor_id}_24"]
    assert uptime == 100.0


def test_status_page_maintenance_excluded_from_uptime(client):
    """Maintenance (status=3) beats represent expected, planned downtime
    — they shouldn't drag the score down. 5 ups + 5 maintenance + 1
    down → 5/(5+1) = 83.33%, not 5/11 = 45.5%."""
    from server.db import database, models

    res = client.post(
        "/api/monitors",
        json={"id": 1, "name": "m", "url": "http://example.com"},
    )
    monitor_id = res.json()["monitorID"]

    async def setup():
        async with database.async_session_maker() as s:
            await s.execute(
                delete(models.Heartbeat).where(models.Heartbeat.monitor_id == monitor_id)
            )
            now = datetime.datetime.utcnow()
            beats = []
            for i in range(5):
                beats.append(models.Heartbeat(
                    monitor_id=monitor_id,
                    status=1,
                    time=now - datetime.timedelta(minutes=60 + i),
                ))
            for i in range(5):
                beats.append(models.Heartbeat(
                    monitor_id=monitor_id,
                    status=3,
                    time=now - datetime.timedelta(minutes=30 + i),
                ))
            beats.append(models.Heartbeat(
                monitor_id=monitor_id,
                status=0,
                time=now - datetime.timedelta(minutes=10),
            ))
            s.add_all(beats)
            await s.commit()

    asyncio.run(setup())

    res = client.get("/api/status-page/heartbeat/test")
    uptime = res.json()["uptimeList"][f"{monitor_id}_24"]
    assert uptime == pytest.approx(5 / 6 * 100, abs=0.01)


def test_trust_presented_ca_accepts_leaf_certificate(monkeypatch, client):
    from server.db import database, models

    res = client.post(
        "/api/monitors",
        json={"id": 1, "name": "leaf", "url": "https://leaf.example"},
    )
    monitor_id = res.json()["monitorID"]

    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives import serialization
    from cryptography import x509
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "leaf.example")]
    )
    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    leaf_der = cert.public_bytes(serialization.Encoding.DER)

    class DummySSL:
        def __init__(self, der: bytes):
            self.der = der

        def get_verified_chain(self):
            return None

        def getpeercertchain(self):
            return None

        def get_peer_cert_chain(self):
            return None

        def getpeercert(self, binary_form=False):
            if binary_form:
                return self.der
            return {}

    class DummyWriter:
        def __init__(self, ssl_obj):
            self.ssl_obj = ssl_obj

        def get_extra_info(self, name):
            if name == "ssl_object":
                return self.ssl_obj
            return None

        def close(self):
            pass

        async def wait_closed(self):
            return None

    async def fake_open_connection(*args, **kwargs):
        return object(), DummyWriter(DummySSL(leaf_der))

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)

    resp = client.post(f"/api/monitors/{monitor_id}/trust-presented-ca")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["sha256"] == cert.fingerprint(hashes.SHA256()).hex()
    assert data["subject"] == cert.subject.rfc4514_string()

    async def fetch_monitor():
        async with database.async_session_maker() as s:
            m = await s.get(models.Monitor, monitor_id)
            return {
                "mode": m.tls_verify_mode,
                "pem": m.custom_ca_pem,
                "sha256": m.custom_ca_sha256,
                "subject": m.custom_ca_subject,
            }

    stored = asyncio.run(fetch_monitor())
    assert stored["mode"] == "presented_ca"
    assert cert.public_bytes(serialization.Encoding.PEM).decode() in stored["pem"]
    assert stored["sha256"] == cert.fingerprint(hashes.SHA256()).hex()
    assert stored["subject"] == cert.subject.rfc4514_string()


def test_trust_presented_ca_clears_tls_failure_event(monkeypatch, client):
    import asyncio
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    from server.db import database, models

    now = datetime.datetime.utcnow()

    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Observer Test CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    async def fake_fetch_chain(*args, **kwargs):
        return [ca_cert]

    monkeypatch.setattr(api, "fetch_presented_chain", fake_fetch_chain)

    async def setup_monitor():
        async with database.async_session_maker() as session:
            monitor = models.Monitor(name="selfsigned", url="https://example.com")
            session.add(monitor)
            await session.commit()
            await session.refresh(monitor)
            msg = (
                "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
                "self-signed certificate in certificate chain (_ssl.c:1010)"
            )
            hb = models.Heartbeat(monitor_id=monitor.id, status=0, msg=msg)
            session.add(hb)
            session.add(models.ImportantHeartbeat(monitor_id=monitor.id, message=msg))
            await session.commit()
            return monitor.id

    monitor_id = asyncio.run(setup_monitor())

    resp = client.post(f"/api/monitors/{monitor_id}/trust-presented-ca")
    assert resp.status_code == 200

    async def fetch_counts():
        async with database.async_session_maker() as session:
            beats = await session.execute(
                select(models.Heartbeat).where(models.Heartbeat.monitor_id == monitor_id)
            )
            imps = await session.execute(
                select(models.ImportantHeartbeat).where(
                    models.ImportantHeartbeat.monitor_id == monitor_id
                )
            )
            monitor_obj = await session.get(models.Monitor, monitor_id)
            return {
                "heartbeats": list(beats.scalars()),
                "important": list(imps.scalars()),
                "mode": monitor_obj.tls_verify_mode,
                "pem": monitor_obj.custom_ca_pem,
                "sha256": monitor_obj.custom_ca_sha256,
            }

    stored = asyncio.run(fetch_counts())
    assert stored["heartbeats"] == []
    assert stored["important"] == []
    assert stored["mode"] == "presented_ca"
    assert ca_cert.public_bytes(serialization.Encoding.PEM).decode() in stored["pem"]
    assert stored["sha256"] == ca_cert.fingerprint(hashes.SHA256()).hex()


def test_http_monitor_presented_ca_fallback_accepts_self_signed(
    monkeypatch, client, tmp_path
):
    import asyncio
    import datetime
    import ipaddress
    import ssl
    from contextlib import suppress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    from server.db import database, models
    from server.monitor_types.http import HTTPMonitor
    import server.monitor_types.http as http_module

    now = datetime.datetime.utcnow()

    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Zerodev Root CA")])
    root_cert = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(root_key, hashes.SHA256())
    )

    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(root_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(root_key, hashes.SHA256())
    )

    cert_path = tmp_path / "selfsigned.pem"
    key_path = tmp_path / "selfsigned.key"
    cert_path.write_bytes(
        leaf_cert.public_bytes(serialization.Encoding.PEM)
        + root_cert.public_bytes(serialization.Encoding.PEM)
    )
    key_path.write_bytes(
        leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )

    async def handler(reader, writer):
        try:
            data = await reader.read(1024)
            if data:
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
                await writer.drain()
        finally:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

    async def scenario():
        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        server = await asyncio.start_server(handler, "127.0.0.1", 0, ssl=server_ctx)
        port = server.sockets[0].getsockname()[1]
        try:
            async with database.async_session_maker() as session:
                monitor = models.Monitor(
                    name=f"selfsigned-{port}",
                    url=f"https://127.0.0.1:{port}",
                    tls_verify_mode="presented_ca",
                    custom_ca_sha256=root_cert.fingerprint(hashes.SHA256()).hex(),
                    custom_ca_pem=root_cert.public_bytes(serialization.Encoding.PEM).decode(),
                )
                session.add(monitor)
                await session.commit()
                await session.refresh(monitor)
                monitor_id = monitor.id

            monkeypatch.setattr(
                http_module,
                "ssl_ctx_for_monitor",
                lambda _m: ssl.create_default_context(),
            )

            async with database.async_session_maker() as session:
                monitor_obj = await session.get(models.Monitor, monitor_id)
                hb = models.Heartbeat(monitor_id=monitor_id, status=0)
                await HTTPMonitor().check(monitor_obj, hb)
                assert hb.status == 1
                assert hb.msg.startswith("HTTP 200")
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_trust_proxy_middleware(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = (
        f"sqlite+aiosqlite:///{db_path.as_posix()}"
        if not db_path.is_absolute()
        else "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
    )

    # If `dist/` exists (e.g. someone ran `npm run build` recently) the
    # `app.mount("/", StaticFiles(...))` line in create_app shadows
    # every route registered after it — including the /whoami probe
    # route this test relies on. Force the mount-skip branch by making
    # `dist/` look absent; the test isn't exercising static serving.
    real_exists = Path.exists
    def patched_exists(self):
        if self.name == "dist":
            return False
        return real_exists(self)
    monkeypatch.setattr(Path, "exists", patched_exists)

    app = create_app()

    @app.get("/whoami")
    async def whoami(request: Request):
        return {"client": request.client.host}

    with TestClient(app) as client:
        token = client.post(
            "/api/setup", json={"username": "admin", "password": "admin"}
        ).json()["token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

        res = client.get(
            "/whoami", headers={"X-Forwarded-For": "198.51.100.5"}
        )
        assert res.status_code == 200
        assert res.json()["client"] != "198.51.100.5"

        client.post("/api/settings", json={"settings": {"trustProxy": True}})

        res = client.get(
            "/whoami", headers={"X-Forwarded-For": "198.51.100.5"}
        )
        assert res.status_code == 200
        assert res.json()["client"] == "198.51.100.5"


def test_cloudflared_start_stop(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = (
        f"sqlite+aiosqlite:///{db_path.as_posix()}"
        if not db_path.is_absolute()
        else "sqlite+aiosqlite:////" + db_path.as_posix().lstrip("/")
    )

    app = create_app()

    with TestClient(app) as client:
        token = client.post(
            "/api/setup", json={"username": "admin", "password": "admin"}
        ).json()["token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

        monkeypatch.setattr(
            "server.cloudflared.shutil.which", lambda _path: "/usr/bin/cloudflared"
        )

        class DummyProcess:
            def __init__(self):
                self.returncode = None
                self._event = asyncio.Event()

            async def communicate(self):
                await self._event.wait()
                return b"", b""

            def terminate(self):
                self.returncode = 0
                self._event.set()

            async def wait(self):
                await self._event.wait()
                return self.returncode

            def kill(self):
                self.returncode = -9
                self._event.set()

        async def fake_spawn(token):
            assert token == "abc123"
            return DummyProcess()

        monkeypatch.setattr(
            client.app.state.cloudflared, "_spawn_process", fake_spawn
        )

        res = client.post(
            "/api/reverse-proxy/cloudflared/start", json={"token": "abc123"}
        )
        data = res.json()
        assert data["ok"] is True
        assert data["data"]["running"] is True
        assert data["data"]["token"] == "abc123"

        settings = client.get("/api/settings").json()["data"]
        assert settings["cloudflared_token"] == "abc123"

        res = client.post("/api/reverse-proxy/cloudflared/stop", json={})
        data = res.json()
        assert data["ok"] is True
        assert data["data"]["running"] is False

        res = client.delete("/api/reverse-proxy/cloudflared/token")
        data = res.json()
        assert data["ok"] is True
        assert data["data"]["token"] == ""

        settings = client.get("/api/settings").json()["data"]
        assert "cloudflared_token" not in settings


def test_is_monitor_in_active_maintenance(client):
    """Single-strategy maintenance with a bracketing dateRange suppresses;
    inactive, expired, or otherwise-shaped windows do not."""
    from server.server import _is_monitor_in_active_maintenance
    from server.db import models
    from server.db.database import async_session_maker

    client.post(
        "/api/monitors",
        json={"id": 1, "name": "A", "url": "http://example.com"},
    )

    past = (datetime.datetime.utcnow() - datetime.timedelta(hours=1)).isoformat()
    future = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat()
    far_past = (datetime.datetime.utcnow() - datetime.timedelta(days=2)).isoformat()
    yesterday = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat()

    async def _check(maint_data: dict) -> bool:
        async with async_session_maker() as session:
            await session.execute(delete(models.MaintenanceMonitor))
            await session.execute(delete(models.Maintenance))
            await session.commit()
            m = models.Maintenance(data=__import__("json").dumps(maint_data))
            session.add(m)
            await session.commit()
            await session.refresh(m)
            session.add(
                models.MaintenanceMonitor(maintenance_id=m.id, monitor_id=1)
            )
            await session.commit()
            return await _is_monitor_in_active_maintenance(session, 1)

    # active + single + window brackets now → True
    assert asyncio.run(
        _check(
            {
                "active": True,
                "strategy": "single",
                "dateRange": [past, future],
            }
        )
    ) is True

    # active=False → False
    assert asyncio.run(
        _check(
            {
                "active": False,
                "strategy": "single",
                "dateRange": [past, future],
            }
        )
    ) is False

    # window expired → False
    assert asyncio.run(
        _check(
            {
                "active": True,
                "strategy": "single",
                "dateRange": [far_past, yesterday],
            }
        )
    ) is False

    # recurring strategies are not yet evaluated → False (no over-suppression)
    assert asyncio.run(
        _check(
            {
                "active": True,
                "strategy": "recurring-weekday",
                "dateRange": [past, future],
                "weekdays": [0, 1, 2, 3, 4, 5, 6],
                "timeRange": [{"hours": 0, "minutes": 0}, {"hours": 23, "minutes": 59}],
            }
        )
    ) is False


def test_pause_resume_dispatch_lifecycle_events(client, monkeypatch):
    """POST /pause and /resume should fire 'paused'/'resumed' events
    through attached notification channels."""
    from server.notification_providers import providers as registry

    captured = []

    class Capturing:
        async def send(self, cfg, message, monitor_data, heartbeat_data):
            captured.append(
                {
                    "message": message,
                    "monitor_id": monitor_data.get("id"),
                    "event": heartbeat_data.get("event"),
                }
            )
            return "ok"

    monkeypatch.setitem(registry, "fake-capture", Capturing())

    res = client.post(
        "/api/notifications",
        json={
            "name": "cap",
            "type": "fake-capture",
            "isDefault": True,
            "active": True,
            "config": {},
        },
    )
    assert res.status_code == 200

    client.post(
        "/api/monitors",
        json={"id": 1, "name": "PauseMe", "url": "http://example.com"},
    )

    res = client.post("/api/monitors/1/pause")
    assert res.status_code == 200
    # Drain any pending fire-and-forget dispatch tasks.
    from server.server import _pending_notification_tasks

    async def _drain():
        for _ in range(10):
            pending = [t for t in _pending_notification_tasks if not t.done()]
            if not pending:
                return
            await asyncio.gather(*pending, return_exceptions=True)

    asyncio.run(_drain())

    assert any(c["event"] == "paused" for c in captured), captured

    # A second pause (already paused) must NOT re-dispatch.
    before = len(captured)
    res = client.post("/api/monitors/1/pause")
    assert res.status_code == 200
    asyncio.run(_drain())
    assert len(captured) == before

    res = client.post("/api/monitors/1/resume")
    assert res.status_code == 200
    asyncio.run(_drain())
    assert any(c["event"] == "resumed" for c in captured), captured

