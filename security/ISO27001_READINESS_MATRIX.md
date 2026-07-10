# ISO/IEC 27001:2022 Readiness Matrix — Affiliate Program

Interne Gap-Analyse, **keine Zertifizierung**. Eine Zertifizierung darf ausschließlich durch eine
akkreditierte, unabhängige Zertifizierungsstelle erfolgen.

| ISMS-Bereich | Bewertung | Notiz |
|---|---|---|
| Scope des ISMS | Nicht definiert | Diese Prüfung deckt nur die Affiliate-Programm-Codebasis ab, nicht das gesamte Unternehmens-ISMS |
| Informationssicherheitsleitlinie | Nicht vorhanden (organisatorisch) | Außerhalb des Code-Scopes |
| Risikomanagement (Annex A.5) | Teilweise | `RISK_REGISTER.md` als technischer Baustein; kein unternehmensweites Risikoregister |
| A.8 Asset Management | Teilweise | Technisches Assetverzeichnis in `THREAT_MODEL.md` §2; kein formelles Unternehmens-Assetregister |
| A.5.23 Cloud-Services-Sicherheit | Teilweise | Cloudflare/Stripe/Resend als Auftragsverarbeiter identifiziert; DPAs nicht Teil dieses Code-Reviews |
| A.8.24 Kryptografie | Bereit | SHA-256/HMAC-SHA256 korrekt verwendet, keine selbstgebauten Krypto-Primitive |
| A.8.25 Sichere Entwicklung | Bereit | Diese Prüfung selbst ist Teil eines sicheren SDLC-Nachweises |
| A.8.28 Sicheres Coding | Bereit (nach Fix) | AFF-001/003/004/012 behoben, Regressionstests ergänzt |
| A.5.30 IKT-Kontinuität | Teilweise | `BACKUP_RESTORE_TEST.md` als Plan; kein praktischer Test in Produktionsumgebung durchgeführt (außerhalb Scope) |
| A.5.24–5.28 Incident Management | Teilweise | `INCIDENT_RESPONSE_PLAN.md` als Erstentwurf; kein gelebter Prozess mit Nachweis über Zeit |
| Interne Audits / Management Review | Nicht vorhanden | Diese Prüfung kann ein einmaliges internes Audit-Artefakt sein, ersetzt aber keinen wiederkehrenden Auditzyklus |
| Statement of Applicability | Nicht erstellt | Erfordert unternehmensweiten Scope, außerhalb dieser Code-fokussierten Prüfung |

## Gesamteinschätzung

Auf **technischer Kontrollebene** (Annex-A-Controls mit direktem Codebezug: Kryptografie, sicheres Coding,
Kontinuität-relevante Fail-Closed-Mechanismen) ist die Affiliate-Programm-Implementierung **gut vorbereitet**.
Auf **ISMS-Ebene** (Scope, Leitlinie, Risikomanagement-Prozess, interne Audits, Management Review) bestehen
**wesentliche Lücken**, die außerhalb des Mandats und der Möglichkeiten einer Code-Sicherheitsprüfung liegen
und organisatorische Arbeit des Unternehmens erfordern. Eine Zertifizierung ist auf Basis dieser Prüfung
**nicht möglich und nicht beabsichtigt**.
