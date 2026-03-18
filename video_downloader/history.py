from __future__ import annotations

from .models import JobRecord
from .queue_store import QueueStore


def list_history(store: QueueStore, status: str | None = None, limit: int = 200) -> list[JobRecord]:
    return store.list_history(status=status, limit=limit)


def retry_history_job(store: QueueStore, job_id: int) -> int | None:
    return store.retry_job(job_id)
