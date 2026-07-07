from __future__ import annotations

import errno
import json
from pathlib import Path

from video_downloader import android_entry
from video_downloader.queue_store import QueueStore


class FakeServer:
    def __init__(self):
        self.worker_started = False
        self.served = False
        self.closed = False

    def start_background_worker(self):
        self.worker_started = True

    def serve_forever(self):
        self.served = True

    def stop_background_worker(self):
        pass

    def server_close(self):
        self.closed = True


def _capture_create_server(captured: dict, fake: FakeServer):
    def fake_create_server(
        *, store, output_dir, password, host, port, workers, ffmpeg_binary, license_manager, app_version
    ):
        captured.update(
            store=store,
            output_dir=output_dir,
            password=password,
            host=host,
            port=port,
            workers=workers,
            ffmpeg_binary=ffmpeg_binary,
            license_manager=license_manager,
            app_version=app_version,
        )
        return fake

    return fake_create_server


def test_start_wires_store_and_output_dir(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    fake = FakeServer()
    monkeypatch.setattr(android_entry, "create_server", _capture_create_server(captured, fake))

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "downloads"
    android_entry.start(str(data_dir), str(output_dir), "secret", 8420, "/opt/bin/ffmpeg")

    assert (data_dir / "state.db").exists()
    assert captured["output_dir"] == output_dir
    assert captured["password"] == "secret"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8420
    assert captured["ffmpeg_binary"] == "/opt/bin/ffmpeg"
    assert captured["license_manager"] is None  # no license_api_base passed -> licensing off
    assert captured["app_version"] == ""
    # The serve loop actually ran and shut down cleanly.
    assert fake.worker_started and fake.served and fake.closed


def test_start_wires_license_manager_when_api_base_given(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(android_entry, "create_server", _capture_create_server(captured, FakeServer()))

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "downloads"
    android_entry.start(
        str(data_dir), str(output_dir), "secret", 8420, "ffmpeg", "https://license.example.com"
    )

    manager = captured["license_manager"]
    assert manager is not None
    assert manager.status().valid is False


def test_duplicate_start_returns_cleanly_when_server_already_healthy(tmp_path: Path, monkeypatch) -> None:
    # The memory.md "Errno 98" incident: a second start() must not crash the
    # thread or spawn a second publisher when our own healthy server already
    # holds the port.
    def raising_create_server(**_kwargs):
        raise OSError(errno.EADDRINUSE, "Address already in use")

    monkeypatch.setattr(android_entry, "create_server", raising_create_server)
    monkeypatch.setattr(android_entry, "_server_already_healthy", lambda port: True)

    publisher_started = []
    monkeypatch.setattr(
        android_entry.threading,
        "Thread",
        lambda *a, **k: publisher_started.append(k.get("name")) or FakeThread(),
    )

    android_entry.start(str(tmp_path / "data"), str(tmp_path / "out"), "secret", 8420)
    assert publisher_started == []  # no second publisher thread


class FakeThread:
    def start(self):
        pass


def test_duplicate_start_reraises_when_port_holder_is_not_ours(tmp_path: Path, monkeypatch) -> None:
    def raising_create_server(**_kwargs):
        raise OSError(errno.EADDRINUSE, "Address already in use")

    monkeypatch.setattr(android_entry, "create_server", raising_create_server)
    monkeypatch.setattr(android_entry, "_server_already_healthy", lambda port: False)

    import pytest

    with pytest.raises(OSError):
        android_entry.start(str(tmp_path / "data"), str(tmp_path / "out"), "secret", 8420)


def test_jobs_snapshot_reports_active_and_recent_completions(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    profile = store.ensure_default_profile()

    active_id = store.add_job(source="https://example.com/a", profile_id=profile.id)
    claimed = store.claim_next_job()
    assert claimed is not None and claimed.id == active_id
    store.update_job_progress(active_id, downloaded_bytes=10, total_bytes=100)

    done_id = store.add_job(source="https://example.com/b", profile_id=profile.id)
    media = tmp_path / "b.mp4"
    media.write_bytes(b"data")
    store.mark_job_completed(done_id, [media])

    snapshot = json.loads(android_entry._jobs_snapshot(store))
    active_ids = [job["id"] for job in snapshot["active"]]
    assert active_id in active_ids
    active_entry = next(job for job in snapshot["active"] if job["id"] == active_id)
    assert active_entry["downloaded_bytes"] == 10
    assert active_entry["total_bytes"] == 100

    completed = {job["id"]: job for job in snapshot["completed"]}
    assert done_id in completed
    assert completed[done_id]["filename"] == "b.mp4"


def test_jobs_snapshot_skips_old_completions(tmp_path: Path) -> None:
    import sqlite3

    store = QueueStore(tmp_path / "state.db")
    store.init()
    profile = store.ensure_default_profile()
    done_id = store.add_job(source="https://example.com/b", profile_id=profile.id)
    media = tmp_path / "b.mp4"
    media.write_bytes(b"data")
    store.mark_job_completed(done_id, [media])
    with sqlite3.connect(tmp_path / "state.db") as conn:
        conn.execute(
            "UPDATE jobs SET finished_at = '2020-01-01T00:00:00+00:00' WHERE id = ?", (done_id,)
        )

    snapshot = json.loads(android_entry._jobs_snapshot(store))
    # Completed long ago -> never re-announced after a process restart.
    assert snapshot["completed"] == []


def test_publisher_calls_notifier_with_snapshot(tmp_path: Path, monkeypatch) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()

    received = []

    class FakeNotifier:
        def onJobsChanged(self, payload: str) -> None:  # noqa: N802 - Java naming
            received.append(json.loads(payload))

    class BreakLoop(Exception):
        pass

    # The endless publisher loop swallows exceptions from its body, so break
    # out of it via the end-of-cycle wait instead.
    class FakeEvent:
        def wait(self, seconds):
            raise BreakLoop

    monkeypatch.setattr(android_entry.threading, "Event", FakeEvent)

    try:
        android_entry._run_downloads_publisher(store, FakeNotifier())
    except BreakLoop:
        pass

    assert received and "active" in received[0] and "completed" in received[0]


def test_publish_to_downloads_is_a_noop_without_the_java_bridge(tmp_path: Path) -> None:
    # Off-Android (this sandbox, CI, Termux, desktop) there is no `java` module
    # to import, so publishing must silently do nothing rather than error.
    output = tmp_path / "video.mp4"
    output.write_bytes(b"data")

    android_entry._publish_file_to_downloads(output)

    assert not android_entry._already_published(output)


def test_publish_marker_roundtrip(tmp_path: Path) -> None:
    output = tmp_path / "video.mp4"
    output.write_bytes(b"data")

    assert not android_entry._already_published(output)
    android_entry._mark_published(output)
    assert android_entry._already_published(output)
