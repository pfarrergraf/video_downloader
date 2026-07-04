# DownloadThat iOS

This folder contains the separate iPhone/iPadOS implementation path for DownloadThat.

It is intentionally not a copy of the Android project:

- Android uses Chaquopy to run the Python web server inside the app.
- Windows desktop uses a local Python/PyInstaller web entrypoint.
- iOS is a native SwiftUI + WKWebView shell with a native bridge. No embedded Python —
  see "Download engine" below for why and what replaces it.

## Current status

`DownloadThatIOS.xcodeproj` is a real, buildable Xcode project (verified via
`.github/workflows/ios-build.yml` on `macos-latest`, since there is no local macOS
toolchain in the dev sandbox this was built in). It builds, launches, loads the bundled
web UI in a `WKWebView`, exchanges JS/native bridge messages, validates licenses, and
downloads direct HTTP/HTTPS file URLs. YouTube/Vimeo/Reddit extraction is being added on
top of that (see "Download engine").

## Build route

```bash
xcodebuild \
  -project ios/DownloadThatIOS/DownloadThatIOS.xcodeproj \
  -scheme DownloadThatIOS \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO \
  build
```

See `DownloadThatIOS/BUILD.md` for the full local-Xcode workflow.

## Architecture

```text
SwiftUI App
  -> ContentView
  -> DownloadWebView (WKWebView)
  -> DownloadBridge (JS/native bridge)
       -> VideoExtractor (YouTube via YouTubeKit/JavaScriptCore, Vimeo/Reddit natively)
       -> URLSession-based direct file downloader
  -> LicenseClient (server validation)
  -> DeviceIdentity (Keychain-backed install id)
```

## Download engine

No embedded Python/yt-dlp on iOS — there's no Chaquopy equivalent with the same
institutional maturity for iOS, and vendoring a full CPython + yt-dlp runtime by hand
would be heavier and more fragile than the alternative. Instead, downloading is native
Swift throughout:

- **YouTube**: [`YouTubeKit`](https://github.com/alexeichhorn/YouTubeKit) (Swift
  Package, MIT) resolves stream URLs, using Apple's built-in `JSContext`
  (JavaScriptCore) to evaluate YouTube's own obfuscated cipher/n-parameter transform
  functions — the same idea as yt-dlp's Python-side `jsinterp.py`, just using Apple's
  real JS engine instead of a hand-rolled interpreter.
- **Vimeo / Reddit**: plain native Swift JSON/manifest parsing — both expose playable
  URLs directly with no cipher and no auth for public content.
- **Explicitly out of scope for now**: TikTok, Instagram, X/Twitter — auth-gated and
  volatile (yt-dlp's own issue tracker shows near-weekly breakage on these), which would
  recreate the maintenance burden going native was meant to avoid.
- **Merging separate audio/video streams**: no ffmpeg (ffmpeg-kit, the usual iOS
  wrapper, was retired by its maintainer in Jan 2025 with no maintained successor, and
  iOS doesn't allow apps to subprocess-exec bundled binaries the way Android's Chaquopy
  build does). Native `AVFoundation` passthrough remux covers H.264/HEVC+AAC; anything
  else (VP9/AV1/Opus) falls back to progressive (pre-muxed) formats, same as any
  ffmpeg-less system already does elsewhere in this codebase.

## Distribution

EU alternative distribution (DMA sideloading via a marketplace like AltStore PAL), not
the App Store — Apple's App Store review guidelines effectively prohibit apps that
download third-party media (independent of implementation language), but that
restriction is an App Review policy, not an OS-level one, so it doesn't apply outside
the App Store. Still requires Apple Developer Program enrollment and notarization
either way. See `docs/IPHONE_APP_PLAN.md` for the full distribution plan.
