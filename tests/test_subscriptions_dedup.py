from __future__ import annotations

import sqlite3
from pathlib import Path

from video_downloader.subscriptions import RemoteItem, _is_youtube_host, _normalize_item_url, sync_due_subscriptions
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


def test_youtube_host_check_rejects_lookalike_urls() -> None:
    # Regression: CodeQL py/incomplete-url-substring-sanitization - a plain
    # "youtube.com" in source_url substring check matches at any position,
    # so an attacker-controlled or malicious subscription source_url like
    # "https://evil.example/?ref=youtube.com" or
    # "https://youtube.com.evil.example/" used to pass. Neither is actually
    # youtube.com.
    assert _is_youtube_host("https://www.youtube.com/feeds/videos.xml?channel_id=x")
    assert _is_youtube_host("https://youtu.be/abc123")
    assert _is_youtube_host("https://music.youtube.com/playlist?list=x")
    assert not _is_youtube_host("https://evil.example/?ref=youtube.com")
    assert not _is_youtube_host("https://youtube.com.evil.example/")
    assert not _is_youtube_host("https://notyoutube.com/")


def test_normalize_item_url_ignores_lookalike_source_url() -> None:
    # With the substring check, a subscription whose source_url merely
    # *contained* "youtube.com" anywhere would make every item_id-only entry
    # (no webpage_url/url field) resolve to a real youtube.com watch link -
    # wrong destination for a non-YouTube source.
    assert _normalize_item_url("", "abc123", "https://evil.example/?ref=youtube.com") == ""
    assert (
        _normalize_item_url("", "abc123", "https://www.youtube.com/feeds/videos.xml?channel_id=x")
        == "https://www.youtube.com/watch?v=abc123"
    )
    # An already-absolute URL is returned as-is regardless of source_url.
    assert _normalize_item_url("https://example.com/v/1", "abc123", "https://anything/") == "https://example.com/v/1"
