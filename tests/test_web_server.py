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
from video_downloader.web.server import LOGIN_MAX_ATTEMPTS, ClassyDLServer, create_server


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


def test_login_locks_out_after_repeated_failures(server: ClassyDLServer) -> None:
    for _ in range(LOGIN_MAX_ATTEMPTS):
        status, _, _ = _request(server, "POST", "/api/login", {"password": "wrong"})
        assert status == 401

    # Locked out now, even with the correct password.
    status, body, _ = _request(server, "POST", "/api/login", {"password": "crypt-keeper"})
    assert status == 429
    assert "Too many failed attempts" in body["detail"]


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
        assert body == {
            "configured": True,
            "valid": True,
            "tier": "yearly",
            "has_key": True,
            "device_allowed": True,
        }
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
        "media_kind": "video",
        "quality_height": "2160",
        "theme": "auto",
        "free_limit": FREE_DAILY_DOWNLOAD_LIMIT,
        "free_window_hours": 24,
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


# -- Phase-1 UX additions: Smart Mode settings, error codes, free-limit copy --


def test_settings_include_smart_mode_defaults_and_free_limit(server: ClassyDLServer) -> None:
    cookie = _login(server)
    _, body, _ = _request(server, "GET", "/api/settings", cookie=cookie)
    assert body["media_kind"] == "video"
    assert body["quality_height"] == "2160"
    assert body["theme"] == "auto"
    assert body["free_limit"] == FREE_DAILY_DOWNLOAD_LIMIT
    assert body["free_window_hours"] == 24


def test_settings_smart_mode_roundtrip(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, _, _ = _request(
        server,
        "POST",
        "/api/settings",
        {"media_kind": "audio", "quality_height": 720, "theme": "dark"},
        cookie=cookie,
    )
    assert status == 200
    _, body, _ = _request(server, "GET", "/api/settings", cookie=cookie)
    assert body["media_kind"] == "audio"
    assert body["quality_height"] == "720"
    assert body["theme"] == "dark"


def test_settings_reject_invalid_smart_mode_values(server: ClassyDLServer) -> None:
    cookie = _login(server)
    _request(
        server,
        "POST",
        "/api/settings",
        {"media_kind": "hologram", "quality_height": 999, "theme": "neon"},
        cookie=cookie,
    )
    _, body, _ = _request(server, "GET", "/api/settings", cookie=cookie)
    # Invalid values are ignored, defaults stay.
    assert body["media_kind"] == "video"
    assert body["quality_height"] == "2160"
    assert body["theme"] == "auto"


def test_failed_job_carries_error_code(server: ClassyDLServer) -> None:
    cookie = _login(server)
    _, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/video"}, cookie=cookie
    )
    job_id = body["job_id"]
    server.store.mark_job_failed(job_id, "ERROR: [youtube] abc: Video unavailable")

    _, body, _ = _request(server, "GET", "/api/queue", cookie=cookie)
    job = next(j for j in body["jobs"] if j["id"] == job_id)
    assert job["error_code"] == "video_unavailable"

    # Jobs without an error report no code.
    _, body2, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/other"}, cookie=cookie
    )
    _, body, _ = _request(server, "GET", "/api/queue", cookie=cookie)
    fresh = next(j for j in body["jobs"] if j["id"] == body2["job_id"])
    assert fresh["error_code"] is None


def test_retry_endpoint_requeues_failed_job(server: ClassyDLServer) -> None:
    cookie = _login(server)
    _, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/video"}, cookie=cookie
    )
    job_id = body["job_id"]
    server.store.mark_job_failed(job_id, "network dropped", error_code="network_offline")

    status, body, _ = _request(server, "POST", f"/api/queue/{job_id}/retry", cookie=cookie)
    assert status == 200
    assert body == {"requeued": True}
    job = server.store.get_job(job_id)
    assert job is not None and job.status == "pending"

    # Retrying a non-failed job is a 404, not a silent success.
    status, _, _ = _request(server, "POST", f"/api/queue/{job_id}/retry", cookie=cookie)
    assert status == 404


def _make_completed_job_with_file(server: ClassyDLServer, cookie: str, name: str = "clip.mp4") -> tuple[int, Path]:
    _, body, _ = _request(
        server, "POST", "/api/queue", {"source": f"https://example.com/{name}"}, cookie=cookie
    )
    job_id = body["job_id"]
    job_dir = server.output_dir / f"job-{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    file_path = job_dir / name
    file_path.write_bytes(b"fake video bytes")
    server.store.mark_job_completed(job_id, [file_path])
    return job_id, file_path


def test_delete_endpoint_entry_only_keeps_files_but_purges_history(server: ClassyDLServer) -> None:
    cookie = _login(server)
    job_id, file_path = _make_completed_job_with_file(server, cookie)
    assert any(e.job_id == job_id for e in server.store.list_events())

    status, body, _ = _request(
        server, "POST", f"/api/queue/{job_id}/delete", {"delete_files": False}, cookie=cookie
    )
    assert status == 200
    assert body == {"deleted": True}
    assert server.store.get_job(job_id) is None
    # Privacy: the event log must not keep what the list no longer shows.
    assert not any(e.job_id == job_id for e in server.store.list_events())
    # "Entry only" means every copy on disk stays.
    assert file_path.exists()

    # Deleting again is a 404, not a silent success.
    status, _, _ = _request(
        server, "POST", f"/api/queue/{job_id}/delete", {"delete_files": False}, cookie=cookie
    )
    assert status == 404


def test_delete_endpoint_with_files_removes_job_dir_and_published_copy(server: ClassyDLServer) -> None:
    cookie = _login(server)
    removed: list[str] = []
    server.published_file_remover = removed.append
    job_id, file_path = _make_completed_job_with_file(server, cookie, name="secret.mp4")

    status, _, _ = _request(
        server, "POST", f"/api/queue/{job_id}/delete", {"delete_files": True}, cookie=cookie
    )
    assert status == 200
    assert not file_path.exists()
    assert not file_path.parent.exists()
    # The Android hook gets the filename so the MediaStore copy goes too.
    assert removed == ["secret.mp4"]


def test_delete_endpoint_refuses_running_jobs_and_requires_auth(server: ClassyDLServer) -> None:
    cookie = _login(server)
    _, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/busy"}, cookie=cookie
    )
    job_id = body["job_id"]  # still pending - never claimed (no worker running)

    status, _, _ = _request(
        server, "POST", f"/api/queue/{job_id}/delete", {"delete_files": True}, cookie=cookie
    )
    assert status == 404
    assert server.store.get_job(job_id) is not None

    status, _, _ = _request(server, "POST", f"/api/queue/{job_id}/delete", {"delete_files": True})
    assert status == 401


def test_clear_endpoint_deletes_every_finished_job_but_not_active_ones(server: ClassyDLServer) -> None:
    cookie = _login(server)
    done_id, done_file = _make_completed_job_with_file(server, cookie)
    _, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/broken"}, cookie=cookie
    )
    failed_id = body["job_id"]
    server.store.mark_job_failed(failed_id, "boom", error_code="unknown")
    _, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/waiting"}, cookie=cookie
    )
    pending_id = body["job_id"]

    status, body, _ = _request(
        server, "POST", "/api/queue/clear", {"delete_files": False}, cookie=cookie
    )
    assert status == 200
    assert body == {"deleted": 2}
    assert server.store.get_job(done_id) is None
    assert server.store.get_job(failed_id) is None
    assert server.store.get_job(pending_id) is not None
    assert done_file.exists()  # delete_files=False keeps everything on disk


def test_engine_endpoints_report_versions(server: ClassyDLServer, monkeypatch) -> None:
    cookie = _login(server)
    status, body, _ = _request(server, "GET", "/api/engine", cookie=cookie)
    assert status == 200
    # The test env installs yt-dlp normally, so both versions resolve.
    assert body["bundled_version"]
    assert body["active_version"]
    assert body["updating"] is False

    # The POST spawns a background ensure_latest - stub it so the test never
    # talks to the real PyPI.
    calls = []
    from video_downloader import engine_update

    monkeypatch.setattr(engine_update, "ensure_latest", lambda force=False: calls.append(force) or (False, None))
    status, body, _ = _request(server, "POST", "/api/engine/update", cookie=cookie)
    assert status == 200
    assert body == {"started": True}
    for _ in range(50):
        if calls:
            break
        import time

        time.sleep(0.1)
    assert calls == [True]


def test_download_endpoint_serves_ranges(server: ClassyDLServer, tmp_path: Path) -> None:
    cookie = _login(server)
    _, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/video"}, cookie=cookie
    )
    job_id = body["job_id"]
    payload = bytes(range(256)) * 4
    output_file = tmp_path / "downloads" / "clip.mp4"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(payload)
    server.store.mark_job_completed(job_id, [output_file])

    conn = HTTPConnection(*server.server_address, timeout=5)
    conn.request("GET", f"/api/download/{job_id}/clip.mp4", headers={"Cookie": cookie})
    response = conn.getresponse()
    assert response.status == 200
    assert response.getheader("Accept-Ranges") == "bytes"
    assert response.read() == payload
    conn.close()

    conn = HTTPConnection(*server.server_address, timeout=5)
    conn.request(
        "GET",
        f"/api/download/{job_id}/clip.mp4",
        headers={"Cookie": cookie, "Range": "bytes=100-199"},
    )
    response = conn.getresponse()
    assert response.status == 206
    assert response.getheader("Content-Range") == f"bytes 100-199/{len(payload)}"
    assert response.read() == payload[100:200]
    conn.close()

    # Out-of-range start -> 416, not a crash or a silent 200.
    conn = HTTPConnection(*server.server_address, timeout=5)
    conn.request(
        "GET",
        f"/api/download/{job_id}/clip.mp4",
        headers={"Cookie": cookie, "Range": f"bytes={len(payload) + 10}-"},
    )
    response = conn.getresponse()
    assert response.status == 416
    response.read()
    conn.close()


def test_events_stream_pushes_job_changes(server: ClassyDLServer) -> None:
    cookie = _login(server)

    conn = HTTPConnection(*server.server_address, timeout=10)
    conn.request("GET", "/api/events", headers={"Cookie": cookie})
    response = conn.getresponse()
    assert response.status == 200
    assert response.getheader("Content-Type") == "text/event-stream"

    def read_event() -> str:
        # Read until a blank line terminates one SSE event.
        lines = []
        while True:
            line = response.fp.readline().decode("utf-8")
            if line in ("\n", "\r\n", ""):
                break
            lines.append(line.rstrip("\r\n"))
        return "\n".join(lines)

    # Initial snapshot arrives without any change happening first.
    first = read_event()
    assert first.startswith("data: ")
    assert json.loads(first[len("data: "):])["jobs"] == []

    # A queue write must push a fresh snapshot through the open stream.
    _, body, _ = _request(
        server, "POST", "/api/queue", {"source": "https://example.com/video"}, cookie=cookie
    )
    job_id = body["job_id"]
    event = read_event()
    while not event.startswith("data: "):  # skip keep-alive pings
        event = read_event()
    jobs = json.loads(event[len("data: "):])["jobs"]
    assert any(job["id"] == job_id for job in jobs)
    conn.close()


def test_events_stream_requires_auth(server: ClassyDLServer) -> None:
    status, _, _ = _request(server, "GET", "/api/events")
    assert status == 401


# ── security hardening ──────────────────────────────────────────────────

def _headers_for(server: ClassyDLServer, path: str, cookie: str | None = None) -> dict[str, str]:
    conn = HTTPConnection(*server.server_address, timeout=5)
    conn.request("GET", path, headers={"Cookie": cookie} if cookie else {})
    resp = conn.getresponse()
    resp.read()
    headers = {k.lower(): v for k, v in resp.getheaders()}
    conn.close()
    return headers


def test_security_headers_present_on_spa_and_api(server: ClassyDLServer) -> None:
    for path in ("/", "/api/health"):
        headers = _headers_for(server, path)
        assert "content-security-policy" in headers, path
        assert headers["x-frame-options"] == "DENY", path
        assert headers["x-content-type-options"] == "nosniff", path
        assert headers["referrer-policy"] == "no-referrer", path
        assert "frame-ancestors 'none'" in headers["content-security-policy"], path


def test_scrape_blocks_ssrf_to_loopback(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, body, _ = _request(
        server, "POST", "/api/scrape", {"url": "http://127.0.0.1:1/"}, cookie=cookie
    )
    assert status == 400
    assert "non-public" in body["detail"].lower()


def test_scrape_blocks_non_http_scheme(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, body, _ = _request(
        server, "POST", "/api/scrape", {"url": "file:///etc/passwd"}, cookie=cookie
    )
    assert status == 400
    assert "scheme" in body["detail"].lower()


def test_static_path_traversal_blocked(server: ClassyDLServer) -> None:
    # A 404 (not a file read) proves the resolve-containment check held.
    conn = HTTPConnection(*server.server_address, timeout=5)
    conn.request("GET", "/..%2f..%2f..%2fetc%2fpasswd")
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    assert resp.status == 404
    assert b"root:" not in body


def test_download_path_traversal_blocked(server: ClassyDLServer) -> None:
    cookie = _login(server)
    status, _, _ = _request(
        server, "GET", "/api/download/1/..%2f..%2f..%2fetc%2fpasswd", cookie=cookie
    )
    assert status == 404


def test_desktop_login_one_time_token(server: ClassyDLServer) -> None:
    token = server.issue_autologin_token()
    # A valid unused token exchanges for a session.
    status, body, set_cookie = _request(
        server, "POST", "/api/desktop-login", {"token": token}
    )
    assert status == 200
    assert body == {"authenticated": True}
    assert set_cookie and "classydl_session=" in set_cookie
    # Single-use: the same token is rejected the second time.
    status, _, _ = _request(server, "POST", "/api/desktop-login", {"token": token})
    assert status == 401
    # An unknown token is rejected.
    status, _, _ = _request(server, "POST", "/api/desktop-login", {"token": "nope"})
    assert status == 401


def test_session_cookie_secure_flag_is_opt_in(tmp_path: Path) -> None:
    store = QueueStore(tmp_path / "state.db")
    store.init()
    srv = create_server(
        store=store,
        output_dir=tmp_path / "downloads",
        password="crypt-keeper",
        host="127.0.0.1",
        port=0,
        workers=1,
        secure_cookies=True,
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        _, _, set_cookie = _request(srv, "POST", "/api/login", {"password": "crypt-keeper"})
        assert "Secure" in set_cookie
    finally:
        srv.shutdown()
        srv.stop_background_worker()
        srv.server_close()


def test_state_db_is_owner_only(tmp_path: Path) -> None:
    import os
    import stat

    store = QueueStore(tmp_path / "state.db")
    store.init()
    mode = stat.S_IMODE(os.stat(tmp_path / "state.db").st_mode)
    # No group/other bits (best-effort; on Windows chmod is advisory so we
    # only assert the intent held on POSIX).
    if os.name == "posix":
        assert mode & 0o077 == 0, oct(mode)
