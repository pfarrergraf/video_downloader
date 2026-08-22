from __future__ import annotations

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
