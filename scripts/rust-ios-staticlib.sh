#!/usr/bin/env bash
# Rust crate → iOS arm64 staticlib（.a），供 Swift 壳链接。
#
# 用法: rust-ios-staticlib.sh <cargo工程根> [-p crate名] <输出.a路径>
# 环境变量: SWIFT_TC / IOS_SDK / XTOOLS_BIN / DARWIN_SDK
#
# 坑位回顾（详见 docs/native-libs.md）：
#   - 只编 staticlib：cdylib 在 Linux 交叉链有导出符号前缀问题
#   - IPHONEOS_DEPLOYMENT_TARGET 必须给（否则 cc-rs 生成空的 -miphoneos-version-min=）
#   - cc-rs 需要 xcrun/libtool shim
#   - 链接 Mach-O（如编测试）需 -fuse-ld=lld + toolset 的 ld64.lld
set -euo pipefail

ROOT=$1; PKG=${2:-}; OUTA=${3:-}
[ -n "$PKG" ] && [ -n "$OUTA" ] || { echo "用法: $0 <cargo工程根> [-p crate名] <输出.a>"; exit 2; }
: "${SWIFT_TC:?}" ; : "${IOS_SDK:?}"; : "${XTOOLS_BIN:?}"; : "${DARWIN_SDK:?}"
SHIM="$(cd "$(dirname "$0")" && pwd)/apple-ios-clang.sh"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cat > "$WORK/cc.sh" <<EOF
#!/usr/bin/env bash
exec "$SWIFT_TC/clang" -target arm64-apple-ios16.0.0 -isysroot "$IOS_SDK" "\$@"
EOF
cat > "$WORK/link.sh" <<EOF
#!/usr/bin/env bash
export PATH="$DARWIN_SDK/toolset/bin:\$PATH"
exec "$SWIFT_TC/clang" -fuse-ld=lld -target arm64-apple-ios16.0.0 -isysroot "$IOS_SDK" "\$@"
EOF
chmod +x "$WORK/cc.sh" "$WORK/link.sh"

cd "$ROOT"
export PATH="$SWIFT_TC:$XTOOLS_BIN:$HOME/.cargo/bin:$PATH"
export CC_aarch64_apple_ios="$WORK/cc.sh"
export CXX_aarch64_apple_ios="$WORK/cc.sh"
export CARGO_TARGET_AARCH64_APPLE_IOS_LINKER="$WORK/link.sh"
export SDKROOT="$IOS_SDK"
export IPHONEOS_DEPLOYMENT_TARGET=16.0

cargo rustc --release --target aarch64-apple-ios -p "$PKG" --lib --crate-type staticlib
mkdir -p "$(dirname "$OUTA")"
cp "target/aarch64-apple-ios/release/lib${PKG//-/_}.a" "$OUTA"
file "$OUTA"
echo "OK: $OUTA"
