# AGENTS.md

Repository-wide engineering guardrails for Codex and other coding agents.

Before changing Android, licensing, purchases, release workflows, or persistence, also read `CLAUDE.md` and the relevant entries in `memory.md`.

## Critical licensing/device-identity invariant

**A normal app update, uninstall/reinstall on the same physical device, or clearing app-local state must not make a valid paid/tester license look as though it moved to a second device.**

This is a hard product invariant for DownloadThat and should be treated as a reusable design rule for future apps which implement device-limited licensing.

### Never do this

- Never use a random per-install UUID from `SharedPreferences`, app-private files, a local database, or similar uninstallable state as the authoritative *device* identity for license-slot enforcement.
- Never assume an identifier is device-stable merely because it survives process restarts or normal app updates.
- Never change the identity algorithm without an explicit migration path for already activated users.
- Never “fix” a reinstall problem by silently removing all device limits or by weakening purchase/refund anti-abuse rules globally.

A random install UUID is appropriate for an **installation identity**, but it is not a **device identity**. Android deletes normal app-private storage during uninstall, so a newly generated UUID after reinstall will be different. If the backend treats that UUID as the one allowed Android device, the same phone will be rejected as a second device.

### Required Android design

For Android device-slot licensing, use a reinstall-stable, privacy-preserving identifier derived from an Android identifier whose lifecycle matches the product requirement. For the current DownloadThat design (minSdk 26, same app signing identity), prefer a one-way derived value based on `Settings.Secure.ANDROID_ID`, namespaced for this app/protocol version, rather than sending the raw Android ID to the backend.

Example conceptual derivation:

`SHA-256("downloadthat-license-device-v1:" + ANDROID_ID)`

The exact implementation may evolve, but these properties must remain true:

1. Same physical Android device + same Android user + same app signing identity => same license device identity after uninstall/reinstall.
2. A genuinely different device normally yields a different identity.
3. Raw hardware identifiers are not required or transmitted.
4. Existing activations can migrate from an old identity scheme without locking out the legitimate user.
5. Google Play purchase ownership remains restorable independently through Play Billing; the custom license layer must not turn a legitimate Play restore into a false “second device” failure.

## Google Play restore contract

**Do not replace the existing Play restore flow with an email-based “restore key” mechanism.** The Play build already has the correct trust chain and it is a permanent product contract.

The supported flow is:

`Restore purchase / Käufe wiederherstellen` -> `AndroidBridge.restorePurchases()` -> `PlayPurchaseController.restore()` -> Google Play `queryPurchasesAsync()` -> matching `BuildConfig.PLAY_PRODUCT_ID` -> Google Play `purchaseToken` -> backend `/api/play/purchases/verify` -> `verifyAndApplyPlayPurchase()` -> verified entitlement -> Android device-slot reclaim/transfer -> immediate sync into the embedded `/api/license` path.

Rules that must remain true:

- Google Play ownership/purchase-token verification is the proof for restoring a Play purchase. A purchaser email address is not required and must not become the primary restore credential.
- The restore button must remain available in Play builds whenever Billing is available.
- A copied DownloadThat license key by itself must not evict another active Android device.
- A live Google-verified owned purchase may reclaim/transfer the one Android activation slot; this is the trusted recovery path for reinstall/device recovery.
- After a successful native Play restore, the embedded Python/local-server license cache must be updated immediately so the download queue does not remain on Free until its normal cache TTL expires.
- Do not remove `restorePurchases()`, `queryPurchasesAsync()`, purchase-token backend verification, or `claimVerifiedDeviceSlot` without an explicit replacement design and corresponding regression tests.

Read `docs/GOOGLE_PLAY_RESTORE_CONTRACT.md` before changing this flow.

### Migration requirement

Any device-identity version change is a data migration, not a local refactor. Before shipping it:

- identify the legacy identity and the new identity/protocol version;
- provide a server-authorized one-time migration or transfer path;
- prevent that migration path from becoming an unlimited device-transfer bypass;
- retain/revoke the old activation deliberately;
- test update, uninstall/reinstall, clear-data, restore-purchase, second-device rejection, and legitimate device-transfer scenarios.

### Mandatory regression tests

Changes touching `InstallIdentity`, `LicenseManager`, entitlement APIs, Google Play verification, `license_activations`, tester grants, refunds, or activation limits must include tests covering at least:

- update on the same installation keeps entitlement;
- uninstall/reinstall identity semantics are explicitly tested or documented with an instrumented/device test when JVM tests cannot model Android lifecycle behavior;
- the same physical device is not falsely rejected after reinstall;
- a second real device is still rejected when the product policy allows only one active Android device;
- migration from the previous identity scheme does not strand existing users;
- Play purchase restore still works after reinstall;
- the restore UI still invokes Google Play owned-purchase reconciliation and does not depend on purchaser email;
- no raw sensitive device identifier is logged, persisted server-side unnecessarily, or exposed to WebView/UI.

If any of these cannot be verified in the current environment, mark the item as **UNVERIFIED** rather than assuming it works.

## Release/version guardrail

Every Google Play test or production artifact must have a deliberately chosen, monotonically increasing `versionCode`. Test builds must also have a human-visible `versionName` which lets a tester distinguish the installed build from production without ADB. Do not upload a materially different test AAB under an indistinguishable visible version such as the same `1.0.3` unless there is a documented reason.

For branch/internal testing, prefer an explicit revision scheme supported by `scripts/android_version_from_tag.py`, for example `v1.0.4.1`, `v1.0.4.2`, etc., and verify the resulting `versionName`/`versionCode` before upload.

## Current incident to remember

In August 2026 DownloadThat's Android licensing used an install-scoped random UUID (`InstallIdentity`) as the server's Android device-slot key. Uninstalling the app deleted that UUID; reinstalling generated a new value; the backend therefore interpreted the same phone as another Android device and rejected the license while the previous activation was still considered active. This is the canonical regression this guardrail exists to prevent.

The same incident also confirmed why the existing **Restore purchase / Käufe wiederherstellen** path matters: restoring Play entitlement must be based on Google Play owned-purchase verification, not on an email lookup or mere possession of the human-readable license key.