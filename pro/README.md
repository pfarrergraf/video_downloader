# DownloadThat Pro — backend + website

Lives inside `video_downloader` (under `pro/`) rather than a separate repo — deliberately
kept out of the Android app's Chaquopy source set (see `android/app/build.gradle`'s
`exclude "pro/**"`) since it's JS/HTML for a separate Cloudflare deployment, not part of
the Python package.

Everything here was built from Claude Code's session tools directly (Stripe products/prices/
payment links, a Cloudflare D1 database) — the two pieces that couldn't be done remotely
(deploying the Worker, and DNS) are the steps below.

The Android app itself now *does* talk to this backend (see `video_downloader/licensing.py`
and `android_entry.py`'s `license_api_base` param) — once you deploy the Worker per the
steps below, update `MainActivity.kt`'s `LICENSE_API_BASE` constant to the real URL so the
app can actually validate licenses instead of treating everyone as free-tier.

`website/index.html` is in German (matching the app itself, which is German-only) and
includes a real screenshot of the app — a phone-mockup hero showing an actual scrape result
with items selected for batch download, embedded inline as a data URI so the page is a
single self-contained file with no separate asset hosting to set up.

## What already exists (done, no action needed)

- **Stripe** (sandbox/test mode account "Gaistreich sandbox"): a product "DownloadThat Pro"
  with 3 prices (€1/mo, €5/yr, €12 one-time) and a Payment Link for each:
  - Monthly: https://buy.stripe.com/test_bJe3cx91IbifdUE8uA7AI00
  - Yearly: https://buy.stripe.com/test_00w6oJfq64TR03OdOU7AI01
  - Lifetime: https://buy.stripe.com/test_5kQ00l5Pwcmj6sc8uA7AI02
  - **These are TEST links — cards won't actually be charged.** See "Going live" below.
- **Cloudflare D1**: a database `downloadthat-licenses` (uuid
  `cee415b0-dad7-4ae5-a080-48872a37d057`) with the `licenses` table already created —
  `worker/schema.sql` mirrors it for reference.

## What you need to do

### 1. Deploy the Worker

```bash
cd worker
npx wrangler login          # opens a browser to authorize wrangler with your Cloudflare account
npx wrangler deploy
```

This gives you a URL like `https://downloadthat-license-server.<your-subdomain>.workers.dev`.

### 2. Set the Worker's secrets

From your Stripe dashboard (**make sure you're in test mode** — toggle top-right — while
using the test Payment Links above):

```bash
npx wrangler secret put STRIPE_SECRET_KEY
# paste your sk_test_... key (Developers -> API keys)
```

### 3. Create the Stripe webhook, then set its secret

In the Stripe dashboard: **Developers -> Webhooks -> Add endpoint**.
- URL: `https://downloadthat-license-server.<your-subdomain>.workers.dev/webhook`
  (or your custom domain, once step 5 is done)
- Events to send: `checkout.session.completed`, `customer.subscription.updated`,
  `customer.subscription.deleted`

Stripe shows a signing secret (`whsec_...`) once the endpoint is created:

```bash
npx wrangler secret put STRIPE_WEBHOOK_SECRET
# paste the whsec_... value
```

### 4. Update the website's API base URL

Edit `website/success.html`, find this line near the bottom:

```js
const LICENSE_API_BASE = "https://downloadthat-license-server.YOUR-SUBDOMAIN.workers.dev";
```

Replace it with your actual Worker URL (or custom domain from step 5).

### 5. (Optional but recommended) Put both behind your geistreich.com domain

In the Cloudflare dashboard, assuming `geistreich.com` is already a zone in this account:

- **Worker custom domain**: Workers & Pages → `downloadthat-license-server` → Settings →
  Domains & Routes → Add custom domain → e.g. `api.downloadthat.geistreich.com`.
- **Website**: easiest via Cloudflare Pages —
  ```bash
  cd website
  npx wrangler pages deploy . --project-name=downloadthat
  ```
  then in the Pages project's settings, add a custom domain, e.g.
  `downloadthat.geistreich.com`.
- Update the 3 Stripe Payment Links' redirect URL (currently
  `https://downloadthat.geistreich.com/success.html?session_id={CHECKOUT_SESSION_ID}`) if you
  pick a different subdomain — via Stripe dashboard → Payment Links → each link → Edit, or ask
  me to update them again once you've decided.

### 6. Test it end-to-end

Use one of the **test** Payment Links above with Stripe's test card `4242 4242 4242 4242`,
any future expiry, any CVC. You should land on `success.html` and see a generated license
key within a few seconds (the page polls the Worker automatically).

Then check it validates:

```bash
curl "https://downloadthat-license-server.<your-subdomain>.workers.dev/api/validate?key=DLT-XXXX-XXXX-XXXX"
```

## Going live (real payments)

The Stripe account connected to this session is a **sandbox**. To actually take €1/€5/€12
from real customers:

1. Complete Stripe's business verification / activate the account for live mode (in the
   Stripe dashboard).
2. Live mode has its own separate Products/Prices/Payment Links — the ones created here
   won't carry over. Re-create the same 3 prices in live mode (or ask me to do it once
   you're set up), and swap the website's pricing buttons to the new live Payment Link URLs.
3. Create a *second* webhook endpoint for live mode (same URL, same events) and set a
   `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET` pair for live mode — either as a second
   Worker (`downloadthat-license-server-live`) or by swapping the existing Worker's secrets
   once you're ready to fully cut over.

## What the Android app now does with this (as of this commit)

- Free tier (no key, or an invalid/expired key): full quality, same as Pro — but rationed
  to 1 download per rolling 24h window (a completed/pending/in-progress job within the
  last 24h blocks a new one with `402`; cancelled/failed jobs don't count against it).
- Pro tier (valid key): no daily limit.
- The license card in the app's web UI is entirely hidden on Termux/desktop — gating only
  applies when `MainActivity.kt` passes a `license_api_base` into `android_entry.start(...)`.
- **`MainActivity.kt`'s `LICENSE_API_BASE` is still a placeholder** pointing at an
  undeployed `*.workers.dev` URL. Until you deploy the Worker (step 1 above) and update
  that constant, the app can't reach the license server — it fails closed as free-tier
  (a network error on `/api/validate` is treated as "not Pro", never as "Pro").
