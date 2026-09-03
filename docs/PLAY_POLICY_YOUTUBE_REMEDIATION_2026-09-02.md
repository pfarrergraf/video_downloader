# Google Play YouTube policy remediation — 2026-09-02

## Confirmed rejection evidence

- Google Play rejected `de.classydl.app` under Device and Network Abuse because
  the app accessed or used YouTube contrary to YouTube's Terms of Service.
- The cited German listing screenshot visibly says `YouTube, Instagram & Co.`.
- `assets/Videorecording Android Medien.mp4` is 69.313 seconds long and shows the
  same named-platform hint at the beginning and again around 00:25.
- The 2026-08-26 player/search-first change hid the manual URL card but promoted
  `SearchActivity`; that activity still queried YouTube and loaded YouTube-hosted
  thumbnails. Hiding the platform name was therefore not a sufficient policy fix.

## Implemented remediation

The `play` flavor now sets `BuildConfig.PLAY_POLICY_RESTRICTED=true`; the `direct`
flavor sets it to `false` so distribution behavior remains isolated.

For the Play flavor:

1. Search entry points on the home, player and library screens are hidden.
2. `SearchActivity` exits immediately if reached unexpectedly.
3. The flag is passed into the embedded Python runtime.
4. The authenticated `/api/queue` endpoint rejects `youtube.com`, every
   `*.youtube.com` subdomain and `youtu.be` before a job is persisted.
5. The rejection response is deliberately generic and does not advertise the
   blocked platform inside the app.

## Verification performed locally

- Targeted policy/server/Android-contract suite: `96 passed`.
- Full repository suite: `464 passed, 2 skipped`.
- Public claims scanner: `Public-claims policy: OK`.
- A fresh browser rendering of the current German WebView source was visually
  inspected and contains no named-platform hint. It is preview evidence only,
  not a substitute for an Android screenshot of the exact Play artifact.
- Host matching covers the apex domain, subdomains and short-link domain while
  rejecting lookalike-host false positives.
- Android compilation and device execution remain unverified locally because
  Android SDK/ADB are not installed on this workstation.

## Remaining release gates

- Build the next candidate with a deliberately incremented `versionCode` and a
  distinguishable `versionName`.
- Install the exact Play artifact on a device/emulator and verify: no Search
  affordance is visible; a shared or entered blocked-platform URL produces the
  generic unsupported-source response; ordinary supported links still queue.
- Capture fresh de-DE screenshots and every other required locale/form factor
  from that exact Play candidate. Do not upload any existing file in
  `store_assets/screenshots/` or the rejected video recording.
- Upload/review in Play Console remains an explicit owner action. Do not appeal
  on the theory that the old behavior was compliant; submit a corrected artifact
  and corrected listing assets.
