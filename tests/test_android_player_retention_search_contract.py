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
    assert "ArrayBlockingQueue(capacity)" in search
    assert "boundedExecutor(3, 24, discardOldest = true)" in search
    assert "LruCache<String, Bitmap>" in search
    assert "androidx.recyclerview.widget.RecyclerView" in layout


def test_search_cancellation_and_enqueue_have_separate_bounded_paths() -> None:
    search = _read("android/app/src/main/java/de/classydl/app/SearchActivity.kt")
    run_page = search.split("private fun runPage", 1)[1].split("private fun setBusy", 1)[0]
    enqueue = search.split("private fun enqueue", 1)[1].split("private fun loadThumbnail", 1)[0]

    assert "private val searchExecutor = boundedExecutor(2, 1)" in search
    assert "private val enqueueExecutor = boundedExecutor(1, 4)" in search
    assert "currentSearchFuture?.cancel(true)" in search
    assert "currentCancellation?.cancel()" in search
    assert "mainHandler.postDelayed(timeout, SEARCH_TIMEOUT_MS)" in run_page
    assert "searchExecutor.submit" in run_page
    assert "enqueueExecutor.execute" in enqueue
    assert "searchExecutor.execute" not in enqueue
    assert "RejectedExecutionException" in enqueue


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


def test_corrupt_legacy_payload_is_quarantined_before_source_deletion() -> None:
    library = _read("android/app/src/main/java/de/classydl/app/MediaLibraryStore.kt")
    assert "CREATE TABLE IF NOT EXISTS library_quarantine" in library
    assert 'quarantine(db, raw, "invalid_history_json")' in library
    assert '"quarantined"' in library
    assert 'runCatching { JSONArray(raw) }.getOrNull() ?: JSONArray()' not in library
    assert "checkMigrationReadback(db, importedIds, quarantinedFingerprints)" in library


def test_corrupt_legacy_entries_are_isolated_while_valid_entries_import() -> None:
    library = _read("android/app/src/main/java/de/classydl/app/MediaLibraryStore.kt")
    assert '"invalid_history_entry"' in library
    assert '"invalid_or_unowned_uri"' in library
    assert "continue" in library.split('"invalid_history_entry"', 1)[1]
    assert "importedIds.add(stableId(uri))" in library


def test_legacy_timestamp_and_duplicate_uri_readback_contract() -> None:
    library = _read("android/app/src/main/java/de/classydl/app/MediaLibraryStore.kt")
    assert "val importedIds = mutableSetOf<String>()" in library
    assert 'item.optLong("lastPlayedAtMs", 0L)' in library
    assert 'put("last_played_at_ms", lastPlayedAtMs.coerceAtLeast(0L))' in library
    assert "last_played_at_ms <= ?" in library
    assert 'SELECT 1 FROM media WHERE id = ?' in library


def test_legacy_migration_is_retryable_across_process_interruption() -> None:
    library = _read("android/app/src/main/java/de/classydl/app/MediaLibraryStore.kt")
    migration = library.split("private fun migrateLegacyHistory()", 1)[1]
    assert "db.beginTransaction()" in migration
    assert migration.index('put("key", "legacy_history_v1")') < migration.index("db.setTransactionSuccessful()")
    assert migration.index("db.endTransaction()") < migration.rindex("checkMigrationReadback(db, importedIds")
    assert migration.index("migrationCommitted") < migration.rindex("prefs.edit().remove(LEGACY_KEY).commit()")
    assert "MIGRATED_STATES" in migration
