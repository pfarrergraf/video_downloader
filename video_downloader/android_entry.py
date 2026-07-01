"""Single entry point Chaquopy calls from Kotlin to start the web server.

Kept intentionally tiny and string/int-only in its signature so the call from the
Android side (com.chaquo.python's dynamic PyObject.callAttr) stays simple — no need
to construct QueueStore/Path objects from the Kotlin side.
"""

from __future__ import annotations

from pathlib import Path

from .queue_store import QueueStore
from .web.server import run_server


def start(
    data_dir: str,
    output_dir: str,
    password: str,
    port: int,
    ffmpeg_binary: str = "ffmpeg",
) -> None:
    store = QueueStore(Path(data_dir) / "state.db")
    store.init()
    run_server(
        store=store,
        output_dir=Path(output_dir),
        password=password,
        host="127.0.0.1",
        port=port,
        workers=2,
        ffmpeg_binary=ffmpeg_binary,
    )
