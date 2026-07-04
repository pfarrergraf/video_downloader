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
