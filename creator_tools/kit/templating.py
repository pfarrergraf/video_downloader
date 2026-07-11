"""Winziges Mustache-Subset für die Creator-Kit-Templates.

Bewusst ohne Jinja/Fremdabhängigkeit (Termux-Regel des Repos): unterstützt genau
das, was die Templates brauchen —

* ``{{key}}``            HTML-escaped Ersetzung, ``{{{key}}}`` roh (für CSS/URLs/Partials)
* ``{{#key}}…{{/key}}``  Block nur, wenn der Wert truthy ist (leerer String/None/False → weg)
* ``{{^key}}…{{/key}}``  Block nur, wenn der Wert falsy ist
* ``{{>name}}``          Partial aus ``templates/partials/<name>.html``
* Punktpfade wie ``{{pro.price}}`` und Listenindizes wie ``{{steps.de.0}}``

Fehlende Schlüssel sind ein harter Fehler — Tippfehler in Templates sollen beim
Rendern auffallen, nicht als leere Stelle im fertigen Bild.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_TAG = re.compile(r"\{\{\{(.+?)\}\}\}|\{\{([#^/>]?)\s*([\w.]+|.+?)\s*\}\}")


class TemplateError(KeyError):
    pass


def lookup(ctx: dict, path: str):
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                raise TemplateError(f"Unbekannter Template-Schlüssel: {path!r}")
            cur = cur[part]
        elif isinstance(cur, (list, tuple)):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError) as exc:
                raise TemplateError(f"Ungültiger Listenzugriff: {path!r}") from exc
        else:
            raise TemplateError(f"Pfad {path!r} führt durch einen Skalar")
    return cur


def _render(text: str, ctx: dict, partials_dir: Path) -> str:
    out: list[str] = []
    pos = 0
    while True:
        m = _TAG.search(text, pos)
        if not m:
            out.append(text[pos:])
            return "".join(out)
        out.append(text[pos : m.start()])
        raw_key, sigil, key = m.group(1), m.group(2) or "", m.group(3)
        if raw_key is not None:  # {{{roh}}}
            out.append(str(lookup(ctx, raw_key.strip())))
            pos = m.end()
        elif sigil == ">":
            partial = (partials_dir / f"{key}.html").read_text(encoding="utf-8")
            out.append(_render(partial, ctx, partials_dir))
            pos = m.end()
        elif sigil and sigil in "#^":
            close = re.compile(r"\{\{/\s*" + re.escape(key) + r"\s*\}\}")
            cm = close.search(text, m.end())
            if not cm:
                raise TemplateError(f"Block {{{{{sigil}{key}}}}} wird nicht geschlossen")
            try:
                val = lookup(ctx, key)
            except TemplateError:
                val = None  # Bedingungen dürfen auf optionale Schlüssel prüfen
            truthy = bool(val)
            if (truthy and sigil == "#") or (not truthy and sigil == "^"):
                out.append(_render(text[m.end() : cm.start()], ctx, partials_dir))
            pos = cm.end()
        elif sigil == "/":
            raise TemplateError(f"Unerwartetes Block-Ende: {{{{/{key}}}}}")
        else:
            out.append(html.escape(str(lookup(ctx, key)), quote=False))
            pos = m.end()


def render_string(text: str, ctx: dict, partials_dir: Path | None = None) -> str:
    return _render(text, ctx, partials_dir or TEMPLATES_DIR / "partials")


def render_template(relpath: str, ctx: dict) -> str:
    """Rendert templates/<relpath> mit dem gegebenen Kontext."""
    path = TEMPLATES_DIR / relpath
    if not path.exists():
        raise FileNotFoundError(f"Template fehlt: {path}")
    return render_string(path.read_text(encoding="utf-8"), ctx)
