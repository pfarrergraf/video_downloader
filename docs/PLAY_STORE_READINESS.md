# Google Play Readiness — DownloadThat / ClassyDL

Datum: 2026-07-13; Architektur aktualisiert 2026-07-14. Zweck: alles, was vor einer Play-Store-Einreichung stimmen muss,
plus eine ehrliche Risikoeinschätzung für Vertrieb und Skalierung. **Wichtig zuerst:**
Das größte Play-Risiko für diese App ist **nicht** die IT-Sicherheit (die ist nach dem
Audit solide), sondern die **Content-Policy** (Downloader-Apps). Das ist unten der
längste Abschnitt — bitte zuerst lesen.

> **Aktuelle Vertriebsentscheidung:** Google Play ist die einzige Kasse. Die direkte
> APK bleibt sekundärer Free-/Aktivierungsweg. Stripe und Affiliate sind nicht mehr
> Teil der Zielarchitektur. Für verbindliche Data-Safety- und Testangaben gilt
> `PLAY_CONSOLE_INTERNAL_TESTING_PREP.md`.

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
5. Verbindliche Positionierungs-Leitplanken stehen in `security/PUBLIC_CLAIMS_POLICY.md`
   und `security/README.md` („private media utility for content you have the right to").
   Marketing muss diszipliniert dabei bleiben — inkonsistente Werbung ist selbst ein
   Ablehnungsgrund.

---

## 2. Data Safety mapping (muss exakt stimmen) 🟠

Eine falsche Data-Safety-Erklärung kann selbst zum Enforcement-Risiko werden. Korrekte
Zuordnung, hergeleitet aus dem aktuellen Play-Backend
(`pro/website/functions/api/play/`, `_google_play.js`, `licensing.py`):

| Datentyp (Play-Kategorie) | Gesammelt? | Wofür / Wo | Geteilt? |
|---|---|---|---|
| **Device or other IDs** | Ja | Per-Install-`device_id` an Lizenzserver (Ein-Gerät-pro-Plattform-Slot); serverseitig **gehasht** gespeichert | Nein |
| **Email address** | Nein | Weder App noch Lizenz-Backend verlangen ein Nutzerkonto oder eine E-Mail-Adresse | Nein |
| **Purchase history** | Ja (nur Pro) | Purchase-Token, Order-Referenz, Produkt und Status zur Google-Verifikation, Wiederherstellung, Erstattung und Buchhaltung | Google verarbeitet den Kauf; keine Weitergabe an Werbe- oder Datenhändler |
| **App activity / Downloads / URLs** | Nein (bleibt on-device) | Download-/Scrape-Historie nur lokal (SQLite) | Nein |
| **Location, Contacts, Photos, SMS, …** | Nein | — | — |
| **Crash logs / Diagnostics** | Nein | Kein Analytics-/Crash-SDK | Nein |

Weitere Formularantworten:
- **Encrypted in transit:** Ja (HTTPS zum Backend).
- **User can request deletion:** Ja — über den Kontakt in `SECURITY.md`; lokale Daten
  können in der App gelöscht werden. Gesetzlich erforderliche Finanzoriginale und
  Erstattungsnachweise bleiben entsprechend der dokumentierten Aufbewahrung erhalten.
- **Data collected required or optional:** Kaufdaten entstehen nur beim optionalen
  Pro-Kauf; `device_id` ist für die gerätebezogene Lizenzaktivierung funktional nötig.

Konsistenz-Check: Die veröffentlichte Datenschutzerklärung (`datenschutz.*.html`) muss
Google Play, Lizenzprüfung und Finanzaufbewahrung beschreiben und darf Stripe oder
Affiliate nicht mehr als aktive Datenempfänger nennen.

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
- [ ] Signiertes `playRelease`-AAB mit getrenntem Upload-Key erzeugen und lokal gegen
      SHA-256 `5F:BD:61:BC:C8:B2:36:76:E8:E9:CE:33:7C:51:F7:24:34:61:CB:9C:31:C8:19:00:69:32:50:99:35:37:03:CE`
      prüfen; Upload-Key-Reset ist derzeit in der Play Console `pending`.
- [ ] Datenschutz-URL nach Domainaufschaltung öffentlich prüfen:
      `https://downloadthat.app/datenschutz.html`.
- [x] `security.txt` + `SECURITY.md` (Vulnerability-Disclosure — Play/AppDefenceAlliance-freundlich).
- [x] Kein Cleartext-Traffic außer Loopback (`network_security_config.xml`).
- [x] Kein Fremd-Tracking-SDK.
- [ ] **Pre-launch report** in Play Console aktivieren (Google testet das AAB automatisch
      auf Crashes/Sicherheit — kostenlos, unbedingt nutzen).
- [ ] Content-Rating-Fragebogen (erwartet „Everyone/PEGI 3").
- [ ] Data-Safety-Form exakt nach Abschnitt 2 ausfüllen (NICHT „no data").
- [ ] Datenlöschungsweg ohne Nutzerkonto dokumentieren; auf `SECURITY.md`-Kontakt und
      die Ausnahmen für gesetzlich aufzubewahrende Finanzbelege verweisen.
- [ ] Store-Listing-Fakten = `product_facts.json` (3/Tag, 12 € einmalig).

---

## 5. Skalierung & „Angriff/Diskreditierung bei einer Million" 🟢 (weitgehend abgedeckt)

Wenn das Ding groß wird, ist die **internet-exponierte Fläche = das Cloudflare-Backend**
(die On-Device-Server sind Loopback und skalieren nicht als Angriffsfläche).

| Sorge | Status |
|---|---|
| Lizenzschlüssel massenhaft fälschen | Nicht möglich — serverseitige Zufallstoken, DB-Lookup, kein Client-Secret (Red-Team A1). |
| Kaufmeldungen fälschen | Purchase-Token wird serverseitig über die Google Play Developer API geprüft; nur `PURCHASED` schaltet Pro frei. |
| Refund/RTDN manipulieren | RTDN-Push benötigt gültiges Google-OIDC; doppelte Meldungen und Reconciliation sind idempotent. |
| DDoS / Endpoint-Hammering | Cloudflare-Edge-Schutz plus serverseitiges Rate-Limiting; produktive WAF-Regel für `POST /api/play/purchases/verify` bleibt ein Go-live-Gate. |
| DSGVO-Beschwerde (kein Löschweg) | Supportweg ist dokumentiert; lokale Daten sind löschbar, Finanzoriginale folgen der gesetzlichen Aufbewahrung. |
| „Security-Researcher diskreditiert uns" | Öffentliche, dokumentierte, responsive Haltung: `SECURITY.md`, Threat Model, Red-Team-Report, CodeQL/SAST/Dependabot in CI, reproduzierbare Builds. Das ist die beste Anti-Diskreditierungs-Versicherung. |

Verbleibende Skalierungs-To-dos: produktive Cloudflare-WAF-Regel, RTDN/Pub-Sub-
Einrichtung, tägliche Reconciliation und ein realer 100.000-Kauf-Lastlauf vor
Produktion.

---

## 6. Was NUR extern geht — siehe `docs/EXTERNAL_ENGAGEMENTS.md`

Kurz: Rechtsrat (Urheberrecht/DRM/YouTube-ToS) **vor** dem Skalieren, ein einmaliger
externer Pentest (L2), und ggf. eine DSGVO-/DPO-Kurzprüfung. Details, grobe Kosten und
Nutzen in `docs/EXTERNAL_ENGAGEMENTS.md`.
