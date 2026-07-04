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
  -destination 'platform=iOS Simulator,name=iPhone 16' \
  CODE_SIGNING_ALLOWED=NO \
  build
```

If the named simulator does not exist, list available simulators:

```bash
xcrun simctl list devices available
```

Then replace the destination name.

## What should work now

- The app launches.
- `iphone_bootstrap.html` loads inside WKWebView.
- Native bridge sends `nativeReady`.
- Web UI asks for license status.
- License activation calls `https://downloadthat.pages.dev/api/validate` with:
  - key
  - platform: ios
  - pseudonymous device hash
  - app version
- Download button intentionally returns `ios_download_engine_not_enabled_yet`.

## Known intentional limitation

The actual iOS download engine is disabled until the distribution route is decided:

- App Store restricted route;
- TestFlight prototype;
- EU/direct distribution;
- PWA-first fallback.

Do not try to port the Android/desktop Python download engine into iOS before this decision.
