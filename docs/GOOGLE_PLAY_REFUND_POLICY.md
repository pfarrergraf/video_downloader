# Google-Play-Erstattungsrichtlinie

## Aktiver Produktvertrag

> Google Play verwaltet Zahlungen und berechtigte Erstattungen. Eine Erstattung
> oder ein Widerruf deaktiviert Pro.

DownloadThat nimmt keine Erstattungsanfragen in der App oder über eine eigene API
entgegen, erstattet keine Google-Play-Order automatisch und sperrt spätere Käufe
nicht anhand einer eigenen Refund-Historie. Nutzer verwenden die von Google Play
bereitgestellten Support- und Erstattungswege. Preise werden ausschließlich als
aktueller lokaler Google-Play-Preis dargestellt; es gibt keinen fest codierten
Preis und keine Erstattungsgarantie.

## Entitlement-Revoke

Der Backend-Kaufstatus bleibt die Zahlungswahrheit. Pro darf nur enden, wenn
Google einen Refund, Void, Cancel oder Revoke bestätigt:

1. Eine authentifizierte RTDN wird über Google OIDC geprüft und der Kaufstatus
   erneut bei Google gelesen.
2. Die serverseitige Reconciliation korrigiert verpasste Benachrichtigungen.
3. Transiente Netzwerk-, OAuth- oder Google-API-Fehler entziehen Pro nicht.

Historische D1-Migrationen, Refund-Datensätze und Finanzexporte werden aus Audit-
und Aufbewahrungsgründen nicht gelöscht. Sie sind kein aktiver Runtime-Pfad.

## Externe Release-Prüfung

Vor Produktion sind Play-seitige Erstattung/Widerruf plus RTDN-Revoke sowie der
separate Reconciliation-Fallback mit einer Internal-Track-Testorder real zu
prüfen. Bis dahin bleibt dieses Verhalten `UNVERIFIED`; es werden keine echten
Käufe oder Erstattungen durch automatisierte Repository-Tests ausgelöst.
