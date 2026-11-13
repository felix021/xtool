# 原生依赖交叉编译（CMake C/C++ 项目、Rust）

前置：[setup-linux.md](setup-linux.md) 的环境与 shim 集已就绪。所有命令假设：

```bash
export SWIFT_TC=~/.local/share/swiftly/toolchains/<版本>/usr/bin   # 真身！
export IOS_SDK=~/.swiftpm/swift-sdks/darwin.artifactbundle/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS.sdk
export DARWIN_SDK=~/.swiftpm/swift-sdks/darwin.artifactbundle
export XTOOLS_BIN=~/tmp/xtools-bin
export PATH="$SWIFT_TC:$XTOOLS_BIN:$PATH"
```

## 一、CMake C/C++ 项目（以 BoringSSL 为例，任何 CMake 库通用）

脚本模板：`scripts/build-boringssl-ios.sh`。核心坑四个：

### 1. `-arch arm64` 是 Darwin driver 专属 flag

CMake 的 `CMAKE_OSX_ARCHITECTURES=arm64` 会给 C 规则翻译成 `-arch arm64`，
而 **ASM 规则**和默认抓到的系统 `c++` 都不认识它（`cc: error: unrecognized
command-line option '-arch'`）。解法：C/CXX/ASM 三个 compiler 全部指向同一个
shim（`scripts/apple-ios-clang.sh`），把 `-arch X` 吃掉、统一翻译成
`-target arm64-apple-ios16.0.0 -isysroot $IOS_SDK`。

### 2. 归档工具必须指真身

swiftly 分发链接的 `llvm-ar` 会静默 no-op → 编译全绿、`.a` 生成失败，报
`could not find native static library ... perhaps a -L flag is missing?`
之类上游不相干的错。显式传：

```bash
-DCMAKE_AR="$SWIFT_TC/llvm-ar" -DCMAKE_RANLIB="$SWIFT_TC/llvm-ranlib"
```

### 3. 交叉环境跑不了 try-run 探测

```bash
-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY
```

### 4. cc-rs / libtool

如果这个 C 库是被 Rust crate 包装的（build.rs 走 cc-rs），还需要 `xcrun`
（探测 SDK）和 `libtool`（Apple 语义归档）两个 shim——`setup-xtools-bin.sh`
都会生成。

产物校验：`file lib*.a` 应显示 `current ar archive`，抽一个 `.o` 应为
`Mach-O 64-bit arm64 object`。

## 二、Rust crate → iOS staticlib

脚本模板：`scripts/rust-ios-staticlib.sh`。坑点：

### 1. 只编 staticlib，别让 cdylib 参战

crate 里同时有 `staticlib + cdylib` 时，cargo 默认两个都编。cdylib 走
Mach-O 链接，在 Linux 交叉链下会撞 rustc 导出符号表 vs Mach-O 符号前缀的
不匹配（`ld64.lld: error: undefined symbol: <你自己的符号>`，明明就在库里）。

```bash
cargo rustc --release --target aarch64-apple-ios -p <crate> --lib --crate-type staticlib
```

### 2. 环境变量全套（缺一个就是一种新报错）

```bash
export IPHONEOS_DEPLOYMENT_TARGET=16.0   # 缺了：cc-rs 生成 "-miphoneos-version-min="（空值）报错
export SDKROOT=$IOS_SDK
export CC_aarch64_apple_ios=<clang-shim>  # CXX 同理；bundled C 依赖（sqlite 等）全靠它
```

### 3. 链接器（只在必须链 Mach-O 时）

真要链（比如编完跑测试）：wrapper 里 `-fuse-ld=lld` 并把
`$DARWIN_SDK/toolset/bin` 排进 PATH（那里的 `ld64.lld` 认 Mach-O；系统
GNU ld 只认 ELF，报 `unrecognised emulation mode: llvm`）。

### 4. 依赖可交叉性

实测可过：`rusqlite`（bundled sqlite）、`ring`、`rustls`、tokio/axum 全家、
`objc2` 系列、`tauri`/`wry` 全家（iOS target）。含 `jni` 的 crate 也能编
（iOS 下那部分代码被 cfg 掉）。

## 三、Tauri v2 工程的特别说明

- Rust 侧直接编 iPhoneOS target 即可（上节命令），但**必须带
  `--features tauri/custom-protocol`**：没有它 tauri 按 dev 模式编译，页面
  加载会代理到不存在的 dev server，真机上白屏，报错还误导人。
- 构建前要先把前端产物备齐（Tauri 的 build.rs 会检查，缺了直接 panic）。
- Swift 侧的坑在 [xcodebuild-lane.md](xcodebuild-lane.md)。
