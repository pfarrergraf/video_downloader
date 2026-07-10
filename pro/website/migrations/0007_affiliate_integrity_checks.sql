-- Independent integrity-gate snapshots. These records are append-only and hash
-- chained so a payout decision can later be reconstructed and tampering is
-- detectable even when business tables still look arithmetically plausible.
CREATE TABLE affiliate_integrity_checks (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('ok', 'blocked')),
  hard_failures_json TEXT NOT NULL,
  deviation_failures_json TEXT NOT NULL,
  metrics_json TEXT NOT NULL,
  previous_hash TEXT,
  check_hash TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL
);

CREATE INDEX idx_affiliate_integrity_checks_time
  ON affiliate_integrity_checks(created_at);

CREATE TRIGGER affiliate_integrity_checks_no_update
BEFORE UPDATE ON affiliate_integrity_checks
BEGIN
  SELECT RAISE(ABORT, 'affiliate_integrity_checks is append-only');
END;

CREATE TRIGGER affiliate_integrity_checks_no_delete
BEFORE DELETE ON affiliate_integrity_checks
BEGIN
  SELECT RAISE(ABORT, 'affiliate_integrity_checks is append-only');
END;
