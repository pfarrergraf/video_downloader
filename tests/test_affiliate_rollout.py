from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_checkout_requires_separate_explicit_flag() -> None:
    flags = read("pro/website/functions/_affiliate_flags.js")
    checkout = read("pro/website/functions/api/create-checkout.js")
    assert "AFFILIATE_CHECKOUT_ENABLED" in flags
    assert "affiliateCheckoutEnabled" in checkout
    assert 'checkout_not_enabled' in checkout


def test_registration_fails_closed_without_dependencies() -> None:
    flags = read("pro/website/functions/_affiliate_flags.js")
    registration = read("pro/website/functions/api/partner/register.js")
    for name in (
        "TURNSTILE_SECRET_KEY",
        "TURNSTILE_SITE_KEY",
        "RESEND_API_KEY",
        "PARTNER_FROM_EMAIL",
        "REFERRAL_HASH_SALT",
    ):
        assert name in flags
    assert "affiliateRegistrationReady" in registration
    assert "registration_not_ready" in registration


def test_browser_blocks_payment_when_checkout_is_disabled() -> None:
    browser = read("pro/website/affiliate-site.js")
    assert "blockCheckout" in browser
    assert "if (!config.checkout_enabled)" in browser
    assert "checkout-waive-btn" in browser
    assert "checkout-wait-btn" in browser


def test_deployment_enables_registration_but_never_checkout() -> None:
    workflow = read(".github/workflows/deploy-pro-website.yml")
    assert "pages secret put AFFILIATE_REGISTRATION_ENABLED" in workflow
    assert "printf '%s' 'false' | npx -y wrangler@3 pages secret put AFFILIATE_CHECKOUT_ENABLED" in workflow
    assert "printf '%s' 'true' | npx -y wrangler@3 pages secret put AFFILIATE_CHECKOUT_ENABLED" not in workflow
    assert "d1 export downloadthat-licenses --remote" in workflow
    assert "d1 migrations apply downloadthat-licenses --remote" in workflow
