# Prüf- & Zertifizierungs-Leiter — DownloadThat / ClassyDL

Datum: 2026-07-13. Zweck: die eine Frage „erfüllt das Produkt Standards?" in eine
**gestufte Leiter** übersetzen — von kostenloser Selbst-Attestierung bis zu formalen
Siegeln — und für jede Stufe ehrlich markieren, was für ein **12-€-Solo-Produkt**
verhältnismäßig ist. Jede Stufe hat ein **Gate**: erst wenn es grün ist, lohnt die
nächste.

Verhältnismäßigkeits-Legende: ✅ sinnvoll · ◐ situativ/optional · ✗ Overkill für dieses Produkt.

---

## L0 — Selbst-Assessment & Transparenz ✅ *(kostenlos, Basis)*

Das ist, was CCC-/Hacker-Kritiker tatsächlich überzeugt: nicht ein gekauftes Siegel,
sondern nachvollziehbare, offene Belege.

| Baustein | Status | Artefakt |
|---|---|---|
| OWASP ASVS v5 Selbst-Assessment (Web/API + On-Device-Server) | ⚠️ in Arbeit | `ASVS_5_MATRIX.md` (Backend erledigt) + `ASVS_CORE_APP_ADDENDUM.md` (neu) |
| OWASP MASVS Selbst-Assessment (Android) | ✅ neu | `MASVS_MATRIX.md` |
| Öffentliches Threat Model (STRIDE) für die ganze App | ✅ | `THREAT_MODEL.md` + `RED_TEAM_REPORT_CORE_APP.md` |
| Coordinated-Disclosure-Policy + `security.txt` | ✅ neu | `/SECURITY.md`, `pro/website/.well-known/security.txt` |
| SBOM veröffentlicht | ⚠️ | `sbom.cdx.json` (auf App-Deps erweitern) |
| Reproducible-Build-Nachweis (APK) | ◐ offen | `android-release.yml` publiziert bereits SHA-256; Reproduzierbarkeit noch nicht verifiziert |

**Gate L0:** ASVS-L1 + MASVS-L1 vollständig durchgegangen, jedes „nein" mit
Risiko-Akzeptanz begründet (`RESIDUAL_RISK_ACCEPTANCE.md`). → **fast erreicht.**

---

## L1 — Automatisierte Verifikation in CI ✅ *(hoher Nutzen/Kosten)*

Belegt kontinuierlich, dass die Codebasis geprüft wird — nicht nur einmalig.

| Baustein | Status | Artefakt |
|---|---|---|
| Dependency-Updates automatisiert | ✅ neu | `.github/dependabot.yml` (pip/npm/gradle/**github-actions**) |
| SAST (Python) | ✅ neu | `bandit` in `security-scan.yml`, Gate: fail-on-High |
| „Broken-code"-Gate | ✅ neu | `ruff` (E9/F63/F7/F82) in `security-scan.yml` |
| Haupt-Testsuite in CI | ✅ neu | `security-scan.yml` (lief zuvor **nicht** in CI — nur Affiliate-Tests) |
| Code-Scanning | ✅ neu | `.github/workflows/codeql.yml` (python + javascript) |
| Secret-Scan | ✅ | `test_affiliate_no_secrets.py` (gating) + gitleaks (informativ) |
| Actions-Pinning (AFF-005) | ◐ | Dependabot `github-actions` als nachhaltige Lösung; SHA-Pin optional als Folgeschritt |

**Gate L1:** CI grün inkl. Security-Jobs, 0 offene High/Critical, SBOM-Drift kontrolliert.
→ **erreicht** (nach diesem Audit).

---

## L2 — Unabhängige Prüfung ◐ *(einmalig, mittlere Kosten: ~ mid 4-stellig €)*

Erst sinnvoll, wenn L0/L1 stehen — sonst bezahlt man einen Auditor für Findings, die
ein Linter gratis gefunden hätte.

| Baustein | Status | Hinweis |
|---|---|---|
| Externer Pentest (Web-API + On-Device-Server + Android) | offen | `PENETRATION_TEST_PLAN.md` auf neuen Scope erweitern |
| Automatisierter Mobile-Scan (MobSF) | offen | ergänzt manuelle WebView-Bridge-Review |
| Manuelle Review der JS-Bridge (`addJavascriptInterface`) | offen | wichtigster App-spezifischer Kontrollpunkt |

**Gate L2:** externer Report vorhanden, alle P0/P1 geschlossen, Re-Test bestanden.

---

## L3 — Formale Siegel ◐/✗ *(teuer, org-/prozessgebunden — Realitäts-Check)*

| Ziel | Verhältnismäßigkeit | Einschätzung |
|---|---|---|
| **Google Play Data-Safety / App Defense Alliance** | ◐ | Nur relevant bei Play-Store-Vertrieb. Heute Sideload-first → optional; die Data-Safety-Angaben lassen sich bereits ehrlich vorbereiten. |
| **EU Cyber Resilience Act (CRA)** | ◐ (wichtigstes formales Ziel) | Als in der EU vertriebenes Produkt mit digitalen Elementen ab 2027 verpflichtend: Schwachstellen-Handling, Update-Pflicht, SBOM, Konformitätserklärung. Gap-Analyse: `CRA_GAP_ANALYSIS.md`. |
| **BSI (z. B. TR/Zertifizierung)** | ✗ für Solo-Produkt | Schwer, für eine Einzel-App unverhältnismäßig; CRA deckt den regulatorischen Kern praxisnäher ab. |
| **ISO 27001** | ✗ | Zertifiziert eine **Organisation/ISMS**, kein Produkt. Für ein Solo-Projekt Aufwand/Kosten unverhältnismäßig. Readiness-Matrix existiert → Status „vorbereitet, nicht angestrebt". |
| **SOC 2** | ✗ | Nur bei B2B/Enterprise-Kunden mit Due-Diligence relevant. Readiness-Matrix existiert → „vorbereitet". |

**Gate L3:** pro Siegel eigener Kriterienkatalog, dokumentierte Go/No-Go-Entscheidung.
→ **Empfehlung: CRA-Gap ernst nehmen (2027), Play-Data-Safety bei Store-Vertrieb; ISO/SOC2
bewusst NICHT anstreben, sondern als vorbereitet ausweisen.**

---

## Rolle B — Zertifizierer: was verlangt welcher Standard?

Verdichtete Kriterienkataloge (Detail in den jeweiligen Matrix-Dateien):

- **OWASP ASVS v5 (L1→L2):** Auth & Session, Zugriffskontrolle je Endpunkt,
  Input-Validierung, Krypto/Secrets-at-rest, sichere Kommunikation, Konfiguration,
  Datenschutz. → `ASVS_5_MATRIX.md` (+ Core-App-Addendum).
- **OWASP MASVS (Android):** Storage (keine Secrets/PII im Klartext, `allowBackup=false`),
  Krypto, Netzwerk (Cleartext nur Loopback), Plattform-Interaktion (WebView-Bridge,
  exportierte Komponenten, App-Links), Code-Qualität/Resilience. → `MASVS_MATRIX.md`.
- **NIST SSDF / SLSA:** Build-Integrität, signierte Releases, Provenienz, SBOM. →
  `NIST_SSDF_MATRIX.md` + `android-release.yml`.
- **EU CRA:** Security-by-design, kostenlose Sicherheitsupdates über den Support-Zeitraum,
  koordinierte Offenlegung, SBOM, Konformitätserklärung. → `CRA_GAP_ANALYSIS.md`.
- **ISO 27001 / SOC 2:** ISMS-/Kontroll-Nachweise (organisatorisch) → Readiness-Matrizen
  vorhanden, Status „vorbereitet".

## Empfohlene Reihenfolge

1. L0 abschließen (ASVS-Core-Addendum + Reproducible-Build-Check) — **jetzt, kostenlos.**
2. L1 grün halten (nach diesem Audit erreicht) — **laufend.**
3. L2 planen, sobald Budget vorhanden; JS-Bridge-Review zuerst.
4. CRA-Gap bis 2027 schließen; ISO/SOC2 nur bei konkretem Kundenbedarf.
