#!/usr/bin/env bash
# clang shim：把 Darwin driver 风格的 "-arch arm64" 翻译成 Linux clang 认识的
# "-target arm64-apple-ios<min> -isysroot <SDK>"。
#
# 背景：CMake 的 CMAKE_OSX_ARCHITECTURES 会给 ASM 规则塞 -arch（Darwin 专属），
# Linux clang 报 "unrecognized command-line option '-arch'"。C/CXX/ASM 三个
# compiler 都指向本 shim。
#
# 环境变量:
#   SWIFT_TC   swiftly 真身 bin（默认见下）
#   IOS_SDK    iPhoneOS.sdk 路径
#   IOS_MIN    最低部署版本（默认 16.0）
set -euo pipefail
SWIFT_TC=${SWIFT_TC:-$HOME/.local/share/swiftly/toolchains/6.4.2/usr/bin}
IOS_SDK=${IOS_SDK:?set IOS_SDK to iPhoneOS.sdk path}
IOS_MIN=${IOS_MIN:-16.0}

skip=0
out=()
for a in "$@"; do
    if [ "$skip" = 1 ]; then skip=0; continue; fi
    case "$a" in
        -arch) skip=1; continue;;   # 吃掉 "-arch <val>"，由 -target 统一表达
    esac
    out+=("$a")
done
exec "$SWIFT_TC/clang" -target "arm64-apple-ios${IOS_MIN}.0" -isysroot "$IOS_SDK" "${out[@]}"
