from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

DEFAULT_TASK_NAME = "ClassyDL-Subscriptions"


def install_scheduler(interval_minutes: int, task_name: str = DEFAULT_TASK_NAME) -> str:
    _assert_windows()
    safe_interval = max(1, int(interval_minutes))
    task_command = _subscription_command()

    cmd = [
        "schtasks",
        "/Create",
        "/SC",
        "MINUTE",
        "/MO",
        str(safe_interval),
        "/TN",
        task_name,
        "/TR",
        task_command,
        "/F",
    ]
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(_error_text(run.stderr, run.stdout))
    return task_command


def uninstall_scheduler(task_name: str = DEFAULT_TASK_NAME) -> None:
    _assert_windows()
    cmd = ["schtasks", "/Delete", "/TN", task_name, "/F"]
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(_error_text(run.stderr, run.stdout))


def _subscription_command() -> str:
    candidate = Path(sys.argv[0]).resolve()
    if candidate.suffix.lower() == ".exe" and "classydl" in candidate.name.lower():
        return f'"{candidate}" sub run'
    return f'"{sys.executable}" -m video_downloader.cli sub run'


def _assert_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("Windows Task Scheduler integration is only available on Windows.")


def _error_text(stderr: str, stdout: str) -> str:
    text = stderr.strip() or stdout.strip() or "Task Scheduler command failed"
    return text
