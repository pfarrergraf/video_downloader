"""Small, Android-safe media discovery helpers.

The Android UI calls this module directly through Chaquopy. It deliberately
returns metadata only; downloads still go through the existing authenticated
/api/queue endpoint so licensing, quota, playlist and output rules remain in
one place.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from typing import Any

from yt_dlp import YoutubeDL

MAX_QUERY_CHARS = 200
MAX_RESULTS = 24
DEFAULT_RESULTS = 8
PAGE_SIZE = 8
SESSION_TTL_SECONDS = 10 * 60
MAX_SESSIONS = 12

_sessions: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_sessions_lock = threading.Lock()


def _clean_query(query: str) -> str:
    cleaned = " ".join((query or "").strip().split())
    if not cleaned:
        raise ValueError("Search query is empty")
    if len(cleaned) > MAX_QUERY_CHARS:
        raise ValueError(f"Search query is longer than {MAX_QUERY_CHARS} characters")
    return cleaned


def _result_from_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    video_id = str(entry.get("id") or "").strip()
    if not video_id:
        return None

    webpage_url = str(entry.get("webpage_url") or entry.get("url") or "").strip()
    if not webpage_url.startswith("http"):
        webpage_url = f"https://www.youtube.com/watch?v={video_id}"

    thumbnail = str(entry.get("thumbnail") or "").strip()
    if not thumbnail:
        thumbnails = entry.get("thumbnails") or []
        if thumbnails:
            thumbnail = str((thumbnails[-1] or {}).get("url") or "").strip()
    if not thumbnail:
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    duration = entry.get("duration")
    try:
        duration_seconds = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_seconds = None

    return {
        "id": video_id,
        "title": str(entry.get("title") or "Untitled"),
        "url": webpage_url,
        "thumbnail": thumbnail,
        "uploader": str(entry.get("uploader") or entry.get("channel") or ""),
        "duration": duration_seconds,
    }


def search_youtube(query: str, limit: int = DEFAULT_RESULTS) -> list[dict[str, Any]]:
    """Return a compact metadata-only YouTube search result list.

    This uses the yt-dlp build already bundled by the Android app. Keeping the
    search in-process is important on Chaquopy: there is no executable Python
    interpreter to shell out to on-device.
    """

    cleaned = _clean_query(query)
    bounded_limit = max(1, min(int(limit), MAX_RESULTS))
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": bounded_limit,
        "noplaylist": True,
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"ytsearch{bounded_limit}:{cleaned}", download=False) or {}

    results: list[dict[str, Any]] = []
    for raw_entry in info.get("entries") or []:
        if not isinstance(raw_entry, dict):
            continue
        result = _result_from_entry(raw_entry)
        if result is not None:
            results.append(result)
        if len(results) >= bounded_limit:
            break
    return results


def search_youtube_json(query: str, limit: int = DEFAULT_RESULTS) -> str:
    """Chaquopy-friendly JSON wrapper used by SearchActivity."""

    return json.dumps({"results": search_youtube(query, limit)}, ensure_ascii=False)


def _prune_sessions(now: float) -> None:
    expired = [token for token, (expires_at, _) in _sessions.items() if expires_at <= now]
    for token in expired:
        _sessions.pop(token, None)


def start_search_session_json(query: str) -> str:
    """Create a bounded metadata snapshot and return its first page.

    Cursors are opaque, process-local and deliberately short lived. A page is
    sliced from one immutable snapshot, so loading more never duplicates or
    reorders results when YouTube changes between requests.
    """

    results = search_youtube(query, MAX_RESULTS)
    token = secrets.token_urlsafe(18)
    now = time.monotonic()
    with _sessions_lock:
        _prune_sessions(now)
        if len(_sessions) >= MAX_SESSIONS:
            oldest = min(_sessions, key=lambda existing: _sessions[existing][0])
            _sessions.pop(oldest, None)
        _sessions[token] = (now + SESSION_TTL_SECONDS, results)
    return _page_json(token, 0, results)


def continue_search_session_json(cursor: str) -> str:
    try:
        token, raw_offset = (cursor or "").split(".", 1)
        offset = int(raw_offset)
    except (TypeError, ValueError):
        return json.dumps({"error": "restart_search", "results": []})
    now = time.monotonic()
    with _sessions_lock:
        _prune_sessions(now)
        session = _sessions.get(token)
        if session is None:
            return json.dumps({"error": "restart_search", "results": []})
        _, results = session
        _sessions[token] = (now + SESSION_TTL_SECONDS, results)
    if offset < 0 or offset > len(results):
        return json.dumps({"error": "restart_search", "results": []})
    return _page_json(token, offset, results)


def _page_json(token: str, offset: int, results: list[dict[str, Any]]) -> str:
    page = results[offset : offset + PAGE_SIZE]
    next_offset = offset + len(page)
    cursor = f"{token}.{next_offset}" if next_offset < len(results) else None
    return json.dumps(
        {"results": page, "next_cursor": cursor, "total": len(results)},
        ensure_ascii=False,
    )
