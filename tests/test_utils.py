from __future__ import annotations

from video_downloader.utils import (
    extract_media_candidates,
    guess_extension,
    is_direct_asset_url,
    is_direct_media_url,
)


def test_extract_media_candidates_ignores_ordinary_navigation_links() -> None:
    # Regression test: this used to capture every <a href> on the page,
    # so probing a failed YouTube video for "more candidates" rediscovered
    # the site's own nav links (About, Terms, channel tabs, ...) and the
    # caller (core.DownloadManager._build_auto_queue) blindly retried an
    # extractor against each one before reaching the real error.
    html = """
    <html><body>
      <nav>
        <a href="https://about.youtube/">About</a>
        <a href="/t/terms">Terms</a>
      </nav>
      <video src="https://cdn.example.com/clip.mp4"></video>
      <a href="https://cdn.example.com/other-clip.webm">Download</a>
      <a href="https://cdn.example.com/stream.m3u8">Watch</a>
    </body></html>
    """
    candidates = extract_media_candidates("https://youtube.com/watch?v=abc123", html)

    assert "https://about.youtube/" not in candidates
    assert "https://youtube.com/t/terms" not in candidates
    assert "https://cdn.example.com/clip.mp4" in candidates
    assert "https://cdn.example.com/other-clip.webm" in candidates
    assert "https://cdn.example.com/stream.m3u8" in candidates


def test_extract_media_candidates_still_finds_og_video_meta_tags() -> None:
    html = """
    <html><head>
      <meta property="og:video" content="https://cdn.example.com/embed.mp4" />
    </head><body></body></html>
    """
    candidates = extract_media_candidates("https://example.com/article", html)

    assert "https://cdn.example.com/embed.mp4" in candidates


def test_is_direct_media_url_excludes_images_and_documents() -> None:
    # is_direct_media_url stays video/audio-only: it also feeds the auto-mode
    # fallback queue for video/audio downloads, so widening it here would flood
    # that queue with unrelated image/document candidates.
    assert not is_direct_media_url("https://example.com/photo.jpg")
    assert not is_direct_media_url("https://example.com/report.pdf")
    assert is_direct_media_url("https://example.com/clip.mp4")


def test_is_direct_asset_url_includes_images_and_documents() -> None:
    assert is_direct_asset_url("https://example.com/photo.jpg")
    assert is_direct_asset_url("https://example.com/icon.svg")
    assert is_direct_asset_url("https://example.com/report.pdf")
    assert is_direct_asset_url("https://example.com/archive.zip")
    assert not is_direct_asset_url("https://example.com/page.html")


class TestGuessExtension:
    def test_defaults_to_mp4_fallback(self) -> None:
        assert guess_extension("https://example.com/media", None) == ".mp4"

    def test_custom_fallback(self) -> None:
        assert guess_extension("https://example.com/media", None, fallback=".bin") == ".bin"

    def test_url_extension_wins_without_content_type(self) -> None:
        assert guess_extension("https://example.com/report.pdf", None) == ".pdf"

    def test_content_type_guesses_pdf(self) -> None:
        assert guess_extension("https://example.com/download", "application/pdf") == ".pdf"

    def test_content_type_guesses_image(self) -> None:
        assert guess_extension("https://example.com/download", "image/png") == ".png"

    def test_mp4_content_type_still_wins(self) -> None:
        assert guess_extension("https://example.com/download", "video/mp4") == ".mp4"
