"""HTML → PNG/PDF über ein lokales Chromium (headless).

Kein Playwright-Python nötig: das Chromium-CLI reicht für pixelgenaue Screenshots
und druckfähige PDFs. Der Renderer schreibt das gerenderte HTML in ein Build-
Verzeichnis neben den Assets, damit relative ``file://``-Pfade (Fonts,
Screenshots) funktionieren.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = REPO_ROOT / "creator_tools" / "assets"
SCREENSHOTS_DIR = REPO_ROOT / "store_assets"

_CHROME_CANDIDATES = (
    os.environ.get("CREATOR_CHROME_BIN", ""),
    "/opt/pw-browsers/chromium",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
    shutil.which("google-chrome") or "",
)


class RendererError(RuntimeError):
    pass


def find_chrome() -> str:
    for cand in _CHROME_CANDIDATES:
        if cand and Path(cand).exists():
            return cand
    raise RendererError(
        "Kein Chromium gefunden. Installiere Chromium oder setze CREATOR_CHROME_BIN "
        "auf den Pfad einer Chrome/Chromium-Binary. Das Rendering ist ein reines "
        "Desktop-/CI-Werkzeug und wird auf Termux nicht benötigt."
    )


def _run_chrome(args: list[str], html: str, workdir: Path) -> None:
    page = workdir / "page.html"
    page.write_text(html, encoding="utf-8")
    cmd = [
        find_chrome(),
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        "--default-background-color=00000000",
        "--virtual-time-budget=4000",
        *args,
        f"file://{page}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RendererError(f"Chromium-Render fehlgeschlagen:\n{proc.stderr[-2000:]}")


def _inject_paths(html: str) -> str:
    """Ersetzt die Asset-Marker durch absolute file://-Pfade."""
    return html.replace("__KIT_ASSETS__", ASSETS_DIR.as_uri()).replace(
        "__STORE_ASSETS__", SCREENSHOTS_DIR.as_uri()
    )


# Headless-Chromium zieht ~88px "Fenster-Chrome" von --window-size ab (alt wie
# neu, empirisch verifiziert). Wir fordern deshalb mehr Höhe an und schneiden
# das Ergebnis exakt auf die Zielgröße zu.
_VIEWPORT_SLACK = 120


def html_to_png(html: str, out_png: Path, width: int, height: int) -> Path:
    from PIL import Image

    out_png.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ckit-") as td:
        _run_chrome(
            [f"--window-size={width},{height + _VIEWPORT_SLACK}", f"--screenshot={out_png}"],
            _inject_paths(html),
            Path(td),
        )
    if not out_png.exists():
        raise RendererError(f"Screenshot wurde nicht geschrieben: {out_png}")
    with Image.open(out_png) as im:
        if im.size != (width, height):
            im.convert("RGB").crop((0, 0, width, height)).save(out_png, optimize=True)
        else:
            im.convert("RGB").save(out_png, optimize=True)
    return out_png


def html_to_pdf(html: str, out_pdf: Path) -> Path:
    """Druckt HTML nach PDF; das Seitenformat kommt aus @page-CSS im Template."""
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ckit-") as td:
        _run_chrome(
            ["--no-pdf-header-footer", f"--print-to-pdf={out_pdf}"],
            _inject_paths(html),
            Path(td),
        )
    if not out_pdf.exists():
        raise RendererError(f"PDF wurde nicht geschrieben: {out_pdf}")
    return out_pdf


def png_to_webp(png: Path, webp: Path | None = None, quality: int = 82) -> Path:
    """Kleine WebP-Vorschau für die HTML-Übersichtsseiten."""
    from PIL import Image

    webp = webp or png.with_suffix(".webp")
    with Image.open(png) as im:
        im.save(webp, "WEBP", quality=quality, method=6)
    return webp
