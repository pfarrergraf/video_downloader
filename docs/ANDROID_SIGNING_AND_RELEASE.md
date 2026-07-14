# Android Signing and Release

Package: `de.classydl.app`. Play and Direct must keep the same app-signing
certificate, package ID and monotone version code so users can change channels
without uninstalling.

## Two keys, two purposes

1. **App-signing key:** the existing release key. Transfer/import it during the
   first Play App Signing setup. Google signs Play APKs with it; CI signs the
   Direct APK with the same key.
2. **Upload key:** a newly generated, separately revocable key. CI signs only the
   Play AAB with it; Google verifies the upload and re-signs delivered APKs with
   the app-signing key.

Verified existing app-signing certificate (local archive from 2026-07-01):

- alias: `classydl`
- SHA-256: `A4:B5:DB:BA:CE:D2:AD:0B:91:06:BD:D4:65:EC:48:1C:1F:F2:03:FD:77:85:82:2E:1A:F6:E0:7E:C9:74:C9:E4`
- local-only location: `.secrets/android/app-signing/` (ignored by Git)

Prepared separate upload certificate (generated 2026-07-14):

- alias: `downloadthat-upload`
- SHA-256: `5F:BD:61:BC:C8:B2:36:76:E8:E9:CE:33:7C:51:F7:24:34:61:CB:9C:31:C8:19:00:69:32:50:99:35:37:03:CE`
- local-only location: `.secrets/android/upload-key/` (ignored by Git)
- Play Console certificate: `C:\ai\playstore_console\downloadthat-upload-certificate.pem`

Never generate a replacement app-signing key for this migration. Do not enable
Play automatic installer protection while the Direct APK remains supported.

## GitHub Actions secrets

App-signing key (Direct APK):

- `ANDROID_APP_SIGNING_KEYSTORE_BASE64`
- `ANDROID_APP_SIGNING_KEYSTORE_PASSWORD`
- `ANDROID_APP_SIGNING_KEY_ALIAS`
- `ANDROID_APP_SIGNING_KEY_PASSWORD`
- `ANDROID_APP_SIGNING_CERT_SHA256`

Upload key (Play AAB):

- `ANDROID_UPLOAD_KEYSTORE_BASE64`
- `ANDROID_UPLOAD_KEYSTORE_PASSWORD`
- `ANDROID_UPLOAD_KEY_ALIAS`
- `ANDROID_UPLOAD_KEY_PASSWORD`
- `ANDROID_UPLOAD_CERT_SHA256`

PowerShell to encode a keystore:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("upload-key.jks")) | Set-Clipboard
```

Generate only the new upload key, not the app-signing key:

The registered upload certificate has SHA-1
`CD:DB:E2:9F:73:92:7E:9F:10:A8:08:55:39:E5:21:D2:2C:23:25:96` and SHA-256
`5F:BD:61:BC:C8:B2:36:76:E8:E9:CE:33:7C:51:F7:24:34:61:CB:9C:31:C8:19:00:69:32:50:99:35:37:03:CE`.
Google Play accepted the reset and scheduled activation for
`2026-07-16 13:23 UTC` (`15:23 CEST`).

```powershell
keytool -genkeypair -keystore upload-key.jks -alias downloadthat-upload -keyalg RSA -keysize 3072 -validity 10000 -dname "CN=DownloadThat Upload, O=DownloadThat, C=DE"
```

## Artifacts and gates

`.github/workflows/android-release.yml` creates:

- `DownloadThat-vX.Y.Z-direct.apk` and stable `DownloadThat-latest.apk`;
- SHA-256 files and release metadata;
- `DownloadThat-vX.Y.Z-play.aab` for Play Console;
- Android CycloneDX SBOM.

The workflow fails on certificate mismatch, non-16-KiB-compatible native
libraries, Stripe endpoints in the Play artifact or Billing classes in Direct.
`playRelease` contains Billing 9.1.0; `directRelease` contains no active Billing.

Version mapping remains `major * 10000 + minor * 100 + patch`; every release must
strictly increase it. Verify locally with `apksigner verify --print-certs` and
compare the normalized SHA-256 fingerprint with the stored expected value.
