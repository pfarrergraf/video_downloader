# Business Logic & Fraud Abuse Cases — Affiliate Program

Für jeden Fall: Mechanismus, geprüfter Code, Ergebnis.

## Eigenkäufe (Self-Referral)

**Mechanismus:** Partner kauft über den eigenen Link. **Kontrolle:**
`postProcessAffiliateCheckout()` vergleicht `normalizeEmail(session.customer_details.email)` mit der
registrierten Partner-E-Mail; bei Übereinstimmung wird die Provision auf `rejected`/`self_referral` gesetzt,
die Lizenz bleibt aber gültig (Kunde behält sein Produkt). **Ergebnis:** Kontrolle vorhanden und korrekt,
kein Finding. **Lücke:** Ein Partner mit einer *zweiten* E-Mail-Adresse (nicht die registrierte) umgeht diese
Prüfung vollständig — das ist eine bekannte, praktisch nicht vollständig schließbare Grenze jedes
Affiliate-Systems ohne Identitätsprüfung; dokumentiert als Restrisiko, keine Code-Änderung möglich ohne KYC
(außerhalb des Scopes).

## Käufer-Partner-Absprache

**Mechanismus:** Freund kauft über Partnerlink, Partner erhält Provision, teilen sich den "Rabatt" (es gibt
in v1 aber **keinen** Kundenrabatt — HANDOVER §2.1). **Ergebnis:** Da kein finanzieller Vorteil an den Käufer
weitergegeben wird, ist der wirtschaftliche Anreiz für Absprachen strukturell geringer als bei
rabattbasierten Programmen; verbleibendes Risiko ist reine Provisionsabsprache, adressiert durch
Reconciliation/Anomalieerkennung (operativ, siehe HANDOVER §5.5).

## Cookie Stuffing (Web)

**Mechanismus:** Massenhaftes Setzen des `dt_affiliate_click`-Cookies ohne echten Nutzerklick. **Kontrolle:**
`recordAffiliateClick()` wird nur serverseitig bei tatsächlichem `GET /p/<slug>`-Aufruf ausgelöst; ein
Angreifer müsste den Browser des Opfers tatsächlich zu dieser URL navigieren lassen (z. B. per verstecktem
`<img>`/`<iframe>` auf einer fremden Seite). **Ergebnis:** Technisch möglich (klassisches Cookie-Stuffing),
aber durch **Last-Touch** (nicht First-Touch) strukturell entschärft — der letzte echte Klick vor dem Kauf
gewinnt, sodass ein früher gestuffter Cookie durch jeden späteren legitimen Klick überschrieben wird. Kein
Code-Fix in diesem Pass; Erkennung über Klick-zu-Conversion-Rate-Anomalien empfohlen (operativ).

## Cookie Stuffing (Android) — siehe AFF-002

Das mobile Äquivalent zu Cookie Stuffing; ausführlich in `PENETRATION_TEST_RESULTS.md` behandelt.

## Partnercode Guessing / Hijacking

**Mechanismus:** Erraten fremder Partnercodes, um sie im Checkout einzugeben und die Provision "kurzzeitig"
umzuleiten. **Kontrolle:** `normalizePartnerCode()` + `isReservedPartnerCode()` verhindern reservierte Codes;
Codes sind aber **keine Geheimnisse** (sie sind das Marketing-Instrument des Partners und öffentlich
weitergegeben) — Erraten hat daher keinen Mehrwert gegenüber einfachem Abtippen eines öffentlich beworbenen
Codes. Kein Finding; das ist inhärent zum Geschäftsmodell (Codes sind bewusst öffentlich).

## Nachträgliche Attribution

**Mechanismus:** Ein Partnercode wird erst nach Kaufabschluss eingegeben, um rückwirkend eine Provision zu
erhalten. **Kontrolle:** `resolveAffiliateAttribution()` wird ausschließlich zum Zeitpunkt der
Checkout-Session-Erstellung aufgerufen (`create-checkout.js`), nicht nachträglich; es gibt keinen Endpunkt,
der eine bereits abgeschlossene Zahlung nachträglich mit einem Partner verknüpft. **Ergebnis:** Kein Finding.

## Doppelte Conversions / Webhook-Replay

Siehe AFF-003 (Race Condition bei doppelter Zustellung) — behoben. Zusätzlich bestätigt: `INSERT OR IGNORE`
mit `UNIQUE(stripe_checkout_session_id)` auf `affiliate_commissions` verhindert eine zweite Provisionszeile
für dieselbe Checkout-Session unabhängig vom Race-Fix.

## Webhook Out-of-Order Delivery

**Szenario:** `charge.dispute.closed` (won) trifft **vor** `charge.dispute.created` ein (theoretisch durch
Netzwerklatenz möglich). **Kontrolle:** `handleAffiliateDisputeClosed()` prüft
`commission.status !== 'reversed' || !reversal_reason.startsWith('stripe_dispute')` und bricht sonst mit
`{restored:false, reason:"no reversible disputed commission"}` ab — eine "won"-Nachricht ohne vorherige
Reversierung hat keinen Effekt. **Ergebnis:** Fail-closed korrekt, kein Finding.

## Parallele Checkouts / parallele Refunds

Siehe AFF-003. Zusätzlich geprüft: `approveEligibleCommissions()` verwendet optimistische Nebenläufigkeit
(`version`-Spalte, bis zu 4 Wiederholungsversuche) bei der Zuweisung der Verkaufsnummer — ein Konflikt führt
zu `deferred_concurrency`, nie zu einer doppelt vergebenen Verkaufsnummer (durchgesetzt durch
`UNIQUE(affiliate_id, qualified_sale_number)` in der Migration als letzte Verteidigungslinie).

## Tier-Manipulation / Umgehung des 50-EUR-Limits

**Kontrolle:** `commissionForSaleNumber()` ist eine reine, deterministische Funktion serverseitig; der Client
hat keinen Einfluss auf `saleNumber` oder `commission_cents` (DB-CHECK-Constraint erzwingt zusätzlich
`commission_cents IN (200,250,300,350,400)`). `PAYOUT_MINIMUM_CENTS = 5000` wird in `prepareAffiliatePayout()`
hart geprüft, kein clientseitiger Parameter kann dies umgehen. **Ergebnis:** Kein Finding.

## Manipulation negativer Salden / Teil-Refund-Missbrauch / Dispute-Restore-Missbrauch

Siehe AFF-003 (die einzige gefundene reale Lücke in diesem Bereich, behoben). Ansonsten bestätigt: Teil-Refund
reduziert `amount_total_cents` auf den tatsächlichen Stripe-Nettobetrag (`syncAffiliateRefundRevenue`), voller
Refund storniert Lizenz und Provision.

## Auszahlung nach Partnersperre

**Kontrolle:** `prepareAffiliatePayout()` prüft `WHERE id = ? AND status = 'active'` auf der
`affiliates`-Tabelle — ein suspendierter/abgelehnter Partner kann keine neue Auszahlung mehr vorbereitet
bekommen. Bereits *vorbereitete* (aber noch nicht freigegebene) Auszahlungen eines danach gesperrten Partners
würden aber **nicht automatisch storniert** — `approveAffiliatePayout`/`markAffiliatePayoutPaid` prüfen den
Affiliate-Status nicht erneut. **Neuer Beobachtungspunkt (nicht als eigenes AFF-ID geführt, da rein
prozessual):** Empfehlung, dass der Admin-Prozess vor jeder Freigabe manuell prüft, ob der Partner seit
Vorbereitung gesperrt wurde — in `PRODUCTION_SECURITY_CHECKLIST.md` aufgenommen.

## Integer-, Rundungs- und Extremwertfehler

Bestätigt durch bestehende und neue Tests: `expectedCommissionForCount()` iterativ gegen
`commissionForSaleNumber()`-Summe für Werte bis 10.000 geprüft (`affiliate_finance.test.mjs`); keine
Fließkommaarithmetik im gesamten Provisions-/Auszahlungspfad (ausschließlich Integer-Cents).
