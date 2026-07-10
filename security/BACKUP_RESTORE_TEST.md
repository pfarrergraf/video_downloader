# Backup & Restore — Plan und lokale Verifikation

## Was in dieser Sitzung geprüft werden konnte

Cloudflare D1 selbst (Snapshot-/Export-Mechanismus, tatsächliche Produktions-RPO/RTO) liegt außerhalb des
Zugriffs dieser Sitzung (keine Produktions- oder Staging-Cloudflare-Umgebung angebunden). Stattdessen wurde
lokal verifiziert, was **aus dem Code heraus** die Wiederherstellbarkeit und Integrität nach einem Restore
bestimmt:

### 1. Migrationen sind idempotent-additiv und reproduzierbar

`tests/test_affiliate_program.py::test_affiliate_migrations_apply_and_seed_fail_closed_control` wendet
`schema.sql` + alle `migrations/0002`–`0009` gegen eine **frische** In-Memory-SQLite-Datenbank an und
verifiziert, dass alle erwarteten Tabellen entstehen und `affiliate_controls` mit `payout_frozen=1` startet
(Fail-Closed-Default nach jeder Neuanlage/Restore-auf-leere-DB).

### 2. Datenintegrität nach (simuliertem) Restore ist über die Hash-Ketten nachweisbar

Da alle vier Nachweisketten (`affiliate_ledger`, `affiliate_audit_log`,
`affiliate_reconciliation_snapshots`, `affiliate_integrity_checks`) hash-verkettet und append-only sind,
lässt sich nach jedem Restore aus einem Backup **unabhängig von Cloudflare-Mechanismen** verifizieren, ob
der wiederhergestellte Datenstand vollständig und unverändert ist: `runIntegrityGate()` liest alle vier
Ketten neu ein und vergleicht jede Zeile gegen ihren erwarteten Hash. Ein Restore aus einem
**unvollständigen** Backup (z. B. abgeschnittene Kette) würde `broken_previous_hash_at:<id>` melden und
sofort die globale Auszahlungssperre auslösen — genau das gewünschte Fail-Closed-Verhalten nach einer
Wiederherstellung.

### 3. Reconciliation nach Restore erkennt Drift gegenüber Stripe

Nach einem Restore aus einem älteren Backup (z. B. durch Datenverlust nach einem Vorfall) würde
`runReconciliation()` die lokale DB gegen die **Live-Stripe-Realität** abgleichen — jede Lücke zwischen dem
wiederhergestellten Stand und tatsächlich seither erfolgten Zahlungen würde als Abweichung erkannt und bei
Überschreiten von 5,00 % die Sperre auslösen, statt stillschweigend mit veralteten Daten weiterzuarbeiten.

## Was NICHT geprüft werden konnte (erfordert Produktionszugriff)

- Tatsächlicher `wrangler d1 export`/Import-Zyklus gegen eine echte Cloudflare-D1-Instanz.
- Tatsächliches RPO/RTO (abhängig von Cloudflares D1-Backup-Frequenz und Restore-Dauer, nicht Teil dieses
  Codes).
- Verhalten bei einem **teilweisen** Cloudflare-D1-Ausfall (nicht simulierbar ohne echte Infrastruktur).

## Empfohlener Praxistest vor Produktionsfreigabe (aus HANDOVER §6.5, weiterhin verbindlich)

1. D1-Produktions-/Staging-Backup erstellen und Export verifizieren.
2. In eine separate Staging-D1-Instanz wiederherstellen.
3. `AFFILIATE_PROGRAM_ENABLED=false` setzen, Feature testweise aktivieren.
4. `runIntegrityGate()` und `runReconciliation()` gegen die wiederhergestellte Instanz ausführen und `ok`
   verifizieren.
5. Ergebnis in diesem Dokument nachtragen (Datum, Snapshot-ID, Integrity-Check-ID, Ergebnis).

**Status:** Plan vollständig, praktische Durchführung gegen echte Cloudflare-Infrastruktur steht aus
(explizit außerhalb des Mandats dieser Sitzung, siehe HANDOVER §7.2 — "Änderungen direkt in Produktion"
und "Migrationen auf der Produktivdatenbank" erfordern zusätzliche ausdrückliche Freigabe).
