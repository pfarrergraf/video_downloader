# Evidence Index — Affiliate Program Security Assessment

Zentrale Übersicht, welche Evidenz zu welchem Finding/welcher Kontrolle gehört. Enthält bewusst **keine**
Secrets, Zugangsdaten oder personenbezogenen Daten — ausschließlich Verweise auf Code, Tests und
Dokumentation in diesem Repository.

## Code-Änderungen (Diff dieser Prüfung)

| Datei | Änderung | Zugehöriges Finding |
|---|---|---|
| `pro/website/functions/_affiliate.js` | `deviationBps` exportiert; `reverseCommission` mit `changes`-Guard; `checkAffiliateRateLimit` ergänzt; totes `createDynamicCheckout`/`stripePost` entfernt | AFF-003, AFF-004, AFF-007, DoD-5%-Test |
| `pro/website/functions/_affiliate_events.js` | `handleAffiliateDisputeClosed` mit `changes`-Guard in beiden Restaurationszweigen | AFF-003 |
| `pro/website/functions/_affiliate_integrity.js` | `deviationBps` exportiert | DoD-5%-Test |
| `pro/website/functions/api/webhook.js` | Stacktrace aus Fehlerantwort entfernt | AFF-012 |
| `pro/website/functions/api/partner/login-request.js` | Rate Limit ergänzt | AFF-004 |
| `pro/website/functions/api/admin/login-request.js` | Rate Limit ergänzt | AFF-004 |
| `pro/website/functions/api/partner/register.js` | Rate Limit ergänzt | AFF-004 |
| `pro/website/migrations/0009_affiliate_rate_limits.sql` | neue Tabelle `affiliate_rate_limit_attempts` | AFF-004 |
| `pro/website/partner-admin.html` | `esc()`-Escaping für alle interpolierten Felder | AFF-001 |
| `pro/website/partner-dashboard.html` | `esc()`-Escaping für `external_reference`/`status` | AFF-001 |
| `android/app/src/main/java/de/classydl/app/AffiliateReferral.kt` | Host-Vergleich case-insensitive | AFF-008 |
| `tests/test_affiliate_no_secrets.py` | Turnstile-Secret-Muster ergänzt | AFF-006 |
| `tests/test_affiliate_program.py` | neuer Test `test_admin_and_partner_dashboards_html_escape_untrusted_fields` | AFF-001 |
| `pro/website/tests/affiliate_race_conditions.test.mjs` (neu) | 4 Tests: Race-Reproduktion (Refund + Dispute-Restore), Idempotenz, 5%-Grenzsemantik | AFF-003, DoD |
| `pro/website/tests/helpers/fake-d1.mjs` (neu) | D1-Testshim auf `node:sqlite`-Basis, führt echtes `schema.sql`+Migrationen aus | Testinfrastruktur |

## Testnachweise (mit Ausführungsergebnis am Ende dieser Prüfung)

| Nachweis | Ergebnis |
|---|---|
| `uv run pytest tests/ --ignore=tests/test_cli_compat.py --ignore=tests/test_easy_ui.py` | **201 passed** |
| `cd pro/website && node --test tests/*.test.mjs` | **8 passed** (4 bestehend + 4 neu) |
| `cd pro/website && npm run check` | Syntaxprüfung aller Cloudflare Functions: **grün** |
| Race-Condition-Regressionsnachweis | Tests wurden **vor** dem Fix ausgeführt und schlugen reproduzierbar fehl (dokumentiertes Fail-Log in `PENETRATION_TEST_RESULTS.md` AFF-003), nach Wiederherstellung des Fixes wieder grün |

## SBOM

`security/sbom.cdx.json` — CycloneDX 1.6, erzeugt mit `cyclonedx-py environment` gegen die reale, per
`uv sync --extra dev` aufgebaute virtuelle Umgebung dieses Repositories (22 Python-Komponenten). Node
(`pro/website`) hat keine npm-Abhängigkeiten (kein SBOM-Eintrag nötig). Android/Gradle-SBOM wurde **nicht**
erzeugt (keine CycloneDX-Gradle-Plugin-Integration im Projekt vorhanden) — als Folgearbeit in
`PRODUCTION_SECURITY_CHECKLIST.md` vermerkt.

## Sub-Agent-Reviews (Rohbefunde, in die obigen Dokumente konsolidiert)

Diese Prüfung nutzte drei parallele, in sich geschlossene Reviews (Android, Frontend/HTML, CI/Supply-Chain).
Ihre Rohergebnisse sind in `PENETRATION_TEST_RESULTS.md` und `RISK_REGISTER.md` vollständig konsolidiert;
es existiert keine separate Rohdatei, da die Ergebnisse direkt in die finalen Findings-Dokumente überführt
wurden (kein Informationsverlust, aber auch keine doppelte Aufbewahrung von Zwischenständen).

## Nicht-Code-Referenzen

- `HANDOVER.md` — Scope-, Freigabe- und Go-/No-Go-Grundlage dieser Prüfung.
- `docs/AFFILIATE_PROGRAM_IMPLEMENTATION.md` — Implementierungs- und Betriebsdokumentation.
- `CLAUDE.md` — Projektregeln, insbesondere Android-Permission-Guardrail (verifiziert eingehalten).
