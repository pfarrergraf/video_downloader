# DownloadThat Pro — backend + website

> **HISTORICAL SETUP NOTES:** Die Stripe-/Affiliate- und
> `gaistreich.com`-Anweisungen weiter unten dokumentieren den entfernten Aufbau.
> Für die aktuelle Google-Play-first-Produktion mit `downloadthat.app` gelten
> `../docs/GOOGLE_PLAY_OPERATIONS.md` und
> `../docs/CLOUDFLARE_DOWNLOADTHAT_APP_SETUP.md`.

Lives inside `video_downloader` (under `pro/`) rather than a separate repo — deliberately
kept out of the Android app's Chaquopy source set (see `android/app/build.gradle`'s
`exclude "pro/**"`) since it's JS/HTML for a separate Cloudflare deployment, not part of
the Python package.

**Deploys entirely through Cloudflare's git integration — no `wrangler` CLI, no API
token, nothing to install.** This was a deliberate redesign: the session building this
has no way to run `wrangler` itself (its network egress is policy-blocked from reaching
`api.cloudflare.com` — confirmed, not a missing-tool issue) and the person operating this
project only has a phone, so a CLI-driven deploy was never going to work for either side.
Cloudflare Pages' "Connect to Git" flow needs neither: point it at this GitHub repo once
from a browser (phone browser included), and it rebuilds and redeploys automatically on
every push to this branch — including pushes made by Claude.

`website/index.html` is in German (matching the app itself, which is German-only) and
includes a real screenshot of the app — a phone-mockup hero showing an actual scrape result
with items selected for batch download, embedded inline as a data URI so the page is a
single self-contained file with no separate asset hosting to set up.

The backend (Stripe webhook handling, license issuance/validation) lives in
`website/functions/api/` as Cloudflare Pages Functions — plain files that Cloudflare
deploys as serverless routes alongside the static site, same git push, same domain, no
separate Worker to manage. (`_lib.js` holds the shared logic; anything Cloudflare Pages
doesn't route because it starts with `_`.)

## What already exists (done, no action needed)

- **Stripe** (sandbox/test mode account "Gaistreich sandbox"): a product "DownloadThat Pro"
  with 3 prices (€1/mo, €5/yr, €12 one-time) and a Payment Link for each:
  - Monthly: https://buy.stripe.com/test_bJe3cx91IbifdUE8uA7AI00
  - Yearly: https://buy.stripe.com/test_00w6oJfq64TR03OdOU7AI01
  - Lifetime: https://buy.stripe.com/test_5kQ00l5Pwcmj6sc8uA7AI02
  - **These are TEST links — cards won't actually be charged.** See "Going live" below.
- **Cloudflare D1**: a database `downloadthat-licenses` (uuid
  `cee415b0-dad7-4ae5-a080-48872a37d057`) with the `licenses` table already created —
  `schema.sql` mirrors it for reference.
- The code for the site and the API routes — nothing left to write, only to connect.
- **Pricing page consent gate**: the buy buttons on `index.html` are inert until the
  visitor checks a box confirming they want performance to start immediately (losing
  their 14-day statutory withdrawal right per § 356 Abs. 5 BGB, see `agb.html` §6.3) -
  required for that early termination to be legally effective. A timestamp gets
  stamped into the Stripe Payment Link's `client_reference_id` as evidence of when
  consent was given.
- **`widerruf.html` + `functions/api/refund.js`**: a self-service refund page. Anyone
  can request a full refund within 14 days of purchase (license key + the email used
  at checkout) regardless of the consent above — this is a voluntary goodwill
  guarantee, not just the bare legal minimum. Calls Stripe's refund API directly
  (one-time payment_intent for lifetime, or the subscription's first invoice +
  immediate cancellation for monthly/yearly) and marks the license `canceled` in D1
  either way.

## What you need to do — all from the Cloudflare dashboard, phone-friendly

### 1. Create the Pages project

Cloudflare dashboard → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**.
- Pick the `pfarrergraf/video_downloader` repo and this branch
  (`claude/gothic-downloader-website-bp7r2u`, or `master` after merging).
- **Root directory**: `pro/website`
- **Build command**: leave empty (nothing to build — it's static HTML + Functions)
- **Build output directory**: `.`

Cloudflare will assign a URL like `https://downloadthat.pages.dev` (or similar) — that's
your site, live immediately once the first build finishes (~30 seconds, no build step).

### 2. Bind the D1 database

In the new Pages project → **Settings** → **Functions** → **D1 database bindings** →
Add binding:
- Variable name: `DB`
- D1 database: `downloadthat-licenses`

(The checked-in `wrangler.toml` declares this too, but the dashboard binding is what
actually takes effect for a git-connected project — add it there to be sure.)

### 3. Set the two secrets

Same Pages project → **Settings** → **Environment variables** → add, both as
**Secret** (not plaintext):
- `STRIPE_SECRET_KEY` — from the Stripe dashboard → Developers → API keys. Use the
  **test** key (`sk_test_...`) while using the test Payment Links above.
- `STRIPE_WEBHOOK_SECRET` — from step 4 below (create the webhook first, then come back
  and set this).

Redeploy after adding secrets (Pages → Deployments → ⋯ → Retry deployment) so the running
Functions pick them up.

### 4. Create the Stripe webhook

Stripe dashboard → **Developers** → **Webhooks** → **Add endpoint**.
- URL: `https://<your-pages-url>/api/webhook`
- Events to send: `checkout.session.completed`, `customer.subscription.updated`,
  `customer.subscription.deleted`

Stripe shows a signing secret (`whsec_...`) once created — that's the
`STRIPE_WEBHOOK_SECRET` value for step 3.

### 5. (Optional) Put it behind your gaistreich.com domain

Pages project → **Custom domains** → add e.g. `downloadthat.gaistreich.com` — only
possible if `gaistreich.com` is already a zone in this Cloudflare account. If you do
this, update the 3 Stripe Payment Links' redirect URL (currently pointing at
`https://downloadthat.gaistreich.com/success.html?...`) to match whatever domain you
actually end up with — tell me the URL and I'll update them via the Stripe API.

### 6. Test it end-to-end

Use one of the **test** Payment Links above with Stripe's test card `4242 4242 4242 4242`,
any future expiry, any CVC. You should land on `success.html` and see a generated license
key within a few seconds.

Then check it validates (from any browser, including your phone's):
`https://<your-pages-url>/api/validate?key=DLT-XXXX-XXXX-XXXX`

### 7. Tell me the final URL

Once it's live, tell me the URL and I'll update `MainActivity.kt`'s `LICENSE_API_BASE`
constant and push — that's a plain repo edit, nothing I need any credential for.

## Alternative: deploy from Termux with `wrangler` instead

If you'd rather run the actual deploy commands yourself (from the same Termux setup
this project already uses for the Android/Termux build — see the repo root `CLAUDE.md`)
instead of clicking through Cloudflare's dashboard, this works too and needs only one
dashboard visit (to mint an API token — nothing bypasses that, some credential always
has to originate there):

```bash
pkg update -y && pkg install -y nodejs git
git clone https://github.com/pfarrergraf/video_downloader.git   # or: cd video_downloader && git pull
cd video_downloader
git checkout claude/gothic-downloader-website-bp7r2u
```

Create a token: Cloudflare dashboard (any browser, phone is fine) → profile icon →
**My Profile** → **API Tokens** → **Create Token** → template **"Edit Cloudflare
Workers"** (covers Pages + D1 + Workers Scripts). Copy the token value — Cloudflare
shows it exactly once.

```bash
export CLOUDFLARE_API_TOKEN=paste-the-token-here     # only lives in this shell session
cd pro/website
npx wrangler pages deploy . --project-name=downloadthat
```

That single command creates the Pages project, deploys the static site + the
`functions/api/*` routes, AND applies the D1 binding from the checked-in
`wrangler.toml` — no dashboard binding step needed with this path. Note the
`*.pages.dev` URL it prints.

Then set the two secrets (prompts for the value, doesn't echo it, isn't logged):

```bash
npx wrangler pages secret put STRIPE_SECRET_KEY --project-name=downloadthat
```

Create the Stripe webhook per step 4 above, using the printed `*.pages.dev` URL, then:

```bash
npx wrangler pages secret put STRIPE_WEBHOOK_SECRET --project-name=downloadthat
```

Continue from step 6 (test it end-to-end) above — same steps either way from here.

`wrangler login` (browser OAuth instead of a pasted token) also works from Termux in
principle, since the OAuth callback goes to `localhost` on the same phone Termux is
running on — but the API token above is more reliable and doesn't depend on the OAuth
redirect completing correctly, so it's the recommended path here.

## Going live (real payments)

The Stripe account connected here (`acct_1ThQGXQioe5jETnQ`, "Gaistreich sandbox") is
still in **test mode**. Test mode and live mode are two fully separate data
environments in Stripe — Products, Prices, Payment Links, and Customers genuinely do
not carry over. That part is unavoidable (it's how Stripe's architecture works, not
something this project overcomplicated), but most of the actual work to recreate them
is scriptable — it is **not** a from-scratch rebuild. Checked against Stripe's API
directly:

**Steps that only you can do (human/Dashboard-only):**

1. **Business verification.** Stripe dashboard → activate your account: legal name,
   address, bank account, ID if requested. This is what actually unlocks live mode —
   nothing below works until this is done. Works fine from a phone browser.
2. **Statement descriptor.** Dashboard → **Settings** → **Business settings** →
   **Public details** → set the statement descriptor to `DOWNLOADTHAT` (this is what
   shows up on the customer's bank/card statement; it's an account-level setting, not
   something set per payment).
3. **Confirm the payout bank account** is attached (same Settings area) — you said
   this is probably already done from an earlier step; just double check it once
   verification is live.
4. **Create the live webhook endpoint.** Dashboard → **Developers** → **Webhooks** →
   **Add endpoint**, same URL and events as the test one (`checkout.session.completed`,
   `customer.subscription.updated`, `customer.subscription.deleted`), but pick **live**
   mode in the mode toggle first. Copy the resulting `whsec_...` signing secret. Webhook
   endpoint creation is one of the few Stripe operations not exposed through my Stripe
   tools (probably deliberately, since the response carries a secret you should only
   ever see once, directly from Stripe) — this step has to happen by hand either way.
5. **2FA** on the Stripe account (you're checking this yourself).
6. **Update secrets**: in the Cloudflare Pages project, swap `STRIPE_SECRET_KEY` to the
   live `sk_live_...` key and `STRIPE_WEBHOOK_SECRET` to the new live `whsec_...`, then
   redeploy so the Functions pick them up.

**Steps I can do for you via the Stripe API, once you tell me verification is done**
(confirmed today that `PostProducts`, `PostPrices`, and `PostPaymentLinks` are all
live-mode-capable API calls my Stripe connection can make — this hasn't been tested
against an actually-verified account yet, since this one is still sandboxed):

7. Recreate the product + the 3 prices (monthly/yearly/lifetime) in live mode.
8. Recreate the 3 Payment Links, same redirect URLs as today
   (`https://downloadthat.pages.dev/success.html?session_id={CHECKOUT_SESSION_ID}`).
9. Update the 3 hardcoded Payment Link URLs in `pro/website/index.html` to the new
   live ones and push.

**On the "Kundennummer"/reconciliation reference you asked about:** the license
database (`licenses` table in D1) already stores, per purchase, the license key,
email, Stripe customer ID, subscription ID, and checkout session ID — that's already
a complete reconciliation key for refunds or a future invoice, no extra work needed.
The one thing that setup can't do is put a *per-customer* value directly on the
customer's own bank/card statement text — Stripe's `statement_descriptor_suffix` field
does exist, but only as a static, per-Payment-Link value (same text for every buyer of
that link), not a per-customer dynamic one. A truly dynamic per-customer statement
suffix would require switching from static Payment Links to creating a Checkout
Session via the API for every single purchase — a real architecture change, and not
needed for what you described (reconciliation/invoicing), since the D1 table already
covers that. Recommend leaving this as-is.

## What the Android app does with this (as of this commit)

- Free tier (no key, or an invalid/expired key): full quality, same as Pro — but rationed
  to `FREE_DAILY_DOWNLOAD_LIMIT` (currently 5) downloads per rolling 24h window (a
  completed/pending/in-progress job within the last 24h counts against it; cancelled/failed
  jobs don't).
- Pro tier (valid key): no daily limit.
- The license card in the app's web UI is entirely hidden on Termux/desktop — gating only
  applies when `MainActivity.kt` passes a `license_api_base` into `android_entry.start(...)`.
- **`MainActivity.kt`'s `LICENSE_API_BASE` now points at the real deployed URL**
  (`https://downloadthat.pages.dev`, set once the site above went live). It fails closed
  as free-tier on any network error talking to `/api/validate` (never "Pro" just because a
  check couldn't complete).
