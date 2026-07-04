#!/usr/bin/env bash
# Pushes the cross-compiled x86_64 ffmpeg binary onto the running emulator and
# executes it directly (independent of the app) to prove the cross-compiled
# binary actually runs on Android, not just that it compiled.
set -euo pipefail

BINARY="${1:?path to the x86_64 ffmpeg binary}"

adb push "$BINARY" /data/local/tmp/ffmpeg
adb shell chmod 755 /data/local/tmp/ffmpeg
OUTPUT="$(adb shell /data/local/tmp/ffmpeg -version 2>&1)"
echo "$OUTPUT"

if ! echo "$OUTPUT" | grep -q "^ffmpeg version"; then
  echo "ffmpeg -version did not print the expected banner" >&2
  exit 1
fi

echo "ffmpeg runs on-device — exec smoke test passed."
