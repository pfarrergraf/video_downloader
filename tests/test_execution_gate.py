from __future__ import annotations

import threading
import time
from pathlib import Path

from video_downloader.execution_gate import ExecutionGate
from video_downloader.queue_store import QueueStore


def _store(tmp_path: Path) -> QueueStore:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    profile = store.ensure_default_profile()
    store.add_job("https://example.test/video", profile.id)
    return store


def test_closed_gate_prevents_claim_until_open(tmp_path: Path) -> None:
    store = _store(tmp_path)
    gate = ExecutionGate(initially_open=False)
    stop = threading.Event()
    result = []
    thread = threading.Thread(target=lambda: result.append(gate.claim_next_job(store, stop=stop)))
    thread.start()
    time.sleep(0.05)
    assert result == []
    assert store.list_jobs(status="pending", limit=5)

    gate.open()
    thread.join(timeout=1)
    assert result[0] is not None
    assert result[0].status == "in_progress"


def test_stop_releases_waiter_without_claim(tmp_path: Path) -> None:
    store = _store(tmp_path)
    gate = ExecutionGate(initially_open=False)
    stop = threading.Event()
    result = []
    thread = threading.Thread(target=lambda: result.append(gate.claim_next_job(store, stop=stop)))
    thread.start()
    stop.set()
    thread.join(timeout=3)
    assert result == [None]
    assert store.list_jobs(status="pending", limit=5)
