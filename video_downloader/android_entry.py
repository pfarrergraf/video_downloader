"""Single entry point Chaquopy calls from Kotlin to start the web server.

Kept intentionally tiny and string/int-only in its signature so the call from the
Android side (com.chaquo.python's dynamic PyObject.callAttr) stays simple — no need
to construct QueueStore/Path objects from the Kotlin side.
"""

from __future__ import annotations

import mimetypes
import threading
import traceback
from pathlib import Path

from .models import JOB_STATUS_COMPLETED
from .queue_store import QueueStore
from .web.server import run_server

_PUBLISH_MARKER_SUFFIX = ".mediastore-published"
_PUBLISH_POLL_SECONDS = 3.0


def _already_published(path: Path) -> bool:
    return Path(str(path) + _PUBLISH_MARKER_SUFFIX).exists()


def _mark_published(path: Path) -> None:
    Path(str(path) + _PUBLISH_MARKER_SUFFIX).touch()


def _publish_file_to_downloads(path: Path) -> None:
    """Best-effort copy of a finished download into Android's shared Downloads
    collection (MediaStore) so it shows up in the stock Files/Downloads app —
    the app's own external-files-dir copy (see MainActivity.kt) is technically
    reachable but not surfaced anywhere near as prominently.

    Any failure here is logged and swallowed: the file already exists safely
    in the app's own storage regardless of whether this extra publish step
    succeeds, so this must never be allowed to affect the download itself.
    """
    try:
        from java import jclass  # type: ignore[import-not-found]
    except ImportError:
        return  # not running under Chaquopy (Termux/desktop/CLI) — nothing to do here

    try:
        build = jclass("android.os.Build")
        if build.VERSION.SDK_INT < 29:
            # The MediaStore Downloads collection was added in API 29 (Q).
            # Older devices only get the external-files-dir copy from 3a.
            return

        python_class = jclass("com.chaquo.python.Python")
        context = python_class.getPlatform().getApplication()
        resolver = context.getContentResolver()

        media_store_downloads = jclass("android.provider.MediaStore$Downloads")
        content_values_class = jclass("android.content.ContentValues")

        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

        values = content_values_class()
        values.put("_display_name", path.name)
        values.put("mime_type", mime_type)
        values.put("is_pending", 1)

        uri = resolver.insert(media_store_downloads.EXTERNAL_CONTENT_URI, values)
        if uri is None:
            return

        out_stream = resolver.openOutputStream(uri)
        try:
            with path.open("rb") as src:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    out_stream.write(chunk)
        finally:
            out_stream.close()

        done_values = content_values_class()
        done_values.put("is_pending", 0)
        resolver.update(uri, done_values, None, None)
    except Exception:
        traceback.print_exc()


def _run_downloads_publisher(store: QueueStore) -> None:
    while True:
        try:
            for job in store.list_jobs(status=JOB_STATUS_COMPLETED, limit=200):
                for file_path in store.list_job_files(job.id):
                    path = Path(file_path)
                    if _already_published(path):
                        continue
                    _publish_file_to_downloads(path)
                    _mark_published(path)
        except Exception:
            traceback.print_exc()
        threading.Event().wait(_PUBLISH_POLL_SECONDS)


def start(
    data_dir: str,
    output_dir: str,
    password: str,
    port: int,
    ffmpeg_binary: str = "ffmpeg",
) -> None:
    store = QueueStore(Path(data_dir) / "state.db")
    store.init()

    threading.Thread(
        target=_run_downloads_publisher,
        args=(store,),
        daemon=True,
        name="classydl-downloads-publisher",
    ).start()

    run_server(
        store=store,
        output_dir=Path(output_dir),
        password=password,
        host="127.0.0.1",
        port=port,
        workers=2,
        ffmpeg_binary=ffmpeg_binary,
    )
