# DownloadThat 1.0.4.2 evidence index

Add entries only after the command, CI run, artifact or external state was
actually observed.

| ID | Level | Commit/run | Evidence | Result |
|---|---|---|---|---|
| PLAN-001 | LOCAL_VERIFIED | `01a49597` base | approved team plan and fixed decisions | PASS |
| FIN-001 | LOCAL_VERIFIED | `f134c448` | independent Finance/Refund review; 28 targeted tests | PASS |
| RUN-001 | LOCAL_VERIFIED | `13240383` | independent Runtime/FGS/Entitlement review; 34 targeted tests | PASS |
| LIB-001 | LOCAL_VERIFIED | `e009097b` | migration quarantine/readback/timestamp and transfer integration review | PASS |
| PIPE-001 | LOCAL_VERIFIED | `6c064161` | independent immutable-candidate review; 22 pytest and 12 Node tests | PASS |
| SEARCH-001 | LOCAL_VERIFIED | `b4342f58` | independent cancellation/HOL/transfer-cleanup review; 26 targeted tests | PASS |
| INT-001 | LOCAL_VERIFIED | `a9f07989` integration snapshot | complete local pytest suite: 433 passed, 2 skipped; 20 Node and 30 website tests | PASS |
| MKT-001 | LOCAL_VERIFIED | `a9f07989` | public-claims policy scan and no-ad SDK/dependency scan: 140 relevant files, no advertising SDK reference | PASS |
| DOC-001 | LOCAL_VERIFIED | `c8883fce` | release ADRs and 12-locale release notes; relative links and diff checked | PASS |
| DOC-002 | LOCAL_VERIFIED | `1e0183fd` | owner gates, blocked external evidence and redacted device E2E checklist | PASS |
| ENV-001 | UNVERIFIED | external GitHub settings | Required Reviewers and branch restrictions for both release environments | BLOCKED |
| FGS-001 | UNVERIFIED | Play Console | submitted foreground-service declaration matching final behavior | BLOCKED |
| CI-001 | CI_EMULATOR_VERIFIED | GitHub run `32778242684` / `26b650ee` | Direct and Play Kotlin compilation plus API 34/35 health, on-device FFmpeg/QuickJS, Share-to-download, background survival, SIGKILL, sticky process recreation and completed 4 MiB recovery download | PASS; debug APK artifact `sha256:c486ffdecf8a525335b4af570be9a46232fc3e3a908e8dd512dbea21f0cb5ef9` |
| CI-002 | IMPLEMENTED_UNVERIFIED | GitHub run `32763096501` / `a9f07989` | Direct Debug Kotlin compilation failed in `MediaHistoryActivity`: trailing action lambdas bound to the optional layout parameter; fixed in the successor commit | FAIL (no artifact) |
| CI-003 | IMPLEMENTED_UNVERIFIED | GitHub runs `32763790259`, `32770952566` | app build, health endpoint, ffmpeg and QuickJS passed on API 34/35; the legacy direct-HTTP download probe bypassed the TransferCoordinator, then attempted to start the non-exported service from adb shell. It is removed from the blocking CI path and retained for exact-Internal-AAB device verification. | HARNESS FAIL; no Play artifact |
| TEAM-001 | LOCAL_VERIFIED | frozen candidate source after `32778242684` | Coding, Critical Reviewer, Finance/Billing, Marketing, Listing and Documenter ACK the candidate source from their independent evidence rows; Listing ACK covers pipeline/manifest only and does not promote `ASSET-001` | PASS for candidate build only |
| ASSET-001 | UNVERIFIED | final UI commit | real phone, 7-inch and 10-inch captures with visual review | BLOCKED |
| AAB-001 | SIGNED_AAB_VERIFIED | GitHub run `32779999775` / `c1eff16f`; artifact `DownloadThat-v1.0.4.2-play-candidate` | package `de.classydl.app`; `1.0.4.2` / `1000402`; AAB `0fd3416a24ff5d1d0063e2cead744699fbb09f2a137a5a27373754a021ce8971`; upload certificate `5FBD61BCC8B23676E8E9CE337C51F7243461CB9C31C8190069325099353703CE`; CI signature/16 KiB/Python checks; CycloneDX 1.6 SBOM with 143 components; locally downloaded and independently rehashed | PASS; provenance records `fgsDeclarationConfirmed=false`; no Play upload |
| PIPE-002 | LOCAL_VERIFIED | post-candidate promotion verifier | verifier accepts a typed, recorded false FGS state while promotion independently requires current owner confirmation; nine targeted tests and exact downloaded-candidate verification pass | PASS; no AAB rebuild |
| PLAY-001 | UNVERIFIED | exact candidate | Internal Testing acceptance of the recorded AAB hash | BLOCKED |
| DEVICE-001 | UNVERIFIED | Internal candidate | redacted completion of `DEVICE_E2E_CHECKLIST.md` | BLOCKED |

Evidence must distinguish local tests, emulator CI, signed artifacts, Play
acceptance and real-device behavior. External screenshots are anonymized and
stored outside Git; this file contains only neutral references and hashes.

An evidence row changes from `UNVERIFIED`/`BLOCKED` only after direct
observation. Workflow source, a checked dispatch input, local unit tests or a
Chat transcript are not substitutes for Console, artifact or device evidence.
