# Android Signing and Release

This document describes the signing key setup, how to produce release artifacts, and how to maintain update continuity across all future releases.

---

## Signing key — the most important rule

**Never rotate the signing key unless it is absolutely unavoidable (e.g. key compromise).**

Android uses the signing key to identify the app and allow updates. If you change the signing key, users who installed the app with the old key cannot receive an automatic update — Android treats the new APK as a different app and requires a manual reinstall. For Play Console with App Signing enrolled, Google manages the signing key; your keystore becomes the "upload key" only, but the principle is the same: do not change it.

---

## Key details

| Property | Value |
|---|---|
| Key alias | stored in GitHub secret `ANDROID_KEY_ALIAS` |
| Keystore | stored as base64 in GitHub secret `ANDROID_KEYSTORE_BASE64` |
| Passwords | stored in `ANDROID_KEYSTORE_PASSWORD` and `ANDROID_KEY_PASSWORD` |
| Key algorithm | RSA 2048 (or as generated) |

---

## GitHub Actions secrets required for release builds

Set these in the repository settings under Settings → Secrets and variables → Actions:

| Secret | Description |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | Base64-encoded `.jks` or `.keystore` file |
| `ANDROID_KEYSTORE_PASSWORD` | Password for the keystore |
| `ANDROID_KEY_ALIAS` | Alias of the key inside the keystore |
| `ANDROID_KEY_PASSWORD` | Password for the key itself |

To create the base64 string from a keystore file:

```bash
# Linux/macOS
base64 -w 0 release.keystore > release.keystore.b64
cat release.keystore.b64   # copy this into the GitHub secret

# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("release.keystore")) | clip
```

---

## How to create a new signing key (first time only)

```bash
keytool -genkey -v \
  -keystore release.keystore \
  -alias downloadthat \
  -keyalg RSA -keysize 2048 \
  -validity 10000 \
  -dname "CN=DownloadThat, OU=Android, O=Geistreich, L=, ST=, C=DE"
```

Store the resulting file somewhere safe offline. Upload the base64 version to GitHub secrets.

---

## Building a release APK and AAB

Release artifacts are built by `.github/workflows/android-release.yml`.

Trigger methods:
1. Push a version tag: `git tag v0.2.0 && git push origin v0.2.0`
2. Use "Run workflow" in GitHub Actions UI (enter version like `v0.2.0`)

The workflow produces:
- `DownloadThat-vX.Y.Z.apk` — signed APK for direct sideload beta
- `DownloadThat-latest.apk` — same APK, stable filename for website download button
- `DownloadThat-vX.Y.Z.apk.sha256` — SHA-256 checksum of the versioned APK
- `DownloadThat-latest.apk.sha256` — SHA-256 checksum of the latest APK
- `DownloadThat-release.json` — machine-readable release metadata
- `DownloadThat-vX.Y.Z.aab` — App Bundle for Play Console upload (build artifact, not attached to release)

---

## APK vs AAB

| Format | Used for | Notes |
|---|---|---|
| `.apk` | Direct sideload (beta) | Signed with release keystore. Testers install this. |
| `.aab` | Play Console upload | Signed with upload key (same keystore). Google re-signs with app signing key after enrollment. |

For the Play Console:
1. Enroll in Google Play App Signing when you first upload an AAB.
2. From that point, your keystore is your "upload key". Google holds the actual signing key.
3. Users who installed the sideload APK must reinstall from the Play Store — Android sees the Google-managed key as different from your upload key.

---

## Verifying an APK signature

```bash
# Show certificate details
keytool -printcert -jarfile DownloadThat.apk

# Verify APK signing (requires Android SDK build-tools)
apksigner verify --print-certs DownloadThat.apk

# On Windows
apksigner.bat verify --print-certs DownloadThat.apk
```

The certificate fingerprint (SHA-256) should remain identical across all releases. If it changes, something went wrong with the signing setup.

---

## versionCode and versionName

The release workflow derives these from the git tag automatically:

```
v1.2.3 → versionName = "1.2.3", versionCode = 10203
v0.2.0 → versionName = "0.2.0", versionCode = 200
```

Rule: `versionCode` must strictly increase with each release. Never reuse or decrease a `versionCode`.

---

## Guardrails for future AI sessions

- Do not add or change the signing key without owner approval.
- Do not remove the `Verify signing secrets are configured` check from the release workflow.
- Do not distribute APKs produced by local debug builds.
- Do not distribute APKs that were built without the release keystore secrets present.
- The AAB artifact is for Play Console only — do not distribute it as a sideload binary.
