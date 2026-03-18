from __future__ import annotations

from typing import Iterable

try:
    from textual.app import App, ComposeResult
    from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane
except ImportError as exc:  # pragma: no cover - import guard for optional dependency
    raise RuntimeError(
        "Textual is not installed. Install dependencies with `uv sync` to use `classydl tui`."
    ) from exc

from .models import DownloadProfile, JobRecord, QueueEvent, SubscriptionRecord
from .queue_store import QueueStore


class ClassyDlTui(App[None]):
    CSS = """
    Screen {
        layout: vertical;
    }
    TabbedContent {
        height: 1fr;
    }
    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("c", "cancel_selected", "Cancel"),
        ("p", "pause_selected", "Pause"),
        ("u", "resume_selected", "Resume"),
        ("y", "retry_selected", "Retry"),
        ("[", "priority_up", "Priority +"),
        ("]", "priority_down", "Priority -"),
    ]

    def __init__(self, store: QueueStore) -> None:
        super().__init__()
        self.store = store

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "ClassyDL TUI - q quit, r refresh, c cancel, p pause, u resume, y retry, [ / ] reprioritize"
        )
        with TabbedContent(initial="queue"):
            with TabPane("Queue", id="queue"):
                yield DataTable(id="queue_table")
            with TabPane("Paused", id="paused"):
                yield DataTable(id="paused_table")
            with TabPane("Active", id="active"):
                yield DataTable(id="active_table")
            with TabPane("Completed", id="completed"):
                yield DataTable(id="completed_table")
            with TabPane("Failed", id="failed"):
                yield DataTable(id="failed_table")
            with TabPane("Subscriptions", id="subscriptions"):
                yield DataTable(id="subscriptions_table")
            with TabPane("Profiles", id="profiles"):
                yield DataTable(id="profiles_table")
            with TabPane("Logs", id="logs"):
                yield DataTable(id="logs_table")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_all()
        self.set_interval(5, self._refresh_all)

    def action_refresh(self) -> None:
        self._refresh_all()

    def action_cancel_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        if self.store.mark_job_cancelled(job_id):
            self.notify(f"Cancelled job #{job_id}")
        else:
            self.notify(f"Could not cancel job #{job_id}", severity="warning")
        self._refresh_all()

    def action_pause_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        if self.store.pause_job(job_id):
            self.notify(f"Paused job #{job_id}")
        else:
            self.notify(f"Only pending jobs can be paused (job #{job_id})", severity="warning")
        self._refresh_all()

    def action_resume_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        if self.store.resume_job(job_id):
            self.notify(f"Resumed job #{job_id}")
        else:
            self.notify(f"Only paused jobs can be resumed (job #{job_id})", severity="warning")
        self._refresh_all()

    def action_retry_selected(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        new_job_id = self.store.retry_job(job_id)
        if new_job_id is None:
            self.notify(f"Retry not allowed for job #{job_id}", severity="warning")
        else:
            self.notify(f"Retried job #{job_id} as #{new_job_id}")
        self._refresh_all()

    def action_priority_up(self) -> None:
        self._change_priority(delta=-10)

    def action_priority_down(self) -> None:
        self._change_priority(delta=10)

    def _change_priority(self, delta: int) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return

        job = self.store.get_job(job_id)
        if job is None:
            self.notify(f"Job not found: #{job_id}", severity="warning")
            return

        target_priority = max(1, job.priority + delta)
        if self.store.reprioritize_job(job_id, target_priority):
            self.notify(f"Job #{job_id} priority set to {target_priority}")
        else:
            self.notify(f"Only pending/paused jobs can be reprioritized (job #{job_id})", severity="warning")
        self._refresh_all()

    def _refresh_all(self) -> None:
        self._render_jobs("queue_table", self.store.list_jobs(status="pending", limit=200))
        self._render_jobs("paused_table", self.store.list_jobs(status="paused", limit=200))
        self._render_jobs("active_table", self.store.list_jobs(status="in_progress", limit=200))
        self._render_jobs("completed_table", self.store.list_history(status="completed", limit=200))
        self._render_jobs("failed_table", self.store.list_history(status="failed", limit=200))
        self._render_subscriptions(self.store.list_subscriptions())
        self._render_profiles(self.store.list_profiles())
        self._render_events(self.store.list_events(limit=200))

    def _active_job_table_id(self) -> str | None:
        tabbed = self.query_one(TabbedContent)
        mapping = {
            "queue": "queue_table",
            "paused": "paused_table",
            "active": "active_table",
            "completed": "completed_table",
            "failed": "failed_table",
        }
        return mapping.get(tabbed.active)

    def _selected_job_id(self) -> int | None:
        table_id = self._active_job_table_id()
        if table_id is None:
            self.notify("Switch to a jobs tab first", severity="warning")
            return None

        table = self.query_one(f"#{table_id}", DataTable)
        if table.row_count == 0:
            self.notify("No rows in current table", severity="warning")
            return None

        row_index = table.cursor_row
        if row_index is None or row_index < 0 or row_index >= table.row_count:
            row_index = 0

        try:
            row = table.get_row_at(row_index)
            return int(str(row[0]))
        except Exception:
            self.notify("Unable to read selected row", severity="error")
            return None

    def _render_jobs(self, table_id: str, jobs: Iterable[JobRecord]) -> None:
        table = self.query_one(f"#{table_id}", DataTable)
        table.clear(columns=True)
        table.add_columns("id", "status", "attempt", "priority", "source", "profile", "updated")
        for job in jobs:
            profile_id = str(job.profile_id) if job.profile_id is not None else "-"
            table.add_row(
                str(job.id),
                job.status,
                f"{job.attempt}/{job.max_attempts}",
                str(job.priority),
                job.source,
                profile_id,
                job.updated_at,
            )

    def _render_subscriptions(self, rows: Iterable[SubscriptionRecord]) -> None:
        table = self.query_one("#subscriptions_table", DataTable)
        table.clear(columns=True)
        table.add_columns("id", "url", "profile", "interval", "last checked", "enabled")
        for row in rows:
            profile_id = str(row.profile_id) if row.profile_id is not None else "default"
            table.add_row(
                str(row.id),
                row.source_url,
                profile_id,
                str(row.interval_minutes),
                row.last_checked_at or "never",
                "yes" if row.enabled else "no",
            )

    def _render_profiles(self, rows: Iterable[DownloadProfile]) -> None:
        table = self.query_one("#profiles_table", DataTable)
        table.clear(columns=True)
        table.add_columns("id", "name", "format", "audio only", "subs", "aria2")
        for row in rows:
            table.add_row(
                str(row.id or "-"),
                row.name,
                row.format_selector,
                "yes" if row.audio_only else "no",
                row.subtitle_langs or "-",
                "yes" if row.use_aria2 else "no",
            )

    def _render_events(self, rows: Iterable[QueueEvent]) -> None:
        table = self.query_one("#logs_table", DataTable)
        table.clear(columns=True)
        table.add_columns("time", "level", "job", "message")
        for row in rows:
            table.add_row(row.created_at, row.level, str(row.job_id or "-"), row.message)


def run_tui(store: QueueStore) -> None:
    app = ClassyDlTui(store=store)
    app.run()
