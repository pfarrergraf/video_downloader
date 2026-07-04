# iOS testing checklist

## Local simulator

- Create Xcode project from the files in `ios/DownloadThatIOS`.
- Add `iphone_bootstrap.html` to Copy Bundle Resources.
- Run on iPhone simulator.
- Confirm bootstrap UI appears.
- Confirm `nativeReady` event triggers.
- Confirm license status round-trip works.

## Real iPhone

- Configure signing team.
- Install through Xcode.
- Confirm Keychain install id survives app restart.
- Confirm license validation sends platform `ios` and a pseudonymous device hash.
- Confirm no raw device identifier is sent.

## Store/distribution decision tests

- App Store route: verify StoreKit 2 purchase/restore path before exposing Pro unlock.
- TestFlight route: do not charge TestFlight users.
- EU/direct route: document entitlement/notarization requirements before enabling Stripe unlock.

## Download engine tests

The first iOS milestone must keep the download engine disabled. Enable real downloads only after a written product/legal decision.

Potential future tests:

- direct file URL download via URLSession;
- save to app sandbox;
- export to Files app;
- progress UI;
- free daily limit enforcement;
- Pro limit bypass;
- failed URL handling;
- user-facing rights warning.
