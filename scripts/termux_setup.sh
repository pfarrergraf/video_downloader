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

echo "==> Installing ClassyDL + web extras"
# Termux manages pip itself via 'pkg' — don't try to self-upgrade it.
if ! pip install ".[web]"; then
  echo "==> Compiled-dependency install failed, retrying with a Rust toolchain"
  pkg install -y rust binutils clang
  pip install ".[web]"
fi

echo
echo "Setup complete. Start the app with: bash scripts/termux_run.sh"
