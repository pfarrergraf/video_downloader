from __future__ import annotations

import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "pro" / "website"
MIGRATIONS = WEBSITE / "migrations"


def _migrated_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript((WEBSITE / "schema.sql").read_text(encoding="utf-8"))
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        db.executescript(migration.read_text(encoding="utf-8"))
    return db


def test_affiliate_migrations_apply_and_seed_fail_closed_control() -> None:
    db = _migrated_db()
    tables = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {
        "affiliates",
        "affiliate_clicks",
        "affiliate_checkout_intents",
        "affiliate_commissions",
        "affiliate_ledger",
        "affiliate_reconciliation_snapshots",
        "affiliate_integrity_checks",
        "affiliate_payouts",
        "affiliate_payout_allocations",
        "affiliate_audit_log",
    } <= tables
    control = db.execute(
        "SELECT payout_frozen, freeze_reason FROM affiliate_controls WHERE id = 'global'"
    ).fetchone()
    assert control is not None
    assert control[0] == 1
    assert "not reconciled" in control[1].lower()


def test_finance_tables_enforce_money_and_append_only_rules() -> None:
    db = _migrated_db()
    now = 1_750_000_000
    db.execute(
        """INSERT INTO affiliates
           (id, slug, code, display_name, legal_name, email, country, status,
            email_verified_at, terms_version, created_at, updated_at)
           VALUES ('a1','creator','CREATOR1','Creator','Creator GmbH',
                   'creator@example.test','DE','active',?,'2026-07-v1',?,?)""",
        (now, now, now),
    )
    db.execute(
        """INSERT INTO licenses
           (license_key,tier,email,stripe_checkout_session_id,status,created_at,updated_at,
            affiliate_id,amount_total_cents,currency)
           VALUES ('DLT-TEST-TEST-TEST','lifetime','buyer@example.test','cs_test_1',
                   'active',?,?, 'a1',1200,'eur')""",
        (now, now),
    )
    db.execute(
        """INSERT INTO affiliate_commissions
           (id,affiliate_id,license_key,stripe_checkout_session_id,status,
            qualified_sale_number,commission_cents,eligible_at,approved_at,created_at,updated_at)
           VALUES ('c1','a1','DLT-TEST-TEST-TEST','cs_test_1','approved',1,200,?,?,?,?,?)""",
        (now, now, now, now, now),
    )
    db.execute(
        """INSERT INTO affiliate_ledger
           (id,affiliate_id,entry_type,amount_cents,reference_type,reference_id,
            created_by,entry_hash,created_at)
           VALUES ('l1','a1','commission_approved',200,'commission','c1',
                   'test','hash-1',?)""",
        (now,),
    )
    with __import__("pytest").raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("UPDATE affiliate_ledger SET amount_cents = 400 WHERE id = 'l1'")
    with __import__("pytest").raises(sqlite3.IntegrityError, match="append-only"):
        db.execute("DELETE FROM affiliate_ledger WHERE id = 'l1'")
    with __import__("pytest").raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO affiliate_commissions
               (id,affiliate_id,license_key,stripe_checkout_session_id,status,
                qualified_sale_number,commission_cents,eligible_at,created_at,updated_at)
               VALUES ('bad','a1','DLT-TEST-TEST-TEST','cs_test_2','approved',2,275,?,?,?)""",
            (now, now, now),
        )


def test_integrity_gate_contains_independent_ceiling_and_five_percent_freeze() -> None:
    source = (WEBSITE / "functions" / "_affiliate_integrity.js").read_text(encoding="utf-8")
    core = (WEBSITE / "functions" / "_affiliate.js").read_text(encoding="utf-8")
    assert "RECONCILIATION_BLOCK_BPS = 500" in core
    assert "attributedLicenses * 400" in source
    assert "paid_out_exceeds_four_euro_per_attributed_license_ceiling" in source
    assert "verifyLedgerChain" in source
    assert "verifyAuditChain" in source
    assert "verifyReconciliationChain" in source
    assert "verifyIntegrityCheckChain" in source
    assert "payout_frozen = ?" in source


def test_checkout_and_webhook_never_trust_browser_commission_amounts() -> None:
    checkout = (WEBSITE / "functions" / "api" / "create-checkout.js").read_text(
        encoding="utf-8"
    )
    webhook = (WEBSITE / "functions" / "api" / "webhook.js").read_text(
        encoding="utf-8"
    )
    assert "env.STRIPE_PRICE_ID" in checkout
    assert '"metadata[affiliate_id]"' in checkout
    assert "resolveAffiliateAttribution" in checkout
    assert "commission_cents" not in checkout
    for event in (
        "charge.refunded",
        "charge.dispute.created",
        "charge.dispute.closed",
        "checkout.session.async_payment_failed",
    ):
        assert event in webhook


def test_android_app_link_is_exact_and_adds_no_permissions() -> None:
    manifest = (
        ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    ).read_text(encoding="utf-8")
    permissions = set(re.findall(r'<uses-permission android:name="([^"]+)"', manifest))
    assert permissions == {
        "android.permission.INTERNET",
        "android.permission.FOREGROUND_SERVICE",
        "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
        "android.permission.POST_NOTIFICATIONS",
    }
    assert manifest.count('android:pathPrefix="/claim/"') == 2
    assert 'android:autoVerify="true"' in manifest
    assert 'android:host="downloadthat.pages.dev"' in manifest
    assert 'android:host="downloadthat.gaistreich.com"' in manifest
    referral = (
        ROOT
        / "android"
        / "app"
        / "src"
        / "main"
        / "java"
        / "de"
        / "classydl"
        / "app"
        / "AffiliateReferral.kt"
    ).read_text(encoding="utf-8")
    assert "ATTRIBUTION_WINDOW_MS = 180L" in referral
    assert 'segments[0] != "claim"' in referral
    assert "rewritePricingUrl" in referral


def test_security_headers_cover_partner_and_api_surfaces() -> None:
    headers = (WEBSITE / "_headers").read_text(encoding="utf-8")
    for required in (
        "Content-Security-Policy",
        "Strict-Transport-Security",
        "X-Content-Type-Options: nosniff",
        "X-Frame-Options: DENY",
        "/partner-dashboard.html",
        "/partner-admin.html",
        "/api/*",
        "Cache-Control: no-store",
    ):
        assert required in headers
