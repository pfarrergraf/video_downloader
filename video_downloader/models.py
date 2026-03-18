from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

JOB_STATUS_PENDING = "pending"
JOB_STATUS_PAUSED = "paused"
JOB_STATUS_IN_PROGRESS = "in_progress"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_CANCELLED = "cancelled"


@dataclass(slots=True)
class DownloadRequest:
    source_url: str
    output_dir: Path
    filename: str | None = None
    method: str = "auto"
    format_selector: str = "bv*+ba/b"
    user_agent: str | None = None
    referer: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    cookies_from_browser: str | None = None
    timeout_seconds: int = 30
    ffmpeg_binary: str = "ffmpeg"
    allow_playlist: bool = False
    max_items: int | None = None
    output_template: str | None = None
    audio_only: bool = False
    subtitle_langs: str | None = None
    audio_langs: str | None = None
    embed_subs: bool = False
    external_downloader: str | None = None
    external_downloader_args: str | None = None
    job_id: int | None = None
    profile_name: str | None = None


@dataclass(slots=True)
class DownloadResult:
    file_path: Path
    method: str
    source_url: str
    details: str = ""
    downloaded_files: list[Path] = field(default_factory=list)


@dataclass(slots=True)
class AttemptLog:
    method: str
    source_url: str
    success: bool
    message: str


@dataclass(slots=True)
class DownloadProfile:
    id: int | None
    name: str
    format_selector: str = "bv*+ba/b"
    output_template: str | None = None
    audio_only: bool = False
    subtitle_langs: str | None = None
    audio_langs: str | None = None
    embed_subs: bool = False
    workers_hint: int = 3
    use_aria2: bool = False
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(slots=True)
class JobRecord:
    id: int
    source: str
    mode: str
    profile_id: int | None
    status: str
    priority: int
    attempt: int
    max_attempts: int
    error: str | None
    output_dir: str | None
    method: str
    user_agent: str | None
    referer: str | None
    headers: dict[str, str]
    cookies_from_browser: str | None
    allow_playlist: bool
    max_items: int | None
    timeout_seconds: int
    ffmpeg_binary: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    updated_at: str


@dataclass(slots=True)
class SubscriptionRecord:
    id: int
    source_url: str
    profile_id: int | None
    interval_minutes: int
    last_checked_at: str | None
    enabled: bool
    created_at: str


@dataclass(slots=True)
class QueueEvent:
    id: int
    job_id: int | None
    level: str
    message: str
    created_at: str


class DownloadWorkflowError(RuntimeError):
    def __init__(self, message: str, attempts: list[AttemptLog]) -> None:
        super().__init__(message)
        self.attempts = attempts
