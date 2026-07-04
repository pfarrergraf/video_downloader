# DownloadThat iOS

This folder contains the separate iPhone/iPadOS implementation path for DownloadThat.

It is intentionally not a copy of the Android project:

- Android uses Chaquopy to run the Python web server inside the app.
- Windows desktop uses a local Python/PyInstaller web entrypoint.
- iOS starts as a native SwiftUI + WKWebView shell with a native bridge.

## Current status

This is a scaffold branch. It defines the code flow and the first Swift source files, but it is not yet a complete Xcode project.

## Build route

Recommended next step on a Mac:

1. Create a new Xcode iOS App project named `DownloadThatIOS`.
2. Copy or add the files from `ios/DownloadThatIOS/` into the Xcode project.
3. Set bundle identifier, signing team, and deployment target.
4. Run on simulator first, then a real iPhone through Xcode.
5. Keep all iOS-only work inside `ios/` until the architecture is stable.

## Architecture

```text
SwiftUI App
  -> ContentView
  -> DownloadWebView (WKWebView)
  -> DownloadBridge (JS/native bridge)
  -> LicenseClient (server validation)
  -> DeviceIdentity (Keychain-backed install id)
```

## Distribution warning

Do not assume App Store approval for the full Android/desktop downloader feature set. Apple review rules are a product constraint here, not just a packaging problem.

The first iPhone version should prove:

- UI loads;
- JavaScript-to-Swift bridge works;
- license activation works;
- iOS device slot can be tracked;
- direct file download/storage flow can be tested safely;
- App Store vs EU/direct distribution decision is made before public release.
