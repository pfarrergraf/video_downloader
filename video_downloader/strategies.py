from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from .models import DownloadRequest, DownloadResult
from .utils import (
    ensure_output_dir,
    guess_extension,
    is_direct_media_url,
    is_manifest_url,
    parse_content_disposition,
    safe_filename,
)


class StrategyError(RuntimeError):
    pass


@dataclass(slots=True)
class Strategy:
    name: str

    def download(self, request: DownloadRequest, source_url: str) -> DownloadResult:
        raise NotImplementedError


class YtDlpStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__(name="yt-dlp")

    def download(self, request: DownloadRequest, source_url: str) -> DownloadResult:
        ensure_output_dir(request.output_dir)
        before_files = _snapshot_files(request.output_dir)

        if request.output_template:
            template = request.output_template
        elif request.filename and request.allow_playlist:
            template = f"{safe_filename(request.filename)}_%(playlist_index)s.%(ext)s"
        else:
            template = (
                f"{safe_filename(request.filename)}.%(ext)s"
                if request.filename
                else "%(title)s [%(id)s].%(ext)s"
            )

        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            source_url,
            "--newline",
            "--no-warnings",
            "--restrict-filenames",
            "-P",
            str(request.output_dir),
            "-o",
            template,
            "-f",
            "ba/b" if request.audio_only else request.format_selector,
            "--print",
            "after_move:filepath",
            "--continue",
        ]
        if request.allow_playlist:
            cmd.append("--yes-playlist")
        else:
            cmd.append("--no-playlist")
        if request.max_items is not None:
            cmd.extend(["--max-downloads", str(request.max_items)])

        if request.user_agent:
            cmd.extend(["--user-agent", request.user_agent])
        referer = _effective_referer(request, source_url)
        if referer:
            cmd.extend(["--referer", referer])
        for key, value in request.headers.items():
            cmd.extend(["--add-header", f"{key}: {value}"])
        if request.cookies_from_browser:
            cmd.extend(["--cookies-from-browser", request.cookies_from_browser])
        if request.audio_only:
            cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0"])
        if request.subtitle_langs:
            cmd.extend(["--write-subs", "--sub-langs", request.subtitle_langs])
        if request.embed_subs:
            cmd.append("--embed-subs")
        if request.external_downloader:
            cmd.extend(["--downloader", request.external_downloader])
        if request.external_downloader_args:
            if request.external_downloader:
                cmd.extend(
                    [
                        "--downloader-args",
                        f"{request.external_downloader}:{request.external_downloader_args}",
                    ]
                )
            else:
                cmd.extend(["--downloader-args", request.external_downloader_args])

        run = subprocess.run(cmd, capture_output=True, text=True)
        printed_files: list[Path] = []
        for line in run.stdout.splitlines():
            candidate = Path(line.strip())
            if candidate.exists() and candidate.is_file():
                printed_files.append(candidate)

        if printed_files:
            details = _yt_dlp_non_zero_details(run)
            return DownloadResult(
                file_path=printed_files[-1],
                method=self.name,
                source_url=source_url,
                details=details,
                downloaded_files=printed_files,
            )

        new_files = _find_new_files(request.output_dir, before_files)
        if new_files:
            details = _yt_dlp_non_zero_details(run)
            return DownloadResult(
                file_path=new_files[-1],
                method=self.name,
                source_url=source_url,
                details=details,
                downloaded_files=new_files,
            )

        if run.returncode != 0:
            failure = _tail_lines(run.stderr, 15) or _tail_lines(run.stdout, 15) or "yt-dlp failed."
            raise StrategyError(failure)
        raise StrategyError("yt-dlp reported success but output file could not be located.")


class FFmpegStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__(name="ffmpeg")

    def download(self, request: DownloadRequest, source_url: str) -> DownloadResult:
        ensure_output_dir(request.output_dir)
        if shutil.which(request.ffmpeg_binary) is None:
            raise StrategyError(f"`{request.ffmpeg_binary}` is not available in PATH.")

        stem = safe_filename(request.filename) if request.filename else f"video_{int(time.time())}"
        output = request.output_dir / f"{stem}.mp4"

        cmd = [request.ffmpeg_binary, "-y", "-hide_banner", "-loglevel", "error"]

        header_lines: list[str] = []
        if request.user_agent:
            header_lines.append(f"User-Agent: {request.user_agent}")
        referer = _effective_referer(request, source_url)
        if referer:
            header_lines.append(f"Referer: {referer}")
        for key, value in request.headers.items():
            header_lines.append(f"{key}: {value}")
        if header_lines:
            cmd.extend(["-headers", "\r\n".join(header_lines) + "\r\n"])

        if is_manifest_url(source_url):
            cmd.extend(["-protocol_whitelist", "file,http,https,tcp,tls,crypto"])

        cmd.extend(["-i", source_url, "-c", "copy", "-movflags", "+faststart", str(output)])

        run = subprocess.run(cmd, capture_output=True, text=True)
        if run.returncode != 0:
            stderr_tail = _tail_lines(run.stderr, 15)
            raise StrategyError(stderr_tail or "ffmpeg failed.")

        if not output.exists() or output.stat().st_size == 0:
            raise StrategyError("ffmpeg exited successfully, but output file is missing or empty.")
        return DownloadResult(
            file_path=output,
            method=self.name,
            source_url=source_url,
            downloaded_files=[output],
        )


class DirectDownloadStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__(name="direct")

    def download(self, request: DownloadRequest, source_url: str) -> DownloadResult:
        ensure_output_dir(request.output_dir)
        headers = _request_headers(request, source_url)

        try:
            response = requests.get(
                source_url,
                headers=headers,
                timeout=request.timeout_seconds,
                stream=True,
                allow_redirects=True,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise StrategyError(f"HTTP download failed: {exc}") from exc

        content_type = response.headers.get("Content-Type")
        if not _response_looks_like_media(response.url, content_type):
            raise StrategyError(
                f"Direct URL is not a media response (Content-Type: {content_type or 'unknown'})."
            )

        extension = guess_extension(source_url, content_type)
        if extension.startswith(".m3u"):
            extension = ".mp4"

        if request.filename:
            filename = safe_filename(request.filename) + extension
        else:
            parsed_name = parse_content_disposition(response.headers.get("Content-Disposition"))
            if parsed_name:
                filename = _ensure_extension(safe_filename(parsed_name), extension)
            else:
                path_name = Path(urlparse(response.url).path).name
                if path_name:
                    filename = _ensure_extension(safe_filename(path_name), extension)
                else:
                    filename = f"video_{int(time.time())}{extension}"

        output = request.output_dir / filename
        try:
            with output.open("wb") as file_obj:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file_obj.write(chunk)
        finally:
            response.close()

        if not output.exists() or output.stat().st_size == 0:
            raise StrategyError("Direct download produced an empty file.")
        return DownloadResult(
            file_path=output,
            method=self.name,
            source_url=source_url,
            downloaded_files=[output],
        )


def _tail_lines(text: str, count: int) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[-count:])


def _snapshot_files(directory: Path) -> set[Path]:
    return {p.resolve() for p in directory.iterdir() if p.is_file()}


def _find_new_files(directory: Path, before: set[Path]) -> list[Path]:
    new_files: list[Path] = []
    for file_path in directory.iterdir():
        if not file_path.is_file():
            continue
        resolved = file_path.resolve()
        if resolved not in before:
            new_files.append(file_path)
    new_files.sort(key=lambda p: p.stat().st_mtime)
    return new_files


def _request_headers(request: DownloadRequest, source_url: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    if request.user_agent:
        headers["User-Agent"] = request.user_agent
    referer = _effective_referer(request, source_url)
    if referer:
        headers["Referer"] = referer
    headers.update(request.headers)
    return headers


def _ensure_extension(filename: str, extension: str) -> str:
    return filename if Path(filename).suffix else f"{filename}{extension}"


def _response_looks_like_media(url: str, content_type: str | None) -> bool:
    if is_direct_media_url(url):
        return True
    if not content_type:
        return False
    lower = content_type.lower()
    if lower.startswith("video/") or lower.startswith("audio/"):
        return True
    allow_markers = ("octet-stream", "application/mp4", "mpegurl", "dash+xml")
    return any(marker in lower for marker in allow_markers)


def _yt_dlp_non_zero_details(run: subprocess.CompletedProcess[str]) -> str:
    if run.returncode == 0:
        return ""
    message = _tail_lines(run.stderr, 10) or _tail_lines(run.stdout, 10)
    if not message:
        message = f"yt-dlp exited with code {run.returncode} after partial success."
    return f"Partial success with non-zero yt-dlp exit: {message}"


def _effective_referer(request: DownloadRequest, source_url: str) -> str | None:
    if request.referer:
        return request.referer
    if request.source_url.startswith("http://") or request.source_url.startswith("https://"):
        return request.source_url
    if source_url.startswith("http://") or source_url.startswith("https://"):
        return source_url
    return None
