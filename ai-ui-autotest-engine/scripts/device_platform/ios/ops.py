#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IOSOps — iOS 平台 PlatformOps 实现（本地模拟器与真机通用）。"""
import json
import subprocess
import time
import urllib.request

from core.util.json_utils import write_json_atomic, read_json
from device_platform.base import PlatformOps, AppDescriptor, LocalDeviceProbeError, RendererProbe
from device_platform.ios.probes.node_adapter import parse_tree  # 模块级契约成员，供 parse_inspect_tree 分派调用
from infra.imeituan_cli import (
    imeituan_input,
    imeituan_open_url,
    imeituan_install,
    imeituan_exec,
    imeituan_screenshot as _device_screenshot,
    imeituan_disconnect_device,
    imeituan_run,
)

# 默认 WDA 端口（remote-desktop --mode serve 或本地启动的 WDA）
DEFAULT_WDA_PORT = 18661
FALLBACK_WDA_PORT = 8100

FRESH_INSTALL_GUIDANCE_ID = None
INSTALL_VERIFY_RETRIES = 20


def register_device(serial: str, device_type: str = "local-emulator") -> dict:
    """注册设备到 imeituan CLI session。"""
    if device_type == "local-emulator":
        from infra.imeituan_cli import imeituan_connect_local_emulator
        return imeituan_connect_local_emulator(serial, platform="ios")
    from infra.imeituan_cli import imeituan_connect_local_device
    return imeituan_connect_local_device(serial, platform="ios")


class NativeIOSProbe(RendererProbe):
    """iOS 视图树渲染层探针。

    与 Android NativeProbe 相同策略：委托给 screen_state.inspect_tree 的
    采集与智能匹配引擎（dump_inspect_tree → parse_inspect_tree → 多级匹配/
    merged_text/可点击祖先上溯/遮挡规避），不自行做简单子串匹配。
    """

    def __init__(self, ops: "IOSOps"):
        self._ops = ops

    @property
    def probe_name(self) -> str:
        return "native"

    def available(self) -> bool:
        return self._ops.device_alive()

    def find_text(self, text: str) -> bool:
        from screen_state.inspect_tree import native_has_text
        return native_has_text(text)

    def find_center(self, text: str) -> tuple:
        from screen_state.inspect_tree import native_find_center
        return native_find_center(text)

    def list_texts(self) -> list:
        from screen_state.inspect_tree import native_list_texts
        return native_list_texts()


def reset_probe_state() -> None:
    """重置本平台探针的进程级状态（页面切换时由 context.invalidate_probes 调用）。

    iOS 探针（NativeIOSProbe）无跨页面的进程级缓存，因此为空实现——
    仅为满足平台模块契约（见 _REQUIRED_MODULE_ATTRS）。
    """
    return None


def build_probes(ops, app_descriptor) -> list:
    """构建 iOS 渲染层探针链。"""
    return [NativeIOSProbe(ops)]


def ensure_toolchain() -> bool:
    """确保 iOS 连接工具链（Xcode + xcrun）就绪。"""
    try:
        r = subprocess.run(["xcrun", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        if r.returncode != 0:
            return False
        # 检测 Xcode
        xr = subprocess.run(["xcode-select", "-p"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        return xr.returncode == 0
    except Exception:
        return False


def probe_local_devices() -> str:
    """探测或启动本地 iOS 模拟器实例，返回其 UDID (serial)。"""
    if not ensure_toolchain():
        raise LocalDeviceProbeError(
            "未检测到 Xcode 或 xcrun 工具链，请确保已安装 Xcode",
            guidance_id="ios_simulator_xcode_not_installed",
            platform="ios",
        )

    # 1. 查找已启动的模拟器
    try:
        r = subprocess.run(["xcrun", "simctl", "list", "devices", "available", "--json"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=10)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            devices_by_runtime = data.get("devices", {})
            booted = []
            for runtime, dlist in devices_by_runtime.items():
                for d in dlist:
                    if d.get("state") == "Booted" and d.get("isAvailable", True):
                        booted.append(d.get("udid"))
            if booted:
                return booted[0]
    except Exception:
        pass

    # 2. 如果没有已启动的，通过 imeituan device simulator quick-start 自动启动一个
    try:
        qr = imeituan_run(["device", "simulator", "quick-start", "-p", "ios", "--format", "json"], timeout=60)
        if qr.returncode == 0:
            payload = json.loads(qr.stdout or "{}")
            serial = payload.get("data", {}).get("serial") or payload.get("data", {}).get("deviceId")
            if serial:
                return serial
    except Exception:
        pass

    # 3. 兜底直接找一个可用的模拟器并 start
    try:
        r = subprocess.run(["xcrun", "simctl", "list", "devices", "available", "--json"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=10)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            for runtime, dlist in data.get("devices", {}).items():
                if "iOS" in runtime:
                    for d in dlist:
                        if d.get("isAvailable", True):
                            udid = d.get("udid")
                            # 启动它
                            subprocess.run(["xcrun", "simctl", "boot", udid], timeout=30)
                            return udid
    except Exception:
        pass

    raise LocalDeviceProbeError(
        "未找到或无法启动可用的 iOS 模拟器实例",
        guidance_id="ios_simulator_no_booted_device",
        platform="ios",
    )


class IOSOps(PlatformOps):
    """iOS 平台 PlatformOps 实现。"""

    def __init__(self, device_serial: str, app_descriptor: AppDescriptor = None):
        self._serial = device_serial
        self._app = app_descriptor
        self._wda_session_id = None
        self._wda_port = DEFAULT_WDA_PORT

    @property
    def serial(self) -> str:
        return self._serial

    # ═══════════════════════════════════════════════════════════
    # WDA 交互底层支持
    # ═══════════════════════════════════════════════════════════

    def _ensure_wda_session(self) -> str:
        """确保拿到活跃的 WDA session ID。"""
        if self._wda_session_id:
            return self._wda_session_id

        bundle_id = self._app.package_name if self._app else "com.meituan.imeituan"
        for port in (self._wda_port, FALLBACK_WDA_PORT):
            url = f"http://127.0.0.1:{port}/session"
            data = json.dumps({"capabilities": {"firstMatch": [{"bundleId": bundle_id}]}}).encode("utf-8")
            try:
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    sid = res.get("sessionId") or res.get("value", {}).get("sessionId")
                    if sid:
                        self._wda_port = port
                        self._wda_session_id = sid
                        return sid
            except Exception:
                continue
        return None

    def get_wda_source(self) -> str:
        """从 WDA 获取页面 XML 元素树。"""
        sid = self._ensure_wda_session()
        if not sid:
            return ""
        url = f"http://127.0.0.1:{self._wda_port}/session/{sid}/source"
        try:
            req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res.get("value", "")
        except Exception:
            return ""

    # ═══════════════════════════════════════════════════════════
    # 感知
    # ═══════════════════════════════════════════════════════════

    def inspect_tree(self, output_path: str, *, timeout: int = 30) -> subprocess.CompletedProcess:
        """获取视图树并写入指定文件。优先写出 WDA XML 内容以保证文字完备。"""
        xml = self.get_wda_source()
        if xml:
            try:
                write_json_atomic(output_path, {"code": 0, "data": {"platform": "ios", "serial": self._serial, "xml": xml}})
                return subprocess.CompletedProcess(args=["wda", "source"], returncode=0, stdout="ok", stderr="")
            except Exception as e:
                pass

        # 降级走 imeituan CLI 的 inspect-tree
        from infra.imeituan_cli import imeituan_inspect_tree
        return imeituan_inspect_tree(output_path, cli_timeout=timeout)

    # ═══════════════════════════════════════════════════════════
    # 交互原语
    # ═══════════════════════════════════════════════════════════

    def tap(self, x: int, y: int) -> bool:
        """坐标点击：优先 WDA tap，降级走 imeituan_input。"""
        sid = self._ensure_wda_session()
        if sid:
            url = f"http://127.0.0.1:{self._wda_port}/session/{sid}/wda/tap"
            data = json.dumps({"x": x, "y": y}).encode("utf-8")
            try:
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return resp.status == 200
            except Exception:
                pass
        
        r = imeituan_input("tap", x=x, y=y)
        return r.returncode == 0

    def swipe(self, from_x: int, from_y: int, to_x: int, to_y: int, duration_ms: int = 500) -> bool:
        """滑动操作：优先 WDA dragFromToForDuration。"""
        sid = self._ensure_wda_session()
        if sid:
            url = f"http://127.0.0.1:{self._wda_port}/session/{sid}/wda/dragfromtoforduration"
            data = json.dumps({
                "fromX": from_x, "fromY": from_y,
                "toX": to_x, "toY": to_y,
                "duration": duration_ms / 1000.0
            }).encode("utf-8")
            try:
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    return resp.status == 200
            except Exception:
                pass

        r = imeituan_input("swipe", from_x=from_x, from_y=from_y, to_x=to_x, to_y=to_y, duration=duration_ms)
        return r.returncode == 0

    def input_text(self, text: str) -> bool:
        """文本输入：优先 WDA keys。"""
        sid = self._ensure_wda_session()
        if sid:
            url = f"http://127.0.0.1:{self._wda_port}/session/{sid}/wda/keys"
            data = json.dumps({"value": list(text)}).encode("utf-8")
            try:
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return resp.status == 200
            except Exception:
                pass

        r = imeituan_input("text", text=text)
        return r.returncode == 0

    def press_back(self) -> bool:
        """iOS 无全局物理返回键，通过向右轻扫模拟返回。"""
        sz = self.screen_size()
        return self.swipe(from_x=10, from_y=sz[1] // 2, to_x=sz[0] // 2, to_y=sz[1] // 2, duration_ms=250)

    def press_home(self) -> bool:
        """按下 Home 键 / 回到桌面。"""
        sid = self._ensure_wda_session()
        if sid:
            url = f"http://127.0.0.1:{self._wda_port}/wda/homescreen"
            try:
                req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return resp.status == 200
            except Exception:
                pass
        return False

    def screenshot(self, path: str) -> bool:
        return _device_screenshot(path)

    # ═══════════════════════════════════════════════════════════
    # App 管理与生命周期
    # ═══════════════════════════════════════════════════════════

    def launch_app(self, component: str, *, launcher_intent: bool = False) -> bool:
        """启动 App（iOS 默认注入 isUITest 抑制断言弹窗）。"""
        bundle_id = self._app.package_name if self._app else component
        r = imeituan_run([
            "device", "app-start", bundle_id,
            "--extras", '{"isUITest":"YES"}',
            "--format", "json"
        ], timeout=45)
        return r.returncode == 0

    def force_stop(self, package: str) -> bool:
        r = imeituan_exec(["device", "app-stop"])
        return r.returncode == 0

    def launch_scheme(self, scheme_url: str) -> bool:
        return self.open_url(scheme_url)

    def open_url(self, url: str) -> bool:
        r = imeituan_open_url(url)
        return r.returncode == 0

    def is_package_installed(self, package: str) -> bool:
        r = imeituan_run(["device", "app-list", "--format", "json"], timeout=15)
        if r.returncode != 0:
            return False
        try:
            d = json.loads(r.stdout or "{}")
            apps = d.get("data", {}).get("apps", [])
            return any(a.get("packageId") == package for a in apps)
        except Exception:
            return False

    def get_installed_version(self, package: str) -> dict:
        """获取已安装包的版本号。"""
        installed = self.is_package_installed(package)
        if not installed:
            return {"installed": False, "versionName": None, "versionCode": None}
        # 通过 imeituan device app-info 获取版本号
        try:
            r = imeituan_run(["device", "app-info", package, "--format", "json"], timeout=15)
            if r.returncode == 0:
                d = json.loads(r.stdout or "{}")
                data = d.get("data", {})
                vn = data.get("versionName") or data.get("version", "")
                if vn:
                    return {"installed": True, "versionName": str(vn), "versionCode": None}
        except Exception:
            pass
        return {"installed": True, "versionName": None, "versionCode": None}

    def uninstall_app(self, package: str) -> bool:
        r = imeituan_run(["device", "uninstall", package, "--format", "json"], timeout=30)
        return r.returncode == 0

    def install_app(self, app_path: str, timeout: int = 300) -> bool:
        r = imeituan_install(app_path, timeout=timeout)
        return r.returncode == 0

    def setup_keyboard(self) -> bool:
        """iOS 模拟器原生支持中文与文本注入，无需安装键盘。"""
        return True

    def check_foreground(self) -> str:
        """获取前台 App 的 bundle ID。"""
        sid = self._ensure_wda_session()
        if sid:
            url = f"http://127.0.0.1:{self._wda_port}/session/{sid}/wda/activeAppInfo"
            try:
                req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    bundle = res.get("value", {}).get("bundleId", "")
                    if bundle:
                        return bundle
            except Exception:
                pass
        
        # 降级通过 app-list 探测
        r = imeituan_run(["device", "app-list", "--format", "json"], timeout=10)
        if r.returncode == 0:
            try:
                d = json.loads(r.stdout or "{}")
                apps = d.get("data", {}).get("apps", [])
                if any(a.get("packageId") == "com.meituan.imeituan" for a in apps):
                    return "com.meituan.imeituan"
            except Exception:
                pass
        return ""

    def screen_size(self) -> tuple:
        """通过 WDA /wda/screen 获取模拟器屏幕分辨率，失败返回默认值。"""
        sid = self._ensure_wda_session()
        if sid:
            try:
                url = f"http://127.0.0.1:{self._wda_port}/session/{sid}/wda/screen"
                req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    val = res.get("value", {})
                    w = val.get("width", 0) or 0
                    h = val.get("height", 0) or 0
                    if w > 0 and h > 0:
                        return (w, h)
            except Exception:
                pass
        # 通过 xcrun simctl 获取设备信息
        try:
            r = subprocess.run(
                ["xcrun", "simctl", "list", "devices", "--json"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=10,
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                for runtime, dlist in data.get("devices", {}).items():
                    for d in dlist:
                        if d.get("udid") == self._serial:
                            dtype = d.get("deviceType", "")
                            # iPhone 15 Pro / iPhone 16 Pro 等常见机型
                            if "iPhone" in dtype:
                                return (1290, 2796)  # 6.7" 默认
                            break
        except Exception:
            pass
        return (1290, 2796)

    def viewport_insets(self) -> dict:
        """iOS 模拟器 safe area insets。

        通过 WDA /wda/screen 获取屏幕信息，后续可扩展为获取真实
        safeAreaInsets。失败时返回典型 iPhone 数值。
        """
        try:
            sid = self._ensure_wda_session()
            if sid:
                url = f"http://127.0.0.1:{self._wda_port}/session/{sid}/wda/screen"
                req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    val = res.get("value", {})
                    status_bar = val.get("statusBarHeight", 0) or 0
                    safe_area = val.get("safeAreaInsets", {}) or {}
                    top = int(safe_area.get("top", status_bar))
                    bottom = int(safe_area.get("bottom", 0))
                    left = int(safe_area.get("left", 0))
                    right = int(safe_area.get("right", 0))
                    if top > 0 or bottom > 0:
                        return {"top": top, "bottom": bottom,
                                "left": left, "right": right}
        except Exception:
            pass
        # 兜底：iPhone 典型值（状态栏 ~54px，横条 ~34px）
        return {"top": 54, "bottom": 34, "left": 0, "right": 0}

    def device_alive(self) -> bool:
        try:
            r = subprocess.run(["xcrun", "simctl", "list", "devices", "booted"], stdout=subprocess.PIPE, timeout=5)
            return r.returncode == 0 and self._serial in (r.stdout.decode("utf-8", "ignore") or "")
        except Exception:
            return False

    def screen_state(self) -> str:
        return "AWAKE"

    def is_screen_interactive(self) -> bool:
        return True

    def pidof(self, package: str) -> str:
        return "1" if self.is_package_installed(package) else ""

    def clear_text(self, x: int, y: int, max_del: int = 20) -> bool:
        self.tap(x, y)
        time.sleep(0.3)
        for _ in range(max_del):
            self.input_text("\b")
        return True

    def supports_cjk_input(self) -> bool:
        return True

    def broadcast(self, action: str, **extras) -> bool:
        return True

    def content_call(self, uri: str, method: str, *args) -> tuple:
        return True, ""

    def keyevent(self, *keycodes) -> bool:
        return True

    def get_setting(self, namespace: str, key: str) -> str:
        return ""

    def clear_app_data(self, package: str) -> bool:
        """iOS 暂不支持清除 App 数据。"""
        return False

    def grant_permissions(self, package: str, permissions: list[str]) -> list[bool]:
        """iOS 暂不支持预授予权限。"""
        return [False] * len(permissions)

    def shell(self, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    def disconnect(self) -> bool:
        return imeituan_disconnect_device(all_sessions=True)["ok"]


PlatformOpsClass = IOSOps
