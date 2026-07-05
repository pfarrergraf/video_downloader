# Stripe and Cloudflare setup checklist

Date: 2026-07-03
Branch of record: `claude/gothic-downloader-website-bp7r2u`
Purpose: make the paid DownloadThat Pro license path deployable and testable without relying on chat history.

## Current access model

This repo contains the Cloudflare Pages site and Pages Functions under `pro/website/`.

In the current ChatGPT session, direct Cloudflare and Stripe connectors are not available. GitHub access is available. Therefore:

- Code and GitHub Actions can be prepared here.
- Cloudflare and Stripe secrets must be entered by the owner in the relevant dashboards or GitHub repository settings.
- Do not paste API keys or signing secrets into chat, docs, commits, issues, PR comments, screenshots, or logs.

## Existing Cloudflare deployment workflow

Workflow file:

- `.github/workflows/deploy-pro-website.yml`

Expected GitHub Actions secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`

The workflow deploys `pro/website` to a Cloudflare Pages project named `downloadthat` using GitHub-hosted runners.

## Cloudflare setup

### 1. Create or confirm API token

Create a Cloudflare API token with the minimum permissions required for Cloudflare Pages deployment and Pages secret management.

Recommended owner action:

1. Cloudflare dashboard -> My Profile -> API Tokens.
2. Create token.
3. Prefer a restricted token scoped to the account/project if Cloudflare offers the required Pages permissions.
4. Store it as GitHub repository secret `CLOUDFLARE_API_TOKEN`.

### 2. Add Cloudflare account ID

1. Open Cloudflare dashboard.
2. Copy the account ID from the account overview sidebar.
3. Store it as GitHub repository secret `CLOUDFLARE_ACCOUNT_ID`.

### 3. Confirm Pages project name

The workflow expects:

- project name: `downloadthat`
- website root: `pro/website`

If the production domain should later be `downloadthat.geistreich.com` or `downloadthat.gaistreich.com`, keep the Pages project name stable and add the custom domain in Cloudflare after successful deployment.

### 4. Confirm D1 binding

The Pages Functions expect a D1 binding named:

- `DB`

The database should contain the license schema from:

- `pro/website/schema.sql`

If the workflow does not create/bind D1 automatically, set the binding manually in Cloudflare Pages project settings.

## Stripe setup

### 1. Test mode first

During beta, use Stripe test mode unless the owner explicitly moves to live mode.

Required GitHub secret for Cloudflare Pages Functions:

- `STRIPE_SECRET_KEY`

For test mode, use a key beginning with `sk_test_`.

### 2. Payment Links

The current website may still contain test Payment Links. Before public launch:

- verify all visible payment links,
- remove or clearly mark test links,
- replace with live links only after Stripe live mode and business verification are complete.
- confirm each live Payment Link has `metadata.tier` set to exactly `monthly`,
  `yearly`, or `lifetime` (Dashboard -> Payment Links -> the link -> Advanced
  options -> Metadata). `_lib.js`'s `handleCheckoutCompleted` reads this to
  decide what license to grant; a Payment Link cloned from another one without
  re-checking this field silently produces a paid checkout with no license
  (falls back to inferring the tier from the purchased price's billing
  interval, but that's a safety net, not a substitute for setting it).

### 2b. Enabling SEPA Direct Debit

SEPA Debit is not on by default and needs each of the following in the Stripe
**live** dashboard - all four are dashboard/account state this repo's code
cannot verify or configure:

- Settings -> Payment methods: "SEPA Direct Debit" toggled on (requires the
  account's business address to be in a SEPA-supported country).
- The Payment Link's own payment method settings need to either use
  "automatic" methods (so the account-level toggle above takes effect) or
  explicitly list `sepa_debit`.
- SEPA Direct Debit only supports EUR - a Payment Link priced in another
  currency will never offer it regardless of the toggle above.
- Business/legal: a valid creditor identifier and mandate text, which Stripe
  provisions once SEPA Direct Debit is activated on the account.

### 3. Webhook endpoint

After the first Cloudflare Pages deployment, create a Stripe webhook endpoint:

- URL: `https://<pages-domain>/api/webhook`

Required events:

- `checkout.session.completed`
- `checkout.session.async_payment_failed` (required for SEPA Direct Debit and
  other delayed-notification payment methods - without it, a bounced SEPA
  debit never revokes the license `_lib.js`'s `handleCheckoutAsyncPaymentFailed`
  already grants on mandate authorization)
- `checkout.session.async_payment_succeeded` (fires 2-14 business days later
  when a SEPA debit actually clears; `handleCheckoutAsyncPaymentSucceeded`
  uses it as a safety net to backfill a license/period-end that the initial
  `checkout.session.completed` handling couldn't complete, not as the trigger
  that grants access - access is already granted at mandate time)
- `customer.subscription.updated`
- `customer.subscription.deleted`

After Stripe creates the webhook signing secret, store it as GitHub repository secret:

- `STRIPE_WEBHOOK_SECRET`

Then rerun the Cloudflare deployment workflow so the secret is pushed into the Pages project.

## Validation checklist

### Cloudflare Pages

- [ ] GitHub Actions deployment workflow completes successfully.
- [ ] Public site opens.
- [ ] Static pages load.
- [ ] Pages Functions routes respond.
- [ ] D1 binding `DB` exists.
- [ ] Required secrets are configured.

### Stripe test mode

- [ ] Test Payment Link opens.
- [ ] Stripe test card completes checkout.
- [ ] Webhook delivery succeeds in Stripe dashboard.
- [ ] License row is created or updated in D1.
- [ ] License validation endpoint returns expected result.
- [ ] Subscription update/cancel events change license status correctly.

### Live mode readiness

- [ ] Stripe account verification complete.
- [ ] Live products/prices/payment links exist.
- [ ] Live webhook endpoint exists.
- [ ] `STRIPE_SECRET_KEY` is changed from `sk_test_...` to `sk_live_...` only when ready.
- [ ] `STRIPE_WEBHOOK_SECRET` is changed to the live webhook secret.
- [ ] Public website no longer contains test Payment Links.

## Guardrails

- Never commit secret values.
- Never print secret values in workflow logs.
- Keep test and live Stripe environments separate.
- Do not mix test Payment Links with live webhook secrets.
- Do not publish live payment links until legal pages, refund process, support email, and privacy policy are final.
