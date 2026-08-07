-- Phase 6: scoped affiliate dashboard access. Tokens are bearer credentials;
-- store only their SHA-256 hash and return the raw token once at creation.
CREATE TABLE IF NOT EXISTS affiliate_access_tokens (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  label TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
  created_at INTEGER NOT NULL,
  last_used_at INTEGER,
  revoked_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_affiliate_access_tokens_scope
  ON affiliate_access_tokens(affiliate_id, status);
