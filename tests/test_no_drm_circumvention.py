"""Guard: the app must never circumvent DRM / technical protection measures.

This is a legal invariant, not a style rule — providing a TPM-circumvention tool
is prohibited per se under s. 95a UrhG / Art. 6 InfoSoc Directive, regardless of
user intent (see security/DRM_CIRCUMVENTION_AUDIT.md). yt-dlp refuses DRM streams
by default; enabling allow_unplayable_formats or wiring in a decryptor would break
that. This test fails if anyone does.
"""

from __future__ import annotations

import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "video_downloader"

# Tool/keyword markers that would indicate active DRM/TPM circumvention.
FORBIDDEN_MARKERS = (
    "allow_unplayable_formats",
    "mp4decrypt",
    "bento4",
    "widevine",
    "playready",
    "fairplay",
    "clearkey",
)


def _python_sources() -> list[Path]:
    return list(PKG.rglob("*.py"))


def test_allow_unplayable_formats_is_never_enabled() -> None:
    # yt-dlp's default is False (refuse DRM). It must never be turned on.
    pattern = re.compile(r"allow_unplayable_formats")
    offenders = []
    for path in _python_sources():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(text):
            offenders.append(str(path.relative_to(PKG.parent)))
    assert not offenders, (
        "allow_unplayable_formats must not appear in the app (DRM invariant): "
        f"{offenders}"
    )


def test_no_decryption_tooling_referenced() -> None:
    offenders: list[str] = []
    for path in _python_sources():
        lowered = path.read_text(encoding="utf-8", errors="ignore").lower()
        for marker in FORBIDDEN_MARKERS:
            if marker == "allow_unplayable_formats":
                continue  # covered by the dedicated test above
            if marker in lowered:
                offenders.append(f"{path.relative_to(PKG.parent)}: {marker}")
    assert not offenders, (
        "DRM-circumvention tooling/keywords must not be referenced: " + "; ".join(offenders)
    )
