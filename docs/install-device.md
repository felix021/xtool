# 签名与装机（Linux，usbmuxd 直连设备）

前置：iOS 设备用 USB 连到这台 Linux（虚拟化环境先做 USB 直通），usbmuxd
已装（[setup-linux.md](setup-linux.md) 第 1 步）。CLI 就是构建时装好的
`~/bin/xtool`。

链路自检（设备插好后应能列出）：

```bash
xtool devices
```

## 认证（一次性）

```bash
xtool auth login          # 交互选择模式，或直接 -m key / -m password
```

| 模式 | 要求 | 说明 |
|---|---|---|
| API key（`-m key`） | 付费开发者会员 | 走官方 App Store Connect API；Team Key + App Manager 角色 |
| 密码（`-m password`） | 任意 Apple ID | 走 Apple 私有 API（模拟虚拟设备登录）；介意的话用小号 |

提示顺序：key 模式是 **Key ID → Issuer ID → Key path**（三个值来自 ASC 后台
Users and Access → Integrations → App Store Connect API，以及 .p8 文件）；
password 模式是 **Apple ID → 密码 → 2FA 验证码**（必须在真人终端做，交互式）。

凭据落盘后无需再次登录。

## 安装

```bash
xtool install App.ipa        # 自动 provisioning → 签名 → 装机 → 校验
```

provisioning profile 约 1 年有效，到期重跑一次 install 即可。

## dev 包与正式版并存

同一个 bundle ID 会**原地覆盖**设备上的现有 app（包括从 App Store/TestFlight
装的正式版）。做实验用的 dev 包要三处都区分：

```yaml
# 1. bundle ID 加后缀（xtool.yml / project.yml）
bundleID: com.example.myapp.dev
# 2+3. Info.plist 两个名字键都加后缀——CFBundleName 默认从可执行文件名合成，
#      不显式写的话权限弹窗/设置里显示的还是原名
CFBundleName: MyApp dev
CFBundleDisplayName: MyApp dev
```

显示名尽量短：主屏标签会被截断。

## ⚠️ 设备操作安全红线（事故换来的规则）

- **禁止 uninstall 不是自己装的 app。** xtool 的 uninstall 会连应用容器数据
  一起删掉。任何删除动作前必须向设备主人确认目标 bundle ID。
- 安装前比对目标 bundle ID 与设备上已有应用：撞正式版 ID = 覆盖风险，停下来确认。
- 原地升级不刷新主屏显示名与设备族行为；验证这类改动需要 uninstall（自己的
  dev ID 才行）+ 全新 install。

## 常见装机侧报错对照

| 报错 | 根因 |
|---|---|
| `xtool devices` 列不出设备 | usbmuxd 没跑 / USB 直通未生效 / 线只供电不传数据 |
| `Operation unsupported`（auth login） | stdin 是管道/socket 而非 TTY 或常规文件 → 文件重定向喂答案；交互认证进真人终端 |
| 装完没图标/名字没变 | 见 swift-build.md「自动注入」一节 + SpringBoard 缓存（uninstall+install 刷） |
