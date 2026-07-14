# Owner-Checkliste: Google Play Go-live

Codex bereitet Code, Artefakte und Texte vor. Nur die folgenden Schritte benötigen
den Kontoinhaber. Kein Punkt darf als erledigt angenommen werden, bevor die Console
oder ein Testbeleg ihn bestätigt.

## Eigene Produktionsdomain

- [x] `downloadthat.app` als separate Cloudflare-Zone registriert; `gaistreich.com`
      bleibt unverändert.
- [ ] Play-first-Stand zunächst auf `downloadthat.pages.dev` als Staging prüfen.
- [ ] Im bestehenden Pages-Projekt `downloadthat` die Custom Domains
      `downloadthat.app` und `www.downloadthat.app` verbinden.
- [ ] DNSSEC, Universal SSL, HTTPS und Apex-Erreichbarkeit prüfen.
- [ ] Erst danach `CANONICAL_REDIRECT_ENABLED=true` setzen und Weiterleitungen
      von `www` und `downloadthat.pages.dev` prüfen.
- [ ] Datenschutz- und Website-URL in Play Console auf `downloadthat.app` setzen.

Details: `docs/CLOUDFLARE_DOWNLOADTHAT_APP_SETUP.md`.

## Einmalig vor dem Internal Track

- [ ] Play-Developer-Konto: Identität, Organisation/Privatstatus und Kontaktangaben bestätigen.
- [ ] Payments Profile: Bankkonto, Steuerprofil und Händlerangaben bestätigen.
- [ ] Play-Verträge und erforderliche Erklärungen akzeptieren.
- [x] App mit sichtbarem Namen `DownloadThat` anlegen und das bestehende
      Release-Zertifikat als App-Signing-Key übertragen (SHA-256
      `A4:B5:DB:BA:CE:D2:AD:0B:91:06:BD:D4:65:EC:48:1C:1F:F2:03:FD:77:85:82:2E:1A:F6:E0:7E:C9:74:C9:E4`).
- [ ] Separaten CI-Upload-Key registrieren. Google hat den Reset angenommen; der
      neue Upload-Key wird am `2026-07-16 13:23 UTC` (`15:23 CEST`) aktiv. SHA-1
      `CD:DB:E2:9F:73:92:7E:9F:10:A8:08:55:39:E5:21:D2:2C:23:25:96`, SHA-256
      `5F:BD:61:BC:C8:B2:36:76:E8:E9:CE:33:7C:51:F7:24:34:61:CB:9C:31:C8:19:00:69:32:50:99:35:37:03:CE`
      (lokales Zertifikat abgeglichen). Erst nach Aktivierung abhaken.
- [ ] Beim ersten akzeptierten AAB bestätigen, dass die technische Paket-ID
      `de.classydl.app` gebunden wurde.
- [ ] Produkt-ID `pro` mit sichtbarem Namen `DownloadThat Pro` als nicht
      konsumierbaren Einmalkauf anlegen; Preis
      für EU/EWR auf 12 EUR setzen und länderspezifische Google-Preise prüfen.
- [ ] License Tester und Internal-Track-Tester eintragen.
- [ ] Pub/Sub-Thema, Push-Service-Account und RTDN in Play Console verbinden.
- [ ] GitHub/Cloudflare-Secrets aus `docs/GOOGLE_PLAY_OPERATIONS.md` setzen.
- [ ] Cloudflare Rate-Limiting-Regel für `POST /api/play/purchases/verify`
      aktivieren, damit anonyme Requests keine Google-API-Quota erschöpfen.
- [ ] `Commerce decommission preflight` ausführen, Exporthash prüfen und nur bei
      bestätigten Testdaten `PLAY_DECOMMISSION_APPROVED=true` setzen.
- [ ] Danach alte Stripe-, Resend-, Turnstile- und Affiliate-Secrets in GitHub,
      Cloudflare und den Anbieter-Dashboards widerrufen/löschen.

## Erklärungen, die der Owner bestätigt

- [ ] Data Safety anhand der tatsächlichen Datenflüsse prüfen und absenden.
- [ ] Zielgruppe, Content Rating, App Access und Werbeangaben bestätigen.
- [ ] Datenschutz-/AGB-Texte rechtlich prüfen lassen; keine automatische
      Rechtsfreigabe aus Code oder Dokumentation ableiten.
- [ ] EU/EWR-Länderliste und 12-EUR-Preisvorschau bestätigen.

## Produktions-Gate

- [ ] Echter License-Tester-Kauf, Neuinstallation/Restore und identischer Schlüssel.
- [ ] Schlüssel in Play-App, Direct APK und Windows erfolgreich validiert.
- [ ] Echter Refund/Void deaktiviert die Lizenz über RTDN; Reconciliation ebenfalls getestet.
- [ ] Pre-launch Report ohne blockierende Befunde; Closed Test abgeschlossen.
- [ ] Monatsarchiv aus Muster-/Testbericht erstellt, Hash geprüft, mit Offline-Key
      entschlüsselt und lokaler Spiegel wiederhergestellt.
- [ ] GCS Data-Access-Audit-Logging geprüft; erst danach zehnjährige Retention locken.
- [ ] Bankabgleich-Verantwortliche Person und monatlicher Ausnahmeprozess festgelegt.
