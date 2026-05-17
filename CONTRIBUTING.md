# Contributing to Observer

Thanks for the interest. Observer is a small, single-maintainer project — contributions are very welcome, but tightly scoped changes land much faster than sprawling ones.

## Before you start

For non-trivial work, open an issue first and describe what you want to build or fix. A two-line exchange saves both of us from a 600-line PR going the wrong direction. Tiny patches, doc fixes, and obvious bug fixes don't need an issue — just send them.

## Development setup

See the **Development** section of [README.md](./README.md#development) — it covers Node/Python versions, the venv, `npm run dev`, and how to run the test suite. Don't duplicate that here; if something's missing or wrong in those instructions, fix the README in your PR.

## Branches

Branch off `main`. Use the type-prefixed naming the repo already uses:

```
fix/<short-slug>      bug fix
feat/<short-slug>     new feature
polish/<short-slug>   small UI / UX refinements
docs/<short-slug>     docs only
chore/<short-slug>    tooling, deps, CI, build
```

Examples: `fix/incident-timeline-camelcase-keys`, `feat/humanize-status-messages`.

## Commits

Conventional-ish, lowercase, imperative. Match the existing log:

```
fix: read camelCase keys in IncidentTimeline
feat: humanize bare exception-class status messages
docs: refresh README — production deploy gotchas + automation API
polish: pin detail topbar actions to the right column
```

Body is optional but encouraged for anything non-obvious — explain the **why**, not the **what**. The diff already shows the what.

Don't use `--amend` or `git push --force` once a PR is open and being reviewed; create new commits instead. Squash on merge handles the final history.

## Pull requests

- **Keep PRs tight.** One concern per PR. If you noticed a tangential bug while in the area, open a separate PR for it. Bundled "while I was here" cleanups are the single most common reason PRs stall.
- **Write a test plan in the body.** A short checklist of what you actually clicked / curled / ran. Reviewers shouldn't have to guess how to verify your change.
- **CI must be green.** Lint and tests run on every PR. If a flake bites you, mention it in a comment — don't disable the check.
- **Screenshots for UI changes.** Before/after if you're modifying existing surfaces; one shot if it's net-new.
- **Out-of-scope notes.** If you considered something and intentionally didn't do it, say so in the PR body so I don't comment asking about it.

## Code style

- **Python**: stdlib-first, type hints where they aid clarity, async everywhere in the request path. Match the surrounding file's import order and naming. No formatter is enforced repo-wide, but don't reformat unrelated lines in a feature PR.
- **Vue / JS**: ESLint + Stylelint via `npm run lint`. Scoped SCSS for component styles. **The Vue runtime template compiler is stripped from the production bundle** — never define a sub-component inline with `template: "..."`. Use `.vue` SFCs.
- **SQL / migrations**: Observer ships with a small in-app migration runner (`server/db/migrations.py`). Add a numbered migration there, never edit an older one.
- **No new comments unless they explain a non-obvious why** — a comment that just narrates the next line is noise.

## Security

For vulnerability reports, follow [SECURITY.md](./SECURITY.md). Don't open public issues for security bugs.

## AI-assisted contributions

**You are welcome to use AI coding assistants** (Claude Code, Cursor, GitHub Copilot, Codex, Aider, etc.) to write or review your contributions. This project's maintainer uses them too — many of the commits in the log were AI-paired.

That said, the bar for what gets merged is the same whether a human or a model produced the diff, and **you, the contributor, take responsibility for the change**. A PR is your work to defend in review.

The rules:

1. **You must understand every line you submit.** If a reviewer asks "why did you do it this way?" and the honest answer is "the model wrote it," that PR isn't ready yet. Read the diff, run the code, and be able to talk through the trade-offs.
2. **Disclose AI assistance in the commit trailer**, the same way the existing log does it:
   ```
   Co-Authored-By: <Model Name> <noreply@anthropic.com>
   ```
   This isn't legalese — it's so future-you reading `git blame` knows what kind of pair the author had. Disclosure is required for material code generation; you don't need to disclose use of autocomplete or grammar-fixing.
3. **No agentic mass changes without prior agreement.** Don't open a PR that's the output of "fix every TODO in the repo" or "convert all components to Composition API." Those need an issue and a green light before the model is turned loose.
4. **Don't paste secrets, customer data, or unreleased private code into prompts.** Treat your AI prompts the same way you'd treat a public pastebin.
5. **Tests stay first-class.** AI is great at writing plausible-looking tests that don't actually exercise anything. Skim them. A test that always passes regardless of the code under test is worse than no test.
6. **CI is the floor, not the ceiling.** "All checks passed" is not the same as "this is correct." The reviewer (and you) are responsible for catching what CI misses.

For agents that operate *inside the repo* (Claude Code, Cursor agent mode, etc.), see [AGENTS.md](./AGENTS.md) for project-specific working instructions — build commands, gotchas, and what to leave alone.

## License

By submitting a contribution you agree that your code can be released under the project's MIT license (see [LICENSE](./LICENSE)).
