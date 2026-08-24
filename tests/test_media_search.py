from __future__ import annotations

import json

import pytest

from video_downloader import media_search


class _FakeYdl:
    last_options = None
    last_query = None

    def __init__(self, options):
        type(self).last_options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, query, download=False):
        type(self).last_query = query
        assert download is False
        return {
            "entries": [
                {
                    "id": "abc123",
                    "title": "First result",
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "thumbnail": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
                    "channel": "Example channel",
                    "duration": 125,
                },
                {
                    "id": "def456",
                    "title": "Second result",
                    "url": "def456",
                    "uploader": "Uploader",
                },
            ]
        }


def test_search_youtube_is_metadata_only_and_bounded(monkeypatch) -> None:
    monkeypatch.setattr(media_search, "YoutubeDL", _FakeYdl)

    results = media_search.search_youtube("  test   song  ", limit=4)

    assert _FakeYdl.last_query == "ytsearch4:test song"
    assert _FakeYdl.last_options["skip_download"] is True
    assert _FakeYdl.last_options["extract_flat"] == "in_playlist"
    assert _FakeYdl.last_options["socket_timeout"] == media_search.SEARCH_SOCKET_TIMEOUT_SECONDS
    assert _FakeYdl.last_options["retries"] == 0
    assert _FakeYdl.last_options["extractor_retries"] == 0
    assert results[0] == {
        "id": "abc123",
        "title": "First result",
        "url": "https://www.youtube.com/watch?v=abc123",
        "thumbnail": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
        "uploader": "Example channel",
        "duration": 125,
    }
    assert results[1]["url"] == "https://www.youtube.com/watch?v=def456"
    assert results[1]["thumbnail"] == "https://i.ytimg.com/vi/def456/hqdefault.jpg"


def test_search_rejects_blank_and_oversized_queries() -> None:
    with pytest.raises(ValueError):
        media_search.search_youtube("   ")
    with pytest.raises(ValueError):
        media_search.search_youtube("x" * (media_search.MAX_QUERY_CHARS + 1))


def test_search_result_limit_is_capped(monkeypatch) -> None:
    monkeypatch.setattr(media_search, "YoutubeDL", _FakeYdl)
    media_search.search_youtube("anything", limit=999)
    assert _FakeYdl.last_query == f"ytsearch{media_search.MAX_RESULTS}:anything"


def test_search_session_is_stable_and_paginated(monkeypatch) -> None:
    results = [{"id": str(i), "title": f"Item {i}"} for i in range(19)]
    monkeypatch.setattr(media_search, "search_youtube", lambda query, limit: results)
    first = json.loads(media_search.start_search_session_json("anything"))
    assert len(first["results"]) == 8
    assert first["total"] == 19
    second = json.loads(media_search.continue_search_session_json(first["next_cursor"]))
    third = json.loads(media_search.continue_search_session_json(second["next_cursor"]))
    assert [item["id"] for item in first["results"] + second["results"] + third["results"]] == [
        str(i) for i in range(19)
    ]
    assert third["next_cursor"] is None


def test_invalid_or_expired_search_cursor_requires_restart(monkeypatch) -> None:
    assert json.loads(media_search.continue_search_session_json("invalid"))["error"] == "restart_search"
    monkeypatch.setattr(media_search, "search_youtube", lambda query, limit: [])
    first = json.loads(media_search.start_search_session_json("anything"))
    assert first["next_cursor"] is None


def test_cancelled_search_stops_before_network_extraction(monkeypatch) -> None:
    class Signal:
        def isCancelled(self):
            return True

    monkeypatch.setattr(
        media_search,
        "YoutubeDL",
        lambda _options: (_ for _ in ()).throw(AssertionError("must not start yt-dlp")),
    )

    result = json.loads(media_search.start_search_session_json("anything", Signal()))

    assert result == {"error": "search_cancelled", "results": []}


def test_cancel_signal_is_checked_during_yt_dlp_work(monkeypatch) -> None:
    class Signal:
        cancelled = False

        def isCancelled(self):
            return self.cancelled

    signal = Signal()

    class CancellingYdl(_FakeYdl):
        def extract_info(self, query, download=False):
            signal.cancelled = True
            self.last_options["match_filter"]({}, incomplete=True)
            raise AssertionError("cancellation hook must abort extraction")

    monkeypatch.setattr(media_search, "YoutubeDL", CancellingYdl)
    result = json.loads(media_search.start_search_session_json("anything", signal))

    assert result["error"] == "search_cancelled"
