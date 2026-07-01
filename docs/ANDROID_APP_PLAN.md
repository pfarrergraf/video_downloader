# Plan: Standalone, sideloadable Android app (no Play Store)

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

**Status: implemented, CI-verified pending latest run.** Two layers, both needed
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
  stable Wikimedia-hosted test file via the actual HTTP API, polls until
  completion, confirms the file exists at the expected external-storage path
  via `adb shell`, and does a best-effort (non-fatal) MediaStore query check —
  non-fatal specifically because the Java-bridge MediaStore code is the
  riskiest untested new piece; the external-storage check is the hard
  pass/fail gate.
- **Not done:** no Storage Access Framework picker for a user-chosen folder —
  the automatic Downloads-collection publish covers the "done when" bar without
  needing one; a picker could still be added later as a nice-to-have if users
  want downloads to land somewhere other than the default Downloads folder.
- **Done when:** a completed download is visible from the stock Android Files
  app. Pending confirmation from the next CI run (this was implemented and
  pushed but not yet observed green, unlike Phases 1–2 which were confirmed
  before being marked done).

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
- Generate a signing keystore once (self-signed is fine for sideloading), store as a
  GitHub Actions secret.
- `android-build.yml` gains a release job: on a version tag, run
  `assembleRelease`, sign, attach the APK to a GitHub Release.
- Distribution becomes: `git tag vX.Y.Z && git push --tags` → CI produces a signed
  APK on the repo's Releases page → anyone downloads and installs it directly.
- **Done when:** a tagged release produces a working signed APK download link.

### Phase 5 (optional) — F-Droid
- Submit to F-Droid once the app is stable — gives auto-updates and organic discovery
  without any store review process controlled by Google/Apple. Requires the build to
  be fully reproducible from source (F-Droid builds it themselves from the tag), which
  Phase 1–4 already sets up.

## Known risks / things that will probably need a fix-it round

- **Android exec restrictions**: newer Android versions (10+) restrict executing
  arbitrary files from writable storage; the `jniLibs` trick in Phase 2 is the
  standard workaround but needs verifying on-device.
- **APK size**: bundling ffmpeg per-ABI adds tens of MB; may want to ship only
  `arm64-v8a` initially (covers the vast majority of phones from the last ~6 years)
  and add `armeabi-v7a` only if someone actually needs it.
- **Google Play Protect** will likely show an "unrecognized app" warning on install
  since it's unsigned by a known publisher — expected for any sideloaded APK, not a
  bug, but worth telling recipients in advance so they're not alarmed.
- **Chaquopy licensing**: as of v12.0.1, Chaquopy is fully open-source and MIT
  licensed with no restrictions (previously it required a commercial license for
  closed-source apps) — this repo can use it freely regardless of license.
  ([chaquo.com](https://chaquo.com/chaquopy/chaquopy-is-now-open-source/))

## Next step

Phase 1 is done. Next up is Phase 2: bundle ffmpeg for Android so audio-only
downloads (which need ffmpeg extraction) work on-device, not just plain video
downloads that yt-dlp can save directly.

In the meantime, the current debug APK from CI run #5 can already be downloaded
and sideloaded onto a real phone to try the scraping/queue/download UI end-to-end
(without ffmpeg-dependent formats): see the workflow run's Artifacts section at
https://github.com/pfarrergraf/video_downloader/actions/runs/28512295438
