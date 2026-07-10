# Incident Response Plan (Draft) — Affiliate Program

Erstentwurf im Rahmen dieser Sicherheitsprüfung. Ersetzt keinen unternehmensweiten IR-Prozess; adressiert
die in HANDOVER §5.7/§8.8 geforderten Runbooks für dieses Feature.

## Auslöser / Erkennungssignale

- `affiliate_controls.payout_frozen = 1` unerwartet gesetzt (durch Reconciliation oder Integrity Gate).
- `affiliate_integrity_checks`/`affiliate_reconciliation_snapshots` melden `status = 'blocked'`.
- Hash-Ketten-Bruch (`verifyLedgerChain`/`verifyAuditChain`/... meldet `ok:false`).
- Ungewöhnliche Conversion-/Refund-/Dispute-Muster eines einzelnen Partners (aktuell **keine automatisierte
  Alarmierung** — HANDOVER §5.5/§5.7, weiterhin offen; manuelle Admin-Sichtung nötig).
- Verdacht auf kompromittiertes Admin-Konto (E-Mail-Zugang zu `AFFILIATE_ADMIN_EMAIL`).

## Runbook 1 — Auszahlungssperre (payout_frozen)

1. Admin öffnet `/partner-admin.html`, prüft `freeze_reason` und die letzte `affiliate_reconciliation_snapshots`-Zeile.
2. **Nicht** manuell entsperren, ohne die Ursache in `reasons_json` verstanden zu haben.
3. Ursache anhand der unveränderlichen Snapshot-/Audit-Kette rekonstruieren (append-only, daher
   forensisch zuverlässig).
4. Korrektur ausschließlich über kompensierende Buchungen (nie UPDATE/DELETE — DB-Trigger verhindern dies
   ohnehin technisch).
5. Erneuten Reconciliation- + Integrity-Gate-Lauf anstoßen (`POST /api/admin/reconcile`); erst bei `ok`
   Auszahlungen fortsetzen.

## Runbook 2 — Kompromittiertes Partnerkonto

1. Admin setzt `affiliates.status = 'suspended'` (verhindert neue Auszahlungsvorbereitung sofort,
   siehe `prepareAffiliatePayout`'s `WHERE status = 'active'`-Filter).
2. Bereits laufende `prepared`/`approved`-Payouts dieses Partners manuell prüfen, bevor sie freigegeben/
   als bezahlt gebucht werden (siehe Beobachtung in `BUSINESS_LOGIC_ABUSE_CASES.md` — kein automatischer
   Stopp bei nachträglicher Sperrung).
3. Falls bereits ausgezahlt: Clawback über `negative_balance_cents` bei nachgewiesenem Betrug/Fehlverhalten.

## Runbook 3 — Kompromittierte Admin-E-Mail

Bislang **kein definierter Prozess** (HANDOVER §5.4, offen). Minimal-Sofortmaßnahme mit den vorhandenen
Mitteln: `AFFILIATE_PROGRAM_ENABLED=false` setzen (globaler Kill-Switch, deaktiviert alle Partner-/Admin-
Routen sofort, siehe `affiliateProgramEnabled()`-Check in jeder Route), dann `AFFILIATE_ADMIN_EMAIL`
und alle offenen `affiliate_admin_tokens` invalidieren (z. B. durch Ändern der Env-Variable — bestehende
Tokens sind an die alte E-Mail gebunden und würden `normalizeEmail(row.email) !== normalizeEmail(env.AFFILIATE_ADMIN_EMAIL)`
fehlschlagen). Empfehlung: formellen Prozess mit zweiter Kontaktperson definieren.

## Runbook 4 — Stripe-/Cloudflare-/Resend-Ausfall

- **Stripe nicht erreichbar:** `runReconciliation()` schlägt fehl und setzt `payout_frozen=1` automatisch
  (Fail-Closed, siehe `catch`-Block in `runReconciliation`). Keine Auszahlung möglich, bis Stripe wieder
  erreichbar ist und ein erfolgreicher Abgleich läuft. Kein manuelles Eingreifen zur Absicherung nötig.
- **Resend nicht erreichbar:** Login/Registrierung/Verifizierung schlagen fehl (`sendTransactionalEmail`
  wirft in Produktion einen Fehler). Kein Datenintegritätsrisiko, reiner Verfügbarkeitsausfall.
- **Cloudflare D1 nicht erreichbar:** Vollständiger Funktionsausfall des Programms; kein Datenverlustrisiko
  durch dieses Feature selbst (D1s eigene Verfügbarkeits-/Backup-Garantien liegen außerhalb des Scopes).

## Notfallabschaltung (Kill Switch)

`AFFILIATE_PROGRAM_ENABLED=false` deaktiviert **sofort** alle Partner-Registrierungs-, Login-, Checkout- und
Admin-Routen (jede Route prüft dies als ersten Schritt) und lässt den bestehenden Lizenz-/Zahlungspfad ohne
Affiliate-Zuordnung unverändert weiterlaufen (Fallback bereits im Frontend vorhanden, siehe
`docs/AFFILIATE_PROGRAM_IMPLEMENTATION.md` §Rollback).

## Offene organisatorische Punkte (nicht durch Code lösbar)

- Kein dediziertes Security-Kontakt-/Vulnerability-Disclosure-Postfach dokumentiert.
- Keine automatisierte Alarmierung (E-Mail/Slack/PagerDuty) bei `payout_frozen`-Wechsel oder
  Integritätsbruch — aktuell rein manuell durch Admin-Login sichtbar.
- Kein Tabletop-Incident-Exercise durchgeführt (siehe HANDOVER §8.8) — außerhalb des Mandats einer
  Code-Sicherheitsprüfung, erfordert Beteiligung des Betriebsteams.
