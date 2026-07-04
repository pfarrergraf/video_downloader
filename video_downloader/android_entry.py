"""Single entry point Chaquopy calls from Kotlin to start the web server.

Kept intentionally tiny and string/int-only in its signature so the call from the
Android side (com.chaquo.python's dynamic PyObject.callAttr) stays simple — no need
to construct QueueStore/Path objects from the Kotlin side.
"""

from __future__ import annotations

import os

# Must happen before anything below imports requests/yt_dlp/urllib and opens an
# HTTPS connection: Android has no OpenSSL system CA store at the filesystem
# paths Python's ssl module checks by default (unlike desktop Linux/Termux), so
# every TLS handshake fails with a certificate-verify error until something
# points it at a real bundle. Setting SSL_CERT_FILE is honored by
# ssl.create_default_context()/load_default_certs() as an override for the
# compiled-in default. Harmless (a no-op override) on platforms that already
# have a working system CA store, so this isn't gated to Android specifically.
try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

import mimetypes
import threading
import traceback
from pathlib import Path

from . import android_bridge
from .licensing import LicenseManager
from .models import JOB_STATUS_COMPLETED
from .queue_store import QueueStore
from .web.server import run_server

# Set by start() and read by set_export_folder() — MainActivity's SAF folder
# picker calls back into this same running store instance (via Chaquopy)
# rather than opening a second sqlite connection to the same file.
_current_store: QueueStore | None = None

_PUBLISH_MARKER_SUFFIX = ".mediastore-published"
_EXPORT_MARKER_SUFFIX = ".folder-exported"
# Kept short: each poll is just a cheap local sqlite query (store.list_jobs),
# and a long interval here directly shows up as a delay between "download
# completed" and "file visible in the stock Files app" from the user's
# perspective — worth optimizing for responsiveness over marginal battery
# cost. Also narrows the race a test observed: CI's download_pipeline_test.sh
# checked the MediaStore Downloads collection ~1.6s after job completion,
# which used to be well inside the previous 3s gap and could report a false
# "not found" even though nothing was actually broken.
_PUBLISH_POLL_SECONDS = 1.0


def _already_published(path: Path) -> bool:
    return Path(str(path) + _PUBLISH_MARKER_SUFFIX).exists()


def _mark_published(path: Path) -> None:
    Path(str(path) + _PUBLISH_MARKER_SUFFIX).touch()


def _already_exported(path: Path) -> bool:
    return Path(str(path) + _EXPORT_MARKER_SUFFIX).exists()


def _mark_exported(path: Path) -> None:
    Path(str(path) + _EXPORT_MARKER_SUFFIX).touch()


def set_export_folder(uri: str, label: str) -> None:
    """Called from MainActivity.kt after the user picks a folder via the
    Storage Access Framework. `uri` is a persisted-permission tree Uri
    (opaque to Python); `label` is a human-readable name for display only.
    """
    if _current_store is not None:
        _current_store.set_setting("export_folder_uri", uri)
        _current_store.set_setting("export_folder_label", label)


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
        from java import jclass, jint  # type: ignore[import-not-found]
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
        # A bare Python int is ambiguous to Chaquopy here: ContentValues.put
        # is overloaded for Byte/Short/Integer/Long (among others), and
        # nothing about a plain int says which one to pick — it raised
        # "ContentValues.put is ambiguous for arguments (str, int)" every
        # single time, silently swallowed by this function's broad except
        # below, so the MediaStore publish step had never actually worked.
        # jint() disambiguates by explicitly typing it as a Java int.
        values.put("is_pending", jint(1))

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
        done_values.put("is_pending", jint(0))
        resolver.update(uri, done_values, None, None)
    except Exception:
        traceback.print_exc()


def _run_downloads_publisher(store: QueueStore) -> None:
    while True:
        try:
            export_uri = store.get_setting("export_folder_uri")
            for job in store.list_jobs(status=JOB_STATUS_COMPLETED, limit=200):
                for file_path in store.list_job_files(job.id):
                    path = Path(file_path)
                    if not _already_published(path):
                        _publish_file_to_downloads(path)
                        _mark_published(path)
                    if export_uri and not _already_exported(path):
                        # Unlike _publish_file_to_downloads, only mark on success:
                        # a revoked/unmounted SAF permission should keep retrying
                        # every poll rather than silently give up on this file.
                        if android_bridge.export_file(path, export_uri):
                            _mark_exported(path)
        except Exception:
            traceback.print_exc()
        threading.Event().wait(_PUBLISH_POLL_SECONDS)


def start(
    data_dir: str,
    output_dir: str,
    password: str,
    port: int,
    ffmpeg_binary: str = "ffmpeg",
    license_api_base: str = "",
    app_version: str = "",
) -> None:
    global _current_store
    store = QueueStore(Path(data_dir) / "state.db")
    store.init()
    _current_store = store

    threading.Thread(
        target=_run_downloads_publisher,
        args=(store,),
        daemon=True,
        name="classydl-downloads-publisher",
    ).start()

    # Empty string (not None — Chaquopy's Kotlin->Python call is simpler with
    # plain str args, see the module docstring) means licensing is off:
    # Termux/desktop callers never pass this, and every request is free to
    # use the full "default" profile — see licensing.py and web/server.py's
    # _resolve_profile.
    license_manager = LicenseManager(Path(data_dir) / "license.json", license_api_base) if license_api_base else None

    run_server(
        store=store,
        output_dir=Path(output_dir),
        password=password,
        host="127.0.0.1",
        port=port,
        workers=2,
        ffmpeg_binary=ffmpeg_binary,
        license_manager=license_manager,
        app_version=app_version,
    )
