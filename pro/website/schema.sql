-- Mirrors the schema already applied to the live D1 database
-- (downloadthat-licenses, uuid cee415b0-dad7-4ae5-a080-48872a37d057) so it's
-- reproducible from source. Re-running this against that database is a
-- harmless no-op error on the already-existing table; it's here for anyone
-- setting up a fresh database (e.g. a separate staging environment).

CREATE TABLE licenses (
  license_key TEXT PRIMARY KEY,
  tier TEXT NOT NULL CHECK (tier IN ('monthly', 'yearly', 'lifetime')),
  email TEXT NOT NULL,
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  stripe_checkout_session_id TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'canceled', 'expired')),
  current_period_end INTEGER,
  -- NULL = delivered immediately (buyer waived the 14-day withdrawal right
  -- in the checkout dialog). A timestamp = buyer kept the right; the key is
  -- sealed (license-for-session/validate refuse it) until this moment.
  -- Added 2026-07-10 via: ALTER TABLE licenses ADD COLUMN deliver_at INTEGER;
  deliver_at INTEGER,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX idx_licenses_email ON licenses(email);
CREATE INDEX idx_licenses_stripe_subscription ON licenses(stripe_subscription_id);
-- UNIQUE, not just indexed: _lib.js's handleCheckoutCompleted also checks for
-- an existing row before inserting, but this is defense-in-depth against a
-- redelivered checkout.session.completed webhook minting a second license
-- for the same payment.
CREATE UNIQUE INDEX idx_licenses_checkout_session ON licenses(stripe_checkout_session_id);

-- Enforces one active device per platform per license key (see
-- docs/DESKTOP_WEB_UI_PLAN.md's "Device-limit policy" and api/validate.js).
-- Keys are hashed (SHA-256 hex) rather than stored raw: this table only ever
-- needs to answer "has this exact device asked about this exact key before",
-- never to look either value up directly - the `licenses` table already has
-- the raw key by primary key for support/admin purposes.
CREATE TABLE license_activations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  license_key_hash TEXT NOT NULL,
  platform TEXT NOT NULL,
  device_id_hash TEXT NOT NULL,
  first_seen INTEGER NOT NULL,
  last_seen INTEGER NOT NULL,
  app_version TEXT,
  revoked_at INTEGER
);

CREATE UNIQUE INDEX idx_activations_key_platform_device
  ON license_activations(license_key_hash, platform, device_id_hash);
CREATE INDEX idx_activations_key_platform ON license_activations(license_key_hash, platform);

-- Rate-limits api/refund.js: without this, anyone who obtains a leaked
-- license_key can try email guesses against it (or just spam Stripe/D1)
-- with no penalty. Rows are opportunistically pruned by refund.js itself on
-- every request rather than needing a separate cron/cleanup job - traffic to
-- this endpoint is low enough that an unbounded table was never a real risk,
-- but there's no reason to keep expired rows around either.
CREATE TABLE refund_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ip TEXT NOT NULL,
  attempted_at INTEGER NOT NULL
);

CREATE INDEX idx_refund_attempts_ip_time ON refund_attempts(ip, attempted_at);
