# Affiliate Current State — Phase 0 Forensics

Stand: 2026-08-07. Scope: read-only repository analysis; no production setting,
database, Play Console resource, secret, billing path, or redirect was changed.

## Executive summary

1. The current sale path is Play-first: Android `play` uses Billing 9.1.0;
   `direct` deliberately contains no Billing client.
2. `pro` is a non-consumable one-time product. The Android app verifies a purchase
   token at `POST /api/play/purchases/verify`; the Pages Function is authoritative.
3. Cloudflare Pages Functions plus the existing D1 database are the smallest
   suitable stack for a future affiliate MVP. No second database or microservice
   is justified.
4. `play_purchases` already makes token processing idempotent (`token_hash` primary
   key) and stores the raw token encrypted, not in plaintext.
5. RTDN reception and a daily reconciliation workflow exist in source, but the
   owner checklist records their production setup and real-device verification as
   open gates.
6. A previous Stripe/affiliate programme was intentionally removed. Its old docs
   and security reports are historical evidence, not an implementation to revive.
7. There is currently no Install Referrer dependency/code, `/r/:code` endpoint,
   affiliate schema, commission engine, dashboard, or affiliate feature flag.
8. Current redirects are canonical-host redirects only; there is no affiliate
   redirect handler.
9. The current Worker uses a service-account private key secret for live Play API
   calls when configured. It is not a keyless runtime design.
10. Current public pages contain no active affiliate/Stripe checkout route; deploy
    checks deliberately assert old partner and checkout endpoints return `404`.
11. There is no Firebase, Google Analytics, Durable Object, KV, R2, or user account
    system in the current active stack. Do not add one for the MVP.
12. Production activation is **NO-GO** until the existing real Play purchase,
    restore, RTDN, reconciliation, refund/void, domain, and Data Safety gates pass.

## A. Already present

| Area | Evidence | Reusable capability |
|---|---|---|
| Android flavours | `android/app/build.gradle`; `play`/`direct` source sets | Keep affiliate attribution Play-only; direct builds must not create commissions. |
| Play Billing | `android/app/src/play/.../PurchaseControllerFactory.kt` | Existing `pro` query, offer token selection, purchase/restore/pending handling and obfuscated account ID. |
| Install identity | `InstallIdentity.kt` | A reset-on-uninstall UUID; suitable as the client-side `install_id` after server-side hashing. |
| Server verification | `EntitlementApi.kt`, `functions/_google_play.js` | Server verifies package, product and token before granting entitlement. |
| D1 purchase record | migrations `0010`–`0013` | `token_hash` is an idempotency key; order ID, completion time and device hash can join a later commission record. |
| RTDN endpoint | `functions/api/play/rtdn.js` | OIDC JWT validation, package/product checks and fail-closed HTTP failure for redelivery. |
| Reconciliation | `functions/_google_play.js`, workflow `google-play-reconciliation.yml` | Daily token re-check exists; extend with an independent voided-purchases cursor. |
| Refund handling | `_play_refunds.js`, `0013_google_play_refunds.sql` | Manual/controlled refund path and revoke semantics already exist. |
| Pages/D1 deployment | `pro/website/wrangler.toml`, deploy workflow | One Cloudflare Pages project and D1 binding already exist. |
| Security controls | `_middleware.js`, `security/CURRENT_SECURITY_IMPLEMENTATION_STATUS.md` | HSTS, referrer policy, token hashing/encryption and source-level tests. |

> **Snapshot note:** Sections A–E record the pre-implementation Phase 0 snapshot.
> The feature branch now contains the disabled Phase 1–7 preparation described in
> the post-snapshot section below; the historical gap statements are intentionally
> retained as evidence of what was absent before implementation.

## B. Partly present and safe to extend

| Component | Current limit | Extension direction |
|---|---|---|
| `InstallIdentity` | Identifies an app install, but has no acquisition provenance. | Hash it with a new server-only pepper; never expose or reuse it as an affiliate code. |
| `play_purchases` | Links token to a license but not to acquisition. | Add nullable `install_attribution_id`; preserve existing rows and behaviour. |
| RTDN | It handles one-time notification processing, but does not persist Pub/Sub `messageId` or use voided-purchases polling. | Add a dedupe inbox/event table and a cursor-based voided-purchase reconciliation job. |
| D1 migrations | Additive, idempotent migrations exist. | Use a new numbered migration only; never modify applied migrations. |
| Pages Functions | Backend/API implementation pattern already exists. | Add a fixed-destination `/r/:affiliate/:campaign?` Function and authenticated admin APIs. |
| Deployment controls | `PLAY_BACKEND_CONFIGURED` protects existing backend setup. | Use independent affiliate flags, defaulting to `false`; never couple them to billing enablement. |

## C. Not present

- Referral click creation, code/campaign validation and a server-fixed Play redirect.
- Play Install Referrer library, one-time repository, retry state and attribution API.
- Affiliate, campaign, click, attribution, event, purchase-attribution and commission tables.
- Immutable event/audit trail for affiliate decisions, Pub/Sub message dedupe, and
  voided-purchases cursor/snapshot.
- Commission state machine, safety-period job, refund/chargeback clawback and
  manual payout ledger.
- Affiliate authentication, dashboard, admin UI and partner onboarding.
- Rate limits/fraud review controls specifically for affiliate acquisition.
- Google Cloud setup/audit/revoke scripts for this current Play-first design.

## D. Technical debt and prerequisites

1. `schema.sql` still documents old Stripe-era columns in `licenses`; do not use
   email or any Stripe identifier for affiliate attribution. Remove/retire them
   only under the existing decommission procedure, never in this feature.
2. The running Worker credential model is a long-lived service-account private key.
   It is stored as a Cloudflare secret when enabled, but an owner-approved keyless
   runtime alternative has not been established.
3. RTDN source processes changes but does not persist a Pub/Sub message-ID inbox;
   duplicate verification is mostly harmless due to token idempotency, yet explicit
   event dedupe is required before it can drive money states.
4. Current reconciliation rechecks known tokens. It does not yet call
   `purchases.voidedpurchases.list`, which is necessary as an independent refund /
   chargeback safety net.
5. `POST /api/play/purchases/verify` is not yet shown as rate-limited in the
   checked-in Pages Function configuration; the owner checklist names this open
   production gate.
6. Existing real Play lifecycle tests are open. No affiliate code may be activated
   before the underlying purchase/void lifecycle has real evidence.

## E. Risk register

| Risk | Why it matters | Required control |
|---|---|---|
| False attribution | Referrer data is an acquisition signal, not proof of a human click. | Signed opaque payload, timestamp consistency, one-time install claim, bounded window and fraud holds. |
| Duplicate events | Pub/Sub is at-least-once; clients retry. | Unique constraints, inbox/event ID and deterministic state transitions. |
| Premature payment | Refunds/chargebacks can arrive after a purchase. | 30-day initial hold; RTDN plus voided-purchases reconciliation before payable. |
| Credential exposure | Play API can verify/refund orders. | Least Play permissions; Cloudflare secrets only; short-lived WIF for CI/setup; no secrets in app. |
| Privacy over-collection | IP/UA, device and order data can be personal data. | No raw IP/UA/advertising ID/Google account; hashes only where needed; deletion schedule. |
| Production regression | Billing release is currently in progress. | Feature flags default false; no current Billing or entitlement logic change in Phase 0–1. |

## Forensic search result

Searched active code, workflows, tests, docs and security material for `affiliate`,
`referral`, `referrer`, `install_referrer`, `partner`, `campaign`, `stripe`,
`billing`, `purchaseToken`, `orderId`, `RTDN`, `PubSub`, `androidpublisher`,
`voided`, `refund`, `commission` and `attribution`.

Historical hits refer to removed functions/migrations and are labelled historical in
current security documentation. Active hits are limited to the Play billing,
verification, RTDN, reconciliation and refund components named above.

## F. Post-Phase-0 implementation status

The current branch adds, behind independently evaluated flags and the deployment
gate `AFFILIATE_PRODUCTION_APPROVED`, the following safe preparation:

- D1 migrations `0014_affiliate_attribution.sql` and `0015_affiliate_dashboard_access.sql` with affiliate/campaign/click,
  immutable install, purchase, commission, inbox, audit and cursor tables.
- Fixed Play redirect routes, signed `dt_v1` claims, per-affiliate hourly rate
  limiting and privacy-minimal rejection auditing.
- Play-flavour-only Install Referrer repository with bounded retry states and
  `/api/affiliate/attributions`.
- Server-verified purchase binding, 30-day hold/release, RTDN and voided-purchase
  reconciliation, clawback/fraud-hold controls and manual payout recording.
- Authenticated aggregate-only admin and partner dashboards with hashed scoped
  access tokens, retention dry-run/cleanup and a reproducible unit-economics
  calculator.

These changes are locally tested but not deployed or enabled. The Internal Track
referrer test, real Play purchase/refund/RTDN evidence, legal/privacy/BOLA review,
maker/checker approval and the 3–5 partner pilot remain external owner gates.
