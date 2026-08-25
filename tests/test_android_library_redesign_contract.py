"""Locks a few load-bearing decisions from the tabs/thumbnails/playback-modes/
multi-select library redesign (Ordner & Playlists tabs, real thumbnails via
MediaMetadataRetriever, shuffle/repeat playback, WhatsApp-style multi-select).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
PLAYER = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "PlayerActivity.kt"
MEDIA_PLAYBACK_SERVICE = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "MediaPlaybackService.kt"
THUMBNAIL_LOADER = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "MediaThumbnailLoader.kt"
PLAYLIST_DETAIL = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "PlaylistDetailActivity.kt"
HISTORY = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "MediaHistoryActivity.kt"


def test_playlist_detail_activity_is_registered_without_broad_storage_permission() -> None:
    manifest = MANIFEST.read_text(encoding="utf-8")
    assert 'android:name=".PlaylistDetailActivity"' in manifest
    assert "READ_MEDIA_" not in manifest
    assert "READ_EXTERNAL_STORAGE" not in manifest
    assert "WRITE_EXTERNAL_STORAGE" not in manifest
    assert "WRITE_SETTINGS" not in manifest


def test_thumbnail_loader_uses_minsdk_safe_frame_extraction() -> None:
    # getFrameAtTime() with no args was only added in API 27; this app's
    # minSdk is 26, so it must keep using the two-arg overload that has
    # existed since API 1.
    loader = THUMBNAIL_LOADER.read_text(encoding="utf-8")
    assert "getFrameAtTime(0L, MediaMetadataRetriever.OPTION_CLOSEST_SYNC)" in loader
    assert "getFrameAtTime()" not in loader


def test_player_activity_applies_shuffle_and_repeat_before_same_item_guard() -> None:
    # Applied ahead of the "already playing this exact item/playlist"
    # early-returns in playPendingMedia, so a repeat/shuffle-only change on
    # a re-delivered intent (onNewIntent) still takes effect.
    player = PLAYER.read_text(encoding="utf-8")
    apply_at = player.index("mediaController.shuffleModeEnabled = pendingShuffle")
    guard_at = player.index("currentMediaItem?.mediaId == items.firstOrNull()?.mediaId")
    assert apply_at < guard_at
    assert "mediaController.repeatMode = pendingRepeatMode" in player
    assert 'const val EXTRA_SHUFFLE = "de.classydl.app.extra.SHUFFLE"' in player
    assert 'const val EXTRA_REPEAT_MODE = "de.classydl.app.extra.REPEAT_MODE"' in player


def test_media_playback_service_still_uses_stable_seek_increments() -> None:
    service = MEDIA_PLAYBACK_SERVICE.read_text(encoding="utf-8")
    assert "setSeekBackIncrementMs(SEEK_STEP_MS)" in service
    assert "setSeekForwardIncrementMs(SEEK_STEP_MS)" in service


def test_playlist_detail_reuses_library_adapter_and_playlist_json_contract() -> None:
    detail = PLAYLIST_DETAIL.read_text(encoding="utf-8")
    assert "LibraryAdapter(thumbnailLoader, Callbacks())" in detail
    assert 'array.put(JSONObject().put("uri", it.uri).put("title", it.title).put("mimeType", it.mimeType ?: ""))' in detail
    assert "action_remove_from_playlist).isVisible = true" in detail


def test_folders_tab_groups_by_relative_path_not_a_new_store_query() -> None:
    # Grouping happens client-side over the existing media() list rather than
    # a new SQL query, so MediaLibraryStore's tested query surface is
    # untouched by the tabs redesign.
    history = HISTORY.read_text(encoding="utf-8")
    assert "media.groupBy { folderLabel(it.relativePath) }" in history
