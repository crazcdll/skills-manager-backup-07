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
import base64 as _b64
import os

from shared.case_utils import resolve_mock_domain

from platform.ssl_helper import get_verify_flag
from platform.auth import _get_cookie_or_warn
from platform.appmock.rules import extract_mock_id

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
#
# 全部走 yooz 代理 → 上游 appmockapi/urlmapping/*.api 家族，按 userDomain 隔离：
#   list   → GET  getUserUrlMapping.api?userDomain
#   add    → POST addUserUrlMapping.api      （url 重复会失败）
#   update → POST updateUserUrlMapping.api   （**必须带 url**，上游校验「URL不能为空」）
#   delete → GET  removeUserUrlMapping.api?userDomain,id
#   set-env→ GET  updateUrlEnv.api?userDomain,id,env （激活/关闭）
#
# 注：getUserUrlMapping.api 不回读 spEnv（恒 null），无法据此程序化确认激活态；
#     激活结果以 updateUrlEnv 的调用是否成功为准（平台旧 list 才回读 spEnv）。
# ═══════════════════════════════════════════════════════════════════

def url_mapping_list(mis: str = None) -> list:
    """查询「指定工作域」的全部域名映射（按 userDomain 过滤）。

    上游 getUserUrlMapping.api 的 data 为扁平列表：
      [{id, title, url, betaUrl, ppeUrl, user, spEnv, ...}]
    """
    domain = resolve_mock_domain(mis)
    if not domain:
        print("URL_MAPPING LIST: 无法确定目标工作域 MIS")
        return []
    result = _proxy_call("GET", "/url-mapping/list", params={"userDomain": domain})
    if result is not None:
        mappings = result.get("mappings", []) or []
        print(f"URL_MAPPING LIST OK: {len(mappings)} mapping(s) domain={domain}")
        return mappings
    return []

def url_mapping_add(url: str, mis: str = None, beta_url: str = "",
                    ppe_url: str = "") -> dict:
    """新增一条域名映射（上游 addUserUrlMapping）。

    同一 userDomain 下 url 不可重复 —— 已存在时上游返回「URL不能重复」，
    调用方应先 list 查 id 并改走 url_mapping_update（或直接用 url_mapping_upsert）。
    注：上游 add/update 均不接收描述字段（title/desc 恒为 null），故不暴露。

    Args:
        url: 线上 URL（不含协议，如 mapi.dianping.com/mapi/x.bin）
        mis: 目标工作域 MIS 号
        beta_url/ppe_url: 测试/预发目标地址（带协议），至少一个

    Returns:
        {"action": "added", "id": <id>, ...}；失败返回 {}
    """
    domain = resolve_mock_domain(mis)
    if not domain:
        print("URL_MAPPING ADD: 无法确定目标工作域 MIS")
        return {}
    if not url:
        print("URL_MAPPING ADD: url 不能为空")
        return {}
    if not beta_url and not ppe_url:
        print("URL_MAPPING ADD: betaUrl 和 ppeUrl 至少需要一个")
        return {}

    body = {"userDomain": domain, "url": url}
    if beta_url:
        body["betaUrl"] = beta_url
    if ppe_url:
        body["ppeUrl"] = ppe_url

    result = _proxy_call("POST", "/url-mapping/add", json_body=body)
    if result is not None:
        mapping_id = extract_mock_id(result)
        print(f"URL_MAPPING ADD OK: id={mapping_id} url={url}")
        return {"action": "added", "id": mapping_id, "url": url,
                "betaUrl": beta_url, "ppeUrl": ppe_url}
    return {}

def url_mapping_update(mapping_id, url: str, mis: str = None,
                       beta_url: str = "", ppe_url: str = "") -> dict:
    """按 id 更新域名映射（上游 updateUserUrlMapping）。

    ⚠️ 上游强制要求 url 字段（缺省报「URL不能为空」），故 url 是必传参数。

    Args:
        mapping_id: 映射 ID（list 返回的 id）
        url: 线上 URL（上游必填，直接透传）
        mis: 目标工作域 MIS 号
        beta_url/ppe_url: 新目标地址（带协议），按需更新

    Returns:
        {"action": "updated", "id": ..., ...}；失败返回 {}
    """
    domain = resolve_mock_domain(mis)
    if not domain:
        print("URL_MAPPING UPDATE: 无法确定目标工作域 MIS")
        return {}
    if not mapping_id:
        print("URL_MAPPING UPDATE: mapping_id 不能为空")
        return {}
    if not url:
        print("URL_MAPPING UPDATE: url 不能为空（上游强制要求）")
        return {}
    if not beta_url and not ppe_url:
        print("URL_MAPPING UPDATE: betaUrl 和 ppeUrl 不能同时为空（上游强制要求）")
        return {}

    body = {"userDomain": domain, "id": str(mapping_id), "url": url}
    if beta_url:
        body["betaUrl"] = beta_url
    if ppe_url:
        body["ppeUrl"] = ppe_url

    result = _proxy_call("POST", "/url-mapping/update", json_body=body)
    if result is not None:
        print(f"URL_MAPPING UPDATE OK: id={mapping_id} url={url}")
        return {"action": "updated", "id": mapping_id, "url": url,
                "betaUrl": beta_url, "ppeUrl": ppe_url}
    return {}

def url_mapping_upsert(url: str, mis: str = None, beta_url: str = "",
                       ppe_url: str = "") -> dict:
    """按 url 幂等写映射：已存在则 update，不存在则 add。

    给「只知道 url、不知道 id」的调用方（如 CLI url-mapping-update）提供
    create-or-update 语义。
    """
    domain = resolve_mock_domain(mis)
    if not domain:
        print("URL_MAPPING UPSERT: 无法确定目标工作域 MIS")
        return {}
    target = (url or "").strip()
    for m in url_mapping_list(domain):
        if (m.get("url") or "").strip() == target:
            return url_mapping_update(m.get("id"), url, mis=domain,
                                      beta_url=beta_url, ppe_url=ppe_url)
    return url_mapping_add(url, mis=domain, beta_url=beta_url, ppe_url=ppe_url)

def url_mapping_delete(mapping_id, mis: str = None) -> bool:
    """按 userDomain + id 删除域名映射（上游 removeUserUrlMapping）。"""
    domain = resolve_mock_domain(mis)
    if not domain:
        print("URL_MAPPING DELETE: 无法确定目标工作域 MIS")
        return False
    result = _proxy_call("GET", "/url-mapping/delete",
                         params={"userDomain": domain, "id": str(mapping_id)})
    if result is not None:
        print(f"URL_MAPPING DELETE OK: id={mapping_id}")
        return True
    return False

def url_mapping_find(url_keyword: str, mis: str = None) -> list:
    """按 URL 关键词搜索指定工作域的已有映射（本地过滤）。"""
    mappings = url_mapping_list(mis)
    if not url_keyword:
        return mappings

    kw = url_keyword.lower()
    matched = [m for m in mappings if kw in (m.get("url", "") or "").lower()]
    print(f"URL_MAPPING FIND: {len(matched)}/{len(mappings)} matched keyword='{url_keyword}'")
    return matched

def url_mapping_set_env(mapping_id, env: str = "beta", mis: str = None) -> bool:
    """激活/关闭域名映射（上游 updateUrlEnv，按 userDomain + id）。

    Args:
        mapping_id: 域名映射 ID
        env: ''=跟随大环境 / beta=强制 beta / ppe=强制 ppe / close=关闭此映射
        mis: 目标工作域 MIS 号

    Returns:
        True 成功，False 失败
    """
    domain = resolve_mock_domain(mis)
    if not domain:
        print("URL_MAPPING SET ENV: 无法确定目标工作域 MIS")
        return False
    result = _proxy_call("GET", "/url-mapping/set-env",
                         params={"userDomain": domain, "id": str(mapping_id), "env": env})
    if result is not None:
        print(f"URL_MAPPING SET ENV OK: id={mapping_id} env={env}")
        return True
    return False

# ═══════════════════════════════════════════════════════════════════
# 环境切换（yooz 代理 + ssoCookie）
# ═══════════════════════════════════════════════════════════════════

def session_env_set(env: str, mis: str = None) -> bool:
    """通过 yooz 代理切换「指定工作域」的 AppMock 代理环境。

    env/set 在 yooz 代理侧强制要求 userDomain（对齐 AppMock 直连契约），
    省略会误切操作者自身，故必须显式带上目标工作域。

    统一入口 appmock_swimlane.py 的 appmock_env_set() 只走本函数（不再经过 imeituan CLI）。
    """
    domain = resolve_mock_domain(mis)
    body = {"env": env}
    if domain:
        body["userDomain"] = domain
    result = _proxy_call("POST", "/env/set", json_body=body)
    if result is not None:
        print(f"SESSION ENV SET OK: env={env} domain={domain}")
        return True
    return False

# ═══════════════════════════════════════════════════════════════════
# 泳道管理（yooz 代理 + ssoCookie）
# ═══════════════════════════════════════════════════════════════════

def session_swimline_list(mis: str) -> list:
    """通过 yooz 代理查询泳道列表（需浏览器 Session）。

    上游 getMySwimLines 强制要求 userDomain（传 user 会报「userDomain不合法」）。
    """
    result = _proxy_call("GET", "/swimline/list", params={"userDomain": mis})
    if result is not None:
        items = result.get("items", [])
        print(f"SESSION SWIMLINE LIST OK: {len(items)} rule(s)")
        return items
    return []

def session_swimline_add(url_pattern: str, lane_name: str, mis: str) -> dict:
    """通过 yooz 代理新增泳道规则（需浏览器 Session）。

    上游 insertOrUpdate 强制要求 userDomain（传 user 会报「userDomain不合法」）。
    """
    result = _proxy_call("POST", "/swimline/add",
                         json_body={"userDomain": mis, "url": url_pattern, "configs": lane_name})
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
                    # 上游泳道项的配置名在 configs 字段（兼容旧字段）
                    user_config = (lane.get("configs") or lane.get("userConfig")
                                   or lane.get("name") or "")
                    break
    if not user_config:
        user_config = ""  # 有些场景不需要 userConfig，让服务端处理

    body = {"id": int(rule_id), "userConfig": user_config}
    domain = resolve_mock_domain(mis)
    if domain:
        body["userDomain"] = domain
    result = _proxy_call("POST", "/swimline/switch", json_body=body)
    if result is not None:
        print(f"SESSION SWIMLINE SWITCH OK: ruleId={rule_id}")
        return True
    return False

def session_swimline_off(rule_id=None, mis: str = None) -> bool:
    """通过 yooz 代理关闭泳道并切回线上（需浏览器 Session）。

    Args:
        rule_id: 可选泳道 ID，传入时清空该泳道的 userConfig
        mis: 目标工作域（env/set 必填，代理侧强制）
    """
    domain = resolve_mock_domain(mis)
    body = {}
    if rule_id:
        body["id"] = int(rule_id)
    if domain:
        body["userDomain"] = domain

    result = _proxy_call("POST", "/swimline/off", json_body=body)
    if result is not None:
        print("SESSION SWIMLINE OFF OK")
        return True
    return False

def session_swimline_remove(rule_id, mis: str = None) -> bool:
    """通过 yooz 代理删除泳道规则（需浏览器 Session）。

    上游 deleteConfig 强制要求 userDomain。

    Args:
        rule_id: 泳道规则 ID
        mis: 目标工作域 MIS 号
    """
    domain = resolve_mock_domain(mis)
    if not domain:
        print("SESSION SWIMLINE REMOVE: 无法确定目标工作域 MIS")
        return False
    result = _proxy_call("POST", "/swimline/remove",
                         json_body={"id": int(rule_id), "userDomain": domain})
    if result is not None:
        print(f"SESSION SWIMLINE REMOVE OK: id={rule_id}")
        return True
    return False


