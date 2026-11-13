# AGENTS.md — 本仓库的协作规范

这是一个公开的经验库仓库。给 AI 协作代理（以及未来的人）的规矩：

## 定位与红线

- **通用能力库**：所有文档和脚本必须与具体项目无关。描述案例时用形态而非名称
  （"Rust 后端 + WebView 壳的 app"、"Tauri v2 工程"、"依赖 C++ 加密库的 app"），
  示例 bundle ID 一律 `com.example.*`，路径一律 `/path/to/your-app`。
- **公开仓库隐私红线**：禁止出现真实主机名/内网 IP、ASC Key ID、Issuer ID、
  Team ID、设备 UDID、任何人名。一律占位符（`<mac>`、`<KEY_ID>`、`<ISSUER_ID>`）。
- 本仓库只收**可复用的流程与工具**，不收某个 app 的构建配置本身。

## 写作约定

- 中文为主，讲人话，术语第一次出现给一句解释。
- 每个 pitfall 必须三要素齐全：**现象 / 根因 / 解法**。现象要写成可搜索的报错原文。
- 文档之间用相对链接，坑的详细展开放 `docs/pitfalls.md`，主题文档只留索引。

## 脚本约定

- 参数化：路径全部走参数或环境变量，禁止硬编码机器特定路径。
- `set -euo pipefail`；可重复执行（幂等）。
- 改动 `parity_check.py` / `gen_contract.py` 后**必须**跑 `python3 parity_check.py --selftest`
  且绿，才允许提交。

## parity 流程（构建管线的硬性步骤）

1. `gen_contract.py` 从源工程配置程序化生成契约（**禁止**手抄 Info.plist）。
2. 构建产物先过 `parity_check.py <contract> <App.app|App.ipa>`，**有 FAIL 必须停**，
   不允许"先装了再说"。
3. 装机侧安全规则：**禁止 uninstall 设备上不是自己装的 app**；安装前比对目标
   bundle ID 是否与设备上已有应用冲突，冲突即停并上报。

## 文档地图

| 想做什么 | 看哪 |
|---|---|
| 装 Linux 环境 | docs/setup-linux.md |
| 编 C/C++ 或 Rust 依赖 | docs/native-libs.md |
| 写 SwiftPM wrapper | docs/swift-build.md |
| 复活 xcodegen 工程 | docs/xcodebuild-lane.md |
| 签名装机 | docs/install-device.md |
| 防配置漏带 | docs/parity.md |
| 查报错 | docs/pitfalls.md |
