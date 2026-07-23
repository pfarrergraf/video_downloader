# Graph Report - security  (2026-07-14)

## Corpus Check
- Corpus is ~14,931 words - fits in a single context window. You may not need a graph.

## Summary
- 78 nodes · 106 edges · 8 communities
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 13 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Penetration Findings|Penetration Findings]]
- [[_COMMUNITY_Security Governance|Security Governance]]
- [[_COMMUNITY_Backend Trust Boundaries|Backend Trust Boundaries]]
- [[_COMMUNITY_SDLC and Compliance|SDLC and Compliance]]
- [[_COMMUNITY_Core Red Team|Core Red Team]]
- [[_COMMUNITY_Production Risk Gates|Production Risk Gates]]
- [[_COMMUNITY_Privacy and Retention|Privacy and Retention]]
- [[_COMMUNITY_Android App Security|Android App Security]]

## God Nodes (most connected - your core abstractions)
1. `Affiliate Program Internal Penetration Test Results` - 12 edges
2. `Core App Red-Team Report` - 11 edges
3. `Production Go-Live Security Gates` - 8 edges
4. `Residual Risk Acceptance Record` - 8 edges
5. `Affiliate Program STRIDE Threat Model` - 7 edges
6. `DownloadThat Security Assessment Report` - 6 edges
7. `Privacy and Data Retention Review` - 5 edges
8. `Cloudflare Pages Functions` - 5 edges
9. `OWASP ASVS 5 Affiliate Readiness` - 4 edges
10. `Security Assessment and Certification Ladder L0-L3` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Android Anti-Tampering and Obfuscation Trade-off` --semantically_similar_to--> `CORE-001 Client-Side Pro Enforcement Residual Risk`  [INFERRED] [semantically similar]
  security/MASVS_MATRIX.md → security/RESIDUAL_RISK_ACCEPTANCE.md
- `AFF-006 Regex Secret Scan Blind Spot` --semantically_similar_to--> `Automated SAST and SCA Gap`  [INFERRED] [semantically similar]
  security/PENETRATION_TEST_RESULTS.md → security/NIST_SSDF_MATRIX.md
- `Stripe-Hosted Checkout Data Flow` --semantically_similar_to--> `Cloudflare to Stripe Trust Boundary`  [INFERRED] [semantically similar]
  security/PCI_SCOPE_ASSESSMENT.md → security/THREAT_MODEL.md
- `Internal Whitebox Security Methodology` --references--> `Affiliate Program STRIDE Threat Model`  [EXTRACTED]
  security/PENETRATION_TEST_PLAN.md → security/THREAT_MODEL.md
- `Production Go-Live Security Gates` --references--> `AFF-009 Production Android Certificate Fingerprint Verification`  [EXTRACTED]
  security/PRODUCTION_SECURITY_CHECKLIST.md → security/PENETRATION_TEST_RESULTS.md

## Hyperedges (group relationships)
- **Affiliate Security Assurance Set** — asvs5_affiliate_readiness, security_evidence_index, executive_security_readiness [INFERRED 0.85]
- **Operational Resilience Set** — backup_restore_fail_closed, incident_response_plan, iso27001_readiness [EXTRACTED 1.00]
- **Affiliate Security Assessment Evidence Chain** — penetration_test_plan_document, penetration_test_results_document, risk_register_document, security_assessment_report_document [EXTRACTED 1.00]
- **Core App Hardening Findings** — red_team_report_core_app_a3_ssrf, red_team_report_core_app_a4_file_permissions, red_team_report_core_app_a5_autologin_secret, red_team_report_core_app_a7_security_headers [EXTRACTED 1.00]
- **Affiliate External Service Flow** — threat_model_cloudflare_functions, threat_model_stripe, threat_model_resend, threat_model_turnstile, threat_model_cloudflare_d1 [EXTRACTED 1.00]

## Communities (8 total, 0 thin omitted)

### Community 0 - "Penetration Findings"
Cohesion: 0.13
Nodes (17): Affiliate Program Penetration Test Plan, Affiliate Security Test Categories, Internal Whitebox Security Methodology, AFF-001 Stored XSS in Partner Admin Dashboard, AFF-002 Explicit Intent Referral Attribution Spoofing, AFF-005 Mutable GitHub Actions and Wrangler Dependencies, AFF-007 Dead Dynamic Checkout Implementation, AFF-008 Case-Sensitive Android Host Comparison (+9 more)

### Community 1 - "Security Governance"
Cohesion: 0.24
Nodes (13): Affiliate Data Flow and Trust Boundaries, OWASP ASVS 5 Affiliate Readiness, On-Device Server ASVS Readiness and Loopback Residual Risks, Affiliate, Android, Cloudflare, and External-Service Attack Surface, Fail-Closed Backup Restore Verification, Affiliate Business-Logic and Fraud Abuse Controls, Security Assessment and Certification Ladder L0-L3, EU Cyber Resilience Act Technical Readiness and Process Gaps (+5 more)

### Community 2 - "Backend Trust Boundaries"
Cohesion: 0.29
Nodes (10): Stripe-Hosted Checkout Data Flow, Cloudflare D1 Persistence, Cloudflare Pages Functions, Affiliate Program STRIDE Threat Model, Partner and Admin Session Trust Boundary, Resend Authentication Email Dependency, Affiliate Single Points of Failure, Stripe Payment Authority (+2 more)

### Community 3 - "SDLC and Compliance"
Cohesion: 0.28
Nodes (9): NIST SP 800-218 SSDF 1.1 Mapping, Automated SAST and SCA Gap, Secure Development Lifecycle Controls, PCI DSS Scope Assessment, Provisional SAQ A or SAQ A-EP Classification, AFF-004 Missing Authentication Rate Limiting, AFF-006 Regex Secret Scan Blind Spot, Production Go-Live Security Gates (+1 more)

### Community 4 - "Core Red Team"
Cohesion: 0.22
Nodes (9): A10 Stripe Webhook Forgery Hypothesis, A1 License Key Forgery Hypothesis, A3 Scrape Endpoint SSRF, A5 Desktop Auto-Login Secret Exposure, A6 Loopback Login Throttle, A7 Core Web Security Headers, A8 Path Traversal Hypothesis, A9 yt-dlp Self-Update Supply Chain (+1 more)

### Community 5 - "Production Risk Gates"
Cohesion: 0.29
Nodes (7): AFF-003 Parallel Webhook Clawback Race Condition, Automatic Production No-Go Conditions, Affiliate Production Security Checklist, Canonical Finding Status: 6 Fixed, 1 Partial, 5 Residual, Canonical Affiliate Risk Register, DownloadThat Security Assessment Report, Affiliate Financial Integrity Invariants

### Community 6 - "Privacy and Retention"
Cohesion: 0.33
Nodes (7): Affiliate Data Minimization, Partner Data Subject Rights Process Gap, Privacy and Data Retention Review, Expired Affiliate Data Retention Gap, SOC 2 Availability, Confidentiality, and Privacy Gaps, SOC 2 Readiness Matrix, SOC 2 Security and Processing Integrity Readiness

### Community 7 - "Android App Security"
Cohesion: 0.33
Nodes (6): Android Anti-Tampering and Obfuscation Trade-off, OWASP MASVS Mapping for Android App, MASVS Level 1 Readiness, Android WebView JavaScript Bridge Hardening, A2 Local Pro Enforcement Bypass, CORE-001 Client-Side Pro Enforcement Residual Risk

## Knowledge Gaps
- **24 isolated node(s):** `Affiliate, Android, Cloudflare, and External-Service Attack Surface`, `No DRM or TPM Circumvention and Preservation Guardrail`, `Android WebView JavaScript Bridge Hardening`, `Secure Development Lifecycle Controls`, `Affiliate Security Test Categories` (+19 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Affiliate Program Internal Penetration Test Results` connect `Penetration Findings` to `SDLC and Compliance`, `Core Red Team`, `Production Risk Gates`?**
  _High betweenness centrality (0.285) - this node is a cross-community bridge._
- **Why does `DownloadThat Security Assessment Report` connect `Production Risk Gates` to `Backend Trust Boundaries`, `SDLC and Compliance`, `Privacy and Retention`?**
  _High betweenness centrality (0.198) - this node is a cross-community bridge._
- **Why does `Core App Red-Team Report` connect `Core Red Team` to `Penetration Findings`, `Android App Security`?**
  _High betweenness centrality (0.190) - this node is a cross-community bridge._
- **What connects `Affiliate, Android, Cloudflare, and External-Service Attack Surface`, `No DRM or TPM Circumvention and Preservation Guardrail`, `Android WebView JavaScript Bridge Hardening` to the rest of the system?**
  _24 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Penetration Findings` be split into smaller, more focused modules?**
  _Cohesion score 0.13 - nodes in this community are weakly interconnected._