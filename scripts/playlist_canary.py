#!/usr/bin/env python3
"""Non-destructive playlist extraction canary.

The canary deliberately asks yt-dlp for flat playlist metadata only. It must
never create media files; a failure means playlist discovery or the current
YouTube/EJS extraction path needs attention.
"""

from __future__ import annotations

import argparse
import os
import shutil
from collections.abc import Callable, Sequence

from video_downloader.playlist_urls import inspect_playlist_url

DEFAULT_URL = "https://www.youtube.com/watch?v=7N0Q_0R85jI&list=PLJU5GH-NqTMY"


def configured_urls(cli_urls: Sequence[str] = ()) -> list[str]:
    if cli_urls:
        return [url.strip() for url in cli_urls if url.strip()]
    env_urls = os.environ.get("CLASSYDL_CANARY_URLS", "")
    if env_urls.strip():
        return [url.strip() for url in env_urls.splitlines() if url.strip()]
    return [DEFAULT_URL]


def run_canary(
    urls: Sequence[str],
    *,
    playlist_end: int = 10,
    min_items: int = 1,
    ytdl_factory: Callable[..., object] | None = None,
) -> int:
    if playlist_end < 1 or min_items < 1:
        raise ValueError("playlist_end and min_items must be positive")

    if ytdl_factory is None:
        import yt_dlp

        ytdl_factory = yt_dlp.YoutubeDL

    node = shutil.which("node")
    if not node:
        raise RuntimeError("The playlist canary requires Node.js for yt-dlp EJS")

    options = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "skip_download": True,
        "simulate": True,
        "extract_flat": True,
        "playlistend": playlist_end,
        "js_runtimes": {"node": {"path": node}},
    }
    total = 0
    with ytdl_factory(options) as ydl:
        for source in urls:
            classified = inspect_playlist_url(source)
            if not classified.is_playlist:
                raise RuntimeError(f"Canary source is not recognized as a playlist: {source}")
            info = ydl.extract_info(classified.normalized, download=False) or {}
            entries = [entry for entry in (info.get("entries") or []) if entry]
            skipped = max(0, len(info.get("entries") or []) - len(entries))
            if len(entries) < min_items:
                raise RuntimeError(
                    f"Canary failed for {classified.normalized}: "
                    f"{len(entries)} playable item(s), minimum is {min_items}"
                )
            total += len(entries)
            title = info.get("title") or classified.playlist_id or classified.normalized
            print(f"PASS {title}: {len(entries)} item(s), {skipped} skipped")
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", action="append", dest="urls", help="Playlist URL; repeatable")
    parser.add_argument("--playlist-end", type=int, default=10)
    parser.add_argument("--min-items", type=int, default=1)
    args = parser.parse_args()
    urls = configured_urls(args.urls or ())
    total = run_canary(urls, playlist_end=args.playlist_end, min_items=args.min_items)
    print(f"Playlist canary passed: {total} playable item(s) checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
