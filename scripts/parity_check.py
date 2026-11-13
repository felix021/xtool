#!/usr/bin/env python3
"""iOS 包 parity 检查器：契约(.json, 从源 project.yml 程序化生成) vs .app 目录或 .ipa。

分级: FAIL(必须修) / WARN(需人审) / PASS。退出码 1 = 存在 FAIL。
纯 python3(plistlib+zipfile)，Mac/Linux 均可跑。

用法: parity_check.py contract.json <App.app | App.ipa>
自测: parity_check.py --selftest   （codex 反例要求：坏包必须被拦住）
"""
import argparse, fnmatch, io, json, plistlib, sys, tempfile, zipfile
from pathlib import Path

KNOWN_TOOL_KEYS = {  # 工具链合成/渠道元数据，出现在包里属正常，不进契约也不告警
    "CFBundleExecutable", "CFBundleIdentifier", "CFBundleInfoDictionaryVersion",
    "CFBundlePackageType", "CFBundleDevelopmentRegion", "CFBundleShortVersionString",
    "CFBundleVersion", "CFBundleSupportedPlatforms", "MinimumOSVersion",
    "DTPlatformName", "DTPlatformBuild", "DTSDKName", "DTSDKBuild", "DTXcode",
    "DTXcodeBuild", "DTCompiler", "BuildMachineOSBuild", "LSRequiresIPhoneOS",
    "UIRequiresFullScreen", "CFBundleIcons~ipad", "CFBundleAllowMixedLocalizations",
    # 工具自动注入且已被显式规则覆盖的键（设备族/图标规则、dev 后缀规则）
    "UIDeviceFamily", "CFBundleIconFile", "CFBundleIcons", "UIRequiredDeviceCapabilities",
    "DTPlatformVersion",
}
DEV_RULED_KEYS = {"CFBundleName", "CFBundleDisplayName"}  # dev_suffix 规则管，不做键级等值


class App:
    """.app 目录或 ipa 内 .app 的统一读取接口。"""

    def __init__(self, path: Path):
        self.zf = None
        self.prefix = ""
        if path.suffix == ".ipa":
            self.zf = zipfile.ZipFile(path)
            apps = sorted({n.split("/")[1] for n in self.zf.namelist()
                           if n.startswith("Payload/") and n.count("/") >= 2
                           and n.split("/")[1].endswith(".app")})
            assert apps, "ipa 里找不到 Payload/*.app"
            self.prefix = f"Payload/{apps[0]}/"
        else:
            assert path.is_dir(), f"{path} 不是目录也不是 ipa"

    # 简化：目录模式的 root 就是构造入参
    @property
    def root(self) -> Path:
        return self._root

    _root: Path = None

    def exists(self, rel: str) -> bool:
        if self.zf:
            try:
                self.zf.getinfo(self.prefix + rel); return True
            except KeyError:
                return False
        return (self._root / rel).exists()

    def size(self, rel: str) -> int:
        if self.zf:
            return self.zf.getinfo(self.prefix + rel).file_size
        return (self._root / rel).stat().st_size

    def names(self) -> list:
        if self.zf:
            return [n[len(self.prefix):] for n in self.zf.namelist()
                    if n.startswith(self.prefix) and not n.endswith("/")]
        return [str(p.relative_to(self._root)) for p in self._root.rglob("*") if p.is_file()]

    def plist(self, rel: str = "Info.plist") -> dict:
        data = (self.zf.read(self.prefix + rel) if self.zf
                else (self._root / rel).read_bytes())
        return plistlib.loads(data)


def init_root(app: App, path: Path):
    app._root = path


def eq(exp, got):
    """契约值(yaml 标量) vs plist 值：宽松数值/字符串等价，bool 严格。"""
    if isinstance(exp, str) and exp.startswith("$("):
        return True  # 构建变量：只查存在
    if isinstance(exp, bool) or isinstance(got, bool):
        return exp is got or exp == got  # bool 与 bool
    if exp == got:
        return True
    try:
        return not isinstance(exp, (dict, list)) and not isinstance(got, (dict, list)) \
            and str(exp) == str(got)
    except Exception:
        return False


def check_plist(contract: dict, plist: dict, out: list):
    set_keys = set(contract.get("set_keys", []))

    def walk(cnode: dict, pnode: dict, path: str):
        for k, v in cnode.items():
            here = f"{path}/{k}"
            if k not in pnode:
                out.append(("FAIL", f"Info.plist 缺键 {here}"))
                continue
            got = pnode[k]
            if isinstance(v, dict):
                if not isinstance(got, dict):
                    out.append(("FAIL", f"Info.plist {here} 应为 dict，实际 {type(got).__name__}"))
                else:
                    walk(v, got, here)
            elif isinstance(v, list) and k in set_keys:
                # 集合语义：契约成员必须全在（允许新增）
                miss = [m for m in v if not any(eq(m, g) for g in got)]
                if miss:
                    out.append(("FAIL", f"Info.plist {here} 缺成员 {miss} (实际 {got})"))
            elif isinstance(v, list):
                if not (isinstance(got, list) and len(v) == len(got)
                        and all(eq(a, b) for a, b in zip(v, got))):
                    out.append(("FAIL", f"Info.plist {here} 值不符: 契约 {v} vs 实际 {got}"))
            else:
                if not eq(v, got):
                    out.append(("FAIL", f"Info.plist {here} 值不符: 契约 {v!r} vs 实际 {got!r}"))

    walk(contract["plist"], plist, "")

    # 契约外新增键 → 提示审阅（防漏配新能力）
    known = KNOWN_TOOL_KEYS | (DEV_RULED_KEYS if contract.get("dev_suffix") else set())
    for k in plist:
        if k not in contract["plist"] and k not in known:
            out.append(("WARN", f"Info.plist 有契约外键 {k}（确认是否源 yml 新增后回填契约）"))


def check_rules(contract: dict, app: App, plist: dict, out: list):
    fams = contract.get("device_families")
    if fams:
        got = plist.get("UIDeviceFamily", [])
        miss = [f for f in fams if f not in got]
        if miss:
            out.append(("FAIL", f"UIDeviceFamily={got} 缺 {miss}（iPad 会退化成 iPhone 兼容布局）"))

    if contract.get("require_icon"):
        icons = plist.get("CFBundleIcons", {}).get("CFBundlePrimaryIcon") \
            if isinstance(plist.get("CFBundleIcons"), dict) else None
        ok = (icons and (icons.get("CFBundleIconFiles") or icons.get("CFBundleIconName"))) \
            or plist.get("CFBundleIconFile") \
            or any(n.endswith(".png") and "AppIcon" in n for n in app.names())
        if not ok:
            out.append(("FAIL", "无图标（CFBundleIcons/CFBundleIconFile/AppIcon png 均缺失）"))
        if not any(n == "Assets.car" for n in app.names()) and not plist.get("CFBundleIconFile"):
            out.append(("WARN", "无 Assets.car 且无 CFBundleIconFile（xtool 线走 iconPath 属正常，xcodebuild 线需查）"))

    if contract.get("dev_suffix"):
        for k in ("CFBundleName", "CFBundleDisplayName"):
            v = plist.get(k, "")
            if contract["dev_suffix"] not in str(v):
                out.append(("FAIL", f"{k}={v!r} 不含 dev 后缀（无法与正式版区分）"))

    for pat in contract.get("required_resources", []):
        hits = [n for n in app.names() if fnmatch.fnmatch(n, pat)]
        if not hits:
            out.append(("FAIL", f"必需资源缺失: {pat}"))
        elif any(app.size(n) == 0 for n in hits):
            out.append(("FAIL", f"必需资源为空文件: {pat}"))


def run(contract_path: Path, app_path: Path) -> int:
    contract = json.loads(contract_path.read_text())
    app = App(app_path)
    init_root(app, app_path)
    out: list = []
    check_plist(contract, app.plist(), out)
    check_rules(contract, app, app.plist(), out)

    fails = [m for lv, m in out if lv == "FAIL"]
    warns = [m for lv, m in out if lv == "WARN"]
    for lv, m in out:
        print(f"[{lv}] {m}")
    print(f"== {contract['app']}: {len(fails)} FAIL, {len(warns)} WARN ==")
    return 1 if fails else 0


def selftest() -> int:
    """反例自测：好包 PASS，坏包（删 Bonjour 成员/删设备族/删图标）必须 FAIL。"""
    import shutil
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        contract = {
            "app": "selftest", "plist": {
                "NSBonjourServices": ["_a._tcp", "_b._tcp"],
                "NSLocalNetworkUsageDescription": "x",
            },
            "device_families": [1, 2], "require_icon": True,
            "required_resources": ["web/index.html"], "set_keys": ["NSBonjourServices"],
        }
        good = {"NSBonjourServices": ["_a._tcp", "_b._tcp"], "NSLocalNetworkUsageDescription": "x",
                "UIDeviceFamily": [1, 2], "CFBundleIcons": {"CFBundlePrimaryIcon": {"CFBundleIconFiles": ["AppIcon60x60"]}}}
        bad = dict(good)
        bad["NSBonjourServices"] = ["_a._tcp"]      # 漏成员
        bad["UIDeviceFamily"] = [1]                  # 漏 iPad
        bad.pop("CFBundleIcons")                     # 漏图标

        def mk(name, pl):
            d = td / name; (d / "web").mkdir(parents=True)
            (d / "web" / "index.html").write_text("x")
            (d / "Info.plist").write_bytes(plistlib.dumps(pl))
            return d

        def judge(d):
            out = []
            check_plist(contract, plistlib.loads((d / "Info.plist").read_bytes()), out)
            a = App(d); init_root(a, d)
            check_rules(contract, a, plistlib.loads((d / "Info.plist").read_bytes()), out)
            return [m for lv, m in out if lv == "FAIL"]

        g = judge(mk("good", good)); b = judge(mk("bad", bad))
        assert not g, f"好包误报: {g}"
        assert len(b) == 3, f"坏包应拦 3 处，实际 {len(b)}: {b}"
        print("selftest PASS: 好包 0 FAIL；坏包拦住 Bonjour 成员缺失/设备族退化/图标缺失 3 处")
        return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("contract", nargs="?")
    ap.add_argument("app", nargs="?")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    sys.exit(selftest() if a.selftest else run(Path(a.contract), Path(a.app)))
