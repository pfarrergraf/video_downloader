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

> ⚠️ **Facts must match `creator_tools/config/product_facts.json`** (the single
> source of truth; `tests/test_creator_tools.py` enforces it): free tier = **3
> downloads/day**, Pro = **one-time 12 €, no subscription**. Earlier drafts of this
> doc said "5/day" and "monthly/yearly/lifetime" — both were wrong and are corrected
> below. For the Data Safety form and content-policy risk, use
> `docs/PLAY_STORE_READINESS.md` (more accurate than the summary here).

## Short description (≤80 chars)

```
Download video, audio & images from links you own. Free core, Pro unlimited.
```

German:

```
Video, Audio & Bilder von deinen Links laden. Kostenloser Kern, Pro unbegrenzt.
```

---

## Full description

```
DownloadThat saves video, audio, and images to your Android phone from links you provide — your own content, or media you are authorized to download.

Paste a link, pick quality, tap download — that's it. Everything runs locally on your device.

FEATURES
• Save video from a link in your preferred quality (up to 4K)
• Audio extraction — save a video's audio as MP3
• Batch downloads — scan a page, pick what you want, download together
• Image downloads — save images from a link
• Runs on-device; no account needed for the free tier
• No ads, no third-party tracking SDKs

FREE TIER
3 downloads per day in full HD/4K quality.

PRO (one-time purchase, 12 €, no subscription)
Unlimited downloads, playlist/batch mode, all future updates.

PERMISSIONS
INTERNET, FOREGROUND_SERVICE(+DATA_SYNC), POST_NOTIFICATIONS — used to run and show progress for your downloads. No storage, contacts, location, camera, or tracking permissions.

PRIVACY
The download itself runs on your device. If you buy Pro, your email and payment are handled by Stripe and a license key is stored to validate your purchase. Full privacy policy: https://downloadthat.pages.dev/datenschutz.html

LEGAL
DownloadThat does not bypass DRM or paywalls. You are responsible for having the right to download the content, and for respecting copyright and each site's terms.
```

---

## Data safety answers

> ⚠️ The old "No — collects no data" answer is **inaccurate** and a common cause of
> Play enforcement: the app sends a device identifier + license key to the license
> server, and a Pro purchase collects an email + payment via Stripe. Use the accurate
> mapping in **`docs/PLAY_STORE_READINESS.md` → "Data Safety mapping"**. Summary:

| Question | Answer |
|---|---|
| Does your app collect or share any user data? | **Yes** (collect, not share for ads) |
| Data types collected | **Device or other IDs** (per-install `device_id` for the one-device license slot); **Email address** + **Purchase history** (only if the user buys Pro, via Stripe); no free-tier account data |
| Is data encrypted in transit? | **Yes** (HTTPS to the license/payment backend) |
| Do you provide a way to request deletion? | **Yes** — email the contact in `SECURITY.md`; erasure is fulfilled via `POST /api/admin/gdpr-erase`. Also `classydl purge-data` clears on-device data |
| Data shared with third parties? | Payment/email processed by **Stripe** (payment processor, not advertising) |

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
