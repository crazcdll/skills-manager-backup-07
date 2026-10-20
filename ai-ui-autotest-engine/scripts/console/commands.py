#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`console` 命令：统一控制台服务的 CLI 入口（workspace-free）。

子命令：
  ensure   幂等启动（已启动则直接复用并打印地址）—— **其他会话在此跳过**
  up       同 ensure（显式语义）
  status   查看运行状态
  url      仅打印访问地址
  down     停止服务（一般不需要；服务设计为常驻）

访问地址**无需携带 token**：服务只监听 127.0.0.1（本机自用），页面打开时由服务端注入全局 token。
"""
import json
import sys

from console import service


def _addr(info) -> str:
    """控制台访问地址（本机）。"""
    info = info or {}
    return (info.get("url") or f"http://127.0.0.1:{info.get('port')}").rstrip("/") + "/"


def banner_link():
    """确保服务在线并返回一行「可直接访问」的控制台地址（best-effort，失败返回空串）。"""
    try:
        info = service.ensure()
    except Exception:
        return ""
    if not info or not info.get("ok"):
        return ""
    return _addr(info)


def cmd_console(args):
    action = (getattr(args, "console_subcmd", None) or "ensure").strip()

    if action in ("ensure", "up"):
        info = service.ensure()
        if not info.get("ok"):
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 1
        verb = "已启动" if info.get("started") else "已在运行（跨会话复用）"
        print(f"🖥  AI UI 测试控制台 {verb}")
        print(f"   打开  : {_addr(info)}")
        print(f"   端口  : {info.get('port')}")
        print(f"   PID   : {info.get('pid')}")
        return 0

    if action == "status":
        info = service.status()
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0 if info.get("running") else 1

    if action == "url":
        info = service.status()
        if not info.get("running"):
            info = service.ensure()
        if not info.get("ok"):
            print(json.dumps(info, ensure_ascii=False))
            return 1
        print(_addr(info))
        return 0

    if action == "down":
        print(json.dumps(service.stop(), ensure_ascii=False))
        return 0

    print(f"未知子命令: {action}（可用：ensure/up/status/url/down）", file=sys.stderr)
    return 2
