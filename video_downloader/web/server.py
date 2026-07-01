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
import threading
import time
from http.client import responses as HTTP_REASONS
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from ..models import JOB_STATUS_COMPLETED, DownloadProfile, JobRecord
from ..queue_runner import QueueRunner
from ..queue_store import QueueStore
from ..scraper import SiteScraper
from ..utils import ensure_output_dir

STATIC_DIR = Path(__file__).parent / "static"
SESSION_COOKIE = "classydl_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 days
AUDIO_PROFILE_NAME = "web-audio"

QUEUE_CANCEL_RE = re.compile(r"^/api/queue/(\d+)/cancel$")
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


class BackgroundQueueWorker:
    """Continuously drains the download queue in a background thread."""

    def __init__(self, store: QueueStore, output_dir: Path, workers: int) -> None:
        self._runner = QueueRunner(store=store, default_output_dir=output_dir)
        self._workers = workers
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="classydl-web-worker", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            summary = self._runner.run(workers=self._workers)
            if summary.processed == 0:
                self._stop.wait(2.0)


def _resolve_profile(store: QueueStore, audio_only: bool) -> DownloadProfile:
    if not audio_only:
        return store.ensure_default_profile()
    existing = store.get_profile_by_name(AUDIO_PROFILE_NAME)
    if existing is not None:
        return existing
    return store.create_profile(
        DownloadProfile(id=None, name=AUDIO_PROFILE_NAME, format_selector="ba/b", audio_only=True)
    )


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
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "files": files,
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
    ) -> None:
        super().__init__(address, ClassyDLRequestHandler)
        self.store = store
        self.output_dir = output_dir
        self.password = password
        self.sessions = SessionStore()
        self.worker = BackgroundQueueWorker(store=store, output_dir=output_dir, workers=workers)

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
        if set_cookie:
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={set_cookie}; Max-Age={SESSION_TTL_SECONDS}; HttpOnly; SameSite=Lax; Path=/",
            )
        if delete_cookie:
            self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; Max-Age=0; HttpOnly; SameSite=Lax; Path=/")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, *, download_name: str | None = None) -> None:
        try:
            data = path.read_bytes()
        except OSError:
            self._send_json(404, {"detail": "File no longer available"})
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        self.wfile.write(data)

    def _require_auth(self) -> bool:
        if not self._authed():
            self._send_json(401, {"detail": "Not authenticated"})
            return False
        return True

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
        if path == "/api/queue":
            if not self._require_auth():
                return
            status = (query.get("status") or [None])[0]
            jobs = self.server.store.list_jobs(status=status, limit=200)
            self._send_json(200, {"jobs": [_serialize_job(self.server.store, job) for job in jobs]})
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
            body = self._read_json()
            supplied = str(body.get("password", ""))
            if not hmac.compare_digest(supplied, self.server.password):
                self._send_json(401, {"detail": "Wrong password"})
                return
            token = self.server.sessions.issue()
            self._send_json(200, {"authenticated": True}, set_cookie=token)
            return

        if path == "/api/logout":
            self.server.sessions.revoke(self._session_token())
            self._send_json(200, {"authenticated": False}, delete_cookie=True)
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

            profile = _resolve_profile(self.server.store, bool(body.get("audio_only", False)))
            job_id = self.server.store.add_job(
                source=source,
                profile_id=profile.id,
                output_dir=str(self.server.output_dir),
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

        self._send_json(404, {"detail": "Not found"})


def create_server(
    *,
    store: QueueStore,
    output_dir: Path,
    password: str,
    host: str = "0.0.0.0",
    port: int = 8420,
    workers: int = 3,
) -> ClassyDLServer:
    if not password:
        raise ValueError(
            "A password is required to run the web UI. Set --password or CLASSYDL_WEB_PASSWORD."
        )
    output_dir = ensure_output_dir(output_dir)
    return ClassyDLServer(
        (host, port),
        store=store,
        output_dir=output_dir,
        password=password,
        workers=workers,
    )


def run_server(
    *,
    store: QueueStore,
    output_dir: Path,
    password: str,
    host: str = "0.0.0.0",
    port: int = 8420,
    workers: int = 3,
) -> None:
    server = create_server(
        store=store,
        output_dir=output_dir,
        password=password,
        host=host,
        port=port,
        workers=workers,
    )
    server.start_background_worker()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop_background_worker()
        server.server_close()
