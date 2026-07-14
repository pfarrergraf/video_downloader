# Production Security Checklist — Historical Affiliate Program

> This checklist preserves the completed affiliate audit. It is not a current
> go-live checklist. Use `docs/GOOGLE_PLAY_OWNER_CHECKLIST.md` and
> `GOOGLE_PLAY_SECURITY_ARCHITECTURE.md` for the Google-Play-first launch.

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

- [x] **GitHub Actions auf Commit-SHA gepinnt** (AFF-005); Regressionstest verhindert
      eine Rückkehr zu beweglichen Tags.
- [ ] **`ANDROID_CERT_SHA256` in Cloudflare-Produktionsumgebung verifizieren** (AFF-009) — `curl
      https://<domain>/.well-known/assetlinks.json` muss ein nicht-leeres, korrektes JSON liefern, für
      **beide** Produktionsdomains.
- [x] `wrangler`-Version in `deploy-pro-website.yml` exakt gepinnt.
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
- [x] CSP `script-src` ohne `'unsafe-inline'`; Initialisierung in externe Datei verschoben (AFF-010).
- [ ] Schriftliche Produktionsfreigabe des Repository-Inhabers dokumentieren.

## Automatisches No-Go (aus HANDOVER §12, unverändert gültig)

Auszahlungssperre aktiv · Reconciliation/Integrity Gate nicht `ok` · offenes Critical-/High-Finding ·
Produktionsbackup nicht verifiziert · Stripe-Webhooks nicht vollständig getestet · Secrets fehlen/sind im
Repo auffindbar · unklarer PCI-Scope · keine verantwortliche Person für Incidents/Auszahlungen · keine
kontrollierte Rückfallmöglichkeit.
