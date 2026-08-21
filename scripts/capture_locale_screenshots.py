"""Capture a home-screen screenshot of the app for every supported locale,
in both light and dark theme.

For the Play Console per-locale screenshot requirement. Drives a real
Chromium (Pixel 7 emulation, matching the existing English screenshots in
store_assets/) against a local ``classydl web`` instance and switches
language and theme in-page via the same ``setLanguage()``/``applyTheme()``
the settings dropdowns use, so what's captured is exactly what a user sees.

Usage:
    .venv-win/Scripts/python.exe scripts/capture_locale_screenshots.py [out_dir]

Requires Playwright + the Chromium browser (not a project dependency —
install ad hoc: ``uv pip install playwright && playwright install chromium``).
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from video_downloader.queue_store import QueueStore  # noqa: E402
from video_downloader.web.server import create_server  # noqa: E402

PASSWORD = "screenshot-capture"
I18N_DIR = REPO_ROOT / "video_downloader" / "web" / "static" / "i18n"


def locale_codes() -> list[str]:
    codes = sorted(p.stem for p in I18N_DIR.glob("*.json"))
    # en first (baseline), then everything else alphabetically.
    codes.remove("en")
    return ["en"] + codes


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "store_assets" / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        store = QueueStore(tmp_path / "state.db")
        store.init()
        srv = create_server(
            store=store,
            output_dir=tmp_path / "downloads",
            password=PASSWORD,
            host="127.0.0.1",
            port=0,
            workers=1,
        )
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        host, port = srv.server_address
        base_url = f"http://{host}:{port}"

        try:
            with sync_playwright() as p:
                device = dict(p.devices["Pixel 7"])
                # Play Console rejects screenshots whose long side exceeds 2x the
                # short side. The stock Pixel 7 device profile (412x839 @2.625x)
                # renders at 1082x2202 -> ratio 2.035, just over the 2.0 cap that
                # was already being silently violated by the pre-existing English
                # screenshots. Trim the viewport height so the captured PNG lands
                # comfortably inside the limit.
                device["viewport"] = {**device["viewport"], "height": 824}
                browser = p.chromium.launch()
                context = browser.new_context(**device, reduced_motion="reduce")
                page = context.new_page()
                page.goto(base_url)
                page.fill("#login-password", PASSWORD)
                page.click("#login-btn")
                page.wait_for_selector("#terms-overlay:not(.hidden), #app:not(.hidden)")
                if page.locator("#terms-overlay:not(.hidden)").count():
                    page.check("#terms-checkbox")
                    page.click("#terms-accept-btn")
                page.wait_for_selector("#app:not(.hidden)")

                for code in locale_codes():
                    page.evaluate("(code) => window.setLanguage(code)", code)
                    page.wait_for_timeout(150)  # let fetch()+DOM updates settle
                    for theme, suffix in (("light", ""), ("dark", "_dark")):
                        page.evaluate("(t) => window.applyTheme(t)", theme)
                        page.wait_for_timeout(50)
                        dest = out_dir / f"screenshot_main_{code}{suffix}.png"
                        page.screenshot(path=str(dest))
                        print(f"captured {dest.name}")

                context.close()
                browser.close()
        finally:
            srv.shutdown()
            srv.stop_background_worker()
            srv.server_close()


if __name__ == "__main__":
    main()
