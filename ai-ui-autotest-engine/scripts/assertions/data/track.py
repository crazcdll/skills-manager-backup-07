#!/usr/bin/env python3
"""lx0 埋点数据验证 — 核心函数库（被 track_step_executor.py 导入）。

从 AppMock 录制数据中筛选 lx0.meituan.com 请求，解析灵犀事件，
按 match 标识匹配事件（val_bid → val_cid → nm 优先级），
提取原始事件数据，创建 AppMock 归档规则。
"""
import json
import base64

from mock.appmock_rules import appmock_create, appmock_update, extract_mock_id

LX0_HOST = "lx0.meituan.com"

def _try_json(s):
    if not isinstance(s, str) or not s.strip():
        return s if s else None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return s

def _normalize_host(host):
    return host.lower().rsplit(":", 1)[0] if ":" in host else host.lower()

def extract_lx0_items(items):
    return [item for item in items
            if _normalize_host(item.get("host", "")) == LX0_HOST]

def _parse_evs(evs, session_meta=None):
    """解析灵犀 evs 事件数组，可选注入 session 元数据。

    将 evs 中每个事件解析为字典，若传入 session_meta，则将 session 元数据
    以 _session_ 前缀注入事件（不覆盖事件已有字段），实现嵌套展平。
    """
    if isinstance(evs, str):
        try:
            evs = json.loads(evs)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(evs, list):
        return []
    results = []
    for ev in evs:
        if not isinstance(ev, dict):
            continue
        vl = ev.get("val_lab")
        if isinstance(vl, str):
            try:
                ev["val_lab"] = json.loads(vl)
            except (json.JSONDecodeError, TypeError):
                pass
        # 注入 session 元数据，实现展平
        if session_meta:
            for mk, mv in session_meta.items():
                if mk not in ev:
                    ev["_session_" + mk] = mv
        results.append(ev)
    return results

def _parse_body(body):
    """解析 lx0 请求 body，展平 session 嵌套。

    body 结构：数组，每项是 session（含元数据 + evs 事件数组）。
    从 session 中提取 evs 之外的公共元数据注入到每个事件，实现展平。
    """
    if not body:
        return []
    if isinstance(body, (dict, list)):
        data = body
    else:
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return []
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []
    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        evs = item.get("evs")
        if evs is not None:
            meta = {k: v for k, v in item.items() if k != "evs"}
            results.extend(_parse_evs(evs, meta))
        elif "nm" in item:
            vl = item.get("val_lab")
            if isinstance(vl, str):
                try:
                    item["val_lab"] = json.loads(vl)
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(item)
    return results

def parse_events(items):
    events = []
    event_to_item = []
    for item in items:
        for ev in _parse_body(item.get("reqBody")):
            if isinstance(ev, dict) and "nm" in ev:
                events.append(ev)
                event_to_item.append(item)
    return events, event_to_item

def match_events(events, assertion):
    """按标识匹配埋点事件。

    assertion 必须是 {"match": "标识字符串"} 格式。
    查找优先级：val_bid → val_cid → nm（值域无交叉，不会误匹配）。

    返回命中的 event 列表，取最后一条。
    """
    target = assertion.get("match") or None
    if not target:
        return []

    # 优先级1: val_bid（最精确）
    for ev in events:
        if ev.get("val_bid") == target:
            return [{"event": ev}]

    # 优先级2: val_cid（分类级别）
    for ev in events:
        if ev.get("val_cid") == target:
            return [{"event": ev}]

    # 优先级3: nm（事件类型）
    for ev in events:
        if ev.get("nm") == target:
            return [{"event": ev}]

    return []

def _collect_val_lab_layers(event):
    """从事件中提取 val_lab 及相关子层字段，供 AI 判定。"""
    layers = []
    vl = event.get("val_lab")
    if isinstance(vl, dict) and vl:
        layers.append(("val_lab", vl))
    tag = event.get("tag")
    if isinstance(tag, dict):
        val_cid = event.get("val_cid", "")
        for cat_name, cat_val in tag.items():
            if isinstance(cat_val, dict):
                if val_cid and val_cid in cat_val:
                    tag_inner = cat_val[val_cid]
                    if isinstance(tag_inner, dict):
                        layers.append((f"tag.{cat_name}.{val_cid}", tag_inner))
                else:
                    for sub_k, sub_v in cat_val.items():
                        if isinstance(sub_v, dict):
                            layers.append((f"tag.{cat_name}.{sub_k}", sub_v))
    lvl = event.get("lx_val_lab")
    if isinstance(lvl, dict) and lvl:
        layers.append(("lx_val_lab", lvl))
    return layers

def _create_track_mock(item, event, mis):
    req_body = item.get("reqBody", "")
    resp_body = item.get("respBody", "")
    req_headers = item.get("reqHeaderStr") or item.get("reqHeaders") or item.get("headers")
    req_val = req_body if isinstance(req_body, (dict, list)) else _try_json(req_body)
    resp_val = resp_body if isinstance(resp_body, (dict, list)) else _try_json(resp_body)
    header_val = req_headers if isinstance(req_headers, (dict, list)) else _try_json(req_headers)
    archive = json.dumps({
        "request": req_val,
        "response": resp_val if resp_val is not None else {},
        "request_headers": header_val if header_val is not None else {},
    }, ensure_ascii=False)
    event_id = event.get("val_bid") or event.get("val_cid") or event.get("nm", "unknown")
    # rule / desc 必须稳定（不带时间戳）：平台对同 (rule, desc) 幂等复用，否则每个
    # 埋点断言步骤都会新建一条归档规则，把分组撑到 100 条上限以上（超限后
    # getMockConfigs 直接 500，规则就无法枚举了）。
    rule = f"/autotest-track/{event_id}"
    result = appmock_create(
        rule=rule,
        response_body=archive,
        mis=mis,
        desc=f"[autotest-track] {event_id}",
        status=-1,
        method="POST",
    )
    mock_id = extract_mock_id(result)
    if not mock_id:
        print(f"APPMOCK ARCHIVE FAIL(track): {result.get('error', '未返回 mockId')}")
        return None
    # 命中复用不会刷新响应体，显式 update 写入本次录制数据（失败不影响证据链接）
    appmock_update(mock_id=mock_id, response_body=archive)
    prefix = base64.b64decode(
        "aHR0cHM6Ly9hcHBtb2NrLnNhbmt1YWkuY29tL2FwcF9tb2NrL21hbmFnZS9tb2NrRGV0YWlsLw=="
    ).decode()
    return f"{prefix}{mock_id}"
    mock_id = result.get("mockId")
    if mock_id:
        prefix = base64.b64decode(
            "aHR0cHM6Ly9hcHBtb2NrLnNhbmt1YWkuY29tL2FwcF9tb2NrL21hbmFnZS9tb2NrRGV0YWlsLw=="
        ).decode()
        return f"{prefix}{mock_id}"
    return None