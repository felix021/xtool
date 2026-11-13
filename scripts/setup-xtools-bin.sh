#!/usr/bin/env bash
# 生成 Linux 上 iOS 交叉编译所需的最小 Apple 工具 shim 集。
#
# 背景：cc-rs（Rust 的 C 构建助手）和 CMake 在 Apple 语义下会找 xcrun / libtool；
# SwiftPM/xcodebuild 生态假设有 Apple binutils。Linux 上都没有——用 llvm-* 真身
# 和小脚本顶上。注意所有 llvm-* 必须用 swiftly 真身路径（分发符号链接会静默 no-op，
# 见 docs/setup-linux.md 坑 1）。
#
# 用法: setup-xtools-bin.sh <shim输出目录> <swift真身bin> <darwin-sdk根>
#   <swift真身bin>   ~/.local/share/swiftly/toolchains/<ver>/usr/bin
#   <darwin-sdk根>   ~/.swiftpm/swift-sdks/darwin.artifactbundle（含 toolset/bin/ld64.lld 与各 SDK）
set -euo pipefail

DIR=$1; TCBIN=$2; DARWIN_SDK=$3
mkdir -p "$DIR"

# 1) binutils：llvm 真身的符号链接
for t in ar ranlib nm objcopy objdump strip; do
    ln -sf "$TCBIN/llvm-$t" "$DIR/$t"
done

# 2) codesign：静态库阶段用不上签名，no-op 顶替
printf '#!/bin/sh\nexit 0\n' > "$DIR/codesign"

# 3) xcrun：cc-rs 用它探测 SDK 和工具路径
cat > "$DIR/xcrun" <<EOF
#!/usr/bin/env bash
# 最小 xcrun shim：只回答 cc-rs 会问的三个问题
SDK="\$DARWIN_SDK/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS.sdk"
case "\$*" in
  *--show-sdk-path*) echo "\$SDK";;
  *"-f clang"*) echo "$TCBIN/clang";;
  *"-f ld"*) echo "\$DARWIN_SDK/toolset/bin/ld64.lld";;
  *"-f ar"*) echo "$TCBIN/llvm-ar";;
  *) exit 0;;
esac
EOF

# 4) libtool：cc-rs 在 apple target 上用 "libtool -static -o out.a objs..." 归档，
#    翻译成 llvm-ar qc
cat > "$DIR/libtool" <<EOF
#!/usr/bin/env bash
out=""; objs=(); prev=""
for a in "\$@"; do
  if [ "\$prev" = "-o" ]; then out="\$a"; prev="\$a"; continue; fi
  prev="\$a"
  case "\$a" in
    -*) continue;;
    *) objs+=("\$a");;
  esac
done
exec "$TCBIN/llvm-ar" qc "\$out" "\${objs[@]}"
EOF

chmod +x "$DIR/xcrun" "$DIR/libtool"
echo "OK: shims in $DIR"
echo "用法: export XTOOLS_BIN=$DIR; export PATH=\$XTOOLS_BIN:\$PATH"
