# DownloadThat internal test — 1.0.4.1

Planned internal-test build for the `feat/native-media-player` branch.

## Release identity

Use the repository's manual **Android release** workflow on the `feat/native-media-player` branch with:

- version: `v1.0.4.1`
- expected `versionName`: `1.0.4.1`
- expected `versionCode`: `1000401`
- `upload_to_play`: only when deliberately creating/updating the Google Play **Internal testing** release
- `publish_github_release`: false unless a direct APK release is explicitly wanted

Do not reuse visible version `1.0.3` for this materially different player build. A tester should be able to identify the installed build from Android/Play UI without ADB.

No merge to `master` and no Production/Open testing rollout is part of this test.

## Why 1.0.4.1

`scripts/android_version_from_tag.py` maps `vMAJOR.MINOR.PATCH.REVISION` monotonically. `v1.0.4.1` becomes `versionName=1.0.4.1` and `versionCode=1000401`, leaving `1.0.4.2`, `.3`, etc. available for internal-test fixes before a later production release decision.

Always confirm in Play Console that the versionCode is higher than every artifact already uploaded to the app before starting the release.

## Tester acquisition

Use the opt-in URL belonging to the intended Play testing track while signed into Google Play with the tester Google account. Do not infer the installed track from the Store listing alone.

After install/update, verify the installed version is `1.0.4.1` (or its exact later internal revision) before recording test findings.

## Licensing regression fixed in this branch

Historical bug: Android used a random per-install UUID as the backend device-slot identity. Uninstalling deleted the UUID, so reinstalling the app on the same phone looked like a second Android device and the license was rejected.

New invariant:

- Android device-slot identity is derived locally as SHA-256 of a DownloadThat namespace plus `Settings.Secure.ANDROID_ID`.
- The raw Android ID is never sent to the backend.
- Same device + Android user + app-signing identity should therefore get the same derived device identity after a normal uninstall/reinstall.
- An ordinary license-key validation cannot evict another active device.
- A Google Play purchase which is freshly verified by purchase token may claim/transfer the one Android slot. This is the reinstall/device-transfer recovery path for Play purchases.
- After a native entitlement succeeds, Android immediately pushes the same license key through the authenticated localhost `/api/license` route so the Python download queue cannot remain stuck on a cached pre-restore `device_allowed=false` result.

This design is intentionally documented as a reusable engineering rule in root `AGENTS.md`.

## Internal-test licensing matrix

Run these on the Play-distributed build:

1. Existing Play purchase, normal app update -> Pro remains active.
2. Uninstall -> reinstall from the internal-test opt-in/store path -> owned purchase restores and Pro becomes active.
3. Reinstall -> enter/restore the existing license -> no false "already active on another device" for the same phone after Play ownership reconciliation.
4. Close/reopen app -> Pro remains active.
5. Restart phone -> Pro remains active.
6. Queue a download immediately after restore -> queue must recognize Pro; no six-hour stale-cache window.
7. Second real Android device using only a copied license key -> must not displace the active device.
8. Second real Android device with the same genuinely owned Play purchase -> verified restore may transfer the single Android slot; first device must fail its next fresh validation. Treat this as device transfer, not simultaneous multi-device entitlement.
9. Refund/revocation -> existing refund/revocation behavior still disables the entitlement.

## Player/search regression matrix

Keep the existing PR #43 physical-device matrix: local video/audio playback, background audio, Bluetooth/headset, PiP, resume/history/playlist/speed/sleep, search -> Video/Audio queue, Free quota, simultaneous download + playback, and the hard rule that DownloadThat never embeds a YouTube stream/player or YouTube-served ads in its native player.

## Go/No-Go

Do not start wider rollout unless:

- Android compile/release build is green;
- Security/CodeQL/unit/contract tests are green;
- the Play-delivered `1.0.4.1` build is confirmed on a physical tester device;
- uninstall/reinstall restores Pro on that same device;
- a download queued immediately after restore is treated as Pro;
- no regression appears in existing download/billing/refund paths;
- native player only plays local/content media and does not embed remote YouTube playback.
