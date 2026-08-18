from __future__ import annotations

from pathlib import Path

import pytest

from video_downloader.models import DownloadRequest
from video_downloader.strategies import (
    YtDlpStrategy,
    StrategyError,
    _audio_format_selector,
    _available_js_runtimes,
    _video_format_selector,
)


def _make_request(
    tmp_path: Path, *, audio_only: bool, ffmpeg_binary: str = "ffmpeg", format_selector: str = "bv*+ba/b"
) -> DownloadRequest:
    return DownloadRequest(
        source_url="https://example.com/video",
        output_dir=tmp_path,
        audio_only=audio_only,
        ffmpeg_binary=ffmpeg_binary,
        format_selector=format_selector,
    )


def _run_and_capture_opts(
    monkeypatch, tmp_path: Path, request: DownloadRequest, *, downloaded_name: str = "downloaded.file"
) -> dict:
    captured: dict[str, dict] = {}

    class FakeYoutubeDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def download(self, urls):
            (tmp_path / downloaded_name).write_bytes(b"data")

    # strategies resolves yt_dlp through engine_update.get_yt_dlp (lazy, so
    # the engine self-update can swap it at runtime) - fake it at that seam.
    import types

    fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
    monkeypatch.setattr("video_downloader.strategies.engine_update.get_yt_dlp", lambda: fake_module)
    YtDlpStrategy().download(request, request.source_url)
    return captured["opts"]


def test_audio_format_selector_prefers_extraction_when_ffmpeg_available() -> None:
    assert _audio_format_selector(ffmpeg_available=True) == "ba/b"


def test_audio_format_selector_falls_back_to_audio_only_format() -> None:
    assert _audio_format_selector(ffmpeg_available=False) == "bestaudio"


def test_audio_only_without_ffmpeg_fails_clearly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: None)
    request = _make_request(tmp_path, audio_only=True, ffmpeg_binary="/no/such/ffmpeg")

    with pytest.raises(StrategyError, match="require FFmpeg"):
        YtDlpStrategy().download(request, request.source_url)


def test_audio_only_with_ffmpeg_extracts_mp3(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: "/usr/bin/ffmpeg")
    request = _make_request(tmp_path, audio_only=True)

    opts = _run_and_capture_opts(monkeypatch, tmp_path, request, downloaded_name="downloaded.mp3")

    assert opts["postprocessors"] == [
        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}
    ]
    # Must be the which()-resolved absolute path, not the bare command name:
    # yt-dlp treats a non-existent ffmpeg_location as "no ffmpeg" without
    # falling back to PATH.
    assert opts["ffmpeg_location"] == "/usr/bin/ffmpeg"


def test_audio_only_flags_when_mp3_conversion_silently_fails(tmp_path: Path, monkeypatch) -> None:
    # Never report an audio job as successful when yt-dlp leaves raw WebM/Opus.
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: "/usr/bin/ffmpeg")
    request = _make_request(tmp_path, audio_only=True)

    class FakeYoutubeDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def download(self, urls):
            (tmp_path / "downloaded.opus").write_bytes(b"data")

    import types

    fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
    monkeypatch.setattr("video_downloader.strategies.engine_update.get_yt_dlp", lambda: fake_module)
    with pytest.raises(StrategyError, match="MP3 conversion failed"):
        YtDlpStrategy().download(request, request.source_url)


def test_video_format_selector_keeps_configured_value_when_ffmpeg_available() -> None:
    assert _video_format_selector("bv*+ba/b", ffmpeg_available=True) == "bv*+ba/b"


def test_video_format_selector_falls_back_to_a_single_stream_without_ffmpeg() -> None:
    # Regression test: this selector requests separate video+audio streams
    # that need merging - without ffmpeg, yt-dlp aborted outright ("You have
    # requested merging of multiple formats but ffmpeg is not installed")
    # instead of falling back to a pre-muxed format the way audio already did.
    assert _video_format_selector("bv*+ba/b", ffmpeg_available=False) == "best"


def test_video_format_selector_leaves_a_no_merge_selector_untouched() -> None:
    # A selector with no "+" (e.g. a user-supplied single-format string)
    # never needed merging in the first place, so there's nothing to degrade.
    assert _video_format_selector("best", ffmpeg_available=False) == "best"


def test_video_format_selector_applies_quality_cap_with_ffmpeg() -> None:
    assert (
        _video_format_selector("bv*+ba/b", ffmpeg_available=True, quality_height=1080)
        == "bv*[height<=1080]+ba/b[height<=1080]/best"
    )


def test_video_format_selector_applies_quality_cap_without_ffmpeg() -> None:
    # No ffmpeg means the "+" alternative is unusable, but the cap should
    # still apply to whatever single pre-muxed stream is picked instead.
    assert (
        _video_format_selector("bv*+ba/b", ffmpeg_available=False, quality_height=720)
        == "best[height<=720]/best"
    )


def test_video_format_selector_ignores_cap_when_none() -> None:
    assert _video_format_selector("bv*+ba/b", ffmpeg_available=True, quality_height=None) == "bv*+ba/b"


def test_playlist_options_forward_explicit_max_items(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: None)
    request = _make_request(tmp_path, audio_only=False)
    request.allow_playlist = True
    request.max_items = 12

    opts = _run_and_capture_opts(monkeypatch, tmp_path, request)

    assert opts["noplaylist"] is False
    assert opts["ignoreerrors"] is True
    assert opts["max_downloads"] == 12
    assert "playlistend" not in opts


def test_playlist_partial_success_reports_skipped_entries(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: None)
    request = _make_request(tmp_path, audio_only=False)
    request.allow_playlist = True

    class FakeYoutubeDL:
        def __init__(self, opts):
            self.logger = opts["logger"]

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def download(self, urls):
            self.logger.error("Video unavailable")
            (tmp_path / "downloaded.webm").write_bytes(b"data")

    import types

    fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
    monkeypatch.setattr("video_downloader.strategies.engine_update.get_yt_dlp", lambda: fake_module)

    result = YtDlpStrategy().download(request, request.source_url)

    assert result.file_path.name == "downloaded.webm"
    assert "1 skipped item" in result.details
    assert "Video unavailable" in result.details


def test_available_js_runtimes_prefers_bundled_android_quickjs(
    monkeypatch, tmp_path: Path
) -> None:
    qjs = tmp_path / "libqjs.so"
    qjs.write_bytes(b"binary")
    monkeypatch.setenv("CLASSYDL_JS_RUNTIME", str(qjs))
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: None)

    assert _available_js_runtimes() == {"quickjs": {"path": str(qjs)}}


def test_youtube_fails_clearly_without_javascript_runtime(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CLASSYDL_JS_RUNTIME", raising=False)
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: None)
    request = _make_request(tmp_path, audio_only=False)
    request.source_url = "https://www.youtube.com/watch?v=abc"

    with pytest.raises(StrategyError, match="JavaScript runtime"):
        YtDlpStrategy().download(request, request.source_url)


def test_video_without_ffmpeg_falls_back_to_single_stream_format(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: None)
    request = _make_request(tmp_path, audio_only=False, ffmpeg_binary="/no/such/ffmpeg")

    opts = _run_and_capture_opts(monkeypatch, tmp_path, request)

    assert "ffmpeg_location" not in opts
    assert opts["format"] == "best"


def test_video_with_ffmpeg_keeps_the_configured_selector(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: "/usr/bin/ffmpeg")
    request = _make_request(tmp_path, audio_only=False)

    opts = _run_and_capture_opts(monkeypatch, tmp_path, request)

    assert opts["ffmpeg_location"] == "/usr/bin/ffmpeg"
    assert opts["format"] == "bv*+ba/b"
