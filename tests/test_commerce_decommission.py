from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "pro" / "website"


def test_stripe_and_affiliate_routes_are_not_deployed() -> None:
    removed = (
        "functions/api/create-checkout.js",
        "functions/api/webhook.js",
        "functions/api/refund.js",
        "functions/api/license-for-session.js",
        "functions/api/partner/config.js",
        "partner.html",
        "partner-dashboard.html",
        "partner-admin.html",
        "affiliate-site.js",
    )
    assert all(not (WEBSITE / relative).exists() for relative in removed)


def test_active_cloudflare_code_has_no_stripe_or_affiliate_dependencies() -> None:
    active = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (WEBSITE / "functions").rglob("*.js")
    ).lower()
    assert "api.stripe.com" not in active
    assert "stripe_secret" not in active
    assert "_affiliate" not in active


def test_first_party_play_refund_and_cooldown_routes_are_not_deployed() -> None:
    removed = (
        "functions/_play_refunds.js",
        "functions/_play_purchase_eligibility.js",
        "functions/api/play/refunds/request.js",
        "functions/api/admin/play-refunds.js",
        "functions/api/play/purchases/eligibility.js",
    )
    assert all(not (WEBSITE / relative).exists() for relative in removed)

    workflow = (ROOT / ".github/workflows/deploy-pro-website.yml").read_text(encoding="utf-8")
    assert "PLAY_AUTOMATED_REFUNDS_ENABLED" not in workflow
    assert "PLAY_REFUND_ADMIN_TOKEN" not in workflow


def test_historical_refund_finance_records_are_preserved() -> None:
    assert (WEBSITE / "migrations/0013_google_play_refunds.sql").exists()
    assert (WEBSITE / "migrations/0016_play_purchase_cooldowns.sql").exists()
    assert (ROOT / "scripts/google_play_finance.py").exists()


def test_public_website_uses_google_play_local_price_without_a_fixed_amount() -> None:
    homepage = (WEBSITE / "index.html").read_text(encoding="utf-8")
    english = (WEBSITE / "i18n/en.json").read_text(encoding="utf-8")
    german = (WEBSITE / "i18n/de.json").read_text(encoding="utf-8")

    assert "12&nbsp;€" not in homepage
    assert "local Google Play price" in english
    assert "lokalen Google-Play-Preis" in german
