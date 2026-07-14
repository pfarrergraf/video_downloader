# Play Console store listing assets

Prepared ahead of time so registration + submission (see
`docs/ANDROID_APP_PLAN.md` Phase 7) doesn't block on generating these.

## Files

- `icon-512.png` — hi-res icon (512×512, rendered from `video_downloader/web/static/icon.svg`).
- `feature_graphic-1024x500.png` — feature graphic (source: `feature_graphic.svg`, edit and
  re-render with `cairosvg` if the wording/branding changes).
- `screenshot_main.png`, `screenshot_queue.png`, `screenshot_settings.png` — real phone-sized
  (412×915 @2x) screenshots of the actual running app (captured via Playwright against a local
  `classydl web` instance, not mockups). `screenshot_queue.png` has synthetic job rows (one
  completed, one in-progress, one pending) inserted directly into the queue store to show all
  three states in one shot — no real network download happened.
- This README.

These assets are release candidates, but must still pass the policy-copy checks below and
be recaptured after material UI changes. Store screenshots must use neutral example URLs;
never show protected-platform brands or imply that every site is supported.

## Store listing text

### Short description (≤80 characters)

**German:** `Video, Audio und Bilder aus Links laden, die du rechtmäßig speichern darfst.`
**English:** `Download video, audio and images from links you may lawfully save.`

### Full description (≤4000 characters)

**German:**

```
DownloadThat speichert Videos, Audio und Bilder aus Links, die du rechtmäßig
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
DownloadThat saves video, audio and images from links you may lawfully save —
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
