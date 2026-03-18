from __future__ import annotations

from pathlib import Path

from video_downloader.easy_ui import EasyUiApp


def test_convert_files_to_mp4_only_converts_supported_sources(monkeypatch, tmp_path: Path) -> None:
    app = EasyUiApp.__new__(EasyUiApp)
    logs: list[str] = []
    app._log_threadsafe = logs.append

    source = tmp_path / "clip.webm"
    source.write_bytes(b"video")
    already_mp4 = tmp_path / "clip.mp4"
    already_mp4.write_bytes(b"video")

    converted_targets: list[Path] = []

    def fake_convert(path: Path) -> Path:
        target = path.with_suffix(".mp4")
        converted_targets.append(target)
        return target

    monkeypatch.setattr("video_downloader.easy_ui.convert_file_to_mp4", fake_convert)

    converted, failures = app._convert_files_to_mp4([source, already_mp4])

    assert converted == 1
    assert failures == []
    assert converted_targets == [source.with_suffix(".mp4")]
    assert any("Converted to MP4" in message for message in logs)
