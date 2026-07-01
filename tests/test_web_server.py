from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

from video_downloader.queue_store import QueueStore
from video_downloader.web.server import ClassyDLServer, create_server


@pytest.fixture
def server(tmp_path: Path):
    store = QueueStore(tmp_path / "state.db")
    store.init()
    srv = create_server(
        store=store,
        output_dir=tmp_path / "downloads",
        password="crypt-keeper",
        host="127.0.0.1",
        port=0,
        workers=1,
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.stop_background_worker()
        srv.server_close()


def _request(server: ClassyDLServer, method: str, path: str, payload=None, cookie: str | None = None):
    conn = HTTPConnection(*server.server_address, timeout=5)
    headers: dict[str, str] = {}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    if cookie:
        headers["Cookie"] = cookie
    conn.request(method, path, body=body, headers=headers)
    response = conn.getresponse()
    raw = response.read()
    data = json.loads(raw.decode("utf-8")) if raw else None
    set_cookie = response.getheader("Set-Cookie")
    conn.close()
    return response.status, data, set_cookie


def test_api_requires_auth(server: ClassyDLServer) -> None:
    _, body, _ = _request(server, "GET", "/api/me")
    assert body == {"authenticated": False}

    status, _, _ = _request(server, "GET", "/api/queue")
    assert status == 401

    status, _, _ = _request(server, "POST", "/api/scrape", {"url": "https://example.com"})
    assert status == 401


def test_login_wrong_password_rejected(server: ClassyDLServer) -> None:
    status, _, _ = _request(server, "POST", "/api/login", {"password": "wrong"})
    assert status == 401

    _, body, _ = _request(server, "GET", "/api/me")
    assert body == {"authenticated": False}


def test_login_then_queue_and_list(server: ClassyDLServer) -> None:
    status, _, set_cookie = _request(server, "POST", "/api/login", {"password": "crypt-keeper"})
    assert status == 200
    cookie = set_cookie.split(";")[0]

    _, body, _ = _request(server, "GET", "/api/me", cookie=cookie)
    assert body == {"authenticated": True}

    status, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/video"}, cookie=cookie
    )
    assert status == 200
    job_id = body["job_id"]

    _, body, _ = _request(server, "GET", "/api/queue", cookie=cookie)
    assert any(job["id"] == job_id and job["source"] == "https://example.com/video" for job in body["jobs"])


def test_logout_revokes_session(server: ClassyDLServer) -> None:
    _, _, set_cookie = _request(server, "POST", "/api/login", {"password": "crypt-keeper"})
    cookie = set_cookie.split(";")[0]

    _, body, _ = _request(server, "GET", "/api/me", cookie=cookie)
    assert body == {"authenticated": True}

    _request(server, "POST", "/api/logout", cookie=cookie)

    _, body, _ = _request(server, "GET", "/api/me", cookie=cookie)
    assert body == {"authenticated": False}
    status, _, _ = _request(server, "GET", "/api/queue", cookie=cookie)
    assert status == 401


def test_create_server_requires_password(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    with pytest.raises(ValueError):
        create_server(store=store, output_dir=tmp_path / "downloads", password="")


def test_queued_jobs_use_the_servers_ffmpeg_binary(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    srv = create_server(
        store=store,
        output_dir=tmp_path / "downloads",
        password="crypt-keeper",
        host="127.0.0.1",
        port=0,
        workers=1,
        ffmpeg_binary="/data/app/de.classydl.app/lib/arm64/libffmpeg.so",
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]

        _, body, _ = _request(
            srv, "POST", "/api/queue", {"source": "https://example.com/video"}, cookie=cookie
        )
        job = store.get_job(body["job_id"])
        assert job is not None
        assert job.ffmpeg_binary == "/data/app/de.classydl.app/lib/arm64/libffmpeg.so"
    finally:
        srv.shutdown()
        srv.stop_background_worker()
        srv.server_close()
