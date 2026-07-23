# ClassyDL — Command Reference

## Development

```bash
uv sync --extra dev --extra build   # install all deps
uv run pytest tests/ -v             # run tests
uv run classydl ui                  # launch Easy UI (Tkinter)
uv run classydl tui                 # launch TUI dashboard (Textual)
```

## Downloads

```bash
# Single URL (yt-dlp auto mode)
uv run classydl download "https://www.youtube.com/watch?v=..."

# Full YouTube playlist (audio, numbered)
uv run yt-dlp "https://www.youtube.com/playlist?list=..." \
  -x --audio-format mp3 --audio-quality 0 \
  -o "downloads/<folder>/%(playlist_index)02d - %(title)s.%(ext)s"

# Spotify track → YouTube audio (via embed metadata)
uv run python scripts/spotify_via_youtube.py "https://open.spotify.com/track/<id>"

# Spotify full album/playlist → YouTube audio (via embed metadata)
uv run python scripts/spotify_via_youtube.py "https://open.spotify.com/album/<id>" \
  --output downloads/<album-folder>
```

### How the Spotify → YouTube fallback works

No Spotify API key or DRM bypass needed.

1. Fetches `open.spotify.com/embed/track/<id>` (no auth, no cookie wall) — returns `__NEXT_DATA__` JSON with clean title + artist list.
2. For albums/playlists: fetches `open.spotify.com/embed/album/<id>` — reads `entity.trackList` for all tracks in one request.
3. Builds a precise yt-dlp search query: `ytsearch1:"Title" PrimaryArtist` — quoted title + primary artist to avoid cover versions.
4. Downloads the best audio match from YouTube via yt-dlp `-x --audio-format mp3`.

Key functions in `video_downloader/strategies.py`:
- `_spotify_scrape_track(url)` — embed scrape → `{title, artist, year, album}`
- `_spotify_album_track_ids(url)` — embed trackList → list of track IDs
- `spotify_url_to_youtube_query(url)` — combines the above → `ytsearch1:` query string
- `SpotifyFallbackStrategy` — Strategy subclass wired into `DownloadManager`

Standalone script: `scripts/spotify_via_youtube.py`

## Build & Packaging

```bash
uv run pyinstaller --clean --noconfirm classydl.spec  # build EXE
pwsh -File scripts/build_windows.ps1 -BundleAll       # full build with bundled ffmpeg
pwsh -File scripts/selfsign_local.ps1                 # create self-signed cert + sign EXE
pwsh -File scripts/resign.ps1                         # re-sign after rebuild
pwsh -File scripts/import_trust.ps1                   # trust cert on this machine
```
