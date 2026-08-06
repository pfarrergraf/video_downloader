"""Regression guards for Android foreground-download notification cleanup."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "android/app/src/main/java/de/classydl/app/DownloadService.kt"


def test_empty_queue_removes_ongoing_notification_without_idle_delay() -> None:
    source = SERVICE.read_text(encoding="utf-8")

    assert "IDLE_TICKS_BEFORE_STOP" not in source
    assert "else if (inForeground)" in source
    assert "stopForeground(STOP_FOREGROUND_REMOVE)" in source
    # The running service keeps its existing Python notifier connection, so a
    # subsequent user-initiated queue item can promote it back to foreground.
    assert "stopSelf()" not in source
