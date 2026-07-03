# Play Console Internal Testing — Preparation Checklist

Use this document when Play Console access becomes available.

---

## Prerequisites

- [ ] Google Play Console developer account fully activated and verified
- [ ] Billing/payment method added to the developer account
- [ ] Release keystore secrets set in GitHub Actions (see `docs/ANDROID_SIGNING_AND_RELEASE.md`)

---

## App identity decisions (must be finalized before first Play Console upload)

**Package name** — once uploaded to Play Console, this cannot be changed.

Current value: `de.classydl.app`

- [ ] Owner decision on final package name: _______________

---

## Required assets

| Asset | Spec | Status |
|---|---|---|
| App icon (hi-res) | 512×512 PNG, max 1 MB | store_assets/icon-512.png ✓ |
| Feature graphic | 1024×500 PNG/JPG | store_assets/feature_graphic-1024x500.png ✓ |
| Screenshots (phone) | 2–8 screenshots, 16:9 or 9:16, 320–3840 px | store_assets/screenshot_*.png ✓ |
| Short description | max 80 characters | see below |
| Full description | max 4000 characters | see below |
| Privacy policy URL | public HTTPS URL | `https://downloadthat.pages.dev/datenschutz.html` |
| App category | | Productivity / Tools |

---

## Short description (≤80 chars)

```
Download videos, audio & images from any site. Free core. Pro unlimited.
```

German:

```
Videos, Audio & Bilder von jeder Seite laden. Kostenloser Kern, Pro unbegrenzt.
```

---

## Full description

```
DownloadThat downloads videos, audio, and images directly to your Android phone.

Paste a link, pick quality, tap download — that's it. Everything runs locally on your device. Nothing gets uploaded to any server you don't control.

FEATURES
• Videos from almost any site in your preferred quality (up to 4K)
• Audio extraction — save any video as MP3
• Batch downloads — scan a page, pick what you want, download together
• Image downloads — save images from any accessible URL
• No cloud upload, no account needed for the free tier
• No ads, no tracking SDKs, no dark-pattern paywalls

FREE TIER
5 downloads per day in full HD/4K quality.

PRO TIER (monthly / yearly / lifetime)
Unlimited downloads, batch mode, priority updates.

PERMISSIONS
INTERNET — required to fetch media from websites. No other permissions are requested.

PRIVACY
Nothing is sent to our servers during a download. Your download history stays on your device. See full privacy policy at: https://downloadthat.pages.dev/datenschutz.html

LEGAL
You are responsible for how you use downloaded content. Please respect copyright and the terms of sites you download from.
```

---

## Data safety answers

Complete the Play Console Data Safety form with these answers:

| Question | Answer |
|---|---|
| Does your app collect or share any of the required user data types? | No |
| Is all of the user data collected by your app encrypted in transit? | Yes (INTERNET permission is used only for outbound download requests over HTTPS) |
| Do you provide a way for users to request that their data is deleted? | N/A (no user data collected) |

---

## Content rating questionnaire

Expected rating: **Everyone** (PEGI 3 / Everyone)

The app does not contain violence, adult content, gambling, or user-generated content. Answers should reflect that.

---

## Tester email group

For internal testing, add tester email addresses in Play Console under:

Internal testing → Testers → Manage testers → Create email list

Minimum 1 email required. The app is not publicly visible during internal testing.

---

## Upload steps (when Play Console is ready)

1. Build and download the AAB artifact from GitHub Actions release run
   - Artifact: `DownloadThat-vX.Y.Z.aab`
2. In Play Console: Create app → set package name → set default language
3. Set up internal testing track
4. Upload the AAB to the internal testing track
5. Fill in app store listing (description, screenshots, feature graphic, icon)
6. Complete content rating questionnaire
7. Complete data safety form
8. Add tester email group
9. Submit for review (internal testing usually auto-approves)
10. Distribute invite link to testers

---

## Notes on update continuity

Users who installed the sideload beta APK will **not** receive an automatic Play Store update. Android treats the sideload APK (signed with your upload key) and the Play Store APK (signed by Google's app signing key) as different apps. Testers must:
1. Uninstall the sideload APK
2. Install from the Play Store link

This is expected and normal for the beta-to-Play-Store transition.
