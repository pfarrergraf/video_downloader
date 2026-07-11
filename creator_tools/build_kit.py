#!/usr/bin/env python3
"""Rendert das unpersonalisierte DownloadThat-Creator-Kit.

Aufrufe (aus dem Repo-Root):

    uv run python creator_tools/build_kit.py directions   # 3 Designrichtungen × 6 Artefakte
    uv run python creator_tools/build_kit.py kit          # komplettes Promotion-/Recruitment-Kit
    uv run python creator_tools/build_kit.py videos       # 7 Motion-Vorlagen (MP4)
    uv run python creator_tools/build_kit.py all

Ausgaben landen unter ``pro/website/assets/influencer/`` (werden committed und vom
Creator-Portal ``pro/website/creator-kit.html`` verlinkt). Personalisierte Kits pro
Creator erzeugt ``generate_creator_kit.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kit import specs  # noqa: E402
from kit.context import build_context, load_facts  # noqa: E402
from kit.qrcodes import qr_svg  # noqa: E402
from kit.renderer import html_to_pdf, html_to_png, png_to_webp  # noqa: E402
from kit.templating import render_template  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT_BASE = REPO / "pro" / "website" / "assets" / "influencer"

THEMES = {
    "premium-tech": "theme-pt",
    "creator-energy": "theme-ce",
    "clean-utility": "theme-cu",
}

# Unpersonalisierte Vorlagen zeigen neutrale Beispielwerte, die sichtbar
# Platzhalter sind (kein erfundener Creator).
SAMPLE_CREATOR = {
    "creator_name": "Dein Name",
    "creator_handle": "@dein.kanal",
    "affiliate_code": "DEINCODE",
    "affiliate_link": "https://downloadthat.pages.dev/?ref=DEINCODE",
    "cta": "",
    "discount_text": "",
    "initial": "D",
}

SAMPLE_CREATOR_EN = dict(SAMPLE_CREATOR, creator_name="Your Name", creator_handle="@your.channel",
                         affiliate_code="YOURCODE",
                         affiliate_link="https://downloadthat.pages.dev/?ref=YOURCODE", initial="Y")


def ctx_for(theme_key: str, lang: str = "de", creator: dict | None = None, **extra) -> dict:
    facts = load_facts()
    if creator is None:
        creator = dict(SAMPLE_CREATOR if lang == "de" else SAMPLE_CREATOR_EN)
    # Promotion-Assets: QR → persönlicher Affiliate-Link.
    # Recruitment-Assets: QR → Partnerseite (per qr_url überschrieben).
    qr = qr_svg(extra.pop("qr_url", None) or creator.get("affiliate_link") or facts["partner_url"])
    return build_context(
        lang=lang,
        creator=creator,
        theme=THEMES[theme_key],
        theme_key=theme_key,
        qr_svg=qr,
        print=False,
        portrait=extra.pop("portrait", False),
        logo_size=extra.pop("logo_size", 64),
        logo_gap=extra.pop("logo_gap", 18),
        logo_font=extra.pop("logo_font", 42),
        **extra,
    )


def render_png(template: str, ctx: dict, out: Path, w: int, h: int, webp: bool = False) -> Path:
    ctx = dict(ctx, W=w, H=h)
    html = render_template(template, ctx)
    html_to_png(html, out, w, h)
    if webp:
        png_to_webp(out)
    print(f"  ✓ {out.relative_to(REPO)}")
    return out


THUMB_TEXTS_DE = {
    "thumb_title": 'Diese Android-App<br><em class="grad-text">spart Zeit</em>',
    "thumb_sub": "Video · Audio · Bilder — lokal gespeichert",
    "thumb_badge": "Im Test",
    "thumb_shot": "screenshot_main.png",
}

COVER_TEXTS = {
    "de": {
        "cover_title": 'Ich teste<br><span class="grad-text">DownloadThat</span>',
        "cover_sub": "Teilen → Speichern. Mehr nicht.",
        "cover_badge": "Kurz erklärt",
    },
    "en": {
        "cover_title": 'Testing<br><span class="grad-text">DownloadThat</span>',
        "cover_sub": "Share → save. That's it.",
        "cover_badge": "Quick look",
    },
}


def cmd_directions() -> None:
    """3 Richtungen × {Story, Feed, Thumbnail, Flyer, Video-Cover, Affiliate-Karte}."""
    out_dir = OUT_BASE / "previews" / "directions"
    for theme_key in THEMES:
        print(f"[{theme_key}]")
        d = out_dir / theme_key
        render_png("story/story-01-know-this-app.html", ctx_for(theme_key, logo_size=72, logo_font=46), d / "story.png", 1080, 1920, webp=True)
        render_png("feed/feed-01-product-intro.html", ctx_for(theme_key, logo_size=60, logo_font=40), d / "feed.png", 1080, 1350, webp=True)
        render_png("thumb/thumb-youtube.html", ctx_for(theme_key, logo_size=56, logo_font=38, **THUMB_TEXTS_DE), d / "thumbnail.png", 1280, 720, webp=True)
        render_png("flyer/flyer-a4-recruitment.html", ctx_for(theme_key, logo_size=58, logo_font=38, qr_url=load_facts()["partner_url"]), d / "flyer.png", 1240, 1754, webp=True)
        render_png("story/cover-video.html", ctx_for(theme_key, logo_size=72, logo_font=46, **COVER_TEXTS["de"]), d / "video-cover.png", 1080, 1920, webp=True)
        render_png("cards/card-affiliate.html", ctx_for(theme_key, logo_size=60, logo_font=40), d / "affiliate-card.png", 1080, 1080, webp=True)


def _langs_of(extra: dict) -> list[str]:
    return [lang for lang in ("de", "en") if lang in extra]


def cmd_kit() -> None:  # noqa: C901 — bewusst ein linearer Build-Ablauf
    promo = OUT_BASE / "promotion"
    recruit = OUT_BASE / "recruitment"

    print("[Stories 1080×1920]")
    for spec in specs.STORIES:
        for lang in _langs_of(spec["extra"]):
            ctx = ctx_for(spec["theme"], lang, logo_size=72, logo_font=46, **spec["extra"][lang])
            render_png(spec["template"], ctx, promo / "stories" / f"{spec['slug']}-{lang}.png", 1080, 1920)

    print("[Feed-Posts]")
    for spec in specs.FEEDS:
        for lang in _langs_of(spec["extra"]):
            ctx = ctx_for(spec["theme"], lang, logo_size=60, logo_font=40, **spec["extra"][lang])
            render_png(spec["template"], ctx, promo / "feed" / f"{spec['slug']}-{lang}-1080x1350.png", 1080, 1350)
        for (w, h) in spec.get("also_sizes", []):
            ctx = ctx_for(spec["theme"], "de", logo_size=56, logo_font=38, **spec["extra"]["de"])
            render_png(spec["template"], ctx, promo / "feed" / f"{spec['slug']}-de-{w}x{h}.png", w, h)

    print("[YouTube]")
    for slug, theme, by_lang in specs.THUMBS:
        for lang, extra in by_lang.items():
            ctx = ctx_for(theme, lang, logo_size=52, logo_font=36, **extra)
            render_png("thumb/thumb-youtube.html", ctx, promo / "youtube" / f"{slug}-{lang}.png", 1280, 720)
    for lang in ("de", "en"):
        render_png("story/cover-video.html", ctx_for("creator-energy", lang, logo_size=72, logo_font=46, **COVER_TEXTS[lang]),
                   promo / "youtube" / f"shorts-cover-{lang}.png", 1080, 1920)
        render_png("cards/endcard-youtube.html", ctx_for("creator-energy", lang, logo_size=56, logo_font=38),
                   promo / "youtube" / f"endcard-{lang}.png", 1920, 1080)
        render_png("cards/card-affiliate.html", ctx_for("creator-energy", lang, logo_size=50, logo_font=34),
                   promo / "youtube" / f"affiliate-link-card-{lang}.png", 1280, 720)

    print("[Affiliate-/QR-Karten]")
    for theme_key in THEMES:
        render_png("cards/card-affiliate.html", ctx_for(theme_key, "de", logo_size=60, logo_font=40),
                   promo / "cards" / f"affiliate-card-{theme_key}-de.png", 1080, 1080)
    qr_formats = [
        ("qr-story", "creator-energy", 1080, 1920, dict(qr_pad_v=250, qr_title_size=76, qr_size=560)),
        ("qr-square", "premium-tech", 1080, 1080, dict(qr_pad_v=80, qr_title_size=58, qr_size=440)),
        ("qr-print", "clean-utility", 1240, 1754, dict(qr_pad_v=120, qr_title_size=68, qr_size=520)),
    ]
    qr_titles = {
        "de": f'Scannen &amp; <span class="grad-text">DownloadThat testen</span>.',
        "en": f'Scan &amp; <span class="grad-text">try DownloadThat</span>.',
    }
    for slug, theme_key, w, h, params in qr_formats:
        for lang in ("de", "en") if slug == "qr-square" else ("de",):
            ctx = ctx_for(theme_key, lang, logo_size=64, logo_font=42, qr_title=qr_titles[lang], **params)
            render_png("cards/qr-card.html", ctx, promo / "cards" / f"{slug}-{lang}.png", w, h)

    print("[Carousels]")
    for set_slug, cfg in specs.CAROUSELS.items():
        total = len(cfg["slides"])
        for idx, slide in enumerate(cfg["slides"], start=1):
            for lang in _langs_of(slide):
                ctx = ctx_for(cfg["theme"], lang, logo_size=56, logo_font=38,
                              page_no=idx, page_total=total, **slide[lang])
                render_png("carousel/carousel-slide.html", ctx,
                           promo / "carousel" / set_slug / f"slide-{idx}-{lang}.png", 1080, 1350)

    print("[Blog/Newsletter]")
    for spec in specs.BLOG:
        for lang in _langs_of(spec["extra"]):
            ctx = ctx_for(spec["theme"], lang, logo_size=48, logo_font=32, **spec["extra"][lang])
            render_png(spec["template"], ctx, promo / "blog" / f"{spec['slug']}-{lang}.png", spec["w"], spec["h"])

    print("[Recruitment: Flyer]")
    for lang in ("de", "en"):
        ctx = ctx_for("premium-tech", lang, logo_size=58, logo_font=38, qr_url=load_facts()["partner_url"])
        render_png("flyer/flyer-a4-recruitment.html", ctx, recruit / f"flyer-a4-{lang}.png", 1240, 1754)
        pdf_ctx = dict(ctx, W=1240, H=1754, print=True)
        html = render_template("flyer/flyer-a4-recruitment.html", pdf_ctx)
        out_pdf = recruit / f"flyer-a4-{lang}.pdf"
        html_to_pdf(html, out_pdf)
        print(f"  ✓ {out_pdf.relative_to(REPO)}")
        for (w, h) in ((1080, 1350), (1080, 1920)):
            pad = 90 if h == 1350 else 240
            tsize = 74 if h == 1350 else 82
            ctx2 = ctx_for("premium-tech", lang, logo_size=62, logo_font=42,
                           fs_pad_v=pad, fs_title_size=tsize, qr_url=load_facts()["partner_url"])
            render_png("flyer/flyer-social-recruitment.html", ctx2, recruit / f"flyer-social-{w}x{h}-{lang}.png", w, h)

    print("[Recruitment: One-Pager]")
    for lang in ("de", "en"):
        ctx = ctx_for("premium-tech", lang, asset_prefix="..")
        html = render_template("onepager/onepager.html", ctx)
        suffix = "" if lang == "de" else "-en"
        out_html = recruit / f"downloadthat-creator-onepager{suffix}.html"
        out_html.parent.mkdir(parents=True, exist_ok=True)
        out_html.write_text(html, encoding="utf-8")
        print(f"  ✓ {out_html.relative_to(REPO)}")
        preview_ctx = ctx_for("premium-tech", lang, asset_prefix=str(OUT_BASE))
        preview_html = render_template("onepager/onepager.html", preview_ctx)
        html_to_png(preview_html, OUT_BASE / "previews" / f"onepager-{lang}.png", 1240, 3400)
        print(f"  ✓ {(OUT_BASE / 'previews' / f'onepager-{lang}.png').relative_to(REPO)}")

    print("[Recruitment: Deck]")
    facts = load_facts()
    qr = qr_svg(facts["partner_url"])
    total = len(specs.DECK)
    for idx, slide in enumerate(specs.DECK, start=1):
        for lang in _langs_of(slide):
            extra = dict(slide[lang])
            extra["slide_side"] = extra["slide_side"].replace("__QR__", qr)
            ctx = ctx_for("premium-tech", lang, logo_size=56, logo_font=38,
                          page_no=idx, page_total=total, **extra)
            render_png("deck/deck-slide.html", ctx, recruit / "deck" / f"slide-{idx}-{lang}.png", 1920, 1080)
            ctx_p = ctx_for("premium-tech", lang, logo_size=56, logo_font=38,
                            page_no=idx, page_total=total, portrait=True, **extra)
            render_png("deck/deck-slide.html", ctx_p, recruit / "deck" / f"slide-{idx}-{lang}-social-1080x1350.png", 1080, 1350)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["directions", "kit", "videos", "all"])
    args = parser.parse_args()
    if args.mode in ("directions", "all"):
        cmd_directions()
    if args.mode in ("kit", "all"):
        cmd_kit()
    if args.mode in ("videos", "all"):
        from kit.video import cmd_videos

        cmd_videos()


if __name__ == "__main__":
    main()
