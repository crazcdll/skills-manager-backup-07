#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接口步骤独立执行器：录制数据快照 → 匹配 → 拍平提取字段 → 写入证据文件。

不执行程序化断言，所有字段拍平为点号路径格式，由 AI 通过 override-step-result 判定。
"""
import json
import os
import time

from core.util.json_utils import read_json, write_json_atomic
from core.errors import FlowStateError, StepAssertionError, UsageError, PayloadError, soft_fail

from core.util.case_utils import resolve_mis, resolve_case_path, current_case_workspace
from core.flow.step_scheduler import update_step_result as fc_update_step
from core.audit.runtime_audit import append_event
from core.util.records import StepRecord, SRC_STEP, SHOT_STEP, frame_path
from core.flow.flow_context import load_context as fc_load
from mock.appmock_record import appmock_record_data
from assertions.data.api import match_items, _parse_json_body, _create_api_mock
from context import get_platform_ops


def _try_parse_json_text(text):
    """字符串本身是 JSON 对象/数组时解析它（如 MRN 的 pageQueryStr 内嵌业务参数）。

    返回 dict/list，或 None（非 JSON / 顶层为标量）。
    """
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def _flatten_value(value, key):
    """拍平单个键值：容器递归；疑似 JSON 字符串解析后继续拍平；否则作为叶子。"""
    if isinstance(value, (dict, list)):
        return _flatten_json(value, key)
    parsed = _try_parse_json_text(value)
    if parsed is not None:
        return _flatten_json(parsed, key)
    return {key: value}


def _flatten_json(obj, prefix=""):
    """将嵌套 JSON 拍平为点号路径格式。

    {"a": {"b": 1, "c": [2, 3]}} → {"a.b": 1, "a.c.0": 2, "a.c.1": 3}
    值为 JSON 字符串时（如 request.pageQueryStr）继续向下拍平：
    {"p": "{\"goods_id\":\"1\"}"} → {"p.goods_id": "1"}
    """
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            items.update(_flatten_value(v, key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            items.update(_flatten_value(v, f"{prefix}.{i}"))
    return items


# ── 响应体：浅骨架 + 按需检索（均不持久化，只做派生视图）──────────────
# 响应体叶子数可达数千、最大深度 14：全量抽平（实测 245KB）比原始响应（106KB）
# 还大，截断也只降到 130–200KB；而把它放进 extracted_fields 又会被报告层逐字段
# 展开，使报告体积 +32%~+76%。因此响应侧一律**不写产物**，全部按需从证据文件的
# source.response 现算：
#   response-search --skeleton        看结构（浅骨架：深度有限、数组折叠）
#   response-search --query <关键字>   按用例里的文案/值定位路径
#   response-search --path <路径>      精确定取值作为断言依据
_SKELETON_MAX_SEGMENTS = 4      # 含 "response" 段，即 response.a.b.c
_SKELETON_MAX_KEYS = 300        # 防御异常大的浅响应
_RESP_VALUE_MAX_LEN = 200
_SEARCH_DEFAULT_LIMIT = 50


def _display_value(value):
    """将任意值渲染为短字符串（容器不展开，防止输出被巨对象撞爆）。"""
    if isinstance(value, dict):
        return f"<object: {len(value)} keys>"
    if isinstance(value, list):
        return f"<list: {len(value)} items>"
    if isinstance(value, str):
        # 折行会让命中结果在终端里散成多行，统一压成单行
        flat = value.replace("\r", " ").replace("\n", " ")
        if len(flat) > _RESP_VALUE_MAX_LEN:
            return flat[:_RESP_VALUE_MAX_LEN] + f"…<+{len(flat) - _RESP_VALUE_MAX_LEN} chars>"
        return flat
    return value


def _flatten_skeleton(obj, prefix="response", max_segments=_SKELETON_MAX_SEGMENTS,
                      max_keys=_SKELETON_MAX_KEYS):
    """抽平响应「浅骨架」：只保留路径段数 ≤ max_segments 的叶子；数组整体折叠。

    与 _flatten_json（全量抽平）区别：不展开数组元素、不无限递归，体积可控。
    """
    items = {}

    def walk(node, path):
        if len(path) > max_segments or len(items) > max_keys:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + [str(k)])
        elif isinstance(node, list):
            items[".".join(path)] = f"<list: {len(node)} items>"
        else:
            items[".".join(path)] = _display_value(node)

    walk(obj, [prefix])
    if len(items) > max_keys:
        kept = dict(list(items.items())[:max_keys])
        kept[".".join([prefix, "__truncated__"])] = f"<+{len(items) - max_keys} more keys>"
        return kept
    return items


def search_response(response, query, limit=_SEARCH_DEFAULT_LIMIT):
    """在原始响应里按「键名子串」或「值子串」检索，返回 [(path, value_display)]。

    路径以 response. 开头（与 extracted_fields 键命名一致），可直接用作
    assert-fields 的 field。大小写不敏感。
    """
    hits = []
    needle = str(query or "").strip().lower()
    if not needle:
        return hits

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if len(hits) >= limit:
                    return
                key_str = str(k)
                if needle in key_str.lower():
                    hits.append((".".join(path + [key_str]), _display_value(v)))
                    if len(hits) >= limit:
                        return
                walk(v, path + [key_str])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if len(hits) >= limit:
                    return
                walk(v, path + [str(i)])
        elif len(hits) < limit and needle in str(node).lower():
            hits.append((".".join(path), _display_value(node)))

    walk(response, ["response"])
    return hits


def get_by_path(response, path):
    """按点号路径从原始响应取值，返回 (found, value)。

    路径可带/不带 response. 前缀；数组用数字下标（如 data.roomList.0.price）。
    """
    segs = [s for s in str(path or "").split(".") if s != ""]
    if segs and segs[0] == "response":
        segs = segs[1:]
    node = response
    for seg in segs:
        if isinstance(node, dict):
            if seg not in node:
                return False, None
            node = node[seg]
        elif isinstance(node, list):
            if not seg.isdigit() or int(seg) >= len(node):
                return False, None
            node = node[int(seg)]
        else:
            return False, None
    return True, node


def _load_response_evidence(case_ws, sid):
    """读取 API 证据文件里的原始响应，返回 (evidence_path, response)。"""
    diag_dir = os.path.join(case_ws, "diagnostics")
    if not sid:
        # 未指定 SID：自动选最新的 api_evidence_*.json，便于 AI 探索
        candidates = []
        if os.path.isdir(diag_dir):
            for name in os.listdir(diag_dir):
                if name.startswith("api_evidence_") and name.endswith(".json"):
                    full = os.path.join(diag_dir, name)
                    candidates.append((os.path.getmtime(full), full))
        if not candidates:
            raise PayloadError("未找到任何 api_evidence_*.json，请先执行 API 步骤")
        evidence_path = sorted(candidates)[-1][1]
    else:
        evidence_path = os.path.join(diag_dir, f"api_evidence_{sid}.json")
    if not os.path.isfile(evidence_path):
        raise PayloadError(
            f"证据文件不存在: {evidence_path}"
            f"（response-search 仅支持 api 步骤；track 字段断言请读 "
            f"diagnostics/track_evidence_{sid or '<SID>'}.json）"
        )
    data = read_json(evidence_path, default={})
    response = (data.get("source") or {}).get("response")
    if response is None:
        raise PayloadError(f"证据文件无 source.response: {evidence_path}")
    return evidence_path, response


def cmd_response_search(args):
    """response-search：在 API 步骤的原始响应里按关键字/路径检索。

    用例通常只声明「文案/值」（如“减碳203.2g”），不写 JSON 路径；本命令让 AI 先用
    关键字在响应里定位到具体路径，再用 --path 精确取值作为字段断言依据。
    """
    root_dir = resolve_case_path(args.dir)
    flow_context = fc_load(root_dir)
    if flow_context is None:
        raise FlowStateError("RESPONSE-SEARCH ABORT: flow-context.json 不存在")
    case_ws = current_case_workspace(root_dir, flow_context)

    sid = getattr(args, "sid", None)
    evidence_path, response = _load_response_evidence(case_ws, sid)
    query = getattr(args, "query", None)
    path = getattr(args, "path", None)
    limit = int(getattr(args, "limit", None) or _SEARCH_DEFAULT_LIMIT)

    if getattr(args, "skeleton", False):
        skeleton = _flatten_skeleton(response, prefix="response")
        print(f"RESPONSE-SKELETON [{sid or 'auto'}] {len(skeleton)} 键"
              f"（深度 ≤{_SKELETON_MAX_SEGMENTS}、数组折叠）")
        print(f"  证据: {evidence_path}")
        for key, value in skeleton.items():
            print(f"  {key} = {value}")
        print("  提示: 用 --query <用例里的文案/值> 在完整响应里检索，再 --path <路径> 精确取值")
        return None

    if path:
        found, value = get_by_path(response, path)
        print(f"RESPONSE PATH: {path}")
        if not found:
            print("  <未找到该路径>")
            return 1
        print(f"  = {_display_value(value)}")
        return None

    hits = search_response(response, query, limit=limit)
    print(f"RESPONSE-SEARCH [{sid or 'auto'}] query={query!r} 命中 {len(hits)} 条（上限 {limit}）")
    print(f"  证据: {evidence_path}")
    if not hits:
        print("  <无命中，可换关键字或用浅骨架键名再试>")
        return 1
    for hit_path, hit_value in hits:
        print(f"  {hit_path} = {hit_value}")
    if len(hits) >= limit:
        print(f"  ⚠️ 命中数已达上限 {limit}，结果被截断：请用更具体的关键字（键名/值）重试，"
              f"或直接用 --path <路径> 精确取值（路径可从骨架键名推导）")
    print("  提示: 用 --path <路径> 精确取值后写入 assert-fields 的 field")
    return None


def _save_response_skeleton(case_ws, sid, source, response):
    """把响应浅骨架写成**独立文件**（不进 steps.jsonl / 报告，避免体积膨胀）。

    产物：case_ws/diagnostics/response_skeleton_<sid>.md
    AI 可直接 read_file 该小文件建立结构印象；精确取值走 response-search --query/--path。
    返回文件路径，未写入返回 None。
    """
    if not case_ws or not isinstance(response, (dict, list)) or not response:
        return None
    try:
        skeleton = _flatten_skeleton(response, prefix="response")
        diag_dir = os.path.join(case_ws, "diagnostics")
        os.makedirs(diag_dir, exist_ok=True)
        path = os.path.join(diag_dir, f"response_skeleton_{sid}.md")
        head = [
            f"# 响应浅骨架 — {sid}",
            "",
            f"- 接口: {(source.get('method') or '').upper()} "
            f"{source.get('host', '')}{source.get('path', '')}",
            f"- http_code: {source.get('http_code')}",
            f"- 字段数: {len(skeleton)}（深度 ≤{_SKELETON_MAX_SEGMENTS}、数组折叠）",
            f"- 全量响应: api_evidence_{sid}.json；精确取值用 response-search --query/--path",
            "",
        ]
        with open(path, "w", encoding="utf-8") as _f:
            _f.write("\n".join(head + [f"{k} = {v}" for k, v in skeleton.items()]) + "\n")
        return path
    except OSError as e:
        soft_fail("infra", "RESPONSE_SKELETON_WRITE_FAILED", e)
        return None


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

    # 响应体不进 extracted_fields：实测报告层会把每个字段展开成组内条目，
    # 浅骨架（5.7KB）会把报告体积放大 +32%~+76%。骨架作为「派生视图」改为
    # response-search --skeleton 按需输出，原始响应仍在证据文件里供 --query/--path 检索。
    extracted_fields = {}
    for section in ("query", "request", "req_headers", "resp_headers"):
        if source.get(section):
            extracted_fields.update(_flatten_json(source[section], section))
    # 接口元信息（状态码/方法/路径/域名）：给「状态码断言」一个统一落点。
    # 断言侧统一写 {"source":"meta","field":"http_code"}，AI 可按 meta.* grep，
    # 避免每次都用自造约定（历史实现把 http_code 只留在记录 extra 里，取数无固定位置）。
    extracted_fields.update({
        "meta.http_code": http_code,
        "meta.method": source["method"],
        "meta.path": source["path"],
        "meta.host": source["host"],
    })

    # 响应浅骨架：单独落文件供 AI 读（不进 extracted_fields，避免报告逐字段展开膨胀）
    skeleton_path = _save_response_skeleton(case_ws, sid, source, source.get("response"))
    if skeleton_path:
        print(f"  \U0001f4c4 响应浅骨架: {skeleton_path}")

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
