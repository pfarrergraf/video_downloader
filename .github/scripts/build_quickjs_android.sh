#!/usr/bin/env bash
# Builds the QuickJS-NG CLI used by yt-dlp-ejs on Android.
# Usage: build_quickjs_android.sh <abi> <output-dir>
set -euo pipefail

ABI="$1"
OUT_DIR="$2"
API=26
QUICKJS_REF="v0.15.1"
QUICKJS_COMMIT="fd0a0210b7be00957751871e7e01b8291268fc29"

case "$ABI" in
  arm64-v8a|x86_64) ;;
  *) echo "Unsupported ABI: $ABI" >&2; exit 1 ;;
esac

: "${ANDROID_NDK_HOME:?ANDROID_NDK_HOME must point at the installed NDK}"
TOOLCHAIN="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake"
[ -f "$TOOLCHAIN" ] || { echo "NDK CMake toolchain not found: $TOOLCHAIN" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git clone --branch "$QUICKJS_REF" --depth 1 https://github.com/quickjs-ng/quickjs.git "$WORK/quickjs"
[ "$(git -C "$WORK/quickjs" rev-parse HEAD)" = "$QUICKJS_COMMIT" ] || {
  echo "QuickJS source commit did not match pinned revision" >&2
  exit 1
}

cmake -S "$WORK/quickjs" -B "$WORK/build" \
  -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN" \
  -DANDROID_ABI="$ABI" \
  -DANDROID_PLATFORM="android-$API" \
  -DCMAKE_BUILD_TYPE=Release \
  -DQJS_ENABLE_INSTALL=OFF \
  -DQJS_BUILD_EXAMPLES=OFF \
  -DCMAKE_EXE_LINKER_FLAGS="-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384"
cmake --build "$WORK/build" --target qjs_exe --parallel

mkdir -p "$OUT_DIR/bin"
cp "$WORK/build/qjs" "$OUT_DIR/bin/qjs"
"$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" "$OUT_DIR/bin/qjs"
echo "==> [$ABI] Done: $OUT_DIR/bin/qjs"
