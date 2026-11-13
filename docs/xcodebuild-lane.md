# 路线 B：沿用既有 Xcode 工程（xcodegen + xcodebuild）

适用：工程本来就是 XcodeGen（project.yml 生成 .xcodeproj）或 Tauri 官方生成
的 Xcode 工程。Rust/原生静态库仍在 Linux 交叉编译，Mac 只做最后的壳构建。

核心价值：xcassets（图标）、storyboard、asset catalog 这些**只有 Apple 工具链
能编译**的东西走这条路都能正常处理——代价是两个大坑，见下。

## 坑 1：构建设置合成的行为，源码里看不见

`.xcodeproj` 被 `xcodegen generate` 重新生成后，一切以 project.yml 为准。
如果原来工程的行为来自**未跟踪的旧 .xcodeproj**或 Xcode 模板默认值，
重新生成后就悄悄退化。实测中招的两个：

| 设置 | 缺失后果 | 修法（写进 project.yml 的 settings.base） |
|---|---|---|
| `TARGETED_DEVICE_FAMILY: "1,2"` | `UIDeviceFamily=[1]`，iPad 上 iPhone 兼容布局 | 显式声明 |
| `ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon` | Assets.car 不入包、无图标 | 显式声明 |

另外注意：**原地升级不会刷新**设备对 UIDeviceFamily/显示名的既有认知
（SpringBoard 缓存）——验证这类改动必须 uninstall + install。

## 坑 2：手写 project.yml 缺 Swift 包依赖（Tauri 工程高发）

Tauri v2 的 iOS 壳需要 Swift 侧运行时：`SwiftRs`（swift-rs）、`Tauri` 模块、
各插件的 Swift 实现。标准 Tauri 模板通过 Xcode 的 Swift Package 依赖接入；
**手写/精简过的 project.yml 常把这段丢了**，症状是链接期一排
`Undefined symbols: _string_from_bytes / _init_plugin_* / _log_stdout ...`。

解法：在 Mac 上用 swiftc 手编这几个静态库，塞进工程的库搜索路径并链接：

```bash
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
# 1) SwiftRs：上游仓库 src-swift/lib.swift（单文件）
xcrun --sdk iphoneos swiftc -emit-library -static -emit-module \
  -module-name SwiftRs -emit-module-path mods/SwiftRs.swiftmodule \
  -o libs/libSwiftRs.a -target arm64-apple-ios15.0 -sdk "$SDK" lib.swift
# 2) Tauri 模块：源码在 cargo registry 的 tauri-<ver>/mobile/ios-api/，
#    必须 find 递归收集（Plugin/ 子目录里藏着 protocol Plugin）
FILES=$(find Sources/Tauri -name "*.swift")
xcrun --sdk iphoneos swiftc -emit-library -static -emit-module \
  -module-name Tauri -emit-module-path mods/Tauri.swiftmodule \
  -o libs/libTauriSwift.a -target arm64-apple-ios15.0 -sdk "$SDK" \
  -I mods $FILES
# 3) 各插件（tauri-plugin-<name>/ios/Sources）：
#    ⚠️ 必须每个插件单独编——不同插件有同名 @_cdecl("initPlugin") 会撞名
xcrun --sdk iphoneos swiftc -emit-library -static \
  -o libs/lib<Name>Plugin.a -target arm64-apple-ios15.0 -sdk "$SDK" \
  -I mods $(find plugin-<name>/ios/Sources -name "*.swift")
```

project.yml 里补：

```yaml
OTHER_LDFLAGS: $(inherited) -lSwiftRs -lTauriSwift -l<Name>Plugin
```

## 静态库放哪：DebugLib 和 Externals 都要放

xcodegen 工程常见约定：`DebugLib/`（debug 配置）和
`Externals/arm64/Release/`（release 配置）放预编译的 `libapp.a`。
**scheme 默认跑 Debug 配置**——只放了 Externals 会报
`ld: library 'app' not found`。两个位置都放最省心。

## 其他碎坑

- `fileGroups: [../../src]` 这类引用的目录必须存在，否则
  `Spec validation error: Invalid file group`。
- xcodegen 报 `No "release config" settings found` / `No "iOS" settings found`
  是提示不是错误，只要 .xcodeproj 生成了就算过。
- 部署目标写 15.0 起步（App Store Connect 2026 起拒绝 15 以下的上传）。

## 构建与产物

```bash
xcodegen generate
xcodebuild -project App.xcodeproj -scheme App_iOS -configuration Release \
  -destination "generic/platform=iOS" CODE_SIGNING_ALLOWED=NO \
  -derivedDataPath build/dd build
# 产物在 build/dd/Build/Products/<config>-iphoneos/App.app
```

打包成 ipa：

```bash
mkdir Payload && cp -R "App.app" Payload/ && zip -qr App.ipa Payload && rm -rf Payload
```

之后的签名装机见 [install-device.md](install-device.md)。
