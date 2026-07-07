from __future__ import annotations

import hashlib
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import engine_update
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


class DownloadStalled(StrategyError):
    """A transfer stopped making progress and was aborted.

    IS a StrategyError on purpose: a stall on one strategy/candidate should
    fall through to the next one (and the queue's retry policy treats
    'stalled' as retryable), unlike a user cancellation.
    """


# No byte progress for this long -> abort the attempt instead of hanging
# forever. Generous on purpose: mobile networks legitimately pause for tens
# of seconds in tunnels/elevators.
STALL_SECONDS = 120.0
# Hard wall-clock ceiling per attempt - nothing a phone user wants runs longer.
MAX_ATTEMPT_SECONDS = 2 * 3600.0
# ffmpeg writes output continuously; a minute and a half of no growth means
# the stream is dead (its own network timeouts often never fire on HLS).
FFMPEG_STALL_SECONDS = 90.0


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
            # Parallel fragment fetches for HLS/DASH - the single biggest
            # speed lever for segmented streams (YouTube throttles per
            # connection). Ignored for plain progressive downloads.
            "concurrent_fragment_downloads": max(1, int(request.concurrent_fragments or 1)),
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
            # Resolved through engine_update (never a module-top import) so a
            # runtime engine self-update is observed by the very next
            # download; engine_in_use() blocks a hot-swap mid-transfer.
            with engine_update.engine_in_use():
                yt_dlp = engine_update.get_yt_dlp()
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
    started = time.monotonic()
    # Stall detection must be cooperative: yt-dlp runs in-process (no child
    # to kill), so the hook itself is the only place an abort can originate.
    # Note the residual gap: if the extractor hangs before any download
    # starts, this hook never fires - socket_timeout bounds each network
    # read there instead.
    last_progress = [started, -1]  # (monotonic time, byte count)

    def hook(status: dict[str, object]) -> None:
        if status.get("status") != "downloading":
            return
        now = time.monotonic()
        downloaded = int(status.get("downloaded_bytes") or 0)
        if downloaded != last_progress[1]:
            last_progress[0] = now
            last_progress[1] = downloaded
        elif now - last_progress[0] > STALL_SECONDS:
            raise DownloadStalled(
                f"Download stalled: no progress for {int(STALL_SECONDS)}s"
            )
        if now - started > MAX_ATTEMPT_SECONDS:
            raise DownloadStalled(
                f"Download timed out with no progress toward finishing within {int(MAX_ATTEMPT_SECONDS)}s"
            )
        if now - last_call[0] < 0.5:
            return
        last_call[0] = now
        # Checked on the same throttle as progress reporting - frequent
        # enough that a cancel request stops the transfer within ~0.5s
        # instead of only being noticed once the whole download finishes.
        if cancel_check and cancel_check():
            raise DownloadCancelled("Download cancelled")
        if callback:
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

        # Popen + poll loop instead of subprocess.run: ffmpeg is a child
        # process we CAN kill, so honor cancel_check (run() only returns when
        # ffmpeg exits on its own) and watch the output file for growth -
        # ffmpeg's own network timeouts often never fire on dead HLS streams.
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        last_size = -1
        last_growth = time.monotonic()
        last_report = 0.0
        while proc.poll() is None:
            time.sleep(0.5)
            if request.cancel_check and request.cancel_check():
                _terminate(proc)
                raise DownloadCancelled("Download cancelled")
            try:
                size = output.stat().st_size
            except OSError:
                size = -1
            now = time.monotonic()
            if size != last_size:
                last_size = size
                last_growth = now
                if request.progress_callback and now - last_report >= 0.5 and size > 0:
                    last_report = now
                    request.progress_callback(size, None)
            elif now - last_growth > FFMPEG_STALL_SECONDS:
                _terminate(proc)
                raise DownloadStalled(
                    f"Download stalled: ffmpeg output stopped growing for {int(FFMPEG_STALL_SECONDS)}s"
                )
        _, stderr = proc.communicate()
        if proc.returncode != 0:
            stderr_tail = _tail_lines(stderr or "", 15)
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

        # Resume support: bytes land in a .part file; if one is already there
        # (an earlier attempt of this same job - same job dir), ask the server
        # for just the rest via Range. Renamed to the final name only on
        # success, so a half-file can never be mistaken for a finished
        # download (and _find_new_files skips *.part explicitly).
        probe_name = _direct_filename(request, source_url, None, None)
        resume_from = 0
        partial = request.output_dir / (probe_name + ".part")
        if partial.exists():
            resume_from = partial.stat().st_size
        if resume_from > 0:
            headers = {**headers, "Range": f"bytes={resume_from}-"}

        try:
            response = requests.get(
                source_url,
                headers=headers,
                # (connect, read) tuple: the read timeout doubles as stall
                # detection - a socket that produces no bytes for this long
                # aborts the attempt instead of hanging forever.
                timeout=(10, request.timeout_seconds),
                stream=True,
                allow_redirects=True,
            )
            if resume_from > 0 and response.status_code == 416:
                # Our partial is at/past the real size (or the server can't
                # satisfy the range) - start over from scratch.
                response.close()
                partial.unlink(missing_ok=True)
                resume_from = 0
                headers.pop("Range", None)
                response = requests.get(
                    source_url,
                    headers=headers,
                    timeout=(10, request.timeout_seconds),
                    stream=True,
                    allow_redirects=True,
                )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise StrategyError(f"HTTP download failed: {exc}") from exc

        if resume_from > 0 and response.status_code != 206:
            # Server ignored the Range header - it's sending the whole file.
            partial.unlink(missing_ok=True)
            resume_from = 0

        content_type = response.headers.get("Content-Type")
        if not _response_looks_like_media(response.url, content_type):
            response.close()
            raise StrategyError(
                f"Direct URL is not a media response (Content-Type: {content_type or 'unknown'})."
            )

        # The .part file always lives under the URL-derived probe name (the
        # only name knowable BEFORE the response arrives, hence the only one
        # stable across attempts); the nicer server-provided name (e.g. from
        # Content-Disposition) is applied in the final rename only.
        filename = _direct_filename(request, source_url, response, content_type)
        output = request.output_dir / filename

        content_length = response.headers.get("Content-Length")
        remaining = int(content_length) if content_length and content_length.isdigit() else None
        total_bytes = (remaining + resume_from) if remaining is not None else None
        downloaded_bytes = resume_from
        last_report = time.monotonic()

        try:
            with partial.open("ab" if resume_from > 0 else "wb") as file_obj:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    # Cancel is checked per chunk (at most once per MiB - a
                    # cheap SQLite read), progress writes stay time-throttled.
                    if request.cancel_check and request.cancel_check():
                        raise DownloadCancelled("Download cancelled")
                    file_obj.write(chunk)
                    downloaded_bytes += len(chunk)
                    if request.progress_callback and time.monotonic() - last_report >= 0.5:
                        last_report = time.monotonic()
                        request.progress_callback(downloaded_bytes, total_bytes)
        except requests.RequestException as exc:
            # Read timeout / dropped connection mid-body: keep the .part for
            # the next attempt's Range resume.
            raise StrategyError(f"HTTP download failed mid-transfer: {exc}") from exc
        finally:
            response.close()

        if not partial.exists() or partial.stat().st_size == 0:
            raise StrategyError("Direct download produced an empty file.")
        partial.replace(output)
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


def _direct_filename(request, source_url: str, response, content_type: str | None) -> str:
    """Filename for a direct download.

    With response=None this is the pre-request "probe" name used for the
    .part resume file - derived only from stable inputs (request/URL), never
    from time or response headers, so every attempt of the same job computes
    the same name and finds the previous attempt's partial data.
    """
    extension = guess_extension(source_url, content_type)
    if extension.startswith(".m3u"):
        extension = ".mp4"
    if request.filename:
        return safe_filename(request.filename) + extension
    if response is not None:
        parsed_name = parse_content_disposition(response.headers.get("Content-Disposition"))
        if parsed_name:
            return _ensure_extension(safe_filename(parsed_name), extension)
        path_name = Path(urlparse(response.url).path).name
        if path_name:
            return _ensure_extension(safe_filename(path_name), extension)
    path_name = Path(urlparse(source_url).path).name
    if path_name:
        return _ensure_extension(safe_filename(path_name), extension)
    digest = hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:12]
    return f"video_{digest}{extension}"


def _terminate(proc: subprocess.Popen) -> None:
    # Polite SIGTERM first (lets ffmpeg finalize what it can), hard kill if
    # it doesn't oblige within a few seconds.
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _tail_lines(text: str, count: int) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[-count:])


def _snapshot_files(directory: Path) -> set[Path]:
    return {p.resolve() for p in directory.iterdir() if p.is_file()}


# In-flight/bookkeeping files that must never be attributed as a download
# result: partial data (resume sources), yt-dlp's own state files, and the
# Android publisher's per-file markers (android_entry.py).
_RESULT_EXCLUDED_SUFFIXES = (".part", ".ytdl", ".mediastore-published", ".folder-exported")


def _find_new_files(directory: Path, before: set[Path]) -> list[Path]:
    new_files: list[Path] = []
    for file_path in directory.iterdir():
        if not file_path.is_file():
            continue
        if file_path.name.endswith(_RESULT_EXCLUDED_SUFFIXES):
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
