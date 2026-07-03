# Android beta distribution, Play Protect mitigation, Cloudflare/Stripe readiness plan

Date: 2026-07-03
Branch of record: `claude/gothic-downloader-website-bp7r2u`
Repository: `pfarrergraf/video_downloader`
Status: planning document, no code changes in this commit
Owner context: Play Console Internal Testing is not available for roughly 10 days; direct APK distribution must be made as safe, transparent, and tester-friendly as possible until then.

---

## 1. Why this document exists

Test users currently see a Google/Android warning when installing the APK from outside Google Play. The current repo does not show an obvious malware-like permission set, but the app still has a high-friction trust profile because it is:

- distributed as a sideloaded APK outside Google Play,
- a media downloader,
- packaged with embedded Python/Chaquopy dependencies,
- expected to use `yt-dlp` and a bundled `ffmpeg` executable,
- not yet backed by Play Console developer/app reputation,
- new enough that Play Protect / Android reputation systems may not have a stable reputation signal for the signing key, package name, APK hash, or domain.

Goal for the next 10 days:

1. keep the sideload flow honest and safe,
2. avoid any attempt to bypass Play Protect,
3. give testers clear installation and verification information,
4. keep builds signed and reproducible,
5. prepare the exact handoff path into Play Console Internal Testing once it becomes available,
6. make Cloudflare Pages and Stripe usable enough for the paid-license path.

---

## 2. Current access reality

### 2.1 Available in the current ChatGPT/GitHub session

- GitHub repository read/write access is available.
- GitHub files, branches, release workflow files, and website source can be inspected and edited.
- GitHub Actions workflows can be prepared in code.

### 2.2 Not available directly in this ChatGPT session

At the time this document was created, no direct Cloudflare or Stripe connector/tool was available in this chat environment. Available tool namespaces did not include Cloudflare or Stripe.

Practical consequence:

- I can prepare Cloudflare/Stripe automation through GitHub Actions and checked-in code.
- I cannot directly create Cloudflare projects, set Cloudflare secrets, create Stripe live products, or inspect Stripe live mode from this chat unless a matching connector becomes available later.
- Required secrets must be added by the human owner in GitHub repository settings / Cloudflare / Stripe dashboards.

### 2.3 Existing automation already present

The current branch already has a Cloudflare Pages deployment workflow:

- `.github/workflows/deploy-pro-website.yml`
- triggers on pushes to `claude/gothic-downloader-website-bp7r2u` and `master` for `pro/website/**`
- uses `wrangler-action` on GitHub-hosted runners, not on the local phone/laptop
- expects GitHub Actions secrets:
  - `CLOUDFLARE_API_TOKEN`
  - `CLOUDFLARE_ACCOUNT_ID`
  - `STRIPE_SECRET_KEY`
  - `STRIPE_WEBHOOK_SECRET`

The current branch also has an Android release workflow:

- `.github/workflows/android-release.yml`
- builds signed APKs and signed AABs
- expects GitHub Actions secrets:
  - `ANDROID_KEYSTORE_BASE64`
  - `ANDROID_KEYSTORE_PASSWORD`
  - `ANDROID_KEY_ALIAS`
  - `ANDROID_KEY_PASSWORD`

---

## 3. Current code observations relevant to Play Protect warnings

### 3.1 Android manifest: low permission footprint

Current `android/app/src/main/AndroidManifest.xml` only declares:

- `android.permission.INTERNET`
- a launcher `MainActivity`
- a non-exported `FileProvider`

No currently observed dangerous permissions:

- no SMS
- no contacts
- no call log
- no location
- no camera
- no microphone
- no accessibility service
- no device admin
- no package install permission
- no overlay permission

This is good. Do not add dangerous permissions unless absolutely necessary.

### 3.2 Release signing exists, but must be enforced

Current `android/app/build.gradle` supports release signing via GitHub Actions secrets. If no keystore secret is present, a local `assembleRelease` may produce an unsigned/uninstallable release artifact. The CI workflow explicitly checks for keystore presence before release.

Distribution rule:

- Only distribute APKs produced by `.github/workflows/android-release.yml`.
- Do not distribute local debug APKs.
- Do not distribute unsigned release APKs.
- Do not distribute random artifacts from intermediate CI jobs.

### 3.3 Website currently emphasizes direct APK installation too aggressively

Current website copy includes messaging such as:

- no Play Store needed,
- no app store needed,
- install the APK directly.

That may be true, but it is poor trust framing during a Play Protect warning phase. It should be reframed as a controlled beta/tester distribution while the Play Console track is not yet available.

### 3.4 Current `/download` implementation streams GitHub release APK

`pro/website/functions/download.js` streams:

`https://github.com/pfarrergraf/video_downloader/releases/latest/download/DownloadThat-latest.apk`

through the site origin and forces a download filename `DownloadThat.apk`.

This is a useful start, but the endpoint should add stricter headers and should be paired with a beta information page rather than used as the first-click CTA.

---

## 4. Strategic approach

### 4.1 Do not attempt to bypass Google security systems

Do not implement any of the following:

- hiding app behavior,
- obfuscating package purpose to evade detection,
- changing filenames to trick scanners,
- instructing testers to disable Play Protect as the primary solution,
- dynamically downloading executable components after install,
- using misleading store-like branding,
- pretending the app is Google Play approved before it is.

### 4.2 Build trust instead

For the next 10 days, use a transparent beta path:

- signed release APK only,
- stable signing key,
- fixed package name,
- version number visible,
- SHA-256 checksum visible,
- certificate fingerprint visible if possible,
- short explanation of why Android warns on apps outside Google Play,
- clear statement that the Play Console testing track is coming,
- limited tester audience,
- no mass-public promotion yet.

---

## 5. Implementation plan

### Phase A - Immediate safety and trust hardening

#### A1. Add a dedicated beta installation page

Create:

- `pro/website/android-beta.html`

Purpose:

- explain that this is a beta/test APK,
- explain that Play Console Internal Testing is not yet active,
- explain that Android may warn on apps installed outside Google Play,
- list package name: `de.classydl.app`,
- list latest version if known,
- list SHA-256 checksum if generated by release workflow,
- link to privacy policy, terms, imprint, and refund page,
- provide one final download button to `/download`.

Suggested copy direction:

- Replace aggressive `No Play Store needed` framing with `Beta-Testversion fuer eingeladene Tester`.
- Say clearly: `Google-Play-Testversion folgt, sobald das Entwicklerkonto vollstaendig eingerichtet ist.`
- Do not tell users to disable Play Protect.
- Do tell users to install only if they received the link directly from the project owner.

Acceptance criteria:

- Header CTA goes to `/android-beta.html`, not directly to `/download`.
- The beta page has a single prominent download button.
- The beta page includes support contact and legal links.
- The beta page does not claim Play Store approval.

#### A2. Change website CTA wording

Files:

- `pro/website/index.html`
- `pro/website/i18n/*.json` if CTA text is localized

Change examples:

- `Download the free APK` -> `Join Android beta` / `Android-Beta herunterladen`
- `No Play Store needed` -> `Play Console testing track coming soon`
- `No app store needed` -> `Signed APK for invited testers`
- `Install the APK directly` -> `Install the signed beta APK directly until Play testing opens`

Acceptance criteria:

- Primary CTA does not trigger an immediate APK download from the landing page.
- Copy sounds like a controlled beta, not store avoidance.
- German and English wording are both coherent if the website language switcher is used.

#### A3. Harden `/download` response headers

File:

- `pro/website/functions/download.js`

Set explicit headers instead of mostly forwarding GitHub headers:

- `Content-Type: application/vnd.android.package-archive`
- `Content-Disposition: attachment; filename="DownloadThat.apk"`
- `X-Content-Type-Options: nosniff`
- `Cache-Control: no-store` or a controlled short max-age during active beta
- delete `set-cookie`
- preserve `Content-Length` if available

Optional:

- provide a `HEAD` handler if useful for browsers/download managers.

Acceptance criteria:

- `/download` still streams the latest APK.
- Browser receives APK content type.
- No GitHub cookies are forwarded.
- The URL shown to testers stays on the project domain.

#### A4. Add beta tester instructions

Create:

- `docs/ANDROID_BETA_TESTER_INSTALL_GUIDE.md`

Content:

- what the app does,
- expected Android warning language,
- what not to do,
- how to verify checksum,
- what feedback to send,
- what logs/screenshots are useful,
- rollback/uninstall steps.

Acceptance criteria:

- A nontechnical tester can follow the guide.
- It does not ask testers to disable Play Protect as a default.

---

### Phase B - Release integrity and metadata

#### B1. Generate SHA-256 files in release workflow

File:

- `.github/workflows/android-release.yml`

Add after APK copy step:

```bash
cd release-out
sha256sum "DownloadThat-${RELEASE_TAG}.apk" > "DownloadThat-${RELEASE_TAG}.apk.sha256"
sha256sum "DownloadThat-latest.apk" > "DownloadThat-latest.apk.sha256"
```

Attach checksum files to GitHub Release.

Acceptance criteria:

- GitHub Release contains:
  - `DownloadThat-vX.Y.Z.apk`
  - `DownloadThat-vX.Y.Z.apk.sha256`
  - `DownloadThat-latest.apk`
  - `DownloadThat-latest.apk.sha256`
- Checksums match the attached APKs.

#### B2. Generate a release metadata JSON

Create during release workflow:

- `DownloadThat-release.json`

Suggested fields:

```json
{
  "appName": "DownloadThat",
  "packageName": "de.classydl.app",
  "versionName": "0.2.0",
  "versionCode": 200,
  "apkFile": "DownloadThat-latest.apk",
  "sha256": "...",
  "releaseTag": "v0.2.0",
  "generatedAt": "2026-07-03T00:00:00Z"
}
```

Attach it to GitHub Release.

Future extension:

- Cloudflare Pages can fetch/display this metadata or a checked-in copy can be updated by CI.

Acceptance criteria:

- Release page has machine-readable metadata.
- Beta page can later consume it.

#### B3. Document signing-key continuity

Create or update:

- `docs/ANDROID_SIGNING_AND_RELEASE.md`

Content:

- never rotate signing key unless unavoidable,
- how to set GitHub secrets,
- how to verify APK signature,
- how to build AAB for Play Console,
- difference between APK for sideload and AAB for Play Console.

Acceptance criteria:

- Future Claude/Copilot sessions know not to break update continuity.

---

### Phase C - Play Protect / tester trust mitigation

#### C1. Add a public security/trust note

Create:

- `pro/website/security.html`

Content:

- low permission footprint,
- no contacts/SMS/location/camera/mic permissions,
- local-only processing statement,
- why `INTERNET` is required,
- why APK is currently outside Play Store,
- Play Console testing status,
- checksum verification.

Acceptance criteria:

- Beta page links to security note.
- Security note does not overpromise.
- Security note explains warnings without dismissing them.

#### C2. Add a repo-side APK review checklist

Create:

- `docs/APK_SECURITY_REVIEW_CHECKLIST.md`

Checklist:

- Manifest permission review
- dependency review
- signing check
- checksum check
- VirusTotal/manual scan result recorded by human, if used
- release source verified
- website download link verified
- privacy/legal pages present

Acceptance criteria:

- Each release can be reviewed before tester distribution.

#### C3. Avoid permission creep

Add developer note to:

- `CLAUDE.md`

Instruction:

- do not add dangerous Android permissions without explicit owner approval and a documented reason.
- preserve `allowBackup="false"` unless deliberately changed with rationale.

Acceptance criteria:

- Future AI sessions are warned before adding risky permissions.

---

### Phase D - Cloudflare Pages readiness

#### D1. Confirm/complete required GitHub Actions secrets

Human task in GitHub repo settings:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `STRIPE_SECRET_KEY`
- eventually `STRIPE_WEBHOOK_SECRET`

Recommended Cloudflare token scope:

- enough to deploy Pages project and manage Pages secrets.
- avoid global all-powerful tokens if a restricted token works.

Acceptance criteria:

- `Deploy Pro website to Cloudflare Pages` workflow can run.
- First run creates/deploys `downloadthat` Pages project or successfully deploys to existing project.

#### D2. Ensure Cloudflare project production branch is correct

Current workflow creates Pages project with:

```bash
npx -y wrangler@3 pages project create downloadthat --production-branch=master
```

But current active branch is:

`claude/gothic-downloader-website-bp7r2u`

Decision needed:

Option 1: Keep production branch as `master`, use workflow deploy command for previews/branch deploys until merge.

Option 2: Change production branch temporarily to `claude/gothic-downloader-website-bp7r2u` while the project is not merged to master.

Recommendation for next 10 days:

- Use explicit workflow deploy from `claude/gothic-downloader-website-bp7r2u`.
- Do not merge to `master` only to satisfy Cloudflare unless branch state is intentionally ready.
- Consider changing `--production-branch` to `claude/gothic-downloader-website-bp7r2u` during beta if Cloudflare treats the master production branch as canonical.

Acceptance criteria:

- The public beta website deploys the latest Claude-branch code.
- The website download CTA points to the intended GitHub latest release asset.

#### D3. Add environment validation page or endpoint

Optional file:

- `pro/website/functions/api/health.js`

Return safe status only:

```json
{
  "ok": true,
  "dbBindingPresent": true,
  "stripeSecretConfigured": true,
  "webhookSecretConfigured": false
}
```

Do not reveal secret values.

Acceptance criteria:

- After deployment, owner can open `/api/health` and see whether required bindings/secrets are present.

---

### Phase E - Stripe usability

#### E1. Clarify current mode: test vs live

Current landing page still contains test Stripe links:

- monthly test link
- yearly test link
- lifetime test link

Task:

- label test mode clearly on beta/staging pages, or
- replace with live links only when Stripe live mode is ready.

Acceptance criteria:

- Users cannot accidentally think a test purchase is a live purchase.
- Before public launch, no `buy.stripe.com/test_...` links remain on the production public site.

#### E2. Validate Stripe webhook flow

Files:

- `pro/website/functions/api/webhook.js`
- `pro/website/functions/_lib.js`
- `pro/website/schema.sql`

Required events:

- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`

Acceptance criteria:

- Successful checkout creates/updates license record.
- Subscription cancellation or expiration invalidates or downgrades license appropriately.
- Lifetime purchases remain valid.
- Webhook signature verification fails closed.

#### E3. Add Stripe setup checklist

Create:

- `docs/STRIPE_CLOUDFLARE_SETUP_CHECKLIST.md`

Content:

- test mode setup
- live mode setup
- webhook endpoint URL
- required events
- required Pages secrets
- D1 binding name `DB`
- how to test `/api/validate?key=...`
- how to test refund route if present

Acceptance criteria:

- A future assistant can continue without needing chat history.

---

### Phase F - Play Console handoff in 10 days

#### F1. Prepare Play Console assets and metadata

Existing branch already has `store_assets/` files.

Tasks:

- verify assets match Play Console requirements,
- prepare short description,
- prepare full description,
- prepare privacy policy URL,
- prepare app category,
- prepare data safety answers,
- prepare tester email group.

Create:

- `docs/PLAY_CONSOLE_INTERNAL_TESTING_PREP.md`

Acceptance criteria:

- When owner has Play Console access, upload can start immediately.

#### F2. Use AAB, not APK, for Play Console

The release workflow already builds:

- `android/app/build/outputs/bundle/release/app-release.aab`

Acceptance criteria:

- AAB artifact is attached/uploaded for manual Play Console upload.
- APK remains only for direct sideload beta.

---

## 6. Proposed task order

### First implementation batch

1. Add `android-beta.html`.
2. Change landing page CTAs to point to beta page.
3. Harden `download.js` headers.
4. Add release checksum generation in `android-release.yml`.
5. Add `docs/ANDROID_BETA_TESTER_INSTALL_GUIDE.md`.
6. Add `docs/APK_SECURITY_REVIEW_CHECKLIST.md`.

### Second implementation batch

1. Add `security.html`.
2. Add release metadata JSON generation.
3. Add or update `docs/ANDROID_SIGNING_AND_RELEASE.md`.
4. Add `docs/STRIPE_CLOUDFLARE_SETUP_CHECKLIST.md`.
5. Add optional `/api/health` for Cloudflare/Stripe/D1 readiness.

### Third implementation batch

1. Review all `test_` Stripe links before public production deployment.
2. Prepare Play Console internal testing doc.
3. Confirm package name strategy before first public Play Console upload.
4. Build and test signed APK release.
5. Collect tester feedback.

---

## 7. Open decisions for Benjamin

1. Domain for beta page:
   - `downloadthat.geistreich.com`
   - `downloadthat.gaistreich.com`
   - Cloudflare generated `*.pages.dev`

2. Package name stability:
   - keep `de.classydl.app`
   - or change before public testing to a brand/domain-aligned package such as `de.geistreich.downloadthat` or `com.gaistreich.downloadthat`

   Important: changing package name later means Android treats it as a different app.

3. Public wording:
   - German-first?
   - English-first?
   - both via existing i18n system?

4. Stripe mode during beta:
   - test mode only,
   - hidden payment links until live mode,
   - visible test purchase flow for trusted testers only.

5. Whether to keep GitHub Releases as the APK source of truth or move APK storage to Cloudflare R2 later.

---

## 8. Guardrails for future AI sessions

- Work on `claude/gothic-downloader-website-bp7r2u` unless Benjamin explicitly says otherwise.
- Do not treat `copilot/claudegothic-downloader-website-bp7r2u` as source of truth.
- Do not change branch refs, force-push, merge, or retarget PRs without first explaining the exact operation to Benjamin.
- Do not add dangerous Android permissions without explicit approval.
- Do not remove release signing checks.
- Do not distribute unsigned/debug APKs.
- Do not frame direct APK install as store avoidance; frame it as controlled beta testing.
- Do not expose Cloudflare, GitHub, Android keystore, or Stripe secrets in code, docs, screenshots, logs, or comments.
- Do not make real Stripe/live-payment changes unless the owner has explicitly requested live mode.

---

## 9. Definition of done for the 10-day bridge period

Before Play Console Internal Testing is available, the bridge-period setup is acceptable when:

- The landing page routes testers through a beta explanation page before download.
- APK is signed by the stable release key.
- GitHub Release contains APK plus checksum files.
- Website download endpoint has hardened headers.
- Website includes security/trust explanation.
- Tester guide exists.
- Release/security checklist exists.
- Cloudflare deploy workflow can deploy the beta site from the Claude branch.
- Stripe test flow is clearly marked or hidden from public production users.
- No dangerous Android permissions have been added.
- Play Console prep document is ready for the day the developer account is usable.
