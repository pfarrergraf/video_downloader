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
from typing import Any, Callable
from urllib.parse import urlencode

from yt_dlp import YoutubeDL

MAX_QUERY_CHARS = 200
MAX_RESULTS = 24
DEFAULT_RESULTS = 8
PAGE_SIZE = 8
SESSION_TTL_SECONDS = 10 * 60
MAX_SESSIONS = 12
SEARCH_SOCKET_TIMEOUT_SECONDS = 8
MAX_PLAYLIST_RESULTS = 3
# YouTube's own (undocumented) "Type: Playlist" search filter, passed as the
# `sp=` query param on a normal /results page. yt-dlp's `ytsearchN:` prefix
# used by search_youtube() below only ever returns videos - there is no
# equivalent pseudo-scheme for playlists, so this is the only way to ask for
# playlist results specifically.
PLAYLIST_SEARCH_TYPE_FILTER = "EgIQAw=="

_sessions: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_sessions_lock = threading.Lock()


class SearchCancelled(RuntimeError):
    pass


def _raise_if_cancelled(cancel_check: Callable[[], bool] | None) -> None:
    if cancel_check is not None and cancel_check():
        raise SearchCancelled("search_cancelled")


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
        "is_playlist": False,
    }


def _playlist_result_from_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    playlist_id = str(entry.get("id") or "").strip()
    if not playlist_id:
        return None

    url = str(entry.get("url") or "").strip()
    if not url.startswith("http"):
        url = f"https://www.youtube.com/playlist?{urlencode({'list': playlist_id})}"

    thumbnail = str(entry.get("thumbnail") or "").strip()
    if not thumbnail:
        thumbnails = entry.get("thumbnails") or []
        if thumbnails:
            thumbnail = str((thumbnails[-1] or {}).get("url") or "").strip()
    if not thumbnail:
        thumbnail = f"https://i.ytimg.com/vi/{playlist_id}/hqdefault.jpg"

    raw_count = entry.get("playlist_count")
    try:
        item_count = int(raw_count) if raw_count is not None else None
    except (TypeError, ValueError):
        item_count = None

    return {
        "id": playlist_id,
        "title": str(entry.get("title") or "Untitled playlist"),
        "url": url,
        "thumbnail": thumbnail,
        "uploader": str(entry.get("uploader") or entry.get("channel") or ""),
        "duration": None,
        "is_playlist": True,
        "item_count": item_count,
    }


def search_youtube(
    query: str,
    limit: int = DEFAULT_RESULTS,
    cancel_check: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """Return a compact metadata-only YouTube search result list.

    This uses the yt-dlp build already bundled by the Android app. Keeping the
    search in-process is important on Chaquopy: there is no executable Python
    interpreter to shell out to on-device.
    """

    cleaned = _clean_query(query)
    _raise_if_cancelled(cancel_check)
    bounded_limit = max(1, min(int(limit), MAX_RESULTS))
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": bounded_limit,
        "noplaylist": True,
        "socket_timeout": SEARCH_SOCKET_TIMEOUT_SECONDS,
        "retries": 0,
        "extractor_retries": 0,
        "fragment_retries": 0,
        "file_access_retries": 0,
        "match_filter": lambda *_args, **_kwargs: _raise_if_cancelled(cancel_check),
        "progress_hooks": [lambda _status: _raise_if_cancelled(cancel_check)],
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"ytsearch{bounded_limit}:{cleaned}", download=False) or {}

    _raise_if_cancelled(cancel_check)
    results: list[dict[str, Any]] = []
    for raw_entry in info.get("entries") or []:
        _raise_if_cancelled(cancel_check)
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


def search_youtube_playlists(
    query: str,
    limit: int = MAX_PLAYLIST_RESULTS,
    cancel_check: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """Best-effort playlist suggestions for a query.

    This depends on an unofficial YouTube search filter and a page layout
    yt-dlp only extracts in flat form, both more fragile than the plain video
    search above - callers must treat any failure here as "no playlists
    found", never as a reason to fail the whole search.
    """

    cleaned = _clean_query(query)
    _raise_if_cancelled(cancel_check)
    bounded_limit = max(1, min(int(limit), MAX_PLAYLIST_RESULTS))
    search_url = "https://www.youtube.com/results?" + urlencode(
        {"search_query": cleaned, "sp": PLAYLIST_SEARCH_TYPE_FILTER}
    )
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "playlistend": bounded_limit,
        "socket_timeout": SEARCH_SOCKET_TIMEOUT_SECONDS,
        "retries": 0,
        "extractor_retries": 0,
        "fragment_retries": 0,
        "file_access_retries": 0,
        "match_filter": lambda *_args, **_kwargs: _raise_if_cancelled(cancel_check),
        "progress_hooks": [lambda _status: _raise_if_cancelled(cancel_check)],
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(search_url, download=False) or {}

    _raise_if_cancelled(cancel_check)
    results: list[dict[str, Any]] = []
    for raw_entry in info.get("entries") or []:
        _raise_if_cancelled(cancel_check)
        if not isinstance(raw_entry, dict):
            continue
        result = _playlist_result_from_entry(raw_entry)
        if result is not None:
            results.append(result)
        if len(results) >= bounded_limit:
            break
    return results


def search_youtube_with_playlists(
    query: str,
    limit: int = MAX_RESULTS,
    cancel_check: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """Video results with up to MAX_PLAYLIST_RESULTS playlists surfaced first.

    Playlist discovery is best-effort (see search_youtube_playlists) - a
    failure there must never break ordinary video search, so it is caught
    here and simply treated as "no playlists this time".
    """

    try:
        playlists = search_youtube_playlists(query, cancel_check=cancel_check)
    except SearchCancelled:
        raise
    except Exception:
        playlists = []
    _raise_if_cancelled(cancel_check)
    videos = search_youtube(query, limit, cancel_check=cancel_check)
    playlist_ids = {playlist["id"] for playlist in playlists}
    videos = [video for video in videos if video["id"] not in playlist_ids]
    return playlists + videos


def _prune_sessions(now: float) -> None:
    expired = [token for token, (expires_at, _) in _sessions.items() if expires_at <= now]
    for token in expired:
        _sessions.pop(token, None)


def start_search_session_json(query: str, cancellation_signal=None) -> str:
    """Create a bounded metadata snapshot and return its first page.

    Cursors are opaque, process-local and deliberately short lived. A page is
    sliced from one immutable snapshot, so loading more never duplicates or
    reorders results when YouTube changes between requests.
    """

    def cancelled() -> bool:
        callback = getattr(cancellation_signal, "isCancelled", None)
        return bool(callback()) if callback is not None else False

    try:
        results = (
            search_youtube_with_playlists(query, MAX_RESULTS, cancel_check=cancelled)
            if cancellation_signal is not None
            else search_youtube_with_playlists(query, MAX_RESULTS)
        )
    except SearchCancelled:
        return json.dumps({"error": "search_cancelled", "results": []})
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
