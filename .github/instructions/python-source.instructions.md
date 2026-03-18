---
description: "Use when modifying the Easy UI (Tkinter GUI), site scraper, download strategies, or the CLI command dispatcher. Covers threading rules, audio-only mode, and scraper integration."
applyTo: video_downloader/**/*.py
---

# ClassyDL — Python Source Conventions

## Threading
- Use `threading.Thread` only — never `multiprocessing`.
- Long-running work (downloads, scraping) runs in daemon threads.
- UI updates from threads use `root.after()` (Tkinter) or message queues.

## CLI (`cli.py`)
- Every subcommand is a `_command_*` function dispatched from `_dispatch_command`.
- When `sys.frozen` is True and no args are given, default to `ui` — NEVER `print_help()`.
- Legacy mode (bare URL as first arg) is handled by `_should_use_legacy_mode`.

## Audio-Only Downloads
- Profile flag: `audio_only=True`
- yt-dlp flags: `-x --audio-format mp3 --audio-quality 0`
- Format selector: `ba/b` (best audio / fallback to best)

## Scraper (`scraper.py`)
- `SiteScraper.scrape()` returns a `ScrapeResult` with `.items` and `.errors`.
- Media classification: `classify_url()` maps extensions to `video`/`audio`/`image`.
- Selection parsing: `parse_pick_spec("1,3,5-8")` returns a list of 0-based indices.
- Always pass `same_domain=True` in UI to avoid cross-origin noise.

## Easy UI (`easy_ui.py`)
- Root window title: `"ClassyDL Easy UI"`.
- The UI must work when frozen (no console). Never use `print()` for user feedback.
- `_scan_site_links_worker` runs scraping in a background thread.
- Downloaded items appear in the log widget via `_log()` helper.

## Strategies (`strategies.py`)
- `YtDlpStrategy` — primary; handles most URLs via yt-dlp subprocess.
- `FFmpegStrategy` — fallback for direct stream URLs requiring ffmpeg.
- `DirectStrategy` — plain HTTP download via requests.
- Each strategy raises `StrategyError` on failure; `DownloadManager` tries the next.
- ffmpeg is located via `shutil.which()` — must be on PATH (or bundled_bins).
