# DownloadThat Partnerprogramm – Implementierung und Betrieb

Stand: 2026-07-10

## Produktregeln

| Bestätigter Verkauf | Provision |
|---:|---:|
| 1–10 | 2,00 EUR |
| 11–50 | 2,50 EUR |
| 51–100 | 3,00 EUR |
| 101–500 | 3,50 EUR |
| ab 501 | 4,00 EUR |

Alle Geldbeträge werden als ganzzahlige Euro-Cent-Werte gespeichert. Die Verkaufsnummer wird erst nach 30 Tagen und nach einer erneuten Stripe-Prüfung vergeben. Frühere Verkäufe werden nicht nachträglich aufgewertet.

Weitere feste Regeln:

- 180 Tage Last-Touch-Attribution; eine ausdrückliche Partnercode-Eingabe hat Vorrang.
- kein Kundenrabatt in Version 1;
- keine Provision für Eigenkäufe, Refunds, fehlgeschlagene Zahlungen oder Disputes;
- monatliche Auszahlung ab 50 EUR;
- nachträgliche Rückbuchungen erzeugen einen negativen Partnersaldo;
- Partner erhalten keine personenbezogenen Käuferdaten.

## Architektur

- **Website/Backend:** Cloudflare Pages + Pages Functions
- **Datenbank:** Cloudflare D1
- **Zahlung:** dynamisch erzeugte Stripe Checkout Sessions
- **E-Mail:** Resend Magic Links
- **Bot-Schutz:** Cloudflare Turnstile
- **Android:** verifizierte App Links ausschließlich für `/claim/<partner>`
- **Deployment:** bestehende GitHub-Integration des Pages-Projekts

Wichtige Dateien:

- `pro/website/functions/_affiliate.js` – Partner-, Provisions- und Auszahlungslogik
- `pro/website/functions/_affiliate_integrity.js` – unabhängiger Finanz- und Hash-Ketten-Abgleich
- `pro/website/functions/_affiliate_integrity_lock.js` – serialisierte Integrity Gates per D1-Lease
- `pro/website/functions/_affiliate_events.js` – Stripe-Refund-/Dispute-Lebenszyklus
- `pro/website/migrations/0002_...0008_...sql` – additive D1-Migrationen
- `pro/website/partner.html` – Registrierung und Login
- `pro/website/partner-dashboard.html` – Partner-Dashboard
- `pro/website/partner-admin.html` – Finanzkontrolle
- `android/.../AffiliateReferral.kt` – 180-Tage-App-Attribution

## Finanzkontrollen

### 1. Harte Invarianten

Jede Auszahlung wird sofort gesperrt, wenn mindestens eine Bedingung verletzt ist:

- ausgezahlte Summe ist größer als `Anzahl aller zugeordneten Lizenzen × 4,00 EUR`;
- ausgezahlte Summe ist größer als alle jemals qualifizierten Provisionen;
- eine Provision entspricht nicht exakt der Staffel;
- Partnerzähler stimmen nicht mit Einzelprovisionen überein;
- `lifetime_paid_cents` stimmt nicht mit tatsächlich als bezahlt gebuchten Auszahlungen überein;
- Auszahlungszuordnungen stimmen nicht centgenau mit Auszahlung und Clawback überein;
- Ledger-Einträge für Freigaben, Rückbuchungen oder Auszahlungen fehlen;
- eine bezahlte Auszahlung hat keine Bank-/SEPA-Referenz;
- doppelte Stripe-Payment-Intent-Zuordnungen existieren;
- eine Auszahlung basiert auf einem gesperrten Reconciliation-Snapshot;
- eine der Hash-Ketten wurde verändert oder unterbrochen.

### 2. Relative 5-Prozent-Sperre

Zusätzlich werden unabhängige Summen aus Stripe, Lizenzen, Provisionen und Ledger verglichen. Eine Abweichung von **mehr als 500 Basispunkten = 5,00 %** setzt global `affiliate_controls.payout_frozen = 1`.

Verglichen werden:

- gültige Stripe-Zahlungen gegen aktive zugeordnete Lizenzen;
- Stripe-Nettoerlös gegen lokal erkannten Erlös;
- erwartete Staffelprovision gegen gespeicherte Provision;
- erwarteter Ledger-Saldo gegen tatsächlichen Ledger-Saldo;
- zugeordnete Lizenzen gegen Provisionsdatensätze.

### 3. Manipulationserkennung

Vier unabhängige, unveränderliche Hash-Ketten werden geprüft:

1. `affiliate_ledger`
2. `affiliate_audit_log`
3. `affiliate_reconciliation_snapshots`
4. `affiliate_integrity_checks`

Update und Delete sind per SQLite-Trigger verboten. Korrekturen erfolgen ausschließlich über kompensierende Buchungen.

Reconciliation und Integrity Gate besitzen getrennte Datenbank-Leases. Damit kann immer nur eine Instanz die jeweilige Hash-Kette fortschreiben; parallele Adminaufrufe verzweigen die Kette nicht. Ein belegter oder abgelaufener Prüflauf führt nicht zu einer Auszahlung, sondern zu einem kontrollierten `409`-Fehler beziehungsweise einer fortbestehenden Sperre.

### 4. Auszahlungsschritte

1. **Prepare:** System erzeugt einen Auszahlungsvorschlag aus einzelnen offenen Provisionen.
2. **Approve:** Admin bestätigt den Vorschlag; derselbe Akteur kann den Systemschritt nicht ersetzen.
3. **Paid:** Erst nach realer SEPA-Überweisung wird mit externer Bankreferenz gebucht.
4. Vor und nach jedem Schritt laufen Stripe-Reconciliation und ein serialisiertes Integrity Gate.

Der Code überweist kein Geld selbst. Dadurch kann ein kompromittiertes Webkonto keine Banküberweisung auslösen. Die technische Trennung ist ein System-/Mensch-Maker-Checker-Verfahren; sie ersetzt bei wachsendem Zahlungsvolumen keine zweite menschliche Freigabeperson oder Bankfreigabe.

## Benötigte Cloudflare-Variablen

### Secrets

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `TURNSTILE_SECRET_KEY`
- `RESEND_API_KEY`
- `REFERRAL_HASH_SALT` – mindestens 32 zufällige Bytes

### Nicht geheime Variablen

- `AFFILIATE_PROGRAM_ENABLED=false` während Migration und Tests
- `PUBLIC_BASE_URL=https://downloadthat.pages.dev` oder endgültige Produktionsdomain
- `STRIPE_PRICE_ID=price_...`
- `TURNSTILE_SITE_KEY=...`
- `PARTNER_FROM_EMAIL=DownloadThat Partner <partner@...>`
- `AFFILIATE_ADMIN_EMAIL=...`
- `ANDROID_CERT_SHA256=AA:BB:...` – mehrere Fingerprints kommasepariert
- `ENVIRONMENT=production`

Keine Secrets in GitHub-Dateien, HTML, Android-Code oder Commit-Nachrichten eintragen.

## Stripe-Webhook-Ereignisse

Der vorhandene Endpoint `/api/webhook` muss in Live- und Testmodus erhalten:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `charge.refunded`
- `charge.dispute.created`
- `charge.dispute.closed`
- vorhandene Subscription-Ereignisse dürfen bestehen bleiben

## D1-Migration

Die SQL-Dateien in lexikographischer Reihenfolge einmalig anwenden:

```text
0002_affiliate_program.sql
0003_affiliate_concurrency.sql
0004_affiliate_payout_allocations.sql
0005_affiliate_admin_auth.sql
0006_reconciliation_dimensions.sql
0007_affiliate_integrity_checks.sql
0008_affiliate_integrity_lock.sql
```

Die Migration startet absichtlich mit globaler Auszahlungssperre. Erst ein erfolgreicher Stripe-Abgleich plus Integrity Gate darf sie lösen.

## Sicherer Rollout

1. Datenbanksicherung/Export erstellen.
2. `AFFILIATE_PROGRAM_ENABLED=false` setzen.
3. Migrationen anwenden.
4. Secrets und Variablen setzen.
5. Test-Webhook-Ereignisse aktivieren.
6. Testpartner registrieren und E-Mail bestätigen.
7. Stripe-Testkauf durchführen.
8. vollständigen Refund, Teil-Refund sowie gewonnenen und verlorenen Dispute testen.
9. 30-Tage-Prüfung in Staging mit kontrollierten Testzeitpunkten validieren.
10. Adminseite öffnen und Reconciliation starten.
11. Nur bei Reconciliation- und Integrity-Status `ok` Feature Flag aktivieren.
12. Erst danach Live-Webhook-Ereignisse und echte Partner zulassen.

## Rollback

- sofort `AFFILIATE_PROGRAM_ENABLED=false` setzen;
- bestehender Lizenz- und Payment-Link-Pfad bleibt als Fallback im Frontend erhalten;
- Auszahlungen bleiben in D1 gesperrt;
- additive Tabellen und Lizenzspalten nicht löschen;
- Ursache anhand unveränderlicher Snapshots und Audit-Kette untersuchen;
- nach Korrektur neuen Reconciliation- und Integrity-Snapshot erzeugen.

## Automatisierte Prüfung

Pull Requests führen aus:

- SQLite-Migrationen und Constraint-Tests;
- Python-Security- und Secret-Leak-Tests;
- Node-Syntaxprüfung sämtlicher Cloudflare Functions;
- Unit-Tests der Centstaffel und absoluten 4-EUR-Obergrenze;
- Kotlin-Kompilierung der Android-App-Link-Integration.
