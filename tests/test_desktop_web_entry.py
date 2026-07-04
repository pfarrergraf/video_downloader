from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

import classydl_web_entry


class FakeServer:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.closed = False
        self.served = False

    def start_background_worker(self) -> None:
        self.started = True

    def serve_forever(self) -> None:
        self.served = True

    def stop_background_worker(self) -> None:
        self.stopped = True

    def server_close(self) -> None:
        self.closed = True


def _token_from_url(url: str) -> str:
    parsed = urlsplit(url)
    return parse_qs(parsed.query)["t"][0]


def test_password_is_generated_once_and_reused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CLASSYDL_DATA_DIR", str(tmp_path))

    opened: list[str] = []
    created_passwords: list[str] = []
    license_managers: list[object] = []
    servers: list[FakeServer] = []

    def fake_open(url: str) -> bool:
        opened.append(url)
        return True

    def fake_create_server(**kwargs):
        created_passwords.append(kwargs["password"])
        license_managers.append(kwargs["license_manager"])
        server = FakeServer()
        servers.append(server)
        return server

    monkeypatch.setattr("webbrowser.open", fake_open)
    monkeypatch.setattr("video_downloader.web.server.create_server", fake_create_server)

    classydl_web_entry.main()
    classydl_web_entry.main()

    assert len(created_passwords) == 2
    assert created_passwords[0] == created_passwords[1]
    assert (tmp_path / "web_password.txt").read_text(encoding="utf-8").strip() == created_passwords[0]
    assert (tmp_path / "license.json").parent == tmp_path
    assert all(manager is not None for manager in license_managers)
    assert _token_from_url(opened[0]) == created_passwords[0]
    assert _token_from_url(opened[1]) == created_passwords[0]
    assert all(server.started and server.served and server.stopped and server.closed for server in servers)


def test_bind_failure_opens_existing_instance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CLASSYDL_DATA_DIR", str(tmp_path))
    (tmp_path / "web_password.txt").write_text("existing-token\n", encoding="utf-8")

    opened: list[str] = []

    def fake_open(url: str) -> bool:
        opened.append(url)
        return True

    def fake_create_server(**kwargs):
        assert kwargs["license_manager"] is not None
        raise OSError("address already in use")

    monkeypatch.setattr("webbrowser.open", fake_open)
    monkeypatch.setattr("video_downloader.web.server.create_server", fake_create_server)

    classydl_web_entry.main()

    assert len(opened) == 1
    assert opened[0].startswith("http://127.0.0.1:8420/desktop_autologin.html?")
    assert _token_from_url(opened[0]) == "existing-token"
