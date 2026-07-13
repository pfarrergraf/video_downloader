"""Site scraper – discovers videos, audio files, and images on any web page."""

from __future__ import annotations

import fnmatch
import ipaddress
import mimetypes
import re
import socket
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup


class SsrfBlockedError(RuntimeError):
    """Raised when a scrape target resolves to a non-public / disallowed host."""


def _ip_is_blocked(ip: str) -> bool:
    """True for loopback/private/link-local/reserved/multicast addresses -
    i.e. anything that lets a scrape reach the host's own internal network or
    a cloud metadata endpoint (169.254.169.254) rather than the public web."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # unparseable -> refuse rather than guess
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def assert_public_url(url: str) -> None:
    """SSRF guard: allow only http(s) URLs whose host resolves entirely to
    public IPs. Raises SsrfBlockedError otherwise.

    This is deliberately strict (blocks every resolved address, so a name
    that maps to one public and one private IP is still refused). It does not
    defend against DNS rebinding between this check and the actual connect -
    that residual risk is accepted for this tool's threat model, where the
    server binds loopback in the real deployments (see server.py / cli.py)."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SsrfBlockedError(f"Blocked non-HTTP(S) URL scheme: {parsed.scheme or '(none)'}")
    host = parsed.hostname
    if not host:
        raise SsrfBlockedError("Blocked URL with no host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SsrfBlockedError(f"Could not resolve host '{host}': {exc}") from exc
    for info in infos:
        ip = info[4][0]
        if _ip_is_blocked(ip):
            raise SsrfBlockedError(
                f"Blocked request to non-public address {ip} (host '{host}')"
            )

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

MAX_ITEMS = 5000

# ── extension sets ──────────────────────────────────────────────────────

VIDEO_EXTENSIONS = {
    ".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi", ".wmv",
    ".flv", ".ts", ".vob", ".ogv", ".3gp", ".3g2",
}

AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus",
    ".wma", ".aiff", ".alac", ".mid", ".midi",
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp",
    ".ico", ".tiff", ".tif", ".avif", ".heic", ".heif",
}

MANIFEST_EXTENSIONS = {".m3u8", ".mpd"}

ALL_MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS | MANIFEST_EXTENSIONS

MediaType = str  # "video" | "audio" | "image" | "unknown"

Logger = Callable[[str], None]


@dataclass(slots=True)
class ScrapedMedia:
    """One discovered media resource."""

    url: str
    media_type: MediaType
    filename: str
    referer: str | None = None
    size_bytes: int | None = None
    source_tag: str = ""  # e.g. "img", "video", "audio", "a", "meta"


@dataclass(slots=True)
class ScrapeResult:
    """Full scrape output."""

    page_url: str
    page_title: str
    items: list[ScrapedMedia] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ── classification ──────────────────────────────────────────────────────

def classify_url(url: str) -> MediaType:
    """Classify a URL by its file extension or path hints."""
    path = urlparse(url).path.lower()
    ext = _path_ext(path)
    if ext in VIDEO_EXTENSIONS or ext in MANIFEST_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "unknown"


def _path_ext(path: str) -> str:
    """Extract extension from a URL path, ignoring query strings."""
    # Handle paths like /image.jpg?w=200
    bare = path.split("?")[0].split("#")[0]
    dot = bare.rfind(".")
    if dot == -1:
        return ""
    return bare[dot:].lower()


def _filename_from_url(url: str) -> str:
    """Best-effort filename from a URL."""
    path = urlparse(url).path
    name = unquote(path.rstrip("/").rsplit("/", 1)[-1])
    if not name or name == "/":
        return "media"
    # Trim excessively long names
    if len(name) > 200:
        name = name[:200]
    return name


# ── core scraper ────────────────────────────────────────────────────────

class SiteScraper:
    """Scrape a web page for all discoverable media assets."""

    # Cap manually-followed redirects (we follow them ourselves so each hop is
    # re-validated by the SSRF guard, which requests' own redirect handling
    # would bypass).
    MAX_REDIRECTS = 10

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 30,
        logger: Logger | None = None,
        allow_private_hosts: bool = False,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.logger = logger
        # Off by default: the web endpoint (/api/scrape) fetches attacker-
        # supplied URLs, so private/loopback targets must be refused. Power
        # users scraping their own LAN can opt in explicitly.
        self.allow_private_hosts = allow_private_hosts

    def scrape(
        self,
        url: str,
        *,
        same_domain: bool = False,
        media_types: set[MediaType] | None = None,
        name_filter: str | None = None,
        deep: bool = False,
        max_depth: int = 1,
    ) -> ScrapeResult:
        """
        Scrape *url* and return discovered media.

        Parameters
        ----------
        url : str
            Page to scrape.
        same_domain : bool
            Only keep media on the same domain.
        media_types : set | None
            Restrict to these types (``{"video", "audio", "image"}``).
            ``None`` means all.
        name_filter : str | None
            Wildcard pattern for filename matching (e.g. ``"*thumb*"``).
        deep : bool
            If True, follow internal page links up to *max_depth* levels.
        max_depth : int
            How many link-hops to follow when *deep* is True.
        """
        self._log(f"Scraping {url}")
        result = ScrapeResult(page_url=url, page_title="")

        try:
            html, final_url = self._fetch_html(url)
        except SsrfBlockedError:
            # Hard failure for the top-level target: let the caller (e.g. the
            # web /api/scrape handler) turn it into a clear 400, rather than a
            # silent empty result. Blocked *sub-pages* in deep mode stay soft
            # (handled in the deep loop below).
            raise
        except Exception as exc:
            result.errors.append(f"Failed to fetch page: {exc}")
            return result

        result.page_url = final_url
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        result.page_title = title_tag.get_text(strip=True) if title_tag else ""

        seen: set[str] = set()
        raw_items = self._extract_media(soup, final_url)

        if deep and max_depth > 0:
            sub_links = self._extract_page_links(soup, final_url, same_domain)
            for sub_url in sub_links[:50]:  # cap to avoid runaway crawling
                self._log(f"  Deep-scraping sub-page: {sub_url}")
                try:
                    sub_html, sub_final = self._fetch_html(sub_url)
                    sub_soup = BeautifulSoup(sub_html, "html.parser")
                    raw_items.extend(self._extract_media(sub_soup, sub_final))
                except Exception as exc:
                    result.errors.append(f"Sub-page {sub_url}: {exc}")

        # Deduplicate & filter
        for item in raw_items:
            canonical = _canonical(item.url)
            if canonical in seen:
                continue
            seen.add(canonical)

            if same_domain and not _is_same_domain(final_url, item.url):
                continue
            if media_types and item.media_type not in media_types:
                continue
            if name_filter and not fnmatch.fnmatch(item.filename.lower(), name_filter.lower()):
                continue

            result.items.append(item)
            if len(result.items) >= MAX_ITEMS:
                break

        self._log(f"Found {len(result.items)} media items on {result.page_url}")
        return result

    # ── extraction helpers ──────────────────────────────────────────────

    def _extract_media(self, soup: BeautifulSoup, base_url: str) -> list[ScrapedMedia]:
        items: list[ScrapedMedia] = []

        # <img> tags
        for tag in soup.find_all("img"):
            src = tag.get("src") or tag.get("data-src") or tag.get("data-lazy-src")
            if src:
                url = urljoin(base_url, src.strip())
                items.append(ScrapedMedia(
                    url=url,
                    media_type="image",
                    filename=_filename_from_url(url),
                    referer=base_url,
                    source_tag="img",
                ))
            # srcset
            srcset = tag.get("srcset")
            if srcset:
                for entry in self._parse_srcset(srcset, base_url):
                    items.append(ScrapedMedia(
                        url=entry,
                        media_type="image",
                        filename=_filename_from_url(entry),
                        referer=base_url,
                        source_tag="img/srcset",
                    ))

        # <picture><source> tags
        for tag in soup.find_all("picture"):
            for source in tag.find_all("source"):
                srcset = source.get("srcset")
                if srcset:
                    for entry in self._parse_srcset(srcset, base_url):
                        items.append(ScrapedMedia(
                            url=entry,
                            media_type="image",
                            filename=_filename_from_url(entry),
                            referer=base_url,
                            source_tag="picture/source",
                        ))

        # <video> and <audio> tags + nested <source>
        for tag_name, mtype in [("video", "video"), ("audio", "audio")]:
            for tag in soup.find_all(tag_name):
                src = tag.get("src")
                if src:
                    url = urljoin(base_url, src.strip())
                    items.append(ScrapedMedia(
                        url=url,
                        media_type=mtype,
                        filename=_filename_from_url(url),
                        referer=base_url,
                        source_tag=tag_name,
                    ))
                poster = tag.get("poster")
                if poster:
                    url = urljoin(base_url, poster.strip())
                    items.append(ScrapedMedia(
                        url=url,
                        media_type="image",
                        filename=_filename_from_url(url),
                        referer=base_url,
                        source_tag=f"{tag_name}/poster",
                    ))
                for source in tag.find_all("source"):
                    ssrc = source.get("src")
                    if ssrc:
                        url = urljoin(base_url, ssrc.strip())
                        items.append(ScrapedMedia(
                            url=url,
                            media_type=mtype,
                            filename=_filename_from_url(url),
                            referer=base_url,
                            source_tag=f"{tag_name}/source",
                        ))

        # <a> links pointing to media files
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            url = urljoin(base_url, href)
            mtype = classify_url(url)
            if mtype != "unknown":
                items.append(ScrapedMedia(
                    url=url,
                    media_type=mtype,
                    filename=_filename_from_url(url),
                    referer=base_url,
                    source_tag="a",
                ))

        # <link> stylesheet/icon/preload pointing to media
        for tag in soup.find_all("link", href=True):
            href = tag["href"].strip()
            url = urljoin(base_url, href)
            mtype = classify_url(url)
            if mtype != "unknown":
                items.append(ScrapedMedia(
                    url=url,
                    media_type=mtype,
                    filename=_filename_from_url(url),
                    referer=base_url,
                    source_tag="link",
                ))

        # OpenGraph / Twitter meta
        for meta in soup.find_all("meta"):
            prop = (meta.get("property") or meta.get("name") or "").lower()
            content = meta.get("content", "").strip()
            if not content:
                continue
            if prop in {"og:video", "og:video:url", "twitter:player:stream"}:
                url = urljoin(base_url, content)
                items.append(ScrapedMedia(
                    url=url, media_type="video",
                    filename=_filename_from_url(url),
                    referer=base_url, source_tag="meta",
                ))
            elif prop in {"og:image", "og:image:url", "twitter:image"}:
                url = urljoin(base_url, content)
                items.append(ScrapedMedia(
                    url=url, media_type="image",
                    filename=_filename_from_url(url),
                    referer=base_url, source_tag="meta",
                ))
            elif prop in {"og:audio", "og:audio:url"}:
                url = urljoin(base_url, content)
                items.append(ScrapedMedia(
                    url=url, media_type="audio",
                    filename=_filename_from_url(url),
                    referer=base_url, source_tag="meta",
                ))

        # Inline URLs in <script> blocks
        for script in soup.find_all("script"):
            text = script.string or script.get_text(" ", strip=True)
            if not text:
                continue
            for match in re.findall(
                r'https?://[^\s"\'<>\\]+?\.(?:mp4|webm|mkv|mov|mp3|m4a|aac|flac|wav|ogg|opus|jpg|jpeg|png|gif|webp|svg|avif|m3u8|mpd)(?:\?[^\s"\'<>\\]*)?',
                text,
                flags=re.IGNORECASE,
            ):
                url = match.strip()
                mtype = classify_url(url)
                items.append(ScrapedMedia(
                    url=url,
                    media_type=mtype if mtype != "unknown" else "video",
                    filename=_filename_from_url(url),
                    referer=base_url,
                    source_tag="script",
                ))

        # CSS background-image in inline styles
        for tag in soup.find_all(style=True):
            style = tag["style"]
            for match in re.findall(r'url\(["\']?(https?://[^"\')\s]+)["\']?\)', style, re.IGNORECASE):
                url = match.strip()
                mtype = classify_url(url)
                if mtype == "unknown":
                    mtype = "image"  # background images are typically images
                items.append(ScrapedMedia(
                    url=url,
                    media_type=mtype,
                    filename=_filename_from_url(url),
                    referer=base_url,
                    source_tag="style",
                ))

        return items

    def _extract_page_links(
        self, soup: BeautifulSoup, base_url: str, same_domain: bool
    ) -> list[str]:
        """Find internal page links for deep scraping."""
        links: list[str] = []
        seen: set[str] = set()
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            url = urljoin(base_url, href)
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                continue
            # skip anchors / media files
            if classify_url(url) != "unknown":
                continue
            canonical = parsed._replace(fragment="").geturl()
            if canonical in seen:
                continue
            seen.add(canonical)
            if same_domain and not _is_same_domain(base_url, url):
                continue
            links.append(canonical)
        return links

    def _parse_srcset(self, srcset: str, base_url: str) -> list[str]:
        """Parse HTML srcset attribute and return absolute URLs."""
        urls: list[str] = []
        for part in srcset.split(","):
            part = part.strip()
            if not part:
                continue
            tokens = part.split()
            if tokens:
                urls.append(urljoin(base_url, tokens[0]))
        return urls

    def _fetch_html(self, url: str) -> tuple[str, str]:
        """GET the page and return (html_text, final_url).

        Redirects are followed manually so the SSRF guard re-checks every hop
        (a public URL that 302s to http://169.254.169.254/ would otherwise
        sail straight through requests' built-in redirect follower)."""
        headers = {"User-Agent": self.user_agent}
        current = url
        for _ in range(self.MAX_REDIRECTS + 1):
            if not self.allow_private_hosts:
                assert_public_url(current)
            with requests.get(
                current,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
                stream=True,
            ) as resp:
                if resp.status_code in (301, 302, 303, 307, 308) and "location" in resp.headers:
                    current = urljoin(current, resp.headers["location"])
                    continue
                resp.raise_for_status()
                ct = resp.headers.get("Content-Type", "").lower()
                if "html" not in ct:
                    raise RuntimeError(f"Not an HTML page (Content-Type: {ct})")
                return resp.text, resp.url
        raise RuntimeError(f"Too many redirects (>{self.MAX_REDIRECTS})")

    def _log(self, msg: str) -> None:
        if self.logger:
            self.logger(msg)


# ── filtering helpers (used by CLI and UI) ──────────────────────────────

def filter_items(
    items: list[ScrapedMedia],
    *,
    media_types: set[MediaType] | None = None,
    name_pattern: str | None = None,
) -> list[ScrapedMedia]:
    """Post-filter already-scraped items by type and/or name glob."""
    out: list[ScrapedMedia] = []
    for item in items:
        if media_types and item.media_type not in media_types:
            continue
        if name_pattern and not fnmatch.fnmatch(item.filename.lower(), name_pattern.lower()):
            continue
        out.append(item)
    return out


def parse_pick_spec(spec: str, total: int) -> list[int]:
    """
    Parse a human-friendly pick spec like ``1,3,5-8`` into 0-based indices.

    Supports:
      - ``all`` → every index
      - ``1,3,5`` → specific 1-based positions
      - ``2-6`` → inclusive ranges
      - ``1,3-5,8`` → mixed
    """
    spec = spec.strip().lower()
    if spec == "all":
        return list(range(total))

    indices: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            lo_i = max(0, int(lo.strip()) - 1)
            hi_i = min(total - 1, int(hi.strip()) - 1)
            indices.extend(range(lo_i, hi_i + 1))
        else:
            idx = int(part) - 1
            if 0 <= idx < total:
                indices.append(idx)

    # Unique, sorted
    return sorted(set(indices))


def format_size(size_bytes: int | None) -> str:
    """Human-readable file size."""
    if size_bytes is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"


# ── private helpers ─────────────────────────────────────────────────────

def _canonical(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return url
    return parsed._replace(fragment="").geturl()


def _is_same_domain(base_url: str, candidate_url: str) -> bool:
    base_host = urlparse(base_url).netloc.lower()
    cand_host = urlparse(candidate_url).netloc.lower()
    if base_host == cand_host:
        return True
    if cand_host.endswith("." + base_host):
        return True
    if base_host.endswith("." + cand_host):
        return True
    return False
