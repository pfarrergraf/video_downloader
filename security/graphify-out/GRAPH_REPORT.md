# Graph Report - security  (2026-07-14)

## Corpus Check
- 27 files · ~15,477 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 215 nodes · 188 edges · 28 communities (25 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6a8e0b88`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]

## God Nodes (most connected - your core abstractions)
1. `Business Logic & Fraud Abuse Cases — Affiliate Program` - 14 edges
2. `Affiliate Program – Penetration Test Results (Internal Assessment)` - 12 edges
3. `Detail-Findings` - 11 edges
4. `Data Flow and Trust Boundaries — Historical Affiliate Program` - 9 edges
5. `Executive Security Summary — DownloadThat Creator/Affiliate Program` - 8 edges
6. `Incident Response Plan (Draft) — Affiliate Program` - 8 edges
7. `Residual Risk Acceptance — Affiliate Program` - 8 edges
8. `Attack Surface Map — Affiliate Program` - 7 edges
9. `Prüf- & Zertifizierungs-Leiter — DownloadThat / ClassyDL` - 7 edges
10. `Privacy & Data Retention Review — Historical Affiliate Program` - 7 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Communities (28 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (16): 1. Klick → Attribution, 2. Checkout → Provisions-Draft, 3. Stripe-Webhook → Provisions-Zeile, 4. Reconciliation (30 Tage später) → Provisions-Freigabe, 5. Auszahlung (Maker-Checker), 6. Partner-/Admin-Dashboard-Anzeige, 7. Android → Website, code:block1 (Partner-Link (Browser/App) → GET /p/<slug> → recordAffiliate) (+8 more)

### Community 1 - "Community 1"
Cohesion: 0.13
Nodes (14): Auszahlung nach Partnersperre, Business Logic & Fraud Abuse Cases — Affiliate Program, Cookie Stuffing (Android) — siehe AFF-002, Cookie Stuffing (Web), Doppelte Conversions / Webhook-Replay, Eigenkäufe (Self-Referral), Integer-, Rundungs- und Extremwertfehler, Käufer-Partner-Absprache (+6 more)

### Community 2 - "Community 2"
Cohesion: 0.13
Nodes (14): AFF-001 — Stored XSS im Partner-Admin-Dashboard (P1 / High), AFF-002 — Android: Explicit-Intent umgeht App-Link-Verifikation (P2, dokumentiertes Restrisiko), AFF-003 — Race Condition: doppelte Clawback-Anwendung bei parallelen Webhook-Zustellungen (P2 / Medium), AFF-004 — Kein Rate Limiting auf Auth-/Registrierungs-Endpunkten (P2 / Medium), AFF-005 — GitHub Actions nicht SHA-gepinnt; ungepinnter `wrangler`-Download mit Secrets im Scope (P2 / Medium), AFF-006 — Secret-Scan-Test: blinder Fleck bei Turnstile, regexbasiert umgehbar (P2 / Medium), AFF-007 — Totes Code-Duplikat mit latentem Bug (P3 / Low), AFF-008 — Android: Case-sensitive Host-Vergleich (P3 / Low) (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.18
Nodes (11): A10 — Stripe-Webhook fälschbar? ❌ WIDERLEGT, A1 — Lizenzschlüssel von außen generierbar? ❌ WIDERLEGT, A2 — Pro-Freischaltung lokal umgehbar? ✅ BESTÄTIGT (Design-Trade-off), A3 — SSRF über `/api/scrape`? ✅ BESTÄTIGT → BEHOBEN, A4 — Lokale Daten für Co-Tenant lesbar? ✅ BESTÄTIGT → BEHOBEN, A5 — Passwort-Leak über Auto-Login-URL? ✅ BESTÄTIGT → BEHOBEN, A6 — Login brute-force-bar? ❌ WIDERLEGT, A7 — Clickjacking / fehlende Header? ✅ BESTÄTIGT → BEHOBEN (+3 more)

### Community 4 - "Community 4"
Cohesion: 0.2
Nodes (9): Auftrag (bewusst gegnerisch formuliert), code:json ({), code:json ({), Ergebnis auf einen Blick, Fazit des Red Teams, Nachher (nach Härtung), Red-Team-Report — Downloader-Kern, On-Device-Server & Android-App, Reproduzierbares PoC-Harness (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.22
Nodes (8): Ergebnis in einem Satz, Executive Security Summary — DownloadThat Creator/Affiliate Program, Go/No-Go-Einschätzung dieser Prüfung, Kurzfassung, Was mathematisch verifiziert wurde, Was nicht in dieser Sitzung geleistet werden konnte (und warum), Wichtigste Befunde, Zulässige Formulierungen (siehe HANDOVER.md §13)

### Community 6 - "Community 6"
Cohesion: 0.22
Nodes (8): Auslöser / Erkennungssignale, Incident Response Plan (Draft) — Affiliate Program, Notfallabschaltung (Kill Switch), Offene organisatorische Punkte (nicht durch Code lösbar), Runbook 1 — Auszahlungssperre (payout_frozen), Runbook 2 — Kompromittiertes Partnerkonto, Runbook 3 — Kompromittierte Admin-E-Mail, Runbook 4 — Stripe-/Cloudflare-/Resend-Ausfall

### Community 7 - "Community 7"
Cohesion: 0.22
Nodes (8): AFF-002 — Android App-Link-Attribution via Explicit Intent fälschbar, AFF-005 — GitHub Actions nicht SHA-gepinnt, AFF-009 — App-Links-Zertifikatsverifikation abhängig von Produktionsvariable, AFF-010 — CSP erlaubt `'unsafe-inline'` für script-src, AFF-011 — Login-CSRF (Magic-Link-Phishing), CORE-001 — Pro-Freischaltung client-seitig durchgesetzt, CORE-002 — Keine Verschlüsselung lokaler Daten „at rest"; HTTP auf Loopback, Residual Risk Acceptance — Affiliate Program

### Community 8 - "Community 8"
Cohesion: 0.22
Nodes (8): 1. System Context, 2. Assets & Schutzbedarf, 3. Trust Boundaries, 4. STRIDE, 5. Abuse & Fraud Cases, 6. Single Points of Failure / kritische Abhängigkeiten, code:block1 (┌──────────────────────────┐), Threat Model — Historical Affiliate Program (STRIDE)

### Community 9 - "Community 9"
Cohesion: 0.25
Nodes (7): Android-Angriffsfläche, Attack Surface Map — Affiliate Program, Cloudflare/Plattform-Angriffsfläche, Externe Abhängigkeiten als indirekte Angriffsfläche, Session-geschützte Endpunkte (Admin-Rolle), Session-geschützte Endpunkte (Partner-Rolle), Öffentlich erreichbare HTTP-Endpunkte (kein Auth erforderlich)

### Community 10 - "Community 10"
Cohesion: 0.25
Nodes (7): 1. Migrationen sind idempotent-additiv und reproduzierbar, 2. Datenintegrität nach (simuliertem) Restore ist über die Hash-Ketten nachweisbar, 3. Reconciliation nach Restore erkennt Drift gegenüber Stripe, Backup & Restore — Plan und lokale Verifikation, Empfohlener Praxistest vor Produktionsfreigabe (aus HANDOVER §6.5, weiterhin verbindlich), Was in dieser Sitzung geprüft werden konnte, Was NICHT geprüft werden konnte (erfordert Produktionszugriff)

### Community 11 - "Community 11"
Cohesion: 0.25
Nodes (7): Empfohlene Reihenfolge, L0 — Selbst-Assessment & Transparenz ✅ *(kostenlos, Basis)*, L1 — Automatisierte Verifikation in CI ✅ *(hoher Nutzen/Kosten)*, L2 — Unabhängige Prüfung ◐ *(einmalig, mittlere Kosten: ~ mid 4-stellig €)*, L3 — Formale Siegel ◐/✗ *(teuer, org-/prozessgebunden — Realitäts-Check)*, Prüf- & Zertifizierungs-Leiter — DownloadThat / ClassyDL, Rolle B — Zertifizierer: was verlangt welcher Standard?

### Community 12 - "Community 12"
Cohesion: 0.25
Nodes (7): Betroffenenrechte, Dateninventar, Drittlandtransfer / Auftragsverarbeiter, Löschfristen, Privacy & Data Retention Review — Historical Affiliate Program, Pseudonymisierung/Hashing — bestätigt korrekt umgesetzt, Zweckbindung

### Community 13 - "Community 13"
Cohesion: 0.25
Nodes (7): Availability, Confidentiality, Gesamteinschätzung, Privacy, Processing Integrity, Security (Common Criteria), SOC 2 Readiness Matrix — Affiliate Program

### Community 14 - "Community 14"
Cohesion: 0.29
Nodes (6): Code-Änderungen (Diff dieser Prüfung), Evidence Index — Security Assessments, Nicht-Code-Referenzen, SBOM, Sub-Agent-Reviews (Rohbefunde, in die obigen Dokumente konsolidiert), Testnachweise (mit Ausführungsergebnis am Ende dieser Prüfung)

### Community 15 - "Community 15"
Cohesion: 0.29
Nodes (6): Bewusst verbleibende Risiken, code:text (Play-App -> Google Play Billing -> Play Developer API), Google Play Security Architecture, Release- und Betriebs-Gates, Verbindliche Kontrollen, Vertrauensgrenzen und Assets

### Community 16 - "Community 16"
Cohesion: 0.29
Nodes (6): Lücken / Folgearbeiten, NIST SP 800-218 (SSDF 1.1) Mapping — Affiliate Program, PO — Prepare the Organization, PS — Protect Software, PW — Produce Well-Secured Software, RV — Respond to Vulnerabilities

### Community 17 - "Community 17"
Cohesion: 0.33
Nodes (5): Geprüfte Kategorien (Mapping auf HANDOVER §8.2/§8.3), Methodik, Penetration Test Plan — Affiliate Program, Scope, Werkzeuge

### Community 18 - "Community 18"
Cohesion: 0.33
Nodes (5): Empfehlung vor Produktionsfreigabe, Kartendaten-Fluss (tatsächlicher Code-Nachweis), PCI DSS Scope Assessment — Affiliate Program, Vorläufige Einschätzung (nicht verbindlich), Was diese Prüfung NICHT leisten kann

### Community 19 - "Community 19"
Cohesion: 0.33
Nodes (5): Definition-of-Done-Abgleich, Ergebnis, Security Assessment Report — DownloadThat Creator/Affiliate Program, Vorgehen, Was diese Prüfung ausdrücklich nicht ist

### Community 20 - "Community 20"
Cohesion: 0.4
Nodes (4): DRM / Technical-Protection-Measure Circumvention Audit, Ergebnis: KEINE DRM-/TPM-Umgehung im Code, Erhaltungsauflage, Wichtige Nuance (für die anwaltliche Bewertung)

### Community 21 - "Community 21"
Cohesion: 0.4
Nodes (4): Automatisches No-Go (aus HANDOVER §12, unverändert gültig), Durch diese Prüfung erledigt / verifiziert, Production Security Checklist — Historical Affiliate Program, Vor Produktionsaktivierung weiterhin zwingend erforderlich (nicht durch diese Sitzung leistbar)

### Community 22 - "Community 22"
Cohesion: 0.4
Nodes (4): Affiliate Program – Risk / Findings Register, Einordnung nach HANDOVER.md-Schweregradskala, Gesamtstatus (kanonisch — maßgeblich für jede Zusammenfassung dieser Prüfung), Warum AFF-002 nicht als blockierendes P1 eingestuft wird

### Community 23 - "Community 23"
Cohesion: 0.5
Nodes (3): Einordnung, EU Cyber Resilience Act (CRA) — Gap-Analyse, Priorisierte Lücken (bis 2027)

### Community 24 - "Community 24"
Cohesion: 0.5
Nodes (3): Level-3-relevante Vertiefung (Zahlungs-/Finanz-/Admin-/Integritätsbereich), OWASP ASVS 5.0.0 Mapping — Affiliate Program, Zusammenfassung

## Knowledge Gaps
- **145 isolated node(s):** `Level-3-relevante Vertiefung (Zahlungs-/Finanz-/Admin-/Integritätsbereich)`, `Zusammenfassung`, `Zusammenfassung`, `Öffentlich erreichbare HTTP-Endpunkte (kein Auth erforderlich)`, `Session-geschützte Endpunkte (Partner-Rolle)` (+140 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Detail-Findings` connect `Community 3` to `Community 4`?**
  _High betweenness centrality (0.006) - this node is a cross-community bridge._
- **Why does `Red-Team-Report — Downloader-Kern, On-Device-Server & Android-App` connect `Community 4` to `Community 3`?**
  _High betweenness centrality (0.005) - this node is a cross-community bridge._
- **What connects `Level-3-relevante Vertiefung (Zahlungs-/Finanz-/Admin-/Integritätsbereich)`, `Zusammenfassung`, `Zusammenfassung` to the rest of the system?**
  _145 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.12 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.13 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.13 - nodes in this community are weakly interconnected._