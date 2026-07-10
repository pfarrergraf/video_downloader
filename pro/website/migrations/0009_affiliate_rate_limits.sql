-- Generic rate-limit ledger for affiliate auth/registration endpoints
-- (partner login-request, admin login-request, partner register), which
-- previously relied on Cloudflare Turnstile alone with no request-count
-- throttle -- mirrors the existing refund_attempts pattern in schema.sql.
-- key_hash is salted with REFERRAL_HASH_SALT so no raw IP/email is stored.
CREATE TABLE affiliate_rate_limit_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bucket TEXT NOT NULL,
  key_hash TEXT NOT NULL,
  attempted_at INTEGER NOT NULL
);
CREATE INDEX idx_affiliate_rate_limit_lookup
  ON affiliate_rate_limit_attempts(bucket, key_hash, attempted_at);
