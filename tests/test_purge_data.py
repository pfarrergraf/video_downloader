"""Tests for the local DSAR / "delete my data" purge (QueueStore.purge_user_data)."""

from __future__ import annotations

from pathlib import Path

from video_downloader.queue_store import QueueStore


def _store(tmp_path: Path) -> QueueStore:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    return store


def test_purge_removes_jobs_and_their_urls(tmp_path: Path) -> None:
    store = _store(tmp_path)
    profile = store.ensure_default_profile()
    job_id = store.add_job("https://example.com/private-video", profile.id)
    store.append_event(job_id, "info", "Queued source: https://example.com/private-video")

    assert store.list_jobs() != []
    assert store.list_events() != []

    counts = store.purge_user_data()

    assert store.list_jobs() == []
    assert store.list_events() == []
    assert counts["jobs"] >= 1
    assert counts["events"] >= 1


def test_purge_keeps_config(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.set_setting("language", "de")
    store.add_job("https://example.com/x", store.ensure_default_profile().id)

    store.purge_user_data()

    # Settings/profiles are config, not activity history - left intact.
    assert store.get_setting("language") == "de"
    assert store.get_profile_by_name("default") is not None


def test_purge_on_empty_store_is_safe(tmp_path: Path) -> None:
    store = _store(tmp_path)
    counts = store.purge_user_data()
    assert all(v == 0 for v in counts.values())
