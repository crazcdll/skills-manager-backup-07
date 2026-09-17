#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HarmonyOps —— HarmonyOS 平台 PlatformOps 实现。

直接拼接 `hdc -t <serial> shell <cmd>`，不经过 imeituan CLI 的 device
shell/input/open-url 封装：CLI 的 open-url --package-id 在鸿蒙分支未生效，
必然触发多包消歧弹窗；imeituan-cli 的 `control inspect-tree` 内置正则
不兼容该系统版本的 hidumper 输出格式。鸿蒙全部走本文件直拼 hdc 命令，
inspect_tree 复用 uitest dumpLayout（详见 platform/harmony/probes/
inspect_tree.py 与 node_adapter.py）。

broadcast/content_call 是 Android ContentProvider/intent broadcast 专属
机制，鸿蒙无等价物，不强行模拟，直接返回 False。

安装机制选型：`hdc install <本地.hap>` 对企业签名包有较高概率因签名校验
失败，HarmonyOS 对企业分发应用只认可「通过系统浏览器打开 HPX 生成的企业
安装页、触发系统级安装器」这一种安装方式。完整链路：打开安装页 → 点击
"点击下载"链接 → 校验来源域名后点击系统安装确认弹窗 → 按 Home 回桌面
（真机实测：停留在浏览器/弹窗界面时系统不会触发后台下载安装）。回到桌面
后安装在后台静默完成，无前台进度可观察，最终是否成功由调用方
（infra/app_installer.py::verify_install）轮询 `bm dump` 版本号确认，本
模块的 install_app 只负责触发安装动作。
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time
from urllib.parse import urlparse

from core.util.json_utils import write_json_atomic, read_json
from device_platform.base import PlatformOps, AppDescriptor, LocalDeviceProbeError
from device_platform.harmony.probes.inspect_tree import inspect_tree as _harmony_inspect_tree
from device_platform.harmony.probes.node_adapter import parse_tree as _harmony_parse_tree
# 统一命名对外导出，供 context.get_probes()/screen_state.inspect_tree 的工厂
# 分发缓存引用（与 platform/android/probes/node_adapter.py 的 parse_tree
# 同名，调用方按 platform 分发到本模块后无需关心具体导出名）。
parse_tree = _harmony_parse_tree
from device_platform.harmony.hdc import ensure_hdc
from core.util.paths import DUMPS_DIR

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

_hdc_bin_cache = None


def _hdc_bin() -> str:
    """惰性解析 hdc 可执行文件路径，并确保其所在目录已 prepend 到当前进程 PATH。

    非交互式子进程不会加载 ~/.zshrc，不能假设 shell 配置已生效，故每次
    实际调用前显式确保一次（ensure_hdc 内部已在 PATH 时是快速返回）。
    """
    global _hdc_bin_cache
    if _hdc_bin_cache is None:
        hdc_path, _ = ensure_hdc(install=False) or (None, None)
        _hdc_bin_cache = hdc_path or "hdc"
    return _hdc_bin_cache


def _hdc(serial: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """执行 hdc -t <serial> <args...>，返回 CompletedProcess。"""
    cmd = [_hdc_bin(), "-t", serial, *args]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr=f"TIMEOUT after {timeout}s")


def _hdc_shell(serial: str, *shell_args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """执行 hdc -t <serial> shell <shell_args...>。

    多参数形式会被拼接为一整条命令字符串转发给设备端 shell 解析——若参数值
    含 shell 元字符（scheme URL 常见的 `&`/`?`），会被误解析（如 `&` 被当作
    后台执行分隔符导致 URL 被截断）。对每个参数做 POSIX shell 转义
    （shlex.quote）后拼接，确保设备端 shell 把每个参数值当作单一字面量解析。
    """
    shell_cmd = " ".join(shlex.quote(a) for a in shell_args)
    return _hdc(serial, "shell", shell_cmd, timeout=timeout)


def _dump_ui_nodes(serial: str, timeout: int = 30) -> list:
    """采集当前前台内容（不限定 bundle_name）的 uitest dumpLayout，解析为
    UiNode 列表。企业安装页/系统安装弹窗均非目标 App 窗口，不能按
    AppDescriptor.package_name 过滤，因此不复用 HarmonyOps.inspect_tree()
    （其固定按目标 App bundle_name 过滤）。
    """
    raw = _harmony_inspect_tree(serial, bundle_name=None, timeout=timeout)
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


def _poll_for_node(serial: str, finder, *, timeout_sec: float = 20, interval_sec: float = 1.5):
    """轮询 dumpLayout 直到 finder(nodes) 返回非 None 节点，或超时返回 None。

    企业安装页的下载链接渲染、系统安装弹窗的弹出都存在网络/系统调度延迟，
    单次采集可能落在渲染完成之前，需要轮询而非一次性采集判定失败。
    """
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            nodes = _dump_ui_nodes(serial)
        except Exception:
            nodes = []
        hit = finder(nodes)
        if hit is not None:
            return hit
        time.sleep(interval_sec)
    return None


# 全新安装后是否存在系统级强制拦截，命中 device_guidance.GUIDANCE_REGISTRY 的
# key；HarmonyOS 企业签名应用首次启动会被信任校验拦截，Android 无此问题（其
# ops.py 中同名常量为 None）。供 device_lifecycle.py::cmd_setup 在
# fresh_install 后据此判断是否提前终止并展示引导，取代硬编码的 platform 判断。
FRESH_INSTALL_GUIDANCE_ID = "harmony_local_untrusted_app"

# App 版本探测/安装动作幂等重试上限。HarmonyOS 走「打开企业安装页 + 点击
# 下载 + 点击系统安装确认」的 UI 自动化安装流程，安装包由系统在后台下载，
# 功能测试包体积明显大于 Android APK，全流程耗时更长，重试上限相应放宽
# （Android 对称常量见 platform/android/ops.py::INSTALL_VERIFY_RETRIES=24）。
INSTALL_VERIFY_RETRIES = 40


def register_device(serial: str, device_type: str = "sandbox") -> dict:
    """注册设备到 imeituan CLI session，返回 {ok, session_id, detail}。

    鸿蒙当前仅支持本地真机（device_type=local），统一走 `device connect
    --target local-device` 本地直连入口，跳过网络连接探测。
    sandbox 云模拟器仅 Android 可用，device_type 参数保留为架构一致性
    （与 platform/android/ops.py::register_device 对称，供未来扩展）。
    """
    from infra.imeituan_cli import imeituan_connect_local_device
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
    from device_platform.harmony.probes.native import NativeProbe
    return [NativeProbe()]


def ensure_toolchain() -> bool:
    """确保鸿蒙连接工具链（hdc）就绪。

    HarmonyOps 全部走 hdc 直连，不经过 adb，因此 setup 阶段不需要
    device_lifecycle.py 里 Android 专属的 ensure_adb() 前置检查；
    真正的 hdc 就绪检查已在 probe_local_devices() 内完成。
    """
    return True


def probe_local_devices() -> str:
    """探测唯一在线的本地鸿蒙真机，返回其 serial。

    供 device_platform.lifecycle.local.LocalDeviceLifecycle.acquire() 调用，
    是 device_type=local + platform=harmony 组合的设备发现入口。

    连接探测只反映 USB 调试授权是否就绪，不代表屏幕可交互：hdc shell
    通道不受屏幕状态影响，锁屏/熄屏时探测依然会成功，因此额外做一次
    屏幕可交互性检查，避免流程推进到 UI 步骤才报错。

    Raises:
        LocalDeviceProbeError: 未探测到设备 / 探测到多台设备 /
            工具链不可用 / 屏幕处于不可交互状态。
    """
    from device_platform.harmony.hdc import ensure_hdc, list_targets

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

    def __init__(self, device_serial: str, app_descriptor: AppDescriptor = None):
        self._serial = device_serial
        self._app = app_descriptor

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

    def inspect_tree(self, output_path: str, *, timeout: int = 30) -> subprocess.CompletedProcess:
        """采集视图树，落盘为 uitest dumpLayout 原始 JSON（未做结构改写）。

        落盘内容直接是 {"attributes": {...}, "children": [...]}，供
        screen_state.inspect_tree.parse_inspect_tree() 读取后分派给
        device_platform.harmony.probes.node_adapter.parse_tree() 解析，与
        Android 侧落盘 imeituan inspect-tree 原始 JSON 的约定一致
        （调用方按平台分派 adapter，不关心落盘格式差异）。
        """
        bundle_name = self._app.package_name if self._app is not None else None
        try:
            result = _harmony_inspect_tree(self._serial, bundle_name=bundle_name, timeout=timeout)
        except Exception as e:
            return subprocess.CompletedProcess(args=["inspect_tree", self._serial], returncode=1, stdout="", stderr=str(e))
        write_json_atomic(output_path, result)
        return subprocess.CompletedProcess(args=["inspect_tree", self._serial], returncode=0, stdout="", stderr="")

    # ═══════════════════════════════════════════════════════════
    # 交互原语
    # ═══════════════════════════════════════════════════════════

    def tap(self, x: int, y: int) -> bool:
        r = _hdc_shell(self._serial, "uitest", "uiInput", "click", str(x), str(y))
        return r.returncode == 0

    def swipe(self, from_x: int, from_y: int, to_x: int, to_y: int,
              duration_ms: int = 500) -> bool:
        r = _hdc_shell(self._serial, "uitest", "uiInput", "swipe",
                       str(from_x), str(from_y), str(to_x), str(to_y), str(duration_ms))
        return r.returncode == 0

    def input_text(self, text: str) -> bool:
        r = _hdc_shell(self._serial, "uitest", "uiInput", "inputText", "0", "0", text)
        return r.returncode == 0

    def press_back(self) -> bool:
        return self.keyevent("Back")

    def press_home(self) -> bool:
        return self.keyevent("Home")

    def screenshot(self, path: str) -> bool:
        device_path = "/data/local/tmp/_ai_ui_autotest_engine_shot.jpeg"
        r = _hdc_shell(self._serial, "snapshot_display", "-f", device_path)
        if r.returncode != 0:
            return False
        r = _hdc(self._serial, "file", "recv", device_path, path)
        return r.returncode == 0

    # ═══════════════════════════════════════════════════════════
    # App 管理
    # ═══════════════════════════════════════════════════════════

    def launch_app(self, component: str, *, launcher_intent: bool = False) -> bool:
        """启动 App。component 沿用 AppDescriptor.main_activity 的 "bundle/ability" 格式。"""
        bundle, _, ability = component.partition("/")
        if not ability:
            ability = "EntryAbility"
        r = _hdc_shell(self._serial, "aa", "start", "-b", bundle, "-a", ability)
        return r.returncode == 0

    def force_stop(self, package: str) -> bool:
        r = _hdc_shell(self._serial, "aa", "force-stop", package)
        return r.returncode == 0

    def launch_scheme(self, scheme_url: str) -> bool:
        """推送 scheme URL。必须用 -A action.system.home -U 组合，不能用 -a <ability>，
        否则会变成显式启动导致 URI 被忽略；不能省略 -b，否则触发多包消歧弹窗。
        """
        bundle = self._bundle_name()
        r = _hdc_shell(self._serial, "aa", "start", "-b", bundle,
                       "-A", "action.system.home", "-U", scheme_url)
        return r.returncode == 0

    def open_url(self, url: str) -> bool:
        return self.launch_scheme(url)

    # ═══════════════════════════════════════════════════════════
    # App 生命周期管理
    # ═══════════════════════════════════════════════════════════

    def is_package_installed(self, package: str) -> bool:
        r = _hdc_shell(self._serial, "bm", "dump", "-a")
        text = r.stdout or ""
        return any(line.strip() == package for line in text.splitlines())

    def get_installed_version(self, package: str) -> dict:
        """解析 `bm dump -n <package>` 输出获取整包版本号。

        输出格式是 `"<package>:\\n{...}"`，JSON 内部除顶层 versionCode/
        versionName（整包权威版本）外，热更补丁子结构也带同名字段（未热更
        时恒为 `0`/`""`），且排在顶层字段前面，`re.search` 抓第一个匹配会
        命中假值。改用 json.loads 剥离包名前缀后按 dict 顶层键取值。
        """
        if not self.is_package_installed(package):
            return {"installed": False, "versionName": None, "versionCode": None}
        r = _hdc_shell(self._serial, "bm", "dump", "-n", package)
        out = r.stdout or ""
        version_name = None
        version_code = None
        brace_idx = out.find("{")
        if brace_idx != -1:
            try:
                data = json.loads(out[brace_idx:])
                version_name = data.get("versionName")
                vc = data.get("versionCode")
                version_code = str(vc) if vc is not None else None
            except (json.JSONDecodeError, ValueError):
                pass
        if version_name is None or version_code is None:
            # JSON 解析失败时的兜底：退回正则扫描，仍可能命中错误的子结构，
            # 但至少不会在解析异常时直接返回空值掩盖问题。
            vn_match = re.search(r'"versionName"\s*:\s*"([^"]*)"', out)
            vc_match = re.search(r'"versionCode"\s*:\s*(\d+)', out)
            version_name = version_name or (vn_match.group(1) if vn_match else None)
            version_code = version_code or (vc_match.group(1) if vc_match else None)
        return {"installed": True, "versionName": version_name, "versionCode": version_code}

    def uninstall_app(self, package: str) -> bool:
        if not self.is_package_installed(package):
            return True
        _hdc(self._serial, "uninstall", package)
        return not self.is_package_installed(package)

    def _snapshot_install_step(self, step_name: str) -> None:
        """安装流程关键节点自动截图落盘，供事后诊断；截图失败不影响安装
        流程本身，仅记录警告。"""
        try:
            install_dir = os.path.join(DUMPS_DIR, "install")
            os.makedirs(install_dir, exist_ok=True)
            path = os.path.join(install_dir, f"{int(time.time() * 1000)}_{step_name}.jpeg")
            if not self.screenshot(path):
                sys.stderr.write(f"[HarmonyOps.install_app] 截图失败（步骤: {step_name}），不影响安装流程\n")
        except Exception as e:
            sys.stderr.write(f"[HarmonyOps.install_app] 截图异常（步骤: {step_name}）: {e}\n")

    def install_app(self, app_path: str, timeout: int = 300) -> bool:
        """通过企业安装页触发安装（见模块顶部选型说明），app_path 须为 HPX
        生成的企业安装页 HTML URL，不支持传入本地 .hap 路径走 `hdc install`。

        流程：打开安装页 → 点击下载链接 → 校验来源后点击安装确认 → 按 Home
        回桌面。回到桌面后即返回，不轮询安装结果——安装是异步的、无前台
        进度可观察，最终是否成功由调用方（verify_install）通过 bm dump
        轮询确认，任何一步操作失败均抛出异常。
        """
        if not isinstance(app_path, str) or not app_path.startswith(("http://", "https://")):
            raise RuntimeError(
                f"HarmonyOps.install_app 需要企业安装页 URL（http/https），收到: {app_path!r}"
            )

        # 重试容错：上一次调用可能已把确认弹窗打开但在点击前失败退出，
        # 先探测弹窗是否已存在，命中则跳过"打开页面→点下载"两步。
        dialog_node = _find_node_by_id(_dump_ui_nodes(self._serial), _INSTALL_DIALOG_CONFIRM_BUTTON_ID)
        if dialog_node is not None:
            self._snapshot_install_step("00_resume_from_existing_dialog")
        else:
            r = _hdc_shell(
                self._serial, "aa", "start", "-A", "ohos.want.action.viewData",
                "-U", app_path, "-e", "type", "text/html", timeout=15,
            )
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode != 0 or "error:" in out.lower():
                raise RuntimeError(f"打开企业安装页失败: {out.strip() or f'returncode={r.returncode}'}")
            self._snapshot_install_step("01_page_opened")

            download_node = _poll_for_node(
                self._serial,
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
                self._serial,
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
        dialog_nodes = _dump_ui_nodes(self._serial)
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
            raw = _harmony_inspect_tree(self._serial, bundle_name=None, timeout=15)
        except Exception:
            return ""
        for child in raw.get("children") or []:
            attrs = child.get("attributes") or {}
            bundle_name = attrs.get("bundleName")
            if bundle_name and attrs.get("focused") == "true":
                return f"app state #foreground bundle name [{bundle_name.lower()}]"
        return ""

    def screen_size(self) -> tuple:
        r = _hdc_shell(self._serial, "hidumper", "-s", "WindowManagerService", "-a", "-a")
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
            r = _hdc_shell(self._serial, "hidumper", "-s", "WindowManagerService", "-a", "-a")
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
        r = _hdc_shell(self._serial, "echo", "alive", timeout=10)
        return r.returncode == 0 and "alive" in (r.stdout or "")

    def screen_state(self) -> str:
        """hidumper PowerManagerService 解析 "Current State: XXX" 字段。

        不复用 imeituan CLI 的 `device wake`——CLI 转发单次开销远高于直连
        hdc（Node 进程冷启动 + session 解析）。
        """
        r = _hdc_shell(self._serial, "hidumper", "-s", "PowerManagerService", "-a", "-s")
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
        r = _hdc_shell(self._serial, "pidof", package)
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
            r = _hdc_shell(self._serial, "uitest", "uiInput", "keyEvent", str(code))
            ok = ok and r.returncode == 0
        return ok

    def get_setting(self, namespace: str, key: str) -> str:
        return ""

    def clear_app_data(self, package: str) -> bool:
        """HarmonyOS 暂不支持清除 App 数据。"""
        return False

    def grant_permissions(self, package: str, permissions: list[str]) -> list[bool]:
        """HarmonyOS 暂不支持预授予权限。"""
        return [False] * len(permissions)

    # ═══════════════════════════════════════════════════════════
    # 逃逸通道
    # ═══════════════════════════════════════════════════════════

    def shell(self, *args) -> subprocess.CompletedProcess:
        return _hdc_shell(self._serial, *args)

    def disconnect(self) -> bool:
        return True


# 模块级契约成员（见 platform/registry.py::_REQUIRED_MODULE_ATTRS）：
# 供 context.create_platform_ops 统一按 (serial, app_descriptor) 构造，
# 不需要在调用方手写 if platform == "harmony" 分支。
PlatformOpsClass = HarmonyOps
