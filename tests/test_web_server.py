from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from pathlib import Path

import pytest

from video_downloader.licensing import FREE_DAILY_DOWNLOAD_LIMIT, LicenseState
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


def test_queue_accepts_allow_playlist_flag(server: ClassyDLServer) -> None:
    _, _, set_cookie = _request(server, "POST", "/api/login", {"password": "crypt-keeper"})
    cookie = set_cookie.split(";")[0]

    status, body, _ = _request(
        server,
        "POST",
        "/api/queue",
        {"source": "https://youtube.com/playlist?list=abc123", "allow_playlist": True},
        cookie=cookie,
    )
    assert status == 200
    job = server.store.get_job(body["job_id"])
    assert job is not None
    assert job.allow_playlist is True


def test_queue_defaults_allow_playlist_to_false(server: ClassyDLServer) -> None:
    _, _, set_cookie = _request(server, "POST", "/api/login", {"password": "crypt-keeper"})
    cookie = set_cookie.split(";")[0]

    status, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/video"}, cookie=cookie
    )
    assert status == 200
    job = server.store.get_job(body["job_id"])
    assert job is not None
    assert job.allow_playlist is False


def test_queue_defaults_quality_height_to_4k(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/video"}, cookie=cookie
    )
    assert status == 200
    job = server.store.get_job(body["job_id"])
    assert job is not None
    assert job.quality_height == 2160


def test_queue_accepts_explicit_quality_height(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, body, _ = _request(
        server,
        "POST",
        "/api/queue",
        {"source": "https://example.com/video", "quality_height": 720},
        cookie=cookie,
    )
    assert status == 200
    job = server.store.get_job(body["job_id"])
    assert job is not None
    assert job.quality_height == 720


def test_queue_rejects_unsupported_quality_height(server: ClassyDLServer) -> None:
    # Anything not one of the UI's offered tiers (a tampered/garbage value)
    # falls back to the same 4K default rather than being passed through
    # verbatim to yt-dlp's format selector.
    cookie = _login(server)
    status, body, _ = _request(
        server,
        "POST",
        "/api/queue",
        {"source": "https://example.com/video", "quality_height": 9999},
        cookie=cookie,
    )
    assert status == 200
    job = server.store.get_job(body["job_id"])
    assert job is not None
    assert job.quality_height == 2160


def test_queue_leaves_quality_height_unset_for_audio_only(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, body, _ = _request(
        server,
        "POST",
        "/api/queue",
        {"source": "https://example.com/video", "audio_only": True, "quality_height": 1080},
        cookie=cookie,
    )
    assert status == 200
    job = server.store.get_job(body["job_id"])
    assert job is not None
    assert job.quality_height is None


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


class _FakeLicenseManager:
    """Interface-compatible stand-in for LicenseManager, no network involved."""

    def __init__(self, *, valid: bool, tier: str | None = None, key: str | None = "DLT-EXISTING") -> None:
        self._state = LicenseState(key=key, valid=valid, tier=tier)

    def is_pro(self) -> bool:
        return self._state.valid

    def status(self) -> LicenseState:
        return self._state

    def set_key(self, key: str) -> LicenseState:
        valid = key.startswith("GOOD")
        self._state = LicenseState(key=key, valid=valid, tier="lifetime" if valid else None)
        return self._state


def _make_server(tmp_path: Path, *, license_manager=None) -> ClassyDLServer:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    srv = create_server(
        store=store,
        output_dir=tmp_path / "downloads",
        password="crypt-keeper",
        host="127.0.0.1",
        port=0,
        workers=1,
        license_manager=license_manager,
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    return srv


def _teardown(srv: ClassyDLServer) -> None:
    srv.shutdown()
    srv.stop_background_worker()
    srv.server_close()


def test_license_endpoint_reports_not_configured_without_a_manager(tmp_path: Path) -> None:
    srv = _make_server(tmp_path)
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]
        status, body, _ = _request(srv, "GET", "/api/license", cookie=cookie)
        assert status == 200
        assert body == {"configured": False}
    finally:
        _teardown(srv)


def test_license_endpoint_reports_status_when_configured(tmp_path: Path) -> None:
    srv = _make_server(tmp_path, license_manager=_FakeLicenseManager(valid=True, tier="yearly"))
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]
        status, body, _ = _request(srv, "GET", "/api/license", cookie=cookie)
        assert status == 200
        assert body == {"configured": True, "valid": True, "tier": "yearly", "has_key": True}
    finally:
        _teardown(srv)


def test_license_post_rejects_invalid_key(tmp_path: Path) -> None:
    srv = _make_server(tmp_path, license_manager=_FakeLicenseManager(valid=False, key=None))
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]
        status, body, _ = _request(srv, "POST", "/api/license", {"key": "DLT-BADKEY"}, cookie=cookie)
        assert status == 400
    finally:
        _teardown(srv)


def test_license_post_accepts_valid_key(tmp_path: Path) -> None:
    srv = _make_server(tmp_path, license_manager=_FakeLicenseManager(valid=False, key=None))
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]
        status, body, _ = _request(srv, "POST", "/api/license", {"key": "GOOD-KEY"}, cookie=cookie)
        assert status == 200
        assert body == {"valid": True, "tier": "lifetime"}
    finally:
        _teardown(srv)


def test_free_tier_blocks_downloads_beyond_the_daily_limit(tmp_path: Path) -> None:
    srv = _make_server(tmp_path, license_manager=_FakeLicenseManager(valid=False))
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]

        for i in range(FREE_DAILY_DOWNLOAD_LIMIT):
            status, _, _ = _request(
                srv, "POST", "/api/queue", {"source": f"https://example.com/{i}"}, cookie=cookie
            )
            assert status == 200

        status, body, _ = _request(
            srv, "POST", "/api/queue", {"source": "https://example.com/one-too-many"}, cookie=cookie
        )
        assert status == 402
        assert f"{FREE_DAILY_DOWNLOAD_LIMIT} download" in body["detail"]
    finally:
        _teardown(srv)


def test_free_tier_allows_a_new_job_once_the_first_is_cancelled(tmp_path: Path) -> None:
    srv = _make_server(tmp_path, license_manager=_FakeLicenseManager(valid=False))
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]

        _, body, _ = _request(srv, "POST", "/api/queue", {"source": "https://example.com/1"}, cookie=cookie)
        first_job_id = body["job_id"]
        _request(srv, "POST", f"/api/queue/{first_job_id}/cancel", cookie=cookie)

        status, _, _ = _request(srv, "POST", "/api/queue", {"source": "https://example.com/2"}, cookie=cookie)
        assert status == 200
    finally:
        _teardown(srv)


def test_free_tier_allows_a_new_download_after_the_daily_window_passes(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    srv = create_server(
        store=store,
        output_dir=tmp_path / "downloads",
        password="crypt-keeper",
        host="127.0.0.1",
        port=0,
        workers=1,
        license_manager=_FakeLicenseManager(valid=False),
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]
        _, body, _ = _request(srv, "POST", "/api/queue", {"source": "https://example.com/1"}, cookie=cookie)
        job_id = body["job_id"]

        # Backdate the job past the rolling 24h window directly in the DB —
        # simulating "yesterday's download" without sleeping in the test.
        old_ts = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
        with sqlite3.connect(tmp_path / "state.db") as conn:
            conn.execute("UPDATE jobs SET created_at = ? WHERE id = ?", (old_ts, job_id))

        status, _, _ = _request(srv, "POST", "/api/queue", {"source": "https://example.com/2"}, cookie=cookie)
        assert status == 200
    finally:
        _teardown(srv)


def test_free_and_pro_tiers_use_the_same_unrestricted_profile(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    srv = create_server(
        store=store,
        output_dir=tmp_path / "downloads",
        password="crypt-keeper",
        host="127.0.0.1",
        port=0,
        workers=1,
        license_manager=_FakeLicenseManager(valid=False),
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]
        _, body, _ = _request(srv, "POST", "/api/queue", {"source": "https://example.com/1"}, cookie=cookie)
        job = store.get_job(body["job_id"])
        assert job is not None
        profile = store.get_profile_by_id(job.profile_id)
        assert profile is not None
        assert profile.name == "default"
        assert profile.format_selector == "bv*+ba/b"
    finally:
        _teardown(srv)


def test_free_tier_cannot_use_allow_playlist_to_bypass_the_quota(tmp_path: Path) -> None:
    srv = _make_server(tmp_path, license_manager=_FakeLicenseManager(valid=False))
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]

        status, body, _ = _request(
            srv,
            "POST",
            "/api/queue",
            {"source": "https://youtube.com/playlist?list=abc123", "allow_playlist": True},
            cookie=cookie,
        )
        assert status == 200
        job = srv.store.get_job(body["job_id"])
        assert job is not None
        assert job.allow_playlist is False
    finally:
        _teardown(srv)


def test_free_tier_quota_check_is_race_safe_under_concurrent_requests(tmp_path: Path) -> None:
    srv = _make_server(tmp_path, license_manager=_FakeLicenseManager(valid=False))
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]

        statuses: list[int] = []
        lock = threading.Lock()

        def fire(i: int) -> None:
            status, _, _ = _request(
                srv, "POST", "/api/queue", {"source": f"https://example.com/{i}"}, cookie=cookie
            )
            with lock:
                statuses.append(status)

        threads = [threading.Thread(target=fire, args=(i,)) for i in range(FREE_DAILY_DOWNLOAD_LIMIT + 5)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert statuses.count(200) == FREE_DAILY_DOWNLOAD_LIMIT
        assert statuses.count(402) == 5
    finally:
        _teardown(srv)


def test_pro_tier_has_no_daily_quota(tmp_path: Path) -> None:
    srv = _make_server(tmp_path, license_manager=_FakeLicenseManager(valid=True, tier="lifetime"))
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        cookie = set_cookie.split(";")[0]
        for i in range(3):
            status, _, _ = _request(
                srv, "POST", "/api/queue", {"source": f"https://example.com/{i}"}, cookie=cookie
            )
            assert status == 200
    finally:
        _teardown(srv)


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


def _login(server: ClassyDLServer) -> str:
    _, _, set_cookie = _request(server, "POST", "/api/login", {"password": "crypt-keeper"})
    return set_cookie.split(";")[0]


def test_settings_defaults_to_auto_language_and_no_folder(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, body, _ = _request(server, "GET", "/api/settings", cookie=cookie)
    assert status == 200
    assert body == {
        "language": "auto",
        "export_folder_label": None,
        "terms_accepted": False,
        "app_version": "",
    }


def test_settings_persists_language(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, body, _ = _request(server, "POST", "/api/settings", {"language": "de"}, cookie=cookie)
    assert status == 200
    assert body == {"saved": True}

    _, body, _ = _request(server, "GET", "/api/settings", cookie=cookie)
    assert body["language"] == "de"


def test_settings_stores_and_resets_export_folder(server: ClassyDLServer) -> None:
    cookie = _login(server)
    _request(
        server,
        "POST",
        "/api/settings",
        {"export_folder_uri": "content://tree/abc", "export_folder_label": "My Folder"},
        cookie=cookie,
    )
    _, body, _ = _request(server, "GET", "/api/settings", cookie=cookie)
    assert body["export_folder_label"] == "My Folder"

    _request(server, "POST", "/api/settings", {"reset_folder": True}, cookie=cookie)
    _, body, _ = _request(server, "GET", "/api/settings", cookie=cookie)
    assert body["export_folder_label"] is None


def test_settings_accept_terms_persists(server: ClassyDLServer) -> None:
    cookie = _login(server)
    _, body, _ = _request(server, "GET", "/api/settings", cookie=cookie)
    assert body["terms_accepted"] is False

    status, _, _ = _request(server, "POST", "/api/settings", {"accept_terms": True}, cookie=cookie)
    assert status == 200

    _, body, _ = _request(server, "GET", "/api/settings", cookie=cookie)
    assert body["terms_accepted"] is True


def test_settings_reports_configured_app_version(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    srv = create_server(
        store=store,
        output_dir=tmp_path / "downloads",
        password="crypt-keeper",
        host="127.0.0.1",
        port=0,
        workers=1,
        app_version="1.2.3",
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        cookie = _login(srv)
        _, body, _ = _request(srv, "GET", "/api/settings", cookie=cookie)
        assert body["app_version"] == "1.2.3"
    finally:
        srv.shutdown()
        srv.stop_background_worker()
        srv.server_close()


def test_settings_requires_auth(server: ClassyDLServer) -> None:
    status, _, _ = _request(server, "GET", "/api/settings")
    assert status == 401
    status, _, _ = _request(server, "POST", "/api/settings", {"language": "de"})
    assert status == 401


def test_open_endpoint_returns_false_off_android(server: ClassyDLServer, tmp_path: Path) -> None:
    # android_bridge.open_file() no-ops (returns False) outside Chaquopy —
    # this exercises the full job-file lookup path without needing a real
    # Android environment, matching how the download endpoint is tested.
    cookie = _login(server)
    status, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/video"}, cookie=cookie
    )
    job_id = body["job_id"]
    output_file = tmp_path / "downloads" / "video.mp4"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(b"fake video")
    server.store.mark_job_completed(job_id, [output_file])

    status, body, _ = _request(
        server, "POST", "/api/open", {"job_id": job_id, "filename": "video.mp4"}, cookie=cookie
    )
    assert status == 200
    assert body == {"opened": False}


def test_open_endpoint_404_for_unknown_file(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, _, _ = _request(
        server, "POST", "/api/open", {"job_id": 999999, "filename": "nope.mp4"}, cookie=cookie
    )
    assert status == 404


def test_open_folder_endpoint_returns_false_off_android(server: ClassyDLServer, tmp_path: Path) -> None:
    cookie = _login(server)
    _, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/video"}, cookie=cookie
    )
    job_id = body["job_id"]
    output_file = tmp_path / "downloads" / "video.mp4"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(b"fake video")
    server.store.mark_job_completed(job_id, [output_file])

    status, body, _ = _request(
        server, "POST", "/api/open-folder", {"job_id": job_id, "filename": "video.mp4"}, cookie=cookie
    )
    assert status == 200
    assert body == {"opened": False}


def test_open_folder_endpoint_404_for_unknown_file(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, _, _ = _request(
        server, "POST", "/api/open-folder", {"job_id": 999999, "filename": "nope.mp4"}, cookie=cookie
    )
    assert status == 404


def test_share_endpoint_returns_false_off_android(server: ClassyDLServer, tmp_path: Path) -> None:
    cookie = _login(server)
    _, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/video"}, cookie=cookie
    )
    job_id = body["job_id"]
    output_file = tmp_path / "downloads" / "video.mp4"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(b"fake video")
    server.store.mark_job_completed(job_id, [output_file])

    status, body, _ = _request(
        server, "POST", "/api/share", {"job_id": job_id, "filename": "video.mp4"}, cookie=cookie
    )
    assert status == 200
    assert body == {"shared": False}


def test_share_endpoint_404_for_unknown_file(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, _, _ = _request(
        server, "POST", "/api/share", {"job_id": 999999, "filename": "nope.mp4"}, cookie=cookie
    )
    assert status == 404
