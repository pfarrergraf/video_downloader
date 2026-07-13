# OWASP ASVS 5.0.0 — Addendum: Downloader-Kern & On-Device-Server

Datum: 2026-07-13. Ergänzt `ASVS_5_MATRIX.md` (dort: Affiliate-/Web-Backend) um den
zuvor formal unterabgedeckten **Downloader-Kern** und den **On-Device-HTTP-Server**
(`video_downloader/web/server.py`). Interne Readiness-Bewertung, keine Zertifizierung.

Bedrohungsmodell-Kontext: Der Server bindet in den realen Deployments (Desktop/Android)
`127.0.0.1`; der CLI-Default ist nach diesem Audit ebenfalls `127.0.0.1` (LAN-Bind nur
mit explizitem `--host` + Warnung).

Legende: ✅ erfüllt · ⚠️ mit Auflage · ❌ offen · N/A

| ASVS-Kapitel | Anforderung | Status | Evidenz / Finding |
|---|---|---|---|
| V2 Validation & Business Logic | Serverseitige Validierung; **SSRF-Schutz** bei serverseitigem Fetch | ✅ (nach Fix) | `scraper.assert_public_url` blockt private/loopback/metadata-IPs inkl. Redirect-Hops (A3); Quality/Settings enum-validiert |
| V3 Web Frontend Security | CSP, Security-Header, Clickjacking-Schutz | ✅ (nach Fix) | CSP `default-src 'self'` + `frame-ancestors 'none'`, `X-Frame-Options`, `nosniff`, `Referrer-Policy` (A7) |
| V4 API & Web Service | Auth je Endpunkt | ✅ | `_require_auth` auf allen `/api/*`-Zustands-Endpunkten; Tests decken das ab |
| V5 File Handling | Kein Path-Traversal bei Datei-Ausgabe | ✅ | DB-Basename-Matching Download/Open/Share; Resolve-Containment Static (A8) |
| V6 Authentication | Brute-Force-Schutz, konstantzeitiger Vergleich | ✅ | `LoginThrottle` 5/60s, `hmac.compare_digest` (A6); Einmal-Token-Handshake statt Passwort-in-URL (A5) |
| V7 Session Management | Zufällige Tokens, HttpOnly/SameSite | ✅ (⚠️ Secure) | `secrets.token_urlsafe(32)`, `HttpOnly; SameSite=Lax`; `Secure` opt-in `secure_cookies=True` (Loopback-HTTP-Default: aus) |
| V8 Authorization | Kein clientseitiges Rechte-Flag | ⚠️ | Pro-Gate client-seitig durchgesetzt (A2, akzeptiertes Restrisiko) |
| V11 Cryptography | CSPRNG, keine Krypto-Secrets im Client | ✅ | `secrets`/`SecureRandom`; Lizenz ohne Client-Secret (A1) |
| V12 Secure Communication | Transport-Schutz | ⚠️ | HTTP auf Loopback (kein TLS); `Secure`-Cookies + HSTS N/A ohne TLS-Terminierung — bewusst, dokumentiert |
| V13 Configuration | Sichere Defaults, keine Secrets im Repo | ✅ (nach Fix) | Bind-Default `127.0.0.1`; Passwortpflicht; `0600`/`0700` at rest (A4); `test_affiliate_no_secrets.py` |
| V14 Data Protection | Datenschutz, Löschung | ✅ (nach Fix) | Secrets/Historie `0600`; lokale DSAR-Löschung `classydl purge-data` |

## Zusammenfassung

**ASVS-L1: erfüllt.** L2 bis auf zwei bewusste, dokumentierte Auflagen erfüllt:
Transport ist HTTP-auf-Loopback (V12, kein TLS im Einzelnutzer-Modell) und die
Pro-Durchsetzung ist client-seitig (V8/A2). Beide sind in `RESIDUAL_RISK_ACCEPTANCE.md`
als akzeptierte Restrisiken geführt.
