#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 服务端规则 —— 开关 / 查询 / CRUD / 字段补丁。

统一走 yooz 代理接口（不再经过 imeituan CLI）。
"""
import json

from aitest.shared.case_utils import resolve_runtime_domain
from aitest.integrations.appmock.client import (
    _YOOZ_BASE,
    _appmock_via_proxy,
    unwrap_proxy_response,
)
from aitest.integrations.ssl_helper import get_verify_flag

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
      {"mockId": 123} / {"id": 123}                     列表项 / 泳道项 / 代理直出

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

    统一走 yooz 代理接口（不再经过 imeituan CLI）。

    Args:
        mock_id: Mock 规则 ID（如 16305525）
        mis: MIS 号（fallback 时使用，默认自动获取）
    Returns:
        True 成功，False 失败
    """
    return _appmock_via_proxy(mock_id, status=1, mis=mis)

def appmock_off(mock_id: str, mis: str = None) -> bool:
    """关闭服务端指定 mock 规则。

    统一走 yooz 代理接口（不再经过 imeituan CLI）。

    Args:
        mock_id: Mock 规则 ID
        mis: MIS 号（fallback 时使用，默认自动获取）
    Returns:
        True 成功，False 失败
    """
    return _appmock_via_proxy(mock_id, status=-1, mis=mis)

# ═══════════════════════════════════════════════════════════════════
# 规则查询
# ═══════════════════════════════════════════════════════════════════

def _pick_rule_item(body, mock_id):
    """从 batch-get 的 {items: [...]} 里选中目标规则（兼容 id/mockId 两种字段）。"""
    items = body.get("items") if isinstance(body, dict) else None
    if not isinstance(items, list) or not items:
        return {}
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("mockId") or item.get("id") or "") == str(mock_id):
            return item
    first = items[0]
    return first if isinstance(first, dict) else {}


def _proxy_get(mock_id, mis):
    """按指定域读取规则副本（运行域读取用）。

    统一走 `/rules/batch-get` + `userDomain`：服务端用应用身份票直取，
    不需要用户 Cookie（sso-auth-cli 只保留给 record / env / swimline /
    url-mapping 这类用户级操作）。
    """
    import requests as _req
    mis = resolve_runtime_domain(mis)
    if not mis:
        print("APPMOCK GET PROXY: 无法确定 MIS 号")
        return {}

    # ── 主路径：应用身份直取（无需 Cookie）──
    try:
        resp = _req.post(
            f"{_YOOZ_BASE}/rules/batch-get",
            json={"mockIds": [str(mock_id)], "userDomain": mis},
            timeout=15,
            verify=get_verify_flag(),
        )
        ok, body, detail = unwrap_proxy_response(resp.json())
        if ok:
            rule = _pick_rule_item(body, mock_id)
            if rule:
                print(f"APPMOCK GET OK (batch-get/{mis}): mockId={mock_id}")
                return rule
            detail = "batch-get 未返回该规则"
        print(f"APPMOCK GET BATCH-GET MISS: {detail}")
    except Exception as e:
        print(f"APPMOCK GET BATCH-GET ERROR: {e}")
    return {}

def _batch_get(mock_ids) -> dict:
    """按 mockId 直取规则母本：{mockId: detail}。

    mockId 全局唯一；存储域与应用身份鉴权均在 yooz 服务端内置并自动取票，
    调用方不需要传域、也不需要传 Cookie。规则库直取始终只读，
    不能用于读取运行域副本（那把 id 不在规则库里）。
    """
    import requests as _req
    ids = list(dict.fromkeys(str(x).strip() for x in (mock_ids or []) if str(x).strip()))
    if not ids:
        return {}
    try:
        resp = _req.post(
            f"{_YOOZ_BASE}/rules/batch-get",
            json={"mockIds": ids},
            timeout=30,
            verify=get_verify_flag(),
        )
        ok, body, detail = unwrap_proxy_response(resp.json())
        if not ok:
            print(f"APPMOCK BATCH-GET FAIL: {detail}")
            return {}
        result = _index_details(body)
        missing = [mid for mid in ids if mid not in result]
        if missing:
            print(f"APPMOCK BATCH-GET WARN: 规则库未返回 {missing}")
        print(f"APPMOCK BATCH-GET OK: {len(result)}/{len(ids)} rules")
        return result
    except Exception as e:
        print(f"APPMOCK BATCH-GET ERROR: {e}")
        return {}


def _index_details(body) -> dict:
    """批量响应归一化为 {mockId: detail}（服务端唯一返回结构：{items: [...]}）。"""
    items = body.get("items") if isinstance(body, dict) else None
    out = {}
    for detail in items or []:
        if not isinstance(detail, dict):
            continue
        mid = str(detail.get("mockId") or detail.get("id") or "").strip()
        if mid:
            out[mid] = detail
    return out


def appmock_get_many(mock_ids) -> dict:
    """批量直取规则母本：{mockId: detail}（失败或缺项由调用方按缺口处理）。"""
    return _batch_get(mock_ids)


def appmock_get(mock_id: str) -> dict:
    """按 mockId 直取规则母本详情（服务端解析归属规则库）。

    Returns:
        规则详情 dict（失败返回空 dict）
    """
    return appmock_get_many([mock_id]).get(str(mock_id).strip(), {})


def appmock_get_in(mock_id: str, mis: str) -> dict:
    """读取指定域里的规则副本（运行域读取用）。"""
    return _proxy_get(mock_id, mis)


# ═══════════════════════════════════════════════════════════════════
# 规则克隆：规则库母本 → 运行域副本（服务端权威实现 + 读回自证）
# ═══════════════════════════════════════════════════════════════════

# 副本归属标记：服务端按 (rule, desc 前缀) 复用本次 run 自建的副本，绝不抢占他人规则
RULE_DESC_PREFIX = "[ai-run]"


def appmock_clone(source_mock_id, mis, desc="", status=-1) -> dict:
    """把规则母本克隆到 `mis` 指定的运行域，返回副本元信息。

    **引擎不做字段搬运**。AppMock 的规则内容是**多形态**的：全量响应
    （response）、部分 Mock（partMock 的 jsonPath patch）、部分 Mock V2
    （formData.lyrebirdMockResp）、纯请求注入（requestHeader / requestParam）。
    引擎逐字段列举必然漂移——历史上的 `response` 单形态假设把「部分 Mock」
    误判成读不到规则，即使放过去也会克隆成空壳。字段契约因此整体下沉到
    yooz 代理层（唯一直接对接 AppMock 的地方），引擎只表达
    「把这条母本克隆到这个域」。

    读取与域无关：mockId 全局唯一，`getMockConfigByMockId` 不校验 userDomain
    （实测传任意域均返回同一条规则）。所以调用方**不需要区分**母本属于我们的
    存储域还是用户自己的域——一律按 id 直取，落到本次运行域消费。

    Args:
        source_mock_id: 规则库母本 id（任意来源）
        mis: 目标运行域（本次 run 领取的虚拟 MIS）
        desc: 副本归属描述；缺省由服务端按 `[ai-run] {id} {rule}` 生成
        status: 新建副本的初始状态（-1 = 建好即关闭，由 case 级状态机开启）

    Returns:
        {"mockId", "rule", "method", "type", "contentFields", "shape",
         "reused", "verified", ...}；失败返回 {"error": <detail>}
    """
    import requests as _req
    payload = {
        "sourceMockId": str(source_mock_id).strip(),
        "userDomain": resolve_runtime_domain(mis),
        "descPrefix": RULE_DESC_PREFIX,
        "status": status,
    }
    if desc:
        payload["desc"] = desc
    try:
        resp = _req.post(
            f"{_YOOZ_BASE}/rules/clone",
            json=payload,
            timeout=60,
            verify=get_verify_flag(),
        )
        ok, body, detail = unwrap_proxy_response(resp.json())
        if not ok:
            print(f"APPMOCK CLONE FAIL: {detail}")
            return {"error": detail}
        if not isinstance(body, dict) or not body.get("mockId"):
            message = f"克隆响应缺少 mockId — {str(body)[:200]}"
            print(f"APPMOCK CLONE FAIL: {message}")
            return {"error": message}
        # 自证失败即视为克隆失败：宁可预检中止，也不把空壳副本放行到执行期
        if not body.get("verified"):
            message = (
                f"克隆自证失败（副本内容与母本不一致）: source={source_mock_id} "
                f"runtime={body.get('mockId')} "
                f"母本指纹={str(body.get('sourceFingerprint'))[:12]} "
                f"副本指纹={str(body.get('copyFingerprint'))[:12]}"
            )
            print(f"APPMOCK CLONE FAIL: {message}")
            return {"error": message}
        print(
            f"APPMOCK CLONE OK: {source_mock_id} → runtime {body.get('mockId')} "
            f"(rule={body.get('rule')}, shape={body.get('shape')}, "
            f"{'reused' if body.get('reused') else 'created'})"
        )
        return body
    except Exception as e:
        print(f"APPMOCK CLONE ERROR: {e}")
        return {"error": f"clone 异常: {e}"}

def _proxy_list(mis):
    """yooz 代理查询全部 mock 规则列表。"""
    import requests as _req
    mis = resolve_runtime_domain(mis)
    if not mis:
        print("APPMOCK LIST PROXY: 无法确定 MIS 号")
        return []
    try:
        resp = _req.post(f"{_YOOZ_BASE}/list", json={"userDomain": mis}, timeout=15, verify=get_verify_flag())
        data = resp.json()
        ok, body, detail = unwrap_proxy_response(data)
        if ok:
            # yooz 已把上游「按分组 id 嵌套的 dict」归一化为 {items: [...]}
            items = body.get("items", []) if isinstance(body, dict) else []
            print(f"APPMOCK LIST OK (yooz proxy): {len(items)} rules")
            return items
        print(f"APPMOCK LIST PROXY FAIL: {detail}")
    except Exception as e:
        print(f"APPMOCK LIST PROXY ERROR: {e}")
    return []

def appmock_list(mis: str = None) -> list:
    """查询指定用户的全部 mock 规则列表。

    统一走 yooz 代理接口（不再经过 imeituan CLI）。

    Returns:
        规则列表 list（失败返回空列表）
    """
    return _proxy_list(mis)

def _proxy_stop_all(mis):
    """yooz 代理停止全部 mock 规则。"""
    import requests as _req
    mis = resolve_runtime_domain(mis)
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

    统一走 yooz 代理接口（不再经过 imeituan CLI）。
    """
    return _proxy_stop_all(mis)

# ═══════════════════════════════════════════════════════════════════
# CRUD 接口（通过 yooz 代理）
# ═══════════════════════════════════════════════════════════════════

def appmock_create(rule: str, response_body: str, mis: str = None,
                   desc: str = "", status: int = 1, status_code: int = 200,
                   header: str = None, delay: int = 0, method: str = None,
                   group_id: int = None, force_add: bool = False,
                   request_header: str = None, request_param: str = None,
                   mock_type: int = None, example_url: str = None,
                   param_rule: str = None) -> dict:
    """通过 yooz 代理创建 AppMock 规则。

    Args:
        rule: URI 路径匹配规则（末尾加 $ 精确匹配；正则需带 example_url）
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
        example_url: 示例请求 URL（rule 为正则/非全匹配时必填）——上游据此校验
                     正则是否命中该示例；带此字段即可直接新建正则规则
        param_rule: 参数级匹配规则（可选，透传 paramRule）

    Returns:
        {"mockId": <str>}（成功）；{"error": <detail>}（失败，便于调用方分治处理）
    """
    resolved_mis = resolve_runtime_domain(mis)
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
    if example_url is not None:
        payload["exampleUrl"] = example_url
    if param_rule is not None:
        payload["paramRule"] = param_rule

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
                   mock_type: int = None, mis: str = None) -> bool:
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
        mis: 运行域（userDomain）—— 必须随写请求下发，让服务端按域校验；
             缺省取当前 run 的运行域租约（无租约直接报错，不静默写全局 id）

    Returns:
        True=成功, False=失败
    """
    import requests as _req
    payload = {"mockId": int(mock_id), "userDomain": resolve_runtime_domain(mis)}
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
    # 1) 获取当前规则详情（patch 只作用于运行域副本）
    detail = appmock_get_in(mock_id, mis)
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
    ok = appmock_update(mock_id=mock_id, response_body=new_resp_str, mis=mis)
    if ok:
        print(f"APPMOCK PATCH-FIELD OK: {field_path}: {old_value} → {new_value}")
    return ok
