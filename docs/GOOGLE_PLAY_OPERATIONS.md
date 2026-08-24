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
- Variablen `PLAY_STORE_URL`, `LICENSE_API_BASE_URL`
- `PUBLIC_BASE_URL=https://downloadthat.app`
- `CANONICAL_REDIRECT_ENABLED` bleibt bis zur verifizierten Custom Domain `false`
  und wird anschließend auf `true` gesetzt.

Produktionsendpunkte:

- Lizenz/API-Basis: `https://downloadthat.app`
- RTDN Audience und Pub/Sub Push: `https://downloadthat.app/api/play/rtdn`
- Reconciliation: `https://downloadthat.app/api/play/reconcile`

DownloadThat betreibt keinen eigenen Refund-Endpunkt und keine Admin-Queue.
Erstattungen werden ausschließlich in Google Play verwaltet. Ein von Google als
erstattet, storniert oder widerrufen bestätigter Kauf entzieht Pro über RTDN;
verpasste Benachrichtigungen werden durch Reconciliation korrigiert. Historische
Refund-Tabellen und Migrationen bleiben als Finanz- und Auditnachweis erhalten,
sind aber kein aktiver Produktpfad.

## Service-Account-Identität und Revoke-Pfad prüfen

GitHub Actions enthält die benötigten Secret-Namen. Das beweist weder die
Gültigkeit des Schlüssels noch die Berechtigungen in Play Console; beides wird
erst durch den echten Internal-Track-Upload und Kauf-/Revoke-Test bestätigt.

1. Google Play Console öffnen und `DownloadThat` wählen.
2. **Nutzer und Berechtigungen** öffnen. Falls die Console stattdessen auf die
   Google Cloud Console verweist, dort unter **IAM und Verwaltung →
   Dienstkonten** die E-Mail des vorgesehenen Kontos kopieren.
3. In Play Console muss genau diese E-Mail als Nutzer/Service-Account für
   `DownloadThat` sichtbar sein. Für den Backend-Betrieb sind Kaufstatus lesen
   sowie den für Verifikation und Reconciliation erforderlichen Zugriff. Für den CI-Upload zusätzlich
   ausschließlich **Apps in Testtracks veröffentlichen** erteilen; keine
   Produktions-, Finanzbericht- oder Kontoadministratorrechte hinzufügen.
4. Die E-Mail als `GOOGLE_PLAY_SERVICE_ACCOUNT_EMAIL`, den zugehörigen privaten
   PKCS#8-Schlüssel als verschlüsseltes
   `GOOGLE_PLAY_SERVICE_ACCOUNT_PRIVATE_KEY` und einen unabhängigen
   32-Byte-Schlüssel als `PLAY_TOKEN_ENCRYPTION_KEY` in Cloudflare Pages unter
   **Workers & Pages → downloadthat → Settings → Variables and Secrets** setzen.
5. Mit einem echten License-Tester-Kauf Kauf, Lieferung, Play-seitige
   Erstattung/Widerruf, RTDN und Reconciliation getrennt prüfen.

Die App akzeptiert weder eine frei eingegebene GPA-Bestellnummer noch eine
behauptete Zahlung. Der Server prüft den geheimen Purchase-Token live bei Google,
Produkt `pro`, Paket `de.classydl.app` und Status `PURCHASED`. Ein transientes
Google- oder Netzwerkproblem entzieht keine bestehende Lizenz. Nur ein von Google
bestätigter negativer Kaufstatus aus authentifizierter RTDN-Verarbeitung oder
serverseitiger Reconciliation darf Pro widerrufen.

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
4. Internal Track: Kauf, Pending, Abbruch, Restore sowie Play-Refund/Void mit
   RTDN und Reconciliation testen.
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
