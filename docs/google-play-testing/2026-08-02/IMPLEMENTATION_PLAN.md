# DownloadThat - implementation plan from closed-test feedback

**Prepared:** 2026-08-02  
**Repository:** `pfarrergraf/video_downloader`  
**Target:** Production-ready Google Play release and defensible production-access submission

## Executive decision

Do not implement the provider report mechanically. The current repository already contains substantial work in areas the report labels as missing: detailed German/English listing copy, real phone screenshots, multilingual website/app content, a Play Billing controller, purchase verification, folder selection and direct file actions. The concrete release blocker is the reported `product unavailable` result. The strongest product gaps are support, first-run guidance, rating/review UX and stronger evidence for the production-access answers.

## Current repository facts relevant to the report

- Play flavor uses Google Play Billing and product ID `pro`.
- `PurchaseControllerFactory.kt` queries an INAPP one-time product and emits `product_unavailable` when the query fails, product details are absent or no one-time offer token is returned.
- Server-side Play purchase verification exists.
- Store listing copy already includes lawful-use wording, multiple links/playlists, audio/video separation, 240p-4K quality, progress, folder choice, open/share, no ads/tracking and localization.
- Existing store assets include an icon, feature graphic and three real phone screenshots.
- The Android bridge already exposes purchase, restore, folder selection and download lifecycle hooks.

## Priority plan

### P0 - Fix and prove Play Billing availability

**Goal:** A licensed tester can see the Pro offer, complete a test purchase and restore it after reinstall.

**Investigate:**

1. Confirm the Play Console product with ID exactly `pro` exists as a one-time product for package `de.classydl.app`.
2. Confirm the product is active and available in every country used by testers.
3. Confirm the tested AAB came from the Play track, not a locally installed APK with a different signature/version.
4. Confirm testers joined the closed test with the same Google account used in Play Store.
5. Confirm license-test accounts and payment-test behavior are configured.
6. Capture Billing response code and debug message in a support-safe diagnostic view.
7. Check whether Billing Library 9 returns one-time offer details as expected for the configured product type and purchase option.
8. Verify backend purchase acknowledgement/verification and entitlement persistence.

**App changes:**

- Replace the generic unavailable state with differentiated states: Play Store account/build mismatch, billing service unavailable, product not configured/available, network issue and temporary verification failure.
- Add a retry action and a support/report action with non-sensitive diagnostics.
- Do not show a purchasable-looking CTA until product details and localized price are loaded.
- Display the localized Play price from `ProductDetails`, not a hard-coded value.
- Add automated tests around missing details, missing offer token, disconnected billing, successful query, purchase pending, verification failure and restore.

**Acceptance criteria:**

- Test account sees localized price.
- Purchase succeeds through Play test billing.
- Pro entitlement is active after server verification.
- Restore works after clearing app data/reinstalling from the test track.
- Failure states are understandable and actionable.

### P1 - Add Help, Support and diagnostics

**Goal:** Users can solve common failures or send a useful report without leaving the app confused.

**Minimum section:**

- How link sharing and clipboard suggestions work.
- Supported media behavior without promising universal site support.
- Why some qualities/formats may be unavailable.
- Download folder and Android Files behavior.
- Background-download/notification guidance.
- Legal-use and DRM/paywall limits.
- Free quota, Pro purchase and restore.
- Troubleshooting for `product unavailable`.
- Contact/feedback link.

**Feedback payload:** app version, version code, distribution flavor, Android version, device model, locale, billing response category and recent non-sensitive error code. Never include license keys, purchase tokens, URLs or downloaded filenames by default.

**Acceptance criteria:** support is reachable from Settings in two taps; all links work; diagnostics can be copied; privacy review completed.

### P1 - Add rating/review UX correctly

**Goal:** Give satisfied users a legitimate, non-coercive review path.

**Changes:**

- Add `Rate DownloadThat` in Settings, opening the Play listing for Play builds.
- Add Google Play In-App Review API as a contextual request after a meaningful success threshold, for example after several successful downloads across multiple days.
- Never gate functionality, incentives or support on a rating.
- Do not ask immediately after install, after an error or after purchase failure.
- Track only that the app attempted a prompt; the API does not guarantee a dialog.

**Acceptance criteria:** manual settings action works; contextual request is frequency-limited; direct/sideload flavor does not expose a broken Play-only action.

### P1 - First-run guidance rather than a long forced tour

**Goal:** Explain the first successful workflow quickly.

**Recommended flow:**

1. `Share a link to DownloadThat or paste it here.`
2. `Choose video/audio and quality.`
3. `Your file appears in Downloads; open, share or choose another folder.`
4. Legal-use reminder with link to details.

Use a dismissible first-run card or three short pages, then contextual hints. Avoid spotlight overlays that break inside the WebView or become stale when the UI changes.

**Acceptance criteria:** skippable; can be reopened from Help; localized; does not block shared-intent startup; tested at 200% font scale.

### P1 - Rebuild Play Store screenshots around benefits

The existing screenshots are real app captures, which is good, but the provider found them insufficiently explanatory.

**Recommended sequence:**

1. `Share a link - DownloadThat fills it automatically.`
2. `Video, audio or images - choose what you need.`
3. `Select quality up to 4K where available.`
4. `Download several links or playlists.`
5. `Follow progress and keep downloads running.`
6. `Open, share, delete or choose your folder.`
7. `On-device processing. No ads. No tracking.`

Use concise overlays outside the raw UI area, neutral example URLs and no protected-platform branding. Produce German and English first; localize only after the source set is stable.

**Acceptance criteria:** current release UI; readable on phone; no unsupported claims; visual consistency; Play Console preview checked.

### P2 - ASO refinement, not keyword stuffing

The current listing is already materially stronger than the tester report suggests. Refine from actual search intent and conversion data.

**Actions:**

- Keep the lawful-use framing prominent.
- Test app title/short description wording within Play limits.
- Use natural phrases such as video downloader, audio download/extraction, playlist download and media downloader only where accurate and policy-safe.
- Avoid claims of universal platform support.
- Align listing text with screenshots and actual feature flags.
- Prepare localized listing QA for the most important markets before expanding further.

### P2 - Release evidence and production-access dossier

Create a release folder for the exact candidate containing:

- version name/code and commit SHA;
- AAB checksum;
- test track and testing dates;
- tester recruitment and engagement evidence;
- device/Android matrix;
- issues found, changes made and retest result;
- billing purchase/restore evidence;
- CI run links;
- final questionnaire answers.

This is more important than polished generic prose. The supplied questionnaire currently asserts changes that may not yet exist.

### P3 - Later growth work

- Community/social channels only after support load and retention justify them.
- Notifications limited to active-download status, completion and genuinely useful opt-in tips; avoid promotional noise.
- Regular updates based on crash, support and conversion evidence rather than a fixed release cadence.

## Proposed implementation order

1. Reproduce and fix `product unavailable`.
2. Add billing diagnostics and tests.
3. Add Help/Support and feedback reporting.
4. Add Settings rating link and contextual review flow.
5. Add lightweight first-run guidance.
6. Capture a new screenshot set from the release candidate.
7. Refine Play listing copy.
8. Run closed-test regression and collect evidence.
9. Write truthful production-access answers from evidence.

## Clarifying questions

### Testing provider and evidence

1. How many testers actually installed and actively used the app, and on which dates?
2. Which device models and Android versions were tested?
3. Can the provider supply raw survey responses, issue logs, screen recordings and test-case results?
4. Did testers use the Play closed-test installation link, or was an APK installed manually?
5. Which Google account/country produced `product unavailable`?
6. Did any tester complete a Pro purchase or restore test successfully?

### Product and pricing

7. Is `pro` intended to be a one-time Play product, an annual subscription, or should both exist? The broader project has discussed annual and lifetime pricing; the current Play code queries only an INAPP one-time product.
8. What exact Play price and country availability should the product have?
9. Should the Play build offer only Play Billing while the direct APK uses external license activation, as the current architecture implies?
10. What is the current free daily quota shown to users?

### UX/support

11. Which support destination should be used: email, website form, GitHub issue form, or an in-app endpoint?
12. Which languages must Help and onboarding support at launch?
13. Is there already a privacy-safe analytics/crash system, or should the launch remain analytics-free?
14. Should the onboarding focus mainly on Android Share-to-DownloadThat, direct URL paste, or both equally?

### Production access

15. Has production access previously been rejected? The provider's question 10 wording suggests a repeat attempt.
16. What exact changes were already shipped during the 14-day test, and which are only proposals?
17. What install forecast is defensible from current channels: under 10k, 10k-100k or another Play Console range?

## Assumptions requiring confirmation

- `pfarrergraf/video_downloader` is the correct DownloadThat repository.
- `master` is the production development base branch.
- Package name remains `de.classydl.app`.
- Play product ID remains `pro`.
- The current release model is free quota plus paid Pro entitlement.
- The reports refer to the same build lineage as the current repository.
- The app must remain compliant with the rule that only lawfully permitted content may be saved and must not bypass DRM/paywalls.

## Non-goals for this first change set

- No immediate production code changes before billing configuration and tester evidence are clarified.
- No claim that every tester recommendation is correct or still current.
- No submission of provider-written answers as if they were verified facts.
- No aggressive notification, review gating or keyword stuffing.
