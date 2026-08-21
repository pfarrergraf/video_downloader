from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
GRADLE = ROOT / "android" / "app" / "build.gradle"
PLAYER = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "PlayerActivity.kt"
SERVICE = ROOT / "android" / "app" / "src" / "main" / "java" / "de" / "classydl" / "app" / "MediaPlaybackService.kt"
BRIDGE = ROOT / "video_downloader" / "android_bridge.py"


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
