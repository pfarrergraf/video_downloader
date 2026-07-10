# Affiliate Program – Risk / Findings Register

Stand: 2026-07-10. Branch: `security/affiliate-readiness-hardening` (Basis: `feature/affiliate-partner-program` @ `fc77401`).

Diese Tabelle ist die kanonische Fundstelle für alle in dieser Prüfung identifizierten Findings.
Details, Reproduktion und Retest-Ergebnisse je Finding stehen in `PENETRATION_TEST_RESULTS.md`.

| ID | Titel | Komponente | Schweregrad | CWE | Status | Retest |
|---|---|---|---|---|---|---|
| AFF-001 | Stored XSS im Partner-Admin-Dashboard über unescaped `display_name`/`email`/`code` | `pro/website/partner-admin.html`, `partner-dashboard.html` | **P1 / High** | CWE-79 | **Behoben** | PASS |
| AFF-002 | Android: Explicit-Intent umgeht App-Link-Verifikation und kann lokale Referral-Zuordnung fälschen | `android/.../AffiliateReferral.kt` | P2 (begrenzter Blast Radius, siehe unten) | CWE-346 | Dokumentiertes Restrisiko, keine vollständige Code-Lösung möglich | N/A (architekturell) |
| AFF-003 | Race Condition: doppelte Webhook-Zustellung kann `negative_balance_cents`-Clawback doppelt anwenden | `functions/_affiliate.js` (`reverseCommission`), `functions/_affiliate_events.js` (`handleAffiliateDisputeClosed`) | **P2 / Medium** | CWE-362 | **Behoben** | PASS (reproduziert vor Fix, grün nach Fix) |
| AFF-004 | Kein Rate Limiting auf Partner-/Admin-Login-Request und Partner-Registrierung | `functions/api/partner/login-request.js`, `functions/api/admin/login-request.js`, `functions/api/partner/register.js` | P2 / Medium | CWE-307 | **Behoben** | PASS |
| AFF-005 | GitHub Actions nicht auf Commit-SHA gepinnt; `deploy-pro-website.yml` lädt `wrangler@3` ungepinnt zur Laufzeit mit Secrets im Scope | `.github/workflows/*.yml` | P2 / Medium | CWE-829 | Dokumentiert, nicht automatisiert behoben (siehe Begründung) | Empfehlung ausstehend |
| AFF-006 | Secret-Scan-Test hat blinden Fleck bei Turnstile-Secrets und ist regex-basiert leicht umgehbar | `tests/test_affiliate_no_secrets.py` | P2 / Medium (Kontrollschwäche, kein aktiver Leak gefunden) | CWE-200 (Kontrollreferenz) | **Teilweise behoben** (Turnstile-Pattern ergänzt) | PASS |
| AFF-007 | Totes Duplikat `createDynamicCheckout` enthielt latenten Bug (hätte 14-Tage-Widerrufsfrist gebrochen) | `functions/_affiliate.js` | P3 / Low | CWE-1164 (unbenutzter Code) | **Behoben** (entfernt) | PASS |
| AFF-008 | Android: Case-sensitive Host-Vergleich verwirft legitime Claims bei gemischter Groß-/Kleinschreibung | `android/.../AffiliateReferral.kt` | P3 / Low | – | **Behoben** | PASS |
| AFF-009 | App-Links-Verifikation hängt von korrekt gesetztem `ANDROID_CERT_SHA256` in Produktion ab; nicht aus dem Repo verifizierbar | `functions/.well-known/assetlinks.json.js` | P2 / operative Prüfpflicht | – | Offen – erfordert Produktionszugriff | Muss vor Go-Live verifiziert werden |
| AFF-010 | CSP erlaubt `'unsafe-inline'` für `script-src`, keine Verteidigungslinie gegen künftige DOM-Injection | `pro/website/_headers` | P3 / Low | CWE-1021 (verwandt) | Dokumentiert, nicht in diesem Pass umgesetzt | Folgearbeit |
| AFF-011 | „Login-CSRF“: Angreifer kann eigenen gültigen Magic Link an Opfer phishen | `functions/api/partner/login.js` | P3 / Informational | CWE-352 (verwandt) | Dokumentiert, geringe Auswirkung | Folgearbeit |
| AFF-012 | Stripe-Webhook-Fehlerantwort gab internen Stacktrace im Response-Body zurück | `functions/api/webhook.js` | P3 / Low | CWE-209 | **Behoben** | PASS |

## Einordnung nach HANDOVER.md-Schweregradskala

- **P0/Critical:** keine offenen Findings dieser Kategorie identifiziert. Insbesondere wurde **keine** Möglichkeit gefunden, die harten Auszahlungsinvarianten (`Gesamtauszahlungen <= Lizenzen × 4 EUR`, `Gesamtauszahlungen <= qualifizierte Provisionen`) zu verletzen, Ledger-/Audit-Hash-Ketten unbemerkt zu manipulieren, oder personenbezogene Käuferdaten aus dem Partner-Dashboard zu erhalten.
- **P1/High:** AFF-001 — behoben und retestet.
- **P2/Medium (6 Findings):** AFF-003, AFF-004 — behoben und retestet. AFF-006 — teilweise behoben (Muster ergänzt, regexbasierte Grenze bleibt bestehen). AFF-002, AFF-005, AFF-009 — offen bzw. dokumentiertes Restrisiko (siehe Begründungen unten und in `RESIDUAL_RISK_ACCEPTANCE.md`).
- **P3/Low/Informational (5 Findings):** AFF-007, AFF-008, AFF-012 — behoben und retestet. AFF-010, AFF-011 — offen, als Folgearbeit dokumentiert (siehe `RESIDUAL_RISK_ACCEPTANCE.md`).

## Gesamtstatus (kanonisch — maßgeblich für jede Zusammenfassung dieser Prüfung)

Von 12 identifizierten Findings sind **6 vollständig behoben und retestet** (AFF-001, AFF-003, AFF-004,
AFF-007, AFF-008, AFF-012), **1 Kontrollschwäche teilweise behoben** (AFF-006) und **5 verbleibend bzw. als
strukturelles/operatives Restrisiko dokumentiert** (AFF-002, AFF-005, AFF-009, AFF-010, AFF-011).
**Keine offenen P0- oder P1-Findings.** Jede andere Zahl in `EXECUTIVE_SECURITY_SUMMARY.md`,
`SECURITY_ASSESSMENT_REPORT.md` oder der PR-Beschreibung muss mit dieser Zeile übereinstimmen — diese Tabelle
ist die kanonische Quelle.

## Warum AFF-002 nicht als blockierendes P1 eingestuft wird

Das Handover-Dokument stuft "persistentes XSS im Adminbereich" explizit als P1-Beispiel ein; AFF-001 folgt dieser Einstufung. AFF-002 ist strukturell anders: Es handelt sich um eine bekannte, plattformseitige Grenze von Android (explizite Intents umgehen die Digital-Asset-Links-Verifikation grundsätzlich und lassen sich von keiner Empfänger-App zuverlässig unterscheiden). Es existiert **kein** korrekter Code-Fix auf App-Seite, der das last-touch-Attributionsmodell (explizit gefordert in HANDOVER §Geschäftsmodell) nicht verletzen würde. Die tatsächliche finanzielle Auswirkung ist durch bestehende Kontrollen strukturell begrenzt:

1. Ein Angreifer benötigt ein **eigenes, registriertes und aktives** Partnerkonto, um von der Umlenkung zu profitieren – das Konto ist damit identifizierbar und sperrbar.
2. Die tatsächliche Provisionsfreigabe durchläuft weiterhin 30-Tage-Prüfung, Reconciliation und Integrity Gate; keine harte Obergrenze wird umgangen.
3. Bereits ausgezahlte Beträge lassen sich per Clawback (negativer Saldo) zurückholen; Admin kann den Partner sperren.

Empfehlung: serverseitige Anomalieerkennung (ungewöhnliche Conversion-Muster pro Partner/Gerät/IP-Cluster – bereits in HANDOVER §5.5 als offener Punkt geführt) statt eines wirkungslosen App-seitigen Pseudo-Fixes.
