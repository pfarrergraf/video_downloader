# Project Memory

A running log of decisions and incidents worth remembering, in case future work
(by Claude or a human) needs the "why," not just the "what." Newest entries on top.

## 2026-07-01 — Open follow-up: intermittent duplicate server start on Android

CI run #17 (after the `jint()` MediaStore fix landed) confirmed the
`ContentValues.put` ambiguity is gone — but the MediaStore publish still
didn't complete within the check's 10s window, this time because of a
different, pre-existing issue: logcat showed `ClassyDL: Server thread
crashed — OSError: [Errno 98] Address already in use`, about 2 minutes after
the app was launched via `adb shell am start`. This matches a crash first
noticed (but not investigated) back in run #13's logs, so it's not a
regression from today's changes — it's an existing, unexplained issue.

Working theory, not yet confirmed: `MainActivity.onCreate` (and therefore
`startPythonServer()`) runs a second time at some point after the initial
launch — possibly an Activity recreation Android triggers for a reason not
yet identified (not clearly caused by the WebView load-retry logic, which
only spans ~10s, far short of the ~2 minute gap observed). The second
`run_server()` call fails to bind to the already-listening port 8420 and
that thread crashes — harmlessly, since the first server instance keeps
running and the app functions normally — but it also means a *second*
`_run_downloads_publisher` thread starts (that thread launches before the
port bind, so it isn't affected by the bind failure), doubling up on
publish-polling against the same sqlite DB. Not itself confirmed to be *why*
the MediaStore publish missed the 10s window this run, but worth ruling out
first.

**Not yet fixed — functionally low priority** since Phase 3's actual "done
when" bar (a completed download visible via the app's external-files-dir
copy) is unaffected either way. Worth investigating if it starts causing
visible problems (e.g. duplicate downloads, doubled log noise) or before
relying on MediaStore-Downloads visibility for anything user-facing.

## 2026-07-01 — MediaStore publish was never actually working: ContentValues.put ambiguity

The previous entry below concluded run #15's MediaStore "not found" was just a
timing race (test checked before the 3s-interval publisher's next cycle) and
fixed it by shrinking the poll interval to 1s and having the CI check retry
for 10s. That fix was itself correct, but it also did its job as a
diagnostic: the very next CI run (#16) hit real headroom to actually run the
publish code, and it immediately failed with a genuine exception that had
been silently swallowed by `_publish_file_to_downloads`'s broad
`except Exception: traceback.print_exc()` since Phase 3 was written:

```
TypeError: android.content.ContentValues.put is ambiguous for arguments
(str, int): options are void ContentValues.put(String, Byte), ...Double,
...Float, ...Integer, ...Long, ...Short
```

Root cause: `values.put("is_pending", 1)` passes a bare Python `int` across
the Chaquopy/Java bridge to an overloaded method, and nothing about a plain
int says which of Byte/Short/Integer/Long/Float/Double to pick — Chaquopy
can't resolve the overload and raises instead of guessing. So the
MediaStore-Downloads publish step had *never* actually inserted anything;
every completed download only ever showed up via the external-files-dir copy
(3a), never the stock Files app's Downloads section (3b) — since the
external-files-dir path already satisfied Phase 3's "done when," this went
unnoticed until the test finally got to see it.

Fixed by importing `jint` from Chaquopy's `java` module (alongside the
already-used `jclass`) and wrapping both `is_pending` values:
`values.put("is_pending", jint(1))`. Chaquopy documents `jint`/`jboolean`/
`jbyte`/`jshort`/`jlong`/`jfloat`/`jdouble` specifically for this purpose —
disambiguating which overload a Python primitive should map to.

**Standing lesson, reinforced:** a "non-fatal, best-effort" check that
swallows its own exceptions can hide a completely broken code path
indefinitely — it takes an active, curious look (or, as here, tightening the
test until it actually has time to observe the real behavior) to find out
it's been silently no-op-ing the entire time. Don't assume "test passed,
non-fatal note printed" means "harmless" without reading what the note
actually says.

## 2026-07-01 — Phase 4 (signed release) + password hardening + a false-alarm MediaStore gap

Three things done together after Phase 3 went green, all under "make everything
ready" for real distribution:

**1. Hardcoded password removed.** `MainActivity.kt` had hardcoded
`PASSWORD = "classydl"` since Phase 1 (flagged as a TODO the whole time). Fixed
by branching on the generated `BuildConfig.DEBUG` flag: debug builds (what CI
and local `gradle installDebug` produce) keep the fixed password so existing
tests/scripts need no changes; release builds generate a random per-install
password via `SecureRandom`, persist it in `SharedPreferences`, and the app logs
itself in automatically (`WebView.evaluateJavascript` on `onPageFinished`,
filling `#login-password` and clicking `#login-btn`) so the end user never sees
or types it. `BuildConfig` had to be explicitly re-enabled via
`buildFeatures { buildConfig true }` — AGP 8 turns it off by default.

**2. Phase 4 release pipeline.** Generated a real signing keystore
(`keytool -genkeypair`, RSA 4096, PKCS12, 10000-day validity) and delivered it
directly to the user (never committed to the repo — it's a permanent secret;
losing it means all future updates need a new signature and users must
uninstall/reinstall). Added `.github/workflows/android-release.yml`, a
*separate* workflow from `android-build.yml` triggered on `push.tags:
v*.*.*` — deliberately not folded into the existing paths-filtered `push`
trigger, since combining `tags` and `paths` filters on one `push` block ANDs
them, which could silently skip a release whose tag commit doesn't happen to
touch `android/**`/`video_downloader/**`. The release job cross-compiles
ffmpeg for `arm64-v8a` only, builds via `gradle :app:assembleRelease
-PabiFilters=arm64-v8a` (a new Gradle property in `app/build.gradle` that
narrows `ndk.abiFilters` for just that invocation, leaving the debug/CI build
on both ABIs), signs using four secrets
(`ANDROID_KEYSTORE_BASE64`/`_PASSWORD`, `ANDROID_KEY_ALIAS`/`_PASSWORD`) that
still need to be added to the repo manually — nothing in the available
tooling can write GitHub Actions secrets programmatically. An explicit
"verify signing secrets are configured" step fails loudly if they're missing,
rather than silently shipping an unsigned/uninstallable APK.

**3. MediaStore "not found" was a race, not a bug.** CI run #15's Phase 3 test
reported the downloaded file wasn't in the MediaStore Downloads collection
(non-fatal check). Investigated by working out the timeline instead of
guessing: the check ran ~1.6s after job completion, and
`android_entry._run_downloads_publisher` only polled every 3s — the test could
easily have checked before the publisher's next cycle ran, for a completely
innocent reason. No exception was ever logged for the publish path. Fixed by
shrinking the poll interval to 1s (cheap — it's just a local sqlite query) and
making the CI check retry for up to 10s with a real logcat dump on a genuine
miss, so a *future* failure would actually mean something instead of being
another false alarm.

**Standing lesson:** before treating a non-fatal CI warning as "a bug to fix
in the publish/network logic," check whether it's explainable by timing/races
in the *test* first — reduces the chance of chasing a phantom bug in code
that was actually working.

## 2026-07-01 — CI download test's 403 was Wikimedia blocking the runner, not Android

After the in-process yt-dlp rewrite (below) shipped, `download_pipeline_test.sh`
still failed in CI — `HTTP Error 403: Forbidden` from
`https://upload.wikimedia.org/wikipedia/commons/c/c8/Example.ogg`, three retries,
all 403. First hypothesis was an SSL/CA-store gap (Android has no OpenSSL system
cert store at the paths Python's `ssl` module checks by default — a real, separate
issue, fixed by setting `SSL_CERT_FILE` to `certifi.where()` in
`android_entry.py`). That fix shipped and the *same* 403 still happened —
proof it was never a cert problem, since a `CERTIFICATE_VERIFY_FAILED` never
appeared in any log, only a clean HTTP 403 response.

Root cause: Wikimedia's upload servers apply anti-bot/datacenter-IP blocking that
GitHub Actions runner IPs run into — unrelated to Chaquopy, Android, or this app.
Nothing wrong with the download pipeline; the test's *choice of external URL* was
the flaky part.

**Fix:** stopped depending on any real internet host for this test. `.github/scripts/download_pipeline_test.sh`
now generates a tiny WAV file with Python's stdlib `wave` module, serves it via
`python3 -m http.server` bound to the runner's loopback, and uses `adb reverse` (not
`adb forward` — the request originates from the emulator/guest reaching back to the
host) so the app running inside the emulator can fetch it as an ordinary HTTP URL.
Verified locally first: spun up the same loopback server and confirmed yt-dlp's
generic extractor downloads it correctly before touching CI.

**Standing lesson:** don't let a CI test's correctness depend on a third-party
site's tolerance for automated/datacenter traffic. When a pipeline needs "a URL to
download," serve the fixture yourself (`adb reverse`/`adb forward` + a stdlib
`http.server`) instead of reaching for a real external host — it removes an entire
category of "looks like our bug but isn't" flakiness.

## 2026-07-01 — yt-dlp downloads were silently broken on Android from day one

Phase 3's new `download_pipeline_test.sh` was the first CI check to actually
exercise a real download (Phases 1–2 only checked `/api/health` and a
standalone `ffmpeg -version`) — and it failed, even though everything before
it had gone green. Root cause: `YtDlpStrategy.download` ran
`subprocess.run([sys.executable, "-m", "yt_dlp", ...])`. That's fine on a
normal OS but not under Chaquopy: Android's Python runs embedded as a library,
there's no standalone `python` binary at `sys.executable` for `subprocess` to
exec, and Chaquopy's own issue tracker documents exactly this failure mode
("Permission denied" from `subprocess.Popen`). So every yt-dlp download had
been silently broken on Android since Phase 1 — nothing had ever actually
tried one.

Fixed by rewriting `YtDlpStrategy` to call yt-dlp **in-process** via
`yt_dlp.YoutubeDL(opts).download(urls)` instead of subprocess — the officially
supported way to embed yt-dlp anyway, and a strict improvement on every
platform (Termux, desktop, Windows), not just an Android-specific workaround.
Verified the internal option dict keys (`outtmpl` as `{"default": path}`,
`cookiesfrombrowser` as a 4-tuple, `postprocessors` list shape, etc.) by
grepping the *installed* yt-dlp package's own `__init__.py` CLI-to-API mapping
rather than guessing from CLI flag names or training-data memory — cheap and
removed real risk of subtle wrong-key bugs. Confirmed working end-to-end
against a local `http.server` instance (this dev sandbox's outbound proxy
blocks arbitrary real hosts like Wikimedia, so a loopback server was the way
to get a genuine network-download test locally instead of only in CI).

**Standing lesson:** a green CI pipeline only proves what it actually
exercises. `/api/health` proves the server boots; `ffmpeg -version` proves
that one binary runs — neither proves the actual download path works. Add the
end-to-end check (Phase 3's real-download test) as early as possible, not
after several phases of "looks done" builds on assumptions.

## 2026-07-01 — Phase 2: ffmpeg for Android, done in two steps

**2a (pragmatic, immediate):** found that `DownloadRequest.ffmpeg_binary` was
never actually passed to the yt-dlp subprocess — only the separate FFmpeg
strategy checked it. Audio-only downloads always forced `-x --audio-format mp3`,
which hard-needs ffmpeg. Fixed `strategies.YtDlpStrategy` to check
`shutil.which(request.ffmpeg_binary)`: with ffmpeg, unchanged (now also passing
`--ffmpeg-location` explicitly); without it, selects `-f bestaudio` and skips
`-x`/`--audio-format`, saving the source's native audio container instead of
failing. Unblocked audio downloads on Android immediately, before any ffmpeg
binary existed at all.

**2b (real ffmpeg build):** rejected downloading a prebuilt third-party
ffmpeg-for-Android binary — no way to verify what's actually inside an unaudited
binary blob shipped in the app, that's a real supply-chain risk. Went with
cross-compiling from official upstream source (ffmpeg release/7.1 + libmp3lame
3.100) via the Android NDK's LLVM toolchain in a new CI job
(`build-ffmpeg`, matrix over arm64-v8a/x86_64), landing the result at
`app/src/main/jniLibs/<abi>/libffmpeg.so`. Despite explicitly warning it'd
likely need several slow iterations (ffmpeg cross-compilation has a well-earned
reputation for being finicky), **it went green on the very first CI attempt** —
both ABIs compiled in ~3 minutes each, and the emulator smoke test independently
pushed the x86_64 binary and ran `-version` on it directly (outside the app),
confirming the real `ffmpeg version ... libavutil/libavcodec/.../libswresample`
banner prints from inside Android, with `--enable-libmp3lame` present in its own
reported configuration — MP3 encoding is real, not just stream copy.

Wiring: `MainActivity.resolveFfmpegBinary()` → `android_entry.start(...,
ffmpeg_binary=...)` → `run_server(...)` → `ClassyDLServer.ffmpeg_binary` →
`store.add_job(ffmpeg_binary=...)`. `web/server.py`'s `create_server`/`run_server`
gained an `ffmpeg_binary` parameter to make this possible — previously there was
no way to tell the web/Android server "here's where ffmpeg lives" at all.

**Takeaway:** the "expect many slow iterations" caution from the Phase 1
memory entry doesn't universally apply — a well-researched first attempt
(current NDK toolchain conventions confirmed via search before writing the
script, conservative/non-aggressive configure flags to avoid silently breaking
unrelated functionality) can and did go green immediately even for a build this
complex. Don't skip the research step next time either.

## 2026-07-01 — "Sometimes downloads the wrong file" bug (shared output directory)

User reported via Termux that queuing a YouTube link with "Queue URL Directly"
sometimes produced the wrong downloaded file. Root cause found in
`strategies.YtDlpStrategy.download`: when yt-dlp's own `--print after_move:filepath`
output can't be confirmed (e.g. a delayed `Path.exists()` on Android's
`~/storage/*` shared-storage FUSE bridge, or two jobs' downloads overlapping in
time), it falls back to `_find_new_files` — "whichever file appeared in the output
directory since I started." All queued jobs previously wrote into one flat shared
directory (`queue_runner._build_request`), so that fallback could attribute an
unrelated job's file (or a leftover file from an earlier, different download) to
the wrong job. Fixed by giving each job its own subdirectory
(`output_dir/job-<id>/`) — the fallback can now only ever see that job's own
files, so misattribution across jobs is structurally impossible regardless of
what triggers the fallback path. Verified with two concurrent fake jobs writing
same-named files into a shared base dir — each still ends up in its own
`job-<id>/` folder untouched by the other.

## 2026-07-01 — Standalone Android app (Chaquopy), Phase 1 scaffold to green CI

**Goal:** after the Termux success, the user wanted something distributable to
*other* Android phones without Google Play — a real sideloadable APK. Full plan in
`docs/ANDROID_APP_PLAN.md`; chosen approach is Chaquopy (embeds CPython in a native
Android app) wrapping the same `video_downloader.web.server` used on Termux, shown
in a WebView. No Android SDK is available in this dev sandbox, so the plan was
scaffolded as real files and verified entirely through GitHub Actions CI + an
emulator smoke test (`reactivecircus/android-emulator-runner`, free on this public
repo). It took 5 push-and-check iterations to go green, each diagnosed from actual
CI logs:

1. **Missing `ndk.abiFilters`** — Chaquopy requires it set explicitly in
   `android.defaultConfig`; plain AGP's implicit "build all ABIs" default doesn't
   apply to it. Fixed by setting `arm64-v8a` (real phones) + `x86_64` (CI/desktop
   emulators).
2. **"Couldn't find Python 3.11"** — Chaquopy needs a Python interpreter on the
   *build* machine (distinct from the Android-target runtime it bundles) to run pip
   during packaging. CI's Ubuntu image doesn't have one pinned to 3.11 by default.
   Fixed by adding `actions/setup-python@v5` and pinning `buildPython "python3.11"`
   explicitly instead of relying on autodetection.
3. **Gradle implicit-dependency validation failure** on `:app:mergeDebugPythonSources`
   — the Chaquopy Python source set pointed at the repo root, which also contains
   `android/app/build/` (this very Gradle project's own output directory) as a
   nested subdirectory, so Gradle's newer task-validation flagged an unordered
   overlap with `:app:mergeDebugResources` and friends. Fixed by excluding
   `android/**` (and `tests/**`, `scripts/**`, etc.) from that source set.
4. **Emulator smoke test script syntax error** — `reactivecircus/android-emulator-runner`
   executes each line of its `script:` block as a *separate* shell invocation, so a
   multi-line `for ... do ... done` loop written inline in the workflow YAML breaks
   ("`Syntax error: end of file unexpected (expecting done)`"). Fixed by moving the
   retry loop into `.github/scripts/smoke_test.sh` and invoking it as a single line
   — and by adding a missing `actions/checkout` step to the emulator job, which
   needed the repo checked out to find that script.
5. **Green**: `/api/health` answered `{"status": "ok"}` from inside a freshly
   booted CI emulator with the just-built debug APK installed — confirming the
   embedded Python server genuinely starts and serves requests on-device, not just
   that the build compiles.

**Standing principle:** none of these were guessable from documentation alone —
Chaquopy's Gradle integration has several hard requirements (explicit abiFilters,
a separate build-time Python, source-set boundaries) that only surface as build
failures. Treat any future Android/Gradle change here as needing a real CI round-trip
before considering it done; don't assume Gradle config compiles just because it
looks syntactically right.

## 2026-07-01 — Gothic web UI, Termux deployment, two debugging rounds

**Goal:** let ClassyDL be driven from a phone via a browser, initially explored as a
hosted web app, then narrowed to "must run with no external server — entirely on the
phone itself" once the user clarified they didn't want to wait for hosting setup and
had already had a bad experience trying to package it as a native app.

**Decision — Termux, not a native app rewrite.** Android + Termux can run a real
Python/ffmpeg environment on-device, so the existing scraper/queue/download code could
be reused unchanged behind a small local web server, opened at `127.0.0.1` in the
phone's own browser. No APK build, no app store, no separate server host.

**Incident 1 — `pip install --upgrade pip` blocked by Termux.**
First version of `scripts/termux_setup.sh` ran `pip install --upgrade pip` before
installing the project. Termux ships a patched pip that refuses to self-upgrade
("Installing pip is forbidden, this will break the python-pip package (termux)"),
and printed the error and exited non-zero. Because the script had `set -e`, it
aborted right there — `pip install ".[web]"` never ran — but `termux_run.sh` was
tried anyway afterward and failed with `classydl: command not found`, since nothing
had actually been installed.
**Fix:** deleted the `pip install --upgrade pip` line entirely. Termux manages pip
version via `pkg`, not pip itself.

**Incident 2 — `pydantic-core` has no Termux/Android wheel.**
The web backend was originally FastAPI + uvicorn. FastAPI depends on Pydantic v2,
whose validation core (`pydantic-core`) is a Rust extension. PyPI has no prebuilt
wheel for Termux's platform tag, so pip fell back to building it from source, which
requires a Rust toolchain Termux doesn't ship by default, and even with one, compiling
a Rust crate on a phone CPU is slow — it hung visibly for 6+ minutes with no output
change ("Installing build dependencies ... -").
**Fix:** rewrote `video_downloader/web/server.py` from a FastAPI app to a pure
standard-library implementation (`http.server.ThreadingHTTPServer` + a custom
`BaseHTTPRequestHandler`). Same routes, same cookie-session auth, same static file
serving — just no compiled dependencies anywhere in the chain. Removed
`fastapi`/`uvicorn`/`pydantic`/`starlette`/`httpx` from `pyproject.toml` entirely.
Tests were rewritten to hit the server over real HTTP instead of using FastAPI's
`TestClient`.

**Outcome:** confirmed working end-to-end on the user's Android phone via Termux
after both fixes — `bash scripts/termux_setup.sh && bash scripts/termux_run.sh`,
then `http://127.0.0.1:8420` in Chrome.

**Standing principle for this repo:** don't add a dependency with compiled/Rust/C
extensions (especially anywhere reachable from `classydl web`) without checking it
has real Termux/Android wheel coverage — "runs on a phone with no server" is a load-
bearing requirement here, not a nice-to-have.

## 2026-07-01 — Why the web UI exists at all

User wanted to use the downloader "via phone or any device with internet access."
Explored a Gothic-themed hosted web app first (FastAPI backend + static frontend,
deployable via Docker/VPS/Cloudflare) — that version still exists as an option
(`Dockerfile`, `--host 0.0.0.0` binding) for whoever wants a shared/remote deployment
later. The user then pivoted to wanting zero external hosting, landing on the
Termux/on-device approach above as the immediate priority.
