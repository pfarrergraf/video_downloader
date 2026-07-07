#!/usr/bin/env bash
# Proves the foreground service keeps the server (and thus downloads) alive
# while the app is backgrounded: press HOME, wait, and /api/health must still
# answer. Also sanity-checks that the "downloads" notification channel exists.
#
# Note the limits of emulator coverage: stock AOSP images don't run vendor
# battery killers (Samsung/Xiaomi etc.), so this is necessary-not-sufficient;
# the owner's real-device testing remains the final gate (see CLAUDE.md).
set -euo pipefail

BASE="http://127.0.0.1:8420"

echo "Backgrounding the app (HOME key)..."
adb shell input keyevent KEYCODE_HOME
sleep 30

if ! curl -sf --max-time 5 "$BASE/api/health" >/dev/null; then
  echo "Server died within 30s of backgrounding - foreground service is not keeping it alive" >&2
  adb logcat -d -s python.stdout python.stderr ClassyDL ActivityManager 2>/dev/null | tail -n 100 || true
  exit 1
fi
echo "Server still healthy after 30s in the background."

echo "Checking the downloads notification channel exists..."
if adb shell dumpsys notification_manager 2>/dev/null | grep -q "downloads" \
  || adb shell dumpsys notification 2>/dev/null | grep -q "downloads"; then
  echo "Notification channel present."
else
  # Non-fatal: dumpsys output formats vary across API levels; the hard gate
  # is the server surviving above.
  echo "NOTE: could not confirm the notification channel via dumpsys (non-fatal)." >&2
fi

# Bring the app back to the foreground for any tests that follow.
adb shell am start -n de.classydl.app/.MainActivity
sleep 3

echo "Background survival test passed."
