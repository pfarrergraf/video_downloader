"""Tests für das Creator-Kit-Werkzeug (creator_tools/).

Rendering-Tests (Chromium/ffmpeg) sind als optionale Smoke-Tests markiert und
werden übersprungen, wenn die Werkzeuge fehlen — die Logik-Tests laufen überall.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "creator_tools"))

from kit.context import ConfigError, build_context, load_creator, load_facts  # noqa: E402
from kit.templating import TemplateError, render_string  # noqa: E402

segno = pytest.importorskip("segno", reason="creator-Extra nicht installiert (uv sync --extra creator)")
from kit.qrcodes import QRError, qr_svg  # noqa: E402


# ---------------------------------------------------------------------------
# Templating
# ---------------------------------------------------------------------------
def test_token_ersetzung_und_escaping():
    out = render_string("Hallo {{name}}!", {"name": "<b>Max & Moritz</b>"})
    assert out == "Hallo &lt;b&gt;Max &amp; Moritz&lt;/b&gt;!"


def test_raw_token_bleibt_html():
    assert render_string("{{{html}}}", {"html": "<i>x</i>"}) == "<i>x</i>"


def test_bedingte_bloecke():
    tpl = "{{#a}}JA{{/a}}{{^a}}NEIN{{/a}}"
    assert render_string(tpl, {"a": "x"}) == "JA"
    assert render_string(tpl, {"a": ""}) == "NEIN"


def test_punktpfade_und_listen():
    ctx = {"f": {"pro": {"price": "12 €"}}, "steps": ["a", "b"]}
    assert render_string("{{f.pro.price}}/{{steps.1}}", ctx) == "12 €/b"


def test_unbekannter_schluessel_ist_harter_fehler():
    with pytest.raises(TemplateError):
        render_string("{{gibt.es.nicht}}", {})


# ---------------------------------------------------------------------------
# Fakten & Kontext
# ---------------------------------------------------------------------------
def test_fakten_stimmen_mit_code_ueberein():
    """Werbeaussagen dürfen nie vom echten Produktstand abweichen."""
    facts = load_facts()
    from video_downloader.licensing import FREE_DAILY_DOWNLOAD_LIMIT

    assert facts["free_tier"]["downloads_per_day"] == FREE_DAILY_DOWNLOAD_LIMIT
    assert str(FREE_DAILY_DOWNLOAD_LIMIT) in facts["free_tier"]["text"]["de"]
    # Kein Rabatt in Version 1 — Templates dürfen keinen erfinden
    assert facts["affiliate"]["customer_discount"] is None
    # Auszahlung ist noch nicht freigeschaltet → Statusnote muss existieren
    assert facts["affiliate"]["payouts_enabled"] is False
    assert facts["affiliate"]["status_note"]["de"]


def test_lokalisierung_klappt_de_en_knoten_um():
    ctx = build_context(lang="en")
    assert ctx["t"]["ad_label"] == "Ad"
    assert ctx["t"]["free_tier"]["text"].startswith("Free forever")
    ctx = build_context(lang="de")
    assert ctx["t"]["ad_label"] == "Werbung"


def test_provisionsstaffel_entspricht_handover():
    tiers = load_facts()["affiliate"]["commission_tiers"]
    assert [(t["sales_from"], t["sales_to"], t["eur"]) for t in tiers] == [
        (1, 10, "2,00"), (11, 50, "2,50"), (51, 100, "3,00"),
        (101, 500, "3,50"), (501, None, "4,00"),
    ]


# ---------------------------------------------------------------------------
# Creator-Konfiguration
# ---------------------------------------------------------------------------
def _write_cfg(tmp_path: Path, **overrides) -> Path:
    cfg = {
        "creator_name": "TechMax",
        "affiliate_code": "TECHMAX",
        "affiliate_link": "https://downloadthat.pages.dev/?ref=TECHMAX",
    }
    cfg.update(overrides)
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def test_creator_config_defaults(tmp_path):
    cfg = load_creator(_write_cfg(tmp_path))
    assert cfg["creator_handle"] == "@techmax"
    assert cfg["language"] == "de"
    assert cfg["initial"] == "T"
    assert cfg["discount_text"] == ""


def test_creator_config_fehlende_pflichtfelder(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"creator_name": "X"}', encoding="utf-8")
    with pytest.raises(ConfigError, match="affiliate_code"):
        load_creator(p)


def test_creator_config_verweigert_erfundenen_rabatt(tmp_path):
    with pytest.raises(ConfigError, match="[Rr]abatt"):
        load_creator(_write_cfg(tmp_path, discount_text="20 % Rabatt!"))
    # mit schriftlicher Bestätigung des Betreibers erlaubt
    cfg = load_creator(_write_cfg(tmp_path, discount_text="Aktionswoche", discount_confirmed=True))
    assert cfg["discount_text"] == "Aktionswoche"


def test_creator_config_verweigert_kaputten_link(tmp_path):
    with pytest.raises(ConfigError, match="http"):
        load_creator(_write_cfg(tmp_path, affiliate_link="downloadthat.pages.dev"))


# ---------------------------------------------------------------------------
# QR-Codes
# ---------------------------------------------------------------------------
def test_qr_svg_hat_viewbox_und_ruhezone():
    svg = qr_svg("https://downloadthat.pages.dev/partner.html")
    assert svg.startswith("<svg"), "muss ein einbettbares Snippet sein"
    assert 'viewBox="0 0 ' in svg, "ohne viewBox skaliert der QR nicht"
    assert 'width="' not in svg.split(">", 1)[0]


def test_qr_verweigert_erfundene_ziele():
    with pytest.raises(QRError):
        qr_svg("beispiel-ohne-schema.de")
    with pytest.raises(QRError):
        qr_svg("")


# ---------------------------------------------------------------------------
# Render-Smoke-Test (nur wenn Chromium vorhanden)
# ---------------------------------------------------------------------------
def _chrome_available() -> bool:
    from kit.renderer import RendererError, find_chrome

    try:
        find_chrome()
        return True
    except RendererError:
        return False


@pytest.mark.skipif(not _chrome_available(), reason="kein Chromium für Render-Smoke-Test")
def test_render_smoke_story(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    from kit.renderer import html_to_png
    from kit.templating import render_template

    ctx = build_context(
        lang="de",
        creator={"creator_name": "Test", "creator_handle": "@test", "affiliate_code": "TEST",
                 "affiliate_link": "https://downloadthat.pages.dev/?ref=TEST", "cta": "", "initial": "T"},
        theme="theme-ce", W=540, H=960, qr_svg=qr_svg("https://downloadthat.pages.dev"),
        logo_size=36, logo_gap=10, logo_font=24,
    )
    html = render_template("story/story-01-know-this-app.html", ctx)
    out = tmp_path / "s.png"
    html_to_png(html, out, 540, 960)
    with Image.open(out) as im:
        assert im.size == (540, 960), "Renderer muss pixelgenau zuschneiden"
