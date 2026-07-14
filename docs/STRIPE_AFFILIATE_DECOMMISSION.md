# Stripe- und Affiliate-Stilllegung

Status: Code-seitig vorbereitet; externe Prüfungen und Secret-Widerruf sind Owner-Gates.

## Zwingende Reihenfolge

1. Remote-D1 und Stripe-Testdaten exportieren, SHA-256 bilden und im privaten
   Stilllegungsnachweis ablegen.
2. Abfragen, ob Lizenzen, Zahlungen, Refunds, Partner oder Provisionen außerhalb
   eindeutig markierter Testdaten existieren. Bei einem unerwarteten Datensatz:
   **Abbruch**, nichts löschen, Owner informieren.
3. Erst nach dokumentiertem Null-Echtkunden-Befund Checkout, Webhook, Refund,
   Session-Delivery und Partner/Admin-Routen aus dem Deployment entfernen.
4. Stripe-, Resend-, Turnstile- und Affiliate-Secrets in GitHub, Cloudflare und
   den Anbieter-Dashboards widerrufen, sofern sie keinen anderen Zweck haben.
5. Decommission-Bericht mit Exporthash, Prüfabfragen, Datum und handelnder Person
   zehn Jahre im Finanzarchiv ablegen. Git-Historie bleibt erhalten.

Der Repository-Umbau kann Schritt 1/2 nicht gegen Live-Systeme beweisen. Deshalb
bleibt ein Deployment bis zur ausgefüllten Owner-Checkliste fail-closed; es gibt
keinen automatischen Löschlauf für unbekannte Kundendaten.
