# Product Cinema V3 → Homepage Integration Audit

## Ausgangslage auf `master` (Basis-Commit `edf5a12`)

- `pro/website/index.html` hat einen einfachen, bereits mobil-optimierten Hero:
  ein zentrierter, einspaltiger Block (Marke/Nav/Sprachumschalter aus `header.nav`,
  danach `<section class="hero">` mit Phone-Mockup + 4-Frame-Textloop-Animation,
  Headline `Share. Save. Done.`, Lead, ein Trust-Chip, zwei CTAs, Windows-Link).
- i18n läuft über `pro/website/i18n.js` + `pro/website/i18n/<code>.json` für 52 Sprachen;
  `tests/test_i18n.py` erzwingt, dass **jede** Locale-Datei exakt dieselben Keys wie
  `en.json` hat (keine fehlenden/zusätzlichen Keys, keine leeren Werte, Platzhalter
  müssen erhalten bleiben). Das bestimmt maßgeblich den i18n-Ansatz unten.
- Checkout: Buy-Button öffnet `#withdrawal-modal`, zwei Stripe-Links mit
  `client_reference_id` (`waived-<ts>` / `wait14`), Sprachumschaltung schreibt
  `?locale=` in die Stripe-Links (`dtUpdateStripeLinks` in `i18n.js`). Nichts davon wird
  angefasst.
- Faktenquelle `creator_tools/config/product_facts.json`: 12 € einmalig, kein Abo,
  3 Downloads/Tag frei, Rechte-Hinweis, DRM/Android-Einschränkung — alle neuen Hero-Texte
  wurden dagegen geprüft.

## Product Cinema V3 (Quelle: `origin/gpt/hero-product-cinema-v3`, unverändert seit PR #11)

Reine Additions-Branch: fügt nur neue Dateien hinzu (Labor-HTML `gpt_hero_product_cinema_v3.html`,
Preview-Wrapper, 3 CSS-Dateien + 1 JS-Datei unter `assets/gpt_product_cinema_v3/`, Doku,
Struktur-Tests). **`pro/website/index.html` wurde von V3 nicht verändert** — die Integration
in die echte Startseite steht noch komplett aus, genau wie `docs/gpt_product_cinema_v3_integration.md`
es als nächsten Schritt vorsieht.

`master` wurde seit Erstellung von V3 nicht in einer Weise verändert, die mit V3 kollidiert
(V3 fügt nur neue, isolierte Dateien hinzu); es gibt keinen Merge-Konflikt zu lösen, nur eine
kontrollierte Integration der Inhalte in die bestehende Struktur.

Kernstück: `.pc3-copy` (Eyebrow/H1 dreizeilig/Lead/Pills/Actions/Legal) und `.pc3-cinema`
(Canvas-Partikelstrom mit 3 Medienquellen, Kamerafahrt-Rig mit Smartphone-Mockup und 6
Szenen `source→share→format→stream→inside→success`, Replay/Schrittmodus-Steuerung).
Vollständig `.pc3-*`/`data-pc3-*` namespaced, keine externe Bibliothek, kein Build-Schritt.

## Integrationsentscheidung

1. **Ersetzen, nicht nebenläufig führen**: Der alte Hero (`<section class="hero">`) wird durch
   die V3-Komposition ersetzt (`.pc3-copy` + `.pc3-cinema`), eingebettet zwischen dem
   unveränderten `header.nav` und den unveränderten Folgesektionen (`#features` …).
   Die Labor-Navigation (`.pc3-nav`, Motion-Button dort, `PRODUCT CINEMA V3`-Tag) entfällt
   vollständig zugunsten der bestehenden echten Navigation.
2. **Produktionsnamen**: Die drei CSS-Dateien werden zu einer Datei
   `pro/website/assets/home/hero-product-cinema.css` zusammengeführt und dabei auf
   Above-the-fold-Komposition (siehe unten) angepasst; die JS-Datei wird zu
   `pro/website/assets/home/hero-product-cinema.js` (gleiche Logik + i18n-Textinjektion
   für die sechs Szenen statt hartkodierter deutscher Strings + zusätzliche
   Tastatur-/Fokus-/Sichtbarkeits-Härtung). CSS-Selektoren/Datenattribute bleiben
   `.pc3-*`/`data-pc3-*` (technischer Namespace, keine sichtbare "V3"-Kennzeichnung).
3. **Labor-Dateien bleiben unverändert** (`gpt_hero_product_cinema_v3.html`,
   `gpt_product_cinema_v3_preview.html`, `assets/gpt_product_cinema_v3/*`,
   `tests/test_gpt_product_cinema_v3.py`) — sie dienen weiterhin als isolierte QA-Vorschau
   und müssen laut Auftrag lauffähig bleiben.
4. **i18n**: neue Texte unter `website.hero_cinema.*`; CTA-Buttons referenzieren bewusst die
   bereits in allen 52 Sprachen vorhandenen `website.hero.cta_primary` /
   `website.hero.cta_secondary`, um keine bereits gepflegte Übersetzung zu duplizieren.
   `de` und `en` werden vollständig und inhaltlich geprüft übersetzt; die verbleibenden
   50 Locale-Dateien erhalten für die neuen Keys den englischen Text als Wert (nicht nur
   Laufzeit-Fallback), damit `tests/test_i18n.py` (identische Keys in jeder Datei) grün
   bleibt und nie ein roher Key oder ein leeres Feld sichtbar wird.
5. Alte `website.hero.*`-Keys (`title_html`, `title_emphasis`, `trust_chip`,
   `windows_link`) bleiben in den i18n-Dateien erhalten (Rollback-Fähigkeit, keine
   Verwaisung anderer Seiten), werden aber im neuen Hero nicht mehr referenziert
   (`title_html`/`title_emphasis`/`trust_chip`/`windows_link` — der Windows-Link wandert
   als kompakter Sekundärlink unter die Cinema-Steuerung).

## Geänderte Dateien

- `pro/website/index.html` (Hero-Sektion ersetzt, Rest unverändert)
- `pro/website/assets/home/hero-product-cinema.css` (neu)
- `pro/website/assets/home/hero-product-cinema.js` (neu)
- `pro/website/i18n/*.json` (52 Dateien: neue `website.hero_cinema.*`-Keys)
- `tests/test_product_cinema_homepage.py` (neu)
- `docs/product_cinema_v3_homepage_integration_audit.md` (dieses Dokument)
- `docs/product_cinema_v3_homepage_release_report.md` (neu, nach Tests)

## Ausdrücklich nicht verändert

- `pro/website/gpt_hero_product_cinema_v3.html`, `gpt_product_cinema_v3_preview.html`,
  `pro/website/assets/gpt_product_cinema_v3/*`, `tests/test_gpt_product_cinema_v3.py`,
  `docs/gpt_product_cinema_v3_integration.md` (Laborvorschau bleibt bestehen)
- Checkout-Modal, Stripe-Links, `client_reference_id`-Logik, Widerrufslogik (`i18n.js`
  `dtUpdateStripeLinks`, `index.html` Buy-Button-Handler)
- Navigation, Sprachumschaltung, Pricing, FAQ, Footer
- Alles unter `video_downloader/`, `android/`, `creator_tools/`, Cloudflare
  Functions/D1/Affiliate-Logik
