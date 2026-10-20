#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HarmonyOps —— HarmonyOS 平台 PlatformOps 实现。

直接拼接 `hdc -t <serial> shell <cmd>`，不经过 imeituan CLI 的 device
shell/input/open-url 封装：CLI 的 open-url --package-id 在鸿蒙分支未生效，
必然触发多包消歧弹窗；imeituan-cli 的 `control inspect-tree` 内置正则
不兼容该系统版本的 hidumper 输出格式。鸿蒙全部走本文件直拼 hdc 命令，
inspect_tree 复用 uitest dumpLayout（详见 devices/harmony/probes/
inspect_tree.py 与 node_adapter.py）。

broadcast/content_call 是 Android ContentProvider/intent broadcast 专属
机制，鸿蒙无等价物，不强行模拟，直接返回 False。

安装机制按【设备形态 form】分两条通道（见 HarmonyOps.install_app，选型依据
KM 2783208642《鸿蒙 HPX 打包类型与 imeituan-cli device install 安装矩阵》）：
  - real（真机/云真机）：`hdc install <本地.hap>` 对企业签名包有较高概率因签名
    校验失败，系统只认可「通过系统浏览器打开 HPX 生成的企业安装页、触发系统级
    安装器」这一种方式。链路：打开安装页 → 点击"点击下载" → 校验来源域名 →
    点击系统安装确认弹窗 → 按 Home 回桌面（真机实测：停留在浏览器/弹窗界面时
    系统不会触发后台下载安装）。
  - emulator（模拟器）：不支持 enterprise Profile（企业安装页会报"下载来源验证
    失败 10002"），只能走 HDC/`bm install` 直装非 enterprise 的**可测性(debug)
    签名 HAP**（release 包缺 MSI pillowConfig handler，登录会静默卡在 Loading，见
    references/apk_sources.json 的 `requires_testability_build`）。为省掉每次 1.4G 重传，HAP
    先落**设备侧缓存目录**（`DEVICE_APK_CACHE_DIR`）：设备侧已有同名同大小包时
    直接 `bm install -p <设备侧路径>`，否则从本机缓存 `hdc file send` 下发一次。
两条通道安装均为异步/不可即时观察，最终是否成功由调用方
（devices/toolchain/app_installer.py::verify_install）轮询 `bm dump` 版本号确认，本
模块的 install_app 只负责触发安装动作。
"""
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import urlparse

from shared.json_utils import write_json_atomic
from devices.base import PlatformOps, AppDescriptor, LocalDeviceProbeError, get_device_category
from devices.harmony.probes.inspect_tree import inspect_tree as _harmony_inspect_tree
from devices.harmony.probes.node_adapter import parse_tree as _harmony_parse_tree
# 统一命名对外导出，供 context.get_probes()/execution.screen.inspect_tree 的工厂
# 分发缓存引用（与 devices/android/probes/node_adapter.py 的 parse_tree
# 同名，调用方按 platform 分发到本模块后无需关心具体导出名）。
parse_tree = _harmony_parse_tree
from devices.harmony.hdc import Hdc, ensure_hdc
from shared.paths import dumps_dir


def _find_first_value(node, keys: set, expect_type):
    """在解析后的 JSON 里递归查找首个命中键的值（字段层级随系统版本变化，不写死）。

    `bm dump` 返回的包信息在不同 HarmonyOS 版本上层级/命名不一致（如顶层、
    appInfo 子结构），因此不按固定路径取值；找不到或类型不符时返回 None。
    """
    if isinstance(node, dict):
        for k, v in node.items():
            if k in keys and isinstance(v, expect_type):
                return v
        for v in node.values():
            found = _find_first_value(v, keys, expect_type)
            if found is not None:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _find_first_value(v, keys, expect_type)
            if found is not None:
                return found
    return None

# 企业安装页"点击下载"链接的匹配文案（页面模板固定文案，真机验证稳定）。
_ENTERPRISE_PAGE_DOWNLOAD_TEXT = "点击下载"
# 系统安装确认弹窗"安装"按钮的语义化 id，比文案匹配更可靠（文案会随首次
# 安装/覆盖安装场景切换，id 不变）。
_INSTALL_DIALOG_CONFIRM_BUTTON_ID = "advanced_dialog_button_1"
# 系统安装确认弹窗允许的可信制品域名前缀，安装前校验弹窗文案中出现的来源
# 域名是否命中，防止企业安装页 URL 被篡改后静默安装未知来源应用。
_TRUSTED_INSTALL_SOURCE_HOSTS = ("hyperloop-s3.sankuai.com",)

# hidumper PowerManagerService "Current State" 取值中判定为"不可交互"的集合。
# 不等同于 imeituan CLI 的 SLEEPING_STATES={SLEEP,DOZE}（该集合仅服务于"是否
# 需要唤醒"这一更窄的判断）——本地真机自动化只要不是 AWAKE 就大概率拿不到
# 目标 App 的可见窗口，因此额外收录 HIBERNATE/SHUTDOWN/STAND_BY/INACTIVE。
_HARMONY_NON_INTERACTIVE_STATES = {"SLEEP", "DOZE", "HIBERNATE", "SHUTDOWN", "STAND_BY", "INACTIVE"}

def _dump_ui_nodes(hdc: Hdc, timeout: int = 30) -> list:
    """采集当前前台内容（不限定 bundle_name）的 uitest dumpLayout，解析为
    UiNode 列表。企业安装页/系统安装弹窗均非目标 App 窗口，不能按
    AppDescriptor.package_name 过滤，因此不复用 HarmonyOps.inspect_tree()
    （其固定按目标 App bundle_name 过滤）。
    """
    raw = _harmony_inspect_tree(hdc.serial, bundle_name=None, timeout=timeout, remote=hdc.remote)
    return _harmony_parse_tree(raw)


def _find_node_by_text(nodes: list, text: str):
    """按文本子串查找节点，返回第一个匹配的 clickable 节点，找不到返回 None。"""
    for n in nodes:
        t = n.get("text") or ""
        if text in t and n.get("clickable"):
            return n
    return None


def _find_node_by_id(nodes: list, m_id: str):
    for n in nodes:
        if n.get("m_id") == m_id:
            return n
    return None


def _center_of_node(node) -> tuple:
    x, y, w, h = node.get("x"), node.get("y"), node.get("w"), node.get("h")
    if None in (x, y, w, h):
        return None
    return x + w // 2, y + h // 2


def _poll_for_node(hdc: Hdc, finder, *, timeout_sec: float = 20, interval_sec: float = 1.5):
    """轮询 dumpLayout 直到 finder(nodes) 返回非 None 节点，或超时返回 None。

    企业安装页的下载链接渲染、系统安装弹窗的弹出都存在网络/系统调度延迟，
    单次采集可能落在渲染完成之前，需要轮询而非一次性采集判定失败。
    """
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            nodes = _dump_ui_nodes(hdc)
        except Exception:
            nodes = []
        hit = finder(nodes)
        if hit is not None:
            return hit
        time.sleep(interval_sec)
    return None


# 全新安装后是否存在系统级强制拦截，命中 device_guidance.GUIDANCE_REGISTRY 的
# key；HarmonyOS 企业签名应用首次启动会被信任校验拦截，Android 无此问题（其
# ops.py 中同名常量为 None）。供 devices/device_commands.py::cmd_setup 在
# fresh_install 后据此判断是否提前终止并展示引导，取代硬编码的 platform 判断。
FRESH_INSTALL_GUIDANCE_ID = "harmony_local_untrusted_app"

# App 版本探测/安装动作幂等重试上限。HarmonyOS 走「打开企业安装页 + 点击
# 下载 + 点击系统安装确认」的 UI 自动化安装流程，安装包由系统在后台下载，
# 功能测试包体积明显大于 Android APK，全流程耗时更长，重试上限相应放宽
# （Android 对称常量见 devices/android/ops.py::INSTALL_VERIFY_RETRIES=24）。
INSTALL_VERIFY_RETRIES = 40


def register_device(serial: str, device_type: str = "sandbox", remote_address: str = None) -> dict:
    """注册设备到 imeituan CLI session，返回 {ok, session_id, detail}。

    按设备获取方式选连接入口（与 android/ios 对称）：
    - 云设备（category=cloud，如 cloud-emulator / cloud_device）：`device register
      --serial <SN> --remote-address <RA>` —— 目标设备在远程 hdc server 上；
    - 本地真机（local）：`device connect --target local-device`，跳过网络探测。
    """
    if get_device_category(device_type) == "cloud":
        from devices.toolchain.imeituan_cli import imeituan_register_device
        return imeituan_register_device(serial, platform="harmony", remote_address=remote_address)
    from devices.toolchain.imeituan_cli import imeituan_connect_local_device
    return imeituan_connect_local_device(serial, platform="harmony")


def reset_probe_state() -> None:
    """重置本平台探针的进程级状态（页面切换时由 context.invalidate_probes 调用）。

    HarmonyOS 的 native 探针无跨页面的进程级缓存（无 CDP 链路），
    因此为空实现——仅为满足平台模块契约（见 _REQUIRED_MODULE_ATTRS）。
    """
    return None


def build_probes(ops, app_descriptor) -> list:
    """构建鸿蒙渲染层探针链：仅 native，无额外探针。

    `uitest dumpLayout` 能穿透 ArkWeb 拿到内部 DOM（Web 节点下直接挂着
    rootWebArea 及 W3C accessibility role 节点），文本查找与点击定位已由
NativeProbe 完整覆盖，无条件返回单一 native 探针。
    """
    from devices.harmony.probes.native import NativeProbe
    return [NativeProbe()]


# 工具链不可用时的排查提示（供 devices/device_commands.py::_ensure_toolchain 数据化读取）。
TOOLCHAIN_HINT = "需安装 hdc（运行 check-deps 自动安装，或 imeituan device environment install hdc）"


def ensure_toolchain() -> bool:
    """确保鸿蒙连接工具链（hdc）就绪（与 android::ensure_toolchain 对称）。

    device create/setup 阶段前置调用时**就地补齐 hdc**：`check-deps` 的 platform
    默认 android（在设备组合确定之前执行），不会安装 hdc；而 hdc 是鸿蒙全链路的唯一
    通道（注册会话、推送 scheme、截图、清理设备产物都依赖它），缺失会让云模拟器
    （cloud-emulator）冷启动直接失败且无从自愈。这里与 Android 的 ensure_adb()
    对齐，保证「走到设备阶段工具链必定就绪」。
    """
    hdc_bin, _ = ensure_hdc(install=True)
    return hdc_bin is not None


def probe_local_devices() -> str:
    """探测唯一在线的本地鸿蒙真机，返回其 serial。

    供 devices.lifecycle.local.LocalDeviceLifecycle.acquire() 调用，
    是 device_type=local + platform=harmony 组合的设备发现入口。

    连接探测只反映 USB 调试授权是否就绪，不代表屏幕可交互：hdc shell
    通道不受屏幕状态影响，锁屏/熄屏时探测依然会成功，因此额外做一次
    屏幕可交互性检查，避免流程推进到 UI 步骤才报错。

    Raises:
        LocalDeviceProbeError: 未探测到设备 / 探测到多台设备 /
            工具链不可用 / 屏幕处于不可交互状态。
    """
    from devices.harmony.hdc import list_targets

    hdc_bin, _ = ensure_hdc(install=True)
    if not hdc_bin:
        raise LocalDeviceProbeError("hdc 不可用，无法探测本地鸿蒙真机（请检查 check-deps 输出）")

    serials = list_targets(hdc_bin)
    if not serials:
        raise LocalDeviceProbeError(
            "未探测到已连接的harmony本地真机，请确认设备已连接并完成授权",
            guidance_id="harmony_local_not_connected", platform="harmony",
        )
    if len(serials) > 1:
        raise LocalDeviceProbeError(
            f"探测到多台harmony本地真机 {serials}，本地场景要求唯一在线设备，请断开多余设备后重试",
            guidance_id="harmony_local_multiple_devices", platform="harmony", serials=serials,
        )

    serial = serials[0]
    screen_ops = HarmonyOps(serial)
    screen_state = screen_ops.screen_state()
    if not screen_ops.is_screen_interactive():
        raise LocalDeviceProbeError(
            f"设备 {serial} 当前处于熄屏/锁屏状态（{screen_state}），请解锁后重试",
            guidance_id="harmony_local_screen_locked",
            platform="harmony", serial=serial, screen_state=screen_state,
        )
    return serial


class HarmonyOps(PlatformOps):
    """HarmonyOS 平台实现。"""

    def __init__(self, device_serial: str, app_descriptor: AppDescriptor = None,
                 remote_address: str = None):
        self._serial = device_serial
        self._app = app_descriptor
        self._remote = remote_address or None
        # 设备连接句柄（hdc 命令拼装唯一入口）：云设备 remote_address 非空时命令自动带 -s；
        # 本地真机为 None，命令形态仍为 `hdc -t <serial>`。
        self._hdc = Hdc(device_serial, remote_address)

    @property
    def serial(self) -> str:
        return self._serial

    def _bundle_name(self) -> str:
        if self._app is None:
            raise RuntimeError(
                "HarmonyOps 需要 AppDescriptor，请通过 get_platform_ops() 获取实例"
            )
        return self._app.package_name

    # ═══════════════════════════════════════════════════════════
    # 感知
    # ═══════════════════════════════════════════════════════════

    def inspect_tree(self, output_path: str, *, timeout: int = 30,
                     whole_screen: bool = False) -> subprocess.CompletedProcess:
        """采集视图树，落盘为 uitest dumpLayout 原始 JSON（未做结构改写）。

        落盘内容直接是 {"attributes": {...}, "children": [...]}，供
        execution.screen.inspect_tree.parse_inspect_tree() 读取后分派给
        devices.harmony.probes.node_adapter.parse_tree() 解析，与
        Android 侧落盘 imeituan inspect-tree 原始 JSON 的约定一致
        （调用方按平台分派 adapter，不关心落盘格式差异）。

        `whole_screen=True` 时不带 `-b`（全窗口合并）：**系统权限弹窗（通知/定位）**
        属系统进程窗口，带 bundle 过滤的 dump 里完全没有它（实测：带 `-b` 时 dump 为
        空、不带才有弹窗节点）。元素定位/文案断言保持默认（按 App 过滤，噪音更少）。
        """
        bundle_name = (None if whole_screen
                       else (self._app.package_name if self._app is not None else None))
        try:
            result = _harmony_inspect_tree(self._serial, bundle_name=bundle_name, timeout=timeout, remote=self._remote)
        except Exception as e:
            return subprocess.CompletedProcess(args=["inspect_tree", self._serial], returncode=1, stdout="", stderr=str(e))
        write_json_atomic(output_path, result)
        return subprocess.CompletedProcess(args=["inspect_tree", self._serial], returncode=0, stdout="", stderr="")

    # ═══════════════════════════════════════════════════════════
    # 交互原语
    # ═══════════════════════════════════════════════════════════

    def tap(self, x: int, y: int) -> bool:
        r = self._hdc.shell("uitest", "uiInput", "click", str(x), str(y))
        if r.returncode == 0:
            # 记录最近一次点击坐标：`uitest uiInput inputText` 需要“聚焦控件的坐标”，
            # 本镜像下 x/y=0,0 不会写入（实测），见 input_text。
            self._last_tap = (x, y)
        return r.returncode == 0

    def swipe(self, from_x: int, from_y: int, to_x: int, to_y: int,
              duration_ms: int = 500) -> bool:
        r = self._hdc.shell("uitest", "uiInput", "swipe",
                       str(from_x), str(from_y), str(to_x), str(to_y), str(duration_ms))
        return r.returncode == 0

    def input_text(self, text: str) -> bool:
        # `uitest uiInput inputText <x> <y> <text>`：本镜像下 x/y=0,0 **不写入**
        # （实测：输入框已聚焦、光标已就位，但字段仍为空），必须给聚焦控件坐标。
        # 引擎的输入流程总是"先 tap 定位输入框、再 input_text"，故用最近一次 tap 坐标；
        # 无 tap 记录时回退 0,0（保持旧行为）。
        #
        # 注意：**不在输入后自动收输入法**。曾按"键盘遮挡视图树"的猜测加上，实测证伪：
        #   ① 键盘弹起时页面元素仍在 `dumpLayout` 结果里（遮挡并非问题，真因是键盘
        #      首启向导页占据了窗口）；
        #   ② 在验证码页输入后立即按 Back 会**打断登录提交**（登录态探针报 logged_out）。
        # 因此"收输入法"不由本层触发：若确有必要，应由真正需要干净视图的调用方在观察前
        # 自行处理，而不是绑进输入语义。
        #
        # 输入法**首启向导**（首次唤起键盘时弹多步向导、占满前台）不在本层处理：
        # 它属系统层引导，词表在 `platform/popup/patterns.py`，收敛入口是
        # `devices.popup.resolve_system_onboarding`（认证动作在控件缺失时经 L2 唯一入口
        # 自愈），本层只负责"输入"这一件事。
        x, y = getattr(self, "_last_tap", (0, 0))
        r = self._hdc.shell("uitest", "uiInput", "inputText", str(x), str(y), text)
        return r.returncode == 0

    def press_back(self) -> bool:
        return self.keyevent("Back")

    def press_home(self) -> bool:
        return self.keyevent("Home")

    def screenshot(self, path: str) -> bool:
        device_path = "/data/local/tmp/_ai_ui_autotest_engine_shot.jpeg"
        r = self._hdc.shell("snapshot_display", "-f", device_path)
        if r.returncode != 0:
            return False
        r = self._hdc.run("file", "recv", device_path, path)
        return r.returncode == 0

    # ═══════════════════════════════════════════════════════════
    # App 管理
    # ═══════════════════════════════════════════════════════════

    def launch_app(self, component: str, *, launcher_intent: bool = False) -> bool:
        """启动 App。component 沿用 AppDescriptor.main_activity 的 "bundle/ability" 格式。"""
        bundle, _, ability = component.partition("/")
        if not ability:
            ability = "EntryAbility"
        r = self._hdc.shell("aa", "start", "-b", bundle, "-a", ability)
        return r.returncode == 0

    def force_stop(self, package: str) -> bool:
        r = self._hdc.shell("aa", "force-stop", package)
        return r.returncode == 0

    def launch_scheme(self, scheme_url: str) -> bool:
        """推送 scheme URL。必须用 -A action.system.home -U 组合，不能用 -a <ability>，
        否则会变成显式启动导致 URI 被忽略；不能省略 -b，否则触发多包消歧弹窗。
        """
        bundle = self._bundle_name()
        r = self._hdc.shell("aa", "start", "-b", bundle,
                       "-A", "action.system.home", "-U", scheme_url)
        return r.returncode == 0

    def open_url(self, url: str) -> bool:
        return self.launch_scheme(url)

    # ═══════════════════════════════════════════════════════════
    # App 生命周期管理
    # ═══════════════════════════════════════════════════════════

    def installed_packages(self) -> list:
        """列出已安装 bundle 名（`bm dump -a`，每行一个）。"""
        r = self._hdc.shell("bm", "dump", "-a")
        text = r.stdout or ""
        return [line.strip() for line in text.splitlines() if line.strip()]

    def is_package_installed(self, package: str) -> bool:
        """精确判断 package 是否安装（逐行精确匹配，避免前缀模糊匹配误判）。"""
        return package in self.installed_packages()

    def get_installed_version(self, package: str) -> dict:
        """解析 `bm dump -n <package>` 输出获取整包版本号。

        输出格式是 `"<package>:\\n{...}"`，JSON 内部除顶层 versionCode/
        versionName（整包权威版本）外，热更补丁子结构也带同名字段（未热更
        时恒为 `0`/`""`），且排在顶层字段前面，`re.search` 抓第一个匹配会
        命中假值。改用 json.loads 剥离包名前缀后按 dict 顶层键取值。
        """
        if not self.is_package_installed(package):
            return {"installed": False, "versionName": None, "versionCode": None}
        r = self._hdc.shell("bm", "dump", "-n", package)
        out = r.stdout or ""
        version_name = None
        version_code = None
        data = None
        brace_idx = out.find("{")
        if brace_idx != -1:
            try:
                data = json.loads(out[brace_idx:])
                version_name = data.get("versionName")
                vc = data.get("versionCode")
                version_code = str(vc) if vc is not None else None
            except (json.JSONDecodeError, ValueError):
                data = None
        if version_name is None or version_code is None:
            # JSON 解析失败时的兜底：退回正则扫描，仍可能命中错误的子结构，
            # 但至少不会在解析异常时直接返回空值掩盖问题。
            vn_match = re.search(r'"versionName"\s*:\s*"([^"]*)"', out)
            vc_match = re.search(r'"versionCode"\s*:\s*(\d+)', out)
            version_name = version_name or (vn_match.group(1) if vn_match else None)
            version_code = version_code or (vc_match.group(1) if vc_match else None)

        # 构建类型（debug/release）：位置/命名随系统版本变化 → 递归查找 + 正则兜底；
        # 拿不到时返回 None（不可确认），由 installed_build_kind 归为 UNKNOWN。
        provision_type = _find_first_value(data, {"appProvisionType", "provisionType"}, str)
        debug_flag = _find_first_value(data, {"debug"}, bool)
        if provision_type is None:
            m = re.search(r'"appProvisionType"\s*:\s*"([^"]*)"', out)
            provision_type = m.group(1) if m else None
        if debug_flag is None:
            m = re.search(r'"debug"\s*:\s*(true|false)', out)
            debug_flag = (m.group(1) == "true") if m else None

        return {
            "installed": True,
            "versionName": version_name,
            "versionCode": version_code,
            "provisionType": provision_type,
            "debug": debug_flag,
        }

    def uninstall_app(self, package: str) -> bool:
        if not self.is_package_installed(package):
            return True
        self._hdc.run("uninstall", package)
        return not self.is_package_installed(package)

    def _snapshot_install_step(self, step_name: str) -> None:
        """安装流程关键节点自动截图落盘，供事后诊断；截图失败不影响安装
        流程本身，仅记录警告。"""
        try:
            install_dir = os.path.join(dumps_dir(), "install")
            os.makedirs(install_dir, exist_ok=True)
            path = os.path.join(install_dir, f"{int(time.time() * 1000)}_{step_name}.jpeg")
            if not self.screenshot(path):
                sys.stderr.write(f"[HarmonyOps.install_app] 截图失败（步骤: {step_name}），不影响安装流程\n")
        except Exception as e:
            sys.stderr.write(f"[HarmonyOps.install_app] 截图异常（步骤: {step_name}）: {e}\n")

    def install_app(self, app_path: str, timeout: int = 300) -> bool:
        """安装 App —— 按设备形态 form 选安装通道（与 apk_sources.json 的 real / emulator 一一对应）。

        - emulator（模拟器）：app_path 为可测性(debug) HAP 直链 → 落到设备侧缓存目录后
          `bm install -p`（云模拟器不支持 enterprise Profile，企业安装页会报"下载来源验证
          失败 10002"；设备侧已有同名同大小包时直接复用，省掉 1.4G 重传）
        - real（真机/云真机）：app_path 为 HPX 企业安装页 HTML URL → 打开安装页走系统安装器

        app_path 的形态（.hap 直链 / 企业安装页）与 form 必须匹配，二者由
        apk_sources.json 的 real / emulator 两个子配置分别提供，不会串。
        """
        if not isinstance(app_path, str) or not app_path.startswith(("http://", "https://")):
            raise RuntimeError(
                f"HarmonyOps.install_app 需要 http/https URL，收到: {app_path!r}"
            )
        if self._is_emulator():
            return self._install_hap_via_hdc(app_path, timeout=max(timeout, 600))
        return self._install_via_enterprise_page(app_path, timeout=timeout)

    def _is_emulator(self) -> bool:
        """当前设备是否模拟器形态（form=emulator）；无 AppDescriptor 时按真机处理。"""
        return bool(self._app) and getattr(self._app, "form", "real") == "emulator"

    @property
    def uses_local_artifact(self) -> bool:
        """模拟器走本地制品（HAP → L1 缓存 → 设备侧缓存）；真机**不走**。

        真机/云真机是 HPX 企业安装页通道（`_install_via_enterprise_page`）：下载由设备
        系统安装器完成，字节不经本地，因此 L1 制品缓存不适用（也不该报告“未命中”）。
        """
        return self._is_emulator()

    # 设备侧安装包缓存目录（L2）：只放本 Skill 用过/装过的 hap。
    # 说明：App 的安装路径由系统决定（hdc/bm 都不能指定安装目录），所以“独立目录”
    # 只能用于**缓存安装包**；好处是同一台设备后续占用可直接 `bm install -p <设备侧
    # 路径>`，省掉 1.4G 重传。该目录进 `device_temp_keep_paths`，清理设备临时目录时
    # 会被保留（别人的遗留会被清掉，我们自己的留着）。
    # L1（host 侧、跨 run/跨子 Agent）在 `shared/artifact_cache.py`，两者都以“大小一致
    # 即复用”为判定口径，不需要额外维护映射。
    DEVICE_APK_CACHE_DIR = "/data/local/tmp/ai_ui_autotest_engine"

    @property
    def device_temp_keep_paths(self) -> tuple:
        return (self.DEVICE_APK_CACHE_DIR,)

    def _device_file_size(self, device_path: str):
        out = (self._hdc.shell("stat", "-c", "%s", device_path, timeout=30).stdout or "").strip()
        return int(out) if out.isdigit() else None

    # 设备侧缓存目录内可缓存的安装包后缀（对应 L1 里的 artifact 类型）。
    _CACHE_ARTIFACT_SUFFIXES = (".hap", ".hsp", ".apk")

    def _gc_device_cache_dir(self, keep_name: str) -> None:
        """缓存版本 GC：删掉设备侧缓存目录里**非当前版本**的安装包，只留 keep_name。

        为什么需要：HAP 文件名带版本号（`meituan-<ver>-...hap`），版本一升新文件名就
        匹配不上旧缓存 → 会重新下发 1.4G，而旧版本因 `device_temp_keep_paths` 被永久
        保护、永不删除。若不做 GC，缓存目录会随版本迭代累积 1.4G×N 把设备撑满。
        只动**本设备缓存目录内**安装包后缀的文件，best-effort、不阻断安装。
        """
        try:
            find = self._hdc.shell(
                "find", self.DEVICE_APK_CACHE_DIR, "-maxdepth", "1", "-type", "f", "(",
                "-name", "*.hap", "-o", "-name", "*.hsp", "-o", "-name", "*.apk", ")",
                timeout=30)
            stale = []
            for line in (find.stdout or "").splitlines():
                path = line.strip()
                if not path:
                    continue
                name = path.rsplit("/", 1)[-1]
                if name == keep_name or not name.lower().endswith(self._CACHE_ARTIFACT_SUFFIXES):
                    continue
                stale.append(path)
            for path in stale:
                self._hdc.shell("rm", "-f", path, timeout=30)
            if stale:
                names = ", ".join(p.rsplit("/", 1)[-1] for p in stale)
                sys.stderr.write(
                    f"[HarmonyOps.install_app] 🧽 缓存版本 GC：删除旧版本 {len(stale)} 个（{names}）\n")
        except Exception as e:  # noqa: BLE001 —— GC 失败不影响安装主流程
            sys.stderr.write(f"[HarmonyOps.install_app] 缓存版本 GC 失败（忽略）: {e}\n")

    def _install_hap_via_hdc(self, hap_url: str, timeout: int = 600) -> bool:
        """模拟器通道：L1 制品缓存 ⇒ 设备侧缓存目录 ⇒ `bm install -p <设备侧路径>`。

        两级缓存各解一件事（分层模型见 `shared/artifact_cache.py`）：
          · **L1（host，跨 run / 跨子 Agent 共享）**：命中则免去 1.4G 重下；
            并发 install 由制品锁串行化，只会下载一次。
          · **L2（本设备，`DEVICE_APK_CACHE_DIR`）**：命中则免去 host→device 重传；
            判定基准是 L1 本地文件的**确切大小**，不再额外探测远端。写入前先做
            **版本 GC**（`_gc_device_cache_dir`），删掉旧版本安装包，防止缓存目录
            随版本迭代累积 1.4G×N。
        安装是否成功仍由调用方 verify_install 通过 bm dump 复核。
        """
        from shared import artifact_cache

        scope = artifact_cache.scope_of(self._app)
        local_path = artifact_cache.resolve(hap_url, scope, label=scope)
        local_size = os.path.getsize(local_path)
        remote_path = f"{self.DEVICE_APK_CACHE_DIR}/{os.path.basename(local_path)}"
        self._hdc.shell("mkdir", "-p", self.DEVICE_APK_CACHE_DIR, timeout=30)
        # 先把缓存目录里**旧版本**的安装包清掉，避免 1.4G×N 随版本迭代累积
        self._gc_device_cache_dir(os.path.basename(local_path))

        device_size = self._device_file_size(remote_path)
        if device_size == local_size:
            sys.stderr.write(
                f"[HarmonyOps.install_app] ✅ 命中设备侧缓存: {remote_path}"
                f"（{device_size // 1024 // 1024}MB），跳过重传\n")
        else:
            if device_size is not None:
                sys.stderr.write("[HarmonyOps.install_app] 设备侧缓存不完整/不一致，重新下发\n")
            sys.stderr.write(
                f"[HarmonyOps.install_app] 下发 HAP 到设备缓存目录: {local_path} -> {remote_path}"
                f"（约 {local_size // 1024 // 1024}MB）...\n")
            sent = self._hdc.run("file", "send", local_path, remote_path, timeout=timeout)
            if sent.returncode != 0:
                out = ((sent.stdout or "") + (sent.stderr or "")).strip()
                raise RuntimeError(
                    f"hdc file send 失败: {out[:300] or f'returncode={sent.returncode}'}")

        sys.stderr.write(f"[HarmonyOps.install_app] bm install -p {remote_path} ...\n")
        attempts = [("bm install", ["bm", "install", "-p", remote_path]),
                    ("bm install -r", ["bm", "install", "-r", "-p", remote_path])]
        last_err = ""
        for label, argv in attempts:
            r = self._hdc.shell(*argv, timeout=timeout)
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0 and "install bundle successfully" in out:
                return True
            last_err = f"{label}: {out.strip()[:200] or f'returncode={r.returncode}'}"
            sys.stderr.write(f"[HarmonyOps.install_app] {label} 未成功：{last_err}\n")

        raise RuntimeError(f"安装失败（{last_err}）")

    def _install_via_enterprise_page(self, app_path: str, timeout: int = 300) -> bool:
        """真机/云真机通道：通过企业安装页触发安装（见模块顶部选型说明），
        app_path 须为 HPX 生成的企业安装页 HTML URL。

        流程：打开安装页 → 点击下载链接 → 校验来源后点击安装确认 → 按 Home
        回桌面。回到桌面后即返回，不轮询安装结果——安装是异步的、无前台
        进度可观察，最终是否成功由调用方（verify_install）通过 bm dump
        轮询确认，任何一步操作失败均抛出异常。
        """
        # 重试容错：上一次调用可能已把确认弹窗打开但在点击前失败退出，
        # 先探测弹窗是否已存在，命中则跳过"打开页面→点下载"两步。
        dialog_node = _find_node_by_id(_dump_ui_nodes(self._hdc), _INSTALL_DIALOG_CONFIRM_BUTTON_ID)
        if dialog_node is not None:
            self._snapshot_install_step("00_resume_from_existing_dialog")
        else:
            r = self._hdc.shell(
                "aa", "start", "-A", "ohos.want.action.viewData",
                "-U", app_path, "-e", "type", "text/html", timeout=15,
            )
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode != 0 or "error:" in out.lower():
                raise RuntimeError(f"打开企业安装页失败: {out.strip() or f'returncode={r.returncode}'}")
            self._snapshot_install_step("01_page_opened")

            download_node = _poll_for_node(
                self._hdc,
                lambda nodes: _find_node_by_text(nodes, _ENTERPRISE_PAGE_DOWNLOAD_TEXT),
                timeout_sec=20,
            )
            if download_node is None:
                self._snapshot_install_step("02_download_link_not_found")
                raise RuntimeError(
                    f"企业安装页未找到「{_ENTERPRISE_PAGE_DOWNLOAD_TEXT}」链接（页面渲染超时或页面结构变化）"
                )
            center = _center_of_node(download_node)
            if center is None or not self.tap(*center):
                raise RuntimeError("点击企业安装页「点击下载」链接失败")
            self._snapshot_install_step("02_download_clicked")

            dialog_node = _poll_for_node(
                self._hdc,
                lambda nodes: _find_node_by_id(nodes, _INSTALL_DIALOG_CONFIRM_BUTTON_ID),
                timeout_sec=20,
            )
            if dialog_node is None:
                self._snapshot_install_step("03_confirm_dialog_not_found")
                raise RuntimeError("点击下载后未出现系统安装确认弹窗（可能被 USB 连接方式等其他弹窗遮挡，或下载触发失败）")
            self._snapshot_install_step("03_confirm_dialog_shown")

        # 域名校验：安装弹窗文案含来源域名（如 "'hyperloop-s3.sankuai.com'
        # 想要安装 'meituan'"），必须命中可信域名列表才继续点击安装，
        # 防止企业安装页 URL 被篡改后静默安装未知来源应用。
        dialog_nodes = _dump_ui_nodes(self._hdc)
        dialog_text = " ".join((n.get("text") or "") for n in dialog_nodes)
        expected_host = urlparse(app_path).netloc
        trusted_hosts = set(_TRUSTED_INSTALL_SOURCE_HOSTS) | ({expected_host} if expected_host else set())
        if not any(host in dialog_text for host in trusted_hosts):
            self._snapshot_install_step("04_host_check_failed")
            raise RuntimeError(
                f"系统安装确认弹窗来源域名校验失败（弹窗文案未包含可信域名 {sorted(trusted_hosts)}），"
                f"疑似安装页被篡改，已终止安装。弹窗文案: {dialog_text[:200]!r}"
            )

        confirm_center = _center_of_node(dialog_node)
        if confirm_center is None or not self.tap(*confirm_center):
            raise RuntimeError("点击系统安装确认弹窗「安装」按钮失败")
        self._snapshot_install_step("05_install_confirmed")

        # 点击"安装"后必须主动按 Home 回到桌面（真机实测：不回桌面不会触发
        # 后台下载），失败也不应阻断后续 verify_install 轮询，只记录日志。
        if not self.press_home():
            sys.stderr.write("[HarmonyOps.install_app] 安装后按 Home 回桌面失败，可能影响后台下载触发\n")
        time.sleep(1)
        self._snapshot_install_step("06_back_to_home")
        return True

    # ═══════════════════════════════════════════════════════════
    # 环境配置
    # ═══════════════════════════════════════════════════════════

    def setup_keyboard(self) -> bool:
        """鸿蒙无 ADBKeyboard 等价机制，本方法不应被调用
        （needs_keyboard_setup 在本地/鸿蒙场景恒为 False）。"""
        return False

    # ═══════════════════════════════════════════════════════════
    # 状态查询
    # ═══════════════════════════════════════════════════════════

    def check_foreground(self) -> str:
        """探测当前前台 bundle name。

        不采用 hidumper AbilityManagerService 的 mission 状态解析（设备停留
        在桌面或被拦截弹窗挡住时都返回空，无法区分），改为读取 uitest
        dumpLayout 输出树的顶层子节点：每个节点自带 bundleName 属性，取
        focused=true 的顶层节点，找不到则返回空。
        """
        try:
            raw = _harmony_inspect_tree(self._serial, bundle_name=None, timeout=15, remote=self._remote)
        except Exception:
            return ""
        for child in raw.get("children") or []:
            attrs = child.get("attributes") or {}
            bundle_name = attrs.get("bundleName")
            if bundle_name and attrs.get("focused") == "true":
                return f"app state #foreground bundle name [{bundle_name.lower()}]"
        return ""

    def screen_size(self) -> tuple:
        r = self._hdc.shell("hidumper", "-s", "WindowManagerService", "-a", "-a")
        m = re.search(r'\((\d+(?:\.\d+)?),\s*(\d+(?:\.\d+)?)\)\s*-\s*\[(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\]', r.stdout or "")
        if m:
            return int(float(m.group(3))), int(float(m.group(4)))
        return (1260, 2720)

    def viewport_insets(self) -> dict:
        """从 hidumper 获取鸿蒙 safe area insets。
        
        解析 WindowManagerService 的 displaySafeArea 信息，
        失败时返回空 dict，由 ScreenLayout 兜底为类属性默认值。
        """
        try:
            r = self._hdc.shell("hidumper", "-s", "WindowManagerService", "-a", "-a")
            out = (r.stdout or "") if r else ""
            top = bottom = 0
            # 尝试解析 safeArea / displaySafeArea 信息
            m = re.search(r'(?:safeArea|displaySafeArea|safe_insets).*?top[=:]\s*(\d+)', out, re.IGNORECASE)
            if m:
                top = int(m.group(1))
            m = re.search(r'(?:safeArea|displaySafeArea|safe_insets).*?bottom[=:]\s*(\d+)', out, re.IGNORECASE)
            if m:
                bottom = int(m.group(1))
            if top == 0 and bottom == 0:
                # 兜底：鸿蒙典型状态栏 ~90px，手势条 ~60px
                return {"top": 90, "bottom": 60, "left": 0, "right": 0}
            return {"top": top, "bottom": bottom, "left": 0, "right": 0}
        except Exception:
            return {"top": 90, "bottom": 60, "left": 0, "right": 0}

    def device_alive(self) -> bool:
        r = self._hdc.shell("echo", "alive", timeout=10)
        return r.returncode == 0 and "alive" in (r.stdout or "")

    def screen_state(self) -> str:
        """hidumper PowerManagerService 解析 "Current State: XXX" 字段。

        不复用 imeituan CLI 的 `device wake`——CLI 转发单次开销远高于直连
        hdc（Node 进程冷启动 + session 解析）。
        """
        r = self._hdc.shell("hidumper", "-s", "PowerManagerService", "-a", "-s")
        if r.returncode != 0:
            return "UNKNOWN"
        m = re.search(r'^Current State:\s*([A-Z_]+)\b', r.stdout or "", re.MULTILINE)
        return m.group(1) if m else "UNKNOWN"

    def is_screen_interactive(self) -> bool:
        """判断当前电源状态是否允许 UI 自动化继续执行。

        不复用 imeituan CLI 内部的 SLEEPING_STATES={SLEEP,DOZE}——HarmonyOS
        电源状态机比 Android 丰富，SHUTDOWN/HIBERNATE/STAND_BY/INACTIVE
        同样意味着当前显示层不是目标 App 窗口，需单独归类为不可交互。
        """
        state = self.screen_state()
        if state == "UNKNOWN":
            return True
        return state not in _HARMONY_NON_INTERACTIVE_STATES

    def pidof(self, package: str) -> str:
        r = self._hdc.shell("pidof", package)
        return (r.stdout or "").strip()

    # ═══════════════════════════════════════════════════════════
    # 文本输入语义操作
    # ═══════════════════════════════════════════════════════════

    def clear_text(self, x: int, y: int, max_del: int = 20) -> bool:
        """清空输入框：tap 聚焦 → 按 Delete 逐字删除。

        HarmonyOS 的 uitest uiInput keyEvent 接受 "Delete" 等按键名，
        不需要 Android 的 KEYCODE_MOVE_END 前缀。
        """
        self.tap(x, y)
        time.sleep(0.4)
        self.keyevent(*(["Delete"] * max_del))
        return True

    def supports_cjk_input(self) -> bool:
        """HarmonyOS 的 uitest uiInput inputText 原生支持 CJK。"""
        return True

    # ═══════════════════════════════════════════════════════════
    # 结构化设备命令（Android 专属机制，鸿蒙无等价物，不强行模拟）
    # ═══════════════════════════════════════════════════════════

    def broadcast(self, action: str, **extras) -> bool:
        return False

    def content_call(self, uri: str, method: str, *args) -> tuple:
        return False, "HarmonyOS 无 ContentProvider 机制，不支持 content_call"

    def keyevent(self, *keycodes) -> bool:
        ok = True
        for code in keycodes:
            r = self._hdc.shell("uitest", "uiInput", "keyEvent", str(code))
            ok = ok and r.returncode == 0
        return ok

    def get_setting(self, namespace: str, key: str) -> str:
        return ""

    def clear_app_data(self, package: str) -> bool:
        """清除 App 数据：`bm clean -n <pkg> -d`（先 force-stop，App 运行中清不干净）。

        ⚠️ 实测：清数据会**重置**该 App 的 user_grant 权限状态
        （清前 `grantStatus:0` → 清后 `-1`）；因此调用方必须遵守
        「清数据 → 预授权 → 启动」的顺序 —— 顺序互换会让刚授的权限被清掉。
        `_cold_restart_app` 的 `clear → grant → stop → launch` 恰好满足。
        """
        self.force_stop(package)
        time.sleep(1)
        r = self._hdc.shell("bm", "clean", "-n", package, "-d", timeout=30)
        out = f"{r.stdout or ''}{r.stderr or ''}"
        ok = "clean bundle data files successfully" in out
        if not ok:
            sys.stderr.write(
                f"[harmony:clear_app_data] 清数据失败: rc={r.returncode} out={out.strip()[:200]}\n")
        return ok

    def grant_permissions(self, package: str, permissions: list[str]) -> list[bool]:
        """预授予权限：`atm perm -g -i <tokenId> -p <permission>`。

        两个鸿蒙特有约束（均为实测结论）：
          1. **仅 debug hap 的 token 可被修改**（`atm perm` 帮助原文
             "only debug hap tokens can be modified"）→ release 包必然失败；
          2. **tokenId 必须动态解析**（重装/升级会变），禁止硬编码。
        """
        if not permissions:
            return []
        token_id = self._resolve_token_id(package)
        if not token_id:
            sys.stderr.write(
                f"[harmony:grant_permissions] 未取到 {package} 的 tokenID，跳过预授权\n")
            return [False] * len(permissions)

        results = []
        for perm in permissions:
            r = self._hdc.shell("atm", "perm", "-g", "-i", token_id, "-p", perm, timeout=30)
            out = f"{r.stdout or ''}{r.stderr or ''}".strip()
            ok = "Success" in out
            if not ok:
                sys.stderr.write(
                    f"[harmony:grant_permissions] {perm} 授权失败: rc={r.returncode} {out[:160]}\n")
            results.append(ok)
        print(f"[harmony:grant_permissions] tokenId={token_id} "
              f"授权 {sum(1 for x in results if x)}/{len(permissions)} 条")
        return results

    def _resolve_token_id(self, package: str) -> str:
        """从 `atm dump -t -b <pkg>` 输出解析 tokenID（**动态取，勿硬编码**）。"""
        r = self._hdc.shell("atm", "dump", "-t", "-b", package, timeout=30)
        m = re.search(r'"tokenID"\s*:\s*(\d+)', f"{r.stdout or ''}{r.stderr or ''}")
        return m.group(1) if m else ""

    @property
    def can_verify_appmock_state(self) -> bool:
        """鸿蒙没有设备端 AppMock 状态查询通道 ⇒ 恒不可确认。

        该能力位决定「清数据 + 预授权」的执行落点（见
        `provisioning/setup/login/steps.py::EnableAppMock`）：不可确认的平台
        必须在该分支内完成数据/权限准备，否则权限准备不会被执行。
        """
        return False

    @property
    def default_permissions_to_grant(self) -> list[str]:
        """鸿蒙默认预授予权限（对等 Android 的「精确定位 + 粗略定位」）。

        通知在鸿蒙不是 user_grant 权限（属系统设置项，由用户在设置里开），故不列入。
        """
        return [
            "ohos.permission.LOCATION",                 # 精确定位
            "ohos.permission.APPROXIMATELY_LOCATION",   # 粗略定位
        ]

    # ═══════════════════════════════════════════════════════════
    # 逃逸通道
    # ═══════════════════════════════════════════════════════════

    def shell(self, *args) -> subprocess.CompletedProcess:
        return self._hdc.shell(*args)

    def disconnect(self) -> bool:
        return True


# 模块级契约成员（见 devices/registry.py::_REQUIRED_MODULE_ATTRS）：
# 供 context.create_platform_ops 统一按 (serial, app_descriptor) 构造，
# 不需要在调用方手写 if platform == "harmony" 分支。
PlatformOpsClass = HarmonyOps
