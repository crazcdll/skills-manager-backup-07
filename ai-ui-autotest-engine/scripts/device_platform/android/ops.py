#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AndroidOps — Android 平台 PlatformOps 实现。

委托 infra/imeituan_cli.py（跨平台通用 CLI 封装）函数执行设备操作：
  - 所有调用通过 imeituan CLI → AdbAdapter 透明转发
  - 诊断日志（UI_AUTOTEST_DIAG_LOG）和超时处理由 imeituan_cli 负责
"""
import json
import os
import re
import subprocess
import sys
import time

from core.util.json_utils import write_json_atomic, read_json
from device_platform.base import PlatformOps, AppDescriptor, LocalDeviceProbeError
from core.util.paths import SKILL_DIR, REFERENCES_DIR
from device_platform.android.probes.node_adapter import parse_tree
from infra.imeituan_cli import (
    imeituan_shell,
    imeituan_input,
    imeituan_open_url,
    imeituan_install,
    imeituan_exec,
    imeituan_screen_size as _device_screen_size,
    imeituan_alive as _device_alive,
    imeituan_screenshot as _device_screenshot,
    imeituan_inspect_tree as _device_inspect_tree,
    imeituan_disconnect_device,
)
from device_platform.android.probes.uiautomator_adapter import parse_uiautomator_xml


# Android 运行时权限列表（预授予，避免弹窗干扰登录流程）
DEFAULT_PERMISSIONS_TO_GRANT = [
    "android.permission.POST_NOTIFICATIONS",      # 通知（Android 13+）
    "android.permission.ACCESS_FINE_LOCATION",    # 精确定位
    "android.permission.ACCESS_COARSE_LOCATION",  # 粗略定位
]


def _uiautomator_inspect_tree(output_path: str) -> subprocess.CompletedProcess:
    """通过 uiautomator dump 获取视图树（imeituan CLI 无此命令，走 device shell 间接调用）。"""
    sys.stderr.write("[uiautomator] 开始 dump...\n")
    r1 = imeituan_shell("uiautomator", "dump", "/data/local/tmp/_ui.xml", timeout=15)
    sys.stderr.write(f"[uiautomator] dump 完成: rc={r1.returncode}, stderr={r1.stderr[:200]!r}, stdout={r1.stdout[:200]!r}\n")
    if r1.returncode != 0:
        return subprocess.CompletedProcess(args=[], returncode=1,
            stderr=f"uiautomator dump failed: {r1.stderr}".encode())

    r2 = imeituan_shell("cat", "/data/local/tmp/_ui.xml", timeout=10)
    sys.stderr.write(f"[uiautomator] cat 完成: rc={r2.returncode}, stdout_len={len(r2.stdout or '')}\n")
    if r2.returncode != 0:
        return subprocess.CompletedProcess(args=[], returncode=1,
            stderr=f"uiautomator cat failed: {r2.stderr}".encode())

    xml_start = (r2.stdout or "").find("<?xml")
    if xml_start < 0:
        return subprocess.CompletedProcess(args=[], returncode=1,
            stderr="uiautomator: no XML content".encode())

    tree = parse_uiautomator_xml(r2.stdout[xml_start:])
    if not tree:
        return subprocess.CompletedProcess(args=[], returncode=1,
            stderr="uiautomator: parse empty".encode())

    try:
        write_json_atomic(output_path, tree)
    except OSError as e:
        return subprocess.CompletedProcess(args=[], returncode=1,
            stderr=f"uiautomator: write failed - {e}".encode())

    return subprocess.CompletedProcess(args=[], returncode=0, stdout="")

# ADBKeyboard 输入法配置（Android 专属）
_ADB_KB_PACKAGE = "com.android.adbkeyboard"
_ADB_KB_IME_ID = "com.android.adbkeyboard/.AdbIME"
_ADB_KB_APK_PATH = os.path.join(REFERENCES_DIR, "ADBKeyboard.apk")

# 全新安装后是否存在系统级强制拦截，命中 device_guidance.GUIDANCE_REGISTRY 的
# key；Android 无此问题，保持 None（与 platform/harmony/ops.py 同名常量对称，
# 详见该文件注释）。
FRESH_INSTALL_GUIDANCE_ID = None

# App 版本探测/安装动作幂等重试上限（verify_install 轮询间隔 3s 不变，仅
# 总次数按平台差异调整，详见 platform/harmony/ops.py 同名常量注释）。
INSTALL_VERIFY_RETRIES = 24


def register_device(serial: str, device_type: str = "sandbox") -> dict:
    """注册设备到 imeituan CLI session，返回 {ok, session_id, detail}。

    根据 device_type 选择连接入口：
    - sandbox（云模拟器）：走 `device register --serial <addr> --remote-address <addr>`，
      将已由 yooz API 创建好的云模拟器注册到 imeituan CLI session。
    - local（本地真机）：走 `device connect --target local-device`，跳过网络
      连接探测，适用于 USB 直连的本地 Android 真机。
    """
    if device_type == "sandbox":
        from infra.imeituan_cli import imeituan_register_device
        return imeituan_register_device(serial, platform="android")
    from infra.imeituan_cli import imeituan_connect_local_device
    return imeituan_connect_local_device(serial, platform="android")


def reset_probe_state() -> None:
    """重置本平台探针的进程级状态（页面切换时由 context.invalidate_probes 调用）。

    需要重置：CDP 不可达标记 + WebView 屏幕偏移缓存。
    页面切换后 WebView 可能重新出现，重置标记后下次 build_probes() 会重新
    执行 inspect-tree 检测与 CDP 建链试探。

    这是平台模块契约成员（见 device_platform/registry.py::_REQUIRED_MODULE_ATTRS），
    与 build_probes 对称：探针链规则与探针状态的生命周期都由平台模块持有，
    工厂层（context）只负责触发，不感知具体平台实现。
    """
    from device_platform.android.probes.webview import reset_cdp_dead_reason
    reset_cdp_dead_reason()


def build_probes(ops, app_descriptor) -> list:
    """构建 Android 渲染层探针链：native 恒在，WebView 按需追加。

    Android WebView 内部 DOM 由 Chromium 内核绘制，inspect-tree 采集不到，
    需要 CDP 直连内核单独取 DOM（device_platform/android/probes/webview.py）；
    仅当 native 树中检测到 WebView 容器且调试 socket 可用时才加入链路，
    避免无 WebView 的页面上产生额外探测开销。

    供 context.get_probes() 统一调用，本函数是该平台探针链规则的
    唯一事实来源（对称实现见 device_platform/harmony/ops.py::build_probes）。
    """
    from device_platform.android.probes.native import NativeProbe
    probes = [NativeProbe()]

    # 检测当前页面是否包含 WebView 容器，含则追加 CDP 探针
    # 直接调用 ops.inspect_tree 避免依赖 context / inspect_tree 模块循环导入
    import json
    import os
    import tempfile

    # 可命中多种 WebView 实现的类名模式（不限于精确 "WebView" 子串）
    _WV_CLASS_PATTERNS = [
        "WebView",      # 原生 android.webkit.WebView
        "webview",      # 小写变体
        "AwContents",   # Chromium Android WebView 内核
        "X5WebView",    # 腾讯 X5 内核
        "TitansWebView", # Titans 定制 WebView 内核
        "SonicWebView", # 腾讯 Sonic 容器
    ]
    # 如果 CDP 已被确认不可达，跳过 inspect-tree 检测，直接返回纯 native 链
    # 避免每次探针链重建都执行 15s 的视图树采集
    try:
        from device_platform.android.probes.webview import _CDP_DEAD_REASON
        if _CDP_DEAD_REASON:
            return probes
    except ImportError:
        pass
    # 首页（MainActivity）不可用 imeituan inspect-tree，跳过 WebView 检测
    focus = ops.check_foreground()
    if focus and any(act in focus for act in app_descriptor.uninspectable_activities):
        return probes

    tmp = tempfile.mktemp(suffix=".json")
    try:
        r = ops.inspect_tree(tmp, timeout=15)
        if r.returncode == 0 and os.path.isfile(tmp):
            tree = read_json(tmp, default={})
            from device_platform.android.probes.node_adapter import parse_tree
            nodes = parse_tree(tree)
            if any(any(p in n.get("class_name", "") for p in _WV_CLASS_PATTERNS) for n in nodes):
                from device_platform.android.probes.webview import WebViewProbe
                wv = WebViewProbe(ops, app_descriptor)
                if wv.available():
                    probes.append(wv)
    finally:
        if os.path.isfile(tmp):
            os.remove(tmp)
    return probes


def ensure_toolchain() -> bool:
    """确保 Android 连接工具链（adb）就绪。

    供 device_lifecycle.py::cmd_setup 在 setup 阶段前置调用，探测本身
    （probe_local_devices）已隐含此检查，此处独立暴露供不经过探测的
    调用路径（如已持有 serial 直接走 setup）复用。
    """
    from infra.adb import ensure_adb
    adb_bin, _ = ensure_adb()
    return adb_bin is not None


def probe_local_devices() -> str:
    """探测唯一在线的本地 Android 真机，返回其 serial。

    供 platform.lifecycle.local.LocalDeviceLifecycle.acquire() 调用，
    是 device_type=local + platform=android 组合的设备发现入口。

    Raises:
        LocalDeviceProbeError: 未探测到设备 / 探测到多台设备 /
            工具链不可用 / 屏幕处于不可交互状态。
    """
    from infra.adb import ensure_adb, list_devices

    adb_bin, _ = ensure_adb()
    if not adb_bin:
        raise LocalDeviceProbeError("adb 不可用，无法探测本地 Android 真机（请检查 check-deps 输出）")

    serials = list_devices(adb_bin)
    if not serials:
        raise LocalDeviceProbeError(
            "未探测到已连接的android本地真机，请确认设备已连接并完成授权",
            guidance_id="android_local_not_connected", platform="android",
        )
    if len(serials) > 1:
        raise LocalDeviceProbeError(
            f"探测到多台android本地真机 {serials}，本地场景要求唯一在线设备，请断开多余设备后重试",
            guidance_id="android_local_multiple_devices", platform="android", serials=serials,
        )

    serial = serials[0]
    screen_ops = AndroidOps(serial)
    screen_state = screen_ops.screen_state()
    if not screen_ops.is_screen_interactive():
        raise LocalDeviceProbeError(
            f"设备 {serial} 当前处于熄屏/锁屏状态（{screen_state}），请解锁后重试",
            guidance_id="android_local_screen_locked",
            platform="android", serial=serial, screen_state=screen_state,
        )
    return serial


class AndroidOps(PlatformOps):
    """Android 平台实现。"""

    def __init__(self, device_serial: str, app_descriptor: AppDescriptor = None):
        self._serial = device_serial
        self._app = app_descriptor

    @property
    def serial(self) -> str:
        return self._serial

    # ═══════════════════════════════════════════════════════════
    # 感知
    # ═══════════════════════════════════════════════════════════

    def inspect_tree(self, output_path: str, *, timeout: int = 30) -> subprocess.CompletedProcess:
        """采集视图树 JSON。

        首页（MainActivity）走 uiautomator dump（裸 adb），其他走 imeituan CLI。
        """
        uninspectable = self._app.uninspectable_activities if self._app else ()
        focus = self.check_foreground()
        _focus_short = (focus or "")[:120]
        if focus and uninspectable and any(act in focus for act in uninspectable):
            sys.stderr.write(f"[inspect_tree] 焦点包含 uninspectable 标识，走 uiautomator. "
                             f"focus={_focus_short!r}, uninspectable={uninspectable}\n")
            return _uiautomator_inspect_tree(output_path)

        sys.stderr.write(f"[inspect_tree] 走 imeituan CLI. focus={_focus_short!r}, "
                         f"uninspectable={uninspectable}\n")
        return _device_inspect_tree(output_path,
                                    cli_timeout=timeout,
                                    subprocess_timeout=timeout + 15)

    # ═══════════════════════════════════════════════════════════
    # 交互原语
    # ═══════════════════════════════════════════════════════════

    def tap(self, x: int, y: int) -> bool:
        """坐标点击。"""
        r = imeituan_input("tap", x=x, y=y)
        if r.returncode != 0:
            sys.stderr.write(f"[android-ops] tap({x},{y}) 失败，returncode={r.returncode}\n")
        return r.returncode == 0

    def swipe(self, from_x: int, from_y: int, to_x: int, to_y: int,
              duration_ms: int = 500) -> bool:
        """滑动手势。"""
        r = imeituan_input("swipe",
                       from_x=from_x, from_y=from_y,
                       to_x=to_x, to_y=to_y,
                       duration=duration_ms)
        if r.returncode != 0:
            sys.stderr.write(f"[android-ops] swipe(({from_x},{from_y})->({to_x},{to_y})) 失败，returncode={r.returncode}\n")
        return r.returncode == 0

    def input_text(self, text: str) -> bool:
        """基础文本输入（纯 ASCII 路径，CJK 降级逻辑在 text_input.py 中）。"""
        r = imeituan_input("text", text=text)
        if r.returncode != 0:
            sys.stderr.write(f"[android-ops] input_text 失败 (len={len(text)}), returncode={r.returncode}\n")
        return r.returncode == 0

    def press_back(self) -> bool:
        """按下返回键。"""
        return self.keyevent("KEYCODE_BACK")

    def press_home(self) -> bool:
        """按下 Home 键。"""
        return self.keyevent("HOME")

    def screenshot(self, path: str) -> bool:
        """截图保存到指定路径。"""
        return _device_screenshot(path)

    # ═══════════════════════════════════════════════════════════
    # App 管理
    # ═══════════════════════════════════════════════════════════

    def launch_app(self, component: str, *, launcher_intent: bool = False) -> bool:
        """启动 App。

        Args:
            component: 组件名（pkg/activity）
            launcher_intent: True 使用 LAUNCHER intent（-a ACTION_MAIN -c CATEGORY_LAUNCHER），
                            模拟从桌面图标启动；False 直接 am start -n component。
        """
        if launcher_intent:
            r = imeituan_shell("am", "start",
                               "-a", "android.intent.action.MAIN",
                               "-c", "android.intent.category.LAUNCHER",
                               "-n", component)
        else:
            r = imeituan_shell("am", "start", "-n", component)
        return r.returncode == 0

    def force_stop(self, package: str) -> bool:
        """强制停止 App — 统一走 imeituan device app-stop，
        package 由 session 的 set-package 自动确定。"""
        r = imeituan_exec(["device", "app-stop"])
        return r.returncode == 0

    def launch_scheme(self, scheme_url: str) -> bool:
        """推送 scheme URL — am start <url>。"""
        r = imeituan_shell("am", "start", scheme_url)
        return r.returncode == 0

    def open_url(self, url: str) -> bool:
        """通过 imeituan CLI device open-url 打开 URL。

        package 已在 device setup 阶段通过 set-package 设置，
        无需再传 --package-id。
        """
        r = imeituan_open_url(url)
        return r.returncode == 0

    # ═══════════════════════════════════════════════════════════
    # App 生命周期管理
    # ═══════════════════════════════════════════════════════════

    def is_package_installed(self, package: str) -> bool:
        """精确判断 package 是否安装（逐行精确匹配，避免前缀模糊匹配误判）。

        不能用 `pm list packages <pkg>` 的输出做子串判断：
        `pm list packages` 对包名参数是前缀模糊匹配。
        """
        r = imeituan_shell("pm", "list", "packages")
        text = (r.stdout or "") if r else ""
        target_line = f"package:{package}"
        for line in text.splitlines():
            if line.strip() == target_line:
                return True
        return False

    def get_installed_version(self, package: str) -> dict:
        """获取已安装应用的版本信息。

        Returns:
            dict: {"installed": bool, "versionName": str|None, "versionCode": str|None}
        """
        if not self.is_package_installed(package):
            return {"installed": False, "versionName": None, "versionCode": None}
        r = imeituan_shell("dumpsys", "package", package)
        out = (r.stdout or "") if r else ""
        if not out or "Unable to find package" in out:
            return {"installed": False, "versionName": None, "versionCode": None}
        vn_match = re.search(r"versionName=([^\s]+)", out)
        vc_match = re.search(r"versionCode=(\d+)", out)
        version_name = vn_match.group(1) if vn_match else None
        version_code = vc_match.group(1) if vc_match else None
        if version_name is None and version_code is None:
            return {"installed": True, "versionName": None, "versionCode": None}
        return {"installed": True, "versionName": version_name, "versionCode": version_code}

    def uninstall_app(self, package: str) -> bool:
        """卸载指定包，以卸载后真实状态为唯一权威判据。

        包本就未安装时视为空操作，直接返回 True。
        """
        if not self.is_package_installed(package):
            return True
        imeituan_shell("pm", "uninstall", package)
        return not self.is_package_installed(package)

    def install_app(self, app_path: str, timeout: int = 300) -> bool:
        """安装 APK 到设备。"""
        r = imeituan_install(app_path, timeout=timeout)
        return r.returncode == 0

    # ═══════════════════════════════════════════════════════════
    # 环境配置
    # ═══════════════════════════════════════════════════════════

    def setup_keyboard(self) -> bool:
        """安装 ADBKeyboard 输入法并设为默认输入法（幂等）。

        已安装则跳过安装，直接设为默认输入法。
        Returns:
            bool: True 表示 ADBKeyboard 已安装且已设为默认输入法
        """
        # 1) 检查是否已安装
        if not self.is_package_installed(_ADB_KB_PACKAGE):
            if not os.path.isfile(_ADB_KB_APK_PATH):
                return False
            if not self.install_app(_ADB_KB_APK_PATH):
                return False

        # 2) 设为默认输入法（enable + set）
        imeituan_shell("ime", "enable", _ADB_KB_IME_ID)
        imeituan_shell("ime", "set", _ADB_KB_IME_ID)

        # 3) 验证
        verify_out = self.get_setting("secure", "default_input_method")
        return _ADB_KB_IME_ID in verify_out

    # ═══════════════════════════════════════════════════════════
    # 状态查询
    # ═══════════════════════════════════════════════════════════

    def check_foreground(self) -> str:
        """读取 mCurrentFocus 行（小写），查询失败返回空串。"""
        try:
            r = imeituan_shell("dumpsys", "window")
            out = (r.stdout or "") if r else ""
        except Exception:
            return ""
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("mCurrentFocus="):
                return line.lower()
        return ""

    def screen_size(self) -> tuple:
        """获取屏幕分辨率 (width, height)。"""
        return _device_screen_size()

    def viewport_insets(self) -> dict:
        """从 dumpsys window 获取状态栏/导航栏真实高度。

        解析 WindowManager 的 InsetsSource 信息（frame 字段），
        获取平台真实值而非固定经验值。

        优先级：
          1. InsetsSource type=ITYPE_STATUS_BAR / ITYPE_NAVIGATION_BAR 的 frame
          2. mInsetsHint 字段
          3. mDecorInsetsInfo 的 nonDecorInsets
        """
        try:
            r = imeituan_shell("dumpsys", "window")
            out = (r.stdout or "") if r else ""
            top = bottom = 0

            # 方案 1: 从 InsetsSource 解析 ITYPE_STATUS_BAR / ITYPE_NAVIGATION_BAR 的 frame
            # 格式: InsetsSource type=ITYPE_STATUS_BAR frame=[0,0][720,48]
            m_status = re.search(
                r'ITYPE_STATUS_BAR\s+frame=\[(\d+),(\d+)\]\[(\d+),(\d+)\]', out)
            m_nav = re.search(
                r'ITYPE_NAVIGATION_BAR\s+frame=\[(\d+),(\d+)\]\[(\d+),(\d+)\]', out)
            if m_status:
                # frame 的 bottom (y2) 即状态栏高度
                top = int(m_status.group(4))
            if m_nav:
                # 导航栏高度 = frame 高度 = y2 - y1
                nav_top = int(m_nav.group(2))
                nav_bot = int(m_nav.group(4))
                bottom = nav_bot - nav_top

            # 方案 2: 从 mInsetsHint 解析
            if top == 0:
                m = re.search(r'ITYPE_STATUS_BAR.*?mInsetsHint=Insets\{[^}]*?top=(\d+)', out)
                if m:
                    top = int(m.group(1))
            if bottom == 0:
                m = re.search(r'ITYPE_NAVIGATION_BAR.*?mInsetsHint=Insets\{[^}]*?bottom=(\d+)', out)
                if m:
                    bottom = int(m.group(1))

            # 方案 3: 从 mDecorInsetsInfo 的 nonDecorInsets 解析
            if top == 0 or bottom == 0:
                m = re.search(
                    r'ROTATION_0=\{nonDecorInsets=Rect\((\d+),\s*(\d+)\s*-\s*(\d+),\s*(\d+)\)', out)
                if m:
                    # nonDecorInsets 格式: Rect(left, top - right, bottom)
                    if top == 0:
                        top = int(m.group(2))
                    if bottom == 0:
                        bottom = int(m.group(4))

            if top > 0 or bottom > 0:
                return {"top": top, "bottom": bottom, "left": 0, "right": 0}
            return {}
        except Exception:
            return {}

    def device_alive(self) -> bool:
        """轻量级设备连通性检查。"""
        return _device_alive()

    def screen_state(self) -> str:
        """dumpsys power 解析 mWakefulness 字段，与 imeituan CLI 内部
        AdbAdapter.getPowerState 解析逻辑一致（正则 + 状态映射）。

        不直接调用 imeituan CLI 的 `device wake` 取其 beforeState 字段——
        该命令走 Node 进程转发，单次开销 0.38-0.55s，是本方法内 imeituan_shell
        单次调用（同样经 CLI 转发但只有一层 shell，无 wake 判断逻辑）的数倍；
        直接执行 dumpsys power 自行解析与现有 device_alive/screen_size 等
        状态查询方法保持同一套调用路径，不引入额外的命令种类。
        """
        r = imeituan_shell("dumpsys", "power")
        if r.returncode != 0:
            return "UNKNOWN"
        m = re.search(r'^\s*mWakefulness\s*=\s*([A-Za-z]+)\s*$', r.stdout or "", re.MULTILINE)
        if not m:
            return "UNKNOWN"
        return {
            "awake": "AWAKE",
            "asleep": "SLEEP",
            "dozing": "DOZE",
            "dreaming": "DREAMING",
        }.get(m.group(1).lower(), "UNKNOWN")

    def is_screen_interactive(self) -> bool:
        """判断当前电源状态是否允许 UI 自动化继续执行。

        DREAMING（屏保态）归为不可交互：屏幕本身是亮的，但显示内容是系统
        屏保而非目标 App，inspect-tree/tap 同样会命中错误的窗口，与 SLEEP/
        DOZE 造成的后果一致。
        """
        state = self.screen_state()
        if state == "UNKNOWN":
            return True
        return state == "AWAKE"

    def pidof(self, package: str) -> str:
        """查询进程 PID，进程不存在返回空串。"""
        r = imeituan_shell("pidof", package)
        return (r.stdout or "").strip() if r else ""

    # ═══════════════════════════════════════════════════════════
    # 文本输入语义操作
    # ═══════════════════════════════════════════════════════════

    def clear_text(self, x: int, y: int, max_del: int = 20) -> bool:
        """清空输入框：tap 聚焦 → KEYCODE_MOVE_END → 批量退格。"""
        self.tap(x, y)
        time.sleep(0.4)
        self.keyevent("KEYCODE_MOVE_END")
        time.sleep(0.1)
        self.keyevent(*(["67"] * max_del))
        return True

    def supports_cjk_input(self) -> bool:
        """Android 的 input_text 不原生支持 CJK，需要 ADBKeyboard。"""
        return False

    # ═══════════════════════════════════════════════════════════
    # 结构化设备命令
    # ═══════════════════════════════════════════════════════════

    def broadcast(self, action: str, **extras) -> bool:
        """发送 am broadcast。"""
        cmd = ["am", "broadcast", "-a", action]
        for k, v in extras.items():
            cmd += ["--es", k, str(v)]
        r = imeituan_shell(*cmd)
        return r.returncode == 0

    def content_call(self, uri: str, method: str, *args) -> tuple:
        """执行 content call，操作 ContentProvider。"""
        cmd = ["content", "call", "--uri", uri, "--method", method]
        for a in args:
            cmd += ["--arg", str(a)]
        r = imeituan_shell(*cmd)
        out = ((r.stdout or "") + (r.stderr or ""))
        return r.returncode == 0, out

    def keyevent(self, *keycodes) -> bool:
        """发送 input keyevent。"""
        r = imeituan_shell("input", "keyevent", *keycodes)
        return r.returncode == 0

    def get_setting(self, namespace: str, key: str) -> str:
        """读取 settings get {namespace} {key}。"""
        r = imeituan_shell("settings", "get", namespace, key)
        return (r.stdout or "").strip() if r else ""

    def clear_app_data(self, package: str) -> bool:
        """通过 pm clear 清除 App 数据。"""
        r = imeituan_shell("pm", "clear", package)
        return r.returncode == 0

    def grant_permissions(self, package: str, permissions: list[str]) -> list[bool]:
        """通过 pm grant 预授予运行时权限。"""
        results = []
        for perm in permissions:
            r = imeituan_shell("pm", "grant", package, perm)
            results.append(r.returncode == 0)
        return results

    @property
    def default_permissions_to_grant(self) -> list[str]:
        return DEFAULT_PERMISSIONS_TO_GRANT

    # ═══════════════════════════════════════════════════════════
    # 逃逸通道
    # ═══════════════════════════════════════════════════════════

    def shell(self, *args) -> subprocess.CompletedProcess:
        """在设备上执行任意 shell 命令（仅用于无法归类的场景）。"""
        return imeituan_shell(*args)

    def disconnect(self) -> bool:
        """断开设备连接。"""
        return imeituan_disconnect_device(all_sessions=True)["ok"]


# 模块级契约成员（见 platform/registry.py::_REQUIRED_MODULE_ATTRS）：
# 供 context.create_platform_ops 统一按 (serial, app_descriptor) 构造，
# 不需要在调用方手写 if platform == "android" 分支。
PlatformOpsClass = AndroidOps
