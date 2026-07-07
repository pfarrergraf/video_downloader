#!/usr/bin/env bash
# Proves downloads survive the #1 mobile failure mode: Android killing the
# app process mid-download. Queues a deliberately slow download, force-stops
# the app while it's in_progress, relaunches, and asserts the job recovers
# to pending and completes WITHOUT any user action (see
# QueueStore.recover_stale_in_progress, called from BackgroundQueueWorker.start).
#
# Runs after download_pipeline_test.sh / share_intent_test.sh in the same
# emulator session; follows their local-file-server-over-adb-reverse pattern.
set -euo pipefail

BASE="http://127.0.0.1:8420"
PASSWORD="classydl"  # matches MainActivity.kt's DEBUG_PASSWORD
FILE_PORT=8423

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

# A throttled HTTP server: 4 MiB served in 64 KiB chunks with a pause per
# chunk (~20s total), slow enough to reliably force-stop mid-transfer.
FILE_SIZE=$((4 * 1024 * 1024))
python3 - "$FILE_PORT" "$FILE_SIZE" <<'PY' > "$TEST_DIR/throttle-server.log" 2>&1 &
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1])
SIZE = int(sys.argv[2])
CHUNK = 64 * 1024


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(SIZE))
        self.end_headers()
        sent = 0
        while sent < SIZE:
            n = min(CHUNK, SIZE - sent)
            try:
                self.wfile.write(b"\0" * n)
            except (BrokenPipeError, ConnectionResetError):
                return
            sent += n
            time.sleep(0.3)


ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
PY
SERVER_PID=$!

# Plain TCP connect check - an HTTP GET would sit through the throttled
# 20s body and time out even though the server is perfectly healthy.
for i in $(seq 1 20); do
  if python3 -c "import socket; socket.create_connection(('127.0.0.1', $FILE_PORT), 1).close()" 2>/dev/null; then
    break
  fi
  sleep 0.5
done

adb reverse "tcp:$FILE_PORT" "tcp:$FILE_PORT"

TEST_URL="http://127.0.0.1:$FILE_PORT/slow.mp4"

curl -sf -c "$COOKIE_JAR" -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"$PASSWORD\"}" >/dev/null

JOB_ID="$(curl -sf -b "$COOKIE_JAR" -X POST "$BASE/api/queue" \
  -H "Content-Type: application/json" \
  -d "{\"source\": \"$TEST_URL\"}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')"

echo "Queued slow job $JOB_ID"

# Wait until it's genuinely mid-transfer (in_progress with bytes on the wire).
STARTED=""
for i in $(seq 1 30); do
  INFO="$(curl -sf -b "$COOKIE_JAR" "$BASE/api/queue" | python3 -c "
import json, sys
jobs = json.load(sys.stdin)['jobs']
job = next((j for j in jobs if j['id'] == $JOB_ID), None)
print(f\"{job['status']} {job['downloaded_bytes']}\" if job else 'missing 0')
")"
  STATUS="${INFO% *}"
  BYTES="${INFO#* }"
  echo "Job $JOB_ID: $STATUS ($BYTES bytes)"
  if [ "$STATUS" = "in_progress" ] && [ "$BYTES" -gt 0 ]; then
    STARTED=1
    break
  fi
  sleep 1
done
if [ -z "$STARTED" ]; then
  echo "Job never reached in_progress with data - can't test the kill" >&2
  exit 1
fi

echo "Force-stopping the app mid-download..."
adb shell am force-stop de.classydl.app
sleep 2

echo "Relaunching..."
adb shell am start -n de.classydl.app/.MainActivity

# The relaunched server must come back AND recover the stranded job.
for i in $(seq 1 40); do
  if curl -sf --max-time 2 "$BASE/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Fresh login: the in-memory session store died with the process.
curl -sf -c "$COOKIE_JAR" -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"$PASSWORD\"}" >/dev/null

STATUS=""
for i in $(seq 1 60); do
  STATUS="$(curl -sf -b "$COOKIE_JAR" "$BASE/api/queue" | python3 -c "
import json, sys
jobs = json.load(sys.stdin)['jobs']
job = next((j for j in jobs if j['id'] == $JOB_ID), None)
print(job['status'] if job else 'missing')
")"
  echo "Job $JOB_ID after restart: $STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 2
done

if [ "$STATUS" != "completed" ]; then
  echo "Job did not recover and complete after force-stop (status: $STATUS)" >&2
  adb logcat -d -s python.stdout python.stderr ClassyDL 2>/dev/null | tail -n 100 || true
  exit 1
fi

FILENAME="$(curl -sf -b "$COOKIE_JAR" "$BASE/api/queue" | python3 -c "
import json, sys
jobs = json.load(sys.stdin)['jobs']
job = next(j for j in jobs if j['id'] == $JOB_ID)
print(job['files'][0]['filename'])
")"
DEVICE_PATH="/sdcard/Android/data/de.classydl.app/files/classydl-downloads/job-${JOB_ID}/${FILENAME}"
SIZE_ON_DEVICE="$(adb shell "stat -c %s '$DEVICE_PATH' 2>/dev/null" | tr -d '\r')"
if [ "$SIZE_ON_DEVICE" != "$FILE_SIZE" ]; then
  echo "Recovered file has wrong size: $SIZE_ON_DEVICE (expected $FILE_SIZE)" >&2
  exit 1
fi

echo "Kill-resilience test passed: job survived force-stop and completed ($SIZE_ON_DEVICE bytes)."
