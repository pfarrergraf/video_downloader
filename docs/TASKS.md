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
- [x] Codex: implement the safe, feature-flagged phases without enabling production behaviour.

## Implementation checklist

- [x] Add additive affiliate D1 migration with constraints/indexes.
- [x] Add disabled feature flags and config validation.
- [x] Implement fixed Play `/r/:affiliateCode/:campaignSlug?` redirect.
- [x] Add signed click payload and immutable-click protection.
- [x] Add Play-only `InstallReferrerRepository` and first-run persistence.
- [x] Add attribution API and immutable install-attribution persistence.
- [x] Bind server-verified Play purchase to attribution idempotently.
- [x] Implement commission state machine and 30-day release job.
- [x] Add RTDN inbox/message-ID dedupe.
- [x] Add voided-purchases cursor reconciliation and clawback handling.
- [x] Add audit events and conservative manual fraud-state foundation.
- [x] Add admin MVP and aggregate-only affiliate counters.
- [x] Add unit/integration and Android contract tests.
- [x] Add aggregate-only dashboard, rate-limit, rejection-audit and retention foundation.
- [x] Add scoped hashed partner dashboard access with BOLA regression coverage.
- [x] Add Phase 7 pilot runbook with stop criteria and redacted evidence rules.
- [x] Add reproducible affiliate funnel/unit-economics calculator without embedded price claims.
- [x] Add aggregate-only Phase 8 pilot evaluation report with stop thresholds.
- [x] Add dry-run setup, access audit and narrow teardown scripts.

## Remaining owner/external gates

- [ ] Approve windows, commission policy, privacy/legal copy and pilot partners.
- [ ] Run a signed Internal Track install-referrer test and real Play purchase/refund/RTDN lifecycle.
- [ ] Perform BOLA/privacy review and maker/checker payout review before enabling any flag.
- [ ] Run staging migration, Internal Track referrer test and 3–5 partner pilot.
