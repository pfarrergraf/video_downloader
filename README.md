# ClassyDL

> Queue-driven video / audio / image downloader — CLI, TUI dashboard, desktop GUI, and a
> standalone Android app.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Proprietary](https://img.shields.io/badge/license-Proprietary-lightgrey.svg)](LICENSE)

## Get the app

**[Download DownloadThat for Android →](https://downloadthat.app/download/android)**
Available through Google Play, with a signed direct APK as a secondary option. No ads,
no git clone or Python installation needed. Free tier included;
Pro removes the daily download limit.

Everything below is developer documentation for building and running ClassyDL's engine
from source (Windows CLI/TUI/desktop GUI, Termux, Docker) — skip it if you just want the
app.

## Features

- **Site scraper** — discover videos, audio, and images on any web page
- **Selection** by type, wildcard name pattern, or manual pick
- **Universal extraction** via yt-dlp with fallback methods (ffmpeg, direct HTTP)
- **Audio-only mode** — extract MP3 at 320 kbps from any supported source
- **Queue + parallel workers** with retries and backoff
- **Smart profiles** (`default` plus custom presets)
- **Subscription polling** for channels / playlists
- **Windows Task Scheduler** integration for auto-runs
- **Textual TUI dashboard** (`classydl tui`)
- **Easy Desktop UI** with built-in scraper (`classydl ui`)
- **Portable EXE** — single-file windowed build via PyInstaller
- Backward-compatible legacy invocation (`classydl "<url>"`)

## Quick Start

```bash
# Clone & install
git clone https://github.com/<your-user>/classydl.git
cd classydl
uv venv
uv sync

# Launch the desktop UI
uv run classydl ui

# Or download a video from the CLI
uv run classydl download "https://example.com/video-page"
```

> **Requires** [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.10+.

## Install

```bash
uv venv
uv sync
```

For development and build tools:

```bash
uv sync --extra dev --extra build
```

## Usage

### Legacy (Still Supported)

```bash
uv run classydl "https://example.com/video-page"
uv run classydl --topic "charts" --topic "top music" --search-count 3
```

### Download

```bash
uv run classydl download "https://example.com/video-page"
uv run classydl download "https://example.com/video-page" --profile default
uv run classydl download --topic "charts" --topic "top music" --search-count 3
```

### Queue

```bash
uv run classydl queue add "https://example.com/video-page" --profile default
uv run classydl queue run --workers 3
uv run classydl queue list --status pending
uv run classydl queue cancel 42
uv run classydl queue pause 42
uv run classydl queue resume 42
uv run classydl queue reprioritize 42 --priority 10
```

### Profiles

```bash
uv run classydl profile create music --audio-only --format "ba/b" --use-aria2
uv run classydl profile list
uv run classydl profile show music
uv run classydl profile delete music
```

### Subscriptions

```bash
uv run classydl sub add "https://www.youtube.com/@channel/videos" --interval-minutes 60 --profile default
uv run classydl sub run
uv run classydl sub list
uv run classydl sub install-scheduler --interval-minutes 30
uv run classydl sub uninstall-scheduler
```

### History

```bash
uv run classydl history list
uv run classydl history list --status failed
uv run classydl history retry 42
```

### TUI Dashboard

```bash
uv run classydl tui
```

### Site Scraper

Scan a page you provide for discoverable video, audio, and image files – then pick what to download. Only use sources and content you are entitled to access and save.

```bash
# Scan a page and list all discovered media
uv run classydl scrape "https://example.com/gallery"

# Filter by type
uv run classydl scrape "https://example.com/page" --type video
uv run classydl scrape "https://example.com/page" --type audio --type image

# Filter by filename pattern (wildcard)
uv run classydl scrape "https://example.com/page" --filter "*thumbnail*"
uv run classydl scrape "https://example.com/page" --filter "*.mp4"

# Download everything found
uv run classydl scrape "https://example.com/page" --download all

# Download specific items by index (1-based)
uv run classydl scrape "https://example.com/page" --download "1,3,5-8"

# Combine type filter + download
uv run classydl scrape "https://example.com/page" --type video --download all

# Interactive mode: view results, filter, then pick
uv run classydl scrape "https://example.com/page" -i

# Deep scrape: follow links to sub-pages
uv run classydl scrape "https://example.com/page" --deep --same-domain

# Only same-domain media, brief output
uv run classydl scrape "https://example.com/page" --same-domain --brief
```

Interactive mode commands:

- Type a selection: `1,3,5-8` or `all`
- Filter by type: `type video`, `type audio`, `type image`
- Filter by name: `name *music*`
- Reset filters: `reset`
- Exit: `quit`

TUI keys:

- `q` quit
- `r` refresh
- `c` cancel selected job
- `p` pause selected pending job
- `u` resume selected paused job
- `y` retry selected failed/cancelled job
- `[` / `]` raise/lower priority for selected pending/paused job

## Web UI (Gothic, browser-based)

A dark, gothic-themed page that runs entirely in the browser — open it from a phone,
tablet, or any device with an internet connection, no app install required. The page
itself is a thin client; the actual scraping/downloading/ffmpeg work happens on
whatever machine runs `classydl web`. The backend is standard-library-only (no
FastAPI/pydantic), so it needs nothing beyond ClassyDL's normal install — this
matters on platforms without prebuilt wheels for compiled packages, like Termux.

```bash
uv sync
CLASSYDL_WEB_PASSWORD="pick-something-strong" uv run classydl web --port 8420
```

Then open `http://<that-machine's-address>:8420` in a browser. On a phone, use
"Add to Home Screen" from the browser menu to get an app-like icon — this avoids the
packaging problems of a native app while still feeling like one.

Options:

| Flag / env var | Purpose |
| ------ | --------- |
| `--password` / `CLASSYDL_WEB_PASSWORD` | Required. Single shared password gating the whole site. |
| `--host` | Bind address (default `0.0.0.0`) |
| `--port` | Bind port (default `8420`) |
| `--output` | Where finished downloads are written/served from |
| `--workers` | Concurrent download workers |
| `CLASSYDL_DATA_DIR` | Where the queue database/config/logs live (defaults to the platform-specific path; set this on Linux/Docker) |

**Reachability from "any device with internet access"** requires the server to be on
a network reachable from the internet — running it on your own PC alone only reaches
devices on the same LAN. Options, in increasing order of effort:

- **Your own PC + Tailscale/ngrok** — no hosting cost, gives a private URL reachable from your phone anywhere, without exposing the machine publicly.
- **A small VPS (DigitalOcean/Hetzner/etc.) or a PaaS (Render/Fly.io/Railway)** — run the bundled `Dockerfile`, get a public HTTPS URL.

```bash
docker build -t classydl .
docker run -p 8420:8420 -e CLASSYDL_WEB_PASSWORD=pick-something-strong -v classydl-data:/data classydl
```

⚠️ This proxies downloads from arbitrary URLs — always set a real password, and don't
expose it without one.

### Run it directly on an Android phone (no external server)

Termux lets the phone run its own Python + ffmpeg, so the whole stack — backend and
the Gothic page — lives on the device itself. Nothing is exposed to the internet;
you just open a browser on the same phone.

```bash
# Inside Termux, in this repo's directory:
bash scripts/termux_setup.sh   # one-time: installs python/ffmpeg, pip-installs ClassyDL
bash scripts/termux_run.sh     # starts the server, prompts for a password
```

Then open `http://127.0.0.1:8420` in Chrome/Firefox on the same phone. Downloads land
in `~/storage/downloads/ClassyDL`, visible from the normal Android Files app (requires
having granted storage access when `termux-setup-storage` prompted).

Notes:

- Keep Termux running (don't swipe it away) while a download is in progress; long-press
  its notification and choose "Acquire wakelock" so Android doesn't suspend it.
- Every dependency here is pure Python, so `pip install` should be quick — no Rust or
  C compiler needed.
- This mode binds to `127.0.0.1` only — it is not reachable from other devices, by
  design, since nothing here is meant to leave the phone.

## Easy Desktop UI

Launch a simpler click-first UI with built-in site scraping:

```bash
uv run classydl ui
python .\video_downloader\easy_ui.py
```

Optional defaults:

```bash
uv run classydl ui --output "D:\Media\Downloads" --method auto --cookies-from-browser chrome
```

Easy UI workflow:

- Paste clipboard directly into the link field
- Download one link immediately
- Optional one-click auto-convert of downloaded videos to MP4
- **Scan a provided page** for discoverable video, audio, and image files
- Filter results by type (video / audio / image) or text pattern
- Select `single`, `multiple`, or `all` discovered media
- One-click buttons: **All Videos**, **All Audio**, **All Images**
- Batch download selected items with one click
- Toggle **deep scrape** to follow links into sub-pages

If `uv run classydl ui` is interpreted as a URL, refresh scripts and run:

```bash
uv sync
uv run python -m video_downloader.cli ui
```

## Convert WEBM to MP4

If a download lands as `.webm` and you need an `.mp4`, convert it with the bundled ffmpeg helper:

```bash
uv run python .\scripts\convert_to_mp4.py .\downloads\video.webm
uv run python .\scripts\convert_to_mp4.py .\downloads --recursive
```

Useful options:

- `--output-dir .\downloads\mp4`
- `--overwrite`
- `--delete-source`

## Build Portable EXE (Windows)

Build a single-file windowed executable with bundled ffmpeg:

```bash
uv sync --extra build
pwsh -File scripts/build_windows.ps1 -BundleAll
```

This produces `dist\classydl.exe` — double-click to launch the GUI.

### Self-Sign for Local Use

Windows may block unsigned executables. To self-sign on this machine:

```powershell
# Create cert + sign EXE (first time)
pwsh -File scripts/selfsign_local.ps1

# Trust the cert on this machine
pwsh -File scripts/import_trust.ps1

# Re-sign after rebuilding
pwsh -File scripts/resign.ps1
```

### Build Options

| Flag | Effect |
| ------ | -------- |
| `-BundleAll` | Copy ffmpeg / aria2c from PATH into the bundle |
| `-FfmpegPath <path>` | Bundle a specific ffmpeg binary |
| `-Aria2Path <path>` | Bundle a specific aria2c binary |
| `-SignCert <path.pfx>` | Sign with a PFX certificate |
| `-SignPassword <pw>` | Password for the PFX |

## Runtime Paths (Windows)

| Path | Purpose |
| ------ | --------- |
| `%APPDATA%\ClassyDL\config.toml` | Configuration |
| `%LOCALAPPDATA%\ClassyDL\state.db` | Queue / state database |
| `%LOCALAPPDATA%\ClassyDL\logs\classydl.log` | Log file |

## Running Tests

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

## License

Proprietary — All rights reserved. See [LICENSE](LICENSE).

## Disclaimer

- This tool does not bypass DRM-protected platforms.
- Download only media you have rights or permission to access.
- `ffmpeg` must be installed and on PATH (or bundled via `-BundleAll`).
- `aria2c` is optional — used only when enabled in a profile and available.
