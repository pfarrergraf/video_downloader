"""Maps raw downloader failures to a small, stable error-code taxonomy.

The web UI translates these codes into friendly, localized messages
(``app.errors.<code>`` in the i18n files) instead of showing users raw
yt-dlp/requests exception text. The queue runner also keys its retry
policy off them (a private video will never succeed, so retrying it just
wastes battery and quota).

The regex tables below match known upstream message fragments. yt-dlp's
wording changes over time — when a pattern stops matching, the failure
degrades to ``unknown`` (today's behavior), never to a wrong code. Keep
patterns lowercase; matching is case-insensitive via ``str.lower()``.
"""

from __future__ import annotations

ERR_NETWORK_OFFLINE = "network_offline"
ERR_GEO_BLOCKED = "geo_blocked"
ERR_LOGIN_REQUIRED = "login_required"
ERR_RATE_LIMITED = "rate_limited"
ERR_VIDEO_UNAVAILABLE = "video_unavailable"
ERR_ENGINE_OUTDATED = "engine_outdated"
ERR_DISK_FULL = "disk_full"
ERR_STALLED = "stalled"
ERR_UNSUPPORTED_URL = "unsupported_url"
ERR_UNKNOWN = "unknown"

ALL_ERROR_CODES = (
    ERR_NETWORK_OFFLINE,
    ERR_GEO_BLOCKED,
    ERR_LOGIN_REQUIRED,
    ERR_RATE_LIMITED,
    ERR_VIDEO_UNAVAILABLE,
    ERR_ENGINE_OUTDATED,
    ERR_DISK_FULL,
    ERR_STALLED,
    ERR_UNSUPPORTED_URL,
    ERR_UNKNOWN,
)

# Ordered: the first matching bucket wins. Order matters where fragments
# overlap — e.g. "sign in to confirm you're not a bot" is an extractor/bot
# check (fixable by updating yt-dlp), while "sign in to confirm your age"
# is an account requirement (not fixable by an engine update), so the
# age/login bucket must be checked first.
_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        ERR_DISK_FULL,
        ("no space left on device", "errno 28", "disk full"),
    ),
    (
        ERR_NETWORK_OFFLINE,
        (
            "getaddrinfo failed",
            "name or service not known",
            "temporary failure in name resolution",
            "network is unreachable",
            "connection refused",
            "failed to establish a new connection",
            "nodename nor servname",
            "no address associated with hostname",
        ),
    ),
    (
        ERR_RATE_LIMITED,
        ("http error 429", "rate-limit reached", "rate limit", "too many requests"),
    ),
    (
        ERR_GEO_BLOCKED,
        (
            "not available in your country",
            "geo restrict",
            "geo-restrict",
            "blocked it in your country",
            "not made this video available in your",
        ),
    ),
    (
        ERR_LOGIN_REQUIRED,
        (
            "sign in to confirm your age",
            "age-restricted",
            "age restricted",
            "private video",
            "this video is private",
            "login required",
            "log in or sign up",
            "requested content is not available",  # Instagram's login-wall phrasing
            "use --cookies",
            "account cookies",
            "only available for registered users",
            "join this channel",
        ),
    ),
    (
        ERR_VIDEO_UNAVAILABLE,
        (
            "video unavailable",
            "this video is unavailable",
            "has been removed",
            "no longer available",
            "account associated with this video has been terminated",
            "http error 404",
            "content isn't available",
            "video has been taken down",
        ),
    ),
    (
        ERR_ENGINE_OUTDATED,
        (
            # Classic signatures of "the site changed and yt-dlp needs an
            # update" — the fix is a newer extractor, not user action.
            "sign in to confirm you're not a bot",
            "sign in to confirm you’re not a bot",
            "unable to extract",
            "could not extract",
            "unable to download webpage: http error 403",
            "http error 403",
            "nsig extraction failed",
            "player = ",
            "some formats may be missing",
            "confirm you are human",
        ),
    ),
    (
        ERR_STALLED,
        ("stalled", "download timed out with no progress"),
    ),
    (
        ERR_UNSUPPORTED_URL,
        ("unsupported url", "is not a valid url", "no media found"),
    ),
)


def classify_error(error: BaseException | str | None) -> str | None:
    """Return the error code for a failure message, or ``None`` for no error.

    Accepts either an exception (its ``str()`` is used, plus ``errno`` for
    OSError disk-full detection) or the already-stringified error stored on
    a job row.
    """
    if error is None:
        return None
    if isinstance(error, BaseException):
        errno = getattr(error, "errno", None)
        if errno == 28:  # ENOSPC
            return ERR_DISK_FULL
        text = str(error)
    else:
        text = error
    if not text.strip():
        return None
    lowered = text.lower()
    for code, fragments in _PATTERNS:
        if any(fragment in lowered for fragment in fragments):
            return code
    return ERR_UNKNOWN
