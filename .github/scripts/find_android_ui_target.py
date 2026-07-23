#!/usr/bin/env python3
"""Select the next safe UI target for the Android share-intent smoke test."""

from __future__ import annotations

from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


def _center(bounds: str) -> tuple[int, int] | None:
    values = [int(value) for value in re.findall(r"\d+", bounds)]
    if len(values) != 4:
        return None
    x1, y1, x2, y2 = values
    return (x1 + x2) // 2, (y1 + y2) // 2


def find_target(xml: str) -> str:
    """Return ``DISMISS x y``, ``x y``, or an empty string."""

    all_nodes = list(ET.fromstring(xml).iter("node"))

    # The hosted emulator occasionally lets Pixel Launcher ANR while our app
    # is in the foreground. Its system dialog covers DownloadThat's picker.
    # Dismiss only an unrelated launcher ANR; an ANR naming DownloadThat stays
    # visible and correctly fails the test.
    titles = [
        node.attrib.get("text", "")
        for node in all_nodes
        if node.attrib.get("resource-id") == "android:id/alertTitle"
    ]
    if any("Launcher" in title and "isn't responding" in title for title in titles):
        close_button = next(
            (
                node
                for node in all_nodes
                if node.attrib.get("resource-id") == "android:id/aerr_close"
            ),
            None,
        )
        if close_button is not None:
            center = _center(close_button.attrib.get("bounds", ""))
            if center:
                return f"DISMISS {center[0]} {center[1]}"

    video_targets = [
        (node, _center(node.attrib.get("bounds", "")))
        for node in all_nodes
        if "Video" in node.attrib.get("text", "")
    ]
    centers = [
        (node, center) for node, center in video_targets if center is not None
    ]

    # A single match is the persistent home-screen kind toggle. The picker
    # adds a second, lower match; choose that lower button.
    if len(centers) >= 2:
        _, center = max(centers, key=lambda item: item[1][1])
        return f"{center[0]} {center[1]}"
    return ""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: find_android_ui_target.py WINDOW_DUMP_XML", file=sys.stderr)
        return 2
    print(find_target(Path(sys.argv[1]).read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
