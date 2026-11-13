#!/usr/bin/env bash
# 给 Darwin SDK 补 clang resource 头文件（stdarg.h / arm_neon.h 等）。
#
# 背景：交叉编译 Swift/C 时这两个头由 clang resource 目录提供。来源用本机
# swiftly 工具链自带的 clang resource（toolchains/<ver>/usr/lib/clang/<ver>），
# 注意 <ver> 真身目录形如 21，"21.0.0" 是指向它的符号链接——别把链接当源拷。
#
# 用法: fix-sdk-resources.sh <darwin-sdk根> [swift真身bin]
#   <darwin-sdk根>  ~/.swiftpm/swift-sdks/darwin.artifactbundle
#   [swift真身bin]  ~/.local/share/swiftly/toolchains/<ver>/usr/bin（默认取 SWIFT_TC）
set -euo pipefail

DARWIN_SDK=$1
TCBIN=${2:-${SWIFT_TC:?set SWIFT_TC 或传第二参}}
SRC_CLANG="$(cd "$(dirname "$TCBIN")/.." && pwd)/lib/clang"
[ -d "$SRC_CLANG" ] || { echo "找不到 $SRC_CLANG" >&2; exit 1; }

VER_DIR=$(find "$SRC_CLANG" -maxdepth 1 -mindepth 1 -type d | head -1)
[ -n "$VER_DIR" ] || { echo "$SRC_CLANG 下没有版本目录" >&2; exit 1; }
VER=$(basename "$VER_DIR")
echo "源: $VER_DIR ($(ls "$VER_DIR/include" | wc -l) headers)"

PLAT="$DARWIN_SDK/Developer/Platforms"
for plat in iPhoneOS iPhoneSimulator MacOSX; do
    for sdk in "$PLAT/$plat.platform/Developer/SDKs"/*.sdk; do
        [ -d "$sdk" ] || continue
        rm -rf "$sdk/usr/lib/clang/$VER" "$sdk/usr/lib/clang/${VER}.0.0"
        cp -R "$VER_DIR" "$sdk/usr/lib/clang/$VER"
        ln -s "$VER" "$sdk/usr/lib/clang/${VER}.0.0"
        echo "$sdk: $(ls "$sdk/usr/lib/clang/$VER/include" | wc -l) headers"
    done
done
echo "OK（如仍缺 arm_neon.h，检查 xip 是否下载完整）"
