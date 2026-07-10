-- Optimistic concurrency and reconciliation lease.
ALTER TABLE affiliates ADD COLUMN version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE affiliate_controls ADD COLUMN reconciliation_lock_token TEXT;
ALTER TABLE affiliate_controls ADD COLUMN reconciliation_lock_until INTEGER;
