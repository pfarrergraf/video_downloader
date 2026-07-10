ALTER TABLE affiliate_reconciliation_snapshots ADD COLUMN stripe_paid_ever_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE affiliate_reconciliation_snapshots ADD COLUMN count_deviation_bps INTEGER NOT NULL DEFAULT 0;
ALTER TABLE affiliate_reconciliation_snapshots ADD COLUMN ledger_deviation_bps INTEGER NOT NULL DEFAULT 0;
