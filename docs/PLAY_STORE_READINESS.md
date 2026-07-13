# Google Play Readiness — DownloadThat / ClassyDL

Datum: 2026-07-13. Zweck: alles, was vor einer Play-Store-Einreichung stimmen muss,
plus eine ehrliche Risikoeinschätzung für Vertrieb und Skalierung. **Wichtig zuerst:**
Das größte Play-Risiko für diese App ist **nicht** die IT-Sicherheit (die ist nach dem
Audit solide), sondern die **Content-Policy** (Downloader-Apps). Das ist unten der
längste Abschnitt — bitte zuerst lesen.

---

## 1. Content-Policy-Risiko (der eigentliche Play-Killer) 🔴

**Sachlage:** DownloadThat ist ein generischer Media-Downloader (yt-dlp-basiert), der
aus einer sehr großen Zahl von Seiten laden kann — potenziell auch aus
Streaming-Diensten. Google Play verbietet Apps, die **unautorisierten Zugriff auf
urheberrechtlich geschützte Inhalte** ermöglichen, und Google besitzt YouTube; YouTube-
Downloader wurden wiederholt aus Play entfernt. Das trifft **nicht** primär die Technik,
sondern die **Positionierung + das reale Verhalten** der App.

**Was schützt uns (bereits vorhanden / jetzt gesetzt):**
- Die App **umgeht kein DRM/keine Paywalls** — das ist eine härtere Google-Grenze als
  „Downloader allgemein". Muss in Listing + Code-Aussagen konsistent bleiben (ist es).
- Keine namentliche Bewerbung geschützter Plattformen (YouTube/Netflix/Spotify …) im
  Listing, Titel, Screenshots oder Werbung. Der Listing-Entwurf wurde entsprechend
  entschärft (`PLAY_CONSOLE_INTERNAL_TESTING_PREP.md`): Framing auf **„Links, die du
  besitzt oder für die du berechtigt bist"**.
- Klare Nutzerverantwortungs-/Rechte-Klausel im Listing und in den AGB.

**Was das nicht wegzaubert (ehrlich):** Ein general-purpose yt-dlp-Downloader hat ein
**erhöhtes Rest-Risiko**, im Play-Review abgelehnt oder später entfernt zu werden — auch
bei sauberem Framing, weil Google auf tatsächliche Funktion abstellen kann. Das ist eine
**Geschäftsentscheidung**, keine Sache, die sich im Code „lösen" lässt.

**Empfehlung (Handlungsoptionen, nicht von mir entscheidbar):**
1. **Play-Konto heute registrieren ist unkritisch** — Registrierung ≠ Veröffentlichung.
   Erst das Listing/Review ist der Prüfpunkt.
2. **Sideload-Kanal (GitHub Releases) als primären/Fallback-Weg behalten** — er ist
   heute schon das Vertriebsmodell und von der Content-Policy nicht betroffen. Nicht das
   ganze Geschäft allein auf Play aufbauen.
3. **Alternative Stores** mit liberalerer Policy als Ergänzung: F-Droid, Amazon Appstore,
   Samsung Galaxy Store, direkter APK-Download.
4. **Vor dem Skalieren auf „eine Million": Rechtsrat einholen** (Urheberrecht/§ 95a UrhG
   Umgehungsverbot, YouTube-ToS, DSM-Richtlinie) — siehe Abschnitt 6. Das ist die
   wichtigste externe Beauftragung, wichtiger als ein Pentest.
5. Interne Positionierungs-Leitplanken stehen schon in `docs/INFLUENCER_CREATIVE_AUDIT.md`
   und `security/README.md` („private media utility for content you have the right to").
   Marketing muss diszipliniert dabei bleiben — inkonsistente Werbung ist selbst ein
   Ablehnungsgrund.

---

## 2. Data Safety mapping (muss exakt stimmen) 🟠

Eine **falsche** Data-Safety-Erklärung ist einer der häufigsten Play-Enforcement-Gründe.
Der frühere Entwurf („collects no data") war falsch. Korrekte Zuordnung, hergeleitet aus
dem Code/Backend (`pro/website/functions/`, `licensing.py`):

| Datentyp (Play-Kategorie) | Gesammelt? | Wofür / Wo | Geteilt? |
|---|---|---|---|
| **Device or other IDs** | Ja | Per-Install-`device_id` an Lizenzserver (Ein-Gerät-pro-Plattform-Slot); serverseitig **gehasht** gespeichert | Nein |
| **Email address** | Ja (nur bei Pro-Kauf) | Stripe-Checkout → im Lizenzdatensatz gespeichert | An **Stripe** (Zahlungsabwicklung) |
| **Purchase history** | Ja (nur bei Pro-Kauf) | Lizenz-Tier/Status | An **Stripe** |
| **App activity / Downloads / URLs** | Nein (bleibt on-device) | Download-/Scrape-Historie nur lokal (SQLite) | Nein |
| **Location, Contacts, Photos, SMS, …** | Nein | — | — |
| **Crash logs / Diagnostics** | Nein | Kein Analytics-/Crash-SDK | Nein |

Weitere Formularantworten:
- **Encrypted in transit:** Ja (HTTPS zum Backend).
- **User can request deletion:** Ja — E-Mail an den Kontakt in `SECURITY.md`; Erasure via
  `POST /api/admin/gdpr-erase`; on-device via `classydl purge-data`.
- **Data collected required or optional:** Kauf-E-Mail/-ID nur bei optionalem Pro-Kauf;
  `device_id` ist funktional erforderlich für die Lizenzbindung.

Konsistenz-Check: Die veröffentlichte Datenschutzerklärung (`datenschutz.*.html`)
beschreibt Stripe + Lizenzdatenbank bereits — Data-Safety-Form und Policy stimmen damit
überein.

---

## 3. Permissions-Begründung (Play verlangt Rechtfertigung)

| Permission | Begründung |
|---|---|
| `INTERNET` | Downloads / Lizenzvalidierung |
| `FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_DATA_SYNC` | Downloads müssen das Wegwischen/Bildschirm-Aus überleben (DownloadService, `dataSync`) — Standard für Download-Manager |
| `POST_NOTIFICATIONS` | Fortschritts-/Fertig-Benachrichtigung, kontextuell beim ersten Download abgefragt |

Keine `READ/WRITE_*`, Standort-, Kamera-, Kontakt-, `QUERY_ALL_PACKAGES`- oder
`REQUEST_INSTALL_PACKAGES`-Rechte. `allowBackup="false"`. Guardrail in `CLAUDE.md`.
→ Play „Permissions declaration" sollte problemlos sein (keine „sensitive/high-risk"
Permission, kein `MANAGE_EXTERNAL_STORAGE`).

---

## 4. Technische Play-Checkliste

- [x] Minimale, begründete Permissions (s. o.).
- [x] `targetSdk`/`compileSdk` 36 (Play verlangt aktuelles Target-API — erfüllt).
- [x] Signiertes AAB via `android-release.yml` (Upload-Key aus GitHub-Secrets).
- [x] Datenschutz-URL öffentlich: `https://downloadthat.pages.dev/datenschutz.html`.
- [x] `security.txt` + `SECURITY.md` (Vulnerability-Disclosure — Play/AppDefenceAlliance-freundlich).
- [x] Kein Cleartext-Traffic außer Loopback (`network_security_config.xml`).
- [x] Kein Fremd-Tracking-SDK.
- [ ] **Pre-launch report** in Play Console aktivieren (Google testet das AAB automatisch
      auf Crashes/Sicherheit — kostenlos, unbedingt nutzen).
- [ ] Content-Rating-Fragebogen (erwartet „Everyone/PEGI 3").
- [ ] Data-Safety-Form exakt nach Abschnitt 2 ausfüllen (NICHT „no data").
- [ ] Account-/Datenlöschung-Anforderung: Play verlangt für Apps mit Konto/Kaufdaten
      einen dokumentierten Löschweg → auf `SECURITY.md`-Kontakt + `gdpr-erase` verweisen.
- [ ] Store-Listing-Fakten = `product_facts.json` (3/Tag, 12 € einmalig).

---

## 5. Skalierung & „Angriff/Diskreditierung bei einer Million" 🟢 (weitgehend abgedeckt)

Wenn das Ding groß wird, ist die **internet-exponierte Fläche = das Cloudflare-Backend**
(die On-Device-Server sind Loopback und skalieren nicht als Angriffsfläche).

| Sorge | Status |
|---|---|
| Lizenzschlüssel massenhaft fälschen | Nicht möglich — serverseitige Zufallstoken, DB-Lookup, kein Client-Secret (Red-Team A1). |
| Zahlungs-Webhooks fälschen | Nicht möglich — HMAC-SHA256 + Timestamp + constant-time (A10). |
| Finanz-/Provisions-Manipulation (Affiliate) | Append-only Ledger/Audit mit DB-Triggern, Maker-Checker, Integrity-Gate, Race-safe (bestehendes Backend-Audit). |
| DDoS / Endpoint-Hammering | Cloudflare-Edge-DDoS-Schutz + serverseitiges Rate-Limiting; **To-do:** Cloudflare WAF-Regeln/Turnstile auf `validate`/`checkout` prüfen, wenn Volumen steigt. |
| DSGVO-Beschwerde (kein Löschweg) | **Behoben** — `gdpr-erase`/`retention-cleanup` (neu, getestet). |
| „Security-Researcher diskreditiert uns" | Öffentliche, dokumentierte, responsive Haltung: `SECURITY.md`, Threat Model, Red-Team-Report, CodeQL/SAST/Dependabot in CI, reproduzierbare Builds. Das ist die beste Anti-Diskreditierungs-Versicherung. |

Verbleibende Skalierungs-To-dos (klein): Cloudflare-WAF/Turnstile-Review bei Lastanstieg;
`retention-cleanup` regelmäßig triggern (z. B. GitHub-Actions-Cron gegen den Endpoint, da
Pages Functions keinen Cron haben).

---

## 6. Was NUR extern geht — siehe `docs/EXTERNAL_ENGAGEMENTS.md`

Kurz: Rechtsrat (Urheberrecht/DRM/YouTube-ToS) **vor** dem Skalieren, ein einmaliger
externer Pentest (L2), und ggf. eine DSGVO-/DPO-Kurzprüfung. Details, grobe Kosten und
Nutzen in `docs/EXTERNAL_ENGAGEMENTS.md`.
