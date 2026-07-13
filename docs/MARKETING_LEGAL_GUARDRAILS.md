# Marketing-Rechts-Leitplanken — Kunden gewinnen UND rechtssicher bleiben

Datum: 2026-07-13. Beantwortet die Kernfrage: *„Je deutlicher wir ‚nur was dir gehört'
sagen, desto sicherer — aber desto weniger Kunden. Wie geht beides?"*

## Die Auflösung des scheinbaren Widerspruchs

Der Denkfehler ist die Annahme, man müsse den attraktiven (oft rechtswidrigen) Use-Case
**bewerben**, um ihn zu verkaufen. Das Gegenteil stimmt:

> **Du bewirbst die Fähigkeit und den legalen Nutzen — nie den rechtswidrigen Use-Case.
> Wer die App zum Rippen nutzen will, versteht ohnehin sofort, dass sie das kann. Du musst
> (und darfst) es nicht aussprechen.**

Das ist kein Kompromiss, sondern **exakt das Geschäftsmodell aller erfolgreichen
Anbieter**. Das ausgesprochene Verbrechen in der Werbung bringt keine zusätzlichen Kunden —
es bringt nur die Haftung (Teilnehmer-/Störerhaftung, Abmahnung) und die Store-Sperre.

### Warum das juristisch der ganze Hebel ist
Ein neutrales Dual-Use-Werkzeug ist legal bereitzustellen (§ 95a greift nicht, solange kein
DRM umgangen wird — bei uns codeseitig verifiziert, siehe `security/DRM_CIRCUMVENTION_AUDIT.md`).
Das Werkzeug wird erst dann zum Rechtsproblem, wenn **du** die rechtswidrige Nutzung
**anpreist/anleitest** — dann haftest du für die Förderung. Die Fähigkeit zu zeigen ist
erlaubt; zum Missbrauch aufzufordern nicht.

## Wettbewerbs-Benchmark (so machen es die Erfolgreichen)

**4K Video Downloader** (kommerziell verkauft, Millionen Nutzer) bewirbt:
- **Fähigkeit + Technik:** „Link einfügen, Auflösung/Format wählen — 4K/8K, MP4/MKV/MP3".
- **Legalen Content-Pool:** empfiehlt ausdrücklich **Creative-Commons**-Inhalte.
- **Disclaimer:** „Bitte Erlaubnis des Rechteinhabers einholen … Herunterladen
  urheberrechtlich geschützter Inhalte ohne Erlaubnis ist untersagt."

Was sie **nicht** sagen: „YouTube werbefrei rippen", „ohne Abo schauen", „lade alles".
Genau diese Disziplin hält sie seit Jahren im Geschäft und in den Stores.

## Was wir verkaufen dürfen (attraktiv UND legal)

Diese Value Props sind massentauglich und 100 % rechtssicher — sie reichen, um Kunden zu
gewinnen:

1. **Offline-Zugriff auf Inhalte, für die du berechtigt bist** — eigene Uploads,
   Creative-Commons, Public Domain, Podcasts mit Download-Erlaubnis, eigene Cloud, gekaufte/
   lizenzierte Medien. „Im Flug, im Zug, im Funkloch — trotzdem da." (Ohne zu sagen *welche*
   fremden Inhalte.)
2. **Format & Flexibilität** — Audio als MP3 extrahieren, Qualität bis 4K, ein Feld für
   Link/Playlist. (4Ks ganzer Pitch.)
3. **Creator-Self-Service** — Creator sichern/reposten ihre **eigenen** Inhalte
   plattformübergreifend. Großes, zahlungskräftiges, **sicherstes** Segment.
4. **Privatsphäre/On-Device** — läuft lokal, kein Konto, keine Werbung *in der App*, kein
   Tracking. Alles wahr, alles legal, echtes Differenzierungsmerkmal.
5. **Archiv & Bildung** — CC-/Bildungs-/Behörden-Inhalte für Studium/Offline sichern.
6. **Die neutrale Fähigkeit, schlicht benannt:** „Video, Audio & Bilder von einem Link
   speichern." Die Kraft ist selbsterklärend — mehr braucht es nicht.

## Was wir NIE sagen dürfen (die Induzierungs-Linie)

- Geschützte Plattformen als Download-Ziel benennen/zeigen (YouTube, Netflix, Spotify,
  TikTok, Insta …) — außer als *nominativer Negativ-Hinweis* („DRM-Dienste funktionieren
  nicht").
- „Werbung überspringen", „ohne Abo schauen", „ohne zu bezahlen", „rip", „lädt alles".
- Fremde Thumbnails/Logos/Markenfarben als unsere Bildsprache (tun wir nicht — nur eigene
  Screenshots).
- Alles, was Download ohne Rechte normalisiert/anleitet.

## Konkret zu ändern (aus dem Materialien-Audit 2026-07-13)

Bereits im Repo korrigiert (Quellen; Re-Render der Bilder nötig, s. u.):
- ✅ **„YouTube, Insta & Co." → „jeder App / any app"** in Deck-Slide 3 (`creator_tools/kit/specs.py`)
  und A4-Flyer (`creator_tools/templates/flyer/flyer-a4-recruitment.html`). *Höchstes Risiko —
  Markenname in verteilter Werbegrafik.*
- ✅ **„von jeder Seite / any site" → „fast jeder / almost any"** in der Play-Kurzbeschreibung
  (`store_assets/README.md`) und **„any video" → „almost any video"** in `f5_desc`
  (`pro/website/i18n/en.json`, `video_downloader/web/static/i18n/en.json`). Konsistent mit der
  eigenen Regel in `INFLUENCER_COPY_LIBRARY.md`.
- ✅ **„Rip" → „Extract"** in `docs/INFLUENCER_COPY_LIBRARY.md`.

Noch offen (Empfehlung, bewusst nicht automatisch geändert):
- ⚠️ **Lokalisierte `f5_desc` in den übrigen ~50 `i18n/*.json`** auf „fast jeder/almost any"
  angleichen — echte Übersetzungsaufgabe, sollte durch eine Lokalisierungsrunde laufen.
- ◐ **„Offline-Hack / alles offline schauen"** (`docs/INFLUENCER_VIDEO_SCRIPTS.md:223`) — Ton
  überdenken; ist durch „Nur mit Erlaubnis laden" on-screen abgemildert, aber grenzwertig.
- ◐ **Netflix/Spotify-Markennamen** an hochsichtbaren öffentlichen Stellen (Onepager/Flyer-
  Footer, `f1_desc`) optional zu „DRM-geschützte Streaming-Dienste" ohne Marke straffen;
  in internen Partnerdocs unkritisch.

## Der gute Bestand (nicht anfassen)

Das Material ist überdurchschnittlich sorgfältig: einzige Faktenquelle mit `honest_limits`
+ `rights_note` (`product_facts.json`), explizite Verbotsliste in
`INFLUENCER_COPY_LIBRARY.md:1132-1166` (u. a. „lädt alles", „umgeht Kopierschutz",
DRM-Versprechen verboten), Rechte-Hinweis in jeder Publikation, Werbe-/Affiliate-Offenlegung,
**100 % eigene Screenshots als Bildsprache** (keine fremden Thumbnails), DRM-Verzicht als
bewusstes Design dargestellt.

## Ehrliche Grenze

Diese Disziplin **senkt** das Play-/Abmahn-Risiko deutlich, **eliminiert** es aber nicht:
Google darf einen General-Downloader trotzdem streng bewerten. Deshalb bleiben Sideload-
Kanal als Standbein und ein anwaltliches Gutachten vor dem großen Push die Absicherung
(siehe `docs/PLAY_STORE_READINESS.md`, `docs/EXTERNAL_ENGAGEMENTS.md`).
