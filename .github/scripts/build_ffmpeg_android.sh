#!/usr/bin/env bash
# Cross-compiles a static ffmpeg CLI binary (+ libmp3lame, for MP3 encoding) for
# Android using the NDK's LLVM toolchain. Built from source deliberately —
# embedding a prebuilt third-party ffmpeg-for-Android binary would be an
# unverifiable supply-chain risk to ship inside the app.
#
# Usage: build_ffmpeg_android.sh <abi> <output-dir>
#   abi: arm64-v8a | x86_64
set -euo pipefail

ABI="$1"
OUT_DIR="$2"
API=26
FFMPEG_REF="release/7.1"
LAME_VERSION="3.100"

case "$ABI" in
  arm64-v8a)
    TARGET=aarch64-linux-android
    FFMPEG_ARCH=aarch64
    FFMPEG_CPU=armv8-a
    ;;
  x86_64)
    TARGET=x86_64-linux-android
    FFMPEG_ARCH=x86_64
    FFMPEG_CPU=x86-64
    ;;
  *)
    echo "Unsupported ABI: $ABI" >&2
    exit 1
    ;;
esac

: "${ANDROID_NDK_HOME:?ANDROID_NDK_HOME must point at the installed NDK}"
TOOLCHAIN="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64"
if [ ! -d "$TOOLCHAIN" ]; then
  echo "NDK toolchain not found at $TOOLCHAIN" >&2
  exit 1
fi

export CC="$TOOLCHAIN/bin/${TARGET}${API}-clang"
export CXX="$TOOLCHAIN/bin/${TARGET}${API}-clang++"
export AR="$TOOLCHAIN/bin/llvm-ar"
export RANLIB="$TOOLCHAIN/bin/llvm-ranlib"
export STRIP="$TOOLCHAIN/bin/llvm-strip"
export NM="$TOOLCHAIN/bin/llvm-nm"
export PATH="$TOOLCHAIN/bin:$PATH"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

echo "==> [$ABI] Building libmp3lame $LAME_VERSION"
curl -fsSL "https://downloads.sourceforge.net/project/lame/lame/${LAME_VERSION}/lame-${LAME_VERSION}.tar.gz" -o lame.tar.gz
tar xf lame.tar.gz
LAME_PREFIX="$WORK/lame-install"
(
  cd "lame-${LAME_VERSION}"
  ./configure \
    --host="$TARGET" \
    --prefix="$LAME_PREFIX" \
    --disable-shared --enable-static \
    --disable-frontend \
    CC="$CC" AR="$AR" RANLIB="$RANLIB" STRIP="$STRIP"
  make -j"$(nproc)"
  make install
)

echo "==> [$ABI] Cloning ffmpeg ($FFMPEG_REF)"
git clone --branch "$FFMPEG_REF" --depth 1 https://github.com/FFmpeg/FFmpeg.git ffmpeg-src
cd ffmpeg-src

echo "==> [$ABI] Configuring ffmpeg"
# max-page-size/common-page-size=16384: Google requires native libraries to
# be 16 KB page-aligned (devices are moving to 16 KB memory pages); NDK
# r27+'s linker defaults to this already, but setting it explicitly doesn't
# depend on that default surviving future NDK bumps.
PATH="$LAME_PREFIX/bin:$PATH" ./configure \
  --prefix="$OUT_DIR" \
  --target-os=android \
  --arch="$FFMPEG_ARCH" \
  --cpu="$FFMPEG_CPU" \
  --enable-cross-compile \
  --cc="$CC" --cxx="$CXX" --ar="$AR" --ranlib="$RANLIB" --strip="$STRIP" --nm="$NM" \
  --sysroot="$TOOLCHAIN/sysroot" \
  --extra-cflags="-O2 -fPIC -I$LAME_PREFIX/include" \
  --extra-ldflags="-pie -Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384 -L$LAME_PREFIX/lib" \
  --disable-shared --enable-static \
  --disable-doc --disable-debug --disable-symver \
  --enable-libmp3lame

echo "==> [$ABI] Building ffmpeg (this takes a while)"
make -j"$(nproc)"
make install

echo "==> [$ABI] Done: $OUT_DIR/bin/ffmpeg"
"$STRIP" "$OUT_DIR/bin/ffmpeg"
