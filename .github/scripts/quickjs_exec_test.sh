#!/usr/bin/env bash
# Pushes the cross-compiled x86_64 qjs binary onto the running emulator and
# executes it directly (independent of the app) to prove the QuickJS CLI that
# yt-dlp-ejs shells out to actually runs on Android, not just that it compiled.
#
# Two traps this script exists to stay clear of:
#
#  1. `adb shell a b c` joins its arguments and hands the result to the DEVICE's
#     shell, so the local quotes around a JS expression are consumed by bash and
#     the device shell parses the JS itself - `console.log(6 * 7)` is a syntax
#     error there ("(" unexpected) and `*` would glob. The whole device-side
#     command must therefore be ONE argument carrying its own quoting.
#  2. adb runs it on a pty, so every line comes back CRLF-terminated and a bare
#     `[ "$OUTPUT" = "42" ]` fails on the invisible trailing \r.
#
# It also deliberately avoids `set -e`: capturing the run in a command
# substitution under `set -e` killed the script before it could echo anything,
# so a failure surfaced as a bare "process failed with exit code 1" with the
# device's own error message swallowed.
set -uo pipefail

BINARY="${1:?path to the x86_64 qjs binary}"
DEVICE_QJS=/data/local/tmp/qjs

adb push "$BINARY" "$DEVICE_QJS" || exit 1
adb shell "chmod 755 '$DEVICE_QJS'" || exit 1

# Runs ONE device-side command string and normalises the pty line endings.
device() {
  adb shell "$1" 2>&1 | tr -d '\r'
}

echo "--- device abi=$(device 'getprop ro.product.cpu.abi') arch=$(device 'uname -m')"
device "ls -l '$DEVICE_QJS'"

OUTPUT="$(device "'$DEVICE_QJS' -e 'console.log(6 * 7)'")"
STATUS=$?
echo "--- qjs -e exit=$STATUS output: $OUTPUT"

if [ "$STATUS" -ne 0 ] || [ "$OUTPUT" != "42" ]; then
  echo "QuickJS did not execute JavaScript correctly (exit=$STATUS)" >&2
  # Distinguishes "the binary cannot run at all" (linker error, wrong ABI,
  # page size) from "it runs but disagreed about the flags or the output".
  for probe in --help --version; do
    echo "--- qjs $probe (diagnostic)" >&2
    device "'$DEVICE_QJS' $probe" >&2
  done
  exit 1
fi

echo "QuickJS runs on-device — exec smoke test passed."
