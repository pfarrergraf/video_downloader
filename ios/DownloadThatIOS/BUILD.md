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

## Download engine

No embedded Python/yt-dlp — see `ios/README.md`'s "Download engine" section and
`docs/IPHONE_APP_PLAN.md` for why. Real extraction is native Swift:

- **YouTube** (single video, playlist, batch) via
  [`YouTubeKit`](https://github.com/alexeichhorn/YouTubeKit), a Swift Package
  dependency (added in `project.pbxproj` as an `XCRemoteSwiftPackageReference` —
  `xcodebuild`/Xcode resolves it automatically at build time over network, same as any
  other SPM dependency; no manual vendoring step).
- **Vimeo, Reddit** via native Swift JSON/manifest parsing, no extra dependency.
- **Distribution route decided**: EU alternative distribution (e.g. AltStore PAL), not
  the App Store — see `docs/IPHONE_APP_PLAN.md` M4. That's what makes shipping a real
  download engine viable at all: Apple's App Store review guidelines effectively
  prohibit apps that download third-party media, but that's a review policy, not an
  OS/sandbox restriction, so it doesn't apply outside the App Store.
- **Not in scope**: TikTok, Instagram, X/Twitter (auth-gated, break on the order of
  weeks — would recreate exactly the maintenance burden going native was meant to
  avoid). ffmpeg-based merging of separate audio/video streams (ffmpeg-kit is dead;
  iOS doesn't allow subprocess-exec of bundled binaries) — covered instead by native
  `AVFoundation` passthrough remux for H.264/HEVC+AAC, with progressive-format
  fallback otherwise.
