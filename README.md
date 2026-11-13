# xtool：在 Linux 上给 iOS 真机出包

在 Linux 服务器上交叉编译、签名并安装**真机 iOS app**——构建、签名、装机全程 Linux：构建用 xtool 交叉编译，装机用 usbmuxd 直连设备。本仓库是这条路踩完坑之后的完整经验库：环境搭建、原生依赖交叉编译、Swift 壳构建、签名装机，以及一套防"配置漏带"的 parity 检查机制。

三条不同形态的产品线实战验证过（Rust 静态库后端 + WebView 壳、C++ 加密库依赖、Tauri v2 跨端框架），路径都是通用的，与具体项目无关。

## 两条技术路线

| 路线 | 构建位置 | 适用 | 产物 |
|---|---|---|---|
| **A. xtool（SwiftPM）** | 纯 Linux | Swift/ObjC 壳 + 预交叉编译的原生静态库 | unsigned `.app` → `xtool install` 签名装机 |
| **B. xcodegen + xcodebuild** | 兼容路线：沿用既有 Xcode 工程资产 | 工程本来就是 XcodeGen/Tauri 生成（含 xcassets、storyboard） | 同上 |

主线是路线 A，构建到装机全程 Linux。认证两种任选：App Store Connect API key（需付费开发者会员，走官方 API），或 Apple ID 密码模式（任何 Apple ID 可用，走 Apple 私有 API）；provisioning 和签名都由 xtool 自动完成。路线 B 只在要**原样保留既有 Xcode 工程资产**时需要（xcassets/storyboard 只有 Apple 的 actool/ibtool 能编译，壳构建在 xcodebuild 上跑）——把图标换成散装 png、启动屏换成 Info.plist 的 UILaunchScreen 字典后，任何工程都能迁回路线 A。

## 目录

```
docs/
  setup-linux.md       Linux 环境：swiftly / xtool / Darwin SDK（官方 Xcode.xip 下载）
  native-libs.md       原生依赖交叉编译：CMake C/C++ 项目（BoringSSL 类）、Rust staticlib
  swift-build.md       路线 A：SwiftPM wrapper 工程写法与 xtool 打包行为
  xcodebuild-lane.md   路线 B：沿用既有 Xcode 工程的坑（合成键、Swift 包依赖）
  install-device.md    签名装机（Linux）：usbmuxd 直连、认证两种模式、dev 并存
  parity.md            parity 检查器：防"旧包有新包没有"的机制设计
  pitfalls.md          全部踩坑速查表（18 条，按主题索引）
scripts/
  setup-xtools-bin.sh    生成最小 Apple 工具 shim 集（xcrun/libtool/llvm-* 等）
  apple-ios-clang.sh     clang shim：把 Darwin 风格 -arch 翻译成 -target
  build-boringssl-ios.sh CMake C/C++ 项目 iOS 交叉编译模板
  rust-ios-staticlib.sh  Rust crate 交叉编译 iOS staticlib 模板
  fix-sdk-resources.sh   给 Darwin SDK 补 clang resource 头文件
  gen_contract.py        从源工程 project.yml 程序化生成 parity 契约
  parity_check.py        契约 vs .app/.ipa 检查器（带 selftest 反例）
```

## 为什么会有这个仓库

一次"重建 iOS 构建管线"的实验暴露了两类反复出现的事故：

1. **手抄配置漏键**：从源工程配置手工转写 Info.plist，读文件被截断，漏了 `NSBonjourServices`——本地网络权限弹窗从此不出现，app 静默不可用；
2. **构建工具合成值丢失**：`TARGETED_DEVICE_FAMILY`、`ASSETCATALOG_COMPILER_APPICON_NAME` 这类不在源码里、由 Xcode 构建过程合成的行为，换了管线之后悄悄退化（iPad 变 iPhone 兼容布局、图标消失）。

结论：这类问题**靠细心是防不住的**，靠机制——契约程序化生成 + 构建后检查 + 装机前阻断。见 [docs/parity.md](docs/parity.md)。

## 快速开始

1. Linux 侧：[docs/setup-linux.md](docs/setup-linux.md) 把 Swift 工具链、xtool、Darwin SDK 装好
2. 原生依赖：[docs/native-libs.md](docs/native-libs.md) 交叉编译出 `.a`
3. 选路线 A 或 B 构建出 `.app`，跑 `parity_check.py` 确认 0 FAIL
4. 装机：[docs/install-device.md](docs/install-device.md) 一次 `xtool auth login`（API key 或 Apple ID 密码模式），之后每版一条 `xtool install`（usbmuxd 直连设备）

## 坑速查（最容易翻车的 6 条）

| # | 坑 | 一句话解法 |
|---|---|---|
| 1 | swiftly 的 `bin/*` 全是分发符号链接，部分场景**静默 no-op**（exit 0 无产物） | 一律用 `toolchains/<ver>/usr/bin/` 真身路径 |
| 2 | Tauri 工程没带 `tauri/custom-protocol` → 真机白屏（报错还误导成网络问题） | cargo rustc 时显式 `--features tauri/custom-protocol` |
| 3 | `xtool sdk build/install` 内置 HTTP client 不走代理 | tarball 手动下 + `XTL_TOOLSET_TARBALL`/`XTL_OAM_TARBALL` 指路；安装直接 cp |
| 4 | SwiftPM 管线不编译 xcassets → 没图标 | `xtool.yml` 里 `iconPath: icon.png` |
| 5 | 光有 `NSLocalNetworkUsageDescription` 不弹本地网络权限 | Bonjour 发现必须声明 `NSBonjourServices` |
| 6 | xtool.app 被重签后钥匙串全挂 | 只 `xattr -dr com.apple.quarantine`，**永远不要** `codesign -f -s -` |

完整 18 条见 [docs/pitfalls.md](docs/pitfalls.md)。
