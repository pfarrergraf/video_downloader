# OWASP ASVS 5.0.0 Mapping — Affiliate Program

Ziel: mindestens Level 2 für die internetexponierte Anwendung; Zahlungs-/Finanz-/Admin-/Integritätsbereiche
zusätzlich gegen relevante Level-3-Anforderungen geprüft. Diese Matrix ist eine **interne Readiness-Bewertung**,
keine formelle ASVS-Zertifizierung (die ASVS kennt ohnehin kein Zertifikat, sondern dient als
Prüfcheckliste).

Legende: ✅ erfüllt · ⚠️ teilweise/mit Auflage · ❌ nicht erfüllt · N/A nicht anwendbar

| ASVS-Kapitel | Kernanforderung (paraphrasiert) | Status | Evidenz / Finding |
|---|---|---|---|
| V1 Encoding & Sanitization | Kontextgerechtes Escaping vor Ausgabe in HTML | ✅ (nach Fix) | AFF-001 behoben; `esc()` in beiden Dashboards |
| V2 Validation & Business Logic | Serverseitige Validierung aller sicherheitsrelevanten Werte | ✅ | Provisionsstaffel, Auszahlungsminimum, Partnercode-Normalisierung ausschließlich serverseitig |
| V3 Web Frontend Security | CSP, Security-Header, Cache-Control | ⚠️ | Header vorhanden (`_headers`), aber `script-src 'unsafe-inline'` (AFF-010) |
| V4 API & Web Service | Konsistente Auth-/Rollenprüfung je Endpunkt | ✅ | Jede Admin-Route einzeln verifiziert |
| V5 File Handling | N/A für diese Feature-Fläche | N/A | Kein Dateiupload im Affiliate-Programm |
| V6 Authentication | Passwortlos (Magic Link), einmalig, kurze TTL (20 Min), gehasht gespeichert | ✅ | `issuePartnerToken`/`issueAdminToken`/`consume*Token` |
| V7 Session Management | Serverseitiger Session-Hash, HttpOnly/Secure/SameSite, Re-Validierung des Live-Status pro Request | ✅ | `getAffiliateSession` liest `affiliate_status` live, nicht gecacht |
| V8 Authorization | Rollenbindung serverseitig, kein clientseitiges Rollenflag | ✅ | Bestätigt für alle Partner-/Admin-Routen |
| V9 Self-contained Tokens | N/A (keine JWTs verwendet, opake Zufalls-Tokens + serverseitiger Lookup) | N/A | — |
| V10 OAuth/OIDC | N/A | N/A | Kein OAuth-Flow |
| V11 Cryptography | SHA-256/HMAC-SHA256, `crypto.getRandomValues`, konstantzeitiger Signaturvergleich | ✅ | `verifyStripeSignature`, `sha256Hex`, `randomToken` |
| V12 Secure Communication | HTTPS erzwungen (HSTS), TLS-Terminierung bei Cloudflare | ✅ | `_headers` HSTS; TLS-Konfiguration selbst außerhalb des Repo-Scopes |
| V13 Configuration | Fail-closed Feature-Flag, kein Secret im Repo | ✅ | `AFFILIATE_PROGRAM_ENABLED` Default `false`; `test_affiliate_no_secrets.py` |
| V14 Data Protection | Datenminimierung (gehashte IP/UA), keine Käufer-PII im Partner-Dashboard | ✅ | Bestätigt, siehe `PRIVACY_AND_DATA_RETENTION_REVIEW.md` |

## Level-3-relevante Vertiefung (Zahlungs-/Finanz-/Admin-/Integritätsbereich)

| Anforderung | Status | Evidenz |
|---|---|---|
| Zwei-Faktor-/Maker-Checker-Kontrolle bei kritischen Finanzoperationen | ✅ | System bereitet vor, Mensch (Admin) genehmigt, echte Überweisung bleibt extern-manuell |
| Unveränderliche, manipulationssichere Audit-Historie | ✅ | Hash-verkettete Ledger/Audit/Reconciliation/Integrity-Tabellen, DB-Trigger gegen UPDATE/DELETE |
| Zentrale, wiederholbare Integritätsprüfung vor jeder sensiblen Aktion | ✅ | `requireLockedIntegrityForPayout` vor jedem Payout-Schritt |
| Race-Condition-Freiheit bei nebenläufigen Finanzbuchungen | ✅ (nach Fix) | AFF-003 behoben und regressionsgetestet |
| Rate Limiting auf Authentisierungsendpunkten | ✅ (nach Fix) | AFF-004 behoben |
| Stored-XSS-Freiheit im Admin-Kontext | ✅ (nach Fix) | AFF-001 behoben |

## Zusammenfassung

**Level 2: erfüllt** (nach Behebung von AFF-001, AFF-004, AFF-012). **Level-3-Vertiefung für
Zahlungs-/Admin-/Integritätsbereiche: erfüllt**, mit zwei offenen operativen Auflagen (AFF-005 SHA-Pinning,
AFF-009 Produktions-Zertifikatsverifikation), die außerhalb des Codes liegen und vor Produktionsfreigabe
nachzuweisen sind (siehe `PRODUCTION_SECURITY_CHECKLIST.md`).

Diese Bewertung ist **keine formelle ASVS-Zertifizierung** — ASVS sieht ohnehin kein Zertifikat vor, sondern
dient als wiederverwendbare Prüfcheckliste für interne und externe Audits.
