# 踩坑速查表

按主题分组，每条：现象（可搜索的报错原文）→ 根因 → 解法。详细背景见各主题文档。

## Linux 环境与工具链（setup-linux.md）

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| 1 | 编译命令 exit=0 但产物不存在；`llvm-ranlib: unable to load 'libxxx.a'`；`Could not parse Swift version: ''` | swiftly 的 `bin/*` 是分发符号链接，部分上下文静默 no-op | 全部改用 `toolchains/<ver>/usr/bin/` 真身；PATH 前置 |
| 2 | `xtool sdk build` 报 `HTTPClientError.deadlineExceeded` | 内置 HTTP client 不走系统代理，GitHub 下载超时 | 手动 curl tarball + `XTL_TOOLSET_TARBALL` / `XTL_OAM_TARBALL` 环境变量指路 |
| 3 | `xtool sdk install` 报 JSON 解析错或卡死 | 同上（联网校验） | 手动 cp bundle 到 `~/.swiftpm/swift-sdks/darwin.artifactbundle` |

## C/C++ / CMake 交叉编译（native-libs.md）

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| 4 | `cc: error: unrecognized command-line option '-arch'` | Darwin driver flag，Linux clang 不认；ASM 规则和系统 c++ 都会踩 | clang shim 统一翻译 `-arch X` → `-target arm64-apple-ios…`，C/CXX/ASM 三处都设 |
| 5 | 编译全绿但 `could not find native static library` | 归档工具（分发链接）静默 no-op，`.a` 没生成 | `CMAKE_AR`/`CMAKE_RANLIB` 显式指真身 llvm-ar/ranlib |
| 6 | CMake configure 阶段 "Check for working compiler - broken"（交叉环境） | try-run 探测跑不了目标代码 | `-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY` |
| 7 | `Could not find install_name_tool` | CMake 找 Apple 配套 binutils | shim 目录里用 llvm-* 系列顶上（setup-xtools-bin.sh） |

## Rust 交叉编译（native-libs.md）

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| 8 | `ld64.lld: undefined symbol: <自己的导出符号>`（编 cdylib 时） | rustc 导出列表与 Mach-O 符号前缀不匹配 | `cargo rustc --crate-type staticlib` 只编静态库 |
| 9 | `clang: error: missing version number in '-miphoneos-version-min='` | cc-rs 拿不到部署目标 | `IPHONEOS_DEPLOYMENT_TARGET=16.0` |
| 10 | `cc-rs: failed to find tool "xcrun"` / 归档走 libtool 失败 | Apple 语义工具缺失 | xcrun / libtool 两个 shim（setup-xtools-bin.sh 生成） |
| 11 | `/usr/bin/ld: unrecognised emulation mode: llvm` | rustc 落到系统 GNU ld（只认 ELF） | 链接 wrapper 里 `-fuse-ld=lld` + toolset 的 `ld64.lld` 进 PATH |

## SwiftPM / xtool 构建（swift-build.md）

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| 12 | `cannot find 'URL' in scope`（manifest） | manifest 用了 Foundation API | `import Foundation` |
| 13 | `manifest property 'defaultLocalization' not set` | 源码含 .lproj | package 声明 `defaultLocalization: "en"` |
| 14 | Swift 5 代码一堆 `mutation of captured var ... concurrently-executing code` error | 默认 Swift 6 语言模式 | `swiftLanguageModes: [.v5]`（注意参数顺序） |
| 15 | `undefined symbol: __isPlatformVersionAtLeast` | 缺 iOS compiler-rt | 链 `-lclang_rt.ios`（SDK toolchain 的 lib/clang/…/darwin） |
| 16 | 装上没图标 | SwiftPM 不编译 xcassets | `xtool.yml: iconPath: icon.png` |

## xcodegen / xcodebuild（xcodebuild-lane.md）

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| 17 | iPad 上 iPhone 兼容布局 | project.yml 缺 `TARGETED_DEVICE_FAMILY`，重生成工程后丢失合成值 | 显式 `"1,2"`；改完要 uninstall+install 刷缓存 |
| 18 | 无图标且包里没 Assets.car | 缺 `ASSETCATALOG_COMPILER_APPICON_NAME` | 显式 `AppIcon` |
| 19 | `ld: library 'app' not found`（明明放了 Externals） | scheme 默认 Debug 配置，找 DebugLib | 静态库 DebugLib / Externals 两处都放 |
| 20 | `Undefined symbols: _string_from_bytes / _init_plugin_*`（Tauri） | 手写 project.yml 缺 Swift 包依赖（SwiftRs/Tauri/插件） | swiftc 手编静态库接入（见 xcodebuild-lane.md 坑 2；插件要分库编，initPlugin 撞名） |

## 装机侧（install-device.md）

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| 21 | `xtool devices` 列不出设备 | usbmuxd 没跑 / USB 直通未生效 | 检查 usbmuxd 服务与 USB 链路 |
| 22 | `Operation unsupported`（auth login） | stdin 是管道/socket 而非 TTY 或常规文件 | 文件重定向喂答案；交互认证进真人终端 |
| 23 | 本地网络权限弹窗不出现、mDNS 发现静默失败 | 只有 `NSLocalNetworkUsageDescription`，缺 `NSBonjourServices` | plist 显式声明 Bonjour 服务类型 |
| 24 | dev 包装上名字还是原名 | `CFBundleName` 从可执行名合成，没显式写 | `CFBundleName`/`CFBundleDisplayName` 都显式写 |
| 25 | 原地升级后显示名/布局没变 | SpringBoard 缓存 | 自己的 dev ID 才能 uninstall+install 刷 |
