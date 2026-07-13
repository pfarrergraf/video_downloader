# DownloadThat security program

Date opened: 2026-07-03
Branch of record: `claude/gothic-downloader-website-bp7r2u`
Status: open working area for Claude/Copilot/humans

## Purpose

This directory is the working area for making DownloadThat reviewable, trustworthy, and eventually due-diligence-ready.

The immediate aim is not to claim certification. The aim is to create evidence that the product is designed, built, released, and operated responsibly.

## Product reality to hold in tension

The informal product promise is: users can download all kinds of media from links they provide.

That is the product intuition and may guide UX, demo flow, and internal product thinking. It must not become a reckless public legal claim. Public copy should frame DownloadThat as a private media utility for user-owned, authorized, or otherwise lawful content.

Internal shorthand:

> DownloadThat helps people download all kinds of media from their own links.

Safer external framing:

> DownloadThat is a private Android media utility for downloading video, audio, and images from links you provide, where you have the right to do so.

## Security workstreams

1. Mobile app security
   - Android permission review
   - release signing continuity
   - no secrets in APK
   - local processing claims checked against code
   - Play Protect warning mitigation without bypass behavior

2. Web/API security
   - Cloudflare Pages Functions
   - Stripe webhook validation
   - D1 license database access
   - refund endpoint abuse resistance
   - rate limiting for public endpoints

3. Data protection
   - data inventory
   - data flow diagrams
   - deletion process
   - subprocessors and vendors
   - privacy policy alignment

4. Release integrity
   - signed release builds only
   - SHA-256 checksums
   - versioned release assets
   - App Bundle path for Play Console

5. Incident readiness
   - who notices problems
   - how releases are paused
   - how licenses/payment issues are handled
   - what gets communicated to testers/customers

## Initial file map

- `risk-register.md` — open product, legal, security, privacy, and distribution risks.
- `data-flow.md` — what data moves through app, Cloudflare, Stripe, GitHub, support.
- `vendor-register.md` — Cloudflare, Stripe, GitHub, Google Play, etc.
- `mobile-security-checklist.md` — Android/MASVS-inspired checklist.
- `web-api-security-checklist.md` — Cloudflare/API/Stripe checklist.
- `incident-response-plan.md` — first response plan for beta period.

## Core-app & certification audit (2026-07-13)

The evidence set was extended beyond the affiliate/web backend to cover the
downloader core, the on-device web server, and the Android app, and a staged
certification roadmap was added. New artifacts live in the top-level `security/`
directory:

- `RED_TEAM_REPORT_CORE_APP.md` — adversarial (CCC-style) assessment with
  reproducible PoCs (`scripts/redteam_poc.py`). Confirmed & fixed: SSRF on
  `/api/scrape`, world-readable local secrets, password-in-URL auto-login,
  missing security headers. Debunked: external license-key forgery, Stripe
  webhook forgery, path traversal, login brute-force.
- `CERTIFICATION_LADDER.md` — L0 (self-assessment/transparency) → L1 (CI security
  automation) → L2 (independent pentest) → L3 (formal seals: CRA, Play Data-Safety;
  ISO 27001 / SOC 2 marked "prepared, not pursued"), with gates and a
  proportionality call for a low-cost solo product.
- `MASVS_MATRIX.md`, `ASVS_CORE_APP_ADDENDUM.md`, `CRA_GAP_ANALYSIS.md` — standard
  mappings for the app/on-device server (certifier perspective, Rolle B).
- `/SECURITY.md` + `pro/website/.well-known/security.txt` — coordinated disclosure.

CI now runs SAST (bandit), a broken-code gate (ruff), the full test suite, CodeQL,
and secret scanning — see `.github/workflows/security-scan.yml`, `codeql.yml`, and
`.github/dependabot.yml`.

## Working rule

Do not add dangerous Android permissions, weaken signing, expose secrets, or make stronger privacy claims than the code supports without updating this directory and documenting the reason.
