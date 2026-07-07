from __future__ import annotations

import hashlib
import io
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from video_downloader import engine_update

FAKE_VERSION = "9999.1.1"  # newer than any real bundled yt-dlp


def build_fake_wheel(version: str = FAKE_VERSION, traversal: bool = False) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as wheel:
        wheel.writestr(
            "yt_dlp/__init__.py",
            "from . import version\n__version__ = version.__version__\n",
        )
        wheel.writestr("yt_dlp/version.py", f"__version__ = '{version}'\n")
        wheel.writestr("yt_dlp-%s.dist-info/METADATA" % version, "Name: yt-dlp\n")
        if traversal:
            wheel.writestr("yt_dlp/../evil.py", "print('escaped')\n")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def clean_engine_state():
    engine_update._reset_for_tests()
    try:
        yield
    finally:
        engine_update._reset_for_tests()


class FakeIndexHandler(BaseHTTPRequestHandler):
    wheel_bytes: bytes = b""
    version: str = FAKE_VERSION
    lie_about_sha: bool = False

    def log_message(self, *args):  # noqa: D102 - quiet test server
        pass

    def do_GET(self):
        if self.path == "/pypi/yt-dlp/json":
            sha = hashlib.sha256(self.wheel_bytes).hexdigest()
            if self.lie_about_sha:
                sha = "0" * 64
            body = json.dumps(
                {
                    "info": {"version": self.version},
                    "urls": [
                        {
                            "filename": f"yt_dlp-{self.version}-py3-none-any.whl",
                            # https in the JSON is required by check_latest; the
                            # test rewrites it back to the local server below.
                            "url": f"https://127.0.0.1:{self.server.server_address[1]}/wheel",
                            "digests": {"sha256": sha},
                        }
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/wheel":
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.wheel_bytes)))
            self.end_headers()
            self.wfile.write(self.wheel_bytes)
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture
def fake_index():
    handler = type("Handler", (FakeIndexHandler,), {"wheel_bytes": build_fake_wheel()})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, handler
    finally:
        server.shutdown()
        server.server_close()


def _install_direct(tmp_path: Path, wheel: bytes, version: str = FAKE_VERSION) -> None:
    """Install a wheel served from a one-shot local URL."""
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        type("H", (FakeIndexHandler,), {"wheel_bytes": wheel, "version": version}),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/wheel"
        sha = hashlib.sha256(wheel).hexdigest()
        engine_update.download_and_install(version, url, sha)
    finally:
        server.shutdown()
        server.server_close()


def test_activate_without_installed_engine_is_a_noop(tmp_path: Path) -> None:
    assert engine_update.activate(tmp_path) is None
    assert engine_update.active_version() == engine_update.bundled_version()


def test_install_apply_and_reactivate(tmp_path: Path) -> None:
    engine_update.activate(tmp_path)
    _install_direct(tmp_path, build_fake_wheel())

    current = json.loads((tmp_path / "engine" / "current.json").read_text())
    assert current["version"] == FAKE_VERSION

    # Hot swap into the running process.
    assert engine_update.apply_update() is True
    assert engine_update.active_version() == FAKE_VERSION
    module = engine_update.get_yt_dlp()
    assert module.version.__version__ == FAKE_VERSION

    # And a fresh process (reset + activate) picks it up at boot.
    engine_update._reset_for_tests()
    assert engine_update.activate(tmp_path) == FAKE_VERSION
    assert engine_update.get_yt_dlp().version.__version__ == FAKE_VERSION


def test_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    engine_update.activate(tmp_path)
    wheel = build_fake_wheel()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), type("H", (FakeIndexHandler,), {"wheel_bytes": wheel})
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/wheel"
        with pytest.raises(RuntimeError, match="checksum"):
            engine_update.download_and_install(FAKE_VERSION, url, "0" * 64)
    finally:
        server.shutdown()
        server.server_close()
    assert not (tmp_path / "engine" / "current.json").exists()
    assert list((tmp_path / "engine").glob("*.tmp")) == []


def test_downgrade_is_rejected(tmp_path: Path) -> None:
    engine_update.activate(tmp_path)
    bundled = engine_update.bundled_version()
    assert bundled is not None  # test env installs yt-dlp normally
    wheel = build_fake_wheel(version="1.0.0")
    with pytest.raises(RuntimeError, match="downgrade"):
        _install_direct(tmp_path, wheel, version="1.0.0")


def test_path_traversal_in_wheel_is_rejected(tmp_path: Path) -> None:
    engine_update.activate(tmp_path)
    wheel = build_fake_wheel(traversal=True)
    with pytest.raises(RuntimeError, match="suspicious"):
        _install_direct(tmp_path, wheel)
    assert not (tmp_path / "engine" / "current.json").exists()
    assert not (tmp_path / "evil.py").exists()


def test_corrupted_state_falls_back_to_bundled(tmp_path: Path) -> None:
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir(parents=True)
    (engine_dir / "current.json").write_text(
        json.dumps({"version": FAKE_VERSION, "path": "yt_dlp-9999.1.1"})
    )
    # ...but the referenced directory doesn't exist.
    assert engine_update.activate(tmp_path) is None
    assert not (engine_dir / "current.json").exists()  # forgotten for good
    assert engine_update.active_version() == engine_update.bundled_version()


def test_ensure_latest_full_flow_and_throttle(tmp_path: Path, fake_index, monkeypatch) -> None:
    server, handler = fake_index
    port = server.server_address[1]
    monkeypatch.setattr(
        engine_update, "PYPI_JSON_URL", f"http://127.0.0.1:{port}/pypi/yt-dlp/json"
    )
    # check_latest requires https URLs from the index; rewrite for the test.
    real_check = engine_update.check_latest

    def check_with_local_url():
        version, url, sha = real_check()
        return version, url.replace("https://", "http://"), sha

    monkeypatch.setattr(engine_update, "check_latest", check_with_local_url)

    engine_update.activate(tmp_path)
    updated, version = engine_update.ensure_latest(force=True)
    assert updated is True
    assert version == FAKE_VERSION
    assert engine_update.active_version() == FAKE_VERSION

    # Second call: nothing newer, and the hourly throttle short-circuits
    # non-forced calls entirely.
    updated, version = engine_update.ensure_latest()
    assert updated is False
    assert version == FAKE_VERSION


def test_check_latest_against_real_pypi() -> None:
    # Integration check that PyPI's JSON shape still matches what we parse.
    # Skips cleanly when the sandbox/CI has no route to pypi.org.
    try:
        version, url, sha256 = engine_update.check_latest()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PyPI unreachable: {exc}")
    assert version
    assert url.startswith("https://")
    assert len(sha256) == 64
