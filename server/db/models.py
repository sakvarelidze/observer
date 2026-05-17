from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression
import datetime
from .database import Base


# All `Column(String)` declarations carry an explicit length. SQLite and
# Postgres treat unbounded VARCHAR fine, but MySQL/MariaDB require a
# length and will refuse to CREATE TABLE without one. Lengths are sized
# to the actual data — usernames/names/types fit comfortably in 255,
# URLs use 2048 (the practical web max), TOTP/bcrypt/token columns also
# fit in 255. Free-text fields (descriptions, DNS results, etc.) use
# Text, which translates to TEXT on every supported engine without a
# size constraint.


class Proxy(Base):
    __tablename__ = "proxies"
    id = Column(Integer, primary_key=True)
    protocol = Column(String(16), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    auth = Column(Boolean, default=False)
    username = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)
    active = Column(Boolean, default=True)
    default = Column(Boolean, default=False)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    two_fa_secret = Column(String(255), nullable=True)
    two_fa_enabled = Column(Boolean, default=False)
    two_fa_temp_secret = Column(String(255), nullable=True)
    two_fa_temp_verified_at = Column(DateTime, nullable=True)


class Monitor(Base):
    __tablename__ = "monitors"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    url = Column(String(2048), nullable=False)
    push_token = Column(String(64), nullable=True, unique=True)
    active = Column(Boolean, default=True)
    type = Column(String(32), default="http")
    parent = Column(Integer, nullable=True)
    interval = Column(Integer, nullable=False, default=30, server_default=text("30"))
    maxretries = Column(Integer, default=0)
    retry_interval = Column(Integer, default=0)
    resend_interval = Column(Integer, default=0)
    ignore_tls = Column(Boolean, default=False)
    tls_verify_mode = Column(String(16), nullable=False, server_default="system")
    custom_ca_pem = Column(Text, nullable=True)
    custom_ca_sha256 = Column(String(64), nullable=True)
    custom_ca_subject = Column(String(256), nullable=True)
    custom_ca_issuer = Column(String(256), nullable=True)
    custom_ca_trusted_at = Column(DateTime, nullable=True)
    expiry_notification = Column(Boolean, default=False)
    cert_expiry_threshold_days = Column(Integer, default=14)
    last_cert_notified_days = Column(Integer, nullable=True)
    last_cert_notified_at = Column(DateTime, nullable=True)
    maxredirects = Column(Integer, default=10)
    cache_bust = Column(Boolean, default=False)
    upside_down = Column(Boolean, default=False)
    accepted_statuscodes_json = Column(Text, default='["200-299"]')
    hostname = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    proxy_id = Column(Integer, ForeignKey("proxies.id"), nullable=True)
    description = Column(Text, nullable=True)
    method = Column(String(16), default="GET")
    body = Column(Text, nullable=True)
    headers_json = Column(Text, nullable=True)
    basic_auth_user = Column(String(255), nullable=True)
    basic_auth_pass = Column(String(255), nullable=True)
    dns_resolve_type = Column(String(8), nullable=True)
    dns_resolve_server = Column(String(255), nullable=True)
    dns_last_result = Column(Text, nullable=True)
    invert_keyword = Column(Boolean, default=False)
    ping_numeric = Column(Boolean, default=True)
    ping_count = Column(Integer, default=3)
    ping_per_request_timeout = Column(Integer, default=2)
    packet_size = Column(Integer, default=56)
    # Slow-response alerting: when set, fire a notification once
    # `slow_response_consecutive` consecutive UP probes have ping >
    # threshold. `slow_alert_active` debounces — flip True when the
    # alert fires, back to False on the first non-slow probe so the
    # next slow streak starts fresh.
    slow_response_threshold_ms = Column(Integer, nullable=True)
    slow_response_consecutive = Column(Integer, nullable=False, default=3, server_default=text("3"))
    slow_alert_active = Column(Boolean, nullable=False, default=False, server_default=expression.false())

    # Note: `unique=True` on push_token (above) gives us "unique among
    # non-null values" semantics on every supported engine — SQLite,
    # Postgres, and MySQL all allow multiple NULLs in a UNIQUE column.
    # The previous SQLite-specific partial index was redundant.

    proxy = relationship(
        "Proxy",
        primaryjoin="Proxy.id==Monitor.proxy_id",
        uselist=False,
        lazy="selectin",  # async-friendly eager load
    )

    @property
    def accepted_statuscodes(self):
        try:
            import json
            return json.loads(self.accepted_statuscodes_json)
        except Exception:
            return ["200-299"]

    @property
    def headers(self):
        try:
            import json
            return json.loads(self.headers_json) if self.headers_json else None
        except Exception:
            return None


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(128), unique=True, nullable=False)
    value = Column(Text)


class StatusPage(Base):
    __tablename__ = "status_pages"
    slug = Column(String(255), primary_key=True)
    title = Column(String(255), nullable=False)
    config = Column(Text)
    public = Column(Boolean, default=True)


class Maintenance(Base):
    __tablename__ = "maintenances"
    id = Column(Integer, primary_key=True)
    data = Column(Text)


class MaintenanceMonitor(Base):
    """Mapping between maintenances and monitors."""

    __tablename__ = "maintenance_monitors"
    maintenance_id = Column(Integer, ForeignKey("maintenances.id"), primary_key=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), primary_key=True)


class MaintenanceStatusPage(Base):
    """Mapping between maintenances and status pages."""

    __tablename__ = "maintenance_status_pages"
    maintenance_id = Column(Integer, ForeignKey("maintenances.id"), primary_key=True)
    status_page_slug = Column(String(255), ForeignKey("status_pages.slug"), primary_key=True)


class ImportantHeartbeat(Base):
    __tablename__ = "important_heartbeats"
    id = Column(Integer, primary_key=True)
    monitor_id = Column(Integer)
    message = Column(Text)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    type = Column(String(64), nullable=False)
    active = Column(Boolean, nullable=False, server_default=expression.true())
    is_default = Column(Boolean, default=False)
    config = Column(Text)


class MonitorNotification(Base):
    """Association between monitors and notifications."""

    __tablename__ = "monitor_notifications"
    id = Column(Integer, primary_key=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=False)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=False)

    __table_args__ = (UniqueConstraint("monitor_id", "notification_id"),)


class APIKey(Base):
    """API key for external access."""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    hashed_key = Column(String(255), nullable=False)
    created_date = Column(DateTime, default=datetime.datetime.utcnow)
    expires = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    role = Column(String(16), default="read")

    def to_json(self):
        now = datetime.datetime.utcnow()
        status = "active" if self.active else "inactive"
        if self.expires and self.expires < now:
            status = "expired"
        return {
            "id": self.id,
            "name": self.name,
            "createdDate": self.created_date.isoformat(),
            "expires": self.expires.isoformat() if self.expires else None,
            "active": self.active,
            "status": status,
            "role": self.role,
        }


class Heartbeat(Base):
    __tablename__ = "heartbeats"
    id = Column(Integer, primary_key=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=False)
    status = Column(Integer, nullable=False)
    time = Column(DateTime, default=datetime.datetime.utcnow)
    msg = Column(Text, default="")
    ping = Column(Float)
    important = Column(Boolean, default=False)
    duration = Column(Float)
    retries = Column(Integer, default=0)
    cert_expire = Column(Integer)

    __table_args__ = (
        Index("ix_heartbeats_monitor_time", "monitor_id", "time"),
    )

    def to_public_json(self):
        return {
            "status": self.status,
            "time": self.time.isoformat(),
            "msg": "",
            "ping": self.ping,
        }

    def to_json(self):
        return {
            "monitorID": self.monitor_id,
            "status": self.status,
            "time": self.time.isoformat(),
            "msg": self.msg,
            "ping": self.ping,
            "important": self.important,
            "duration": self.duration,
            "retries": self.retries,
        **({"cert_expire": self.cert_expire} if self.cert_expire is not None else {}),
        }


class Incident(Base):
    """Incident pinned to a status page."""

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True)
    status_page_slug = Column(String(255), ForeignKey("status_pages.slug"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    style = Column(String(32), default="primary")
    created_date = Column(DateTime, default=datetime.datetime.utcnow)
    last_updated_date = Column(DateTime)
    pinned = Column(Boolean, default=True)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "style": self.style,
            "createdDate": self.created_date.isoformat(),
            **(
                {"lastUpdatedDate": self.last_updated_date.isoformat()}
                if self.last_updated_date
                else {}
            ),
        }


class Tag(Base):
    """User definable tag for monitors."""

    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    color = Column(String(32), nullable=False)


class MonitorTag(Base):
    """Association between monitors and tags."""

    __tablename__ = "monitor_tags"
    __table_args__ = (
        UniqueConstraint("monitor_id", "tag_id", "value", name="uix_monitor_tag"),
    )

    id = Column(Integer, primary_key=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    value = Column(String(255), default="")
