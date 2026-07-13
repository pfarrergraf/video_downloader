# Externe Beauftragungen — was nur Dritte können, Kosten & Nutzen

Datum: 2026-07-13. Diese Datei trennt, was intern/automatisiert bereits erledigt ist,
von dem, was **nur eine externe Firma oder ein Anwalt** leisten kann — mit grober
Kosteneinordnung (EU-Markt, 2026, Größenordnung, kein Angebot) und dem konkreten Nutzen.

## Bereits intern erledigt (senkt die externen Kosten)

Externe Prüfer sollen ihre teure Zeit nicht mit Dingen verbringen, die ein Linter gratis
findet. Vor einer Beauftragung liegt bereits vor: Threat Model, Red-Team-Report mit PoCs,
ASVS/MASVS-Selbstbewertung, SAST/CodeQL/Dependabot/Secret-Scan in CI, Härtung (SSRF,
Header, Dateirechte, Auto-Login-Token), GDPR-Erasure/Retention, SBOM. → Ein Pentester
startet damit auf einem gehärteten Stand und liefert mehr Substanz pro Stunde.

## Priorisierte externe Beauftragungen

### 1. Rechtsrat: Urheberrecht / DRM / Downloader-Legalität 🔴 WICHTIGSTE
- **Warum nur extern:** Rechtsverbindliche Einschätzung darf nur ein Anwalt geben; das ist
  das größte Geschäftsrisiko dieser App (Play-Content-Policy, § 95a UrhG Umgehungsverbot,
  YouTube-ToS, DSM-RL, Haftung bei „einer Million" Nutzern).
- **Wen:** IT-/Urheberrechts-Kanzlei (DE/EU), Schwerpunkt Medien/Internet.
- **Kosten (grob):** fokussiertes schriftliches Gutachten **€1.500–5.000**; laufende
  Beratung **€250–400/h**.
- **Nutzen:** klare Leitplanken fürs Marketing/Feature-Set, bevor skaliert wird; verhindert
  ein Geschäft, das auf einem entfernbaren Play-Listing oder abmahnbarer Werbung steht.

### 2. Externer Penetrationstest (L2 der Zertifizierungs-Leiter) 🟠
- **Warum nur extern:** Unabhängigkeit + Haftung; ein Siegel/Report für Kunden/Due-Diligence
  braucht einen Dritten.
- **Scope:** Cloudflare-Backend (Lizenz/Zahlung/Admin), Android-App inkl. WebView-Bridge,
  On-Device-Server.
- **Wen:** seriöse Boutique oder CREST/OSCP-zertifiziertes Team; für Mobile zusätzlich
  MobSF-gestützt.
- **Kosten (grob):** fokussiert **€6.000–15.000**; reine Mobile-App **€3.000–8.000**;
  großes/CREST-akkreditiertes Team **€15.000–40.000**.
- **Nutzen:** unabhängiger Nachweis „extern getestet, P0/P1 geschlossen" — Voraussetzung
  für Gate L2 und für B2B-/Enterprise-Verkauf.
- **Timing:** erst sinnvoll, wenn L0/L1 stehen (jetzt der Fall). Nicht vor Play-Launch nötig.

### 3. DSGVO-/Datenschutz-Kurzprüfung + ggf. externer DSB 🟠
- **Warum nur extern:** Rechtskonforme Datenschutzerklärung/AVV mit Subauftragnehmern
  (Cloudflare, Stripe) und — je nach Umfang/Volumen — ein benannter Datenschutzbeauftragter.
- **Wen:** Datenschutz-Kanzlei oder externer DSB-Dienstleister.
- **Kosten (grob):** Erstprüfung **€1.000–3.000**; externer DSB als Retainer **€100–300/Monat**
  (nur bei entsprechendem Umfang/Pflicht).
- **Nutzen:** belastbare Rechtsgrundlage bei Skalierung; die Technik (Erasure/Retention,
  Datenminimierung) ist bereits vorbereitet — der Anwalt bewertet nur noch.

### 4. Marke / Unternehmensbasis 🟢 (bei Kommerzialisierung)
- **Wen:** Markenanwalt / DPMA/EUIPO.
- **Kosten (grob):** Markenanmeldung **€300–900** Amtsgebühren + **€500–1.500** Anwalt.
- **Nutzen:** schützt „DownloadThat", verhindert Namensstreit beim Wachsen.

### 5. Play-Policy-Beratung 🟢 (optional, meist verzichtbar)
- Nischenberater für Store-Listing/Policy: **€500–2.000**. Meist reicht Googles eigener
  **Pre-launch Report** (kostenlos) + die Policy-Doku. Nur erwägen, wenn nach Abschnitt 1
  (Recht) eine Play-Strategie tatsächlich verfolgt wird.

## Bewusst (noch) NICHT beauftragen

- **ISO 27001** (~€10.000–30.000 Erstjahr) und **SOC 2 Type II** (~$15.000–50.000):
  organisations-/prozessgebunden, für ein Solo-Produkt unverhältnismäßig. Readiness-Matrizen
  liegen vor → als „vorbereitet, nicht angestrebt" führen; erst bei konkretem
  Enterprise-Kundenbedarf beauftragen.
- **Managed Bug-Bounty** (Plattformgebühr + Bounties): erst ab relevanter Nutzerbasis; bis
  dahin genügt die veröffentlichte Coordinated-Disclosure-Policy (`SECURITY.md`).

## Empfohlene Reihenfolge

1. **Jetzt:** Play-Konto registrieren (unkritisch), Listing/Data-Safety nach den korrigierten
   Docs, Pre-launch Report nutzen, Sideload-Kanal behalten.
2. **Vor dem Skalieren/Marketing-Push:** Rechtsrat (1) — die wichtigste Ausgabe.
3. **Für B2B/Vertrauen:** externer Pentest (2) + DSGVO-Kurzprüfung (3).
4. **Bei Kommerzialisierung:** Marke (4).
5. **Nur bei Enterprise-Bedarf:** ISO/SOC 2.
