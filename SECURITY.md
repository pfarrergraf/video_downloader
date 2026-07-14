# Security Policy

DownloadThat / ClassyDL takes security seriously. This document describes how to
report vulnerabilities and what is in scope.

## Reporting a vulnerability

Please report security issues privately by email to **gpt.assist.benjamin@gmail.com**
with the subject prefix `[SECURITY]`. Do not open a public GitHub issue for an
undisclosed vulnerability.

Include, where possible:

- affected component (desktop/web UI, Android app, licensing/payment backend),
- version / commit,
- a description and reproduction steps or a proof-of-concept,
- the impact you believe it has.

We follow **coordinated disclosure**: we will acknowledge your report, work on a
fix, and credit you (if you wish) once a fix is released. Please give us reasonable
time to remediate before any public disclosure.

## Scope

In scope:

- The Python core and the standard-library web server (`video_downloader/`).
- The Android app (`android/`, package `de.classydl.app`).
- The Cloudflare-hosted Google-Play entitlement and licensing backend (`pro/website/`).

Out of scope / known and accepted:

- **Local Pro-tier bypass on a device you control.** Pro entitlement is enforced by
  a server running on the user's own device, so a technically capable owner can
  bypass it locally. This is a deliberate trade-off for a low-cost one-time-purchase
  app, not a vulnerability. See `security/RESIDUAL_RISK_ACCEPTANCE.md`.
- Denial of service from a client that already holds a valid session on its own
  loopback server.
- Findings that require a rooted/compromised device or physical access.

## Security posture

The project maintains an internal security program under `security/`, including a
threat model, ASVS/MASVS self-assessments, a red-team report, a penetration-test
plan, and an incident-response plan. Automated checks (SAST, dependency updates,
code scanning, secret scanning, the full test suite) run in CI — see
`.github/workflows/security-scan.yml` and `.github/workflows/codeql.yml`.

The current commerce security design is documented in
`security/GOOGLE_PLAY_SECURITY_ARCHITECTURE.md`. Older Stripe and affiliate
assessment files are retained as historical evidence and are not a description
of the active production architecture.
