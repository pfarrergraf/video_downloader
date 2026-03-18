from __future__ import annotations

from pathlib import Path

from video_downloader.conversion import (
    build_ffmpeg_mp4_command,
    build_mp4_output_path,
    collect_convertible_files,
)


def test_collect_convertible_files_from_directory(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "clip.webm").write_bytes(b"video")
    (nested / "movie.mkv").write_bytes(b"video")
    (tmp_path / "already.mp4").write_bytes(b"video")

    top_level = collect_convertible_files([tmp_path], recursive=False)
    recursive = collect_convertible_files([tmp_path], recursive=True)

    assert [path.name for path in top_level] == ["clip.webm"]
    assert [path.name for path in recursive] == ["clip.webm", "movie.mkv"]


def test_build_mp4_output_path_uses_target_directory(tmp_path: Path) -> None:
    source = tmp_path / "clip.webm"
    source.write_bytes(b"video")
    output_dir = tmp_path / "converted"

    target = build_mp4_output_path(source, output_dir=output_dir)

    assert target == output_dir / "clip.mp4"
    assert output_dir.exists()


def test_build_ffmpeg_mp4_command_uses_quality_defaults(tmp_path: Path) -> None:
    source = tmp_path / "clip.webm"
    target = tmp_path / "clip.mp4"

    command = build_ffmpeg_mp4_command(source, target, overwrite=False)

    assert command[:5] == ["ffmpeg", "-n", "-hide_banner", "-loglevel", "error"]
    assert "-crf" in command
    assert "18" in command
    assert "libx264" in command
    assert "aac" in command
