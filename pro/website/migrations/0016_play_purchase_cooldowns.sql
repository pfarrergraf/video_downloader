CREATE TABLE IF NOT EXISTS play_purchase_cooldown_bypasses (
  device_id_hash TEXT PRIMARY KEY,
  expires_at INTEGER NOT NULL,
  source_refund_request_id TEXT REFERENCES play_refund_requests(id) ON DELETE SET NULL,
  reason TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_play_purchase_cooldown_bypass_expiry
  ON play_purchase_cooldown_bypasses(expires_at);
