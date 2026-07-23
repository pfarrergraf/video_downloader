"""Regression guards for the trustworthy Android cold-start experience."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_webview_is_hidden_behind_branded_startup_overlay() -> None:
    layout = (
        ROOT / "android/app/src/main/res/layout/activity_main.xml"
    ).read_text(encoding="utf-8")
    assert 'android:id="@+id/startup_overlay"' in layout
    assert 'android:id="@+id/startup_status"' in layout
    assert 'android:visibility="invisible"' in layout
    assert "@string/app_name" in layout
    assert "@string/startup_preparing" in layout


def test_main_activity_waits_for_health_before_loading_webview() -> None:
    activity = (
        ROOT / "android/app/src/main/java/de/classydl/app/MainActivity.kt"
    ).read_text(encoding="utf-8")
    assert 'URL("$SERVER_URL/api/health")' in activity
    assert "waitForServerThenLoad()" in activity
    assert "webView.loadUrl(SERVER_URL)" in activity
    assert "webView.visibility = View.VISIBLE" in activity
    assert "startupOverlay.visibility = View.GONE" in activity


def test_main_frame_errors_never_reveal_chromium_error_page() -> None:
    activity = (
        ROOT / "android/app/src/main/java/de/classydl/app/MainActivity.kt"
    ).read_text(encoding="utf-8")
    assert "if (request?.isForMainFrame != true) return" in activity
    assert "mainFrameLoadFailed = true" in activity
    assert "showStartupOverlay()" in activity
    assert "startupStatus.setText(R.string.startup_failed)" in activity
