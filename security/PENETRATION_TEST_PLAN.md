# Penetration Test Plan — Affiliate Program

## Scope

**In Scope (diese interne Prüfung):**
- Statische Code-Analyse des gesamten unter `HANDOVER.md` §3 gelisteten Codes.
- Lokale, reproduzierbare dynamische Tests gegen eine In-Memory-SQLite-Instanz (node:sqlite / Python
  `sqlite3`), die `schema.sql` + alle `migrations/*.sql` real ausführt — keine Mock-Daten für Kernlogik.
- Race-Condition-Reproduktion via deterministischer Promise.all-Interleaving-Technik (siehe
  `PENETRATION_TEST_RESULTS.md` AFF-003).
- Statische Android-Manifest-/Kotlin-Analyse.
- Statische CI/Supply-Chain-Analyse.

**Explizit außerhalb des Scopes dieser Sitzung (siehe HANDOVER.md §7.2, §9, §13):**
- Jegliche Anfragen gegen echte Stripe-, Cloudflare-, Resend- oder GitHub-Produktionsendpunkte.
- Lasttests, DoS-/Ressourcenerschöpfungstests.
- Tests mit realen Zahlungen, Refunds, Disputes oder Bankauszahlungen.
- Social Engineering, Phishing, Passwortangriffe gegen reale Personen.
- Externe, unabhängige Penetrationstests, formelle Zertifizierungsaudits.
- Migrationen gegen eine produktive Datenbank.

## Methodik

1. **Vollständige Lektüre** aller in HANDOVER.md §Zuerst-vollständig-lesen gelisteten Dateien (durchgeführt).
2. **Threat Modeling** (STRIDE) vor der Detailprüfung, um Prüfschwerpunkte zu priorisieren (`THREAT_MODEL.md`).
3. **Manuelle Code-Review** der Kernfinanzlogik durch die Hauptsitzung (höchste Kritikalität), parallelisierte
   Sub-Agent-Reviews für Android, Frontend/HTML und CI/Supply-Chain (jeweils mit eigenem, in sich
   geschlossenem Auftrag und Belegpflicht "Datei:Zeile").
4. **Reproduktion** jedes vermuteten Findings mit einem lauffähigen, deterministischen Test **vor** der
   Behebung, um Fehlalarme auszuschließen (durchgeführt für AFF-001, AFF-003; für AFF-002/AFF-005/AFF-009
   ist eine Code-Reproduktion nicht sinnvoll möglich, da es sich um Konfigurations- bzw.
   Plattformgrenzen handelt — dort stattdessen Nachvollzug per Kontrollflussanalyse).
5. **Behebung** auf dem isolierten Branch `security/affiliate-readiness-hardening`.
6. **Retest** mit demselben Reproduktionstest nach der Behebung, plus vollständiger Regressionslauf
   der bestehenden Suite.
7. **Dokumentation** in `PENETRATION_TEST_RESULTS.md` im geforderten Findings-Format.

## Geprüfte Kategorien (Mapping auf HANDOVER §8.2/§8.3)

| Kategorie | Geprüft | Ergebnis |
|---|---|---|
| Authentisierung, Magic Links, Token Replay | Ja | Kein Finding (Einmal-Token, gehasht, 20-Min-TTL) |
| Session Fixation/Theft | Ja | Kein Finding (Session-Hash serverseitig, HttpOnly/Secure) |
| IDOR/BOLA, Rollen-/Mandantentrennung | Ja | Kein Finding |
| CSRF | Ja | Kein Finding (SameSite=Lax + POST-only) |
| XSS | Ja | **AFF-001, behoben** |
| SQL Injection | Ja | Kein Finding (durchgehend parametrisiert) |
| Command Injection | Ja | Kein Finding (kein Shell-Aufruf im Affiliate-Code) |
| SSRF | Ja | Kein Finding (alle ausgehenden Fetches auf feste, hartkodierte Hosts: Stripe/Resend/Turnstile) |
| Open Redirect / Host Header | Ja | Kein Finding |
| CORS | Ja | Kein Finding (keine CORS-Header gesetzt, bewusst same-origin) |
| CSP | Ja | AFF-010 (Härtungsempfehlung, `unsafe-inline`) |
| Cache Poisoning / Cache-Leaks | Ja | Kein Finding (`Cache-Control: no-store` auf sensiblen Routen bestätigt) |
| Parameter Pollution / Mass Assignment | Ja | Kein Finding (alle Insert/Update-Statements mit expliziter Feldliste, kein `Object.assign`-artiges Pattern) |
| Fehler-/Stacktrace-Leaks | Ja | **AFF-012, behoben** |
| Rate Limiting / Brute Force | Ja | **AFF-004, behoben** |
| Sichere Zufallswerte | Ja | Kein Finding (`crypto.getRandomValues`/`crypto.randomUUID`, kein `Math.random()` in sicherheitsrelevantem Code) |
| Kryptografische Verwendung | Ja | Kein Finding (SHA-256 für Hash-Ketten/Tokens, HMAC-SHA256 mit konstantzeitigem Vergleich für Webhook-Signatur) |
| Eigenkäufe, Cookie Stuffing, Fraud Cases | Ja | Siehe `BUSINESS_LOGIC_ABUSE_CASES.md` |
| Race Conditions / Double Spending | Ja | **AFF-003, behoben** |
| Cloudflare/D1/Actions/Supply Chain | Ja | AFF-005, AFF-006 |
| Android (MASVS/MASTG-orientiert) | Ja | AFF-002, AFF-008 |

## Werkzeuge

- Statische Analyse: manuelle Code-Lektüre + gezielte `grep`/Kontrollflussanalyse (kein automatisiertes SAST-
  Tool in dieser Sitzung installiert/ausgeführt — als Folgearbeit in `PRODUCTION_SECURITY_CHECKLIST.md`
  empfohlen: `semgrep`/CodeQL für Cloudflare-Functions-JS).
- Dynamische Reproduktion: `node:sqlite` (In-Memory), Node's eingebauter Test-Runner (`node --test`),
  `pytest` + Python `sqlite3`.
- SBOM: `cyclonedx-py` gegen die reale `uv`-Umgebung (siehe `security/sbom.cdx.json`).
