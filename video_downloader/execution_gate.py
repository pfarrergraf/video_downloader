"""Thread-safe admission gate for queue claims.

Android must not begin network/file transfer work until its dataSync foreground
service has successfully entered foreground state.  Other deployments don't
need that lifecycle handshake and use an always-open gate.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import JobRecord
    from .queue_store import QueueStore


class ExecutionGate:
    """Serialize gate transitions with the actual pending -> in_progress claim."""

    def __init__(self, *, initially_open: bool = True) -> None:
        self._condition = threading.Condition()
        self._open = bool(initially_open)

    @property
    def is_open(self) -> bool:
        with self._condition:
            return self._open

    def open(self) -> None:
        with self._condition:
            self._open = True
            self._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            self._open = False

    def claim_next_job(self, store: QueueStore, *, stop: threading.Event) -> JobRecord | None:
        """Wait until admitted, then claim while a close cannot interleave.

        Holding the condition lock across ``claim_next_job`` makes "close the
        gate" and "pending -> in_progress" a single synchronization contract.
        A transfer which was already claimed is cancelled cooperatively by the
        existing timeout/cancel path; closing the gate prevents every later
        claim, including retries and recovered/requeued jobs.
        """
        with self._condition:
            self._condition.wait_for(lambda: self._open or stop.is_set(), timeout=2.0)
            if stop.is_set() or not self._open:
                return None
            return store.claim_next_job()

