-- Phase 1 Play-first affiliate foundation. All public behaviour is separately
-- feature-gated; these additive tables are safe to deploy while disabled.
CREATE TABLE IF NOT EXISTS affiliates (
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

CREATE TABLE IF NOT EXISTS affiliate_campaigns (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  source TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  UNIQUE (affiliate_id, slug)
);
CREATE INDEX IF NOT EXISTS idx_affiliate_campaigns_status ON affiliate_campaigns(status, affiliate_id);

CREATE TABLE IF NOT EXISTS referral_clicks (
  click_id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL REFERENCES affiliates(id),
  campaign_id TEXT REFERENCES affiliate_campaigns(id),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  source TEXT,
  rejected_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_referral_clicks_affiliate_time ON referral_clicks(affiliate_id, created_at);

CREATE TABLE IF NOT EXISTS install_attributions (
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
CREATE INDEX IF NOT EXISTS idx_install_attributions_affiliate_time ON install_attributions(affiliate_id, attributed_at);

CREATE TABLE IF NOT EXISTS affiliate_purchases (
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_affiliate_purchases_order
  ON affiliate_purchases(order_id) WHERE order_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS affiliate_commissions (
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
CREATE INDEX IF NOT EXISTS idx_affiliate_commissions_release ON affiliate_commissions(status, available_at);
CREATE INDEX IF NOT EXISTS idx_affiliate_commissions_affiliate ON affiliate_commissions(affiliate_id, status);

CREATE TABLE IF NOT EXISTS affiliate_event_inbox (
  source TEXT NOT NULL,
  external_event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  received_at INTEGER NOT NULL,
  processed_at INTEGER,
  status TEXT NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'processed', 'retryable', 'rejected')),
  payload_hash TEXT,
  PRIMARY KEY (source, external_event_id)
);

CREATE TABLE IF NOT EXISTS affiliate_audit_events (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  reason TEXT,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_affiliate_audit_object ON affiliate_audit_events(object_type, object_id, created_at);

CREATE TABLE IF NOT EXISTS affiliate_reconciliation_cursors (
  source TEXT PRIMARY KEY,
  window_start_millis INTEGER NOT NULL,
  window_end_millis INTEGER NOT NULL,
  next_page_token TEXT,
  updated_at INTEGER NOT NULL
);
