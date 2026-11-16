#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""线上测试身份下发（经 yooz-server）。

    GET {YOOZ_BASE}/node/api/data/monitor/test-identity/query
    → { uid, secret, region }

服务端用中性字段名下发（`uid` 账号 / `secret` 口令 / `region` 国家码），
本模块负责翻译成引擎内部的 `{account, password, country_code}`，下游无感知。

约定：
  · 不落盘、不设 TTL —— 每次运行首次解析凭证时实时查一次（用户显式提供则不查）；
  · 接口失败/未配置由调用方决定降级策略（见 `provisioning/credentials.py`）。
"""
from aitest.integrations.sandbox_api import api_get

_PATH = "/node/api/data/monitor/test-identity/query"


def fetch_online_credential(timeout: int = 8) -> dict:
    """返回 `{account, password, country_code}`；字段不全时返回空 dict。

    Raises:
        platform.sandbox_api.SandboxApiError: 网络/HTTP/鉴权失败（由调用方兜底）。
    """
    data = api_get(_PATH, {}, timeout=timeout) or {}
    if not isinstance(data, dict):
        return {}
    account = str(data.get("uid") or "").strip()
    password = data.get("secret") or ""
    country_code = str(data.get("region") or "").strip()
    if not account or not password or not country_code:
        return {}
    return {
        "account": account,
        "password": str(password),
        "country_code": country_code,
    }
