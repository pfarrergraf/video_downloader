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

curl -sf -c "$COOKIE_JAR" -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"$PASSWORD\"}" >/dev/null

curl -sf -b "$COOKIE_JAR" -X POST "$BASE/api/settings" \
  -H "Content-Type: application/json" \
  -d '{"accept_terms": true}' >/dev/null

echo "Force-stopping and relaunching so the WebView's next auto-login sees terms already accepted..."
adb shell am force-stop de.classydl.app
sleep 2
adb shell am start -n de.classydl.app/.MainActivity

for i in $(seq 1 40); do
  if curl -sf --max-time 2 "$BASE/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
# Give the WebView a moment past the server-health point to finish loading
# and run its own auto-login + setAuthed(true) before the share intent
# arrives - it needs its own login, not just a server that's up.
sleep 5

# Fresh login: the in-memory session store died with the process (same
# reason kill_resilience_test.sh re-logs in after its own force-stop).
# Retried: right after a force-stop/relaunch the socket can accept a
# connection before the app is ready and reply empty (curl exit 52), which
# under `set -e` killed the whole script (seen in CI attempt #1 of run 138).
LOGGED_IN=""
for i in $(seq 1 15); do
  if curl -sf --max-time 5 -c "$COOKIE_JAR" -X POST "$BASE/api/login" \
    -H "Content-Type: application/json" \
    -d "{\"password\": \"$PASSWORD\"}" >/dev/null 2>&1; then
    LOGGED_IN=1
    break
  fi
  sleep 2
done
if [ -z "$LOGGED_IN" ]; then
  echo "Could not log in after relaunch - server never became ready" >&2
  exit 1
fi

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
for i in $(seq 1 25); do
  # The post-force-stop activity can drop out of the foreground on slow CI
  # emulators (attempt #2 of run 138: the final UI dump showed the launcher,
  # right after WebView cache-init errors). A plain `am start` on the
  # singleTop activity only brings it back to the front (onNewIntent, no
  # extras), so it can't clobber the pending picker state.
  if ! adb shell dumpsys window 2>/dev/null | grep -q "mCurrentFocus.*de.classydl.app"; then
    echo "App not in foreground (iteration $i) - bringing it back"
    adb shell am start -n de.classydl.app/.MainActivity >/dev/null 2>&1 || true
    sleep 2
  fi
  adb shell uiautomator dump /sdcard/window_dump.xml >/dev/null 2>&1 || true
  adb pull /sdcard/window_dump.xml "$TEST_DIR/window_dump.xml" >/dev/null 2>&1 || true
  if [ -s "$TEST_DIR/window_dump.xml" ]; then
    TAP_XY="$(python3 -c "
import re
with open('$TEST_DIR/window_dump.xml', encoding='utf-8') as f:
    xml = f.read()
nodes = re.findall(r'<node[^>]*text=\"Video\"[^>]*bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"', xml)
if not nodes:
    nodes = re.findall(r'<node[^>]*text=\"[^\"]*Video[^\"]*\"[^>]*bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"', xml)
# The home screen's persistent kind-toggle is ALWAYS present, so a single
# match means only that toggle has rendered yet and the picker itself
# hasn't shown up - require both (home toggle + picker button) before
# trusting the 'lowest on screen' pick, or an early dump could tap the
# wrong one and the retry loop would stop looking.
if len(nodes) >= 2:
    x1, y1, x2, y2 = max(nodes, key=lambda n: int(n[1]))
    print(f'{(int(x1) + int(x2)) // 2} {(int(y1) + int(y2)) // 2}')
" || true)"
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
