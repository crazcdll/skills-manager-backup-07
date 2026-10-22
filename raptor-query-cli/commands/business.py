"""
Business 业务指标命令
"""
import json
import sys
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from client import RaptorClient

from commands.base import Command
from commands.utils import parse_time


QUERY_TYPE_MAP = {
    "minute":       "minute",
    "5m":           "fiveMinute",
    "fiveMinute":   "fiveMinute",
    "20m":          "twentyMinute",
    "twentyMinute": "twentyMinute",
    "2h":           "twoHour",
    "twoHour":      "twoHour",
    "hour":         "hour",
    "day":          "day",
}

DEFAULT_QUERY_TYPE = "hour"


def resolve_query_type(qt: str) -> str:
    resolved = QUERY_TYPE_MAP.get(qt, qt)
    if resolved not in set(QUERY_TYPE_MAP.values()):
        raise ValueError(f"无效 queryType: {qt}，支持: {', '.join(sorted(QUERY_TYPE_MAP.keys()))}")
    return resolved


def parse_tag_filter(filters: list) -> dict:
    """解析 key=value 格式的 tag 过滤，值转为 list（API 要求）"""
    result = {}
    for f in (filters or []):
        if '=' not in f:
            raise ValueError(f"tag 过滤格式错误: {f}，应为 key=value")
        k, v = f.split('=', 1)
        result[k.strip()] = [v.strip()]  # API 要求 list
    return result


class BusinessCommand(Command):
    name = "business"
    help_text = "业务指标查询"

    def _list_tag_keys(self, appkey, business_key, start_ts, end_ts):
        body = {"appkey": appkey, "businessKey": business_key,
                "startTime": start_ts, "endTime": end_ts}
        data = self.client.post("/dw/openapi/business/meta/tagKeys", body)
        return data.get("result", [])

    def _is_composite(self, appkey, biz_key):
        """判断是否复合指标，返回子指标列表"""
        try:
            data = self.client.post("/dw/openapi/business/meta/businessKeysV2", {"appkey": appkey})
            custom = data.get("result", {}).get("customBusinesses", {})
            if biz_key in custom:
                sub = custom[biz_key].get("subMetrics", {})
                return list(sub.values()) if sub else []
        except Exception:
            pass
        return []

    def _list_tag_values(self, appkey, business_key, tag_name, start_ts, end_ts):
        body = {
            "appkey": appkey, "businessKey": business_key,
            "queryType": "hour", "metricType": "SUM",
            "tagMatch": {}, "groupByTagKey": tag_name,
            "startTime": start_ts, "endTime": end_ts,
        }
        data = self.client.post("/dw/openapi/business/dataV2", body)
        result = data.get("result", [])
        values = []
        for item in result:
            values.extend([k for k in item.get("result", {}).keys() if k])
        return values

    def run(self, args):
        if args.list_tags:
            start_ts, end_ts = parse_time(args.start, getattr(args, "end", None))
            try:
                meta_data = self.client.post(
                    "/dw/openapi/business/meta/businessKeysV2", {"appkey": args.appkey})
                basic = meta_data.get("result", {}).get("basicBusinesses", {})
                keys_to_query = [args.business] if args.business else list(basic.keys())

                if args.json:
                    output = {}
                    for biz in keys_to_query:
                        tags = self._list_tag_keys(args.appkey, biz, start_ts, end_ts)
                        output[biz] = [
                            {"tagId": t.get("tagId"), "name": t.get("name"),
                             "desc": t.get("desc"), "limit": t.get("limit"),
                             "values": self._list_tag_values(args.appkey, biz, t["name"], start_ts, end_ts)}
                            for t in tags
                        ]
                    print(json.dumps(output, indent=2, ensure_ascii=False))
                    return

                print(f"\n🏷️  {args.appkey} Business Tag 分析 ({args.start})\n")
                for biz in keys_to_query:
                    tags = self._list_tag_keys(args.appkey, biz, start_ts, end_ts)
                    if not tags:
                        print(f"  [{biz}] 无 tag")
                        continue
                    print(f"  [{biz}]")
                    for t in tags:
                        values = self._list_tag_values(args.appkey, biz, t["name"], start_ts, end_ts)
                        val_str = ", ".join(values) if values else "(无数据)"
                        print(f"    {t['name']:<20}  limit={t['limit']:<3}  values: {val_str}")
                    print()
            except Exception as e:
                print(f"❌ {e}", file=sys.stderr)
                sys.exit(1)

        elif args.business:
            start_ts, end_ts = parse_time(args.start, getattr(args, "end", None))
            tag_match = parse_tag_filter(args.filter)
            query_type = resolve_query_type(args.query_type)
            filter_str = f"  filter={tag_match}" if tag_match else ""

            # 检测复合指标：metricType 强制 AVG，tag 需要三段式 key
            subs = self._is_composite(args.appkey, args.business)
            is_composite = len(subs) > 0
            metric_type = "AVG" if is_composite else args.metric

            # 复合指标的 tag/groupBy 需要三段式: appkey:businessKey:tagKey
            group_by_key = args.group_by or ""
            if is_composite and group_by_key and ":" not in group_by_key:
                # 自动拼三段式：在子指标里找 tag 匹配
                for sub in subs:
                    sub_appkey = sub.get("appkey", "")
                    sub_biz = sub.get("businessKey", "")
                    group_by_key = f"{sub_appkey}:{sub_biz}:{group_by_key}"
                    break  # 用第一个子指标
            if is_composite and tag_match:
                # tag_match 的 key 也要三段式
                new_tm = {}
                for k, v in tag_match.items():
                    if ":" not in k:
                        for sub in subs:
                            k = f"{sub.get('appkey','')}:{sub.get('businessKey','')}:{k}"
                            break
                    new_tm[k] = v
                tag_match = new_tm
                filter_str = f"  filter={tag_match}" if tag_match else ""

            if is_composite and not args.json:
                print(f"ℹ️  复合指标，metricType 强制 AVG，子指标: {', '.join(s.get('businessKey','') for s in subs)}")

            body = {
                "appkey": args.appkey,
                "businessKey": args.business,
                "queryType": query_type,
                "metricType": metric_type,
                "tagMatch": tag_match,
                "groupByTagKey": group_by_key,
                "startTime": start_ts,
                "endTime": end_ts,
            }

            try:
                data = self.client.post("/dw/openapi/business/dataV2", body)

                if args.json:
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    return

                result = data.get("result", [])
                if not result:
                    print("❌ 无数据", file=sys.stderr)
                    return

                # groupBy 时：result[0].result = {tagVal: {ts: v}}, statistics = {tagVal: {COUNT,SUM,...}}
                r = result[0].get("result", {})
                stats = result[0].get("statistics", {})

                if args.group_by:
                    tag_vals = list(r.keys())
                    if not tag_vals:
                        print("❌ 无数据（tag 可能无值或时间范围太短）", file=sys.stderr)
                        return

                    if args.trend:
                        # 时序趋势：展示各 tag value 随时间变化
                        print(f"\n📊 {args.appkey}/{args.business}  groupBy={args.group_by}  ({args.start}){filter_str}\n")

                        # 收集所有有非 null 数据的时间点
                        all_ts = set()
                        for ts_data in r.values():
                            if ts_data:
                                all_ts.update(k for k, v in ts_data.items() if v is not None)
                        sorted_ts = sorted(all_ts)[-20:]  # 最近 20 个点

                        if not sorted_ts:
                            print("  (无时序数据)")
                        else:
                            # 表头
                            header = f"  {'时间':<16}" + "".join(f"  {tv[:12]:>12}" for tv in tag_vals)
                            print(header)
                            print("  " + "-" * (16 + 14 * len(tag_vals)))
                            for ts in sorted_ts:
                                dt = datetime.fromtimestamp(int(ts) / 1000).strftime("%m-%d %H:%M")
                                row = f"  {dt:<16}"
                                for tv in tag_vals:
                                    v = (r.get(tv) or {}).get(ts)
                                    row += f"  {(str(int(v)) if v is not None else '-'):>12}"
                                print(row)
                            print()

                    # 汇总表（无论 trend 与否都输出）
                    # 自动检测有哪些统计字段（兼容复合指标只有 AVG 的情况）
                    sample_stats = stats.get(tag_vals[0], {}) if tag_vals else {}
                    has_count = "COUNT" in sample_stats
                    has_sum = "SUM" in sample_stats
                    has_avg = "AVG" in sample_stats
                    has_pct = "Count_Percent(%)" in sample_stats

                    header = f"  {'Tag Value':<35}"
                    sep = f"  {'-'*35}"
                    if has_count: header += f"  {'COUNT':>10}"; sep += f"  {'-'*10}"
                    if has_sum:   header += f"  {'SUM':>12}"; sep += f"  {'-'*12}"
                    if has_avg:   header += f"  {'AVG':>12}"; sep += f"  {'-'*12}"
                    if has_pct:   header += f"  {'占比%':>7}"; sep += f"  {'-'*7}"
                    print(header)
                    print(sep)
                    for tv in tag_vals:
                        s = stats.get(tv, {})
                        row = f"  {tv:<35}"
                        if has_count: row += f"  {(s.get('COUNT') or 0):>10.0f}"
                        if has_sum:   row += f"  {(s.get('SUM') or 0):>12.0f}"
                        if has_avg:   row += f"  {(s.get('AVG') or 0):>12.2f}"
                        if has_pct:   row += f"  {(s.get('Count_Percent(%)') or 0):>6.1f}%"
                        print(row)

                else:
                    # 无 groupBy：取整体统计
                    print(f"\n📈 {args.appkey}/{args.business}  ({args.start}){filter_str}")
                    # 复合指标可能有多个子 key
                    displayed = False
                    for bk, s in stats.items():
                        if not isinstance(s, dict):
                            continue
                        count = s.get("COUNT") or 0
                        total = s.get("SUM") or 0
                        avg_val = s.get("AVG") or 0
                        if not avg_val and count:
                            avg_val = total / count
                        parts = []
                        if count: parts.append(f"COUNT={count:.0f}")
                        if total: parts.append(f"SUM={total:.0f}")
                        if avg_val: parts.append(f"AVG={avg_val:.2f}")
                        label = f"  [{bk}]" if len(stats) > 1 else "  "
                        print(f"{label} {' '.join(parts) if parts else '无数据'}")
                        displayed = True
                    if not displayed:
                        print("   无数据")

            except Exception as e:
                print(f"❌ {e}", file=sys.stderr)
                sys.exit(1)

        else:
            url = "/dw/openapi/business/meta/businessKeysV2"
            try:
                data = self.client.post(url, {"appkey": args.appkey})
                result = data.get("result", {})
                basic = result.get("basicBusinesses", {})
                custom = result.get("customBusinesses", {})

                if args.json:
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    return

                total = len(basic) + len(custom)
                print(f"\n📊 {args.appkey} 业务指标 - {total} 个")
                print(f"   普通指标: {len(basic)} 个")
                for k in sorted(basic.keys()):
                    print(f"     - {k}")
                print(f"   复合指标: {len(custom)} 个")
                for k in sorted(custom.keys()):
                    print(f"     - {k}")
            except Exception as e:
                print(f"❌ {e}", file=sys.stderr)
                sys.exit(1)

    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser("business", help="业务指标查询")
        p.add_argument("-a", "--appkey", required=True, help="应用标识")
        p.add_argument("-s", "--start", default="24h", help="时间范围（默认 24h）或绝对时间（2026-04-06 13:57:00）")
        p.add_argument("-e", "--end", default=None, help="结束时间（绝对时间，配合 -s 绝对时间使用）")
        p.add_argument("-b", "--business", default="", help="业务指标 key")
        p.add_argument("-m", "--metric", default="SUM",
                       help="聚合方式：COUNT/SUM/AVG/MAX/MIN（默认 SUM）")
        p.add_argument("-q", "--query-type", default=DEFAULT_QUERY_TYPE, dest="query_type",
                       help="时间粒度：minute/5m/20m/2h/hour/day（默认 hour）")
        p.add_argument("-g", "--group-by", default="", dest="group_by",
                       help="按 tag 分组（需配合 -b）")
        p.add_argument("-f", "--filter", action="append", default=[], metavar="key=value",
                       help="tag 过滤，可多次指定（如 -f progress=RtTask）")
        p.add_argument("--trend", action="store_true",
                       help="输出 groupBy 时序趋势（需配合 -g）")
        p.add_argument("--list-tags", action="store_true",
                       help="列出 tag 定义及实际值（可配合 -b）")
        p.add_argument("--json", action="store_true", help="JSON 输出")
        return p


ALIASES = {
    "bk": "business",
    "biz": "business",
}
