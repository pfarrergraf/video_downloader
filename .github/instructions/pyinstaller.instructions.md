---
description: "Use when building, packaging, or debugging the standalone EXE, PyInstaller spec, bundling ffmpeg/aria2, code signing, or fixing issues with the dist/classydl.exe. Covers windowed-app pitfalls, self-signing, and bundled binaries."







































- ffmpeg is located via `shutil.which()` — must be on PATH (or bundled_bins).- Each strategy raises `StrategyError` on failure; `DownloadManager` tries the next.- `DirectStrategy` — plain HTTP download via requests.- `FFmpegStrategy` — fallback for direct stream URLs requiring ffmpeg.- `YtDlpStrategy` — primary; handles most URLs via yt-dlp subprocess.## Strategies (`strategies.py`)- Downloaded items appear in the log widget via `_log()` helper.- `_scan_site_links_worker` runs scraping in a background thread.- The UI must work when frozen (no console). Never use `print()` for user feedback.- Root window title: `"ClassyDL Easy UI"`.## Easy UI (`easy_ui.py`)- Always pass `same_domain=True` in UI to avoid cross-origin noise.- Selection parsing: `parse_pick_spec("1,3,5-8")` returns a list of 0-based indices.- Media classification: `classify_url()` maps extensions to `video`/`audio`/`image`.- `SiteScraper.scrape()` returns a `ScrapeResult` with `.items` and `.errors`.## Scraper (`scraper.py`)- Format selector: `ba/b` (best audio / fallback to best)- yt-dlp flags: `-x --audio-format mp3 --audio-quality 0`- Profile flag: `audio_only=True`## Audio-Only Downloads- Legacy mode (bare URL as first arg) is handled by `_should_use_legacy_mode`.- When `sys.frozen` is True and no args are given, default to `ui` — NEVER `print_help()`.- Every subcommand is a `_command_*` function dispatched from `_dispatch_command`.## CLI (`cli.py`)- UI updates from threads use `root.after()` (Tkinter) or message queues.- Long-running work (downloads, scraping) runs in daemon threads.- Use `threading.Thread` only — never `multiprocessing`.## Threading# ClassyDL — Python Source Conventions---applyTo: video_downloader/**/*.pyapplyTo: classydl.spec, classydl_entry.py, scripts/build_windows.ps1, scripts/selfsign_local.ps1, scripts/resign.ps1, scripts/import_trust.ps1
---

# PyInstaller & Standalone EXE — Packaging Rules

## CRITICAL LESSONS (learned the hard way)

### 1. Windowed EXE + no args = silent exit
The EXE is built with `console=False` (windowed). There is NO console.
If `main()` prints help text or errors to stdout/stderr, the user sees NOTHING.

**Rule**: `classydl_entry.py` and `cli.py` MUST default to launching the UI
(`argv = ["ui"]`) when `sys.argv[1:]` is empty AND `sys.frozen` is True.

**Rule**: `classydl_entry.py` wraps `main()` in try/except and shows a
`tkinter.messagebox.showerror()` crash dialog on unhandled exceptions when frozen.

### 2. Never print to console in windowed mode
Any `print()`, `console.print()`, or `sys.stdout.write()` will silently vanish.
For user-facing messages in the frozen app, use `tkinter.messagebox` or log to file.

### 3. Bundled binaries need PATH
`classydl_entry.py` prepends `sys._MEIPASS/bundled_bins` to `os.environ["PATH"]`
so that `shutil.which("ffmpeg")` finds the bundled copy.

### 4. UPX is disabled
UPX compression causes random crashes on some Windows systems. The spec has `upx=False`.
Do not re-enable without testing on multiple machines.

### 5. freeze_support() is required
Even though the app uses threading (not multiprocessing), `freeze_support()` is
called in the entry point because PyInstaller's runtime hooks expect it.

## Spec File (`classydl.spec`)

- Uses `collect_all()` for rich, textual, yt_dlp, video_downloader
- Uses `collect_submodules('yt_dlp')` for plugin-style imports
- `pathex` uses `os.path.abspath('.')` (absolute)
- `console=False` — windowed app, uses `runw.exe` bootloader
- `upx=False` — disabled for reliability
- If `bundled_bins/` directory exists at build time, all files in it are included

## Build Script (`scripts/build_windows.ps1`)

Parameters:
- `-BundleAll` — copy ffmpeg/aria2c from PATH into `bundled_bins/`
- `-FfmpegPath` / `-Aria2Path` — specify exact binary paths
- `-SignCert` / `-SignPassword` — sign with a PFX certificate
- `-Windowed` — (currently spec is always windowed)

Typical build command:
```powershell
pwsh -File scripts/build_windows.ps1 -BundleAll
```

## Signing Scripts

| Script | Purpose |
|--------|---------|
| `scripts/selfsign_local.ps1` | Create self-signed cert + sign EXE |
| `scripts/resign.ps1` | Re-sign after rebuild using existing cert |
| `scripts/import_trust.ps1` | Import cert into Trusted Root (this machine only) |

After rebuilding, always run `resign.ps1` to re-sign.

## Testing Before Build

Always run tests before building:
```bash
uv sync --extra dev --extra build
uv run pytest tests/ -v
```

## Common Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| EXE does nothing on double-click | No args → `print_help()` to no console | Ensure `cli.py` defaults to `ui` when frozen + no args |
| EXE crashes silently | Unhandled exception in windowed mode | Check crash dialog in `classydl_entry.py`; read log at `%LOCALAPPDATA%\ClassyDL\logs\` |
| ffmpeg not found at runtime | Bundled bins not on PATH | Verify `classydl_entry.py` prepends `_MEIPASS/bundled_bins` to PATH |
| SmartScreen blocks EXE | Unsigned or self-signed | Run `selfsign_local.ps1` then `import_trust.ps1` |
| Import errors at runtime | Missing hidden imports | Add to `collect_all()` or `hiddenimports` in spec |
| UPX-related crashes | UPX corrupting binaries | Keep `upx=False` in spec |
