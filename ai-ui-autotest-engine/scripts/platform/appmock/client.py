#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 公共基础设施 —— 常量、辅助函数、yooz 代理调用。

被 appmock_device / appmock_rules / appmock_record / appmock_swimlane 共享。
"""
import base64 as _b64
import json

from shared.case_utils import resolve_mock_domain
from shared.context import get_app_descriptor, get_platform_ops
from platform.ssl_helper import get_verify_flag
from shared.errors import AutotestError, soft_fail

# yooz 服务端 AppMock 代理接口
_YOOZ_BASE = _b64.b64decode("aHR0cHM6Ly95b296LnNhbmt1YWkuY29t").decode() + "/node/api/data/monitor/appmock"
_YOOZ_APPMOCK_PROXY = f"{_YOOZ_BASE}/status"

# ═══════════════════════════════════════════════════════════════════
# yooz 代理响应信封解析（全仓库唯一事实来源）
# ═══════════════════════════════════════════════════════════════════

def unwrap_proxy_response(payload):
    """拆解 yooz 代理的两层信封，返回 (ok, body, detail)。

    代理把平台结果包成两层：外层固定 {"code":0,"data":{...}}，真正的执行结果在
    内层 data.code / data.msg / data.data。只判外层会把平台报错当成功，历史上
    因此出过三类静默错：规则开关请求发出去了但没生效、500 错误页 HTML 被当作规则
    列表遍历、创建失败却打印「已启用」。

    Args:
        payload: resp.json() 的原始 dict

    Returns:
        ok     — 内层 code 为 0（或响应本就不带内层信封）时为 True
        body   — 内层 data 字段，无则空 dict
        detail — 失败摘要，形如 "code=-4: 添加失败，匹配规则须满足全匹配或正则匹配"
    """
    if not isinstance(payload, dict):
        return False, {}, f"响应不是 JSON 对象: {str(payload)[:120]}"
    if payload.get("code") != 0:
        return False, {}, f"外层 code={payload.get('code')}: {str(payload.get('msg'))[:120]}"
    inner = payload.get("data")
    if not isinstance(inner, dict):
        return False, {}, f"响应缺少 data 字段: {json.dumps(payload, ensure_ascii=False)[:160]}"
    if "code" not in inner:
        # 少数接口直接把结果放在 data 下，没有内层信封
        return True, inner, ""
    if inner.get("code") != 0:
        reason = inner.get("data")
        if isinstance(reason, dict):
            reason = (reason.get("message") or reason.get("msg")
                      or json.dumps(reason, ensure_ascii=False))
        elif not reason:
            reason = inner.get("msg")
        return False, inner, f"code={inner.get('code')}: {str(reason)[:200]}"
    body = inner.get("data")
    return True, ({} if body is None else body), ""

# ═══════════════════════════════════════════════════════════════════
# PlatformOps content_call 执行 AppMock content provider 操作
# ═══════════════════════════════════════════════════════════════════

def _device_content_call(method, *args):
    """通过 PlatformOps.content_call 操作 AppMock content provider。

    Args:
        method: content provider 方法名（如 enable / disable / getStatus）
        *args: 额外的 --arg 参数
    Returns:
        (success: bool, output: str)
    """
    try:
        content_uri = get_app_descriptor().appmock_content_uri
        ops = get_platform_ops()
        return ops.content_call(content_uri, method, *args)
    except AutotestError as e:
        soft_fail("device", "CONTENT_CALL_FAILED", e)
        return False, ""
    except Exception as e:
        return False, str(e)

# ═══════════════════════════════════════════════════════════════════
# yooz 服务端代理开关
# ═══════════════════════════════════════════════════════════════════

def _appmock_via_proxy(mock_id, status, mis=None):
    """通过 yooz 服务端代理开关 mock 规则（内网零鉴权）。

    Args:
        mock_id: Mock 规则 ID
        status: 1=开启, -1=关闭
        mis: MIS 号（默认自动获取）
    Returns:
        True 成功，False 失败
    """
    import requests as _req

    if not mis:
        mis = resolve_mock_domain()
    if not mis:
        print("APPMOCK PROXY: 无法确定当前用户 MIS 号（请设置 APPMOCK_USER_MIS 环境变量）")
        return False

    try:
        resp = _req.post(
            _YOOZ_APPMOCK_PROXY,
            json={"mockId": str(mock_id), "userDomain": mis, "status": status},
            timeout=15,
            verify=get_verify_flag()
        )
        data = resp.json()
        ok, _, detail = unwrap_proxy_response(data)
        if ok:
            action = "ON" if status == 1 else "OFF"
            print(f"APPMOCK {action} OK (yooz proxy): mockId={mock_id}")
            return True
        print(f"APPMOCK PROXY FAIL: {detail}")
        return False
    except Exception as e:
        print(f"APPMOCK PROXY ERROR: {e}")
        return False
