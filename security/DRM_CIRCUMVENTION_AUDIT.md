# DRM / Technical-Protection-Measure Circumvention Audit

Datum: 2026-07-13. Zweck: die öffentlich gemachte Aussage **„DownloadThat bypasses no
DRM / no technical protection measures"** von einer Behauptung zu einer **codeseitig
verifizierten Tatsache** machen. Das ist die juristisch wichtigste Eigenschaft der App:
Nach § 95a UrhG / Art. 6 InfoSoc-RL ist das Bereitstellen eines Werkzeugs *per se*
verboten, wenn dessen Zweck die **Umgehung wirksamer technischer Schutzmaßnahmen** ist —
unabhängig von der Nutzerabsicht. Solange die App **keine** TPM umgeht, bleibt sie ein
zulässiges Dual-Use-Werkzeug.

## Ergebnis: KEINE DRM-/TPM-Umgehung im Code

Vollständige Suche über `video_downloader/**` nach Umgehungs-Indikatoren
(`widevine`, `playready`, `fairplay`, `cenc`, `clearkey`, `pssh`, `mp4decrypt`,
`bento4`, `decrypt`, `allow_unplayable_formats`, `drm`, `unplayable`):

| Prüfpunkt | Ergebnis |
|---|---|
| Widevine/PlayReady/FairPlay-Handling | **Keins** |
| CENC/ClearKey/PSSH-Key-Extraktion | **Keine** |
| Externe Entschlüsselungs-Tools (mp4decrypt, Bento4, …) aufgerufen | **Nein** |
| `allow_unplayable_formats` in yt-dlp-Optionen gesetzt | **Nein** → bleibt beim yt-dlp-Default `False` |
| Einzige „DRM"-Fundstelle im Code | Der Verzicht-Hinweis selbst (`cli.py:1300`) |

**Kernbeleg:** In `video_downloader/strategies.py` (yt-dlp-Optionsaufbau, Zeilen 112-153)
wird `allow_unplayable_formats` bewusst **nicht** gesetzt. yt-dlp lehnt DRM-geschützte
Streams damit von sich aus ab (Fehler „This video is DRM protected") — die App kann
Netflix/Disney+/Spotify-Premium-o.ä.-Inhalte technisch **nicht** speichern. Die
ffmpeg-/direct-Strategien remuxen nur bereits **unverschlüsselt ausgelieferte** Streams.

## Wichtige Nuance (für die anwaltliche Bewertung)

- **`cookiesfrombrowser`** (`strategies.py:136-137`) erlaubt yt-dlp den Zugriff mit den
  **eigenen** Browser-Cookies des Nutzers. Das ist **keine** TPM-Umgehung, sondern
  authentifizierter Zugriff mit den legitimen Zugangsdaten des Nutzers (z. B. auf eigene,
  login-geschützte Inhalte). Rechtlich getrennt von § 95a zu bewerten, aber klar
  abzugrenzen.
- Die App speichert **ungeschützt ausgelieferte** Streams. Ob eine konkrete Plattform
  (z. B. YouTubes Signatur/„rolling cipher") als *wirksame* technische Schutzmaßnahme
  i.S.d. § 95a gilt, ist eine **Rechtsfrage** (in DE umstritten) — nicht durch dieses
  Code-Audit entschieden, sondern der anwaltlichen Bewertung vorbehalten.

## Erhaltungsauflage

Diese Eigenschaft ist eine juristische Kernannahme. Daher:
- `allow_unplayable_formats` darf **nicht** aktiviert werden.
- Keine Widevine-/CENC-/ClearKey-Entschlüsselung, keine Einbindung von mp4decrypt/Bento4
  oder vergleichbaren Tools.
- Jede Änderung in `strategies.py` an der yt-dlp-Optionskonstruktion ist gegen diese Auflage
  zu prüfen. Empfehlung: künftig durch einen Test absichern, der das Fehlen von
  `allow_unplayable_formats` erzwingt.
