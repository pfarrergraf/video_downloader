from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
GRADLE = ROOT / "android" / "app" / "build.gradle"
PLAYER = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "PlayerActivity.kt"
SERVICE = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "MediaPlaybackService.kt"
BRIDGE = ROOT / "video_downloader" / "android_bridge.py"
RETENTION = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "PlaybackRetentionStore.kt"
LIBRARY = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "MediaLibraryStore.kt"
DOWNLOAD_SERVICE = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "DownloadService.kt"


def test_player_uses_stable_media3_stack() -> None:
    text = GRADLE.read_text(encoding="utf-8")
    assert "def media3Version = '1.10.1'" in text
    assert "media3-exoplayer:${media3Version}" in text
    assert "media3-ui:${media3Version}" in text
    assert "media3-session:${media3Version}" in text


def test_manifest_exposes_media_open_with_without_broad_storage_permission() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    assert 'android:name=".PlayerActivity"' in text
    assert 'android:name="android.intent.action.VIEW"' in text
    assert 'android:mimeType="video/*"' in text
    assert 'android:mimeType="audio/*"' in text
    assert "READ_MEDIA_" not in text
    assert "READ_EXTERNAL_STORAGE" not in text
    assert "WRITE_EXTERNAL_STORAGE" not in text


def test_background_playback_service_contract() -> None:
    manifest = MANIFEST.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")
    assert "FOREGROUND_SERVICE_MEDIA_PLAYBACK" in manifest
    assert 'android:foregroundServiceType="mediaPlayback"' in manifest
    assert "androidx.media3.session.MediaSessionService" in manifest
    assert "class MediaPlaybackService : MediaSessionService()" in service
    assert "setHandleAudioBecomingNoisy(true)" in service


def test_internal_downloads_open_directly_in_native_player() -> None:
    bridge = BRIDGE.read_text(encoding="utf-8")
    assert 'jclass("de.classydl.app.PlayerActivity")' in bridge
    assert 'setAction("de.classydl.app.action.PLAY_INTERNAL")' in bridge
    open_file_body = bridge.split("def open_file", 1)[1].split("def open_folder", 1)[0]
    assert "createChooser" not in open_file_body


def test_player_does_not_restart_same_item_on_activity_recreation() -> None:
    text = PLAYER.read_text(encoding="utf-8")
    assert "currentMediaItem?.mediaId == mediaId" in text
    assert "setMediaId(mediaId)" in text


def test_player_rejects_remote_uris_in_single_items_and_playlists() -> None:
    player = PLAYER.read_text(encoding="utf-8")

    assert 'LOCAL_URI_SCHEMES = setOf("content", "file")' in player
    assert "!isLocalPlaybackUri(uri)" in player
    assert "!isLocalPlaybackUri(Uri.parse(uri))" in player
    assert "rejectedEntries++" in player
    assert "player_playlist_items_skipped" in player


def test_only_owned_downloads_are_retained_and_missing_history_files_are_handled() -> None:
    retention = RETENTION.read_text(encoding="utf-8")
    library = LIBRARY.read_text(encoding="utf-8")
    player = PLAYER.read_text(encoding="utf-8")
    history = (ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "MediaHistoryActivity.kt").read_text(encoding="utf-8")

    assert 'parsed.authority == FILE_PROVIDER_AUTHORITY' in retention
    assert "if (!isOwnedDownloadUri(uri)) return" in retention
    assert "if (!retentionStore.isOwnedDownloadUri(uri)) return" in player
    assert "contentResolver.openFileDescriptor" in history
    assert "store.pruneUnreadable()" in history
    assert "removeFromLibrary" in library


def test_library_action_helper_keeps_click_lambda_last_for_weighted_buttons() -> None:
    history = (ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "MediaHistoryActivity.kt").read_text(encoding="utf-8")

    assert "private fun action(text: Int, params: LinearLayout.LayoutParams? = null, click: () -> Unit)" in history
    assert "action(R.string.library_add_to_playlist) { choosePlaylist(media) }, weighted()" in history


def test_completed_notification_opens_native_player_without_chooser() -> None:
    source = DOWNLOAD_SERVICE.read_text(encoding="utf-8")
    completed = source.split("private fun notifyCompleted", 1)[1].split("private fun createChannel", 1)[0]

    assert "Intent(this, PlayerActivity::class.java)" in completed
    assert "setAction(PlayerActivity.ACTION_PLAY_INTERNAL)" in completed
    assert "Intent.createChooser" not in completed
