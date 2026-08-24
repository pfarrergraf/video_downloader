from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android" / "app" / "src" / "main"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_player_phase2_retention_contract() -> None:
    player = _read("android/app/src/main/java/de/classydl/app/PlayerActivity.kt")
    service = _read("android/app/src/main/java/de/classydl/app/MediaPlaybackService.kt")
    manifest = _read("android/app/src/main/AndroidManifest.xml")

    assert "PlaybackRetentionStore" in player
    assert "CHECKPOINT_MS = 5_000L" in player
    assert "setPlaybackSpeed" in player
    assert "EXTRA_PLAYLIST_JSON" in player
    assert "enterPictureInPictureMode" in player
    assert 'android:supportsPictureInPicture="true"' in manifest
    assert "sleepDeadlineMs" in service
    assert "player?.pause()" in service


def test_search_routes_downloads_through_existing_queue_and_terms_gate() -> None:
    search = _read("android/app/src/main/java/de/classydl/app/SearchActivity.kt")
    client = _read("android/app/src/main/java/de/classydl/app/LocalApiClient.kt")
    backend = _read("video_downloader/media_search.py")

    assert '"start_search_session_json"' in search
    assert '"continue_search_session_json"' in search
    assert '"/api/login"' in client
    assert '"/api/settings"' in client
    assert 'optBoolean("terms_accepted", false)' in client
    assert '"/api/queue"' in client
    assert '.put("audio_only", audioOnly)' in client
    assert 'f"ytsearch{bounded_limit}:{cleaned}"' in backend
    assert '"skip_download": True' in backend


def test_discovery_does_not_add_ad_blocking_or_broad_storage_permissions() -> None:
    manifest = _read("android/app/src/main/AndroidManifest.xml")
    search = _read("android/app/src/main/java/de/classydl/app/SearchActivity.kt").lower()
    backend = _read("video_downloader/media_search.py").lower()

    assert "READ_MEDIA_VIDEO" not in manifest
    assert "READ_MEDIA_AUDIO" not in manifest
    assert "MANAGE_EXTERNAL_STORAGE" not in manifest
    for forbidden in ("adblock", "block ads", "remove ads", "skip ads"):
        assert forbidden not in search
        assert forbidden not in backend


def test_search_callbacks_are_ignored_after_activity_is_destroyed() -> None:
    search = _read("android/app/src/main/java/de/classydl/app/SearchActivity.kt")

    assert "private val generation = AtomicInteger()" in search
    assert "override fun onDestroy()" in search
    assert "generation.incrementAndGet()" in search
    assert "token != generation.get()" in search


def test_search_uses_recycler_and_bounded_thumbnail_workers() -> None:
    search = _read("android/app/src/main/java/de/classydl/app/SearchActivity.kt")
    layout = _read("android/app/src/main/res/layout/activity_media_search.xml")
    assert "ListAdapter<SearchResult" in search
    assert "Executors.newFixedThreadPool(3)" in search
    assert "LruCache<String, Bitmap>" in search
    assert "androidx.recyclerview.widget.RecyclerView" in layout


def test_library_schema_and_destructive_actions_are_separate() -> None:
    library = _read("android/app/src/main/java/de/classydl/app/MediaLibraryStore.kt")
    main = _read("android/app/src/main/java/de/classydl/app/MainActivity.kt")
    assert "CREATE TABLE media" in library
    assert "CREATE TABLE playlists" in library
    assert "CREATE TABLE playlist_items" in library
    assert "ON DELETE CASCADE" in library
    assert "fun clearPlaybackHistory()" in library
    assert "fun removeFromLibrary" in library
    assert "fun deleteFile" in library
    assert "fun removeFromPlaylist" in library
    assert "fun movePlaylistItem" in library
    assert "legacy_history_v1" in library
    assert "reconcileDownloads" in library
    assert "reconcileMediaLibrary()" in main
