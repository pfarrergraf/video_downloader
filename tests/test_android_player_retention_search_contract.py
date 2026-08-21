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


def test_search_routes_downloads_through_existing_queue() -> None:
    search = _read("android/app/src/main/java/de/classydl/app/SearchActivity.kt")
    client = _read("android/app/src/main/java/de/classydl/app/LocalApiClient.kt")
    backend = _read("video_downloader/media_search.py")

    assert 'callAttr("search_youtube_json", query, 4)' in search
    assert '"/api/login"' in client
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
