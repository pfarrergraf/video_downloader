# Play Console store listing assets

Prepared ahead of time so registration + submission (see
`docs/ANDROID_APP_PLAN.md` Phase 7) doesn't block on generating these.

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
  network download happened.
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
• Läuft komplett auf deinem Gerät – keine Werbung, kein Tracking
• Verfügbar in vielen Sprachen

KOSTENLOS NUTZBAR
Die kostenlose Version bietet die volle Qualität bis 4K, begrenzt auf ein
tägliches Download-Kontingent. Mit DownloadThat Pro entfällt dieses Limit.

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
The free tier offers full quality up to 4K, limited to a daily download
quota. DownloadThat Pro removes that limit.

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
