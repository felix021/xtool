#!/usr/bin/env python3
"""从源工程 project.yml 程序化生成 parity 契约（杜绝手抄 Info.plist）。

用法:
  gen_contract.py --yml project.yml --target MyApp \
      [--families 1,2] [--icon] [--dev] \
      [--resource 'web/index.html'] [--set-key NSBonjourServices] \
      --out myapp.json

说明:
  --target     主 app target 在 yml 里的名字（targets.<name>.info.properties 被抽取为键级契约）
  --families   必须支持的 UIDeviceFamily（合成键规则；缺 iPad 会退化成 iPhone 兼容布局）
  --icon       要求包里有图标（SwiftPM 线用 iconPath、xcodebuild 线用 xcassets 编译产物）
  --dev        dev 包：CFBundleName/CFBundleDisplayName 不做键级等值，改为"必须含 dev 后缀"规则
  --resource   必需资源（glob，可重复；SwiftPM 线注意资源在 <pkg>_<Target>.bundle 内）
  --set-key    按集合语义比较的键（成员包含而非全等，可重复；如 NSBonjourServices）
"""
import argparse, json, sys
from pathlib import Path

import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yml", required=True, type=Path)
    ap.add_argument("--target", required=True)
    ap.add_argument("--families", default="1,2")
    ap.add_argument("--icon", action="store_true")
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--resource", action="append", default=[])
    ap.add_argument("--set-key", action="append", default=[])
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()

    doc = yaml.safe_load(a.yml.read_text())
    try:
        props = dict(doc["targets"][a.target]["info"]["properties"])
    except KeyError as e:
        sys.exit(f"project.yml 里找不到 targets.{a.target}.info.properties: {e}")

    if a.dev:
        # dev 构建名称故意与正式版不同，交给 dev 后缀规则，不做键级等值
        for k in ("CFBundleDisplayName", "CFBundleName"):
            props.pop(k, None)

    contract = {
        "app": a.target,
        "source_yml": str(a.yml),
        "plist": props,
        "device_families": [int(x) for x in a.families.split(",")],
        "require_icon": a.icon,
        "required_resources": a.resource,
        "set_keys": a.set_key,
    }
    if a.dev:
        contract["dev_suffix"] = "dev"

    a.out.write_text(json.dumps(contract, ensure_ascii=False, indent=1))
    print(f"contract[{a.target}]: {len(props)} plist keys -> {a.out}")


if __name__ == "__main__":
    main()
