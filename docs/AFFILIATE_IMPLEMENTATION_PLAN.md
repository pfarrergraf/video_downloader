# Affiliate Implementation Plan

## Go / no-go

**Go now:** Phase 0 documentation, isolated tests, schema/endpoint implementation
behind disabled flags, and dry-run Google setup scripts.

**No-go until after Play production evidence:** enable redirects, attribution,
commissions, affiliate registration, or payouts. The existing owner checklist still
requires real Play purchase, restore, void/refund, RTDN and reconciliation evidence.

## Phases

| Phase | Scope | Release condition |
|---|---|---|
| 0 | This forensic record, ADR, privacy/operations plan and tests design. | Complete; no production activation. |
| 1 | Add additive D1 migration, disabled flags, affiliate/campaign CRUD only for admin seeding, and `/r` redirect. | Implemented and locally tested; flags remain false. |
| 2 | Play-only `InstallReferrerRepository` plus attribution endpoint. | Implemented behind client/server flags; real Internal Track test remains open. |
| 3 | Bind an already server-verified `play_purchases` record to immutable attribution; create pending commission. | Implemented and locally tested; existing Play lifecycle evidence remains required. |
| 4 | Inbox dedupe, RTDN commission reaction, voided-purchases cursor reconciliation, hold-release worker. | Implemented and locally tested; manual real refund/void evidence remains open. |
| 5 | Minimal authenticated admin controls, manual payout recording and audit export. | Admin/payout API implemented; maker/checker and privacy review remain open. |
| 6 | Affiliate dashboard with aggregate-only views. | Implemented behind dashboard/admin flags; BOLA/privacy review remains open. |
| 7 | 3–5 partner pilot, all payouts manual. | Pilot runbook/checklist implemented; real partner pilot and 60-day evidence remain external. |
| 8 | Pilot evaluation and unit economics. | Aggregate report/calculator implemented; requires real pilot data. |
| 9 | Public self-service affiliate registration. | Explicitly deferred; onboarding remains admin-approved and manual. |

## Exact files to change

- `android/app/build.gradle` — Play-only Install Referrer dependency.
- `android/app/src/main/java/de/classydl/app/MainActivity.kt` — start repository
  without delaying existing Billing/UI.
- `android/app/src/main/java/de/classydl/app/InstallIdentity.kt` — only if a
  narrow helper is needed; preserve current migration behaviour.
- `pro/website/wrangler.toml` — only existing D1 binding; no new store.
- `pro/website/schema.sql` and a new D1 migration — additive affiliate schema.
- `pro/website/functions/_google_play.js` — narrow purchase-to-commission hook
  after verification; preserve current entitlement invariants.
- `pro/website/functions/api/play/rtdn.js` — inbox/dedupe and commission-event hook.
- `pro/website/functions/api/play/reconcile.js` — authenticated reconciliation
  trigger; add a separate bounded voided-purchases path.
- `.github/workflows/google-play-reconciliation.yml` — call only an idempotent,
  cursor-aware reconciliation endpoint; do not add broad schedule triggers.
- `.github/workflows/deploy-pro-website.yml` — deploy only existing secret
  infrastructure, with all affiliate flags false unless explicitly set.

## Exact files to create

- `android/app/src/play/java/de/classydl/app/InstallReferrerRepository.kt`
- `pro/website/migrations/0014_affiliate_attribution.sql`, `0015_affiliate_dashboard_access.sql`
- `pro/website/functions/_affiliate.js`, `_affiliate_retention.js`
- `pro/website/functions/_affiliate_commissions.js`
- `pro/website/functions/api/affiliate/attributions.js`
- `pro/website/functions/r/[affiliateCode].js` and
  `pro/website/functions/r/[affiliateCode]/[campaignSlug].js`
- `pro/website/functions/api/admin/affiliates.js`,
  `api/admin/affiliates/dashboard.js`, and `api/affiliate/dashboard.js`
- `pro/website/tests/affiliate_*.test.mjs`
- `tests/test_android_install_referrer_contract.py` (source/contract guard)
- `scripts/setup_google_affiliate.sh`, `scripts/audit_google_access.sh`, and
  optionally `scripts/revoke_setup_access.sh` only after owner-approved project IDs.

## Feature flags

All must default to the literal string `false` and be independently evaluated:

```text
AFFILIATE_ENABLED=false
AFFILIATE_REDIRECT_ENABLED=false
AFFILIATE_ATTRIBUTION_ENABLED=false
AFFILIATE_COMMISSION_ENABLED=false
AFFILIATE_DASHBOARD_ENABLED=false
AFFILIATE_ADMIN_ENABLED=false
AFFILIATE_PRODUCTION_APPROVED=false
```

`AFFILIATE_ENABLED` gates all public affiliate behaviour. Billing must not read any
affiliate flag to decide entitlement; an outage in affiliate code must never affect
a legitimate Play purchase.

Deployment additionally requires the non-runtime owner gate
`AFFILIATE_PRODUCTION_APPROVED=true` before `AFFILIATE_ENABLED=true` is accepted.

## Attribution rules

- Last valid server-created click wins only before the first successful attribution.
- Repeated clicks from the same affiliate can update the candidate click before
  install; they never extend expiry past 30 days.
- Existing install/app update/Google-account switch: no retroactive attribution.
- Reinstall: eligible only as a new install identity plus a referrer carrying a
  still-valid click; never overwrite a prior attributed install.
- Purchase up to 60 days after `attributed_at` is eligible; after that it remains a
  valid entitlement but creates no commission.
- Invalid, expired, tampered, duplicate or Direct-APK referrers create no record
  beyond a privacy-minimal rejected audit event.
- Self-referral, abnormal refund rate, reused click across installs and impossible
  timestamp order enter `fraud_hold`; no automatic rejection based solely on a
  device/hash signal.

## Test matrix

| Layer | Cases |
|---|---|
| Redirect | active/disabled/unknown code, campaign ownership, no `next` parameter, cache headers, signed payload, click id uniqueness. |
| Android | OK, no referrer, malformed payload, feature unsupported, unavailable, disconnect, offline first start, process restart, exactly-once state. |
| Attribution API | MAC/expiry/timestamp checks, duplicate click, `UNIQUE(install_id_hash)`, retry after 5xx, no raw referrer logs. |
| Purchase | purchased/pending/cancelled, forged/wrong product token, duplicate verify, token/order uniqueness, purchase before attribution. |
| RTDN/reconciliation | duplicate message ID, late RTDN, missing RTDN recovered by voided API, cursor continuation, 429/5xx retry without revocation. |
| Commission | hold release, refund before/after release, void, chargeback, fraud hold/clear/reject, manual payout idempotency. |
| Privacy/auth | affiliate cannot query another affiliate or buyer/order/token/device data; deletion/retention job behaves predictably. |

## Failure handling

`SERVICE_UNAVAILABLE`, backend 5xx, D1 temporary failure and Google quota errors
are retryable and must not create a commission or revoke entitlement. A known,
verified void is final for commission purposes. Return non-2xx for a failed Pub/Sub
delivery so it retries; acknowledge duplicates safely after an inbox lookup.
