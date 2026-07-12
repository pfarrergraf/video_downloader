from __future__ import annotations

from typing import Callable

import requests

from .models import AttemptLog, DownloadRequest, DownloadResult, DownloadWorkflowError
from .strategies import (
    DirectDownloadStrategy,
    FFmpegStrategy,
    StrategyError,
    YtDlpStrategy,
)
from .utils import (
    extract_media_candidates,
    is_direct_asset_url,
    is_direct_media_url,
    is_manifest_url,
)

Logger = Callable[[str], None]


class DownloadManager:
    def __init__(self, logger: Logger | None = None) -> None:
        self.logger = logger
        self._strategies = {
            "yt-dlp": YtDlpStrategy(),
            "ffmpeg": FFmpegStrategy(),
            "direct": DirectDownloadStrategy(),
        }

    def download(self, request: DownloadRequest) -> DownloadResult:
        if request.method != "auto":
            strategy = self._strategies.get(request.method)
            if strategy is None:
                raise DownloadWorkflowError(
                    f"Unknown method `{request.method}`.",
                    attempts=[],
                )
            return self._run_single(strategy.name, request, request.source_url)

        attempts: list[AttemptLog] = []
        queue = self._build_auto_queue(request)
        seen: set[tuple[str, str]] = set()

        for method, source_url in queue:
            if (method, source_url) in seen:
                continue
            seen.add((method, source_url))

            strategy = self._strategies[method]
            self._log(f"Trying {method} on {source_url}")
            try:
                result = strategy.download(request, source_url)
                attempts.append(
                    AttemptLog(method=method, source_url=source_url, success=True, message="Success")
                )
                return result
            except StrategyError as exc:
                attempts.append(
                    AttemptLog(method=method, source_url=source_url, success=False, message=str(exc))
                )
                self._log(f"{method} failed: {exc}")

        raise DownloadWorkflowError("All download methods failed.", attempts=attempts)

    def _run_single(self, method: str, request: DownloadRequest, source_url: str) -> DownloadResult:
        self._log(f"Using {method} for {source_url}")
        try:
            return self._strategies[method].download(request, source_url)
        except StrategyError as exc:
            attempts = [
                AttemptLog(method=method, source_url=source_url, success=False, message=str(exc)),
            ]
            raise DownloadWorkflowError(f"{method} failed.", attempts=attempts) from exc

    def _build_auto_queue(self, request: DownloadRequest) -> list[tuple[str, str]]:
        source = request.source_url
        if request.allow_playlist:
            return [("yt-dlp", source)]
        if not (source.startswith("http://") or source.startswith("https://")):
            return [("yt-dlp", source)]

        queue: list[tuple[str, str]] = []
        if is_direct_asset_url(source) and not is_direct_media_url(source):
            # A known image/document extension (e.g. .jpg, .pdf, .zip) is a
            # plain static file, not a page yt-dlp needs to extract from - and
            # yt-dlp's generic extractor, tried against it anyway, downloads
            # the same bytes but mislabels the extension (e.g. "unknown_video"
            # for a PDF). Try the direct fetch first; yt-dlp stays queued right
            # after as a fallback in case direct fails for some other reason.
            queue.append(("direct", source))
        queue.append(("yt-dlp", source))

        if is_manifest_url(source):
            queue.append(("ffmpeg", source))
        if is_direct_media_url(source):
            queue.append(("direct", source))

        discovered = self._probe_page(request)
        for candidate in discovered:
            if is_manifest_url(candidate):
                queue.append(("ffmpeg", candidate))
            elif is_direct_media_url(candidate):
                queue.append(("direct", candidate))
            queue.append(("yt-dlp", candidate))

        queue.append(("direct", source))
        queue.append(("ffmpeg", source))
        return queue

    def _probe_page(self, request: DownloadRequest) -> list[str]:
        headers = {}
        if request.user_agent:
            headers["User-Agent"] = request.user_agent
        if request.referer:
            headers["Referer"] = request.referer
        headers.update(request.headers)

        self._log("Probing page for embedded media URLs")
        try:
            with requests.get(
                request.source_url,
                headers=headers,
                timeout=request.timeout_seconds,
                allow_redirects=True,
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").lower()
                if "html" not in content_type:
                    return []
                return extract_media_candidates(response.url, response.text)
        except requests.RequestException as exc:
            self._log(f"Page probe skipped: {exc}")
            return []

    def _log(self, message: str) -> None:
        if self.logger:
            self.logger(message)
