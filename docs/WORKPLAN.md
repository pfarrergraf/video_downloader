# DownloadThat — Arbeitsplan & Aufgaben-Board (KI-kollaborierbar)

Dieses Dokument ist das **gemeinsame Aufgaben-Board** für alle KIs (und Menschen), die an
DownloadThat weiterarbeiten. Es liegt auf `master`, damit der Stand jederzeit auf GitHub
sichtbar ist.

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

- **Fakten nur in `creator_tools/config/product_facts.json`** ändern (einzige Quelle;
  `tests/test_creator_tools.py` erzwingt Konsistenz): free = 3/Tag, Pro = 12 € einmalig.
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
- [ ] Analog zu `datenschutz.*.html` die Rechtsseite in weitere Sprachen übersetzen
  (mind. die 16, die bei `datenschutz` existieren). Dateien: `rechtliches.<lang>.html`.
  Der Sprachumschalter (`legal-lang.js`) listet bereits alle Sprachen; fehlende Dateien
  führen zu 404 (bekanntes, bestehendes Verhalten).

**Log T2:**
- (offen)

### T3 — „almost any" konsistent über alle i18n-Locales
- [ ] `f5_desc` (und ähnliche absolute „any"/„jede") in den übrigen ~48
  `pro/website/i18n/*.json` (und dem In-App-Spiegel) auf die „fast jeder/almost any"-Formel
  bringen — EN/DE sind bereits erledigt. Übersetzungsrunde erforderlich.

**Log T3:**
- (offen)

### T4 — „Offline-Hack"-Ton prüfen
- [ ] `docs/INFLUENCER_VIDEO_SCRIPTS.md:223` („alles offline schauen / Offline-Hack")
  tonal entschärfen (bereits durch „Nur mit Erlaubnis laden" abgemildert, aber grenzwertig).

**Log T4:**
- (offen)

### T5 — Retention-Cleanup automatisch triggern
- [ ] `POST /api/admin/retention-cleanup` regelmäßig auslösen (z. B. GitHub-Actions-Cron
  gegen den Endpoint mit Admin-Session), da Cloudflare Pages Functions keinen Cron haben.

**Log T5:**
- (offen)

### T6 — Externe Beauftragungen (Owner-Aufgabe, hier nur getrackt)
- [ ] Anwaltliches Gutachten Urheberrecht/DRM/YouTube-ToS **vor** dem großen Marketing-Push
  (siehe `docs/EXTERNAL_ENGAGEMENTS.md`). Später: Pentest, DSGVO-Kurzprüfung, Marke.

**Log T6:**
- (offen — Entscheidung des Repository-Inhabers)

---

## Änderungs-Historie
- 2026-07-14 — Board angelegt (Claude/opus). Enthält die offenen Punkte aus dem
  Standards-/Marketing-Audit; T1 wird direkt im Anschluss umgesetzt.
