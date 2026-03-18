from __future__ import annotations

from video_downloader import scheduler_windows


def test_subscription_command_uses_executable_wrapper(monkeypatch) -> None:
    monkeypatch.setattr("video_downloader.scheduler_windows.sys.argv", [r"C:\\Tools\\classydl.exe"])
    command = scheduler_windows._subscription_command()
    assert "classydl.exe" in command
    assert "sub run" in command
