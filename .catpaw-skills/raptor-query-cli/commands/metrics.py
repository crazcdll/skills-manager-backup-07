"""
Transaction/Event/Problem 指标数据查询命令
支持多 type、多 name 合并查询（单次请求，减少 QPM）
"""
import json
import sys
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Dict

if TYPE_CHECKING:
    from client import RaptorClient

from commands.base import Command
from commands.utils import parse_time, _parse_abs, _ceil_end_time


def format_number(num) -> str:
    return f"{int(num):,}"


def format_duration(ms) -> str:
    if ms < 1000:
        return f"{int(ms)}ms"
    return f"{ms/1000:.1f}s"


def _is_aligned(start_dt: datetime, end_dt: datetime) -> str:
    """检测时间范围是否对齐到整月/整周/整天/整小时，返回对应粒度或 None。

    判断优先级：month > week > day > hour（从大到小）
    - 整月：start/end 都是某月1号 00:00:00，且跨度 ≥ 1 个月
    - 整周：start/end 都是 00:00:00，且跨度是 7 天的倍数
    - 整天：start/end 都是 00:00:00，且跨度 ≥ 1 天
    - 整小时：start/end 都是 XX:00:00，且跨度 ≥ 1 小时
    """
    s_midnight = (start_dt.hour == 0 and start_dt.minute == 0 and start_dt.second == 0)
    e_midnight = (end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0)
    s_on_hour = (start_dt.minute == 0 and start_dt.second == 0)
    e_on_hour = (end_dt.minute == 0 and end_dt.second == 0)
    span = end_dt - start_dt

    # 整月：两端都是1号 00:00，跨度 ≥ 28 天
    if s_midnight and e_midnight and start_dt.day == 1 and end_dt.day == 1 and span.days >= 28:
        return "month"
    # 整周：两端都是 00:00，跨度是 7 天的倍数
    if s_midnight and e_midnight and span.days >= 7 and span.days % 7 == 0:
        return "week"
    # 整天：两端都是 00:00，跨度 ≥ 1 天
    if s_midnight and e_midnight and span.days >= 1:
        return "day"
    # 整小时：两端都是 XX:00:00，跨度 ≥ 1 小时
    if s_on_hour and e_on_hour and span.total_seconds() >= 3600:
        return "hour"
    return None


def auto_query_type(time_str: str, end_str: str = None) -> str:
    """根据时间范围自动选择查询粒度（second/minute/hour/day/week/month）

    策略：
    1. 先做边界对齐检测：若 start/end 恰好对齐整月/周/天/小时，直接用对应粒度
    2. 不满足对齐，按跨度 fallback：
       - ≤ 5min → second
       - ≤ 2h  → minute
       - ≤ 24h → hour
       - ≤ 7d  → day
       - ≤ 30d → week
       - > 30d → month
    """
    now = datetime.now()

    # 绝对时间：复用 utils._parse_abs 统一解析（含紧凑格式）
    start_dt = _parse_abs(time_str)
    if start_dt is not None:
        end_dt = (_parse_abs(end_str) if end_str else None) or now
        if end_str:
            end_dt = _ceil_end_time(end_dt)
        # 优先：边界对齐检测
        aligned = _is_aligned(start_dt, end_dt)
        if aligned:
            return aligned
        # fallback：按跨度推断
        span_hours = (end_dt - start_dt).total_seconds() / 3600
        return _span_to_query_type(span_hours)

    # 相对时间：5m / 1h / 7d — 无法做边界对齐，直接按跨度
    match = re.match(r'^(\d+)(m|h|d)$', time_str.lower())
    if not match:
        return "minute"
    value, unit = int(match.group(1)), match.group(2)
    if unit == 'm':
        span_hours = value / 60
    elif unit == 'h':
        span_hours = value
    else:
        span_hours = value * 24
    return _span_to_query_type(span_hours)


def _span_to_query_type(span_hours: float) -> str:
    """跨度（小时）→ 查询粒度（不满足整对齐时的 fallback）"""
    if span_hours <= 5 / 60:       # ≤ 5min
        return "second"
    if span_hours <= 2:            # ≤ 2h
        return "minute"
    if span_hours <= 24:           # ≤ 24h
        return "hour"
    if span_hours <= 24 * 7:       # ≤ 7d
        return "day"
    if span_hours <= 24 * 30:      # ≤ 30d
        return "week"
    return "month"


class MetricsCommand(Command):
    data_type: str = ""
    api_path: str = ""

    field_map = {
        "transaction": {"count_field": "totalCount", "fail_field": "fails", "has_tp": True},
        "event":       {"count_field": "totalCount", "fail_field": "fail",  "has_tp": False},
        "problem":     {"count_field": "totalCount", "fail_field": None,    "has_tp": False},
    }

    def _fetch_multi(self, appkey, types, names, ip, start_ts, end_ts, qt):
        ips = [x.strip() for x in ip.split(",") if x.strip()] if ip else ["All"]
        requests = [
            {"appkey": appkey, "ip": i, "type": t, "name": n}
            for i in ips for t in types for n in names
        ]
        if len(requests) > 500:
            raise ValueError(f"请求组合数 {len(requests)} 超过上限 500")
        body = {"requests": requests, "startTime": start_ts, "endTime": end_ts, "queryType": qt}
        return self.client.post(self.api_path, body)

    def _parse_all_series(self, result: dict) -> dict:
        parsed = {}
        for key, data_item in result.items():
            if not isinstance(data_item, dict):
                continue
            series_dict = data_item.get("series", {})
            if not series_dict:
                continue
            series_list = []
            for ts_str, point in series_dict.items():
                if isinstance(point, dict):
                    point["timestamp"] = int(ts_str)
                    series_list.append(point)
            series_list.sort(key=lambda x: x.get("timestamp", 0))
            parsed[key] = series_list
        return parsed

    def _print_summary_table(self, all_series, appkey, time_str):
        """多 type/name/ip：汇总对比表"""
        config = self.field_map.get(self.data_type, {})
        count_field = config.get("count_field", "totalCount")
        fail_field = config.get("fail_field")
        has_tp = config.get("has_tp", False)

        print(f"\n📊 {appkey}  ({time_str})\n")
        if has_tp:
            print(f"  {'ip / type / name':<55}  {'总请求':>10}  {'失败':>8}  {'成功率':>7}  {'均TP99(算术)':>14}")
            print(f"  {'-'*55}  {'-'*10}  {'-'*8}  {'-'*7}  {'-'*14}")
        else:
            print(f"  {'ip / type / name':<55}  {'总量':>10}")
            print(f"  {'-'*55}  {'-'*10}")

        for key, series in sorted(all_series.items()):
            parts = key.split("_", 3)
            # key 格式：appkey_ip_type_name
            label = f"{parts[1]}/{parts[2]}/{parts[3]}" if len(parts) >= 4 else key
            total_count = sum(p.get(count_field, 0) for p in series)
            if has_tp:
                total_fails = sum(p.get(fail_field, 0) for p in series) if fail_field else 0
                tp_vals = [p.get("tp99", 0) for p in series if p.get("tp99") is not None]
                avg_tp99 = sum(tp_vals) / len(tp_vals) if tp_vals else 0
                sr = ((total_count - total_fails) / total_count * 100) if total_count else 100.0
                print(f"  {label:<55}  {format_number(total_count):>10}  {format_number(total_fails):>8}  {sr:>6.1f}%  {format_duration(avg_tp99):>14}")
            else:
                print(f"  {label:<55}  {format_number(total_count):>10}")

        if has_tp:
            print(f"\n  ⚠️ 均TP99 为各时间点算术均值，非整体百分位。如需整体聚合值，使用 -q day/week/month")
            print(f"  💡 更多指标(TP999等)使用 --json 查看")

    def _print_single_trend(self, series, label, time_str):
        """单 type/name：时序趋势"""
        config = self.field_map.get(self.data_type, {})
        count_field = config.get("count_field", "totalCount")
        fail_field = config.get("fail_field")
        has_tp = config.get("has_tp", False)

        print(f"\n📊 {label}  ({time_str})\n")
        if has_tp:
            print(f"  {'时间':<17}  {'QPS/min':>9}  {'TP99':>10}  {'成功率':>7}")
            print(f"  {'-'*17}  {'-'*9}  {'-'*10}  {'-'*7}")
        else:
            print(f"  {'时间':<17}  {'数量':>10}")
            print(f"  {'-'*17}  {'-'*10}")

        total_count = 0
        total_fails = 0
        tp_values = []

        for point in series:
            ts = point.get("timestamp", 0)
            dt = datetime.fromtimestamp(ts / 1000).strftime("%m-%d %H:%M")
            count = point.get(count_field, 0)
            total_count += count
            if has_tp:
                fails = point.get(fail_field, 0) if fail_field else 0
                total_fails += fails
                tp99 = point.get("tp99", 0)
                tp_values.append(tp99)
                sr = ((count - fails) / count * 100) if count else 100.0
                print(f"  {dt:<17}  {format_number(count):>9}  {format_duration(tp99):>10}  {sr:>6.0f}%")
            else:
                print(f"  {dt:<17}  {format_number(count):>10}")

        print(f"\n  📈 汇总: 总={format_number(total_count)}", end="")
        if fail_field is not None:
            print(f"  失败={format_number(total_fails)}", end="")
        if tp_values:
            avg_tp99 = sum(tp_values) / len(tp_values)
            print(f"  均TP99={format_duration(int(avg_tp99))}(各点算术均值，非整体百分位)", end="")
        print()
        print(f"  💡 如需整体聚合值，使用 -q day/week/month；更多指标(TP999等)使用 --json 查看")

    def run(self, args):
        end_arg = getattr(args, "end", None)
        start_ts, end_ts = parse_time(args.start, end_arg)
        user_qt = getattr(args, "query_type", None)
        qt = user_qt if user_qt else auto_query_type(args.start, end_arg)
        types = [t.strip() for t in args.type.split(",") if t.strip()]
        names = [n.strip() for n in args.name.split(",") if n.strip()]
        ips = [x.strip() for x in args.ip.split(",") if x.strip()] if args.ip else ["All"]
        multi = len(types) > 1 or len(names) > 1 or len(ips) > 1

        # 提示用户当前使用的查询粒度（--json 模式下不打印，避免污染输出）
        qt_source = "手动指定" if user_qt else "自动推断"
        if not args.json:
            print(f"\nℹ️ 查询粒度: {qt} ({qt_source})")

        try:
            data = self._fetch_multi(args.appkey, types, names, args.ip, start_ts, end_ts, qt)
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return
            result = data.get("result", {})
            if not result:
                print("❌ 无数据", file=sys.stderr)
                return
            all_series = self._parse_all_series(result)
            if multi:
                self._print_summary_table(all_series, args.appkey, args.start)
            else:
                series = list(all_series.values())[0] if all_series else []
                label = f"{args.appkey} / {ips[0]} / {types[0]} / {names[0]}"
                self._print_single_trend(series, label, args.start)
        except Exception as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    @classmethod
    def add_parser(cls, subparsers, name: str, aliases, help_text: str):
        p = subparsers.add_parser(name, aliases=aliases, help=help_text)
        p.add_argument("-a", "--appkey", required=True, help="服务名")
        p.add_argument("-t", "--type", required=True,
                       help="类型，支持逗号分隔多个，如 URL,SQL,System")
        p.add_argument("-n", "--name", default="All",
                       help="名称，支持逗号分隔多个，默认 All")
        p.add_argument("-i", "--ip", default="All", help="IP/set名，默认 All（如 gray-release-nib-st）")
        p.add_argument("-s", "--start", default="5m", help="时间范围（5m/1h/7d）或绝对时间（2026-03-17 22:00:00）")
        p.add_argument("-e", "--end", default=None, help="结束时间（绝对时间，配合 -s 绝对时间使用）")
        p.add_argument("-q", "--query-type", default=None, dest="query_type",
                       choices=["second", "minute", "hour", "day", "week", "month"],
                       help="查询粒度（不指定则根据时间跨度自动推断）")
        p.add_argument("--json", action="store_true", help="输出原始 JSON")
        return p


class TransactionCommand(MetricsCommand):
    name = "transaction"
    help_text = "查询 Transaction 指标"
    data_type = "transaction"
    api_path = "/dw/openapi/transaction/data/datas"

    @staticmethod
    def add_parser(subparsers):
        return MetricsCommand.add_parser(
            subparsers, "transaction", ["tx"],
            "查询 Transaction 指标（QPS/TP99/成功率），-t 支持逗号分隔多 type"
        )


class EventCommand(MetricsCommand):
    name = "event"
    help_text = "查询 Event 指标"
    data_type = "event"
    api_path = "/dw/openapi/event/data/datas"

    def run(self, args):
        end_arg = getattr(args, "end", None)
        start_ts, end_ts = parse_time(args.start, end_arg)
        user_qt = getattr(args, "query_type", None)
        qt = user_qt if user_qt else auto_query_type(args.start, end_arg)
        types = [t.strip() for t in args.type.split(",") if t.strip()]
        names = [n.strip() for n in args.name.split(",") if n.strip()]
        ips = [x.strip() for x in args.ip.split(",") if x.strip()] if args.ip else ["All"]
        multi = len(types) > 1 or len(names) > 1 or len(ips) > 1
        trend = getattr(args, "trend", False)

        # 提示用户当前使用的查询粒度（--json 模式下不打印，避免污染输出）
        qt_source = "手动指定" if user_qt else "自动推断"
        if not args.json:
            print(f"\nℹ️ 查询粒度: {qt} ({qt_source})")

        try:
            data = self._fetch_multi(args.appkey, types, names, args.ip, start_ts, end_ts, qt)
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return
            result = data.get("result", {})
            if not result:
                print("❌ 无数据", file=sys.stderr)
                return
            all_series = self._parse_all_series(result)
            if multi and not trend:
                self._print_summary_table(all_series, args.appkey, args.start)
            elif multi and trend:
                # --trend：多 type/name/ip 逐一输出时序
                for key, series in all_series.items():
                    parts = key.split("_", 3)
                    label = f"{args.appkey} / {parts[1]}/{parts[2]}/{parts[3]}" if len(parts) >= 4 else f"{args.appkey} / {key}"
                    self._print_single_trend(series, label, args.start)
            else:
                series = list(all_series.values())[0] if all_series else []
                label = f"{args.appkey} / {ips[0]} / {types[0]} / {names[0]}"
                self._print_single_trend(series, label, args.start)
        except Exception as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser("event", aliases=["ev"],
                                   help="查询 Event 指标（事件统计），-t 支持逗号分隔多 type")
        p.add_argument("-a", "--appkey", required=True, help="服务名")
        p.add_argument("-t", "--type", required=True,
                       help="类型，支持逗号分隔多个，如 URL,SQL,System")
        p.add_argument("-n", "--name", default="All",
                       help="名称，支持逗号分隔多个，默认 All")
        p.add_argument("-i", "--ip", default="All", help="IP/set名，默认 All（如 gray-release-nib-st）")
        p.add_argument("-s", "--start", default="5m", help="时间范围（5m/1h/7d）或绝对时间（2026-04-06 13:57:00）")
        p.add_argument("-e", "--end", default=None, help="结束时间（绝对时间，配合 -s 绝对时间使用）")
        p.add_argument("-q", "--query-type", default=None, dest="query_type",
                       choices=["second", "minute", "hour", "day", "week", "month"],
                       help="查询粒度（不指定则根据时间跨度自动推断）")
        p.add_argument("--trend", action="store_true", help="多 type/name 时逐一输出时序趋势")
        p.add_argument("--json", action="store_true", help="输出原始 JSON")
        return p


class ProblemCommand(MetricsCommand):
    name = "problem"
    help_text = "查询 Problem 指标"
    data_type = "problem"
    api_path = "/dw/openapi/problem/data/datas"

    @staticmethod
    def add_parser(subparsers):
        return MetricsCommand.add_parser(
            subparsers, "problem", ["pb"],
            "查询 Problem 指标（异常/报错统计），-t 支持逗号分隔多 type"
        )
