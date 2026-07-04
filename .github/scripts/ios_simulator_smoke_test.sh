#!/usr/bin/env bash
# Boots an iOS Simulator, installs and launches the built .app, and verifies it's
# actually still running a few seconds later — mirrors android-build.yml's
# emulator-smoke-test job, which installs the APK and hits /api/health rather than
# trusting a bare launch-command exit code. `simctl launch` can report success even if
# the app crashes immediately on launch, so this checks the process list and recent
# crash logs instead of the launch command's exit status alone.
#
# Usage: ios_simulator_smoke_test.sh <path-to-.app> <bundle-id>
set -euo pipefail

APP_PATH="$1"
BUNDLE_ID="$2"

if [ ! -d "$APP_PATH" ]; then
  echo "App bundle not found at $APP_PATH" >&2
  exit 1
fi

DEVICE_NAME="DownloadThatIOS-CI"
RUNTIME="$(xcrun simctl list runtimes available -j \
  | python3 -c 'import json,sys; runtimes=json.load(sys.stdin)["runtimes"]; ios=[r for r in runtimes if r["identifier"].startswith("com.apple.CoreSimulator.SimRuntime.iOS")]; print(sorted(ios, key=lambda r: r["version"])[-1]["identifier"])')"
echo "Using runtime: $RUNTIME"

DEVICE_TYPE="com.apple.CoreSimulator.SimDeviceType.iPhone-16"
if ! xcrun simctl list devicetypes | grep -q "iPhone-16"; then
  DEVICE_TYPE="$(xcrun simctl list devicetypes -j \
    | python3 -c 'import json,sys; print([d["identifier"] for d in json.load(sys.stdin)["devicetypes"] if "iPhone" in d["name"]][-1])')"
fi
echo "Using device type: $DEVICE_TYPE"

UDID="$(xcrun simctl create "$DEVICE_NAME" "$DEVICE_TYPE" "$RUNTIME")"
echo "Created simulator $UDID"
trap 'xcrun simctl shutdown "$UDID" >/dev/null 2>&1 || true; xcrun simctl delete "$UDID" >/dev/null 2>&1 || true' EXIT

xcrun simctl boot "$UDID"
xcrun simctl bootstatus "$UDID" -b

echo "Installing $APP_PATH"
xcrun simctl install "$UDID" "$APP_PATH"

echo "Launching $BUNDLE_ID"
xcrun simctl launch "$UDID" "$BUNDLE_ID"

# Give the app a few seconds to either settle or crash.
sleep 5

if ! xcrun simctl spawn "$UDID" launchctl list | grep -q "$BUNDLE_ID"; then
  echo "App process not found in launchctl list a few seconds after launch — likely crashed on startup." >&2
  echo "Recent crash reports:" >&2
  find "$HOME/Library/Logs/DiagnosticReports" -iname "DownloadThatIOS*" -newermt "-2 minutes" -exec cat {} \; 2>/dev/null >&2 || true
  exit 1
fi

echo "App is running (found in launchctl list). Smoke test passed."
