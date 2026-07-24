#!/usr/bin/env bash
set -euo pipefail

BINARY="${1:?path to the x86_64 qjs binary}"
adb push "$BINARY" /data/local/tmp/qjs
adb shell chmod 755 /data/local/tmp/qjs
OUTPUT="$(adb shell /data/local/tmp/qjs -e 'console.log(6 * 7)' 2>&1)"
echo "$OUTPUT"
[ "$OUTPUT" = "42" ] || { echo "QuickJS did not execute JavaScript correctly" >&2; exit 1; }
echo "QuickJS runs on-device — exec smoke test passed."
