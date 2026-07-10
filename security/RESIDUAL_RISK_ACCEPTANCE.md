# Residual Risk Acceptance — Affiliate Program

Diese Datei dokumentiert Risiken, die nach dieser Prüfung **bewusst nicht durch einen Code-Fix** geschlossen
wurden, mit Begründung, kompensierenden Kontrollen und Verantwortlichkeit. Sie ersetzt keine förmliche
Risikoakzeptanz durch den Repository-Inhaber — diese Sitzung **dokumentiert** die Empfehlung, **akzeptiert**
sie aber nicht in dessen Namen.

## AFF-002 — Android App-Link-Attribution via Explicit Intent fälschbar

- **Grund für Nicht-Behebung:** Strukturelle Android-Plattformgrenze; kein zuverlässiger Code-Fix möglich,
  ohne das explizit geforderte Last-Touch-Attributionsmodell zu verletzen oder eine wirkungslose
  Pseudo-Kontrolle einzuführen.
- **Kompensierende Kontrolle:** Finanzielle Auswirkung bleibt durch 30-Tage-Prüfung, Reconciliation,
  Integrity Gate und Admin-Maker-Checker-Prozess begrenzt; Angreifer benötigt ein eigenes, identifizierbares
  und sperrbares Partnerkonto; Clawback via `negative_balance_cents` möglich.
- **Zieldatum für Neubewertung:** Bei nächster größerer Android-Architekturänderung oder falls ein
  produktentaugliches Attributions-SDK mit serverseitiger Click-ID-Verifikation eingeführt wird.
- **Verantwortlich:** Repository-Inhaber (Produktentscheidung, ob das Restrisiko für das erwartete
  Transaktionsvolumen akzeptabel ist).

## AFF-005 — GitHub Actions nicht SHA-gepinnt

- **Grund für Nicht-Behebung:** Diese Sitzung hat keinen verifizierten Zugriff auf die echten
  Commit-SHAs der referenzierten Drittanbieter-Repositories (GitHub-MCP-Zugriff ist auf
  `pfarrergraf/video_downloader` beschränkt); erfundene Hashes wären gefährlicher als der Status quo.
- **Kompensierende Kontrolle:** `affiliate-program.yml` referenziert keine Secrets und läuft nicht auf
  `pull_request_target`; secret-tragende Workflows sind auf `push`/Tags beschränkt (nicht fork-PR-triggerbar).
- **Zieldatum:** Vor nächster Produktionsfreigabe.
- **Verantwortlich:** Repository-Inhaber oder eine CI-Pipeline mit Internetzugriff.

## AFF-009 — App-Links-Zertifikatsverifikation abhängig von Produktionsvariable

- **Grund für Nicht-Behebung:** Kann grundsätzlich nicht aus dem Repository heraus verifiziert werden.
- **Kompensierende Kontrolle:** Regex-Validierung des Fingerprint-Formats bereits im Code
  (`assetlinks.json.js`); bei fehlender/falscher Variable degradiert die App nur zur manuellen
  Chooser-Auswahl statt eines unbemerkten Sicherheitslecks.
- **Zieldatum:** Vor jeder Produktionsfreigabe und danach periodisch.
- **Verantwortlich:** Repository-Inhaber (Cloudflare-Pages-Umgebungskonfiguration).

## AFF-010 — CSP erlaubt `'unsafe-inline'` für script-src

- **Grund für Nicht-Behebung:** Erfordert Restrukturierung aller Affiliate-HTML-Seiten (Auslagerung
  aller Inline-Skripte) und erneute Verifikation der Turnstile-Integration unter einer nonce-/hash-basierten
  CSP — als eigenständige, in sich geschlossene Folgearbeit eingestuft statt in dieser Härtungssitzung
  mitzuerledigen (Risiko einer unvollständigen CSP-Migration, die etwas anderes bricht).
- **Kompensierende Kontrolle:** Die konkrete AFF-001-Lücke, die diese CSP-Schwäche ausgenutzt hätte, ist
  bereits durch HTML-Escaping geschlossen.
- **Zieldatum:** Nächster Frontend-Hardening-Zyklus.
- **Verantwortlich:** Entwicklungsteam.

## AFF-011 — Login-CSRF (Magic-Link-Phishing)

- **Grund für Nicht-Behebung:** Geringe Auswirkung (Dashboard exponiert keine sensiblen Eingabefelder, die
  ein Opfer im falschen Konto preisgeben könnte); Aufwand einer vollständigen Lösung (Login-Bestätigung mit
  Double-Submit) steht in keinem Verhältnis zum begrenzten Schaden.
- **Kompensierende Kontrolle:** Keine zusätzliche.
- **Zieldatum:** Kein festes Datum, in Verbesserungsplan aufgenommen.
- **Verantwortlich:** Entwicklungsteam.
