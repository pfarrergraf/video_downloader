ALTER TABLE play_purchases ADD COLUMN purchase_completed_at INTEGER;
ALTER TABLE play_purchases ADD COLUMN entitlement_delivered_at INTEGER;
ALTER TABLE play_purchases ADD COLUMN purchase_device_id_hash TEXT;

CREATE TABLE IF NOT EXISTS play_refund_requests (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE REFERENCES play_purchases(token_hash) ON DELETE CASCADE,
  order_id TEXT,
  device_id_hash TEXT NOT NULL,
  reason TEXT NOT NULL CHECK (reason IN ('technical_failure', 'accidental_purchase', 'other')),
  status TEXT NOT NULL CHECK (status IN ('manual_review', 'processing', 'refunded', 'rejected')),
  policy_reason TEXT NOT NULL,
  requested_at INTEGER NOT NULL,
  decided_at INTEGER,
  refunded_at INTEGER,
  updated_at INTEGER NOT NULL,
  last_error TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_play_refund_order
  ON play_refund_requests(order_id) WHERE order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_play_refund_review
  ON play_refund_requests(status, requested_at);
CREATE INDEX IF NOT EXISTS idx_play_refund_device
  ON play_refund_requests(device_id_hash, status);
