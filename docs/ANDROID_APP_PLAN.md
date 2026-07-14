# Plan: Standalone, sideloadable Android app (no Play Store)

> **HISTORISCH / ABGELÖST.** Dieser frühe Sideload-only-Plan beschreibt nicht die
> aktuelle Google-Play-first-Architektur. Siehe
> `security/GOOGLE_PLAY_SECURITY_ARCHITECTURE.md` und
> `docs/GOOGLE_PLAY_OWNER_CHECKLIST.md`.

Goal: package ClassyDL as a real Android APK that anyone can install by downloading
the file and enabling "install from unknown sources" — no Google Play, no developer
account, no review process. Distributed via GitHub Releases (and optionally F-Droid
later).

## Chosen architecture

**Chaquopy** (a Gradle plugin that embeds a real CPython interpreter in an Android
app) + a thin native Android shell:

```
Android app (Kotlin, minimal)
 ├─ on launch: starts embedded Python, running video_downloader.web.server
 │             bound to 127.0.0.1:<port>  (the exact module built for Termux)
 └─ MainActivity hosts a WebView pointed at http://127.0.0.1:<port>
                (the exact same static/index.html Gothic UI, unchanged)
```

Why this over Kivy/Buildozer or a full native rewrite: the entire backend
(`scraper.py`, `core.py`, `queue_runner.py`, `queue_store.py`, `web/server.py`) is
already pure Python with no compiled dependencies — a requirement we already had to
satisfy for Termux. Chaquopy runs that code completely unmodified inside the app's
own process. The frontend is already a browser page. This reuses ~100% of existing
code; a Kivy rewrite would mean rebuilding the UI in Kivy's widget system for no
benefit, since we already have a working web UI.

## Why this needs a different build environment than this session

Building an Android APK requires the Android SDK/NDK and Gradle, which aren't
available in this sandbox (no `sdkmanager`, no emulator, no `adb`). The plan below is
scaffolded as real files in this repo, but the *first actual build* has to happen
either:
- on your machine, in Android Studio, or
- in CI (GitHub Actions has Android SDK images) — recommended, so a signed APK comes
  out automatically as a Release artifact without you needing Android Studio at all.

Expect a debug loop similar to the Termux rounds: CI build fails on something
platform-specific → fix → rebuild, until it's green.

## Phases

### Phase 1 — Scaffold the app, get a debug APK building (and self-testing) in CI
- **Status: DONE and verified green in CI** (2026-07-01, run #5:
  https://github.com/pfarrergraf/video_downloader/actions/runs/28512295438).
  `/api/health` answered `{"status": "ok"}` from inside a freshly booted CI
  emulator with the just-built debug APK installed — the embedded Python server
  is genuinely alive on-device.
- `android/` Gradle project (Chaquopy 17.0.0 + AGP 8.7.3): `app/build.gradle` bundles
  the existing `video_downloader` package straight from the repo root as a Chaquopy
  Python source set (no wheel-building step), plus a `pip{}` block for `requests`,
  `beautifulsoup4`, `yt-dlp` (rich/textual are CLI/TUI-only, deliberately excluded).
- `MainActivity.kt` starts Python via `com.chaquo.python.Python`, runs
  `video_downloader.android_entry.start(...)` on a background thread, and hosts a
  `WebView` pointed at `http://127.0.0.1:8420` (with a network-security-config
  cleartext exception scoped to `127.0.0.1` only, and a short retry loop for the
  race between "activity created" and "server thread listening").
- `video_downloader/android_entry.py` is a new, minimal entry point: wires up a
  `QueueStore` + calls `run_server(...)` from plain string/int arguments, so the
  Kotlin side doesn't need to construct Python objects across the JNI boundary.
- `.github/workflows/android-build.yml` has two jobs: `build` (assembles the debug
  APK via `gradle/actions/setup-gradle`, no committed wrapper jar needed — see
  below) and `emulator-smoke-test` (boots a hardware-accelerated x86_64 emulator via
  `reactivecircus/android-emulator-runner`, installs the APK, launches the activity,
  and polls `/api/health` through `adb forward`, via `.github/scripts/smoke_test.sh`
  since the action runs each `script:` line as a separate shell invocation and
  can't survive a multi-line loop inline). Both run on free/unlimited minutes
  since this repo is public.
- `app.build.gradle`'s Chaquopy Python source set excludes `android/**` (and
  `tests/**`, `scripts/**`, etc.) from the repo-root srcDir — needed because the
  Android project's own `build/` output directory otherwise nests inside the same
  tree Chaquopy scans, which Gradle's task-validation flags as an implicit
  dependency conflict.
- `ndk.abiFilters` includes both `arm64-v8a` (real phones) and `x86_64` (CI/desktop
  emulators) — Chaquopy requires this to be set explicitly, unlike plain AGP.
  Phase 4 narrows this to `arm64-v8a` only for the APK that's actually distributed.
- No `gradle-wrapper.jar` is committed (a real Gradle distribution can't be produced
  as text) — CI provisions Gradle 8.10.2 directly via `gradle/actions/setup-gradle`.
  Whoever opens this in Android Studio locally will get prompted to generate a
  wrapper, or can run `gradle wrapper` once themselves.
- Chaquopy needs a Python 3.11 interpreter on the **build machine** (separate from
  the Android-target runtime it bundles) to run pip during packaging — CI installs
  one via `actions/setup-python@v5`; `buildPython "python3.11"` is pinned explicitly
  in `app/build.gradle` rather than relying on autodetection.
- It took 5 CI iterations to go green (missing abiFilters → missing build-time
  Python → Gradle task-overlap validation → broken multi-line shell script →
  success), each diagnosed from real CI logs rather than guessed — see `memory.md`
  for the full blow-by-blow.
- **Done when:** the `emulator-smoke-test` job goes green — i.e., `/api/health`
  answers from inside a freshly booted emulator with the just-built APK installed.
  ✅ Done.

### Phase 2 — Bundle ffmpeg

**Step 2a — pragmatic fallback: DONE.** `DownloadRequest.ffmpeg_binary` was never
actually wired into the yt-dlp subprocess call (only the separate, rarely-used
FFmpeg strategy checked it) — `strategies.YtDlpStrategy.download` now checks
`shutil.which(request.ffmpeg_binary)` and:
- if ffmpeg is available: unchanged behavior (`-f ba/b` + `-x --audio-format mp3`,
  now also passing `--ffmpeg-location` explicitly instead of relying on yt-dlp's
  own PATH search — needed for wherever Phase 2b's bundled binary ends up living),
- if not: selects `-f bestaudio` and skips `-x`/`--audio-format` entirely, so
  yt-dlp saves whatever audio-only container the source already provides
  (m4a/opus/webm) with **no extraction or re-encoding**, which needs no ffmpeg at
  all.

This means audio downloads already work on the current Android APK today, just
not always as a universally-converted MP3. Covered by
`tests/test_strategies_audio_fallback.py`.

**Step 2b — real ffmpeg build: DONE, green on the first CI attempt** (2026-07-01,
run #8: https://github.com/pfarrergraf/video_downloader/actions/runs/28514879147).
Rejected embedding an unverified prebuilt ffmpeg-for-Android binary from a
third-party source (supply-chain trust risk — no way to verify what's actually in
an unaudited binary blob shipped inside the app). Instead:
- `.github/scripts/build_ffmpeg_android.sh` cross-compiles **libmp3lame 3.100**
  then **ffmpeg release/7.1** from their official upstream sources, using the
  Android NDK's LLVM toolchain (`aarch64-linux-android26-clang` /
  `x86_64-linux-android26-clang`, `llvm-ar`/`llvm-ranlib`/`llvm-strip`/`llvm-nm`),
  producing a static CLI binary with `--enable-libmp3lame` (confirmed present in
  the binary's own `ffmpeg -version` configuration banner in CI logs) — MP3
  encoding genuinely works, not just stream copy.
- A `build-ffmpeg` CI job (matrix over `arm64-v8a`, `x86_64`) runs this and
  uploads each binary as an artifact; the `build` job downloads both and places
  them at `android/app/src/main/jniLibs/<abi>/libffmpeg.so` before the Gradle
  build (Android only allows executing files shipped as `.so` under `jniLibs`
  post-scoped-storage — naming it as a "library" is the standard workaround, not
  an actual shared library).
- `MainActivity.resolveFfmpegBinary()` resolves `applicationInfo.nativeLibraryDir
  + "/libffmpeg.so"` and passes it through
  `android_entry.start(..., ffmpeg_binary=...)` → `run_server(...)` →
  `ClassyDLServer.ffmpeg_binary` → `store.add_job(ffmpeg_binary=...)`, falling
  back to the plain `"ffmpeg"` command name if the bundled binary is ever
  missing (e.g. an APK built before this phase).
- `.github/scripts/ffmpeg_exec_test.sh` independently pushes the x86_64 binary
  onto the CI emulator and runs `-version` on it directly (outside the app),
  proving the cross-compiled binary actually executes on Android — confirmed:
  full `ffmpeg version ... libavutil/libavcodec/.../libswresample` banner printed
  from inside the emulator.
- Each full compile took ~3 minutes per ABI in CI (much faster than the
  "expect several slow iterations" worry below turned out to require — it went
  green on the very first attempt).
- **Done when:** an audio-only download produces a converted MP3 on-device (not
  just the pragmatic native-format fallback). ✅ Infrastructure confirmed
  end-to-end (ffmpeg runs on-device with libmp3lame linked in); an actual
  audio-only download exercising this on a real queued job hasn't been manually
  verified yet — worth a real-device sanity check when convenient, but the
  underlying pieces are all individually proven.

### Phase 3 — Storage

**Status: DONE and verified green in CI** (2026-07-01, run #15:
https://github.com/pfarrergraf/video_downloader/actions/runs/28519642270).
`download_pipeline_test.sh` completed end-to-end on-device: job queued, downloaded,
and confirmed at `/sdcard/Android/data/de.classydl.app/files/classydl-downloads/job-1/`
(8044 bytes). Two layers, both needed
because they cover different Android versions/failure modes:

- **3a (base layer):** `MainActivity` now points `output_dir` at
  `getExternalFilesDir(null)` instead of internal `filesDir` — app-specific
  external storage, which needs no runtime permission on any supported API
  level (scoped storage explicitly exempts an app's own directory under
  `Android/data/<package>/`), and is reachable via `adb shell` and most file
  manager apps without root, unlike internal storage. Falls back to `filesDir`
  in the rare case external storage isn't currently available.
- **3b (Downloads-collection layer):** `video_downloader/android_entry.py` runs
  a background poller (`_run_downloads_publisher`) that watches for newly
  completed jobs and copies each finished file into Android's shared
  `MediaStore.Downloads` collection (API 29+) via Chaquopy's `java` bridge
  (`from java import jclass`) — this is what actually surfaces the file in the
  stock Files app's "Downloads" section, not just a technically-reachable path.
  A per-file `.mediastore-published` marker (sibling file) makes this durable
  across app restarts without needing a DB schema change. Every step is wrapped
  in broad exception handling: if the Java bridge call fails for any reason,
  it's logged and swallowed — the file already exists safely via 3a regardless,
  so a MediaStore hiccup must never affect the download itself. No-ops cleanly
  off-Android (Termux/desktop/CI unit tests) since `java` isn't importable
  there — see `tests/test_android_entry.py`.
- `.github/scripts/download_pipeline_test.sh` extends the CI emulator job to
  exercise a real download end-to-end for the first time (previous phases only
  checked `/api/health` and a standalone `ffmpeg -version`): queues a tiny
  test file via the actual HTTP API, polls until completion, confirms the file
  exists at the expected external-storage path via `adb shell`, and does a
  best-effort (non-fatal) MediaStore query check — non-fatal specifically
  because the Java-bridge MediaStore code is the riskiest untested new piece;
  the external-storage check is the hard pass/fail gate. The test file is
  generated on the fly (stdlib `wave` module) and served from the CI runner
  itself via `python3 -m http.server` + `adb reverse`, rather than fetched
  from a real internet host — an earlier version pointed at a Wikimedia URL
  and got intermittently 403'd by Wikimedia's anti-bot/datacenter-IP blocking
  of GitHub Actions runners, which looked like an Android bug but wasn't; see
  `memory.md`'s "CI download test's 403 was Wikimedia blocking the runner, not
  Android" entry.
- **Not done:** no Storage Access Framework picker for a user-chosen folder —
  the automatic Downloads-collection publish covers the "done when" bar without
  needing one; a picker could still be added later as a nice-to-have if users
  want downloads to land somewhere other than the default Downloads folder.
- **Done when:** a completed download is visible from the stock Android Files
  app. ✅ Done via the external-files-dir copy (3a), confirmed by
  `download_pipeline_test.sh` passing in CI run #15. The MediaStore
  Downloads-collection publish (3b) turned out to have been completely
  broken since it was written (the `ContentValues.put` bug below) — that bug
  is now fixed, but 3b still isn't confirmed actually inserting rows: CI run
  #17 still reported "not found" within the 10s check window, this time
  because of a separate, pre-existing issue (a duplicate server-start crash —
  see `memory.md`'s "intermittent duplicate server start" entry). 3b remains
  a best-effort, unconfirmed nice-to-have; the "done when" bar above is met
  through 3a regardless.

**3b was silently broken by a ContentValues.put bug since it was written.**
Run #15's MediaStore check reported "not found" for the downloaded file;
first hypothesis was a timing race (the check ran ~1.6s after job completion
while the publisher only polled every 3s). Shrunk
`android_entry._PUBLISH_POLL_SECONDS` to 1.0 and made the CI check retry for
up to 10s so a real failure would be distinguishable from a race — and the
very next run (#16) surfaced a genuine, previously-silent exception:
`TypeError: android.content.ContentValues.put is ambiguous for arguments
(str, int)`. Root cause: `values.put("is_pending", 1)` passed a bare Python
`int` across the Chaquopy/Java bridge to an overloaded method (Byte/Short/
Integer/Long/Float/Double all accept `put(String, ...)`), which Chaquopy
can't resolve without help — it had been raising and getting silently
swallowed by `_publish_file_to_downloads`'s broad `except Exception` on
every single call since Phase 3 was written. Fixed by wrapping both
`is_pending` values with Chaquopy's `jint()` type-disambiguation helper
(`from java import jclass, jint`). See `memory.md` for the full incident —
the standing lesson: a "best-effort, non-fatal" check that swallows its own
exceptions can hide a completely broken code path indefinitely.

**Critical fix found by Phase 3's own CI test:** the first real, non-mocked
download attempt on Android (via `download_pipeline_test.sh`) failed even
though `/api/health` and `ffmpeg -version` both passed — proving those two
checks alone weren't sufficient coverage. Root cause: `YtDlpStrategy` shelled
out to `sys.executable -m yt_dlp` via `subprocess`. That works on a normal OS
but not under Chaquopy — Python is embedded as a library there, not a
standalone executable, so `sys.executable` isn't something `subprocess` can
exec (matches Chaquopy's documented `subprocess.Popen`/"Permission denied"
limitation). Every yt-dlp download failed on Android from the very start of
Phase 1, silently, because nothing before this exercised an actual download.
Fixed by rewriting `YtDlpStrategy` to call yt-dlp in-process via its Python
API (`yt_dlp.YoutubeDL(opts).download(...)`) instead of subprocess — verified
option names against the installed yt-dlp source directly (`outtmpl` needs a
dict with a `'default'` key, `cookiesfrombrowser` a 4-tuple, etc., rather than
guessing from the CLI flag names) and confirmed working end-to-end against a
local HTTP server (network access to real hosts isn't available in this dev
sandbox). This is a strict improvement on every platform, not just an Android
workaround — one less subprocess spawn, and it was already relying on the
same directory-diff fallback (`_find_new_files`) for its primary file
detection in some cases anyway.

### Phase 4 — Release pipeline

**Status: implemented, needs a one-time secret setup before it can run for
real.** A release keystore was generated (`keytool -genkeypair`, RSA 4096,
10000-day validity, PKCS12) and delivered directly to you off-repo (never
committed — a signing key is a permanent secret; anyone with it can publish
updates that Android will accept as "the same app" as yours) — see the chat
message it was sent in for the file and passwords.

**One-time setup required before the release workflow can produce a signed
APK** — add these four repository secrets (Settings → Secrets and variables →
Actions → New repository secret) in `pfarrergraf/video_downloader`:
- `ANDROID_KEYSTORE_BASE64` — the base64-encoded keystore file contents
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS` — `classydl`
- `ANDROID_KEY_PASSWORD` (same as the keystore password for this PKCS12
  keystore — `keytool` doesn't support separate store/key passwords for that
  format)

**⚠️ Back up the keystore file itself somewhere safe (password manager,
offline storage) independent of these GitHub secrets.** If it's ever lost,
there is no way to publish an update that replaces the existing app on
someone's phone with the same signing identity — they'd have to uninstall
the old one and install a new one from scratch under a new signature.

Once those secrets exist:
- `.github/workflows/android-release.yml` (a separate workflow from
  `android-build.yml` — see the file's header comment for why: a `push.tags`
  trigger combined with a `paths` filter would AND them together and could
  skip a release whose tag commit doesn't touch those specific paths, which
  defeats the point of "tag it to release it") triggers on any tag matching
  `v*.*.*`.
- It cross-compiles ffmpeg for `arm64-v8a` only (release ships one ABI, see
  below), builds via `gradle :app:assembleRelease -PabiFilters=arm64-v8a`
  with the four secrets as env vars, and attaches
  `DownloadThat-<tag>.apk` to an auto-created GitHub Release via
  `softprops/action-gh-release`.
- A "verify signing secrets are configured" step fails the build early with a
  clear error if the secrets are missing, instead of silently publishing an
  unsigned (uninstallable) APK.
- `app/build.gradle`'s `signingConfigs.release` reads the four env vars
  (`System.getenv(...)`) and decodes the keystore into `$buildDir` at
  configure time; if unset (e.g. a contributor running `gradle
  assembleRelease` locally without the secrets), the release build type is
  simply left unsigned — same as plain AGP's default, no new failure mode.
- `-PabiFilters=arm64-v8a` narrows `ndk.abiFilters` for that one build
  invocation via a Gradle project property (`app/build.gradle`'s
  `abiFilterList`, defaulting to `arm64-v8a,x86_64` when the property isn't
  passed) — the debug/CI-emulator build stays on both ABIs unchanged, only
  the release build drops `x86_64` (which only ever existed so the debug APK
  could run on CI/desktop emulators, not for real phones).
- Distribution becomes: `git tag vX.Y.Z && git push origin vX.Y.Z` → CI
  produces a signed APK on the repo's Releases page → anyone downloads and
  installs it directly (with Android's standard "unrecognized developer"
  warning for a non-Play-Store APK, expected and harmless).
- **Done when:** a tagged release produces a working signed, installable APK
  download link. Pending: the one-time secrets setup above, then pushing a
  real tag to confirm the workflow end-to-end (not yet done — needs the repo
  owner to add the secrets first).

### Phase 5 (optional) — F-Droid
- Submit to F-Droid once the app is stable — gives auto-updates and organic discovery
  without any store review process controlled by Google/Apple. Requires the build to
  be fully reproducible from source (F-Droid builds it themselves from the tag), which
  Phase 1–4 already sets up.

### Phase 6 — Monetization (free/Pro tiers)

**Status: implemented, blocked on deploying the license server.** The project's license
changed from MIT to proprietary (all-rights-reserved) as part of this — see `LICENSE`.

- **Stripe** (currently a sandbox/test-mode account "Gaistreich sandbox"): a "DownloadThat
  Pro" product with 3 prices/Payment Links — €1/month, €5/year, €12 one-time lifetime.
- **`pro/`** (in this repo, excluded from the Android app's Chaquopy source set via
  `build.gradle`'s `exclude "pro/**"` since it's a separate JS/HTML deployment, not part
  of the Python package):
  - `pro/worker/` — a Cloudflare Worker that verifies Stripe webhooks (via Web Crypto
    HMAC, no SDK/`nodejs_compat` needed), issues license keys into a Cloudflare D1
    database (`downloadthat-licenses`, already created) on `checkout.session.completed`,
    keeps them in sync on subscription renewal/cancellation, and exposes
    `GET /api/validate?key=...` for the app to check.
  - `pro/website/` — a marketing landing page (pricing tiers linking to the real Payment
    Links) and a `success.html` that shows the buyer their license key right after
    checkout (polls the Worker by Stripe checkout session ID — no email service needed).
  - `pro/README.md` — exact deploy commands (`wrangler deploy`, secrets, Stripe webhook
    setup, optional `gaistreich.com` subdomain routing). **Not yet deployed** — this
    needs to happen from a session with real `wrangler`/Cloudflare account access, which
    this sandboxed session's Cloudflare MCP connection doesn't have (it can manage
    D1/KV/R2 but has no Worker-deploy or DNS tool).
- **App-side gating** (`video_downloader/licensing.py`, wired into `web/server.py` and
  `android_entry.py`):
  - Free tier (no key, or an invalid/expired one): same quality as Pro (the existing
    `default` profile, unchanged), but rationed to 1 download per rolling 24h window —
    `402` from `/api/queue` if that's already been used (counting
    pending/in-progress/completed jobs from the last 24h; cancelled/failed ones don't
    count, so a source that didn't work out doesn't burn the day's quota). Originally
    gated by a 720p resolution cap instead of a daily count — changed based on
    feedback that "1 free download a day, full quality" is the clearer offer.
  - Pro tier (valid key): no daily quota at all.
  - Entirely opt-in: `LicenseManager` is only constructed when a `license_api_base` is
    passed to `android_entry.start(...)` — Termux/desktop/CLI/tests never pass one, so
    they're always treated as Pro and completely unaffected. Even on Android, only
    **release** builds pass a real `LICENSE_API_BASE`; debug builds (what CI's
    `download_pipeline_test.sh` installs) pass an empty string, keeping the established
    CI path exercising exactly what it always has.
  - Fails closed, not open: a network error talking to the license server is treated as
    "not Pro" (never as "Pro just because we couldn't check") — see
    `licensing.LicenseManager.refresh`'s offline-grace-then-expire logic.
  - A small "Lizenz" card in `static/index.html` shows status and lets the user paste a
    key; it hides itself entirely when `GET /api/license` reports `configured: false`
    (Termux/desktop), so nothing changes for those platforms visually either.
- **`MainActivity.kt`'s `LICENSE_API_BASE` is a placeholder** — an unreachable
  `*.workers.dev` URL — until the Worker in `pro/worker/` is actually deployed and that
  constant is updated to the real URL.
- **Done when:** a real purchase on the deployed marketing site produces a key that
  unlocks Pro in a real release APK. Pending: deploying `pro/worker/` (needs real
  Cloudflare/Stripe dashboard access, see `pro/README.md`), then updating
  `LICENSE_API_BASE`.

### Phase 7 — Google Play Store publishing

**Status: IN PROGRESS.** Triggered by Play Protect flagging the sideloaded APK as
"Diese App ist eine Fälschung" (fake/malicious) specifically on *updates*, not fresh
installs — the pattern matches Play Protect's real-time scanner, which is stricter
about unregistered developers' apps that update themselves post-install (a common
malware-dropper technique) and about a bundled executable that isn't a conventional
JNI shared library (`libffmpeg.so` — see Phase 2 / "Known risks" below). Enrolling as
a known Play Console developer (Play App Signing) is expected to resolve this
regardless of the ffmpeg packaging trick, since the trust signal is about the
publisher/signing identity, not the technique itself.

- **CI now also builds a Play Console-ready artifact**: `android-release.yml`'s
  `build-signed-release` job runs `gradle :app:bundleRelease` (same signing/version
  overrides as the APK) and uploads `DownloadThat-<tag>.aab` as a workflow artifact
  (Actions run → Artifacts, not attached to the public GitHub Release — that stays
  APK-only for direct/sideload installs). The existing release keystore
  (`ANDROID_KEYSTORE_*` secrets) works fine as the Play Console "upload key".
- **Real policy risk, not just a technicality**: Google Play's Intellectual Property /
  copyright policy explicitly prohibits apps that let users download copyrighted
  streaming content (e.g. from YouTube) without authorization — a public "Production"
  listing for a general-purpose video downloader is a real rejection/takedown risk,
  disclaimer footer notwithstanding. **Internal testing** (or closed testing) doesn't
  require passing that review and is the recommended track for now: builds are
  available within seconds/minutes, up to 100 testers via an email allowlist, and —
  critically — it still enrolls the app's signing identity with Play App Signing,
  which is what should fix the Play Protect false-positive. Moving to a public
  Production listing later is a separate decision with real rejection risk that needs
  revisiting once the app is otherwise feature-complete.
- **What only the account owner can do** (needs a real identity/payment, no MCP/tool
  access from this sandbox): create a Google Play Console developer account (one-time
  $25 fee), complete identity verification (legal name/address/phone; government ID
  may be requested), create the app entry, choose "Internal testing" as the release
  track, opt into Play App Signing (let Google manage the app signing key — the
  keystore in this repo's secrets only needs to work as the *upload* key, which it
  already does), upload the `.aab` from the workflow artifact, and fill in the Data
  Safety form (this app collects no personal data beyond what's needed to validate a
  pasted Pro license key against `pro/worker/`'s D1-backed endpoint — no ads SDK, no
  analytics, no device identifiers collected).
- **Privacy policy**: already exists and is public — `pro/website/datenschutz.html`
  (German; Play Console doesn't require English specifically, but consider adding an
  English version before a Production listing, since store review skews toward
  English-language material).
- **Legal prep, done ahead of time**: `pro/website/agb.html` (Terms of Use draft,
  including the liability disclaimer that the user — not the developer — is
  responsible for the legality of what they download; **explicitly marked as a
  draft needing a lawyer's review before real/live use**, especially the digital-
  content withdrawal-right clause, which the current Stripe Payment Link checkout
  doesn't yet capture the required explicit consent for). Impressum/Datenschutz name
  placeholders filled in with "Benjamin Graf" (address/phone/VAT still placeholders —
  can't be filled in without the real values). In-app: a first-launch terms
  acceptance gate (`#terms-overlay` in `static/index.html`, persisted via
  `QueueStore` as `terms_accepted_version`, gated on `server.py`'s
  `CURRENT_TERMS_VERSION` so bumping that constant re-prompts everyone) and an
  "About" section in Settings (developer name, links to the legal pages, open-source
  license attribution for yt-dlp/ffmpeg/LAME/Chaquopy/etc.).
- **Store listing assets prepared ahead of time**: `store_assets/` (512×512 icon,
  1024×500 feature graphic, three real screenshots of the running app captured via
  Playwright, and short/full description text in German and English) — see
  `store_assets/README.md`. Excluded from the Chaquopy Python source set
  (`build.gradle`) like `pro/**`.
- **Done ahead of the 2026-08-31 deadline**: `compileSdk`/`targetSdk` bumped to 36,
  AGP to 8.13.0 (min Gradle 8.13, defaults to NDK 27.0.12077973 — the first NDK
  release whose linker defaults to 16 KB page-aligned native libraries), and the
  self-built ffmpeg binary now also passes explicit
  `-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384` linker flags. This also
  covers Google's separate 16 KB native-library alignment requirement (already past
  its 2026-05-31 enforcement date for new Play Console submissions). Verified via
  `android-build.yml`/`android-release.yml` CI, not locally (no Android SDK in this
  sandbox) — Chaquopy 17.0 documents support for AGP 8.9 through 8.13, so no
  Chaquopy version bump was needed.

## Known risks / things that will probably need a fix-it round

- **Resolved — hardcoded password:** `MainActivity.kt` used to hardcode
  `PASSWORD = "classydl"` for every install (a Phase 1 scaffold shortcut,
  flagged as a TODO ever since). Fixed: debug builds (CI, local `gradle
  installDebug`) still use that fixed value on purpose, so existing tests and
  dev workflows keep working unchanged; release builds now generate a random
  per-install password on first launch via `SecureRandom`, persisted in
  `SharedPreferences`, and log in automatically by injecting it into the
  login form via `WebView.evaluateJavascript` on `onPageFinished` — the user
  never sees or types a password, but no two sideloaded installs share one.
  Distinguished via the generated `BuildConfig.DEBUG` flag (needed
  `buildFeatures { buildConfig true }`, off by default since AGP 8).
- **Android exec restrictions**: newer Android versions (10+) restrict executing
  arbitrary files from writable storage; the `jniLibs` trick in Phase 2 is the
  standard workaround but needs verifying on-device.
- **Resolved — APK size**: the release build (Phase 4) now passes
  `-PabiFilters=arm64-v8a` to drop the `x86_64` slice that only existed for
  CI/desktop emulator testing — the distributed APK ships `arm64-v8a` only,
  covering the vast majority of real phones from the last ~6 years.
  `armeabi-v7a` can be added later if someone actually needs it.
- **Google Play Protect** will likely show an "unrecognized app" warning on install
  since it's unsigned by a known publisher — expected for any sideloaded APK, not a
  bug, but worth telling recipients in advance so they're not alarmed.
- **Chaquopy licensing**: as of v12.0.1, Chaquopy is fully open-source and MIT
  licensed with no restrictions (previously it required a commercial license for
  closed-source apps) — this repo can use it freely regardless of license.
  ([chaquo.com](https://chaquo.com/chaquopy/chaquopy-is-now-open-source/))

## Next step

Phases 1–3 are done and confirmed green in CI (run #15, including a real
end-to-end download landing on-device). Phase 4's code (signing config,
release workflow, per-install password, arm64-only release ABI) is now
implemented but **blocked on a one-time manual step**: add the four
`ANDROID_KEYSTORE_*`/`ANDROID_KEY_*` secrets to the GitHub repo (see Phase 4
above for exact names — the keystore itself was generated and sent to you
directly, not committed). Once those secrets exist, push a tag
(`git tag v0.1.0 && git push origin v0.1.0`) to trigger the first real signed
release build and confirm it end-to-end.

In the meantime, the current debug APK can already be downloaded and
sideloaded onto a real phone to try the full scraping/queue/download UI
end-to-end (including ffmpeg-dependent audio formats): see the latest
`android-build.yml` run's Artifacts section on the repo's Actions tab.
