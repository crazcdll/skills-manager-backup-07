"""
Topology 拓扑命令
"""
import json
import sys
import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from client import RaptorClient

from commands.base import Command
from commands.utils import parse_time


def _print_items(items: list, limit: int, sort_key: str):
    """格式化输出拓扑节点列表"""
    if sort_key == "count":
        items = sorted(items, key=lambda x: x.get("stats", {}).get("count", 0), reverse=True)
    elif sort_key == "tp99":
        items = sorted(items, key=lambda x: x.get("stats", {}).get("tp99", 0), reverse=True)
    elif sort_key == "fail":
        items = sorted(items, key=lambda x: 100 - x.get("stats", {}).get("successPercent", 100), reverse=True)

    for item in items[:limit]:
        stats = item.get("stats", {})
        domain = item.get("domain", "?")
        target = item.get("targetDomain", "?")
        print(f"   {domain} → {target}")
        print(f"      调用量: {stats.get('count', 0):.0f}  成功率: {stats.get('successPercent', 0):.1f}%  avg: {stats.get('avg', 0):.1f}ms  TP99: {stats.get('tp99', 0):.1f}ms")

    if len(items) > limit:
        print(f"   ... 共 {len(items)} 个，显示前 {limit} 个（用 -l 调整）")


class TopologyCommand(Command):
    """拓扑命令"""
    name = "topology"
    help_text = "获取上下游拓扑"

    def run(self, args):
        start_ts, end_ts = parse_time(args.start, getattr(args, "end", None))

        # queryType 根据时间范围选择
        duration_min = (end_ts - start_ts) / 60000
        if duration_min <= 60:
            query_type = "minute"
        elif duration_min <= 1440:
            query_type = "hour"
        else:
            query_type = "day"

        # 构建请求列表，记录各方向对应的 result index
        requests_list = []
        up_idx = None
        down_idx = None

        if args.direction in ["up", "all"]:
            up_idx = len(requests_list)
            requests_list.append({"domain": "*", "targetDomain": args.appkey})
        if args.direction in ["down", "all"]:
            down_idx = len(requests_list)
            requests_list.append({"domain": args.appkey, "targetDomain": "*"})

        body = {
            "startTime": start_ts,
            "endTime": end_ts,
            "queryType": query_type,
            "requests": requests_list
        }

        try:
            data = self.client.post("/dw/openapi/topology/data", body)

            if args.json:
                result = data.get("result", [])
                for i, items in enumerate(result):
                    if isinstance(items, list):
                        if args.sort is not None:
                            if args.sort == "count":
                                items = sorted(items, key=lambda x: x.get("stats", {}).get("count", 0), reverse=True)
                            elif args.sort == "tp99":
                                items = sorted(items, key=lambda x: x.get("stats", {}).get("tp99", 0), reverse=True)
                            elif args.sort == "fail":
                                items = sorted(items, key=lambda x: 100 - x.get("stats", {}).get("successPercent", 100), reverse=True)
                        if args.limit is not None:
                            items = items[:args.limit]
                        result[i] = items
                data["result"] = result
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return

            result = data.get("result", [[]])

            if not result or all(not r for r in result):
                print(f"❌ 未找到 {args.appkey} 的拓扑数据", file=sys.stderr)
                return

            # fallback 默认值（用户未显式传参时）
            sort_key = args.sort or "count"
            limit = args.limit if args.limit is not None else 20

            print(f"\n🔗 {args.appkey} 拓扑")

            if up_idx is not None:
                up_items = result[up_idx] if up_idx < len(result) else []
                print(f"\n⬆️  上游 ({len(up_items)} 个)")
                if up_items:
                    _print_items(up_items, limit, sort_key)
                else:
                    print("   （无上游调用）")

            if down_idx is not None:
                down_items = result[down_idx] if down_idx < len(result) else []
                print(f"\n⬇️  下游 ({len(down_items)} 个)")
                if down_items:
                    _print_items(down_items, limit, sort_key)
                else:
                    print("   （无下游调用）")

        except Exception as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser("topology", help="获取上下游拓扑")
        p.add_argument("-a", "--appkey", required=True, help="应用标识")
        p.add_argument("-s", "--start", default="1h", help="时间范围（5m/1h/7d）或绝对时间（2026-03-17 22:00:00）")
        p.add_argument("-e", "--end", default=None, help="结束时间（绝对时间，配合 -s 绝对时间使用）")
        p.add_argument("-d", "--direction", default="all", choices=["up", "down", "all"], help="方向（默认 all）")
        p.add_argument("-l", "--limit", type=int, default=None,
                       help="显示条数（默认 20；--json 模式下不指定则输出全量）")
        p.add_argument("--sort", default=None, choices=["count", "tp99", "fail"],
                       help="排序字段：count/tp99/fail（默认 count；--json 模式下不指定则不排序）")
        p.add_argument("--json", action="store_true", help="JSON 输出")
        return p


ALIASES = {
    "topo": "topology",
}
