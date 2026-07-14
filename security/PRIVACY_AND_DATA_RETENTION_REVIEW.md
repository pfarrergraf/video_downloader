# Privacy & Data Retention Review — Historical Affiliate Program

> Historical evidence only. Affiliate collection is being removed. Current
> Play purchase data is limited to provider identifiers, encrypted Purchase
> Tokens, token hashes, status/timestamps and the linked license. Financial
> originals are retained separately under the controls in
> `docs/GOOGLE_PLAY_OPERATIONS.md`.

Technische Bewertung; **keine anwaltliche Datenschutzfreigabe** (HANDOVER §9.6).

## Dateninventar

| Datum | Tabelle | Personenbezug | Minimierung |
|---|---|---|---|
| Klick-IP | `affiliate_clicks.ip_hash` | Ja (indirekt, gehasht) | `SHA-256(REFERRAL_HASH_SALT:IP)` — Rückrechnung ohne Salt praktisch unmöglich |
| User-Agent | `affiliate_clicks.user_agent_hash` | Schwach | Gleiches Verfahren |
| Partner-E-Mail/Name/Land | `affiliates.*` | Ja, direkt | Notwendig für Vertragsbeziehung (Partnerprogramm-Teilnahme) |
| Käufer-E-Mail | `licenses.email` (bestehende Tabelle, nicht neu) | Ja, direkt | Wird **nicht** an Partner/Admin-Affiliate-UI weitergegeben (bestätigt) |
| Android Referral-Slug + Zeitstempel | SharedPreferences (Gerät) | Nein (nur öffentlicher Slug) | Explizit datenminimal designed |

## Zweckbindung

- Klick-Hashes: ausschließlich zur 180-Tage-Attributionsprüfung, kein Tracking-/Profiling-Zweck ersichtlich.
- Partnerdaten: ausschließlich zur Vertragsabwicklung (Registrierung, Auszahlung, Kommunikation).

## Löschfristen

**Lücke (bestätigt, bereits in HANDOVER §5.1 als offen geführt):** Kein automatisierter Aufräumprozess für
abgelaufene `affiliate_clicks` (nach 180 Tagen), abgelaufene `affiliate_auth_tokens`/`affiliate_admin_tokens`
(nach 20 Minuten) oder verwendete Sessions im Code gefunden — diese Zeilen bleiben unbegrenzt in D1
bestehen. Dies ist kein akutes Sicherheitsrisiko (Daten sind gehasht/kurzlebig in ihrer *Gültigkeit*, auch
wenn sie physisch bestehen bleiben), aber eine Datenschutz-/Datenminimierungslücke im Sinne der
Aufbewahrungspflicht. Empfehlung: periodischer Cron/D1-Job, der abgelaufene Zeilen löscht.

## Betroffenenrechte

Kein technischer Prozess für Auskunft/Löschung eines Partners im Code gefunden (z. B. kein
"Konto löschen"-Endpunkt). Organisatorisch zu definieren (HANDOVER §5.6, offen).

## Drittlandtransfer / Auftragsverarbeiter

Stripe, Resend, Cloudflare (inkl. Turnstile) sind faktische Auftragsverarbeiter. Verträge/Standorte/
Garantien liegen außerhalb des Code-Scopes dieser Prüfung (HANDOVER §5.6, offen).

## Pseudonymisierung/Hashing — bestätigt korrekt umgesetzt

`REFERRAL_HASH_SALT` wird konsistent für IP/User-Agent-Hashing verwendet; ohne den Salt (ein Secret) ist
keine Rückrechnung auf die Original-IP möglich. Dies ist eine sinnvolle technische Maßnahme im Sinne von
Art. 32 DSGVO, ersetzt aber keine rechtliche Bewertung, ob eine DSFA (Datenschutz-Folgenabschätzung)
erforderlich ist (HANDOVER §5.6, offen — durch Rechtsberatung zu klären).
