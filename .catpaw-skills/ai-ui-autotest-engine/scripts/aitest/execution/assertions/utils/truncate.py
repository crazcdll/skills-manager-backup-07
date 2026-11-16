"""递归截断超长字符串，保留完整结构。

不按 key 名过滤任何字段 —— 不同业务场景的接口数据结构差异巨大，
硬编码噪音字段白名单会导致换一个场景就失效。
只按 value 长度做截断，保留所有字段和结构信息。

对于 JSON 字符串 value，先尝试解析为 Python 对象再递归处理，
避免将结构化数据整体截断为「一段字符串」。
"""

import json

_MAX_STRING_LENGTH = 100  # 单个字符串超过此长度时截断，数据已反序列化，业务字段值通常较短


def _try_parse_json(s):
    """尝试将字符串解析为 JSON 对象，解析失败返回 None。"""
    s = s.strip()
    if not (s.startswith("{") or s.startswith("[")):
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None


def truncate_values(obj, _depth=0):
    """递归截断超长字符串，保留完整结构。

    - dict/list 结构完整保留，不按 key 名过滤
    - 非 string 标量原样保留
    - 超长字符串优先尝试解析为 JSON，成功则递归处理其结构
    - 解析失败或非 JSON 字符串，截断为 [truncated: N chars] 前缀 + 前 _MAX_STRING_LENGTH 字符
    - 最大递归深度 20 层防止栈溢出
    """
    if _depth > 20:
        return "[max depth]"
    if isinstance(obj, dict):
        return {k: truncate_values(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [truncate_values(v, _depth + 1) for v in obj]
    if isinstance(obj, str) and len(obj) > _MAX_STRING_LENGTH:
        parsed = _try_parse_json(obj)
        if parsed is not None:
            return truncate_values(parsed, _depth + 1)
        return f"[truncated: {len(obj)} chars] {obj[:_MAX_STRING_LENGTH]}..."
    return obj