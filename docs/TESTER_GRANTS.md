# Owner- und Tester-Schlüssel

DownloadThat unterstützt neben gekauften Lizenzen serverseitige manuelle Grants.
Der Rohschlüssel wird nur beim Erstellen einmal angezeigt; in D1 liegt ausschließlich
sein SHA-256-Hash. Ein Grant hebt das Tageslimit auf, behält aber die vorhandene
Gerätebindung pro Plattform bei.

## Einmalige Einrichtung

1. Einen langen zufälligen Admin-Token lokal erzeugen und sicher aufbewahren:

   ```powershell
   $bytes = [byte[]]::new(48)
   [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
   $adminToken = [Convert]::ToBase64String($bytes)
   ```

2. Den Wert als Cloudflare-Pages-Secret `TESTER_GRANTS_ADMIN_TOKEN` setzen und
   zusätzlich als gleichnamiges GitHub-Secret hinterlegen. Danach den Website-
   Workflow erneut ausführen, damit das Secret in die Pages Functions gelangt.

## Schlüssel erstellen

Im Repository aus PowerShell:

```powershell
pwsh -File scripts/create_tester_grant.ps1 -AdminToken $adminToken -Label "Owner" -GrantType owner
pwsh -File scripts/create_tester_grant.ps1 -AdminToken $adminToken -Label "Tester Alice" -GrantType tester -ExpiresInDays 14
```

Die Ausgabe enthält den Schlüssel genau einmal. Er sollte über einen sicheren
Kanal an die betreffende Person weitergegeben und nicht in Tickets, Logs oder
Screenshots gespeichert werden. Tester-Grants verfallen automatisch; Owner-Grants
haben standardmäßig kein Ablaufdatum.

## Widerrufen und prüfen

Die Liste enthält niemals Rohschlüssel:

```powershell
$headers = @{ Authorization = "Bearer $adminToken" }
Invoke-RestMethod https://downloadthat.app/api/admin/tester-grants -Headers $headers
```

Widerruf:

```powershell
$body = @{ action = "revoke"; id = "GRANT-ID-AUS-DER-LISTE" } | ConvertTo-Json
Invoke-RestMethod https://downloadthat.app/api/admin/tester-grants -Method Post -Headers $headers -ContentType 'application/json' -Body $body
```

Die App verwendet den Grant-Schlüssel wie einen normalen Lizenzschlüssel. Nach
Widerruf oder Ablauf wird er bei der nächsten Online-Prüfung ungültig; ein
abgelaufener Tester-Grant verlängert auch die Offline-Gnadenfrist nicht.

## Sicherheitsgrenzen

- Kein Master-Schlüssel und keine Umgehungslogik sind im Client eingebaut.
- Der Admin-Token gehört ausschließlich in Cloudflare/GitHub-Secrets.
- Bei Verlust eines Tester-Schlüssels sofort widerrufen und einen neuen erzeugen.
