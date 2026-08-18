"""Reject repository material which leaks into the Android Chaquopy app zip."""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path


APP_IMY_PATH = "base/assets/chaquopy/app.imy"
ALLOWED_PREFIX = "video_downloader/"
# Python source and the local web UI are small. A substantially larger app.imy
# indicates that non-runtime checkout content was bundled by mistake.
MAX_APP_IMY_BYTES = 5 * 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("aab", type=Path)
    args = parser.parse_args()

    with zipfile.ZipFile(args.aab) as bundle:
        try:
            app_imy = bundle.read(APP_IMY_PATH)
        except KeyError:
            print(f"missing {APP_IMY_PATH}", file=sys.stderr)
            return 1

    if len(app_imy) > MAX_APP_IMY_BYTES:
        print(
            f"{APP_IMY_PATH} is {len(app_imy)} bytes; limit is {MAX_APP_IMY_BYTES}",
            file=sys.stderr,
        )
        return 1

    with zipfile.ZipFile(io.BytesIO(app_imy)) as app_zip:
        unexpected = sorted(
            entry.filename
            for entry in app_zip.infolist()
            if not entry.is_dir() and not entry.filename.startswith(ALLOWED_PREFIX)
        )
    if unexpected:
        print(
            "Android Python bundle contains non-runtime checkout files:\n"
            + "\n".join(unexpected[:20]),
            file=sys.stderr,
        )
        return 1

    print(f"Android Python bundle verified: {len(app_imy)} bytes, app sources only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
