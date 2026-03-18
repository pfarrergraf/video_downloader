from __future__ import annotations

from pathlib import Path

from video_downloader.models import DownloadProfile
from video_downloader.queue_store import QueueStore


def test_profile_crud_roundtrip(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()

    created = store.create_profile(
        DownloadProfile(
            id=None,
            name="music",
            format_selector="ba/b",
            audio_only=True,
            use_aria2=True,
        )
    )

    assert created.id is not None
    assert created.name == "music"

    fetched = store.get_profile_by_name("music")
    assert fetched is not None
    assert fetched.audio_only is True
    assert fetched.use_aria2 is True

    listed = store.list_profiles()
    names = {p.name for p in listed}
    assert "default" in names
    assert "music" in names

    assert store.delete_profile("music") is True
    assert store.get_profile_by_name("music") is None


def test_job_pause_resume_and_reprioritize(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    profile = store.ensure_default_profile()

    job_id = store.add_job(source="https://example.com/video", profile_id=profile.id)
    job = store.get_job(job_id)
    assert job is not None
    assert job.status == "pending"
    assert job.priority == 100

    assert store.pause_job(job_id) is True
    paused = store.get_job(job_id)
    assert paused is not None
    assert paused.status == "paused"

    assert store.reprioritize_job(job_id, 12) is True
    updated = store.get_job(job_id)
    assert updated is not None
    assert updated.priority == 12

    assert store.resume_job(job_id) is True
    resumed = store.get_job(job_id)
    assert resumed is not None
    assert resumed.status == "pending"
