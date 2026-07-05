from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
import yt_dlp

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


class DownloadCancelled(RuntimeError):
    """Raised from within a download to unwind it immediately on user cancel.

    Deliberately NOT a StrategyError subclass: DownloadManager.download()'s
    auto-queue only catches StrategyError to fall through to the next
    strategy/URL candidate, and a cancellation must abort the whole job
    instead of triggering a pointless attempt with ffmpeg/direct-download.
    """


@dataclass(slots=True)
class Strategy:
    name: str

    def download(self, request: DownloadRequest, source_url: str) -> DownloadResult:
        raise NotImplementedError


class YtDlpStrategy(Strategy):
    """Runs yt-dlp in-process via its Python API.

    This used to shell out to `sys.executable -m yt_dlp`, which works on a
    normal OS but not under Chaquopy (Android): Python there is embedded as a
    library, not a standalone executable, so `sys.executable` isn't something
    that can be subprocess-spawned — every download failed with a permission/
    exec error. Calling yt-dlp as a library works identically everywhere.
    """

    def __init__(self) -> None:
        super().__init__(name="yt-dlp")

    def download(self, request: DownloadRequest, source_url: str) -> DownloadResult:
        ensure_output_dir(request.output_dir)
        before_files = _snapshot_files(request.output_dir)
        ffmpeg_available = shutil.which(request.ffmpeg_binary) is not None

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

        http_headers: dict[str, str] = {}
        if request.user_agent:
            http_headers["User-Agent"] = request.user_agent
        referer = _effective_referer(request, source_url)
        if referer:
            http_headers["Referer"] = referer
        http_headers.update(request.headers)

        postprocessors: list[dict[str, object]] = []
        if request.audio_only and ffmpeg_available:
            postprocessors.append(
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}
            )
        if request.embed_subs:
            postprocessors.append({"key": "FFmpegEmbedSubtitle"})

        ydl_opts: dict[str, object] = {
            "outtmpl": {"default": str(request.output_dir / template)},
            "format": (
                _audio_format_selector(ffmpeg_available)
                if request.audio_only
                else _video_format_selector(
                    request.format_selector, ffmpeg_available, request.quality_height
                )
            ),
            "noplaylist": not request.allow_playlist,
            "restrictfilenames": True,
            "continuedl": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "socket_timeout": request.timeout_seconds,
            "http_headers": http_headers,
        }
        if request.max_items is not None:
            ydl_opts["max_downloads"] = request.max_items
        if request.cookies_from_browser:
            ydl_opts["cookiesfrombrowser"] = (request.cookies_from_browser, None, None, None)
        if ffmpeg_available:
            ydl_opts["ffmpeg_location"] = request.ffmpeg_binary
        if request.subtitle_langs:
            ydl_opts["writesubtitles"] = True
            ydl_opts["subtitleslangs"] = request.subtitle_langs.split(",")
        if postprocessors:
            ydl_opts["postprocessors"] = postprocessors
        if request.external_downloader:
            ydl_opts["external_downloader"] = request.external_downloader
        if request.external_downloader_args:
            key = request.external_downloader or "default"
            ydl_opts["external_downloader_args"] = {key: [request.external_downloader_args]}
        if request.progress_callback or request.cancel_check:
            ydl_opts["progress_hooks"] = [
                _yt_dlp_progress_hook(request.progress_callback, request.cancel_check)
            ]

        error_message = ""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([source_url])
        except Exception as exc:  # yt_dlp raises DownloadError and friends
            # Re-check cancel_check directly rather than trusting the caught
            # exception's type/identity: yt-dlp may wrap whatever the progress
            # hook raised into its own DownloadError before it reaches here.
            # Asking the DB-backed cancel_check again is what actually tells
            # us this was a cancellation and not an unrelated network/
            # extractor failure that happened to land at the same time.
            if request.cancel_check and request.cancel_check():
                raise DownloadCancelled("Download cancelled") from exc
            error_message = str(exc)

        new_files = _find_new_files(request.output_dir, before_files)
        if new_files:
            result_file = new_files[-1]
            # yt-dlp downloads the raw source stream first, then runs
            # FFmpegExtractAudio as a separate step - if that postprocessing
            # step itself fails (e.g. the bundled ffmpeg binary can't encode
            # mp3 on this device), the exception above still leaves the raw,
            # un-converted file (e.g. .opus/.webm instead of the requested
            # .mp3) on disk. That file is still a real, playable download -
            # just not one every device/car stereo can open - so this stays a
            # success, but surfaces a clear note instead of pretending the
            # requested MP3 conversion actually happened.
            if (
                request.audio_only
                and ffmpeg_available
                and result_file.suffix.lower() != ".mp3"
                and not error_message
            ):
                error_message = (
                    f"MP3 conversion failed; saved as {result_file.suffix} instead. "
                    "This plays fine on this device but may not on others (e.g. a car stereo)."
                )
            return DownloadResult(
                file_path=result_file,
                method=self.name,
                source_url=source_url,
                details=error_message,
                downloaded_files=new_files,
            )

        raise StrategyError(error_message or "yt-dlp reported success but output file could not be located.")


def _yt_dlp_progress_hook(callback, cancel_check=None):
    # yt-dlp calls this many times per second; throttling avoids hammering
    # the queue store (SQLite) with a write on every chunk.
    last_call = [0.0]

    def hook(status: dict[str, object]) -> None:
        if status.get("status") != "downloading":
            return
        now = time.monotonic()
        if now - last_call[0] < 0.5:
            return
        last_call[0] = now
        # Checked on the same throttle as progress reporting - frequent
        # enough that a cancel request stops the transfer within ~0.5s
        # instead of only being noticed once the whole download finishes.
        if cancel_check and cancel_check():
            raise DownloadCancelled("Download cancelled")
        if callback:
            downloaded = int(status.get("downloaded_bytes") or 0)
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            callback(downloaded, int(total) if total else None)

    return hook


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

        content_length = response.headers.get("Content-Length")
        total_bytes = int(content_length) if content_length and content_length.isdigit() else None
        downloaded_bytes = 0
        last_report = time.monotonic()

        output = request.output_dir / filename
        try:
            with output.open("wb") as file_obj:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    file_obj.write(chunk)
                    downloaded_bytes += len(chunk)
                    if request.progress_callback and time.monotonic() - last_report >= 0.5:
                        last_report = time.monotonic()
                        request.progress_callback(downloaded_bytes, total_bytes)
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


def _audio_format_selector(ffmpeg_available: bool) -> str:
    if ffmpeg_available:
        return "ba/b"
    # Without ffmpeg, yt-dlp can't extract/remux audio out of a combined
    # stream or re-encode it — only ever pick a format that's already
    # audio-only, so the file it saves needs no further processing.
    return "bestaudio"


def _video_format_selector(
    configured_selector: str, ffmpeg_available: bool, quality_height: int | None = None
) -> str:
    if quality_height:
        # height<=N picks the best quality at or below the requested cap
        # (not "next higher available", which would silently blow past a
        # cap the user picked specifically to save bandwidth/storage).
        height_filter = f"[height<={int(quality_height)}]"
        selector = f"bv*{height_filter}+ba/b{height_filter}/best"
    else:
        selector = configured_selector
    if ffmpeg_available or "+" not in selector:
        return selector
    # The selector explicitly requests separate best-video and best-audio
    # streams merged together, which requires ffmpeg - yt-dlp aborts outright
    # ("merging of multiple formats but ffmpeg is not installed") rather than
    # silently downgrading. Falling back to a single pre-muxed stream mirrors
    # what _audio_format_selector already does for audio: every device can
    # still download *something* (typically capped below the split-stream-only
    # 1080p+ tiers on YouTube) instead of failing outright whenever ffmpeg
    # isn't resolvable. When a quality cap was requested, keep it applied to
    # the single-stream fallback too.
    if quality_height:
        return f"best[height<={int(quality_height)}]/best"
    return "best"


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


def _effective_referer(request: DownloadRequest, source_url: str) -> str | None:
    if request.referer:
        return request.referer
    if request.source_url.startswith("http://") or request.source_url.startswith("https://"):
        return request.source_url
    if source_url.startswith("http://") or source_url.startswith("https://"):
        return source_url
    return None
