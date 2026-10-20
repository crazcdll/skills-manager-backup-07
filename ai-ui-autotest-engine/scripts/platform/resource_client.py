#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""虚拟 mis 池客户端 —— 经 yooz-server 中转（`/data/monitor/mis-pool/*`）。

薄封装：**只调接口，不做本地决策**（归属/占用唯一权威在平台表）。
鉴权与信封解包复用 `platform.sandbox_api`（apiKey 注入 + 双层信封拆解）。

接口语义（对应 yooz-server 路由）：
  acquire        —— 私有优先 → 公共兜底 → 池空（返回 {"pool_empty": True}）
  heartbeat      —— 刷新"最后活动时间"（6h 抢占 / 6h stale 判据，同一阈值）
  release        —— 释放（单个 / 批量）
  list           —— 查询（可筛 owner_mis / scope / status）
  release_stale  —— 一键释放长期占用（默认 6 小时）
"""
from platform.sandbox_api import api_post, api_get

_BASE = "/node/api/data/monitor/mis-pool"


def acquire_mis(real_mis: str) -> dict:
    """领取一个虚拟 mis（私有优先 → 公共兜底）。

    Returns:
        {"mis": "...", "scope": "private|public"} 或 {"pool_empty": True}
    """
    return api_post(f"{_BASE}/acquire", {"real_mis": real_mis}, timeout=20) or {}


def heartbeat_mis(mis: str) -> dict:
    """刷新该虚拟 mis 的最后活动时间。"""
    return api_post(f"{_BASE}/heartbeat", {"mis": mis}, timeout=15) or {}


def release_mis(mis_list) -> dict:
    """释放一个或多个虚拟 mis（置回 idle、清占用人）。"""
    return api_post(f"{_BASE}/release", {"mis_list": list(mis_list or [])}, timeout=15) or {}


def release_stale_mis(hours: int = 6) -> dict:
    """一键释放长期占用（最后活动 > hours 小时；默认 6h，与抢占阈值一致）。"""
    return api_post(f"{_BASE}/release-stale", {"hours": hours}, timeout=20) or {}


def list_mis(owner_mis: str = None, scope: str = None, status: str = None) -> dict:
    """查询虚拟 mis 池（默认按最后活动倒序）。"""
    params = {}
    if owner_mis:
        params["owner_mis"] = owner_mis
    if scope:
        params["scope"] = scope
    if status:
        params["status"] = status
    return api_get(f"{_BASE}/list", params, timeout=20) or {}
