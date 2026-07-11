# GPT Product Cinema V3 — Integration Guide

## Ziel

V3 kombiniert die beiden vollständig ausgebauten Verbesserungen:

1. **Magnetischer Datenstrom**: Video-, Audio- und Bildobjekte bleiben visuell unterscheidbar, bewegen sich auf gekrümmten Bahnen zum Smartphone und formen sich zum DownloadThat-Pfeil.
2. **Kamerafahrt durch das Smartphone**: Die Kamera nähert sich während der Bediensequenz, folgt der Datei durch die Glasoberfläche in die lokale Verarbeitung und kehrt anschließend in einen ruhigen Erfolgszustand zurück.

## Vorschauen

- `pro/website/gpt_product_cinema_v3_preview.html`
- `pro/website/gpt_hero_product_cinema_v3.html`

## Dateien

- `pro/website/assets/gpt_product_cinema_v3/gpt_product_cinema_v3_base.css`
- `pro/website/assets/gpt_product_cinema_v3/gpt_product_cinema_v3_stage.css`
- `pro/website/assets/gpt_product_cinema_v3/gpt_product_cinema_v3_motion.css`
- `pro/website/assets/gpt_product_cinema_v3/gpt_product_cinema_v3.js`

## Vollständige Sequenz

1. Medienlink und Share-Button
2. stilisiertes Teilen-Menü
3. Auswahl von Video, Audio oder Bildern
4. magnetische Bündelung der drei Medientypen
5. Morph zum DownloadThat-Pfeil
6. Kamerafahrt durch die Displayoberfläche
7. lokale Dateiverarbeitung
8. ruhiger Erfolgszustand mit CTA

## Technische Eigenschaften

- keine externe JavaScript-Bibliothek;
- kein Build-Schritt;
- statisch über Cloudflare auslieferbar;
- Canvas mit maximal 240 Partikeln;
- Partikelzahl passt sich der verfügbaren Breite an;
- drei unterscheidbare Partikeltypen statt abstrakter Punkte;
- vollständig namespaced mit `.pc3-*` und `data-pc3-*`;
- automatische Sequenz und manueller Schrittmodus;
- Replay-Steuerung;
- Pointer-Tilt außerhalb der starken Kameraphasen;
- Animation pausiert bei verborgenem Browser-Tab;
- `prefers-reduced-motion` und eigener Motion-Schalter;
- wichtige Inhalte bleiben DOM-Text;
- Tastatursteuerung für alle relevanten Schaltflächen.

## Validierung

Lokal mit Chromium/CDP geprüft:

- Desktop: 1440 × 1000;
- Mobile: 390 × 844;
- Startzustand;
- magnetischer Datenstrom;
- Kamerafahrt/Inside-Zustand;
- finaler Erfolgszustand;
- kein horizontaler Überlauf auf Desktop;
- kein horizontaler Überlauf auf 390 px;
- automatische Sequenz endet mit `data-pc3-phase="success"`;
- mobile Headline bleibt vollständig sichtbar;
- Smartphone ist auf Mobile bereits im ersten Bildschirm angeschnitten sichtbar;
- alle Dateien werden lokal geladen.

## Sicherheitsgrenzen

Nicht verändert werden:

- `pro/website/index.html`;
- Stripe-Links;
- Checkout- und Widerrufslogik;
- Lizenzierung;
- Affiliate-Attribution;
- Partnerregistrierung;
- Android-Berechtigungen;
- Download-Backend.

## Empfohlener Merge-Ablauf

1. Diesen Branch als isolierte Vorschau mergen.
2. Vorschau auf echten Android-Geräten prüfen.
3. Texte unter `website.hero_cinema.*` internationalisieren.
4. vorhandenen Hero vorübergehend als `classic` behalten.
5. V3 hinter einer Hero-Variantenschaltung integrieren.
6. `/download`, `#pricing`, Sprachumschaltung, Checkout und Affiliate-Parameter testen.
7. erst danach V3 als Standard aktivieren.

## Produktionsintegration

Für die spätere Integration werden aus `gpt_hero_product_cinema_v3.html` nur folgende Bereiche benötigt:

- `.pc3-copy`;
- `.pc3-cinema`.

Die produktive Navigation und alle nachfolgenden Websitebereiche bleiben bestehen. Die drei CSS-Dateien und die JavaScript-Datei können unverändert geladen werden, da ihre Selektoren vollständig namespaced sind.

## Rollback

Der Rollback besteht aus:

1. ursprüngliches Hero-Markup wieder aktivieren;
2. vier V3-Asset-Referenzen entfernen.

Es gibt keine Datenbank-, Payment-, Lizenz- oder Backendmigration.
