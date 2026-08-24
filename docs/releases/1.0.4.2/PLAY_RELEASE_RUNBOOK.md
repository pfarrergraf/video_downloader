# Exact-artifact Play runbook

This runbook authorizes no production promotion, real payment, refund or Play
Console declaration by itself. External actions require the named owner gate and
must be recorded in `EVIDENCE_INDEX.md` at their actually observed level.

## External controls to configure and verify

The workflow files reference these GitHub Environments, but repository source
cannot prove their protection settings:

| Environment | Required external control | Allowed use |
|---|---|---|
| `android-candidate-signing` | Required Reviewer who is not the dispatcher; deployment branch limited to `release/v1.0.4.2-team`; signing and Play read-only secrets | Version query and one candidate build |
| `google-play-internal` | Owner Required Reviewer; deployment branch limited to `release/v1.0.4.2-team`; least-privilege Play service account | Upload verified existing bytes to Internal Testing only |

The owner records a redacted settings screenshot/reference after checking both
environments. Secret values, account identifiers and reviewer identities never
enter Git.

## Before building

1. Freeze the integration commit and require TEAM ACK from Coding, Critical
   Reviewer, Finance/Billing, Marketing, Listing and Documenter.
2. Record whether the Google Play foreground-service declaration is complete;
   an unconfirmed declaration blocks promotion, not creation of signed bytes.
3. Query the highest version code known to Play. Use `v1.0.4.2` / `1000402` if
   free; otherwise choose the smallest higher `1.0.4.N` revision.
4. Run the final local and Android debug/emulator gates.

The FGS confirmation must describe actual transfer-scoped `dataSync` behavior
and the separate `mediaPlayback` service. A checked workflow input is not proof
that the Play Console declaration was submitted; record the Console observation
separately. API 34 and API 35 CI must be green on the frozen commit.

## Build candidate

Dispatch the candidate workflow once from the frozen commit. It may compile and
sign, but it must not upload to Play or create a GitHub release. Retain the AAB,
SBOM and provenance manifest together. Record the workflow run, commit, package,
version name/code, upload-certificate SHA-256 and AAB SHA-256.

A run that fails before producing a valid candidate consumes no Play version.
After a valid candidate manifest exists, do not rebuild that version.

Do not dispatch while Android CI or any TEAM candidate role remains
`BLOCKED`/`UNVERIFIED`. Missing real phone/tablet assets and an unconfirmed Play
FGS declaration remain explicit promotion/listing blockers; the candidate
provenance records the actual FGS confirmation input. Listing capture jobs may
use debug artifacts but never the candidate AAB.

## Promote candidate

Dispatch the promotion workflow with the candidate run id, artifact name and
expected AAB SHA-256. The workflow must download the existing artifact, verify
its provenance and certificate, and upload only to Internal Testing. It must not
run Gradle, compile or bundle anything.

Promotion additionally requires the owner-confirmed Play foreground-service
declaration. A checked input is authorization for the workflow gate, while the
separate redacted Console observation remains the evidence for `FGS-001`.

Configuration-only upload failures retry the same artifact. A new AAB is allowed
only after a demonstrated code defect in the Internal candidate.

The `google-play-internal` Required Reviewer is the final external authorization
for this mutation. Approval covers only upload to Internal Testing; it does not
authorize production, price changes, purchases, refunds or account changes.

## After Internal acceptance

Run every `DEVICE_E2E_VERIFIED` scenario in `TEST_MATRIX.md`. Submit listing
changes only after those tests pass. Promote the existing Play release/version
to later tracks; never rebuild or re-upload a cosmetically changed bundle.

Use `DEVICE_E2E_CHECKLIST.md`. Play Billing scenarios use Play license-test
instruments and an owner-controlled test order. Automation must not create an
actual charge or issue a refund. Evidence is redacted before its neutral
reference is added to Git.
