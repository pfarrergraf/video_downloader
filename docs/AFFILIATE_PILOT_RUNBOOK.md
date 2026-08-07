# Affiliate pilot runbook

This runbook is the executable boundary for Phase 7. It does not authorize
production activation by itself. A pilot starts only after the owner has recorded
the Play lifecycle evidence, legal/privacy approval, and maker/checker payout
approval.

## Pilot shape

- 3–5 named partners, one approved affiliate code per partner.
- Play-only links; no Direct APK, Stripe, coupon, recurring revenue share or
  automatic payout.
- 30-day click-to-install window, 60-day install-to-purchase window and 30-day
  payout hold, unless the owner records a different policy before enabling flags.
- Manual weekly review; manual payouts only after a clean reconciliation pass.

## Launch checklist

1. Run the existing Play owner checklist: purchase, restore, pending, cancel,
   refund/void, RTDN and daily reconciliation on a signed Internal Track build.
2. Apply migration `0014_affiliate_attribution.sql` to staging and verify the
   schema backup/hash.
3. Keep `AFFILIATE_ENABLED=false` while seeding partner rows and campaigns.
4. Run one signed `/r/<code>` click through an Internal Track install and verify
   exactly one immutable attribution, one verified purchase link and one pending
   commission. Never paste a raw referrer or token into evidence.
5. Enable redirect and attribution first for one partner. Commission remains off
   until the attribution evidence is reviewed.
6. Enable commission for the pilot only after the owner signs the reconciliation
   and fraud-review checklist. Keep admin dashboard/payout access separate.

## Weekly evidence

Record only aggregate values: clicks, installs, verified purchases, pending,
payable, paid, voided and fraud-held commission totals per partner. Compare the
voided-purchases cursor with Play backend reconciliation and inspect duplicate
RTDN counts. Do not export buyer data, raw order IDs, tokens, device IDs or raw
referrers.

For the Phase 8 evaluation, store only that aggregate JSON and run
`uv run python scripts/affiliate_pilot_report.py aggregate.json`. A report with a
stop reason freezes the pilot; it is not an automatic accusation or payout decision.

## Stop criteria

Immediately set all affiliate runtime flags false and freeze pending/payable
commissions if any of the following occurs:

- attribution is duplicated, crosses affiliate codes, or binds a purchase before
  server verification;
- RTDN/voided reconciliation is stale, failing, or disagrees with Play state;
- refund/void ratio is unexplained or a partner requests purchaser data;
- a dashboard/API response exposes a token, buyer identifier, device identifier,
  raw order ID or another partner's aggregate;
- payout evidence is incomplete or maker/checker separation is missing.

Resume only after a redacted incident record, correction audit event and owner
approval. A pilot has not passed until 60 days of reconciled data and at least two
clean manual payout cycles are complete.
