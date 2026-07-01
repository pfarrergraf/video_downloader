# Project Memory

A running log of decisions and incidents worth remembering, in case future work
(by Claude or a human) needs the "why," not just the "what." Newest entries on top.

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
