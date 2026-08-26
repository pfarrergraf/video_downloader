# Android publishing channels and signing keys

**Read this before you touch anything about signing, releasing, or "getting a
build onto a phone".** DownloadThat has three separate distribution channels
and four separate signing identities. Mixing them up has already cost this
project a false "the signing key is broken" investigation (see CLAUDE.md,
2026-08-26). This file is the single source of truth for which key belongs to
which channel.

If you only remember one thing: **the channel decides the key. Never pick a key
because it is the one you have.**

---

## 1. The three channels

| | **A — Google Play** | **B — Direct APK** | **C — Internal app sharing** |
|---|---|---|---|
| What it is | The real product on the Play Store | Sideload channel for people who don't use Play | Throwaway channel for demos, screenshots, "let me see it" |
| Artifact | `app-play-release.aab` | `app-direct-release.apk` | `app-play-release.aab` (same Gradle task as A) |
| Flavour | `play` (Billing **on**) | `direct` (Billing **off**) | `play` (Billing **on**) |
| Built by | `.github/workflows/android-release.yml` | `.github/workflows/android-release.yml` | `.github/workflows/android-internal-sharing.yml` |
| CI signs it with | **Upload key** (key 2) | **App-signing key** (key 1) | **Throwaway key** (key 4) |
| What the user installs is signed with | App-signing key (key 1) — Play re-signs | App-signing key (key 1) — unchanged | Internal app sharing key (key 3) — Play re-signs |
| versionCode rules | Must be unique and monotone; enforced twice in CI | Same as A (same build) | **None.** Codes may be reused |
| Review / release notes | Yes | No | No |
| Reaches a Play track | Yes | No | **Never possible** — the API forbids it |
| In App Bundle Explorer | Yes | No | No |
| Link lifetime | Permanent | Permanent (GitHub Release asset) | 60 days, max 100 downloads |

### Channel C also needs a one-time device opt-in

The receiving Google account must turn internal app sharing on, once per
device: **Play Store app → Settings → About → tap "Play Store version" 7 times
→ toggle "Internal app sharing" on**. Testers who skip this get an error when
they open the link. That is the main reason channel C is *not* easier than
channel B for ordinary testers.

---

## 2. The four signing identities

| # | Name | Held where | Used for | Fingerprint |
|---|---|---|---|---|
| 1 | **App-signing key** | Google (Play App Signing) + `ANDROID_APP_SIGNING_*` GitHub secrets | What every real user's installed app is signed with. CI uses it directly only for the Direct APK. | `ANDROID_APP_SIGNING_CERT_SHA256` secret |
| 2 | **Upload key** | `ANDROID_UPLOAD_*` GitHub secrets | Signing the AAB *for upload only*. Play verifies it, strips it, re-signs with key 1. Independently revocable. | `ANDROID_UPLOAD_CERT_SHA256` secret |
| 3 | **Internal app sharing key** | Google only — we never hold it | Play re-signs every internal-app-sharing upload with this. Shown in Play Console → Internal app sharing → "Internal test certificate". | SHA-256 `94:D5:E2:B8:99:9B:60:11:75:CE:80:DB:03:09:5A:D6:BE:1B:1A:34:59:53:5B:17:68:AA:98:4D:6C:B3:86:93` (public fingerprint, not a secret) |
| 4 | **Throwaway key** | Nowhere — generated inside the internal-sharing workflow run and discarded | Making the internal-sharing AAB a structurally valid signed archive. Play throws this signature away. | Different every run; nothing may depend on it |

### Consequences that trip people up

- **Key 1 ≠ key 3.** An internal-app-sharing install and a Play/Direct install
  have *different* signatures, so they cannot upgrade over each other.
  Uninstall first. This is expected, not a bug.
- **Anything registered with an API provider against a certificate must list
  the right one.** Key 1's certificate is what production uses; key 3's is what
  internal-sharing testers run under. Registering only one and then testing
  through the other channel looks exactly like a broken backend.
- **Key 4 is not a secret and not a fallback.** Never store it, never reuse it
  across runs, and never sign a Direct APK or a Play upload with it. A
  jarsigner-only signature (which is what key 4 produces) would not even
  install on Android 11+; it is valid solely because Play re-signs channel C.

---

## 3. Decision table

| If you are asked to… | Use | Never |
|---|---|---|
| Ship a new version to users | Channel A: `android-release.yml`, then `android-promote-candidate.yml` | Never hand-upload an AAB; never skip the TEAM gate |
| Give someone a sideloadable file | Channel B: the signed Direct APK from the GitHub Release | Never re-sign an APK with a different key to "make it install" |
| Get a build on a phone for a demo, screenshot or video | Channel C: `android-internal-sharing.yml`, then upload the AAB in Play Console | Never dispatch `android-release.yml` for this — it burns a versionCode on the release line |
| Test Play Billing purchases | Channel A (internal track) or channel C, with the account added as a **license tester**. License testers bypass the purchase key check, so even a sideload works, as long as the package name matches | Never assume a purchase failure means the key is wrong before checking license-tester membership |
| Fix a red CI run reporting a certificate mismatch | Suspect the *parsing* first — a CLI tool's output format, or an unpinned SDK version. Verify against an already-shipped APK | **Never rotate or re-upload a production signing key to fix a red CI run.** Play App Signing key material is not recoverable |

---

## 4. Why the internal-sharing link is not printed in CI by default

This repository is **public**. Run logs, step summaries and workflow artifacts
are readable by anyone. An internal-app-sharing download link is a working
distribution channel with a 100-download cap, so printing it publicly both
leaks an unreviewed build and burns the cap.

Therefore `android-internal-sharing.yml` defaults to *build only*: it publishes
the AAB as an artifact, and a human uploads it at
<https://play.google.com/console/internal-app-sharing> to get the link
privately.

The automated leg exists behind the `share_via_api` input. Turn it on only
after setting Internal app sharing in Play Console to **"Restrict access to
email lists"** — then a leaked link is useless to anyone outside those lists,
and CI printing it is no longer a public distribution channel.

---

## 5. Verifying a claim instead of guessing

```bash
# What is this APK actually signed with?
apksigner verify --print-certs app.apk | grep 'certificate SHA-256 digest'

# What is this AAB signed with? (AABs are jarsigner-signed, not apksigner-signed)
keytool -printcert -jarfile app.aab | grep SHA256

# What is installed on the device signed with?
adb shell dumpsys package de.classydl.app | grep -A2 signatures
```

If the fingerprint matches key 3's, you are looking at an internal-app-sharing
install and *nothing about the production key is involved*.
