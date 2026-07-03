# APK Security Review Checklist

Use this checklist before distributing any new release APK to beta testers.
Complete each item manually and note the result or date.

---

## Release source

- [ ] APK was produced by `.github/workflows/android-release.yml` (GitHub Actions, not local build)
- [ ] Release tag matches the intended version (e.g. `v0.2.0`)
- [ ] GitHub Actions run shows no unexpected errors or skipped signing steps

---

## Signing

- [ ] APK is signed with the release keystore (not a debug key)
- [ ] Signing identity matches previous releases (key alias, certificate fingerprint)
- [ ] No keystore rotation since the last release without documented reason

Verify with:

```bash
# Linux/macOS
keytool -printcert -jarfile DownloadThat-vX.Y.Z.apk

# Windows (PowerShell, with Android SDK on PATH)
apksigner verify --print-certs DownloadThat-vX.Y.Z.apk
```

---

## Checksum

- [ ] SHA-256 file `DownloadThat-vX.Y.Z.apk.sha256` is present in GitHub Release
- [ ] SHA-256 hash on the release page matches the downloaded APK
- [ ] `DownloadThat-release.json` is present and fields match the release

---

## Manifest permissions

Current approved permissions:

- `android.permission.INTERNET` — required for downloads

Not present (verify remains true):

- [ ] No `READ_CONTACTS` / `WRITE_CONTACTS`
- [ ] No `READ_SMS` / `SEND_SMS`
- [ ] No `READ_CALL_LOG`
- [ ] No `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION`
- [ ] No `CAMERA`
- [ ] No `RECORD_AUDIO`
- [ ] No `REQUEST_INSTALL_PACKAGES`
- [ ] No `SYSTEM_ALERT_WINDOW` (overlay)
- [ ] No `BIND_ACCESSIBILITY_SERVICE`
- [ ] No `DEVICE_ADMIN`

Verify with:

```bash
aapt dump permissions DownloadThat-vX.Y.Z.apk
# or
apkanalyzer manifest print DownloadThat-vX.Y.Z.apk | grep "uses-permission"
```

---

## Dependency review

- [ ] No new Python packages added to `android/requirements-chaquopy.txt` since last review
- [ ] No new `yt-dlp` version that introduces unexpected network behavior
- [ ] Chaquopy version unchanged or change is documented

---

## Website download link

- [ ] `/download` endpoint on the website still returns the correct APK (HTTP 200)
- [ ] `Content-Type` is `application/vnd.android.package-archive`
- [ ] No GitHub cookies forwarded in response
- [ ] SHA-256 shown on `android-beta.html` matches the release

---

## Privacy and legal pages

- [ ] `/datenschutz.html` (privacy policy) is present and current
- [ ] `/impressum.html` (imprint) is present and current
- [ ] `/agb.html` (terms) is present and current
- [ ] `/widerruf.html` (right of withdrawal) is present and current
- [ ] Support contact email is correct

---

## Optional: external scan

- [ ] Uploaded APK to VirusTotal (or similar) — record result and date: ___________
- [ ] No unexpected detections. Note any false positives: ___________

---

## Final check

- [ ] Beta page (`/android-beta.html`) loads correctly
- [ ] Download button on beta page triggers APK download (not a redirect to GitHub)
- [ ] Tester install guide (`docs/ANDROID_BETA_TESTER_INSTALL_GUIDE.md`) is current
- [ ] Distributed only to invited testers, not publicly promoted

---

Reviewed by: _______________ Date: _______________
