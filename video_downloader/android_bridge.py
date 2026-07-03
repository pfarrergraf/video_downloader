"""Android-only file operations, reached via Chaquopy's `java` module.

Mirrors the guard pattern already used by android_entry.py's MediaStore
publisher: every function here is a no-op (returns False) when not running
under Chaquopy, so this module can be imported unconditionally from
web/server.py without breaking Termux/desktop/CLI use.
"""

from __future__ import annotations

import mimetypes
import traceback
from pathlib import Path

FILE_PROVIDER_AUTHORITY = "de.classydl.app.fileprovider"


def _application_context():
    from java import jclass  # type: ignore[import-not-found]

    python_class = jclass("com.chaquo.python.Python")
    return python_class.getPlatform().getApplication()


def open_file(path: Path) -> bool:
    """Fire an ACTION_VIEW intent so the device's default app opens `path`.

    Uses a FileProvider content:// URI rather than a raw file:// one: apps
    targeting API 24+ get a FileUriExposedException handing another app a
    file:// Uri for content outside its own package.
    """
    try:
        from java import jclass  # type: ignore[import-not-found]
    except ImportError:
        return False  # not running under Chaquopy (Termux/desktop/CLI)

    try:
        if not path.is_file():
            return False
        context = _application_context()

        file_provider = jclass("androidx.core.content.FileProvider")
        java_file = jclass("java.io.File")(str(path))
        uri = file_provider.getUriForFile(context, FILE_PROVIDER_AUTHORITY, java_file)

        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        intent_class = jclass("android.content.Intent")
        intent = intent_class(intent_class.ACTION_VIEW)
        intent.setDataAndType(uri, mime_type)
        # NEW_TASK: required because we're starting an Activity from the
        # Application context, not from an Activity context.
        # GRANT_READ_URI_PERMISSION: the receiving app has no other
        # permission to read a FileProvider Uri that isn't its own.
        intent.addFlags(intent_class.FLAG_ACTIVITY_NEW_TASK | intent_class.FLAG_GRANT_READ_URI_PERMISSION)

        context.startActivity(intent)
        return True
    except Exception:
        traceback.print_exc()
        return False


def open_folder(path: Path) -> bool:
    """Fire an ACTION_VIEW intent asking a file manager to show `path`'s
    parent directory.

    Android has no first-class "show this folder" API — this relies on the
    same "resource/folder" MIME-type trick most file managers (stock AOSP,
    Files by Google, Samsung My Files) recognize. Not universal, so this is
    deliberately best-effort: on a device with no app that understands it,
    startActivity raises ActivityNotFoundException and this just returns
    False instead of crashing.
    """
    try:
        from java import jclass  # type: ignore[import-not-found]
    except ImportError:
        return False  # not running under Chaquopy (Termux/desktop/CLI)

    try:
        directory = path if path.is_dir() else path.parent
        if not directory.is_dir():
            return False
        context = _application_context()

        file_provider = jclass("androidx.core.content.FileProvider")
        java_file = jclass("java.io.File")(str(directory))
        uri = file_provider.getUriForFile(context, FILE_PROVIDER_AUTHORITY, java_file)

        intent_class = jclass("android.content.Intent")
        intent = intent_class(intent_class.ACTION_VIEW)
        intent.setDataAndType(uri, "resource/folder")
        intent.addFlags(intent_class.FLAG_ACTIVITY_NEW_TASK | intent_class.FLAG_GRANT_READ_URI_PERMISSION)

        context.startActivity(intent)
        return True
    except Exception:
        traceback.print_exc()
        return False


def share_file(path: Path) -> bool:
    """Fire an ACTION_SEND intent so the user can forward `path` via the
    system share sheet (Bluetooth, messaging apps, email, etc.).
    """
    try:
        from java import jclass  # type: ignore[import-not-found]
    except ImportError:
        return False  # not running under Chaquopy (Termux/desktop/CLI)

    try:
        if not path.is_file():
            return False
        context = _application_context()

        file_provider = jclass("androidx.core.content.FileProvider")
        java_file = jclass("java.io.File")(str(path))
        uri = file_provider.getUriForFile(context, FILE_PROVIDER_AUTHORITY, java_file)

        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        intent_class = jclass("android.content.Intent")
        send_intent = intent_class(intent_class.ACTION_SEND)
        send_intent.setType(mime_type)
        send_intent.putExtra(intent_class.EXTRA_STREAM, uri)
        send_intent.addFlags(intent_class.FLAG_GRANT_READ_URI_PERMISSION)

        chooser = intent_class.createChooser(send_intent, None)
        chooser.addFlags(intent_class.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(chooser)
        return True
    except Exception:
        traceback.print_exc()
        return False


def export_file(path: Path, tree_uri: str) -> bool:
    """Copy `path` into a user-chosen SAF directory tree (see MainActivity's
    folder picker, which persists `tree_uri` via set_export_folder()).

    Best-effort: any failure here must never affect the download itself,
    which already exists safely in the app's own storage regardless.
    """
    try:
        from java import jclass  # type: ignore[import-not-found]
    except ImportError:
        return False

    try:
        if not path.is_file():
            return False
        context = _application_context()
        uri_class = jclass("android.net.Uri")
        parsed_tree_uri = uri_class.parse(tree_uri)

        document_file_class = jclass("androidx.documentfile.provider.DocumentFile")
        tree_dir = document_file_class.fromTreeUri(context, parsed_tree_uri)
        if tree_dir is None or not tree_dir.canWrite():
            return False

        # Overwrite semantics: drop any earlier export of the same filename
        # first, otherwise SAF's createFile silently appends "(1)" etc. and
        # re-exporting the same job would keep piling up duplicates. If the
        # delete itself fails (transient SAF hiccup, revoked permission),
        # bail out instead of creating a same-named duplicate next to a file
        # that's still there - the caller retries this on the next poll.
        existing = tree_dir.findFile(path.name)
        if existing is not None and not existing.delete():
            return False

        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        new_file = tree_dir.createFile(mime_type, path.name)
        if new_file is None:
            return False

        resolver = context.getContentResolver()
        out_stream = resolver.openOutputStream(new_file.getUri())
        try:
            with path.open("rb") as src:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    out_stream.write(chunk)
        finally:
            out_stream.close()
        return True
    except Exception:
        traceback.print_exc()
        return False
