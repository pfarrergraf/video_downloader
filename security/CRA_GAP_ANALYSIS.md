# EU Cyber Resilience Act (CRA) — Gap-Analyse

Datum: 2026-07-13. Der CRA (Verordnung (EU) 2024/2847) gilt für „Produkte mit
digitalen Elementen", die in der EU bereitgestellt werden. Zentrale Pflichten greifen
ab **2027**; die Meldepflicht für aktiv ausgenutzte Schwachstellen früher. DownloadThat
ist ein solches Produkt. Dies ist **keine Rechtsberatung**, sondern eine technische
Selbst-Einschätzung als Vorbereitung.

Legende: ✅ erfüllt · ⚠️ teilweise · ❌ offen · N/A

| CRA-Anforderung (Anhang I, paraphrasiert) | Status | Beleg / To-do |
|---|---|---|
| **Security-by-design & -default** | ✅ (nach Audit) | Default-Loopback-Bind, SSRF-Guard, CSP, `0600`-Secrets, minimale Android-Permissions |
| **Keine bekannten ausnutzbaren Schwachstellen bei Auslieferung** | ⚠️ | SAST/CodeQL/Dependabot in CI (neu); L2-Pentest ausstehend |
| **Sichere Standardkonfiguration** | ✅ | Web-UI startet nur mit Passwort; Bind default `127.0.0.1`; Cleartext nur Loopback |
| **Schutz der Vertraulichkeit (Verschlüsselung/Zugriffsschutz)** | ⚠️ | Zugriffsschutz via Dateirechte `0600`; **keine Verschlüsselung at rest** (Restrisiko akzeptiert, `RESIDUAL_RISK_ACCEPTANCE.md`) |
| **Schutz der Integrität (Code/Daten/Config)** | ✅ | Signierte Releases + SHA-256; yt-dlp-Self-Update mit SHA-256-Verifikation & No-Downgrade |
| **Datenminimierung** | ✅ | Nur nötige Daten; lokale DSAR-Löschung `classydl purge-data` (neu) |
| **Angriffsflächen-Minimierung** | ✅ | 4 Android-Permissions; nicht-exportierte Service/Provider; enge App-Links |
| **Resilienz gegen DoS** | ⚠️ | Login-Lockout, SSE-Client-Cap; Loopback-Modell begrenzt Exposition |
| **Sicherheitsupdates über Support-Zeitraum, kostenlos** | ⚠️ | Releases signiert; **kein Auto-Update-Kanal** (Sideload/Beta) — Update-Prozess & Support-Zeitraum definieren |
| **Koordinierte Schwachstellen-Offenlegung (CVD)** | ✅ neu | `/SECURITY.md` + `security.txt` (RFC 9116) |
| **SBOM (maschinenlesbar)** | ⚠️ | `sbom.cdx.json` (CycloneDX) vorhanden; auf App-/Android-Deps erweitern |
| **Meldepflicht aktiv ausgenutzter Schwachstellen** | ⚠️ | `INCIDENT_RESPONSE_PLAN.md` vorhanden; CRA-Meldewege (ENISA/CSIRT) ergänzen |
| **Konformitätserklärung & technische Doku** | ❌ | Vor Marktbereitstellung 2027 zu erstellen |

## Priorisierte Lücken (bis 2027)

1. **Support-/Update-Policy** definieren: Support-Zeitraum, wie Sicherheitsupdates
   ausgeliefert werden (auch Sideload braucht einen dokumentierten Update-Weg).
2. **SBOM erweitern** auf App-/Android-Abhängigkeiten und in CI aktuell halten.
3. **CVD-Meldewege** um CRA-konforme Behörden-Meldung ergänzen.
4. **Konformitätserklärung + technische Dokumentation** erstellen (näher an 2027).

## Einordnung

Der technische Kern (Security-by-design, Integrität, CVD, Datenminimierung) ist nach
diesem Audit weitgehend erfüllt. Die offenen Punkte sind überwiegend **prozessual/dokumentarisch**
(Update-Policy, Konformitätserklärung, Meldewege) — machbar für ein Solo-Produkt, aber
rechtzeitig vor 2027 anzugehen. Der CRA ist damit das realistisch wichtigste **formale**
Ziel, nicht ISO/SOC2.
