from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "pro" / "website"


def test_legacy_stripe_routes_are_not_deployed() -> None:
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


def test_active_cloudflare_code_has_no_stripe_or_legacy_affiliate_dependencies() -> None:
    active = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (WEBSITE / "functions").rglob("*.js")
    ).lower()
    assert "api.stripe.com" not in active
    assert "stripe_secret" not in active
    # The Play-first affiliate implementation is intentionally present now, but
    # every public path is independently feature-gated and no Stripe-era module
    # may be revived.
    assert "affiliateflags" in active
    assert "affiliate_production_approved" in active
