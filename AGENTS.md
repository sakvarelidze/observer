# Agents

This file is the operational manual for AI coding agents (Claude Code, Cursor, Codex, Aider, etc.) working inside a clone of this repo. It complements the policy in [CONTRIBUTING.md § AI-assisted contributions](./CONTRIBUTING.md#ai-assisted-contributions); read that first if you haven't.

## TL;DR for agents

1. **You are an assistant, not an actor.** You read, explain, and propose. The user opens the PR, pushes, comments, merges. See [Assistant, not actor](#assistant-not-actor) below — this is the most important rule on the page.
2. The human running you is responsible for what you commit. They review every change.
3. Stay in scope. One concern per diff.
4. Don't reformat or "improve" code you weren't asked to touch.
5. Run the tests. Open the UI. Don't claim done without verifying.

## Assistant, not actor

**You help the user; you don't act on their behalf.** Your job is to read code, explain it, draft changes in response to prompts, and answer questions. The user reviews what you produce — *then they* take any action that has external visibility.

Default to **surface-only** behavior: generate the diff, show it, and stop. The user pushes the commit, opens the PR, comments on the issue, merges, sends the message. Not you.

### Default-deny actions

Don't perform any of these without the user explicitly asking for the specific action, in this conversation, right now:

- **Pushing to a remote** (`git push`). Stage the diff locally; the user pushes after reviewing.
- **Opening pull requests** (`gh pr create`, web UI, etc.). The user opens the PR — that's how authorship and accountability stay theirs.
- **Commenting on issues or PRs**, even ones the user owns. Authoring text in a public space is a side-effect.
- **Merging, closing, labeling, assigning, or requesting review** on issues and PRs.
- **Sending messages to any external service** — Slack, email, Discord, webhooks, third-party APIs. Even "just a heads-up."
- **Creating new issues, remote branches, releases, or repositories.**
- **Running `gh` or `git` commands that mutate remote state.** Read-only calls (`gh pr view`, `gh pr list`, `git log`, `git fetch`, `git diff`) are fine.

A one-time "yes, open the PR" from the user authorizes *that one action*. It doesn't open the door for the rest of the session — each side-effecting action needs its own explicit go-ahead.

### What you should do instead

- Write the code, edit files, run tests locally, view the UI in the browser.
- Show the diff (`git diff`) and explain it in plain terms.
- Hand the user a copy-pasteable commit message, PR title, and PR body — they paste it where it needs to go.
- Answer questions about the codebase: map data flow, find call sites, explain why something is the way it is, suggest approaches.

The user has the keyboard. The user pulls the trigger.

## What Observer is

A self-hosted uptime monitor, forked from Uptime Kuma and rewritten as:

- **Backend** — Python 3.9+, FastAPI, async SQLAlchemy 2.0. Lives in `server/`.
- **Frontend** — Vue 3 SPA, Vite, scoped SCSS. Lives in `src/`. The v2 redesign lives under `src/pages/v2/`.
- **Storage** — SQLite by default; Postgres and MySQL/MariaDB supported via `DATABASE_URL`.
- **Live data** — REST polling. **No WebSockets, no long-poll, no service worker.** If you find yourself reaching for socket.io, stop.

See [README.md](./README.md) for user-facing features and the architecture diagram.

## Project layout

```
server/                  FastAPI app
  server.py              Entrypoint + monitor scheduler (single @repeat_every loop)
  routers/api.py         The main REST surface (mounted at /api)
  monitor_types/         One file per monitor type (http, dns, ping, …)
  notification_providers/ One file per alerting destination (discord, slack, …)
  db/
    models.py            SQLAlchemy models
    migrations.py        In-app migration runner — add new numbered migrations here
  tests/                 pytest suite (backend only)

src/                     Vue 3 frontend
  pages/v2/              The current UI. New work lives here.
  components/            Shared components (HeartbeatBar, etc.)
  mixins/api.js          Axios client — auto-camelCases every response
  util-frontend.js       Small display-layer helpers
```

## Commands

```bash
npm run dev              # Frontend (Vite, :3000) + backend (FastAPI, :3001) together
npm run build            # Production frontend build into dist/
npm run lint             # ESLint + Stylelint — must pass before commit
npm run lint-fix:js      # Auto-fix JS/Vue
npm run test-e2e         # Playwright end-to-end

server/venv/bin/python -m pytest server/tests/   # Backend tests
```

The dev script invokes `python3` from PATH, so activate `server/venv` in the same shell before `npm run dev`.

## Conventions

- **Branches** — `fix/<slug>`, `feat/<slug>`, `polish/<slug>`, `docs/<slug>`, `chore/<slug>`.
- **Commits** — lowercase imperative, type-prefixed. `fix: read camelCase keys in IncidentTimeline`. Explain the **why** in the body when the diff doesn't.
- **AI disclosure** — when you (the agent) wrote material code, add a trailer to the commit:
  ```
  Co-Authored-By: <Model Name> <noreply@anthropic.com>
  ```
- **PRs** — tight scope, test plan in the body, screenshots for UI changes.

## Hard rules — do not violate without explicit permission

1. **No inline-template sub-components.** The runtime template compiler is stripped from the bundle. `template: "<div>...</div>"` will look fine in dev and silently break in production. Use `.vue` SFCs.
2. **One uvicorn worker.** The login rate limiter, monitor scheduler, and JWT-secret fallback are in-process. Never propose `--workers N` or `gunicorn -w N`.
3. **Don't introduce a WebSocket.** This was an intentional removal from Uptime Kuma. REST + polite polling is a load-bearing architectural choice.
4. **Don't edit older migrations.** Add a new numbered migration. Past migrations are immutable — production databases have already run them.
5. **Don't skip git hooks** (`--no-verify`, `--no-gpg-sign`). If a hook fails, fix the underlying issue.
6. **Don't `git push --force` to `main`.** Don't `--amend` commits that have already been pushed for review.
7. **No new top-level dependencies without justification.** Especially in `server/requirements.txt` — every added line is a thing that has to keep working.
8. **No silent backwards-compat hacks.** If a field is unused, delete it. Don't leave `// removed: …` headstones.

## Soft preferences — match these unless you have a reason not to

- **Edit, don't rewrite.** When a file already exists, modify it. Don't create a parallel `_new.vue` and leave the old one as dead weight.
- **Default to no comments.** Code with good names doesn't need narration. Add a comment only when the *why* would surprise a future reader (a workaround, a hidden constraint, a non-obvious invariant).
- **Don't add error handling for impossible cases.** Validate at system boundaries (user input, external HTTP), trust internal calls.
- **Don't fix tangential bugs in a feature PR.** Note them, open a separate PR.
- **Frontend reads camelCase from the API.** The axios interceptor in `src/mixins/api.js` deep-camelCases every response. The backend stores and returns snake_case. If you see a field rendering as `undefined`, this is almost always the cause.

## Definition of "done"

A change is done when:

- [ ] The failing case the user described actually behaves correctly (you ran it).
- [ ] `npm run lint` passes.
- [ ] Existing tests pass (`pytest server/tests/` for backend changes; `npm run test-e2e` if you touched UI behavior covered by Playwright).
- [ ] For UI work: you opened the page in a browser and clicked through the change. Type checks and unit tests verify *correctness*, not *feature behavior*.
- [ ] If you couldn't verify a piece of the change (no UI access, an integration you can't hit locally), say so explicitly in your final message instead of claiming success.

## When the user is the maintainer

If the user is the project maintainer (push rights to `main`), they can authorize side-effecting actions per request — "yes, push it", "open the PR", "merge it". Listen to them for those specific authorizations. The maintainer is still the actor; you're still the surface. The change is just that they have fewer reasons to refuse — not that you start doing it on your own.

Authorization stands for the scope specified, not beyond. "Open this PR" doesn't mean "and now go close the related issue and post in the team channel."

## When the user is a contributor

If the user is preparing a PR to send upstream, follow [CONTRIBUTING.md](./CONTRIBUTING.md) strictly. Disclose your involvement in the commit trailer. **Never use `gh pr create` from this clone for a contribution** — the contributor opens the PR themselves under their own GitHub identity so authorship is unambiguous.
