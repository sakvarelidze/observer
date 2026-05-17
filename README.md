<h1 align="center">
  Observer 👁️
</h1>

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="Observer dashboard — pulse-wall view showing 53 monitors with live heartbeat bars, response times, and uptime percentages" width="100%">
</p>

<p align="center">
  <img src="docs/screenshots/dashboard_monitor.png" alt="Observer monitor dashboard — detailed overview of a monitor with live heartbeat bars, response times, and uptime percentages" width="100%">
</p>

<p align="center">
  <img src="docs/screenshots/status_page.png" alt="Observer Status Page — pulse-wall view showing monitors with live heartbeat bars, response times, and uptime percentages" width="100%">
</p>

A self-hosted uptime and infrastructure monitor. Probe HTTP / DNS / Ping / SMTP / SNMP / MongoDB / RabbitMQ / Tailscale endpoints on a schedule, get alerts when something breaks, and publish a public status page.

Observer started life as a fork of [Uptime Kuma](https://github.com/louislam/uptime-kuma) (Huge shoutout!). The backend was rewritten from scratch in Python on FastAPI; the frontend is the v2 redesign described below. The persistent WebSocket bridge that Uptime Kuma uses for live data was replaced with REST + polite polling, which is simpler to operate, scales further on a single host, and plays nicely with reverse proxies and Cloudflare Tunnel.

## Quick start

The fastest path is `docker compose`:

```bash
git clone https://github.com/sakvarelidze/observer.git
cd observer
docker compose up -d
```

The frontend will be available at `http://localhost:3000`, the API at `http://localhost:3001`. On first visit, `/setup` walks you through creating the admin account.

## Features

**Monitoring**

- HTTP(S), DNS, Ping (ICMP), SMTP, SNMP, MongoDB, RabbitMQ, Tailscale Ping, Push (heartbeat receiver), Manual, and Group monitors.
- Per-monitor probe intervals, retry counts, expected status codes, keyword/JSON-query body checks.
- Cert expiry tracking for HTTPS monitors with configurable warning thresholds.
- Tag-based grouping, monitor-level color and description.

**Alerting**

- Eight notification providers, all native-rich-card where the platform supports it: Discord (embeds), Slack (Block Kit + colored attachments), Microsoft Teams (MessageCard sections), Telegram (HTML + linkified URL), ntfy, PagerDuty (Events API v2 with stable dedup keys for auto-resolve), Twilio (SMS), Grafana OnCall.
- Cert-expiry warnings dispatched alongside down/up alerts.
- Default channels (fire on every important heartbeat) and per-monitor channels.

**Status pages**

- Multiple status pages per instance, each at `/status/<slug>`.
- Public or private (private pages 403 unauthenticated visitors).
- Custom title, icon, footer text. Manual incident banners and scheduled-maintenance ribbons.
- Heartbeat bars per monitor, 24h / 30d / 1y uptime percentages.

**Operations**

- Configurable heartbeat retention (default 180 days). The hourly pruner trims old heartbeats so SQLite doesn't grow unbounded.
- Maintenance windows.
- Reverse-proxy header trust toggle (`X-Forwarded-For`, `Forwarded`) and built-in Cloudflare Tunnel manager.
- LDAP authentication, password + 2FA (TOTP), API keys for external automation.
- REST API with auto-generated OpenAPI docs at `/docs`.

**UI**

- Pulse-wall dashboard with per-monitor heartbeat bars, status pills, and ⌘K command palette for jump-to-monitor / jump-to-page.
- Live updates via REST polling — no WebSocket, no long-poll, no service worker.
- Multi-language UI.
- Public status page in the same dark v2 aesthetic.

## Architecture

```
┌──────────────────────┐        ┌──────────────────────┐
│  Vue 3 frontend      │  REST  │  FastAPI backend     │
│  (Vite, Pinia-free,  │ ─────► │  (Uvicorn, async     │
│   scoped SCSS)       │        │   SQLAlchemy)        │
└──────────────────────┘        └──────────┬───────────┘
                                           │
                                           ▼
                                ┌──────────────────────┐
                                │  SQLite or Postgres  │
                                └──────────────────────┘
```

- **Backend** — `server/` is a FastAPI app. The runner is a `@repeat_every` task that fans monitor probes out via `asyncio.gather`, persists heartbeats, and dispatches notifications via fire-and-forget tasks so a slow webhook can't delay the next tick. SQLAlchemy 2.0 async ORM, SQLite by default (`aiosqlite`), Postgres supported via `asyncpg`.
- **Frontend** — `src/` is a Vue 3 SPA built with Vite. v2 pages live under `src/pages/v2/`. Scoped SCSS, no runtime template compiler.
- **Notification providers** — `server/notification_providers/<name>.py`. Each is a small `NotificationProvider` subclass that builds its native payload from the structured primitives `build_status_message` returns. Dropping in a new provider is a one-file change plus a frontend catalog entry in `src/pages/v2/MonitorFields.vue`.

## Development

Prereqs: Node 20+, Python 3.9+, npm.

```bash
# Install JS deps
npm install

# Set up the Python venv and install backend deps
python3 -m venv server/venv
source server/venv/bin/activate    # Windows: server\venv\Scripts\activate
pip install -r server/requirements.txt

# Run frontend (Vite, port 3000) and backend (FastAPI, port 3001) together
npm run dev
```

Then open `http://localhost:3000`.

`npm run dev` starts Vite first, then FastAPI; the Vite config proxies `/api` to the backend so you get HMR on the Vue side and a live-reloading Python server without juggling tabs. The dev script invokes `python3` from your `PATH`, so make sure the venv is activated in the same shell — otherwise the backend won't find its dependencies.

### Common scripts

| Command                | What it does                                            |
| ---------------------- | ------------------------------------------------------- |
| `npm run dev`          | Run frontend + backend together with HMR                |
| `npm run build`        | Production build of the frontend into `dist/`          |
| `npm run lint`         | ESLint + Stylelint                                      |
| `npm run lint-fix:js`  | Auto-fix JS/Vue lint                                    |
| `npm run test-e2e`     | Playwright end-to-end tests                             |
| `npm run start-server` | Run only the FastAPI backend (after a frontend build)   |

Backend-only test suite:

```bash
server/venv/bin/python -m pytest server/tests/
```

### Configuration

Behavior is driven by env vars; sensible defaults make most of these optional.

> **Set `JWT_SECRET` in any production deploy.** Without it, each process generates a new random secret on startup and every restart silently invalidates all logged-in sessions. The symptom is "I logged in, clicked something, and got bounced to /login." Generate once with `openssl rand -base64 48` and persist it (env var, systemd `EnvironmentFile`, Docker `.env`, etc.).

> **Run a single worker.** The login rate limiter, monitor scheduler, and JWT-secret fallback all live in-process. Multi-worker setups (`uvicorn --workers N`, `gunicorn -w N`) double-poll every monitor, double-bill the targets, and break session continuity. Stick to one uvicorn process per host.

| Var                                | Default                                | Purpose                                              |
| ---------------------------------- | -------------------------------------- | ---------------------------------------------------- |
| `DATABASE_URL`                     | `sqlite+aiosqlite:///./data/observer.db` | SQLAlchemy async URL (see below)                   |
| `JWT_SECRET`                       | random per-process                     | Session signing key — **set explicitly in production** to keep sessions across restarts |
| `PORT`                             | `3001`                                 | FastAPI listen port                                  |
| `RUNNER_TICK_SECONDS`              | `5`                                    | Probe scheduler tick                                 |
| `HEARTBEAT_PRUNE_INTERVAL_SECONDS` | `3600`                                 | How often the retention pruner runs                  |
| `APPLY_DEFAULT_INTERVAL_ON_STARTUP`| `false`                                | One-shot legacy upgrade for monitors with bad intervals |

The `keepDataPeriodDays` retention setting (and most other UI settings) live in the database, configurable from `/settings`.

### Database engines

Observer runs against SQLite, Postgres, or MySQL/MariaDB. Pick one by setting `DATABASE_URL`:

```bash
# SQLite — default, single file on disk, zero setup
DATABASE_URL=sqlite+aiosqlite:///./data/observer.db

# Postgres
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/observer

# MySQL / MariaDB
DATABASE_URL=mysql+asyncmy://user:pass@host:3306/observer
```

For Docker compose, override the default in `compose.yaml` or via an `.env` file:

```yaml
services:
  backend:
    environment:
      - DATABASE_URL=postgresql+asyncpg://observer:secret@db:5432/observer
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: observer
      POSTGRES_USER: observer
      POSTGRES_PASSWORD: secret
    volumes:
      - postgres-data:/var/lib/postgresql/data
volumes:
  postgres-data:
```

For SQLite users on existing databases that came from the original Uptime Kuma layout, the legacy table-rename + column-add migration runs automatically on first start. Postgres and MySQL deployments are new with the Python rewrite and start from a clean schema.

## API

A live OpenAPI spec is generated by FastAPI at runtime — visit `http://<host>:3001/docs` for the Swagger UI or `http://<host>:3001/redoc` for the ReDoc view.

### Authenticating

Every `/api/*` endpoint accepts either:

- a Bearer JWT in the `Authorization` header (what the UI uses, returned by `POST /api/login`), or
- an `X-API-Key` header for headless / scripted access.

Mint API keys under **Settings → API Keys**. Three roles:

| Role        | Can call                |
| ----------- | ----------------------- |
| `read`      | `GET` / `HEAD` only     |
| `write`     | All other methods       |
| `readwrite` | Everything              |

The plaintext key is shown once at creation time. Store it then — the database only keeps a SHA-256 hash.

### Bulk-creating monitors

`POST /api/monitors` defaults nearly every field, so a minimal HTTP monitor body is short. For example, the wishlist of *name, URL, interval, description, accepted status codes, certificate expiry alert*:

```bash
curl -X POST https://observer.example.com/api/monitors \
  -H "X-API-Key: $OBSERVER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "http",
    "name": "Cloudflare",
    "url": "https://cloudflare.com",
    "interval": 60,
    "description": "Edge network",
    "accepted_statuscodes": ["200-299"],
    "expiryNotification": true,
    "certExpiryThresholdDays": 14
  }'
```

A few things worth knowing for scripts:

- Both `snake_case` and `camelCase` keys are accepted on input — pick one and stay consistent (responses use `camelCase` for fields with an alias and `snake_case` for the rest).
- `name` must be unique. Duplicates return `400 monitorNameTaken`.
- The endpoint kicks off an immediate first probe, so a real heartbeat lands in the UI within seconds rather than after the first interval.
- The full schema (every settable field with its default) lives in `MonitorSchema` in `server/routers/api.py` — also viewable interactively at `/docs`.

## Contributing

Issues and pull requests are welcome. The details — branch naming, commit style, code conventions, and the project's stance on AI-assisted contributions — live in [CONTRIBUTING.md](./CONTRIBUTING.md). If you're an AI coding agent (Claude Code, Cursor, Codex, etc.) working in a clone, also read [AGENTS.md](./AGENTS.md) for the operational rules. Security disclosures go through [SECURITY.md](./SECURITY.md).

## License

MIT — see [LICENSE](./LICENSE). Original Uptime Kuma codebase © 2021 Louis Lam; subsequent rewrite and additions © 2025-2026 Saba Sakvarelidze.
