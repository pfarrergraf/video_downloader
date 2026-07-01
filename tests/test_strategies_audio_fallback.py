from __future__ import annotations

import subprocess
from pathlib import Path

from video_downloader.models import DownloadRequest
from video_downloader.strategies import YtDlpStrategy, _audio_format_selector


def _make_request(tmp_path: Path, *, audio_only: bool, ffmpeg_binary: str = "ffmpeg") -> DownloadRequest:
    return DownloadRequest(
        source_url="https://example.com/video",
        output_dir=tmp_path,
        audio_only=audio_only,
        ffmpeg_binary=ffmpeg_binary,
    )


def _run_and_capture_cmd(monkeypatch, tmp_path: Path, request: DownloadRequest) -> list[str]:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        output = tmp_path / "downloaded.file"
        output.write_bytes(b"data")
        return subprocess.CompletedProcess(cmd, 0, stdout=f"{output}\n", stderr="")

    monkeypatch.setattr("video_downloader.strategies.subprocess.run", fake_run)
    YtDlpStrategy().download(request, request.source_url)
    return captured["cmd"]


def test_audio_format_selector_prefers_extraction_when_ffmpeg_available() -> None:
    assert _audio_format_selector(ffmpeg_available=True) == "ba/b"


def test_audio_format_selector_falls_back_to_audio_only_format() -> None:
    assert _audio_format_selector(ffmpeg_available=False) == "bestaudio"


def test_audio_only_without_ffmpeg_skips_extraction_flags(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: None)
    request = _make_request(tmp_path, audio_only=True, ffmpeg_binary="/no/such/ffmpeg")

    cmd = _run_and_capture_cmd(monkeypatch, tmp_path, request)

    assert "-x" not in cmd
    assert "--audio-format" not in cmd
    assert "--ffmpeg-location" not in cmd
    assert "bestaudio" in cmd


def test_audio_only_with_ffmpeg_extracts_mp3(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("video_downloader.strategies.shutil.which", lambda name: "/usr/bin/ffmpeg")
    request = _make_request(tmp_path, audio_only=True)

    cmd = _run_and_capture_cmd(monkeypatch, tmp_path, request)

    assert "-x" in cmd
    assert "--audio-format" in cmd
    assert "--ffmpeg-location" in cmd
    assert "ba/b" in cmd
