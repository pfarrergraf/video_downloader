import os
import sys

# PyInstaller frozen-app support: multiprocessing would need freeze_support()
# here but the app only uses threading - keep this guard for safety.
if getattr(sys, "frozen", False):
    import multiprocessing

    multiprocessing.freeze_support()

    # Make bundled binaries (ffmpeg, aria2c) discoverable via PATH.
    _bundled = os.path.join(sys._MEIPASS, "bundled_bins")
    if os.path.isdir(_bundled):
        os.environ["PATH"] = _bundled + os.pathsep + os.environ.get("PATH", "")


LICENSE_API_BASE = os.environ.get("CLASSYDL_LICENSE_API_BASE", "https://downloadthat.pages.dev")


def _show_crash_dialog() -> None:
    if not getattr(sys, "frozen", False):
        return
    import traceback

    try:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        messagebox.showerror("ClassyDL Web - Fatal Error", traceback.format_exc())
        root.destroy()
    except Exception:
        pass


_PLATFORM_NAMES = {"windows": "windows", "darwin": "macos", "linux": "linux"}


def main() -> None:
    import platform as platform_module
    import secrets
    import webbrowser
    from pathlib import Path
    from urllib.parse import quote

    from video_downloader.app_config import load_or_create_config, resolve_paths
    from video_downloader.licensing import LicenseManager
    from video_downloader.logging_setup import configure_logging
    from video_downloader.queue_store import QueueStore
    from video_downloader.utils import ensure_output_dir
    from video_downloader.web.server import create_server

    host = "127.0.0.1"
    port = 8420

    paths = resolve_paths()
    config = load_or_create_config(paths)
    configure_logging(paths)

    store = QueueStore(paths.state_db)
    store.init()

    password_path = paths.config_file.parent / "web_password.txt"
    password_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        password = password_path.read_text(encoding="utf-8").strip()
    except OSError:
        password = ""
    if not password:
        password = secrets.token_hex(32)
        password_path.write_text(password + "\n", encoding="utf-8")
    # The web password is a long-lived secret; keep it owner-only so a
    # co-tenant on a multi-user host can't read it (best-effort on Windows,
    # where POSIX modes are advisory).
    try:
        os.chmod(password_path, 0o600)
    except OSError:
        pass

    output_dir = ensure_output_dir(Path(config.default_output_dir).expanduser().resolve())
    workers = max(1, min(int(config.default_workers), int(config.max_workers), 8))
    platform_name = _PLATFORM_NAMES.get(platform_module.system().lower(), platform_module.system().lower())
    license_manager = LicenseManager(
        paths.config_file.parent / "license.json", LICENSE_API_BASE, platform=platform_name
    )

    try:
        server = create_server(
            store=store,
            output_dir=output_dir,
            password=password,
            host=host,
            port=port,
            workers=workers,
            license_manager=license_manager,
        )
    except OSError:
        # Most likely another ClassyDL desktop-web instance is already bound to
        # the fixed local port. That instance already holds the user's session
        # cookie (30-day TTL), so just open the root - no secret in the URL,
        # and we can't mint a one-time token on a server we didn't create.
        webbrowser.open(f"http://{host}:{port}/")
        return

    server.start_background_worker()
    # Hand the browser a single-use token instead of the password: the token
    # is redeemed once at /api/desktop-login and expires in seconds, so it's
    # safe to leave in history/referrer.
    autologin_url = f"http://{host}:{port}/desktop_autologin.html?t={quote(server.issue_autologin_token())}"
    webbrowser.open(autologin_url)
    try:
        server.serve_forever()
    finally:
        server.stop_background_worker()
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _show_crash_dialog()
        raise
