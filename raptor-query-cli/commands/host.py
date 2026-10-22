"""
Host 相关命令
"""
import json
import re
import sys
import requests as req
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from client import RaptorClient

from commands.base import Command
from commands.utils import parse_time

COMMON_METRICS = [
    "cpu.busy", "cpu.idle", "cpu.steal",
    "load.1minPerCPU",
    "mem.memfree.percent", "mem.swapfree.percent",
    "disk.io.util/device=max",
    "net.if.in.Mbps.all", "net.if.out.Mbps.all",
    "ss.estab", "ss.closewait",
    "jvm.gc.count", "jvm.fullgc.count", "jvm.gc.time",
    "jvm.memory.used", "jvm.thread.count",
]

METRIC_DESC = {
    "cpu.busy":               "CPU 使用率 (%)",
    "cpu.idle":               "CPU 空闲率 (%)",
    "cpu.steal":              "CPU steal（虚拟化抢占）",
    "load.1minPerCPU":        "每核 1min 负载",
    "mem.memfree.percent":    "内存空闲率 (%)",
    "mem.swapfree.percent":   "Swap 空闲率 (%)",
    "disk.io.util/device=max":"磁盘 IO 利用率 max (%)",
    "net.if.in.Mbps.all":     "入流量 (Mbps)",
    "net.if.out.Mbps.all":    "出流量 (Mbps)",
    "ss.estab":               "TCP ESTABLISHED 连接数",
    "ss.closewait":           "TCP CLOSE_WAIT 连接数",
    "jvm.gc.count":           "GC 次数",
    "jvm.fullgc.count":       "Full GC 次数",
    "jvm.gc.time":            "GC 耗时 (ms)",
    "jvm.memory.used":        "JVM 堆内存使用",
    "jvm.thread.count":       "JVM 线程数",
}

QUERY_TYPE_MAP = {
    "minute": "minute", "min": "minute",
    "second": "second", "sec": "second",
    "2h": "twoHour", "twohour": "twoHour",
    "hour": "hour", "h": "hour",
    "day": "day", "d": "day",
}


def split_metrics(value):
    """逗号分割指标名，自动识别 /key=val,key=val 格式的 tag 部分不分割"""
    raw_parts = [p.strip() for p in value.split(",") if p.strip()]
    merged = []
    for part in raw_parts:
        if merged and '/' in merged[-1] and re.match(r'^\w+=', part):
            merged[-1] += ',' + part
        else:
            merged.append(part)
    return merged


def auto_query_type(time_str: str) -> str:
    """根据时间范围自动选粒度"""
    match = re.match(r'^(\d+)(m|h|d)$', time_str.lower())
    if not match:
        return "minute"
    value, unit = int(match.group(1)), match.group(2)
    if unit == 'm' or (unit == 'h' and value <= 2):
        return "minute"
    elif unit == 'h' and value <= 12:
        return "twoHour"
    else:
        return "hour"


class HostsCommand(Command):
    name = "hosts"
    help_text = "获取主机列表"

    def run(self, args):
        url = "/dw/openapi/host/endpoint/list"
        body = {"appkey": args.appkey}
        try:
            data = self.client.post(url, body)
            result = data.get("result", {})
            machines = result.get("machines", []) if result else []

            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return

            limit = args.limit or len(machines)
            print(f"\n📋 {args.appkey} 主机列表 - {len(machines)} 台")
            print(f"   {'主机名':<40}  {'IP':<16}")
            print(f"   {'-'*40}  {'-'*16}")
            for m in machines[:limit]:
                hostname = m.get("hostname", m.get("name", "N/A"))
                ip = m.get("ip", "N/A")
                print(f"   {hostname:<40}  {ip:<16}")
            if len(machines) > limit:
                print(f"   ... 还有 {len(machines) - limit} 台（用 -l 0 显示全部）")
        except Exception as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser("hosts", help="获取主机列表")
        p.add_argument("-a", "--appkey", required=True, help="应用标识")
        p.add_argument("-l", "--limit", type=int, default=15, help="最多显示条数（默认15，0=全量）")
        p.add_argument("--json", action="store_true", help="JSON 输出")
        return p


class HostMetricsCommand(Command):
    name = "host-metrics"
    help_text = "查询主机指标时序数据，或列出主机自定义指标"

    def run(self, args):
        endpoints = [e.strip() for e in args.endpoints.split(",") if e.strip()]

        # --list：列出主机的自定义指标
        if args.list:
            try:
                body = {"endpoint": endpoints, "limit": args.limit or 200,
                        "needApp": True, "needSidecar": False}
                if args.query:
                    body["query"] = args.query
                r = req.post(
                    f"http://cat.service.sankuai.com/raptor/s/hosts/metrics"  # internal: .sankuai.com intranet, HTTP allowed
                    f"?token={self.client.token}",
                    json=body,
                    timeout=10,
                )
                data = r.json()
                metrics = data.get("result", [])

                if args.json:
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    return

                print(f"\n📋 {endpoints[0]} 自定义指标 - {len(metrics)} 个\n")
                for m in metrics:
                    flags = []
                    if m.get("hasMinute"): flags.append("minute")
                    if m.get("hasSecond"): flags.append("second")
                    if m.get("hasTags"):   flags.append("hasTags")
                    print(f"   {m['id']:<60}  [{', '.join(flags)}]")
                print(f"\n💡 常用系统指标:")
                for m in COMMON_METRICS:
                    print(f"   {m:<40}  {METRIC_DESC.get(m,'')}")
            except Exception as e:
                print(f"❌ {e}", file=sys.stderr)
                sys.exit(1)
            return

        # 查指标时序数据（via /dw/openapi/host/data）
        if args.metrics:
            metrics = []
            for val in args.metrics:
                metrics.extend(split_metrics(val))
        else:
            metrics = ["cpu.busy", "mem.memfree.percent", "load.1minPerCPU"]

        start_ts, end_ts = parse_time(args.start, getattr(args, "end", None))
        qt = QUERY_TYPE_MAP.get(args.query_type.lower(), args.query_type) \
             if args.query_type else auto_query_type(args.start)

        body = {
            "appkey": args.appkey,
            "endpoints": endpoints,
            "metrics": metrics,
            "queryType": qt,
            "sample": args.sample.upper(),
            "startTime": start_ts,
            "endTime": end_ts,
        }

        try:
            data = self.client.post("/dw/openapi/host/data", body)

            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return

            trends = data.get("result", {}).get("metricTrends", {})
            if not trends:
                print("❌ 无数据", file=sys.stderr)
                return

            for host in endpoints:
                print(f"\n📊 {host}  ({args.start}  {qt}  {args.sample})\n")
                print(f"  {'指标':<40}  {'最新值':>10}  {'均值':>10}  {'最大值':>10}  {'时间':>6}")
                print(f"  {'-'*40}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*6}")
                for metric, info in trends.items():
                    ts_data = info.get("endpointsEntries", {}).get(host, {}).get("timeTrend", {})
                    non_null = {k: v for k, v in ts_data.items() if v is not None}
                    if not non_null:
                        print(f"  {metric:<40}  {'N/A':>10}")
                        continue
                    vals = list(non_null.values())
                    avg  = sum(vals) / len(vals)
                    maxv = max(vals)
                    latest_ts  = max(non_null.keys())
                    latest_val = non_null[latest_ts]
                    dt = datetime.fromtimestamp(int(latest_ts) / 1000).strftime("%H:%M")
                    print(f"  {metric:<40}  {latest_val:>10.3f}  {avg:>10.3f}  {maxv:>10.3f}  {dt:>6}")

                if args.trend and len(metrics) == 1:
                    # 单指标时输出时序趋势
                    metric = metrics[0]
                    ts_data = trends.get(metric, {}).get("endpointsEntries", {}) \
                                    .get(host, {}).get("timeTrend", {})
                    non_null = {k: v for k, v in ts_data.items() if v is not None}
                    sorted_pts = sorted(non_null.items())[-20:]
                    print(f"\n  📈 {metric} 时序（最近 {len(sorted_pts)} 点）\n")
                    print(f"  {'时间':>6}  {'值':>10}")
                    print(f"  {'-'*6}  {'-'*10}")
                    for ts, v in sorted_pts:
                        dt = datetime.fromtimestamp(int(ts) / 1000).strftime("%H:%M")
                        print(f"  {dt:>6}  {v:>10.3f}")

        except Exception as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser("host-metrics", help="查询主机指标时序数据")
        p.add_argument("-a", "--appkey", required=True, help="应用标识（必填）")
        p.add_argument("-e", "--endpoints", required=True, help="主机名，多个用逗号分隔")
        p.add_argument("-m", "--metrics", action="append", default=None,
                       help="指标名，多个用逗号分隔或多次 -m 指定；含 tag 的指标（如 name/key=val,key=val）自动识别（默认: cpu.busy,mem.memfree.percent,load.1minPerCPU）")
        p.add_argument("-s", "--start", default="1h", help="时间范围（默认 1h）")
        p.add_argument("--end", default=None, help="结束时间（绝对时间，配合 -s 绝对时间使用）")
        p.add_argument("-q", "--query-type", default="", dest="query_type",
                       help="时间粒度：minute/second/2h/hour/day（默认按时间范围自动选）")
        p.add_argument("--sample", default="AVG", help="聚合方式：AVG/MIN/MAX/COUNT（默认 AVG）")
        p.add_argument("--trend", action="store_true", help="单指标时输出完整时序（需 -m 指定单个指标）")
        p.add_argument("--list", action="store_true", help="列出主机的自定义指标（不查数值）")
        p.add_argument("--query", default="", help="--list 时按关键词过滤指标名（模糊匹配）")
        p.add_argument("-l", "--limit", type=int, default=200, help="--list 时最多返回条数")
        p.add_argument("--json", action="store_true", help="JSON 输出")
        return p


class SetsCommand(Command):
    name = "sets"
    help_text = "查询 appkey 的机器分组列表（set/机房/region/custom）"

    def _fetch_groups(self, appkey):
        """调用 /cat/s/host/group 获取分组列表"""
        r = req.get(
            f"http://cat.service.sankuai.com/cat/s/host/group",  # internal: .sankuai.com intranet, HTTP allowed
            params={"domain": appkey, "token": self.client.token},
            timeout=self.client.timeout,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", {})

    def _fetch_hosts_by_group(self, appkey, group_name):
        """调用 /raptor/s/hosts/machine/list 获取指定分组的机器"""
        r = req.get(
            f"http://cat.service.sankuai.com/raptor/s/hosts/machine/list",  # internal: .sankuai.com intranet, HTTP allowed
            params={"domain": appkey, "group": group_name, "token": self.client.token},
            timeout=self.client.timeout,
        )
        r.raise_for_status()
        data = r.json()
        result = data.get("result", {})
        return result.get("machines", [])

    def run(self, args):
        try:
            groups = self._fetch_groups(args.appkey)
        except Exception as e:
            print(f"❌ 获取分组失败: {e}", file=sys.stderr)
            sys.exit(1)

        sets     = groups.get("set", [])
        machines = groups.get("machine", [])
        customs  = groups.get("custom", [])
        regions  = groups.get("region", [])

        # 如果指定了 --group，校验合法性并查该分组下的机器
        if args.group:
            all_groups = sets + machines + customs + regions
            if args.group not in all_groups:
                print(f"❌ 分组 '{args.group}' 不存在，可用分组：", file=sys.stderr)
                if sets:    print(f"   set:    {', '.join(sets)}", file=sys.stderr)
                if machines: print(f"   机房:   {', '.join(machines)}", file=sys.stderr)
                if regions:  print(f"   region: {', '.join(regions)}", file=sys.stderr)
                if customs:  print(f"   custom: {', '.join(customs)}", file=sys.stderr)
                sys.exit(1)
            try:
                hosts = self._fetch_hosts_by_group(args.appkey, args.group)
            except Exception as e:
                print(f"❌ 获取机器列表失败: {e}", file=sys.stderr)
                sys.exit(1)

            if args.json:
                print(json.dumps(hosts, indent=2, ensure_ascii=False))
                return
            print(f"\n📋 {args.appkey} / 分组 {args.group} — {len(hosts)} 台\n")
            print(f"   {'主机名':<45}  {'IP':<16}")
            print(f"   {'-'*45}  {'-'*16}")
            for h in hosts:
                print(f"   {h.get('hostname',''):<45}  {h.get('ip',''):<16}")
            return

        # 无 --group 时，--json 输出分组名列表
        if args.json:
            print(json.dumps({"set": sets, "machine": machines, "custom": customs, "region": regions}, indent=2, ensure_ascii=False))
            return

        # 列出所有分组
        total = len(sets) + len(machines) + len(customs) + len(regions)
        print(f"\n📋 {args.appkey} 机器分组 — {total} 个\n")
        if sets:
            print(f"  🔹 set ({len(sets)} 个):")
            for s in sets:
                print(f"     {s}")
        if machines:
            print(f"\n  🔸 机房 ({len(machines)} 个):")
            for m in machines:
                print(f"     {m}")
        if regions:
            print(f"\n  🌐 region ({len(regions)} 个):")
            for r in regions:
                print(f"     {r}")
        if customs:
            print(f"\n  ⚙️  custom ({len(customs)} 个):")
            for c in customs:
                print(f"     {c}")
        print(f"\n💡 查某分组机器：raptor sets -a {args.appkey} --group <分组名>")
        print(f"   查监控数据时用 -i 指定分组：raptor tx -a {args.appkey} -i <分组名>")

    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser("sets", help="查询 appkey 的机器分组列表")
        p.add_argument("-a", "--appkey", required=True, help="应用标识")
        p.add_argument("--group", default="", help="指定分组名，列出该分组下所有机器")
        p.add_argument("--json", action="store_true", help="JSON 输出")
        return p


COMMANDS = {
    "hosts": HostsCommand,
    "host-metrics": HostMetricsCommand,
    "sets": SetsCommand,
}

ALIASES = {"hm": "host-metrics"}
