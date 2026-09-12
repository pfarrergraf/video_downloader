# Production Access Questionnaire - provider draft and truthful-answer checklist

**Provider:** Testers Community  
**App:** Downloadthat  
**Play URL:** `https://play.google.com/store/apps/details?id=de.classydl.app`  
**Source:** `downloadthat_production.pdf` (5 pages)  
**SHA-256:** `481e23538eca3c1987e0255e6e11aa10400d4d501471e1af9164e6d5d1509435`

> The supplied document contains suggested answers. Do not submit them verbatim unless every statement accurately describes the real closed test and the exact build submitted for production access.

## Questions and provider-proposed answers

### 1. How did you recruit users for your closed test?

Provider proposal: A paid testing provider was used, supplemented by target users such as content creators and media enthusiasts.

**Verify before submission:**

- Was recruitment exclusively through the paid provider, or were independent target users actually included?
- How many testers came from each channel?
- Do records exist for invitations, opt-in dates and participation?

### 2. How easy was it to recruit testers?

Provider proposal: `Easy`.

**Verify before submission:** Choose the answer that reflects the actual recruitment process rather than the provider's preferred wording.

### 3. Describe tester engagement during the closed test

Provider proposal: Testers gave feedback on usability, features and experience, leading to onboarding and feature-visibility changes.

**Verify before submission:** Name the actual feedback channels, response volume, active-user pattern and concrete changes that were implemented before requesting production access.

### 4. Summarize the feedback and explain how it was collected

Provider proposal: Testers requested ASO work, a walkthrough, improved screenshots, an app-rating feature and a support section; feedback was collected through surveys, direct communication and usability sessions.

**Verify before submission:** The supplied reports do not contain survey responses, interview notes, tester identities, session records or raw feedback. Request this evidence from the provider and describe only collection methods that actually occurred.

### 5. Who is the intended audience?

Provider proposal: People who need to save legally permitted video, audio and images, including content creators and educators.

**Recommended factual framing:**

DownloadThat is intended for users who need to save their own, public-domain, appropriately licensed or explicitly permitted media from links. Typical users include creators, educators and people managing media they are authorized to download. The app does not bypass DRM or paywalls.

### 6. How does the app provide value?

Provider proposal: Easy video/audio saving up to 4K, multiple-link downloads, progress display and direct sharing.

**Recommended factual framing:**

DownloadThat combines link, multi-link and playlist processing; separate video/audio choices; quality selection up to 4K where the source provides it; progress tracking; folder selection; and direct open/share actions. Processing is designed to run on the user's device. Users remain responsible for having the necessary rights.

### 7. Expected first-year installs

Provider proposal: `10k-100k`.

**Verify before submission:** Use a defensible forecast based on launch channels and current audience. This is not a technical readiness criterion and should not be inflated.

### 8. What changes did you make based on the closed test?

Provider proposal: ASO description, dynamic onboarding, improved screenshots and a rating button were implemented.

**Critical warning:** At the time this review was prepared, these claims were not all established as completed in the repository. The answer must list only changes present in the production candidate. Likely candidates after implementation and verification are:

- Fixed Play Billing product discovery and added diagnostic/fallback handling.
- Added in-app help, troubleshooting and feedback entry points.
- Added a non-intrusive rating entry point and contextual in-app review flow.
- Improved first-run guidance.
- Reworked store screenshots and listing copy based on observed confusion.

### 9. How did you decide the app is ready for production?

Provider proposal: Extensive testing, critical issue resolution, feature optimization and full compliance.

**Recommended evidence-based structure:**

- Closed test completed for the required period and tester threshold.
- Core flows verified: first launch, shared-link intake, single/multiple/playlist download, video/audio selection, quality selection, background survival, file open/share/delete, folder export, free quota, purchase and restore.
- Billing product successfully queried and purchased through a licensed test account.
- No unresolved release-blocking crashes or data-loss issues.
- Privacy, legal-use messaging, store listing and Data safety declarations reviewed against the shipping build.
- Feedback-driven changes were retested in the release candidate.

### 10. What did you do differently this time?

Provider proposal: Prioritized user feedback, refined functionality and onboarding, and improved visibility and engagement.

**Verify before submission:** This question may refer to a previous rejected production-access attempt. State exactly what changed since that attempt. If there was no previous attempt, confirm how Play Console presents the question before answering.

## Evidence to retain

- Closed-test start/end dates and active tester count.
- Device/Android-version matrix.
- Raw survey or interview responses.
- Bug list with resolution status and release version.
- Screenshots or recordings of the fixed Pro purchase and restore flows.
- Play Console product configuration and licensed-tester setup.
- Release-candidate version code/name and commit SHA.
- CI run links for Android build and device/emulator smoke tests.

## Submission rule

Every claim should be specific, modest and auditable. Avoid phrases such as `fully compliant`, `all devices`, `all functionality` or `no bugs` unless supported by documented evidence.
