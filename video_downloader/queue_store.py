from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from .models import (
    DownloadProfile,
    JOB_STATUS_CANCELLED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_IN_PROGRESS,
    JOB_STATUS_PENDING,
    JOB_STATUS_PAUSED,
    JobRecord,
    QueueEvent,
    SubscriptionRecord,
)


class QueueStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    format_selector TEXT NOT NULL,
                    output_template TEXT,
                    audio_only INTEGER NOT NULL DEFAULT 0,
                    subtitle_langs TEXT,
                    audio_langs TEXT,
                    embed_subs INTEGER NOT NULL DEFAULT 0,
                    workers_hint INTEGER NOT NULL DEFAULT 3,
                    use_aria2 INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'url',
                    profile_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority INTEGER NOT NULL DEFAULT 100,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    error TEXT,
                    output_dir TEXT,
                    method TEXT NOT NULL DEFAULT 'auto',
                    user_agent TEXT,
                    referer TEXT,
                    headers_json TEXT NOT NULL DEFAULT '{}',
                    cookies_from_browser TEXT,
                    allow_playlist INTEGER NOT NULL DEFAULT 0,
                    max_items INTEGER,
                    timeout_seconds INTEGER NOT NULL DEFAULT 30,
                    ffmpeg_binary TEXT NOT NULL DEFAULT 'ffmpeg',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id)
                );

                CREATE TABLE IF NOT EXISTS job_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_url TEXT NOT NULL UNIQUE,
                    profile_id INTEGER,
                    interval_minutes INTEGER NOT NULL DEFAULT 60,
                    last_checked_at TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id)
                );

                CREATE TABLE IF NOT EXISTS subscription_seen_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscription_id INTEGER NOT NULL,
                    remote_item_id TEXT NOT NULL,
                    seen_at TEXT NOT NULL,
                    UNIQUE(subscription_id, remote_item_id),
                    FOREIGN KEY(subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE SET NULL
                );
                """
            )

        self.ensure_default_profile()

    def ensure_default_profile(self) -> DownloadProfile:
        profile = self.get_profile_by_name("default")
        if profile:
            return profile
        return self.create_profile(DownloadProfile(id=None, name="default"))

    def create_profile(self, profile: DownloadProfile) -> DownloadProfile:
        now = _utcnow()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO profiles (
                    name, format_selector, output_template, audio_only, subtitle_langs,
                    audio_langs, embed_subs, workers_hint, use_aria2, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.name,
                    profile.format_selector,
                    profile.output_template,
                    int(profile.audio_only),
                    profile.subtitle_langs,
                    profile.audio_langs,
                    int(profile.embed_subs),
                    max(1, min(8, int(profile.workers_hint))),
                    int(profile.use_aria2),
                    now,
                    now,
                ),
            )
            profile_id = int(cursor.lastrowid)
        return self.get_profile_by_id(profile_id)  # type: ignore[return-value]

    def list_profiles(self) -> list[DownloadProfile]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM profiles ORDER BY name ASC").fetchall()
        return [self._row_to_profile(row) for row in rows]

    def get_profile_by_name(self, name: str) -> DownloadProfile | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM profiles WHERE name = ?", (name,)).fetchone()
        return self._row_to_profile(row) if row else None

    def get_profile_by_id(self, profile_id: int) -> DownloadProfile | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return self._row_to_profile(row) if row else None

    def delete_profile(self, name: str) -> bool:
        if name == "default":
            return False
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM profiles WHERE name = ?", (name,))
            return cursor.rowcount > 0

    def add_job(
        self,
        source: str,
        profile_id: int | None,
        *,
        mode: str = "url",
        priority: int = 100,
        max_attempts: int = 3,
        output_dir: str | None = None,
        method: str = "auto",
        user_agent: str | None = None,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        cookies_from_browser: str | None = None,
        allow_playlist: bool = False,
        max_items: int | None = None,
        timeout_seconds: int = 30,
        ffmpeg_binary: str = "ffmpeg",
    ) -> int:
        now = _utcnow()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO jobs (
                    source, mode, profile_id, status, priority, attempt, max_attempts, error,
                    output_dir, method, user_agent, referer, headers_json, cookies_from_browser,
                    allow_playlist, max_items, timeout_seconds, ffmpeg_binary,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 0, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    mode,
                    profile_id,
                    JOB_STATUS_PENDING,
                    int(priority),
                    max(1, int(max_attempts)),
                    output_dir,
                    method,
                    user_agent,
                    referer,
                    json.dumps(headers or {}),
                    cookies_from_browser,
                    int(allow_playlist),
                    max_items,
                    int(timeout_seconds),
                    ffmpeg_binary,
                    now,
                    now,
                ),
            )
            job_id = int(cursor.lastrowid)

        self.append_event(job_id, "info", f"Queued source: {source}")
        return job_id

    def claim_next_job(self) -> JobRecord | None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = ?
                ORDER BY priority ASC, created_at ASC
                LIMIT 1
                """,
                (JOB_STATUS_PENDING,),
            ).fetchone()
            if row is None:
                conn.commit()
                return None

            now = _utcnow()
            updated = conn.execute(
                """
                UPDATE jobs
                SET status = ?, started_at = COALESCE(started_at, ?), updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (JOB_STATUS_IN_PROGRESS, now, now, row["id"], JOB_STATUS_PENDING),
            )
            conn.commit()
            if updated.rowcount <= 0:
                return None
            claimed = conn.execute("SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone()
            return self._row_to_job(claimed) if claimed else None

    def set_job_attempt(self, job_id: int, attempt: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET attempt = ?, updated_at = ? WHERE id = ?",
                (int(attempt), _utcnow(), job_id),
            )

    def mark_job_completed(self, job_id: int, file_paths: Iterable[Path], details: str = "") -> None:
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, error = NULL, finished_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (JOB_STATUS_COMPLETED, now, now, job_id),
            )
            for path in file_paths:
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                conn.execute(
                    """
                    INSERT INTO job_files (job_id, path, size_bytes, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (job_id, str(path), int(size), now),
                )
        self.append_event(job_id, "info", "Job completed successfully")
        if details:
            self.append_event(job_id, "info", details)

    def mark_job_failed(self, job_id: int, error: str) -> None:
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, error = ?, finished_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (JOB_STATUS_FAILED, error, now, now, job_id),
            )
        self.append_event(job_id, "error", error)

    def mark_job_cancelled(self, job_id: int) -> bool:
        now = _utcnow()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?, updated_at = ?
                WHERE id = ? AND status IN (?, ?)
                """,
                (JOB_STATUS_CANCELLED, now, now, job_id, JOB_STATUS_PENDING, JOB_STATUS_IN_PROGRESS),
            )
        if cursor.rowcount > 0:
            self.append_event(job_id, "warning", "Job cancelled by operator")
            return True
        return False

    def pause_job(self, job_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (JOB_STATUS_PAUSED, _utcnow(), job_id, JOB_STATUS_PENDING),
            )
        if cursor.rowcount > 0:
            self.append_event(job_id, "warning", "Job paused by operator")
            return True
        return False

    def resume_job(self, job_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (JOB_STATUS_PENDING, _utcnow(), job_id, JOB_STATUS_PAUSED),
            )
        if cursor.rowcount > 0:
            self.append_event(job_id, "info", "Job resumed by operator")
            return True
        return False

    def reprioritize_job(self, job_id: int, priority: int) -> bool:
        safe_priority = max(1, int(priority))
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET priority = ?, updated_at = ?
                WHERE id = ? AND status IN (?, ?)
                """,
                (safe_priority, _utcnow(), job_id, JOB_STATUS_PENDING, JOB_STATUS_PAUSED),
            )
        if cursor.rowcount > 0:
            self.append_event(job_id, "info", f"Job priority changed to {safe_priority}")
            return True
        return False

    def mark_job_pending(self, job_id: int, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (JOB_STATUS_PENDING, error, _utcnow(), job_id),
            )

    def append_event(self, job_id: int | None, level: str, message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO events (job_id, level, message, created_at) VALUES (?, ?, ?, ?)",
                (job_id, level, message, _utcnow()),
            )

    def get_job(self, job_id: int) -> JobRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def list_jobs(self, status: str | None = None, limit: int = 200) -> list[JobRecord]:
        params: list[object] = []
        query = "SELECT * FROM jobs"
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_job(row) for row in rows]

    def list_job_files(self, job_id: int) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT path FROM job_files WHERE job_id = ? ORDER BY id ASC",
                (job_id,),
            ).fetchall()
        return [str(row["path"]) for row in rows]

    def retry_job(self, job_id: int) -> int | None:
        original = self.get_job(job_id)
        if original is None:
            return None
        if original.status not in {JOB_STATUS_FAILED, JOB_STATUS_CANCELLED}:
            return None
        return self.add_job(
            source=original.source,
            profile_id=original.profile_id,
            mode=original.mode,
            priority=original.priority,
            max_attempts=original.max_attempts,
            output_dir=original.output_dir,
            method=original.method,
            user_agent=original.user_agent,
            referer=original.referer,
            headers=original.headers,
            cookies_from_browser=original.cookies_from_browser,
            allow_playlist=original.allow_playlist,
            max_items=original.max_items,
            timeout_seconds=original.timeout_seconds,
            ffmpeg_binary=original.ffmpeg_binary,
        )

    def list_history(self, status: str | None = None, limit: int = 200) -> list[JobRecord]:
        final_statuses = (JOB_STATUS_COMPLETED, JOB_STATUS_FAILED, JOB_STATUS_CANCELLED)
        params: list[object] = []
        if status and status not in final_statuses:
            status = None

        query = "SELECT * FROM jobs WHERE status IN (?, ?, ?)"
        params.extend(final_statuses)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_job(row) for row in rows]

    def add_subscription(
        self,
        source_url: str,
        profile_id: int | None,
        interval_minutes: int,
    ) -> int:
        now = _utcnow()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO subscriptions (
                    source_url, profile_id, interval_minutes, last_checked_at, enabled, created_at
                ) VALUES (?, ?, ?, NULL, 1, ?)
                ON CONFLICT(source_url) DO UPDATE SET
                    profile_id=excluded.profile_id,
                    interval_minutes=excluded.interval_minutes,
                    enabled=1
                """,
                (source_url, profile_id, max(1, int(interval_minutes)), now),
            )
            if cursor.lastrowid:
                return int(cursor.lastrowid)

        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM subscriptions WHERE source_url = ?",
                (source_url,),
            ).fetchone()
        return int(row["id"])

    def list_subscriptions(self) -> list[SubscriptionRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM subscriptions ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_subscription(row) for row in rows]

    def due_subscriptions(self) -> list[SubscriptionRecord]:
        now = datetime.now(UTC)
        due: list[SubscriptionRecord] = []
        for sub in self.list_subscriptions():
            if not sub.enabled:
                continue
            if sub.last_checked_at is None:
                due.append(sub)
                continue
            try:
                checked = datetime.fromisoformat(sub.last_checked_at)
            except ValueError:
                due.append(sub)
                continue
            if checked.tzinfo is None:
                checked = checked.replace(tzinfo=UTC)
            delta = now - checked
            if delta >= timedelta(minutes=sub.interval_minutes):
                due.append(sub)
        return due

    def mark_subscription_checked(self, subscription_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE subscriptions SET last_checked_at = ? WHERE id = ?",
                (_utcnow(), subscription_id),
            )

    def has_seen_item(self, subscription_id: int, remote_item_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM subscription_seen_items
                WHERE subscription_id = ? AND remote_item_id = ?
                """,
                (subscription_id, remote_item_id),
            ).fetchone()
        return row is not None

    def mark_seen_item(self, subscription_id: int, remote_item_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO subscription_seen_items (subscription_id, remote_item_id, seen_at)
                VALUES (?, ?, ?)
                """,
                (subscription_id, remote_item_id, _utcnow()),
            )

    def list_events(self, limit: int = 200) -> list[QueueEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [
            QueueEvent(
                id=int(row["id"]),
                job_id=int(row["job_id"]) if row["job_id"] is not None else None,
                level=str(row["level"]),
                message=str(row["message"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def _row_to_profile(self, row: sqlite3.Row) -> DownloadProfile:
        return DownloadProfile(
            id=int(row["id"]),
            name=str(row["name"]),
            format_selector=str(row["format_selector"]),
            output_template=str(row["output_template"]) if row["output_template"] is not None else None,
            audio_only=bool(row["audio_only"]),
            subtitle_langs=str(row["subtitle_langs"]) if row["subtitle_langs"] is not None else None,
            audio_langs=str(row["audio_langs"]) if row["audio_langs"] is not None else None,
            embed_subs=bool(row["embed_subs"]),
            workers_hint=int(row["workers_hint"]),
            use_aria2=bool(row["use_aria2"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _row_to_job(self, row: sqlite3.Row) -> JobRecord:
        headers_text = row["headers_json"] or "{}"
        try:
            headers_data = json.loads(headers_text)
        except json.JSONDecodeError:
            headers_data = {}
        if not isinstance(headers_data, dict):
            headers_data = {}

        return JobRecord(
            id=int(row["id"]),
            source=str(row["source"]),
            mode=str(row["mode"]),
            profile_id=int(row["profile_id"]) if row["profile_id"] is not None else None,
            status=str(row["status"]),
            priority=int(row["priority"]),
            attempt=int(row["attempt"]),
            max_attempts=int(row["max_attempts"]),
            error=str(row["error"]) if row["error"] is not None else None,
            output_dir=str(row["output_dir"]) if row["output_dir"] is not None else None,
            method=str(row["method"]),
            user_agent=str(row["user_agent"]) if row["user_agent"] is not None else None,
            referer=str(row["referer"]) if row["referer"] is not None else None,
            headers={str(k): str(v) for k, v in headers_data.items()},
            cookies_from_browser=str(row["cookies_from_browser"])
            if row["cookies_from_browser"] is not None
            else None,
            allow_playlist=bool(row["allow_playlist"]),
            max_items=int(row["max_items"]) if row["max_items"] is not None else None,
            timeout_seconds=int(row["timeout_seconds"]),
            ffmpeg_binary=str(row["ffmpeg_binary"]),
            created_at=str(row["created_at"]),
            started_at=str(row["started_at"]) if row["started_at"] is not None else None,
            finished_at=str(row["finished_at"]) if row["finished_at"] is not None else None,
            updated_at=str(row["updated_at"]),
        )

    def _row_to_subscription(self, row: sqlite3.Row) -> SubscriptionRecord:
        return SubscriptionRecord(
            id=int(row["id"]),
            source_url=str(row["source_url"]),
            profile_id=int(row["profile_id"]) if row["profile_id"] is not None else None,
            interval_minutes=int(row["interval_minutes"]),
            last_checked_at=str(row["last_checked_at"]) if row["last_checked_at"] is not None else None,
            enabled=bool(row["enabled"]),
            created_at=str(row["created_at"]),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()
