#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 服务端规则 —— 开关 / 查询 / CRUD / 字段补丁。

优先 imeituan CLI，SSO 失败时自动 fallback 到 yooz 代理。
"""
import json

from core.util.case_utils import resolve_mis
from mock.appmock_core import (
    _cli_or_proxy,
    _YOOZ_BASE,
    _appmock_via_proxy,
    unwrap_proxy_response,
)
from infra.appmock_auth import _get_cookie_or_warn
from infra.ssl_helper import get_verify_flag

# ═══════════════════════════════════════════════════════════════════
# mockId 提取（全仓库唯一事实来源）
# ═══════════════════════════════════════════════════════════════════

# 各接口把 id 放在不同 key 上：代理 create 用 mockId，列表/泳道项用 id/ruleId
_ID_KEYS = ("mockId", "id", "ruleId")


def extract_mock_id(payload) -> str:
    """从任意 AppMock 响应结构中取出规则 id，取不到返回空串（永不返回 "None"）。

    真实返回形态不统一，这里一次收敛（最多下钻 3 层 data）：
      {"data": {"data": {"mockId": {"mockId": 123}}}}   yooz 代理 /create（id 再包一层）
      {"data": {"data": {"mockId": 123}}}              平台原生 addMockConfig
      {"data": {"mockId": 123}}                         部分代理接口
      {"mockId": 123} / {"id": 123}                     CLI 直出 / 列表项 / 泳道项

    关键点：
      1. JSON null 与空串一律视为「没有 id」——直接 str(...) 会把 null 变成真值字符串
         "None"，于是开关请求既不报错也关不掉规则，最终变成静默的 Mock 规则泄漏；
      2. id 的 value 本身可能是 dict（代理把平台返回的 {"mockId": N} 原样透传），
         必须再下钻一层，否则会返回 "{'mockId': N}" 这种垃圾 id，开关同样静默失效。
    """
    current = payload
    for _ in range(4):
        if not isinstance(current, dict):
            return ""
        for key in _ID_KEYS:
            value = current.get(key)
            if isinstance(value, dict):
                value = value.get("mockId") or value.get("id")
            if value is not None and str(value).strip():
                return str(value).strip()
        current = current.get("data")
    return ""


# ═══════════════════════════════════════════════════════════════════
# 服务端规则开关
# ═══════════════════════════════════════════════════════════════════

def appmock_on(mock_id: str, mis: str = None) -> bool:
    """激活服务端指定 mock 规则。

    优先使用 imeituan CLI，SSO 认证失败时自动 fallback 到 yooz 代理。

    Args:
        mock_id: Mock 规则 ID（如 16305525）
        mis: MIS 号（fallback 时使用，默认自动获取）
    Returns:
        True 成功，False 失败
    """
    return _cli_or_proxy(
        f"ON mockId={mock_id}",
        ["inject", "mock", "on", str(mock_id)],
        lambda: _appmock_via_proxy(mock_id, status=1, mis=mis),
        parse_cli=lambda r, out: print(f"APPMOCK ON OK: mockId={mock_id}") or True,
    )

def appmock_off(mock_id: str, mis: str = None) -> bool:
    """关闭服务端指定 mock 规则。

    优先使用 imeituan CLI，SSO 认证失败时自动 fallback 到 yooz 代理。

    Args:
        mock_id: Mock 规则 ID
        mis: MIS 号（fallback 时使用，默认自动获取）
    Returns:
        True 成功，False 失败
    """
    return _cli_or_proxy(
        f"OFF mockId={mock_id}",
        ["inject", "mock", "off", str(mock_id)],
        lambda: _appmock_via_proxy(mock_id, status=-1, mis=mis),
        parse_cli=lambda r, out: print(f"APPMOCK OFF OK: mockId={mock_id}") or True,
    )

# ═══════════════════════════════════════════════════════════════════
# 规则查询
# ═══════════════════════════════════════════════════════════════════

def _proxy_get(mock_id, mis):
    """yooz 代理查询 mock 规则详情。"""
    import requests as _req
    mis = resolve_mis(mis)
    if not mis:
        print("APPMOCK GET PROXY: 无法确定 MIS 号")
        return {}
    sso_cookie = _get_cookie_or_warn()
    if not sso_cookie:
        print("APPMOCK GET PROXY: SSO Cookie 获取失败")
        return {}
    try:
        resp = _req.get(
            f"{_YOOZ_BASE}/query",
            params={"mockId": str(mock_id), "userDomain": mis, "ssoCookie": sso_cookie},
            timeout=15,
            verify=get_verify_flag()
        )
        data = resp.json()
        ok, body, detail = unwrap_proxy_response(data)
        if ok:
            print(f"APPMOCK GET OK (yooz proxy): mockId={mock_id}")
            return body if isinstance(body, dict) else {}
        print(f"APPMOCK GET PROXY FAIL: {detail}")
    except Exception as e:
        print(f"APPMOCK GET PROXY ERROR: {e}")
    return {}

def appmock_get(mock_id: str, mis: str = None) -> dict:
    """查询指定 mock 规则详情。

    优先 CLI，CIBA 失败走 yooz 代理。

    Returns:
        规则详情 dict（失败返回空 dict）
    """
    def _parse(r, out):
        try:
            return json.loads(r.stdout)
        except Exception:
            return {"raw": out}
    return _cli_or_proxy(
        "GET",
        ["inject", "mock", "get", str(mock_id)],
        lambda: _proxy_get(mock_id, mis),
        parse_cli=_parse,
        fail_value={},
    )

def _proxy_list(mis):
    """yooz 代理查询全部 mock 规则列表。"""
    import requests as _req
    mis = resolve_mis(mis)
    if not mis:
        print("APPMOCK LIST PROXY: 无法确定 MIS 号")
        return []
    try:
        resp = _req.post(f"{_YOOZ_BASE}/list", json={"userDomain": mis}, timeout=15, verify=get_verify_flag())
        data = resp.json()
        ok, body, detail = unwrap_proxy_response(data)
        if ok:
            items = body if isinstance(body, list) else []
            print(f"APPMOCK LIST OK (yooz proxy): {len(items)} rules")
            return items
        print(f"APPMOCK LIST PROXY FAIL: {detail}")
    except Exception as e:
        print(f"APPMOCK LIST PROXY ERROR: {e}")
    return []

def appmock_list(mis: str = None) -> list:
    """查询指定用户的全部 mock 规则列表。

    优先 CLI，CIBA 失败走 yooz 代理。

    Returns:
        规则列表 list（失败返回空列表）
    """
    def _parse(r, out):
        try:
            result = json.loads(r.stdout)
            return result.get("items", result.get("data", []))
        except Exception:
            return []
    return _cli_or_proxy(
        "LIST",
        ["inject", "mock", "list"],
        lambda: _proxy_list(mis),
        parse_cli=_parse,
        fail_value=[],
    )

def _proxy_stop_all(mis):
    """yooz 代理停止全部 mock 规则。"""
    import requests as _req
    mis = resolve_mis(mis)
    if not mis:
        print("APPMOCK STOP-ALL PROXY: 无法确定 MIS 号")
        return False
    try:
        resp = _req.post(f"{_YOOZ_BASE}/stop-all", json={"userDomain": mis}, timeout=15, verify=get_verify_flag())
        data = resp.json()
        ok, _, detail = unwrap_proxy_response(data)
        if ok:
            print("APPMOCK STOP-ALL OK (yooz proxy)")
            return True
        print(f"APPMOCK STOP-ALL PROXY FAIL: {detail}")
    except Exception as e:
        print(f"APPMOCK STOP-ALL PROXY ERROR: {e}")
    return False

def appmock_stop_all(mis: str = None) -> bool:
    """停止指定用户的全部 mock 规则。

    优先 CLI，CIBA 失败走 yooz 代理。
    """
    return _cli_or_proxy(
        "STOP-ALL",
        ["inject", "mock", "stop-all"],
        lambda: _proxy_stop_all(mis),
    )

# ═══════════════════════════════════════════════════════════════════
# CRUD 接口（通过 yooz 代理）
# ═══════════════════════════════════════════════════════════════════

def appmock_create(rule: str, response_body: str, mis: str = None,
                   desc: str = "", status: int = 1, status_code: int = 200,
                   header: str = None, delay: int = 0, method: str = None,
                   group_id: int = None, force_add: bool = False,
                   request_header: str = None, request_param: str = None,
                   mock_type: int = None) -> dict:
    """通过 yooz 代理创建 AppMock 规则。

    Args:
        rule: URI 路径匹配规则（末尾加 $ 精确匹配）
        response_body: Mock 响应体（JSON 字符串）
        mis: MIS 号（省略则自动解析）
        desc: 描述
        status: 1=开启, -1=关闭
        status_code: HTTP 状态码
        header: 响应头（JSON 字符串）
        delay: 延迟(ms)
        method: GET/POST/PUT/HEAD
        group_id: 分组 ID
        force_add: 是否强制新增（即使已有同 rule 的规则）
        request_header: 请求头注入（JSON 字符串，partMock 模式生效）
        request_param: 请求参数注入（JSON 字符串，partMock 模式生效）
        mock_type: Mock 类型（0=全量 Mock, 1=partMock 字段级修改）

    Returns:
        {"mockId": <str>}（成功）；{"error": <detail>}（失败，便于调用方分治处理）
    """
    resolved_mis = resolve_mis(mis)
    if not resolved_mis:
        print("APPMOCK CREATE: 无法确定 MIS 号")
        return {}

    import requests as _req
    payload = {
        "rule": rule,
        "userDomain": resolved_mis,
        "response": response_body,
        "status": status,
        "desc": desc,
        "statusCode": status_code,
        "delay": delay,
    }
    if header:
        payload["header"] = header
    if method:
        payload["method"] = method
    if group_id is not None:
        payload["group"] = group_id
    if force_add:
        payload["forceAdd"] = True
    if request_header is not None:
        payload["requestHeader"] = request_header
    if request_param is not None:
        payload["requestParam"] = request_param
    if mock_type is not None:
        payload["type"] = mock_type

    try:
        resp = _req.post(f"{_YOOZ_BASE}/create", json=payload, timeout=30, verify=get_verify_flag())
        data = resp.json()
        ok, _, detail = unwrap_proxy_response(data)
        if ok:
            mock_id = extract_mock_id(data)
            if not mock_id:
                message = f"响应未返回 mockId — {json.dumps(data, ensure_ascii=False)[:300]}"
                print(f"APPMOCK CREATE FAIL: {message}")
                return {"error": message}
            print(f"APPMOCK CREATE OK: mockId={mock_id} rule={rule}")
            return {"mockId": mock_id}
        print(f"APPMOCK CREATE FAIL: {detail}")
        return {"error": detail}
    except Exception as e:
        print(f"APPMOCK CREATE ERROR: {e}")
        return {"error": f"create 异常: {e}"}

def appmock_update(mock_id: str, response_body: str = None,
                   rule: str = None, desc: str = None,
                   status: int = None, status_code: int = None,
                   header: str = None, delay: int = None,
                   request_header: str = None, request_param: str = None,
                   mock_type: int = None) -> bool:
    """通过 yooz 代理更新 AppMock 规则。

    Args:
        mock_id: Mock 规则 ID（必填）
        response_body: 新的响应体（JSON 字符串）
        rule: 新的 URI 路径匹配规则
        desc: 新的描述
        status: 1=开启, -1=关闭
        status_code: HTTP 状态码
        header: 新的响应头（JSON 字符串）
        delay: 延迟(ms)
        request_header: 请求头注入（JSON 字符串，partMock 模式生效）
        request_param: 请求参数注入（JSON 字符串，partMock 模式生效）
        mock_type: Mock 类型（0=全量 Mock, 1=partMock 字段级修改）

    Returns:
        True=成功, False=失败
    """
    import requests as _req
    payload = {"mockId": int(mock_id)}
    if response_body is not None:
        payload["response"] = response_body
    if rule is not None:
        payload["rule"] = rule
    if desc is not None:
        payload["desc"] = desc
    if status is not None:
        payload["status"] = status
    if status_code is not None:
        payload["statusCode"] = status_code
    if header is not None:
        payload["header"] = header
    if delay is not None:
        payload["delay"] = delay
    if request_header is not None:
        payload["requestHeader"] = request_header
    if request_param is not None:
        payload["requestParam"] = request_param
    if mock_type is not None:
        payload["type"] = mock_type

    try:
        resp = _req.post(f"{_YOOZ_BASE}/update", json=payload, timeout=30, verify=get_verify_flag())
        data = resp.json()
        ok, _, detail = unwrap_proxy_response(data)
        if ok:
            print(f"APPMOCK UPDATE OK: mockId={mock_id}")
            return True
        print(f"APPMOCK UPDATE FAIL: {detail}")
    except Exception as e:
        print(f"APPMOCK UPDATE ERROR: {e}")
    return False

# ═══════════════════════════════════════════════════════════════════
# 正则规则落地（平台新建通道不受理 → 先建字面规则再改 rule）
# ═══════════════════════════════════════════════════════════════════

# 平台 addMockConfig 新建通道的规则格式报错文案（只放行字面 URI 路径）
NON_LITERAL_RULE_ERROR = "匹配规则须满足全匹配或正则匹配"


def appmock_provision_rule(rule: str, desc: str, *, placeholder_rule: str,
                           response_body: str = "", mis: str = None,
                           status: int = -1, status_code: int = 200,
                           method: str = None, request_header: str = None,
                           request_param: str = None, mock_type: int = None) -> dict:
    """落地一条「平台新建通道不受理」的匹配规则（典型：正则规则 `/.*?$`）。

    平台现状（实测）：

      - `addMockConfig` 新建通道只放行字面 URI 路径（可带结尾 `$`）；rule 里出现
        `*` `+` `?` `^` `[` `(` 等一律返回 -4「匹配规则须满足全匹配或正则匹配」；
      - `updateMockConfig` 的 rule 字段不做该校验，可以改成正则；
      - `addMockConfig` 对同 (rule, desc) 重复提交是幂等的 —— 命中既有规则时直接
        返回它的 mockId，不新建、也不做格式校验。

    所以「先建字面占位规则，再 update 成目标规则」是唯一能让新账号也落地的路径，
    且天然幂等：`placeholder_rule` 必须稳定，重复调用命中同一条而非每次新建。

    注意：不要把这里当补丁绕过去 —— 用非字面 rule 直接 create 必然失败，
    调用方应统一走本函数。

    Args:
        rule: 目标匹配规则，可为正则（如 `/.*?$`）
        desc: 规则描述（同时是命中复用 key 的一部分，同 rule 不同 desc 会被当成新规则）
        placeholder_rule: 稳定占位字面规则（如 `/autotest-ptest-bootstrap$`）

    Returns:
        {"mockId": <str>} 成功；{"error": <detail>} 失败
    """
    created = appmock_create(
        rule=placeholder_rule, response_body=response_body, mis=mis,
        desc=desc, status=status, status_code=status_code, method=method,
        request_header=request_header, request_param=request_param,
        mock_type=mock_type,
    )
    mock_id = extract_mock_id(created)
    if not mock_id:
        return {"error": created.get("error", "占位规则创建失败")}

    if not appmock_update(
        mock_id=mock_id, rule=rule, desc=desc, status=status,
        request_header=request_header, request_param=request_param,
        mock_type=mock_type,
    ):
        return {"error": f"占位规则已建（mockId={mock_id}）但切换 rule={rule} 失败"}

    print(f"APPMOCK PROVISION OK: mockId={mock_id} rule={rule}")
    return {"mockId": mock_id}

# ═══════════════════════════════════════════════════════════════════
# 动态 Mock：修改已有规则的指定字段
# ═══════════════════════════════════════════════════════════════════

def appmock_patch_field(mock_id: str, field_path: str, new_value,
                        mis: str = None) -> bool:
    """读取已有 Mock 规则的响应体 JSON，按 dotpath 修改指定字段，再更新回去。

    适用于 preview 等接口已被预设规则 Mock 的场景：直接修改已有规则的
    response body 中的某个字段值，而非从录制数据中查找（已被 Mock 的接口
    不会出现在录制数据中）。

    Args:
        mock_id: 已有的 Mock 规则 ID
        field_path: JSON 字段路径，支持 . 分隔的嵌套路径（如 "data.totalPrice"）
        new_value: 新值（数字/字符串/bool/None）
        mis: MIS 号

    Returns:
        True=成功, False=失败

    Example:
        appmock_patch_field("16305525", "data.totalPrice", "0.01")
    """
    # 1) 获取当前规则详情
    detail = appmock_get(mock_id, mis=mis)
    if not detail:
        print(f"APPMOCK PATCH-FIELD FAIL: 无法获取 mockId={mock_id} 的规则详情")
        return False

    # 2) 提取 response 字段
    resp_str = detail.get("response") or detail.get("data", {}).get("response", "")
    if not resp_str:
        print(f"APPMOCK PATCH-FIELD FAIL: mockId={mock_id} 没有 response 字段")
        return False

    try:
        resp_json = json.loads(resp_str) if isinstance(resp_str, str) else resp_str
    except json.JSONDecodeError as e:
        print(f"APPMOCK PATCH-FIELD FAIL: response 不是合法 JSON: {e}")
        return False

    # 3) 按 dotpath 修改字段
    keys = field_path.split(".")
    obj = resp_json
    for key in keys[:-1]:
        if isinstance(obj, dict) and key in obj:
            obj = obj[key]
        elif isinstance(obj, list):
            try:
                obj = obj[int(key)]
            except (ValueError, IndexError):
                print(f"APPMOCK PATCH-FIELD FAIL: 路径 '{field_path}' 中 '{key}' 不存在")
                return False
        else:
            print(f"APPMOCK PATCH-FIELD FAIL: 路径 '{field_path}' 中 '{key}' 不存在")
            return False

    last_key = keys[-1]
    if isinstance(obj, dict):
        old_value = obj.get(last_key, "<不存在>")
        obj[last_key] = new_value
    elif isinstance(obj, list):
        try:
            idx = int(last_key)
            old_value = obj[idx]
            obj[idx] = new_value
        except (ValueError, IndexError):
            print(f"APPMOCK PATCH-FIELD FAIL: 数组索引 '{last_key}' 无效")
            return False
    else:
        print(f"APPMOCK PATCH-FIELD FAIL: 无法在 {type(obj).__name__} 上设置字段")
        return False

    # 4) 更新回去
    new_resp_str = json.dumps(resp_json, ensure_ascii=False)
    ok = appmock_update(mock_id=mock_id, response_body=new_resp_str)
    if ok:
        print(f"APPMOCK PATCH-FIELD OK: {field_path}: {old_value} → {new_value}")
    return ok
