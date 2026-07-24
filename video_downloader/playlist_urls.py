from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
    "www.youtu.be",
}


@dataclass(frozen=True, slots=True)
class PlaylistUrl:
    source: str
    normalized: str
    is_playlist: bool
    playlist_id: str | None = None
    is_dynamic: bool = False


def inspect_playlist_url(source: str) -> PlaylistUrl:
    """Recognize playlist intent and canonicalize stable YouTube playlists."""
    cleaned = unescape(source.strip())
    try:
        parsed = urlsplit(cleaned)
    except ValueError:
        return PlaylistUrl(cleaned, cleaned, False)

    host = (parsed.hostname or "").lower().rstrip(".")
    query = parse_qs(parsed.query, keep_blank_values=False)
    playlist_id = next((value.strip() for value in query.get("list", []) if value.strip()), None)

    if host in _YOUTUBE_HOSTS and playlist_id:
        dynamic = playlist_id.startswith("RD")
        if dynamic:
            # Mixes are seeded by the current video and can be unbounded. Keep
            # the original watch URL so yt-dlp receives that seed.
            normalized = urlunsplit((parsed.scheme or "https", parsed.netloc, parsed.path, parsed.query, ""))
        else:
            normalized = f"https://www.youtube.com/playlist?{urlencode({'list': playlist_id})}"
        return PlaylistUrl(cleaned, normalized, True, playlist_id, dynamic)

    path = parsed.path.rstrip("/").lower()
    if path.endswith("/sets") or "/sets/" in f"{path}/":
        return PlaylistUrl(cleaned, cleaned, True)

    return PlaylistUrl(cleaned, cleaned, False)


def is_playlist_url(source: str) -> bool:
    return inspect_playlist_url(source).is_playlist
