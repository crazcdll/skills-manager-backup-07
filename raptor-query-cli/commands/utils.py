"""
公共工具函数 - 统一时间解析
"""
import re
from datetime import datetime, timedelta


# 带分隔符的绝对时间格式（strptime 安全，不存在歧义）
_ABS_TIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",   # 2026-04-06 13:57:00  (19 chars)
    "%Y-%m-%d %H:%M",      # 2026-04-06 13:57     (16 chars)
    "%Y-%m-%d",            # 2026-04-06           (10 chars)
]

# 紧凑格式：按长度精确匹配，避免 strptime 歧义拆分
_COMPACT_TIME_FORMATS = {
    14: "%Y%m%d%H%M%S",    # 20260406135700
    12: "%Y%m%d%H%M",      # 202604061357
    8:  "%Y%m%d",          # 20260406
}


def _parse_abs(time_str: str) -> datetime:
    """将绝对时间字符串解析为 datetime，失败返回 None"""
    # 带分隔符格式
    for fmt in _ABS_TIME_FORMATS:
        try:
            return datetime.strptime(time_str, fmt)
        except (ValueError, TypeError):
            continue
    # 纯数字紧凑格式：按长度精确匹配
    if time_str.isdigit():
        fmt = _COMPACT_TIME_FORMATS.get(len(time_str))
        if fmt:
            try:
                return datetime.strptime(time_str, fmt)
            except (ValueError, TypeError):
                pass
    return None


def _ceil_end_time(dt: datetime) -> datetime:
    """结束时间向上取整（适配 API 左闭右开 [start, end) 语义）

    规则：
    - 分=59 → 进位到下一小时 :00:00（如 13:59:00 / 13:59:30 / 13:59:59 → 14:00:00）
    - 秒=59（非59分） → 进位到下一分钟 :00（如 13:57:59 → 13:58:00）
    - 其他情况不动
    """
    if dt.minute == 59:
        # 59分（不论秒数） → 整小时（一步到位）
        dt = dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    elif dt.second == 59:
        # 非59分的59秒 → 下一分钟
        dt = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return dt


def parse_time(time_str: str, end_str: str = None) -> tuple:
    """解析时间为毫秒时间戳对 (start_ts, end_ts)

    支持格式：
    - 相对时间：5m / 1h / 7d
    - 绝对时间：2026-04-06 13:57:00 / 2026-04-06 13:57 / 2026-04-06
    - 紧凑绝对时间：20260406135700 / 202604061357 / 20260406

    end_str: 可选结束时间（绝对时间模式专用，相对时间模式忽略）
    结束时间会自动向上取整（59秒→整分，59分→整小时），适配 API 左闭右开语义。
    """
    now = datetime.now()

    start_dt = _parse_abs(time_str)
    if start_dt is not None:
        end_dt = (_parse_abs(end_str) if end_str else None) or now
        if end_str:
            end_dt = _ceil_end_time(end_dt)
        return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000)

    # 相对时间：5m / 1h / 7d
    match = re.match(r'^(\d+)(m|h|d)$', time_str.lower())
    if not match:
        raise ValueError(
            f"无效时间格式: {time_str}，支持 5m/1h/7d 或 2026-04-06 13:57:00 或 20260406135700"
        )
    value, unit = int(match.group(1)), match.group(2)
    delta = timedelta(minutes=value) if unit == 'm' else \
            timedelta(hours=value)   if unit == 'h' else \
            timedelta(days=value)
    end_ts = int(now.timestamp() * 1000)
    start_ts = int((now - delta).timestamp() * 1000)
    return start_ts, end_ts
