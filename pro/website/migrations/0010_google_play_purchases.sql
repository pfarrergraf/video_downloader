CREATE TABLE IF NOT EXISTS play_purchases (
  token_hash TEXT PRIMARY KEY,
  purchase_token_ciphertext TEXT NOT NULL,
  purchase_token_iv TEXT NOT NULL,
  order_id TEXT,
  package_name TEXT NOT NULL,
  product_id TEXT NOT NULL,
  purchase_state TEXT NOT NULL CHECK (purchase_state IN ('pending', 'purchased', 'revoked')),
  license_key TEXT REFERENCES licenses(license_key) ON DELETE SET NULL,
  verified_at INTEGER NOT NULL,
  acknowledged_at INTEGER,
  revoked_at INTEGER,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_play_purchases_license
  ON play_purchases(license_key) WHERE license_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_play_purchases_reconciliation
  ON play_purchases(verified_at, purchase_state);
