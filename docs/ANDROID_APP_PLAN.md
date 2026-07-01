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
- Static `ffmpeg` binaries per ABI (`arm64-v8a`, `armeabi-v7a`) placed under
  `android/app/src/main/jniLibs/<abi>/libffmpeg.so` (Android only allows executing
  binaries shipped as `.so` under `jniLibs` post-scoped-storage — naming it as a
  "library" is the standard workaround, not an actual shared library).
- At startup, the app resolves the real path to the bundled binary and passes it to
  `video_downloader`'s `ffmpeg_binary` request field (already a supported parameter —
  see `DownloadRequest.ffmpeg_binary` in `models.py`), no core code changes needed.
- **Done when:** an audio-only download that requires ffmpeg extraction succeeds
  on-device.

### Phase 3 — Storage
- Scoped storage: write to the app's external files dir by default (always writable,
  no permission prompt), and offer a Storage Access Framework picker so the user can
  point downloads at the shared `Downloads/` folder if they want them visible outside
  the app without a file manager that shows app-private storage.
- **Done when:** a completed download is visible from the stock Android Files app.

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
