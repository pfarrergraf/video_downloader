# PCI DSS Scope Assessment — Affiliate Program

> **HISTORICAL EVIDENCE:** Bewertet das inzwischen entfernte Affiliate-/Stripe-System.
> Nicht als aktuellen Produktionsstatus verwenden; maßgeblich ist
> `CURRENT_SECURITY_IMPLEMENTATION_STATUS.md`.

**Wichtig:** Diese Bewertung stellt **keine** verbindliche PCI-DSS-Scope-Bestätigung dar. Der tatsächliche
Scope und die anzuwendende SAQ-Kategorie müssen verbindlich mit Stripe bzw. dem Acquirer geklärt werden
(HANDOVER §9.5, weiterhin offen).

## Kartendaten-Fluss (tatsächlicher Code-Nachweis)

1. Der Kaufabschluss läuft ausschließlich über von Stripe **gehostete** Checkout Sessions
   (`stripePost("/checkout/sessions", ...)` / `createStripeSession(...)` in `create-checkout.js`).
2. Der Browser des Käufers wird per `session.url` **zu Stripes eigener Domain weitergeleitet**
   (`checkout.stripe.com`, ersichtlich an `form-action 'self' https://checkout.stripe.com` in `_headers`).
3. Kartendaten werden **zu keinem Zeitpunkt** von DownloadThat-Code entgegengenommen, verarbeitet,
   übertragen oder gespeichert — bestätigt durch vollständige Durchsicht aller `functions/**`-Dateien:
   keine Stelle liest, sendet oder speichert PAN/CVV/Ablaufdatum.
4. Rückkanal ist ausschließlich der signaturgeprüfte Stripe-Webhook (`api/webhook.js`), der nur
   Metadaten (Beträge, Status, IDs) verarbeitet, keine Kartendaten.
5. `affiliate_commissions`/`affiliate_ledger`/`licenses` speichern ausschließlich Cent-Beträge, Stripe-IDs
   und Status — keine Kartendaten in D1.

## Vorläufige Einschätzung (nicht verbindlich)

Dieses Muster (vollständig gehostetes Stripe Checkout, keine eigene Kartendatenverarbeitung/-speicherung)
entspricht typischerweise **SAQ A** oder **SAQ A-EP** (abhängig davon, ob die Checkout-Seite selbst
JavaScript einbindet, das mit der Zahlungsseite interagiert — hier: nein, die Weiterleitung erfolgt komplett
serverseitig über `session.url`). Die endgültige SAQ-Zuordnung ist **ausschließlich durch Stripe/den
Acquirer** verbindlich festzulegen.

## Was diese Prüfung NICHT leisten kann

- Keine Aussage „PCI-zertifiziert“ oder „vollständig außerhalb des PCI-Scope“.
- Keine Bewertung von Stripes eigener PCI-Compliance (liegt bei Stripe als PCI Level 1 Service Provider).
- Keine Bewertung von Netzwerksegmentierung auf Cloudflare-Infrastrukturebene (außerhalb des Code-Scopes).

## Empfehlung vor Produktionsfreigabe

Verbindliche SAQ-Bestätigung mit Stripe einholen und dokumentieren (HANDOVER §5.3, weiterhin offen).
