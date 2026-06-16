from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
)
from typing import get_origin, get_args, Dict, Optional, List, Iterable, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, update, or_, case
from sqlalchemy.exc import IntegrityError
import os
import time
import asyncio
import datetime
import json
import jwt
import secrets
import hashlib
import logging
import pyotp
from passlib.context import CryptContext
from ldap3 import Server, Connection, ALL
from ldap3.core.exceptions import LDAPBindError, LDAPException
from datetime import datetime as dt_datetime, timezone, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from urllib.parse import urlparse
from ..db import models, database
from ..notification_providers import get_provider
from ..settings import DEFAULT_INTERVAL_SECONDS, MIN_INTERVAL_SECONDS
from ..monitor_types import monitor_types, HTTPMonitor, is_actively_probed
from ..tls import fetch_presented_chain, is_ca
from ..cloudflared import CloudflaredManager

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/api")

# Secret key for signing JWT tokens. The previous default of "change-me"
# was a hard-coded leak — anyone running the project without setting the
# env var shipped with a publicly-known signing secret, which lets a
# third party forge admin tokens. Now: env var if set; otherwise a
# fresh per-process random secret. The latter invalidates all sessions
# on restart (acceptable for self-hosters who haven't bothered setting
# JWT_SECRET) but eliminates the well-known-secret leak.
_jwt_secret_from_env = os.getenv("JWT_SECRET")
if _jwt_secret_from_env:
    JWT_SECRET = _jwt_secret_from_env
else:
    JWT_SECRET = secrets.token_urlsafe(64)
    logger.warning(
        "JWT_SECRET env var not set — using a random per-process secret. "
        "Sessions will be invalidated on every restart. "
        "Set JWT_SECRET to a strong random value (e.g. `openssl rand -base64 48`) "
        "to make sessions persistent across restarts."
    )
JWT_ALGORITHM = "HS256"


# In-process per-IP login rate-limiter. Counts only failed attempts in
# a rolling window. Resets on a successful login. CPython dict ops are
# atomic between awaits, so no lock is needed for single-process FastAPI.
# This DOES NOT share state across multiple worker processes — that's
# fine for the typical single-uvicorn deploy; if you fronted this with
# gunicorn -w N or scaled horizontally you'd want Redis here.
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_MAX_FAILURES = 10
_login_failures: "dict[str, list[float]]" = {}

# Pre-computed dummy bcrypt hash. Verifying req.password against this
# costs the same amount of CPU as a real verify, so a "user does not
# exist" response takes the same time as "user exists, password wrong".
# Defeats username enumeration via bcrypt-timing side channel.
_DUMMY_BCRYPT_HASH = pwd_context.hash("not-a-real-password-only-for-timing-equalisation")


def _client_ip(request: "Request") -> str:
    if request and request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check_login_rate(ip: str) -> None:
    """Raise 429 if the caller has tripped the per-IP rate limit."""
    now = time.monotonic()
    cutoff = now - _LOGIN_WINDOW_SECONDS
    timestamps = [t for t in _login_failures.get(ip, []) if t > cutoff]
    _login_failures[ip] = timestamps
    if len(timestamps) >= _LOGIN_MAX_FAILURES:
        retry_after = max(1, int(_LOGIN_WINDOW_SECONDS - (now - timestamps[0])))
        raise HTTPException(
            status_code=429,
            detail="tooManyLoginAttempts",
            headers={"Retry-After": str(retry_after)},
        )


def _record_login_failure(ip: str) -> None:
    _login_failures.setdefault(ip, []).append(time.monotonic())


def _clear_login_failures(ip: str) -> None:
    _login_failures.pop(ip, None)


class CloudflaredStartPayload(BaseModel):
    token: Optional[str] = None


class CloudflaredStopPayload(BaseModel):
    currentPassword: Optional[str] = None


def coerce_config_to_dict(raw):
    if raw is None:
        return {}
    if isinstance(raw, (dict, list)):
        return raw if isinstance(raw, dict) else {}
    if isinstance(raw, (bytes, bytearray, memoryview)):
        raw = raw.decode("utf-8", "ignore")
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
            return val if isinstance(val, dict) else {}
        except Exception:
            return {}
    return {}


def coerce_to_bool(value) -> bool:
    """Best-effort conversion of settings payloads to boolean."""

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off", ""}:
            return False
        try:
            return bool(json.loads(value))
        except Exception:
            return bool(value)
    try:
        return bool(json.loads(value))
    except Exception:
        return bool(value)


async def save_setting(
    session: AsyncSession, key: str, value: str | None
) -> None:
    """Create, update or delete a setting entry."""

    stmt = select(models.Setting).where(models.Setting.key == key)
    res = await session.execute(stmt)
    setting = res.scalar_one_or_none()
    if value is None:
        if setting is not None:
            await session.delete(setting)
    else:
        if setting is not None:
            setting.value = value
        else:
            session.add(models.Setting(key=key, value=value))


def get_cloudflared_manager(request: Request) -> CloudflaredManager:
    manager = getattr(request.app.state, "cloudflared", None)
    if not isinstance(manager, CloudflaredManager):
        manager = CloudflaredManager()
        request.app.state.cloudflared = manager
    return manager


def generate_token(username: str, user_id: int | None = None) -> str:
    """Generate a signed JWT token."""
    payload = {
        "username": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
    }
    if user_id is not None:
        payload["user_id"] = user_id
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
class OrmBaseModel(BaseModel):
    """Base model with helper to sanitize ORM data."""

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, extra="ignore"
    )

    @classmethod
    def from_orm_clean(cls, obj):
        """Return ORM data coerced to the declared field types."""
        data = cls.model_validate(obj, from_attributes=True).model_dump(by_alias=True)

        for name, field in cls.model_fields.items():
            alias = field.alias or name
            value = data.get(alias)
            t = getattr(field, "annotation", None)

            if value is None:
                continue

            if t is bool or (get_origin(t) is Optional and bool in get_args(t)):
                if isinstance(value, str):
                    val = value.lower()
                    if val in {"1", "true", "yes"}:
                        data[alias] = True
                    elif val in {"0", "false", "no", "", "none", "null"}:
                        data[alias] = False
                    else:
                        try:
                            data[alias] = bool(int(val))
                        except ValueError:
                            data[alias] = bool(value)
                else:
                    data[alias] = bool(value)
            elif t is int or (get_origin(t) is Optional and int in get_args(t)):
                data[alias] = int(value)
            elif t is float or (get_origin(t) is Optional and float in get_args(t)):
                data[alias] = float(value)

        return data


async def get_session() -> AsyncSession:
    async with database.async_session_maker() as session:
        yield session


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> models.User:
    """Return the authenticated user based on the bearer token."""

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="invalidToken")

    token = auth[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalidToken") from exc

    user_id = payload.get("user_id")
    username = payload.get("username")

    query = select(models.User)
    if user_id is not None:
        query = query.where(models.User.id == user_id)
    elif username is not None:
        query = query.where(models.User.username == username)
    else:
        raise HTTPException(status_code=401, detail="invalidToken")

    res = await session.execute(query)
    user = res.scalar_one_or_none()
    if not user or not getattr(user, "active", True):
        raise HTTPException(status_code=401, detail="invalidToken")

    return user


def resolve_host_port(m: models.Monitor) -> tuple[str, int]:
    """Derive host and port for *m* supporting HTTP and TCP monitors."""
    if getattr(m, "type", "http") == "http":
        parsed = urlparse(getattr(m, "url", ""))
        host = parsed.hostname or getattr(m, "hostname", None)
        if not host:
            raise ValueError("monitor URL missing hostname")
        port = parsed.port or getattr(m, "port", None)
        if not port:
            port = 443 if parsed.scheme == "https" else 80
        return host, int(port)
    host = getattr(m, "hostname", None)
    port = getattr(m, "port", None)
    if not host or not port:
        parsed = urlparse(getattr(m, "url", ""))
        host = host or parsed.hostname
        port = port or parsed.port
    if not host or not port:
        raise ValueError("monitor missing hostname or port")
    return host, int(port)


async def verify_api_key(
    key: str, session: AsyncSession, required_role: str | None = None
) -> models.APIKey:
    """Return the API key if valid, not expired and has the required role."""
    hashed = hashlib.sha256(key.encode()).hexdigest()
    res = await session.execute(
        select(models.APIKey).where(models.APIKey.hashed_key == hashed)
    )
    api_key = res.scalar_one_or_none()
    if not api_key or not api_key.active:
        raise HTTPException(status_code=403, detail="invalidAPIKey")
    if api_key.expires and api_key.expires < datetime.datetime.utcnow():
        raise HTTPException(status_code=403, detail="apiKeyExpired")
    if required_role:
        allowed = {
            "read": {"read", "readwrite"},
            "write": {"write", "readwrite"},
        }
        if api_key.role not in allowed.get(required_role, {required_role}):
            raise HTTPException(status_code=403, detail="insufficientAPIKeyPermissions")
    return api_key


def require_api_key(required_role: str = "read"):
    async def dependency(
        x_api_key: str = Header(..., alias="X-API-Key"),
        session: AsyncSession = Depends(get_session),
    ) -> models.APIKey:
        """FastAPI dependency that validates an ``X-API-Key`` header."""
        return await verify_api_key(x_api_key, session, required_role)

    return dependency


async def get_ldap_settings(session: AsyncSession) -> tuple[str | None, str | None]:
    res = await session.execute(
        select(models.Setting).where(
            models.Setting.key.in_(["ldapURL", "ldapDNTemplate"])
        )
    )
    data = {s.key: s.value for s in res.scalars().all()}
    url = data.get("ldapURL") or os.getenv("LDAP_URL")
    tmpl = data.get("ldapDNTemplate") or os.getenv("LDAP_DN_TEMPLATE")
    return url, tmpl


class LoginRequest(BaseModel):
    username: str
    password: str
    token: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., alias="currentPassword")
    new_password: str = Field(..., alias="newPassword")


class AdminPasswordRequest(BaseModel):
    admin_password: str = Field(..., alias="adminPassword")


class APIKeyCreateRequest(BaseModel):
    name: str
    role: str = "read"
    expires: Optional[datetime.datetime] = None
    active: Optional[bool] = True


class TwoFAPasswordRequest(BaseModel):
    current_password: str = Field(..., alias="currentPassword")


class TwoFAVerifyRequest(TwoFAPasswordRequest):
    token: str


class TwoFASaveRequest(TwoFAPasswordRequest):
    token: str


class UserSchema(OrmBaseModel):
    id: Optional[int] = None
    username: str
    password: Optional[str] = None
    is_admin: Optional[bool] = False
    active: Optional[bool] = True


def _parse_bool(value) -> bool:
    """Convert various representations to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        val = value.lower()
        if val in {"1", "true", "yes"}:
            return True
        if val in {"0", "false", "no", "", "none", "null"}:
            return False
    return bool(value)


async def _send_notifications_for_monitor(session, monitor, hb):
    # per-monitor notifications
    res = await session.execute(
        select(models.Notification)
        .join(
            models.MonitorNotification,
            models.Notification.id == models.MonitorNotification.notification_id,
        )
        .where(
            models.MonitorNotification.monitor_id == monitor.id,
            models.Notification.active == True,
        )
    )
    notifications = list(res.scalars().unique().all())

    # default notifications
    res_def = await session.execute(
        select(models.Notification).where(
            models.Notification.is_default == True,
            models.Notification.active == True,
        )
    )
    defaults = [
        n for n in res_def.scalars().all() if all(n.id != x.id for x in notifications)
    ]
    notifications.extend(defaults)

    monitor_data = {
        "id": monitor.id,
        "name": monitor.name,
        "url": monitor.url,
        "hostname": monitor.hostname,
        "port": monitor.port,
        "type": monitor.type,
    }
    heartbeat_data = hb.to_json()
    heartbeat_data["event"] = getattr(hb, "event", None)

    for notif in notifications:
        provider = get_provider(notif.type)
        if not provider:
            continue
        cfg = coerce_config_to_dict(notif.config)
        await provider.send(cfg, hb.msg, monitor_data, heartbeat_data)


class MonitorSchema(OrmBaseModel):
    id: Optional[int] = None
    name: str
    # `url` is meaningful only for HTTP-style monitor types. Other types
    # (group, port, ping, push, etc.) leave it empty. Was non-optional
    # historically, which forced every client to send url="" as a bandaid;
    # now genuinely optional so the bandaid can go away.
    url: Optional[str] = None
    push_token: Optional[str] = Field(None, alias="pushToken")
    active: Optional[bool] = True
    type: Optional[str] = "http"
    parent: Optional[int] = None
    interval: Optional[int] = DEFAULT_INTERVAL_SECONDS
    maxretries: Optional[int] = 0
    retry_interval: Optional[int] = Field(0, alias="retryInterval")
    resend_interval: Optional[int] = Field(0, alias="resendInterval")
    ignore_tls: Optional[bool] = Field(False, alias="ignoreTls")
    tls_verify_mode: Optional[str] = "system"
    custom_ca_subject: Optional[str] = None
    custom_ca_issuer: Optional[str] = None
    custom_ca_sha256: Optional[str] = None
    expiry_notification: Optional[bool] = Field(False, alias="expiryNotification")
    cert_expiry_threshold_days: Optional[int] = Field(
        14, alias="certExpiryThresholdDays"
    )
    last_cert_notified_days: Optional[int] = Field(
        None, alias="lastCertNotifiedDays"
    )
    last_cert_notified_at: Optional[datetime.datetime] = Field(
        None, alias="lastCertNotifiedAt"
    )
    maxredirects: Optional[int] = 10
    cache_bust: Optional[bool] = Field(False, alias="cacheBust")
    upside_down: Optional[bool] = Field(False, alias="upsideDown")
    accepted_statuscodes: Optional[list[str]] = ["200-299"]
    hostname: Optional[str] = None
    port: Optional[int] = None
    proxy_id: Optional[int] = Field(None, alias="proxyId")
    description: Optional[str] = None
    method: Optional[str] = "GET"
    body: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    basic_auth_user: Optional[str] = None
    basic_auth_pass: Optional[str] = None
    dns_resolve_type: Optional[str] = Field(None, alias="dnsResolveType")
    dns_resolve_server: Optional[str] = Field(None, alias="dnsResolveServer")
    dns_last_result: Optional[str] = Field(None, alias="dnsLastResult")
    invert_keyword: Optional[bool] = Field(False, alias="invertKeyword")
    ping_numeric: Optional[bool] = Field(True, alias="pingNumeric")
    slow_response_threshold_ms: Optional[int] = Field(
        None, alias="slowResponseThresholdMs"
    )
    slow_response_consecutive: Optional[int] = Field(
        3, alias="slowResponseConsecutive"
    )

    @model_validator(mode="after")
    def normalize_push_token(self):
        """Normalize push_token based on monitor type."""
        t = (self.type or "").lower()
        tok = self.push_token
        if isinstance(tok, str) and tok.strip().lower() in {"", "string", "none", "null"}:
            tok = None
        # For non-push monitors never persist or expose a token
        if t != "push":
            self.push_token = None
        else:
            # Generate a token only when one isn't provided
            self.push_token = tok or secrets.token_urlsafe(24)
        return self

    @field_validator("parent", "proxy_id", mode="before")
    @classmethod
    def zero_to_none(cls, v):
        """Normalize 0, "0", "", or None to None for optional FK fields."""
        if v in (0, "0", "", None):
            return None
        try:
            return int(v)
        except Exception:  # pragma: no cover - defensive
            return v
    ping_count: Optional[int] = Field(3, alias="pingCount")
    ping_per_request_timeout: Optional[int] = Field(
        2, alias="pingPerRequestTimeout"
    )
    packet_size: Optional[int] = Field(56, alias="packetSize")
    notification_id_list: Optional[List[int]] = Field(
        None, alias="notificationIDList"
    )

    @field_validator(
        "active",
        "ignore_tls",
        "expiry_notification",
        "cache_bust",
        "upside_down",
        "invert_keyword",
        "ping_numeric",
        mode="before",
    )
    @classmethod
    def _bool_validator(cls, v):
        return _parse_bool(v)

class NotificationSchema(OrmBaseModel):
    id: Optional[int] = None
    name: str
    type: str
    active: Optional[bool] = None
    is_default: Optional[bool] = Field(None, alias="isDefault")
    config: Optional[Union[Dict, str]] = None
    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, extra="allow"
    )


def _build_config(n: NotificationSchema) -> Dict:
    """Merge any extra fields from the request into the config dict.

    This helper converts camelCase keys used by the frontend into the
    snake_case format stored in the database.  It also works when the
    incoming payload already provides a ``config`` object.
    """

    cfg: Dict = coerce_config_to_dict(n.config)

    # normalize common acronyms before snake-casing config keys
    def _normalize_acronyms(o: Dict):
        renames = [
            ("webhookURL", "webhookUrl"),
            ("WebhookURL", "webhookUrl"),
            ("URL", "url"),
            ("SSL", "ssl"),
            ("TLS", "tls"),
            ("HTTP", "http"),
            ("HTTPS", "https"),
        ]
        for from_k, to_k in renames:
            if from_k in o and to_k not in o:
                o[to_k] = o.pop(from_k)

    _normalize_acronyms(cfg)

    # convert camelCase keys inside config to snake_case
    cfg = {
        "".join(["_" + c.lower() if c.isupper() else c for c in k]).lstrip("_"): v
        for k, v in cfg.items()
    }

    # ``model_dump()`` will include extra fields thanks to ``extra='allow'``
    extra_fields = n.model_dump(
        exclude={"id", "name", "type", "active", "is_default", "config"},
        by_alias=False,
        exclude_none=True,
    )

    for key, value in extra_fields.items():
        snake = "".join(
            ["_" + c.lower() if c.isupper() else c for c in key]
        ).lstrip("_")
        cfg[snake] = value

    # Handle legacy Discord key to maintain backwards compatibility
    if "discord_webhook_url" in cfg and "webhook_url" not in cfg:
        cfg["webhook_url"] = cfg.pop("discord_webhook_url")

    return cfg

class StatusPageSchema(OrmBaseModel):
    title: str
    slug: str
    config: Optional[Dict] = None
    public: Optional[bool] = True
    monitors: Optional[List[Union[int, str, Dict]]] = None


class IncidentSchema(OrmBaseModel):
    id: Optional[int] = None
    title: str
    content: str
    style: Optional[str] = "primary"


class TagSchema(OrmBaseModel):
    id: Optional[int] = None
    name: str
    color: str


@router.post("/login")
async def login(
    req: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    ip = _client_ip(request)
    _check_login_rate(ip)

    res = await session.execute(
        select(models.User).where(models.User.username == req.username)
    )
    user = res.scalar_one_or_none()

    # Always burn bcrypt time, even when the user doesn't exist, so the
    # response time can't be used to enumerate valid usernames.
    if user and user.active:
        password_ok = pwd_context.verify(req.password, user.password)
    else:
        pwd_context.verify(req.password, _DUMMY_BCRYPT_HASH)
        password_ok = False

    if password_ok:
        if getattr(user, "two_fa_enabled", False):
            secret = getattr(user, "two_fa_secret", None)
            if not secret:
                # Fail closed: the previous behaviour fell through and
                # issued the token, which means an attacker with DB
                # write access could null out two_fa_secret to bypass
                # the second factor entirely. Refuse the login instead
                # and log loud so the operator notices the misconfig.
                # Don't count this against the rate limit — it's our
                # bug, not their attack.
                logger.error(
                    "User %s has 2FA enabled but no two_fa_secret stored — "
                    "denying login. Reset 2FA for this user from the admin UI.",
                    user.username,
                )
                raise HTTPException(status_code=500, detail="twoFAMisconfigured")
            if req.token is None:
                _record_login_failure(ip)
                raise HTTPException(status_code=403, detail="tokenRequired")
            totp = pyotp.TOTP(secret)
            if not totp.verify(req.token, valid_window=1):
                _record_login_failure(ip)
                raise HTTPException(status_code=403, detail="invalidTwoFAToken")
        _clear_login_failures(ip)
        return {"token": generate_token(user.username, user.id)}

    ldap_url, ldap_dn_template = await get_ldap_settings(session)
    if ldap_url and ldap_dn_template:
        dn = ldap_dn_template.format(username=req.username)
        try:
            server = Server(ldap_url, get_info=ALL)
            conn = Connection(server, dn, req.password, auto_bind=True)
            conn.unbind()
            _clear_login_failures(ip)
            return {"token": generate_token(req.username)}
        except LDAPBindError as exc:
            logger.exception("LDAP authentication failed for %s", req.username)
            _record_login_failure(ip)
            raise HTTPException(status_code=401, detail="Invalid credentials") from exc
        except LDAPException as exc:
            logger.exception("LDAP connection failed")
            raise HTTPException(status_code=500, detail="ldapConnectionFailed") from exc
        except Exception as exc:
            logger.exception("Unexpected LDAP error")
            raise HTTPException(status_code=500, detail="ldapConnectionFailed") from exc

    _record_login_failure(ip)
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/users")
async def create_user(u: UserSchema, session: AsyncSession = Depends(get_session)):
    if not u.password:
        raise HTTPException(status_code=400, detail="Password required")
    hashed = pwd_context.hash(u.password)
    user = models.User(
        username=u.username,
        password=hashed,
        is_admin=u.is_admin or False,
        active=u.active if u.active is not None else True,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="usernameTaken")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail="User creation failed") from e
    return {"id": user.id}


@router.get("/users")
async def list_users(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(models.User))
    users = res.scalars().all()
    result = []
    for u in users:
        data = UserSchema.from_orm_clean(u)
        data.pop("password", None)
        result.append(data)
    return result


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int, req: AdminPasswordRequest, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(models.User).where(models.User.is_admin.is_(True))
    )
    admins = res.scalars().all()
    if not any(pwd_context.verify(req.admin_password, a.password) for a in admins):
        raise HTTPException(status_code=403, detail="invalidAdminPassword")
    res = await session.execute(select(models.User).where(models.User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.active = False
    await session.commit()
    return {"ok": True}


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: int, req: AdminPasswordRequest, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(models.User).where(models.User.is_admin.is_(True))
    )
    admins = res.scalars().all()
    if not any(pwd_context.verify(req.admin_password, a.password) for a in admins):
        raise HTTPException(status_code=403, detail="invalidAdminPassword")
    res = await session.execute(select(models.User).where(models.User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.active = True
    await session.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int, req: AdminPasswordRequest, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(models.User).where(models.User.is_admin.is_(True))
    )
    admins = res.scalars().all()
    if not any(pwd_context.verify(req.admin_password, a.password) for a in admins):
        raise HTTPException(status_code=403, detail="invalidAdminPassword")
    await session.execute(delete(models.User).where(models.User.id == user_id))
    await session.commit()
    return {"ok": True}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(models.User).where(models.User.is_admin.is_(True))
    )
    admins = res.scalars().all()
    admin = next((a for a in admins if pwd_context.verify(payload.current_password, a.password)), None)
    if admin is None:
        raise HTTPException(status_code=400, detail="invalidCurrentPassword")
    user = admin
    user.password = pwd_context.hash(payload.new_password)
    await session.commit()
    return {
        "ok": True,
        "token": generate_token(user.username, user.id),
        "msgi18n": "successAuthChangePassword",
    }


@router.get("/twofa/status")
async def twofa_status(
    current_user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(models.User, current_user.id)
    if not user:
        raise HTTPException(status_code=401, detail="invalidToken")
    return {"ok": True, "status": bool(getattr(user, "two_fa_enabled", False))}


@router.post("/twofa/prepare")
async def twofa_prepare(
    req: TwoFAPasswordRequest,
    current_user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(models.User, current_user.id)
    if not user:
        raise HTTPException(status_code=401, detail="invalidToken")

    if not pwd_context.verify(req.current_password, user.password):
        raise HTTPException(status_code=403, detail="invalidCurrentPassword")

    secret = pyotp.random_base32()
    user.two_fa_temp_secret = secret
    user.two_fa_temp_verified_at = None
    await session.commit()

    issuer = os.getenv("TWO_FA_ISSUER", "Observer")
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.username,
        issuer_name=issuer,
    )
    return {"ok": True, "uri": uri}


@router.post("/twofa/verify")
async def twofa_verify(
    req: TwoFAVerifyRequest,
    current_user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(models.User, current_user.id)
    if not user:
        raise HTTPException(status_code=401, detail="invalidToken")

    if not pwd_context.verify(req.current_password, user.password):
        raise HTTPException(status_code=403, detail="invalidCurrentPassword")

    secret = user.two_fa_temp_secret or user.two_fa_secret
    if not secret:
        raise HTTPException(status_code=400, detail="twoFANotPrepared")

    totp = pyotp.TOTP(secret)
    valid = bool(totp.verify(req.token, valid_window=1))

    if valid and user.two_fa_temp_secret:
        user.two_fa_temp_verified_at = datetime.datetime.utcnow()
        await session.commit()

    return {"ok": True, "valid": valid}


@router.post("/twofa/enable")
async def twofa_enable(
    req: TwoFASaveRequest,
    current_user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(models.User, current_user.id)
    if not user:
        raise HTTPException(status_code=401, detail="invalidToken")

    if not pwd_context.verify(req.current_password, user.password):
        raise HTTPException(status_code=403, detail="invalidCurrentPassword")

    if not user.two_fa_temp_secret:
        raise HTTPException(status_code=400, detail="twoFANotPrepared")

    totp = pyotp.TOTP(user.two_fa_temp_secret)
    if not totp.verify(req.token, valid_window=1):
        raise HTTPException(status_code=400, detail="invalidTwoFAToken")

    user.two_fa_secret = user.two_fa_temp_secret
    user.two_fa_enabled = True
    user.two_fa_temp_secret = None
    user.two_fa_temp_verified_at = None
    await session.commit()

    return {"ok": True, "msgi18n": "twoFAEnabledSuccess"}


@router.post("/twofa/disable")
async def twofa_disable(
    req: TwoFAPasswordRequest,
    current_user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(models.User, current_user.id)
    if not user:
        raise HTTPException(status_code=401, detail="invalidToken")

    if not pwd_context.verify(req.current_password, user.password):
        raise HTTPException(status_code=403, detail="invalidCurrentPassword")

    user.two_fa_secret = None
    user.two_fa_enabled = False
    user.two_fa_temp_secret = None
    user.two_fa_temp_verified_at = None
    await session.commit()

    return {"ok": True, "msgi18n": "twoFADisabledSuccess"}


@router.get("/api-keys")
async def list_api_keys(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(models.APIKey))
    keys = [k.to_json() for k in res.scalars().all()]
    return keys


@router.post("/api-keys")
async def create_api_key(
    payload: APIKeyCreateRequest, session: AsyncSession = Depends(get_session)
):
    clear = secrets.token_hex(16)
    hashed = hashlib.sha256(clear.encode()).hexdigest()
    if payload.role not in {"read", "write", "readwrite"}:
        raise HTTPException(status_code=400, detail="invalidRole")
    key = models.APIKey(
        name=payload.name,
        hashed_key=hashed,
        role=payload.role,
        expires=payload.expires,
        active=payload.active if payload.active is not None else True,
    )
    session.add(key)
    await session.commit()
    return {"ok": True, "id": key.id, "key": clear}


@router.delete("/api-keys/{key_id}")
async def delete_api_key(key_id: int, session: AsyncSession = Depends(get_session)):
    await session.execute(delete(models.APIKey).where(models.APIKey.id == key_id))
    await session.commit()
    return {"ok": True}


@router.post("/api-keys/{key_id}/disable")
async def disable_api_key(key_id: int, session: AsyncSession = Depends(get_session)):
    key = await session.get(models.APIKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.active = False
    await session.commit()
    return {"ok": True}


@router.post("/api-keys/{key_id}/enable")
async def enable_api_key(key_id: int, session: AsyncSession = Depends(get_session)):
    key = await session.get(models.APIKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    key.active = True
    await session.commit()
    return {"ok": True}


@router.get("/entry-page")
async def entry_page(session: AsyncSession = Depends(get_session)):
    """Return entry page configuration for the Vue frontend."""
    result = await session.execute(
        select(models.Setting).where(models.Setting.key == "entryPage")
    )
    setting = result.scalar_one_or_none()
    entry_page = setting.value if setting else None
    return {"type": "entryPage", "entryPage": entry_page}


@router.get("/monitors")
async def get_monitors(session: AsyncSession = Depends(get_session)):
    """Return all monitors with their tags."""
    result = await session.execute(select(models.Monitor))
    monitors = result.scalars().all()

    tag_rows = await session.execute(
        select(models.MonitorTag, models.Tag)
        .join(models.Tag, models.MonitorTag.tag_id == models.Tag.id)
    )
    tag_map: Dict[int, list] = {}
    for mt, t in tag_rows.fetchall():
        tag_map.setdefault(mt.monitor_id, []).append(
            {
                "id": mt.id,
                "monitor_id": mt.monitor_id,
                "tag_id": mt.tag_id,
                "value": mt.value,
                "name": t.name,
                "color": t.color,
            }
        )

    notif_rows = await session.execute(select(models.MonitorNotification))
    notif_map: Dict[int, List[int]] = {}
    for mn in notif_rows.scalars().all():
        notif_map.setdefault(mn.monitor_id, []).append(mn.notification_id)

    result_list = []
    for m in monitors:
        data = MonitorSchema.from_orm_clean(m)
        data.pop("maxretries", None)
        data["notificationIDList"] = notif_map.get(m.id, [])
        result_list.append({**data, "tags": tag_map.get(m.id, [])})
    return result_list


@router.post("/monitors")
async def add_monitor(m: MonitorSchema, session: AsyncSession = Depends(get_session)):
    print("add_monitor request", m.model_dump())
    interval = m.interval
    if interval is None or int(interval) < MIN_INTERVAL_SECONDS:
        interval = DEFAULT_INTERVAL_SECONDS
    monitor_kwargs = {
        "name": m.name,
        "url": m.url,
        "push_token": m.push_token,
        "active": m.active if m.active is not None else True,
        "type": m.type,
        "parent": m.parent,
        "interval": int(interval),
        "maxretries": m.maxretries,
        "retry_interval": m.retry_interval,
        "resend_interval": m.resend_interval,
        "ignore_tls": m.ignore_tls,
        "tls_verify_mode": m.tls_verify_mode,
        "expiry_notification": m.expiry_notification,
        "cert_expiry_threshold_days": m.cert_expiry_threshold_days,
        "last_cert_notified_days": m.last_cert_notified_days,
        "last_cert_notified_at": m.last_cert_notified_at,
        "maxredirects": m.maxredirects,
        "cache_bust": m.cache_bust,
        "upside_down": m.upside_down,
        "accepted_statuscodes_json": json.dumps(m.accepted_statuscodes),
        "hostname": m.hostname,
        "port": m.port,
        "proxy_id": m.proxy_id,
        "description": m.description,
        "method": m.method,
        "body": m.body,
        "headers_json": json.dumps(m.headers) if m.headers else None,
        "basic_auth_user": m.basic_auth_user,
        "basic_auth_pass": m.basic_auth_pass,
        "dns_resolve_type": m.dns_resolve_type,
        "dns_resolve_server": m.dns_resolve_server,
        "dns_last_result": m.dns_last_result,
        "invert_keyword": m.invert_keyword,
        "ping_numeric": m.ping_numeric,
        "ping_count": m.ping_count,
        "ping_per_request_timeout": m.ping_per_request_timeout,
        "packet_size": m.packet_size,
        "slow_response_threshold_ms": m.slow_response_threshold_ms,
        "slow_response_consecutive": m.slow_response_consecutive,
    }
    if m.id is not None:
        monitor_kwargs["id"] = m.id
    monitor = models.Monitor(**monitor_kwargs)
    session.add(monitor)
    try:
        await session.commit()
        await session.refresh(monitor)
    except IntegrityError as e:
        await session.rollback()
        msg = str(getattr(e, "orig", e)).lower()
        if "monitors.name" in msg:
            raise HTTPException(status_code=400, detail="monitorNameTaken") from e
        return JSONResponse(
            status_code=409,
            content={"ok": False, "msg": "push_token already exists"},
        )

    if m.notification_id_list:
        for notif_id in {int(x) for x in m.notification_id_list}:
            session.add(
                models.MonitorNotification(
                    monitor_id=monitor.id, notification_id=notif_id
                )
            )

    hb = models.Heartbeat(monitor_id=monitor.id, status=2, msg="Pending")
    session.add(hb)
    await session.commit()
    # Run first check immediately so UI gets a real heartbeat quickly
    asyncio.create_task(_run_single_check(monitor.id))

    # Return the full monitor record so direct API consumers and the
    # Vue store can populate state without an immediate follow-up GET.
    # Tags are added in a separate request after creation, so they're
    # always empty here; notificationIDList echoes the request input.
    monitor_data = MonitorSchema.from_orm_clean(monitor)
    monitor_data["tags"] = []
    monitor_data["notificationIDList"] = sorted(
        {int(x) for x in (m.notification_id_list or [])}
    )
    return {
        "ok": True,
        "monitorID": monitor.id,
        "interval": monitor.interval,
        "monitor": monitor_data,
    }


async def _run_single_check(monitor_id: int):
    """Execute one monitor check outside of request lifecycle."""
    async with database.async_session_maker() as s:
        res = await s.execute(
            select(models.Monitor).where(models.Monitor.id == monitor_id)
        )
        m = res.scalar_one_or_none()
        if not m:
            return
        # Passive monitors (push) are never actively probed — their first
        # real heartbeat arrives when the external caller posts to /push.
        # Probing here would fall through to the HTTPMonitor default and
        # bury the freshly-created "Pending" placeholder under a bogus
        # HTTP beat.
        if not is_actively_probed(getattr(m, "type", "http")):
            return
        hb = models.Heartbeat(monitor_id=m.id)
        monitor_cls = monitor_types.get(getattr(m, "type", "http"), HTTPMonitor)
        try:
            await monitor_cls().check(m, hb)
        except BaseException as exc:
            # Record the failure as a DOWN beat so the new monitor
            # doesn't get stuck on its initial Pending state when the
            # very first probe blows up.
            print(f"Initial probe for monitor {m.id} ({m.name}) raised: {exc!r}")
            hb.status = 0
            hb.msg = f"Internal probe error: {exc!r}"
            hb.ping = None
        res_prev = await s.execute(
            select(models.Heartbeat)
            .where(models.Heartbeat.monitor_id == m.id)
            .order_by(models.Heartbeat.time.desc())
            .limit(1)
        )
        last = res_prev.scalars().first()
        if last is None or last.status != hb.status:
            hb.important = True
            s.add(models.ImportantHeartbeat(monitor_id=m.id, message=hb.msg))
        s.add(hb)
        await s.commit()


@router.get("/monitor/{monitor_id}")
async def get_monitor(monitor_id: int, session: AsyncSession = Depends(get_session)):
    res = await session.execute(
        select(models.Monitor).where(models.Monitor.id == monitor_id)
    )
    monitor = res.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    tag_rows = await session.execute(
        select(models.MonitorTag, models.Tag)
        .join(models.Tag, models.MonitorTag.tag_id == models.Tag.id)
        .where(models.MonitorTag.monitor_id == monitor_id)
    )
    tags = [
        {
            "id": mt.id,
            "monitor_id": mt.monitor_id,
            "tag_id": mt.tag_id,
            "value": mt.value,
            "name": t.name,
            "color": t.color,
        }
        for mt, t in tag_rows.fetchall()
    ]

    notif_rows = await session.execute(
        select(models.MonitorNotification.notification_id).where(
            models.MonitorNotification.monitor_id == monitor_id
        )
    )
    notif_ids = [row[0] for row in notif_rows.fetchall()]

    data = MonitorSchema.from_orm_clean(monitor)
    data["tags"] = tags
    data["notificationIDList"] = notif_ids
    return {"ok": True, "monitor": data}


@router.post("/monitor/{monitor_id}")
async def edit_monitor(
    monitor_id: int, m: MonitorSchema, session: AsyncSession = Depends(get_session)
):
    print("edit_monitor request", m.model_dump())
    res = await session.execute(
        select(models.Monitor).where(models.Monitor.id == monitor_id)
    )
    monitor = res.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    monitor.name = m.name
    monitor.url = m.url
    monitor.push_token = m.push_token
    monitor.type = m.type
    monitor.parent = m.parent
    if m.interval is not None:
        monitor.interval = max(int(m.interval), MIN_INTERVAL_SECONDS)
    monitor.maxretries = m.maxretries
    monitor.retry_interval = m.retry_interval
    monitor.resend_interval = m.resend_interval
    monitor.ignore_tls = m.ignore_tls
    monitor.tls_verify_mode = m.tls_verify_mode
    monitor.expiry_notification = m.expiry_notification
    monitor.cert_expiry_threshold_days = m.cert_expiry_threshold_days
    monitor.last_cert_notified_days = m.last_cert_notified_days
    monitor.last_cert_notified_at = m.last_cert_notified_at
    monitor.maxredirects = m.maxredirects
    monitor.cache_bust = m.cache_bust
    monitor.upside_down = m.upside_down
    monitor.accepted_statuscodes_json = json.dumps(m.accepted_statuscodes)
    monitor.hostname = m.hostname
    monitor.port = m.port
    monitor.proxy_id = m.proxy_id
    monitor.description = m.description
    monitor.method = m.method
    monitor.body = m.body
    monitor.headers_json = json.dumps(m.headers) if m.headers else None
    monitor.basic_auth_user = m.basic_auth_user
    monitor.basic_auth_pass = m.basic_auth_pass
    monitor.dns_resolve_type = m.dns_resolve_type
    monitor.dns_resolve_server = m.dns_resolve_server
    monitor.dns_last_result = m.dns_last_result
    monitor.invert_keyword = m.invert_keyword
    monitor.ping_numeric = m.ping_numeric
    monitor.ping_count = m.ping_count
    monitor.ping_per_request_timeout = m.ping_per_request_timeout
    monitor.packet_size = m.packet_size
    monitor.slow_response_threshold_ms = m.slow_response_threshold_ms
    monitor.slow_response_consecutive = m.slow_response_consecutive
    if m.active is not None:
        monitor.active = m.active
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return JSONResponse(
            status_code=409,
            content={"ok": False, "msg": "push_token already exists"},
        )

    if m.notification_id_list is not None:
        desired = {int(x) for x in m.notification_id_list}
        rows = await session.execute(
            select(models.MonitorNotification).where(
                models.MonitorNotification.monitor_id == monitor_id
            )
        )
        current = {r.notification_id for r in rows.scalars().all()}
        to_add = desired - current
        to_del = current - desired

        if to_del:
            await session.execute(
                delete(models.MonitorNotification).where(
                    models.MonitorNotification.monitor_id == monitor_id,
                    models.MonitorNotification.notification_id.in_(to_del),
                )
            )
        for nid in to_add:
            session.add(
                models.MonitorNotification(
                    monitor_id=monitor_id, notification_id=nid
                )
            )
        await session.commit()

    return {"ok": True, "monitorID": monitor.id, "interval": monitor.interval}


@router.post("/monitors/{monitor_id}")
async def update_monitor_alias(
    monitor_id: int, m: MonitorSchema, session: AsyncSession = Depends(get_session)
):
    return await edit_monitor(monitor_id, m, session)


@router.post("/monitors/{monitor_id}/trust-presented-ca")
async def trust_presented_ca(
    monitor_id: int, session: AsyncSession = Depends(get_session)
):
    m = await session.get(models.Monitor, monitor_id)
    if not m:
        raise HTTPException(404, "Monitor not found")

    host, port = resolve_host_port(m)

    try:
        chain = await fetch_presented_chain(host, port, m.hostname or host)
    except asyncio.TimeoutError:
        raise HTTPException(504, "TLS connect timed out")
    except Exception as e:
        raise HTTPException(502, f"TLS connect failed: {e}")

    if not chain:
        raise HTTPException(502, "TLS connect failed: empty certificate chain")

    ca_certs = [c for c in chain if is_ca(c)]
    if not ca_certs:
        # Fallback to the leaf certificate when the server does not present a CA.
        # This allows trusting single-certificate chains commonly returned by
        # appliances or services that use the leaf as the trust anchor.
        ca_certs = [chain[0]]

    chosen = next((c for c in reversed(chain) if is_ca(c)), ca_certs[0])

    pem_bundle = "".join(c.public_bytes(serialization.Encoding.PEM).decode() for c in ca_certs)
    sha256 = chosen.fingerprint(hashes.SHA256()).hex()
    subj = chosen.subject.rfc4514_string()
    iss = chosen.issuer.rfc4514_string()

    # 5) Persist & switch mode
    # If the most recent heartbeat recorded a certificate verification failure we
    # drop it so the initial "DOWN" event caused by trusting the certificate is
    # not counted towards uptime metrics.  This mirrors the behaviour users
    # expect when acknowledging a self-signed certificate.
    res = await session.execute(
        select(models.Heartbeat)
        .where(models.Heartbeat.monitor_id == monitor_id)
        .order_by(models.Heartbeat.time.desc())
        .limit(1)
    )
    last_heartbeat = res.scalars().first()
    removed_msg: str | None = None
    if (
        last_heartbeat
        and not bool(last_heartbeat.status)
        and last_heartbeat.msg
        and "certificate verify failed" in last_heartbeat.msg.lower()
    ):
        removed_msg = last_heartbeat.msg
        await session.delete(last_heartbeat)

    if removed_msg:
        res_imp = await session.execute(
            select(models.ImportantHeartbeat)
            .where(models.ImportantHeartbeat.monitor_id == monitor_id)
            .order_by(models.ImportantHeartbeat.id.desc())
            .limit(1)
        )
        last_imp = res_imp.scalars().first()
        if last_imp and last_imp.message and last_imp.message.lower() == removed_msg.lower():
            await session.delete(last_imp)

    m.custom_ca_pem = pem_bundle
    m.custom_ca_sha256 = sha256
    m.custom_ca_subject = subj[:256]
    m.custom_ca_issuer = iss[:256]
    m.custom_ca_trusted_at = dt_datetime.now(timezone.utc)
    m.tls_verify_mode = "presented_ca"
    await session.commit()

    return {"ok": True, "subject": subj, "issuer": iss, "sha256": sha256}


@router.post("/monitors/{monitor_id}/clear-trusted-ca")
async def clear_trusted_ca(
    monitor_id: int, session: AsyncSession = Depends(get_session)
):
    m = await session.get(models.Monitor, monitor_id)
    if not m:
        raise HTTPException(404, "Monitor not found")
    m.tls_verify_mode = "system"
    m.custom_ca_pem = None
    m.custom_ca_sha256 = None
    m.custom_ca_subject = None
    m.custom_ca_issuer = None
    m.custom_ca_trusted_at = None
    await session.commit()
    return {"ok": True}


async def _dispatch_lifecycle_event(
    session: AsyncSession, monitor, event: str, message: str
) -> None:
    """Send a lifecycle notification (``paused`` / ``resumed``) for a monitor.

    Loads attached + default notification channels and fires through the
    same fire-and-forget helper the runner uses. Lazy-imports the runner
    dispatcher to avoid a circular import (server.server imports this
    module at top level).
    """
    from ..server import _dispatch_notification_async

    res_notif = await session.execute(
        select(models.Notification)
        .join(
            models.MonitorNotification,
            models.Notification.id == models.MonitorNotification.notification_id,
        )
        .where(
            models.MonitorNotification.monitor_id == monitor.id,
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

    if not notifications:
        return

    monitor_data = {
        "id": monitor.id,
        "name": monitor.name,
        "url": monitor.url,
        "hostname": monitor.hostname,
        "port": monitor.port,
        "type": monitor.type,
    }
    now_iso = dt_datetime.utcnow().isoformat()
    heartbeat_data = {
        "monitorID": monitor.id,
        "status": 1 if event == "resumed" else 0,
        "time": now_iso,
        "msg": message,
        "ping": None,
        "important": True,
        "duration": None,
        "retries": 0,
        "event": event,
    }
    for notif in notifications:
        _dispatch_notification_async(notif, message, monitor_data, heartbeat_data)


@router.post("/monitors/{monitor_id}/pause")
async def pause_monitor(
    monitor_id: int, session: AsyncSession = Depends(get_session)
):
    """Pause a monitor by setting its ``active`` flag to False."""
    res = await session.execute(
        select(models.Monitor).where(models.Monitor.id == monitor_id)
    )
    monitor = res.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    was_active = monitor.active
    monitor.active = False
    await session.commit()
    if was_active:
        await _dispatch_lifecycle_event(
            session, monitor, "paused", f"{monitor.name} was paused"
        )
    return {"ok": True}


@router.post("/monitors/{monitor_id}/resume")
async def resume_monitor(
    monitor_id: int, session: AsyncSession = Depends(get_session)
):
    """Resume a paused monitor by setting its ``active`` flag to True."""
    res = await session.execute(
        select(models.Monitor).where(models.Monitor.id == monitor_id)
    )
    monitor = res.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    was_active = monitor.active
    monitor.active = True
    await session.commit()
    if not was_active:
        await _dispatch_lifecycle_event(
            session, monitor, "resumed", f"{monitor.name} was resumed"
        )
    return {"ok": True}


@router.delete("/monitors/{monitor_id}")
async def delete_monitor(
    monitor_id: int, session: AsyncSession = Depends(get_session)
):
    await session.execute(
        delete(models.Monitor).where(models.Monitor.id == monitor_id)
    )
    await session.execute(
        delete(models.Heartbeat).where(models.Heartbeat.monitor_id == monitor_id)
    )
    await session.execute(
        delete(models.ImportantHeartbeat).where(
            models.ImportantHeartbeat.monitor_id == monitor_id
        )
    )
    await session.commit()
    return {"ok": True}


@router.post("/monitors/{monitor_id}/clear-events")
async def clear_events(monitor_id: int, session: AsyncSession = Depends(get_session)):
    res = await session.execute(
        select(models.Monitor).where(models.Monitor.id == monitor_id)
    )
    monitor = res.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    await session.execute(
        delete(models.ImportantHeartbeat).where(
            models.ImportantHeartbeat.monitor_id == monitor_id
        )
    )
    await session.commit()
    return {"ok": True}


@router.post("/monitors/{monitor_id}/clear-heartbeats")
async def clear_heartbeats(
    monitor_id: int, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(models.Monitor).where(models.Monitor.id == monitor_id)
    )
    monitor = res.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    await session.execute(
        delete(models.Heartbeat).where(models.Heartbeat.monitor_id == monitor_id)
    )
    await session.commit()
    return {"ok": True}


@router.get("/monitors/{monitor_id}/heartbeats")
async def get_heartbeats(
    monitor_id: int,
    session: AsyncSession = Depends(get_session),
    offset: int = 0,
    limit: int = 10,
):
    stmt = (
        select(models.Heartbeat)
        .where(models.Heartbeat.monitor_id == monitor_id)
        .order_by(models.Heartbeat.time.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await session.execute(stmt)
    beats = res.scalars().all()
    return {"ok": True, "data": [hb.to_json() for hb in beats]}


@router.get("/monitors/{monitor_id}/heartbeats/count")
async def get_heartbeats_count(
    monitor_id: int, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(func.count(models.Heartbeat.id)).where(
            models.Heartbeat.monitor_id == monitor_id
        )
    )
    count = res.scalar_one()
    return {"ok": True, "count": count}


_PING_STATS_PERIODS = {
    # period code → (n_buckets, bucket_seconds, span_seconds)
    # Bucket sizes tuned so that monitors at typical 30s-60s probe
    # intervals get a smooth-looking line — old hourly-on-24h was too
    # coarse: a 30-min-old monitor's 60 probes all collapsed into a
    # single bucket, and the chart rendered as one isolated point per
    # series rather than a trend line.
    "24h": (144, 600, 86400),       # 144 × 10-min buckets
    "7d": (84, 7200, 604800),       # 84  × 2-hour buckets
    "30d": (90, 28800, 2592000),    # 90  × 8-hour buckets
}


@router.get("/monitors/{monitor_id}/ping-stats")
async def ping_stats(
    monitor_id: int,
    period: str = "24h",
    session: AsyncSession = Depends(get_session),
):
    """Bucketed avg/max response time for the response-time chart on the
    monitor detail page. Buckets are aligned to the present time so the
    last bucket is always 'now'; empty buckets get null avg/max so the
    frontend can render gaps instead of connecting through them."""
    if period not in _PING_STATS_PERIODS:
        period = "24h"
    n_buckets, bucket_seconds, span_seconds = _PING_STATS_PERIODS[period]

    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(seconds=span_seconds)

    res = await session.execute(
        select(models.Heartbeat.time, models.Heartbeat.ping)
        .where(
            models.Heartbeat.monitor_id == monitor_id,
            models.Heartbeat.time >= cutoff,
            models.Heartbeat.ping.isnot(None),
        )
        .order_by(models.Heartbeat.time)
    )
    rows = res.all()

    bucket_start_ts = cutoff.timestamp()
    bucket_pings: list[list[float]] = [[] for _ in range(n_buckets)]
    for row in rows:
        idx = int((row.time.timestamp() - bucket_start_ts) // bucket_seconds)
        if 0 <= idx < n_buckets:
            bucket_pings[idx].append(row.ping)

    buckets = []
    for i in range(n_buckets):
        bucket_t = bucket_start_ts + i * bucket_seconds
        iso = datetime.datetime.utcfromtimestamp(bucket_t).isoformat() + "Z"
        pings = bucket_pings[i]
        if pings:
            buckets.append({
                "t": iso,
                "avg": int(round(sum(pings) / len(pings))),
                "max": int(round(max(pings))),
                "count": len(pings),
            })
        else:
            buckets.append({"t": iso, "avg": None, "max": None, "count": 0})

    all_pings = [p for chunk in bucket_pings for p in chunk]
    summary = {
        "avg": int(round(sum(all_pings) / len(all_pings))) if all_pings else None,
        "max": int(round(max(all_pings))) if all_pings else None,
        "count": len(all_pings),
    }

    return {
        "ok": True,
        "buckets": buckets,
        "summary": summary,
        "period": period,
        "bucket_seconds": bucket_seconds,
    }


_INCIDENTS_PERIOD_SECONDS = {
    "24h": 86400,
    "7d": 7 * 86400,
    "30d": 30 * 86400,
    "90d": 90 * 86400,
}


@router.get("/monitors/{monitor_id}/incidents")
async def monitor_incidents(
    monitor_id: int,
    period: str = "30d",
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """Group consecutive DOWN heartbeats into incidents.

    Walks the heartbeat stream in order. A run of DOWN probes opens an
    incident; the first UP probe after that closes it. Pending and
    maintenance probes are ignored — they neither open nor close an
    incident, so a heartbeat sequence like UP DOWN PENDING DOWN UP
    produces a single incident, not two.

    Each returned incident:
      started_at         ISO-8601 of the first DOWN
      ended_at           ISO-8601 of the closing UP (null if ongoing)
      duration_seconds   ended_at - started_at (or now - started_at)
      ongoing            true iff the monitor is still down at request time
      msg                error text from the first DOWN probe of the run
      probe_count        number of DOWN heartbeats inside the run
    """
    if period not in _INCIDENTS_PERIOD_SECONDS:
        period = "30d"
    limit = max(1, min(int(limit), 500))
    span_seconds = _INCIDENTS_PERIOD_SECONDS[period]
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(seconds=span_seconds)

    res = await session.execute(
        select(models.Heartbeat.time, models.Heartbeat.status, models.Heartbeat.msg)
        .where(
            models.Heartbeat.monitor_id == monitor_id,
            models.Heartbeat.time >= cutoff,
        )
        .order_by(models.Heartbeat.time)
    )
    rows = res.all()

    incidents = []
    open_run = None  # {"started": dt, "msg": str, "count": int}

    for row in rows:
        if row.status not in (0, 1):
            # Pending / maintenance — neither open nor close an incident.
            continue
        if row.status == 0:
            if open_run is None:
                open_run = {
                    "started": row.time,
                    "msg": (row.msg or "").strip(),
                    "count": 1,
                }
            else:
                open_run["count"] += 1
        else:  # row.status == 1, an UP probe closes the run.
            if open_run is not None:
                incidents.append({
                    "started_at": open_run["started"].isoformat() + "Z",
                    "ended_at": row.time.isoformat() + "Z",
                    "duration_seconds": int(
                        (row.time - open_run["started"]).total_seconds()
                    ),
                    "ongoing": False,
                    "msg": open_run["msg"],
                    "probe_count": open_run["count"],
                })
                open_run = None

    if open_run is not None:
        now = datetime.datetime.utcnow()
        incidents.append({
            "started_at": open_run["started"].isoformat() + "Z",
            "ended_at": None,
            "duration_seconds": int((now - open_run["started"]).total_seconds()),
            "ongoing": True,
            "msg": open_run["msg"],
            "probe_count": open_run["count"],
        })

    # Newest first; clip to limit.
    incidents.reverse()
    incidents = incidents[:limit]

    return {
        "ok": True,
        "period": period,
        "incidents": incidents,
        "summary": {
            "count": len(incidents),
            "ongoing": any(i["ongoing"] for i in incidents),
            "total_downtime_seconds": sum(i["duration_seconds"] for i in incidents),
        },
    }


@router.get("/monitors/{monitor_id}/uptime-daily")
async def uptime_daily(
    monitor_id: int,
    days: int = 30,
    session: AsyncSession = Depends(get_session),
):
    """Per-day uptime percentage for the daily-uptime bar chart.

    Returns one bucket per day (UTC midnight to midnight) for the last N
    days. Bucket value is the fraction of probes that were status=1.
    Days with zero probes get null pct so the chart can render a gap
    rather than an implied 0% (paused / not yet created).
    """
    days = max(1, min(int(days), 365))
    now = datetime.datetime.utcnow()
    # Align cutoff to the start of (today - days + 1) so we get exactly
    # `days` aligned buckets ending at today.
    today_midnight = datetime.datetime(now.year, now.month, now.day)
    cutoff = today_midnight - datetime.timedelta(days=days - 1)

    res = await session.execute(
        select(models.Heartbeat.time, models.Heartbeat.status)
        .where(
            models.Heartbeat.monitor_id == monitor_id,
            models.Heartbeat.time >= cutoff,
        )
        .order_by(models.Heartbeat.time)
    )
    rows = res.all()

    # Count up + total per day index, where day_index 0 = cutoff day.
    # Only probes with a definitive up/down outcome (status 0 or 1)
    # contribute to the uptime percentage. Pending (2) and maintenance
    # (3) are *transient* states — counting them as "down" would make
    # a healthy monitor whose latest probe happens to be in-flight read
    # as 50% uptime, which is the bug the user reported.
    up_counts = [0] * days
    total_counts = [0] * days
    cutoff_ts = cutoff.timestamp()
    for row in rows:
        if row.status not in (0, 1):
            continue  # skip pending / maintenance / unknown
        idx = int((row.time.timestamp() - cutoff_ts) // 86400)
        if 0 <= idx < days:
            total_counts[idx] += 1
            if row.status == 1:
                up_counts[idx] += 1

    buckets = []
    for i in range(days):
        day_t = cutoff + datetime.timedelta(days=i)
        total = total_counts[i]
        if total > 0:
            pct = round((up_counts[i] / total) * 10000) / 100
            buckets.append({
                "date": day_t.date().isoformat(),
                "uptime": pct,
                "probes": total,
                "down": total - up_counts[i],
            })
        else:
            buckets.append({
                "date": day_t.date().isoformat(),
                "uptime": None,
                "probes": 0,
                "down": 0,
            })

    total_probes = sum(total_counts)
    total_up = sum(up_counts)
    summary = {
        "uptime": round((total_up / total_probes) * 10000) / 100 if total_probes else None,
        "probes": total_probes,
        "down": total_probes - total_up,
        "days": days,
    }

    return {"ok": True, "buckets": buckets, "summary": summary}


_UPTIME_WINDOW_DELTAS = {
    "24": datetime.timedelta(hours=24),
    "720": datetime.timedelta(days=30),
    "1y": datetime.timedelta(days=365),
}


@router.get("/monitors/{monitor_id}/uptime")
async def monitor_uptime(
    monitor_id: int,
    windows: str = "24,720,1y",
    session: AsyncSession = Depends(get_session),
):
    """Rolling uptime percentage for a single monitor over the requested
    windows (24h / 30d / 1y).

    Split out from the dashboard heartbeat poll: opening one monitor's
    detail page used to rely on the dashboard recomputing 30d/1y uptime
    for *every* monitor on every poll, which meant a year-long scan across
    the whole heartbeat table every 10s. This computes only the one
    monitor the user is looking at, on demand. Keys mirror the dashboard's
    `<id>_<window>` convention so the frontend merges them straight into
    the shared uptimeList. Up (1) and down (0) beats form the denominator;
    pending (2) / maintenance (3) are excluded, matching the dashboard.
    """
    now = datetime.datetime.utcnow()
    requested = [w.strip() for w in windows.split(",") if w.strip()]
    out: Dict[str, float] = {}
    for key in requested:
        delta = _UPTIME_WINDOW_DELTAS.get(key)
        if delta is None:
            continue
        res = await session.execute(
            select(
                func.sum(case((models.Heartbeat.status == 1, 1), else_=0)),
                func.sum(case((models.Heartbeat.status.in_([0, 1]), 1), else_=0)),
            )
            .where(models.Heartbeat.monitor_id == monitor_id)
            .where(models.Heartbeat.time >= now - delta)
        )
        up_count, reckonable = res.one()
        up_count = int(up_count or 0)
        reckonable = int(reckonable or 0)
        if reckonable > 0:
            out[f"{monitor_id}_{key}"] = round(up_count / reckonable * 100, 4)
    return {"ok": True, "uptimeList": out}


_BADGE_PERIOD_HOURS = {
    "24h": 24,
    "7d": 24 * 7,
    "30d": 24 * 30,
    "90d": 24 * 90,
}


@router.get("/badges/{monitor_id}.svg")
async def uptime_badge(
    monitor_id: int,
    period: str = "24h",
    label: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Public Shields.io-style SVG uptime badge for embedding in a
    README or external status page. Reachable without auth; the only
    information leaked is the uptime percentage of a monitor whose
    numeric ID an embedder already knows.

    The badge is colour-banded:
      ≥99%  green
      ≥95%  amber
      <95%  red
      no data  grey

    `?period=24h|7d|30d|90d`. Default 24h.
    `?label=name` overrides the default "uptime" label.
    """
    from fastapi.responses import Response
    from server.badges import render_badge, color_for_uptime

    hours = _BADGE_PERIOD_HOURS.get(period, 24)
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)

    res = await session.execute(
        select(models.Heartbeat.status).where(
            models.Heartbeat.monitor_id == monitor_id,
            models.Heartbeat.time >= cutoff,
        )
    )
    rows = res.scalars().all()

    # Same exclusion rule as the daily-uptime chart — pending and
    # maintenance are transient/non-attributable, not failures.
    samples = [s for s in rows if s in (0, 1)]
    if samples:
        ups = sum(1 for s in samples if s == 1)
        pct = round((ups / len(samples)) * 10000) / 100
        value = f"{pct}%"
    else:
        pct = None
        value = "no data"

    svg = render_badge(
        # "observer-uptime" rather than just "uptime" so the badge is
        # visually distinguishable from Uptime Kuma's identical-looking
        # "uptime" badge in shared READMEs. Override with ?label=foo if
        # you'd rather have your own naming.
        label=(label or "observer-uptime").strip()[:40],
        value=value,
        color=color_for_uptime(pct),
    )
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            # Cache for 60s so a popular badge doesn't hammer the DB.
            # Long enough to absorb traffic spikes, short enough that
            # state changes show up reasonably quickly.
            "Cache-Control": "public, max-age=60",
        },
    )


@router.get("/monitors/{monitor_id}/tls-summary")
async def tls_summary(monitor_id: int, session: AsyncSession = Depends(get_session)):
    res = await session.execute(
        select(models.Heartbeat)
        .where(models.Heartbeat.monitor_id == monitor_id)
        .where(models.Heartbeat.cert_expire.isnot(None))
        .order_by(models.Heartbeat.id.desc())
        .limit(1)
    )
    hb = res.scalars().first()
    if not hb or hb.cert_expire is None:
        return {"ok": False, "valid": False, "certInfo": None}
    days = hb.cert_expire
    valid_to = (
        datetime.datetime.utcnow() + datetime.timedelta(days=days)
    ).isoformat()
    return {
        "ok": True,
        "valid": hb.cert_expire >= 0,
        "certInfo": {"daysRemaining": days, "validTo": valid_to},
    }


@router.get("/push-example/{name}")
async def push_example(
    name: str, interval: Optional[int] = None, url: Optional[str] = None
):
    code = f"curl {url or 'https://example.com/api/push/key?status=up&msg=OK&ping='}{interval or ''}"
    return {"code": code}


@router.post("/push/{token}")
async def push_heartbeat(
    token: str,
    status: str = "up",
    msg: str = "OK",
    ping: Optional[float] = None,
    session: AsyncSession = Depends(get_session),
):
    res = await session.execute(
        select(models.Monitor).where(
            models.Monitor.push_token == token, models.Monitor.active == True
        )
    )
    monitor = res.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    status_int = 1 if status == "up" else 0
    hb = models.Heartbeat(
        monitor_id=monitor.id,
        status=status_int,
        msg=msg,
        ping=ping,
    )

    # Determine if status has changed since the last heartbeat
    res_prev = await session.execute(
        select(models.Heartbeat)
        .where(models.Heartbeat.monitor_id == monitor.id)
        .order_by(models.Heartbeat.time.desc())
        .limit(1)
    )
    last = res_prev.scalars().first()
    if last is None or last.status != hb.status:
        hb.important = True
        hb.event = "up" if hb.status in (1, True) else "down"
        session.add(models.ImportantHeartbeat(monitor_id=monitor.id, message=msg))

    session.add(hb)
    await session.commit()
    if hb.important:
        await _send_notifications_for_monitor(session, monitor, hb)
    return {"ok": True}


@router.get("/settings")
async def get_settings(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(models.Setting))
    settings = {}
    for s in result.scalars().all():
        try:
            settings[s.key] = json.loads(s.value)
        except Exception:
            settings[s.key] = s.value
    return {"data": settings}


@router.post("/settings")
async def set_settings(
    payload: Dict,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    for key, raw_value in payload.get("settings", {}).items():
        value = raw_value
        if not isinstance(value, str):
            value = json.dumps(value)
        stmt = select(models.Setting).where(models.Setting.key == key)
        res = await session.execute(stmt)
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            session.add(models.Setting(key=key, value=value))

        if key == "trustProxy":
            request.app.state.trust_proxy_enabled = coerce_to_bool(raw_value)

    await session.commit()
    return {"ok": True}


@router.get("/reverse-proxy/cloudflared")
async def get_cloudflared_status(
    request: Request, session: AsyncSession = Depends(get_session)
):
    manager = get_cloudflared_manager(request)
    if not manager.token:
        res = await session.execute(
            select(models.Setting).where(models.Setting.key == "cloudflared_token")
        )
        setting = res.scalar_one_or_none()
        if setting is not None:
            manager.set_token(setting.value)
    return {"data": manager.status()}


@router.post("/reverse-proxy/cloudflared/start")
async def start_cloudflared(
    payload: CloudflaredStartPayload,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    manager = get_cloudflared_manager(request)
    token = payload.token or manager.token
    if not token:
        return {"ok": False, "msg": "missingToken", "data": manager.status()}

    ok, msg = await manager.start(token)
    if ok:
        await save_setting(session, "cloudflared_token", token)
        await session.commit()
    else:
        await session.rollback()
    return {"ok": ok, "msg": msg, "data": manager.status()}


@router.post("/reverse-proxy/cloudflared/stop")
async def stop_cloudflared(
    payload: CloudflaredStopPayload,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    # currentPassword is accepted for API parity but not required here yet
    manager = get_cloudflared_manager(request)
    ok, msg = await manager.stop()
    await session.commit()
    return {"ok": ok, "msg": msg, "data": manager.status()}


@router.delete("/reverse-proxy/cloudflared/token")
async def remove_cloudflared_token(
    request: Request, session: AsyncSession = Depends(get_session)
):
    manager = get_cloudflared_manager(request)
    manager.set_token(None)
    await save_setting(session, "cloudflared_token", None)
    await session.commit()
    return {"ok": True, "data": manager.status()}


@router.get("/notifications")
async def get_notifications(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(models.Notification))
    data = []
    for n in res.scalars().all():
        cfg = coerce_config_to_dict(n.config)
        if "discord_webhook_url" in cfg and "webhook_url" not in cfg:
            cfg["webhook_url"] = cfg.pop("discord_webhook_url")
        data.append({
            "id": n.id,
            "name": n.name,
            "type": n.type,
            "is_default": n.is_default,
            "active": n.active,
            "config": cfg,
        })
    return data


@router.post("/notifications")
async def add_notification(n: NotificationSchema, session: AsyncSession = Depends(get_session)):
    notif = models.Notification(
        name=n.name,
        type=n.type,
        active=bool(n.active) if n.active is not None else True,
        is_default=bool(n.is_default) if n.is_default is not None else False,
        config=json.dumps(_build_config(n)),
    )
    if n.id is not None:
        notif.id = n.id
    session.add(notif)
    await session.commit()
    await session.refresh(notif)
    return {"ok": True, "id": notif.id}


@router.post("/notifications/test")
async def test_notification(n: NotificationSchema):
    provider = get_provider(n.type)
    if not provider:
        raise HTTPException(status_code=400, detail="Unknown provider")
    # Pass a synthetic monitor + heartbeat with event="test" so providers
    # that go through message_formatter render the same well-formed
    # message they'd produce for a real alert (no "Type: UNKNOWN" etc.).
    test_monitor = {"name": n.name or "Observer", "type": "http", "url": ""}
    test_heartbeat = {"event": "test", "status": 1, "msg": "test"}
    try:
        await provider.send(_build_config(n), "Test", test_monitor, test_heartbeat)
    except ValueError as exc:
        # propagate invalid configuration error as a 400 status
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        # surface provider errors as validation issues
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/notifications/{notif_id}")
async def edit_notification(notif_id: int, n: NotificationSchema, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(models.Notification).where(models.Notification.id == notif_id))
    notif = res.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.name = n.name
    notif.type = n.type
    if n.active is not None:
        notif.active = bool(n.active)
    if n.is_default is not None:
        notif.is_default = bool(n.is_default)
    notif.config = json.dumps(_build_config(n))
    await session.commit()
    return {"ok": True, "id": notif.id}


@router.delete("/notifications/{notif_id}")
async def delete_notification(notif_id: int, session: AsyncSession = Depends(get_session)):
    await session.execute(delete(models.Notification).where(models.Notification.id == notif_id))
    await session.commit()
    return {"ok": True}


@router.get("/tags")
async def get_tags(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(models.Tag))
    tags = res.scalars().all()
    return {
        "ok": True,
        "tags": [
            {"id": t.id, "name": t.name, "color": t.color}
            for t in tags
        ],
    }


@router.post("/tags")
async def add_tag(tag: TagSchema, session: AsyncSession = Depends(get_session)):
    t = models.Tag(name=tag.name, color=tag.color)
    if tag.id is not None:
        t.id = tag.id
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return {
        "ok": True,
        "tag": {"id": t.id, "name": t.name, "color": t.color},
    }


@router.post("/tags/{tag_id}")
async def edit_tag(tag_id: int, tag: TagSchema, session: AsyncSession = Depends(get_session)):
    t = await session.get(models.Tag, tag_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tag not found")
    t.name = tag.name
    t.color = tag.color
    await session.commit()
    return {
        "ok": True,
        "tag": {"id": t.id, "name": t.name, "color": t.color},
    }


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, session: AsyncSession = Depends(get_session)):
    await session.execute(
        delete(models.MonitorTag).where(models.MonitorTag.tag_id == tag_id)
    )
    await session.execute(delete(models.Tag).where(models.Tag.id == tag_id))
    await session.commit()
    return {"ok": True}


class MonitorTagSchema(BaseModel):
    monitor_id: int = Field(..., alias="monitorId")
    tag_id: int = Field(..., alias="tagId")
    value: Optional[str] = ""
    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, extra="ignore"
    )


@router.post("/monitor-tags")
async def add_monitor_tag(
    mt: MonitorTagSchema, session: AsyncSession = Depends(get_session)
):
    monitor = await session.get(models.Monitor, mt.monitor_id)
    tag = await session.get(models.Tag, mt.tag_id)
    if not monitor or not tag:
        raise HTTPException(status_code=404, detail="Monitor or tag not found")
    value = mt.value or ""
    res = await session.execute(
        select(models.MonitorTag).where(
            models.MonitorTag.monitor_id == mt.monitor_id,
            models.MonitorTag.tag_id == mt.tag_id,
            models.MonitorTag.value == value,
        )
    )
    existing = res.scalar_one_or_none()
    if existing:
        return {
            "ok": True,
            "monitorTag": {"id": existing.id},
            "msg": "Label already assigned",
        }

    monitor_tag = models.MonitorTag(
        monitor_id=mt.monitor_id,
        tag_id=mt.tag_id,
        value=value,
    )
    session.add(monitor_tag)
    await session.commit()
    await session.refresh(monitor_tag)
    return {"ok": True, "monitorTag": {"id": monitor_tag.id}}


@router.delete("/monitor-tags")
async def delete_monitor_tag(
    monitor_id: int,
    tag_id: int,
    value: str = "",
    session: AsyncSession = Depends(get_session),
):
    await session.execute(
        delete(models.MonitorTag).where(
            models.MonitorTag.monitor_id == monitor_id,
            models.MonitorTag.tag_id == tag_id,
            models.MonitorTag.value == value,
        )
    )
    await session.commit()
    return {"ok": True}


_DB_PORT_DEFAULTS = {
    "postgres": 5432,
    "mysql": 3306,
}


class DatabaseSetupRequest(BaseModel):
    """Wizard payload — engine type plus the connection details that
    engine needs."""

    type: str  # "sqlite" | "postgres" | "mysql"
    hostname: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    path: Optional[str] = None  # SQLite-only — file path

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


def _build_database_url(req: DatabaseSetupRequest) -> str:
    """Translate the wizard payload into a SQLAlchemy async URL."""
    engine_type = (req.type or "").strip().lower()
    if engine_type == "sqlite":
        path = (req.path or "./data/observer.db").strip()
        return f"sqlite+aiosqlite:///{path}"
    if engine_type in ("postgres", "postgresql"):
        if not (req.hostname and req.username and req.database):
            raise HTTPException(
                status_code=400,
                detail="hostname, username and database are required for Postgres",
            )
        port = req.port or _DB_PORT_DEFAULTS["postgres"]
        password = f":{req.password}" if req.password else ""
        return (
            f"postgresql+asyncpg://{req.username}{password}"
            f"@{req.hostname}:{port}/{req.database}"
        )
    if engine_type in ("mysql", "mariadb"):
        if not (req.hostname and req.username and req.database):
            raise HTTPException(
                status_code=400,
                detail="hostname, username and database are required for MySQL/MariaDB",
            )
        port = req.port or _DB_PORT_DEFAULTS["mysql"]
        password = f":{req.password}" if req.password else ""
        return (
            f"mysql+asyncmy://{req.username}{password}"
            f"@{req.hostname}:{port}/{req.database}"
        )
    raise HTTPException(status_code=400, detail=f"unknown database type: {engine_type!r}")


async def _try_connect(database_url: str) -> None:
    """Open a one-shot connection and run SELECT 1 so the wizard can
    validate credentials without committing to an engine swap."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text as _text

    engine_test = create_async_engine(database_url, future=True, echo=False)
    try:
        async with engine_test.connect() as conn:
            await conn.execute(_text("SELECT 1"))
    finally:
        await engine_test.dispose()


@router.get("/setup-database-info")
async def setup_database_info(request: Request):
    """Tell the frontend whether the wizard needs to run."""
    return {
        "needsDbSetup": bool(getattr(request.app.state, "needs_db_setup", False))
    }


@router.post("/setup-database/test")
async def setup_database_test(payload: DatabaseSetupRequest):
    """Validate a connection without persisting anything."""
    url = _build_database_url(payload)
    try:
        await _try_connect(url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"connectionFailed: {exc}")
    return {"ok": True}


@router.post("/setup-database")
async def setup_database(payload: DatabaseSetupRequest, request: Request):
    """Persist the chosen URL, swap the active engine, kick off the
    background workers that lifespan deferred."""
    if not getattr(request.app.state, "needs_db_setup", False):
        raise HTTPException(status_code=400, detail="alreadySetup")

    url = _build_database_url(payload)
    try:
        await _try_connect(url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"connectionFailed: {exc}")

    from server.db import write_database_config, init_db
    from pathlib import Path as _Path

    write_database_config(url)
    await init_db(database_url=url)
    request.app.state.needs_db_setup = False

    # Tear down the throwaway bootstrap DB — its only job was to keep
    # the server alive long enough to serve this wizard.
    try:
        (_Path("data") / "_bootstrap.db").unlink(missing_ok=True)
    except Exception:
        pass

    starter = getattr(request.app.state, "start_background_workers", None)
    if starter:
        try:
            await starter()
        except Exception as exc:
            print(f"WARN: post-DB-setup worker boot raised: {exc!r}")

    return {"ok": True}


@router.get("/setup-needed")
async def need_setup(session: AsyncSession = Depends(get_session)):
    res = await session.execute(
        select(models.Setting).where(models.Setting.key == "setup_done")
    )
    setting = res.scalar_one_or_none()
    if setting:
        return {"needSetup": False}

    res = await session.execute(select(models.User).limit(1))
    return {"needSetup": res.scalar_one_or_none() is None}


@router.post("/setup")
async def setup(payload: Dict, session: AsyncSession = Depends(get_session)):
    username = payload.get("username")
    password = payload.get("password")

    if not username or not password:
        raise HTTPException(status_code=400, detail="usernameAndPasswordRequired")

    res = await session.execute(select(models.User).limit(1))
    if res.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="alreadySetup")

    hashed = pwd_context.hash(password)
    user = models.User(
        username=username,
        password=hashed,
        is_admin=True,
        active=True,
    )
    session.add(user)
    session.add(models.Setting(key="setup_done", value="true"))

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="usernameTaken")

    token = generate_token(user.username, user.id)
    return {"ok": True, "token": token}


@router.post("/maintenance")
async def create_maintenance(data: Dict, session: AsyncSession = Depends(get_session)):
    """Create a new maintenance record."""
    m = models.Maintenance(data=json.dumps(data))
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return {"ok": True, "maintenanceID": m.id}


@router.get("/maintenance")
async def list_maintenances(session: AsyncSession = Depends(get_session)):
    """Return all maintenance records."""
    res = await session.execute(select(models.Maintenance))
    maints = res.scalars().all()
    result = []
    for m in maints:
        try:
            data = json.loads(m.data) if m.data else {}
        except Exception:
            data = {}
        result.append({"id": m.id, **data})
    return result


@router.get("/maintenance/{maintenance_id}")
async def get_maintenance(
    maintenance_id: int, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(models.Maintenance).where(models.Maintenance.id == maintenance_id)
    )
    m = res.scalar_one_or_none()
    if not m:
        m = models.Maintenance(id=maintenance_id, data="{}")
        session.add(m)
        await session.commit()
    return {"ok": True, "maintenance": {"id": m.id, **(m.data and {"data": m.data})}}


@router.post("/maintenance/{maintenance_id}")
async def edit_maintenance(
    maintenance_id: int, data: Dict, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(models.Maintenance).where(models.Maintenance.id == maintenance_id)
    )
    m = res.scalar_one_or_none()
    if m:
        m.data = json.dumps(data)
    else:
        m = models.Maintenance(id=maintenance_id, data=json.dumps(data))
        session.add(m)
    await session.commit()
    return {"ok": True, "maintenanceID": maintenance_id}


@router.delete("/maintenance/{maintenance_id}")
async def delete_maintenance(
    maintenance_id: int, session: AsyncSession = Depends(get_session)
):
    """Delete a maintenance record and all related mappings."""
    await session.execute(
        delete(models.MaintenanceMonitor).where(
            models.MaintenanceMonitor.maintenance_id == maintenance_id
        )
    )
    await session.execute(
        delete(models.MaintenanceStatusPage).where(
            models.MaintenanceStatusPage.maintenance_id == maintenance_id
        )
    )
    await session.execute(
        delete(models.Maintenance).where(models.Maintenance.id == maintenance_id)
    )
    await session.commit()
    return {"ok": True}


@router.post("/maintenance/{maintenance_id}/monitors")
async def set_maintenance_monitors(
    maintenance_id: int, data: Dict, session: AsyncSession = Depends(get_session)
):
    """Assign monitors to a maintenance record."""
    monitor_ids = [m.get("id") if isinstance(m, dict) else m for m in data.get("monitors", [])]
    await session.execute(
        delete(models.MaintenanceMonitor).where(models.MaintenanceMonitor.maintenance_id == maintenance_id)
    )
    for mid in monitor_ids:
        session.add(models.MaintenanceMonitor(maintenance_id=maintenance_id, monitor_id=mid))
    await session.commit()
    return {"ok": True}


@router.get("/maintenance/{maintenance_id}/monitors")
async def get_maintenance_monitors(
    maintenance_id: int, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(models.Monitor)
        .join(models.MaintenanceMonitor, models.Monitor.id == models.MaintenanceMonitor.monitor_id)
        .where(models.MaintenanceMonitor.maintenance_id == maintenance_id)
    )
    monitors = res.scalars().all()
    return {
        "ok": True,
        "monitors": [{"id": m.id, "name": m.name} for m in monitors],
    }


@router.post("/maintenance/{maintenance_id}/status-pages")
async def set_maintenance_status_pages(
    maintenance_id: int, data: Dict, session: AsyncSession = Depends(get_session)
):
    """Assign status pages to a maintenance record."""
    slugs = [s.get("id") if isinstance(s, dict) else s for s in data.get("statusPages", [])]
    await session.execute(
        delete(models.MaintenanceStatusPage).where(models.MaintenanceStatusPage.maintenance_id == maintenance_id)
    )
    for slug in slugs:
        if slug:
            session.add(models.MaintenanceStatusPage(maintenance_id=maintenance_id, status_page_slug=slug))
    await session.commit()
    return {"ok": True}


@router.get("/maintenance/{maintenance_id}/status-pages")
async def get_maintenance_status_pages(
    maintenance_id: int, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(models.StatusPage)
        .join(
            models.MaintenanceStatusPage,
            models.StatusPage.slug == models.MaintenanceStatusPage.status_page_slug,
        )
        .where(models.MaintenanceStatusPage.maintenance_id == maintenance_id)
    )
    pages = res.scalars().all()
    return {
        "ok": True,
        "statusPages": [{"id": p.slug, "title": p.title} for p in pages],
    }


@router.get("/monitors/{monitor_id}/important-heartbeats")
async def important_list(
    monitor_id: int,
    session: AsyncSession = Depends(get_session),
    offset: int = 0,
    limit: int = 10,
):
    stmt = (
        select(models.ImportantHeartbeat)
        .where(models.ImportantHeartbeat.monitor_id == monitor_id)
        .order_by(models.ImportantHeartbeat.id.asc())
        .offset(offset)
        .limit(limit)
    )
    res = await session.execute(stmt)
    hbs = res.scalars().all()
    return {
        "ok": True,
        "data": [
            {"id": hb.id, "monitor_id": hb.monitor_id, "message": hb.message}
            for hb in hbs
        ],
    }


@router.get("/monitors/{monitor_id}/important-heartbeats/count")
async def important_count(
    monitor_id: int, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(func.count(models.ImportantHeartbeat.id)).where(
            models.ImportantHeartbeat.monitor_id == monitor_id
        )
    )
    count = res.scalar_one()
    return {"ok": True, "count": count}


@router.get("/important-heartbeats/count")
async def important_count_all(session: AsyncSession = Depends(get_session)):
    res = await session.execute(
        select(func.count(models.ImportantHeartbeat.id))
    )
    count = res.scalar_one()
    return {"ok": True, "count": count}


@router.get("/important-heartbeats/paged")
async def important_list_paged(
    session: AsyncSession = Depends(get_session), offset: int = 0, limit: int = 10
):
    stmt = select(models.ImportantHeartbeat).offset(offset).limit(limit)
    res = await session.execute(stmt)
    hbs = res.scalars().all()
    return {
        "ok": True,
        "data": [
            {"id": hb.id, "monitor_id": hb.monitor_id, "message": hb.message}
            for hb in hbs
        ],
    }


@router.get("/events")
async def list_events(
    session: AsyncSession = Depends(get_session),
    offset: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
):
    """Recent monitor events, newest first.

    Backed by `Heartbeat WHERE important=True` rather than the anaemic
    `ImportantHeartbeat` table — that table only stores `(id, monitor_id,
    message)`, but the in-app feed needs the timestamp and status as well.

    Joins the monitor row so the client can render `<monitor name>` without
    one extra fetch per event.
    """
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200
    if offset < 0:
        offset = 0

    status_filter = None
    if status is not None:
        mapping = {"up": 1, "down": 0, "pending": 2, "maintenance": 3}
        if status in mapping:
            status_filter = mapping[status]

    stmt = (
        select(
            models.Heartbeat.id,
            models.Heartbeat.monitor_id,
            models.Heartbeat.status,
            models.Heartbeat.time,
            models.Heartbeat.msg,
            models.Heartbeat.ping,
            models.Monitor.name,
            models.Monitor.type,
        )
        .join(models.Monitor, models.Monitor.id == models.Heartbeat.monitor_id)
        .where(models.Heartbeat.important == True)  # noqa: E712 - sqlalchemy boolean compare
    )
    if status_filter is not None:
        stmt = stmt.where(models.Heartbeat.status == status_filter)
    stmt = (
        stmt.order_by(models.Heartbeat.time.desc(), models.Heartbeat.id.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await session.execute(stmt)
    rows = res.mappings().all()

    events = []
    for row in rows:
        events.append({
            "id": int(row["id"]),
            "monitorID": int(row["monitor_id"]),
            "monitorName": row["name"],
            "monitorType": row["type"],
            "status": int(row["status"]),
            "time": row["time"].isoformat() if row["time"] is not None else None,
            "msg": row["msg"] or "",
            "ping": float(row["ping"]) if row["ping"] is not None else None,
        })

    count_stmt = (
        select(func.count())
        .select_from(models.Heartbeat)
        .where(models.Heartbeat.important == True)  # noqa: E712
    )
    if status_filter is not None:
        count_stmt = count_stmt.where(models.Heartbeat.status == status_filter)
    total_res = await session.execute(count_stmt)
    total = int(total_res.scalar_one() or 0)

    return {
        "ok": True,
        "events": events,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/status-page")
async def list_status_pages(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(models.StatusPage))
    pages = res.scalars().all()
    result = []
    for p in pages:
        try:
            cfg = json.loads(p.config)
        except Exception:
            cfg = {}
        if "icon" not in cfg:
            cfg["icon"] = "/icon.svg"
        result.append({"slug": p.slug, "title": p.title, "config": cfg, "public": p.public})
    return result


@router.post("/status-page")
async def create_status_page(
    sp: StatusPageSchema, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(models.StatusPage).where(models.StatusPage.slug == sp.slug)
    )
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug exists")
    cfg = sp.config or {}
    if "icon" not in cfg:
        cfg["icon"] = "/icon.svg"
    if sp.monitors:
        if all(isinstance(m, (int, str)) for m in sp.monitors):
            group_defs = [{"name": "Main", "monitorList": sp.monitors}]
        else:
            group_defs = sp.monitors  # type: ignore[assignment]
        monitor_ids: List[int] = []
        monitor_names: List[str] = []
        def _norm(name: str) -> str:
            return name.strip().casefold()
        for g in group_defs:
            for m in g.get("monitorList", []):
                if isinstance(m, dict):
                    mid = m.get("id")
                    mname = m.get("name")
                elif isinstance(m, int):
                    mid = m
                    mname = None
                else:
                    mid = None
                    mname = m
                if isinstance(mid, int):
                    monitor_ids.append(mid)
                elif isinstance(mname, str):
                    monitor_names.append(_norm(mname))
        if len(monitor_names) != len(set(monitor_names)):
            raise HTTPException(status_code=400, detail="monitorNameDuplicate")
        conditions = []
        if monitor_ids:
            conditions.append(models.Monitor.id.in_(monitor_ids))
        if monitor_names:
            conditions.append(
                func.lower(func.trim(models.Monitor.name)).in_(monitor_names)
            )
        monitor_map = {}
        if conditions:
            stmt = (
                select(models.Monitor).where(or_(*conditions))
                if len(conditions) > 1
                else select(models.Monitor).where(conditions[0])
            )
            res = await session.execute(stmt)
            monitors = res.scalars().all()
        else:
            monitors = []
        monitors_by_id = {m.id: m for m in monitors}
        monitors_by_name = {_norm(m.name): m for m in monitors}
        missing_ids = set(monitor_ids) - set(monitors_by_id.keys())
        missing_names = set(monitor_names) - set(monitors_by_name.keys())
        if missing_ids or missing_names:
            raise HTTPException(status_code=400, detail="monitorNameNotFound")
        tag_rows = await session.execute(
            select(models.MonitorTag, models.Tag)
            .join(models.Tag, models.MonitorTag.tag_id == models.Tag.id)
            .where(models.MonitorTag.monitor_id.in_([m.id for m in monitors]))
        )
        tag_map: Dict[int, list] = {}
        for mt, t in tag_rows.fetchall():
            tag_map.setdefault(mt.monitor_id, []).append(
                {
                    "id": mt.id,
                    "monitor_id": mt.monitor_id,
                    "tag_id": mt.tag_id,
                    "value": mt.value,
                    "name": t.name,
                    "color": t.color,
                }
            )
        for m in monitors:
            data = MonitorSchema.from_orm_clean(m)
            data.pop("maxretries", None)
            data["tags"] = tag_map.get(m.id, [])
            monitor_map[m.id] = data
        groups = []
        for idx, g in enumerate(group_defs, start=1):
            g_name = g.get("name") or f"Group {idx}"
            g_monitors = []
            for m in g.get("monitorList", []):
                send_url = False
                mid = None
                if isinstance(m, dict):
                    send_url = bool(m.get("sendUrl", False))
                    if "id" in m:
                        mid = m["id"]
                    elif "name" in m:
                        key = _norm(m["name"])
                        mid = (
                            monitors_by_name.get(key).id
                            if key in monitors_by_name
                            else None
                        )
                elif isinstance(m, int):
                    mid = m
                else:
                    key = _norm(m)
                    mid = (
                        monitors_by_name.get(key).id
                        if key in monitors_by_name
                        else None
                    )
                if isinstance(mid, int) and mid in monitor_map:
                    g_monitors.append({**monitor_map[mid], "sendUrl": send_url})
            groups.append({"id": idx, "name": g_name, "monitorList": g_monitors})
        cfg["publicGroupList"] = groups
        cfg["monitorList"] = monitor_map
    page = models.StatusPage(
        slug=sp.slug,
        title=sp.title,
        config=json.dumps(cfg) if not isinstance(cfg, str) else cfg,
        public=sp.public if sp.public is not None else True,
    )
    session.add(page)
    await session.commit()
    return {"ok": True, "slug": sp.slug}


@router.get("/status-page/{slug}")
async def get_status_page(slug: str, session: AsyncSession = Depends(get_session)):
    res = await session.execute(
        select(models.StatusPage).where(models.StatusPage.slug == slug)
    )
    page = res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        cfg = json.loads(page.config)
    except Exception:
        cfg = {}
    if "icon" not in cfg:
        cfg["icon"] = "/icon.svg"
    cfg.setdefault("title", page.title)
    cfg.setdefault("slug", page.slug)

    inc_res = await session.execute(
        select(models.Incident)
        .where(models.Incident.status_page_slug == slug)
        .where(models.Incident.pinned == True)
        .order_by(models.Incident.created_date.desc())
    )
    inc = inc_res.scalars().first()
    incident_json = inc.to_json() if inc else None

    return {
        "ok": True,
        "config": cfg,
        "incident": incident_json,
        "publicGroupList": cfg.get("publicGroupList", []),
        "maintenanceList": cfg.get("maintenanceList", []),
        "public": page.public,
    }


@router.post("/status-page/{slug}/incident")
async def post_incident(
    slug: str, data: IncidentSchema, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(select(models.StatusPage).where(models.StatusPage.slug == slug))
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Status page not found")

    now = datetime.datetime.utcnow()

    if data.id is not None:
        res = await session.execute(
            select(models.Incident).where(
                models.Incident.id == data.id,
                models.Incident.status_page_slug == slug,
            )
        )
        incident = res.scalar_one_or_none()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        incident.title = data.title
        incident.content = data.content
        incident.style = data.style or "primary"
        incident.last_updated_date = now
    else:
        await session.execute(
            update(models.Incident)
            .where(models.Incident.status_page_slug == slug, models.Incident.pinned == True)
            .values(pinned=False)
        )
        incident = models.Incident(
            status_page_slug=slug,
            title=data.title,
            content=data.content,
            style=data.style or "primary",
            created_date=now,
            pinned=True,
        )
        session.add(incident)

    await session.commit()
    await session.refresh(incident)
    return {"ok": True, "incident": incident.to_json()}


@router.post("/status-page/{slug}/unpin-incident")
async def unpin_incident(slug: str, session: AsyncSession = Depends(get_session)):
    await session.execute(
        update(models.Incident)
        .where(models.Incident.status_page_slug == slug, models.Incident.pinned == True)
        .values(pinned=False)
    )
    await session.commit()
    return {"ok": True}


@router.post("/status-page/{slug}")
async def save_status_page(
    slug: str, data: Dict, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(
        select(models.StatusPage).where(models.StatusPage.slug == slug)
    )
    page = res.scalar_one_or_none()
    if not page:
        page = models.StatusPage(slug=slug, title=data.get("title", slug), config="{}")
        session.add(page)
    cfg = data.get("config", {})
    if isinstance(cfg, str):
        try:
            cfg_obj = json.loads(cfg)
        except Exception:
            cfg_obj = {}
    else:
        cfg_obj = cfg or {}

    if "title" in cfg_obj and cfg_obj["title"] is not None:
        page.title = str(cfg_obj["title"]).strip()

    new_slug = str(cfg_obj.get("slug", "")).strip().lower()
    if new_slug and new_slug != page.slug:
        exists = await session.execute(
            select(models.StatusPage).where(models.StatusPage.slug == new_slug)
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Slug exists")
        page.slug = new_slug

    page.config = json.dumps(cfg_obj)
    if "public" in data:
        page.public = bool(data["public"])
    await session.commit()
    return {"ok": True, "slug": page.slug}


@router.delete("/status-page/{slug}")
async def delete_status_page(slug: str, session: AsyncSession = Depends(get_session)):
    await session.execute(
        delete(models.StatusPage).where(models.StatusPage.slug == slug)
    )
    await session.commit()
    return {"ok": True}


@router.get("/status-page/heartbeat/{slug}")
async def get_status_page_heartbeat(
    slug: str,
    session: AsyncSession = Depends(get_session),
    limit: int = 100,
    since: float | None = None,
    uptime_windows: str = "24,720,1y",
):
    now = datetime.datetime.utcnow()

    res = await session.execute(select(models.Monitor.id, models.Monitor.interval))
    monitor_rows = res.mappings().all()
    monitor_ids: List[int] = []
    for row in monitor_rows:
        monitor_id = int(row["id"])
        monitor_ids.append(monitor_id)

    if not monitor_ids:
        return {"heartbeatList": {}, "uptimeList": {}}

    # Fetch the most recent `limit` heartbeats per monitor for display.
    # Using DESC + LIMIT keeps each query tiny and index-friendly; we
    # reverse the result afterwards to restore chronological order.
    since_dt = None
    if since is not None:
        since_dt = datetime.datetime.utcfromtimestamp(since)

    heartbeat_list: Dict[int, list] = {}
    for mid in monitor_ids:
        stmt = select(models.Heartbeat).where(models.Heartbeat.monitor_id == mid)
        if since_dt is not None:
            stmt = stmt.where(models.Heartbeat.time >= since_dt)
        stmt = stmt.order_by(models.Heartbeat.time.desc()).limit(limit)
        res = await session.execute(stmt)
        beats = list(reversed(res.scalars().all()))
        if beats:
            heartbeat_list[mid] = [hb.to_json() for hb in beats]

    # Calculate uptime using SQL aggregates — one query per period.
    # This avoids loading every historical heartbeat into Python memory.
    #
    # Only `up` (status=1) and `down` (status=0) beats represent a known
    # availability state. `pending` (2) and `maintenance` (3) beats are
    # transitional / expected and are excluded from the denominator —
    # otherwise a brand-new monitor whose first beat is `pending` would
    # forever sit at 99.x% (the pending sample stays in the 24h window
    # for a day) and a planned maintenance window would drag the score
    # down even though the user marked it as expected.
    #
    # Only the requested windows are computed. The authenticated dashboard
    # renders just the 24h figure, so it asks for `uptime_windows=24` and
    # we skip the far more expensive 30d / 1y full-window scans — those are
    # fetched per-monitor by the detail page (their only consumer) instead
    # of being recomputed for every monitor on every 10s poll. Public
    # status pages keep requesting all three via the default.
    uptime_list: Dict[str, float] = {}
    all_durations = {
        "24": datetime.timedelta(hours=24),
        "720": datetime.timedelta(days=30),
        "1y": datetime.timedelta(days=365),
    }
    requested = [w.strip() for w in uptime_windows.split(",") if w.strip()]
    durations = {k: all_durations[k] for k in requested if k in all_durations}
    for key, delta in durations.items():
        period_start = now - delta
        stmt = (
            select(
                models.Heartbeat.monitor_id,
                func.sum(case((models.Heartbeat.status == 1, 1), else_=0)).label("up_count"),
                func.sum(
                    case(
                        (models.Heartbeat.status.in_([0, 1]), 1),
                        else_=0,
                    )
                ).label("reckonable"),
            )
            .where(models.Heartbeat.monitor_id.in_(monitor_ids))
            .where(models.Heartbeat.time >= period_start)
            .group_by(models.Heartbeat.monitor_id)
        )
        res = await session.execute(stmt)
        for row in res.mappings():
            mid = int(row["monitor_id"])
            up_count = int(row["up_count"] or 0)
            reckonable = int(row["reckonable"] or 0)
            if reckonable > 0:
                uptime_list[f"{mid}_{key}"] = round(up_count / reckonable * 100, 4)

    return {"heartbeatList": heartbeat_list, "uptimeList": uptime_list}


@router.post("/status-page/cert-expiry")
async def status_page_cert_expiry(
    body: Dict, session: AsyncSession = Depends(get_session)
):
    ids = [int(i) for i in (body.get("monitorIDs") or []) if str(i).isdigit()]
    if not ids:
        return {"ok": True, "map": {}}

    # Single query: for each monitor get the most recent heartbeat that
    # has cert_expire set, using MAX(id) as a proxy for most-recent.
    subq = (
        select(
            models.Heartbeat.monitor_id,
            func.max(models.Heartbeat.id).label("max_id"),
        )
        .where(models.Heartbeat.monitor_id.in_(ids))
        .where(models.Heartbeat.cert_expire.isnot(None))
        .group_by(models.Heartbeat.monitor_id)
        .subquery()
    )
    res = await session.execute(
        select(models.Heartbeat).join(subq, models.Heartbeat.id == subq.c.max_id)
    )
    heartbeats = res.scalars().all()

    out: Dict[str, Dict] = {str(mid): {"valid": False, "daysRemaining": None} for mid in ids}
    for hb in heartbeats:
        out[str(hb.monitor_id)] = {
            "valid": hb.cert_expire >= 0,
            "daysRemaining": hb.cert_expire,
        }
    return {"ok": True, "map": out}
