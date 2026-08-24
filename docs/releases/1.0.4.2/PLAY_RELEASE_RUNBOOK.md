# Exact-artifact Play runbook

## Before building

1. Freeze the integration commit and require TEAM ACK from Coding, Critical
   Reviewer, Finance/Billing, Marketing, Listing and Documenter.
2. Confirm the Google Play foreground-service declaration is complete.
3. Query the highest version code known to Play. Use `v1.0.4.2` / `1000402` if
   free; otherwise choose the smallest higher `1.0.4.N` revision.
4. Run the final local and Android debug/emulator gates.

## Build candidate

Dispatch the candidate workflow once from the frozen commit. It may compile and
sign, but it must not upload to Play or create a GitHub release. Retain the AAB,
SBOM and provenance manifest together. Record the workflow run, commit, package,
version name/code, upload-certificate SHA-256 and AAB SHA-256.

A run that fails before producing a valid candidate consumes no Play version.
After a valid candidate manifest exists, do not rebuild that version.

## Promote candidate

Dispatch the promotion workflow with the candidate run id, artifact name and
expected AAB SHA-256. The workflow must download the existing artifact, verify
its provenance and certificate, and upload only to Internal Testing. It must not
run Gradle, compile or bundle anything.

Configuration-only upload failures retry the same artifact. A new AAB is allowed
only after a demonstrated code defect in the Internal candidate.

## After Internal acceptance

Run every `DEVICE_E2E_VERIFIED` scenario in `TEST_MATRIX.md`. Submit listing
changes only after those tests pass. Promote the existing Play release/version
to later tracks; never rebuild or re-upload a cosmetically changed bundle.
