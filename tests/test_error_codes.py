from __future__ import annotations

import pytest

from video_downloader.errors import (
    ERR_DISK_FULL,
    ERR_ENGINE_OUTDATED,
    ERR_GEO_BLOCKED,
    ERR_LOGIN_REQUIRED,
    ERR_NETWORK_OFFLINE,
    ERR_RATE_LIMITED,
    ERR_STALLED,
    ERR_UNKNOWN,
    ERR_UNSUPPORTED_URL,
    ERR_VIDEO_UNAVAILABLE,
    classify_error,
)

# Real-world message shapes, mostly verbatim from yt-dlp/requests output.
CASES = [
    ("ERROR: [youtube] abc: Video unavailable", ERR_VIDEO_UNAVAILABLE),
    ("ERROR: [youtube] abc: This video is no longer available", ERR_VIDEO_UNAVAILABLE),
    ("HTTP Error 404: Not Found", ERR_VIDEO_UNAVAILABLE),
    ("ERROR: [youtube] abc: Sign in to confirm you're not a bot", ERR_ENGINE_OUTDATED),
    ("ERROR: Unable to extract player version", ERR_ENGINE_OUTDATED),
    ("ERROR: unable to download webpage: HTTP Error 403: Forbidden", ERR_ENGINE_OUTDATED),
    ("nsig extraction failed: Some formats may be missing", ERR_ENGINE_OUTDATED),
    ("ERROR: [youtube] abc: Sign in to confirm your age", ERR_LOGIN_REQUIRED),
    ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access", ERR_LOGIN_REQUIRED),
    (
        "ERROR: [Instagram] abc: Requested content is not available, rate-limit reached or login required",
        # Both the login and rate-limit buckets match Instagram's combined
        # wording; rate_limited is checked first and is the actionable hint.
        ERR_RATE_LIMITED,
    ),
    ("ERROR: [generic] abc: HTTP Error 429: Too Many Requests", ERR_RATE_LIMITED),
    ("The uploader has not made this video available in your country", ERR_GEO_BLOCKED),
    ("urlopen error [Errno -2] Name or service not known", ERR_NETWORK_OFFLINE),
    ("Failed to establish a new connection: [Errno 111] Connection refused", ERR_NETWORK_OFFLINE),
    ("OSError: [Errno 28] No space left on device", ERR_DISK_FULL),
    ("ERROR: Unsupported URL: https://example.com/page", ERR_UNSUPPORTED_URL),
    ("Download stalled: no progress for 120s", ERR_STALLED),
    ("something entirely novel went wrong", ERR_UNKNOWN),
]


@pytest.mark.parametrize(("message", "expected"), CASES)
def test_classify_error_messages(message: str, expected: str) -> None:
    assert classify_error(message) == expected


def test_classify_error_none_and_blank() -> None:
    assert classify_error(None) is None
    assert classify_error("") is None
    assert classify_error("   ") is None


def test_classify_error_accepts_exceptions() -> None:
    assert classify_error(ValueError("Video unavailable")) == ERR_VIDEO_UNAVAILABLE
    enospc = OSError(28, "No space left on device")
    assert classify_error(enospc) == ERR_DISK_FULL


def test_age_gate_beats_engine_outdated() -> None:
    # "Sign in to confirm your age" must NOT be treated as a bot check —
    # an engine update can't fix an age gate.
    assert classify_error("Sign in to confirm your age") == ERR_LOGIN_REQUIRED
