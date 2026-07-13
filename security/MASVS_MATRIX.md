# OWASP MASVS Mapping — Android-App (`de.classydl.app`)

Datum: 2026-07-13. Interne Readiness-Bewertung der sideload-baren Android-App
(Kotlin-Shell + Chaquopy/CPython + WebView vor dem On-Device-Server). **Keine
formelle Zertifizierung** — MASVS ist eine Prüfcheckliste. Ziel: MASVS-L1 vollständig,
resilience-relevante L2-Punkte bewertet.

Legende: ✅ erfüllt · ⚠️ teilweise/mit Auflage · ❌ offen · N/A nicht anwendbar

| MASVS-Kategorie | Kernanforderung | Status | Evidenz / Finding |
|---|---|---|---|
| **MASVS-STORAGE-1** Keine sensiblen Daten unkontrolliert gespeichert | Secrets/PII nicht im Klartext an lesbaren Orten | ✅ (nach Fix) | `state.db`/`web_password.txt`/`license.json` jetzt `0600`, Dir `0700`; `allowBackup="false"` verhindert Auto-Backup-Restore; per-Install-Passwort in SharedPreferences |
| **MASVS-STORAGE-2** Keine sensiblen Daten in Logs/IPC | — | ✅ | Server-Logging stummgeschaltet; keine Secrets in `logcat` |
| **MASVS-CRYPTO-1/2** Starke, korrekt genutzte Krypto | Zufalls-/Session-Token | ✅ | `SecureRandom` per-Install-Passwort (release); `secrets.token_urlsafe(32)` Sessions; Einmal-Token Auto-Login |
| **MASVS-AUTH-1** Auth-Anforderungen erfüllt | Loopback-Server passwortgeschützt | ✅ | Shared-Password + `hmac.compare_digest`, Lockout 5/60s; Einmal-Token-Handshake |
| **MASVS-NETWORK-1** Sicherer Netzwerkverkehr | Kein Cleartext außer nötig | ✅ | `network_security_config.xml`: Cleartext **nur** `127.0.0.1`; Rest default-secure; `certifi`-CA gesetzt |
| **MASVS-NETWORK-2** TLS-Konfiguration | Externe Calls über TLS | ✅ | Lizenz-/Update-Calls HTTPS |
| **MASVS-PLATFORM-1** Sichere IPC / exportierte Komponenten | Nur nötige Exporte | ✅ | `DownloadService`/`FileProvider` `exported="false"`; `MainActivity` nur wegen LAUNCHER exportiert; App-Links eng auf `…/claim/` autoVerify |
| **MASVS-PLATFORM-2** WebView-Härtung | JS-Bridge nicht fremd-exponiert | ⚠️ | `addJavascriptInterface(WebAppBridge,"AndroidBridge")` + `javaScriptEnabled`; mitigiert durch `shouldOverrideUrlLoading` (nur `127.0.0.1` bleibt im WebView, alles andere → System-Browser). **L2-Empfehlung:** manuelle Bridge-Review in L2 (Pentest) |
| **MASVS-PLATFORM-3** Deep-Links/Intents sicher | Kein breiter `ACTION_VIEW` | ✅ | Nur `SEND` (Share) + eng gescopte App-Links; kein Wildcard-Intent |
| **MASVS-CODE-1** Minimale Berechtigungen | Nur Nötiges | ✅ | 4 Permissions (INTERNET, FOREGROUND_SERVICE[_DATA_SYNC], POST_NOTIFICATIONS), alle owner-approved & dokumentiert (`ANDROID_PERMISSIONS_2026-07-07.md`); Guardrail in `CLAUDE.md` |
| **MASVS-CODE-2** Updates/Patching | Fixe Auslieferung | ⚠️ | Sideload über GitHub Releases, signiert + SHA-256; kein Auto-Update-Kanal (bewusst, Beta) — für CRA-Update-Pflicht relevant |
| **MASVS-CODE-3** Keine Debug-Artefakte in Release | Debug-Pfad getrennt | ⚠️ | `DEBUG_PASSWORD="classydl"` & Licensing-off nur unter `BuildConfig.DEBUG`; Release generiert Zufallspasswort. Als bekannter TODO in `memory.md` geführt |
| **MASVS-RESILIENCE-*** | Obfuskation/Anti-Tampering | N/A / bewusst offen | `minifyEnabled false`, keine Obfuskation. Für ein Open-Utility bewusst — die Pro-Durchsetzung ist ohnehin client-seitig (A2), Resilience-Härtung wäre Sicherheits-Theater |

## Zusammenfassung

**MASVS-L1: erfüllt** (nach Storage-Härtung). Zwei ⚠️ mit klaren Auflagen:
Debug-Artefakt-Trennung (CODE-3, dokumentiert & release-sauber) und WebView-Bridge
(PLATFORM-2, mitigiert; manuelle Review in L2 empfohlen). RESILIENCE bewusst nicht
adressiert — verhältnismäßig für ein sideload-bares Open-Utility.
