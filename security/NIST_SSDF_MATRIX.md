# NIST SP 800-218 (SSDF 1.1) Mapping — Affiliate Program

Interne Readiness-Bewertung, keine formelle Attestierung.

## PO — Prepare the Organization

| Praktik | Status | Evidenz |
|---|---|---|
| PO.1 Sicherheitsanforderungen definiert | ✅ | `HANDOVER.md` enthält explizite, testbare Finanz-/Sicherheitsinvarianten |
| PO.3 Werkzeuge/Umgebungen für sicheres Entwickeln | ✅ | `uv` für Python-Dependency-Pinning, D1-Migrationen versioniert, CI-Workflow pro PR |
| PO.5 sichere Entwicklungsumgebung | ⚠️ | GitHub-Actions-Pinning noch auf Tag-Ebene (AFF-005) |

## PS — Protect Software

| Praktik | Status | Evidenz |
|---|---|---|
| PS.1 Schutz vor unbefugter Änderung | ✅ | Branch Protection (angenommen aktiv, außerhalb Repo-Scope prüfbar), append-only DB-Trigger |
| PS.2 Integritätsnachweis für Release-Artefakte | ⚠️ | Kein Signieren/Provenance-Nachweis für Cloudflare-Pages-Deployment sichtbar; Android-Release-Signing vorhanden (`android-release.yml`) |
| PS.3 Archivierung/Schutz jeder Softwareversion | ✅ | Git-Historie + GitHub Releases (Android) |

## PW — Produce Well-Secured Software

| Praktik | Status | Evidenz |
|---|---|---|
| PW.1 Sicherheitsanforderungen in Design | ✅ | Threat Model, harte Finanzinvarianten von Anfang an im Schema (`CHECK`-Constraints) |
| PW.4 Wiederverwendung geprüfter Software statt Neuerfindung | ✅ | Stripe Checkout (kein eigenes Kartendaten-Handling), Cloudflare Turnstile statt Eigenbau-CAPTCHA |
| PW.5 Sichere Coding-Praktiken (Eingabevalidierung, parametrisierte Queries) | ✅ | Durchgängig `.bind()`, keine SQL-Konkatenation |
| PW.6 Kompilierungs-/Build-Härtung | N/A | Keine kompilierten Artefakte im Web-Teil; Android: ProGuard/R8 außerhalb dieses Scopes geprüft |
| PW.7 Code-Review vor Merge | ✅ (durch diese Prüfung nachgeholt) | Diese Sitzung selbst ist ein vertieftes Review vor Merge in `feature/affiliate-partner-program` |
| PW.8 Testen auf bekannte Schwachstellenklassen | ✅ | XSS, Race Conditions, IDOR, CSRF, SQLi systematisch geprüft (siehe `PENETRATION_TEST_PLAN.md`) |
| PW.9 Konfiguration mit sicheren Standardwerten | ✅ | `AFFILIATE_PROGRAM_ENABLED=false` Default, `payout_frozen=1` Default in Migration |

## RV — Respond to Vulnerabilities

| Praktik | Status | Evidenz |
|---|---|---|
| RV.1 Schwachstellen identifizieren/beheben fortlaufend | ✅ (dieser Zyklus) | 12 Findings identifiziert, 9 behoben, 3 mit begründeter Ausnahme dokumentiert |
| RV.2 Ursachenanalyse statt Symptombehandlung | ✅ | Fixes adressieren die zugrunde liegende Race-Condition-Ursache (fehlende `changes`-Prüfung), nicht nur Symptome |
| RV.3 Regressionstests für jede Behebung | ✅ | Neue Tests für AFF-001, AFF-003, AFF-006; bestehende Suite vollständig grün nachgewiesen |

## Lücken / Folgearbeiten

- Kein automatisiertes SAST/SCA-Tool in der CI-Pipeline dieser Sitzung ergänzt (empfohlen: `semgrep`/CodeQL,
  `pip-audit`/`osv-scanner`, siehe `PRODUCTION_SECURITY_CHECKLIST.md`).
- Kein formeller Vulnerability-Disclosure-Prozess/Security-Kontakt öffentlich dokumentiert (HANDOVER §5.7,
  weiterhin offen).
