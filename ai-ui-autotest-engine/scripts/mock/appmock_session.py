#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 浏览器 Session 接口代理 —— 域名映射、泳道、环境切换等。

/appmock/ 前缀的接口（env/set、swimline/*、urlMapping/*）不支持 SSO 应用身份
Token，需要浏览器 Session Cookie。本模块统一处理认证：
  1. 通过 sso-auth-cli 获取 AppMock 的用户级 Cookie
  2. 将 Cookie 作为 ssoCookie 参数传给 yooz 代理
  3. yooz 代理用 _resolveSessionCookie 优先使用传入的 Cookie

这样所有请求统一走 yooz 代理域名，保持域名一致。

依赖：
  sso-auth-cli（Rust 版）— 系统级安装，通过 CIBA/OIDC 获取 SSO Cookie
  requests（Python）— HTTP 请求
"""
import argparse
import base64 as _b64
import json
import os
import subprocess
from core.util.paths import CONFIG_DIR, ensure_dirs
from core.util.case_utils import resolve_mis

from infra.ssl_helper import get_verify_flag
from infra.appmock_auth import _get_appmock_cookie, _get_cookie_or_warn
from mock.appmock_rules import extract_mock_id

# yooz 代理基址（统一域名，可通过环境变量 YOOZ_BASE_OVERRIDE 指向本地实例）
_YOOZ_DEFAULT = _b64.b64decode("aHR0cHM6Ly95b296LnNhbmt1YWkuY29t").decode() + "/node/api/data/monitor/appmock"
_YOOZ_BASE = os.environ.get("YOOZ_BASE_OVERRIDE", _YOOZ_DEFAULT)

def _proxy_call(method, path, *, params=None, json_body=None, timeout=15):
    """统一的 yooz 代理请求：获取 cookie → 发请求 → 校验 code==0 → 返回 data 或 None。"""
    import requests as _req

    cookie = _get_cookie_or_warn()
    if not cookie:
        return None
    if params is not None:
        params = dict(params, ssoCookie=cookie)
    if json_body is not None:
        json_body = dict(json_body, ssoCookie=cookie)
    try:
        resp = _req.request(method, f"{_YOOZ_BASE}{path}", params=params, json=json_body, timeout=timeout, verify=get_verify_flag())
        data = resp.json().get("data", {})
        if data.get("code") == 0:
            return data.get("data", {})
        print(f"PROXY FAIL {path}: {data}")
    except Exception as e:
        print(f"PROXY ERROR {path}: {e}")
    return None

# ═══════════════════════════════════════════════════════════════════
# 域名映射
# ═══════════════════════════════════════════════════════════════════

def url_mapping_list() -> list:
    """查询当前用户的所有域名映射。"""
    result = _proxy_call("GET", "/url-mapping/list", params={"type": "mine"})
    if result is not None:
        mappings = result.get("mappings", [])
        print(f"URL_MAPPING LIST OK: {len(mappings)} mapping(s)")
        return mappings
    return []

def url_mapping_update(url: str, title: str, mis: str = None,
                       beta_url: str = "", ppe_url: str = "",
                       sp_env: str = "beta") -> dict:
    """新增或更新域名映射。

    Args:
        sp_env: 域名映射的激活环境。"beta" 表示激活映射（将请求转发到 betaUrl），
                "close" 表示关闭映射。默认 "beta"（创建即激活）。
                B1（有泳道）场景可传 None 跳过此字段，由 swimline-switch 控制激活。
    """
    if not url or not title:
        print("URL_MAPPING UPDATE: url 和 title 不能为空")
        return {}
    if not beta_url and not ppe_url:
        print("URL_MAPPING UPDATE: betaUrl 和 ppeUrl 至少需要一个")
        return {}

    if not mis:
        mis = resolve_mis()
    if not mis:
        print("URL_MAPPING UPDATE: 无法确定 MIS 号")
        return {}

    body = {"user": mis, "url": url, "title": title}
    if beta_url:
        body["betaUrl"] = beta_url
    if ppe_url:
        body["ppeUrl"] = ppe_url
    if sp_env:
        body["spEnv"] = sp_env

    result = _proxy_call("POST", "/url-mapping/update", json_body=body)
    if result is not None:
        print(f"URL_MAPPING UPDATE OK: url={url} beta={beta_url} ppe={ppe_url}")
        return {"action": "updated", "url": url, "betaUrl": beta_url, "ppeUrl": ppe_url}
    return {}

def url_mapping_delete(mapping_id: int) -> bool:
    """删除指定域名映射。"""
    result = _proxy_call("GET", "/url-mapping/delete", params={"id": str(mapping_id)})
    if result is not None:
        print(f"URL_MAPPING DELETE OK: id={mapping_id}")
        return True
    return False

def url_mapping_find(url_keyword: str) -> list:
    """按 URL 关键词搜索已有映射（本地过滤）。"""
    mappings = url_mapping_list()
    if not url_keyword:
        return mappings

    kw = url_keyword.lower()
    matched = [m for m in mappings if kw in (m.get("url", "") or "").lower()]
    print(f"URL_MAPPING FIND: {len(matched)}/{len(mappings)} matched keyword='{url_keyword}'")
    return matched

def url_mapping_set_env(url_id: int, env: str = "beta") -> bool:
    """激活/关闭域名映射（设置 spEnv 字段）。

    通过 yooz 代理调用 AppMock 原生 API /appmock/userUrlConfig/updateConfig。

    Args:
        url_id: 域名映射 ID
        env: 目标环境。"beta" 激活映射（转发到 betaUrl），
             "close" 关闭映射（恢复原样）。

    Returns:
        True 成功，False 失败
    """
    result = _proxy_call("GET", "/url-mapping/set-env", params={"urlId": str(url_id), "env": env})
    if result is not None:
        print(f"URL_MAPPING SET ENV OK: id={url_id} env={env}")
        return True
    return False

# ═══════════════════════════════════════════════════════════════════
# 环境切换（yooz 代理 + ssoCookie）
# ═══════════════════════════════════════════════════════════════════

def session_env_set(env: str) -> bool:
    """通过 yooz 代理切换 AppMock 代理环境（需浏览器 Session）。

    注意：此函数仅在 imeituan CLI 不可用时作为 fallback。
    正常情况下 appmock_swimlane.py 的 appmock_env_set() 会优先走 CLI。
    """
    result = _proxy_call("POST", "/env/set", json_body={"env": env})
    if result is not None:
        print(f"SESSION ENV SET OK: env={env}")
        return True
    return False

# ═══════════════════════════════════════════════════════════════════
# 泳道管理（yooz 代理 + ssoCookie）
# ═══════════════════════════════════════════════════════════════════

def session_swimline_list(mis: str) -> list:
    """通过 yooz 代理查询泳道列表（需浏览器 Session）。"""
    result = _proxy_call("GET", "/swimline/list", params={"user": mis})
    if result is not None:
        items = result.get("items", [])
        print(f"SESSION SWIMLINE LIST OK: {len(items)} rule(s)")
        return items
    return []

def session_swimline_add(url_pattern: str, lane_name: str, mis: str) -> dict:
    """通过 yooz 代理新增泳道规则（需浏览器 Session）。"""
    result = _proxy_call("POST", "/swimline/add",
                         json_body={"user": mis, "url": url_pattern, "configs": lane_name})
    if result is not None:
        print(f"SESSION SWIMLINE ADD OK: {result}")
        return result
    return {}

def session_swimline_switch(rule_id, mis: str = None, user_config: str = None) -> bool:
    """通过 yooz 代理切换泳道（需浏览器 Session）。

    Args:
        rule_id: 泳道规则 ID
        mis: MIS 号（用于自动查找 userConfig）
        user_config: 泳道配置名称（如不传，则从泳道列表中按 rule_id 查找）
    """
    # 如果没有显式传入 userConfig，尝试从泳道列表查找
    if not user_config:
        lanes = session_swimline_list(mis)
        if isinstance(lanes, list):
            for lane in lanes:
                if extract_mock_id(lane) == str(rule_id or "").strip():
                    user_config = lane.get("userConfig", lane.get("name", ""))
                    break
    if not user_config:
        user_config = ""  # 有些场景不需要 userConfig，让服务端处理

    result = _proxy_call("POST", "/swimline/switch",
                         json_body={"id": int(rule_id), "userConfig": user_config})
    if result is not None:
        print(f"SESSION SWIMLINE SWITCH OK: ruleId={rule_id}")
        return True
    return False

def session_swimline_off(rule_id=None) -> bool:
    """通过 yooz 代理关闭泳道并切回线上（需浏览器 Session）。

    Args:
        rule_id: 可选泳道 ID，传入时清空该泳道的 userConfig
    """
    body = {}
    if rule_id:
        body["id"] = int(rule_id)

    result = _proxy_call("POST", "/swimline/off", json_body=body)
    if result is not None:
        print("SESSION SWIMLINE OFF OK")
        return True
    return False

def session_swimline_remove(rule_id) -> bool:
    """通过 yooz 代理删除泳道规则（需浏览器 Session）。

    Args:
        rule_id: 泳道规则 ID
    """
    result = _proxy_call("POST", "/swimline/remove", json_body={"id": int(rule_id)})
    if result is not None:
        print(f"SESSION SWIMLINE REMOVE OK: id={rule_id}")
        return True
    return False


