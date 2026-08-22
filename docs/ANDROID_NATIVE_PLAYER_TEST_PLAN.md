# Native player test and internal-release plan

Status: implementation branch `feat/native-media-player`; no merge to `master`.

## Release boundary

- Version for this isolated test cycle: `v1.0.4` / `versionCode 1000400`.
- The Android release workflow is manual. Both GitHub-release publishing and
  Google Play upload default to off and require separate explicit selection.
- Google Play uses the signed `playRelease` AAB. The Direct debug APK is for
  first-device sideload testing only.
- No production, closed, or open rollout is in scope.

## Go/no-go before Internal Testing

Go requires a green Android build, a successful Samsung-device APK test,
working core downloads, local playback of MP4/H.264/AAC, WebM/VP9/Opus, MP3,
M4A/AAC, Ogg/Opus, WAV, and FLAC, and no direct remote or YouTube playback in
the DownloadThat player.

MKV, HEVC, and AV1 are best effort: an unsupported device codec must report a
playback failure without crashing. A regular DownloadThat output failing in a
core format is a no-go; do not silently add LibVLC or a Media3 FFmpeg decoder.

## Device matrix

On the current Samsung Galaxy test: cold start, URL entry, Share Target,
video/audio queueing, Free limit, Pro state, parallel playback/download,
history, playlist, speed, sleep timer, PiP, rotation, screen-off, lock screen,
Bluetooth, headset removal, audio focus, network loss, invalid URLs, app close
during download, and process restart.

Negative tests must prove that `http://`/`https://` single-media intents,
playlist entries, history entries, and external intents never become a native
player MediaItem. External local `content://` files may play but are not
retained in history or resume state.

## Deferred owner task: Play Billing test account

After a stable Internal build has been installed through the genuine Play
Internal Testing link, set up a License Tester and a track tester, then test a
Play test purchase, restore, pending purchase, refund, and revocation. This is
required before a future production decision but does not block the local APK
phase.
