# Google-Play-Billing-Review vom 7. August 2026

## Ergebnis und Release-Entscheidung

Der auf dem Screenshot sichtbare Zustand war ein schwerer Entitlement-Fehler:
Google Play meldete einen bereits vorhandenen Kauf, während DownloadThat den
Nutzer weiter als Free einstufte und erneut zum Kauf aufforderte. Die App behandelte
`ITEM_ALREADY_OWNED` nur als allgemeinen Fehler und synchronisierte den vorhandenen
Kauf nicht automatisch. Dieser Codepfad ist behoben und automatisiert abgesichert.

Die Änderung ist **noch nicht für Produktion freigegeben**. Vor Freigabe müssen eine
neue `playRelease`-AAB aus diesem Stand und der vollständige Lifecycle auf einem
Internal-Track-Gerät mit License-Tester-Konto geprüft werden. Die vorhandene Datei
`C:\ai\playstore_console\releases\v0.8.5.2\classydl-debug-apk\app-direct-debug.apk`
ist ein älterer Direct-Debug-Build ohne diese Änderungen und ohne Play-Billing-Pfad.

## Was ein Kauf auslöst

DownloadThat ruft den Play-Kaufdialog ausschließlich nach einer Nutzeraktion auf
„Pro holen“ auf. Ein erfolgreiches `launchBillingFlow()` bedeutet nur, dass Google
Play den Kaufdialog geöffnet hat; es ist noch kein Kaufbeleg und schaltet Pro nicht
frei. Der Kaufstatus kommt später über den Play-Callback oder eine Besitzabfrage.

Eine Buchung, die scheinbar nach einem Abbruch erscheint, kann deshalb nicht anhand
der App-Meldung allein als neuer Kauf eingeordnet werden. Geprüft werden müssen der
Zeitpunkt, die GPA-Order-ID, der Status in Play Console und die Google-Belegmail.
Mögliche Erklärungen sind ein schon zuvor abgeschlossener oder verzögert bestätigter
Kauf, ein außerhalb der App abgeschlossener Kauf oder eine Kartenreservierung. Der
Screenshot „Diesen Artikel hast du bereits“ belegt jedenfalls, dass Google das
Konto zu diesem Zeitpunkt bereits als Eigentümer des nicht konsumierbaren Produkts
geführt hat. Die App hätte diesen Besitz wiederherstellen müssen.

Google kann aktive Einmalkauf-Produkte außerdem außerhalb der App im Rahmen seiner
Cart-Abandonment-Funktion anbieten. Deshalb ist eine Prüfung bzw. bewusste
Deaktivierung dieser Play-Console-Funktion Teil des Go-live-Gates.

## Verbindliche Invarianten

1. Ohne bestätigten Play-Status `PURCHASED` wird niemals Pro gewährt.
2. `PENDING`, Abbruch, Netzwerkfehler und ein nur erfolgreich geöffneter Dialog sind
   kein Kauf und kein Entitlement.
3. Vor jedem neuen Kauf wird zuerst geprüft, ob das Konto `pro` bereits besitzt.
4. `ITEM_ALREADY_OWNED` öffnet nie erneut Checkout, sondern startet Restore.
5. Ein Kauf-Token erzeugt idempotent genau eine stabile Lizenz.
6. Unbekannte neue Google-Statuswerte gewähren nichts, widerrufen aber auch keine
   bestehende Lizenz irrtümlich.
7. Nur eine explizit verifizierte Stornierung bzw. ein Widerruf löscht Pro.
8. Native Android-Schicht und eingebettete Python-Schicht verwenden dieselbe
   Installations-ID, damit ein Gerät nicht als zwei Android-Geräte zählt.
9. Ein Callback darf beim WebView-/Login-Start nicht verloren gehen.
10. Mehrfachklicks öffnen höchstens einen aktiven Kauf- oder Restore-Vorgang.

## Umgesetzte Korrekturen

- Besitzabfrage vor jedem `launchBillingFlow()`; keine gecachten `ProductDetails`.
- Automatische Besitzabfrage bei jedem `onResume()` für verlorene Callbacks,
  abgeschlossene Pending-Käufe und Käufe auf einem anderen Gerät.
- Eigene Behandlung von `USER_CANCELED`, `ITEM_ALREADY_OWNED`, temporären Fehlern,
  Pending und unvollständigen Resultaten.
- Bei `ITEM_ALREADY_OWNED` bis zu drei begrenzte Besitzabfragen; auch bei kurz
  verzögertem Play-Cache wird kein zweiter Checkout geöffnet.
- Kauf-/Restore-Sperre in Web- und Nativer Schicht gegen schnelles Hin-und-her-Klicken.
- Gepufferter Native-zu-Web-Callback mit Authentifizierungs-Handshake.
- Gemeinsame, migrationssichere Installations-ID für Native und Python.
- Authentifiziertes lokales Löschen einer widerrufenen Lizenz bei gleichzeitiger
  Erhaltung der Installations-ID.
- Backend-Verifikation von Paket, Produkt und Token; Grant nur für `PURCHASED`;
  serverseitige Bestätigung mit Retry; Token-basierte Idempotenz.
- Unbekannte Google-Statuswerte werden als Upstream-Fehler behandelt, nicht als
  Widerruf. Refund/Revocation bleibt über RTDN und täglichen Abgleich wirksam.

## Kritische Testmatrix vor Produktion

| Fall | Erwartung | Automatisiert | Echter Play-Test |
|---|---|---:|---:|
| Ein sauberer Kauf | genau eine Lizenz, Pro sofort, Bestätigung | ja | offen |
| Kaufdialog abbrechen | kein Pro, klare Abbruchmeldung, keine neue Order | ja (Policy) | offen |
| 20 schnelle Klicks | nur ein aktiver Flow | ja (Vertrag) | offen |
| Bereits gekauft | Restore statt Checkout, Tageslimit verschwindet | ja | offen |
| App-Prozess stirbt nach Zahlung | Restore bei Neustart/Resume | ja | offen |
| Callback vor Web-Login | Ergebnis gepuffert und später zugestellt | ja | offen |
| Pending, später genehmigt | vorher kein Pro, danach automatisch Pro | ja | offen |
| Pending, später abgelehnt | nie Pro | ja | offen |
| Netzwerk weg vor/bei Verifikation | kein falscher Grant/Entzug, späterer Restore | ja | offen |
| Bestätigung vorübergehend 503 | Retry, keine zweite Lizenz | ja | offen |
| Falsches Produkt/Paket | fail closed | ja | offen |
| Unbekannter Google-Status | kein Grant und kein falscher Widerruf | ja | offen |
| Refund/Void/Chargeback | Pro endet in Native und Python | ja (Backend) | offen |
| Refund, dann Neukauf | alter Anspruch bleibt widerrufen, neuer Kauf aktiviert | teilweise | offen |
| Neuinstallation, gleiches Konto | Restore und identischer Lizenzschlüssel | ja (Backend) | offen |
| Zwei Android-Geräte | Gerätepolitik greift, ein Install zählt nicht doppelt | ja | offen |
| Wechsel Play-Konto | nur Besitz des aktiven Play-Kontos wird verwendet | Codepfad | offen |
| Product/Offer regional nicht verfügbar | kein Checkout, klare Fehlermeldung | ja | offen |

## Manuelles Testprotokoll im Internal Track

Für jeden Fall werden App-Version, Testkonto-Alias, Uhrzeit, erwartetes Resultat,
tatsächliches Resultat, GPA-Testorder und Screenshot protokolliert. Keine echten
Zahlungs- oder personenbezogenen Daten werden ins Repository geschrieben.

1. License Tester und Internal-Track-Tester korrekt eintragen; Testkarte sichtbar
   bestätigen. Normale Tester im Testtrack können sonst real belastet werden.
2. Frische Installation: drei Downloads ausführen, Limitdialog öffnen und mit
   „Testkarte, immer genehmigt“ kaufen. Pro muss ohne Neustart aktiv werden.
3. App-Daten behalten, App neu starten, Restore prüfen und 20-mal schnell auf den
   Kauf-/Restore-Bereich tippen. Es darf kein zweiter Checkout erscheinen.
4. Kauf in Play Console refundieren **und widerrufen**; RTDN und anschließend den
   manuellen/täglichen Reconciliation-Pfad separat prüfen.
5. Nach bestätigtem Widerruf einen neuen Testkauf durchführen. Der neue Token muss
   genau eine aktive Lizenz liefern; der alte Token bleibt widerrufen.
6. Slow-Testkarten für Pending-Genehmigung und Pending-Ablehnung verwenden; App
   währenddessen schließen und wieder öffnen.
7. Während der Serververifikation Netzwerk trennen und wiederherstellen; Pro darf
   weder doppelt entstehen noch wegen eines bloßen Transportfehlers gelöscht werden.
8. Auf einem zweiten Android-Gerät mit demselben Play-Konto Restore prüfen und die
   dokumentierte Gerätepolitik verifizieren.
9. Play Console Orders und Testbelege mit den App-Ereignissen abgleichen. Ein
   UI-Abbruch allein ist kein Nachweis für den finanziellen Orderstatus.
10. Cart Abandonment/Merchandising in Play Console bewusst prüfen und für den ersten
    Release deaktivieren, wenn Käufe ausschließlich aus der App heraus gewünscht sind.

## Harte Release-Gates

- `playRelease` aus exakt diesem Commit kompiliert und als Internal-AAB hochgeladen.
- Android-Unit-Tests und beide Flavors kompilieren mit vorhandenem Android SDK.
- Alle offenen Spalten „Echter Play-Test“ oben sind protokolliert bestanden.
- Cloudflare-Rate-Limit für `POST /api/play/purchases/verify` ist produktiv aktiv.
- RTDN, täglicher Reconciliation-Job und Alerting sind live verifiziert.
- Die konkrete betroffene Google-Order ist in Play Console geklärt und bei Bedarf
  über Google Play erstattet; App-Code kann keine Google-Abbuchung selbst zurückbuchen.

## Offizielle Referenzen

- https://developer.android.com/google/play/billing/integrate
- https://developer.android.com/google/play/billing/errors
- https://developer.android.com/google/play/billing/security
- https://developer.android.com/google/play/billing/test
- https://support.google.com/googleplay/android-developer/answer/1153481
