"""Motion-Vorlagen: rendert echte MP4s (H.264/AAC) aus HTML-Szenen.

Ablauf pro Video:
1. Szenen als PNG rendern (1296×2304 = 1,2× Zielgröße, Ken-Burns-Headroom).
2. ffmpeg ``zoompan`` animiert jede Szene (abwechselnd rein-/rauszoomen),
   ``xfade`` blendet die Szenen ineinander.
3. Musik wird als neutraler Synth-Pad **selbst erzeugt** (aevalsrc) — keine
   Lizenzfragen; die Spur ist bewusst leise und über ``--music`` austauschbar.
4. Untertitel sind in die Szenen eingebrannt (Safe Areas, Markenschrift);
   zusätzlich wird eine ``.srt`` mit denselben Texten und Zeiten geschrieben.

Voraussetzung: ein vollständiges ffmpeg (libx264 + aac) im PATH.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .context import build_context
from .qrcodes import qr_svg
from .renderer import html_to_png
from .templating import render_template

REPO = Path(__file__).resolve().parent.parent.parent
OUT_BASE = REPO / "pro" / "website" / "assets" / "influencer" / "promotion" / "video"

W, H = 1080, 1920
SCALE = 1.2  # Rendergröße für Zoom-Headroom
FPS = 30
XFADE = 0.5


class VideoError(RuntimeError):
    pass


def find_ffmpeg() -> str:
    ff = shutil.which("ffmpeg")
    if not ff:
        raise VideoError(
            "ffmpeg nicht gefunden. Für die Video-Vorlagen wird ein vollständiges "
            "ffmpeg (libx264 + aac) benötigt, z. B. `apt install ffmpeg`."
        )
    out = subprocess.run([ff, "-encoders"], capture_output=True, text=True).stdout
    if "libx264" not in out:
        raise VideoError(f"{ff} hat keinen libx264-Encoder — bitte volles ffmpeg installieren.")
    return ff


# ---------------------------------------------------------------------------
# Szenen-Bausteine (scene_body-HTML für templates/scenes/scene.html)
# ---------------------------------------------------------------------------
def hero(title: str, sub: str = "") -> str:
    s = f"<h1>{title}</h1>"
    if sub:
        s += f'<div class="sub">{sub}</div>'
    return s


def phone(shot: str, title: str = "") -> str:
    s = f'<h1 style="font-size:72px;">{title}</h1>' if title else ""
    return s + f'<div class="phone"><img src="__STORE_ASSETS__/{shot}" alt=""></div>'


def steps(items: list[str]) -> str:
    rows = "".join(
        f'<div class="row card"><div class="num">{i}</div><div class="txt">{t}</div></div>'
        for i, t in enumerate(items, start=1)
    )
    return f'<div class="steplist">{rows}</div>'


def code_box(code: str) -> str:
    return f'<div class="codebox"><div class="code grad-text">{code}</div></div>'


def qr_block(qr: str, link: str) -> str:
    return (
        f'<div class="qr-frame">{qr}</div>'
        f'<div class="sub" style="word-break:break-all;">{link}</div>'
    )


def avatar_block(creator: dict) -> str:
    inner = (
        f'<img src="{creator["profile_image_data"]}" alt="">'
        if creator.get("profile_image_data")
        else creator.get("initial", "?")
    )
    return (
        f'<div class="avatar">{inner}</div>'
        f'<h1 style="font-size:84px;">{creator["creator_name"]}</h1>'
        f'<div class="sub">{creator["creator_handle"]}</div>'
    )


# ---------------------------------------------------------------------------
# Video-Definitionen
# ---------------------------------------------------------------------------
def video_specs(creator: dict, lang: str = "de") -> dict[str, dict]:
    de = lang == "de"
    qr = qr_svg(creator["affiliate_link"])
    code = creator["affiliate_code"]
    link = creator["affiliate_link"]
    cta = creator.get("cta") or ("Kostenlos testen — Link in der Bio" if de else "Try it free — link in bio")

    def L(d, e):
        return d if de else e

    return {
        "video-01-intro-10s": dict(
            theme="creator-energy",
            scenes=[
                (2.5, hero(L('Medien <span class="grad-text">direkt aufs Handy</span>.', 'Media <span class="grad-text">straight to your phone</span>.')),
                 L("DownloadThat für Android", "DownloadThat for Android")),
                (2.5, phone("screenshot_main.png"), L("Link einfügen oder einfach teilen", "Paste a link or just share")),
                (2.5, steps([L("Teilen antippen", "Tap share"), L("DownloadThat wählen", "Pick DownloadThat"), L("Fertig", "Done")]),
                 L("Zwei Fingertipps — mehr nicht", "Two taps — that's it")),
                (2.5, hero(L('<span class="grad-text">Kostenlos</span> testen.', '<span class="grad-text">Try it free</span>.'),
                           L("3 Downloads/Tag · volle Qualität · Werbung", "3 downloads/day · full quality · Ad")), cta),
            ]),
        "video-02-tutorial-15s": dict(
            theme="clean-utility",
            scenes=[
                (3, hero(L('So speicherst du <span class="grad-text">erlaubte Medien</span>.', 'How to save <span class="grad-text">permitted media</span>.')),
                 L("Schritt für Schritt · Werbung", "Step by step · Ad")),
                (3, steps([L("Gewünschte Seite öffnen", "Open the page you want")]), L("Schritt 1", "Step 1")),
                (3, steps([L("Teilen antippen", "Tap share"), L("DownloadThat wählen", "Pick DownloadThat")]), L("Schritt 2 + 3", "Steps 2 + 3")),
                (3, phone("screenshot_main.png"), L("Format wählen: Video, MP3 oder Bild", "Pick a format: video, MP3 or image")),
                (3, phone("screenshot_queue.png"), L("Lokal gespeichert — läuft im Hintergrund weiter", "Saved locally — keeps running in the background")),
            ]),
        "video-03-creator-ad-20s": dict(
            theme="creator-energy",
            scenes=[
                (4, avatar_block(creator), L("Meine ehrliche App-Empfehlung · Werbung", "My honest app recommendation · Ad")),
                (4, hero(L('Downloads <span class="grad-text">ohne Umwege</span>.', 'Downloads <span class="grad-text">without detours</span>.'),
                         L("Video · Audio · Bilder — 100 % lokal", "Video · audio · images — 100% on-device")),
                 L("Keine Cloud, keine Werbung, kein Konto", "No cloud, no ads, no account")),
                (4, phone("screenshot_queue.png"), L("Teilen → DownloadThat → gespeichert", "Share → DownloadThat → saved")),
                (4, code_box(code), L("Mein Creator-Code", "My creator code")),
                (4, qr_block(qr, link), cta),
            ]),
        "video-04-review-30s": dict(
            theme="creator-energy",
            scenes=[
                (5, hero(L('Downloads auf Android sind <span class="grad-text">nervig</span>.', 'Downloads on Android are <span class="grad-text">annoying</span>.')),
                 L("Copy-Paste, dubiose Seiten, Cloud-Umwege …", "Copy-paste, sketchy sites, cloud detours…")),
                (5, hero('<span class="grad-text">DownloadThat</span>.', L("Eine App, ein Teilen-Menü", "One app, one share sheet")),
                 L("Ich habe sie eine Woche getestet · Werbung", "I tested it for a week · Ad")),
                (5, phone("screenshot_main.png"), L("Link einfügen oder teilen — bis 4K", "Paste or share — up to 4K")),
                (5, steps([L("Ganze Playlists", "Whole playlists"), L("MP3 aus jedem Video", "MP3 from any video"), L("Downloads überleben App-Kill", "Downloads survive app kills")]),
                 L("Meine drei Highlights", "My three highlights")),
                (5, hero(L('Ehrlich: <span class="grad-text">kein Netflix, kein Spotify</span>.', 'Honestly: <span class="grad-text">no Netflix, no Spotify</span>.')),
                 L("DRM-Dienste gehen nicht — bewusst", "DRM services don't work — by design")),
                (5, hero(L('Free testen, <span class="grad-text">12 € einmalig</span> für Pro.', 'Try free, <span class="grad-text">€12 once</span> for Pro.')), cta),
            ]),
        "video-05a-story-attention-6s": dict(
            theme="creator-energy",
            scenes=[
                (3, hero(L('Kennst du <span class="grad-text">das</span>?', 'You know <span class="grad-text">this</span>?'),
                         L("Video gefunden — und wie speichern?", "Found a video — now how to save it?")),
                 L("Story 1/3 · Werbung", "Story 1/3 · Ad")),
                (3, hero(L('Es geht <span class="grad-text">einfacher</span>.', 'There\'s an <span class="grad-text">easier way</span>.')),
                 L("Wischen für die Lösung →", "Swipe for the fix →")),
            ]),
        "video-05b-story-demo-6s": dict(
            theme="creator-energy",
            scenes=[
                (3, steps([L("Teilen antippen", "Tap share"), L("DownloadThat wählen", "Pick DownloadThat"), L("Fertig", "Done")]),
                 L("Story 2/3 · So geht's", "Story 2/3 · Here's how")),
                (3, phone("screenshot_queue.png"), L("Läuft im Hintergrund weiter", "Keeps running in the background")),
            ]),
        "video-05c-story-code-6s": dict(
            theme="creator-energy",
            scenes=[
                (3, code_box(code), L("Mein Code für euch", "My code for you")),
                (3, qr_block(qr, link), L("Story 3/3 · Link auch in meiner Bio", "Story 3/3 · Link also in my bio")),
            ]),
        # Video 6: ohne Sprecher — vollständig über Text/UI verständlich (EN-Basis
        # für internationale Verwendung; Texte kommen aus dieser Spezifikation).
        "video-06-no-voice-25s": dict(
            theme="creator-energy",
            lang_override="en",
            scenes=[
                (4, hero('Save media <span class="grad-text">on your phone</span>.', "Android · free tier · Ad"), "No cloud. No ads. No account."),
                (4, phone("screenshot_main.png"), "Paste a link — or just share"),
                (4, steps(["Tap share", "Pick DownloadThat", "Done — saved locally"]), "Two taps from link to file"),
                (4, phone("screenshot_queue.png"), "Video · MP3 · images · up to 4K"),
                (4, hero('Free: <span class="grad-text">3 downloads/day</span>.', "Pro: €12 one-time · no subscription"), "Only download what you're allowed to."),
                (5, qr_block(qr, link), "Scan or tap the link in bio"),
            ]),
        # Video 7: Sprecher-Version — gleiche Bildspur wie das Review, aber mit
        # Sprechpausen-Timing; das Voiceover-Skript (DE/EN) liegt als .txt bei.
        "video-07-voiceover-30s": dict(
            theme="premium-tech",
            scenes=[
                (5, hero(L('<span class="grad-text">DownloadThat</span>', 'DownloadThat'), L("Der ruhige Weg, Medien zu sichern", "The calm way to save media")),
                 L("Sprecher-Version · Werbung", "Voiceover version · Ad")),
                (5, phone("screenshot_main.png"), L("Ein Eingabefeld. Eine Qualität. Ein Knopf.", "One input. One quality. One button.")),
                (5, steps([L("Teilen", "Share"), L("DownloadThat", "DownloadThat"), L("Gespeichert", "Saved")]), L("Der ganze Workflow", "The whole workflow")),
                (5, phone("screenshot_queue.png"), L("Warteschlange mit echtem Fortschritt", "A queue with real progress")),
                (5, hero(L('Free für immer, Pro für <span class="grad-text">12 €</span>.', 'Free forever, Pro for <span class="grad-text">€12</span>.')),
                 L("Einmal zahlen, kein Abo", "Pay once, no subscription")),
                (5, qr_block(qr, link), cta),
            ]),
    }


VOICEOVER_SCRIPTS = {
    "de": """Sprecher-Skript — DownloadThat, 30 Sekunden (Video 7)
[0-5 s]   Es gibt Apps, die machen viel Lärm. Und es gibt DownloadThat.
[5-10 s]  Ein Eingabefeld, eine Qualitätswahl, ein Knopf. Mehr braucht es nicht.
[10-15 s] Oder noch einfacher: Teilen antippen, DownloadThat wählen — gespeichert.
[15-20 s] Videos, Musik als MP3, Bilder. Alles bleibt lokal auf deinem Gerät.
[20-25 s] Die Free-Version bleibt für immer kostenlos. Pro kostet einmalig zwölf Euro — kein Abo.
[25-30 s] DownloadThat für Android. Der Link ist in der Beschreibung. [Werbung; Hinweis: Lade nur Inhalte herunter, für die du die Rechte besitzt.]
""",
    "en": """Voiceover script — DownloadThat, 30 seconds (video 7)
[0-5 s]   Some apps make a lot of noise. And then there's DownloadThat.
[5-10 s]  One input field, one quality picker, one button. That's all it takes.
[10-15 s] Or even simpler: tap share, pick DownloadThat — saved.
[15-20 s] Videos, music as MP3, images. Everything stays local on your device.
[20-25 s] The free tier stays free forever. Pro is a one-time twelve euros — no subscription.
[25-30 s] DownloadThat for Android. Link in the description. [Ad; only download content you have the rights to.]
""",
}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _fmt_ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_srt(scenes: list, out_srt: Path) -> None:
    lines = []
    t = 0.0
    for i, (dur, _body, caption) in enumerate(scenes, start=1):
        import re as _re

        text = _re.sub(r"<[^>]+>", "", caption)
        lines.append(f"{i}\n{_fmt_ts(t)} --> {_fmt_ts(t + dur)}\n{text}\n")
        t += dur - XFADE
    out_srt.write_text("\n".join(lines), encoding="utf-8")


def _music_filter(duration: float) -> str:
    """Selbst erzeugter, neutraler Synth-Pad (CC0 — im Projekt generiert)."""
    return (
        "aevalsrc='(0.10*sin(2*PI*220*t)+0.08*sin(2*PI*277.18*t)"
        "+0.08*sin(2*PI*329.63*t)+0.05*sin(2*PI*440.8*t))"
        f"*(0.75+0.25*sin(2*PI*0.13*t))':s=44100:d={duration:.2f},"
        "lowpass=f=900,afade=t=in:d=1.2,"
        f"afade=t=out:st={max(duration - 1.5, 0):.2f}:d=1.5,volume=0.5"
    )


def render_video(name: str, spec: dict, out_dir: Path, creator: dict, lang: str,
                 music: Path | None = None) -> Path:
    ff = find_ffmpeg()
    lang = spec.get("lang_override", lang)
    scenes = spec["scenes"]
    theme_class = {"premium-tech": "theme-pt", "creator-energy": "theme-ce", "clean-utility": "theme-cu"}[spec["theme"]]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = out_dir / f"{name}-{lang}.mp4"
    rw, rh = int(W * SCALE), int(H * SCALE)

    with tempfile.TemporaryDirectory(prefix="ckit-video-") as td:
        tdir = Path(td)
        # 1. Szenen rendern
        for i, (dur, body, caption) in enumerate(scenes):
            ctx = build_context(
                lang=lang, creator=creator,
                theme=theme_class, W=rw, H=rh,
                scene_body=body, scene_caption=caption,
                scene_title_size=104, scene_phone_w=560, scene_phone_h=900,
                logo_size=76, logo_gap=20, logo_font=50,
            )
            html = render_template("scenes/scene.html", ctx)
            html_to_png(html, tdir / f"scene{i}.png", rw, rh)

        # 2. ffmpeg-Filtergraph: zoompan je Szene + xfade-Kette
        inputs: list[str] = []
        filters: list[str] = []
        for i, (dur, _b, _c) in enumerate(scenes):
            frames = int(dur * FPS)
            inputs += ["-loop", "1", "-t", f"{dur:.2f}", "-i", str(tdir / f"scene{i}.png")]
            zexpr = (
                f"zoom+{0.05 / frames:.6f}" if i % 2 == 0
                else f"1.05-{0.05 / frames:.6f}*on"
            )
            filters.append(
                f"[{i}:v]fps={FPS},zoompan=z='{zexpr}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"
                f":d={frames}:s={W}x{H}:fps={FPS},setsar=1[v{i}]"
            )
        last = "v0"
        offset = 0.0
        for i in range(1, len(scenes)):
            offset += scenes[i - 1][0] - XFADE
            out_lbl = f"x{i}" if i < len(scenes) - 1 else "vout"
            filters.append(
                f"[{last}][v{i}]xfade=transition=fade:duration={XFADE}:offset={offset:.2f}[{out_lbl}]"
            )
            last = out_lbl
        if len(scenes) == 1:
            filters.append("[v0]null[vout]")

        total = sum(d for d, _b, _c in scenes) - XFADE * (len(scenes) - 1)
        # 3. Audio
        if music:
            audio_in = ["-i", str(music)]
            amap = [f"{len(scenes)}:a"]
            afilter = []
        else:
            filters.append(f"{_music_filter(total)}[aout]")
            audio_in, amap, afilter = [], ["[aout]"], []

        cmd = [
            ff, "-y", *inputs, *audio_in,
            "-filter_complex", ";".join(filters + afilter),
            "-map", "[vout]", "-map", *amap,
            "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
            str(out_mp4),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise VideoError(f"ffmpeg fehlgeschlagen für {name}:\n{proc.stderr[-2500:]}")

    _write_srt(scenes, out_mp4.with_suffix(".srt"))
    print(f"  ✓ {out_mp4.relative_to(REPO) if out_mp4.is_relative_to(REPO) else out_mp4}")
    return out_mp4


DEFAULT_CREATOR = {
    "creator_name": "Dein Name",
    "creator_handle": "@dein.kanal",
    "affiliate_code": "DEINCODE",
    "affiliate_link": "https://downloadthat.pages.dev/?ref=DEINCODE",
    "cta": "",
    "discount_text": "",
    "initial": "D",
}


def cmd_videos(creator: dict | None = None, out_dir: Path | None = None,
               lang: str = "de", names: list[str] | None = None,
               music: Path | None = None) -> list[Path]:
    creator = creator or dict(DEFAULT_CREATOR)
    out_dir = out_dir or OUT_BASE
    specs = video_specs(creator, lang)
    results = []
    print("[Videos]")
    for name, spec in specs.items():
        if names and name not in names:
            continue
        results.append(render_video(name, spec, out_dir, creator, lang, music=music))
    # Sprecher-Skripte für Video 7 beilegen
    for lg, text in VOICEOVER_SCRIPTS.items():
        p = out_dir / f"video-07-voiceover-script-{lg}.txt"
        p.write_text(text, encoding="utf-8")
    return results
