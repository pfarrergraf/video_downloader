from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from video_downloader.models import DownloadRequest
from video_downloader.strategies import (
    DirectDownloadStrategy,
    DownloadCancelled,
    _find_new_files,
)

PAYLOAD = bytes(range(256)) * 512  # 128 KiB, content-addressable by offset


class RangeHandler(BaseHTTPRequestHandler):
    """Minimal static server WITH Range support (http.server has none)."""

    def log_message(self, *args):  # noqa: D102 - quiet test server
        pass

    def do_GET(self):
        start = 0
        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            start = int(range_header.split("=")[1].rstrip("-"))
            if start >= len(PAYLOAD):
                self.send_response(416)
                self.end_headers()
                return
            self.send_response(206)
            self.send_header(
                "Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}"
            )
        else:
            self.send_response(200)
        body = PAYLOAD[start:]
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def range_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/clip.mp4"
    finally:
        server.shutdown()
        server.server_close()


def test_direct_download_resumes_from_partial_via_range(tmp_path: Path, range_server: str) -> None:
    # Simulate a previous attempt that got the first 40,000 bytes: the
    # strategy must ask for the rest (Range) and stitch a correct file.
    partial = tmp_path / "clip.mp4.part"
    partial.write_bytes(PAYLOAD[:40_000])

    reports: list[tuple[int, int | None]] = []
    request = DownloadRequest(
        source_url=range_server,
        output_dir=tmp_path,
        progress_callback=lambda done, total: reports.append((done, total)),
    )
    result = DirectDownloadStrategy().download(request, range_server)

    assert result.file_path.read_bytes() == PAYLOAD
    assert not partial.exists()
    # Progress reporting counts the resumed bytes toward the total.
    if reports:
        assert reports[-1][1] == len(PAYLOAD)


def test_direct_download_fresh_when_no_partial(tmp_path: Path, range_server: str) -> None:
    request = DownloadRequest(source_url=range_server, output_dir=tmp_path)
    result = DirectDownloadStrategy().download(request, range_server)
    assert result.file_path.read_bytes() == PAYLOAD


def test_direct_download_restarts_when_partial_is_complete(tmp_path: Path, range_server: str) -> None:
    # A .part that already covers the whole file gets a 416 - the strategy
    # must recover by starting over, not crash.
    partial = tmp_path / "clip.mp4.part"
    partial.write_bytes(PAYLOAD)

    request = DownloadRequest(source_url=range_server, output_dir=tmp_path)
    result = DirectDownloadStrategy().download(request, range_server)
    assert result.file_path.read_bytes() == PAYLOAD


def test_direct_download_honors_cancel_check(tmp_path: Path, range_server: str) -> None:
    request = DownloadRequest(
        source_url=range_server,
        output_dir=tmp_path,
        cancel_check=lambda: True,
    )
    with pytest.raises(DownloadCancelled):
        DirectDownloadStrategy().download(request, range_server)


def test_find_new_files_skips_partials_and_markers(tmp_path: Path) -> None:
    (tmp_path / "video.mp4").write_bytes(b"real")
    (tmp_path / "video.mp4.part").write_bytes(b"partial")
    (tmp_path / "video.mp4.ytdl").write_bytes(b"state")
    (tmp_path / "video.mp4.mediastore-published").write_bytes(b"")
    (tmp_path / "video.mp4.folder-exported").write_bytes(b"")

    found = _find_new_files(tmp_path, before=set())
    assert [p.name for p in found] == ["video.mp4"]
