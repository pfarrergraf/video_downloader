#!/usr/bin/env bash
# Exercises a real, tiny, stable download through the queue end-to-end and
# verifies the resulting file lands where MainActivity.kt points output_dir
# (Phase 3's app-specific external storage) — proving the whole pipeline
# actually works on-device, not just that health-check/ffmpeg run in isolation.
set -euo pipefail

BASE="http://127.0.0.1:8420"
PASSWORD="classydl"  # matches MainActivity.kt's hardcoded PASSWORD constant
TEST_URL="https://upload.wikimedia.org/wikipedia/commons/c/c8/Example.ogg"

COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

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
if adb shell content query --uri content://media/external/downloads --projection _display_name 2>/dev/null | grep -q "$FILENAME"; then
  echo "Confirmed: file also published to MediaStore Downloads."
else
  echo "NOTE: file not found in MediaStore Downloads query (non-fatal) — check android_entry publish logic if this persists." >&2
fi

echo "Download pipeline smoke test passed."
