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
