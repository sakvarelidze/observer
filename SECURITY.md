# Security Policy

## Reporting a vulnerability

**Do not open a public issue, post in discussions, or share details on social media until a fix has shipped.** Public disclosure ahead of a patch puts every Observer user at risk.

There are two private channels:

1. **Preferred — GitHub private security advisories.** Open one at
   <https://github.com/sakvarelidze/observer/security/advisories/new>. The form is only visible to the maintainer; you can attach proof-of-concept code, screenshots, and a proposed fix without exposing the report publicly.
2. **Email fallback** — `earthgxng@proton.me`. Use this if you don't have a GitHub account or the advisories form is unavailable. Please mark the subject line with `[SECURITY]` so it doesn't get lost.

## What to include

A useful report describes:

- The affected version — commit SHA, release tag, or "current `main`".
- The type of issue — auth bypass, SSRF, XSS, RCE, info disclosure, etc.
- A minimal reproduction — endpoint, request body, expected vs. actual behavior.
- The impact you observed and any prerequisites (auth, network position, specific config).

If you've already drafted a patch, link it (or attach a diff) — that speeds things up considerably.

## What to expect

- **Acknowledgement within 7 days** of receipt.
- A follow-up with the maintainer's read of the issue and a tentative fix timeline.
- Coordinated disclosure: a CVE (if appropriate), credit in the release notes (unless you ask to stay anonymous), and a public advisory once the fix is shipped.

## Out of scope

- Reports generated solely by automated scanners with no manual validation.
- Best-practice nags (missing `X-Frame-Options` on internal endpoints, etc.) without a concrete attack path.
- Third-party services and dependencies — please report those upstream and let us know if a coordinated update is needed.

## Third-party bug bounty platforms

At this time, the project does not participate in third-party bug bounty platforms (HackerOne, Bugcrowd, etc.). All reports go through the channels above.
