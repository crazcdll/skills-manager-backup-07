#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 公共基础设施 —— 常量、辅助函数、CLI→Proxy fallback 框架。

被 appmock_device / appmock_rules / appmock_record / appmock_swimlane 共享。
"""
import base64 as _b64
import json

from infra.imeituan_cli import imeituan_exec
from core.util.case_utils import resolve_mis
from context import get_app_descriptor, get_platform_ops
from infra.ssl_helper import get_verify_flag
from core.errors import AutotestError, soft_fail

# yooz 服务端 AppMock 代理接口
_YOOZ_BASE = _b64.b64decode("aHR0cHM6Ly95b296LnNhbmt1YWkuY29t").decode() + "/node/api/data/monitor/appmock"
_YOOZ_APPMOCK_PROXY = f"{_YOOZ_BASE}/status"

# ═══════════════════════════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════════════════════════

def _cli_out(r):
    """合并 imeituan CLI 的 stdout+stderr 并 strip。"""
    return ((r.stdout or "") + (r.stderr or "")).strip()

def _is_sso_failure(out):
    """检测 imeituan CLI 输出是否为 SSO 认证失败。"""
    return "SSO_CIBA_FAILED" in out or "SSO" in out.upper()

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
# CLI→Proxy 统一 fallback 框架
# ═══════════════════════════════════════════════════════════════════

def _cli_or_proxy(action, cli_args, proxy_fn, *, parse_cli=None, fail_value=False):
    """执行 imeituan CLI，SSO 失败时自动 fallback 到 proxy 函数。

    Args:
        action: 日志标签（如 "SWIMLINE LIST"）
        cli_args: 传给 imeituan_exec 的参数列表
        proxy_fn: 无参 callable，SSO 失败时调用
        parse_cli: callable(r, out) → 结果（CLI 成功时调用，默认返回 True）
        fail_value: 非 SSO 失败时的返回值
    """
    r = imeituan_exec(cli_args)
    out = _cli_out(r)
    if r.returncode == 0:
        if parse_cli:
            return parse_cli(r, out)
        print(f"APPMOCK {action} OK")
        return True
    if _is_sso_failure(out):
        print(f"APPMOCK {action}: CLI SSO 失败，走 yooz 代理...")
        result = proxy_fn()
        if not result and result != 0:
            print(f"APPMOCK {action} FAIL: CLI SSO 失败且 yooz 代理也未成功")
        return result
    print(f"APPMOCK {action} FAIL: {out}")
    return fail_value

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
        mis = resolve_mis()
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
