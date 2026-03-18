import os
import sys

# PyInstaller frozen-app support: multiprocessing would need freeze_support()
# here but the app only uses threading – keep this guard for safety.
if getattr(sys, "frozen", False):
    import multiprocessing
    multiprocessing.freeze_support()

    # Make bundled binaries (ffmpeg, aria2c) discoverable via PATH
    _bundled = os.path.join(sys._MEIPASS, "bundled_bins")
    if os.path.isdir(_bundled):
        os.environ["PATH"] = _bundled + os.pathsep + os.environ.get("PATH", "")

from video_downloader.cli import main


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # In a windowed (no-console) build, unhandled exceptions vanish silently.
        # Show a crash dialog so the user sees what went wrong.
        if getattr(sys, "frozen", False):
            import traceback
            try:
                from tkinter import Tk, messagebox
                root = Tk()
                root.withdraw()
                messagebox.showerror(
                    "ClassyDL – Fatal Error",
                    traceback.format_exc(),
                )
                root.destroy()
            except Exception:
                pass
        raise
