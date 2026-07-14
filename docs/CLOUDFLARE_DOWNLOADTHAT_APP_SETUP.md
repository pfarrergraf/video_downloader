# Cloudflare setup for downloadthat.app

Status: domain registered as a separate Cloudflare zone on 2026-07-14.
Canonical origin: `https://downloadthat.app`.

## Isolation from gaistreich.com

`downloadthat.app` is a separate DNS zone. Do not create or modify records,
Workers routes, redirect rules or email settings inside the `gaistreich.com` zone.
The existing Pages project `downloadthat` remains the application origin; only a
custom domain is attached to it.

## Safe activation order

1. Keep `CANONICAL_REDIRECT_ENABLED=false` while the new domain is not verified.
2. Deploy the Play-first website to the existing `downloadthat.pages.dev` staging origin.
3. Verify `/download`, `/download/android`, `/api/health`, legal pages and removed Stripe routes.
4. In Cloudflare: **Workers & Pages → downloadthat → Custom domains → Set up a domain**.
5. Add `downloadthat.app`; let Cloudflare create the DNS record and certificate.
6. Add `www.downloadthat.app` to the same Pages project.
7. Verify both hosts over HTTPS and verify that the apex serves the new deployment.
8. Set `PUBLIC_BASE_URL=https://downloadthat.app` and `CANONICAL_REDIRECT_ENABLED=true`.
9. Redeploy, then verify 308 redirects from `www` and `downloadthat.pages.dev` for GET/HEAD.
10. Update Google Play, Pub/Sub and GitHub variables listed below.

Do not add a manual CNAME before associating the custom domain in Pages. Do not
configure a Workers Route for this domain; Pages Custom Domains is the owner.

## Cloudflare zone settings

- DNSSEC: enable and confirm status `Active`.
- SSL/TLS: keep Universal SSL enabled; use `Always Use HTTPS`.
- Minimum TLS version: 1.2.
- HSTS: the application sends one year with `includeSubDomains`; do not preload yet.
- Bot Fight Mode / managed challenges: leave off until native app API calls have been tested.
- Under Attack Mode: emergency control only, because challenges would break app API traffic.
- Registrar auto-renew: keep enabled and protect the Cloudflare account with MFA.

## Variables after custom-domain verification

GitHub environment/repository variables:

- `PUBLIC_BASE_URL=https://downloadthat.app`
- `CANONICAL_REDIRECT_ENABLED=true`
- `LICENSE_API_BASE_URL=https://downloadthat.app`
- `PLAY_RECONCILIATION_URL=https://downloadthat.app/api/play/reconcile`
- `PLAY_STORE_URL=<internal-test or public Play URL>`

Cloudflare Pages environment/secrets:

- `PUBLIC_BASE_URL=https://downloadthat.app`
- `CANONICAL_REDIRECT_ENABLED=true`
- `PLAY_RTDN_AUDIENCE=https://downloadthat.app/api/play/rtdn`
- existing Google Play, token-encryption and reconciliation secrets remain unchanged.

Google Cloud Pub/Sub push endpoint:

- `https://downloadthat.app/api/play/rtdn`

Google Play Console URLs:

- Privacy policy: `https://downloadthat.app/datenschutz.html`
- Website: `https://downloadthat.app/`

## Verification commands (PowerShell)

```powershell
(Invoke-WebRequest https://downloadthat.app/api/health -UseBasicParsing).Content
(Invoke-WebRequest https://downloadthat.app/download/android -UseBasicParsing).StatusCode
(Invoke-WebRequest https://www.downloadthat.app/download/android -MaximumRedirection 0 -SkipHttpErrorCheck).StatusCode
(Invoke-WebRequest https://downloadthat.pages.dev/download/android -MaximumRedirection 0 -SkipHttpErrorCheck).StatusCode
```

The last two checks should return `308` only after the redirect switch is enabled.
