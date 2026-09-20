#!/usr/bin/env python3
"""业务接口数据验证工具函数。

从 AppMock 录制数据中按 path 匹配业务接口请求，
提取 request/response 原始数据并创建 AppMock 归档规则。

声明格式（steps-input.json 中 api_assert 的 path 字段）：
  {"path": "/path/to/api"}
  path 按 / 拆分后从末尾逐段匹配（后缀段匹配），至少最后一段一致。

本模块由 api_step_executor.py 在 C3 走查阶段按步骤即时调用。
"""
import json
import base64


from mock.appmock_rules import appmock_create, appmock_update, extract_mock_id

def _parse_json_body(body):
    if not body:
        return None
    if isinstance(body, (dict, list)):
        return body
    try:
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None

def _match_path_suffix(pattern, actual_path):
    """按 / 拆分路径段，从末尾匹配后缀段。

    断言 /api/hotel/orderfill/preview 可匹配 /hotelorder/trade/precreate/preview，
    因为末尾段 preview 相同。至少需要最后一段匹配。
    """
    p_segs = [s for s in pattern.split("/") if s]
    a_segs = [s for s in actual_path.split("/") if s]
    if not p_segs or not a_segs:
        return False
    i, j = len(p_segs) - 1, len(a_segs) - 1
    matched = 0
    while i >= 0 and j >= 0 and p_segs[i] == a_segs[j]:
        matched += 1
        i -= 1
        j -= 1
    return matched >= 1


def match_items(items, assertion):
    """从录制数据中匹配业务接口。

    匹配规则：
      - path: 按 / 拆分后从末尾逐段匹配（后缀段匹配），至少最后一段必须一致
      - path 为空：直接返回空列表（不放行）——否则会匹配任意录制项并取最后一条，
        形成「静默假通过」（生成侧已由 build_steps_json 硬校验 path 必填）
    """
    path_pattern = assertion.get("path") or ""
    if not str(path_pattern).strip():
        return []

    matched = []
    for item in items:
        item_url = item.get("reqUrl") or ""
        item_path = item_url.split("?")[0] if "?" in item_url else item_url

        if path_pattern and not _match_path_suffix(path_pattern, item_path):
            continue
        matched.append(item)

    return matched

def _create_api_mock(item, assertion, mis):
    req_body = item.get("reqBody", "")
    resp_body = item.get("respBody", "")
    req_headers = item.get("reqHeaderStr") or item.get("reqHeaders") or item.get("headers")
    req_val = req_body if isinstance(req_body, (dict, list)) else _parse_json_body(req_body)
    resp_val = resp_body if isinstance(resp_body, (dict, list)) else _parse_json_body(resp_body)
    header_val = req_headers if isinstance(req_headers, (dict, list)) else _parse_json_body(req_headers)
    archive = json.dumps({
        "request": req_val,
        "response": resp_val if resp_val is not None else {},
        "request_headers": header_val if header_val is not None else {},
    }, ensure_ascii=False)
    path = assertion.get("path", "")
    label = path.split("/")[-1] if path else "unknown"
    # rule / desc 必须稳定（不带时间戳）：平台对同 (rule, desc) 幂等复用，否则每个
    # 断言步骤都会新建一条归档规则，把分组撑到 100 条上限以上（超限后
    # getMockConfigs 直接 500，规则就无法枚举了）。
    rule = f"/autotest-api/{label}"
    result = appmock_create(
        rule=rule,
        response_body=archive,
        mis=mis,
        desc=f"[autotest-api] {path}",
        status=-1,
        method="POST",
    )
    mock_id = extract_mock_id(result)
    if not mock_id:
        print(f"APPMOCK ARCHIVE FAIL(api): {result.get('error', '未返回 mockId')}")
        return None
    # 命中复用不会刷新响应体，显式 update 写入本次录制数据（失败不影响证据链接）
    appmock_update(mock_id=mock_id, response_body=archive)
    prefix = base64.b64decode(
        "aHR0cHM6Ly9hcHBtb2NrLnNhbmt1YWkuY29tL2FwcF9tb2NrL21hbmFnZS9tb2NrRGV0YWlsLw=="
    ).decode()
    return f"{prefix}{mock_id}"