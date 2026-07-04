# DownloadThat iPhone app plan

Branch: `iPhone`

## Goal

Prepare a separate iPhone implementation path without mixing iOS-specific code into the Android, desktop, CLI, or Python packaging flows.

The iPhone app must not be treated as a Chaquopy clone. Android can embed the Python core through Chaquopy; iOS needs a different strategy:

- Native Swift/SwiftUI shell.
- WKWebView for the shared Gothic-style UI where practical.
- Native Swift bridge for license state, device identity, file import/export, and platform-specific storage.
- No bundled Python runtime, full stop — not just "not yet." Chaquopy exists because
  Android/Gradle has mature, institutional tooling for embedding CPython; the closest
  iOS equivalent (BeeWare's `Python-Apple-support`) is built for apps that *are* Python
  via Briefcase, not for bolting a scripting runtime onto a hand-maintained Swift app.
  The download engine itself (see "Download capability" below) is native Swift, not a
  vendored copy of `yt-dlp`.
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

### Route B — EU alternative distribution / direct distribution candidate (chosen route)

Use the existing web/Stripe license key flow, device activation, and cross-platform key. This is the chosen distribution route: list via an existing alternative marketplace (e.g. AltStore PAL) rather than operating an independent marketplace (which requires a €1M standby letter of credit under Apple's Alternative App Marketplace terms). Still requires Apple Developer Program enrollment and app notarization — those are OS-level/DMA-compliance requirements, not App Review policy, so they apply regardless of distribution route. EU DMA fee terms have changed more than once in the past year (a flat per-install Core Technology Fee was replaced by a 5% Core Technology Commission on 2026-01-01) and remain contested — re-verify current terms before committing, since they affect Pro-license margins on this channel specifically.

This route is why the App Store's media-download restriction (see "Apple policy constraints" above) doesn't block the real download engine here: that restriction is an App Review policy, not an OS/sandbox rule, so it doesn't apply outside the App Store.

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

No `yt-dlp` on iOS, ever — not a deferred milestone, an architectural decision. The
download engine is native Swift throughout:

- **YouTube**: [`YouTubeKit`](https://github.com/alexeichhorn/YouTubeKit) (Swift
  Package, MIT, actively maintained) resolves stream URLs. It reimplements YouTube's
  simple signature cipher natively in Swift, and for the harder n-parameter throttling
  challenge it extracts YouTube's own transform function from the current player JS and
  evaluates it in `JSContext` (Apple's built-in JavaScriptCore) — the direct Swift
  analog of yt-dlp's own `jsinterp.py` (evaluate just the one small function, not a full
  browser), using Apple's real JS engine instead of a hand-rolled interpreter.
- **Vimeo, Reddit**: native Swift JSON/manifest parsing — both expose playable URLs
  directly with no cipher and no auth for public content.
- **Explicitly excluded**: TikTok, Instagram, X/Twitter — auth-gated, anti-bot arms
  races that break on the order of weeks (confirmed by yt-dlp's own issue tracker
  through 2025-2026). Including them would recreate the multi-extractor maintenance
  treadmill that going native was meant to avoid.
- **Merging separate audio/video streams**: no ffmpeg. `ffmpeg-kit` (the usual iOS
  wrapper) was retired by its maintainer in Jan 2025 with no maintained successor, and
  iOS does not allow apps to subprocess-exec bundled binaries the way Android's Chaquopy
  build execs a disguised ffmpeg CLI binary — that's an OS/sandbox restriction, not an
  App Review policy, so it applies under EU sideloading too. Native `AVFoundation`
  passthrough remux (`AVMutableComposition` + `AVAssetExportSession`, `.passthrough`)
  covers H.264/HEVC video + AAC audio with no re-encoding; anything else (VP9/AV1/Opus,
  common in higher-quality YouTube DASH tiers) falls back to progressive (pre-muxed)
  formats — the same fallback any ffmpeg-less system already uses elsewhere in this
  codebase, just expressed in Swift instead of Python.
- Batch and playlist follow the same shape already used by the shared web UI: batch is
  client-side fan-out (one job per line), and a playlist is enumerated (YouTube's
  `browse` endpoint, plain JSON, no cipher needed just to list video IDs) into that same
  per-video fan-out — no new job-queue concept needed on iOS.

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

- Direct-file downloads via URLSession (done).
- Save via Files-compatible document picker or app sandbox.
- Add clear legal warning before first use.

### M3.5 — Real extraction engine (YouTube/Vimeo/Reddit)

- Add `YouTubeKit` as a Swift Package dependency; resolve YouTube stream URLs through
  it (JavaScriptCore-backed cipher/n-parameter solving).
- Native Swift extraction for Vimeo and Reddit (no cipher/auth needed).
- Playlist enumeration (YouTube `browse` endpoint) and batch (client-side fan-out),
  feeding the same per-video extraction + existing URLSession download pipeline.
- Local free-tier quota (3 downloads/24h) and Pro bypass, mirroring
  `web/server.py`'s `_recent_job_count`/`FREE_DAILY_DOWNLOAD_LIMIT` semantics.
- Fast-follow: `AVFoundation` passthrough remux for separate audio/video streams,
  constrained to H.264/HEVC+AAC.

### M4 — Distribution decision (decided: EU alternative distribution)

Route B (EU alternative distribution via an existing marketplace like AltStore PAL) is
the chosen route — see "Route B" above. Apple Developer Program enrollment and
notarization are still required. TestFlight remains useful as a pre-release internal
testing step regardless of the final distribution channel.

## Non-goals for this branch

- No App Store submission (distribution is EU alternative/sideloading — see M4).
- No embedded Python runtime, ever — the download engine is native Swift
  (`YouTubeKit`/JavaScriptCore for YouTube, native parsing for Vimeo/Reddit), not a
  vendored copy of `yt-dlp`.
- No hidden downloaded executable code — `YouTubeKit`'s bundled JS (parser/codegen/
  helper for extracting YouTube's own cipher functions) ships in the app bundle at
  build time like any other resource; nothing is fetched or executed at runtime that
  wasn't part of the notarized build.
- No TikTok/Instagram/X-Twitter extraction — auth-gated and volatile, out of scope
  (see "Download capability" above).
- No automatic Stripe unlock inside an App Store build, moot for now since the chosen
  route (Route B) isn't the App Store.
