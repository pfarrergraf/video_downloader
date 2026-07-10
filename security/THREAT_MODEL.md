# Threat Model — DownloadThat Affiliate Program (STRIDE)

## 1. System Context

```
                        ┌──────────────────────────┐
  Buyer's browser  ───► │  Cloudflare Pages         │ ───► Stripe (Checkout, Webhooks)
  Partner's browser───► │  + Pages Functions        │ ───► Resend (transactional email)
  Admin's browser  ───► │  (pro/website/functions)  │ ───► Cloudflare Turnstile (siteverify)
  Android app      ───► │        │                  │
  (App Link /claim)     │        ▼                  │
                        │   Cloudflare D1 (SQLite)   │
                        └──────────────────────────┘
```

Externe Abhängigkeiten: Stripe (Zahlungswahrheit), Resend (E-Mail-Zustellung für alle Auth-Flows),
Cloudflare Turnstile (Bot-Schutz), Cloudflare D1 (einzige Datenpersistenz), Cloudflare Pages/Functions
(Laufzeit- und Deployment-Plattform), GitHub Actions (CI/Supply Chain), Android OS Digital Asset Links
(App-Link-Verifikation).

## 2. Assets & Schutzbedarf

| Asset | Vertraulichkeit | Integrität | Verfügbarkeit |
|---|---|---|---|
| Auszahlungs-/Ledger-Daten (`affiliate_ledger`, `affiliate_payouts`) | Mittel | **Sehr hoch** | Hoch |
| Hash-Ketten (Ledger/Audit/Reconciliation/Integrity) | Niedrig | **Sehr hoch** | Hoch |
| Partner-Session-/Magic-Link-Tokens | **Hoch** (nur gehasht gespeichert) | Hoch | Mittel |
| Admin-Session | **Sehr hoch** | **Sehr hoch** | Hoch |
| Partner-PII (E-Mail, Name, Land) | Hoch | Mittel | Niedrig |
| Käufer-PII | **Sehr hoch** (darf Partner/Admin-UI nicht erreichen) | Hoch | Niedrig |
| Stripe-/Resend-/Turnstile-Secrets | **Sehr hoch** | **Sehr hoch** | Hoch |
| Android lokale Referral-Zuordnung (Slug + Zeitstempel) | Niedrig | Mittel (Fraud-relevant) | Niedrig |

## 3. Trust Boundaries

1. **Internet ↔ Cloudflare Pages Functions** — einzige extern erreichbare Grenze; jede `/api/*`-Route ist
   potenziell durch einen anonymen Angreifer erreichbar.
2. **Partner-Session ↔ Admin-Session** — durchgesetzt durch `role`-Feld in `affiliate_sessions`, geprüft in
   `getAffiliateSession(request, env, requiredRole)`. Verletzung wäre ein P0.
3. **Ein Partner ↔ ein anderer Partner** — durchgesetzt durch serverseitige Bindung an `session.affiliate_id`,
   nie clientseitig übergebene IDs (bestätigt, kein Finding).
4. **Cloudflare Functions ↔ Stripe** — Vertrauen basiert auf HMAC-Signaturprüfung des Webhooks
   (`verifyStripeSignature`, konstante Zeit über XOR-Akkumulation) und auf servergeneriertem
   `STRIPE_SECRET_KEY` für ausgehende API-Aufrufe. Die einzige Quelle der finanziellen Wahrheit ist Stripe
   selbst (`fetchStripeSessionReality`, `fetchStripeAffiliateReality`) — die lokale DB wird nie als alleinige
   Wahrheit für eine Provisionsfreigabe akzeptiert.
5. **Android-App ↔ Website** — die App vertraut nur genau zwei Hosts (`ALLOWED_HOSTS`) und genau einem Pfad
   (`/claim/<slug>`); umgekehrt vertraut die Website der App **nicht speziell** — ein `/p/<slug>?buy=1`-Aufruf
   aus der App durchläuft denselben serverseitigen Attributionscode wie jeder Browser-Klick.
6. **Registrierender Partner ↔ Admin-Dashboard** — war vor dieser Prüfung **nicht ausreichend** durchgesetzt
   (AFF-001): Partner-kontrollierte Felder erreichten den Admin-Browser ungefiltert. Jetzt durch HTML-Escaping
   geschlossen.

## 4. STRIDE

| Kategorie | Bedrohung | Betroffene Komponente | Kontrolle / Finding |
|---|---|---|---|
| **S**poofing | Gefälschter Stripe-Webhook | `api/webhook.js` | HMAC-Signaturprüfung mit 5-Min-Toleranzfenster (Replay-Schutz) — bestätigt korrekt implementiert |
| **S**poofing | Partner meldet sich als anderer Partner an | `partner/login.js` | Session-Token ist serverseitig gehasht, 32 zufällige Bytes, 20-Minuten-Magic-Link-Ablauf — kein Finding |
| **S**poofing | Android: gefälschte lokale App-Link-Zuordnung durch Drittapp | `AffiliateReferral.kt` | AFF-002 — architekturelle Grenze, kompensierend kontrolliert |
| **T**ampering | Manipulation von Ledger-/Audit-Einträgen im Nachhinein | `affiliate_ledger`, `affiliate_audit_log` | DB-Trigger verbieten UPDATE/DELETE; Hash-Kette macht Einfügungen mitten in der Kette erkennbar — bestätigt korrekt |
| **T**ampering | Partner manipuliert eigene Anzeige-/Codefelder, um Admin-Session zu kompromittieren | `partner/register.js` → `partner-admin.html` | **AFF-001, behoben** |
| **T**ampering | Doppelte Buchung durch Webhook-Replay/-Race | `_affiliate.js`, `_affiliate_events.js` | **AFF-003, behoben** |
| **R**epudiation | Admin bestreitet eine Auszahlungsfreigabe | `affiliate_audit_log` | Append-only, hash-verkettet, `actor`-Feld je Aktion — bestätigt ausreichend |
| **I**nformation Disclosure | Käufer-PII erreicht Partner-Dashboard | `partnerDashboardData()` | Bestätigt: keine Käuferfelder selektiert — kein Finding |
| **I**nformation Disclosure | Stacktrace-Leak über Fehlerantworten | `api/webhook.js` | **AFF-012, behoben** |
| **D**enial of Service | E-Mail-Bombing über Login-/Registrierungs-Endpunkte | `partner/login-request.js` u.a. | **AFF-004, behoben** |
| **D**enial of Service | Erschöpfung der Stripe-Checkout-Session-Paginierung (>10.000 Sessions) | `fetchStripeAffiliateReality` | Bewusst fail-closed: wirft Fehler statt partieller Reconciliation — bestätigt korrektes Verhalten, kein Finding |
| **E**levation of Privilege | Partner erreicht Admin-Endpunkt | alle `admin/*.js` | Serverseitige Rollenprüfung — kein Finding |
| **E**levation of Privilege | XSS als Privilegien-Eskalationsvektor (Partner → Admin-Handlungsfähigkeit) | siehe Tampering/AFF-001 | Cross-Kategorie-Bedrohung, in AFF-001 abgedeckt |

## 5. Abuse & Fraud Cases

Siehe `BUSINESS_LOGIC_ABUSE_CASES.md` für die vollständige, separat geforderte Fraud-Case-Analyse.

## 6. Single Points of Failure / kritische Abhängigkeiten

- **Cloudflare D1** ist die einzige Datenpersistenz — kein Replikat, keine Read-Replica-Strategie im Code
  sichtbar. Ausfall = vollständiger Funktionsausfall (aber fail-closed: `AFFILIATE_PROGRAM_ENABLED`-Flag und
  `affiliate_controls.payout_frozen`-Default sind beide sicher-geschlossen).
- **Stripe-API-Erreichbarkeit** ist Voraussetzung für jede Reconciliation und jeden Payout-Schritt
  (`runReconciliation` ruft Stripe live auf) — ein Stripe-Ausfall blockiert Auszahlungen vollständig, aber
  auch das ist die gewünschte Fail-Closed-Eigenschaft, nicht ein Fehler.
- **Resend** ist Single Point of Failure für **jede** Authentisierung (Registrierung, Login, Admin-Login) —
  kein alternativer Zustellweg vorgesehen. Ausfall = kompletter Login-Ausfall (Verfügbarkeits-, kein
  Integritätsrisiko).
- **`AFFILIATE_ADMIN_EMAIL`** ist ein einzelner Admin-Account ohne Fallback/zweite Person — siehe
  HANDOVER §5.4 (bereits als offener Punkt geführt: Notfallprozess bei kompromittierter Admin-E-Mail).
