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
