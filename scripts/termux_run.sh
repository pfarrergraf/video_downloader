#!/data/data/com.termux/files/usr/bin/bash
# Launches the Gothic web UI locally on the phone — nothing leaves the device.
# Run from the repo root: bash scripts/termux_run.sh
set -euo pipefail

export CLASSYDL_DATA_DIR="${CLASSYDL_DATA_DIR:-$HOME/.classydl}"
OUTPUT_DIR="${CLASSYDL_OUTPUT_DIR:-$HOME/storage/downloads/ClassyDL}"
PORT="${CLASSYDL_WEB_PORT:-8420}"

if [ -z "${CLASSYDL_WEB_PASSWORD:-}" ]; then
  read -r -s -p "Set a password for this session: " CLASSYDL_WEB_PASSWORD
  echo
  export CLASSYDL_WEB_PASSWORD
fi

mkdir -p "$OUTPUT_DIR"

# Keeps Termux (and this process) alive while the screen is off / app is backgrounded.
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

echo "Open http://127.0.0.1:$PORT in a browser on this phone."
classydl web --host 127.0.0.1 --port "$PORT" --output "$OUTPUT_DIR"
