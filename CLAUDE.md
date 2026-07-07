# CLAUDE.md

Guidance for Claude Code sessions working in this repo.

## Project

ClassyDL — a queue-driven video/audio/image downloader. Core logic (`scraper.py`,
`core.py`, `queue_runner.py`, `queue_store.py`) is used by three front ends: the CLI
(`cli.py`), the Textual TUI (`tui_app.py`), and the Tkinter desktop UI (`easy_ui.py`).

## Web UI (`video_downloader/web/`)

A browser-based "Gothic" UI was added so the tool can be driven from a phone or any
device with a browser. Important constraints baked into its design — don't undo these
without re-reading why:

- **`video_downloader/web/server.py` is standard-library only** (`http.server`,
  no FastAPI/uvicorn/pydantic/starlette). This was a deliberate rewrite, not the
  original design — see "Termux/Android" below for why. Do not reintroduce a web
  framework with compiled dependencies here without checking it installs cleanly on
  Termux first.
- Routes, session/auth model, and static file serving intentionally mirror what a
  small FastAPI app would look like (`/api/login`, `/api/queue`, `/api/scrape`,
  `/api/download/{job_id}/{filename}`, cookie-based sessions) — if re-adding a
  framework is ever justified, the route contract in `static/index.html`'s JS should
  keep working unchanged.
- Tests in `tests/test_web_server.py` hit the server over real HTTP
  (`http.client.HTTPConnection` against a `ClassyDLServer` bound to `port=0`), not a
  framework test client — keep that pattern for any new endpoints.
- `classydl web` requires a password (`--password` / `CLASSYDL_WEB_PASSWORD`); it
  refuses to start without one since it proxies arbitrary downloads.

## Termux / Android (no-server deployment)

One goal for the web UI is running entirely on-device on Android via Termux, with no
external server. Two real incidents shaped how the setup scripts work now
(`scripts/termux_setup.sh`, `scripts/termux_run.sh`) — see `memory.md` for details:

1. Termux's pip refuses `pip install --upgrade pip` by design (it's managed via
   `pkg`, not pip). Don't add that line back.
2. Termux/Android has no prebuilt (manylinux) wheels for most compiled/Rust
   extensions (e.g. `pydantic-core`, `uvloop`, `httptools`). Any dependency added to
   this project — especially under `video_downloader/web/` — should be pure Python,
   or Termux compatibility needs to be explicitly re-verified (compiling from source
   on a phone is slow and can hang for many minutes).

`CLASSYDL_DATA_DIR` (env var, read in `app_config.resolve_paths()`) overrides where
the config/state DB/logs live — needed because the original Windows-only path
resolution otherwise creates a literal `AppData/Roaming/...` folder under `$HOME` on
Linux/Termux, which works but is ugly. Set it explicitly in non-Windows deployments.

## Standalone Android app (`android/`)

A real sideloadable APK (no Play Store) is being built via Chaquopy — embeds CPython
in a native Android app, wrapping `video_downloader.web.server` unmodified behind a
WebView. Full plan and phase status: `docs/ANDROID_APP_PLAN.md`. Key things to know
before touching `android/`:

- There is no Android SDK in this dev sandbox — `android/` changes can only be
  verified via CI (`.github/workflows/android-build.yml`), which builds a debug APK
  and boots it in an emulator to smoke-test `/api/health`. Push, then check the
  Actions run; don't assume Gradle/Chaquopy config is correct just because it looks
  right — it took 5 iterations to get Phase 1 green, see `memory.md`.
- Chaquopy has several non-obvious hard requirements learned the hard way: explicit
  `ndk.abiFilters`, a separate build-time Python 3.11 (`buildPython` pinned, plus
  `actions/setup-python` in CI), and Python source-set directories that must not
  overlap with the Gradle project's own `build/` output (hence `exclude "android/**"`
  on a source set rooted at the repo root).
- `reactivecircus/android-emulator-runner`'s `script:` block runs each line as a
  separate shell invocation — no multi-line control flow (loops, if/fi) survives
  inline; put anything like that in a script file under `.github/scripts/` instead.
- **Never shell out to `sys.executable` (or spawn a new Python interpreter via
  `subprocess`) anywhere in code reachable from Android.** Chaquopy embeds
  Python as a library, not a standalone binary — `sys.executable` isn't
  something `subprocess` can exec there. This is why `YtDlpStrategy` calls
  `yt_dlp.YoutubeDL(...)` in-process instead of `python -m yt_dlp`; see
  `memory.md`. `/api/health` and `ffmpeg -version` passing does NOT mean
  downloads work — only `download_pipeline_test.sh`'s real download actually
  exercises this path, which is exactly how this bug was caught (three phases
  after it was introduced).

## Testing

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

`tests/test_cli_compat.py` and `tests/test_easy_ui.py` fail with
`ModuleNotFoundError: No module named 'tkinter'` in headless sandboxes without
Tkinter installed (this remote dev environment included) — that's a pre-existing
environment gap, not a regression. Ignore those two files when Tkinter isn't
available: `pytest tests/ --ignore=tests/test_cli_compat.py --ignore=tests/test_easy_ui.py`.

## Branch / workflow notes

Web UI work happened on `claude/gothic-downloader-website-bp7r2u`. The user tests
Android/Termux changes on their own phone and reports back errors as screenshots —
expect a debug loop of "push a fix → user pulls and reruns in Termux → reports the
next error" for anything touching `scripts/termux_*.sh` or `video_downloader/web/`.

## Android permission guardrail

**Do not add dangerous Android permissions to `android/app/src/main/AndroidManifest.xml` without explicit written approval from the repository owner.**

Currently approved permissions:
- `android.permission.INTERNET` — required for downloads
- `android.permission.FOREGROUND_SERVICE` — approved 2026-07-07; downloads must survive backgrounding (DownloadService)
- `android.permission.FOREGROUND_SERVICE_DATA_SYNC` — approved 2026-07-07; required for the dataSync service type on API 34+
- `android.permission.POST_NOTIFICATIONS` — approved 2026-07-07; progress/completion notifications, requested contextually on first download

See `docs/ANDROID_PERMISSIONS_2026-07-07.md` for the approval record and rationale.

Specifically prohibited without documented owner approval and a written reason:
- Any `READ_*` / `WRITE_*` permissions for contacts, SMS, call log, storage beyond what Chaquopy needs
- `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION`
- `CAMERA` / `RECORD_AUDIO`
- `REQUEST_INSTALL_PACKAGES`
- `SYSTEM_ALERT_WINDOW` (overlay)
- `BIND_ACCESSIBILITY_SERVICE`
- `DEVICE_ADMIN`

Also: preserve `android:allowBackup="false"` in the manifest unless explicitly instructed to change it, and document any change with a rationale.

These rules exist to keep the permission footprint minimal during beta distribution, where Google Play Protect warnings are already a known friction point. See `docs/ANDROID_BETA_DISTRIBUTION_AND_STRIPE_PLAN_2026-07-03.md` section 3.1.
