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

-- Google Play is the entitlement authority for Android purchases. Raw tokens
-- are never stored: token_hash is the idempotency key and the API credential
-- itself is AES-256-GCM encrypted with a deployment secret.
CREATE TABLE play_purchases (
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
  purchase_completed_at INTEGER,
  entitlement_delivered_at INTEGER,
  purchase_device_id_hash TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE UNIQUE INDEX idx_play_purchases_license ON play_purchases(license_key) WHERE license_key IS NOT NULL;
CREATE INDEX idx_play_purchases_reconciliation ON play_purchases(verified_at, purchase_state);

CREATE TABLE play_refund_requests (
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

CREATE UNIQUE INDEX idx_play_refund_order ON play_refund_requests(order_id) WHERE order_id IS NOT NULL;
CREATE INDEX idx_play_refund_review ON play_refund_requests(status, requested_at);
CREATE INDEX idx_play_refund_device ON play_refund_requests(device_id_hash, status);

-- Short-lived, administrator-issued exceptions let release testers exercise
-- repeat-purchase/refund flows without deleting the audit trail which drives
-- the production cooldown policy.
CREATE TABLE play_purchase_cooldown_bypasses (
  device_id_hash TEXT PRIMARY KEY,
  expires_at INTEGER NOT NULL,
  source_refund_request_id TEXT REFERENCES play_refund_requests(id) ON DELETE SET NULL,
  reason TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX idx_play_purchase_cooldown_bypass_expiry
  ON play_purchase_cooldown_bypasses(expires_at);

-- Server-issued owner/tester grants. Raw bearer keys are returned once at
-- creation and only their SHA-256 hashes are stored here.
CREATE TABLE tester_grants (
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

CREATE INDEX idx_tester_grants_status_expiry ON tester_grants(status, expires_at);

-- Play-first affiliate tables. They are intentionally present in the reproducible
-- schema while all public affiliate behaviour remains feature-flagged off.
CREATE TABLE affiliates (
  id TEXT PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'disabled', 'rejected')),
  commission_type TEXT NOT NULL DEFAULT 'fixed' CHECK (commission_type IN ('fixed', 'percentage')),
  commission_value_minor INTEGER NOT NULL DEFAULT 0 CHECK (commission_value_minor >= 0),
  commission_rate_bps INTEGER NOT NULL DEFAULT 0 CHECK (commission_rate_bps BETWEEN 0 AND 10000),
  created_at INTEGER NOT NULL,
  approved_at INTEGER,
  disabled_at INTEGER,
  updated_at INTEGER NOT NULL
);

CREATE TABLE affiliate_campaigns (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  source TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  UNIQUE (affiliate_id, slug)
);
CREATE INDEX idx_affiliate_campaigns_status ON affiliate_campaigns(status, affiliate_id);

CREATE TABLE referral_clicks (
  click_id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL REFERENCES affiliates(id),
  campaign_id TEXT REFERENCES affiliate_campaigns(id),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  source TEXT,
  rejected_reason TEXT
);
CREATE INDEX idx_referral_clicks_affiliate_time ON referral_clicks(affiliate_id, created_at);

CREATE TABLE install_attributions (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL REFERENCES affiliates(id),
  campaign_id TEXT REFERENCES affiliate_campaigns(id),
  click_id TEXT NOT NULL UNIQUE REFERENCES referral_clicks(click_id),
  install_id_hash TEXT NOT NULL UNIQUE,
  referrer_received_at INTEGER NOT NULL,
  click_timestamp INTEGER,
  install_timestamp INTEGER,
  attributed_at INTEGER NOT NULL,
  attribution_source TEXT NOT NULL DEFAULT 'play_install_referrer',
  attribution_version TEXT NOT NULL DEFAULT 'v1'
);
CREATE INDEX idx_install_attributions_affiliate_time ON install_attributions(affiliate_id, attributed_at);

CREATE TABLE affiliate_purchases (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL REFERENCES affiliates(id),
  install_attribution_id TEXT NOT NULL REFERENCES install_attributions(id),
  purchase_token_hash TEXT NOT NULL UNIQUE REFERENCES play_purchases(token_hash),
  order_id TEXT,
  product_id TEXT NOT NULL,
  amount_minor INTEGER,
  currency TEXT,
  purchase_timestamp INTEGER,
  status TEXT NOT NULL DEFAULT 'verified' CHECK (status IN ('verified', 'voided', 'rejected')),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE UNIQUE INDEX idx_affiliate_purchases_order ON affiliate_purchases(order_id) WHERE order_id IS NOT NULL;

CREATE TABLE affiliate_commissions (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL REFERENCES affiliates(id),
  affiliate_purchase_id TEXT NOT NULL UNIQUE REFERENCES affiliate_purchases(id),
  gross_amount_minor INTEGER,
  commission_amount_minor INTEGER NOT NULL CHECK (commission_amount_minor >= 0),
  currency TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'payable', 'paid', 'voided', 'fraud_hold', 'clawback_due')),
  available_at INTEGER NOT NULL,
  approved_at INTEGER,
  paid_at INTEGER,
  payment_reference TEXT,
  voided_at INTEGER,
  void_reason TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX idx_affiliate_commissions_release ON affiliate_commissions(status, available_at);
CREATE INDEX idx_affiliate_commissions_affiliate ON affiliate_commissions(affiliate_id, status);

CREATE TABLE affiliate_event_inbox (
  source TEXT NOT NULL,
  external_event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  received_at INTEGER NOT NULL,
  processed_at INTEGER,
  status TEXT NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'processed', 'retryable', 'rejected')),
  payload_hash TEXT,
  PRIMARY KEY (source, external_event_id)
);

CREATE TABLE affiliate_audit_events (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  reason TEXT,
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_affiliate_audit_object ON affiliate_audit_events(object_type, object_id, created_at);

CREATE TABLE affiliate_reconciliation_cursors (
  source TEXT PRIMARY KEY,
  window_start_millis INTEGER NOT NULL,
  window_end_millis INTEGER NOT NULL,
  next_page_token TEXT,
  updated_at INTEGER NOT NULL
);

CREATE TABLE affiliate_access_tokens (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  label TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
  created_at INTEGER NOT NULL,
  last_used_at INTEGER,
  revoked_at INTEGER
);
CREATE INDEX idx_affiliate_access_tokens_scope ON affiliate_access_tokens(affiliate_id, status);
