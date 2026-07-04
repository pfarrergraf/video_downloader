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
