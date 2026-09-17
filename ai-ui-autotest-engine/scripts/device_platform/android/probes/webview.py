#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WebViewProbe — WebView DOM 渲染层探针（Chrome DevTools Protocol）。

WebView 在 Android View 树中是叶子节点，内部 DOM 由 Chromium 内核绘制，
不向 View 系统注册子节点，因此 inspect-tree 采集不到。本探针通过 CDP
直连内核取 DOM。

链路：
  1. adb shell cat /proc/net/unix  → 发现 webview_devtools_remote_<pid>
  2. adb forward tcp:<port> localabstract:<socket>
  3. GET /json/version             → 校验 Android-Package 归属
  4. GET /json/list                → 选定目标页面
  5. WebSocket Runtime.evaluate    → 取 innerText / 元素坐标

依赖 App 已开启 WebView 调试开关（setWebContentsDebuggingEnabled）。
线上包通常关闭，此时 available() 返回 False，Probe 链自动退化为纯 native。
"""
import json
import random
import re
import subprocess
import sys
import urllib.request

from device_platform.base import RendererProbe
from infra.adb import ensure_adb

_SOCKET_RE = re.compile(r"webview_devtools_remote_\d+")
_PORT_RANGE = (9300, 9399)
_HTTP_TIMEOUT = 8
_WS_TIMEOUT = 20

# 模块级 CDP 不可达标记
# 遵循执行原则第 4 条（"环境不可用快速失败"）和 available() 契约
# （"不可用时跳过，不产生副作用也不报错"）。
#
# CDP 不可达可能是设备/App 级别的持久状态（如 App 未开启调试开关），
# 也可能是页面级别的瞬时状态（如当前页面无 WebView 但后续页面有）。
# 因此该标记会在 invalidate_probes() 时被重置，允许探针链在页面切换后
# 重新发现 WebView 调试能力。
# 持久性不可达的实际判据由 available() 内部的 _discover_socket() 决定，
# 标记仅用于缓存结果避免重复执行昂贵的 CDP 建链操作。
_CDP_DEAD_REASON = None  # None=未确认, str=失败原因

# 进程级 WebView 屏幕偏移缓存 (ox, oy)
# 提升为模块级而非实例级：探针链 invalidate 重建会新建实例，若偏移挂在
# 实例上则每次重建都要重算（实测独立 inspect-tree 单次 ~4.7s）。
# 同进程内页面布局通常稳定，进程级缓存即可覆盖同一命令内多次定位。
_SCREEN_OFFSET_CACHE = None


def reset_cdp_dead_reason():
    """重置 CDP 不可达标记，供 invalidate_probes() 在页面切换时调用。
    
    页面切换后（如从 MRN 跳转到 H5 WebView），WebView 的 CDP 调试能力
    可能重新出现。重置标记后，下次 build_probes() 会重新执行完整的
    inspect-tree 检测 + CDP 建链试探。

    同时重置进程级屏幕偏移缓存——页面切换后 WebView 容器在屏幕上的
    位置可能变化（导航栏高度不同），继续用旧偏移会导致坐标错位。
    """
    global _CDP_DEAD_REASON, _SCREEN_OFFSET_CACHE
    _CDP_DEAD_REASON = None
    _SCREEN_OFFSET_CACHE = None


def get_cdp_dead_reason():
    """返回当前 CDP 不可达原因，供异常诊断和断言重试策略使用。
    
    返回 None 表示 CDP 尚未确认不可达（可正常尝试），
    返回字符串表示不可达原因（如 'no_socket' / 'forward_failed' / 'ws_timeout'）。
    """
    return _CDP_DEAD_REASON

# WebView 探针专用 JS 表达式模板（避免重复构造，减少内存）
# 三合一策略：innerText 优先 → 叶子节点 textContent 兜底 → 空保护
_JS_PAGE_TEXT = """(()=>{
  const inner=document.body&&document.body.innerText;
  if(inner&&inner.trim().length>0) return inner.trim();
  const texts=[];
  if(document.title) texts.push(document.title);
  document.querySelectorAll('*:not(script):not(style)').forEach(e=>{
    if(e.children.length===0&&e.textContent&&e.textContent.trim()){
      texts.push(e.textContent.trim());
    }
  });
  return [...new Set(texts)].join('\\n');
})()"""

# 找包含目标文本的最具体可见元素（优先 innerText 最短 = 最精确的容器）
_JS_FIND_CENTER = """((q)=>{
  const d=window.devicePixelRatio||1;
  const els=[...document.querySelectorAll('*:not(script):not(style)')]
    .filter(e=>e.innerText&&e.innerText.includes(q))
    .sort((a,b)=>a.innerText.length-b.innerText.length);
  if(!els.length) return '';
  const r=els[0].getBoundingClientRect();
  if(!r.width&&!r.height) return '';
  return JSON.stringify([Math.round((r.left+r.width/2)*d),Math.round((r.top+r.height/2)*d)]);
})(%s)"""


class WebViewProbe(RendererProbe):
    """基于 CDP 的 WebView DOM 探针。

    实例持有端口转发与目标页面信息，按 case 生命周期复用（见 context.get_probes）。
    """

    def __init__(self, ops, app_descriptor):
        self._ops = ops
        self._app = app_descriptor
        self._port = None
        self._socket = None
        self._resolved = False
        self._page_cache = None      # 最近一次 /json/list 原始列表（诊断用）
        self._last_target = None     # 最近一次选中的目标页面信息（诊断用）

    @property
    def probe_name(self) -> str:
        return "webview"

    def available(self) -> bool:
        """探测 WebView 调试 socket 并建立端口转发，成功返回 True。

        结果在实例内缓存，同一 case 内重复调用不重复建链。

        模块级 _CDP_DEAD_REASON 标记被设置时直接返回 False，
        避免每次探针链重建都重复执行昂贵的检测。
        """
        if _CDP_DEAD_REASON:
            return False
        if self._resolved:
            return self._port is not None
        self._resolved = True
        try:
            self._socket = self._discover_socket()
            if not self._socket:
                return False
            self._port = self._forward(self._socket)
            return self._port is not None
        except Exception as e:
            sys.stderr.write(f"  ⚠️  WebViewProbe 初始化失败: {e}\n")
            self._port = None
            return False

    def find_text(self, text: str) -> bool:
        """文本存在性判断，大小写不敏感。

        策略：先精确匹配（大小写不敏感），再逐行匹配兜底。
        与 NativeProbe 的智能匹配对齐，避免因大小写差异漏匹配。
        """
        page_text = self._page_text()
        if not page_text:
            return False
        text_lower = text.lower()
        page_lower = page_text.lower()
        if text_lower in page_lower:
            return True
        # 逐行匹配兜底：某些 SPA 框架的 innerText 会保留 CSS 隐藏文本
        for line in page_lower.split("\n"):
            if text_lower in line:
                return True
        return False

    def find_center(self, text: str) -> tuple:
        """返回设备屏幕物理坐标（已含 WebView 容器屏幕偏移）。

        使用 innerText 匹配（兼容所有 DOM 渲染结构），优先选 innerText 最短
        的容器（即最具体的、直接包含目标文本的叶子容器），不限制 children
        为空，避免 SPA 框架中文本在非叶子节点中的场景漏匹配。

        坐标换算：
        - getBoundingClientRect() 返回的是相对 WebView 视口左上角的坐标
          （viewport 原点在 WebView 容器内，不含容器在屏幕上的偏移）。
        - WebView 容器本身可能被原生导航栏/标题栏顶下屏幕一段距离
          （如顶部导航栏），因此必须叠加容器在屏幕上的
          位置 (locationOnScreen) 才是可点击的屏幕物理坐标。
        """
        raw = self._evaluate(_JS_FIND_CENTER % json.dumps(text))
        if not raw:
            return None
        try:
            x, y = json.loads(raw)
            ox, oy = self._screen_offset()
            return int(x + ox), int(y + oy)
        except (ValueError, TypeError):
            return None

    def _screen_offset(self):
        """返回 WebView 容器在屏幕上的物理坐标偏移 (ox, oy)。

        从 native 视图树中定位 WebView 容器节点（class 含 WebView 相关
        模式），取其 locationOnScreen 左上角坐标。

        实现要点：
        - 复用 screen_state.dump_inspect_tree（自带 8s 进程内缓存 + 重试），
          避免每次定位都独立跑一遍 inspect-tree（实测单次 ~4.7s）。
        - 偏移量做进程级缓存：同进程内探针链即使被 invalidate 重建，
          也无需重算偏移（页面布局在进程生命周期内通常稳定）。

        Returns:
            tuple[int, int]: (ox, oy)，默认 (0, 0)（找不到容器时退化为
            viewport 原点，保证旧行为不回归）。
        """
        global _SCREEN_OFFSET_CACHE
        if _SCREEN_OFFSET_CACHE is not None:
            return _SCREEN_OFFSET_CACHE
        ox = oy = 0
        try:
            from screen_state.inspect_tree import dump_inspect_tree, parse_inspect_tree
            tree = dump_inspect_tree(wait_sec=6, max_attempts=1)
            if tree:
                nodes = parse_inspect_tree(tree)
                _WV_PATTERNS = ("WebView", "webview", "AwContents",
                                "X5WebView", "TitansWebView", "SonicWebView")
                for n in nodes:
                    if any(p in n.get("class_name", "") for p in _WV_PATTERNS):
                        if n.get("x") is not None and n.get("y") is not None:
                            ox, oy = int(n["x"]), int(n["y"])
                            break
        except Exception as e:
            sys.stderr.write(f"  ⚠️  WebView 屏幕偏移解析失败，退化 viewport 原点: {e}\n")
        _SCREEN_OFFSET_CACHE = (ox, oy)
        return _SCREEN_OFFSET_CACHE

    def list_texts(self) -> list:
        """列出页面全部可见文本行（包含 title，排除 script/style 标签内容）。

        复用 _page_text 的 JS 策略：innerText 优先 → 叶子节点 textContent 兜底。
        """
        raw = self._page_text()
        if not raw:
            return []
        return [ln.strip() for ln in raw.splitlines() if ln.strip()]

    def close(self) -> None:
        if self._port is not None:
            self._adb("forward", "--remove", f"tcp:{self._port}")
            self._port = None

    # ─── CDP 链路内部实现 ───────────────────────────────────────

    def _discover_socket(self):
        global _CDP_DEAD_REASON
        if _CDP_DEAD_REASON:
            return None
        r = self._ops.shell("cat", "/proc/net/unix")
        out = (getattr(r, "stdout", "") or "")
        m = _SOCKET_RE.search(out)
        if not m:
            _CDP_DEAD_REASON = "no_socket"
        return m.group(0) if m else None

    def _forward(self, socket_name):
        """建立端口转发并校验归属，成功返回端口号。

        端口冲突时 adb forward 会失败，若不校验就直接请求，可能命中本机
        其它 Chromium 实例（如 IDE 的 Electron devtools）并返回合法 JSON。
        因此必须用 Android-Package 校验归属。

        尝试 2 次端口转发（端口冲突概率低，5 次太重）：
        全部失败后标记 _CDP_DEAD_REASON，避免后续调用重试。
        """
        global _CDP_DEAD_REASON
        for _ in range(2):
            port = random.randint(*_PORT_RANGE)
            self._adb("forward", "--remove", f"tcp:{port}")
            r = self._adb("forward", f"tcp:{port}",
                          f"localabstract:{socket_name}")
            if r is None or r.returncode != 0:
                continue
            if self._verify_owner(port):
                return port
            self._adb("forward", "--remove", f"tcp:{port}")
        _CDP_DEAD_REASON = "forward_failed"
        sys.stderr.write("  ⚠️  WebViewProbe 端口转发失败或归属校验未通过\n")
        return None

    def _adb(self, *args):
        """执行 host 侧 adb 命令（端口转发不是设备内命令，走不了 ops.shell）。

        自动处理云模拟器场景：如果 host adb 尚未连接设备，先 adb connect 再重试。
        """
        adb_bin = ensure_adb(install=False)
        if isinstance(adb_bin, tuple):
            adb_bin = adb_bin[0]
        if not adb_bin:
            return None

        def _run():
            try:
                return subprocess.run([adb_bin, "-s", self._ops.serial, *args],
                                      capture_output=True, text=True, timeout=20)
            except (subprocess.SubprocessError, OSError):
                return None

        r = _run()
        if r is not None and r.returncode == 0:
            return r

        # host adb 未连接设备（云模拟器场景常见），尝试 connect 后重试
        # 用 devices -l 检查 serial 是否在设备列表中
        try:
            check = subprocess.run([adb_bin, "devices"],
                                   capture_output=True, text=True, timeout=10)
            if self._ops.serial not in (check.stdout or ""):
                sys.stderr.write(f"  ⚠️  host adb 尚未连接 {self._ops.serial}，正在 connect...\n")
                subprocess.run([adb_bin, "connect", self._ops.serial],
                              capture_output=True, text=True, timeout=15)
                return _run()
        except (subprocess.SubprocessError, OSError):
            pass

        return r if r else None

    def _verify_owner(self, port):
        data = self._http_json(f"http://localhost:{port}/json/version")
        if not isinstance(data, dict):
            return False
        return data.get("Android-Package") == self._app.package_name

    def _pick_target(self):
        """从 CDP 页面列表中选择当前可见的目标页面。

        选择策略（按优先级）：
        1. visible=true + attached=true + empty=false — 当前屏幕可见、已挂载
           且已渲染出内容的页面（最可靠）。empty=false 排除"页面对象已创建但
           DOM 尚未加载"的瞬态页面。
        2. visible=true + attached=true — 退而求其次，接受 empty 状态未知。
        3. 遍历跳过 never_attached 僵尸对象后的第一个候选 — 兜底。

        CDP 的 /json/list 返回页面按创建时间排序，同一 URL 可能残留多个僵尸
        页面对象（`never_attached=true` 的旧页，DOM 为空、读不到任何文本、
        点不中任何元素）。visible/attached/empty 才是真正的"当前可见"判定
        依据，绝不能依赖索引顺序（pages[0]）——否则可能命中僵尸页导致
        find-text/assert 永远 NOT_FOUND（典型场景：页面跳转后残留的上一个
        旧页对象，DOM 已清空但 CDP 仍保留其条目）。
        """
        data = self._http_json(f"http://localhost:{self._port}/json/list")
        self._page_cache = data if isinstance(data, list) else None
        if not isinstance(data, list):
            return None
        # 过滤：type=page + WebSocket 可用 + url 非空
        candidates = [t for t in data
                      if t.get("type") == "page"
                      and t.get("webSocketDebuggerUrl")
                      and t.get("url", "") not in ("", "about:blank")]
        if not candidates:
            return None

        def _desc(p):
            try:
                return json.loads(p.get("description", "{}"))
            except (json.JSONDecodeError, TypeError):
                return {}

        # 优先级 1: visible + attached + 非空（已渲染内容，最可靠）
        for p in candidates:
            d = _desc(p)
            if d.get("visible") and d.get("attached") and d.get("empty") is False:
                self._last_target = p
                return p
        # 优先级 2: visible + attached（empty 状态未知）
        for p in candidates:
            d = _desc(p)
            if d.get("visible") and d.get("attached"):
                self._last_target = p
                return p
        # 优先级 3: 兜底——跳过 never_attached 僵尸对象，取首个真实页面
        for p in candidates:
            d = _desc(p)
            if not d.get("never_attached"):
                self._last_target = p
                return p
        self._last_target = candidates[0]
        return candidates[0]

    def describe(self) -> dict:
        """输出探针健康状态摘要，供 [DIAG] 诊断与 probe-status 命令使用。

        返回字段：
            probe_name        — 探针名
            available         — 当前是否可用
            cdp_dead_reason   — CDP 不可达原因（None=正常）
            socket            — 发现的 webview devtools socket
            port              — 本地转发端口
            page_count        — CDP 页面列表数量
            target_url        — 最近一次选中的目标页面 URL
            target_attached   — 目标页面 attached 状态
            target_visible    — 目标页面 visible 状态
            target_empty      — 目标页面 empty 状态
            dom_text_lines    — 最近一次读取的 DOM 文本行数（0 表示未读到/空 DOM）
        """
        page_count = 0
        target_url = target_attached = target_visible = target_empty = None
        dom_lines = 0
        # 先刷新 CDP 页面列表，确保 page_count / target_* 是当前快照
        # （_pick_target 会更新 _page_cache 和 _last_target）
        if self._resolved and self._port is not None:
            self._pick_target()
        if self._page_cache:
            page_count = len(self._page_cache)
        if self._last_target:
            target_url = (self._last_target.get("url") or "")[:120]
            d = {}
            try:
                d = json.loads(self._last_target.get("description", "{}"))
            except (json.JSONDecodeError, TypeError):
                pass
            target_attached = d.get("attached")
            target_visible = d.get("visible")
            target_empty = d.get("empty")
        if self._resolved and self._port is not None:
            raw = self._page_text()
            dom_lines = len([ln for ln in (raw or "").splitlines() if ln.strip()])
        try:
            from device_platform.android.probes.webview import get_cdp_dead_reason
            cdp_reason = get_cdp_dead_reason()
        except (ImportError, AttributeError):
            cdp_reason = "N/A"
        return {
            "probe_name": self.probe_name,
            "available": self.available(),
            "cdp_dead_reason": cdp_reason,
            "socket": self._socket,
            "port": self._port,
            "page_count": page_count,
            "target_url": target_url,
            "target_attached": target_attached,
            "target_visible": target_visible,
            "target_empty": target_empty,
            "dom_text_lines": dom_lines,
        }

    def _page_text(self):
        """获取页面全部可见文本，三合一策略保证跨页面通用性。

        策略优先级：
        1. document.body.innerText — 标准浏览器 API，CSS 感知，自动排除隐藏元素
           （script/style 标签内容不在 innerText 中），兼容所有 DOM 渲染结构
        2. 叶子节点 textContent 兜底 — 当 innerText 为空时（如 SVG 内文本、
           某些 Shadow DOM 场景），退回到 querySelectorAll 逐节点采集
        3. title 补充 — 页面标题通常不在 body 内，单独追加

        为什么不用 textContent 直取？
        - textContent 包含 <script> 标签内的 JS 源码，严重污染匹配
        - textContent 不感知 CSS（display:none 的文本也会返回）
        - 只取叶子节点又会漏掉非叶子节点中的文本
        """
        return self._evaluate(_JS_PAGE_TEXT)

    def _evaluate(self, expression):
        """在目标页面执行 JS 并返回字符串结果，失败返回空串。

        非可恢复性错误会标记 _CDP_DEAD_REASON，后续调用直接跳过：
        - WebSocket 超时 → 页面不可达，标记不可恢复
        - 连接被拒绝/重置 → 端口已断开，标记不可恢复
        - 无目标页面 → 所有页面已关闭，标记不可恢复
        - 一般异常 → 可能是瞬时错误，不标记（允许重试）
        """
        global _CDP_DEAD_REASON
        if not self.available():
            return ""
        target = self._pick_target()
        if not target:
            _CDP_DEAD_REASON = "no_target_page"
            return ""
        try:
            import websocket
        except ImportError:
            sys.stderr.write(
                "  ⚠️  缺少 websocket-client，WebView DOM 感知不可用"
                "（pip3 install websocket-client）\n")
            return ""
        ws = None
        try:
            ws = websocket.create_connection(target["webSocketDebuggerUrl"],
                                             timeout=_WS_TIMEOUT,
                                             suppress_origin=True)
            ws.send(json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expression, "returnByValue": True},
            }))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == 1:
                    return msg.get("result", {}).get("result", {}).get("value") or ""
        except websocket.WebSocketTimeoutException:
            _CDP_DEAD_REASON = "ws_timeout"
            sys.stderr.write(f"  ⚠️  CDP WebSocket 超时 (>{_WS_TIMEOUT}s)，标记为不可达\n")
            return ""
        except (ConnectionRefusedError, ConnectionResetError):
            _CDP_DEAD_REASON = "ws_refused"
            sys.stderr.write("  ⚠️  CDP WebSocket 连接被拒绝，标记为不可达\n")
            return ""
        except Exception as e:
            sys.stderr.write(f"  ⚠️  CDP Runtime.evaluate 失败: {e}\n")
            return ""
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

    @staticmethod
    def _http_json(url):
        try:
            with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT) as resp:
                return json.load(resp)
        except Exception:
            return None