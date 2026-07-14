# SOC 2 Readiness Matrix — Affiliate Program

> **HISTORICAL EVIDENCE:** Bewertet das inzwischen entfernte Affiliate-/Stripe-System.
> Nicht als aktuellen Produktionsstatus verwenden; maßgeblich ist
> `CURRENT_SECURITY_IMPLEMENTATION_STATUS.md`.

**Wichtig:** Dies ist eine interne Readiness-Bewertung gegen die AICPA Trust Services Criteria. Sie stellt
**keinen SOC-2-Bericht** dar und begründet **keine** Aussage „SOC-2-zertifiziert“. Eine formelle Type I/II-
Attestierung erfordert eine unabhängige CPA-Prüfung, für Type II zusätzlich einen beobachteten
Kontrollzeitraum.

## Security (Common Criteria)

| Kriterium | Bewertung | Evidenz / Lücke |
|---|---|---|
| CC6.1 Logischer Zugriffsschutz | Bereit | Rollenbasierte Session-Trennung, gehashte Tokens |
| CC6.6 Schutz vor externen Bedrohungen | Bereit (nach Fix) | AFF-001/AFF-004 behoben; Rate Limiting, XSS-Schutz |
| CC6.8 Schutz vor unautorisierter/böswilliger Software | Teilweise | Kein SAST/Dependency-Scanning-Tool in CI (Folgearbeit) |
| CC7.2 Erkennung von Sicherheitsvorfällen | Teilweise | Hash-Ketten/Integrity-Gate erkennen Datenmanipulation; kein zentrales Alerting-System dokumentiert (HANDOVER §5.7 offen) |
| CC7.3 Reaktion auf Vorfälle | Bereit | `INCIDENT_RESPONSE_PLAN.md` (dieser Prüfung) als Erstentwurf |
| CC8.1 Change Management | Bereit | Git-Branches, PR-Review, CI-Gates, Migrationen versioniert |

## Availability

Nicht im Kernscope dieser Prüfung (Betriebs-/Infrastrukturverantwortung liegt bei Cloudflare); RPO/RTO in
`BACKUP_RESTORE_TEST.md` dokumentiert. Bewertung: **nicht bewertbar ohne Cloudflare-Produktionszugriff**.

## Processing Integrity

| Kriterium | Bewertung | Evidenz |
|---|---|---|
| Vollständigkeit/Genauigkeit der Verarbeitung | Bereit | Doppelte, unabhängige Reconciliation (lokale DB vs. Live-Stripe), Integer-Cent-Arithmetik, harte Obergrenzen |
| Autorisierung kritischer Transaktionen | Bereit | Maker-Checker für Auszahlungen |
| Fehlererkennung und -korrektur | Bereit | Globale Auszahlungssperre bei jeder harten Invarianzverletzung |

## Confidentiality

| Kriterium | Bewertung | Evidenz |
|---|---|---|
| Zugriffsbeschränkung auf vertrauliche Daten | Bereit | Käufer-PII nie im Partner-/Admin-Dashboard exponiert |
| Verschlüsselung in Transit | Bereit | HTTPS/HSTS erzwungen |
| Sichere Löschung/Aufbewahrung | Teilweise | Kein automatisierter Aufräumprozess für abgelaufene Tokens/Clicks im Code gefunden (HANDOVER §5.1, offen) |

## Privacy

Siehe `PRIVACY_AND_DATA_RETENTION_REVIEW.md` für Details. Zusammenfassung: Datenminimierung bei Klicks
(gehashte IP/UA), keine Käufer-PII-Weitergabe an Partner, aber Löschfristen/Betroffenenrechte-Prozess sind
organisatorisch noch zu definieren.

## Gesamteinschätzung

**SOC-2-Readiness: gegeben für Security und Processing Integrity**, mit dokumentierten Lücken bei
Availability (nicht bewertbar ohne Produktionszugriff) und einzelnen Confidentiality-/Privacy-Prozessen
(Aufbewahrungsautomatisierung). Für eine formelle Attestierung sind zusätzlich ein beobachteter
Kontrollzeitraum (Type II) und eine unabhängige CPA-Prüfung erforderlich.
