# Play Console store listing assets

Existing material and the capture contract for the next Play listing. The
canonical locale mapping is `play_locale_matrix.json`.

## Release status

`BLOCKED`: current phone images predate the 1.0.4.2 UI/string freeze and there
are no verified 7-inch or 10-inch captures. Nothing in this directory authorizes
an upload. Final screenshots must be captured from a debug build of the exact
frozen candidate commit; generated UI, PSD compositions and campaign images are
not substitutes for product screenshots.

## Files

- `icon-512.png` — hi-res icon (512×512, rendered from `video_downloader/web/static/icon.svg`).
- `feature_graphic-1024x500.png` — feature graphic (source: `feature_graphic.svg`, edit and
  re-render with `cairosvg` if the wording/branding changes).
- `feature_graphic-zh-CN-1024x500.png`, `feature_graphic-ja-1024x500.png`, and
  `feature_graphic-ru-1024x500.png` — localized feature graphics for Simplified
  Chinese, Japanese, and Russian. Their editable SVG sources are beside them.
- `screenshot_main.png`, `screenshot_queue.png`, `screenshot_settings.png` — real phone-sized
  (Pixel 7 emulation, 1082×2202 device pixels) screenshots of the actual running app (captured via Playwright against a local
  `classydl web` instance, not mockups). `screenshot_queue.png` has synthetic job rows (one
  playlist video, one audio file, and one video) inserted directly into the queue store — no real
  network download happened. **Known issue, not yet fixed:** at 1082×2202 these are
  height÷width = 2.035, just over Play Console's documented 2:1 cap on phone screenshots
  ([support.google.com/googleplay/android-developer/answer/9866151](https://support.google.com/googleplay/android-developer/answer/9866151))
  — re-capture at viewport height 824 (see below) before relying on these for a real upload.
- `screenshots/screenshot_main_<locale>.png` (light) and `screenshots/screenshot_main_<locale>_dark.png`
  (dark) — one home-screen screenshot per supported locale per theme, 1082×2163 (kept under
  the 2:1 cap unlike the three files above), for the Play Console per-language screenshot
  slots. Generated with `scripts/capture_locale_screenshots.py`, which drives the same
  in-page `setLanguage()`/`applyTheme()` the settings dropdowns use so what's captured is
  exactly what a user sees — re-run it after any `video_downloader/web/static/i18n/*.json` or
  `index.html` copy change:
  `.venv-win/Scripts/python.exe scripts/capture_locale_screenshots.py` (needs Playwright +
  Chromium, not a project dependency — `uv pip install playwright && playwright install
  chromium` first). Locale codes match the filenames under
  `video_downloader/web/static/i18n/`. Play Console has no separate "dark screenshot" slot —
  a listing's `phoneScreenshots` is just one ordered array per language, so light/dark is a
  curation choice (which screenshots go in the array, and in what order), not a technical one.
- `icon-pro-1024.png`, `icon-pro-badge-1024.png` — **not committed to git yet, unclear
  status, needs owner review before use.** Appeared as untracked files in the working
  tree on 2026-08-03 (same day as the T22/T23 tester-feedback work) with no
  accompanying task claim, log entry, README update, or reference anywhere in
  code/docs/CI — so they won't be present in a fresh clone. Likely an exploratory
  "Pro" app-icon variant (an infinity/download-arrow mark) and a badge overlay of the
  same mark with a "PRO" pill, possibly scoped toward the tester-report's "better
  screenshots/store visuals" suggestion (see
  `docs/TESTER_REPORT_ASSESSMENT_2026-08-03.md`). Do not wire these into the Play
  listing, the app icon, or any store asset — and don't `git add` them — without
  confirming they're the intended final design first; nothing currently depends on
  them.
- This README.

The icon is language-neutral and is reused for every translation. The existing
phone screenshots are English UI captures; Play Console may reuse the default
listing graphics for localized listings when no localized screenshots are
provided.

These assets are release candidates, but must still pass the policy-copy checks below and
be recaptured after material UI changes. Store screenshots must use neutral example URLs;
never show protected-platform brands or imply that every site is supported.

## Store listing text

### Short description (≤80 characters)

**German:** `Video und Audio aus Links laden, die du rechtmäßig speichern darfst.`
**English:** `Download video and audio from links you may lawfully save.`

### Full description (≤4000 characters)

**German:**

```
DownloadThat speichert Videos und Audio aus Links, die du rechtmäßig
speichern darfst – direkt auf deinem Gerät.

WICHTIGSTE FUNKTIONEN
• Ein Feld für einen Link, mehrere Links oder eine ganze Playlist
• Video oder Audio (MP3) getrennt herunterladen
• Qualitätsauswahl von 240p bis 4K
• Automatischer Fortschrittsbalken für laufende Downloads
• Eigenen Download-Ordner wählen, Dateien direkt öffnen oder teilen
• Medienverarbeitung auf deinem Gerät – keine Werbung, kein Tracking
• Verfügbar in vielen Sprachen

KOSTENLOS NUTZBAR
Die kostenlose Version bietet 3 erfolgreiche Downloads je rollierenden 24
Stunden. Pro entfernt das tägliche App-Downloadlimit von DownloadThat.

WICHTIGER HINWEIS
DownloadThat ist ein technisches Werkzeug. Du bist selbst dafür verantwortlich,
sicherzustellen, dass du die erforderlichen Rechte an den Inhalten besitzt. Die
App umgeht weder DRM noch Paywalls. Bitte lade nur eigene, gemeinfreie, entsprechend
lizenzierte oder ausdrücklich freigegebene Inhalte herunter.
```

**English:**

```
DownloadThat saves video and audio from links you may lawfully save —
directly on your device.

KEY FEATURES
• One field for a single link, multiple links, or a whole playlist
• Download video or audio (MP3) separately
• Quality selector from 240p up to 4K
• Live progress bar for running downloads
• Choose your own download folder, open or share files directly
• Media processing happens on your device — no ads, no tracking
• Available in many languages

FREE TO USE
The Free tier offers 3 successful downloads per rolling 24 hours.
Pro removes DownloadThat's daily app download limit.

IMPORTANT
DownloadThat is a technical tool. You are responsible for making sure you
have the required rights. The app does not bypass DRM or paywalls. Only save
content you own, public-domain or appropriately licensed content, or content
you have explicit permission to download.
```

## Regenerating

```bash
pip install cairosvg pillow
python3 -c "
import cairosvg
cairosvg.svg2png(url='video_downloader/web/static/icon.svg', write_to='store_assets/icon-512.png', output_width=512, output_height=512)
cairosvg.svg2png(url='store_assets/feature_graphic.svg', write_to='/tmp/fg.png', output_width=1024, output_height=500)
from PIL import Image
Image.open('/tmp/fg.png').convert('RGB').save('store_assets/feature_graphic-1024x500.png')
"
```

Screenshots: run `classydl web --password ... -o /tmp/out`, then drive it with Playwright at a
412×915 viewport (see git history of this file's introducing commit for the exact script used).

## Final screenshot layout and dry-run

After UI/string freeze, place at least four real PNG captures for every real UI
locale under each of:

- `captures/phone/<ui-locale>/`
- `captures/7-inch/<ui-locale>/`
- `captures/10-inch/<ui-locale>/`

The 20 unsupported Play languages deliberately reuse `captures/*/en/` through
the canonical matrix. Preview all 86×3 assignments without credentials or
network writes:

```powershell
node scripts/upload_google_play.mjs --sync-screenshot-assets true --package de.classydl.app --locale-matrix store_assets/play_locale_matrix.json --phone-dir store_assets/captures/phone --seven-inch-dir store_assets/captures/7-inch --ten-inch-dir store_assets/captures/10-inch --dry-run true
```

An upload requires both `--dry-run false` and `--confirm-upload true`; neither
is allowed before the documented TEAM-Go.
