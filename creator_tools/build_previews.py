#!/usr/bin/env python3
"""Erzeugt die beiden visuellen Übersichtsseiten:

* ``docs/influencer-design-directions.html`` — 3 Richtungen im Vergleich + Entscheidung
* ``docs/influencer-kit-preview.html``       — alle gerenderten Assets auf einer Seite

Beide Seiten referenzieren die committeten Renders unter
``pro/website/assets/influencer/`` relativ — sie funktionieren lokal (file://)
und auf GitHub-Checkouts ohne Server.

    uv run python creator_tools/build_previews.py
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "pro" / "website" / "assets" / "influencer"
REL = "../pro/website/assets/influencer"  # aus docs/ heraus

CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#12101f; color:#eee; font-family:system-ui,sans-serif; line-height:1.5; padding:40px 4vw 80px; }
h1 { font-size:34px; margin-bottom:6px; }
h2 { font-size:24px; margin:44px 0 14px; border-bottom:1px solid #333; padding-bottom:8px; }
h3 { font-size:17px; margin:22px 0 10px; color:#bbb; }
p.lead { color:#aaa; max-width:900px; }
.grid { display:flex; flex-wrap:wrap; gap:14px; align-items:flex-start; }
figure { background:#1c1a2e; border:1px solid #333; border-radius:10px; padding:10px; }
figure img { display:block; border-radius:6px; }
figure video { display:block; border-radius:6px; background:#000; }
figcaption { font-size:12px; color:#999; margin-top:8px; max-width:100%; word-break:break-all; }
.pick { background:#1f2b1f; border:1px solid #3c6; border-radius:12px; padding:18px 22px; margin:22px 0; max-width:900px; }
.pick b { color:#7ce27c; }
a { color:#4adfb6; }
.note { font-size:13px; color:#888; margin-top:6px; }
"""


def fig(src: str, w: int, caption: str = "", video: bool = False) -> str:
    cap = f"<figcaption>{caption or Path(src).name}</figcaption>"
    if video:
        return f'<figure><video src="{src}" width="{w}" controls muted loop></video>{cap}</figure>'
    return f'<figure><img src="{src}" width="{w}" loading="lazy" alt="">{cap}</figure>'


def collect(subdir: str, width: int, video: bool = False, suffix: str = ".png") -> str:
    d = ASSETS / subdir
    if not d.exists():
        return "<p class='note'>— (noch nicht gebaut)</p>"
    items = sorted(p for p in d.rglob(f"*{suffix}") if p.is_file())
    return "<div class='grid'>" + "".join(
        fig(f"{REL}/{subdir}/{p.relative_to(d)}", width, p.name, video=video) for p in items
    ) + "</div>"


def build_directions() -> None:
    themes = [
        ("premium-tech", "Premium Tech", "Gold auf Schwarz — die Identität der Website (`#c9a869` auf `#0e0c14`). Seriös, druckfähig, B2B."),
        ("creator-energy", "Creator Energy", "Koralle→Mint-Gradient auf Navy — die Identität der echten App-UI. Energisch, mobil, Social-first."),
        ("clean-utility", "Clean Utility", "Helles, ruhiges Layout mit denselben Akzentfarben. Für Tutorials, Blogs und erklärende Kanäle."),
    ]
    artifacts = ["story", "feed", "thumbnail", "flyer", "video-cover", "affiliate-card"]
    rows = []
    for key, name, desc in themes:
        cells = "".join(
            fig(f"{REL}/previews/directions/{key}/{a}.webp", 220, a) for a in artifacts
        )
        rows.append(f"<h2>{name}</h2><p class='lead'>{desc}</p><div class='grid'>{cells}</div>")
    html = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<title>DownloadThat — Design-Richtungen (Influencer-Kit)</title><style>{CSS}</style></head><body>
<h1>Drei Designrichtungen im Vergleich</h1>
<p class="lead">Jede Richtung zeigt dieselben sechs Artefakte: Story, Feed-Post, YouTube-Thumbnail,
A4-Flyer, Video-Cover und Affiliate-Karte. Alle Renders nutzen echte App-Screenshots und die
verifizierte Faktenbasis aus <code>docs/INFLUENCER_CREATIVE_AUDIT.md</code>.</p>
<div class="pick"><b>Entscheidung:</b> Hauptrichtung für das Recruitment-Kit ist <b>Premium Tech</b>
(deckungsgleich mit der Kauf-Website — Creator landen nach dem Flyer genau in dieser Welt).
Ergänzende Social-Media-Richtung ist <b>Creator Energy</b> (deckungsgleich mit der App-UI, die in
jedem echten Screenshot und Video der Influencer zu sehen ist). <b>Clean Utility</b> bleibt als
dritte Variante für Tutorial-/Blog-Formate im Kit verfügbar.</div>
{''.join(rows)}
</body></html>"""
    out = REPO / "docs" / "influencer-design-directions.html"
    out.write_text(html, encoding="utf-8")
    print(f"✓ {out.relative_to(REPO)}")


def build_preview(rel: str = REL, out_path: Path | None = None, deployed: bool = False) -> None:
    global REL
    old_rel, REL = REL, rel
    doc_note = (
        "Skripte, Captions und Offenlegungstexte liegen dem personalisierten Kit bei."
        if deployed else
        f"Download-Portal für Partner: <a href='../pro/website/creator-kit.html'>pro/website/creator-kit.html</a> · "
        f"Faktenbasis: <a href='INFLUENCER_CREATIVE_AUDIT.md'>INFLUENCER_CREATIVE_AUDIT.md</a>"
    )
    html = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<title>DownloadThat — Influencer-Kit: visuelle Gesamtübersicht</title><style>{CSS}</style></head><body>
<h1>Influencer-Kit — alle gerenderten Vorlagen</h1>
<p class="lead">Unpersonalisierte Master-Renders (Beispielwerte: „Dein Name“, Code „DEINCODE“).
Personalisierte Fassungen erzeugt <code>creator_tools/generate_creator_kit.py</code>.
{doc_note}</p>

<h2 id="recruitment">Kit A — Recruitment</h2>
<h3>A4-Flyer (DE/EN, PDF + PNG) und Social-Flyer</h3>
{collect_flat("recruitment", 280)}
<h3>Präsentations-Deck (8 Seiten, je Querformat + Social-Portrait, DE/EN)</h3>
{collect("recruitment/deck", 300)}
<h3>One-Pager (HTML, DE/EN)</h3>
<div class="grid">{fig(f"{REL}/previews/onepager-de.png", 340, "downloadthat-creator-onepager.html (Vorschau)")}
{fig(f"{REL}/previews/onepager-en.png", 340, "downloadthat-creator-onepager-en.html (Vorschau)")}</div>

<h2 id="promotion">Kit B — Promotion</h2>
<h3 id="stories">Stories (10 Vorlagen, DE + EN)</h3>
{collect("promotion/stories", 200)}
<h3 id="feed">Feed-Posts (10 Vorlagen, DE + EN, mehrere Formate)</h3>
{collect("promotion/feed", 240)}
<h3 id="youtube">YouTube (Thumbnails, Shorts-Cover, Endcards, Link-Karten)</h3>
{collect("promotion/youtube", 300)}
<h3 id="cards">Affiliate- & QR-Karten</h3>
{collect("promotion/cards", 260)}
<h3 id="carousel">Carousel-Sets (3 × 5 Slides, DE + EN)</h3>
{collect("promotion/carousel", 200)}
<h3 id="blog">Blog & Newsletter</h3>
{collect("promotion/blog", 300)}
<h3 id="video">Videos (7 Vorlagen / 9 MP4s, H.264 + AAC, mit SRT)</h3>
{collect("promotion/video", 220, video=True, suffix=".mp4")}
"""
    if not deployed:
        html += """
<h2>Designrichtungen</h2>
<p class="lead">Vergleich aller drei Richtungen: <a href="influencer-design-directions.html">influencer-design-directions.html</a></p>"""
    html += "</body></html>"
    out = out_path or (REPO / "docs" / "influencer-kit-preview.html")
    out.write_text(html, encoding="utf-8")
    REL = old_rel
    print(f"✓ {out.relative_to(REPO)}")


def collect_flat(subdir: str, width: int) -> str:
    d = ASSETS / subdir
    items = sorted(p for p in d.glob("*.png") if p.is_file())
    return "<div class='grid'>" + "".join(
        fig(f"{REL}/{subdir}/{p.name}", width, p.name) for p in items
    ) + "</div>"


if __name__ == "__main__":
    build_directions()
    build_preview()
    # Deploybare Galerie neben den Assets (Cloudflare Pages hat kein Directory-Listing)
    build_preview(rel=".", out_path=ASSETS / "index.html", deployed=True)
