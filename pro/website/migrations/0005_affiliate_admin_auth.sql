CREATE TABLE affiliate_admin_tokens (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at INTEGER NOT NULL,
  used_at INTEGER,
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_affiliate_admin_tokens_lookup
  ON affiliate_admin_tokens(token_hash, expires_at);
