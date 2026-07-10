# DownloadThat – Handover, Security Readiness und Produktionsfreigabe

**Stand:** 10. Juli 2026  
**Repository:** `pfarrergraf/video_downloader`  
**Branch:** `feature/affiliate-partner-program`  
**Pull Request:** `#4 – Add secure creator and affiliate partner program`  
**Status:** Implementiert, CI-validiert und reviewbereit; **noch nicht produktiv aktiviert**.

---

## 1. Zweck dieses Dokuments

Dieses Dokument übergibt die Implementierung des DownloadThat Creator- und Affiliate-Partnerprogramms an die nächste technische Instanz. Es beschreibt:

1. was implementiert wurde;
2. was nachweislich geprüft wurde;
3. was noch aussteht;
4. welche Mindestprüfungen vor Produktion verpflichtend sind;
5. welche vertieften Sicherheits-, Compliance- und Audit-Readiness-Prüfungen durchzuführen sind;
6. welche Handlungen CloudCode / Claude Code ohne weitere Rückfrage durchführen darf;
7. welche Handlungen eine zusätzliche ausdrückliche Freigabe benötigen;
8. welche Voraussetzungen für eine Produktionsfreigabe gelten.

In diesem Dokument bezeichnet **„Security Agent“** CloudCode, Claude Code, Codex oder einen vergleichbaren autorisierten KI-Coding-Agenten, der im Auftrag des Repository-Inhabers an diesem Projekt arbeitet.

---

## 2. Zusammenfassung des erreichten Stands

Das Partnerprogramm wurde als additive Erweiterung der bestehenden DownloadThat-Webseite, Cloudflare-Pages-Functions, D1-Datenbank und Android-App implementiert.

### 2.1 Geschäftslogik

Die Provision wird als unveränderlicher ganzzahliger Euro-Cent-Betrag berechnet:

| Bestätigter Verkauf des Partners | Provision je Verkauf |
|---:|---:|
| 1–10 | 2,00 EUR |
| 11–50 | 2,50 EUR |
| 51–100 | 3,00 EUR |
| 101–500 | 3,50 EUR |
| ab 501 | 4,00 EUR |

Zusätzlich gelten:

- 180 Tage Last-Touch-Attribution;
- ausdrücklich eingegebener Partnercode hat Vorrang;
- 30 Tage Prüfzeit vor Freigabe einer Provision;
- Auszahlung grundsätzlich monatlich ab 50,00 EUR;
- kein Kundenrabatt in Version 1;
- keine Provision für Eigenkäufe, fehlgeschlagene Zahlungen, Refunds, Teil-Refunds, Betrug oder verlorene Disputes;
- bereits ausgezahlte, später rückabgewickelte Provisionen erzeugen einen negativen Partnersaldo;
- Partner erhalten keine personenbezogenen Käufer- oder Zahlungsdaten.

### 2.2 Partnerfunktionen

Implementiert wurden:

- öffentliche Partnerprogramm-Seite;
- Partner-Selbstregistrierung;
- E-Mail-Verifizierung;
- Magic-Link-Login ohne Passwort;
- Partner-Dashboard;
- persönlicher Partnerlink;
- Direktkauf-Link;
- Partnercode;
- Android-Zuordnungslink `/claim/<partner>`;
- aggregierte Klick-, Checkout-, Verkaufs- und Auszahlungsstatistiken;
- Partnerbedingungen und partnerbezogene Datenschutzhinweise.

### 2.3 Checkout und Stripe

Implementiert wurden:

- dynamisch und serverseitig erzeugte Stripe Checkout Sessions;
- serverseitige Validierung der Attribution;
- Speicherung der Widerrufsentscheidung und Textversion;
- Signaturprüfung der Stripe-Webhooks;
- Behandlung von:
  - `checkout.session.completed`;
  - `checkout.session.async_payment_succeeded`;
  - `checkout.session.async_payment_failed`;
  - `charge.refunded`;
  - `charge.dispute.created`;
  - `charge.dispute.closed`;
- verzögerte Zahlverfahren wie SEPA erzeugen erst nach bestätigtem Zahlungseingang eine finanzielle Provisionszeile;
- Teil-Refunds reduzieren den lokal erkannten Umsatz auf den tatsächlichen Stripe-Nettobetrag;
- vollständige Refunds stornieren die zugehörige Lizenz;
- Refunds und Disputes entfernen beziehungsweise reversieren die Affiliate-Provision;
- gewonnene Disputes können kontrolliert wiederhergestellt werden.

### 2.4 Finanzkontrollsystem

Implementiert wurden:

- ganzzahlige Cent-Buchführung;
- append-only Affiliate-Ledger;
- append-only Audit-Protokoll;
- unveränderliche Reconciliation-Snapshots;
- unveränderliche Integrity-Check-Snapshots;
- SHA-256-Hash-Ketten für alle vier Nachweisketten;
- Datenbanktrigger gegen Update und Delete der unveränderlichen Tabellen;
- kompensierende Gegenbuchungen statt nachträglicher Manipulation;
- getrennte D1-Leases für Reconciliation und Integrity Gate;
- centgenaue Zuordnung jeder Auszahlung zu einzelnen Provisionen;
- Rückbuchungs- und Clawback-Salden;
- System-/Admin-Maker-Checker-Prozess;
- Bank-/SEPA-Referenz als Pflichtfeld beim Verbuchen einer realen Auszahlung;
- globale Auszahlungssperre.

### 2.5 Absolute Auszahlungsschranken

Das System prüft unter anderem zwingend:

```text
Gesamtauszahlungen <= Anzahl aller zugeordneten Lizenzen * 4,00 EUR
```

und:

```text
Gesamtauszahlungen <= Summe aller tatsächlich qualifizierten Provisionen
```

Eine Verletzung einer harten Finanzinvariante führt unabhängig von Prozentwerten sofort zur globalen Auszahlungssperre.

### 2.6 Fünf-Prozent-Reconciliation

Die folgenden Quellen werden unabhängig gegeneinander abgeglichen:

- gültige Stripe-Zahlungen;
- zugeordnete Lizenzen;
- Stripe-Nettoerlös;
- lokal erkannter Nettoerlös;
- Provisionsdatensätze;
- erwartete Provisionsstaffel;
- Ledger-Saldo;
- bisherige Auszahlungen;
- Auszahlungszuordnungen;
- Rückbuchungs- und Clawback-Salden.

Bei einer aggregierten Abweichung von **mehr als 500 Basispunkten beziehungsweise 5,00 Prozent** wird `affiliate_controls.payout_frozen = 1` gesetzt.

### 2.7 Android

Implementiert wurden:

- eng begrenzte, verifizierbare Android App Links ausschließlich für `/claim/<partner>`;
- Speicherung nur des öffentlichen Partner-Slugs und Erfassungszeitpunkts;
- Ablauf nach 180 Tagen;
- Umschreiben ausschließlich des eigenen DownloadThat-Pro-Kauflinks;
- Erhaltung der tatsächlich verwendeten DownloadThat-Domain;
- keine allgemeine Übernahme fremder URLs;
- keine neuen Android-Berechtigungen.

### 2.8 Sicherheitsbasis

Implementiert wurden:

- Cloudflare Turnstile für Registrierung und Login;
- gehashte Magic-Link-Tokens;
- gehashte Sitzungs-Tokens;
- HttpOnly-, Secure- und SameSite-Cookies;
- Content Security Policy;
- HSTS;
- `X-Content-Type-Options`;
- Frame-Schutz;
- restriktive Permissions Policy;
- `Cache-Control: no-store` für sensible Oberflächen;
- Secret-Leak-Test in CI;
- keine Secrets im Repository;
- Feature-Flag `AFFILIATE_PROGRAM_ENABLED=false` als Fail-Closed-Standard.

---

## 3. Wichtige Dateien

### Backend und Kontrolllogik

- `pro/website/functions/_affiliate.js`
- `pro/website/functions/_affiliate_events.js`
- `pro/website/functions/_affiliate_refund_sync.js`
- `pro/website/functions/_affiliate_integrity.js`
- `pro/website/functions/_affiliate_integrity_lock.js`
- `pro/website/functions/api/webhook.js`
- `pro/website/functions/api/create-checkout.js`

### Partner- und Adminoberflächen

- `pro/website/partner.html`
- `pro/website/partner-dashboard.html`
- `pro/website/partner-admin.html`
- `pro/website/partnerbedingungen.html`
- `pro/website/partner-datenschutz.html`

### Datenbank

- `pro/website/migrations/0002_affiliate_program.sql`
- `pro/website/migrations/0003_affiliate_concurrency.sql`
- `pro/website/migrations/0004_affiliate_payout_allocations.sql`
- `pro/website/migrations/0005_affiliate_admin_auth.sql`
- `pro/website/migrations/0006_reconciliation_dimensions.sql`
- `pro/website/migrations/0007_affiliate_integrity_checks.sql`
- `pro/website/migrations/0008_affiliate_integrity_lock.sql`

### Android

- `android/app/src/main/java/de/classydl/app/AffiliateReferral.kt`
- `android/app/src/main/java/de/classydl/app/MainActivity.kt`
- `android/app/src/main/AndroidManifest.xml`
- `pro/website/functions/.well-known/assetlinks.json.js`

### Tests und Dokumentation

- `.github/workflows/affiliate-program.yml`
- `tests/test_affiliate_program.py`
- `tests/test_affiliate_no_secrets.py`
- `pro/website/tests/affiliate_finance.test.mjs`
- `docs/AFFILIATE_PROGRAM_IMPLEMENTATION.md`
- `HANDOVER.md`

---

## 4. Bereits durchgeführte Prüfungen

Der Implementierungsstand vor diesem reinen Dokumentations-Commit wurde durch den Workflow **Affiliate program validation**, Lauf `#21`, vollständig grün validiert.

Bestanden wurden:

- Anwendung aller D1-/SQLite-Migrationen auf einer frischen Testdatenbank;
- Datenbank-Constraints;
- append-only Trigger;
- Provisionsstaffel und Staffelgrenzen;
- absolute 4-EUR-Obergrenze;
- Finance- und Security-Tests;
- Secret-Leak-Test;
- Syntaxprüfung sämtlicher Cloudflare Functions;
- Node-Unit-Tests;
- Prüfung der Android-Berechtigungen;
- Kotlin-Kompilierung der Android-Referral-Integration.

Diese Prüfungen sind wichtig, ersetzen aber **keinen unabhängigen Penetrationstest, keine Produktionsprüfung, keine Datenschutz-/Rechtsprüfung und keine formelle Zertifizierung oder Attestierung**.

---

## 5. Was noch nicht erledigt oder nicht nachgewiesen ist

Die folgenden Punkte sind ausdrücklich offen:

### 5.1 Deployment und Infrastruktur

- [ ] Pull Request nach Review in `master` mergen.
- [ ] D1-Produktivdatenbank vollständig sichern und Export verifizieren.
- [ ] Migrationen `0002` bis `0008` in Staging anwenden.
- [ ] Migrationen `0002` bis `0008` erst nach erfolgreichem Staging-Test in Produktion anwenden.
- [ ] Rollback beziehungsweise Wiederherstellung aus Backup praktisch testen.
- [ ] Cloudflare Pages-/Functions-Konfiguration kontrollieren.
- [ ] Produktionsdomain und DNS vollständig verifizieren.
- [ ] `downloadthat.gaistreich.com` einschließlich TLS, Redirects, CSP und App Links prüfen.
- [ ] Cloudflare-Logs, Alarme und Aufbewahrung konfigurieren.
- [ ] Regelmäßige Bereinigung abgelaufener Tokens, Sessions und nicht mehr benötigter Klickdaten implementieren oder planen.
- [ ] Regelmäßige automatisierte Reconciliation planen; gegenwärtig ist die Adminausführung maßgeblich.

### 5.2 Secrets und Umgebungsvariablen

Folgende Werte müssen außerhalb des Repositories gesetzt und geprüft werden:

- [ ] `STRIPE_SECRET_KEY`
- [ ] `STRIPE_WEBHOOK_SECRET`
- [ ] `STRIPE_PRICE_ID`
- [ ] `TURNSTILE_SECRET_KEY`
- [ ] `TURNSTILE_SITE_KEY`
- [ ] `RESEND_API_KEY`
- [ ] `PARTNER_FROM_EMAIL`
- [ ] `AFFILIATE_ADMIN_EMAIL`
- [ ] `REFERRAL_HASH_SALT` mit ausreichender Entropie
- [ ] `PUBLIC_BASE_URL`
- [ ] `ANDROID_CERT_SHA256`
- [ ] `ENVIRONMENT=production`
- [ ] zunächst `AFFILIATE_PROGRAM_ENABLED=false`

### 5.3 Stripe

- [ ] Test- und Live-Webhook-Endpunkte getrennt konfigurieren.
- [ ] Alle benötigten Ereignistypen aktivieren.
- [ ] Webhook-Signaturprüfung mit echtem Stripe-Testevent verifizieren.
- [ ] Idempotenz bei mehrfacher Zustellung desselben Events prüfen.
- [ ] Zustellung in falscher Reihenfolge prüfen.
- [ ] verspätete Zustellung prüfen.
- [ ] verlorene beziehungsweise manuell erneut gesendete Events prüfen.
- [ ] SEPA-Erfolg und SEPA-Fehlschlag im Testmodus prüfen.
- [ ] Voll-Refund, Teil-Refund und mehrere Teil-Refunds prüfen.
- [ ] Dispute `created`, verloren und gewonnen prüfen.
- [ ] prüfen, ob die bestehende Lizenzlogik bei verzögerten Zahlungen den gewünschten Produktzugang gewährt oder bis Zahlungseingang einschränken soll.
- [ ] PCI-DSS-Scope mit Stripe beziehungsweise Acquirer verbindlich bestimmen; gehosteter Stripe Checkout reduziert typischerweise den Scope, hebt die Händlerpflichten aber nicht automatisch vollständig auf.

### 5.4 E-Mail und Identität

- [ ] Absenderdomain bei Resend verifizieren.
- [ ] SPF, DKIM und DMARC prüfen.
- [ ] Magic-Link-Zustellung, Ablauf und Einmalverwendung prüfen.
- [ ] Login-Ratenbegrenzung und Missbrauchsszenarien testen.
- [ ] Kontosperrung, Reaktivierung und E-Mail-Änderung als administrativen Prozess definieren.
- [ ] Adminzugang durch zusätzliche starke Authentisierung beziehungsweise Cloudflare Access absichern.
- [ ] Notfallprozess bei kompromittierter Admin-E-Mail definieren.

### 5.5 Auszahlung und Buchhaltung

- [ ] echte Bank-/SEPA-Auszahlung ist nicht automatisiert und muss als kontrollierter Prozess definiert werden.
- [ ] zweite menschliche Freigabeperson oder Bank-Vier-Augen-Freigabe für wachsende Volumina einführen.
- [ ] Auszahlungsempfängerdaten, Steuerdaten und Rechnungs-/Gutschriftverfahren definieren.
- [ ] steuerliche Behandlung der Provisionen professionell prüfen.
- [ ] Behandlung ausländischer Partner und gegebenenfalls Quellensteuer-/Umsatzsteuerfragen klären.
- [ ] monatlichen Abschluss-, Reconciliation- und Freigabeprozess dokumentieren.
- [ ] maximale Auszahlung pro Partner und pro Abrechnungsperiode als zusätzliche Risikogrenze erwägen.
- [ ] Alarmierung bei ungewöhnlichen Conversion-, Refund-, Dispute- und Auszahlungsmustern einrichten.

### 5.6 Recht und Datenschutz

- [ ] Partnerbedingungen anwaltlich prüfen lassen.
- [ ] Datenschutzhinweise und allgemeine Datenschutzerklärung prüfen und zusammenführen.
- [ ] Auftragsverarbeitungsverträge beziehungsweise Data Processing Agreements mit Cloudflare, Stripe, Resend und weiteren Dienstleistern prüfen.
- [ ] Verzeichnis der Verarbeitungstätigkeiten ergänzen.
- [ ] Rechtsgrundlagen und Löschfristen dokumentieren.
- [ ] Drittlandtransfers und eingesetzte Garantien dokumentieren.
- [ ] prüfen, ob eine Datenschutz-Folgenabschätzung erforderlich ist.
- [ ] Betroffenenrechte-Prozess definieren und testen.
- [ ] Cookie-/Tracking-Einordnung rechtlich prüfen.
- [ ] Werbekennzeichnung und Influencer-Vorgaben für die Zielmärkte prüfen.

### 5.7 Betrieb

- [ ] Incident-Response-Plan erstellen.
- [ ] Security-Kontakt und Vulnerability-Disclosure-Prozess definieren.
- [ ] Backup- und Restore-Ziele, RPO und RTO festlegen.
- [ ] Monitoring und Alarmierung für Webhook-Fehler, Reconciliation-Sperren, Hash-Ketten-Fehler und ungewöhnliche Auszahlungen einrichten.
- [ ] Runbook für Auszahlungssperren erstellen.
- [ ] Runbook für kompromittierte Partnerkonten erstellen.
- [ ] Runbook für Stripe-/Cloudflare-Ausfall erstellen.
- [ ] Abhängigkeiten, SBOM und Patchprozess dauerhaft pflegen.
- [ ] Verantwortlichkeiten und Stellvertretungen festlegen.

---

## 6. Verbindliche Mindestprüfung vor Aktivierung

Die folgenden Prüfungen sind Mindestanforderungen. Ohne dokumentiertes Ergebnis darf `AFFILIATE_PROGRAM_ENABLED` nicht auf `true` gesetzt werden.

### 6.1 Funktionsprüfung

- [ ] Registrierung mit gültigen und ungültigen Eingaben.
- [ ] doppelte E-Mail, doppelter Code und reservierte Codes.
- [ ] E-Mail-Verifizierung.
- [ ] abgelaufener und bereits verwendeter Magic Link.
- [ ] Partnerlogin und Logout.
- [ ] Partner-Dashboard ohne Zugriff auf fremde Partnerdaten.
- [ ] Admin-Dashboard nur für den Admin.
- [ ] Partnerlink, Direktkauf-Link, Code und Android-Claim-Link.
- [ ] Ablauf der Attribution nach 180 Tagen.
- [ ] Vorrang eines ausdrücklich eingegebenen Partnercodes.
- [ ] Eigenkauf-Erkennung.

### 6.2 Provisionsstaffel

Mindestens die Grenzwerte prüfen:

- [ ] Verkauf 1 = 2,00 EUR.
- [ ] Verkauf 10 = 2,00 EUR.
- [ ] Verkauf 11 = 2,50 EUR.
- [ ] Verkauf 50 = 2,50 EUR.
- [ ] Verkauf 51 = 3,00 EUR.
- [ ] Verkauf 100 = 3,00 EUR.
- [ ] Verkauf 101 = 3,50 EUR.
- [ ] Verkauf 500 = 3,50 EUR.
- [ ] Verkauf 501 = 4,00 EUR.
- [ ] keine rückwirkende Aufwertung früherer Verkäufe.
- [ ] parallele Freigaben erzeugen keine doppelte Verkaufsnummer.

### 6.3 Zahlungslebenszyklus

- [ ] sofort bezahlter Kartenkauf.
- [ ] verzögerte SEPA-Zahlung vor Zahlungseingang.
- [ ] erfolgreiche verzögerte SEPA-Zahlung.
- [ ] fehlgeschlagene verzögerte SEPA-Zahlung.
- [ ] vollständiger Refund vor Provisionsfreigabe.
- [ ] vollständiger Refund nach Provisionsfreigabe.
- [ ] vollständiger Refund nach Auszahlung.
- [ ] Teil-Refund vor und nach Freigabe.
- [ ] mehrere Teil-Refunds.
- [ ] Dispute-Eröffnung.
- [ ] verlorener Dispute.
- [ ] gewonnener Dispute.
- [ ] Webhook-Duplikate.
- [ ] Webhook-Reihenfolge vertauscht.
- [ ] Webhook-Replay.

### 6.4 Finanzinvarianten

- [ ] Gesamtauszahlung kann niemals `Lizenzen * 4 EUR` überschreiten.
- [ ] Gesamtauszahlung kann niemals die qualifizierte Provision überschreiten.
- [ ] falscher Provisionsbetrag sperrt sofort.
- [ ] fehlender Ledger-Eintrag sperrt sofort.
- [ ] beschädigte Hash-Kette sperrt sofort.
- [ ] doppelte Payment-Intent-Zuordnung sperrt sofort.
- [ ] Auszahlungsallokation muss centgenau stimmen.
- [ ] Auszahlung ohne Bankreferenz wird abgelehnt.
- [ ] negativer Saldo wird vor neuer Auszahlung verrechnet.
- [ ] jede Abweichung größer als 5,00 Prozent sperrt global.
- [ ] exakt 5,00 Prozent und die beabsichtigte Grenzsemantik werden explizit geprüft.
- [ ] Reconciliation- und Integrity-Leases verhindern parallele Läufe.
- [ ] abgelaufene Leases können kontrolliert übernommen werden.

### 6.5 Wiederherstellung

- [ ] D1-Backup erstellen.
- [ ] Datenbank aus Backup wiederherstellen.
- [ ] Feature Flag deaktivieren.
- [ ] Checkout auf sicheren Fallback zurückführen.
- [ ] Auszahlungssperre manuell und automatisch verifizieren.
- [ ] Hash-Ketten und Auditdaten nach Restore prüfen.

---

## 7. Erweiterte Security-Prüfung – freigegebener Umfang

### 7.1 Formelle Freigabe

Der Repository-Inhaber **Benjamin Graf** erteilt dem Security Agent ausdrücklich die Freigabe, eine **umfassende interne Security Readiness Assessment- und Remediation-Schleife** durchzuführen, die in Breite und methodischer Tiefe den technischen Prüfungen einer professionellen Application-Security- beziehungsweise Cybersecurity-Beratung entsprechen soll.

Der Security Agent darf innerhalb des unten definierten Scopes ohne weitere Einzelbestätigung:

- Sicherheitsprüfungen planen;
- den vollständigen Repository-Code lesen und analysieren;
- neue Security-Dokumentation, Tests, Workflows und Prüfscripte erstellen;
- auf einem separaten Branch Code korrigieren und härten;
- automatisierte SAST-, SCA-, Secret-, IaC-, Container- und Konfigurationsprüfungen einrichten;
- Testdatenbanken und lokale beziehungsweise Staging-Umgebungen verwenden;
- nicht-destruktive DAST- und API-Tests gegen ausdrücklich zu diesem Projekt gehörende Staging-Systeme durchführen;
- Fuzzing, Property-Based Testing und Race-Condition-Tests in lokalen beziehungsweise isolierten Testumgebungen durchführen;
- Threat Models, Datenflussdiagramme und Attack-Surface-Analysen erstellen;
- Schwachstellen reproduzieren, soweit dabei keine realen Kundendaten, realen Zahlungen oder fremden Systeme betroffen sind;
- Findings priorisieren, beheben, erneut testen und dokumentieren;
- Pull Requests, Issues und Security-Berichte erstellen;
- Evidenzpakete für externe Prüfer vorbereiten;
- eine SOC-2-, ISO/IEC-27001-, PCI-DSS- und Datenschutz-Readiness-Gap-Analyse erstellen;
- Empfehlungen für Kontrollziele, Policies, Nachweise und Betriebsmesswerte formulieren.

Für diese nicht-destruktiven Arbeiten im Repository, in CI, lokal und in einer ausdrücklich vorgesehenen Test-/Staging-Umgebung ist keine erneute Freigabe pro Einzelprüfung erforderlich.

### 7.2 Nicht durch diese Freigabe abgedeckt

Eine zusätzliche ausdrückliche Freigabe ist zwingend erforderlich für:

- Änderungen direkt in Produktion;
- Aktivierung des Partnerprogramms in Produktion;
- Anwendung von Migrationen auf der Produktivdatenbank;
- Änderung, Rotation oder Offenlegung produktiver Secrets;
- reale Käufe, Refunds, Disputes oder Bankauszahlungen;
- Tests mit realen Personen- oder Kundendaten;
- destruktive Last-, DoS- oder Ressourcenerschöpfungstests;
- Löschen oder absichtliches Beschädigen produktiver Daten;
- Social Engineering, Phishing oder Passwortangriffe gegen reale Personen;
- Scans oder Angriffe gegen Stripe, Cloudflare, Resend, GitHub oder andere Drittsysteme;
- Tests außerhalb der eigenen Domains, Konten und ausdrücklich autorisierten Infrastruktur;
- Umgehung von Nutzungsbedingungen oder Sicherheitskontrollen eines Drittanbieters;
- öffentliche Veröffentlichung unveröffentlichter Schwachstellen;
- Beauftragung kostenpflichtiger externer Dienstleister.

Bei Unsicherheit gilt: **fail closed, keine produktive oder externe Aktion durchführen und die Freigabe des Inhabers einholen.**

---

## 8. Erwarteter Prüfumfang wie bei einer Security-IT-Firma

Der Security Agent soll mindestens die folgenden Arbeitsstränge durchführen.

### 8.1 Architektur und Threat Modeling

- Systemkontext und Datenflussdiagramm erstellen.
- Trust Boundaries identifizieren.
- Assets und Schutzbedarf klassifizieren.
- Bedrohungsmodell nach STRIDE oder vergleichbarer Methode erstellen.
- Abuse Cases und Fraud Cases dokumentieren.
- Angriffsflächen von Web, API, Cloudflare, D1, Stripe, Resend, GitHub Actions und Android erfassen.
- Single Points of Failure und kritische Abhängigkeiten bestimmen.

### 8.2 Application Security

Mindestens prüfen:

- Authentisierung und Sitzungsmanagement;
- Magic Links, Token-Lebensdauer und Replay;
- Autorisierung, IDOR und BOLA;
- Rollen- und Mandantentrennung;
- CSRF;
- XSS;
- SQL Injection;
- Command Injection;
- SSRF;
- Open Redirects;
- Host-Header-Angriffe;
- CORS;
- CSP-Bypässe;
- Cache Poisoning und Cache-Leaks;
- Request Smuggling, soweit die Plattform betroffen sein kann;
- unsichere Deserialisierung;
- Pfadmanipulation;
- Mass Assignment;
- Parameter Pollution;
- Fehlermeldungen und Informationslecks;
- Rate Limits und Brute Force;
- Bot- und Abuse-Schutz;
- sichere Zufallswerte;
- kryptografische Verwendung;
- Datenschutz und Datenminimierung.

### 8.3 Business-Logic- und Fraud-Prüfung

Besonders intensiv prüfen:

- Eigenkäufe;
- Partner- und Käuferabsprachen;
- Cookie Stuffing;
- Code Guessing und Code Hijacking;
- Attribution nach Kaufabschluss;
- mehrfaches Zählen einer Zahlung;
- Webhook-Replay;
- parallele Checkout- und Refund-Rennen;
- doppelte Verkaufsnummern;
- Tier-Manipulation;
- negative Salden;
- Teil-Refund-Missbrauch;
- Dispute-Restore-Missbrauch;
- Auszahlung vor endgültiger Zahlung;
- Auszahlung nach Partner-Sperrung;
- Umgehung des 50-EUR-Limits;
- Rundungs- und Integerfehler;
- Überlauf- und Extremwerttests;
- Manipulation von Ledger, Audit, Snapshot oder Allokation;
- Race Conditions und Double Spending;
- Ausfall zwischen Datenbankoperationen;
- Wiederholung nach Timeouts;
- inkonsistente externe und interne Zustände.

### 8.4 Cloud- und Plattformprüfung

- Cloudflare-Bindings und Variablen;
- Trennung von Preview, Staging und Produktion;
- D1-Berechtigungen;
- Least Privilege;
- Secret-Verwaltung;
- Logzugriff und Logaufbewahrung;
- Deploymentschutz;
- Branch Protection;
- GitHub Actions Permissions;
- Supply-Chain-Risiken von Actions;
- Pinning kritischer Actions auf Commit-SHAs erwägen;
- Artefakt- und Cache-Sicherheit;
- Domain-, TLS-, DNS- und Redirect-Konfiguration;
- Security Header auf jeder Route;
- Cloudflare Access für Adminoberflächen prüfen.

### 8.5 Dependency- und Supply-Chain-Sicherheit

- SCA für Python, Node, Gradle und Android;
- bekannte CVEs;
- transitive Abhängigkeiten;
- veraltete oder nicht gepflegte Pakete;
- Lizenzprüfung;
- Lockfile-Integrität;
- Dependency Confusion;
- Typosquatting-Risiken;
- SBOM im CycloneDX- oder SPDX-Format;
- reproduzierbare Builds soweit praktisch;
- Signierung und Provenance von Release-Artefakten;
- OpenSSF Scorecard beziehungsweise vergleichbare Supply-Chain-Prüfung.

### 8.6 Android Security

- App-Link-Verifikation;
- Host- und Pfadbeschränkung;
- Intent Spoofing;
- WebView-Navigation;
- JavaScript Bridge;
- Network Security Configuration;
- Exported Components;
- FileProvider;
- Backup-Einstellungen;
- lokale Speicherung der Referral-Daten;
- Manipulation der lokalen Preferences;
- Deep-Link-Fuzzing;
- Release-Signing und Zertifikatswechsel;
- Prüfung gegen OWASP MASVS beziehungsweise Mobile Application Security Testing Guide, soweit einschlägig.

### 8.7 Datenschutz und Governance

- Dateninventar;
- Datenfluss und Empfänger;
- Löschfristen;
- Zweckbindung;
- Zugriffskontrolle;
- Betroffenenrechte;
- Auftragsverarbeiter;
- Drittlandtransfer;
- Logging personenbezogener Daten;
- Pseudonymisierung und Hashing;
- Incident Response;
- Breach Notification;
- Richtlinien, Rollen und Verantwortlichkeiten;
- Security Awareness und administrative Prozesse.

### 8.8 Resilienz und Betrieb

- Backup und Restore;
- RPO/RTO;
- Ausfall von Stripe;
- Ausfall von Cloudflare D1;
- Ausfall von Resend;
- verlorene Webhook-Ereignisse;
- Wiederanlauf nach Teilfehlern;
- Alarmierung;
- Runbooks;
- Tabletop Incident Exercise;
- Schlüssel- und Secret-Rotation;
- Notfallabschaltung;
- Feature-Flag-Rollback;
- Datenintegritätsprüfung nach Wiederherstellung.

---

## 9. Standards und Readiness-Ziele

### 9.1 OWASP ASVS

Die Webanwendung soll gegen **OWASP ASVS 5.0.0** gemappt werden.

Ziel:

- mindestens ASVS Level 2 für die internetexponierte Anwendung;
- für Zahlungs-, Finanz-, Admin- und Integritätsfunktionen zusätzliche Level-3-Anforderungen prüfen;
- jede anwendbare Anforderung erhält Status, Evidenz, Finding und gegebenenfalls Remediation.

### 9.2 NIST Secure Software Development Framework

Die Entwicklungs- und Releaseprozesse sollen gegen **NIST SP 800-218 SSDF 1.1** geprüft werden, insbesondere:

- Organisation vorbereiten;
- Software schützen;
- gut abgesicherte Software erzeugen;
- auf Schwachstellen reagieren;
- Nachweise in CI und Releaseprozess verankern.

### 9.3 SOC 2 Readiness

Eine SOC-2-Readiness-Bewertung soll mindestens die AICPA Trust Services Criteria berücksichtigen:

- Security;
- je nach Scope Availability;
- Processing Integrity;
- Confidentiality;
- Privacy.

Der Security Agent darf:

- Kontrollmatrix erstellen;
- Policies und technische Evidenz vorbereiten;
- Lücken und Maßnahmen dokumentieren;
- einen Readiness-Report erstellen.

Der Security Agent darf **keinen SOC-2-Bericht ausstellen und keine SOC-2-Konformität behaupten**. Eine formelle SOC-Attestierung ist eine unabhängige Prüfleistung durch entsprechend qualifizierte Prüfer beziehungsweise CPA-Firmen. Für einen späteren Type-II-Bericht müssen Kontrollen zusätzlich über einen Beobachtungszeitraum wirksam betrieben und nachgewiesen werden.

### 9.4 ISO/IEC 27001 Readiness

Eine Readiness-Bewertung für **ISO/IEC 27001:2022** soll prüfen:

- Scope des ISMS;
- Informationssicherheitsleitlinie;
- Rollen und Verantwortlichkeiten;
- Asset- und Risikomanagement;
- Risk Treatment Plan;
- Statement of Applicability;
- Lieferantenmanagement;
- Incident Management;
- Business Continuity;
- interne Audits;
- Management Review;
- kontinuierliche Verbesserung;
- Evidenz der technischen und organisatorischen Kontrollen.

Der Security Agent darf Gap-Analyse, Dokumentation und Evidenz vorbereiten. Eine Zertifizierung darf ausschließlich durch eine geeignete unabhängige und akkreditierte Zertifizierungsstelle bestätigt werden.

### 9.5 PCI DSS Readiness

Der Security Agent soll:

- den tatsächlichen Karteninhaberdatenfluss dokumentieren;
- nachweisen, dass Kartendaten nicht durch DownloadThat verarbeitet oder gespeichert werden, soweit dies tatsächlich zutrifft;
- Stripe Checkout, Webhooks und Merchant-Konfiguration prüfen;
- die korrekte SAQ-/Validierungsanforderung mit Stripe beziehungsweise dem Acquirer klären lassen;
- keine Aussage „PCI-zertifiziert“ oder „außerhalb des PCI-Scope“ ohne formelle Scope-Bestätigung treffen.

### 9.6 Datenschutz-/DSGVO-Readiness

Der Security Agent soll technische und organisatorische Lücken dokumentieren, kann aber keine anwaltliche Datenschutzfreigabe oder behördliche Bestätigung ersetzen.

---

## 10. Verlangte Security-Artefakte

Die vertiefte Prüfung soll mindestens folgende Dateien oder gleichwertige Nachweise erzeugen:

```text
security/
  SECURITY_ASSESSMENT_REPORT.md
  EXECUTIVE_SECURITY_SUMMARY.md
  THREAT_MODEL.md
  DATA_FLOW_AND_TRUST_BOUNDARIES.md
  ATTACK_SURFACE.md
  RISK_REGISTER.md
  ASVS_5_MATRIX.md
  NIST_SSDF_MATRIX.md
  SOC2_READINESS_MATRIX.md
  ISO27001_READINESS_MATRIX.md
  PCI_SCOPE_ASSESSMENT.md
  PRIVACY_AND_DATA_RETENTION_REVIEW.md
  PENETRATION_TEST_PLAN.md
  PENETRATION_TEST_RESULTS.md
  BUSINESS_LOGIC_ABUSE_CASES.md
  INCIDENT_RESPONSE_PLAN.md
  BACKUP_RESTORE_TEST.md
  PRODUCTION_SECURITY_CHECKLIST.md
  RESIDUAL_RISK_ACCEPTANCE.md
  EVIDENCE_INDEX.md
  sbom.cdx.json
```

Findings sollen mindestens enthalten:

- eindeutige ID;
- Titel;
- betroffene Komponente;
- Schweregrad;
- CVSS, soweit sinnvoll;
- CWE beziehungsweise Kontrollreferenz;
- Beschreibung;
- Reproduktionsschritte;
- Auswirkung;
- Wahrscheinlichkeit;
- Evidenz;
- empfohlene Behebung;
- verantwortliche Person;
- Zieldatum;
- Status;
- Retest-Ergebnis;
- akzeptiertes Restrisiko, falls nicht behoben.

---

## 11. Schweregrade und Behebungsregeln

### Critical / P0

Beispiele:

- Auszahlung über die mathematische Obergrenze;
- Remote Code Execution;
- vollständige Authentisierungs- oder Autorisierungsumgehung;
- Zugriff auf produktive Secrets;
- Manipulation von Ledger oder Auszahlungen ohne Erkennung;
- massenhafter Zugriff auf personenbezogene Daten.

Regel: sofortige Sperre, keine Produktionsfreigabe, unverzügliche Behebung und Retest.

### High / P1

Beispiele:

- IDOR auf Partner- oder Adminfunktionen;
- reproduzierbares Double Spending;
- Webhook-Fälschung oder Replay mit finanzieller Wirkung;
- persistentes XSS im Adminbereich;
- unautorisierte Änderung von Auszahlungsempfängern.

Regel: keine Produktionsfreigabe, Behebung und Retest verpflichtend.

### Medium / P2

Regel: grundsätzlich vor Produktion beheben. Ausnahme nur mit dokumentierter Risikoakzeptanz, kompensierender Kontrolle, Verantwortlichem und verbindlichem Zieldatum.

### Low / P3 und Informational

Regel: dokumentieren, priorisieren und in den Verbesserungsplan übernehmen.

---

## 12. Go-/No-Go-Kriterien für Produktion

### Go nur, wenn alle Bedingungen erfüllt sind

- [ ] Pull Request reviewed und gemergt.
- [ ] alle CI-Checks grün.
- [ ] keine offenen Critical-/P0-Findings.
- [ ] keine offenen High-/P1-Findings.
- [ ] Medium-/P2-Findings behoben oder formal akzeptiert.
- [ ] Staging-End-to-End-Test vollständig bestanden.
- [ ] Stripe-Testkauf, SEPA, Refunds und Disputes bestanden.
- [ ] Reconciliation meldet `ok`.
- [ ] Integrity Gate meldet `ok`.
- [ ] Backup und Restore praktisch bestanden.
- [ ] Secrets und Berechtigungen geprüft.
- [ ] Adminzugang zusätzlich abgesichert.
- [ ] Alarmierung und Runbooks vorhanden.
- [ ] rechtliche, steuerliche und datenschutzrechtliche Prüfung erfolgt.
- [ ] Partnerbedingungen freigegeben.
- [ ] Auszahlungs- und Buchhaltungsprozess freigegeben.
- [ ] Android App Links mit Release-Zertifikat verifiziert.
- [ ] schriftliche Produktionsfreigabe des Inhabers dokumentiert.

### Automatisches No-Go

- eine Auszahlungssperre ist aktiv;
- Reconciliation oder Integrity Gate ist nicht `ok`;
- ein Critical- oder High-Finding ist offen;
- Produktionsbackup ist nicht verifiziert;
- Stripe-Webhooks sind nicht vollständig getestet;
- Secrets fehlen oder sind im Repository auffindbar;
- Rechts-/Steuer-/Datenschutzprüfung fehlt;
- unklarer PCI-DSS-Scope;
- keine verantwortliche Person für Security Incidents oder Auszahlungen;
- keine kontrollierte Rückfallmöglichkeit.

---

## 13. Externe Prüfung und formelle Approvals

Die interne Prüfung durch den Security Agent dient als **Readiness Assessment** und als technische Vorprüfung. Sie ist kein Ersatz für unabhängige Bestätigung.

Vor größerem öffentlichem Rollout beziehungsweise erheblichem Zahlungsvolumen wird empfohlen:

1. unabhängiger professioneller Penetrationstest;
2. Datenschutz- und Vertragsprüfung durch entsprechend qualifizierte Beratung;
3. steuerliche Prüfung des Affiliate- und Gutschriftmodells;
4. PCI-Scope-Bestätigung durch Stripe/Acquirer und gegebenenfalls QSA;
5. SOC-2-Readiness-Assessment und bei geschäftlichem Bedarf formelle SOC-Attestierung;
6. ISO/IEC-27001-Gap-Analyse und bei Bedarf Zertifizierung durch akkreditierte Stelle;
7. jährlicher oder nach wesentlichen Änderungen wiederholter Security-Test;
8. erneuter Test nach schwerwiegenden Findings oder Architekturänderungen.

Es dürfen nur folgende Formulierungen verwendet werden, solange keine externe Bestätigung vorliegt:

- „intern gegen OWASP ASVS geprüft“;
- „NIST-SSDF-orientierter Entwicklungsprozess“;
- „SOC-2-ready beziehungsweise SOC-2-Readiness geprüft“;
- „ISO/IEC-27001-Readiness bewertet“;
- „PCI-DSS-Scope wird durch Stripe/Acquirer bestimmt“.

Nicht zulässig ohne formellen Nachweis:

- „SOC-2-zertifiziert“;
- „ISO-27001-zertifiziert“;
- „PCI-zertifiziert“;
- „vollständig sicher“;
- „gehackt werden unmöglich“;
- „behördlich freigegeben“.

---

## 14. Empfohlene Reihenfolge der nächsten Arbeiten

1. Security Agent liest `HANDOVER.md` und `docs/AFFILIATE_PROGRAM_IMPLEMENTATION.md` vollständig.
2. Vollständige PR- und Architekturprüfung durchführen.
3. Threat Model und Datenflussmodell erstellen.
4. automatisierte SAST-, SCA-, Secret- und SBOM-Prüfungen erweitern.
5. ASVS-5-Matrix erstellen.
6. Business-Logic- und Fraud-Test-Suite ausbauen.
7. isolierte Staging-Umgebung definieren.
8. End-to-End-Zahlungsszenarien in Stripe Test Mode durchführen.
9. Backup-/Restore-Übung durchführen.
10. Security-Findings beheben und retesten.
11. SOC-2-/ISO-27001-/PCI-/Datenschutz-Readiness-Matrizen erstellen.
12. extern prüfbares Evidenzpaket erzeugen.
13. unabhängigen Penetrationstest einplanen.
14. rechtliche und steuerliche Prüfung einholen.
15. Go-/No-Go-Meeting beziehungsweise dokumentierte Inhaberfreigabe.
16. Migration in Produktion bei weiterhin deaktiviertem Feature Flag.
17. Smoke Tests und Reconciliation in Produktion.
18. erst danach `AFFILIATE_PROGRAM_ENABLED=true` setzen.
19. engmaschiges Monitoring in der ersten Betriebsphase.
20. Post-Launch-Sicherheitsreview und Lessons Learned.

---

## 15. Verbindlicher Abschlussvermerk

Der aktuelle Implementierungsstand ist eine umfangreiche und sicherheitsorientierte technische Grundlage. Er ist **nicht gleichbedeutend mit einer Produktions-, Rechts-, Steuer-, Datenschutz-, SOC-, ISO- oder PCI-Freigabe**.

CloudCode / Claude Code ist hiermit autorisiert, die beschriebenen erweiterten internen Prüfungen, Security-Härtungen, Evidenzerstellungen und Remediation-Schleifen innerhalb des freigegebenen nicht-destruktiven Scopes selbstständig durchzuführen. Der Agent soll nicht bei der ersten grünen Testausgabe abbrechen, sondern Findings reproduzieren, beheben, erneut prüfen und Restrisiken nachvollziehbar dokumentieren.

Die endgültige Aktivierung in Produktion, reale finanzielle Transaktionen sowie formelle externe Zertifizierungen oder Attestierungen bleiben separaten Freigaben und unabhängigen Prüfinstanzen vorbehalten.

---

## 16. Referenzrahmen

Die Prüfung soll sich an den jeweils aktuellen offiziellen Fassungen orientieren, insbesondere:

- [OWASP Application Security Verification Standard](https://owasp.org/www-project-application-security-verification-standard/)
- [NIST SP 800-218 Secure Software Development Framework](https://csrc.nist.gov/pubs/sp/800/218/final)
- [ISO/IEC 27001 Information Security Management Systems](https://www.iso.org/standard/27001)
- [AICPA System and Organization Controls](https://www.aicpa-cima.com/resources/landing/system-and-organization-controls-soc-suite-of-services)
- [PCI Security Standards Council – PCI DSS](https://www.pcisecuritystandards.org/standards/pci-dss/)
- OWASP MASVS/MSTG für die Android-Komponente
- einschlägige Datenschutz-, Verbraucher-, Steuer- und Werberegeln der tatsächlich bedienten Märkte
