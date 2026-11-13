# parity 检查：防"旧包有、新包没有"

## 为什么需要

换一条构建管线（比如从 Mac 上的 Xcode 换到 Linux 交叉编译），最容易出的事故
不是编不过——编译错误会喊疼——而是**静默少了东西**。实战中两类真实事故：

1. **手抄漏键**：从源工程配置手工转写 Info.plist，读源文件时被截断，漏了
   `NSBonjourServices`。后果：本地网络权限弹窗永不出现，app 的设备发现功能
   静默瘫痪，安装一切正常毫无报错。
2. **合成键丢失**：`TARGETED_DEVICE_FAMILY` / `ASSETCATALOG_COMPILER_APPICON_NAME`
   不在任何源码文件里，由 Xcode 构建过程合成。换了管线后没人合成它们 →
   iPad 布局退化成 iPhone 兼容模式、图标消失。

结论：**靠细心防不住，靠枚举"重要键"也防不住**（下一个漏的键不会在你名单上）。
机制只有两条腿：

- 契约**程序化**从源工程配置生成（消灭手抄这个错误类别本身）；
- 显式规则断言**工具合成**的行为（消灭"源码里根本没有"这个类别）。

## 用法

```bash
# 1. 从源工程 project.yml 的 info 段生成契约（--dev 表示 dev 包：名称交给后缀规则）
python3 scripts/gen_contract.py \
  --yml /path/to/project.yml --target MyApp \
  --families 1,2 --icon \
  --resource 'web/index.html' --resource 'packs/*.db' \
  --set-key NSBonjourServices \
  --dev --out myapp.json

# 2. 构建完成后检查（.app 目录或 .ipa 都行）
python3 scripts/parity_check.py myapp.json build/MyApp.app
# 退出码 1 = 有 FAIL，管线必须停在这里

# 3. 改了检查器本身？自测反例必须绿
python3 scripts/parity_check.py --selftest
```

## 检查什么

| 维度 | 规则 | 定级 |
|---|---|---|
| 契约键 | 源 yml info 段的每个键路径必须在包 plist 中存在且值相等（`$(VAR)` 构建变量只查存在；声明为 set 语义的键做成员包含比较，允许新增） | 缺失/不等 → FAIL |
| 设备族 | `UIDeviceFamily` 必须包含契约声明的 families | 缺 iPad → FAIL |
| 图标 | `CFBundleIcons`/`CFBundleIconFile`/AppIcon png 至少其一存在 | 全无 → FAIL |
| dev 后缀 | dev 包的 `CFBundleName`/`CFBundleDisplayName` 必须含后缀 | 违反 → FAIL |
| 必需资源 | 契约里的 glob 模式必须命中非空文件 | 缺失/空 → FAIL |
| 契约外键 | 包里有、契约里没有的键 | WARN（提醒回填契约，防漏配新能力） |

已知工具注入/合成且被显式规则覆盖的键（`UIDeviceFamily`、`CFBundleIconFile`
等）不告警——名单在 `parity_check.py` 的 `KNOWN_TOOL_KEYS`。

## selftest 为什么重要

检查器本身也会错。selftest 构造一个好包 + 一个坏包（删 Bonjour 成员、删设备族、
删图标），断言坏包**必须**被拦住三处。改动检查逻辑后先跑它。

## 已知盲区（V1 如实声明）

- **entitlements**：需要 Apple 的 codesign 工具（`codesign -d --entitlements :-`）提取对比，
  且要区分"签名渠道注入的"（get-task-allow 等，按渠道豁免）和"功能性能力"
  （keychain groups、app groups 等，必须保）。未实现。
- **Mach-O 依赖**：otool -L 层面的动态库/rpath 对比。未实现。
- **签名后产物**：`xtool install` 是"重签+装机"一体，签名后的最终包拿不到，
  无法做签名前后的对比（只能做到"装机前检查未签名产物"）。要做的话得给
  xtool 加导出接口，或拆成"签名导出"+"安装"两步。
- **运行时行为**：静态对比永远覆盖不了权限弹窗、深链接、分屏。最小验收
  checklist：干净首启（权限弹窗该弹的都弹）+ 覆盖升级（旧数据兼容）两条路径，
  不能只测其一。

## 设计基准

本机制源自一次完整的方案评审（三快照 B/U/S 四对比模型：旧正式包/新构建/
签名后产物），V1 实现了其中"源配置→U"链 + 合成键规则。B 基准（旧 ipa
逐键 diff）作为可选增强：有旧正式 ipa 时可以再加一层"未解释的删除即 FAIL"，
那是抓"源码里没有、旧管线凭历史状态才有"这类残余风险的唯一手段。
