#!/usr/bin/env bash
# CMake C/C++ 项目 → iOS arm64 静态库（以 BoringSSL 为例，任意 CMake 库通用）。
#
# 用法: build-boringssl-ios.sh <源码目录> <输出目录>
# 环境变量: SWIFT_TC / IOS_SDK / XTOOLS_BIN（见 docs/setup-linux.md 速查表）
#
# 坑位回顾（详见 docs/native-libs.md）：
#   - -arch 翻译（apple-ios-clang.sh）
#   - CMAKE_AR/RANLIB 指真身（分发链接静默 no-op）
#   - TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY（交叉环境跑不了 try-run）
set -euo pipefail

SRC=$1; OUT=$2
: "${SWIFT_TC:?set SWIFT_TC}"; : "${IOS_SDK:?set IOS_SDK}"; : "${XTOOLS_BIN:?set XTOOLS_BIN}"
export PATH="$XTOOLS_BIN:$PATH"
SHIM="$(cd "$(dirname "$0")" && pwd)/apple-ios-clang.sh"
chmod +x "$SHIM"

args=(
    -DCMAKE_SYSTEM_NAME=iOS
    -DCMAKE_OSX_SYSROOT="$IOS_SDK"
    -DCMAKE_OSX_ARCHITECTURES=arm64
    -DCMAKE_OSX_DEPLOYMENT_TARGET=16.0
    -DCMAKE_C_COMPILER="$SHIM"
    -DCMAKE_CXX_COMPILER="$SHIM"
    -DCMAKE_ASM_COMPILER="$SHIM"
    -DCMAKE_AR="$SWIFT_TC/llvm-ar"
    -DCMAKE_RANLIB="$SWIFT_TC/llvm-ranlib"
    -DCMAKE_BUILD_TYPE=Release
    -DBUILD_TESTING=OFF
    -DCMAKE_MACOSX_BUNDLE=OFF
    -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY
)
cmake -S "$SRC" -B "$OUT/objects" "${args[@]}"
cmake --build "$OUT/objects" --target crypto ssl --parallel "$(nproc)"
mkdir -p "$OUT/lib"
cp "$OUT/objects/libcrypto.a" "$OUT/objects/libssl.a" "$OUT/lib/"
file "$OUT/lib/libssl.a"
echo "OK: $OUT/lib/"
