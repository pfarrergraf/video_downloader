"""FastAPI backend for the Gothic browser UI.

This is the piece that actually runs on a server: it wraps the existing
scraper / queue / download-manager modules behind a small HTTP API so any
browser (phone included) can drive ClassyDL without installing anything.
"""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from ..models import JOB_STATUS_COMPLETED, DownloadProfile, JobRecord
from ..queue_runner import QueueRunner
from ..queue_store import QueueStore
from ..scraper import SiteScraper
from ..utils import ensure_output_dir

STATIC_DIR = Path(__file__).parent / "static"
SESSION_COOKIE = "classydl_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 days
AUDIO_PROFILE_NAME = "web-audio"


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


def create_app(
    *,
    store: QueueStore,
    output_dir: Path,
    password: str,
    workers: int = 3,
) -> FastAPI:
    if not password:
        raise ValueError(
            "A password is required to run the web UI. Set --password or CLASSYDL_WEB_PASSWORD."
        )

    output_dir = ensure_output_dir(output_dir)
    sessions = SessionStore()
    worker = BackgroundQueueWorker(store=store, output_dir=output_dir, workers=workers)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        worker.start()
        try:
            yield
        finally:
            worker.stop()

    app = FastAPI(title="ClassyDL", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.sessions = sessions

    def _authed(request: Request) -> bool:
        return sessions.is_valid(request.cookies.get(SESSION_COOKIE))

    def _require_auth(request: Request) -> None:
        if not _authed(request):
            raise HTTPException(status_code=401, detail="Not authenticated")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok"}

    @app.get("/api/me")
    def me(request: Request) -> dict[str, Any]:
        return {"authenticated": _authed(request)}

    @app.post("/api/login")
    async def login(request: Request, response: Response) -> dict[str, Any]:
        body = await request.json()
        supplied = str(body.get("password", ""))
        if not hmac.compare_digest(supplied, password):
            raise HTTPException(status_code=401, detail="Wrong password")
        token = sessions.issue()
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            samesite="lax",
        )
        return {"authenticated": True}

    @app.post("/api/logout")
    def logout(request: Request, response: Response) -> dict[str, Any]:
        sessions.revoke(request.cookies.get(SESSION_COOKIE))
        response.delete_cookie(SESSION_COOKIE)
        return {"authenticated": False}

    @app.post("/api/scrape")
    async def scrape(request: Request) -> dict[str, Any]:
        _require_auth(request)
        body = await request.json()
        url = str(body.get("url", "")).strip()
        if not url:
            raise HTTPException(status_code=400, detail="url is required")

        media_types = body.get("media_types") or None
        name_filter = body.get("name_filter") or None
        deep = bool(body.get("deep", False))
        same_domain = bool(body.get("same_domain", False))

        scraper = SiteScraper()
        try:
            result = await run_in_threadpool(
                scraper.scrape,
                url,
                same_domain=same_domain,
                media_types=set(media_types) if media_types else None,
                name_filter=name_filter,
                deep=deep,
            )
        except Exception as exc:  # network/parsing failures surface to the caller
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return {
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
        }

    @app.post("/api/queue")
    async def queue_add(request: Request) -> dict[str, Any]:
        _require_auth(request)
        body = await request.json()
        source = str(body.get("source", "")).strip()
        if not source:
            raise HTTPException(status_code=400, detail="source is required")

        audio_only = bool(body.get("audio_only", False))
        profile = _resolve_profile(store, audio_only)
        job_id = store.add_job(
            source=source,
            profile_id=profile.id,
            output_dir=str(output_dir),
        )
        return {"job_id": job_id}

    @app.get("/api/queue")
    def queue_list(request: Request, status: str | None = None) -> dict[str, Any]:
        _require_auth(request)
        jobs = store.list_jobs(status=status, limit=200)
        return {"jobs": [_serialize_job(store, job) for job in jobs]}

    @app.post("/api/queue/{job_id}/cancel")
    def queue_cancel(request: Request, job_id: int) -> dict[str, Any]:
        _require_auth(request)
        ok = store.mark_job_cancelled(job_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Job not found or already finished")
        return {"cancelled": True}

    @app.get("/api/download/{job_id}/{filename}")
    def download_file(request: Request, job_id: int, filename: str) -> FileResponse:
        _require_auth(request)
        for candidate in store.list_job_files(job_id):
            path = Path(candidate)
            if path.name == filename:
                if not path.is_file():
                    raise HTTPException(status_code=404, detail="File no longer available")
                return FileResponse(path, filename=path.name)
        raise HTTPException(status_code=404, detail="File not found for this job")

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app


def run_server(
    *,
    store: QueueStore,
    output_dir: Path,
    password: str,
    host: str = "0.0.0.0",
    port: int = 8420,
    workers: int = 3,
) -> None:
    import uvicorn

    app = create_app(store=store, output_dir=output_dir, password=password, workers=workers)
    uvicorn.run(app, host=host, port=port)
