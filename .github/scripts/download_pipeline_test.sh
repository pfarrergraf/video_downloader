#!/usr/bin/env bash
# Exercises a real download through the queue end-to-end and verifies the
# resulting file lands where MainActivity.kt points output_dir (Phase 3's
# app-specific external storage) — proving the whole pipeline actually works
# on-device, not just that health-check/ffmpeg run in isolation.
#
# The test file is served from the CI runner itself (via `adb reverse`, so
# the emulator's loopback reaches back to the host) rather than fetched from
# a real internet host: upload.wikimedia.org and similar hosts intermittently
# 403 requests from GitHub Actions runner IPs (datacenter/anti-bot blocking
# unrelated to this app), which made earlier versions of this test flaky in a
# way that looked like an Android/Chaquopy bug but wasn't. Serving our own
# tiny file removes that external dependency entirely.
set -euo pipefail

BASE="http://127.0.0.1:8420"
PASSWORD="classydl"  # matches MainActivity.kt's hardcoded PASSWORD constant
FILE_PORT=8421

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

python3 - "$TEST_DIR/testfile.wav" <<'PY'
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
  if curl -sf "http://127.0.0.1:$FILE_PORT/testfile.wav" -o /dev/null; then
    break
  fi
  sleep 0.5
done

adb reverse "tcp:$FILE_PORT" "tcp:$FILE_PORT"

TEST_URL="http://127.0.0.1:$FILE_PORT/testfile.wav"

curl -sf -c "$COOKIE_JAR" -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"$PASSWORD\"}" >/dev/null

JOB_ID="$(curl -sf -b "$COOKIE_JAR" -X POST "$BASE/api/queue" \
  -H "Content-Type: application/json" \
  -d "{\"source\": \"$TEST_URL\"}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')"

echo "Queued job $JOB_ID for $TEST_URL"

STATUS=""
for i in $(seq 1 30); do
  RESPONSE="$(curl -sf -b "$COOKIE_JAR" "$BASE/api/queue")"
  STATUS="$(echo "$RESPONSE" | python3 -c "
import json, sys
jobs = json.load(sys.stdin)['jobs']
job = next((j for j in jobs if j['id'] == $JOB_ID), None)
print(job['status'] if job else 'missing')
")"
  ERROR="$(echo "$RESPONSE" | python3 -c "
import json, sys
jobs = json.load(sys.stdin)['jobs']
job = next((j for j in jobs if j['id'] == $JOB_ID), None)
print((job or {}).get('error') or '')
")"
  if [ -n "$ERROR" ]; then
    echo "Job $JOB_ID status: $STATUS (last error: $ERROR)"
  else
    echo "Job $JOB_ID status: $STATUS"
  fi
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 2
done

if [ "$STATUS" != "completed" ]; then
  echo "Job did not complete (status: $STATUS, error: $ERROR)" >&2
  adb logcat -d -s python.stdout python.stderr ClassyDL 2>/dev/null | tail -n 100 || true
  exit 1
fi

FILENAME="$(curl -sf -b "$COOKIE_JAR" "$BASE/api/queue" | python3 -c "
import json, sys
jobs = json.load(sys.stdin)['jobs']
job = next(j for j in jobs if j['id'] == $JOB_ID)
print(job['files'][0]['filename'])
")"

echo "Downloaded file: $FILENAME"

DEVICE_PATH="/sdcard/Android/data/de.classydl.app/files/classydl-downloads/job-${JOB_ID}/${FILENAME}"
SIZE="$(adb shell "stat -c %s '$DEVICE_PATH' 2>/dev/null" | tr -d '\r')"
if [ -z "$SIZE" ] || [ "$SIZE" = "0" ]; then
  echo "Downloaded file not found or empty at $DEVICE_PATH" >&2
  adb shell "find /sdcard/Android/data/de.classydl.app -type f" || true
  exit 1
fi
echo "Confirmed on-device file: $DEVICE_PATH ($SIZE bytes)"

echo "Checking MediaStore Downloads collection (best-effort, non-fatal)..."
# The publisher thread polls every ~1s (android_entry._PUBLISH_POLL_SECONDS), so
# give it a few cycles' worth of headroom instead of checking once immediately
# after the job completes — a single-shot check here previously reported a
# false "not found" purely from being faster than the publisher's next poll,
# not from an actual publish failure.
MEDIASTORE_FOUND=""
for i in $(seq 1 10); do
  if adb shell content query --uri content://media/external/downloads --projection _display_name 2>/dev/null | grep -q "$FILENAME"; then
    MEDIASTORE_FOUND="1"
    break
  fi
  sleep 1
done
if [ -n "$MEDIASTORE_FOUND" ]; then
  echo "Confirmed: file also published to MediaStore Downloads."
else
  echo "NOTE: file not found in MediaStore Downloads query after 10s (non-fatal) — dumping publisher-related logcat for diagnosis:" >&2
  adb logcat -d -s python.stdout python.stderr ClassyDL 2>/dev/null | tail -n 100 || true
fi

echo "Checking /api/engine (engine self-update wiring)..."
ENGINE_JSON="$(curl -sf -b "$COOKIE_JAR" "$BASE/api/engine")"
echo "Engine status: $ENGINE_JSON"
echo "$ENGINE_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
assert data.get('active_version'), f'active_version missing: {data}'
assert data.get('updating') is False, f'unexpected updating state: {data}'
"
echo "Engine endpoint OK."

echo "Download pipeline smoke test passed."
