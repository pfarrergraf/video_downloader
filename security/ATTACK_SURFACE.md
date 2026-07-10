# Attack Surface Map — Affiliate Program

## Öffentlich erreichbare HTTP-Endpunkte (kein Auth erforderlich)

| Route | Datei | Risiko-Notizen |
|---|---|---|
| `GET /partner.html` | statisch | Kein dynamischer Inhalt, kein Finding |
| `POST /api/partner/register` | `functions/api/partner/register.js` | Turnstile + Rate Limit (AFF-004 behoben); Eingabe `display_name`/`email` erreicht später Admin-DOM (AFF-001 behoben) |
| `POST /api/partner/login-request` | `functions/api/partner/login-request.js` | Turnstile + Rate Limit (AFF-004 behoben); generische Antwort verhindert Account-Enumeration |
| `GET /api/partner/verify?token=` | `functions/api/partner/verify.js` | Einmal-Token, 20 Min TTL, gehasht in DB |
| `GET /api/partner/login?token=` | `functions/api/partner/login.js` | wie oben; prüft zusätzlich `affiliate.status==='active'` |
| `POST /api/admin/login-request` | `functions/api/admin/login-request.js` | Turnstile + Rate Limit (AFF-004 behoben); nur eine feste Admin-Adresse akzeptiert |
| `GET /api/admin/login?token=` | `functions/api/admin/login.js` | wie oben |
| `GET /api/partner/config` | `functions/api/partner/config.js` | Liefert nur öffentliche Konfiguration (Turnstile Site Key, Provisionsstaffel) — kein Secret-Leak |
| `POST /api/create-checkout` | `functions/api/create-checkout.js` | Kein Turnstile (bewusst, Stripe selbst hat Betrugserkennung); Server bestimmt Provisionslogik, nicht der Client |
| `POST /api/webhook` | `functions/api/webhook.js` | Nur per HMAC-Signatur erreichbar; Stacktrace-Leak behoben (AFF-012) |
| `GET /.well-known/assetlinks.json` | `functions/.well-known/assetlinks.json.js` | Muss öffentlich sein (Android-Anforderung); Inhalt hängt von `ANDROID_CERT_SHA256` ab (AFF-009) |

## Session-geschützte Endpunkte (Partner-Rolle)

| Route | Datei |
|---|---|
| `GET /api/partner/me` | `functions/api/partner/me.js` — Daten strikt aus `session.affiliate_id` |
| `POST /api/partner/logout` | `functions/api/partner/logout.js` |
| `GET /partner-dashboard.html` | Cache-Control: no-store; XSS-gehärtet (AFF-001) |

## Session-geschützte Endpunkte (Admin-Rolle)

| Route | Datei |
|---|---|
| `GET /api/admin/overview` | `functions/api/admin/overview.js` |
| `POST /api/admin/reconcile` | `functions/api/admin/reconcile.js` |
| `POST /api/admin/payout-prepare` | `functions/api/admin/payout-prepare.js` |
| `POST /api/admin/payout-approve` | `functions/api/admin/payout-approve.js` — Maker-Checker via `prepared_by !== actor` |
| `POST /api/admin/payout-paid` | `functions/api/admin/payout-paid.js` — erfordert externe Referenz ≥3 Zeichen |
| `GET /partner-admin.html` | Cache-Control: no-store; XSS-gehärtet (AFF-001) |

Alle sechs Admin-Routen prüfen `getAffiliateSession(request, env, "admin")` identisch — kein Route-spezifisches
Vergessen der Prüfung gefunden (in jeder Datei einzeln verifiziert).

## Android-Angriffsfläche

- **Exportierte Komponenten:** `MainActivity` (`exported=true`, notwendig für Launcher/Share/App-Links) —
  einziger relevanter Vektor, siehe AFF-002. `DownloadService`, `FileProvider` sind `exported=false`.
- **App-Link-Pfad:** exakt `/claim/<slug>` auf zwei fest benannten Hosts, kein Wildcard.
- **WebView:** navigiert nie zu Fremdinhalten (`shouldOverrideUrlLoading` leitet alles außer `127.0.0.1` an
  den System-Browser weiter) — JS-Bridge dadurch für Angreiferinhalt unerreichbar.

## Cloudflare/Plattform-Angriffsfläche

- **D1-Binding `DB`:** ein einzelnes Binding, keine granulare Rechteteilung zwischen Lese-/Schreibpfaden
  (D1 kennt aktuell keine partiellen Berechtigungen pro Binding — architekturelle Grenze der Plattform, nicht
  des Codes).
- **Secrets:** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `TURNSTILE_SECRET_KEY`, `RESEND_API_KEY`,
  `REFERRAL_HASH_SALT` — alle als Cloudflare-Secrets vorgesehen, keines im Repository gefunden (verifiziert
  durch `test_affiliate_no_secrets.py`, jetzt inkl. Turnstile-Muster, AFF-006).
- **GitHub Actions:** siehe AFF-005 (Tag- statt SHA-Pinning, ungepinnter `wrangler`-Download).

## Externe Abhängigkeiten als indirekte Angriffsfläche

Stripe, Resend, Cloudflare Turnstile — alle drei nur über offizielle, dokumentierte APIs mit Secret-Key-Auth
angesprochen; kein eigener Code parst/vertraut ungeprüften Antworten dieser Dienste über die
HTTP-Statuscode-Prüfung (`if (!response.ok) throw ...`) hinaus in sicherheitsrelevanten Pfaden.
