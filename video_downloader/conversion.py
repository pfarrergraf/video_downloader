from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from .utils import ensure_output_dir

CONVERTIBLE_VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".webm", ".wmv"}


def collect_convertible_files(paths: Iterable[Path], recursive: bool = False) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for raw_path in paths:
        path = raw_path.expanduser().resolve()
        if path.is_dir():
            pattern = "**/*" if recursive else "*"
            for candidate in sorted(path.glob(pattern)):
                if not candidate.is_file():
                    continue
                if candidate.suffix.lower() not in CONVERTIBLE_VIDEO_EXTENSIONS:
                    continue
                resolved = candidate.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                files.append(resolved)
            continue
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file or directory: {path}")
        if path.suffix.lower() not in CONVERTIBLE_VIDEO_EXTENSIONS:
            raise ValueError(f"File is not a supported source format: {path}")
        if path not in seen:
            seen.add(path)
            files.append(path)
    return files


def build_mp4_output_path(source_path: Path, output_dir: Path | None = None) -> Path:
    base_dir = ensure_output_dir(output_dir.expanduser().resolve()) if output_dir else source_path.parent
    return base_dir / f"{source_path.stem}.mp4"


def build_ffmpeg_mp4_command(
    source_path: Path,
    target_path: Path,
    *,
    ffmpeg_binary: str = "ffmpeg",
    overwrite: bool = False,
) -> list[str]:
    return [
        ffmpeg_binary,
        "-y" if overwrite else "-n",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "320k",
        "-movflags",
        "+faststart",
        str(target_path),
    ]


def convert_file_to_mp4(
    source_path: Path,
    *,
    output_dir: Path | None = None,
    ffmpeg_binary: str = "ffmpeg",
    overwrite: bool = False,
    delete_source: bool = False,
) -> Path:
    source = source_path.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Source file does not exist: {source}")
    if source.suffix.lower() not in CONVERTIBLE_VIDEO_EXTENSIONS:
        raise ValueError(f"File is not a supported source format: {source}")
    if shutil.which(ffmpeg_binary) is None:
        raise RuntimeError(f"`{ffmpeg_binary}` is not available in PATH.")

    target = build_mp4_output_path(source, output_dir=output_dir)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Target file already exists: {target}")

    command = build_ffmpeg_mp4_command(
        source,
        target,
        ffmpeg_binary=ffmpeg_binary,
        overwrite=overwrite,
    )
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        message = _tail_lines(result.stderr, 15) or _tail_lines(result.stdout, 15) or "ffmpeg failed."
        raise RuntimeError(message)
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("ffmpeg exited successfully, but the MP4 file is missing or empty.")
    if delete_source:
        source.unlink()
    return target


def _tail_lines(text: str, count: int) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[-count:])
