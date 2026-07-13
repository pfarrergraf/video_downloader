"""Backend for the Gothic browser UI — standard library only.

This intentionally avoids FastAPI/uvicorn/pydantic: pydantic-core has no
prebuilt wheel for Termux (Android) and falls back to compiling a Rust
crate from source, which is slow and fragile on a phone. Using only the
stdlib http.server means this installs identically everywhere ClassyDL's
base dependencies already do — Termux, Docker, a VPS, Windows.
"""

from __future__ import annotations

import hmac
import json
import mimetypes
import re
import secrets
import shutil
import threading
import time
from datetime import UTC, datetime, timedelta
from http.client import responses as HTTP_REASONS
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from .. import android_bridge, engine_update
from ..errors import classify_error
from ..licensing import FREE_DAILY_DOWNLOAD_LIMIT, FREE_WINDOW_HOURS, LicenseManager
from ..models import (
    JOB_STATUS_CANCELLED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_IN_PROGRESS,
    JOB_STATUS_PENDING,
    DownloadProfile,
    JobRecord,
)
from ..queue_runner import QueueRunner
from ..queue_store import QueueStore
from ..scraper import SiteScraper, SsrfBlockedError
from ..utils import ensure_output_dir

STATIC_DIR = Path(__file__).parent / "static"
SESSION_COOKIE = "classydl_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 days
AUDIO_PROFILE_NAME = "web-audio"
# Default cap applied when the client doesn't send an explicit quality_height
# (older clients, or the UI's own "Auto" option) - the user asked for 4K as
# the default ceiling, not fully uncapped, so a single 8K/60fps source
# doesn't silently balloon a phone download.
DEFAULT_QUALITY_HEIGHT = 2160
ALLOWED_QUALITY_HEIGHTS = {240, 480, 720, 1080, 1440, 2160}
# Bump this to force every existing install to re-accept the terms overlay
# (see /api/settings) the next time it's materially changed - stored per
# install in QueueStore's settings table as "terms_accepted_version".
CURRENT_TERMS_VERSION = "2026-07"
# Statuses that count against the free tier's daily quota: an attempt that's
# running or succeeded uses up the day's download. Cancelled/failed jobs
# don't, so a user isn't punished for a source that didn't work out.
FREE_TIER_COUNTED_STATUSES = (JOB_STATUS_PENDING, JOB_STATUS_IN_PROGRESS, JOB_STATUS_COMPLETED)

QUEUE_CANCEL_RE = re.compile(r"^/api/queue/(\d+)/cancel$")
QUEUE_RETRY_RE = re.compile(r"^/api/queue/(\d+)/retry$")
QUEUE_DELETE_RE = re.compile(r"^/api/queue/(\d+)/delete$")
DOWNLOAD_RE = re.compile(r"^/api/download/(\d+)/([^/]+)$")

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")


class SessionStore:
    """In-memory session tokens — fine for a single-process personal deployment."""

    def __init__(self) -> None:
        self._tokens: dict[str, float] = {}
        self._lock = threading.Lock()

    def issue(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._tokens[token] = time.time() + SESSION_TTL_SECONDS
        return token

    def is_valid(self, token: str | None) -> bool:
        if not token:
            return False
        with self._lock:
            expires = self._tokens.get(token)
            if expires is None:
                return False
            if expires < time.time():
                del self._tokens[token]
                return False
            return True

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._tokens.pop(token, None)


# This server proxies arbitrary downloads behind a single shared password
# (see module docstring / CLAUDE.md) - without a lockout, anyone who can
# reach the port can try passwords indefinitely with no penalty.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 60


class LoginThrottle:
    """Per-source-IP failed-login lockout - in-memory, matches SessionStore's
    "fine for a single-process personal deployment" scope (a restart or a
    second process behind a load balancer would reset it, but that's not
    this project's deployment model)."""

    def __init__(self) -> None:
        self._failures: dict[str, tuple[int, float]] = {}  # ip -> (count, locked_until)
        self._lock = threading.Lock()

    def is_locked(self, ip: str) -> float:
        """Returns seconds remaining locked out, or 0 if not locked."""
        with self._lock:
            entry = self._failures.get(ip)
            if entry is None:
                return 0.0
            _, locked_until = entry
            remaining = locked_until - time.time()
            return remaining if remaining > 0 else 0.0

    def record_failure(self, ip: str) -> None:
        with self._lock:
            count, _ = self._failures.get(ip, (0, 0.0))
            count += 1
            locked_until = time.time() + LOGIN_LOCKOUT_SECONDS if count >= LOGIN_MAX_ATTEMPTS else 0.0
            self._failures[ip] = (count, locked_until)

    def record_success(self, ip: str) -> None:
        with self._lock:
            self._failures.pop(ip, None)


# The desktop launcher used to put the web password itself in the auto-login
# URL (?t=<password>), which leaks the long-lived secret into browser history,
# referrers, and extensions. Instead the launcher mints one of these: a
# single-use, short-lived token exchanged once for a session cookie.
AUTOLOGIN_TOKEN_TTL_SECONDS = 120


class AutoLoginTokens:
    """Single-use, short-lived tokens for the desktop auto-login handshake."""

    def __init__(self) -> None:
        self._tokens: dict[str, float] = {}
        self._lock = threading.Lock()

    def issue(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._tokens[token] = time.time() + AUTOLOGIN_TOKEN_TTL_SECONDS
        return token

    def consume(self, token: str | None) -> bool:
        """Redeem a token exactly once; False if unknown/expired/already used."""
        if not token:
            return False
        with self._lock:
            expires = self._tokens.pop(token, None)
            return expires is not None and expires >= time.time()


class ChangeBus:
    """Monotonic change counter + condition — the bridge between QueueStore's
    on_change hook (writer side) and /api/events' SSE loops (reader side)."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._seq = 0

    def notify(self) -> None:
        with self._cond:
            self._seq += 1
            self._cond.notify_all()

    def wait_for_change(self, last_seen: int, timeout: float) -> int:
        """Blocks until the sequence advances past last_seen (or timeout);
        returns the current sequence either way."""
        with self._cond:
            self._cond.wait_for(lambda: self._seq != last_seen, timeout=timeout)
            return self._seq


class BackgroundQueueWorker:
    """Continuously drains the download queue in a background thread."""

    # How often to reap week-old partial data of failed jobs.
    JANITOR_INTERVAL_SECONDS = 3600.0
    # Proactive daily engine check, so the app is usually already fixed
    # BEFORE the user hits a broken site (ensure_latest also runs reactively
    # on engine-outdated failures - see queue_runner).
    ENGINE_CHECK_INTERVAL_SECONDS = 24 * 3600.0

    def __init__(self, store: QueueStore, output_dir: Path, workers: int) -> None:
        self._store = store
        self._runner = QueueRunner(store=store, default_output_dir=output_dir)
        self._workers = workers
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="classydl-web-worker", daemon=True)
        self._last_janitor_run = 0.0
        self._last_engine_check = 0.0

    def start(self) -> None:
        # Jobs stranded as in_progress by a process kill (Android reclaims
        # the app without warning) go back to pending here - the one moment
        # it's provably safe, since this process hasn't started any worker
        # yet. Their partial files are still on disk, so they resume rather
        # than restart. Deliberately NOT in QueueStore.init(): CLI/tests open
        # stores without owning the queue, and a second process recovering
        # jobs a first process is actively working would corrupt state.
        recovered = self._store.recover_stale_in_progress()
        if recovered:
            self._store.append_event(
                None, "info", f"Recovered {recovered} interrupted download(s) after restart"
            )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            summary = self._runner.run(workers=self._workers)
            now = time.time()
            if now - self._last_janitor_run >= self.JANITOR_INTERVAL_SECONDS:
                self._last_janitor_run = now
                try:
                    self._runner.cleanup_stale_partials()
                except Exception:  # noqa: BLE001 - hygiene must never kill the drain loop
                    pass
            if now - self._last_engine_check >= self.ENGINE_CHECK_INTERVAL_SECONDS:
                self._last_engine_check = now
                if self._store.get_setting("engine_auto_update", "1") != "0":
                    try:
                        engine_update.ensure_latest()
                    except Exception:  # noqa: BLE001 - update failures never kill the drain loop
                        pass
            if summary.processed == 0:
                self._stop.wait(2.0)


def _resolve_profile(store: QueueStore, audio_only: bool) -> DownloadProfile:
    # Quality is the same for free and Pro — the free tier is rationed by
    # download count (see _recent_job_count), not by resolution.
    if not audio_only:
        return store.ensure_default_profile()
    existing = store.get_profile_by_name(AUDIO_PROFILE_NAME)
    if existing is not None:
        return existing
    return store.create_profile(
        DownloadProfile(id=None, name=AUDIO_PROFILE_NAME, format_selector="ba/b", audio_only=True)
    )


def _resolve_quality_height(body: dict[str, Any]) -> int | None:
    raw = body.get("quality_height")
    if raw is None:
        return DEFAULT_QUALITY_HEIGHT
    try:
        height = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_QUALITY_HEIGHT
    return height if height in ALLOWED_QUALITY_HEIGHTS else DEFAULT_QUALITY_HEIGHT


def _recent_job_count(store: QueueStore, *, within_hours: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(hours=within_hours)
    count = 0
    for status in FREE_TIER_COUNTED_STATUSES:
        for job in store.list_jobs(status=status, limit=200):
            try:
                created = datetime.fromisoformat(job.created_at)
            except ValueError:
                continue
            if created >= cutoff:
                count += 1
    return count


def _serialize_job(store: QueueStore, job: JobRecord) -> dict[str, Any]:
    files: list[dict[str, str]] = []
    if job.status == JOB_STATUS_COMPLETED:
        for path_str in store.list_job_files(job.id):
            path = Path(path_str)
            files.append(
                {
                    "filename": path.name,
                    "download_url": f"/api/download/{job.id}/{path.name}",
                }
            )
    return {
        "id": job.id,
        "source": job.source,
        "status": job.status,
        "attempt": job.attempt,
        "max_attempts": job.max_attempts,
        "error": job.error,
        # Prefer the code stored at failure time (queue_runner classified the
        # live exception); fall back to re-classifying the message for rows
        # written before the error_code column existed.
        "error_code": job.error_code or classify_error(job.error),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "files": files,
        "downloaded_bytes": job.downloaded_bytes,
        "total_bytes": job.total_bytes,
    }


class ClassyDLServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        store: QueueStore,
        output_dir: Path,
        password: str,
        workers: int,
        ffmpeg_binary: str = "ffmpeg",
        license_manager: LicenseManager | None = None,
        app_version: str = "",
        published_file_remover=None,
        secure_cookies: bool = False,
    ) -> None:
        super().__init__(address, ClassyDLRequestHandler)
        self.store = store
        self.output_dir = output_dir
        self.password = password
        # When True, session cookies carry the Secure flag - only correct
        # behind a TLS terminator (see _send_json). Default HTTP/loopback: off.
        self.secure_cookies = secure_cookies
        self.ffmpeg_binary = ffmpeg_binary
        self.license_manager = license_manager
        self.app_version = app_version
        # Optional best-effort hook (filename: str) -> None used by "delete
        # entry + file": on Android this removes the copy the downloads
        # publisher put into the system's shared Downloads collection
        # (MediaStore), which the server itself can't reach. None everywhere
        # else - desktop/Termux never make that extra copy.
        self.published_file_remover = published_file_remover
        self.sessions = SessionStore()
        self.login_throttle = LoginThrottle()
        self.autologin_tokens = AutoLoginTokens()
        self.worker = BackgroundQueueWorker(store=store, output_dir=output_dir, workers=workers)
        # SSE push plumbing: every job-state/progress write in the store
        # bumps the bus; each /api/events client thread waits on it. Bounded
        # because every SSE client holds one ThreadingHTTPServer thread.
        self.change_bus = ChangeBus()
        store.on_change = self.change_bus.notify
        self.sse_clients = 0
        self.sse_lock = threading.Lock()
        # Guards the free-tier quota check-then-act sequence in do_POST's
        # /api/queue handler - without it, concurrent requests on this
        # ThreadingHTTPServer can all read the same "used" count before any
        # of them commits a new job, letting a free-tier user queue more than
        # FREE_DAILY_DOWNLOAD_LIMIT downloads in a burst.
        self.quota_lock = threading.Lock()

    def issue_autologin_token(self) -> str:
        """Mint a single-use desktop auto-login token (see AutoLoginTokens)."""
        return self.autologin_tokens.issue()

    def start_background_worker(self) -> None:
        self.worker.start()

    def stop_background_worker(self) -> None:
        self.worker.stop()


class ClassyDLRequestHandler(BaseHTTPRequestHandler):
    server: ClassyDLServer  # type: ignore[assignment]
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter default logging
        pass

    # -- helpers ----------------------------------------------------------
    def _session_token(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def _authed(self) -> bool:
        return self.server.sessions.is_valid(self._session_token())

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    # Applied to every response. The SPA is fully self-contained (no external
    # CDN/font/script), so a strict CSP that only allows 'self' + inline
    # (the SPA hand-inlines its script/style) blocks any injected exfiltration
    # to a third-party host while keeping the page working. frame-ancestors
    # 'none' is the clickjacking control the old server lacked entirely.
    _SECURITY_CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )

    def _send_security_headers(self) -> None:
        """Emit the baseline hardening headers on every response.

        Must be called after send_response() and before end_headers(). Kept in
        one place so JSON, file, and SSE responses stay consistent.
        """
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", self._SECURITY_CSP)

    def _send_json(
        self,
        status: int,
        payload: dict[str, Any],
        *,
        set_cookie: str | None = None,
        delete_cookie: bool = False,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status, HTTP_REASONS.get(status, ""))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_security_headers()
        # `Secure` is opt-in (create_server(secure_cookies=True)): the default
        # deployment is plain HTTP on loopback, where a Secure cookie would be
        # silently dropped by the browser and break login. Operators who put
        # this behind a TLS terminator flip the flag on.
        secure = "; Secure" if getattr(self.server, "secure_cookies", False) else ""
        if set_cookie:
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={set_cookie}; Max-Age={SESSION_TTL_SECONDS}; HttpOnly; SameSite=Lax; Path=/{secure}",
            )
        if delete_cookie:
            self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; Max-Age=0; HttpOnly; SameSite=Lax; Path=/{secure}")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, *, download_name: str | None = None) -> None:
        # Streamed in chunks, never read whole into memory: downloads can be
        # multi-GB videos and this used to buffer the entire file per request.
        # Single-range requests get a proper 206 so the WebView's <video>
        # player (and browser download resume) can seek.
        try:
            file_size = path.stat().st_size
            file_obj = path.open("rb")
        except OSError:
            self._send_json(404, {"detail": "File no longer available"})
            return

        start = 0
        end = file_size - 1
        status = 200
        range_header = self.headers.get("Range", "")
        range_match = re.match(r"bytes=(\d*)-(\d*)$", range_header.strip()) if range_header else None
        if range_match and file_size > 0:
            raw_start, raw_end = range_match.groups()
            if raw_start:
                start = int(raw_start)
                if raw_end:
                    end = min(int(raw_end), file_size - 1)
            elif raw_end:
                # suffix form: last N bytes
                start = max(0, file_size - int(raw_end))
            if start >= file_size:
                file_obj.close()
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.send_header("Content-Length", "0")
                self._send_security_headers()
                self.end_headers()
                return
            status = 206

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        # The Android WebView's HTTP cache survives app updates (only wiped on
        # uninstall) and this server never sent a validator (ETag/Last-Modified)
        # for it to revalidate against, so without this a "successfully
        # updated" install could keep rendering whatever index.html/JS the
        # WebView had cached from a previous version.
        self.send_header("Cache-Control", "no-store")
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self._send_security_headers()
        self.end_headers()
        try:
            with file_obj:
                file_obj.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = file_obj.read(min(1024 * 256, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client went away mid-transfer - routine, not an error

    def _require_auth(self) -> bool:
        if not self._authed():
            self._send_json(401, {"detail": "Not authenticated"})
            return False
        return True

    # Max concurrent SSE clients: each holds one ThreadingHTTPServer thread
    # open for its whole lifetime. One local WebView needs exactly 1; a small
    # headroom covers a desktop browser tab or two alongside it.
    SSE_MAX_CLIENTS = 4
    SSE_PING_SECONDS = 15.0
    # Progress writes land ~2x/sec per job; batching pushes to at most one
    # every 250ms keeps the wire (and re-render) cost flat with many jobs.
    SSE_MIN_INTERVAL = 0.25

    def _serve_events(self) -> None:
        """Server-Sent Events stream: pushes the full /api/queue payload on
        every job change (close-delimited, so no chunked-encoding hand-rolling
        on BaseHTTPRequestHandler). The page falls back to polling if this
        errors — see index.html."""
        with self.server.sse_lock:
            if self.server.sse_clients >= self.SSE_MAX_CLIENTS:
                self._send_json(503, {"detail": "Too many event streams open"})
                return
            self.server.sse_clients += 1
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            # Explicit close: tells this handler (and the client) the stream
            # has no length and ends when the connection does.
            self.send_header("Connection", "close")
            self._send_security_headers()
            self.end_headers()

            bus = self.server.change_bus
            seq = -1  # deliberately behind: send one snapshot immediately
            while True:
                new_seq = bus.wait_for_change(seq, timeout=self.SSE_PING_SECONDS)
                if new_seq == seq:
                    # No change - comment line as keep-alive so dead
                    # connections surface as write errors.
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                seq = new_seq
                jobs = self.server.store.list_jobs(limit=200)
                payload = json.dumps(
                    {"jobs": [_serialize_job(self.server.store, job) for job in jobs]}
                )
                self.wfile.write(b"data: " + payload.encode("utf-8") + b"\n\n")
                self.wfile.flush()
                time.sleep(self.SSE_MIN_INTERVAL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # client disconnected - the normal way these streams end
        finally:
            with self.server.sse_lock:
                self.server.sse_clients -= 1

    def _static_path(self, url_path: str) -> Path | None:
        rel = unquote(url_path.lstrip("/")) or "index.html"
        base = STATIC_DIR.resolve()
        candidate = (base / rel).resolve()
        try:
            candidate.relative_to(base)
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    # -- routing ------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 - stdlib naming convention
        parts = urlsplit(self.path)
        path = parts.path
        query = parse_qs(parts.query)

        if path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return
        if path == "/api/me":
            self._send_json(200, {"authenticated": self._authed()})
            return
        if path == "/api/license":
            if not self._require_auth():
                return
            manager = self.server.license_manager
            if manager is None:
                self._send_json(200, {"configured": False})
                return
            state = manager.status()
            self._send_json(
                200,
                {
                    "configured": True,
                    "valid": state.is_pro,
                    "tier": state.tier,
                    "has_key": bool(state.key),
                    "device_allowed": state.device_allowed,
                },
            )
            return
        if path == "/api/queue":
            if not self._require_auth():
                return
            status = (query.get("status") or [None])[0]
            jobs = self.server.store.list_jobs(status=status, limit=200)
            self._send_json(200, {"jobs": [_serialize_job(self.server.store, job) for job in jobs]})
            return
        if path == "/api/events":
            if not self._require_auth():
                return
            self._serve_events()
            return
        if path == "/api/engine":
            if not self._require_auth():
                return
            state = engine_update.read_state()
            active = engine_update.active_version()
            latest = state.get("latest_known")
            self._send_json(
                200,
                {
                    "bundled_version": engine_update.bundled_version(),
                    "active_version": active,
                    "latest_known": latest,
                    "update_available": bool(
                        latest and active and engine_update.is_newer(latest, active)
                    ),
                    "last_check_at": state.get("last_check_at"),
                    "updating": engine_update.is_updating(),
                },
            )
            return
        if path == "/api/settings":
            if not self._require_auth():
                return
            store = self.server.store
            self._send_json(
                200,
                {
                    "language": store.get_setting("language", "auto"),
                    "export_folder_label": store.get_setting("export_folder_label"),
                    "terms_accepted": store.get_setting("terms_accepted_version") == CURRENT_TERMS_VERSION,
                    "app_version": self.server.app_version,
                    # Smart Mode: the UI persists the last choice so a repeat
                    # download is a single tap (no format/quality dialog).
                    "media_kind": store.get_setting("media_kind", "video"),
                    "quality_height": store.get_setting("quality_height", str(DEFAULT_QUALITY_HEIGHT)),
                    "theme": store.get_setting("theme", "auto"),
                    # Sent so the UI never hardcodes the free-tier number —
                    # the 3/5/1 copy drift this replaces came from exactly
                    # that (see i18n app.limit.body's {limit} placeholder).
                    "free_limit": FREE_DAILY_DOWNLOAD_LIMIT,
                    "free_window_hours": FREE_WINDOW_HOURS,
                },
            )
            return

        match = DOWNLOAD_RE.match(path)
        if match:
            if not self._require_auth():
                return
            job_id, filename = int(match.group(1)), unquote(match.group(2))
            for candidate in self.server.store.list_job_files(job_id):
                candidate_path = Path(candidate)
                if candidate_path.name == filename:
                    self._send_file(candidate_path, download_name=candidate_path.name)
                    return
            self._send_json(404, {"detail": "File not found for this job"})
            return

        static_path = self._static_path(path)
        if static_path is not None:
            self._send_file(static_path)
            return
        self._send_json(404, {"detail": "Not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming convention
        path = urlsplit(self.path).path

        if path == "/api/login":
            ip = self.client_address[0]
            remaining = self.server.login_throttle.is_locked(ip)
            if remaining > 0:
                self._send_json(
                    429,
                    {"detail": f"Too many failed attempts. Try again in {int(remaining) + 1}s."},
                )
                return
            body = self._read_json()
            supplied = str(body.get("password", ""))
            if not hmac.compare_digest(supplied, self.server.password):
                self.server.login_throttle.record_failure(ip)
                self._send_json(401, {"detail": "Wrong password"})
                return
            self.server.login_throttle.record_success(ip)
            token = self.server.sessions.issue()
            self._send_json(200, {"authenticated": True}, set_cookie=token)
            return

        if path == "/api/desktop-login":
            # One-time-token handshake for the desktop launcher: exchanges a
            # single-use token (minted in-process by the launcher) for a
            # session, so the long-lived password never rides in a URL.
            body = self._read_json()
            if not self.server.autologin_tokens.consume(str(body.get("token", ""))):
                self._send_json(401, {"detail": "Invalid or expired token"})
                return
            token = self.server.sessions.issue()
            self._send_json(200, {"authenticated": True}, set_cookie=token)
            return

        if path == "/api/logout":
            self.server.sessions.revoke(self._session_token())
            self._send_json(200, {"authenticated": False}, delete_cookie=True)
            return

        if path == "/api/license":
            if not self._require_auth():
                return
            manager = self.server.license_manager
            if manager is None:
                self._send_json(400, {"detail": "Licensing is not enabled on this platform."})
                return
            body = self._read_json()
            key = str(body.get("key", "")).strip()
            if not key:
                self._send_json(400, {"detail": "key is required"})
                return
            state = manager.set_key(key)
            if not state.valid:
                self._send_json(400, {"detail": "This license key is not valid or has expired."})
                return
            if not state.device_allowed:
                self._send_json(400, {"detail": "This license is already active on another device of this type."})
                return
            self._send_json(200, {"valid": True, "tier": state.tier})
            return

        if path == "/api/engine/update":
            if not self._require_auth():
                return
            # Fire-and-forget: the check+download+swap runs in a background
            # thread; the UI polls GET /api/engine for the outcome.
            threading.Thread(
                target=lambda: engine_update.ensure_latest(force=True),
                name="classydl-engine-update",
                daemon=True,
            ).start()
            self._send_json(200, {"started": True})
            return

        if path == "/api/settings":
            if not self._require_auth():
                return
            body = self._read_json()
            store = self.server.store
            if isinstance(body.get("language"), str) and body["language"]:
                store.set_setting("language", body["language"])
            if body.get("media_kind") in ("video", "audio"):
                store.set_setting("media_kind", body["media_kind"])
            if body.get("theme") in ("auto", "light", "dark"):
                store.set_setting("theme", body["theme"])
            quality = body.get("quality_height")
            if isinstance(quality, (int, str)) and str(quality).isdigit() and int(quality) in ALLOWED_QUALITY_HEIGHTS:
                store.set_setting("quality_height", str(int(quality)))
            if body.get("reset_folder") is True:
                store.clear_setting("export_folder_uri")
                store.clear_setting("export_folder_label")
            else:
                if isinstance(body.get("export_folder_uri"), str) and body["export_folder_uri"]:
                    store.set_setting("export_folder_uri", body["export_folder_uri"])
                if isinstance(body.get("export_folder_label"), str) and body["export_folder_label"]:
                    store.set_setting("export_folder_label", body["export_folder_label"])
            if body.get("accept_terms") is True:
                store.set_setting("terms_accepted_version", CURRENT_TERMS_VERSION)
            self._send_json(200, {"saved": True})
            return

        if path == "/api/open":
            if not self._require_auth():
                return
            body = self._read_json()
            job_id = body.get("job_id")
            filename = str(body.get("filename", ""))
            try:
                job_id = int(job_id)
            except (TypeError, ValueError):
                self._send_json(400, {"detail": "job_id is required"})
                return
            for candidate in self.server.store.list_job_files(job_id):
                candidate_path = Path(candidate)
                if candidate_path.name == filename:
                    opened = android_bridge.open_file(candidate_path)
                    self._send_json(200, {"opened": opened})
                    return
            self._send_json(404, {"detail": "File not found for this job"})
            return

        if path == "/api/open-folder":
            if not self._require_auth():
                return
            body = self._read_json()
            job_id = body.get("job_id")
            filename = str(body.get("filename", ""))
            try:
                job_id = int(job_id)
            except (TypeError, ValueError):
                self._send_json(400, {"detail": "job_id is required"})
                return
            for candidate in self.server.store.list_job_files(job_id):
                candidate_path = Path(candidate)
                if candidate_path.name == filename:
                    export_uri = self.server.store.get_setting("export_folder_uri")
                    opened = android_bridge.open_folder(export_uri)
                    self._send_json(200, {"opened": opened})
                    return
            self._send_json(404, {"detail": "File not found for this job"})
            return

        if path == "/api/share":
            if not self._require_auth():
                return
            body = self._read_json()
            job_id = body.get("job_id")
            filename = str(body.get("filename", ""))
            try:
                job_id = int(job_id)
            except (TypeError, ValueError):
                self._send_json(400, {"detail": "job_id is required"})
                return
            for candidate in self.server.store.list_job_files(job_id):
                candidate_path = Path(candidate)
                if candidate_path.name == filename:
                    shared = android_bridge.share_file(candidate_path)
                    self._send_json(200, {"shared": shared})
                    return
            self._send_json(404, {"detail": "File not found for this job"})
            return

        if path == "/api/scrape":
            if not self._require_auth():
                return
            body = self._read_json()
            url = str(body.get("url", "")).strip()
            if not url:
                self._send_json(400, {"detail": "url is required"})
                return

            media_types = body.get("media_types") or None
            scraper = SiteScraper()
            try:
                result = scraper.scrape(
                    url,
                    same_domain=bool(body.get("same_domain", False)),
                    media_types=set(media_types) if media_types else None,
                    name_filter=body.get("name_filter") or None,
                    deep=bool(body.get("deep", False)),
                )
            except SsrfBlockedError as exc:  # SSRF guard: refuse non-public targets
                self._send_json(400, {"detail": str(exc)})
                return
            except Exception as exc:  # network/parsing failures surface to the caller
                self._send_json(502, {"detail": str(exc)})
                return

            self._send_json(
                200,
                {
                    "page_url": result.page_url,
                    "page_title": result.page_title,
                    "errors": result.errors,
                    "items": [
                        {
                            "url": item.url,
                            "media_type": item.media_type,
                            "filename": item.filename,
                            "size_bytes": item.size_bytes,
                        }
                        for item in result.items
                    ],
                },
            )
            return

        if path == "/api/queue":
            if not self._require_auth():
                return
            body = self._read_json()
            source = str(body.get("source", "")).strip()
            if not source:
                self._send_json(400, {"detail": "source is required"})
                return

            manager = self.server.license_manager
            is_pro = manager is None or manager.is_pro()
            audio_only = bool(body.get("audio_only", False))
            # Playlists are effectively unlimited downloads in a single job -
            # counting them as "1" against the free-tier quota would let a
            # free-tier user bypass the limit entirely by always using
            # playlist URLs, so only Pro accounts get to request one.
            allow_playlist = bool(body.get("allow_playlist", False)) and is_pro

            if not is_pro:
                # Holds the lock across the whole check-then-add sequence, not
                # just the read: without this, concurrent requests near the
                # quota boundary can all read the same "used" count before any
                # of them commits a job, letting a burst of requests exceed
                # FREE_DAILY_DOWNLOAD_LIMIT.
                with self.server.quota_lock:
                    used = _recent_job_count(self.server.store, within_hours=FREE_WINDOW_HOURS)
                    if used >= FREE_DAILY_DOWNLOAD_LIMIT:
                        self._send_json(
                            402,
                            {
                                "detail": f"Free tier allows {FREE_DAILY_DOWNLOAD_LIMIT} downloads per "
                                f"{FREE_WINDOW_HOURS}h. Upgrade to Pro for unlimited downloads."
                            },
                        )
                        return

                    profile = _resolve_profile(self.server.store, audio_only)
                    job_id = self.server.store.add_job(
                        source=source,
                        profile_id=profile.id,
                        output_dir=str(self.server.output_dir),
                        ffmpeg_binary=self.server.ffmpeg_binary,
                        allow_playlist=allow_playlist,
                        quality_height=None if audio_only else _resolve_quality_height(body),
                    )
                    self._send_json(200, {"job_id": job_id})
                    return

            profile = _resolve_profile(self.server.store, audio_only)
            job_id = self.server.store.add_job(
                source=source,
                profile_id=profile.id,
                output_dir=str(self.server.output_dir),
                ffmpeg_binary=self.server.ffmpeg_binary,
                allow_playlist=allow_playlist,
                quality_height=None if audio_only else _resolve_quality_height(body),
            )
            self._send_json(200, {"job_id": job_id})
            return

        match = QUEUE_CANCEL_RE.match(path)
        if match:
            if not self._require_auth():
                return
            ok = self.server.store.mark_job_cancelled(int(match.group(1)))
            if not ok:
                self._send_json(404, {"detail": "Job not found or already finished"})
                return
            self._send_json(200, {"cancelled": True})
            return

        match = QUEUE_RETRY_RE.match(path)
        if match:
            if not self._require_auth():
                return
            # Requeues IN PLACE (same job id/dir) so partial data resumes -
            # see QueueStore.requeue_job. Only failed jobs qualify.
            ok = self.server.store.requeue_job(int(match.group(1)))
            if not ok:
                self._send_json(404, {"detail": "Job not found or not in a failed state"})
                return
            self._send_json(200, {"requeued": True})
            return

        match = QUEUE_DELETE_RE.match(path)
        if match:
            if not self._require_auth():
                return
            body = self._read_json()
            delete_files = bool(body.get("delete_files", False))
            if not self._delete_history_entry(int(match.group(1)), delete_files):
                self._send_json(404, {"detail": "Job not found or still running (cancel it first)"})
                return
            self._send_json(200, {"deleted": True})
            return

        if path == "/api/queue/clear":
            if not self._require_auth():
                return
            body = self._read_json()
            delete_files = bool(body.get("delete_files", False))
            deleted = 0
            # list_history caps at its limit per call; loop until a pass
            # deletes nothing so "clear" really means clear, not "clear the
            # newest 200".
            while True:
                jobs = self.server.store.list_history()
                progress = sum(
                    1 for job in jobs if self._delete_history_entry(job.id, delete_files)
                )
                deleted += progress
                if progress == 0:
                    break
            self._send_json(200, {"deleted": deleted})
            return

        self._send_json(404, {"detail": "Not found"})

    def _delete_history_entry(self, job_id: int, delete_files: bool) -> bool:
        """Remove a finished job from history; optionally its files too.

        "Entry only" leaves every copy on disk untouched - the user just
        doesn't want it in the list. "Delete files" also removes the app's
        own job-<id> directory AND (via the Android hook) the copy the
        publisher put into the system Downloads collection, because "I don't
        want anyone to see I downloaded this" is only true once the visible
        copy is gone as well. A copy exported to a user-picked SAF folder is
        deliberately left alone - that folder is the user's own space, and
        we hold no delete permission stronger than their file manager's.
        """
        store = self.server.store
        job = store.get_job(job_id)
        if job is None or job.status not in (
            JOB_STATUS_COMPLETED,
            JOB_STATUS_FAILED,
            JOB_STATUS_CANCELLED,
        ):
            return False
        filenames = [Path(p).name for p in store.list_job_files(job_id)]
        if not store.delete_job(job_id):
            return False
        if delete_files:
            base = Path(job.output_dir).expanduser() if job.output_dir else self.server.output_dir
            shutil.rmtree(base / f"job-{job_id}", ignore_errors=True)
            remover = self.server.published_file_remover
            if remover is not None:
                for name in filenames:
                    try:
                        remover(name)
                    except Exception:  # noqa: BLE001 - best-effort, never blocks the delete
                        pass
        return True


def create_server(
    *,
    store: QueueStore,
    output_dir: Path,
    password: str,
    host: str = "0.0.0.0",
    port: int = 8420,
    workers: int = 3,
    ffmpeg_binary: str = "ffmpeg",
    license_manager: LicenseManager | None = None,
    app_version: str = "",
    published_file_remover=None,
    secure_cookies: bool = False,
) -> ClassyDLServer:
    if not password:
        raise ValueError(
            "A password is required to run the web UI. Set --password or CLASSYDL_WEB_PASSWORD."
        )
    # Put any previously self-updated yt-dlp on sys.path before the first
    # download imports it. The engine files live next to the state DB, so
    # every deployment (Android/Termux/desktop) shares this one call site.
    engine_update.activate(store.db_path.parent)
    output_dir = ensure_output_dir(output_dir)
    return ClassyDLServer(
        (host, port),
        store=store,
        output_dir=output_dir,
        password=password,
        workers=workers,
        ffmpeg_binary=ffmpeg_binary,
        license_manager=license_manager,
        app_version=app_version,
        published_file_remover=published_file_remover,
        secure_cookies=secure_cookies,
    )


def run_server(
    *,
    store: QueueStore,
    output_dir: Path,
    password: str,
    host: str = "0.0.0.0",
    port: int = 8420,
    workers: int = 3,
    ffmpeg_binary: str = "ffmpeg",
    license_manager: LicenseManager | None = None,
    app_version: str = "",
) -> None:
    server = create_server(
        store=store,
        output_dir=output_dir,
        password=password,
        host=host,
        port=port,
        workers=workers,
        ffmpeg_binary=ffmpeg_binary,
        license_manager=license_manager,
        app_version=app_version,
    )
    server.start_background_worker()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop_background_worker()
        server.server_close()
