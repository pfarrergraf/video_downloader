# Affiliate Operations Runbook

## Operating invariants

- Existing Google Play entitlement remains authoritative and independent of affiliate
  availability. Attribution failure never changes a customer's entitlement.
- A Play purchase token/order produces at most one affiliate purchase and one
  commission. All retries use an idempotency key.
- No payout is automatic. `paid` requires an authenticated admin action and external
  payment reference after the hold/reconciliation gate.
- RTDN is fast notification; the Google Play Developer API is state authority;
  voided-purchases polling is the missing-event safety net.

## Observability and alerting

Emit redacted structured events with correlation IDs: `affiliate.click.created`,
`affiliate.install.attributed`, `affiliate.purchase.attributed`,
`affiliate.commission.created`, `affiliate.commission.payable`,
`affiliate.purchase.voided`, `affiliate.commission.voided`, and
`affiliate.fraud.flagged`.

Alert an operator for: repeated D1/Google 5xx, RTDN delivery failure, reconciliation
cursor stall, duplicate-event surge, commission transition conflict, reconciliation
drift, or a payable payout blocked by fraud/void. Do not send raw token, referrer,
buyer, or order data to logs/alerts.

## Reconciliation

Run daily and on demand, with a locked cursor/checkpoint:

1. Process inbox events in a transaction/idempotent claim.
2. Refresh only affected known purchases from `productsv2`.
3. Page through `voidedpurchases.list` using its continuation token, record each
   source event, match token hash/order ID, revoke entitlement/commission as needed.
4. Advance cursor only after the page is committed. Retry 429/5xx with bounded
   backoff; do not infer a void from transport failure.
5. Release pending commissions only after a clean pass and `available_at`.

## MVP fraud controls

- Per-code redirect rate limit and short-lived signed payload.
- Unique click/install/purchase/event constraints; no affiliate-selected purchase
  binding.
- Review holds for anomalous volume, repeat click claims, impossible timestamps,
  affiliate self-purchase indicators, high void/refund ratio or automation signals.
- Do not use Play Integrity in MVP. Re-evaluate only with measured abuse and a
  documented privacy/operational benefit.

## Incident response

| Incident | Immediate action |
|---|---|
| credential suspicion | set all affiliate flags false; rotate affected runtime secret; audit Play/Cloud IAM; preserve redacted evidence. |
| incorrect attribution | disable redirect/attribution flags, freeze pending/payable commissions, correct via compensating audit event. |
| duplicate RTDN | preserve inbox record and safely return success after no-op verification. |
| missed RTDN | run cursor-based voided reconciliation; do not manually grant payout. |
| D1/Google outage | retain retryable state; no expiry/void assumption; pause payable release. |
| suspected fraud | set `fraud_hold`; investigate with minimized data; never expose purchaser data to affiliate. |

## Dashboard boundary

The current Phase 6 dashboard is an authenticated JSON endpoint rather than a
hosted public HTML login. This avoids inventing an account system before legal and
identity requirements are approved. The affiliate dashboard exposes own
code/links, clicks, attributed installs, verified purchases,
pending/payable/paid/voided aggregate amounts and date range. Admin dashboard adds
status, commission policy, campaign management, fraud flags, payout references and
audit trail. Neither receives raw purchase tokens or buyer details.

Partner access tokens are created/revoked by the authenticated admin endpoint and
returned only once. Rotate/revoke them after a suspected disclosure; never paste
them into tickets, screenshots or repository files.
