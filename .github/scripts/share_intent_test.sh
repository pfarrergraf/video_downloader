#!/usr/bin/env bash
# Proves the "Share -> DownloadThat" 2-tap flow end-to-end on the emulator:
# an ACTION_SEND intent carrying "some text + URL" must be picked up by
# MainActivity (manifest intent-filter -> onNewIntent -> URL extraction ->
# WebView JS bridge -> window.onSharedUrl auto-queue with the remembered
# Smart-Mode settings) and come out the other end as a completed download.
#
# Runs after download_pipeline_test.sh, so the app is already installed,
# started, logged in (debug auto-login), and the local file server pattern
# is established. Like that test, the file is served from the runner via
# `adb reverse` to avoid flaky external hosts.
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

# Share the URL into the app exactly the way another app would - embedded in
# prose, because YouTube etc. share "title + URL", not a bare URL. The
# explicit component skips the share-sheet chooser (no UI automation needed).
adb shell am start -n de.classydl.app/.MainActivity \
  -a android.intent.action.SEND -t text/plain \
  --es android.intent.extra.TEXT "'Check this out: $TEST_URL'"

echo "Sent ACTION_SEND intent with $TEST_URL"

# The page's JS must now auto-queue it - find the job by source.
JOB_ID=""
for i in $(seq 1 30); do
  JOB_ID="$(curl -sf -b "$COOKIE_JAR" "$BASE/api/queue" | python3 -c "
import json, sys
jobs = json.load(sys.stdin)['jobs']
job = next((j for j in jobs if j['source'] == '$TEST_URL'), None)
print(job['id'] if job else '')
")"
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
echo "Shared URL was auto-queued as job $JOB_ID"

STATUS=""
for i in $(seq 1 30); do
  STATUS="$(curl -sf -b "$COOKIE_JAR" "$BASE/api/queue" | python3 -c "
import json, sys
jobs = json.load(sys.stdin)['jobs']
job = next((j for j in jobs if j['id'] == $JOB_ID), None)
print(job['status'] if job else 'missing')
")"
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
