# ADR-002: Revisioned entitlement convergence

Status: Accepted for 1.0.4.2

## Decision

Native Android and the embedded Python queue converge on one persisted desired
entitlement state: monotone revision, `SET` or `CLEAR`, optional key and change
time. Python applies a revision idempotently, ignores older commands and retains
`CLEAR` as a tombstone. Native backend callbacks carry their request epoch so a
late validation result cannot resurrect entitlement after a newer revocation.

## Consequences

- A queue operation waits for runtime readiness and application of its desired
  entitlement revision.
- Reapplying the same key does not destroy a still-valid offline grace after a
  transient network failure.
- Authenticated revocation and a newer verified purchase remain ordered.
- Play restore and reinstall-stable device identity are unchanged.

The authoritative purchase-token, restore and device-slot requirements remain
in the [Google Play restore contract](../../../GOOGLE_PLAY_RESTORE_CONTRACT.md).
Real purchase, restore, revoke and device behavior is not proven by local source
tests and remains `UNVERIFIED` until the device checklist is completed.

