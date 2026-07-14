# Google Play Betrieb und Konfiguration

## Runtime-Secrets und Variablen

Die endgültigen Namen werden vom Backend-Code erzwungen und müssen in Cloudflare
Pages sowie dem Deployment-Workflow identisch gesetzt sein. Niemals Tokens,
Service-Account-JSON oder private `age`-Schlüssel in Git oder App-Artefakte legen.

- Google-Play-Service-Account mit minimalen Rechten zum Lesen und Bestätigen von Käufen
- Purchase-Token-Verschlüsselungsschlüssel (32 zufällige Bytes, getrennt vom OAuth-Key)
- Erwartete RTDN-OIDC-Audience und Push-Service-Account-E-Mail
- Paket-ID `de.classydl.app`, Produkt-ID `pro`; sichtbarer Name `DownloadThat Pro`
- `PLAY_STORE_URL`: zunächst Internal-/Closed-Test-Link, später öffentliches Listing

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
3. Internal Track: Kauf, Pending, Abbruch, Restore, Refund, RTDN testen.
4. Closed Test und Pre-launch Report auswerten.
5. Data Safety/Rating/Target Audience/App Access bestätigen.
6. Erst dann Produktion; `PLAY_STORE_URL` zentral auf das öffentliche Listing ändern.

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
