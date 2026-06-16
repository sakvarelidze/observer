from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import argparse
import os
import sys
from pathlib import Path
import jwt
from typing import Callable

# make the repository root importable when running this file directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.routers import api
from server.db import init_db, models, database
from server.monitor_types.http import HTTPMonitor
from server.monitor_types import monitor_types, is_actively_probed
from server.notification_providers import get_provider
from sqlalchemy import and_, delete, func, select, text
from sqlalchemy.orm import selectinload
from server.settings import DEFAULT_INTERVAL_SECONDS, MIN_INTERVAL_SECONDS
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi_utils.tasks import repeat_every
import datetime
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Scope, Receive, Send

from server.cloudflared import CloudflaredManager

# Parse --data-file early so the database can be initialized with it
_early_parser = argparse.ArgumentParser(add_help=False)
_early_parser.add_argument("--data-file")
_early_args, _ = _early_parser.parse_known_args()
if _early_args.data_file:
    data_path = Path(_early_args.data_file)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{data_path}")

RUNNER_TICK_SECONDS = int(
    os.getenv("RUNNER_TICK_SECONDS", os.getenv("MONITOR_RUNNER_INTERVAL", "5"))
)

# Heartbeat retention prune cadence. Hourly is plenty — nothing about the
# database becomes urgent over a single hour, and the user-configured
# `keepDataPeriodDays` is in days.
HEARTBEAT_PRUNE_INTERVAL_SECONDS = int(
    os.getenv("HEARTBEAT_PRUNE_INTERVAL_SECONDS", "3600")
)
DEFAULT_HEARTBEAT_RETENTION_DAYS = 180

# Strong references to in-flight fire-and-forget notification dispatch
# tasks. Without this, asyncio's loop only weakly references them and
# they can be GC'd mid-flight, dropping the alert silently.
_pending_notification_tasks: "set[asyncio.Task]" = set()


def _dispatch_notification_async(
    notif,
    message: str,
    monitor_data: dict,
    heartbeat_data: dict,
) -> None:
    """Fire-and-forget a single notification send.

    Decouples webhook latency from the monitor runner's tick — a slow
    Slack/Discord/Telegram receiver no longer delays the next probe.
    Exceptions are caught and logged inside the task so the runner keeps
    going regardless.
    """
    provider = get_provider(notif.type)
    if not provider:
        return
    cfg = api.coerce_config_to_dict(notif.config)

    async def _runner() -> None:
        try:
            await provider.send(cfg, message, monitor_data, heartbeat_data)
        except Exception as exc:
            print(
                f"Failed to send notification {notif.name} "
                f"for monitor {monitor_data.get('id')}: {exc}"
            )

    task = asyncio.create_task(_runner())
    _pending_notification_tasks.add(task)
    task.add_done_callback(_pending_notification_tasks.discard)


async def _is_monitor_in_active_maintenance(session, monitor_id: int) -> bool:
    """Return True iff the monitor is currently inside an active maintenance window.

    Used by monitor_runner to suppress up/down and slow-response notifications
    while a planned maintenance is in effect. TLS expiry alerts are NOT
    suppressed — they aren't about service availability and the user still
    needs to renew.

    Strategies fully evaluated: ``single`` (the standard "from X to Y" window).
    Strategies not yet evaluated: ``cron``, ``recurring-interval``,
    ``recurring-weekday``, ``recurring-day-of-month`` — these require cron
    parsing and per-tz recurrence math that we haven't wired up. They return
    False (no suppression) rather than risk silently muting real outages.
    """
    res = await session.execute(
        select(models.Maintenance)
        .join(
            models.MaintenanceMonitor,
            models.Maintenance.id == models.MaintenanceMonitor.maintenance_id,
        )
        .where(models.MaintenanceMonitor.monitor_id == monitor_id)
    )
    maintenances = list(res.scalars().all())
    if not maintenances:
        return False

    now = datetime.datetime.utcnow()
    for m in maintenances:
        try:
            data = json.loads(m.data or "{}")
        except (TypeError, ValueError):
            continue
        if not data.get("active", False):
            continue
        if data.get("strategy", "single") != "single":
            # Recurring/cron strategies are not yet evaluated. Skip them
            # rather than over-suppress.
            continue
        date_range = data.get("dateRange") or ["", ""]
        if len(date_range) < 2 or not date_range[0] or not date_range[1]:
            continue
        try:
            start = datetime.datetime.fromisoformat(date_range[0])
            end = datetime.datetime.fromisoformat(date_range[1])
        except (TypeError, ValueError):
            continue
        if start <= now <= end:
            return True
    return False


async def _load_last_heartbeats(session, monitor_ids):
    """Return {monitor_id: latest Heartbeat} for the given monitor IDs.

    Replaces an N+1 loop (one SELECT per monitor) with a single greatest-
    time-per-group query — the inner aggregate computes max(time) per
    monitor, and the outer SELECT pulls the matching Heartbeat row. The
    `ix_heartbeats_monitor_time` composite index covers both the
    aggregate and the join. With a 50-monitor fleet this drops the
    per-tick warmup from 50 round-trips to 1.

    Monitors with no heartbeats simply don't appear in the result;
    callers should treat a missing key as "no prior heartbeat" — the
    same shape the old per-monitor SELECT returned via .first() = None.
    """
    if not monitor_ids:
        return {}

    max_subq = (
        select(
            models.Heartbeat.monitor_id.label("mid"),
            func.max(models.Heartbeat.time).label("mt"),
        )
        .where(models.Heartbeat.monitor_id.in_(monitor_ids))
        .group_by(models.Heartbeat.monitor_id)
        .subquery()
    )

    res = await session.execute(
        select(models.Heartbeat).join(
            max_subq,
            and_(
                models.Heartbeat.monitor_id == max_subq.c.mid,
                models.Heartbeat.time == max_subq.c.mt,
            ),
        )
    )
    rows = res.scalars().all()

    # Tie-break: if two heartbeats share an exact-microsecond time (rare
    # but possible on fast probes), keep the one with the highest id —
    # that's the most recent insert.
    out = {}
    for hb in rows:
        existing = out.get(hb.monitor_id)
        if existing is None or hb.id > existing.id:
            out[hb.monitor_id] = hb
    return out


async def _prune_old_heartbeats() -> int:
    """One-shot heartbeat retention prune. Returns rows deleted.

    Reads `keepDataPeriodDays` from the settings table (default 180) and
    deletes heartbeats older than now - days. Exposed at module level so
    tests can drive it directly without waiting for the @repeat_every
    schedule to fire.
    """
    async with database.async_session_maker() as session:
        res = await session.execute(
            select(models.Setting).where(
                models.Setting.key == "keepDataPeriodDays"
            )
        )
        setting = res.scalar_one_or_none()
        days = DEFAULT_HEARTBEAT_RETENTION_DAYS
        if setting is not None and setting.value is not None:
            try:
                days = int(json.loads(setting.value))
            except Exception:
                try:
                    days = int(setting.value)
                except (TypeError, ValueError):
                    days = DEFAULT_HEARTBEAT_RETENTION_DAYS

        # Sanity guard — refuse to wipe everything on a bad value.
        if days < 1:
            return 0

        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        result = await session.execute(
            delete(models.Heartbeat).where(models.Heartbeat.time < cutoff)
        )
        await session.commit()
        return result.rowcount or 0


class ConditionalProxyHeadersMiddleware:
    """Apply proxy header parsing only when explicitly enabled."""

    def __init__(self, app: ASGIApp, enabled_getter: Callable[[], bool]):
        self.app = app
        self.enabled_getter = enabled_getter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in {"http", "websocket"} and self.enabled_getter():
            self.apply_proxy_headers(scope)
        await self.app(scope, receive, send)

    @staticmethod
    def apply_proxy_headers(scope: Scope) -> None:
        headers = Headers(scope=scope)
        client = scope.get("client") or (None, None)
        host, port = client

        forwarded = headers.get("forwarded")
        client_host = None
        if forwarded:
            first = forwarded.split(",", 1)[0]
            parts = [p.strip() for p in first.split(";")]
            for part in parts:
                if part.lower().startswith("for="):
                    client_host = part.split("=", 1)[1].strip("\"")
                    break
        if not client_host:
            xff = headers.get("x-forwarded-for")
            if xff:
                client_host = xff.split(",")[0].strip()

        if client_host:
            if client_host.startswith("[") and "]" in client_host:
                addr = client_host
                rest = client_host.split("]", 1)[1]
                if rest.startswith(":"):
                    try:
                        port = int(rest[1:])
                    except ValueError:
                        pass
                host = addr
            elif ":" in client_host:
                host_part, maybe_port = client_host.rsplit(":", 1)
                if maybe_port.isdigit():
                    host = host_part
                    port = int(maybe_port)
                else:
                    host = client_host
            else:
                host = client_host

        xproto = headers.get("x-forwarded-proto")
        if xproto:
            scope["scheme"] = xproto.split(",")[0].strip()

        xport = headers.get("x-forwarded-port")
        if xport and xport.isdigit():
            port = int(xport)

        scope["client"] = (host, port)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Forward-references to functions defined later in create_app —
        # Python resolves them at call time, by which point the closure
        # bindings exist. monitor_runner self-schedules via @repeat_every,
        # so awaiting it once kicks off the background loop.
        await init_database()
        # Skip the rest of startup if we're on the bootstrap DB — there's
        # no real schema to read from yet, and the runner / pruner would
        # just churn against the throwaway SQLite. They get spun up after
        # the wizard swaps in the real DB (see /api/setup-database).
        if not app.state.needs_db_setup:
            await load_proxy_settings()
            await repair_notification_configs()
            await apply_interval_default_to_legacy()
            await monitor_runner()
            await heartbeat_pruner()
        yield

    app = FastAPI(lifespan=lifespan)

    app.state.trust_proxy_enabled = False
    app.state.cloudflared = CloudflaredManager()
    app.state.needs_db_setup = False
    # Expose for the setup-database endpoint to call after a successful
    # save — flipping the flag and (re-)kicking the background workers.
    app.state.start_background_workers = None

    async def init_database():
        await init_db()
        app.state.needs_db_setup = database.is_bootstrap_database()

    async def load_proxy_settings() -> None:
        async with database.async_session_maker() as session:
            # trustProxy flag
            res = await session.execute(
                select(models.Setting).where(models.Setting.key == "trustProxy")
            )
            setting = res.scalar_one_or_none()
            if setting is not None:
                raw = setting.value
                enabled = False
                if isinstance(raw, str):
                    try:
                        enabled = bool(json.loads(raw))
                    except Exception:
                        enabled = raw.lower() in {"1", "true", "yes"}
                else:
                    enabled = bool(raw)
                app.state.trust_proxy_enabled = enabled
            else:
                app.state.trust_proxy_enabled = False

            # cloudflared token
            res = await session.execute(
                select(models.Setting).where(
                    models.Setting.key == "cloudflared_token"
                )
            )
            token_setting = res.scalar_one_or_none()
            token = token_setting.value if token_setting else None
            app.state.cloudflared.set_token(token)

    PUBLIC_PATHS = {
        "/api/login",
        "/api/setup-needed",
        "/api/setup",
        "/api/entry-page",
        "/api/setup-database-info",
        "/api/setup-database",
        "/api/setup-database/test",
    }
    # Path-prefix exemptions (badges live under /api/badges/<id>.svg).
    PUBLIC_PATH_PREFIXES = ("/api/badges/",)

    def _is_public_path(path: str) -> bool:
        return path in PUBLIC_PATHS or path.startswith(PUBLIC_PATH_PREFIXES)

    needs_setup: bool | None = None

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        nonlocal needs_setup
        if request.method == "OPTIONS":
            return await call_next(request)

        # Bootstrap mode: nothing else can be reached until the user
        # picks a database via the wizard. Anything not on the
        # setup-database surface returns 403 dbSetupNeeded.
        if app.state.needs_db_setup and request.url.path.startswith("/api"):
            if _is_public_path(request.url.path):
                return await call_next(request)
            return JSONResponse(
                status_code=403, content={"detail": "dbSetupNeeded"}
            )

        if needs_setup is not False:
            async with database.async_session_maker() as session:
                res = await session.execute(
                    select(models.Setting).where(models.Setting.key == "setup_done")
                )
                setting = res.scalar_one_or_none()
                if setting:
                    needs_setup = False
                else:
                    res = await session.execute(select(models.User).limit(1))
                    needs_setup = res.scalar_one_or_none() is None

        if needs_setup and request.url.path.startswith("/api") and not _is_public_path(request.url.path):
            return JSONResponse(status_code=403, content={"detail": "setupNeeded"})

        if request.url.path.startswith("/api") and not _is_public_path(request.url.path):
            if request.method == "GET" and request.url.path.startswith("/api/status-page"):
                parts = request.url.path.split("/")
                slug = None
                if len(parts) >= 4:
                    if parts[3] == "heartbeat" and len(parts) >= 5:
                        slug = parts[4]
                    else:
                        slug = parts[3]
                if slug:
                    async with database.async_session_maker() as session:
                        res = await session.execute(
                            select(models.StatusPage).where(models.StatusPage.slug == slug)
                        )
                        page = res.scalar_one_or_none()
                    if page and getattr(page, "public", True):
                        return await call_next(request)

            auth = request.headers.get("Authorization")
            if auth and auth.startswith("Bearer "):
                token = auth[7:]
                try:
                    jwt.decode(token, api.JWT_SECRET, algorithms=[api.JWT_ALGORITHM])
                    return await call_next(request)
                except jwt.PyJWTError:
                    return JSONResponse(
                        status_code=401, content={"detail": "invalidToken"}
                    )
            required = "write" if request.method not in {"GET", "HEAD"} else "read"
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                return JSONResponse(
                    status_code=403, content={"detail": "missingAPIKey"}
                )
            async with database.async_session_maker() as session:
                try:
                    await api.verify_api_key(api_key, session, required)
                except api.HTTPException as e:  # type: ignore[attr-defined]
                    return JSONResponse(
                        status_code=e.status_code, content={"detail": e.detail}
                    )
        return await call_next(request)

    app.add_middleware(
        ConditionalProxyHeadersMiddleware,
        enabled_getter=lambda: bool(
            getattr(app.state, "trust_proxy_enabled", False)
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api.router)

    async def repair_notification_configs():
        async with database.async_session_maker() as session:
            result = await session.execute(
                select(models.Notification).where(models.Notification.type == "teams")
            )
            any_changes = False
            for notif in result.scalars().all():
                cfg = api.coerce_config_to_dict(notif.config)
                if "webhook_u_r_l" in cfg and "webhook_url" not in cfg:
                    cfg["webhook_url"] = cfg.pop("webhook_u_r_l")
                json_cfg = json.dumps(cfg)
                if notif.config != json_cfg:
                    notif.config = json_cfg
                    any_changes = True
            if any_changes:
                await session.commit()

    async def apply_interval_default_to_legacy():
        if os.getenv("APPLY_DEFAULT_INTERVAL_ON_STARTUP", "false").lower() != "true":
            return
        async with database.async_session_maker() as session:
            await session.execute(
                text(
                    """
                    UPDATE monitors
                    SET interval = :new_default
                    WHERE (interval IS NULL OR interval < :min_ok OR interval = 60)
                    """
                ),
                {"new_default": DEFAULT_INTERVAL_SECONDS, "min_ok": MIN_INTERVAL_SECONDS},
            )
            await session.commit()

    # Serve the built frontend if available
    static_dir = Path(__file__).resolve().parent.parent / "dist"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_handler(full_path: str) -> FileResponse:
            """Return index.html for any SPA route."""
            return FileResponse(static_dir / "index.html")

    # Run a lightweight tick and only check monitors that are due.
    # A small tick (default 5s) ensures shorter intervals are honored without heavy load.
    @repeat_every(seconds=RUNNER_TICK_SECONDS, wait_first=False)
    async def monitor_runner() -> None:
        """Check all active monitors and store heartbeats."""
        async with database.async_session_maker() as session:
            res = await session.execute(
                select(models.Monitor)
                .options(selectinload(models.Monitor.proxy))
                .where(models.Monitor.active == True)
            )
            monitors = res.scalars().all()

            now = datetime.datetime.utcnow()
            tasks: list[asyncio.Future] = []
            results: list[tuple[models.Monitor, models.Heartbeat]] = []

            # Single greatest-time-per-group query instead of one per
            # monitor — see _load_last_heartbeats for details.
            last_map = await _load_last_heartbeats(
                session, [m.id for m in monitors]
            )

            for m in monitors:
                # Passive monitors (push) deliver their own heartbeats via
                # the /push endpoint — actively probing them here would
                # fall through to the HTTPMonitor default and clobber the
                # pushed status with a spurious HTTP result every tick.
                if not is_actively_probed(m.type):
                    continue
                interval = max(
                    int(getattr(m, "interval", DEFAULT_INTERVAL_SECONDS) or DEFAULT_INTERVAL_SECONDS),
                    MIN_INTERVAL_SECONDS,
                )
                last = last_map.get(m.id)
                is_due = (last is None) or (
                    (now - last.time).total_seconds() >= interval
                )
                if not is_due:
                    continue

                hb = models.Heartbeat(monitor_id=m.id)
                monitor_cls = monitor_types.get(m.type, HTTPMonitor)
                tasks.append(monitor_cls().check(m, hb))
                results.append((m, hb))

            if tasks:
                # `return_exceptions=True` so a single misbehaving probe
                # doesn't abort the whole tick — without this, gather
                # re-raises on the first failure and every other monitor
                # in this batch silently loses its heartbeat for the
                # tick. Convert the failure into a DOWN heartbeat with
                # the error message so the operator notices.
                gather_results = await asyncio.gather(
                    *tasks, return_exceptions=True
                )
                for (m, hb), gres in zip(results, gather_results):
                    if isinstance(gres, BaseException):
                        print(
                            f"Monitor {m.id} ({m.name}) check raised: {gres!r}"
                        )
                        hb.status = 0
                        hb.msg = f"Internal probe error: {gres!r}"
                        hb.ping = None

            for m, hb in results:
                # Use the preloaded last heartbeat to detect status changes
                last = last_map.get(m.id)
                if last is None or last.status != hb.status:
                    hb.important = True
                    # expose a simple event label for formatters
                    hb.event = "up" if hb.status in (1, True) else "down"
                    session.add(
                        models.ImportantHeartbeat(monitor_id=m.id, message=hb.msg)
                    )
                session.add(hb)
            await session.commit()

            # Send certificate expiry notifications
            for m, hb in results:
                if not getattr(m, "expiry_notification", False):
                    continue
                if hb.cert_expire is None:
                    continue
                threshold = getattr(m, "cert_expiry_threshold_days", 14) or 14
                if hb.cert_expire > threshold:
                    continue

                resend_ok = True
                if m.last_cert_notified_at:
                    resend_ok = (
                        datetime.datetime.utcnow() - m.last_cert_notified_at
                    ) >= datetime.timedelta(hours=24)

                if (
                    m.last_cert_notified_days is None
                    or hb.cert_expire < m.last_cert_notified_days
                    or resend_ok
                ):
                    res_notif = await session.execute(
                        select(models.Notification)
                        .join(
                            models.MonitorNotification,
                            models.Notification.id
                            == models.MonitorNotification.notification_id,
                        )
                        .where(
                            models.MonitorNotification.monitor_id == m.id,
                            models.Notification.active == True,
                        )
                    )
                    notifications = list(res_notif.scalars().unique().all())

                    res_def = await session.execute(
                        select(models.Notification).where(
                            models.Notification.is_default == True,
                            models.Notification.active == True,
                        )
                    )
                    defs = res_def.scalars().all()
                    seen = {n.id for n in notifications}
                    notifications.extend([n for n in defs if n.id not in seen])

                    msg = f"Certificate expires in {hb.cert_expire} days"
                    monitor_data = {
                        "id": m.id,
                        "name": m.name,
                        "url": m.url,
                        "hostname": m.hostname,
                        "port": m.port,
                        "type": m.type,
                    }
                    heartbeat_data = hb.to_json()
                    heartbeat_data["event"] = getattr(hb, "event", None)

                    for notif in notifications:
                        _dispatch_notification_async(
                            notif, msg, monitor_data, heartbeat_data
                        )

                    m.last_cert_notified_days = hb.cert_expire
                    m.last_cert_notified_at = datetime.datetime.utcnow()

            await session.commit()

            # Dispatch notifications for monitors with important heartbeats
            for m, hb in results:
                if not hb.important:
                    continue
                if await _is_monitor_in_active_maintenance(session, m.id):
                    continue

                res_notif = await session.execute(
                    select(models.Notification)
                    .join(
                        models.MonitorNotification,
                        models.Notification.id
                        == models.MonitorNotification.notification_id,
                    )
                    .where(
                        models.MonitorNotification.monitor_id == m.id,
                        models.Notification.active == True,
                    )
                )
                notifications = list(res_notif.scalars().unique().all())

                res_def = await session.execute(
                    select(models.Notification).where(
                        models.Notification.is_default == True,
                        models.Notification.active == True,
                    )
                )
                defs = res_def.scalars().all()
                seen = {n.id for n in notifications}
                notifications.extend([n for n in defs if n.id not in seen])

                monitor_data = {
                    "id": m.id,
                    "name": m.name,
                    "url": m.url,
                    "hostname": m.hostname,
                    "port": m.port,
                    "type": m.type,
                }
                heartbeat_data = hb.to_json()
                heartbeat_data["event"] = getattr(hb, "event", None)

                for notif in notifications:
                    _dispatch_notification_async(
                        notif, hb.msg, monitor_data, heartbeat_data
                    )

            # Slow-response detection. Independent of the up/down
            # important-heartbeat path: a probe can be UP-but-slow,
            # which doesn't flip `hb.important`. We track per-monitor
            # state via Monitor.slow_alert_active so we don't re-fire
            # on every slow probe in the same streak.
            for m, hb in results:
                threshold = getattr(m, "slow_response_threshold_ms", None)
                if not threshold or threshold <= 0:
                    continue

                is_slow = (
                    hb.status == 1
                    and hb.ping is not None
                    and hb.ping > threshold
                )

                if not is_slow:
                    # Any non-slow probe (fast UP or DOWN) clears the
                    # debounce so the next slow streak fires fresh.
                    if m.slow_alert_active:
                        m.slow_alert_active = False
                        session.add(m)
                    continue

                # Already alerted for this slow streak — don't re-fire.
                if getattr(m, "slow_alert_active", False):
                    continue

                if await _is_monitor_in_active_maintenance(session, m.id):
                    continue

                # Confirm the streak: this probe + the previous (N-1)
                # probes must all be slow UPs. Pulling N-1 from the DB
                # because the runner just inserted `hb` and we don't
                # want to read-back-our-own-write.
                consecutive_required = (
                    getattr(m, "slow_response_consecutive", None) or 3
                )
                if consecutive_required < 1:
                    consecutive_required = 1

                if consecutive_required > 1:
                    res_recent = await session.execute(
                        select(models.Heartbeat)
                        .where(
                            models.Heartbeat.monitor_id == m.id,
                            models.Heartbeat.id != hb.id,
                        )
                        .order_by(models.Heartbeat.time.desc())
                        .limit(consecutive_required - 1)
                    )
                    recents = list(res_recent.scalars().all())
                    if len(recents) < consecutive_required - 1:
                        continue  # not enough history yet
                    if not all(
                        h.status == 1
                        and h.ping is not None
                        and h.ping > threshold
                        for h in recents
                    ):
                        continue

                # Fire. Mark debounce + load notifications + dispatch.
                m.slow_alert_active = True
                session.add(m)

                res_notif = await session.execute(
                    select(models.Notification)
                    .join(
                        models.MonitorNotification,
                        models.Notification.id
                        == models.MonitorNotification.notification_id,
                    )
                    .where(
                        models.MonitorNotification.monitor_id == m.id,
                        models.Notification.active == True,
                    )
                )
                notifications = list(res_notif.scalars().unique().all())
                res_def = await session.execute(
                    select(models.Notification).where(
                        models.Notification.is_default == True,
                        models.Notification.active == True,
                    )
                )
                defs = res_def.scalars().all()
                seen = {n.id for n in notifications}
                notifications.extend([n for n in defs if n.id not in seen])

                monitor_data = {
                    "id": m.id,
                    "name": m.name,
                    "url": m.url,
                    "hostname": m.hostname,
                    "port": m.port,
                    "type": m.type,
                }
                heartbeat_data = hb.to_json()
                heartbeat_data["event"] = "slow"
                heartbeat_data["threshold_ms"] = threshold

                for notif in notifications:
                    _dispatch_notification_async(
                        notif,
                        f"{m.name} responding slowly ({int(hb.ping)}ms)",
                        monitor_data,
                        heartbeat_data,
                    )

            # Persist the slow_alert_active flag changes from this tick.
            await session.commit()

    @repeat_every(seconds=HEARTBEAT_PRUNE_INTERVAL_SECONDS, wait_first=True)
    async def heartbeat_pruner() -> None:
        """Drop heartbeats older than the user-configured retention window.

        Without this, the SQLite database grows unbounded — a 30-second
        monitor accumulates ~1M rows/year. The frontend `Monitor History`
        settings page writes `keepDataPeriodDays`; we honor that here.
        """
        try:
            await _prune_old_heartbeats()
        except Exception as exc:
            print(f"Heartbeat prune failed: {exc!r}")

    async def _start_real_workers():
        """Run the post-DB startup steps that lifespan() skipped while
        the server was on the bootstrap DB. Called from the
        /api/setup-database endpoint after a successful engine swap."""
        await load_proxy_settings()
        await repair_notification_configs()
        await apply_interval_default_to_legacy()
        await monitor_runner()
        await heartbeat_pruner()

    app.state.start_background_workers = _start_real_workers

    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 3001)))
    parser.add_argument("--data-file")
    args = parser.parse_args()
    if args.data_file:
        data_path = Path(args.data_file)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{data_path}")

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
