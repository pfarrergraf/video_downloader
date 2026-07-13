"""Tests for the site scraper module."""

from __future__ import annotations

import pytest

from video_downloader.scraper import (
    SiteScraper,
    ScrapedMedia,
    SsrfBlockedError,
    assert_public_url,
    classify_url,
    filter_items,
    format_size,
    parse_pick_spec,
    _filename_from_url,
    _is_same_domain,
    _path_ext,
)


# ── SSRF guard ────────────────────────────────────────────────────────────

class TestSsrfGuard:
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://localhost/",
            "http://169.254.169.254/latest/meta-data/",  # cloud metadata
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://172.16.0.1/",
            "http://[::1]/",
        ],
    )
    def test_blocks_private_and_loopback(self, url):
        with pytest.raises(SsrfBlockedError):
            assert_public_url(url)

    @pytest.mark.parametrize("url", ["file:///etc/passwd", "gopher://x/", "ftp://x/"])
    def test_blocks_non_http_schemes(self, url):
        with pytest.raises(SsrfBlockedError):
            assert_public_url(url)

    def test_blocks_missing_host(self):
        with pytest.raises(SsrfBlockedError):
            assert_public_url("http:///nohost")

    def test_scrape_of_loopback_raises(self):
        # Full path through scrape(): a loopback target is a hard error, not a
        # silent empty result.
        with pytest.raises(SsrfBlockedError):
            SiteScraper().scrape("http://127.0.0.1:1/")

    def test_allow_private_hosts_opt_in_skips_guard(self):
        # With the opt-in flag the guard is bypassed: the loopback fetch is
        # attempted and fails as an ordinary connection error, which scrape()
        # captures in result.errors rather than raising SsrfBlockedError.
        scraper = SiteScraper(allow_private_hosts=True, timeout=1)
        result = scraper.scrape("http://127.0.0.1:1/")
        assert result.items == []
        assert result.errors  # a connection failure was recorded, not an SSRF block
        assert not any("non-public" in e.lower() for e in result.errors)


# ── classify_url ────────────────────────────────────────────────────────

class TestClassifyUrl:
    def test_mp4(self):
        assert classify_url("https://example.com/video.mp4") == "video"

    def test_webm(self):
        assert classify_url("https://example.com/clip.webm") == "video"

    def test_mp3(self):
        assert classify_url("https://example.com/song.mp3") == "audio"

    def test_flac(self):
        assert classify_url("https://example.com/track.flac") == "audio"

    def test_jpg(self):
        assert classify_url("https://example.com/photo.jpg") == "image"

    def test_png(self):
        assert classify_url("https://example.com/icon.png") == "image"

    def test_webp(self):
        assert classify_url("https://example.com/pic.webp") == "image"

    def test_m3u8(self):
        assert classify_url("https://cdn.example.com/stream.m3u8") == "video"

    def test_unknown(self):
        assert classify_url("https://example.com/page.html") == "unknown"

    def test_query_string(self):
        assert classify_url("https://example.com/video.mp4?token=abc") == "video"

    def test_no_extension(self):
        assert classify_url("https://example.com/media") == "unknown"


# ── _path_ext ───────────────────────────────────────────────────────────

class TestPathExt:
    def test_simple(self):
        assert _path_ext("/video.mp4") == ".mp4"

    def test_with_query(self):
        assert _path_ext("/video.mp4?x=1") == ".mp4"

    def test_no_ext(self):
        assert _path_ext("/stream") == ""


# ── _filename_from_url ──────────────────────────────────────────────────

class TestFilenameFromUrl:
    def test_simple(self):
        assert _filename_from_url("https://example.com/photo.jpg") == "photo.jpg"

    def test_nested_path(self):
        assert _filename_from_url("https://example.com/a/b/clip.mp4") == "clip.mp4"

    def test_empty_path(self):
        assert _filename_from_url("https://example.com/") == "media"

    def test_encoded(self):
        assert _filename_from_url("https://example.com/my%20file.png") == "my file.png"


# ── _is_same_domain ────────────────────────────────────────────────────

class TestIsSameDomain:
    def test_exact_match(self):
        assert _is_same_domain("https://example.com/page", "https://example.com/img.jpg")

    def test_subdomain(self):
        assert _is_same_domain("https://example.com", "https://cdn.example.com/img.jpg")

    def test_different(self):
        assert not _is_same_domain("https://example.com", "https://other.com/img.jpg")


# ── filter_items ────────────────────────────────────────────────────────

class TestFilterItems:
    def _make(self, url: str, mtype: str, fname: str) -> ScrapedMedia:
        return ScrapedMedia(url=url, media_type=mtype, filename=fname)

    def test_by_type(self):
        items = [
            self._make("https://a.com/v.mp4", "video", "v.mp4"),
            self._make("https://a.com/s.mp3", "audio", "s.mp3"),
            self._make("https://a.com/p.png", "image", "p.png"),
        ]
        result = filter_items(items, media_types={"video"})
        assert len(result) == 1
        assert result[0].media_type == "video"

    def test_by_name_pattern(self):
        items = [
            self._make("https://a.com/thumb_1.jpg", "image", "thumb_1.jpg"),
            self._make("https://a.com/banner.jpg", "image", "banner.jpg"),
            self._make("https://a.com/thumb_2.jpg", "image", "thumb_2.jpg"),
        ]
        result = filter_items(items, name_pattern="*thumb*")
        assert len(result) == 2

    def test_combined(self):
        items = [
            self._make("https://a.com/thumb.jpg", "image", "thumb.jpg"),
            self._make("https://a.com/thumb.mp4", "video", "thumb.mp4"),
            self._make("https://a.com/banner.jpg", "image", "banner.jpg"),
        ]
        result = filter_items(items, media_types={"image"}, name_pattern="*thumb*")
        assert len(result) == 1
        assert result[0].filename == "thumb.jpg"


# ── parse_pick_spec ─────────────────────────────────────────────────────

class TestParsePickSpec:
    def test_all(self):
        assert parse_pick_spec("all", 5) == [0, 1, 2, 3, 4]

    def test_single(self):
        assert parse_pick_spec("3", 10) == [2]

    def test_csv(self):
        assert parse_pick_spec("1,3,5", 10) == [0, 2, 4]

    def test_range(self):
        assert parse_pick_spec("2-4", 10) == [1, 2, 3]

    def test_mixed(self):
        assert parse_pick_spec("1,3-5,8", 10) == [0, 2, 3, 4, 7]

    def test_out_of_range(self):
        assert parse_pick_spec("99", 5) == []

    def test_dedup(self):
        assert parse_pick_spec("1,1,2", 5) == [0, 1]


# ── format_size ─────────────────────────────────────────────────────────

class TestFormatSize:
    def test_none(self):
        assert format_size(None) == "?"

    def test_bytes(self):
        assert "B" in format_size(500)

    def test_megabytes(self):
        result = format_size(5 * 1024 * 1024)
        assert "MB" in result


# ── SiteScraper extraction (with mock HTML) ─────────────────────────────

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Gallery</title>
    <meta property="og:image" content="https://example.com/og-image.jpg">
    <meta property="og:video" content="https://example.com/og-video.mp4">
</head>
<body>
    <img src="/photos/cat.jpg">
    <img data-src="/photos/lazy-dog.png">
    <img srcset="/photos/small.webp 480w, /photos/large.webp 1024w">
    <video src="/media/intro.mp4" poster="/media/poster.jpg">
        <source src="/media/intro.webm">
    </video>
    <audio>
        <source src="/sounds/beep.mp3">
    </audio>
    <a href="/downloads/archive.zip">Not media</a>
    <a href="/downloads/song.flac">A song</a>
    <a href="/page2.html">Another page</a>
    <script>
        var streamUrl = "https://cdn.example.com/stream.m3u8?token=xyz";
    </script>
    <div style="background-image: url('https://example.com/bg.png')"></div>
</body>
</html>
"""


class TestSiteScraperExtraction:
    def _scraper(self) -> SiteScraper:
        return SiteScraper()

    def _extract(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        scraper = self._scraper()
        return scraper._extract_media(soup, "https://example.com/gallery")

    def test_finds_images(self):
        items = self._extract()
        images = [i for i in items if i.media_type == "image"]
        # cat.jpg, lazy-dog.png, small.webp, large.webp, poster.jpg, og-image.jpg, bg.png
        assert len(images) >= 5

    def test_finds_videos(self):
        items = self._extract()
        videos = [i for i in items if i.media_type == "video"]
        # intro.mp4, intro.webm, og-video.mp4, stream.m3u8
        assert len(videos) >= 3

    def test_finds_audio(self):
        items = self._extract()
        audio = [i for i in items if i.media_type == "audio"]
        # beep.mp3
        assert len(audio) >= 1

    def test_finds_linked_media(self):
        items = self._extract()
        urls = {i.url for i in items}
        assert any("song.flac" in u for u in urls)

    def test_no_non_media_links(self):
        items = self._extract()
        urls = {i.url for i in items}
        assert not any("archive.zip" in u for u in urls)

    def test_script_extraction(self):
        items = self._extract()
        urls = {i.url for i in items}
        assert any("stream.m3u8" in u for u in urls)

    def test_style_extraction(self):
        items = self._extract()
        urls = {i.url for i in items}
        assert any("bg.png" in u for u in urls)

    def test_og_meta(self):
        items = self._extract()
        urls = {i.url for i in items}
        assert "https://example.com/og-image.jpg" in urls
        assert "https://example.com/og-video.mp4" in urls

    def test_source_tags(self):
        items = self._extract()
        tags = {i.source_tag for i in items}
        assert "img" in tags
        assert "video" in tags or "video/source" in tags
        assert "audio/source" in tags


class TestSiteScraperScrapeWithFilter:
    """Test the full scrape pipeline with mocked HTTP."""

    def test_type_filter(self):
        from bs4 import BeautifulSoup
        scraper = SiteScraper()
        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        raw = scraper._extract_media(soup, "https://example.com")
        videos = filter_items(raw, media_types={"video"})
        images = filter_items(raw, media_types={"image"})
        assert all(i.media_type == "video" for i in videos)
        assert all(i.media_type == "image" for i in images)

    def test_name_filter(self):
        from bs4 import BeautifulSoup
        scraper = SiteScraper()
        soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
        raw = scraper._extract_media(soup, "https://example.com")
        cats = filter_items(raw, name_pattern="*cat*")
        assert len(cats) >= 1
        assert all("cat" in i.filename.lower() for i in cats)
