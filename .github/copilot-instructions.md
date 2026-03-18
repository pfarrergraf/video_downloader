# ClassyDL — Project Guidelines

## Project Overview

ClassyDL is a queue-driven video/audio/image downloader for Windows.  
Entry point: `classydl_entry.py` → `video_downloader.cli:main`.  
GUI: Tkinter-based Easy UI (`video_downloader/easy_ui.py`).  
Core engine: yt-dlp with fallback strategies (ffmpeg, direct HTTP).

## Tech Stack

- **Python 3.12** (>=3.10 in pyproject)
- **Package manager**: `uv` (not pip directly)
- **GUI**: Tkinter (`easy_ui.py`), Textual TUI (`tui_app.py`)
- **Downloads**: yt-dlp, requests, BeautifulSoup4
- **Packaging**: PyInstaller (spec file: `classydl.spec`)
- **Tests**: pytest under `tests/`

## Key Commands

```bash
uv sync --extra dev --extra build   # install all deps
uv run pytest tests/ -v             # run tests
uv run classydl ui                  # launch Easy UI
uv run classydl tui                 # launch TUI dashboard
uv run pyinstaller --clean --noconfirm classydl.spec  # build EXE
pwsh -File scripts/build_windows.ps1 -BundleAll       # full build with bundled ffmpeg
pwsh -File scripts/selfsign_local.ps1                 # create self-signed cert + sign EXE
pwsh -File scripts/resign.ps1                         # re-sign after rebuild
pwsh -File scripts/import_trust.ps1                   # trust cert on this machine
```

## Architecture

- `video_downloader/cli.py` — CLI entry, argparse, dispatches to commands
- `video_downloader/easy_ui.py` — Tkinter desktop UI with scraper integration
- `video_downloader/core.py` — DownloadManager orchestration
- `video_downloader/strategies.py` — download strategies (yt-dlp, ffmpeg, direct)
- `video_downloader/scraper.py` — site scraping, media discovery
- `video_downloader/queue_store.py` — SQLite job queue
- `video_downloader/queue_runner.py` — parallel worker runner
- `video_downloader/models.py` — dataclasses (DownloadRequest, DownloadProfile, etc.)
- `video_downloader/profiles.py` — profile CRUD
- `video_downloader/subscriptions.py` — subscription polling
- `video_downloader/history.py` — download history
- `video_downloader/app_config.py` — config loading, path resolution

## Conventions

- Threading only (no multiprocessing) — but `freeze_support()` is called in entry point for safety.
- All CLI subcommands are in `cli.py` as `_command_*` functions.
- Audio-only downloads use yt-dlp flags: `-x --audio-format mp3 --audio-quality 0` with format `ba/b`.
- The standalone EXE is **windowed** (`console=False` in spec). When launched without args it defaults to `ui` mode — never print to a non-existent console.
- Self-signed code-signing cert: `CN=ClassyDL Local Dev`, stored in `Cert:\CurrentUser\My` and trusted via `Cert:\CurrentUser\Root`.
- Bundled binaries (ffmpeg, aria2c) go into `bundled_bins/` before PyInstaller runs; the entry point prepends that to PATH.

## Build & Packaging (CRITICAL — read before touching)

See `.github/instructions/pyinstaller.instructions.md` for detailed packaging rules.
