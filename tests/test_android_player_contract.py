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
GESTURE_MATH = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "PlayerGestureMath.kt"


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


def test_background_notification_reopens_current_player_without_restarting_media() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    player = PLAYER.read_text(encoding="utf-8")

    assert "Intent(this, PlayerActivity::class.java)" in service
    assert ".setAction(PlayerActivity.ACTION_SHOW_CURRENT)" in service
    assert ".setSessionActivity(playerActivity)" in service
    assert "FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP" in service
    assert 'const val ACTION_SHOW_CURRENT = "de.classydl.app.action.SHOW_CURRENT_PLAYBACK"' in player

    consume_intent = player.split("private fun consumeIntent", 1)[1].split("private fun playPendingMedia", 1)[0]
    play_pending = player.split("private fun playPendingMedia", 1)[1].split("private fun showCurrentMedia", 1)[0]
    show_current = player.split("private fun showCurrentMedia", 1)[1].split("private fun saveCurrentPosition", 1)[0]
    assert "if (showCurrentSession) return" in consume_intent
    assert "showCurrentMedia(mediaController)" in play_pending
    assert "setMediaItem" not in show_current
    assert "seekTo" not in show_current


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


def test_player_touch_volume_uses_continuous_one_percent_player_gain() -> None:
    player = PLAYER.read_text(encoding="utf-8")
    gesture_math = GESTURE_MATH.read_text(encoding="utf-8")

    assert "AudioManager" not in player
    assert "mediaController.volume = PlayerGestureMath.unitValueFromPercent(target, MIN_VOLUME_PERCENT)" in player
    assert "Player.COMMAND_SET_VOLUME" in player
    assert "override fun onVolumeChanged(volume: Float)" in player
    assert 'showBubble("🔊 ${PlayerGestureMath.percentFromUnitValue(volume)}%")' in player
    assert "gestureStartVolumePercent" in player
    assert "startY - currentY" in gesture_math
    assert "roundToInt()" in gesture_math
    assert "percent.coerceIn(minPercent.coerceIn(0, 100), 100) / 100f" in gesture_math


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


def test_library_checkbox_is_noninteractive_so_row_tap_drives_selection() -> None:
    """Superseded by the tabs/thumbnails/multi-select library redesign, which
    replaced MediaHistoryActivity's manually-built LinearLayout rows (and the
    `action()` helper this test used to lock) with a RecyclerView adapter.
    The equivalent hard-won gotcha in the new code: a CheckBox is Checkable
    and toggles itself on tap by default, which would desync the checkmark
    from LibraryAdapter.Callbacks' selection sets unless the checkbox is
    explicitly made non-interactive and the row body drives selection."""
    adapter = (ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "LibraryAdapter.kt").read_text(encoding="utf-8")

    assert adapter.count("holder.checkbox.isClickable = false") == 2


def test_completed_notification_opens_native_player_without_chooser() -> None:
    source = DOWNLOAD_SERVICE.read_text(encoding="utf-8")
    completed = source.split("private fun notifyCompleted", 1)[1].split("private fun createChannel", 1)[0]

    assert "Intent(this, PlayerActivity::class.java)" in completed
    assert "setAction(PlayerActivity.ACTION_PLAY_INTERNAL)" in completed
    assert "Intent.createChooser" not in completed
