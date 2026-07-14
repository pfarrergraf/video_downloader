# Data Flow and Trust Boundaries — Historical Affiliate Program

> Historical evidence only. The affiliate program and Stripe checkout are not
> part of the Google-Play-first target deployment. The current flow and trust
> boundaries are authoritative in `GOOGLE_PLAY_SECURITY_ARCHITECTURE.md`.

## 1. Klick → Attribution

```
Partner-Link (Browser/App) → GET /p/<slug> → recordAffiliateClick()
  → affiliate_clicks (ip_hash, user_agent_hash = SHA-256(REFERRAL_HASH_SALT:wert))
  → Cookie dt_affiliate_click gesetzt (180 Tage TTL, HttpOnly/Secure/SameSite=Lax)
```
IP-Adresse und User-Agent werden **nie im Klartext** gespeichert, nur gesalzen gehasht — Datenminimierung
bestätigt.

## 2. Checkout → Provisions-Draft

```
Buyer klickt "Kaufen" → POST /api/create-checkout
  → resolveAffiliateAttribution(explicitCode || cookie)
     Regel: expliziter Code > Cookie > keine Attribution
  → affiliate_checkout_intents (Zuordnung + Widerrufsentscheidung)
  → Stripe Checkout Session (metadata.affiliate_id, metadata.checkout_intent_id)
```
Trust Boundary: Der Client kann `partner_code` frei setzen, aber **nicht** `affiliate_id` oder
Provisionshöhe — beides wird ausschließlich serverseitig über die DB-Abfrage in
`resolveAffiliateAttribution` aufgelöst. Bestätigt: `create-checkout.js` enthält keine
`commission_cents`-Referenz (durch `test_checkout_and_webhook_never_trust_browser_commission_amounts`
erzwungen).

## 3. Stripe-Webhook → Provisions-Zeile

```
Stripe → POST /api/webhook (Stripe-Signature Header)
  → verifyStripeSignature() [HMAC-SHA256, 5-Min-Toleranz]
  → handleAffiliateCheckoutPaid() → affiliate_commissions (status='pending', eligible_at=+30 Tage)
```
Trust Boundary: Alles vor der Signaturprüfung ist **unauthentifizierter externer Input**. Nach erfolgreicher
Signaturprüfung wird Stripes Payload als maßgeblich behandelt — aber selbst dann wird der tatsächliche
Zahlungsstatus bei Freigabe **erneut live bei Stripe abgefragt** (`fetchStripeSessionReality`), die
Webhook-Payload allein reicht für eine Provisionsfreigabe nicht aus.

## 4. Reconciliation (30 Tage später) → Provisions-Freigabe

```
Admin/Cron → runReconciliation()
  → approveEligibleCommissions() [Live-Stripe-Abfrage je Commission]
  → localFinanceReality() vs. fetchStripeAffiliateReality() [zwei unabhängige Quellen]
  → 5,00-%-Abweichungsvergleich → affiliate_controls.payout_frozen
```
Trust Boundary: Zwei **unabhängig berechnete** Wahrheiten (lokale DB-Aggregation vs. Live-Stripe-API)
müssen übereinstimmen. Keine der beiden Seiten wird blind vertraut.

## 5. Auszahlung (Maker-Checker)

```
System (actor="system-payout-engine") → prepareAffiliatePayout() → status='prepared'
Admin (actor="admin:<email>")          → approveAffiliatePayout() → status='approved'
Admin (extern verifizierte SEPA-Überweisung) → markAffiliatePayoutPaid(externalReference) → status='paid'
```
Trust Boundary: Jeder Schritt erzwingt erneut `runReconciliation()` + `requireLockedIntegrityForPayout()`.
Der Code selbst überweist **kein Geld** — die reale Banküberweisung ist ein externer, manueller Schritt
(Kompromittierung des Web-Admin-Kontos kann daher keine reale Zahlung auslösen, nur eine
"paid"-Buchung anfordern, die einen bereits erfolgten externen Vorgang **dokumentiert**).

## 6. Partner-/Admin-Dashboard-Anzeige

```
Partner-Session → GET /api/partner/me → partnerDashboardData(session.affiliate_id)
Admin-Session    → GET /api/admin/overview → alle Partner/Payouts/Reconciliations
  → Browser: innerHTML-Rendering (vor AFF-001-Fix: ungefiltert; danach: esc()-escaped)
```
Trust Boundary (die durch AFF-001 verletzt war): Partner-kontrollierte Daten (`display_name`, `email`,
`code`) überqueren die Grenze zwischen "Partner-Vertrauensstufe" und "Admin-Browser-Ausführungskontext"
ohne Kodierung. Jetzt durch HTML-Escaping geschlossen.

## 7. Android → Website

```
Android App Link /claim/<slug> → AffiliateReferral.capture() → SharedPreferences (MODE_PRIVATE)
  → rewritePricingUrl() → /p/<slug>?buy=1 (identischer Weg wie jeder Browser-Klick, Abschnitt 1)
```
Trust Boundary: Die App vertraut nur zwei Hosts/einem Pfad; die Website vertraut der App **nicht speziell** —
ein App-generierter Klick durchläuft exakt dieselbe serverseitige Attributionslogik wie jeder andere Klick.
Siehe AFF-002 für die Grenze dieser Boundary auf Android-Seite.

## Zusammenfassung der Trust Boundaries

| Grenze | Kontrolle | Status |
|---|---|---|
| Internet → `/api/*` | Turnstile (Auth-Endpunkte) + Rate Limit (neu) + serverseitige Eingabevalidierung | Gehärtet (AFF-004) |
| Stripe → Webhook | HMAC-Signatur + Live-Reality-Check bei Freigabe | Bestätigt korrekt |
| Partner-Session → Admin-Funktion | Rollenprüfung serverseitig | Bestätigt korrekt |
| Partner-Daten → Admin-Browser-DOM | HTML-Escaping | **Gehärtet (AFF-001)** |
| Android-App → Website-Backend | Kein besonderes Vertrauen, gleiche Pipeline wie Browser | Bestätigt korrekt |
| Drittapp (Android) → App-Link-Empfang | Keine (plattformbedingt) | Dokumentiertes Restrisiko (AFF-002) |
