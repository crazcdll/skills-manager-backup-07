#!/usr/bin/env python3
"""
DataUnity 工具调用封装层 - skill

通过 DataUnity 平台 /ability-map/agent 接口调用内部工具。
与 runner.py（直接 Thrift RPC）不同，此处通过 HTTP 调用 DataUnity 平台。

使用：
    from scripts.du_runner import run_tool, get_result, check_ok, DuError

    resp = run_tool(26, {
        "bizLine": "20",
        "poiName": "测试门店",
    })
    poi_id = get_result(resp, "mtPoiId")
"""

import json
import os
import subprocess
import sys
from typing import Any, Dict, Optional


BASE_URL = "https://dataunity.nibqa.test.sankuai.com/ability-map/agent"


class DuError(Exception):
    """DataUnity 调用错误"""
    def __init__(self, message: str, resp: dict = None):
        super().__init__(message)
        self.resp = resp or {}


def _http_get(url: str) -> dict:
    r = subprocess.run(
        ["curl", "-s", "--location", url, "--header", "Content-Type: application/json"],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": f"响应解析失败: {r.stdout[:300]}"}


def _http_post(url: str, payload: dict) -> dict:
    r = subprocess.run(
        [
            "curl", "-s", "--location", "--request", "POST", url,
            "--header", "Content-Type: application/json",
            "--data-raw", json.dumps(payload, ensure_ascii=False),
        ],
        capture_output=True, text=True, timeout=60,
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": f"响应解析失败: {r.stdout[:300]}"}


def run_tool(
    tool_id: int,
    overrides: Dict[str, Any],
    operator: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    调用 DataUnity 工具。

    参数：
        tool_id   - 工具 ID
        overrides - 参数覆盖字典 {paramKey: paramValue}
        operator  - 操作人 MIS，None 时从 config 读取
        dry_run   - True 时打印参数但不执行

    返回：DataUnity 工具执行响应（原始 JSON）

    异常：
        DuError - 工具不存在或网络失败
        SystemExit - 致命错误时退出
    """
    # 获取操作人（复用 utils.get_operator()，保证与全日房/钟点房逻辑一致）
    if operator is None:
        try:
            from hotel_testdata_cli.scripts.utils import get_operator
            operator = get_operator()
        except ImportError:
            try:
                from scripts.utils import get_operator
                operator = get_operator()
            except Exception:
                operator = "agent-hotel"

    # 获取工具详情
    detail = _http_get(f"{BASE_URL}/tool/query/detail?toolId={tool_id}")
    if detail.get("code") != 200:
        raise DuError(
            f"获取工具 {tool_id} 详情失败: {detail.get('message', detail)}",
            resp=detail,
        )

    context = detail["data"]["context"]
    for param in context[0]["params"]:
        key = param["paramKey"]
        # 工具 API 返回的 paramKey 可能带 "?" 后缀（表示可选参数），
        # 例如 "roomName?" → 实际传参时 key 为 "roomName"，需要去掉 "?" 后匹配
        lookup_key = key.rstrip("?")
        if lookup_key in overrides:
            val = overrides[lookup_key]
            if val is None:
                # 显式传 None 表示清空该参数（覆盖模板默认值为 null）
                param["paramValue"] = None
            else:
                param["paramValue"] = val
    context[0]["operator"] = operator

    if dry_run:
        print(f"\n[dry-run] 工具 {tool_id} 参数：")
        for p in context[0]["params"]:
            print(f"  {p['paramKey']} = {repr(p['paramValue'])}")
        return {"dry_run": True}

    resp = _http_post(f"{BASE_URL}/tool/execute", {"toolId": tool_id, "context": context})
    return resp


def get_result(resp: dict, item_key: str) -> Optional[str]:
    """从执行结果中提取指定 itemKey 的 value"""
    try:
        for r in resp["data"]["context"][0]["results"]:
            if r["itemKey"] == item_key:
                return r.get("value")
    except Exception:
        pass
    return None


def get_status(resp: dict) -> Optional[int]:
    """获取执行状态码（2=失败，其他=成功）"""
    try:
        return resp["data"]["context"][0].get("status")
    except Exception:
        return None


def get_error(resp: dict) -> str:
    """提取错误信息"""
    return get_result(resp, "DATA_UNITY_EXECUTE_ERROR_MESSAGE") or ""


def check_ok(resp: dict, step_name: str = "") -> None:
    """
    校验执行是否成功，失败时打印完整响应并退出。

    参数：
        resp      - DataUnity 执行响应
        step_name - 步骤描述（用于错误提示）
    """
    err = get_error(resp)
    st = get_status(resp)
    if st == 2 or "失败" in err:
        label = f"[ERROR] {step_name} 失败" if step_name else "[ERROR] 执行失败"
        print(f"{label}: {err}", file=sys.stderr)
        print(json.dumps(resp, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

