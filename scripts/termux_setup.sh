#!/data/data/com.termux/files/usr/bin/bash
# One-time setup: installs everything ClassyDL needs inside Termux (Android).
# Run from the repo root: bash scripts/termux_setup.sh
set -euo pipefail

echo "==> Updating Termux packages"
pkg update -y && pkg upgrade -y

echo "==> Installing python, git, ffmpeg"
pkg install -y python git ffmpeg

echo "==> Requesting shared storage access (lets downloads show up in the Files app)"
termux-setup-storage || true

echo "==> Installing ClassyDL"
# Termux manages pip itself via 'pkg' — don't try to self-upgrade it.
# The web UI has no extra/compiled dependencies, so a plain install is enough.
pip install .

echo
echo "Setup complete. Start the app with: bash scripts/termux_run.sh"
