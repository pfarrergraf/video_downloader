from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_activity_applies_system_bar_and_cutout_insets() -> None:
    activity = (ROOT / "android/app/src/main/java/de/classydl/app/MainActivity.kt").read_text(encoding="utf-8")
    layout = (ROOT / "android/app/src/main/res/layout/activity_main.xml").read_text(encoding="utf-8")
    assert 'android:id="@+id/root"' in layout
    assert "WindowCompat.setDecorFitsSystemWindows(window, false)" in activity
    assert "WindowInsetsCompat.Type.systemBars()" in activity
    assert "WindowInsetsCompat.Type.displayCutout()" in activity
    assert "view.updatePadding(" in activity


def test_media_intents_never_use_wildcard_mime() -> None:
    service = (ROOT / "android/app/src/main/java/de/classydl/app/DownloadService.kt").read_text(encoding="utf-8")
    bridge = (ROOT / "video_downloader/android_bridge.py").read_text(encoding="utf-8")
    assert '"*/*"' not in service
    assert '"*/*"' not in bridge
    for mime in ("video/mp4", "video/webm", "audio/mpeg", "audio/mp4"):
        assert mime in (ROOT / "android/app/src/main/java/de/classydl/app/MediaMimeTypes.kt").read_text(encoding="utf-8")
        assert mime in bridge
