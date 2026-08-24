# DownloadThat 1.0.4.2 test matrix

`UNVERIFIED` is intentional until the matching environment has actually run the
scenario. Never infer device or Play behavior from source assertions.

| Area | Scenario | Required level | Current |
|---|---|---|---|
| Runtime | concurrent start, bind failure, retry, listener attach/detach | CI_EMULATOR_VERIFIED | LOCAL_VERIFIED |
| FGS | no idle notification; every queue producer obtains a transfer lease | CI_EMULATOR_VERIFIED | LOCAL_VERIFIED |
| FGS | background transfer, retry, recovery, timeout and idle stop | DEVICE_E2E_VERIFIED | UNVERIFIED: the former adb-shell queue probe bypasses the non-exported, user-gesture-bound transfer contract; verify on the exact Internal AAB |
| Entitlement | slow server, restart, SET/CLEAR revision ordering, offline grace | CI_EMULATOR_VERIFIED | LOCAL_VERIFIED |
| Billing | cancel, pending, purchased, lost callback, restore | DEVICE_E2E_VERIFIED | UNVERIFIED |
| Billing | refund/void, missed RTDN reconciliation, repurchase | DEVICE_E2E_VERIFIED | UNVERIFIED |
| Identity | reinstall same device and reject a second device | DEVICE_E2E_VERIFIED | UNVERIFIED |
| Search | cursor paging, expiry, rotation, stale results, bounded thumbnails | CI_EMULATOR_VERIFIED | LOCAL_VERIFIED |
| Library | atomic legacy migration, retry, corrupt row, reconciliation | CI_EMULATOR_VERIFIED | LOCAL_VERIFIED |
| Player | missing file, resume, playlist ordering and play-all | CI_EMULATOR_VERIFIED | LOCAL_VERIFIED |
| Listing | 50 UI locales, 86 Play mapping, RTL and default inheritance | LOCAL_VERIFIED | BLOCKED: real captures absent |
| Artifact | package, version, upload certificate, 16 KiB, SBOM and hash | SIGNED_AAB_VERIFIED | UNVERIFIED |

Real Play evidence records only neutral test IDs, candidate hash, UTC time,
expected/actual outcome and a redacted evidence reference. Do not store GPA
numbers, account addresses, tester emails or payment data in Git.

The executable owner checklist for device, Billing, identity, FGS and library
scenarios is [DEVICE_E2E_CHECKLIST.md](DEVICE_E2E_CHECKLIST.md). Every row starts
`UNVERIFIED`; do not bulk-promote rows based on a single successful install.
