# Product Cinema V3 → Homepage: Release Report

## Ausgangslage

- Basis: `master` @ `edf5a12` (unverändert seit V3 auf `origin/gpt/hero-product-cinema-v3`
  erstellt wurde — reine Additions-Branch, kein Merge-Konflikt).
- Integrationsbranch: `claude/integrate-product-cinema-v3-homepage-h7od7l`.
- Details zur Ausgangslage, den Unterschieden und der Integrationsentscheidung stehen in
  `docs/product_cinema_v3_homepage_integration_audit.md`.

## Übernommene V3-Funktionen

Magnetischer Datenstrom (Video/Audio/Bild-Quellen, gekrümmte Bahnen, Morph zum
DownloadThat-Pfeil), Kamerafahrt durch das Smartphone (`source → share → format → stream
→ inside → success`), Glas-/Portalübergang, lokale Dateiverarbeitung, ruhiger
Erfolgszustand, Replay, manueller Schrittmodus, Motion-Schalter, `prefers-reduced-motion`,
adaptive Canvas-Partikel, vollständig lokale Assets, kein Build-Schritt — alles erhalten,
keine externe Bibliothek eingeführt.

## Layoutverbesserungen

- **Above-the-fold**: `min-height: calc(100svh - var(--dt-nav-h))`, wobei `--dt-nav-h`
  aus der tatsächlich gemessenen Nav-Höhe gesetzt wird (JS, `ResizeObserver`-freier
  einfacher `offsetHeight`-Sync bei `load`/`resize`/`orientationchange`) statt einer
  geratenen festen Zahl.
- Stage-/Gerätegröße auf `clamp()` umgestellt (vh-getrieben für die Stage, vw-getrieben
  für das Gerät), damit das Smartphone auf Mobile in der geforderten Zielbreite bleibt
  (360 px → ~187 px, 390 px → ~203 px Telefonbreite) und auf Desktop vollständig in
  700–1080 px Viewporthöhe passt.
- **Mobile Reihenfolge per CSS statt Duplikat-Markup**: Die Copy-Spalte ist in zwei
  Grid-Areas aufgeteilt (`primary`: Eyebrow/Headline/Lead/Trust-Chips/Primär-CTA;
  `secondary`: Sekundär-CTA/Rechtshinweis/Windows-Link). Per `grid-template-areas`
  steht `secondary` auf Desktop wie bisher unter `primary` in derselben Spalte, auf
  Mobile aber *nach* der Cinema-Stage — genau die geforderte Priorität
  Nav→Headline→Lead→Primär-CTA→Smartphone→Sekundärinfo, ohne zwei CTA-Kopien im DOM.
- Trust-Chips auf zwei reduziert (`trust_local`, `trust_cloud`), Format-Karte von drei
  gestapelten Buttons auf ein 3-Spalten-Grid verkürzt — beides spart Mobile-Höhe.
- Ein real gemessener, konkreter Bug aus der Quelle wurde beim Zusammenführen behoben:
  die drei Lab-CSS-Dateien deklarierten Farbtokens auf einem bloßen `:root`
  (`--bg`, `--text`, `--grad`, …) — das hätte beim Laden auf der echten Startseite
  stillschweigend die gleichnamigen, aber andersfarbigen Variablen des restlichen
  Sitedesigns überschrieben. Alle Tokens laufen jetzt unter `--pc3-*`, gescoped auf
  `.pc3`.

## Above-the-fold-Ergebnisse (gemessen, Chromium/Playwright, deutsche Sprache)

| Viewport | Nav | Headline+Lead+CTA | Smartphone vollständig | Quellen | Timeline/Controls |
|---|---|---|---|---|---|
| 1366×768 | ✓ | ✓ | ✓ (bis 602px von 768) | ✓ | ✓ (bis 670px) |
| 1440×900 | ✓ | ✓ | ✓ (bis 679px von 900) | ✓ | ✓ (bis 774px) |
| 1920×1080 | ✓ | ✓ | ✓ (bis 803px von 1080) | ✓ | ✓ (bis 893px) |
| 360×800 | ✓ | ✓ (Primär-CTA bis 379px) | ✓ (bis 787px von 800) | teilweise (Design) | knapp unterhalb (826px) |
| 390×844 | ✓ | ✓ (Primär-CTA bis 391px) | ✓ (bis 833px von 844) | teilweise (Design) | knapp unterhalb (860px) |
| 412×915 | ✓ | ✓ | ✓ (bis 886px von 915) | teilweise (Design) | ✓ (bis 904px) |

`document.documentElement.scrollWidth === window.innerWidth` bei allen acht getesteten
Breiten (360/390/412/768/1024/1366/1440/1920) — kein horizontaler Überlauf.

Die Timeline/Controls-Leiste liegt bei 360×800 und 390×844 knapp (16–39 px) unterhalb
des ersten Viewports; das ist zulässig, da Abschnitt 5 des Auftrags für Mobile
ausdrücklich nur Nav, Headline, Lead, Primär-CTA, vollständiges Smartphone und
Teile der Quellen als Pflicht listet, nicht die Steuerungsleiste selbst.

768×1024 und 1024×768 (nur allgemeine Testviewports, kein Pflicht-Fit laut Auftrag)
wurden ebenfalls ohne horizontalen Overflow geprüft; 1024×768 fällt knapp unter den
1080-px-Breakpoint und nutzt daher noch das gestapelte Mobile-Layout (Smartphone dort
nicht vollständig im ersten Bildschirm) — siehe „Bekannte Einschränkungen“.

## Mobile-Ergebnisse

- Vollständige Headline ("AUSWÄHLEN." nie abgeschnitten) bei 360/390/412 bestätigt
  (Screenshots).
- Primär-CTA sofort erreichbar und nie unterhalb des ersten Viewports.
- Smartphone vollständig sichtbar bei 360×800 und 390×844 (Kernanforderung erfüllt).
- Keine gequetschten nebeneinander liegenden CTAs: Sekundär-CTA liegt jetzt nach der
  Stage, Primär-CTA allein in der ersten Zeile — keine Layoutkollision getestet.

## i18n-Status

- `website.hero_cinema.*` (27 Keys: Eyebrow, drei Titelzeilen, Lead, zwei Trust-Chips,
  Rechtshinweis, sechs Szenen-Captions, Szenen-Überschriften/-Labels, Replay/Schrittmodus,
  Motion-Schalter-Label, Region-Label) in **allen 50 Website-Locales** ergänzt.
- **de** und **en** sind vollständige, inhaltlich geprüfte Übersetzungen.
- Die restlichen 48 Locales erhalten für diese neuen Keys den englischen Text als Wert
  (nicht nur Laufzeit-Fallback) — sichtbar z. B. im `ar-390-start.png`-Screenshot: die
  neue Headline/Lead/Trust-Chips erscheinen auf Englisch, während der bereits vorhandene
  Primär-CTA-Button korrekt auf Arabisch übersetzt bleibt (`website.hero.cta_primary`
  wird bewusst wiederverwendet statt dupliziert).
- `tests/test_i18n.py` (Key-Parität App/Website, keine leeren Werte, Platzhalter-Erhalt)
  bleibt grün — die identischen Keys wurden auch in
  `video_downloader/web/static/i18n/*.json` ergänzt, da der bestehende Test genau diese
  App/Website-Parität erzwingt, obwohl die App diesen Hero nie rendert.
- RTL (`ar`/`he`/`fa`/`ur`) wird nicht neu unterstützt — die Seite setzte schon vorher
  nirgends `dir="rtl"`; das ist eine vorbestehende Lücke, keine Regression dieses PRs.

## Accessibility

- `prefers-reduced-motion: reduce`: keine Partikel/Kamerafahrt/Gerätebewegung, Sprung
  direkt in den Erfolgszustand mit sichtbarem CTA (Screenshot `reduced-motion-390.png`).
- Sichtbarer Motion-Schalter (`data-pc3-motion`, `aria-pressed`).
- Inaktive Szenen erhalten `aria-hidden="true"` **und** `inert` (nicht nur Opacity) —
  verifiziert per Playwright: 0 fokussierbare Elemente in inaktiven Szenen über die
  gesamte Tab-Reihenfolge.
- Tastatursteuerung: native `<button>`-Elemente, Enter/Space verifiziert (Replay-Reset,
  Motion-Toggle `aria-pressed`).
- `aria-live="polite"` nur auf der Timeline-Leiste (sechs Phasenwechsel pro Durchlauf,
  keine Frame-für-Frame-Ausgabe).
- Touchziele ≥ 44×44 px (Controls, CTAs, Format-Buttons).
- `forced-colors: active`-Grundregeln für Karten/Buttons ergänzt.
- Kein JS nötig für Headline/Lead/CTA/erste Szene (verifiziert mit
  `javaScriptEnabled: false`, Screenshot `no-js-390.png`).
- Pausiert bei `document.hidden` (Canvas-rAF **und** Autoplay-Timer, nicht nur ersteres).
- RTL/200%-Zoom: keine harten Pixel-Höhen auf Textcontainern; nicht separat mit
  Zoom-Emulation gemessen (bekannte Einschränkung, siehe unten).

## Performance

- Partikelzahl weiterhin `min(240, max(120, breite/4.2))` (Mobile ≈120–130, Desktop
  bis 240).
- DPR auf 2 gedeckelt.
- Canvas lazy über `defer`-Script, läuft erst nach Parsing.
- Ein-Schuss-Downgrade: bei anhaltend >40 ms Frametime über ~1,5 s wird das
  Partikel-Array einmalig um ein Drittel gekürzt.
- Stresstest (5× Replay, Resize 390→1024→390, 8× Schrittmodus, Sprachwechsel während
  der Animation): 0 Konsolenfehler, kein horizontaler Overflow danach.

## Getestete Viewports (Playwright/Chromium, real gerendert)

360×800, 390×844, 412×915, 768×1024, 1024×768, 1366×768, 1440×900, 1920×1080 — jeweils
Startzustand, Datenstrom (`stream`), Erfolgszustand; zusätzlich 1366×768 im
`inside`-Zustand, 1440×900 im Erfolgszustand, Reduced Motion bei 390×844, sowie
`ar`/`ja`/`zh` bei 390×844. Screenshots unter
`docs/product_cinema_v3_homepage_screenshots/`.

## Testbefehle und Ergebnisse

```
uv sync --extra dev
uv run pytest tests/test_product_cinema_homepage.py tests/test_gpt_product_cinema_v3.py tests/test_i18n.py -v
# 27 passed, 1 skipped (test_creator_tools.py has 1 unrelated skip)

uv run pytest tests/ --ignore=tests/test_cli_compat.py --ignore=tests/test_easy_ui.py -q
# 225 passed, 1 skipped
```

Die beiden ignorierten Dateien scheitern wie in `CLAUDE.md` dokumentiert an fehlendem
`tkinter` in dieser Sandbox — eine vorbestehende Umgebungslücke, keine Regression.

## Checkout/Stripe/Affiliate — unverändert

`#withdrawal-modal`, beide Stripe-Links (`buy.stripe.com/...`), `client_reference_id`-
Logik, `#buy-license-btn`, Sprachumschaltung der Stripe-Links (`dtUpdateStripeLinks`)
— alle unverändert vorhanden und per Test (`test_checkout_and_stripe_bits_are_untouched
_by_the_hero_change`) sowie manueller Prüfung des Diffs bestätigt. Der Cinema-Diff
berührt `#pricing`, `#faq`, Footer, Checkout-Modal-Markup oder `functions/` nicht.

## Bekannte Einschränkungen

1. Timeline/Controls-Leiste liegt bei 360×800/390×844 knapp unterhalb des ersten
   Viewports (siehe Tabelle oben) — laut Auftrag zulässig, da nicht Pflichtbestandteil
   der mobilen Above-the-fold-Komposition.
2. 1024×768 (nur allgemeiner Testviewport) nutzt noch das gestapelte Layout unterhalb
   des 1080-px-Breakpoints; das Smartphone ist dort nicht vollständig im ersten
   Bildschirm sichtbar. Kein Pflicht-Fit laut Auftrag, aber ein guter Kandidat für eine
   spätere Breakpoint-Verfeinerung.
3. Nur `de`/`en` sind inhaltlich vollständig übersetzt; die restlichen 48 Locales zeigen
   für die neuen Animationstexte englischen Text (siehe i18n-Status).
4. RTL wird nicht aktiv unterstützt (vorbestehende Lücke, keine Regression).
5. 200%-Text-Zoom und tatsächliche Low-End-Android/Samsung-Internet-Hardware wurden
   nicht in einem echten Gerät getestet, nur strukturell (keine festen Text-Container-
   Höhen, `clamp()` statt fixer `px`-Schriftgrößen an den meisten Stellen).

## Rollback

1. `git revert` der fünf Integrations-Commits (oder `git checkout edf5a12 -- pro/website/index.html`),
   um den alten Hero wiederherzustellen.
2. Die zwei neuen `<link>`/`<script>`-Referenzen auf `assets/home/hero-product-cinema.*`
   aus `pro/website/index.html` entfernen (bzw. per Revert automatisch entfernt).
3. Keine Datenbank-, Payment-, Lizenz- oder Backend-Migration betroffen — die
   `website.hero_cinema.*`-i18n-Keys können unverändert liegen bleiben (kein Schaden,
   falls ungenutzt) oder ebenfalls per Revert der i18n-Commits entfernt werden.

## Commit-SHAs (auf `claude/integrate-product-cinema-v3-homepage-h7od7l`, Basis `edf5a12`)

- `a69b455` — Bring in Product Cinema V3 lab preview files unchanged
- `642b83f` — Add production Product Cinema hero assets (neutral names)
- `0ffa290` — Integrate Product Cinema hero into the homepage, above-the-fold
- `bd71d5e` — Wire the Product Cinema hero into website i18n
- `4101677` — Add Product Cinema homepage integration tests
