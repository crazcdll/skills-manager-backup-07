#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接口步骤独立执行器：录制数据快照 → 匹配 → 拍平提取字段 → 写入证据文件。

不执行程序化断言，所有字段拍平为点号路径格式，由 AI 通过 override-step-result 判定。
"""
import os
import time

from core.util.json_utils import write_json_atomic
from core.errors import FlowStateError, StepAssertionError, soft_fail

from core.util.case_utils import resolve_mis
from core.flow.step_scheduler import update_step_result as fc_update_step
from core.audit.runtime_audit import append_event
from core.util.records import StepRecord, SRC_STEP, SHOT_STEP, frame_path
from mock.appmock_record import appmock_record_data
from assertions.data.api import match_items, _parse_json_body, _create_api_mock
from context import get_platform_ops


def _flatten_json(obj, prefix=""):
    """将嵌套 JSON 拍平为点号路径格式。

    {"a": {"b": 1, "c": [2, 3]}} → {"a.b": 1, "a.c.0": 2, "a.c.1": 3}
    """
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                items.update(_flatten_json(v, key))
            else:
                items[key] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            key = f"{prefix}.{i}"
            if isinstance(v, (dict, list)):
                items.update(_flatten_json(v, key))
            else:
                items[key] = v
    return items


def _fetch_and_match(mis, assertion, timeout_sec, case_ws=None, sid=None):
    deadline = time.time() + timeout_sec
    attempt = 0
    items = []
    while True:
        attempt += 1
        data = appmock_record_data(
            auto_filter=True, save_path=None, mis=mis, exclude_noise=True,
        )
        items = data.get("items", []) if data else []
        matched = match_items(items, assertion)
        if matched:
            return matched[-1], items, attempt
        if time.time() >= deadline:
            return None, items, attempt
        print(f"  API 步骤: 第 {attempt} 次轮询未匹配到接口，等待 2s 后重试...")
        time.sleep(2)


def _parse_query(url):
    """从 URL 中解析 query 参数为 dict，支持重复 key 取最后一个值。"""
    if "?" not in url:
        return {}
    qs = url.split("?", 1)[1]
    params = {}
    for part in qs.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    return params


def _extract_req_headers(headers):
    """从 reqHeaders 中提取对业务断言有用的核心字段。"""
    if not isinstance(headers, dict):
        return {}
    result = {}
    for key in ("userid", "csecuuid"):
        if headers.get(key) is not None:
            result[key] = headers[key]
    return result


def _extract_resp_headers(headers):
    """从 respHeaders 中提取对业务断言有用的核心字段。"""
    if not isinstance(headers, dict):
        return {}
    result = {}
    for key in ("M-TraceId", "M-Appkey"):
        if headers.get(key) is not None:
            result[key] = headers[key]
    return result


def _save_evidence(case_ws, sid, source, extracted_fields, expected_fields=None):
    """将结构化证据写入独立文件 api_evidence_<sid>.json，供 AI 读取分析。

    包含原始嵌套结构（source）、拍平后的字段（extracted_fields）和
    待校验的字段清单（expected_fields），AI 优先读取 extracted_fields 做判定。
    """
    if not case_ws:
        return None
    diag_dir = os.path.join(case_ws, "diagnostics")
    os.makedirs(diag_dir, exist_ok=True)
    path = os.path.join(diag_dir, f"api_evidence_{sid}.json")
    payload = {
        "source": source,
        "extracted_fields": extracted_fields,
    }
    if expected_fields:
        payload["expected_fields"] = expected_fields
    try:
        write_json_atomic(path, payload)
        return path
    except Exception as e:
        print(f"  ⚠️ 证据文件保存失败: {e}")
        return None


def _take_screenshot(case_ws, ci, sid):
    """API 步骤现场截图（归一到 frames/，失败返回 None）。"""
    try:
        ops = get_platform_ops()
        shot_name = f"{sid}.png" if sid else "api_step.png"
        if ci is not None:
            shot_name = f"case_{ci + 1:02d}_{shot_name}"
        out = frame_path(case_ws, shot_name)
        if ops.screenshot(out):
            return shot_name
    except Exception as e:
        soft_fail("device", "API_STEP_SHOT_FAILED", e)
    return None


def _finalize_step(root_dir, case_ws, record, ci, sid, ok_val, action_type,
                   screenshot=None, fail_reason="", assertions=None):
    """统一收口：落盘记录 + 更新 flow-context + 记录 audit 事件。"""
    record.append(case_ws)
    fc_update_step(root_dir, sid, ok_val, action_type,
                   screenshot=screenshot, fail_reason=fail_reason,
                   assertions=assertions)
    append_event(root_dir, "step.completed", {
        "case_index": ci, "sid": sid, "result": ok_val, "kind": action_type,
    })


def execute_api_step(root_dir, case_ws, ctx, step_def, args):
    step_start = time.time()
    sid = step_def.get("sid", "")
    desc = step_def.get("desc", "")
    assertion = step_def.get("api_assert") or {}
    ci = ctx.get("current_case", {}).get("index")
    mis = resolve_mis(ctx.get("meta", {}).get("user_mis", ""))

    if not mis:
        raise FlowStateError("API STEP ABORT: 无法确定 MIS 号")

    timeout_sec = assertion.get("wait_timeout_sec", 10)
    path = assertion.get("path", "")
    expected_fields = assertion.get("expected_fields", [])

    print(f"API STEP [{sid}]: {desc}")
    print(f"  匹配: path={path} timeout={timeout_sec}s")
    if expected_fields:
        print(f"  待校验字段: {len(expected_fields)} 个")

    item, items, attempts = _fetch_and_match(mis, assertion, timeout_sec, case_ws=case_ws, sid=sid)

    if not item:
        ok_val = 0
        recorded_endpoints = [
            (it.get("reqUrl") or "").split("?")[0]
            for it in items[:20]
        ]
        record = StepRecord(
            sid=sid, src=SRC_STEP, type="api", desc=desc, ok=ok_val, status="FAIL",
            ms=int((time.time() - step_start) * 1000), kind="api",
            expected_fields=expected_fields or None,
            failure={"error": f"未匹配到接口 (path={path})", "reason": "NO_MATCH",
                     "total_items": len(items), "attempts": attempts,
                     "recorded_endpoints": recorded_endpoints},
            extra={"matched": False},
        )
        _finalize_step(root_dir, case_ws, record, ci, sid, ok_val, "api", fail_reason="接口未匹配")
        print(f"API STEP [{sid}] ❌ FAIL | 未匹配到接口 (共轮询 {attempts} 次, 录制数据 {len(items)} 条)")
        raise StepAssertionError(f"API STEP [{sid}] 未匹配到接口")

    req_body = _parse_json_body(item.get("reqBody"))
    resp_body = _parse_json_body(item.get("respBody"))
    http_code = item.get("httpCode")
    req_headers = _extract_req_headers(item.get("reqHeaders"))
    resp_headers = _extract_resp_headers(item.get("respHeaders"))

    print(f"  ✅ MATCHED | http_code={http_code}")

    source = {
        "request": req_body if req_body is not None else {},
        "response": resp_body if resp_body is not None else {},
        "query": _parse_query(item.get("reqUrl") or ""),
        "http_code": http_code,
        "host": item.get("host", ""),
        "path": (item.get("reqUrl") or "").split("?")[0],
        "method": (item.get("method") or "").upper(),
        "req_headers": req_headers,
        "resp_headers": resp_headers,
    }

    # extracted_fields：对 query/request/headers 等业务字段做拍平，方便 AI 直接比对待校验字段。
    extracted_fields = {}
    for section in ("query", "request", "req_headers", "resp_headers"):
        if source.get(section):
            extracted_fields.update(_flatten_json(source[section], section))

    evidence_path = _save_evidence(case_ws, sid, source, extracted_fields, expected_fields=expected_fields)

    shot_name = _take_screenshot(case_ws, ci, sid)

    appmock_url = None
    try:
        url = _create_api_mock(item, assertion, mis)
        if url:
            appmock_url = url
            print(f"  AppMock: {url}")
    except Exception as e:
        soft_fail("infra", "API_APPMOCK_ARCHIVE_FAILED", e)

    record = StepRecord(
        sid=sid, src=SRC_STEP, type="api", desc=desc, ok=1, status="PASS",
        ms=int((time.time() - step_start) * 1000), kind="api",
        fields=extracted_fields,
        expected_fields=expected_fields or None,
        extra={
            "matched": True,
            "http_code": http_code,
            "host": source["host"],
            "path": source["path"],
            "method": source["method"],
            "evidence_path": evidence_path,
        },
    )
    if appmock_url:
        record.extra["appmock_url"] = appmock_url
    record.shot(shot_name, label="接口现场", kind=SHOT_STEP)

    assertions_data = None
    if expected_fields:
        assertions_data = {
            "api_fields": {
                "expected_fields": expected_fields,
                "evidence_path": evidence_path or "",
            }
        }

    _finalize_step(root_dir, case_ws, record, ci, sid, 1, "api",
                   screenshot=shot_name, fail_reason="", assertions=assertions_data)
    print(f"API STEP [{sid}] ✅ PASS | {http_code} {source['host']}{source['path']}")
    print(f"  📄 结构化证据: {evidence_path}")
    if expected_fields:
        print(f"  📋 待校验字段: {len(expected_fields)} 个（AI 将通过 hook 逐字段判定）")
    if shot_name:
        print(f"STEP 截图: {shot_name}")
    return 0
