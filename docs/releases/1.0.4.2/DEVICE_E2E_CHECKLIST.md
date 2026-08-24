# DownloadThat 1.0.4.2 device E2E checklist

Owner-controlled execution only. Repository automation must not create a real
charge or issue a refund. Use Google Play license testing and an Internal-track
test order. Store no order number, tester email, payment data, device identifier
or unredacted screenshot in Git.

## Evidence header

| Field | Redacted value |
|---|---|
| Candidate AAB SHA-256 | `UNVERIFIED` |
| Candidate run and commit | `UNVERIFIED` |
| Version name / code | `UNVERIFIED` |
| Play acceptance UTC | `UNVERIFIED` |
| Primary device class / API | `UNVERIFIED` |
| Second device class / API | `UNVERIFIED` |
| Neutral tester ID | `UNVERIFIED` |
| Evidence archive reference | `UNVERIFIED` |

Preconditions: install only the Internal Play candidate whose hash matches the
header; enable a Play license tester and test payment instrument; confirm RTDN
and reconciliation observability; prepare a second physical Android device; do
not paste logs containing purchase tokens or device identifiers.

## Billing and entitlement

For each row record `PASS`/`FAIL`, UTC time and a redacted evidence reference.

| ID | Action | Expected result | Current |
|---|---|---|---|
| BILL-01 | Open purchase sheet, then cancel | No Pro grant; app remains usable as Free; no generic failure | UNVERIFIED |
| BILL-02 | Start a pending test purchase | Pending is shown; Pro is not granted before approval | UNVERIFIED |
| BILL-03 | Reject the pending test purchase | Free remains active; no stale Pro cache | UNVERIFIED |
| BILL-04 | Approve the pending test purchase | Backend verifies ownership; Pro reaches native and Python queue | UNVERIFIED |
| BILL-05 | Complete purchase, terminate app before callback, reopen | Foreground reconciliation restores the verified entitlement | UNVERIFIED |
| BILL-06 | Restart the process after verified purchase | Share and native search both see Pro without a quota mismatch | UNVERIFIED |
| BILL-07 | Trigger Restore purchase | Owned purchase is queried and token verified; no purchaser email is requested | UNVERIFIED |
| BILL-08 | Reinstall on the same physical device, then restore | Same-device identity is accepted; Pro is restored | UNVERIFIED |
| BILL-09 | Attempt activation on a real second device | One-device policy rejects the second slot without evicting the first | UNVERIFIED |
| BILL-10 | Interrupt network/Google API during reconciliation | Existing entitlement is not falsely revoked; recovery remains possible | UNVERIFIED |
| BILL-11 | Owner marks the Play test order refunded/voided | Authenticated RTDN causes Pro revocation; no app refund request exists | UNVERIFIED |
| BILL-12 | Suppress/miss RTDN, then run reconciliation | Google state revokes Pro through reconciliation | UNVERIFIED |
| BILL-13 | Repurchase with a new test token after confirmed revoke | Exactly one active entitlement remains; stale callbacks do not resurrect/clear it | UNVERIFIED |

The restore mechanism and device-slot rules are normative in
[Google Play restore contract](../../GOOGLE_PLAY_RESTORE_CONTRACT.md). Refund
authority and revoke rules are normative in
[Google Play refund policy](../../GOOGLE_PLAY_REFUND_POLICY.md).

## Transfer, FGS, search and media

| ID | Action | Expected result | Current |
|---|---|---|---|
| APP-01 | Open app, search and library without downloading | No `dataSync` notification is created | UNVERIFIED |
| APP-02 | Share a supported link, choose video, background app | Visible FGS starts before transfer; download completes | UNVERIFIED |
| APP-03 | Search and enqueue audio, then video | Enqueue is not blocked by stale search; both use the same entitlement | UNVERIFIED |
| APP-04 | Start a slow search, immediately start a new search | Old work is cancelled/bounded; stale result never replaces current result | UNVERIFIED |
| APP-05 | Swipe Activity from Recents during active download | Visible FGS and transfer continue; completion is reported | UNVERIFIED |
| APP-06 | Cancel an active download | Transfer stops cooperatively; no orphaned completed entry appears | UNVERIFIED |
| APP-07 | Retry a failed partial download | Retry obtains a transfer lease and resumes safely | UNVERIFIED |
| APP-08 | Let queue become empty | Execution gate closes; download notification and service stop | UNVERIFIED |
| APP-09 | Exercise API 35 `dataSync` timeout path | Active work is cancelled fail-closed and service stops promptly | UNVERIFIED |
| APP-10 | Upgrade from prior app data and reopen after interruption | Library migration is atomic/retryable; corrupt rows are quarantined | UNVERIFIED |
| APP-11 | Create, rename, reorder, play all and delete a playlist | Order persists; playlist deletion does not silently delete media files | UNVERIFIED |
| APP-12 | Remove/rename a downloaded file outside the app, then reopen | Reconciliation marks/removes the missing entry without crashing playback | UNVERIFIED |

## Completion gate

- [ ] Every row has an observed result and redacted evidence reference.
- [ ] No purchase token, order number, account address, tester email or raw
      device identifier appears in Git or shared logs.
- [ ] Failures are linked to an issue and keep `DEVICE-001` blocked.
- [ ] The candidate hash still matches `EVIDENCE_INDEX.md`; no rebuild occurred.
- [ ] Owner and Critical Reviewer sign off before later-track promotion.
