# DownloadThat native media player — architecture and rollout

Base commit: `d9fbc7bc10e8d2c4ccb947cef1a0aec77bcc5a26` (`before player`)

## Goal

Turn DownloadThat from a short-session downloader into a repeat-use media utility without destabilizing the existing Python/WebView download stack.

The player is deliberately native Android code. The downloader remains unchanged behind the existing localhost WebView/Python architecture.

## Architecture

- `PlayerActivity` — native playback UI and Android `ACTION_VIEW` entry point.
- `MediaPlaybackService` — owns one app-wide ExoPlayer + MediaSession.
- Media3 1.10.1 — current stable Media3 release when this feature was prepared.
- Existing `FileProvider` — hands app-private completed downloads to the player as `content://` URIs.
- Existing `android_bridge.open_file()` — now starts DownloadThat's player directly for completed downloads.
- External file managers — can offer DownloadThat for `audio/*`, `video/*`, and `application/ogg` through the manifest intent filter.

## Why Media3 / ExoPlayer

Media3 is Android's maintained playback stack and avoids introducing another large native runtime such as LibVLC. That matters for this repository because the Android package already contains Chaquopy, FFmpeg and QuickJS native payloads and must continue satisfying Play's native-library/page-alignment constraints.

Media3 supports progressive MP4/M4A/FMP4, WebM/Matroska, MP3, Ogg, WAV, MPEG-TS, MPEG-PS, FLV, ADTS/AAC, FLAC and AMR containers. Actual encoded audio/video sample support still depends on Android's available decoders on the device.

The shipped FFmpeg CLI remains a downloader/conversion tool; it is not wired in as a real-time decoder. Adding Media3's FFmpeg decoder extension would require a separately maintained native build and should only be considered after measuring real unsupported-codec failures on production devices.

## Background playback

The ExoPlayer instance lives in `MediaPlaybackService`, not the Activity. This gives:

- screen-off audio playback,
- app-switch/background audio,
- lock-screen and notification transport controls,
- Bluetooth/headset media controls,
- audio focus handling,
- automatic pause on unplugged headphones (`setHandleAudioBecomingNoisy(true)`).

The required `FOREGROUND_SERVICE_MEDIA_PLAYBACK` permission is added. No broad storage/media read permission is added.

## Storage / privacy model

External files arrive through the URI permission Android grants with the `ACTION_VIEW` intent. Internal files use the existing app-owned FileProvider. The implementation intentionally does **not** request `READ_MEDIA_VIDEO`, `READ_MEDIA_AUDIO`, `READ_EXTERNAL_STORAGE`, or `MANAGE_EXTERNAL_STORAGE`.

This keeps the feature compatible with scoped storage and minimizes Play Console permission review surface.

## Retention roadmap after the playback MVP

Do these only after the native playback path is green on CI and physical devices:

1. Persist `lastPositionMs` + `lastPlayedAt` locally and show **Continue listening / Continue watching**.
2. Add **Recently played** to the existing DownloadThat UI.
3. Add queue/playlist playback from completed downloads.
4. Add playback speed and sleep timer for audio.
5. Add Picture-in-Picture for video.
6. Add optional subtitle side-loading (WebVTT/SRT/SSA/ASS supported by Media3).
7. Instrument privacy-preserving local counters first; only add remote analytics after an explicit product/privacy decision.

The retention metric to watch is not raw session duration alone. Measure D1/D7 return rate, player starts per downloader completion, repeat playback starts, and percentage of completed downloads opened inside DownloadThat.

## Acceptance matrix

Minimum physical-device checks before merge/release:

- MP4 H.264/AAC downloaded by DownloadThat.
- WebM VP9/Opus.
- MP3.
- M4A/AAC.
- Ogg/Opus.
- WAV.
- FLAC.
- MKV with a platform-supported codec.
- File-manager `Open with -> DownloadThat` for MP4 and MP3.
- Home button while audio plays -> playback continues.
- Screen lock -> playback continues and lock-screen controls work.
- Headphones unplugged -> playback pauses.
- Incoming phone/audio-focus interruption -> playback behaves according to Android audio focus.
- Existing download queue continues to work while player is active.
- Play and direct product flavors both compile.

## CI guardrails

`tests/test_android_player_contract.py` guards the architectural contract without requiring an Android SDK. The repository's Android GitHub Actions workflow remains the authoritative compile/emulator check because `CLAUDE.md` explicitly documents that Android SDK verification is CI-only in this environment.
