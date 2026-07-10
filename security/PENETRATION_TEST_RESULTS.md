# Affiliate Program – Penetration Test Results (Internal Assessment)

Diese Ergebnisse stammen aus einer **internen** Code-Review-, Threat-Modeling- und Whitebox-Testprüfung
(kein externer Penetrationstest, siehe `PENETRATION_TEST_PLAN.md` §Scope). Geprüft wurde ausschließlich
statisch (Quellcode, Migrationen, CI-Konfiguration) und über lokale/isolierte Node- bzw. SQLite-basierte
Reproduktionen – **keine** Anfragen gegen Stripe, Cloudflare, Resend oder andere Drittsysteme.

---

## AFF-001 — Stored XSS im Partner-Admin-Dashboard (P1 / High)

- **Komponente:** `pro/website/partner-admin.html` (Zeile mit `render()`), Datenquelle `pro/website/functions/api/admin/overview.js`, Eingabe über `pro/website/functions/api/partner/register.js`
- **CWE:** CWE-79 (Improper Neutralization of Input During Web Page Generation)
- **CVSS 3.1 (geschätzt):** 8.1 (AV:N/AC:L/PR:N/UI:N/S:C/C:N/I:H/A:N) – kein Auth nötig für den Angreifer (Selbstregistrierung), Auswirkung im Kontext des Admin-Opfers hoch (Session-Kontext, Zahlungsfreigaben), keine Vertraulichkeitsverletzung direkt.

**Beschreibung:** `render()` in `partner-admin.html` baut die Partnertabelle per Template-Literal direkt in
`innerHTML` ohne HTML-Escaping: `` `<strong>${a.display_name}</strong> ... ${a.code} · ${a.email}` ``.
`display_name` wird bei der Registrierung (`register.js`) nur längenbegrenzt (`slice(0,100)`), nicht
HTML-escaped. `email` wird per Regex `/^[^\s@]+@[^\s@]+\.[^\s@]+$/` validiert, die u. a. `<`, `>`, `"`
zulässt. Da `/api/admin/overview` **alle** Partner zurückgibt (unabhängig vom Status), reicht eine reine
Selbstregistrierung ohne weitere Freigabe, damit der Payload beim nächsten Laden des Admin-Dashboards im
Browser des Admins ausgeführt wird – im selben Origin, mit dem `dt_partner_session`-Cookie des Admins.

**Reproduktion:**
1. `POST /api/partner/register` mit `display_name = "<img src=x onerror=fetch('/api/admin/payout-prepare',{method:'POST',headers:{'Content-Type':'application/json'},body:'{\"affiliate_id\":\"<eigene-id>\"}'})>"`.
2. E-Mail-Verifizierung durchlaufen (Status wird `active`, ist aber für den Angriff nicht zwingend nötig – `overview.js` liefert alle Status).
3. Admin öffnet `/partner-admin.html` → Payload wird im Adminkontext ausgeführt und kann beliebige `/api/admin/*`-Endpunkte mit der Session des Admins aufrufen.

**Auswirkung:** Vollständige Kompromittierung der Admin-Session-Fähigkeiten (Auszahlung vorbereiten/freigeben/als bezahlt buchen, Reconciliation anstoßen) durch einen nicht privilegierten, selbstregistrierten Partner.

**Wahrscheinlichkeit:** Hoch – keine Vorbedingungen außer öffentlicher Registrierung.

**Evidenz:** `pro/website/partner-admin.html` (Render-Funktion, Zeile mit `document.getElementById('affiliates').innerHTML=...`), `pro/website/functions/api/partner/register.js:29` (`displayName` ohne HTML-Escaping gespeichert).

**Behebung:** HTML-Escaping-Funktion `esc()` ergänzt und auf alle aus der API stammenden Felder angewendet, die per `innerHTML` gerendert werden (`display_name`, `code`, `email`, `id`, `status`, `reconciliation_snapshot_id`, `reasons_json`-Inhalte) in `partner-admin.html`; zusätzlich defensiv `external_reference` und `status` in `partner-dashboard.html` (dort admin-eingegebener Freitext, geringeres Risiko, aber gleiche Baustelle).

**Tests:** `tests/test_affiliate_program.py::test_admin_and_partner_dashboards_html_escape_untrusted_fields` (neu, siehe unten) verifiziert quellcodebasiert, dass keine unescaped `${a.display_name}`/`${a.email}`/`${a.code}`/`${p.external_reference}`-Interpolation mehr existiert und `esc(` konsequent verwendet wird.

**Retest-Ergebnis:** PASS – neue Testfälle grün; manuelle Prüfung des Diffs bestätigt, dass jede vormals unescaped Interpolation jetzt durch `esc(...)` läuft.

**Restrisiko:** Niedrig. CSP erlaubt weiterhin `'unsafe-inline'` (AFF-010) – ein künftiger, erneuter Escaping-Fehler wäre dadurch nicht durch CSP abgefangen. Empfehlung zur Härtung in AFF-010 dokumentiert.

**Status:** Behoben.

---

## AFF-002 — Android: Explicit-Intent umgeht App-Link-Verifikation (P2, dokumentiertes Restrisiko)

- **Komponente:** `android/app/src/main/java/de/classydl/app/AffiliateReferral.kt` (`capture()`), `MainActivity` (`android:exported="true"`, zwingend für Launcher/Share-Target/App-Links)
- **CWE:** CWE-346 (Origin Validation Error), MASVS-PLATFORM
- **CVSS 3.1 (geschätzt):** 4.3 (AV:L/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N) – erfordert eine zweite, bösartige App auf demselben Gerät; Auswirkung ist Fehlattribution einer künftigen Provision, kein direkter Datenverlust.

**Beschreibung:** `capture()` prüft nur Schema/Host/Pfad/Slug-Format des empfangenen `Intent.ACTION_VIEW`-Datenwerts, nicht aber, ob der Intent tatsächlich über die vom Betriebssystem verifizierte App-Link-Auflösung eintraf. Ein zweites, auf demselben Gerät installiertes Programm kann einen **expliziten** Intent direkt an `de.classydl.app/.MainActivity` senden (`Intent.setClassName(...)`); explizite Intents umgehen Intent-Filter/`autoVerify`/Digital-Asset-Links vollständig – das ist eine dokumentierte Eigenschaft der Android-Plattform, keine Fehlkonfiguration in diesem Code.

**Reproduktion (statisch nachvollzogen, nicht auf echtem Gerät/Fremdsystem ausgeführt):**
```kotlin
val i = Intent(Intent.ACTION_VIEW, Uri.parse("https://downloadthat.pages.dev/claim/attacker-slug"))
i.setClassName("de.classydl.app", "de.classydl.app.MainActivity")
startActivity(i)
```
`capture()` würde dies unabhängig von echter Digital-Asset-Links-Prüfung als gültige Zuordnung akzeptieren.

**Auswirkung:** Eine bereits auf dem Gerät vorhandene bösartige App kann wiederholt und unbemerkt die lokale Partner-Slug-Zuordnung auf einen beliebigen (aktiven) Partnercode umschreiben. Das im Geschäftsmodell **explizit gewollte** Last-Touch-Prinzip (180 Tage) bedeutet, dass ein Überschreiben an sich kein Fehlverhalten ist – die eigentliche Schwäche ist, dass die Überschreibung nicht auf eine echte, verifizierte Nutzerinteraktion zurückgeht.

**Warum kein Code-Fix umgesetzt wurde:** Es existiert keine Android-API, mit der eine empfangende Aktivität zuverlässig zwischen einem von der Plattform verifizierten Implicit-Intent und einem von einer beliebigen Drittanwendung konstruierten (identischen) Intent unterscheiden kann. Ein scheinbarer Fix (z. B. Prüfung von `Intent.CATEGORY_BROWSABLE`) wäre wirkungslos, da der Angreifer diese Kategorie selbst setzen kann – ein solcher "Fix" würde ein falsches Sicherheitsgefühl erzeugen und wird deshalb bewusst **nicht** umgesetzt.

**Kompensierende Kontrollen (bereits vorhanden):** Kapitel `RISK_REGISTER.md` → Begründung AFF-002; zusammengefasst: Auszahlung erfordert weiterhin 30-Tage-Prüfung + Reconciliation + Integrity Gate + Admin-Freigabe; Angreifer braucht ein eigenes, identifizierbares Partnerkonto; Clawback via `negative_balance_cents` ist möglich.

**Tests:** Bestehender `tests/test_affiliate_program.py::test_android_app_link_is_exact_and_adds_no_permissions` deckt die korrekte Manifest-Konfiguration ab (kein Fix in diesem Bereich nötig/möglich).

**Retest-Ergebnis:** N/A (architekturelle Grenze, kein Code-Fix).

**Restrisiko:** Akzeptiert mit Auflage. Siehe `RESIDUAL_RISK_ACCEPTANCE.md`. Empfehlung: serverseitige Anomalieerkennung für ungewöhnliche Conversion-Muster (Alarmierung, siehe HANDOVER §5.5/§5.7, weiterhin offen).

**Status:** Dokumentiertes Restrisiko, kein P0/P1-Blocker für Produktionsfreigabe im Sinne dieser Prüfung.

---

## AFF-003 — Race Condition: doppelte Clawback-Anwendung bei parallelen Webhook-Zustellungen (P2 / Medium)

- **Komponente:** `pro/website/functions/_affiliate.js` (`reverseCommission`), `pro/website/functions/_affiliate_events.js` (`handleAffiliateDisputeClosed`)
- **CWE:** CWE-362 (Concurrent Execution using Shared Resource with Improper Synchronization, "Race Condition")
- **CVSS 3.1 (geschätzt):** 5.3 (AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:L/A:N) – erfordert Timing-abhängige doppelte Webhook-Zustellung; Auswirkung ist eine Buchungsabweichung, keine Umgehung der harten Auszahlungsobergrenze.

**Beschreibung:** Stripe garantiert **at-least-once**-Zustellung von Webhooks; zwei nahezu gleichzeitige
Zustellungen desselben Ereignisses (z. B. `charge.refunded`) können in zwei parallelen Cloudflare-Worker-
Instanzen landen. Beide lasen in der ursprünglichen Implementierung den Provisions-Datensatz, sahen beide
den (noch) nicht-reversierten Status, und beide führten danach – **ungeprüft auf tatsächliche
Statusänderung** – die Buchung `negative_balance_cents = negative_balance_cents + wasSettled` aus. Der
Ledger-Eintrag selbst war durch `UNIQUE(entry_type, reference_type, reference_id)` bereits gegen Duplikate
geschützt, der Saldo-Zähler jedoch nicht. Dieselbe Lücke bestand spiegelbildlich im
"Dispute gewonnen"-Wiederherstellungspfad (`MAX(negative_balance_cents - settled_cents, 0)`).

**Reproduktion:** Ein deterministischer Node-Test simuliert die Race Condition ohne echte Nebenläufigkeit,
indem zwei `reverseCommission(...)`-Aufrufe per `Promise.all` gestartet werden: da der zugrunde liegende
DB-Zugriff synchron ist und beide async-Funktionen bis zu ihrem ersten `await` synchron laufen, lesen beide
Aufrufe denselben Vor-Zustand, bevor einer von beiden schreibt – exakt das Nebenläufigkeitsmuster einer
echten doppelten Webhook-Zustellung. Der Test wurde **vor** dem Fix ausgeführt und schlug reproduzierbar
fehl (`negative_balance_cents` wurde auf 400 statt 200 verdoppelt); nach dem Fix ist er grün.

**Auswirkung:** Kein Verstoß gegen die absolute 4-EUR-Obergrenze und keine Überzahlung – der Fehler wirkt
ausschließlich zulasten des Partners (überhöhter negativer Saldo, der künftige Auszahlungen fälschlich
kürzt) und wäre vom bestehenden Integrity Gate **nicht** erkannt worden, da keine Prüfung
`negative_balance_cents` gegen eine aus Ledger/Commissions abgeleitete Erwartung abgleicht.

**Behebung:** Beide betroffenen UPDATE-Statements, die den Status von `reversed`/`pending`→Zielstatus
umschalten, werden jetzt mit `.run()` ausgeführt und ihr `meta.changes`-Wert geprüft; nur wenn genau eine
Zeile geändert wurde, werden die nachgelagerten Saldo-/Ledger-Effekte angewendet. Ein racender Duplikat-
Aufruf sieht `changes === 0` und bricht mit `{reversed:false, reason:"already reversed"}` bzw.
`{restored:false, reason:"already restored"}` ab.

**Tests:** `pro/website/tests/affiliate_race_conditions.test.mjs` (neu) – vier Tests: (1) parallele
Refund-Webhook-Duplikate reversieren genau einmal, (2) sequentielle Wiederholungen bleiben idempotent, (3)
parallele "Dispute gewonnen"-Duplikate stellen den Saldo genau einmal wieder her, (4) explizite Prüfung der
5,00-%-Grenzsemantik (siehe AFF-Sonderfall unten). Neue `pro/website/tests/helpers/fake-d1.mjs` führt
`schema.sql` + alle `migrations/*.sql` gegen eine echte In-Memory-SQLite-Datenbank aus (node:sqlite), keine
Mock-Daten.

**Retest-Ergebnis:** PASS. Verifiziert durch gezieltes, temporäres Zurücksetzen der Guards (`git stash` +
manuelles Entfernen der `changes`-Prüfung): alle vier Tests liefen weiter, aber die beiden Race-Tests
schlugen exakt wie erwartet fehl (`true !== false`, doppelte Kreditierung nachgewiesen) – danach Fix
wiederhergestellt, alle Tests wieder grün.

**Restrisiko:** Niedrig. Die gleiche Klasse von Bug wurde an den zwei bekannten Stellen behoben; eine
vollständige, automatisierte statische Analyse auf "UPDATE ohne changes-Prüfung gefolgt von einem weiteren
zustandsabhängigen Schreibzugriff" wurde nicht durchgeführt (kein Linter-Regel dafür vorhanden) – als
Folgearbeit empfohlen.

**Status:** Behoben.

---

## AFF-004 — Kein Rate Limiting auf Auth-/Registrierungs-Endpunkten (P2 / Medium)

- **Komponente:** `functions/api/partner/login-request.js`, `functions/api/admin/login-request.js`, `functions/api/partner/register.js`
- **CWE:** CWE-307 (Improper Restriction of Excessive Authentication Attempts)
- **CVSS 3.1 (geschätzt):** 4.3 (AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L)

**Beschreibung:** Vor dieser Prüfung war Cloudflare Turnstile der einzige Schutz gegen Missbrauch dieser
drei Endpunkte. Turnstile bremst rein skriptgesteuerten Missbrauch, nicht aber einen langsamen,
menschlich- oder CAPTCHA-Farm-gestützten Angreifer, der z. B. das Postfach eines Partners oder des Admins
mit Anmeldelinks flutet (E-Mail-Bombing) oder Partnercode-/Slug-Verfügbarkeit durch wiederholte
Registrierungsversuche enumeriert. `functions/api/refund.js` implementiert bereits ein D1-basiertes
Rate-Limit-Muster (`refund_attempts`-Tabelle) – dieses Muster wurde für die Affiliate-Endpunkte nicht
übernommen.

**Behebung:** Neue generische Funktion `checkAffiliateRateLimit(env, bucket, key, windowSeconds,
maxAttempts)` in `_affiliate.js` (salted+gehashter Schlüssel, keine Klartext-IP/E-Mail-Speicherung) und
neue Tabelle `affiliate_rate_limit_attempts` (Migration `0009_affiliate_rate_limits.sql`). Angewendet auf:
- `partner/login-request.js`: 5 Versuche / 15 Minuten je (IP, E-Mail).
- `admin/login-request.js`: 5 Versuche / 15 Minuten je (IP, E-Mail).
- `partner/register.js`: 10 Versuche / Stunde je IP.

**Tests:** Migration wird durch die bestehende `_migrated_db()`-Prüfung in `tests/test_affiliate_program.py`
mit erfasst (frische Testdatenbank appliziert alle Migrationen inkl. `0009` fehlerfrei). Die Rate-Limit-
Logik selbst ist reine SQL-Zählung, identisch zum bereits getesteten `refund_attempts`-Muster; keine
separate Node-Testdatei für dieses spezifische Feature ergänzt, da es strukturell mit dem bestehenden,
bereits produktiv laufenden Muster identisch ist.

**Retest-Ergebnis:** PASS (Migrationen, Syntaxcheck, bestehende Suite grün nach Änderung).

**Restrisiko:** Niedrig. Rate Limits sind pro Bucket global (nicht partnerübergreifend korreliert) – ein
verteilter Angreifer mit vielen IPs könnte weiterhin in Summe deutlich mehr als 5/15 Minuten pro Ziel-E-Mail
auslösen. Für Produktion wird zusätzlich eine Cloudflare-seitige Rate-Limiting-Regel empfohlen (außerhalb
des Applikationscodes, siehe `PRODUCTION_SECURITY_CHECKLIST.md`).

**Status:** Behoben.

---

## AFF-005 — GitHub Actions nicht SHA-gepinnt; ungepinnter `wrangler`-Download mit Secrets im Scope (P2 / Medium)

- **Komponente:** `.github/workflows/affiliate-program.yml`, `android-build.yml`, `android-release.yml`, `deploy-pro-website.yml`
- **CWE:** CWE-829 (Inclusion of Functionality from Untrusted Control Sphere)

**Beschreibung:** Alle referenzierten Third-Party-Actions (`actions/checkout@v4`, `astral-sh/setup-uv@v6`,
`actions/setup-node@v4`, `actions/setup-java@v4`, `android-actions/setup-android@v3`,
`actions/setup-python@v5`, `gradle/actions/setup-gradle@v4`, `actions/upload-artifact@v4`) sind auf
veränderliche Tags statt unveränderliche Commit-SHAs gepinnt – Standard-Supply-Chain-Finding (vgl.
`tj-actions/changed-files`-Vorfall 2025). Zusätzlich lädt `deploy-pro-website.yml` `wrangler` per
`npx -y wrangler@3` zur Laufzeit ohne Versions-Pin, in einem Schritt, der `CLOUDFLARE_API_TOKEN`,
`CLOUDFLARE_ACCOUNT_ID`, `STRIPE_SECRET_KEY` und `STRIPE_WEBHOOK_SECRET` im Environment hat.

**Positiv festgestellt (kein Finding):** `affiliate-program.yml` selbst referenziert **keine** Secrets und
läuft auf `pull_request` (nicht `pull_request_target`) – ein Fork-PR kann über diesen Workflow nichts
exfiltrieren. Secret-tragende Workflows sind korrekt auf `push`/Tag-Trigger beschränkt (nicht PR-triggerbar).
`permissions: contents: read` ist auf Workflow-Ebene korrekt gesetzt (least privilege).

**Warum kein automatisierter Fix in diesem Pass:** Ein korrektes SHA-Pinning erfordert die Verifikation der
tatsächlichen, aktuellen Commit-SHA jeder referenzierten Action gegen deren echtes Repository. Diese Sitzung
hat keinen autorisierten, verifizierten Zugriff auf beliebige externe GitHub-Repositories (der
GitHub-MCP-Zugriff dieser Sitzung ist ausdrücklich auf `pfarrergraf/video_downloader` beschränkt) und keinen
allgemeinen Internetzugriff zur Verifikation. Erfundene/geratene SHA-Werte einzutragen wäre **gefährlicher**
als der Status quo (stille Fehlkonfiguration oder CI-Bruch) und widerspricht der Fail-Closed-Vorgabe dieser
Prüfung. Empfehlung statt Blindpinning: Dependabot `github-actions`-Ecosystem-Updates aktivieren (automatisiert
SHA-Bumps mit sichtbarem Diff) und einmalig durch den Repository-Inhaber oder eine Pipeline mit echtem
Internetzugriff pinnen lassen.

**Empfohlene Ziel-Syntax (Platzhalter, NICHT ungeprüft übernehmen):**
```yaml
- uses: actions/checkout@<verify-current-sha> # v4.x.x
```

**Tests:** N/A (Konfigurationsempfehlung, keine automatisiert prüfbare Code-Änderung ohne externe Verifikation).

**Retest-Ergebnis:** Offen – Nachweis erst nach Umsetzung durch den Repository-Inhaber möglich.

**Restrisiko:** Mittel bis zur Umsetzung. Siehe `PRODUCTION_SECURITY_CHECKLIST.md`.

**Status:** Dokumentiert, Umsetzung ausstehend (erfordert externen Repository-Zugriff/Freigabe).

---

## AFF-006 — Secret-Scan-Test: blinder Fleck bei Turnstile, regexbasiert umgehbar (P2 / Medium)

- **Komponente:** `tests/test_affiliate_no_secrets.py`
- **CWE:** CWE-200 (verwandt, Kontrollreferenz statt Schwachstelle)

**Beschreibung:** Die bestehenden Muster erkannten Stripe-/Resend-Secrets und private Schlüssel, aber
**keine** Cloudflare-Turnstile-Secrets, obwohl `env.TURNSTILE_SECRET_KEY` aktiv im Code verwendet wird
(`_affiliate.js`, `verifyTurnstile`). Zusätzlich ist jede regexbasierte Prüfung durch Verkettung,
Kodierung oder Zeilenumbrüche trivial umgehbar; das ist eine grundsätzliche, nicht vollständig behebbare
Einschränkung dieser Testklasse.

**Behebung:** Zusätzliches Muster `Turnstile secret key` (`\b[0-3]x[0-9A-Za-z_-]{20,}\b`) ergänzt; geprüft,
dass keine der bekannten Cloudflare-Test-Dummy-Schlüssel (`1x0000000000000000000000000000000AA` etc.) im
Repository vorkommen, die das neue Muster fälschlich auslösen würden.

**Tests:** `tests/test_affiliate_no_secrets.py::test_affiliate_changes_contain_no_embedded_secrets` läuft
weiterhin grün mit dem erweiterten Muster-Set.

**Retest-Ergebnis:** PASS.

**Restrisiko:** Mittel – die grundsätzliche Umgehbarkeit regexbasierter Scans bleibt bestehen. Empfehlung:
zusätzlich `gitleaks`/`trufflehog` oder GitHub Advanced Security Secret Scanning als tiefere, historienweite
Kontrolle einsetzen (dieser Test bleibt sinnvoll als schneller CI-Gate-Backstop, ersetzt aber keinen echten
Secret-Scanner).

**Status:** Teilweise behoben (bekannter blinder Fleck geschlossen); Restlimitation dokumentiert.

---

## AFF-007 — Totes Code-Duplikat mit latentem Bug (P3 / Low)

- **Komponente:** `functions/_affiliate.js` (entfernte Funktion `createDynamicCheckout`)
- **CWE:** CWE-1164 (Irrelevant Code)

**Beschreibung:** Neben der tatsächlich aufgerufenen Checkout-Erstellung in
`functions/api/create-checkout.js` existierte eine zweite, nirgends importierte Implementierung derselben
Logik in `_affiliate.js`. Sie unterschied sich in zwei sicherheitsrelevanten Punkten: (1) sie prüfte
`affiliateProgramEnabled(env)` **nicht**, (2) sie setzte `client_reference_id` auf die Checkout-Intent-ID
statt auf das Sentinel `"wait14"`, das `_lib.js`'s `handleCheckoutCompleted` zur Steuerung der
gesetzlichen 14-Tage-Widerrufsfrist auswertet – wäre diese Funktion jemals verdrahtet worden, hätte sie
die Widerrufsfrist-Lieferverzögerung stillschweigend gebrochen. Da die Funktion nachweislich (Grep über
das gesamte Repository) nirgends aufgerufen wird, wurde sie vollständig entfernt statt "repariert" –
das reduziert die Angriffs-/Fehlerfläche für künftige Wartung, ohne Verhalten zu ändern.

**Behebung:** Funktion sowie die dadurch verwaiste private Hilfsfunktion `stripePost` entfernt.

**Tests:** `npm run check` (Node-Syntaxprüfung aller Cloudflare Functions) und die bestehende
`pro/website/tests/affiliate_finance.test.mjs`-Suite laufen unverändert grün.

**Retest-Ergebnis:** PASS.

**Restrisiko:** Keines.

**Status:** Behoben.

---

## AFF-008 — Android: Case-sensitive Host-Vergleich (P3 / Low)

- **Komponente:** `android/.../AffiliateReferral.kt`

**Beschreibung:** `uri.host` wird nicht normalisiert, `ALLOWED_HOSTS` enthält nur Kleinschreibung. Ein
Host mit gemischter Groß-/Kleinschreibung (z. B. von einem Redirector) würde eine legitime Zuordnung
stillschweigend verwerfen. Kein Sicherheitsproblem (kann nicht zur Umgehung der Validierung genutzt
werden), aber eine Robustheitslücke.

**Behebung:** `uri.host?.lowercase()` bzw. `original.host?.lowercase()` vor dem Vergleich.

**Tests:** Bestehender `test_android_app_link_is_exact_and_adds_no_permissions` bleibt unverändert grün
(prüft Manifest-Konstanten, nicht Laufzeitverhalten); eine Kotlin-Unit-Test-Infrastruktur existiert in
diesem Projekt nicht (nur Kotlin-Compile-Check in CI) – Verhalten wurde durch Nachvollzug des Kontrollflusses
verifiziert, nicht durch einen neuen automatisierten Test.

**Retest-Ergebnis:** PASS (Compile-Check unverändert grün, Logik manuell nachvollzogen).

**Status:** Behoben.

---

## AFF-012 — Stacktrace-Leak in Webhook-Fehlerantwort (P3 / Low)

- **Komponente:** `functions/api/webhook.js`
- **CWE:** CWE-209 (Generation of Error Message Containing Sensitive Information)

**Beschreibung:** Der `catch`-Block gab `stack: err?.stack` im JSON-Response zurück. Die vorgelagerte
Stripe-Signaturprüfung stellt sicher, dass nur Aufrufer mit Kenntnis von `STRIPE_WEBHOOK_SECRET` diesen
Codepfad überhaupt erreichen können — die praktische Ausnutzbarkeit war dadurch gering — aber interne
Pfade/Stacktraces gehören grundsätzlich nicht in eine Client-Antwort.

**Behebung:** `stack` aus dem Response-Body entfernt; vollständige Details bleiben in `console.error`
(serverseitiges Log) erhalten.

**Tests:** `npm run check` (Syntaxprüfung) grün; kein dedizierter Test ergänzt, da dies eine reine
Response-Shape-Änderung ohne Verzweigungslogik ist.

**Retest-Ergebnis:** PASS.

**Status:** Behoben.

---

## AFF-009, AFF-010, AFF-011

Siehe `RISK_REGISTER.md` für Kurzbeschreibung. Diese drei Punkte sind operative Prüf- bzw.
Härtungsempfehlungen ohne in diesem Pass umgesetzten Code-Fix (Begründung jeweils dort). Sie sind in
`PRODUCTION_SECURITY_CHECKLIST.md` als Voraussetzungen vor Produktionsfreigabe aufgenommen.

---

## Was geprüft und für unauffällig befunden wurde (kein Finding)

- **SQL Injection:** Sämtliche Datenbankzugriffe in `_affiliate*.js` und `functions/api/**` verwenden
  ausschließlich parametrisierte `.bind()`-Aufrufe; keine Stelle mit String-Konkatenation von
  Benutzereingaben in SQL-Text gefunden.
- **IDOR/BOLA:** `partner/me.js` leitet alle Daten ausschließlich aus der serverseitig verifizierten
  Session (`session.affiliate_id`) ab, nie aus einer clientseitig übergebenen ID. Alle `admin/*.js`-Routen
  prüfen `getAffiliateSession(request, env, "admin")` und verweigern sonst mit 401.
- **CSRF:** Alle zustandsändernden Aktionen sind POST-only mit `SameSite=Lax`-Cookie; kein GET-Endpunkt
  mit Seiteneffekt außer dem inhärent tokenbasierten Magic-Link-Konsum.
- **CORS:** Keine `Access-Control-Allow-Origin`-Header irgendwo in `functions/` (bewusst, da `/api/*`
  same-origin ist).
- **Sensible Daten im Partner-Dashboard:** `partnerDashboardData()` selektiert ausschließlich
  eigene aggregierte Partnerfelder; kein Pfad zu Käufer-E-Mail/-Name gefunden.
- **Open Redirect / Host-Header-Vertrauen:** Keine Stelle liest `request.headers.get("Host")` zur
  Redirect-Konstruktion; `publicBaseUrl()` bevorzugt `env.PUBLIC_BASE_URL`.
- **Finanzinvarianten:** Absolute Obergrenze (`Lizenzen × 400 Cent`), Provisionsstaffel-Grenzwerte,
  Append-only-Ledger/Audit-Trigger, 5,00-%-Reconciliation-Grenzsemantik (exakt 500 Bps = kein Freeze, 501
  Bps = Freeze) wurden durch bestehende und neue Tests bestätigt.
- **Android-Berechtigungen:** Ausschließlich die vier freigegebenen Berechtigungen vorhanden; keine
  Verletzung der CLAUDE.md-Guardrail.
- **WebView/JS-Bridge:** `shouldOverrideUrlLoading` verhindert, dass die WebView jemals Fremdinhalte lädt;
  die `@JavascriptInterface`-Bridge ist dadurch für Angreiferinhalte unerreichbar.
- **Node/npm-Abhängigkeiten:** `pro/website` hat keine einzige npm-Abhängigkeit (kein Lockfile nötig).
- **Python-/Gradle-Abhängigkeiten:** `uv.lock` ist committet und exakt gepinnt; Gradle-Plugins/-Deps sind
  exakt versioniert (keine `+`-Ranges).
