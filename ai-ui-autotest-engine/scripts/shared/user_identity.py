#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""当前用户身份（MIS）解析 —— 资源 MIS 的"默认来源"（用户级、不联网）。

资源 MIS（设备归属 / 报告 user_id）在多数场景下就是"跑测试的人自己"。把它做成
"可自动派生"能避免每轮让用户手输（本 workspace 的 intake 会随 post-clean 删除，
不自动派生则每轮都要重问）。

【为什么放在 shared/ 而不是 platform.auth】
`shared` 是最底层、只依赖自身；而身份解析有两个消费方：
  · 信息收集 provider（`provisioning.questions.providers.env`）—— 派生 resource_mis 题；
  · 运行时解析（`shared.case_utils.resolve_mis`）—— intake 缺失时的兜底默认值。
若把实现留在 `platform.auth`，`shared.case_utils` 消费它就会构成
`shared → platform` 的跳层/反向依赖（架构守卫规则 7 直接失败）。因此实现收敛到
本模块，`platform.auth` 不再承载身份解析。

只读本机已有信息（环境变量 / SSO Cookie 缓存文件 / git 配置），**不触发任何网络
或授权**；任一环节拿不到或校验不过就返回 ""，由调用方回退到"提问"——宁可问，
也不填错 user_id。
"""
import base64
import os
import re
import subprocess

from shared.json_utils import read_json
from shared.paths import appmock_cookie_path

# 美团 MIS 形态（保守）：小写字母开头，小写字母/数字/下划线
_MIS_RE = re.compile(r"^[a-z][a-z0-9_]{2,31}$")

# 进程内 memo（questions() 每命令会被调用多次，避免重复解析/起子进程）
_MIS_MEMO = {"value": None}


def _mis_from_sso_cookie() -> str:
    """从缓存的 AppMock SSO Cookie 中解析当前用户 MIS（仅读缓存文件，不取票）。

    Cookie 形如 `<client>_ssoid=<token>`，token 再以 `**` 分片，最后一段是
    base64url 编码的身份块：`员工号,MIS,姓名,邮箱,…`。

    强校验（避免格式变化导致**静默填错**）：MIS 形态合法 **且** 邮箱 local part == MIS。
    """
    try:
        cookie = (read_json(appmock_cookie_path(), default={}) or {}).get("cookie") or ""
    except Exception:
        cookie = ""
    if not cookie or "_ssoid=" not in cookie:
        return ""

    token = cookie.split("_ssoid=", 1)[1]
    segment = token.split("**")[-1]
    try:
        decoded = base64.urlsafe_b64decode(
            segment + "=" * (-len(segment) % 4)).decode("utf-8", "replace")
    except Exception:
        return ""

    fields = decoded.split(",")
    if len(fields) < 4:
        return ""
    mis, email = fields[1].strip(), fields[3].strip()
    if not _MIS_RE.match(mis):
        return ""
    local, _, domain = email.lower().partition("@")
    if domain != "meituan.com" or local != mis.lower():
        return ""
    return mis


def _mis_from_git_email() -> str:
    """从 `git config user.email` 解析 MIS（local part；要求 @meituan.com）。"""
    try:
        r = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True, text=True, timeout=5,
        )
        email = (r.stdout or "").strip()
    except Exception:
        return ""
    local, _, domain = email.lower().partition("@")
    if domain != "meituan.com" or not _MIS_RE.match(local):
        return ""
    return local


def current_user_mis() -> str:
    """当前用户的 MIS（资源 MIS 的默认来源）；无法确定时返回 ""。

    优先级：`HOTEL_UI_MIS`（显式，原样采信）> 缓存的 SSO 身份 > `git config user.email`。
    进程内 memoize；不联网。
    """
    if _MIS_MEMO["value"] is not None:
        return _MIS_MEMO["value"]

    mis = os.environ.get("HOTEL_UI_MIS", "").strip() or _mis_from_sso_cookie() or _mis_from_git_email()
    _MIS_MEMO["value"] = mis
    return mis
