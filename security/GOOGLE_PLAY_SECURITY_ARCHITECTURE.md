# Google Play Security Architecture

Stand: 2026-07-14. Dieses Dokument ist die Soll-Architektur für den produktiven
Vertrieb. Ältere Stripe-/Affiliate-Prüfberichte bleiben historische Evidenz,
beschreiben aber nicht mehr das aktive System.

## Vertrauensgrenzen und Assets

```text
Play-App -> Google Play Billing -> Play Developer API
    | purchaseToken                    |
    +------> Cloudflare Functions <----+ RTDN via Pub/Sub/OIDC
                 |       |
                 |       +-> D1: Lizenz + verschlüsselter Token/Token-Hash
                 +-> POST-Lizenzvalidierung (Play, Direct APK, Windows)

Google financial reports -> monthly workflow -> retained private GCS archive
                                           +-> age-encrypted local mirror
```

Schützenswerte Assets sind Purchase Tokens, stabile Lizenzschlüssel, die
Token-zu-Lizenz-Zuordnung, Google-Service-Account-Zugang, RTDN-Authentizität,
Release-Schlüssel sowie unveränderte Finanzoriginale.

## Verbindliche Kontrollen

- Nur die serverseitig über die Play Developer API bestätigte Kombination aus
  Paket `de.classydl.app`, Produkt `pro` und Status `PURCHASED` darf Pro
  aktivieren. Client-Payload und RTDN allein sind nie Zahlungswahrheit.
- Der SHA-256-Hash des Purchase Tokens ist eindeutig. Der Token selbst wird mit
  AES-GCM verschlüsselt; Schlüsselmaterial liegt nur als Runtime-Secret vor.
- Doppelte Kauf-/RTDN-Zustellung ist idempotent und liefert dieselbe Lizenz.
- Käufe werden nach erfolgreicher Verifikation serverseitig bestätigt. Pending,
  storniert, unbekannt oder nicht verifizierbar bleibt fail-closed.
- OIDC des Pub/Sub-Pushs wird auf Signatur, Issuer, Audience und erwartetes
  Service-Account-Subject geprüft. Danach wird der Kaufstatus erneut bei Google
  gelesen.
- Refund/Void/Revoke deaktiviert Kauf und Lizenz. Eine tägliche Reconciliation
  korrigiert verpasste Nachrichten.
- Neue Clients senden Lizenzschlüssel nur per POST. Der alte GET-Endpunkt ist
  zeitlich begrenzte Kompatibilität und antwortet mit Deprecation-Headern.
- Play-Entitlements haben höchstens 72 Stunden Offline-Grace nach der letzten
  erfolgreichen Serverprüfung; Free-Funktionen bleiben offline verfügbar.

## Release- und Betriebs-Gates

- Play-AAB und Direct-APK: identische Paket-ID, App-Signing-Key und monotone
  Versionsnummer; CI nutzt ausschließlich den separaten Upload-Key.
- Billing-Code existiert nur im Play-Flavor; Direct enthält keinen aktiven Kauf.
- Kein Produktionsrelease ohne Signaturvergleich, 16-KiB-Native-Library-Prüfung,
  SBOM, SHA-256, echten Kauf/Restore/Refund, RTDN und Reconciliation.
- Automatischer Play-Installer-Schutz bleibt aus, solange Direct APK unterstützt
  wird.
- Finanzbucket ist privat, uniform, versioniert und mit zehnjähriger Retention.
  Das irreversible Lock wird nur nach Restore-Test und expliziter Owner-Freigabe
  gesetzt.

## Bewusst verbleibende Risiken

- Ein technisch versierter Gerätebesitzer kann lokale Pro-Prüfungen umgehen; das
  Backend darf daraus keine neue oder weiterverwendbare Lizenz erzeugen.
- Google Play und Cloudflare sind Verfügbarkeitsabhängigkeiten. Ausfälle sperren
  neue Käufe fail-closed; Free und die zeitlich begrenzte Grace bleiben nutzbar.
- Content-Policy-/Urheberrechtsrisiko einer allgemeinen Downloader-App bleibt eine
  Rechts- und Store-Policy-Frage, keine durch Billing lösbare Sicherheitsfrage.
