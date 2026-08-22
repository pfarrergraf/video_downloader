# DownloadThat native player + retention/discovery — 2026-08-21

## Base and scope

The feature branch is based on commit `d9fbc7bc10e8d2c4ccb947cef1a0aec77bcc5a26` (`before player`).

The Android app now has two product loops instead of only one:

1. **Acquire** — share/paste a supported URL or search by title, then queue video/audio through the existing downloader.
2. **Retain** — play media in DownloadThat, resume later, keep recent history, queue recent items, use playback speed, sleep timer and video PiP.

## Player architecture

- AndroidX Media3/ExoPlayer `1.10.1`.
- `MediaPlaybackService` owns the app-wide player and `MediaSession`.
- `PlayerActivity` is a controller/surface only.
- Background audio and Android system transport controls remain active through the media session service.
- `ACTION_VIEW` for `video/*`, `audio/*` and `application/ogg` lets Android offer DownloadThat in compatible file-manager “Open with” flows.
- Internal completed downloads route directly to `PlayerActivity` through the existing `FileProvider`.
- No `READ_MEDIA_*`, legacy storage or all-files permission is introduced.

## Phase 2 retention features implemented

### Continue watching / listening

`PlaybackRetentionStore` checkpoints playback every five seconds and on stop/end. A media item resumes only when the previous checkpoint is meaningful: at least five seconds in and not effectively completed.

History stays local in app-private SharedPreferences. `allowBackup=false` means it is not restored to a new install by Android backup.

### Recently played

`MediaHistoryActivity` shows up to 30 recent items with:

- title;
- saved position;
- duration when known;
- “continue” vs. “play again” semantics;
- clear-history control.

### Local playback queue

“Play recent” builds a Media3 playlist from up to 20 recent items and hands the playlist to the existing service-owned player. Media3 therefore supplies next/previous behavior through normal player/system controls.

### Playback speed

The player cycles through `1.0x -> 1.25x -> 1.5x -> 2.0x -> 0.75x` and persists the selected speed locally.

### Sleep timer

The UI cycles `off -> 15 -> 30 -> 60 -> off`. The deadline is persisted locally and enforced by `MediaPlaybackService`, not by the Activity, so closing the player screen does not silently cancel the timer while background audio continues.

### Picture in Picture

`PlayerActivity` is PiP-enabled for video. Android 12+ uses auto-enter while older supported Android versions enter PiP from `onUserLeaveHint()` when video is playing. Player chrome is hidden in PiP.

## Media discovery / search-to-download

`SearchActivity` is reachable from both the main DownloadThat screen and the native player/history surfaces.

Flow:

1. user enters a title/artist/video query;
2. `video_downloader.media_search` uses the already-bundled in-process yt-dlp runtime to request four metadata-only search results;
3. the app renders title, uploader/duration and a restricted YouTube thumbnail URL;
4. each result has **Video** and **Audio** actions;
5. the selected result is submitted to the existing authenticated `/api/queue` endpoint via `LocalApiClient`.

The important architectural rule is step 5: discovery does **not** write directly to `QueueStore` and does not create a parallel downloader. The existing API remains authoritative for free-tier quota, Pro entitlement, source normalization, quality defaults and queue behavior.

The search helper is intentionally metadata-only (`skip_download=True`, flat search extraction). It does not stream audiovisual content into the search screen.

## YouTube advertising / embedded playback non-goal

This branch does **not** add an ad blocker, alter an embedded YouTube player, suppress YouTube ads, or market DownloadThat as a “YouTube without ads” client.

Current YouTube API developer policies explicitly prohibit modifying/blocking ads shown by YouTube/API services and prohibit modifying or blocking parts of the YouTube player. Therefore an ad-suppression layer is intentionally kept out of the Play-facing architecture.

DownloadThat’s own native playback of a file already present on the device remains ad-free in the simple product sense that DownloadThat itself does not inject advertising into local playback.

## Format scope

Media3 progressive container support covers the core target set including MP4/M4A/FMP4, WebM/Matroska, MP3, Ogg, WAV, MPEG-TS/PS, FLV, ADTS/AAC, FLAC and AMR. Actual encoded sample support can still depend on the Android device decoder set.

The first production path deliberately does not add LibVLC or a separately built Media3 FFmpeg decoder extension. The repository already ships substantial native payloads (Chaquopy/CPython, ffmpeg CLI, QuickJS) and must preserve Play 16-KB native-library alignment and package-size discipline.

## Tests

- `tests/test_android_player_contract.py`
- `tests/test_android_player_retention_search_contract.py`
- `tests/test_media_search.py`

Required physical-device smoke matrix before merge/release:

- MP4/H.264 + AAC;
- MP4/HEVC when the device supports it;
- WebM/VP9 + Opus;
- MKV;
- MP3;
- M4A/AAC;
- Ogg/Opus;
- WAV;
- FLAC;
- Android file-manager `Open with -> DownloadThat`;
- screen-off audio;
- headset/Bluetooth play-pause;
- resume after leaving/reopening;
- speed persistence;
- sleep timer;
- video PiP;
- recent playlist next/previous;
- search -> Video queue;
- search -> Audio queue;
- free-tier quota rejection from search;
- simultaneous active download + playback.

## Product metrics worth adding later

Do not optimize only for raw session length. The useful retention metrics are:

- download -> player conversion rate;
- playback starts per user;
- resume usage;
- recent-library return rate;
- search -> result -> download conversion;
- D1 / D7 retention;
- repeated playback of an older download;
- background-audio session rate;
- PiP usage.
