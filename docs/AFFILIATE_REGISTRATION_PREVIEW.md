# Affiliate registration preview rollout

## Intended production state

The public partner pages and registration flow may be enabled before payments are released.

Required flags:

```text
AFFILIATE_PROGRAM_ENABLED=true
AFFILIATE_REGISTRATION_ENABLED=true
AFFILIATE_CHECKOUT_ENABLED=false
ENVIRONMENT=production
```

`AFFILIATE_CHECKOUT_ENABLED=false` is the controlling payment lock. The browser blocks the existing purchase buttons and `/api/create-checkout` returns `404 checkout_not_enabled`. Enabling registration does not enable Stripe Checkout.

## Registration readiness

Registration becomes operational only when all of the following are present in the Cloudflare Pages production environment:

```text
DB binding
TURNSTILE_SECRET_KEY
TURNSTILE_SITE_KEY
RESEND_API_KEY
PARTNER_FROM_EMAIL
REFERRAL_HASH_SALT
```

`/api/partner/config` reports separate values:

- `registration_enabled`
- `registration_ready`
- `checkout_enabled`

The public page remains visible when setup is incomplete, but the forms are disabled. This avoids accepting registrations that cannot be protected by Turnstile or verified by email.

## Automated deployment safeguards

The master deployment workflow now:

1. verifies Cloudflare deployment credentials;
2. exports the remote `downloadthat-licenses` D1 database;
3. uploads the SQL export as a 30-day GitHub Actions artifact;
4. applies migrations `0002` through `0009` idempotently;
5. sets registration flags to true;
6. sets checkout to false;
7. copies optional registration secrets from GitHub Actions secrets when available;
8. deploys Pages and Functions;
9. checks the public config endpoint and fails if checkout is not false.

## GitHub Actions secrets needed for live registration

```text
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
TURNSTILE_SECRET_KEY
TURNSTILE_SITE_KEY
RESEND_API_KEY
PARTNER_FROM_EMAIL
REFERRAL_HASH_SALT
```

Recommended additional values:

```text
AFFILIATE_ADMIN_EMAIL
ANDROID_CERT_SHA256
```

Stripe values can remain configured, but the checkout flag stays false:

```text
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
STRIPE_PRICE_ID
```

## Payment release remains an owner action

Do not activate payment merely by merging code. Before payment release, complete the production checklist, Stripe test-mode lifecycle tests, reconciliation, integrity checks, legal/tax/privacy review, and explicit owner approval.

The final activation action is changing only:

```text
AFFILIATE_CHECKOUT_ENABLED=true
```

The server will still refuse checkout unless registration dependencies and all three Stripe settings are present.
