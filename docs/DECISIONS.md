# Architecture Decisions

## ADR-001 — Play-first affiliate attribution

**Status:** accepted for feature-gated implementation, not enabled in production.

**Decision:** Affiliate links lead exclusively to the fixed official Google Play
listing. Google Play Billing remains the payment channel for the Play flavour. The
DownloadThat backend attributes a valid first install and creates a commission only
after server-side purchase verification; Stripe remains disabled and Direct APK is
out of the MVP.

**Why:** This preserves the current distribution strategy, avoids two competing
payment/attribution systems, uses existing D1/Pages Functions and makes Play's
verified purchase state the financial authority.

**Alternatives rejected for MVP:** Stripe affiliate checkout (disabled), Direct APK
commissioning (secondary channel), third-party affiliate SaaS (unnecessary new
processor/data transfer), promo-only attribution (weak evidence), and microservices/
second database (unjustified operational complexity).

**Consequences:** Attribution is probabilistic acquisition evidence, never proof of
identity; commissions have a 30-day hold and need RTDN plus voided reconciliation.
Existing Billing and entitlement paths must remain independent and feature flags
default off. Legal/payout/tax decisions remain owner responsibilities.
