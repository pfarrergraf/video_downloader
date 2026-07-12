from __future__ import annotations

import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

MEDIA_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mkv",
    ".mov",
    ".m4v",
    ".avi",
    ".wmv",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".wav",
}

MANIFEST_HINTS = (".m3u8", ".mpd")

# Non-video/audio assets a site scrape can discover (images, documents) that a
# generic "download this URL" request should also be allowed to fetch directly.
ASSET_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp",
    ".ico", ".tiff", ".tif", ".avif", ".heic", ".heif",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".txt", ".csv", ".odt", ".ods",
}


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return cleaned or "video"


def is_manifest_url(url: str) -> bool:
    lower = url.lower()
    return any(hint in lower for hint in MANIFEST_HINTS)


def is_direct_media_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    return any(path.endswith(ext) for ext in MEDIA_EXTENSIONS)


def is_direct_asset_url(url: str) -> bool:
    """Like is_direct_media_url, but also accepts scraped non-media assets
    (images, documents) so a generic direct download can fetch them too."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    return any(path.endswith(ext) for ext in ASSET_EXTENSIONS)


def guess_extension(url: str, content_type: str | None, fallback: str = ".mp4") -> str:
    if content_type:
        content_type = content_type.lower()
        if "mp4" in content_type:
            return ".mp4"
        if "webm" in content_type:
            return ".webm"
        if "mpegurl" in content_type or "m3u8" in content_type:
            return ".mp4"
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return guessed
    ext = os.path.splitext(urlparse(url).path)[1]
    return ext if ext else fallback


def parse_content_disposition(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"filename\*=UTF-8''([^;]+)", value, flags=re.IGNORECASE)
    if match:
        return unquote(match.group(1).strip().strip("\"'"))
    match = re.search(r'filename="?([^";]+)"?', value, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_media_candidates(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    def add_candidate(candidate: str | None) -> None:
        if not candidate:
            return
        candidate = candidate.strip()
        if not candidate:
            return
        absolute = urljoin(base_url, candidate)
        if absolute.startswith("http://") or absolute.startswith("https://"):
            candidates.append(absolute)

    for meta in soup.find_all("meta"):
        key = (meta.get("property") or meta.get("name") or "").lower()
        if key in {"og:video", "og:video:url", "twitter:player:stream"}:
            add_candidate(meta.get("content"))

    for tag in soup.find_all(["video", "source"]):
        add_candidate(tag.get("src"))

    # Unlike <video>/<source>, an <a> tag's href is just as likely to be
    # ordinary page navigation (nav bar, footer, legal pages) as an actual
    # media link - only add it here if it structurally looks like media
    # (a direct file extension or a known manifest hint), otherwise callers
    # that blindly retry every discovered candidate through an extractor
    # (see core.DownloadManager._build_auto_queue) end up working through a
    # page's entire link soup before reaching the one real error.
    for tag in soup.find_all("a"):
        href = tag.get("href")
        if not href:
            continue
        absolute = urljoin(base_url, href.strip())
        if is_direct_media_url(absolute) or is_manifest_url(absolute):
            add_candidate(href)

    for script in soup.find_all("script"):
        text = script.string or script.get_text(" ", strip=True)
        if not text:
            continue
        for match in re.findall(
            r"https?://[^\s\"'<>\\]+(?:\.m3u8|\.mpd|\.mp4|\.webm|\.mkv|\.mov)(?:\?[^\s\"'<>\\]+)?",
            text,
            flags=re.IGNORECASE,
        ):
            add_candidate(match)

    # Preserve order while deduplicating.
    unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique
