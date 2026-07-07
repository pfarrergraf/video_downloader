from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import shutil
import threading
import time
from typing import Callable

from . import engine_update
from .core import DownloadManager
from .errors import ERR_ENGINE_OUTDATED, classify_error, retry_policy
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

# Partial downloads of failed jobs stay on disk so a retry can resume them —
# but not forever. See QueueRunner.cleanup_stale_partials.
STALE_PARTIAL_MAX_AGE_DAYS = 7


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
        output_dir = self._job_output_dir(job)
        engine_update_tried = False

        attempt = job.attempt
        while attempt < max_attempts:
            attempt += 1
            current = self.store.get_job(job.id)
            if current is None or current.status == JOB_STATUS_CANCELLED:
                self.store.append_event(job.id, "warning", "Job aborted because it was cancelled")
                self._cleanup_orphaned_files(output_dir)
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
                    self._cleanup_orphaned_files(output_dir)
                    return False
                self.store.mark_job_completed(job.id, files, details=result.details)
                return True
            except DownloadWorkflowError as exc:
                error = _format_workflow_error(exc)
            except Exception as exc:  # pragma: no cover - defensive catch for worker threads
                error = str(exc)

            # Re-check regardless of which exception landed above: a real
            # cancel_check-triggered abort (see strategies.DownloadCancelled)
            # normally arrives as its own exception, but yt-dlp can wrap it,
            # and ffmpeg/direct strategies signal it the same way - so the
            # only reliable signal is asking the DB again.
            latest = self.store.get_job(job.id)
            if latest is not None and latest.status == JOB_STATUS_CANCELLED:
                self.store.append_event(job.id, "warning", "Job aborted because it was cancelled")
                self._cleanup_orphaned_files(output_dir)
                return False

            error_code = classify_error(error)
            retryable, backoff = retry_policy(error_code)

            if error_code == ERR_ENGINE_OUTDATED and not engine_update_tried:
                # The site changed and the extractor can't cope - the fix is
                # a newer yt-dlp, not a retry. Try a self-update (throttled
                # internally to once/hour across all threads); if it actually
                # installed something newer, this attempt didn't count.
                engine_update_tried = True
                self.store.append_event(
                    job.id, "info", "Extractor failure looks engine-related; checking for a yt-dlp update"
                )
                updated, latest_version = engine_update.ensure_latest()
                if updated:
                    self.store.append_event(
                        job.id, "info", f"Engine updated to {latest_version}; retrying immediately"
                    )
                    attempt -= 1  # free retry - the failure wasn't the job's fault
                    continue

            if not retryable:
                # A retry can never fix this class of failure (private video,
                # geo block, full disk, ...) - fail fast with the honest
                # answer instead of burning battery on doomed attempts.
                self.store.append_event(
                    job.id, "warning", f"Not retrying ({error_code}): a retry cannot fix this."
                )
                self.store.mark_job_failed(job.id, error, error_code=error_code)
                return False

            if attempt < max_attempts:
                schedule = backoff or BACKOFF_SECONDS
                delay = schedule[min(attempt - 1, len(schedule) - 1)]
                self.store.append_event(
                    job.id,
                    "warning",
                    f"Attempt {attempt} failed: {error}. Retrying in {delay}s.",
                )
                time.sleep(delay)
                continue

            # Final failure: partial files are deliberately KEPT (unlike
            # cancel) so the UI's "retry" (requeue_job, same job dir) can
            # resume from them. cleanup_stale_partials reaps them after
            # STALE_PARTIAL_MAX_AGE_DAYS.
            self.store.mark_job_failed(job.id, error, error_code=error_code)
            return False

        self.store.mark_job_failed(job.id, "Job failed without a terminal error")
        return False

    def _is_cancelled(self, job_id: int) -> bool:
        current = self.store.get_job(job_id)
        return current is not None and current.status == JOB_STATUS_CANCELLED

    def _job_output_dir(self, job: JobRecord) -> Path:
        base_output_dir = (
            Path(job.output_dir).expanduser().resolve() if job.output_dir else self.default_output_dir
        )
        return base_output_dir / f"job-{job.id}"

    def _cleanup_orphaned_files(self, output_dir: Path) -> None:
        # Cancelled jobs never get a job_files DB entry (only
        # mark_job_completed writes those), so whatever bytes yt-dlp already
        # wrote for them are permanently unreachable through the app - left
        # alone, they'd accumulate on disk forever. FAILED jobs deliberately
        # do NOT go through here anymore: their partials are the resume data
        # for the UI's retry button (requeue_job). Best-effort: a concurrent
        # writer still holding the directory open shouldn't crash the worker.
        try:
            shutil.rmtree(output_dir, ignore_errors=True)
        except OSError:
            pass

    def cleanup_stale_partials(self, max_age_days: int = STALE_PARTIAL_MAX_AGE_DAYS) -> int:
        """Reap partial data of long-dead failed jobs (disk hygiene).

        Failed jobs keep their job-<id> directory so a retry can resume - but
        a failure nobody retried for a week is abandoned; on a phone that
        disk space matters. Returns the number of directories removed.
        """
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        removed = 0
        for job in self.store.list_jobs(status="failed", limit=500):
            try:
                finished = datetime.fromisoformat(job.finished_at) if job.finished_at else None
            except ValueError:
                finished = None
            if finished is None or finished >= cutoff:
                continue
            job_dir = self._job_output_dir(job)
            if job_dir.exists():
                self._cleanup_orphaned_files(job_dir)
                removed += 1
        return removed

    def _resolve_profile(self, profile_id: int | None) -> DownloadProfile:
        if profile_id is not None:
            profile = self.store.get_profile_by_id(profile_id)
            if profile is not None:
                return profile
        return self.store.ensure_default_profile()

    def _build_request(self, job: JobRecord, profile: DownloadProfile) -> DownloadRequest:
        # Each job gets its own subdirectory rather than sharing one flat folder.
        # strategies.YtDlpStrategy._find_new_files falls back to "whatever file
        # appeared in the output dir since I started" when yt-dlp's own reported
        # filename can't be confirmed (e.g. a delayed stat() on Android's shared
        # storage FUSE bridge) — with a shared folder that fallback can attribute
        # a *different* job's (or an old, pre-existing) file to this job. A
        # per-job directory makes that misattribution structurally impossible.
        output_dir = ensure_output_dir(self._job_output_dir(job))

        external_downloader: str | None = None
        external_downloader_args: str | None = None
        if profile.use_aria2 and shutil.which("aria2c"):
            external_downloader = "aria2c"
            external_downloader_args = "-x 16 -k 1M -s 16"

        # Parallel HLS/DASH fragment fetches (yt-dlp native downloader).
        # Tunable via the settings table without an app update; clamped so a
        # typo can't spawn 100 connections on a phone.
        concurrent_fragments = 4
        raw_fragments = self.store.get_setting("engine_fragments")
        if raw_fragments and raw_fragments.isdigit():
            concurrent_fragments = max(1, min(8, int(raw_fragments)))

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
            concurrent_fragments=concurrent_fragments,
            progress_callback=lambda downloaded, total, _job_id=job.id: self.store.update_job_progress(
                _job_id, downloaded, total
            ),
            cancel_check=lambda _job_id=job.id: self._is_cancelled(_job_id),
        )

    def _log(self, message: str) -> None:
        if self.logger:
            self.logger(message)
