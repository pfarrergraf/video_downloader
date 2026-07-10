-- DownloadThat affiliate/creator partner program.
-- Apply once to the D1 database before enabling AFFILIATE_PROGRAM_ENABLED.
-- All money is stored as integer euro cents. Ledger and audit rows are append-only.

ALTER TABLE licenses ADD COLUMN affiliate_id TEXT;
ALTER TABLE licenses ADD COLUMN affiliate_click_id TEXT;
ALTER TABLE licenses ADD COLUMN affiliate_commission_id TEXT;
ALTER TABLE licenses ADD COLUMN stripe_payment_intent_id TEXT;
ALTER TABLE licenses ADD COLUMN amount_total_cents INTEGER;
ALTER TABLE licenses ADD COLUMN currency TEXT;

CREATE TABLE affiliates (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE COLLATE NOCASE,
  code TEXT NOT NULL UNIQUE COLLATE NOCASE,
  display_name TEXT NOT NULL,
  legal_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  country TEXT NOT NULL,
  website TEXT,
  channels_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'pending_email'
    CHECK (status IN ('pending_email', 'active', 'suspended', 'rejected')),
  email_verified_at INTEGER,
  terms_version TEXT NOT NULL,
  approved_sale_count INTEGER NOT NULL DEFAULT 0 CHECK (approved_sale_count >= 0),
  lifetime_approved_cents INTEGER NOT NULL DEFAULT 0 CHECK (lifetime_approved_cents >= 0),
  lifetime_paid_cents INTEGER NOT NULL DEFAULT 0 CHECK (lifetime_paid_cents >= 0),
  negative_balance_cents INTEGER NOT NULL DEFAULT 0 CHECK (negative_balance_cents >= 0),
  first_payout_reviewed_at INTEGER,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX idx_affiliates_status ON affiliates(status);
CREATE INDEX idx_affiliates_email ON affiliates(email);

CREATE TABLE affiliate_auth_tokens (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  purpose TEXT NOT NULL CHECK (purpose IN ('verify_email', 'login')),
  expires_at INTEGER NOT NULL,
  used_at INTEGER,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (affiliate_id) REFERENCES affiliates(id)
);
CREATE INDEX idx_affiliate_auth_tokens_lookup
  ON affiliate_auth_tokens(token_hash, purpose, expires_at);

CREATE TABLE affiliate_sessions (
  session_hash TEXT PRIMARY KEY,
  affiliate_id TEXT,
  role TEXT NOT NULL CHECK (role IN ('partner', 'admin')),
  expires_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL,
  FOREIGN KEY (affiliate_id) REFERENCES affiliates(id)
);
CREATE INDEX idx_affiliate_sessions_expiry ON affiliate_sessions(expires_at);

CREATE TABLE affiliate_clicks (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL,
  campaign TEXT,
  landing_path TEXT NOT NULL,
  ip_hash TEXT,
  user_agent_hash TEXT,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  converted_at INTEGER,
  FOREIGN KEY (affiliate_id) REFERENCES affiliates(id)
);
CREATE INDEX idx_affiliate_clicks_affiliate_time
  ON affiliate_clicks(affiliate_id, created_at);
CREATE INDEX idx_affiliate_clicks_expiry ON affiliate_clicks(expires_at);

CREATE TABLE affiliate_checkout_intents (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT,
  click_id TEXT,
  withdrawal_choice TEXT NOT NULL CHECK (withdrawal_choice IN ('waived', 'wait14')),
  withdrawal_consented_at INTEGER,
  withdrawal_text_version TEXT NOT NULL,
  stripe_checkout_session_id TEXT UNIQUE,
  payment_status TEXT NOT NULL DEFAULT 'created'
    CHECK (payment_status IN ('created', 'paid', 'failed', 'refunded', 'disputed')),
  amount_total_cents INTEGER,
  currency TEXT,
  created_at INTEGER NOT NULL,
  finalized_at INTEGER,
  FOREIGN KEY (affiliate_id) REFERENCES affiliates(id),
  FOREIGN KEY (click_id) REFERENCES affiliate_clicks(id)
);
CREATE INDEX idx_affiliate_checkout_intents_affiliate
  ON affiliate_checkout_intents(affiliate_id, created_at);

CREATE TABLE affiliate_commissions (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL,
  license_key TEXT NOT NULL,
  stripe_checkout_session_id TEXT NOT NULL UNIQUE,
  stripe_payment_intent_id TEXT,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'reversed', 'paid', 'rejected', 'disputed')),
  qualified_sale_number INTEGER,
  commission_cents INTEGER,
  eligible_at INTEGER NOT NULL,
  approved_at INTEGER,
  reversed_at INTEGER,
  reversal_reason TEXT,
  payout_id TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (affiliate_id) REFERENCES affiliates(id),
  FOREIGN KEY (license_key) REFERENCES licenses(license_key),
  CHECK (commission_cents IS NULL OR commission_cents IN (200, 250, 300, 350, 400)),
  CHECK (qualified_sale_number IS NULL OR qualified_sale_number > 0),
  UNIQUE (affiliate_id, qualified_sale_number)
);
CREATE INDEX idx_affiliate_commissions_affiliate_status
  ON affiliate_commissions(affiliate_id, status, eligible_at);
CREATE INDEX idx_affiliate_commissions_payment_intent
  ON affiliate_commissions(stripe_payment_intent_id);

CREATE TABLE affiliate_ledger (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL,
  entry_type TEXT NOT NULL
    CHECK (entry_type IN ('commission_approved', 'commission_reversed', 'payout_paid', 'manual_adjustment')),
  amount_cents INTEGER NOT NULL,
  reference_type TEXT NOT NULL,
  reference_id TEXT NOT NULL,
  created_by TEXT NOT NULL,
  previous_hash TEXT,
  entry_hash TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (affiliate_id) REFERENCES affiliates(id),
  UNIQUE (entry_type, reference_type, reference_id)
);
CREATE INDEX idx_affiliate_ledger_affiliate_time
  ON affiliate_ledger(affiliate_id, created_at);

CREATE TRIGGER affiliate_ledger_no_update
BEFORE UPDATE ON affiliate_ledger
BEGIN
  SELECT RAISE(ABORT, 'affiliate_ledger is append-only');
END;
CREATE TRIGGER affiliate_ledger_no_delete
BEFORE DELETE ON affiliate_ledger
BEGIN
  SELECT RAISE(ABORT, 'affiliate_ledger is append-only');
END;

CREATE TABLE affiliate_reconciliation_snapshots (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('ok', 'warning', 'blocked')),
  valid_license_count INTEGER NOT NULL,
  stripe_paid_session_count INTEGER NOT NULL,
  recognized_revenue_cents INTEGER NOT NULL,
  expected_commission_cents INTEGER NOT NULL,
  recorded_liability_cents INTEGER NOT NULL,
  ledger_liability_cents INTEGER NOT NULL,
  paid_out_cents INTEGER NOT NULL,
  max_possible_commission_cents INTEGER NOT NULL,
  revenue_deviation_bps INTEGER NOT NULL,
  commission_deviation_bps INTEGER NOT NULL,
  reasons_json TEXT NOT NULL,
  previous_hash TEXT,
  snapshot_hash TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL
);

CREATE TRIGGER affiliate_reconciliation_no_update
BEFORE UPDATE ON affiliate_reconciliation_snapshots
BEGIN
  SELECT RAISE(ABORT, 'reconciliation snapshots are immutable');
END;
CREATE TRIGGER affiliate_reconciliation_no_delete
BEFORE DELETE ON affiliate_reconciliation_snapshots
BEGIN
  SELECT RAISE(ABORT, 'reconciliation snapshots are immutable');
END;

CREATE TABLE affiliate_controls (
  id TEXT PRIMARY KEY CHECK (id = 'global'),
  payout_frozen INTEGER NOT NULL DEFAULT 1 CHECK (payout_frozen IN (0, 1)),
  freeze_reason TEXT NOT NULL DEFAULT 'Program not reconciled yet',
  frozen_at INTEGER,
  last_reconciliation_at INTEGER,
  last_reconciliation_snapshot_id TEXT,
  updated_at INTEGER NOT NULL
);
INSERT INTO affiliate_controls
  (id, payout_frozen, freeze_reason, frozen_at, updated_at)
VALUES
  ('global', 1, 'Program not reconciled yet', unixepoch(), unixepoch());

CREATE TABLE affiliate_payouts (
  id TEXT PRIMARY KEY,
  affiliate_id TEXT NOT NULL,
  amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
  status TEXT NOT NULL DEFAULT 'prepared'
    CHECK (status IN ('prepared', 'approved', 'paid', 'canceled', 'blocked')),
  reconciliation_snapshot_id TEXT NOT NULL,
  prepared_by TEXT NOT NULL,
  approved_by TEXT,
  external_reference TEXT,
  prepared_at INTEGER NOT NULL,
  approved_at INTEGER,
  paid_at INTEGER,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (affiliate_id) REFERENCES affiliates(id),
  FOREIGN KEY (reconciliation_snapshot_id) REFERENCES affiliate_reconciliation_snapshots(id)
);
CREATE INDEX idx_affiliate_payouts_affiliate_status
  ON affiliate_payouts(affiliate_id, status);

CREATE TABLE affiliate_payout_items (
  payout_id TEXT NOT NULL,
  commission_id TEXT NOT NULL UNIQUE,
  amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
  PRIMARY KEY (payout_id, commission_id),
  FOREIGN KEY (payout_id) REFERENCES affiliate_payouts(id),
  FOREIGN KEY (commission_id) REFERENCES affiliate_commissions(id)
);

CREATE TABLE affiliate_audit_log (
  id TEXT PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  details_json TEXT NOT NULL,
  previous_hash TEXT,
  entry_hash TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL
);
CREATE INDEX idx_affiliate_audit_entity
  ON affiliate_audit_log(entity_type, entity_id, created_at);

CREATE TRIGGER affiliate_audit_no_update
BEFORE UPDATE ON affiliate_audit_log
BEGIN
  SELECT RAISE(ABORT, 'affiliate_audit_log is append-only');
END;
CREATE TRIGGER affiliate_audit_no_delete
BEFORE DELETE ON affiliate_audit_log
BEGIN
  SELECT RAISE(ABORT, 'affiliate_audit_log is append-only');
END;
