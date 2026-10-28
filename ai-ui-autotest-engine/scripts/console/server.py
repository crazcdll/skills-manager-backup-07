#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""控制台服务进程：HTTP + SSE + MJPEG（Python 标准库，无第三方依赖）。

鉴权模型（简单）：
  · 一个**全局 token**（持久化于机器级 console 目录，重启不变）；
  · 页面打开时由服务端**注入**该 token（`__CONSOLE_TOKEN__` 占位符），
    因此浏览器直接访问 `http://127.0.0.1:<port>/` 即可用，URL 无需带 token；
  · 其余接口（/api/*、/events、/device/*/mjpeg）统一校验该全局 token。

只监听 `127.0.0.1`——自用，不做局域网共享 / HTTPS。

后台线程：
  · discovery ：周期扫描 run / device 快照（同时维护 run→device 索引）
  · tailer    ：增量 tail run-events.jsonl / steps.jsonl / 各 workspace 的 console-ingest.jsonl 并广播
  · heartbeat ：周期重写服务名片与 token 文件（误删可自愈，只写机器级目录）
"""
import argparse
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402

from console import aggregator, config, discovery  # noqa: E402
from console.preview.manager import MANAGER, resolve_udid  # noqa: E402
from console.store import HUB  # noqa: E402
from console.tailer import Tailer  # noqa: E402
from shared.json_utils import write_json_atomic  # noqa: E402
from shared.paths import (  # noqa: E402
    console_dir, console_server_json, console_singleton_lock_path, console_token_path,
    iter_console_ingest_paths,
)

WEB_DIR = os.path.join(_HERE, "web")
TOKEN = ""
_STAGE_STATE = {}   # (task, run, stage_id) -> status
TOKEN_PLACEHOLDER = b"__CONSOLE_TOKEN_VALUE__"
# raw 遥测合并上限：单事件最多保留的行数与单行字符数（超出截断并标注）
_RAW_MAX_LINES = 40
_RAW_MAX_LINE_CHARS = 600


# ═══════════════════════════════════════════════════════════════════
# 后台线程
# ═══════════════════════════════════════════════════════════════════

def _discovery_loop():
    """周期刷新快照与「会话(task)→设备」索引。

    两类数据的成本差一个数量级，所以拆成两个节奏：
      · run / session —— 纯本地文件，`DISCOVERY_INTERVAL_SEC`（2s）；
      · 设备池 —— 每轮要打 2 次 `/device/list`（HTTP + 两次 DB 聚合 + 可能的过期回收），
        按 `DEVICE_DISCOVERY_INTERVAL_SEC`（10s）刷新。面板最多晚 10s 看到别人领机。

    设备刷新失败（服务端抖动）时**保留上一轮快照**：设备面板不该因为一次网络超时闪空。
    """
    devices = []
    devices_ready_at = 0.0
    while True:
        try:
            runs = discovery.discover_runs()
            sessions = discovery.discover_sessions(runs)
            now = time.time()
            if now >= devices_ready_at:
                try:
                    fresh = discovery.discover_devices(runs)
                    for d in fresh:
                        # scrcpy 认的 udid 未必等于 device_serial（那是设备内部网卡地址）→ 查一次真实值
                        d["scrcpy_udid"] = resolve_udid(
                            d.get("scrcpy_url", ""), d.get("adb_address", ""))
                    devices = fresh
                except Exception as e:  # noqa: BLE001 —— 后端抖动：沿用旧快照
                    sys.stderr.write(f"[console] 设备快照刷新失败（沿用上一轮）: {e}\n")
                devices_ready_at = now + config.DEVICE_DISCOVERY_INTERVAL_SEC
            HUB.set_snapshot(runs, devices, sessions)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[console] 快照刷新失败: {e}\n")
        time.sleep(config.DISCOVERY_INTERVAL_SEC)


def _publish_stages(runs):
    """SOP 阶段状态变化 → 事件（只在状态变更时发，避免刷屏）。"""
    for r in runs:
        # 设备归属统一用 run→设备索引（= 设备列表里的 serial），避免 sandbox 的
        # 「adb 地址」与「租约键 sandboxId」不一致导致前端按设备筛选对不上。
        device = HUB.device_of_session(r["task"]) or r.get("device_serial", "")
        for st in r.get("stages", []):
            key = (r["task"], r["run"], st.get("id"))
            if _STAGE_STATE.get(key) != st.get("status"):
                _STAGE_STATE[key] = st.get("status")
                HUB.publish(aggregator.stage_event(r["task"], r["run"], device, st))


def _tail_loop():
    """增量消费三个日志源并广播为统一 UI 事件。"""
    tl = Tailer()
    ingest_tl = Tailer()
    while True:
        try:
            runs = HUB.get_runs()
            for source, task, run, case_index, rec, device in tl.poll(runs):
                dev = HUB.device_of_session(task) or device   # 统一设备归属（按会话）
                if source == "step":
                    HUB.publish(aggregator.step_event(task, run, case_index, dev, rec))
                else:
                    HUB.publish(aggregator.audit_event(task, run, dev, rec))
            _publish_stages(runs)
            # raw 遥测（CLI stdout/stderr）单条量大且密集：按 (task,run,cmd,stream)
            # 合并成一个多行事件后再发布，避免刷爆 SSE 与前端渲染。
            slots, order = {}, []
            for ipath in iter_console_ingest_paths():
                for rec in ingest_tl.poll_file(ipath):
                    key = (rec.get("task", ""), rec.get("run", ""),
                           rec.get("cmd", ""), rec.get("stream", "stdout"))
                    slot = slots.get(key)
                    if slot is None:
                        slot = {"task": key[0], "run": key[1],
                                "cmd": key[2], "stream": key[3], "lines": []}
                        slots[key] = slot
                        order.append(slot)
                    slot["lines"].append(rec.get("line", ""))
            for slot in order:
                lines = slot["lines"]
                omitted = 0
                if len(lines) > _RAW_MAX_LINES:
                    omitted = len(lines) - _RAW_MAX_LINES
                    lines = lines[:_RAW_MAX_LINES]
                clipped = [(ln[:_RAW_MAX_LINE_CHARS] + "…") if len(ln) > _RAW_MAX_LINE_CHARS else ln
                           for ln in lines]
                text = "\n".join(clipped)
                if omitted:
                    text += f"\n…（已省略 {omitted} 行）"
                HUB.publish(aggregator.raw_event(
                    slot["task"], slot["run"], slot["cmd"], slot["stream"],
                    text, level="debug",
                    device=HUB.device_of_session(slot["task"])))
        except Exception:  # noqa: BLE001
            pass
        time.sleep(config.TAIL_INTERVAL_SEC)


def _heartbeat_loop(info):
    """周期重写服务名片与 token 文件（写到**机器级** console 目录，误删可自愈）。

    ⚠️ home 固定为 `~/.local/share/ai-ui-autotest-engine/console/`，**不再**写回
    Skill 目录：否则 Skill 每多一份副本（.catpaw / .claude / 各项目）就会多出一个
    `.console`，而且删掉后 15s 就被本心跳重建，表现为「删不掉的幽灵目录」。
    """
    while True:
        time.sleep(config.SERVER_HEARTBEAT_SEC)
        try:
            os.makedirs(os.path.dirname(console_server_json()), exist_ok=True)
            write_json_atomic(console_server_json(), info)
            tok = info.get("token") or ""
            if tok:
                with open(console_token_path(), "w", encoding="utf-8") as f:
                    f.write(tok)
        except Exception:  # noqa: BLE001
            pass


# ═══════════════════════════════════════════════════════════════════
# HTTP 处理
# ═══════════════════════════════════════════════════════════════════

_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "CatpawConsole/1.0"

    def log_message(self, *args):  # 静音
        pass

    # ── 工具 ─────────────────────────────────────────────
    def _query(self):
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    def _token_ok(self, q):
        tok = (self.headers.get("X-Console-Token")
               or (q.get("token", [None])[0]) or "").strip()
        return bool(TOKEN) and tok == TOKEN

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _static(self, name, ctype):
        try:
            with open(os.path.join(WEB_DIR, name), "rb") as f:
                data = f.read()
        except OSError:
            return self._json({"error": "not found"}, 404)
        # 页面注入全局 token：打开 http://<本机IP>:<port>/ 即用，URL 无需带 token
        if name == "index.html":
            data = data.replace(TOKEN_PLACEHOLDER, TOKEN.encode("utf-8"))
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _static_font(self, name):
        """字体文件（供 @font-face 引用）。只接受纯文件名 + .woff2，防路径穿越。"""
        safe = os.path.basename(name or "")
        if safe != name or not safe.endswith(".woff2"):
            return self._json({"error": "not found"}, 404)
        try:
            with open(os.path.join(WEB_DIR, "fonts", safe), "rb") as f:
                data = f.read()
        except OSError:
            return self._json({"error": "not found"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", "font/woff2")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ── GET 路由 ─────────────────────────────────────────
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path, q = parsed.path, self._query()

        if path == "/healthz":
            # 暴露 home：调用方据此识别“不是本机实例”（home 缺失/不匹配）并回收，
            # 避免多个副本各自拉起常驻服务、或旧实例继续写自己的状态目录
            return self._json({"ok": True, "service": "catpaw-console",
                               "version": config.CONSOLE_VERSION, "pid": os.getpid(),
                               "home": console_dir()})
        if path in _STATIC:
            return self._static(*_STATIC[path])
        # 字体（@font-face 引用，CSS 请求不携带 token → 免鉴权）
        if path.startswith("/fonts/"):
            return self._static_font(path[len("/fonts/"):])

        # scrcpy 页面反代（无需 token）：转发上游内容但不携带其 CSP → 本地页面可 iframe 内嵌
        _p = [x for x in path.split("/") if x]
        if len(_p) >= 3 and _p[0] == "device" and _p[2] == "scrcpy":
            return self._scrcpy_proxy(_p[1], "/".join(_p[3:]))

        if not self._token_ok(q):
            return self._json({"error": "unauthorized"}, 401)

        if path == "/api/overview":
            return self._json(self._overview())
        if path == "/api/runs":
            return self._json({"runs": HUB.get_runs()})
        if path == "/api/devices":
            return self._json({"devices": HUB.get_devices()})
        if path == "/api/sessions":
            return self._json({"sessions": HUB.get_sessions()})
        if path == "/api/history":
            return self._json({"history": discovery.history()})
        if path == "/api/events":
            since = int((q.get("since", ["0"])[0]) or 0)
            return self._json({"events": HUB.snapshot(since=since),
                               "seq": HUB.latest_seq()})
        if path == "/events":
            return self._sse()

        parts = [p for p in path.split("/") if p]
        if len(parts) == 4 and parts[:2] == ["api", "runs"]:
            return self._json({"run": self._find_run(parts[2], parts[3])})
        if len(parts) == 3 and parts[0] == "device" and parts[2] == "mjpeg":
            return self._mjpeg(parts[1])
        return self._json({"error": "not found", "path": path}, 404)

    # ── API 实现 ─────────────────────────────────────────
    def _overview(self):
        devices = HUB.get_devices()
        runs = HUB.get_runs()
        sessions = HUB.get_sessions()
        return {
            "service": "catpaw-console",
            "version": config.CONSOLE_VERSION,
            "uptime_sec": int(time.time() - HUB.started_at),
            "runs_total": len(runs),
            "runs_active": sum(1 for r in runs if r.get("status") == "running"),
            "sessions_total": len(sessions),
            "sessions_active": sum(1 for s in sessions if s.get("status") == "running"),
            "devices_total": len(devices),
            "devices_active": sum(1 for d in devices if d.get("status") == "active"),
            "events": HUB.stats["events"],
            "seq": HUB.latest_seq(),
        }

    def _find_run(self, task, run):
        for r in HUB.get_runs():
            if r.get("task") == task and r.get("run") == run:
                return r
        return None

    # ── SSE ──────────────────────────────────────────────
    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = HUB.subscribe()
        try:
            since = int(self._query().get("since", ["0"])[0] or 0)
            for ev in HUB.snapshot(since=since, limit=1500):
                self._sse_send(ev)
            while True:
                try:
                    self._sse_send(q.get(timeout=config.SSE_HEARTBEAT_SEC))
                except Exception:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            HUB.unsubscribe(q)

    def _sse_send(self, ev):
        self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8"))
        self.wfile.flush()

    # ── MJPEG ────────────────────────────────────────────
    def _mjpeg(self, serial):
        device = next((d for d in HUB.get_devices() if d.get("serial") == serial), None)
        if not device:
            return self._json({"error": "unknown device"}, 404)
        stream = MANAGER.stream(device)
        if stream is None:
            return self._json({"error": "device has no frame stream (scrcpy url only)"}, 409)
        boundary = config.MJPEG_BOUNDARY
        self.send_response(200)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={boundary}")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        b = boundary.encode()
        try:
            for mime, payload in stream:
                self.wfile.write(b"--" + b + b"\r\n")
                self.wfile.write(f"Content-Type: {mime}\r\n".encode())
                self.wfile.write(f"Content-Length: {len(payload)}\r\n\r\n".encode())
                self.wfile.write(payload)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


    # ── scrcpy 页面反代 ──────────────────────────────────
    def _scrcpy_proxy(self, serial, rest):
        """把设备的 scrcpy 网页反代到本服务 origin。

        为什么要反代：上游页面带 `Content-Security-Policy: … frame-ancestors 'self'
        https://*.sankuai.com …`，白名单不含 127.0.0.1，浏览器会拒绝 iframe 渲染。
        本方法只透传 `Content-Type` 与 body（**不复制上游 CSP / X-Frame-Options**），
        于是页面以“同源”身份被本地控制台内嵌，且其内部相对资源（bundle.js/main.css）
        也经由本代理加载。
        """
        device = next((d for d in HUB.get_devices() if d.get("serial") == serial), None)
        base = (device or {}).get("scrcpy_url", "")
        if not base:
            return self._json({"error": "no scrcpy url for device"}, 404)
        url = base.rstrip("/") + "/" + rest.lstrip("/")
        qs = urllib.parse.urlparse(self.path).query
        if qs:
            url += ("&" if "?" in url else "?") + qs
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "catpaw-console"})
            with urllib.request.urlopen(req, timeout=10) as r:
                body = r.read()
                ctype = r.headers.get("Content-Type", "application/octet-stream")
                code = getattr(r, "status", 200) or 200
        except Exception as e:  # noqa: BLE001
            return self._json({"error": f"scrcpy proxy failed: {e}"}, 502)
        # 页面是 text/html 时注入样式（同源反代才有机会注入）：
        #   1) 深色背景 + 去 margin（原页面浅色，嵌深色控制台很违和）；
        #   2) 隐藏 ws-scrcpy 自带控制侧栏 `.control-buttons-list`（工具栏）；
        #   3) `.device-view` / `.video` 原本 float:right（画面被推右且留白），改为居中自适应。
        if ctype.startswith("text/html"):
            inject = (
                b"<style>"
                b"html,body{margin:0!important;padding:0!important;height:100%;"
                b"background:#04070c!important;overflow:hidden!important}"
                b"body{display:flex!important;align-items:center!important;justify-content:center!important}"
                b".control-buttons-list{display:none!important}"
                b".device-view{float:none!important;display:block!important;margin:0 auto!important;"
                b"max-width:100%;max-height:100%}"
                b".video{float:none!important;display:block!important;margin:0 auto!important;"
                b"max-width:100%!important;max-height:100%!important}"
                b"video,canvas{display:block!important;margin:auto!important;"
                b"max-width:100%!important;max-height:100%!important;object-fit:contain!important}"
                b"</style>"
            )
            if b"</head>" in body:
                body = body.replace(b"</head>", inject + b"</head>", 1)
            else:
                body = inject + body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


# ═══════════════════════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════════════════════

class _Server(ThreadingHTTPServer):
    """只做一件事：把客户端断连 / 协议错误静音，避免刷无意义堆栈。"""

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionError, OSError)):
            return
        super().handle_error(request, client_address)


def _bind_server(start_port, scan, host):
    last = None
    for p in range(start_port, start_port + scan):
        try:
            return _Server((host, p), Handler), p
        except OSError as e:
            last = e
    raise SystemExit(f"无法绑定端口 {start_port}..{start_port + scan}: {last}")


_SINGLETON_FH = None   # 进程级持有（防 GC 释放锁）


def _acquire_singleton() -> bool:
    """获取服务进程级单例锁；拿不到说明已有实例在跑 → 本进程应退出（不报错）。

    锁由本进程**持有至退出**（OS 在进程结束时自动释放）——单例的硬保证在此层，
    与 `server.json` 是否新鲜无关。
    """
    global _SINGLETON_FH
    import fcntl
    path = console_singleton_lock_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = open(path, "w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return False
    _SINGLETON_FH = fh
    return True


def main():
    global TOKEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--port", type=int, default=config.DEFAULT_PORT)
    ap.add_argument("--port-range", type=int, default=config.PORT_SCAN_RANGE)
    ap.add_argument("--host", default=config.BIND_HOST, help="监听地址（默认仅本机）")
    args = ap.parse_args()
    TOKEN = args.token

    if not _acquire_singleton():
        sys.stderr.write("[console] 已有实例在运行，本进程退出（单例）\n")
        sys.stderr.flush()
        return

    httpd, port = _bind_server(args.port, args.port_range, args.host)
    url = f"http://127.0.0.1:{port}"
    info = {
        "version": config.CONSOLE_VERSION,
        "pid": os.getpid(),
        "host": args.host,
        "port": port,
        "url": url,
        "token": TOKEN,
        "home": console_dir(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    write_json_atomic(console_server_json(), info)

    for fn, nm in ((_discovery_loop, "discovery"), (_tail_loop, "tailer")):
        threading.Thread(target=fn, name=nm, daemon=True).start()
    threading.Thread(target=_heartbeat_loop, args=(info,), name="heartbeat", daemon=True).start()

    sys.stderr.write(f"[console] 服务已就绪 {url}/（仅本机）\n")
    sys.stderr.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        MANAGER.stop_all()


if __name__ == "__main__":
    main()
