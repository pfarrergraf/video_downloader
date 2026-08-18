# DownloadThat — Arbeitsplan & Aufgaben-Board (KI-kollaborierbar)

Dieses Dokument ist das **gemeinsame Aufgaben-Board** für alle KIs (und Menschen), die an
DownloadThat weiterarbeiten. Es liegt auf `master`, damit der Stand jederzeit auf GitHub
sichtbar ist.

> **Parallele Agenten:** Wenn mehrere KIs gleichzeitig arbeiten, gilt zusätzlich
> `docs/AGENT_COORDINATION.md` (Live-Absprache, wer gerade was macht + Kollisionsregeln).
> Dort zuerst claimen, dann hier abhaken.

## So arbeitest du mit diesem Board (Protokoll — bitte einhalten)

Für **jede** Aufgabe, die du übernimmst:

1. **Übernehmen:** Trage dich unter der Aufgabe im „Log" ein, bevor du beginnst — Datum,
   wer du bist (z. B. „Claude/opus, 2026-07-14"), und `Status: in Arbeit`. So sieht die
   nächste KI, dass die Aufgabe belegt ist (kein Doppel-Aufwand).
2. **Umsetzen:** Arbeite auf der Entwicklungs-Branch `claude/downloadthat-standards-audit-7jpshq`
   (oder einer neuen Feature-Branch) und **halte `master` aktuell** (Fast-Forward-Merge +
   Push), damit die Dateien auf GitHub im Master sichtbar sind.
3. **Abhaken:** Setze die Checkbox der Aufgabe auf `[x]` und ergänze im Log
   `Status: erledigt` + **1–3 Zeilen, was du konkret gemacht hast** (Dateien/Kernänderung).
4. **Grün halten:** Vor dem Merge Tests laufen lassen (siehe Konventionen).

Neue Aufgaben unten anhängen, gleiche Struktur (Checkbox + Log).

## Konventionen (wichtige Leitplanken — nicht verletzen)

- Produktfakten aus aktiver App-, Play- und Website-Konfiguration ableiten; das
  frühere Creator-/Affiliate-Kit wurde vollständig stillgelegt.
- **DRM-Invariante:** kein DRM/TPM umgehen — `allow_unplayable_formats` bleibt aus, keine
  Decrypt-Tools. Abgesichert durch `tests/test_no_drm_circumvention.py` +
  `security/DRM_CIRCUMVENTION_AUDIT.md`.
- **Marketing-Leitplanken:** `docs/MARKETING_LEGAL_GUARDRAILS.md` — Fähigkeit + legalen
  Nutzen bewerben, nie den rechtswidrigen Use-Case; keine geschützten Plattformen als
  Download-Ziel benennen.
- **Termux/Android:** keine kompilierten/Rust-Deps im App-Pfad; Web-Server bleibt
  stdlib-only (siehe `CLAUDE.md`).
- **Tests vor Merge:**
  `uv run pytest tests/ --ignore=tests/test_cli_compat.py --ignore=tests/test_easy_ui.py`
  und im Web-Backend `cd pro/website && npm test && npm run check`.

---

## Aufgaben-Board

### T1 — Rechtliche Deep-Dive-Unterseite + FAQ-Verlinkung
- [x] `rechtliches.html` (DE, Original) + `rechtliches.en.html` (EN): tiefergehende
  Erläuterung der Rechtslage (Creative Commons, Public Domain, eigene Inhalte, Lizenzen,
  was erlaubt/nicht erlaubt ist, DRM-Verzicht, Verantwortung des Nutzers, YouTube/Play-Bezug)
  — eigenständig formuliert, **nicht** von Dritten kopiert. Hülle/Style wie `datenschutz.html`
  (self-contained `<style>`, `legal-lang.js` mit `data-doc="rechtliches"`).
- [x] FAQ-Antwort „Ist das legal?" auf der Startseite (`index.html`) um einen
  **Hyperlink** zur Unterseite ergänzen (eigenes `<a>`-Element, da i18n `textContent`
  setzt; Link locale-abhängig via `data-i18n-attr="href:…"`).
- [x] i18n-Keys `website.faq.q5_more` (+ `q5_more_href`) in allen Locales beider
  i18n-Verzeichnisse (Key-Parität wird von `tests/test_i18n.py` erzwungen).

**Log T1:**
- 2026-07-14 — Claude/opus — **erledigt.** Neu: `pro/website/rechtliches.html` (DE) +
  `rechtliches.en.html` (EN), self-contained im datenschutz-Stil, mit `legal-lang.js`
  (`data-doc="rechtliches"`); Inhalt: CC-Lizenzbausteine, Public Domain, eigene Inhalte,
  Download-Erlaubnis, DRM/§ 95a, Plattform-ToS, Nutzerverantwortung. FAQ-Antwort q5 in
  `index.html` neu formuliert + „Mehr dazu"-Link (`<a data-i18n data-i18n-attr="href:…">`,
  locale-abhängig: DE→`rechtliches.html`, sonst→`rechtliches.en.html`). Keys `q5_more`/
  `q5_more_href` + neuer `q5_body`-Text in en/de gesetzt; Keys per Skript in alle 100
  i18n-Dateien (Website + App) eingefügt (Round-Trip formattreu). Verifiziert: alle Seiten
  liefern 200, HTML parst, `test_i18n.py` 7/7, JS 18/18, Python 278/278. Offen bleibt die
  Übersetzung der Unterseite selbst in weitere Sprachen → T2.

### T2 — `rechtliches.*` in weitere Locales übersetzen
- [x] Analog zu `datenschutz.*.html` die Rechtsseite in weitere Sprachen übersetzen
  (mind. die 16, die bei `datenschutz` existieren). Dateien: `rechtliches.<lang>.html`.
  Der Sprachumschalter (`legal-lang.js`) listet bereits alle Sprachen; fehlende Dateien
  führen zu 404 (bekanntes, bestehendes Verhalten).

**Log T2:**
- 2026-07-14 — Claude/opus — **erledigt.** 13 neue `rechtliches.<lang>.html` erstellt —
  genau die Sprachen mit vorhandener `datenschutz.<lang>.html` (cs, da, el, es, fi, fr, it,
  nl, no, pl, pt, ro, sv). Gleiche self-contained Hülle/Style wie das DE-Original (Style-Block
  identisch), `legal-lang.js data-doc="rechtliches"`, Footer verlinkt lokalisierte Geschwister
  (`impressum/datenschutz/agb.<lang>.html`), Register je Sprache wie beim `datenschutz`-Pendant
  (cs/el/fr/pt formell, Rest informell). Inhalt sinngemäß eigenständig übersetzt (CC-Bausteine,
  Public Domain, DRM/Umgehungsverbot mit EU-Bezug Art. 6 RL 2001/29/EG, Plattform-ToS,
  Nutzerverantwortung) — nicht von Dritten kopiert. Validiert: HTML wohlgeformt, `<html lang>`
  korrekt, 1×h1/6×h2/13×li je Datei, Links erhalten. Kein Zugriff auf i18n/*.json. Damit
  liefert der Sprachumschalter für diese 13 Sprachen keine 404 mehr; verbleibende Sprachen der
  `LEGAL_LANGUAGES`-Liste (ohne `datenschutz`-Pendant) bleiben bewusst offen.

### T3 — Public-Copy ohne pauschale Website-Support-Claims
- [x] Pauschale Reichweitenformulierungen vollständig aus beiden i18n-Spiegeln
  entfernt. Maßgeblich ist `security/PUBLIC_CLAIMS_POLICY.md`; eine bloße
  Relativierung auf eine große Mehrheit ist ausdrücklich nicht mehr zulässig.

**Log T3:**
- (offen)

### T4 — „Offline-Hack"-Ton prüfen
- [x] Historische Influencer-Skripte und Generatoren aus dem aktiven Arbeitsstand entfernt.

**Log T4:**
- 2026-07-14 — Claude/opus — **erledigt.** Skript 5 („Offline in den Urlaub") entschärft:
  Overlay `Offline-Hack` → `Offline dabei`; „ich kann trotzdem alles schauen" →
  „meine gespeicherten Videos laufen trotzdem" (DE) bzw. „my saved videos still play" (EN);
  EN-Overlay `Offline` ergänzt. Fokus jetzt auf eigenem/gespeichertem Content statt auf
  „alles schauen" — entspricht der Verbotsliste in `MARKETING_LEGAL_GUARDRAILS.md` (kein
  „ohne Abo schauen"/„lädt alles"). Rest des Skripts (Rechte-Hinweis on-screen) unverändert.

### T5 — Retention-Cleanup automatisch triggern
- [x] `POST /api/admin/retention-cleanup` regelmäßig auslösen (z. B. GitHub-Actions-Cron
  gegen den Endpoint mit Admin-Session), da Cloudflare Pages Functions keinen Cron haben.

**Log T5:**
- 2026-07-14 — GPT-5.6 — **erledigt** (siehe „Abschluss-Ergänzung 2026-07-14" unten):
  täglicher GitHub-Actions-Cron mit manuellem Trigger, rotierbarer Bearer-Token plus
  bestehender Admin-Session als Authentifizierung, Secret-Sync im Deploy-Workflow.
  Checkbox oben war stehen geblieben, obwohl die Aufgabe bereits erledigt war —
  jetzt nachgezogen.

### T6 — Externe Beauftragungen (Owner-Aufgabe, hier nur getrackt)
- [ ] Anwaltliches Gutachten Urheberrecht/DRM/YouTube-ToS **vor** dem großen Marketing-Push
  (siehe `docs/EXTERNAL_ENGAGEMENTS.md`). Später: Pentest, DSGVO-Kurzprüfung, Marke.

**Log T6:**
- (offen — Entscheidung des Repository-Inhabers)

---

## Änderungs-Historie
- 2026-07-14 — Board angelegt (Claude/opus). Enthält die offenen Punkte aus dem
  Standards-/Marketing-Audit; T1 wird direkt im Anschluss umgesetzt.
- 2026-07-14 — Frühere T3-Formulierung verworfen: relativierte pauschale Claims
  waren weiterhin zu weit und wurden durch die verbindliche Public-Copy-Policy
  ersetzt.

## Abschluss-Ergänzung 2026-07-14 (append-only)

- [x] **T3 — endgültig erledigt:** `hero`, Feature-Texte, App-Taglines und Store-Copy
  beider i18n-Spiegel auf konkrete, rechtebezogene Formulierungen umgestellt;
  repositoryweiter CI-Guard verhindert die Wiedereinführung.
- [x] **T5 — erledigt (GPT-5.6):** täglicher GitHub-Actions-Cron mit manuellem Trigger,
  rotierbarer Bearer-Token plus bestehender Admin-Session als Authentifizierung und
  Deployment-Synchronisierung ergänzt. Gate: 263 Python-Tests, 21 Node-Tests, JS-Check grün.

## T7 — Google-Play-first-Vertrieb und autonome Abrechnung

- [x] Android-Flavors `playRelease` und `directRelease` mit gemeinsamer Paket-ID,
  Signatur und Versionslogik; Play Billing nur im Play-Flavor.
- [x] Serverseitige Kaufprüfung, idempotente Lizenzzuordnung, RTDN, Widerruf und
  Reconciliation einschließlich D1-Migrationen und Tests.
- [x] Website Play-first mit direkter APK als sekundärem Weg; aktive Stripe- und
  Affiliate-Verkaufsflächen sicher stilllegen.
- [x] Reproduzierbares Google-Play-Finanzarchiv mit Hashmanifest, `age`-Verschlüsselung,
  zehnjähriger GCS-Aufbewahrung und lokalem PowerShell-Spiegel.
- [x] Release-/Security-Gates, Store-Unterlagen und kompakte Owner-Checkliste erstellen.

**Log T7:**
- 2026-07-14 — Codex — **in Arbeit** auf `agent/codex/google-play-first`; externe
  Play-Console-, Bank-, Identitäts- und Vertragsschritte bleiben ausdrücklich Owner-Gates.
- 2026-07-14 — Codex — **Code abgeschlossen, Produktion noch gesperrt.** Python-Gate:
  258 bestanden, 1 übersprungen; Node: 13 bestanden; Android-Variantenscan: 10/10.
  Ein echter AAB-/APK-Build, 16-KiB-Binärprüfung, License-Tester-Kauf/Restore/Refund,
  RTDN, GCS-Restore und Secret-Widerruf bleiben externe Produktions-Gates gemäß
  `GOOGLE_PLAY_OWNER_CHECKLIST.md`.

## T21 — Zuverlässige Playlist-Erkennung und -Downloads

- [x] Playlist-URLs serverseitig erkennen und kanonisch normalisieren.
- [x] Web- und Easy-UI automatisch in den Playlistmodus schalten.
- [x] Einzelne nicht verfügbare Playlist-Einträge überspringen, ohne den
  gesamten Download abzubrechen.
- [x] Die für aktuelle YouTube-Extraktion erforderliche EJS-/JavaScript-
  Laufzeit korrekt anbinden und gemeinsam mit dem Enginepfad absichern.
- [x] Regressionstests sowie reale, nicht speichernde Playlist-Proben für die
  gemeldete Beispielplaylist und wechselnde Chartlisten ausführen.
- [x] Täglichen und manuell startbaren, nicht-speichernden Playlist-Canary in
  `.github/workflows/playlist-canary.yml` bereitstellen.

**Log T21:**
- 2026-07-24 — Codex — **in Arbeit** auf
  `agent/codex/playlist-reliability`.
- 2026-07-24 — Codex — **erledigt**. Die gemeldete 21er-Playlist wurde
  vollständig und ohne Mediendownload extrahiert; Deutschland-/USA-Chartlisten
  wurden stichprobenartig geprüft. Alle 302 Python-Tests, 22 Website-Tests,
  JavaScript-Syntax, Ruff, 16 Distributionsprüfungen sowie ein echter
  arm64-v8a-QuickJS-Crossbuild mit 16-KiB-Ausrichtung sind grün.
- 2026-07-24 — Codex — Der Canary wurde lokal mit zehn Metadaten-Einträgen
  erfolgreich ausgeführt; er nutzt `extract_flat`, `skip_download` und Node/EJS
  und erzeugt keine Mediendateien.

## T22 — Tester-Feedback: Erststart-Hilfe, Support/Bewertung, Billing-Fehlertexte

- [x] Die zwei Tester-PDF-Berichte gegen Code und Play-Owner-Gates prüfen und
  eine belastbare Einschätzung dokumentieren.
- [x] Natives Erststart-Tutorial einmalig automatisch zeigen (Android, nach
  Terms-Akzeptanz, ohne den Share-Intent-Picker zu verdecken).
- [x] Support-Mail-Link und "Bei Google Play bewerten"-Button in den
  Einstellungen ergänzen.
- [x] Rohe Play-Billing-Fehlercodes durch lokalisierte, verständliche
  Toast-Texte ersetzen.

**Log T22:**
- 2026-08-03 — Codex — **erledigt.** Bewertung in
  `docs/TESTER_REPORT_ASSESSMENT_2026-08-03.md`. Erststart-Hilfe,
  Support-/Bewertungswege und lokalisierte Billing-Rückmeldungen implementiert.
  303 Python-Tests, 24 Website-Tests, JS-Syntax, Ruff, Public-Claims-Guard und
  ein mobiler Browserdurchlauf grün. Play-Console-Produktaktivierung und die
  reale Kauf-Lifecycle-Prüfung bleiben Owner-Gates.
- 2026-08-06 — Claude — Beim Prüfen des Release-APKs festgestellt: T22 war
  laut `AGENT_COORDINATION.md` erledigt, aber nie eingecheckt. Unverändert
  nachcommittet (`agent/claude/help-tutorial-fixes`, FF nach `master`).

### T22-Nacharbeit — Tutorial-Bugfix + Icon-Politur (T24)
- [x] Bug: Ein Tap auf die Video/Audio-Buttons im Tutorial fror den Auto-Loop
  dauerhaft ein ("Animation hängt auf Schritt 4").
- [x] Schließen + erneutes Öffnen des Tutorials startet wieder zuverlässig bei
  Szene 1.
- [x] ✕- und 📖-Icons im Tutorial-Overlay in ihrem Kreis zentriert.
- [x] 📖-Icon (Textanleitung) pulsiert durchgehend, solange das Tutorial offen
  ist; ❓ im Header pulsiert einmalig nach dem automatischen Erststart-Tutorial.

**Log T24:**
- 2026-08-06 — Claude — **erledigt** auf `agent/claude/help-tutorial-fixes`.
  `[data-pc3-next]` ist im App-Tutorial jetzt `pointer-events: none` statt
  anklickbar+loop-tötend (diese Controls sind nur auf der Marketing-Website
  echt interaktiv). `openHelp()`/`stopHelpAnimation()`/`restartHelpAnimation()`
  garantieren Neustart bei jedem Öffnen. Icon-Zentrierung wie `.icon-btn`
  (flex). 6 neue Regressionstests in `tests/test_help_popup.py` (16/16 grün),
  volles Python-Gate 309/309 grün.

## T23 — Play-Preistext-Aktualisierung (12-EUR-Claim → lokaler Preis)

- [x] Nach Aktivierung des Play-Produkts `pro` alle aktiven Website-,
  Listing- und Owner-Dokumenttexte von der alten 12-EUR-Angabe auf die
  lokale Play-Preislogik umstellen.

**Log T23:**
- 2026-08-03 — Codex — **erledigt.** Aktives Play-Produkt `pro` mit 173
  Ländern/Regionen bestätigt; Website-Locale (beide i18n-Spiegel, alle 50
  Dateien je Baum), Android-Downloadseite und aktive Play-/Marketing-Dokumente
  verwenden nun lokale Google-Play-Preise (Deutschland aktuell 11,99 EUR
  Endpreis). 20 gezielte Python-Tests, 24 Website-Tests, JS-Syntax, 100
  JSON-Locale-Dateien, Public-Claims-Guard, `git diff --check`. Historische
  Stripe-Unterlagen (`pro/README.md`, `docs/ANDROID_APP_PLAN.md`,
  `docs/product_cinema_v3_homepage_integration_audit.md`) bewusst nicht
  geändert — dokumentieren das stillgelegte alte Preismodell, keine aktiven
  Claims.
- 2026-08-06 — Claude — Wie T22: laut Log erledigt, aber nie eingecheckt.
  Unverändert nachcommittet (`agent/claude/help-tutorial-fixes`, FF nach
  `master`). Stichprobe nach "12 €"/"12 EUR"-Resten über den aktiven Code
  durchgeführt — keine gefunden außer den oben genannten, bewusst
  unveränderten historischen Stripe-Dokumenten.

## Notification-Fix — Download-Benachrichtigung bei leerer Warteschlange

- [x] Die laufende Vordergrund-Benachrichtigung sofort entfernen, sobald die
  Warteschlange leer ist, statt bis zu 30s sichtbar zu bleiben.

**Log:**
- 2026-08-06 — Codex — **erledigt.** `DownloadService.kt` verlässt den
  Vordergrund und entfernt die Benachrichtigung beim ersten leeren
  Queue-Snapshot; die Abschlussmeldung bleibt erhalten. 10 gezielte
  Python-Tests grün; lokaler Kotlin-Compile nicht verfügbar (kein Gradle
  Wrapper/CLI in diesem Checkout).
- 2026-08-06 — Claude — Wie T22/T23: laut Log erledigt, aber nie eingecheckt.
  Unverändert nachcommittet (`agent/claude/help-tutorial-fixes`, FF nach
  `master`).

## Offen — Owner-Gates (nicht code-seitig lösbar)

Aus `docs/TESTER_REPORT_ASSESSMENT_2026-08-03.md` und
`docs/GOOGLE_PLAY_OWNER_CHECKLIST.md`, für den Repository-Inhaber:

- **Play-Produkt `pro` real verifizieren:** License-Tester-Kauf, Restore nach
  Neuinstallation, Refund/Void über RTDN, Reconciliation — mit Beleg
  (Build/Version, Konto-Rolle, Ergebnis, Zeitstempel, Screenshots ohne
  personenbezogene/Zahlungsdaten).
- **Eigene Produktionsdomain:** `downloadthat.app`/`www` als Custom Domain im
  Pages-Projekt verbinden, DNSSEC/SSL prüfen, danach erst
  `CANONICAL_REDIRECT_ENABLED=true` setzen.
- **Play-Konto/Payments:** Identität, Organisation/Privatstatus,
  Bankkonto/Steuerprofil, Play-Verträge.
- **RTDN/Secrets:** Pub/Sub-Thema + Push-Service-Account verbinden,
  GitHub/Cloudflare-Secrets aus `docs/GOOGLE_PLAY_OPERATIONS.md` setzen,
  Rate-Limiting für `POST /api/play/purchases/verify` aktivieren.
- **Data Safety / Zielgruppe / Content Rating / Werbeangaben** in Play Console
  anhand der tatsächlichen Datenflüsse absenden.
- **Rechtliche Prüfung:** Datenschutz-/AGB-Texte anwaltlich prüfen lassen —
  keine automatische Rechtsfreigabe aus Code/Doku ableiten (siehe auch T6).
- **Store-Screenshots erneuern:** `store_assets/screenshot_*.png` sind laut
  `TESTER_REPORT_ASSESSMENT` "raw UI captures without benefit captions" —
  neue, beschriftete, lokalisierte Screenshots vom Release-Build erstellen und
  in Play Console verifizieren. Zwei unversionierte Kandidaten-Assets liegen
  bereits in `store_assets/` (`icon-pro-1024.png`, `icon-pro-badge-1024.png`,
  seit 2026-08-03), aber ohne README-Eintrag oder Verwendung irgendwo — vor
  Verwendung mit dem Owner abstimmen.

## Lokaler Developer Mode

- [x] Sieben Klicks auf den Versionsbereich in den Einstellungen blenden lokale,
  begrenzte Transportdiagnosen ein. Sie verändern niemals Lizenzstatus,
  Tageslimit oder Pro-Berechtigung.
- [x] Die Fragmentzahl ist serverseitig auf 1–8 begrenzt; das Engine-Autoupdate
  kann lokal ein- und ausgeschaltet werden.
- [x] Nightly ist die Standardquelle. Ein gegebenenfalls späterer
  Stable-Rollback bleibt ein eigenes Arbeitspaket und wird nicht durch den
  lokalen Developer Mode oder eine versteckte Freischaltung aktiviert.

**Log:**
- 2026-08-18 — Codex — umgesetzt in `video_downloader/web/static/index.html`
  und `video_downloader/web/server.py`; 347 Python-Tests bestanden. Lokaler
  Windows-Web-Build erfolgreich, Android-Build lokal nicht möglich (kein
  Gradle/Android-SDK in dieser Umgebung).

## Nightly-Engine-Notfallrelease

- [x] Nightly wird für den nächsten Release und den Runtime-Updater zur
  Standardquelle, weil yt-dlp Stable 2026.07.04 bei der reproduzierbaren
  YouTube-Probe HTTP 403 liefert, die Nightly dagegen erfolgreich lädt.

**Log:**

- 2026-08-18 — Codex — Der Updater ermittelt Nightly-Releases korrekt aus der
  PyPI-Release-Liste (nicht aus der stets stabilen `info.version`), vergleicht
  die kanonische Modulversion robust und aktualisiert eine echte
  Stable-Laufzeit erfolgreich. Windows bündelt zusätzlich verifiziertes
  QuickJS 0.15.1; der lokale Web-Build und die Python-Test-Suite sind grün.
