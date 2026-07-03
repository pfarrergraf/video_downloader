from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import shutil
import threading
import time
from typing import Callable

from .core import DownloadManager
from .models import (
    DownloadProfile,
    DownloadRequest,
    DownloadWorkflowError,
    JOB_STATUS_CANCELLED,
    JobRecord,
)
from .queue_store import QueueStore
from .utils import ensure_output_dir


BACKOFF_SECONDS = (5, 20, 60)


def _format_workflow_error(exc: DownloadWorkflowError) -> str:
    # str(exc) alone is just the generic "All download methods failed." -
    # exc.attempts carries each strategy's real failure message, which used
    # to be discarded here, making every failed job equally uninformative
    # regardless of the actual cause (extractor error, network error, etc.).
    if not exc.attempts:
        return str(exc)
    details = "; ".join(f"{attempt.method}: {attempt.message}" for attempt in exc.attempts)
    return f"{exc}: {details}"


@dataclass(slots=True)
class RunSummary:
    processed: int = 0
    completed: int = 0
    failed: int = 0


class QueueRunner:
    def __init__(
        self,
        store: QueueStore,
        default_output_dir: Path,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self.store = store
        self.default_output_dir = default_output_dir
        self.logger = logger

    def run(self, workers: int = 3) -> RunSummary:
        safe_workers = max(1, min(8, int(workers)))
        summary = RunSummary()
        lock = threading.Lock()

        def worker_loop() -> None:
            local_processed = 0
            local_completed = 0
            local_failed = 0
            manager = DownloadManager(logger=self._log)

            while True:
                job = self.store.claim_next_job()
                if job is None:
                    break

                local_processed += 1
                success = self._process_job(manager, job)
                if success:
                    local_completed += 1
                else:
                    local_failed += 1

            with lock:
                summary.processed += local_processed
                summary.completed += local_completed
                summary.failed += local_failed

        with ThreadPoolExecutor(max_workers=safe_workers, thread_name_prefix="classydl") as pool:
            futures = [pool.submit(worker_loop) for _ in range(safe_workers)]
            for future in futures:
                future.result()

        return summary

    def _process_job(self, manager: DownloadManager, job: JobRecord) -> bool:
        profile = self._resolve_profile(job.profile_id)
        max_attempts = max(1, int(job.max_attempts))

        for attempt in range(job.attempt + 1, max_attempts + 1):
            current = self.store.get_job(job.id)
            if current is None or current.status == JOB_STATUS_CANCELLED:
                self.store.append_event(job.id, "warning", "Job aborted because it was cancelled")
                return False

            self.store.set_job_attempt(job.id, attempt)
            self.store.append_event(job.id, "info", f"Starting attempt {attempt}/{max_attempts}")
            try:
                request = self._build_request(job, profile)
                result = manager.download(request)
                files = result.downloaded_files or [result.file_path]
                latest = self.store.get_job(job.id)
                if latest is not None and latest.status == JOB_STATUS_CANCELLED:
                    self.store.append_event(job.id, "warning", "Download finished after cancellation; result ignored")
                    return False
                self.store.mark_job_completed(job.id, files, details=result.details)
                return True
            except DownloadWorkflowError as exc:
                error = _format_workflow_error(exc)
            except Exception as exc:  # pragma: no cover - defensive catch for worker threads
                error = str(exc)

            if attempt < max_attempts:
                delay = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
                self.store.append_event(
                    job.id,
                    "warning",
                    f"Attempt {attempt} failed: {error}. Retrying in {delay}s.",
                )
                time.sleep(delay)
                continue

            self.store.mark_job_failed(job.id, error)
            return False

        self.store.mark_job_failed(job.id, "Job failed without a terminal error")
        return False

    def _resolve_profile(self, profile_id: int | None) -> DownloadProfile:
        if profile_id is not None:
            profile = self.store.get_profile_by_id(profile_id)
            if profile is not None:
                return profile
        return self.store.ensure_default_profile()

    def _build_request(self, job: JobRecord, profile: DownloadProfile) -> DownloadRequest:
        base_output_dir = (
            Path(job.output_dir).expanduser().resolve() if job.output_dir else self.default_output_dir
        )
        # Each job gets its own subdirectory rather than sharing one flat folder.
        # strategies.YtDlpStrategy._find_new_files falls back to "whatever file
        # appeared in the output dir since I started" when yt-dlp's own reported
        # filename can't be confirmed (e.g. a delayed stat() on Android's shared
        # storage FUSE bridge) — with a shared folder that fallback can attribute
        # a *different* job's (or an old, pre-existing) file to this job. A
        # per-job directory makes that misattribution structurally impossible.
        output_dir = ensure_output_dir(base_output_dir / f"job-{job.id}")

        external_downloader: str | None = None
        external_downloader_args: str | None = None
        if profile.use_aria2 and shutil.which("aria2c"):
            external_downloader = "aria2c"
            external_downloader_args = "-x 16 -k 1M -s 16"

        return DownloadRequest(
            source_url=job.source,
            output_dir=output_dir,
            method=job.method,
            format_selector=profile.format_selector,
            user_agent=job.user_agent,
            referer=job.referer,
            headers=job.headers,
            cookies_from_browser=job.cookies_from_browser,
            timeout_seconds=job.timeout_seconds,
            ffmpeg_binary=job.ffmpeg_binary,
            allow_playlist=job.allow_playlist,
            max_items=job.max_items,
            output_template=profile.output_template,
            audio_only=profile.audio_only,
            subtitle_langs=profile.subtitle_langs,
            audio_langs=profile.audio_langs,
            embed_subs=profile.embed_subs,
            external_downloader=external_downloader,
            external_downloader_args=external_downloader_args,
            job_id=job.id,
            profile_name=profile.name,
            quality_height=job.quality_height,
            progress_callback=lambda downloaded, total, _job_id=job.id: self.store.update_job_progress(
                _job_id, downloaded, total
            ),
        )

    def _log(self, message: str) -> None:
        if self.logger:
            self.logger(message)
