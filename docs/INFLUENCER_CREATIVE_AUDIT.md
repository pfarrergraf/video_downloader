# DownloadThat — Influencer Creative Audit

**Stand:** 2026-07-10 · **Branch:** `claude/downloadthat-creator-kit-tiisu5`
**Zweck:** Faktenbasis für das Influencer-Recruitment-Kit und das Influencer-Promotion-Kit.
Jede Marketingaussage in den Creator-Materialien muss sich auf dieses Dokument zurückführen lassen.

---

## 1. Produktstand (verifiziert im Code / auf der Website)

| Fakt | Wert | Quelle |
|---|---|---|
| Produktname | **DownloadThat** (Engine intern: ClassyDL) | `README.md`, `store_assets/` |
| Plattform | Android (Sideload-APK, kein Play Store), zusätzlich Windows/Termux für Entwickler | `README.md`, `pro/website/index.html` |
| Website | `https://downloadthat.pages.dev` | `pro/README.md` |
| Funktionsumfang | Video, Audio (MP3-Extraktion), Bilder; Playlists komplett; bis 4K; Seiten-Scraper („Search a page“, Deep Search) | `pro/website/i18n/de.json`, App-Screenshots |
| Bedienweg 1 | Link(s) einfügen → Qualität wählen → Download | `store_assets/screenshot_main.png` |
| Bedienweg 2 | Android-Share-Sheet: „Teilen“ → DownloadThat → Smart Mode startet mit gemerkten Einstellungen (2 Taps) | `docs/SIMPLE_APP_REDESIGN_2026-07-07.md` |
| Zuverlässigkeit | Foreground-Service, Kill-Recovery mit echtem Resume, Benachrichtigungen, selbstheilende Engine (täglicher yt-dlp-Selbst-Update), klassifizierte menschliche Fehlermeldungen | `docs/SIMPLE_APP_REDESIGN_2026-07-07.md` |
| Privatsphäre | 100 % lokal auf dem Gerät, kein Cloud-Upload, keine Werbung, kein Tracking, kein Konto | `i18n/de.json` (features.f3, f4) |
| Sprachen / UI | Deutsch + Englisch, Hell-Theme-Standard + Dunkel, große Schrift/Touch-Ziele (seniorentauglich) | `SIMPLE_APP_REDESIGN_2026-07-07.md` |
| **Free-Tier** | **3 Downloads pro Tag**, volle HD/4K-Qualität, für immer, ohne Konto | `video_downloader/licensing.py:43` (`FREE_DAILY_DOWNLOAD_LIMIT = 3`), `i18n/de.json` |
| **Pro** | **12 € einmalig, kein Abo**: unbegrenzte Downloads, Playlist-Downloads, alle Updates | `i18n/de.json` (pricing), Stripe-Link in `index.html` |
| Grenzen | Keine DRM-Streaming-Dienste (Spotify, Netflix o. ä.); kein iOS; kein In-App-Browser | `i18n/de.json` (features.f1_desc), Redesign-Doc („bewusst NICHT gebaut“) |

> ⚠️ Veraltete Angaben, die NICHT mehr verwendet werden dürfen: drei Preisstufen (1 €/Monat, 5 €/Jahr) aus `pro/README.md` — der Live-Stand ist **eine Lizenz, 12 € einmalig**. Ebenso „5 Downloads/Tag“ (alter Wert) — aktuell sind es **3**.

## 2. Affiliate-Programm (Stand HANDOVER.md, 2026-07-10)

- **Status:** Registrierung ist öffentlich geöffnet (`partner.html`); **Bezahl-/Auszahlungsfunktion ist noch deaktiviert** und wird separat freigeschaltet. Materialien müssen das ehrlich sagen („früh dabei sein“, kein „verdiene ab heute“).
- **Vergütung** je bestätigtem Pro-Lizenzkauf, gestaffelt nach Gesamtverkäufen des Partners:
  1–10: 2,00 € · 11–50: 2,50 € · 51–100: 3,00 € · 101–500: 3,50 € · ab 501: 4,00 €
- 180 Tage Last-Touch-Attribution; ausdrücklich eingegebener Partnercode hat Vorrang; 30 Tage Prüfzeit; Auszahlung monatlich ab 50 €; keine Provision bei Refund, Dispute oder Eigenkauf.
- **Kein Kundenrabatt in Version 1** → `{{discount_text}}` bleibt leer; Rabatte dürfen niemals erfunden werden.
- Partner erhalten: persönlichen Partnerlink, Direktkauf-Link, Partnercode, Android-Claim-Link (`/claim/<partner>`), Dashboard mit aggregierten Statistiken. Login per Magic-Link, kein Passwort.

## 3. Vorhandenes Branding — zwei Gesichter, beide echt

| | Website („Gothic Premium“) | App („Creator Gradient“) |
|---|---|---|
| Hintergrund | `#0e0c14` (Schwarz-Violett), Karten `#1b1626` | `#12101f`-Navy, Karten `#1c1a2e` |
| Akzent | **Gold** `#c9a869`, dim `#8a713f`, hell `#d9bb82` | **Gradient Koralle→Pfirsich→Mint** (`#ff6b6b → #ffb26b → #4adfb6`) |
| Text | `#f1ede4` / `#a89fb3` | Weiß / Lavendel-Grau |
| Quelle | `pro/website/index.html` CSS-Variablen | `store_assets/icon-512.png`, `feature_graphic-1024x500.png`, `screenshot_main.png` |

Der ursprüngliche Auftrag nennt „warme Goldakzente“ — das trifft auf die **Website** zu; die **App** selbst nutzt den Koralle-Mint-Gradienten. Beide Welten werden im Kit als Designrichtungen abgebildet (Premium Tech = Gold, Creator Energy = Gradient).

**Logo:** `store_assets/icon-512.png` (+ `video_downloader/web/static/icon.svg`) — abgerundetes dunkles Quadrat, Gradient-Pfeil nach unten auf Grundlinie. Wortmarke: fette Grotesk mit Verlaufsfüllung (siehe `feature_graphic.svg`).

## 4. Vorhandene Assets

- `store_assets/icon-512.png` — App-Icon 512², transparenzlos, dunkler Kachelhintergrund.
- `store_assets/feature_graphic-1024x500.png` (+ `.svg` Master) — Wortmarke + Claim „Video, audio & images — from any site“.
- `store_assets/screenshot_main.png` (824×1830) — Startansicht: Link-Feld, Qualität „Auto (up to 4K)“, Buttons „Download video/audio“ (engl. UI).
- `store_assets/screenshot_queue.png` (824×1830) — „Search a page“, Queue mit laufendem Download (Fortschrittsbalken 61 %, MB-Anzeige) und abgeschlossenem Download.
- `store_assets/screenshot_settings.png` — Einstellungen.
- `pro/website/index.html` — eingebetteter Hero-Screenshot (Scrape-Ergebnis mit Auswahl) als Data-URI.

## 5. Fehlende Aufnahmen (Platzhalter-Pflicht, nichts fälschen)

| Wunsch-Aufnahme | Dateiname (Soll) | Auflösung | Beschreibung |
|---|---|---|---|
| Share-Sheet-Moment | `store_assets/screenshot_share_sheet.png` | 1080×2400 | Android-Teilen-Dialog mit sichtbarem DownloadThat-Eintrag über einer Videoseite |
| Deutsche UI, helles Theme | `store_assets/screenshot_main_de_light.png` | 1080×2400 | Startansicht deutsch/hell (aktueller Redesign-Stand) |
| Format-Auswahl | `store_assets/screenshot_format_choice.png` | 1080×2400 | Auswahl Video/Audio/Bild bzw. Qualitätsliste |
| Fertig-Notification | `store_assets/screenshot_notification.png` | 1080×2400 | Fortschritts-/Fertig-Benachrichtigung |
| „Meine Downloads“ | `store_assets/screenshot_my_downloads.png` | 1080×2400 | Liste mit Ansehen/Teilen-Buttons |
| Screenrecording Share-Flow | `store_assets/recording_share_flow.mp4` | 1080×2400, 10–15 s | Teilen → DownloadThat → Fortschritt → fertig (Basis für echte Produktvideos) |

Bis diese existieren, verwenden die Templates die drei echten Store-Screenshots; UI-Nachbauten in Videos sind als **stilisierte Darstellung** gekennzeichnet und geben sich nicht als echte Screenshots aus.

## 6. Erlaubte Kernbotschaften (Positivliste)

- Medien direkt auf dem eigenen Gerät speichern/verarbeiten; keine unnötige Cloud-Zwischenstation.
- Einfacher Ablauf: „Teilen → DownloadThat → gespeichert“ bzw. Link einfügen.
- Video, Audio (MP3) und Bilder; ganze Playlists; bis 4K.
- Free-Version zum Testen (3 Downloads/Tag, volle Qualität); Pro-Lizenz 12 € einmalig, kein Abo, unbegrenzt.
- Keine Werbung, kein Tracking, kein Konto; Downloads überleben das Schließen der App.
- Android-Fokus, Installation direkt von der Website (bewusst ohne Play Store).
- Pflicht-Hinweis, wo thematisch passend: **„Lade nur Inhalte herunter, für die du die erforderlichen Rechte oder die Erlaubnis besitzt.“**

## 7. Verbotene Aussagen (Negativliste)

„lädt wirklich alles herunter“ · „funktioniert garantiert auf jeder Plattform“ · „umgeht jeden Kopierschutz“ · jegliche DRM-Umgehungs-Hinweise · erfundene Rabatte (es existiert keiner) · erfundene Nutzerzahlen/Bewertungen/Testimonials · garantierte oder suggerierte Einnahmen · falsche Verknappung · Play-Store-/App-Store-Verfügbarkeit · „von Google geprüft“ · Zertifizierungs-Behauptungen (siehe `HANDOVER.md` §13).

## 8. Widersprüche / Altlasten im Repo

1. `pro/README.md` beschreibt drei Stripe-Preise (Monat/Jahr/Lifetime) und „FREE_DAILY_DOWNLOAD_LIMIT (currently 5)“ — beides überholt; maßgeblich sind `licensing.py` (3/Tag) und die Live-Website (12 € einmalig).
2. `pro/README.md` nennt die App „German-only“ — seit dem Simple-App-Redesign ist die UI de **und** en.
3. Store-Screenshots zeigen die englische Dunkel-UI vor dem Hell-Theme-Redesign — nutzbar, aber die fehlenden Aufnahmen aus §5 sollten sie mittelfristig ersetzen.

## 9. Konsequenzen für das Creator-Kit

- Alle Templates ziehen Preis-/Limit-Angaben aus einer zentralen Faktendatei (`creator_tools/config/product_facts.json`) statt hartkodierter Texte — eine Stelle zum Aktualisieren.
- Personalisierung ausschließlich über `{{platzhalter}}`; `{{discount_text}}` ist standardmäßig leer und wird bei leerem Wert samt umgebender Zeile entfernt.
- QR-Codes verweisen nur auf echte Ziele (`https://downloadthat.pages.dev/…` bzw. den vom Partner konfigurierten `affiliate_link`).
- Affiliate-Kommunikation trägt immer den Status-Hinweis, solange die Auszahlung deaktiviert ist.
