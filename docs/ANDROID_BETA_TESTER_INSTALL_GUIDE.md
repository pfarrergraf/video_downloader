# Android Beta Tester Install Guide

**App**: DownloadThat
**Package name**: `de.classydl.app`
**Beta type**: Google Play internal testing (primary) or signed direct APK (secondary)
**Status**: The Play-first release is being prepared.

---

## What the app does

DownloadThat saves video, audio and images from links you provide and may lawfully
save. Media processing happens on your Android device; license checks and updates
use limited network services. The Free tier needs no account.

---

## Before you install

- Only install this APK if you received the download link directly from the project owner.
- Do not install APKs you received from any other source, even if they look similar.
- The current beta is only for arm64 Android phones (most Android phones since 2015 qualify).

---

## Expected Android warning

Android will warn you that this app is from outside the Google Play Store. This is **normal and expected** for beta apps that are not yet published on the Play Store.

The message may look like:

> **Play Protect:** This app was not checked by Play Protect. It may be able to harm your device.

or

> **Unknown source:** Your phone is set to block installation of apps from unknown sources.

**What to do:**

1. Tap **"Install anyway"** or **"More details" → "Install anyway"**.
2. Do **not** disable Play Protect permanently. It is there to protect you. One-time approval for this specific APK is enough.
3. If Android asks you to "scan" the app with Play Protect, you can allow that — it is fine.

---

## How to verify the APK checksum

The release page at:

```
https://github.com/pfarrergraf/video_downloader/releases/latest
```

includes a file named `DownloadThat-latest.apk.sha256`. To verify:

**On Android (using Termux or a file manager with hash tools):**

```bash
sha256sum DownloadThat.apk
```

Compare the output to the contents of the `.sha256` file. They must match exactly.

**On Windows (PowerShell):**

```powershell
Get-FileHash DownloadThat.apk -Algorithm SHA256
```

**On macOS / Linux:**

```bash
sha256sum DownloadThat.apk
# or
shasum -a 256 DownloadThat.apk
```

---

## Installation steps

1. Open the download link in your browser.
2. Tap **Download** on the beta page.
3. When the download finishes, tap the file in the notification bar or open it in your Downloads folder.
4. Approve the installation when prompted (see warning above).
5. Open DownloadThat from your app drawer.

---

## What to send as feedback

If something goes wrong, the most useful information is:

- Your Android version (Settings → About phone → Android version)
- Your phone model
- A screenshot of any error message
- What you were doing when it happened (paste link, download type, etc.)
- Whether it was a fresh install or an update

Send feedback directly to the project owner. Do not post beta APKs or debug logs publicly.

---

## How to uninstall

Go to **Settings → Apps → DownloadThat → Uninstall**.

This removes the app. Any downloaded files you saved remain in your Downloads folder and are not deleted by uninstalling the app.

---

## Notes

- The beta APK is arm64-v8a only. It will not install on very old 32-bit Android devices.
- Play Store internal testing track will replace this direct sideload flow once the developer account is fully set up. You will receive an update link at that time.
- Do not sideload the APK onto tablets or devices other than your primary test phone unless you specifically agreed to test on multiple devices.
