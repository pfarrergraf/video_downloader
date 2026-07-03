from __future__ import annotations

from video_downloader.utils import extract_media_candidates


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
