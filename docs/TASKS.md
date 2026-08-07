# Affiliate Tasks

## Phase 0 — complete

- [x] Map active Billing, entitlement, RTDN, refund, D1 and deployment paths.
- [x] Separate historical Stripe/affiliate artefacts from active code.
- [x] Verify current official Install Referrer, Play Developer API, RTDN, voided
  purchases, Pub/Sub push and WIF documentation.
- [x] Produce architecture, privacy, operations, marketing and setup plan.

## Before code

- [ ] Benjamin: approve 30-day hold, 30-day click-to-install and 60-day
  install-to-purchase windows, and initial commission policy.
- [ ] Benjamin: complete existing real Play lifecycle production gates.
- [ ] Benjamin: approve privacy/legal/affiliate agreement and pilot partners.
- [ ] Codex: implement only after the above decisions are recorded.

## Implementation checklist

- [ ] Add additive affiliate D1 migration with constraints/indexes.
- [ ] Add disabled feature flags and config validation.
- [ ] Implement fixed Play `/r/:affiliateCode/:campaignSlug?` redirect.
- [ ] Add signed click payload and click-rate limit.
- [ ] Add Play-only `InstallReferrerRepository` and first-run persistence.
- [ ] Add attribution API and immutable install-attribution persistence.
- [ ] Bind server-verified Play purchase to attribution idempotently.
- [ ] Implement commission state machine and 30-day release job.
- [ ] Add RTDN inbox/message-ID dedupe.
- [ ] Add voided-purchases cursor reconciliation and clawback handling.
- [ ] Add fraud-hold rules and audit events.
- [ ] Add admin MVP and aggregate-only affiliate dashboard.
- [ ] Add unit, integration, Android contract and privacy/BOLA tests.
- [ ] Add dry-run setup, access audit and narrow teardown scripts.
- [ ] Run staging migration, Internal Track referrer test and 3–5 partner pilot.
