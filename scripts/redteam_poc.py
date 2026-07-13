"""Red-Team PoC harness for ClassyDL / DownloadThat.

Runs the runnable attacks (A3 SSRF, A4 file perms, A6 brute-force, A7 headers,
A8 path traversal) against a live local ClassyDLServer instance. Prints a
machine-readable PASS/FAIL-per-hypothesis summary. Run before and after the
hardening to capture the delta.
"""
from __future__ import annotations

import http.client
import json
import os
import stat
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from video_downloader.queue_store import QueueStore
from video_downloader.web import server as srv

PASSWORD = "correct-horse-battery-staple"


def _login(conn: http.client.HTTPConnection) -> str:
    conn.request("POST", "/api/login", json.dumps({"password": PASSWORD}),
                 {"Content-Type": "application/json"})
    resp = conn.getresponse()
    cookie = resp.getheader("Set-Cookie", "") or ""
    resp.read()
    return cookie.split(";")[0] if cookie else ""


class _InternalService(BaseHTTPRequestHandler):
    """Stands in for an internal-only HTTP endpoint (e.g. cloud metadata)."""
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><img src='http://169.254.169.254/secret.png'></body></html>")

    def log_message(self, *a):  # noqa: N802
        pass


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="poc-"))
    store = QueueStore(tmp / "state.db")
    store.init()
    server = srv.create_server(
        store=store, output_dir=tmp / "out", password=PASSWORD,
        host="127.0.0.1", port=0,
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]

    # internal service on its own loopback port
    internal = ThreadingHTTPServer(("127.0.0.1", 0), _InternalService)
    threading.Thread(target=internal.serve_forever, daemon=True).start()
    internal_port = internal.server_address[1]

    conn = http.client.HTTPConnection("127.0.0.1", port)
    cookie = _login(conn)
    results: dict[str, str] = {}

    # ── A6: brute-force lockout ────────────────────────────────────────
    fresh = http.client.HTTPConnection("127.0.0.1", port)
    codes = []
    for _ in range(6):
        fresh.request("POST", "/api/login", json.dumps({"password": "x"}),
                      {"Content-Type": "application/json"})
        r = fresh.getresponse(); r.read(); codes.append(r.status)
    results["A6_bruteforce"] = (
        f"lockout={'YES' if 429 in codes else 'NO'} codes={codes}"
    )

    # ── A7: security headers on the SPA ────────────────────────────────
    conn.request("GET", "/", headers={"Cookie": cookie})
    r = conn.getresponse(); r.read()
    hdrs = {k.lower(): v for k, v in r.getheaders()}
    present = [h for h in ("content-security-policy", "x-frame-options",
                           "x-content-type-options", "referrer-policy") if h in hdrs]
    results["A7_headers"] = f"present={present or 'NONE'}"

    # ── A8: path traversal on download + static ────────────────────────
    conn.request("GET", "/api/download/1/..%2f..%2f..%2fetc%2fpasswd", headers={"Cookie": cookie})
    r = conn.getresponse(); r.read(); dl_status = r.status
    conn.request("GET", "/..%2f..%2f..%2fetc%2fpasswd", headers={"Cookie": cookie})
    r = conn.getresponse(); body = r.read(); st_status = r.status
    leaked = b"root:" in body
    results["A8_traversal"] = f"download={dl_status} static={st_status} leaked_passwd={leaked}"

    # ── A3: SSRF via /api/scrape to an internal loopback service ───────
    conn.request("POST", "/api/scrape",
                 json.dumps({"url": f"http://127.0.0.1:{internal_port}/"}),
                 {"Content-Type": "application/json", "Cookie": cookie})
    r = conn.getresponse(); body = json.loads(r.read() or b"{}")
    items = body.get("items", [])
    if r.status == 200 and items:
        results["A3_ssrf"] = f"REACHED internal service, items={len(items)} (VULNERABLE)"
    else:
        results["A3_ssrf"] = f"BLOCKED status={r.status} detail={str(body.get('detail',''))[:90]}"

    # ── A4: file permissions of state.db ───────────────────────────────
    mode = stat.S_IMODE(os.stat(tmp / "state.db").st_mode)
    results["A4_fileperms"] = f"state.db mode={oct(mode)} ({'world-readable' if mode & 0o077 else 'restricted'})"

    server.shutdown(); internal.shutdown()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
