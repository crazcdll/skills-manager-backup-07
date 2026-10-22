"""
Logview 相关命令
- logview: 获取 logview ID 列表
- logview-detail: 获取 logview 堆栈详情（调用树）
"""
import json
import sys
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from client import RaptorClient

from commands.base import Command
from commands.utils import parse_time


def format_ts(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%H:%M:%S.%f")[:-3]


def extract_trace_ids(node: dict) -> list:
    """递归提取调用树中的 traceId"""
    import re
    traces = set()
    raw = json.dumps(node, ensure_ascii=False)
    # 匹配各种 traceId 格式
    for m in re.findall(r'traceId["\s:=]+([a-f0-9\-]+|\-?\d{15,})', raw, re.IGNORECASE):
        traces.add(m)
    return list(traces)


def calc_duration(node: dict) -> int:
    """计算节点耗时(ms)：自身 timestamp 到最后一个子孙的 timestamp"""
    ts = node.get("timestamp", 0)
    if not ts:
        return 0
    max_ts = ts
    def walk(n):
        nonlocal max_ts
        t = n.get("timestamp", 0)
        if t > max_ts:
            max_ts = t
        for c in n.get("children", []) or []:
            walk(c)
    walk(node)
    return max_ts - ts


def format_duration(ms: int) -> str:
    """格式化耗时"""
    if ms < 0:
        return ""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms/1000:.1f}s"
    else:
        return f"{ms/60000:.1f}min"


def print_tree(node: dict, depth: int = 0, max_depth: int = 10, _stats: dict = None) -> dict:
    """递归打印调用树，含耗时计算和重复节点折叠"""
    if _stats is None:
        _stats = {"total_nodes": 0, "error_nodes": 0, "root_ts": node.get("timestamp", 0)}
    if depth > max_depth:
        return _stats
    indent = "  " * depth
    t = node.get("type", "?")
    name = node.get("name", "?")
    status = node.get("status", "0")
    ts = node.get("timestamp", 0)
    data_str = str(node.get("data", "") or "")
    is_error = status != "0"
    children = node.get("children", []) or []

    _stats["total_nodes"] += 1
    if is_error:
        _stats["error_nodes"] += 1

    status_mark = "✅" if not is_error else "❌"
    time_str = format_ts(ts) if ts else ""
    dur = calc_duration(node)
    dur_str = f" ({format_duration(dur)})" if dur > 0 else ""

    print(f"{indent}{status_mark} [{t}] {name}  {time_str}{dur_str}")

    if data_str and data_str not in ("%TR", ""):
        d = data_str.replace("\\n", "\n").replace("\n", "\n").replace("\\t", "  ")
        if is_error:
            lines = [l.strip() for l in d.split("\n") if l.strip()]
            for line in lines:
                print(f"{indent}   | {line}")
        else:
            preview = (data_str[:100] + "…") if len(data_str) > 100 else data_str
            preview = preview.replace("\n", " ").strip()
            if preview:
                print(f"{indent}   └─ {preview}")

    # 折叠连续相同类型+名称的子节点
    i = 0
    while i < len(children):
        child = children[i]
        ct, cn = child.get("type", ""), child.get("name", "")
        # 找连续相同的
        j = i + 1
        while j < len(children):
            nc = children[j]
            if nc.get("type", "") == ct and nc.get("name", "") == cn and nc.get("status", "0") == "0":
                j += 1
            else:
                break
        repeat = j - i
        if repeat >= 3 and child.get("status", "0") == "0":
            # 折叠：只打印首尾 + 摘要
            print_tree(children[i], depth + 1, max_depth, _stats)
            print(f"{indent}  ⋮ ... 重复 {repeat - 2} 个 [{ct}] {cn}")
            _stats["total_nodes"] += repeat - 2
            print_tree(children[j - 1], depth + 1, max_depth, _stats)
            i = j
        else:
            print_tree(children[i], depth + 1, max_depth, _stats)
            i += 1

    # 根节点打印汇总
    if depth == 0:
        total_dur = calc_duration(node)
        print(f"\n📊 汇总: {_stats['total_nodes']} 个节点, {_stats['error_nodes']} 个异常, 总耗时 {format_duration(total_dur)}")

    return _stats


class LogviewCommand(Command):
    """获取 Logview ID 列表"""
    name = "logview"
    help_text = "获取 Logview ID 列表"

    def run(self, args):
        start_ts, end_ts = parse_time(args.start, getattr(args, "end", None))
        url = f"/dw/openapi/{args.data_type}/data/logviewIds"
        body = {
            "startTime": start_ts,
            "endTime": end_ts,
            "queryType": "minute",
            "requests": [{"appkey": args.appkey, "ip": args.ip,
                          "type": args.type, "name": args.name}]
        }
        try:
            data = self.client.post(url, body)
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return
            result = data.get("result", {})
            total = 0
            ids_shown = []
            for key, val in result.items():
                for ts, item in val.get("series", {}).items():
                    for lid in item.get("logviewIds", "").split(","):
                        if lid:
                            total += 1
                            if len(ids_shown) < args.limit:
                                ids_shown.append(lid)
            print(f"\n📝 {args.appkey} Logview IDs - 共 {total} 个（显示前 {len(ids_shown)} 个）")
            for lid in ids_shown:
                print(f"   {lid}")
            if ids_shown:
                print(f"\n💡 查看堆栈详情: raptor logview-detail -a {args.appkey} --id {ids_shown[0]}")
        except Exception as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser("logview", help="获取 Logview ID 列表")
        p.add_argument("-a", "--appkey", required=True, help="应用标识")
        p.add_argument("-s", "--start", default="1h", help="时间范围（默认 1h）或绝对时间（2026-03-12 20:00:00）")
        p.add_argument("-e", "--end", default=None, help="结束时间（绝对时间，默认 now）")
        p.add_argument("--data-type", default="problem", dest="data_type",
                       help="数据类型：transaction/event/problem（默认 problem）")
        p.add_argument("-t", "--type", default="error", help="类型（默认 error）")
        p.add_argument("-n", "--name", default="All", help="名称（默认 All）")
        p.add_argument("-i", "--ip", default="All", help="IP（默认 All）")
        p.add_argument("-l", "--limit", type=int, default=10, help="最多显示条数（默认 10）")
        p.add_argument("--json", action="store_true", help="JSON 输出")
        return p


class LogviewDetailCommand(Command):
    """获取 Logview 堆栈详情（调用树）"""
    name = "logview-detail"
    help_text = "获取 Logview 调用树详情"

    @staticmethod
    def parse_logview_url(url: str) -> dict:
        """从 Raptor logview 页面 URL 提取参数"""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        return {
            "appkey": params.get("domain", [""])[0],
            "logview_id": params.get("message", [""])[0],
            "metric_type": params.get("logViewType", ["other"])[0],
        }

    def run(self, args):
        # --url 模式：自动提取参数
        if args.url:
            url_params = self.parse_logview_url(args.url)
            appkey = args.appkey or url_params["appkey"]
            logview_id = args.logview_id or url_params["logview_id"]
            metric_type = args.metric_type or url_params["metric_type"]
            if not appkey or not logview_id:
                print(f"❌ URL 解析失败，缺少 domain 或 message 参数", file=sys.stderr)
                sys.exit(1)
        else:
            appkey = args.appkey
            logview_id = args.logview_id
            if not appkey or not logview_id:
                print(f"❌ 需要 -a/--appkey 和 --id，或使用 --url", file=sys.stderr)
                sys.exit(1)
            metric_type = args.metric_type or ("error" if "error" in logview_id.lower() else "other")

        body = {
            "appkey": appkey,
            "logviewId": logview_id,
            "metricType": metric_type,
        }
        try:
            data = self.client.post("/dw/openapi/logview/data", body)
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return

            code = data.get("code")
            if code != 10000:
                print(f"❌ code={code} {data.get('message','')}", file=sys.stderr)
                sys.exit(1)

            result = data.get("result", {})
            domain = result.get("domain", appkey)
            host = result.get("hostName", "N/A")
            ip = result.get("ipAddress", "N/A")
            msg = result.get("message", {})

            print(f"\n🔍 Logview: {args.logview_id}")
            print(f"   appkey: {domain}  host: {host}  IP: {ip}\n")

            if msg:
                print_tree(msg, depth=0, max_depth=args.depth)
                # 自动提取 traceId
                traces = extract_trace_ids(msg)
                if traces:
                    print(f"\n🔗 traceId: {', '.join(traces)}")
                    appkey_hint = appkey
                    print(f"   LogCenter 查询: logcenter query -l {appkey_hint} -s 30m -q \"{traces[0]}\" --size 20 --analyze")
            else:
                print("   (无调用树数据)")

        except Exception as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser("logview-detail", help="获取 Logview 调用树详情")
        p.add_argument("-a", "--appkey", default="", help="应用标识（--url 时可省略）")
        p.add_argument("--id", dest="logview_id", default="", help="Logview ID（--url 时可省略）")
        p.add_argument("--url", default="", help="Raptor Logview 页面 URL（自动提取参数）")
        p.add_argument("--metric-type", default="", dest="metric_type",
                       help="指标类型：error/other（默认自动判断）")
        p.add_argument("-d", "--depth", type=int, default=10, help="最大展示层级（默认 10）")
        p.add_argument("--json", action="store_true", help="输出原始 JSON")
        return p


ALIASES = {
    "lv": "logview",
    "ld": "logview-detail",
}
