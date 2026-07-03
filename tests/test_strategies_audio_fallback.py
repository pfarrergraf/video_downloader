from __future__ import annotations

from pathlib import Path

from video_downloader.models import DownloadRequest
from video_downloader.strategies import YtDlpStrategy, _audio_format_selector, _video_format_selector


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


def _run_and_capture_opts(monkeypatch, tmp_path: Path, request: DownloadRequest) -> dict:
    captured: dict[str, dict] = {}

    class FakeYoutubeDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def download(self, urls):
            (tmp_path / "downloaded.file").write_bytes(b"data")

    monkeypatch.setattr("video_downloader.strategies.yt_dlp.YoutubeDL", FakeYoutubeDL)
    YtDlpStrategy().download(request, request.source_url)
    return captured["opts"]


def test_audio_format_selector_prefers_extraction_when_ffmpeg_available() -> None:
    assert _audio_format_selector(ffmpeg_available=True) == "ba/b"


def test_audio_format_selector_falls_back_to_audio_only_format() -> None:
    assert _audio_format_selector(ffmpeg_available=False) == "bestaudio"


def test_audio_only_without_ffmpeg_skips_extraction_flags(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: None)
    request = _make_request(tmp_path, audio_only=True, ffmpeg_binary="/no/such/ffmpeg")

    opts = _run_and_capture_opts(monkeypatch, tmp_path, request)

    assert "postprocessors" not in opts
    assert "ffmpeg_location" not in opts
    assert opts["format"] == "bestaudio"


def test_audio_only_with_ffmpeg_extracts_mp3(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: "/usr/bin/ffmpeg")
    request = _make_request(tmp_path, audio_only=True)

    opts = _run_and_capture_opts(monkeypatch, tmp_path, request)

    assert opts["postprocessors"] == [
        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}
    ]
    assert opts["ffmpeg_location"] == "ffmpeg"
    assert opts["format"] == "ba/b"


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

    assert opts["ffmpeg_location"] == "ffmpeg"
    assert opts["format"] == "bv*+ba/b"
