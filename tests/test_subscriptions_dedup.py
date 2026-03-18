from __future__ import annotations

import sqlite3
from pathlib import Path

from video_downloader.subscriptions import RemoteItem, sync_due_subscriptions
from video_downloader.queue_store import QueueStore


def test_subscription_dedup_across_runs(tmp_path: Path, monkeypatch) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()

    default_profile = store.ensure_default_profile()
    store.add_subscription(
        source_url="https://example.com/channel",
        profile_id=default_profile.id,
        interval_minutes=1,
    )

    def fake_fetch(_: str):
        return [
            RemoteItem(item_id="a1", url="https://example.com/video/a1"),
            RemoteItem(item_id="a2", url="https://example.com/video/a2"),
        ]

    monkeypatch.setattr("video_downloader.subscriptions.fetch_remote_items", fake_fetch)

    first = sync_due_subscriptions(store)
    assert first.jobs_created == 2

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("UPDATE subscriptions SET last_checked_at = '2000-01-01T00:00:00+00:00'")
    conn.commit()
    conn.close()

    second = sync_due_subscriptions(store)
    assert second.jobs_created == 0
