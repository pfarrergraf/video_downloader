# Build DownloadThat iOS

## Prerequisites

- macOS with Xcode 16 or newer recommended.
- iOS 17 simulator runtime.
- No Apple Developer Team is required for simulator builds.
- A real iPhone build requires a signing team in Xcode.

## Open in Xcode

```bash
open ios/DownloadThatIOS/DownloadThatIOS.xcodeproj
```

Select the shared scheme:

```text
DownloadThatIOS
```

Then choose an iPhone simulator and press Run.

## Command-line simulator build

From the repository root:

```bash
xcodebuild \
  -project ios/DownloadThatIOS/DownloadThatIOS.xcodeproj \
  -scheme DownloadThatIOS \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO \
  build
```

This exact command is what `.github/workflows/ios-build.yml` runs on every push to
`iPhone`, on a `macos-latest` GitHub Actions runner — that CI run is the source of
truth for "does this project build," since there is no macOS/Xcode toolchain in the
Linux sandbox these changes were authored in. Check the Actions tab for the latest
run status before trusting a local build claim in a commit message.

If you want a named simulator instead, list available simulators:

```bash
xcrun simctl list devices available
```

Then use a concrete destination, for example:

```bash
-destination 'platform=iOS Simulator,name=iPhone 16'
```

## What should work now

- The app launches.
- `iphone_bootstrap.html` loads inside WKWebView.
- Native bridge sends `nativeReady`.
- Web UI asks for license status.
- License activation calls `GET https://downloadthat.pages.dev/api/validate` with
  query parameters (matching `pro/website/functions/api/validate.js`, the same
  endpoint Android and desktop use):
  - `key`
  - `platform=ios`
  - `device_id`: a SHA256 hash of the Keychain-backed install UUID, never the raw
    identifier (the server hashes whatever it receives again before storing it)
  - `app_version`
- Direct HTTPS/HTTP file URLs download through `URLSession`.
- Downloaded files are saved in the app Documents directory with collision-safe filenames.
- The UI shows success/failure and the saved local path.

## Still intentionally limited

The current iOS MVP supports direct file URLs only. The Android/desktop yt-dlp platform-download engine is intentionally not ported into iOS yet.

Reason: the iOS distribution route must be decided first:

- App Store restricted route with StoreKit/IAP and potentially narrower downloader capabilities;
- TestFlight-only prototype;
- EU/direct distribution route with the existing cross-platform license key;
- PWA-first fallback.

Do not enable broad platform downloading on iOS before that product/legal decision.
