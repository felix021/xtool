# Linux 环境搭建（swiftly / xtool / Darwin SDK）

目标：在一台 Linux x86_64（实测 Ubuntu 24.04）上具备编译 iOS arm64 代码的全部能力。

## 1. 系统包

```bash
sudo apt-get install -y usbmuxd libfuse2 gnupg2 libcurl4-openssl-dev libxml2-dev
```

（usbmuxd 供 Linux 直连 iOS 设备装机用；设备不连这台机器可跳过。）

## 2. Swift 工具链：用 swiftly 装，但**只用真身路径**

```bash
cd /tmp
curl -O https://download.swift.org/swiftly/linux/swiftly-$(uname -m).tar.gz
tar zxf swiftly-$(uname -m).tar.gz
./swiftly init --quiet-shell-followup --assume-yes
. "${SWIFTLY_HOME_DIR:-$HOME/.local/share/swiftly}/env.sh"
swift --version
```

### ⚠️ 头号坑：swiftly 的分发符号链接

`~/.local/share/swiftly/bin/` 下的 `swift` / `clang` / `llvm-ar` …… 全是指向 swiftly
自身的符号链接（多路分发器）。在某些上下文里（非交互 shell、被构建工具调用）它们会
**静默 no-op：exit 0、不产出任何文件**。症状包括：

- 编译命令 exit=0 但 `.o` 不存在；
- `llvm-ranlib: error: unable to load 'libxxx.a': No such file or directory`（上游归档步骤早就静默失败了）；
- xtool 报 `Could not parse Swift version: ''`。

**解法**：一律使用真身 `~/.local/share/swiftly/toolchains/<版本>/usr/bin/`，并把它排在
PATH 最前面。本仓库所有脚本都按这个约定（`SWIFT_TC` 环境变量）。

## 3. xtool 本体

```bash
mkdir -p ~/bin
curl -fL "https://github.com/xtool-org/xtool/releases/latest/download/xtool-$(uname -m).AppImage" \
  -o ~/bin/xtool
chmod +x ~/bin/xtool
xtool --help
```

## 4. Darwin SDK 的来源：官方下载 Xcode.xip

在 developer.apple.com/download/all（浏览器登录 Apple ID）下载 Xcode.xip
（约 8GB），`xtool sdk build` 直接吃 xip，本机无需任何 Apple 设备：

```bash
xtool sdk build ~/Downloads/Xcode_<版本>.xip ~/tmp/sdk-out
# 成功标志：输出 "Built SDK at ~/tmp/sdk-out/darwin.xtoolsdk"
```

## 5. 构建 SDK：绕开 xtool 的联网步骤

```bash
# xtool 要从 GitHub 下载两个组件，但它的 HTTP client 不走系统代理，
# 会报 HTTPClientError.deadlineExceeded —— 手动下好后用环境变量指路：
curl -fL "https://github.com/xtool-org/darwin-tools-linux-llvm/releases/download/v1.1.0/toolset-$(uname -m).tar.gz" -o ~/tmp/toolset.tar.gz
curl -fL "https://github.com/xtool-org/OpenAppleMacros/releases/download/v1.4.1/OpenAppleMacrosServer-$(uname -m).tar.gz" -o ~/tmp/oam.tar.gz
# 版本号以 xtool 源码 SDKBuilder.swift 里的 darwinToolsVersion/oamVersion 为准

XTL_TOOLSET_TARBALL=~/tmp/toolset.tar.gz XTL_OAM_TARBALL=~/tmp/oam.tar.gz \
  xtool sdk build ~/Downloads/Xcode_<版本>.xip ~/tmp/sdk-out
```

安装（`xtool sdk install` 同样可能因联网校验挂掉，手动拷贝等效且更稳）：

```bash
rm -rf ~/.swiftpm/swift-sdks/darwin.artifactbundle
cp -R ~/tmp/sdk-out/darwin.xtoolsdk ~/.swiftpm/swift-sdks/darwin.artifactbundle
swift sdk list   # → darwin
```

## 6. 齐备性校验（一分钟的保险）

```bash
SDK=~/.swiftpm/swift-sdks/darwin.artifactbundle/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS.sdk
# C 标准头
ls $SDK/usr/include/stdlib.h
# clang resource（arm64 NEON / stdarg 都在这，缺失会在编 Swift 时炸）
ls $SDK/usr/lib/clang/21/include/stdarg.h $SDK/usr/lib/clang/21/include/arm_neon.h
```

缺 clang resource 时用 `scripts/fix-sdk-resources.sh` 补（从搬来的 Xcode toolchain
取 `usr/lib/clang/21`——注意 `21` 是真实目录、`21.0.0` 是指向它的符号链接，别拷反）。

## 7. 工具 shim 集

cc-rs（Rust 的 C 构建助手）和 CMake 在 Apple 语义下会找 `xcrun`、`libtool`、
Darwin 风格 `-arch` flag——Linux 上都没有/都不认。一次性生成全套 shim：

```bash
TCBIN=~/.local/share/swiftly/toolchains/<版本>/usr/bin
SDK=$SDK ./scripts/setup-xtools-bin.sh ~/tmp/xtools-bin $TCBIN \
     ~/.swiftpm/swift-sdks/darwin.artifactbundle
export PATH=~/tmp/xtools-bin:$PATH
```

详见 [native-libs.md](native-libs.md) 每个 shim 的用途。

## 环境变量速查（本仓库脚本的统一约定）

| 变量 | 含义 |
|---|---|
| `SWIFT_TC` | swiftly 真身 bin（`toolchains/<ver>/usr/bin`） |
| `IOS_SDK` | iPhoneOS.sdk 绝对路径 |
| `XTOOLS_BIN` | shim 目录 |
| `DARWIN_SDK` | darwin.artifactbundle 根（含 toolset/bin/ld64.lld） |
