# 路线 A：xtool（SwiftPM）构建 iOS app

xtool 的 app 模型：**一个 SwiftPM package，一个 library product 就代表主 app**，
配 `xtool.yml` 描述 bundle ID / Info.plist / 图标 / 根资源。原生依赖（Rust、
C/C++ 静态库）在 Linux 上先交叉编译好（见 [native-libs.md](native-libs.md)），
Swift 壳通过 unsafeFlags 链接。

## 工程骨架

```
myapp-xtool/
  Package.swift
  xtool.yml
  Info.plist          # 全部键显式写在这里（xtool.yml: infoPath）
  icon.png            # 图标（SwiftPM 不编译 xcassets，见下）
  libs/libmyapp.a     # 交叉编译产物
  Sources/
    MyLibC/           # C 桥接 target（publicHeadersPath）
    MyApp/            # Swift 壳 + 资源
      Resources/...
```

`xtool.yml` 全部字段：

```yaml
version: 1
bundleID: com.example.myapp
infoPath: Info.plist
iconPath: icon.png          # 可选：没有它就没图标
resources:                  # 可选：拷到 .app 根（Bundle.main 可见）
- Resources/server.jar
```

## Package.swift 的五个坑

1. **`import Foundation`**：manifest 里用 `URL(fileURLWithPath: #filePath)`
   就必须加，否则 `cannot find 'URL' in scope`。
2. **`defaultLocalization: "en"`**：源码带 `.lproj` 目录（本地化）时必须声明，
   否则 `manifest property 'defaultLocalization' not set`。
3. **`swiftLanguageModes: [.v5]`**：源码是 Swift 5 语义写的，默认 Swift 6 模式
   会把并发检查的 warning 升级成 error（`mutation of captured var ... in
   concurrently-executing code`）。
4. **参数顺序**：`swiftLanguageModes` 必须在 `targets` 之后、
   `cxxLanguageStandard` 之前（错了 manifest 直接编译失败，报错信息会提示）。
5. **链接静态库**：
   ```swift
   linkerSettings: [
       .unsafeFlags(["-L\(root)/libs", "-lmyapp", "-lc++"]),
       // compiler-rt：availability 符号（__isPlatformVersionAtLeast 等）在这里
       .unsafeFlags(["-L\(root)/sdk-clang-rt", "-lclang_rt.ios"]),
   ]
   ```
   `sdk-clang-rt` 指到 Xcode toolchain 的
   `usr/lib/clang/21/lib/darwin/`（`libclang_rt.ios.a`）。
   缺了报 `undefined symbol: __isPlatformVersionAtLeast`。

## xtool 会自动注入/合成什么（不知道这些就会"莫名缺东西"）

| 键 | 来源 | 备注 |
|---|---|---|
| `UIDeviceFamily` | xtool 注入 `[1,2]` | iPad 布局正常，无需自己写 |
| `CFBundleIconFile` | `iconPath` 生成 | xcassets 里的图标**不会**被编译 |
| `CFBundleName` | 默认 = 可执行文件名 | 想要别的名字（如 dev 后缀）必须**显式写** |
| `CFBundleShortVersionString` | 默认 `1.0.0` | 要跟源工程版本对齐就显式写 |

## 资源：Bundle.module 而不是 Bundle.main

SwiftPM 的 `.copy(...)` 资源会被打进独立的
`<包名>_<Target>.bundle`，代码里定位要用 `Bundle.module.resourceURL`
（原工程写 `Bundle.main.resourceURL` 的要改这一处）。资源放进 `.app` 根
（`xtool.yml: resources:`）的才走 `Bundle.main`。几百 MB 的资源目录实测没问题。

## Info.plist：权限键的完整清单意识

从源工程转写 plist 时**必须程序化**（见 [parity.md](parity.md)），
但先知道几类键的存在感：

- `NSLocalNetworkUsageDescription` + **`NSBonjourServices`**：后者不写，
  本地网络权限弹窗**不会出现**，mDNS 发现静默失败——最常见的"功能莫名不可用"。
- `NSMicrophoneUsageDescription` / `NSCameraUsageDescription` 等 usage 键：
  缺了不是"少个弹窗"，是 TCC 直接杀进程。
- `CFBundleURLTypes`：深链接 scheme。
- `UISupportedInterfaceOrientations`（含 `~ipad` 变体）：方向锁定的键在 plist
  这边，不在 build settings。

## 构建命令

```bash
cd myapp-xtool
export PATH="$SWIFT_TC:$XTOOLS_BIN:~/bin:$PATH"
xtool dev build        # 不登录、不签名，产出 xtool/MyApp.app
```

产物自检：`file MyApp.app/MyApp` → `Mach-O 64-bit arm64 executable`；
`LC_BUILD_VERSION` 的 `platform 2`（iOS）、`minos` = 部署目标。
