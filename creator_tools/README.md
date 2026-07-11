# creator_tools — DownloadThat Influencer- & Affiliate-Creator-Kit

Werkzeuge, Templates und Render-Pipeline für das Marketing-Kit. Zwei Pakete:

- **Kit A (Recruitment)** — Material, mit dem der Betreiber Creator anspricht:
  A4-Flyer (PDF/PNG), One-Pager, 8-Seiten-Deck, Outreach-Texte.
- **Kit B (Promotion)** — Material für gewonnene Partner: Story-/Feed-/Carousel-,
  Thumbnail-, Karten-, QR- und Video-Vorlagen (DE/EN), Captions und Skripte.

Fertig gerenderte, unpersonalisierte Assets liegen unter
`pro/website/assets/influencer/` und werden vom Creator-Portal
(`pro/website/creator-kit.html`) verlinkt. Übersicht aller Renders:
`docs/influencer-kit-preview.html`. Faktenbasis und erlaubte Aussagen:
`docs/INFLUENCER_CREATIVE_AUDIT.md`.

## Voraussetzungen

```bash
uv sync --extra creator          # segno (QR) + pillow — reine Python-Wheels
```

Zusätzlich (nur zum Rendern, nicht für Tests der Logik):

- **Chromium/Chrome** — HTML→PNG/PDF. Gefunden über `CREATOR_CHROME_BIN`,
  `/opt/pw-browsers/chromium` oder `PATH`. Kein Playwright-Python nötig.
- **ffmpeg mit libx264+aac** — nur für die Video-Vorlagen.

Das ist bewusst ein **Desktop-/CI-Werkzeug**: Auf Termux/Android wird nichts
hiervon gebraucht (die Termux-Regel „nur reine Python-Wheels“ aus `CLAUDE.md`
bleibt gewahrt — segno/pillow sind die einzigen Python-Abhängigkeiten, und die
App selbst importiert nichts aus `creator_tools/`).

## Unpersonalisiertes Kit bauen

```bash
uv run python creator_tools/build_kit.py directions   # 3 Designrichtungen × 6 Artefakte
uv run python creator_tools/build_kit.py kit          # alle Bilder, Flyer, Deck, One-Pager
uv run python creator_tools/build_kit.py videos       # 7 Motion-Vorlagen (9 MP4s + SRT)
uv run python creator_tools/build_kit.py all
```

## Personalisiertes Kit für einen Creator

```bash
uv run python creator_tools/generate_creator_kit.py creator_tools/config/example_creator.json
uv run python creator_tools/generate_creator_kit.py cfg.json --with-videos --lang en
```

Ausgabe: `creator_tools/output/<creator>/` mit Stories, Feed-Posts, Thumbnail,
Affiliate-/QR-Karten, Endcard, A4-Flyer (PDF+PNG), Captions (DE+EN) und optional
personalisierten MP4s. Konfig-Felder: siehe `config/example_creator.json`;
Pflicht sind `creator_name`, `affiliate_code`, `affiliate_link`.

Schutzregeln (führen zu hartem Fehler statt stillem Unsinn):

- `affiliate_link` muss eine echte `http(s)`-URL sein (QR mit Fantasieziel wird verweigert),
- `discount_text` ohne `discount_confirmed: true` bricht ab — es existiert kein
  Rabatt im Partnerprogramm v1, und Vorlagen dürfen keinen erfinden,
- unbekannte Template-Schlüssel brechen den Render ab (Tippfehler fallen sofort auf).

## Aufbau

```
creator_tools/
  build_kit.py             # unpersonalisierter Gesamt-Build
  generate_creator_kit.py  # personalisierte Kits aus JSON-Config
  kit/                     # Templating (Mustache-Subset), Renderer (Chromium),
                           # QR (segno), Video (ffmpeg), Fakten/Kontext, Specs
  templates/               # HTML-Master (bearbeitbar), 3 Themes über CSS-Variablen
  config/product_facts.json# EINZIGE Quelle für Preise/Limits/Provisionen
  assets/fonts/            # Inter + Space Grotesk (SIL OFL, lokal, offline)
  output/                  # personalisierte Kits (gitignored)
```

Design-Themes: `premium-tech` (Website-Gold auf Schwarz), `creator-energy`
(App-Gradient Koralle→Mint), `clean-utility` (hell, Tutorial-Fokus). Vergleich:
`docs/influencer-design-directions.html`.

## Fakten ändern (Preis, Limit, Provision …)

Nur `config/product_facts.json` anpassen und neu bauen — Templates enthalten
keine hartkodierten Preise. `tests/test_creator_tools.py` prüft, dass die
Faktendatei mit dem Code übereinstimmt (z. B. `FREE_DAILY_DOWNLOAD_LIMIT`).

## Musik in den Videos

Die Musikspur wird beim Rendern als neutraler Synth-Pad **selbst erzeugt**
(ffmpeg `aevalsrc`, im Projekt generiert, keine Fremdlizenz). Eigene Musik:
`--music pfad/zur/datei.mp3` beim Video-Build bzw. Generator.
