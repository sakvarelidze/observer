from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import select, text
import json
import os
from pathlib import Path

engine = None
async_session_maker = None
Base = declarative_base()


# Persistent config for the URL chosen via the in-app first-run wizard.
# Env var DATABASE_URL takes precedence, then this file, then we fall
# back to a throwaway SQLite "bootstrap" DB so the server can come up
# at all and serve the wizard. Path is relative to CWD which matches
# the project's existing `./data/` convention (compose mounts it).
DB_CONFIG_PATH = Path("data") / "db.config.json"
BOOTSTRAP_DATABASE_URL = "sqlite+aiosqlite:///./data/_bootstrap.db"


def resolve_database_url() -> str:
    """Pick the active DATABASE_URL with env > config file > bootstrap precedence."""
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    if DB_CONFIG_PATH.exists():
        try:
            with open(DB_CONFIG_PATH) as f:
                cfg = json.load(f)
            if cfg.get("url"):
                return cfg["url"]
        except Exception:
            # Corrupt config file — log via print and fall through to
            # bootstrap so the wizard can rewrite it.
            print(f"WARN: db.config.json is unreadable: {DB_CONFIG_PATH}")

    return BOOTSTRAP_DATABASE_URL


def is_bootstrap_database() -> bool:
    """True iff the active engine is the throwaway bootstrap SQLite —
    i.e. neither env var nor config file points anywhere real, and the
    server is running so it can serve the database-setup wizard."""
    if os.getenv("DATABASE_URL"):
        return False
    if DB_CONFIG_PATH.exists():
        try:
            with open(DB_CONFIG_PATH) as f:
                cfg = json.load(f)
            if cfg.get("url"):
                return False
        except Exception:
            pass
    return True


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    """Make the directory containing the SQLite file ahead of opening,
    so the driver doesn't fail with `unable to open database file` on
    fresh checkouts where `./data/` doesn't exist yet."""
    if not database_url.startswith("sqlite"):
        return
    try:
        from sqlalchemy.engine.url import make_url
        url = make_url(database_url)
    except Exception:
        return
    db_path = url.database
    if not db_path or db_path == ":memory:":
        return
    parent = Path(db_path).parent
    if str(parent) and parent != Path(""):
        parent.mkdir(parents=True, exist_ok=True)


def write_database_config(database_url: str) -> None:
    """Persist a chosen URL so future starts pick it up. The file
    contains the DB password — restrict permissions to 0600 on POSIX."""
    DB_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB_CONFIG_PATH.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump({"url": database_url}, f, indent=2)
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    os.replace(tmp, DB_CONFIG_PATH)


async def init_db(database_url: str | None = None):
    """Initialize (or reinitialize) the database engine and create tables.

    Supports SQLite, Postgres, and MySQL/MariaDB. Pass `database_url`
    to point at a specific URL (used by the setup wizard's "apply"
    flow when the user picks an engine). Otherwise resolves via env
    var → config file → bootstrap fallback.

    The legacy Kuma schema migration only runs on SQLite — those legacy
    databases never existed on Postgres or MySQL because Observer's
    rewrite of the backend is the first version to support them.
    """
    global engine, async_session_maker

    if database_url is None:
        database_url = resolve_database_url()

    # SQLite refuses to open a file whose parent directory doesn't exist
    # — and on a fresh checkout there's no `data/` yet. Make the parent
    # before handing the URL to the driver. No-op for in-memory or for
    # non-sqlite engines.
    _ensure_sqlite_parent_dir(database_url)

    # If we're called a second time (post-wizard swap), tear down the
    # previous engine first so its connection pool drains cleanly.
    if engine is not None:
        try:
            await engine.dispose()
        except Exception:
            pass

    engine = create_async_engine(database_url, future=True, echo=False)
    async_session_maker = sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    from . import models  # noqa

    is_sqlite = engine.dialect.name == "sqlite"

    async def _init():
        async with engine.begin() as conn:
            if is_sqlite:
                # SQLite path needs renames-before-create and ALTERs-after.
                await _sqlite_legacy_migration(conn)
            else:
                # Postgres / MySQL: clean schema, create_all is enough.
                await conn.run_sync(Base.metadata.create_all)

        async with async_session_maker() as session:
            seed_demo = os.getenv("DB_SEED") and not os.getenv("PYTEST_CURRENT_TEST")
            if seed_demo:
                res = await session.execute(select(models.User).limit(1))
                if res.scalar_one_or_none() is None:
                    from passlib.context import CryptContext

                    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
                    user = models.User(
                        username="admin",
                        password=pwd_context.hash("admin"),
                        is_admin=True,
                        active=True,
                    )
                    session.add(user)

                res = await session.execute(select(models.Monitor).limit(1))
                if res.scalar_one_or_none() is None:
                    demo = models.Monitor(
                        name="Example Monitor",
                        url="https://example.org",
                        type="http",
                        interval=30,
                        maxretries=0,
                        retry_interval=0,
                        resend_interval=0,
                        ignore_tls=False,
                        expiry_notification=False,
                        maxredirects=10,
                        accepted_statuscodes_json='["200-299"]',
                        invert_keyword=False,
                        ping_numeric=True,
                        ping_count=3,
                        ping_per_request_timeout=2,
                        packet_size=56,
                    )
                    session.add(demo)
                    await session.commit()
                    session.add(
                        models.Heartbeat(monitor_id=demo.id, status=1, msg="OK")
                    )
                    await session.commit()

    await _init()


async def _sqlite_legacy_migration(conn):
    """Bring an existing SQLite database from the original Node.js Kuma
    layout up to the current schema. Only relevant for SQLite — the
    Postgres/MySQL backends are new with the Python rewrite and start
    from a clean schema via Base.metadata.create_all.
    """
    # Detect legacy table names from the Node.js version and rename
    result = await conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    tables = {row[0] for row in result.fetchall()}
    if "monitor" in tables and "monitors" not in tables:
        await conn.execute(text("ALTER TABLE monitor RENAME TO monitors"))
    if "heartbeat" in tables and "heartbeats" not in tables:
        await conn.execute(text("ALTER TABLE heartbeat RENAME TO heartbeats"))
    if "notification" in tables and "notifications" not in tables:
        await conn.execute(text("ALTER TABLE notification RENAME TO notifications"))
    if "setting" in tables and "settings" not in tables:
        await conn.execute(text("ALTER TABLE setting RENAME TO settings"))
    if "monitor_notification" in tables and "monitor_notifications" not in tables:
        await conn.execute(
            text("ALTER TABLE monitor_notification RENAME TO monitor_notifications")
        )
    if "proxy" in tables and "proxies" not in tables:
        await conn.execute(text("ALTER TABLE proxy RENAME TO proxies"))

    # Bring the schema up to current — creates any missing tables but
    # doesn't ALTER existing ones; the column-by-column ALTER block
    # below handles that.
    await conn.run_sync(Base.metadata.create_all)

    # Remove legacy setting key left from older versions
    await conn.execute(text("DELETE FROM settings WHERE key='SetupDone'"))

    # Add newly introduced columns if they do not exist yet.
    result = await conn.execute(text("PRAGMA table_info(monitors)"))
    cols = {row[1] for row in result.fetchall()}
    if "type" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN type TEXT DEFAULT 'http'")
        )
    if "interval" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN interval INTEGER DEFAULT 30")
        )
    else:
        try:
            await conn.execute(
                text(
                    "ALTER TABLE monitors ALTER COLUMN interval SET DEFAULT 30"
                )
            )
        except Exception:
            pass
    if "maxretries" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN maxretries INTEGER DEFAULT 0"
            )
        )
    if "retry_interval" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN retry_interval INTEGER DEFAULT 0"
            )
        )
    if "resend_interval" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN resend_interval INTEGER DEFAULT 0"
            )
        )
    if "ignore_tls" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN ignore_tls BOOLEAN DEFAULT 0"
            )
        )
    if "tls_verify_mode" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN tls_verify_mode TEXT DEFAULT 'system'"
            )
        )
    if "custom_ca_pem" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN custom_ca_pem TEXT")
        )
    if "custom_ca_sha256" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN custom_ca_sha256 TEXT")
        )
    if "custom_ca_subject" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN custom_ca_subject TEXT")
        )
    if "custom_ca_issuer" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN custom_ca_issuer TEXT")
        )
    if "custom_ca_trusted_at" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN custom_ca_trusted_at DATETIME")
        )
    if "expiry_notification" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN expiry_notification BOOLEAN DEFAULT 0"
            )
        )
    if "maxredirects" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN maxredirects INTEGER DEFAULT 10"
            )
        )
    if "cache_bust" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN cache_bust BOOLEAN DEFAULT 0"
            )
        )
    if "upside_down" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN upside_down BOOLEAN DEFAULT 0"
            )
        )
    if "accepted_statuscodes_json" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN accepted_statuscodes_json TEXT DEFAULT '[\"200-299\"]'"
            )
        )
    if "hostname" not in cols:
        await conn.execute(text("ALTER TABLE monitors ADD COLUMN hostname TEXT"))
        await conn.execute(text("ALTER TABLE monitors ADD COLUMN port INTEGER"))
    if "dns_resolve_type" not in cols:
        await conn.execute(text("ALTER TABLE monitors ADD COLUMN dns_resolve_type TEXT"))
    if "dns_resolve_server" not in cols:
        await conn.execute(text("ALTER TABLE monitors ADD COLUMN dns_resolve_server TEXT"))
    if "dns_last_result" not in cols:
        await conn.execute(text("ALTER TABLE monitors ADD COLUMN dns_last_result TEXT"))
    if "invert_keyword" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN invert_keyword BOOLEAN DEFAULT 0")
        )
    if "parent" not in cols:
        await conn.execute(text("ALTER TABLE monitors ADD COLUMN parent INTEGER"))
    if "proxy_id" not in cols:
        await conn.execute(text("ALTER TABLE monitors ADD COLUMN proxy_id INTEGER"))
    if "description" not in cols:
        await conn.execute(text("ALTER TABLE monitors ADD COLUMN description TEXT"))
    if "method" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN method TEXT DEFAULT 'GET'")
        )
    if "body" not in cols:
        await conn.execute(text("ALTER TABLE monitors ADD COLUMN body TEXT"))
    if "headers_json" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN headers_json TEXT")
        )
    if "basic_auth_user" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN basic_auth_user TEXT")
        )
    if "basic_auth_pass" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN basic_auth_pass TEXT")
        )
    if "ping_numeric" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN ping_numeric BOOLEAN DEFAULT 1")
        )
    if "ping_count" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN ping_count INTEGER DEFAULT 3")
        )
    if "ping_per_request_timeout" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN ping_per_request_timeout INTEGER DEFAULT 2"
            )
        )
    if "packet_size" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN packet_size INTEGER DEFAULT 56")
        )
    if "cert_expiry_threshold_days" not in cols:
        await conn.execute(
            text(
                "ALTER TABLE monitors ADD COLUMN cert_expiry_threshold_days INTEGER DEFAULT 14"
            )
        )
    if "last_cert_notified_days" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN last_cert_notified_days INTEGER")
        )
    if "last_cert_notified_at" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN last_cert_notified_at DATETIME")
        )
    if "slow_response_threshold_ms" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN slow_response_threshold_ms INTEGER")
        )
    if "slow_response_consecutive" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN slow_response_consecutive INTEGER DEFAULT 3")
        )
    if "slow_alert_active" not in cols:
        await conn.execute(
            text("ALTER TABLE monitors ADD COLUMN slow_alert_active BOOLEAN DEFAULT 0")
        )

    result = await conn.execute(text("PRAGMA table_info(users)"))
    user_cols = {row[1] for row in result.fetchall()}
    if "active" not in user_cols:
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN active BOOLEAN DEFAULT 1")
        )
    if "two_fa_secret" not in user_cols:
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN two_fa_secret TEXT")
        )
    if "two_fa_enabled" not in user_cols:
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN two_fa_enabled BOOLEAN DEFAULT 0")
        )
    if "two_fa_temp_secret" not in user_cols:
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN two_fa_temp_secret TEXT")
        )
    if "two_fa_temp_verified_at" not in user_cols:
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN two_fa_temp_verified_at DATETIME")
        )

    result = await conn.execute(text("PRAGMA table_info(heartbeats)"))
    hb_cols = {row[1] for row in result.fetchall()}
    if "cert_expire" not in hb_cols:
        await conn.execute(
            text("ALTER TABLE heartbeats ADD COLUMN cert_expire INTEGER")
        )

    result = await conn.execute(text("PRAGMA table_info(status_pages)"))
    sp_cols = {row[1] for row in result.fetchall()}
    if "public" not in sp_cols:
        await conn.execute(
            text("ALTER TABLE status_pages ADD COLUMN public BOOLEAN DEFAULT 1")
        )

    result = await conn.execute(text("PRAGMA table_info(notifications)"))
    if not result.fetchall():
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS notifications ("
                "id INTEGER PRIMARY KEY,"
                "name TEXT NOT NULL,"
                "type TEXT NOT NULL,"
                "active BOOLEAN DEFAULT 1,"
                "is_default BOOLEAN DEFAULT 0,"
                "config TEXT"
                ")"
            )
        )
