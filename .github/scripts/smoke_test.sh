#!/usr/bin/env bash
# Polls the app's health endpoint after it's been installed and launched in the
# CI emulator. Kept as its own script because android-emulator-runner's `script:`
# block executes each line as a separate shell invocation, so a multi-line
# for-loop inline in the workflow YAML doesn't survive intact.
set -uo pipefail

for i in $(seq 1 20); do
  if curl -sf http://127.0.0.1:8420/api/health; then
    echo "Server responded — smoke test passed."
    exit 0
  fi
  sleep 2
done

echo "Server never responded on /api/health" >&2
adb logcat -d | tail -n 200
exit 1
