# Google Play Betrieb und Konfiguration

## Runtime-Secrets und Variablen

Die endgültigen Namen werden vom Backend-Code erzwungen und müssen in Cloudflare
Pages sowie dem Deployment-Workflow identisch gesetzt sein. Niemals Tokens,
Service-Account-JSON oder private `age`-Schlüssel in Git oder App-Artefakte legen.

- Google-Play-Service-Account mit minimalen Rechten zum Lesen und Bestätigen von Käufen
- Purchase-Token-Verschlüsselungsschlüssel (32 zufällige Bytes, getrennt vom OAuth-Key)
- Erwartete RTDN-OIDC-Audience und Push-Service-Account-E-Mail
- Paket-ID `de.classydl.app`, Produkt-ID `pro`; sichtbarer Name `DownloadThat Pro`
- `PLAY_STORE_URL`: stabiles Paket-Listing
  `https://play.google.com/store/apps/details?id=de.classydl.app`; der Link
  bleibt für neue Play-Versionen unverändert

Exakte Cloudflare/GitHub-Namen:

- `GOOGLE_PLAY_SERVICE_ACCOUNT_EMAIL`
- `GOOGLE_PLAY_SERVICE_ACCOUNT_PRIVATE_KEY`
- `PLAY_TOKEN_ENCRYPTION_KEY` (Base64 von exakt 32 Zufallsbytes)
- `PLAY_RTDN_AUDIENCE`, `PLAY_RTDN_SERVICE_ACCOUNT_EMAIL`
- `PLAY_RECONCILIATION_SECRET`
- `PLAY_REFUND_ADMIN_TOKEN` (separater, zufälliger Bearer-Token für die manuelle Queue)
- `PLAY_AUTOMATED_REFUNDS_ENABLED=false` bis Migration, Berechtigungen und echter
  Internal-Track-Test vollständig bestanden sind; erst danach `true`
- Variablen `PLAY_STORE_URL`, `LICENSE_API_BASE_URL`
- `PUBLIC_BASE_URL=https://downloadthat.app`
- `CANONICAL_REDIRECT_ENABLED` bleibt bis zur verifizierten Custom Domain `false`
  und wird anschließend auf `true` gesetzt.

Produktionsendpunkte:

- Lizenz/API-Basis: `https://downloadthat.app`
- RTDN Audience und Pub/Sub Push: `https://downloadthat.app/api/play/rtdn`
- Reconciliation: `https://downloadthat.app/api/play/reconcile`
- Refund-Anfrage (nur aus der Play-App, mit live verifiziertem Purchase-Token):
  `https://downloadthat.app/api/play/refunds/request`
- Manuelle Queue (Bearer-geschützt):
  `https://downloadthat.app/api/admin/play-refunds`

## Service-Account-Identität und Refund-Recht prüfen

GitHub Actions enthält die benötigten Secret-Namen. Das beweist weder die
Gültigkeit des Schlüssels noch die Berechtigungen in Play Console; beides wird
erst durch den echten Internal-Track-Upload und Kauf-/Refund-Test bestätigt.

1. Google Play Console öffnen und `DownloadThat` wählen.
2. **Nutzer und Berechtigungen** öffnen. Falls die Console stattdessen auf die
   Google Cloud Console verweist, dort unter **IAM und Verwaltung →
   Dienstkonten** die E-Mail des vorgesehenen Kontos kopieren.
3. In Play Console muss genau diese E-Mail als Nutzer/Service-Account für
   `DownloadThat` sichtbar sein. Für den Backend-Betrieb sind Kaufstatus lesen
   sowie Bestellungen verwalten/erstatten nötig. Für den CI-Upload zusätzlich
   ausschließlich **Apps in Testtracks veröffentlichen** erteilen; keine
   Produktions-, Finanzbericht- oder Kontoadministratorrechte hinzufügen.
4. Die E-Mail als `GOOGLE_PLAY_SERVICE_ACCOUNT_EMAIL`, den zugehörigen privaten
   PKCS#8-Schlüssel als verschlüsseltes
   `GOOGLE_PLAY_SERVICE_ACCOUNT_PRIVATE_KEY` und einen unabhängigen
   32-Byte-Schlüssel als `PLAY_TOKEN_ENCRYPTION_KEY` in Cloudflare Pages unter
   **Workers & Pages → downloadthat → Settings → Variables and Secrets** setzen.
5. Migration `0013_google_play_refunds.sql` zuerst auf Staging/lokal und danach
   kontrolliert auf D1 anwenden. `PLAY_AUTOMATED_REFUNDS_ENABLED` bleibt `false`.
6. Mit einem echten License-Tester-Kauf Kauf, Lieferung, manuelle Queue und
   genau eine Erstattung prüfen. Erst dann den Schalter auf `true` setzen.

Die App akzeptiert weder eine frei eingegebene GPA-Bestellnummer noch eine
behauptete Zahlung. Vor jedem neuen Refund prüft der Server den geheimen
Purchase-Token live bei Google, Produkt `pro`, Paket `de.classydl.app`, Status
`PURCHASED` und die gespeicherte Order. Derselbe Kauf kann nur einen Datensatz
erzeugen. Ein zweiter bereits erstatteter Kauf desselben Installationsgeräts,
ein Gerätewechsel, fehlende Kaufzeit und jede Google-API-Abweichung gehen immer
in die manuelle Prüfung.

Regelwerk:

- bis 48 Stunden: automatisch, sofern der Sicherheitsschalter aktiv ist und
  kein Wiederholungsmuster vorliegt;
- Tag 3 bis 14: nur bei Grund `technical_failure` und fehlender bestätigter
  Pro-Lieferung automatisch; sonst manuell;
- nach 14 Tagen: immer manuell;
- jede Erstattung ruft Google mit `revoke=true` auf und deaktiviert die Lizenz.

Nach bestätigten Erstattungen sperrt das Backend nur einen weiteren Pro-Kauf;
die kostenlose Nutzung bleibt vollständig verfügbar. Die Staffel ist:

- nach der ersten Erstattung: 1 Tag;
- nach der zweiten: 7 Tage;
- nach der dritten: 30 Tage;
- ab der vierten: 180 Tage.

Für wiederholbare Release-Tests kann ein Administrator anhand der ID einer
bereits erstatteten Anfrage eine zeitlich begrenzte Ausnahme setzen, ohne die
Historie zu löschen (PowerShell, Token nur lokal als Umgebungsvariable halten):

```powershell
$headers = @{ Authorization = "Bearer $env:PLAY_REFUND_ADMIN_TOKEN" }; $body = @{ id = "REFUND_REQUEST_ID"; action = "grant_test_bypass"; hours = 24 } | ConvertTo-Json; Invoke-RestMethod -Method Post -Uri "https://downloadthat.app/api/admin/play-refunds" -Headers $headers -ContentType "application/json" -Body $body
```

Der Finanzworkflow verwendet `GCP_WORKLOAD_IDENTITY_PROVIDER`,
`GCP_FINANCE_ARCHIVER_SERVICE_ACCOUNT`, `PLAY_REPORTS_SOURCE_URI`,
`GCS_FINANCE_ARCHIVE_BUCKET` und den ausschließlich öffentlichen
`FINANCE_AGE_RECIPIENT`. Der private `age`-Schlüssel bleibt offline.

PowerShell zum Erzeugen des Token-Schlüssels (Ausgabe direkt als Secret setzen):

```powershell
$b = [byte[]]::new(32); [Security.Cryptography.RandomNumberGenerator]::Fill($b); [Convert]::ToBase64String($b)
```

Einmalige Offline-Erzeugung des Finanzschlüssels nach Installation von `age`:

```powershell
age-keygen -o C:\DownloadThat\Offline-Keys\finance-age-key.txt
```

Nur die mit `# public key:` ausgegebene `age1...`-Zeile kommt als
`FINANCE_AGE_RECIPIENT` in CI.

## Releasefolge

1. CI baut `playRelease` als AAB und `directRelease` als APK.
2. CI prüft Version, Zertifikat, 16-KiB-Ausrichtung, SBOM, Hashes und Flavor-Trennung.
3. Der Release-Workflow lädt das geprüfte AAB automatisch ausschließlich in
   den Internal Track; Produktion bleibt eine bewusste Play-Console-Freigabe.
4. Internal Track: Kauf, Pending, Abbruch, Restore, Refund, RTDN testen.
5. Closed Test und Pre-launch Report auswerten.
6. Data Safety/Rating/Target Audience/App Access bestätigen.
7. Erst dann Produktion. Die Website und App verwenden schon das stabile
   Paket-Listing; der direkte APK-Link folgt automatisch dem neuesten GitHub Release.

Der aktive Play-first-Betrieb benötigt keine Stripe-Schlüssel. Der einmalige
`Commerce decommission preflight` archiviert nach der Owner-Prüfung nur noch den
D1-Stand; Stripe-Sandboxdaten verbleiben bei Stripe und sind keine
Laufzeitabhängigkeit der App oder Website.

## Finance

Einmalige Bucket-Vorbereitung (PowerShell im Repository-Root):

```powershell
.\scripts\setup-google-play-finance-archive.ps1 -ProjectId <projekt> -BucketName downloadthat-finance-archive-<projekt>
```

Das irreversible Lock erfolgt separat und erst nach Restore-Test:

```powershell
.\scripts\setup-google-play-finance-archive.ps1 -ProjectId <projekt> -BucketName downloadthat-finance-archive-<projekt> -LockRetention -LockConfirmation LOCK-10-YEARS
```

Der monatliche Workflow benötigt Workload Identity, den Play-Report-Bucket,
Zielbucket und den öffentlichen `age`-Empfänger. Der private `age`-Schlüssel wird
offline gesichert und niemals CI bereitgestellt. Der lokale Task ruft anschließend
`scripts/sync-google-play-finance-archive.ps1` auf. Der erwartete Bankeingang bleibt
bis zur manuellen Bestätigung als Ausnahme offen.

Wiederholbarer lokaler Abruf (PowerShell im Repository-Root):

```powershell
.\scripts\sync-google-play-finance-from-gcs.ps1 -BucketName downloadthat-finance-archive-<projekt>
```

Für die Aufgabenplanung wird genau dieser Aufruf monatlich nach dem 10. hinterlegt;
das verwendete Windows-Konto benötigt nur Leserechte auf den Archivpfad und den
Zielordner. Der Kopiervorgang prüft SHA-256 nach dem Schreiben.
