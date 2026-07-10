# Production Security Checklist — Affiliate Program

Konsolidiert HANDOVER.md §6/§12 mit den Ergebnissen dieser Prüfung. **Kein Punkt hier ersetzt eine
schriftliche Freigabe des Repository-Inhabers.**

## Durch diese Prüfung erledigt / verifiziert

- [x] Keine offenen P0/P1-Findings im Code (AFF-001 behoben und retestet).
- [x] Absolute Auszahlungsobergrenzen mathematisch nachvollzogen und regressionsgetestet.
- [x] Exakte 5,00-%-Grenzsemantik explizit getestet und dokumentiert.
- [x] Race Conditions bei doppelter Webhook-Zustellung identifiziert, behoben, reproduziert und retestet.
- [x] Rate Limiting auf Partner-/Admin-Auth-Endpunkten ergänzt.
- [x] Secret-Scan-Abdeckung um Turnstile-Muster erweitert.
- [x] Stacktrace-Leak in Webhook-Fehlerantwort entfernt.
- [x] Totes Code-Duplikat mit latentem Bug entfernt.
- [x] Android-Berechtigungen erneut verifiziert: keine Abweichung von den vier freigegebenen Berechtigungen.
- [x] SBOM (CycloneDX) für die Python-Abhängigkeiten erzeugt (`security/sbom.cdx.json`).
- [x] Vollständige bestehende Test-Suite nach allen Änderungen erneut grün (201 Python-Tests,
      8 Node-Tests, Node-Syntaxprüfung aller Cloudflare Functions).

## Vor Produktionsaktivierung weiterhin zwingend erforderlich (nicht durch diese Sitzung leistbar)

- [ ] **GitHub Actions auf Commit-SHA pinnen** (AFF-005) — erfordert Verifikation echter Hashes mit
      Internetzugriff; Dependabot `github-actions`-Updates aktivieren.
- [ ] **`ANDROID_CERT_SHA256` in Cloudflare-Produktionsumgebung verifizieren** (AFF-009) — `curl
      https://<domain>/.well-known/assetlinks.json` muss ein nicht-leeres, korrektes JSON liefern, für
      **beide** Produktionsdomains.
- [ ] `wrangler`-Version in `deploy-pro-website.yml` fest pinnen statt `npx -y wrangler@3`.
- [ ] Alle in HANDOVER.md §5 gelisteten Secrets/Variablen in Cloudflare setzen und verifizieren.
- [ ] Vollständiger Stripe-Testmodus-Durchlauf: sofortige Kartenzahlung, SEPA erfolgreich/fehlgeschlagen,
      Voll-/Teil-Refund, Dispute erstellt/verloren/gewonnen, Webhook-Duplikate/-Reihenfolge (HANDOVER §6.3).
- [ ] Backup/Restore praktisch gegen echte Cloudflare-D1-Instanz getestet (`BACKUP_RESTORE_TEST.md`).
- [ ] PCI-SAQ-Kategorie verbindlich mit Stripe klären (`PCI_SCOPE_ASSESSMENT.md`).
- [ ] Rechts-/Datenschutz-/Steuerprüfung durch qualifizierte externe Stellen (HANDOVER §5.6).
- [ ] Cloudflare Access oder gleichwertiger Zusatzschutz für `/partner-admin.html` erwägen (Verteidigung in
      der Tiefe zusätzlich zur Anwendungs-Session, insbesondere da nur ein einzelnes Admin-Konto existiert).
- [ ] Automatisierte Alarmierung bei `payout_frozen`-Wechsel/Integritätsbruch einrichten (aktuell rein
      manuell sichtbar).
- [ ] Automatisierten Aufräumprozess für abgelaufene Klicks/Tokens/Sessions einrichten
      (`PRIVACY_AND_DATA_RETENTION_REVIEW.md`).
- [ ] CSP von `'unsafe-inline'` auf nonce-/hash-basiert umstellen (AFF-010, Verteidigung in der Tiefe).
- [ ] Schriftliche Produktionsfreigabe des Repository-Inhabers dokumentieren.

## Automatisches No-Go (aus HANDOVER §12, unverändert gültig)

Auszahlungssperre aktiv · Reconciliation/Integrity Gate nicht `ok` · offenes Critical-/High-Finding ·
Produktionsbackup nicht verifiziert · Stripe-Webhooks nicht vollständig getestet · Secrets fehlen/sind im
Repo auffindbar · unklarer PCI-Scope · keine verantwortliche Person für Incidents/Auszahlungen · keine
kontrollierte Rückfallmöglichkeit.
