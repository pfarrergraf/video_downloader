-- Exact allocation permits negative clawback balances to be offset without
-- pretending that a commission was fully settled when only part was paid.
ALTER TABLE affiliate_commissions ADD COLUMN settled_cents INTEGER NOT NULL DEFAULT 0;
ALTER TABLE affiliate_payouts ADD COLUMN negative_balance_applied_cents INTEGER NOT NULL DEFAULT 0;

CREATE TABLE affiliate_payout_allocations (
  id TEXT PRIMARY KEY,
  payout_id TEXT NOT NULL,
  commission_id TEXT NOT NULL,
  amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
  created_at INTEGER NOT NULL,
  FOREIGN KEY (payout_id) REFERENCES affiliate_payouts(id),
  FOREIGN KEY (commission_id) REFERENCES affiliate_commissions(id)
);
CREATE INDEX idx_affiliate_payout_allocations_payout
  ON affiliate_payout_allocations(payout_id);
CREATE INDEX idx_affiliate_payout_allocations_commission
  ON affiliate_payout_allocations(commission_id);
