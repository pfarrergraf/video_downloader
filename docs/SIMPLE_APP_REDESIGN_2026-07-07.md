# Simple-App-Redesign — Umbau für Jugendliche & Senioren (2026-07-07)

Ziel (Owner-Auftrag): Die Android-App soll **einfacher, schneller,
verlässlicher und intuitiver** sein als die populären Konkurrenten
(Seal, YTDLnis, NewPipe & Forks, TubeMate/Snaptube, 1DM/ADM).
Alle sechs Phasen sind umgesetzt; jede Phase ist ein eigener Commit auf
`claude/android-downloader-app-analysis-sofdmq`.

## Wo wir die Konkurrenz schlagen

| Kriterium | Konkurrenz-Benchmark | DownloadThat jetzt |
|---|---|---|
| Taps vom Link zum Download | YTDLnis: ~2 (Share-Sheet) | **2**: Teilen → App (Smart Mode wendet gemerkte Einstellungen an und startet sofort) |
| YouTube-Änderung bricht App | NewPipe: tagelang tot bis App-Update; Seal/YTDLnis: manuelles yt-dlp-Update | **Selbstheilend**: täglicher Engine-Check + automatisches Update bei Extractor-Fehlern, ein Gratis-Retry |
| App-Kill mitten im Download | Alle: Foreground-Service; keiner erklärt Fehler | **Foreground-Service + Kill-Recovery + echtes Resume** (`.part`-Dateien überleben, HTTP-Range) |
| Fehlermeldungen | Überall rohe yt-dlp-Stacktraces | **10 klassifizierte Codes → menschliche Sätze** („Dieses Video ist leider nicht mehr verfügbar."), Roh-Fehler hinter „Details anzeigen" |
| Senioren-Tauglichkeit | Nirgends (Grayjay sogar negativ) | Hell-Theme-Standard, 18-px-Basis, System-Schriftgröße (textZoom), ≥48-dp-Ziele, Ein-Screen-Modus |
| HLS/DASH-Tempo | Seal: aria2c opt-in | `concurrent_fragment_downloads=4` ab Werk, 3 Worker, SSE-Live-Fortschritt |

## Die sechs Phasen (je 1 Commit)

1. **UX-Redesign Web-Layer** — Ein-Screen-Modus (Link → „Herunterladen"),
   Smart Mode (media_kind/quality/theme serverseitig gemerkt), „Meine
   Downloads" mit großen Ansehen/Teilen-Buttons, Hell+Dunkel nach System,
   Splash <0,5 s ohne Chime, Google Fonts raus (per Test fixiert),
   Free-Limit-Texte auf `{limit}`/`{hours}`-Platzhalter (Drift-Test).
2. **Share-Target + Zwischenablage** — `ACTION_SEND`-Intent-Filter +
   `singleTask`, race-sichere Übergabe (warm push / kalt pull über die
   Bridge), Clipboard-Vorschlags-Chip (einmal pro URL, nie nervend),
   `textZoom` folgt der System-Schriftgröße. CI: `share_intent_test.sh`.
3. **Zuverlässigkeits-Kern** — `errors.py`-Taxonomie steuert Retries
   (nicht-retrybare Klassen scheitern sofort ehrlich), Kill-Recovery
   (`recover_stale_in_progress`), In-Place-Retry (`/api/queue/<id>/retry`,
   gleiche Job-ID ⇒ Resume), Range-Resume im Direct-Download, Stall-
   Erkennung überall, ffmpeg/direct respektieren Abbrechen, 7-Tage-Janitor
   für Partials. CI: `kill_resilience_test.sh` (force-stop mitten im
   Download → Job vollendet sich selbst).
4. **Engine-Self-Update** — `engine_update.py`: yt-dlp-Wheel von PyPI
   (SHA-256-verifiziert, kein Downgrade, Pfad-Traversal-Schutz, stiller
   Fallback auf gebündelte Version), Hot-Swap nur bei 0 aktiven Downloads,
   sonst ab nächstem Start; `/api/engine` + Transparenz-Zeile in den
   Einstellungen. Owner-genehmigt (Runtime-Code-Nachladen).
5. **Foreground-Service + Benachrichtigungen** — `DownloadService`
   (dataSync), Fortschritts- und Fertig-Notifications (Tap öffnet Datei),
   `POST_NOTIFICATIONS` kontextuell beim ersten Download, Doppelstart-Fix
   (Errno-98-Incident). Berechtigungen owner-genehmigt: siehe
   `ANDROID_PERMISSIONS_2026-07-07.md`. CI: `background_survival_test.sh`.
6. **Speed-Feinschliff** — SSE (`/api/events`) statt 1,5-s-Polling mit
   automatischem Fallback, gestreamtes File-Serving mit HTTP-Range (206,
   kein Ganze-Datei-Puffern mehr), SAF-Export ersetzt MediaStore-Publish
   statt ihn zu doppeln (max. 1 Extra-Kopie).

## Bewusst NICHT gebaut

- **Kein In-App-Browser/Suche** (Snaptube-Modell): rechtliche Fläche,
  Play-Protect-Risiko, Scope.
- **Kein aria2c-Cross-Compile**: `concurrent_fragments` deckt den Gewinn;
  nur neu bewerten, wenn Benchmarks dagegen sprechen.
- **Kein `ACTION_VIEW`-Filter**: „Öffnen mit"-Rauschen bei jedem Web-Link
  ist genau die Verwirrung, die wir vermeiden wollen.

## Verifikation

- 187 pytest-Tests grün (Sandbox, ohne die zwei bekannten Tkinter-Dateien).
- Playwright-Screenshots: hell/dunkel, de/en, 200 % Schriftgröße (kein
  horizontaler Überlauf), Settings inkl. Engine-Zeile; SSE verbindet ohne
  JS-Fehler.
- Android nur über CI verifizierbar: `android-build.yml` fährt jetzt
  Smoke → ffmpeg → Download-Pipeline (+`/api/engine`) → Share-Intent →
  Background-Survival → Kill-Resilienz im Emulator.
- Offen für den Owner am echten Gerät: Notifications-Optik, Share-Sheet-
  Gefühl, Hersteller-Battery-Killer (Emulator kann das nicht abbilden),
  MediaStore-Publish-Bestätigung.
