"""Baut den Template-Kontext: Produktfakten + Creator-Personalisierung.

Die Produktfakten (``config/product_facts.json``) sind die einzige Quelle für
Preise, Limits und Programm-Konditionen. Creator-Configs personalisieren nur —
sie können keine Produktaussagen überschreiben.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

REQUIRED_CREATOR_KEYS = ("creator_name", "affiliate_code", "affiliate_link")

LANGS = ("de", "en")


class ConfigError(ValueError):
    pass


def load_facts() -> dict:
    return json.loads((CONFIG_DIR / "product_facts.json").read_text(encoding="utf-8"))


def load_creator(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Creator-Config nicht gefunden: {p}")
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Creator-Config ist kein gültiges JSON ({p}): {exc}") from exc
    missing = [k for k in REQUIRED_CREATOR_KEYS if not cfg.get(k)]
    if missing:
        raise ConfigError(
            f"Creator-Config {p} unvollständig, es fehlen: {', '.join(missing)}"
        )
    link = str(cfg["affiliate_link"])
    if not link.startswith(("https://", "http://")):
        raise ConfigError(f"affiliate_link muss eine http(s)-URL sein: {link!r}")
    if cfg.get("discount_text") and not cfg.get("discount_confirmed"):
        raise ConfigError(
            "discount_text ist gesetzt, aber es existiert kein Rabatt im Programm "
            "(Version 1: kein Kundenrabatt). Entferne discount_text oder setze "
            "discount_confirmed=true, wenn der Betreiber einen Rabatt schriftlich "
            "bestätigt hat."
        )
    cfg.setdefault("creator_handle", "@" + str(cfg["creator_name"]).lower().replace(" ", ""))
    cfg.setdefault("language", "de")
    cfg.setdefault("style", "creator-energy")
    cfg.setdefault("cta", "")
    cfg.setdefault("discount_text", "")
    cfg.setdefault("initial", str(cfg["creator_name"])[:1].upper())
    if cfg["language"] not in LANGS:
        raise ConfigError(f"language muss eines von {LANGS} sein: {cfg['language']!r}")
    return cfg


def build_context(lang: str = "de", creator: dict | None = None, **extra) -> dict:
    """Kontext für ein Template: Fakten, Sprachauswahl, optionale Personalisierung."""
    if lang not in LANGS:
        raise ConfigError(f"Unbekannte Sprache: {lang!r}")
    facts = load_facts()
    other = "en" if lang == "de" else "de"
    ctx: dict = {
        "f": facts,
        "lang": lang,
        "other_lang": other,
        "is_de": lang == "de",
        "t": _localized(facts, lang),
        "creator": creator or {},
        "personalized": bool(creator),
    }
    ctx.update(extra)
    return ctx


def _localized(node, lang: str):
    """Klappt {de:…, en:…}-Knoten rekursiv auf die gewählte Sprache um."""
    if isinstance(node, dict):
        keys = set(node.keys())
        if keys and keys <= {"de", "en"} and lang in node:
            return node[lang]
        return {k: _localized(v, lang) for k, v in node.items()}
    if isinstance(node, list):
        return [_localized(v, lang) for v in node]
    return node
