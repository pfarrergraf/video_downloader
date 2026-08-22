# Google Play purchase restore contract

This document is a repository guardrail for Android billing/licensing changes.

## User-facing mechanism

The Play build already exposes **Restore purchase / Käufe wiederherstellen** in the License section.

That button is the supported recovery path for a previously purchased Google Play Pro entitlement. It is **not** an email-based license lookup and must not be redesigned as one.

Expected flow:

1. The user presses **Restore purchase / Käufe wiederherstellen**.
2. Android calls `AndroidBridge.restorePurchases()`.
3. `PlayPurchaseController.restore()` queries Google Play Billing for currently owned `INAPP` purchases with `queryPurchasesAsync()`.
4. A matching DownloadThat Pro purchase is identified by `BuildConfig.PLAY_PRODUCT_ID`.
5. The app sends the Google Play `purchaseToken` to `/api/play/purchases/verify`.
6. The backend verifies that token against Google Play before granting or restoring entitlement.
7. A successfully verified owned purchase may reclaim/transfer the single Android license slot. Possession of a copied license key alone must never be sufficient to evict another active device.
8. The returned DownloadThat license key is synchronized into the embedded Python/local-server license manager so the download queue sees Pro immediately.

## No email restore

Do not depend on the purchaser's Google email address for restoration. The entitlement proof is the Google Play owned-purchase record and purchase token verification, not an email string entered by the user.

If a future account system is introduced, it may be an additional recovery surface, but it must not replace Play Billing ownership verification for Play purchases.

## Device identity

Restore and reinstall are separate concerns:

- Same-device uninstall/reinstall should normally produce the same reinstall-stable Android device identity.
- Restore purchase is the authoritative recovery path when local entitlement state is gone or when a verified Play purchase legitimately needs to reclaim the Android slot.
- A random install UUID must never again be used as the authoritative license device identity.

## Regression requirements

Any change touching billing, `restore()`, `queryPurchasesAsync`, `EntitlementApi.verifyPurchase`, `/api/play/purchases/verify`, `claimVerifiedDeviceSlot`, `InstallIdentity`, or `license_activations` must retain tests proving:

- the restore button is present in Play builds;
- the button calls `restorePurchases()`;
- restore queries owned Google Play purchases;
- the purchase token is verified server-side before slot transfer;
- no email lookup is required for Play restore;
- a plain copied license key cannot displace another active Android device;
- uninstall/reinstall on the same physical device does not create a false second-device failure;
- after restore, the embedded download queue recognizes Pro without waiting for its normal license-cache TTL.

If any of these properties are intentionally changed, update this document, `AGENTS.md`, the corresponding tests, and the internal-test checklist in the same change.