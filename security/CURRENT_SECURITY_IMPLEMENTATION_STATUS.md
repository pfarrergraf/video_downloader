# Current Security Implementation Status

Stand: 2026-07-14. Architektur: Google Play ist die einzige Kasse; direkte APK
und Windows sind sekundäre Aktivierungskanäle. Dieses Dokument ist die aktuelle
Security-Zusammenfassung. Affiliate-/Stripe-Berichte bleiben historische Evidenz.

## Kurzfazit

Die wesentlichen Befunde aus `security/` wurden in Code, Tests und Release-Prozesse
überführt. Besonders SSRF, lokale Geheimnisse, Desktop-Autologin, Web-Header,
DRM-Invariante und Play-Kaufprüfung sind nicht nur dokumentiert, sondern technisch
abgesichert. Eine formale Zertifizierung oder externe Prüfung ist damit nicht behauptet.

## Umgesetzte Kontrollen

| Bereich | Umsetzung und Evidenz | Status |
|---|---|---|
| SSRF beim Seitenscan | `video_downloader/scraper.py` validiert Schema, aufgelöste IPs und jeden Redirect-Hop; Regressionen in `tests/test_scraper.py` und `tests/test_web_server.py`. | umgesetzt |
| Lokale Secrets | `video_downloader/server.py` schützt Secret-Dateien/-Verzeichnisse; Berechtigungsprüfung in `tests/test_web_server.py`. | umgesetzt |
| Desktop-Login | Einmaliger Token statt Passwort in URL; Tests in `tests/test_desktop_web_entry.py` und `tests/test_web_server.py`. | umgesetzt |
| Lokale Weboberfläche | Login-Drosselung, konstante Vergleiche, CSP, Frame-/MIME-Schutz; Server-Regressionstests vorhanden. | umgesetzt |
| DRM/TPM | Keine Entschlüsselungswerkzeuge und kein `allow_unplayable_formats`; fail-closed Test `tests/test_no_drm_circumvention.py`. | umgesetzt |
| Android-Härtung | Minimale Berechtigungen, Backup aus, nicht exportierte Komponenten, Cleartext nur Loopback und externe WebView-Navigation außerhalb der App. | umgesetzt |
| Play Billing | Server prüft Paket, Produkt und `PURCHASED`; Token verschlüsselt und gehasht; idempotente Lizenz, Acknowledgement, OIDC-geprüfte RTDN, Refund/Revoke und Reconciliation in `pro/website/functions/_google_play.js`. | umgesetzt, Produktionstest offen |
| Lizenzprüfung | Neue POST-Prüfung und maximal 72 Stunden Offline-Grace in `pro/website/functions/_license_validation.js`. | umgesetzt |
| CI/Supply Chain | SAST, Tests, Secret-Scan und CodeQL; alle Drittanbieter-Actions auf Commit-SHA gepinnt, geschützt durch `tests/test_ci_supply_chain.py`. | umgesetzt |
| Website-CSP | `script-src 'self'`; aktive Inline-Skripte entfernt und durch Website-Test geschützt. Inline-Styles bleiben vorerst erlaubt. | umgesetzt mit Einschränkung |
| Öffentliche Aussagen | Kanonische Policy `security/PUBLIC_CLAIMS_POLICY.md`, Scanner `scripts/check_public_claims.py`, CI- und Deployment-Gate; alte Creator-/Affiliate-Quellen entfernt. | umgesetzt |

## Geschlossene Befunde dieses Bereinigungspasses

- **SEC-COPY-001 / Medium – geschlossen:** Widersprüchliche Alttexte konnten universelle Quellenabdeckung, Anti-Store-Positionierung oder absolute Offline-/Cloud-Aussagen erneut erzeugen. Quellen und öffentliche Assets wurden entfernt, aktive Übersetzungen bereinigt und ein fail-closed Scanner ergänzt.
- **AFF-005 / Medium – geschlossen:** Drittanbieter-GitHub-Actions sind auf verifizierte Commit-SHAs gepinnt; die Wrangler-CLI ist exakt versioniert.
- **AFF-010 / Low – geschlossen:** `script-src 'unsafe-inline'` wurde entfernt; Initialisierung liegt in einer externen Datei.
- **DRM-AUDIT-FOLLOWUP – geschlossen:** Die empfohlene automatische Invariantenprüfung existiert in `tests/test_no_drm_circumvention.py`.

## Noch offene Gates

- **Medium / Produktionsgate:** echter interner Play-Kauf, Wiederherstellung, Refund/Widerruf, RTDN und Reconciliation gegen Google müssen grün belegt sein.
- **Medium / Produktionsgate:** Data-Safety-, App-Access-, Zielgruppen- und Datenschutzangaben müssen anhand der realen Datenflüsse bestätigt werden.
- **Medium / unabhängige Evidenz:** externer Pentest sowie manueller L2-Review der Android-WebView-/Bridge-Grenzen stehen aus.
- **Medium / Betrieb:** Restore-Test des Produktions-Finanzarchivs und Bankabgleich bleiben vor Launch bzw. monatlich nachzuweisen.
- **Low / Prozess:** CRA-Supportzeitraum, Schwachstellenmeldeprozess und Konformitätsunterlagen müssen vor den jeweils anwendbaren Fristen finalisiert werden. Rechtliche und steuerliche Bewertung bleibt bei qualifizierten Stellen.

## Verbindliche Prüfungen

```powershell
uv run python scripts/check_public_claims.py
uv run pytest -q
uv run ruff check video_downloader/ scripts/check_public_claims.py
uv run bandit -c pyproject.toml -r video_downloader/ -q --severity-level high
```

Für die Website zusätzlich in `pro/website`: `npm test` und `npm run check`.
