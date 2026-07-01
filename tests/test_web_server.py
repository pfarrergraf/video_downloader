from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from video_downloader.queue_store import QueueStore
from video_downloader.web.server import create_app


def _make_client(tmp_path: Path) -> TestClient:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    app = create_app(
        store=store,
        output_dir=tmp_path / "downloads",
        password="crypt-keeper",
        workers=1,
    )
    return TestClient(app)


def test_api_requires_auth(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    assert client.get("/api/me").json() == {"authenticated": False}
    assert client.get("/api/queue").status_code == 401
    assert client.post("/api/scrape", json={"url": "https://example.com"}).status_code == 401


def test_login_wrong_password_rejected(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    response = client.post("/api/login", json={"password": "wrong"})
    assert response.status_code == 401
    assert client.get("/api/me").json() == {"authenticated": False}


def test_login_then_queue_and_list(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    login = client.post("/api/login", json={"password": "crypt-keeper"})
    assert login.status_code == 200
    assert client.get("/api/me").json() == {"authenticated": True}

    queued = client.post("/api/queue", json={"source": "https://example.com/video"})
    assert queued.status_code == 200
    job_id = queued.json()["job_id"]

    jobs = client.get("/api/queue").json()["jobs"]
    assert any(job["id"] == job_id and job["source"] == "https://example.com/video" for job in jobs)


def test_logout_revokes_session(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    client.post("/api/login", json={"password": "crypt-keeper"})
    assert client.get("/api/me").json() == {"authenticated": True}

    client.post("/api/logout")
    assert client.get("/api/me").json() == {"authenticated": False}
    assert client.get("/api/queue").status_code == 401


def test_create_app_requires_password(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    try:
        create_app(store=store, output_dir=tmp_path / "downloads", password="")
        assert False, "expected ValueError"
    except ValueError:
        pass
