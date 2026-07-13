# Red-Team-Report — Downloader-Kern, On-Device-Server & Android-App

Datum: 2026-07-13 · Rolle: Angreifer (CCC-/IT-Security-Firmen-Perspektive) ·
Scope: `video_downloader/` (Kern + `web/server.py`), `classydl_web_entry.py`,
`android/`, `licensing.py`. Ergänzt das bestehende, affiliate-/backend-fokussierte
`PENETRATION_TEST_RESULTS.md` um die bisher formal unterabgedeckte App selbst.

## Auftrag (bewusst gegnerisch formuliert)

> „Diese vibe-codierte App erfüllt keine Standards. Sie ist leicht manipulierbar,
> die Daten sind unsicher, und Lizenzschlüssel lassen sich von außen erzeugen."

Ziel dieses Reports: jede Teilbehauptung als **bewiesen** oder **widerlegt**
markieren — mit reproduzierbaren PoCs gegen eine lokale Instanz (kein Fremdsystem).

## Ergebnis auf einen Blick

| # | Angriffshypothese | Verdikt | Status nach Härtung |
|---|---|---|---|
| A1 | Lizenzschlüssel von außen generierbar | ❌ widerlegt | — (kein Fix nötig) |
| A2 | Pro-Freischaltung lokal umgehbar | ✅ bestätigt | akzeptierter Trade-off, dokumentiert |
| A3 | SSRF über `/api/scrape` | ✅ bestätigt | **behoben** (SSRF-Guard, 400) |
| A4 | Lokale Daten für Co-Tenant lesbar | ✅ bestätigt | **behoben** (0600/0700) |
| A5 | Passwort-Leak über Auto-Login-URL | ✅ bestätigt | **behoben** (Einmal-Token) |
| A6 | Login brute-force-bar | ❌ widerlegt | Kontrolle bereits vorhanden |
| A7 | Clickjacking / fehlende Header | ✅ bestätigt | **behoben** (CSP + Header) |
| A8 | Path-Traversal (Download/Static) | ❌ widerlegt | Kontrolle bereits vorhanden |
| A9 | Supply-Chain über yt-dlp-Self-Update | ❌ widerlegt | gut abgesichert, in-scope dokumentiert |
| A10 | Stripe-Webhook fälschbar | ❌ widerlegt | korrekt signaturgeprüft |

**Kernaussage:** Von den drei plakativen Vorwürfen ist einer schlicht falsch
(Schlüsselfälschung), einer ein bewusster Produkt-Trade-off (lokale Pro-Umgehung),
und die „unsicheren Daten" waren real, sind aber mit gezielten, günstigen Fixes
geschlossen. „Erfüllt keine Standards" ist als Pauschale widerlegt.

---

## Reproduzierbares PoC-Harness

Ein lauffähiges Harness (`scripts/redteam_poc.py`) startet eine lokale
`ClassyDLServer`-Instanz plus einen internen „Metadaten"-Dienst und fährt A3/A4/A6/A7/A8
automatisiert. Auszüge unten sind die realen Ausgaben vor und nach der Härtung.

### Vorher (Ist-Zustand)
```json
{
  "A6_bruteforce": "lockout=YES codes=[401, 401, 401, 401, 401, 429]",
  "A7_headers": "present=NONE",
  "A8_traversal": "download=404 static=404 leaked_passwd=False",
  "A3_ssrf": "REACHED internal service, items=1 (VULNERABLE)",
  "A4_fileperms": "state.db mode=0o644 (world-readable)"
}
```

### Nachher (nach Härtung)
```json
{
  "A6_bruteforce": "lockout=YES codes=[401, 401, 401, 401, 401, 429]",
  "A7_headers": "present=['content-security-policy','x-frame-options','x-content-type-options','referrer-policy']",
  "A8_traversal": "download=404 static=404 leaked_passwd=False",
  "A3_ssrf": "BLOCKED status=400 detail=Blocked request to non-public address 127.0.0.1 (host '127.0.0.1')",
  "A4_fileperms": "state.db mode=0o600 (restricted)"
}
```

---

## Detail-Findings

### A1 — Lizenzschlüssel von außen generierbar? ❌ WIDERLEGT
**Vorgehen:** Client-Code (`licensing.py`) und Server-Code (`pro/website/functions/`)
auf ein eingebettetes Signier-Secret oder eine Schlüssel-Ableitung durchsucht.
**Befund:** Keins vorhanden. Schlüssel werden serverseitig erzeugt
(`_lib.js:generateLicenseKey`, 96 bit `crypto.getRandomValues`, Format
`DLT-XXXXXXXX-XXXXXXXX-XXXXXXXX`) und rein per DB-Lookup validiert
(`api/validate.js` → Cloudflare D1). Der Schlüssel trägt keine selbst-verifizierbare
Nutzlast; seine einzige Bedeutung ist „existiert als Zeile in `licenses`". Der Client
ruft nur `GET /api/validate?key=…`. Es gibt nichts zu invertieren, kein Secret zu
stehlen; Brute-Force über 96 bit ist infeasibel. **Der Vorwurf ist technisch falsch.**

### A2 — Pro-Freischaltung lokal umgehbar? ✅ BESTÄTIGT (Design-Trade-off)
**Vorgehen:** `server.py:836 is_pro = manager is None or manager.is_pro()` analysiert;
`license.json` editiert; Netzwerkzugriff auf `downloadthat.pages.dev` blockiert.
**Befund:** Die Free-/Pro-Entscheidung fällt in einem Server, der **auf dem Gerät des
Nutzers** läuft. Wer sein eigenes Gerät kontrolliert, kann die gecachte Lizenz-State-Datei
patchen (bis 6 h gültig) oder durch dauerhaftes Offline-Halten die 7-Tage-Offline-Grace
ausnutzen. **Einordnung:** Das ist kein Fremd-Angriff auf andere Nutzer, sondern die bei
On-Device-Software übliche Grenze der Client-seitigen Durchsetzung. Für eine 12-€-Einmalzahlung
ist serverseitiges DRM unverhältnismäßig. → In `RESIDUAL_RISK_ACCEPTANCE.md` als akzeptiertes
Restrisiko geführt.

### A3 — SSRF über `/api/scrape`? ✅ BESTÄTIGT → BEHOBEN
**Vorgehen:** Authentifiziert `POST /api/scrape {"url":"http://127.0.0.1:<port>/"}` gegen
einen internen Loopback-Dienst.
**Befund (vorher):** Der Server holte die interne URL, folgte Redirects und extrahierte
Medien — d. h. ein authentifizierter Aufrufer konnte den Server interne Ziele
(`169.254.169.254`, RFC1918) abrufen lassen. Materiell v. a. beim **alten CLI-Default
`--host 0.0.0.0`** über Klartext-HTTP.
**Fix:** `scraper.assert_public_url()` — Scheme-Allowlist (nur http/https), Auflösung des
Hosts und Block aller privaten/Loopback/Link-Local/Reserved/Multicast-IPs; Redirects werden
manuell verfolgt und **jeder Hop erneut geprüft** (verhindert Redirect-zu-intern). Der
`/api/scrape`-Handler liefert nun `400` mit klarer Begründung. Restrisiko: DNS-Rebinding
zwischen Prüfung und Connect (dokumentiert, für dieses Bedrohungsmodell akzeptiert, da die
realen Deployments Loopback binden).

### A4 — Lokale Daten für Co-Tenant lesbar? ✅ BESTÄTIGT → BEHOBEN
**Vorgehen:** Dateirechte von `state.db`, `web_password.txt`, `license.json` geprüft.
**Befund (vorher):** `0644` (world-readable) — auf einem Multi-User-Host konnten andere
lokale Nutzer die Klartext-URL-Historie, das Web-Passwort und den Lizenzschlüssel lesen.
**Fix:** Daten-Verzeichnisse `0700`, sensible Dateien `0600` (`app_config._harden`,
`queue_store._harden_db_files` inkl. WAL/SHM, `licensing._save`, `classydl_web_entry`).
Best-effort/advisory unter Windows (dort ohnehin per-User-Pfade).

### A5 — Passwort-Leak über Auto-Login-URL? ✅ BESTÄTIGT → BEHOBEN
**Vorgehen:** Desktop-Auto-Login-URL inspiziert.
**Befund (vorher):** `…/desktop_autologin.html?t=<web_password>` — das langlebige Passwort
lag in Query-String, Browser-History und potenziell Referrern.
**Fix:** Einmal-Token-Handshake — der Launcher mintet in-process ein Single-Use-Token
(`server.issue_autologin_token()`, TTL 120 s), das die Seite einmalig gegen
`/api/desktop-login` eintauscht. Das Passwort verlässt nie den Prozess. Fallback bei
belegtem Port öffnet nur `/` (kein Secret in der URL).

### A6 — Login brute-force-bar? ❌ WIDERLEGT
**Befund:** `LoginThrottle` sperrt nach 5 Fehlversuchen pro IP für 60 s; Vergleich ist
konstantzeitig (`hmac.compare_digest`). PoC bestätigt `429` ab dem 6. Versuch.
Restnotiz: hinter einem Reverse-Proxy kollabieren alle Clients auf eine IP
(kein `X-Forwarded-For`-Handling) — im Loopback-Modell irrelevant.

### A7 — Clickjacking / fehlende Header? ✅ BESTÄTIGT → BEHOBEN
**Befund (vorher):** Keinerlei Security-Header auf der ~117-KB-SPA → framebar, DOM-XSS
unmitigiert. **Fix:** zentral in `server.py` — CSP (`default-src 'self'`,
`frame-ancestors 'none'`, kein externer Host), `X-Frame-Options: DENY`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` auf allen Antworten.

### A8 — Path-Traversal (Download/Static)? ❌ WIDERLEGT
**Befund:** Der Download-Endpoint matcht den `[^/]+`-Dateinamen gegen die **in der DB
gespeicherten** Job-Dateien per Basename — Nutzereingabe konstruiert nie einen Pfad. Static
nutzt Resolve-plus-Containment. PoC mit `..%2f..%2fetc%2fpasswd` → `404`, kein Leak.

### A9 — Supply-Chain über yt-dlp-Self-Update? ❌ WIDERLEGT (in-scope)
**Befund:** `engine_update.py` lädt yt-dlp über TLS von PyPI, verifiziert SHA-256, lässt
kein Downgrade zu und prüft Zip-Path-Traversal. Angemessen abgesichert; als bewusste
Supply-Chain-Fläche in `THREAT_MODEL.md` geführt.

### A10 — Stripe-Webhook fälschbar? ❌ WIDERLEGT
**Befund:** `_lib.js:verifyStripeSignature` prüft HMAC-SHA256 über `${t}.${payload}`,
5-Minuten-Timestamp-Toleranz gegen Replay, konstantzeitiger Vergleich; ohne
`STRIPE_WEBHOOK_SECRET` bzw. bei ungültiger Signatur wird abgewiesen. Korrekt.

---

## Fazit des Red Teams

Die App ist **kein** Musterbeispiel für „unsicherer Vibe-Code". Die scharfen Vorwürfe
treffen entweder gar nicht (A1, A10) oder auf bereits vorhandene Kontrollen (A6, A8, A9).
Real waren vier Härtungslücken (A3, A4, A5, A7) — allesamt typische Frühphasen-To-dos,
die mit kleinen, gezielten Änderungen geschlossen wurden. Die einzige „per Design"
verbleibende Schwäche (A2) ist ein bewusster, verhältnismäßiger Produkt-Trade-off.
