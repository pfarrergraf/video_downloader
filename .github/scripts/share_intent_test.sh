#!/usr/bin/env bash
# Proves the "Share -> DownloadThat -> pick a format" flow end-to-end on the
# emulator: an ACTION_SEND intent carrying "some text + URL" must be picked
# up by MainActivity (manifest intent-filter -> onNewIntent -> URL
# extraction -> WebView JS bridge -> window.onSharedUrl), show the
# share-format picker (#share-format-overlay in index.html) instead of
# auto-downloading, and - once "Video" is tapped, the same way a real user
# would - come out the other end as a completed download.
#
# Runs after download_pipeline_test.sh, so the app is already installed,
# started, logged in (debug auto-login), and the local file server pattern
# is established. Like that test, the file is served from the runner via
# `adb reverse` to avoid flaky external hosts.
#
# A fresh install has never accepted the terms overlay, so the WebView's
# own setAuthed(true) (fired once by MainActivity's injected auto-login,
# long before this script runs) shows the terms gate instead of the app -
# window.onSharedUrl exists but $('app') stays hidden forever, so it just
# stashes the URL client-side and nothing ever flushes it (regression
# caught via MainActivity's "Shared URL delivery result" diagnostic log:
# it reported "handler-app-hidden"). accept_terms is a plain server-side
# setting (QueueStore, not session-scoped), so setting it via curl and then
# force-stopping/relaunching - same recovery the app must survive anyway,
# see kill_resilience_test.sh - makes the WebView's next cold setAuthed(true)
# see terms already accepted and show the app immediately.
set -euo pipefail

BASE="http://127.0.0.1:8420"
PASSWORD="classydl"  # matches MainActivity.kt's DEBUG_PASSWORD
FILE_PORT=8422
CURL_RETRY=(
  --fail
  --silent
  --show-error
  --retry 10
  --retry-all-errors
  --retry-delay 1
  --connect-timeout 2
  --max-time 5
)

TEST_DIR="$(mktemp -d)"
COOKIE_JAR="$(mktemp)"
SERVER_PID=""
cleanup() {
  rm -f "$COOKIE_JAR"
  rm -rf "$TEST_DIR"
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

python3 - "$TEST_DIR/shared.wav" <<'PY'
import struct
import sys
import wave

with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(8000)
    w.writeframes(struct.pack("<h", 0) * 4000)  # 0.5s of silence
PY

python3 -m http.server "$FILE_PORT" --bind 127.0.0.1 --directory "$TEST_DIR" &
SERVER_PID=$!

for i in $(seq 1 20); do
  if curl -sf "http://127.0.0.1:$FILE_PORT/shared.wav" -o /dev/null; then
    break
  fi
  sleep 0.5
done

adb reverse "tcp:$FILE_PORT" "tcp:$FILE_PORT"

TEST_URL="http://127.0.0.1:$FILE_PORT/shared.wav"

curl "${CURL_RETRY[@]}" -c "$COOKIE_JAR" -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"$PASSWORD\"}" >/dev/null

curl "${CURL_RETRY[@]}" -b "$COOKIE_JAR" -X POST "$BASE/api/settings" \
  -H "Content-Type: application/json" \
  -d '{"accept_terms": true}' >/dev/null

echo "Force-stopping and relaunching so the WebView's next auto-login sees terms already accepted..."
adb shell am force-stop de.classydl.app
sleep 2
adb shell am start -n de.classydl.app/.MainActivity

HEALTH_READY=false
for i in $(seq 1 40); do
  if curl -sf --max-time 2 "$BASE/api/health" >/dev/null 2>&1; then
    HEALTH_READY=true
    break
  fi
  sleep 1
done
if [ "$HEALTH_READY" != "true" ]; then
  echo "App server did not recover after force-stop/relaunch" >&2
  adb logcat -d -s python.stdout python.stderr ClassyDL chromium 2>/dev/null | tail -n 100 || true
  exit 1
fi
# Give the WebView a moment past the server-health point to finish loading
# and run its own auto-login + setAuthed(true) before the share intent
# arrives - it needs its own login, not just a server that's up.
sleep 5

# Fresh login: the in-memory session store died with the process (same
# reason kill_resilience_test.sh re-logs in after its own force-stop).
curl "${CURL_RETRY[@]}" -c "$COOKIE_JAR" -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"$PASSWORD\"}" >/dev/null

# Share the URL into the app exactly the way another app would - embedded in
# prose, because YouTube etc. share "title + URL", not a bare URL. The
# explicit component skips the share-sheet chooser (no UI automation needed).
adb shell am start -n de.classydl.app/.MainActivity \
  -a android.intent.action.SEND -t text/plain \
  --es android.intent.extra.TEXT "'Check this out: $TEST_URL'"

echo "Sent ACTION_SEND intent with $TEST_URL"

# The link lands in the field and the share-format picker appears instead of
# auto-downloading - tap "Video" the same way a real user would. The picker's
# button and the home screen's persistent kind-toggle both render the label
# "Video" (same visual language throughout the app), so among matches pick
# the one whose bounds sit lowest on screen: the picker is a full-viewport
# centered modal, so its buttons land further down than the home screen's
# row, which sits right under the URL field near the top.
TAP_XY=""
for i in $(seq 1 15); do
  adb shell uiautomator dump /sdcard/window_dump.xml >/dev/null 2>&1 || true
  adb pull /sdcard/window_dump.xml "$TEST_DIR/window_dump.xml" >/dev/null 2>&1 || true
  if [ -s "$TEST_DIR/window_dump.xml" ]; then
    TAP_XY="$(python3 "$(dirname "$0")/find_android_ui_target.py" \
      "$TEST_DIR/window_dump.xml" || true)"
  fi
  if [[ "$TAP_XY" == DISMISS\ * ]]; then
    read -r _ DISMISS_X DISMISS_Y <<< "$TAP_XY"
    echo "Dismissing unrelated Pixel Launcher ANR dialog at: $DISMISS_X $DISMISS_Y"
    adb shell input tap "$DISMISS_X" "$DISMISS_Y"
    TAP_XY=""
    sleep 2
    continue
  fi
  if [ -n "$TAP_XY" ]; then
    break
  fi
  sleep 1
done

if [ -z "$TAP_XY" ]; then
  echo "Could not locate the share-format picker's Video button via uiautomator" >&2
  tail -c 4000 "$TEST_DIR/window_dump.xml" 2>/dev/null || true
  adb logcat -d -s python.stdout python.stderr ClassyDL chromium 2>/dev/null | tail -n 100 || true
  exit 1
fi

echo "Tapping the picker's Video button at: $TAP_XY"
adb shell input tap $TAP_XY

# The page's JS must now have queued it - find the job by source.
#
# Both the curl and the JSON parse are deliberately tolerant of failure here
# (`|| true`, try/except): under `set -e`, a single transient hiccup inside
# this loop's command substitution would otherwise abort the WHOLE script
# instead of just that one iteration, defeating the retry loop's entire
# purpose (caught in CI: a mid-loop curl/parse failure killed this script
# with an unhandled JSONDecodeError instead of retrying).
JOB_ID=""
for i in $(seq 1 30); do
  RESPONSE="$(curl -sf --max-time 5 -b "$COOKIE_JAR" "$BASE/api/queue" || true)"
  if [ -n "$RESPONSE" ]; then
    JOB_ID="$(printf '%s' "$RESPONSE" | python3 -c "
import json, sys
try:
    jobs = json.load(sys.stdin)['jobs']
except Exception:
    jobs = []
job = next((j for j in jobs if j['source'] == '$TEST_URL'), None)
print(job['id'] if job else '')
" || true)"
  fi
  if [ -n "$JOB_ID" ]; then
    break
  fi
  sleep 1
done

if [ -z "$JOB_ID" ]; then
  echo "Shared URL never appeared in the queue - share intent flow is broken" >&2
  adb logcat -d -s python.stdout python.stderr ClassyDL chromium 2>/dev/null | tail -n 100 || true
  exit 1
fi
echo "Shared URL was queued (after tapping Video) as job $JOB_ID"

STATUS=""
for i in $(seq 1 30); do
  RESPONSE="$(curl -sf --max-time 5 -b "$COOKIE_JAR" "$BASE/api/queue" || true)"
  STATUS="missing"
  if [ -n "$RESPONSE" ]; then
    STATUS="$(printf '%s' "$RESPONSE" | python3 -c "
import json, sys
try:
    jobs = json.load(sys.stdin)['jobs']
except Exception:
    jobs = []
job = next((j for j in jobs if j['id'] == $JOB_ID), None)
print(job['status'] if job else 'missing')
" || echo 'missing')"
  fi
  echo "Job $JOB_ID status: $STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 2
done

if [ "$STATUS" != "completed" ]; then
  echo "Shared download did not complete (status: $STATUS)" >&2
  adb logcat -d -s python.stdout python.stderr ClassyDL 2>/dev/null | tail -n 100 || true
  exit 1
fi

echo "Share intent test passed."
