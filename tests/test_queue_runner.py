from __future__ import annotations

from pathlib import Path

from video_downloader.models import AttemptLog, DownloadResult, DownloadWorkflowError
from video_downloader.queue_runner import QueueRunner
from video_downloader.queue_store import QueueStore


class FakeManager:
    def __init__(self, logger=None) -> None:
        self.logger = logger

    def download(self, request):
        request.output_dir.mkdir(parents=True, exist_ok=True)
        output = request.output_dir / "fake.mp4"
        output.write_bytes(b"ok")
        return DownloadResult(
            file_path=output,
            method="yt-dlp",
            source_url=request.source_url,
            downloaded_files=[output],
        )


def test_queue_runner_completes_job(tmp_path: Path, monkeypatch) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    default_profile = store.ensure_default_profile()

    job_id = store.add_job(
        source="https://example.com/video",
        profile_id=default_profile.id,
        output_dir=str(tmp_path / "out"),
    )

    monkeypatch.setattr("video_downloader.queue_runner.DownloadManager", FakeManager)
    runner = QueueRunner(store=store, default_output_dir=tmp_path / "out")
    summary = runner.run(workers=1)

    assert summary.processed == 1
    assert summary.completed == 1
    assert summary.failed == 0

    job = store.get_job(job_id)
    assert job is not None
    assert job.status == "completed"
    files = store.list_job_files(job_id)
    assert len(files) == 1


class FailingManager:
    """Mirrors what core.DownloadManager raises when every strategy fails -
    exc.attempts carries each strategy's real error, not just the generic
    top-level message."""

    def __init__(self, logger=None) -> None:
        self.logger = logger

    def download(self, request):
        raise DownloadWorkflowError(
            "All download methods failed.",
            attempts=[
                AttemptLog(method="yt-dlp", source_url=request.source_url, success=False, message="Sign in to confirm you're not a bot"),
                AttemptLog(method="direct", source_url=request.source_url, success=False, message="HTTP download failed: 403 Forbidden"),
            ],
        )


def test_queue_runner_stores_the_real_per_strategy_error(tmp_path: Path, monkeypatch) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    default_profile = store.ensure_default_profile()

    job_id = store.add_job(
        source="https://example.com/video",
        profile_id=default_profile.id,
        output_dir=str(tmp_path / "out"),
        max_attempts=1,
    )

    monkeypatch.setattr("video_downloader.queue_runner.DownloadManager", FailingManager)
    runner = QueueRunner(store=store, default_output_dir=tmp_path / "out")
    runner.run(workers=1)

    job = store.get_job(job_id)
    assert job is not None
    assert job.status == "failed"
    assert "Sign in to confirm you're not a bot" in job.error
    assert "403 Forbidden" in job.error


def test_cancelled_job_is_not_completed_and_orphaned_file_is_cleaned_up(tmp_path: Path, monkeypatch) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    default_profile = store.ensure_default_profile()

    job_id = store.add_job(
        source="https://example.com/video",
        profile_id=default_profile.id,
        output_dir=str(tmp_path / "out"),
    )

    class CancelledDuringDownloadManager:
        """Mimics a download that keeps running to completion after the job
        was cancelled mid-transfer (the pre-fix behavior for strategies that
        don't check cancel_check, and the fallback path even for yt-dlp if
        the cancel lands between the last progress-hook check and the final
        write) - the file gets fully written, but the job must still end up
        cancelled, not completed, and the file must not be left on disk."""

        def __init__(self, logger=None) -> None:
            self.logger = logger

        def download(self, request):
            request.output_dir.mkdir(parents=True, exist_ok=True)
            output = request.output_dir / "fake.mp4"
            output.write_bytes(b"ok")
            # Simulate the cancel request arriving while "download" was in flight.
            store.mark_job_cancelled(request.job_id)
            return DownloadResult(
                file_path=output,
                method="yt-dlp",
                source_url=request.source_url,
                downloaded_files=[output],
            )

    monkeypatch.setattr("video_downloader.queue_runner.DownloadManager", CancelledDuringDownloadManager)
    runner = QueueRunner(store=store, default_output_dir=tmp_path / "out")
    runner.run(workers=1)

    job = store.get_job(job_id)
    assert job is not None
    assert job.status == "cancelled"
    assert store.list_job_files(job_id) == []
    assert not (tmp_path / "out" / f"job-{job_id}").exists()


class FailingDownloadWritesPartialFile:
    """A failure (not a cancellation) that leaves a partial file behind -
    e.g. a network drop mid-transfer. Since the retry/requeue flow resumes
    from partial data, failed jobs deliberately KEEP their job directory
    (the janitor reaps abandoned ones after a week - see below)."""

    def __init__(self, logger=None) -> None:
        self.logger = logger

    def download(self, request):
        request.output_dir.mkdir(parents=True, exist_ok=True)
        (request.output_dir / "fake.mp4.part").write_bytes(b"partial")
        raise DownloadWorkflowError("All download methods failed.", attempts=[])


def test_failed_job_keeps_partial_files_for_resume(tmp_path: Path, monkeypatch) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    default_profile = store.ensure_default_profile()

    job_id = store.add_job(
        source="https://example.com/video",
        profile_id=default_profile.id,
        output_dir=str(tmp_path / "out"),
        max_attempts=1,
    )

    monkeypatch.setattr("video_downloader.queue_runner.DownloadManager", FailingDownloadWritesPartialFile)
    runner = QueueRunner(store=store, default_output_dir=tmp_path / "out")
    runner.run(workers=1)

    job = store.get_job(job_id)
    assert job is not None
    assert job.status == "failed"
    # Partial data survives so a retry (requeue_job, same job dir) resumes it.
    assert (tmp_path / "out" / f"job-{job_id}" / "fake.mp4.part").exists()


def test_janitor_reaps_week_old_failed_partials_only(tmp_path: Path, monkeypatch) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    default_profile = store.ensure_default_profile()

    old_id = store.add_job(
        source="https://example.com/old",
        profile_id=default_profile.id,
        output_dir=str(tmp_path / "out"),
        max_attempts=1,
    )
    fresh_id = store.add_job(
        source="https://example.com/fresh",
        profile_id=default_profile.id,
        output_dir=str(tmp_path / "out"),
        max_attempts=1,
    )
    for job_id in (old_id, fresh_id):
        job_dir = tmp_path / "out" / f"job-{job_id}"
        job_dir.mkdir(parents=True)
        (job_dir / "fake.mp4.part").write_bytes(b"partial")
        store.mark_job_failed(job_id, "network dropped")

    # Backdate the old job's finished_at past the retention window.
    import sqlite3

    with sqlite3.connect(tmp_path / "state.db") as conn:
        conn.execute(
            "UPDATE jobs SET finished_at = '2020-01-01T00:00:00+00:00' WHERE id = ?", (old_id,)
        )

    runner = QueueRunner(store=store, default_output_dir=tmp_path / "out")
    removed = runner.cleanup_stale_partials(max_age_days=7)

    assert removed == 1
    assert not (tmp_path / "out" / f"job-{old_id}").exists()
    assert (tmp_path / "out" / f"job-{fresh_id}").exists()


def test_non_retryable_error_fails_fast_without_burning_attempts(tmp_path: Path, monkeypatch) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    default_profile = store.ensure_default_profile()

    calls = []

    class PrivateVideoManager:
        def __init__(self, logger=None) -> None:
            self.logger = logger

        def download(self, request):
            calls.append(1)
            raise DownloadWorkflowError(
                "All download methods failed.",
                attempts=[
                    AttemptLog(
                        method="yt-dlp",
                        source_url=request.source_url,
                        success=False,
                        message="Private video. Sign in if you've been granted access",
                    )
                ],
            )

    job_id = store.add_job(
        source="https://example.com/private",
        profile_id=default_profile.id,
        output_dir=str(tmp_path / "out"),
        max_attempts=3,
    )

    monkeypatch.setattr("video_downloader.queue_runner.DownloadManager", PrivateVideoManager)
    runner = QueueRunner(store=store, default_output_dir=tmp_path / "out")
    runner.run(workers=1)

    job = store.get_job(job_id)
    assert job is not None
    assert job.status == "failed"
    assert job.error_code == "login_required"
    # A retry can't make a private video public - exactly one attempt, no
    # backoff sleeps, despite max_attempts=3.
    assert len(calls) == 1


def test_recover_stale_in_progress_requeues_preserving_progress(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    default_profile = store.ensure_default_profile()

    job_id = store.add_job(
        source="https://example.com/video",
        profile_id=default_profile.id,
        output_dir=str(tmp_path / "out"),
    )
    claimed = store.claim_next_job()
    assert claimed is not None and claimed.id == job_id
    store.set_job_attempt(job_id, 2)
    store.update_job_progress(job_id, downloaded_bytes=12345, total_bytes=99999)

    # Simulate the process being killed here: the job is stranded in_progress.
    recovered = store.recover_stale_in_progress()
    assert recovered == 1

    job = store.get_job(job_id)
    assert job is not None
    assert job.status == "pending"
    # attempt and byte progress survive - the retry resumes, not restarts.
    assert job.attempt == 2
    assert job.downloaded_bytes == 12345

    # And the recovered job is claimable again.
    reclaimed = store.claim_next_job()
    assert reclaimed is not None and reclaimed.id == job_id


def test_requeue_job_resets_failed_job_in_place(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    default_profile = store.ensure_default_profile()

    job_id = store.add_job(
        source="https://example.com/video",
        profile_id=default_profile.id,
        output_dir=str(tmp_path / "out"),
    )
    store.mark_job_failed(job_id, "network dropped", error_code="network_offline")

    assert store.requeue_job(job_id) is True
    job = store.get_job(job_id)
    assert job is not None
    assert job.status == "pending"
    assert job.attempt == 0
    assert job.finished_at is None

    # Only failed jobs qualify; a pending one must not be "requeued" again.
    assert store.requeue_job(job_id) is False
