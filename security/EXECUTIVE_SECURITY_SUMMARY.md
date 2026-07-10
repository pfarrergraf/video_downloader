# Executive Security Summary — DownloadThat Creator/Affiliate Program

**Datum:** 2026-07-10 · **Geprüfter Stand:** `feature/affiliate-partner-program` @ `fc77401` (PR #4) ·
**Prüfbranch:** `security/affiliate-readiness-hardening` · **Programmstatus:** weiterhin deaktiviert
(`AFFILIATE_PROGRAM_ENABLED=false`), **keine Produktionsaktivierung durch diese Prüfung**.

## Kurzfassung

Diese Prüfung ist eine **interne** Security-Readiness-Bewertung (Code-Review, Threat Modeling, statische
und lokale/reproduzierbare Tests) im Umfang und methodischem Anspruch einer professionellen
Application-Security-Prüfung — **kein** unabhängiger externer Penetrationstest, keine formelle
SOC-2-/ISO-27001-/PCI-Zertifizierung und keine Rechts-/Steuerprüfung. Sie ersetzt keine dieser externen
Prüfungen (siehe `docs/AFFILIATE_PROGRAM_IMPLEMENTATION.md` und `HANDOVER.md` §13).

## Ergebnis in einem Satz

Die Kernfinanzlogik (Provisionsstaffel, absolute Auszahlungsobergrenze, Append-only-Hash-Ketten,
Maker-Checker-Auszahlung, 5,00-%-Reconciliation-Sperre) hält den geforderten harten Invarianten stand;
**ein kritisches (P1) und mehrere mittlere (P2) Findings** wurden gefunden, alle mit Code-Zugriff behebbaren
Findings sind **behoben und regressionsgetestet**; zwei Findings erfordern externe/operative Schritte
außerhalb dieser Sitzung (siehe unten).

## Wichtigste Befunde

| # | Finding | Schweregrad | Status |
|---|---|---|---|
| AFF-001 | Stored XSS im Admin-Dashboard über selbstregistrierbare Partnerfelder → vollständige Kompromittierung der Admin-Session-Fähigkeiten | **P1/High** | **Behoben, retestet** |
| AFF-003 | Race Condition bei doppelter Webhook-Zustellung kann Partner-Clawback-Saldo doppelt anwenden (wirkt zulasten des Partners, nicht der Firma; keine Umgehung der Auszahlungsobergrenze) | P2/Medium | **Behoben, reproduziert & retestet** |
| AFF-004 | Kein Rate Limiting auf Login-/Registrierungs-E-Mail-Versand (E-Mail-Bombing-Risiko) | P2/Medium | **Behoben** |
| AFF-002 | Android: geräteseitige App auf demselben Gerät kann lokale Referral-Zuordnung fälschen (plattformbedingte Grenze, kein Code-Fix möglich) | P2 (begrenzt) | Dokumentiertes Restrisiko + Kompensationskontrollen |
| AFF-005 | GitHub Actions nicht auf Commit-SHA gepinnt; `wrangler` ungepinnt in Deploy-Workflow mit Secrets | P2/Medium | Dokumentiert, Umsetzung erfordert externen Repo-Zugriff |
| AFF-009 | App-Links-Zertifikatsverifikation hängt von korrekt gesetzter Produktionsvariable ab | P2 (operativ) | Muss vor Go-Live extern verifiziert werden |

Vollständige Liste inkl. P3/Informational: `RISK_REGISTER.md`. Details, CVSS, Reproduktion, Fix, Retest:
`PENETRATION_TEST_RESULTS.md`.

## Was mathematisch verifiziert wurde

- `Gesamtauszahlungen ≤ Anzahl zugeordneter Lizenzen × 4,00 EUR` — durchgesetzt in `runReconciliation()` und
  unabhängig noch einmal im Integrity Gate (`_affiliate_integrity.js`); beide müssen `ok` melden, bevor eine
  Auszahlung vorbereitet, freigegeben oder als bezahlt gebucht werden darf.
- `Gesamtauszahlungen ≤ Summe aller qualifizierten Provisionen` — dieselbe doppelte Kontrolle.
- Exakt 5,00 % Abweichung (500 Basispunkte) löst **keine** Sperre aus, 5,01 % (501 Bps) **löst** eine Sperre
  aus — jetzt explizit unit-getestet (`deviationBps`-Grenzwerttest).
- Jede Auszahlung ist über `affiliate_payout_allocations` centgenau auf einzelne Provisionen zurückführbar;
  ein Integrity-Gate-Check erkennt jede Abweichung.
- Doppelte Stripe-Payment-Intent-Zuordnungen, fehlende Ledger-Einträge und beschädigte Hash-Ketten führen
  jeweils zu `hard_failures` und damit zur globalen Auszahlungssperre.

## Was nicht in dieser Sitzung geleistet werden konnte (und warum)

1. **SHA-Pinning der GitHub Actions** — erfordert Verifikation echter Commit-Hashes gegen externe
   Repositories außerhalb des für diese Sitzung autorisierten Zugriffs; erfundene Hashes wären gefährlicher
   als der Status quo. Empfehlung dokumentiert, Umsetzung an Repository-Inhaber/CI-Pipeline mit Internetzugriff.
2. **Verifikation von `ANDROID_CERT_SHA256` in der Cloudflare-Produktionsumgebung** — kann prinzipiell nicht
   aus dem Repository heraus geprüft werden.
3. **Externer Penetrationstest, Rechts-/Steuerprüfung, formelle SOC-2-/ISO-27001-/PCI-Zertifizierung** —
   ausdrücklich außerhalb des Mandats dieser Sitzung (siehe `HANDOVER.md` §9, §13).

## Go/No-Go-Einschätzung dieser Prüfung

**No-Go weiterhin, aber aus anderen Gründen als zuvor.** Vor dieser Prüfung standen keine offenen P0/P1-
Findings im Code fest, aber es waren auch keine gezielt gesucht worden. Nach dieser Prüfung: **keine
offenen P0/P1-Findings mehr** (AFF-001 behoben). Die verbleibenden Blocker für eine Produktionsfreigabe sind
ausschließlich die in `HANDOVER.md` §5 und §12 bereits benannten **externen/operativen** Voraussetzungen
(Secrets setzen, Staging-End-to-End-Test mit echtem Stripe-Testmodus, Rechts-/Steuerprüfung, Backup-Test in
echter Cloudflare-Umgebung, schriftliche Inhaberfreigabe) — siehe `PRODUCTION_SECURITY_CHECKLIST.md` für die
konsolidierte, aktualisierte Liste.

## Zulässige Formulierungen (siehe HANDOVER.md §13)

Diese Prüfung erlaubt die Aussage „intern gegen OWASP ASVS geprüft“, „NIST-SSDF-orientierter
Entwicklungsprozess“, „SOC-2-/ISO-27001-Readiness bewertet“. Sie erlaubt **nicht** die Aussage
„zertifiziert“, „vollständig sicher“ oder „behördlich freigegeben“.
