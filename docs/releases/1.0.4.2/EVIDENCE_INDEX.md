# DownloadThat 1.0.4.2 evidence index

No release evidence exists yet. Add entries only after the command, CI run,
artifact or external state was actually observed.

| ID | Level | Commit/run | Evidence | Result |
|---|---|---|---|---|
| PLAN-001 | LOCAL_VERIFIED | `01a49597` base | approved team plan and fixed decisions | PASS |
| FIN-001 | LOCAL_VERIFIED | `f134c448` | independent Finance/Refund review; 28 targeted tests | PASS |
| RUN-001 | LOCAL_VERIFIED | `13240383` | independent Runtime/FGS/Entitlement review; 34 targeted tests | PASS |
| LIB-001 | LOCAL_VERIFIED | `e009097b` | migration quarantine/readback/timestamp and transfer integration review | PASS |
| PIPE-001 | LOCAL_VERIFIED | `6c064161` | independent immutable-candidate review; 22 pytest and 12 Node tests | PASS |
| SEARCH-001 | LOCAL_VERIFIED | `b4342f58` | independent cancellation/HOL/transfer-cleanup review; 26 targeted tests | PASS |
| INT-001 | LOCAL_VERIFIED | `b4342f58` integration snapshot | complete local pytest suite: 427 passed, 2 skipped | PASS |
| DOC-001 | LOCAL_VERIFIED | `c8883fce` | release ADRs and 12-locale release notes; relative links and diff checked | PASS |
| DOC-002 | LOCAL_VERIFIED | `1e0183fd` | owner gates, blocked external evidence and redacted device E2E checklist | PASS |
| ENV-001 | UNVERIFIED | external GitHub settings | Required Reviewers and branch restrictions for both release environments | BLOCKED |
| FGS-001 | UNVERIFIED | Play Console | submitted foreground-service declaration matching final behavior | BLOCKED |
| CI-001 | UNVERIFIED | final integration commit | Android compile plus API 34/35 emulator runs | BLOCKED |
| ASSET-001 | UNVERIFIED | final UI commit | real phone, 7-inch and 10-inch captures with visual review | BLOCKED |
| AAB-001 | UNVERIFIED | candidate run | signed AAB, SBOM, provenance, certificate and SHA-256 | BLOCKED |
| PLAY-001 | UNVERIFIED | exact candidate | Internal Testing acceptance of the recorded AAB hash | BLOCKED |
| DEVICE-001 | UNVERIFIED | Internal candidate | redacted completion of `DEVICE_E2E_CHECKLIST.md` | BLOCKED |

Evidence must distinguish local tests, emulator CI, signed artifacts, Play
acceptance and real-device behavior. External screenshots are anonymized and
stored outside Git; this file contains only neutral references and hashes.

An evidence row changes from `UNVERIFIED`/`BLOCKED` only after direct
observation. Workflow source, a checked dispatch input, local unit tests or a
Chat transcript are not substitutes for Console, artifact or device evidence.
