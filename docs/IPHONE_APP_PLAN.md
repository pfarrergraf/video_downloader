# DownloadThat iPhone app plan

Branch: `iPhone`

## Goal

Prepare a separate iPhone implementation path without mixing iOS-specific code into the Android, desktop, CLI, or Python packaging flows.

The iPhone app must not be treated as a Chaquopy clone. Android can embed the Python core through Chaquopy; iOS needs a different strategy:

- Native Swift/SwiftUI shell.
- WKWebView for the shared Gothic-style UI where practical.
- Native Swift bridge for license state, device identity, file import/export, and platform-specific storage.
- No bundled Python runtime as the first milestone.
- No hidden downloaded executable code.
- No App Store submission until the review/compliance risk is explicitly decided.

## Apple policy constraints that shape the architecture

1. The iOS app must be self-contained and must not download, install, or execute code that changes app functionality.
2. Apps that browse the web must use the appropriate WebKit framework.
3. Unlocking digital features inside an App Store-distributed iOS app normally requires Apple In-App Purchase, unless a specific exception or entitlement applies.
4. Apps that save, convert, or download media from third-party sources need explicit authorization from those sources. This is the largest App Store review risk for DownloadThat.

## Product decision for iPhone

The iPhone app should share the same product model as Android and desktop:

- Free tier: 3 downloads per rolling 24h window.
- Pro: unlimited downloads plus batch/playlist features where legally and technically available.
- Same cross-platform license identity as Android, Windows, macOS, and Linux.
- Device slot: one iOS/iPadOS slot per license key.

However, App Store distribution may require Apple In-App Purchase for unlocking iOS Pro features. Therefore the iPhone branch supports two possible commercial routes:

### Route A — App Store-compliant iOS version

Use StoreKit 2 for iOS Pro purchase/restore. The server links the Apple transaction to the existing cross-platform license account. Existing web/Android/desktop keys may unlock previously purchased access only if the App Store rules allow that flow for this app category at submission time.

This route is safer for broad distribution but may force Apple IAP and App Review limitations.

### Route B — EU alternative distribution / direct distribution candidate

Use the existing web/Stripe license key flow, device activation, and cross-platform key. This route is strategically interesting for EU distribution but requires separate Apple entitlement/notarization planning and may not be available globally.

### Route C — TestFlight/internal prototype

Use a developer/test build to validate UI, storage, license activation, file handling, and device identity without making any App Store distribution promises.

## Separate iOS folder layout

```text
ios/
  README.md
  DownloadThatIOS/
    App/
      DownloadThatIOSApp.swift
      ContentView.swift
      DownloadWebView.swift
      Info.plist
    Bridge/
      AppConfig.swift
      DeviceIdentity.swift
      LicenseClient.swift
      DownloadBridge.swift
    Resources/
      iphone_bootstrap.html
    Tests/
      README.md
```

This folder is intentionally separate from:

- `android/`
- `video_downloader/`
- `classydl_web_entry.py`
- `pro/website/`

## Code flow

### 1. App launch

`DownloadThatIOSApp` starts the SwiftUI app and shows `ContentView`.

### 2. Web UI container

`ContentView` hosts `DownloadWebView`, a WKWebView wrapper. The first milestone loads `Resources/iphone_bootstrap.html`, not the Python server UI.

Reason: iOS cannot simply start the Python `video_downloader.web.server` flow used by Android/desktop.

### 3. Native bridge

JavaScript posts messages to the Swift bridge:

```text
licenseStatus
activateLicense
pickOutputLocation
startDownload
openSettings
```

Swift receives those messages through `WKScriptMessageHandler`.

### 4. License validation

`LicenseClient` calls the existing license API with:

```json
{
  "key": "...",
  "platform": "ios",
  "device_id": "hashed-device-install-id",
  "app_version": "..."
}
```

The API should eventually enforce one iOS slot per key.

### 5. Device identity

`DeviceIdentity` creates a random install UUID, stores it in Keychain, and hashes it before sending it to the license server.

Do not use IDFA. Do not use device serials. Do not send raw device identifiers.

### 6. Download capability

Milestone 1 does not port yt-dlp to iOS. It implements a native Swift stub and separates legal/compliance decisions from UI wiring.

Possible later implementations:

- direct-file URL download via URLSession;
- backend-assisted metadata resolver;
- user-owned/cloud-file workflows;
- EU/direct-distribution build with broader behavior if legally approved.

## Milestones

### M0 — Repository scaffold

- Create `iPhone` branch.
- Add isolated `ios/` folder.
- Add SwiftUI/WKWebView skeleton.
- Add license/device bridge skeleton.
- Add App Store risk notes.

### M1 — Local Xcode project

- Create real Xcode project from `ios/DownloadThatIOS` sources.
- Build and run on simulator.
- Validate WKWebView bridge events.

### M2 — License integration

- Extend `/api/validate` to accept `platform=ios`, `device_id`, and `app_version`.
- Add iOS slot enforcement.
- Persist consent/license activation server-side.

### M3 — Download prototype

- Start with direct-file downloads only.
- Save via Files-compatible document picker or app sandbox.
- Add clear legal warning before first use.

### M4 — Distribution decision

Choose one:

- TestFlight-only prototype;
- App Store-compliant restricted version;
- EU alternative distribution candidate;
- PWA-first iPhone path.

## Non-goals for this branch

- No immediate App Store submission.
- No Python bundling promise.
- No attempt to bypass Apple review.
- No torrent/downloader behavior hidden from review.
- No automatic Stripe unlock inside an App Store build unless confirmed allowed for the chosen route.
