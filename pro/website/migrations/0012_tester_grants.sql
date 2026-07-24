-- Owner and tester grants are server-issued, hash-addressed bearer keys.
-- The raw key is returned only at creation time and is never stored in D1.
CREATE TABLE IF NOT EXISTS tester_grants (
  id TEXT PRIMARY KEY,
  key_hash TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  grant_type TEXT NOT NULL CHECK (grant_type IN ('owner', 'tester')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
  expires_at INTEGER,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  revoked_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_tester_grants_status_expiry
  ON tester_grants(status, expires_at);
