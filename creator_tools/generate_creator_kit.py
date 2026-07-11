#!/usr/bin/env python3
"""Erzeugt ein personalisiertes Creator-Kit aus einer JSON-Konfiguration.

Aufruf (aus dem Repo-Root):

    uv run python creator_tools/generate_creator_kit.py creator_tools/config/example_creator.json
    uv run python creator_tools/generate_creator_kit.py cfg.json --with-videos
    uv run python creator_tools/generate_creator_kit.py cfg.json --lang en --out mein/ordner

Beispiel-Konfiguration (alle weiteren Felder optional):

    {
      "creator_name": "TechMax",
      "creator_handle": "@techmax",
      "affiliate_code": "TECHMAX",
      "affiliate_link": "https://downloadthat.pages.dev/?ref=TECHMAX",
      "profile_image": "inputs/techmax.png",
      "language": "de",
      "style": "creator-energy",
      "cta": "Über meinen Link kostenlos ausprobieren"
    }

Regeln:
* ``affiliate_link`` muss eine echte http(s)-URL sein — QR-Codes mit erfundenen
  Zielen werden verweigert.
* ``discount_text`` bleibt leer, solange es keinen Rabatt gibt; ein gesetzter
  Wert ohne ``discount_confirmed: true`` bricht mit Fehler ab.
* Der Renderprozess läuft komplett offline (lokales Chromium + ffmpeg).
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kit.context import ConfigError, build_context, load_creator, load_facts  # noqa: E402
from kit.qrcodes import qr_svg  # noqa: E402
from kit.renderer import RendererError, html_to_pdf, html_to_png  # noqa: E402
from kit.templating import render_template  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO / "creator_tools" / "output"

THEMES = {
    "premium-tech": "theme-pt",
    "creator-energy": "theme-ce",
    "clean-utility": "theme-cu",
}


def _embed_profile_image(cfg: dict, cfg_path: Path) -> None:
    """Bindet das Profilbild als data-URI ein (Templates laufen über file://)."""
    img = cfg.get("profile_image")
    if not img:
        return
    p = Path(img)
    if not p.is_absolute():
        p = (cfg_path.parent / p).resolve()
    if not p.exists():
        raise ConfigError(f"profile_image nicht gefunden: {p}")
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    cfg["profile_image_data"] = f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def _ctx(cfg: dict, lang: str, **extra) -> dict:
    theme = THEMES.get(cfg.get("style", "creator-energy"))
    if theme is None:
        raise ConfigError(f"Unbekannter style: {cfg.get('style')!r} — erlaubt: {sorted(THEMES)}")
    return build_context(
        lang=lang, creator=cfg,
        theme=theme, theme_key=cfg.get("style"),
        qr_svg=qr_svg(cfg["affiliate_link"]),
        print=False, portrait=False,
        logo_size=extra.pop("logo_size", 64), logo_gap=18, logo_font=extra.pop("logo_font", 42),
        **extra,
    )


def _captions(cfg: dict, facts: dict, lang: str) -> str:
    """Fertige Caption-Bausteine mit eingesetzten Platzhaltern (Kurzfassung der
    Copy-Library — die volle Bibliothek liegt in docs/INFLUENCER_COPY_LIBRARY.md)."""
    de = lang == "de"
    code, link = cfg["affiliate_code"], cfg["affiliate_link"]
    disclosure = facts["affiliate_disclosure"]["de" if de else "en"]
    rights = facts["rights_note"]["de" if de else "en"]
    ad = facts["ad_label"]["de" if de else "en"]
    if de:
        return f"""[{ad}] Instagram/TikTok-Caption — Produktvorstellung
Diese App hat meinen Download-Workflow auf Android ersetzt: Teilen antippen, DownloadThat wählen, fertig. Video, Audio (MP3) und Bilder — alles bleibt lokal auf dem Gerät. Free-Version: 3 Downloads am Tag, für immer. Link: {link}
{disclosure}

[{ad}] Caption — Creator-Code
Mit meinem Code {code} unterstützt du diesen Kanal, wenn du dir DownloadThat Pro holst (12 € einmalig, kein Abo). Für dich bleibt der Preis gleich. Link: {link}
{disclosure}

[{ad}] Story-Text kurz
Teilen → DownloadThat → gespeichert. Mehr ist es nicht. Link in Bio. ({ad})

Hinweis für alle Posts: {rights}
"""
    return f"""[{ad}] Instagram/TikTok caption — product intro
This app replaced my download workflow on Android: tap share, pick DownloadThat, done. Video, audio (MP3) and images — everything stays local on the device. Free tier: 3 downloads a day, forever. Link: {link}
{disclosure}

[{ad}] Caption — creator code
Use my code {code} to support this channel when you grab DownloadThat Pro (€12 one-time, no subscription). The price stays the same for you. Link: {link}
{disclosure}

[{ad}] Short story text
Share → DownloadThat → saved. That's all. Link in bio. ({ad})

Note for every post: {rights}
"""


def generate(cfg_path: Path, out_root: Path | None = None, lang: str | None = None,
             with_videos: bool = False, music: Path | None = None) -> Path:
    cfg = load_creator(cfg_path)
    _embed_profile_image(cfg, cfg_path)
    facts = load_facts()
    lang = lang or cfg.get("language", "de")
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in cfg["creator_name"].lower()).strip("-") or "creator"
    out = (out_root or DEFAULT_OUT) / slug
    out.mkdir(parents=True, exist_ok=True)
    print(f"Erzeuge personalisiertes Kit für {cfg['creator_name']} ({lang}) → {out}")

    def png(template: str, name: str, w: int, h: int, **extra) -> None:
        html = render_template(template, dict(_ctx(cfg, lang, **extra), W=w, H=h))
        html_to_png(html, out / name, w, h)
        print(f"  ✓ {name}")

    # Bilder
    png("story/story-01-know-this-app.html", "story-01-app.png", 1080, 1920, logo_size=72, logo_font=46)
    png("story/story-code.html", "story-02-code.png", 1080, 1920, logo_size=72, logo_font=46,
        story_title='Mein <span class="grad-text">Creator-Code</span>.' if lang == "de" else 'My <span class="grad-text">creator code</span>.')
    png("story/story-steps.html", "story-03-steps.png", 1080, 1920, logo_size=72, logo_font=46,
        story_title='Teilen. <span class="grad-text">DownloadThat</span>. Fertig.' if lang == "de" else 'Share. <span class="grad-text">DownloadThat</span>. Done.')
    png("feed/feed-01-product-intro.html", "feed-square.png", 1080, 1080, logo_size=56, logo_font=38)
    png("feed/feed-01-product-intro.html", "feed-portrait.png", 1080, 1350, logo_size=60, logo_font=40)
    png("feed/feed-recommend.html", "feed-recommend.png", 1080, 1350, logo_size=60, logo_font=40,
        quote_text=("Endlich eine Download-App, die sich nicht wie eine Falle anfühlt: keine Werbung, kein Konto, alles bleibt auf meinem Gerät."
                    if lang == "de" else
                    "Finally a downloader that doesn't feel like a trap: no ads, no account, everything stays on my device."))
    png("thumb/thumb-youtube.html", "youtube-thumbnail.png", 1280, 720, logo_size=52, logo_font=36,
        thumb_title=('Diese Android-App<br><em class="grad-text">spart Zeit</em>' if lang == "de" else 'This Android app<br><em class="grad-text">saves time</em>'),
        thumb_sub=("Video · Audio · Bilder — lokal gespeichert" if lang == "de" else "Video · audio · images — saved locally"),
        thumb_badge=("Im Test" if lang == "de" else "Tested"), thumb_shot="screenshot_main.png")
    png("cards/card-affiliate.html", "affiliate-card.png", 1080, 1080, logo_size=60, logo_font=40)
    png("cards/qr-card.html", "qr-card.png", 1080, 1350, logo_size=64, logo_font=42,
        qr_pad_v=110, qr_title_size=64, qr_size=470,
        qr_title=('Scannen &amp; <span class="grad-text">DownloadThat testen</span>.' if lang == "de" else 'Scan &amp; <span class="grad-text">try DownloadThat</span>.'))
    png("cards/endcard-youtube.html", "youtube-endcard.png", 1920, 1080, logo_size=56, logo_font=38)

    # Flyer (A4, personalisiert über QR/Code nicht nötig — Partner-Werbung an Dritte)
    flyer_ctx = dict(_ctx(cfg, lang, logo_size=58, logo_font=38), W=1240, H=1754)
    html_to_png(render_template("flyer/flyer-a4-recruitment.html", flyer_ctx), out / "flyer-a4.png", 1240, 1754)
    html_to_pdf(render_template("flyer/flyer-a4-recruitment.html", dict(flyer_ctx, print=True)), out / "flyer-a4.pdf")
    print("  ✓ flyer-a4.png / flyer-a4.pdf")

    # Captions (beide Sprachen — Copy ist billig, Kontextwechsel teuer)
    (out / "captions-de.txt").write_text(_captions(cfg, facts, "de"), encoding="utf-8")
    (out / "captions-en.txt").write_text(_captions(cfg, facts, "en"), encoding="utf-8")
    print("  ✓ captions-de.txt / captions-en.txt")

    if with_videos:
        from kit.video import cmd_videos

        cmd_videos(creator=cfg, out_dir=out, lang=lang,
                   names=["video-01-intro-10s", "video-03-creator-ad-20s",
                          "video-05a-story-attention-6s", "video-05b-story-demo-6s",
                          "video-05c-story-code-6s"],
                   music=music)

    print(f"Fertig: {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config", help="Pfad zur Creator-JSON-Konfiguration")
    parser.add_argument("--out", type=Path, default=None, help="Ausgabe-Wurzelverzeichnis (Standard: creator_tools/output/)")
    parser.add_argument("--lang", choices=["de", "en"], default=None, help="Sprache überschreiben")
    parser.add_argument("--with-videos", action="store_true", help="Auch personalisierte MP4s rendern (braucht ffmpeg)")
    parser.add_argument("--music", type=Path, default=None, help="Eigene Musikspur (ersetzt den generierten Pad)")
    args = parser.parse_args()
    try:
        generate(Path(args.config), args.out, args.lang, args.with_videos, args.music)
    except (ConfigError, RendererError) as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
