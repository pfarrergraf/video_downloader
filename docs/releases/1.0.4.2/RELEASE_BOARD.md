# DownloadThat 1.0.4.2 release board

This is the only mutable source of truth for the next Android release. Worker
agents report evidence to the orchestrator; only the orchestrator updates this
board.

## Fixed decisions

- Scope: entitlement convergence, transfer-scoped foreground service, native
  search, persistent library/playlists/player, and matching store metadata.
- Refund policy: Google Play decides. DownloadThat does not offer its own refund
  request or automatic refund path. Confirmed Play refunds/voids revoke Pro via
  RTDN or reconciliation.
- Artifact policy: build one signed candidate AAB, then upload those exact bytes
  to Internal Testing by run id and SHA-256. Never rebuild during promotion.
- Candidate version: `v1.0.4.2` / `1000402`, subject to a read-only highest Play
  version-code check before the candidate build.

## Work packages

| Package | Owner | Reviewer | Status | Evidence |
|---|---|---|---|---|
| Refund decommission and Billing contract | Finance/Billing | Critical Reviewer | ACTIVE | pending |
| Runtime, execution gate, FGS, entitlement | Coding | Critical Reviewer + Finance | ACTIVE | pending |
| Search, library, playlists, player | Coding | Critical Reviewer | ACTIVE | pending |
| Claims and listing pipeline | Marketing + Listing | Finance + Critical Reviewer | QUEUED | pending |
| Candidate/promote workflow | Orchestrator | Critical Reviewer | ACTIVE | pending |
| Release documentation and evidence | Documenter | Orchestrator | ACTIVE | this directory |

## Gate status

Verification levels are never collapsed into a generic "tested" status.

| Gate | Status | Required evidence |
|---|---|---|
| G0 scope, policy, branch | LOCAL_VERIFIED | fixed decisions above; integration branch |
| G1 local code and contract tests | BLOCKED | all work packages integrated and green |
| G2 Android compile and API 34/35 emulator | BLOCKED | final commit CI run |
| G3 claims, locales, real screenshots | BLOCKED | listing manifest and visual review |
| G4 TEAM candidate approval | BLOCKED | ACK from all seven roles |
| G5 signed candidate AAB | BLOCKED | provenance, signing cert, SHA-256, SBOM |
| G6 Internal Play acceptance | BLOCKED | exact-artifact promotion record |
| G7 real device and Billing matrix | BLOCKED | redacted device evidence |
| G8 production promotion | BLOCKED | G7 complete; same Play version promoted |

## Team protocol

Task states: `QUEUED`, `ACTIVE`, `REVIEW`, `BLOCKED`, `READY`, `MERGED`.
Evidence levels: `IMPLEMENTED_UNVERIFIED`, `LOCAL_VERIFIED`,
`CI_EMULATOR_VERIFIED`, `SIGNED_AAB_VERIFIED`, `PLAY_ACCEPTED`,
`DEVICE_E2E_VERIFIED`, `SUPERSEDED`.

Every handoff records the commit, changed scope, commands and results, risks,
verdict, acceptance criterion, and next owner. No author approves their own
work. A blocker without a named owner and release condition is invalid.
