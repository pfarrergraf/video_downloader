"""QR-Codes für Affiliate-Links — als SVG-Snippet für die HTML-Templates.

Regeln (siehe Auftrag): hoher Kontrast, ruhige Zone von >= 4 Modulen, kein Logo
über den Modulen, keine erfundenen Ziel-URLs. Fehlerkorrektur "Q", damit der
Code auch gedruckt/abfotografiert lesbar bleibt.
"""

from __future__ import annotations

import io
import re

import segno


class QRError(ValueError):
    pass


def qr_svg(url: str, dark: str = "#14111c", light: str = "#ffffff") -> str:
    """Liefert ein <svg>…</svg>-Snippet (skaliert über CSS auf Zielgröße)."""
    if not url or not url.startswith(("https://", "http://")):
        raise QRError(
            f"QR-Ziel muss eine echte http(s)-URL sein, bekommen: {url!r}. "
            "Erfundene Ziel-URLs sind nicht erlaubt."
        )
    qr = segno.make(url, error="q")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", xmldecl=False, svgns=True, border=4, dark=dark, light=light)
    svg = buf.getvalue().decode("utf-8")
    # segno schreibt feste width/height ohne viewBox — für CSS-Skalierung beides
    # gegen eine viewBox tauschen, sonst bleibt der Code winzig in der Ecke.
    m = re.search(r'width="(\d+)" height="(\d+)"', svg)
    if m:
        w, h = m.group(1), m.group(2)
        svg = svg.replace(m.group(0), f'viewBox="0 0 {w} {h}"', 1)
    return svg
