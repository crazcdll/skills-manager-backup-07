"""RPC 接口粒度上下游查询"""
from .base import Command
from datetime import datetime, timedelta
import re


def parse_date(time_str: str, query_type: str = "hour") -> str:
    """解析时间为 date 格式。支持相对时间和绝对时间"""
    now = datetime.now()

    # 绝对时间
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d"):
        try:
            dt = datetime.strptime(time_str, fmt)
            return _dt_to_date(dt, query_type)
        except ValueError:
            continue

    # 相对时间
    match = re.match(r'^(\d+)(m|h|d|w)$', time_str.lower())
    if not match:
        raise ValueError(f"无效时间格式: {time_str}（支持 1h/1d/1w 或 2026-04-06 13:57:00 或 20260406135700）")
    value, unit = int(match.group(1)), match.group(2)
    delta = timedelta(minutes=value) if unit == 'm' else \
            timedelta(hours=value) if unit == 'h' else \
            timedelta(days=value) if unit == 'd' else \
            timedelta(weeks=value)
    dt = now - delta
    return _dt_to_date(dt, query_type)


def _dt_to_date(dt: datetime, query_type: str) -> str:
    """datetime 转 API date 格式（取整到对应粒度的起点）"""
    if query_type == "hour":
        # 取整到小时
        return dt.replace(minute=0, second=0, microsecond=0).strftime("%Y%m%d%H")
    elif query_type == "day":
        return dt.strftime("%Y%m%d")
    elif query_type == "week":
        # 周六为起始
        days_since_sat = (dt.weekday() + 2) % 7
        sat = dt - timedelta(days=days_since_sat)
        return sat.strftime("%Y%m%d")
    elif query_type == "month":
        return dt.strftime("%Y%m01")
    return dt.replace(minute=0, second=0, microsecond=0).strftime("%Y%m%d%H")


def _match_keyword(text: str, keyword: str) -> bool:
    """忽略大小写的子串匹配"""
    return keyword.lower() in text.lower()


def _format_total(total: int) -> str:
    """格式化调用量为可读字符串"""
    if total >= 1_0000_0000:
        return f"{total / 1_0000_0000:.1f}亿"
    elif total >= 1_0000:
        return f"{total / 1_0000:.0f}万"
    return str(total)


class RpcCommand(Command):
    name = "rpc"
    aliases = ["rpc"]
    help = "RPC 接口粒度上下游查询"

    @classmethod
    def add_parser(cls, sub):
        p = sub.add_parser(cls.name, help=cls.help, aliases=cls.aliases)
        p.add_argument("-a", "--appkey", required=True, help="应用 appkey")
        p.add_argument("-d", "--direction", default="down", choices=["up", "down"],
                       help="方向：up=上游(谁调我), down=下游(我调谁)")
        p.add_argument("-m", "--method", default="All",
                       help="接口名（默认 All，可指定具体接口）")
        p.add_argument("-s", "--start", default="0h",
                       help="时间（默认当前小时）：相对(1h/1d/1w)或绝对(2026-03-13 17:00:00)")
        p.add_argument("-q", "--query-type", default="hour",
                       choices=["hour", "day", "week", "month"],
                       help="查询粒度（默认 hour）")
        p.add_argument("-l", "--limit", type=int, default=None,
                       help="显示条数（默认 50；--json 模式下不指定则输出全量）")
        p.add_argument("--sort", default=None,
                       choices=["total", "avg", "fail", "failrate", "qps"],
                       help="排序字段：total/avg/fail/failrate/qps（默认 failrate；--json 模式下不指定则不排序）")
        p.add_argument("--target", default=None,
                       help="按目标 appkey 模糊过滤（子串匹配），命中自动展开接口明细")
        p.add_argument("--target-method", default=None,
                       help="按目标方法名模糊过滤（子串匹配），只显示包含匹配方法的下游并展开")
        p.add_argument("--expand", default=None,
                       help="展开指定下游的接口明细（appkey 子串匹配，不过滤其他行）")
        p.add_argument("--expand-all", action="store_true",
                       help="所有下游全部展开接口明细")
        p.add_argument("--json", action="store_true", help="JSON 输出")
        return p

    def run(self, args):
        query_type = args.query_type
        date = parse_date(args.start, query_type)

        direction = "upStreams" if args.direction == "up" else "downStreams"
        dir_label = "上游（谁调我）" if args.direction == "up" else "下游（我调谁）"

        body = {
            "date": date,
            "queryType": query_type,
            "domain": args.appkey,
            "method": args.method,
        }

        data = self.client.post(f"/dw/openapi/rpc/{direction}", body)
        result = data.get("result") or {}
        rpc_domains = result.get("rpcDomains", [])

        if args.json:
            import json
            # 用户显式传参时，在 json 模式下也生效
            if args.target or args.target_method or args.sort is not None or args.limit is not None:
                domains = rpc_domains[:]
                # target / target-method 过滤
                if args.target or args.target_method:
                    filtered = []
                    for d in domains:
                        if d.get("domain") == "All":
                            filtered.append(d)
                            continue
                        hit, _ = self._domain_matches_target(d, args.target, args.target_method)
                        if hit:
                            filtered.append(d)
                    domains = filtered
                # 排序（只排非 All 行）
                if args.sort is not None:
                    sort_map = {"total": "total", "avg": "avg", "fail": "fail", "failrate": "failPercent", "qps": "qps"}
                    all_rows = [d for d in domains if d.get("domain") == "All"]
                    detail_rows = [d for d in domains if d.get("domain") != "All"]
                    detail_rows.sort(key=lambda x: x.get(sort_map.get(args.sort, "failPercent"), 0), reverse=True)
                    domains = all_rows + detail_rows
                # limit 截断（只截非 All 行）
                if args.limit is not None:
                    all_rows = [d for d in domains if d.get("domain") == "All"]
                    detail_rows = [d for d in domains if d.get("domain") != "All"]
                    domains = all_rows + detail_rows[:args.limit]
                # 回写
                result["rpcDomains"] = domains
                data["result"] = result
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return

        print(f"\n📡 RPC {dir_label}: {args.appkey}")
        print(f"   时间: {date} ({query_type})  接口: {args.method}")

        if not rpc_domains:
            if args.method != "All":
                print(f"   ⚠️ 无数据，可能是接口名不匹配。")
            else:
                hints = {
                    "hour": "尝试 -s 1h（前一小时）或 -q day -s 0d（今天全天）",
                    "day": "尝试 -s 1d（昨天）或 -q week",
                    "week": "尝试 -s 1w（上一周）或 -q month",
                    "month": "尝试更早的月份",
                }
                print(f"   ⚠️ 无数据。{hints.get(query_type, '')}")
            return

        # 过滤掉 domain=All 的汇总行
        detail = [d for d in rpc_domains if d.get("domain") != "All"]
        summary = [d for d in rpc_domains if d.get("domain") == "All"]

        # fallback 默认值（用户未显式传参时）
        sort_key = args.sort or "failrate"
        limit = args.limit if args.limit is not None else 50

        # 排序
        sort_map = {"total": "total", "avg": "avg", "fail": "fail", "failrate": "failPercent", "qps": "qps"}
        detail.sort(key=lambda x: x.get(sort_map.get(sort_key, "failPercent"), 0), reverse=True)

        # 判断展示模式
        target = args.target
        target_method = args.target_method
        expand = args.expand
        expand_all = args.expand_all

        # 模式：target/target-method 过滤模式
        if target or target_method:
            self._print_filtered(detail, summary, args, target, target_method)
        # 模式：expand 指定展开
        elif expand:
            self._print_with_expand(detail, summary, args, expand)
        # 模式：expand-all 全展开
        elif expand_all:
            self._print_all_expanded(detail, summary, args)
        # 默认模式
        else:
            self._print_default(detail, summary, args)

    def _print_summary(self, summary):
        """输出汇总行"""
        if summary:
            s = summary[0]
            print(f"   汇总: total={s.get('total',0)}  avg={s.get('avg',0):.1f}ms  fail={s.get('fail',0)}  failPct={s.get('failPercent',0)*100:.4f}%  qps={s.get('qps',0):.1f}")

    def _print_footer(self, detail):
        """输出脚注"""
        flags = []
        if any(d.get("crossRegion") for d in detail):
            flags.append("🌍=跨Region")
        if any(d.get("crossIdc") for d in detail):
            flags.append("🏢=跨IDC")
        flags.append("⏱ timeout=代码中配置的RPC超时阈值(ms)")
        print(f"\n   {'  '.join(flags)}")

    def _get_flags(self, d):
        """获取跨域标记"""
        cross_region = "🌍" if d.get("crossRegion") else ""
        cross_idc = "🏢" if d.get("crossIdc") else ""
        return f"{cross_region}{cross_idc}" if cross_region or cross_idc else ""

    def _domain_matches_target(self, d, target, target_method):
        """判断一条 domain 记录是否命中过滤条件"""
        appkey_hit = False
        method_hits = []

        if target:
            appkey_hit = _match_keyword(d.get("domain", ""), target)

        methods = d.get("methods", [])
        if target_method:
            for m in methods:
                if _match_keyword(m.get("methodName", ""), target_method):
                    method_hits.append(m.get("methodName", ""))

        # 逻辑：如果同时传了 target 和 target-method，需要 appkey 命中 AND 方法命中
        # 如果只传了 target，appkey 命中即可
        # 如果只传了 target-method，方法命中即可
        if target and target_method:
            return appkey_hit and len(method_hits) > 0, method_hits
        elif target:
            return appkey_hit, method_hits
        elif target_method:
            return len(method_hits) > 0, method_hits
        return False, []

    def _print_expanded_domain(self, d, method_hits=None, indent="   "):
        """树状输出一个下游的接口明细"""
        domain = d.get("domain", "?")
        total = d.get("total", 0)
        avg = d.get("avg", 0)
        fail = d.get("fail", 0)
        timeout = d.get("timeOut", "-")
        flags = self._get_flags(d)

        print(f"\n{indent}{domain}  (汇总: total={_format_total(total)} avg={avg:.1f}ms fail={fail} timeout={timeout}ms) {flags}")

        methods = d.get("methods", [])
        if not methods:
            print(f"{indent}   （无接口明细）")
            return

        # 按 total 降序排列
        methods_sorted = sorted(methods, key=lambda x: x.get("total", 0), reverse=True)

        for i, m in enumerate(methods_sorted):
            is_last = (i == len(methods_sorted) - 1)
            prefix = "└─" if is_last else "├─"
            m_name = m.get("methodName", "?")
            m_total = m.get("total", 0)
            m_avg = m.get("avg", 0)
            m_fail = m.get("fail", 0)
            m_fail_pct = m.get("failPercent", 0)
            m_qps = m.get("qps", 0)
            m_timeout = m.get("timeOut", "-")
            m_flags = ""
            if m.get("crossRegion"):
                m_flags += "🌍"
            if m.get("crossIdc"):
                m_flags += "🏢"

            hit_mark = ""
            if method_hits and m_name in method_hits:
                hit_mark = " ← 匹配"

            print(f"{indent}   {prefix} {m_name:<50s} total={_format_total(m_total):<8s} avg={m_avg:.1f}ms  timeout={m_timeout}  fail={m_fail}  fail%={m_fail_pct*100:.4f}%  qps={m_qps:.1f} {m_flags}{hit_mark}")

    def _print_filtered(self, detail, summary, args, target, target_method):
        """过滤模式：--target / --target-method"""
        limit = args.limit if args.limit is not None else 50
        matched = []
        match_info = []  # (domain_item, method_hits)

        for d in detail:
            hit, method_hits = self._domain_matches_target(d, target, target_method)
            if hit:
                matched.append(d)
                match_info.append((d, method_hits))

        search_desc = []
        if target:
            search_desc.append(f"appkey含\"{target}\"")
        if target_method:
            search_desc.append(f"方法含\"{target_method}\"")

        print(f"   🔍 搜索: {' & '.join(search_desc)} — 命中 {len(matched)} 个下游")

        if not matched:
            print("   ⚠️ 无匹配结果，请检查关键词")
            return

        for d, method_hits in match_info[:limit]:
            self._print_expanded_domain(d, method_hits=method_hits)

        if len(matched) > limit:
            print(f"\n   ... 还有 {len(matched) - limit} 个，用 -l 增加显示数")

        self._print_footer(matched)

    def _print_with_expand(self, detail, summary, args, expand_keyword):
        """展开模式：--expand，展开匹配的下游，其余正常显示"""
        limit = args.limit if args.limit is not None else 50
        self._print_summary(summary)

        dir_col = "调用方" if args.direction == "up" else "被调方"
        print(f"\n   {'#':<4} {dir_col:<35s} {'接口':<20s} {'total':>10} {'avg(ms)':>8} {'timeout':>7} {'fail':>7} {'fail%':>6} {'qps':>10}")
        print(f"   {'-'*4} {'-'*35} {'-'*20} {'-'*10} {'-'*8} {'-'*7} {'-'*7} {'-'*6} {'-'*10}")

        for i, d in enumerate(detail[:limit]):
            domain = d.get("domain", "?")
            should_expand = _match_keyword(domain, expand_keyword)

            if should_expand:
                # 展开显示
                total = d.get("total", 0)
                avg = d.get("avg", 0)
                timeout = d.get("timeOut", "-")
                fail = d.get("fail", 0)
                fail_pct = d.get("failPercent", 0)
                qps = d.get("qps", 0)
                flags = self._get_flags(d)

                print(f"\n   {i+1:<4} ▼ {domain:<33s} {'':20s} {_format_total(total):>10s} {avg:>8.1f} {timeout:>7} {fail:>7} {fail_pct*100:>8.4f}% {qps:>10.1f} {flags}")

                methods = d.get("methods", [])
                methods_sorted = sorted(methods, key=lambda x: x.get("total", 0), reverse=True)
                for j, m in enumerate(methods_sorted):
                    is_last = (j == len(methods_sorted) - 1)
                    prefix = "└─" if is_last else "├─"
                    m_name = m.get("methodName", "?")
                    m_total = m.get("total", 0)
                    m_avg = m.get("avg", 0)
                    m_fail = m.get("fail", 0)
                    m_fail_pct = m.get("failPercent", 0)
                    m_qps = m.get("qps", 0)
                    m_timeout = m.get("timeOut", "-")
                    m_flags = ""
                    if m.get("crossRegion"):
                        m_flags += "🌍"
                    if m.get("crossIdc"):
                        m_flags += "🏢"
                    print(f"        {prefix} {m_name:<48s} {_format_total(m_total):>10s} {m_avg:>8.1f} {m_timeout:>7} {m_fail:>7} {m_fail_pct*100:>8.4f}% {m_qps:>10.1f} {m_flags}")
                print()
            else:
                # 正常合并行
                method = d.get("methodName", "?")
                total = d.get("total", 0)
                avg = d.get("avg", 0)
                timeout = d.get("timeOut", "-")
                fail = d.get("fail", 0)
                fail_pct = d.get("failPercent", 0)
                qps = d.get("qps", 0)
                flags = self._get_flags(d)

                print(f"   {i+1:<4} {domain:<35s} {method:<20s} {_format_total(total):>10s} {avg:>8.1f} {timeout:>7} {fail:>7} {fail_pct*100:>8.4f}% {qps:>10.1f} {flags}")

        if len(detail) > limit:
            print(f"\n   ... 还有 {len(detail) - limit} 条，用 -l 增加显示数")

        print(f"\n   共 {len(detail)} 个下游")
        self._print_footer(detail)

    def _print_all_expanded(self, detail, summary, args):
        """全展开模式：--expand-all"""
        limit = args.limit if args.limit is not None else 50
        self._print_summary(summary)
        print(f"\n   共 {len(detail)} 个下游（全部展开）")

        for d in detail[:limit]:
            self._print_expanded_domain(d)

        if len(detail) > limit:
            print(f"\n   ... 还有 {len(detail) - limit} 个，用 -l 增加显示数")

        self._print_footer(detail)

    def _print_default(self, detail, summary, args):
        """默认模式：合并展示 + timeout 列"""
        limit = args.limit if args.limit is not None else 50
        self._print_summary(summary)

        dir_col = "调用方" if args.direction == "up" else "被调方"
        print(f"\n   {'#':<4} {dir_col:<35s} {'接口':<20s} {'total':>10} {'avg(ms)':>8} {'timeout':>7} {'fail':>7} {'fail%':>6} {'qps':>10}")
        print(f"   {'-'*4} {'-'*35} {'-'*20} {'-'*10} {'-'*8} {'-'*7} {'-'*7} {'-'*6} {'-'*10}")

        for i, d in enumerate(detail[:limit]):
            domain = d.get("domain", "?")
            method = d.get("methodName", "?")
            total = d.get("total", 0)
            avg = d.get("avg", 0)
            timeout = d.get("timeOut", "-")
            fail = d.get("fail", 0)
            fail_pct = d.get("failPercent", 0)
            qps = d.get("qps", 0)
            flags = self._get_flags(d)

            print(f"   {i+1:<4} {domain:<35s} {method:<20s} {_format_total(total):>10s} {avg:>8.1f} {timeout:>7} {fail:>7} {fail_pct*100:>8.4f}% {qps:>10.1f} {flags}")

        if len(detail) > limit:
            print(f"\n   ... 还有 {len(detail) - limit} 条，用 -l 增加显示数")

        print(f"\n   共 {len(detail)} 个下游")
        self._print_footer(detail)
