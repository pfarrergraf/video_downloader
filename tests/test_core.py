from __future__ import annotations

from pathlib import Path

from video_downloader.core import DownloadManager
from video_downloader.models import DownloadRequest


def _request(source_url: str) -> DownloadRequest:
    return DownloadRequest(source_url=source_url, output_dir=Path("/tmp/does-not-matter"))


def test_auto_queue_always_tries_the_source_itself(monkeypatch) -> None:
    manager = DownloadManager()
    monkeypatch.setattr(manager, "_probe_page", lambda request: [])

    queue = manager._build_auto_queue(_request("https://youtube.com/watch?v=abc123"))

    assert queue[0] == ("yt-dlp", "https://youtube.com/watch?v=abc123")


def test_auto_queue_adds_probed_candidates_for_every_strategy(monkeypatch) -> None:
    manager = DownloadManager()
    monkeypatch.setattr(manager, "_probe_page", lambda request: ["https://cdn.example.com/video.mp4"])

    queue = manager._build_auto_queue(_request("https://blog.example.com/post"))

    assert ("direct", "https://cdn.example.com/video.mp4") in queue
    assert ("yt-dlp", "https://cdn.example.com/video.mp4") in queue
