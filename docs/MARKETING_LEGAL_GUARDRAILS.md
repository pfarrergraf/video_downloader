# Marketing- und Public-Copy-Leitplanken

Stand: 2026-07-14 · Status: **aktuell**

Die verbindliche maschinenlesbare und menschliche Policy ist
`security/PUBLIC_CLAIMS_POLICY.md`. Dieses Dokument fasst ihre praktische Anwendung
für deutschsprachige Texte zusammen. Ältere Influencer-, Affiliate- und
Sideload-Dokumente sind historische Evidenz und keine Textquelle.

## Zulässige Positionierung

- DownloadThat speichert Video, Audio und Bilder aus Links, die Nutzer selbst
  bereitstellen und rechtmäßig speichern dürfen.
- Die Medienverarbeitung erfolgt auf dem Gerät.
- Lizenzprüfung, Google Play Billing, Quellabruf und Updates benötigen begrenzte
  Netzwerkdienste.
- Google Play ist der primäre Android-Kanal; die signierte direkte APK ist eine
  sekundäre Installationsoption.
- Free: drei Downloads pro 24 Stunden ohne Benutzerkonto. Pro: einmalig 12 EUR,
  kein Abo.
- Keine Werbe-SDKs und kein Analytics-Tracking, solange dies im Code verifiziert
  bleibt.

## Unzulässige Positionierung

- Keine pauschale Reichweitenbehauptung über alle, nahezu alle, die meisten oder
  beliebige Websites, Plattformen, Apps oder Videos.
- Keine Anti-Store- oder Sideload-only-Werbung.
- Keine absolute Behauptung, die gesamte App sei offline, vollständig lokal oder
  nutze keinerlei Netzwerk-/Cloud-Dienst.
- Keine fremden Plattformnamen als positives Downloadversprechen und keine
  fremden Logos, Thumbnails oder Markenfarben als eigene Bildsprache.
- Keine Anleitung zur Umgehung von Werbung, Abos, Bezahlschranken, DRM oder
  technischen Schutzmaßnahmen.
- Keine erfundenen Rabatte, Nutzerzahlen, Testimonials, Einkommensversprechen,
  Zertifizierungen oder Google-Freigaben.

## Release-Regel

`uv run python scripts/check_public_claims.py` muss vor Store-, Website- oder
Marketing-Veröffentlichungen erfolgreich sein. Eine beabsichtigte Änderung dieser
Regeln erfordert gleichzeitig aktualisierte Security-Evidenz und Tests.
