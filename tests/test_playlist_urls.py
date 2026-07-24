from video_downloader.playlist_urls import inspect_playlist_url, is_playlist_url


def test_youtube_watch_with_list_is_canonicalized() -> None:
    result = inspect_playlist_url(
        "https://www.youtube.com/watch?v=7N0Q_0R85jI&list=PLJU5GH-NqTMY&si=tracking"
    )

    assert result.is_playlist is True
    assert result.playlist_id == "PLJU5GH-NqTMY"
    assert result.normalized == "https://www.youtube.com/playlist?list=PLJU5GH-NqTMY"


def test_youtube_music_and_html_escaped_query_are_recognized() -> None:
    result = inspect_playlist_url(
        "https://music.youtube.com/watch?v=abc&amp;list=PL4fGSI1pDJn6KpOXlp0MH8qA9tngXaUJ-"
    )

    assert result.is_playlist is True
    assert result.normalized.endswith("list=PL4fGSI1pDJn6KpOXlp0MH8qA9tngXaUJ-")


def test_dynamic_mix_keeps_seed_video() -> None:
    source = "https://www.youtube.com/watch?v=abc&list=RDabc"
    result = inspect_playlist_url(source)

    assert result.is_playlist is True
    assert result.is_dynamic is True
    assert result.normalized == source


def test_single_video_and_unrelated_list_parameter_stay_single() -> None:
    assert is_playlist_url("https://www.youtube.com/watch?v=abc") is False
    assert is_playlist_url("https://example.com/watch?list=shopping") is False


def test_soundcloud_set_is_recognized_without_rewriting() -> None:
    source = "https://soundcloud.com/artist/sets/my-album"
    result = inspect_playlist_url(source)

    assert result.is_playlist is True
    assert result.normalized == source
