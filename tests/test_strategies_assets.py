from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from video_downloader.models import DownloadRequest
from video_downloader.strategies import DirectDownloadStrategy, StrategyError

IMAGE_PAYLOAD = b"\xff\xd8\xff" + b"fake-jpeg-bytes" * 10
PDF_PAYLOAD = b"%PDF-1.4\n" + b"fake-pdf-bytes" * 10


class AssetHandler(BaseHTTPRequestHandler):
    """Serves a fixed body + Content-Type per path, no Range support needed here."""

    def log_message(self, *args):  # noqa: D102 - quiet test server
        pass

    def do_GET(self):
        if self.path == "/photo.jpg":
            body, content_type = IMAGE_PAYLOAD, "image/jpeg"
        elif self.path == "/report.pdf":
            body, content_type = PDF_PAYLOAD, "application/pdf"
        elif self.path == "/no-extension-image":
            body, content_type = IMAGE_PAYLOAD, "image/jpeg"
        elif self.path == "/page.html":
            body, content_type = b"<html>not an asset</html>", "text/html"
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def asset_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), AssetHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def test_direct_download_accepts_image_by_extension(tmp_path: Path, asset_server: str) -> None:
    request = DownloadRequest(source_url=f"{asset_server}/photo.jpg", output_dir=tmp_path)
    result = DirectDownloadStrategy().download(request, f"{asset_server}/photo.jpg")
    assert result.file_path.read_bytes() == IMAGE_PAYLOAD
    assert result.file_path.suffix == ".jpg"


def test_direct_download_accepts_pdf_by_extension(tmp_path: Path, asset_server: str) -> None:
    request = DownloadRequest(source_url=f"{asset_server}/report.pdf", output_dir=tmp_path)
    result = DirectDownloadStrategy().download(request, f"{asset_server}/report.pdf")
    assert result.file_path.read_bytes() == PDF_PAYLOAD
    assert result.file_path.suffix == ".pdf"


def test_direct_download_accepts_image_by_content_type_without_extension(
    tmp_path: Path, asset_server: str
) -> None:
    # No file extension in the URL - only the Content-Type header identifies
    # this as an image, which is exactly the case guess_extension's mimetypes
    # fallback (added alongside this feature) needs to name the file correctly.
    request = DownloadRequest(source_url=f"{asset_server}/no-extension-image", output_dir=tmp_path)
    result = DirectDownloadStrategy().download(request, f"{asset_server}/no-extension-image")
    assert result.file_path.read_bytes() == IMAGE_PAYLOAD
    assert result.file_path.suffix == ".jpg"


def test_direct_download_still_rejects_html_pages(tmp_path: Path, asset_server: str) -> None:
    # Regression guard: the widened acceptance must not start treating
    # ordinary HTML responses as downloadable media/assets.
    request = DownloadRequest(source_url=f"{asset_server}/page.html", output_dir=tmp_path)
    with pytest.raises(StrategyError):
        DirectDownloadStrategy().download(request, f"{asset_server}/page.html")
