#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""虚拟 mis 池命令 —— 领取 / 查看 / 释放 / 一键释放长期占用。

作用域与身份：
  · 领取用 **resource_mis**（真实 mis）→ 平台按 `owner_mis` 私有优先发放；
  · 领取结果写入 workspace 级 `intake.mock_domain`（AppMock 工作域）；
  · 释放用 **mock_domain**（本 workspace 当前持有的虚拟 mis）。

命令级心跳（`maybe_heartbeat_mis`）在 `cli.py::_heartbeat_lease` 内被调用，
按时间限流（默认 30min），避免每条命令一次网络请求。
"""
import json
import os
import time

from shared.case_utils import resolve_mis, resolve_mock_domain, set_mock_domain
from shared.errors import UsageError, MockError
from shared.paths import mis_heartbeat_marker_path
from platform.resource_client import (
    acquire_mis, heartbeat_mis, release_mis, release_stale_mis, list_mis,
)

# 命令级心跳的最小间隔（秒）——测试不会连续 6h，30min 足够保活
_HEARTBEAT_INTERVAL_SEC = 1800


def cmd_mis_acquire(args):
    """领取一个虚拟 mis → 写 intake.mock_domain。"""
    real_mis = (getattr(args, "mis", "") or "").strip() or resolve_mis()
    if not real_mis:
        raise UsageError(
            "mis acquire 需要真实 mis（resource_mis）：请先 set-mis，或在 intake 提供 resource_mis"
        )
    data = acquire_mis(real_mis)
    if data.get("pool_empty"):
        raise MockError("虚拟 mis 池已空（私有 + 公共均无空闲）—— 请到平台注册/释放后重试")
    md = data.get("mis")
    if not md:
        raise MockError(f"mis acquire 失败：{data}")
    set_mock_domain(md)
    print(json.dumps({"ok": True, "mis": md, "scope": data.get("scope")}, ensure_ascii=False))


def cmd_mis_status(args):
    """查看虚拟 mis 池（默认只看本人私有；`--pool` 看全池）。"""
    owner = None if getattr(args, "pool", False) else (resolve_mis() or None)
    data = list_mis(owner_mis=owner)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_mis_release(args):
    """释放本 workspace 当前持有的虚拟 mis。"""
    md = resolve_mock_domain()
    if not md:
        raise UsageError("mis release 需要 mock_domain：本 workspace 未领取虚拟 mis")
    res = release_mis([md])
    print(json.dumps({"ok": True, "mis": md, "released": res.get("released", 0)}, ensure_ascii=False))


def cmd_mis_release_stale(args):
    """一键释放长期占用（最后活动 > N 小时，默认 6，与 6h 抢占阈值一致）。"""
    res = release_stale_mis(getattr(args, "hours", 6) or 6)
    print(json.dumps({"ok": True, "count": res.get("count", 0)}, ensure_ascii=False))


def cmd_mis(args):
    """`mis` 子命令分发。"""
    handlers = {
        "acquire": cmd_mis_acquire,
        "status": cmd_mis_status,
        "release": cmd_mis_release,
        "release-stale": cmd_mis_release_stale,
    }
    sub = args.mis_subcmd
    handler = handlers.get(sub)
    if handler is None:
        raise UsageError(f"未知 mis 子命令 '{sub}'")
    return handler(args)


def maybe_heartbeat_mis(mock_domain: str, interval: int = _HEARTBEAT_INTERVAL_SEC):
    """限流心跳：距上次一次超过 interval 才真正调接口；成功后才写标记（失败下次重试）。

    心跳是网络调用，**不做**每命令一次（会拖慢每条命令）；30min 一次足以在 6h 抢占阈值内保活。
    """
    if not mock_domain:
        return
    marker = mis_heartbeat_marker_path()
    now = time.time()
    try:
        if os.path.isfile(marker):
            with open(marker, encoding="utf-8") as f:
                last = float((f.read() or "0").strip() or 0)
            if now - last < interval:
                return
    except (OSError, ValueError):
        pass
    heartbeat_mis(mock_domain)
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as f:
            f.write(str(now))
    except OSError:
        pass
