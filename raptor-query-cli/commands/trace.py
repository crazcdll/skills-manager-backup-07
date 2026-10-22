"""
Trace 链路追踪命令
- trace: 通过 traceId 查询调用链，按 appKey 过滤 span

功能：
  1. 树形调用链展示（按 spanId 层级缩进，还原父子关系）
  2. 慢 Span 自动展示全部 annotation（db.statement、peer.hostname 等）
  3. --span 参数：指定 spanId 前缀，只看该子树（下钻）
  4. 自动诊断分析（--diagnose）：识别瓶颈类型并给出建议

底层：Raptor MCP（见 commands/mcp_client.py）
  - `get_by_traceid_and_appkey`（按 appkey 过滤，数据精准）
  - `get_tracedetail_by_traceid`（全量查询，无需 appkey，数据量大）
"""
import json
from collections import defaultdict

from commands.base import Command
from commands.mcp_client import call_mcp_tool

# 慢 Span 阈值（ms）
SLOW_THRESHOLD = 500

# annotation 关键字段（诊断用）
DIAG_KEYS = {
    'db.statement', 'db.system', 'peer.hostname', 'peer.address',
    'http.url', 'http.method', 'http.status_code',
    'errorMsg', 'exception', 'error',
    'MTRootMethod', 'url', 'code', 'status',
    'sql', 'SQL', 'db', 'cache.key',
}


# ─────────────────────────────────────────────
# MCP 调用层（统一走 commands/mcp_client.py，按响应 id 匹配）
# ─────────────────────────────────────────────

def _call_mcp_trace(trace_id: str, app_key: str, timeout: int = 30) -> list:
    data = call_mcp_tool("trace_by_appkey",
                         {"traceId": trace_id, "appKey": app_key},
                         timeout=timeout)
    return data.get('traces', [])


def _call_mcp_trace_all(trace_id: str, timeout: int = 30) -> list:
    """全量查询：只需 traceId，返回所有 span（不按 appkey 过滤）"""
    data = call_mcp_tool("trace_all", {"traceId": trace_id}, timeout=timeout)
    return data.get('traces', [])


# ─────────────────────────────────────────────
# 树形构建 & 展示
# ─────────────────────────────────────────────

def _span_dur(s: dict) -> int:
    try:
        return int(s.get('serverDuration') or s.get('clientDuration') or 0)
    except (ValueError, TypeError):
        return 0


def _get_annotations(s: dict) -> dict:
    """返回 span 的所有 annotation 字典"""
    return {a.get('key', ''): str(a.get('value', '')) for a in s.get('annotation', [])}


def _build_tree(spans: list) -> dict:
    """
    按 spanId 层级（0-22, 0-22-1, 0-22-1-2）构建树。
    返回 {spanId: [child_spanId, ...]}
    """
    span_ids = {s.get('spanId', '') for s in spans}
    children = defaultdict(list)
    roots = []

    for s in spans:
        sid = s.get('spanId', '')
        # 找父：去掉最后一段
        parts = sid.rsplit('-', 1)
        if len(parts) == 2 and parts[0] in span_ids:
            children[parts[0]].append(sid)
        else:
            roots.append(sid)

    return roots, dict(children)


def _print_tree(span_map: dict, children: dict, sid: str,
                indent: int = 0, span_filter: str = None,
                slow_only: bool = False):
    """递归打印树形调用链"""
    s = span_map.get(sid)
    if not s:
        return

    dur    = _span_dur(s)
    name   = s.get('spanName', '')
    status = s.get('status', 'UNKNOWN')
    infra  = s.get('infraName', '')
    sip    = s.get('serverEndpoint', {}).get('ip', '')
    sstart = s.get('serverStart', '') or s.get('clientStart', '')
    anns   = _get_annotations(s)

    is_slow = dur >= SLOW_THRESHOLD
    is_err  = status not in ('SUCCESS', 'OK', '')

    # 过滤：--span 子树模式
    if span_filter and not sid.startswith(span_filter):
        # 仍递归子节点（子树可能在过滤前缀内）
        for child_sid in sorted(children.get(sid, [])):
            _print_tree(span_map, children, child_sid, indent,
                        span_filter=span_filter, slow_only=slow_only)
        return

    if slow_only and not is_slow and not is_err:
        # 但子节点可能有慢/错，仍递归
        for child_sid in sorted(children.get(sid, [])):
            _print_tree(span_map, children, child_sid, indent,
                        span_filter=span_filter, slow_only=slow_only)
        return

    prefix = "  " * indent
    connector = "└─ " if indent > 0 else ""

    # 状态标记
    flag = "🔴" if is_err else ("🟡" if is_slow else "🟢")

    dur_str = f"{dur}ms" if dur else "?"
    print(f"{prefix}{connector}{flag} [{dur_str}] {name}")
    print(f"{prefix}{'   ' if indent > 0 else ''}   spanId={sid}  infra={infra}  server={sip}")
    if sstart:
        print(f"{prefix}{'   ' if indent > 0 else ''}   start={sstart}")

    # 慢 Span 或错误 Span 展示 annotation（下钻线索）
    if is_slow or is_err:
        diag_anns = {k: v for k, v in anns.items() if k in DIAG_KEYS and v}
        if diag_anns:
            print(f"{prefix}{'   ' if indent > 0 else ''}   ── annotations ──")
            for k, v in diag_anns.items():
                v_short = v[:200] + ('...' if len(v) > 200 else '')
                print(f"{prefix}{'   ' if indent > 0 else ''}     {k}: {v_short}")

    # 递归子节点
    for child_sid in sorted(children.get(sid, [])):
        _print_tree(span_map, children, child_sid, indent + 1,
                    span_filter=span_filter, slow_only=slow_only)


# ─────────────────────────────────────────────
# 诊断分析
# ─────────────────────────────────────────────

def _diagnose(spans: list) -> None:
    """
    自动诊断：识别常见瓶颈模式，输出结构化分析 + 建议。

    识别模式：
      - DB 慢查询（infra=mysql/jdbc, 慢 Span 有 db.statement）
      - 缓存穿透/慢读（infra=squirrel/redis/memcache）
      - RPC 超时（infra=mtthrift/pigeon/http, 慢 Span）
      - 重复调用（同一接口高频出现）
      - 错误 Span（status=FAIL/ERROR）
      - 串行慢链路（顺序调用多个慢节点）
    """
    print("\n" + "═" * 60)
    print("🩺 自动诊断分析")
    print("═" * 60)

    issues = []
    slow_spans = [s for s in spans if _span_dur(s) >= SLOW_THRESHOLD]
    err_spans  = [s for s in spans if s.get('status', '') not in ('SUCCESS', 'OK', '')]

    if not slow_spans and not err_spans:
        print("✅ 未发现明显异常（无慢 Span，无错误 Span）")
        return

    # ── 模式 1：DB 慢查询 ──
    db_slow = []
    for s in slow_spans:
        infra = s.get('infraName', '').lower()
        anns  = _get_annotations(s)
        if any(x in infra for x in ('mysql', 'jdbc', 'sql', 'db')):
            db_slow.append((s, anns))
        elif any(k in anns for k in ('db.statement', 'sql', 'SQL')):
            db_slow.append((s, anns))

    if db_slow:
        issues.append('db_slow')
        print("\n🔴 【DB 慢查询】")
        for s, anns in db_slow:
            dur  = _span_dur(s)
            name = s.get('spanName', '')
            sid  = s.get('spanId', '')
            sip  = s.get('serverEndpoint', {}).get('ip', '')
            print(f"  [{dur}ms] {name}  spanId={sid}  server={sip}")
            for k in ('db.statement', 'sql', 'SQL', 'db.system', 'peer.hostname', 'peer.address'):
                if k in anns:
                    v = anns[k][:300] + ('...' if len(anns[k]) > 300 else '')
                    print(f"    {k}: {v}")
        print("\n  💡 建议：")
        stmts = [anns.get('db.statement','') or anns.get('sql','') or anns.get('SQL','')
                 for _,anns in db_slow if anns.get('db.statement') or anns.get('sql')]
        has_in  = any('IN (' in s.upper() or ' IN(' in s.upper() for s in stmts if s)
        has_sel = any('SELECT *' in s.upper() for s in stmts if s)
        if has_in:
            print("    • IN 查询列表可能过长 → 检查传入 ID 数量，考虑分批查询或加索引")
        if has_sel:
            print("    • SELECT * 避免全列扫描 → 改为按需查询字段")
        hosts = list({anns.get('peer.hostname','') for _,anns in db_slow if anns.get('peer.hostname')})
        if hosts:
            print(f"    • 目标主机：{', '.join(hosts)}")
            if any('slave' in h or 'replica' in h for h in hosts):
                print("    • 指向从库 → 检查主从同步延迟、从库负载")
        print("    • 去慢查询日志（SLOW_QUERY_LOG）查执行计划（EXPLAIN）")
        print("    • 检查该 SQL 是否缺少索引")

    # ── 模式 2：缓存慢/穿透 ──
    cache_slow = []
    for s in slow_spans:
        infra = s.get('infraName', '').lower()
        if any(x in infra for x in ('squirrel', 'redis', 'memcache', 'cache')):
            cache_slow.append(s)

    if cache_slow:
        issues.append('cache_slow')
        print("\n🟡 【缓存慢/穿透】")
        for s in cache_slow:
            dur  = _span_dur(s)
            name = s.get('spanName', '')
            sid  = s.get('spanId', '')
            print(f"  [{dur}ms] {name}  spanId={sid}")
        print("\n  💡 建议：")
        print("    • 检查缓存 Key 是否命中（exists/get 结果）")
        print("    • 若穿透：加布隆过滤器或空值缓存")
        print("    • 若网络慢：检查缓存集群负载、连接池配置")

    # ── 模式 3：RPC 超时 ──
    rpc_slow = []
    for s in slow_spans:
        infra = s.get('infraName', '').lower()
        if any(x in infra for x in ('mtthrift', 'pigeon', 'http', 'octo', 'grpc')):
            rpc_slow.append(s)

    if rpc_slow:
        issues.append('rpc_slow')
        print("\n🟡 【RPC 慢调用】")
        # 按耗时降序，取 Top5
        for s in sorted(rpc_slow, key=lambda x: -_span_dur(x))[:5]:
            dur    = _span_dur(s)
            name   = s.get('spanName', '')
            sid    = s.get('spanId', '')
            caller = s.get('clientEndpoint', {}).get('appKey', '')
            sip    = s.get('serverEndpoint', {}).get('ip', '')
            print(f"  [{dur}ms] {name}  spanId={sid}")
            print(f"    caller={caller}  server={sip}")
        if len(rpc_slow) > 5:
            print(f"  ... 共 {len(rpc_slow)} 个慢 RPC Span")
        print("\n  💡 建议：")
        print("    • 检查被调服务本身的 TP99 / 错误率（用 raptor transaction）")
        print("    • 检查是否存在串行多次调用同一接口（可考虑并发/批量化）")
        print("    • 检查超时配置是否合理（客户端 timeout 过短会提前中断）")

    # ── 模式 4：重复调用 ──
    method_cnt: dict = {}
    for s in spans:
        name = s.get('spanName', '')
        method_cnt[name] = method_cnt.get(name, 0) + 1
    repeat = [(name, cnt) for name, cnt in method_cnt.items() if cnt >= 5]
    if repeat:
        issues.append('repeat')
        print("\n🟡 【高频重复调用】")
        for name, cnt in sorted(repeat, key=lambda x: -x[1])[:5]:
            print(f"  {cnt}x  {name}")
        print("\n  💡 建议：")
        print("    • 考虑批量接口替代循环单次调用（N+1 问题）")
        print("    • 检查业务逻辑是否重复查询相同数据（可加本地缓存）")

    # ── 模式 5：错误 Span ──
    if err_spans:
        issues.append('error')
        print(f"\n🔴 【错误 Span（共 {len(err_spans)} 个）】")
        for s in err_spans[:5]:
            name   = s.get('spanName', '')
            sid    = s.get('spanId', '')
            status = s.get('status', '')
            dur    = _span_dur(s)
            anns   = _get_annotations(s)
            print(f"  [{status}] [{dur}ms] {name}  spanId={sid}")
            for k in ('errorMsg', 'exception', 'error', 'code'):
                if k in anns:
                    print(f"    {k}: {anns[k][:200]}")
        if len(err_spans) > 5:
            print(f"  ... 共 {len(err_spans)} 个")
        print("\n  💡 建议：")
        print("    • 优先排查错误 Span 的 errorMsg/exception 字段")
        print("    • 用 raptor logview 查对应时间窗口的完整堆栈")

    # ── 模式 6：串行慢链路 ──
    # 检测同一父节点下是否存在多个串行慢子节点（时间上不重叠）
    if slow_spans:
        # 统计最慢的 Span 在整条链路中的占比
        total_dur = sum(_span_dur(s) for s in spans)
        top_slow  = sorted(slow_spans, key=lambda x: -_span_dur(x))[:1]
        if top_slow and total_dur > 0:
            top = top_slow[0]
            top_dur = _span_dur(top)
            pct = top_dur * 100 // total_dur
            if pct >= 50:
                print(f"\n📌 【关键瓶颈 Span】")
                print(f"  {top.get('spanName','')} 占总耗时 {pct}%")
                print(f"  spanId={top.get('spanId','')}  duration={top_dur}ms")
                print(f"  → 这是最值得优化的单点，优化它可带来最大收益")

    # ── 总结 ──
    print("\n── 诊断总结 ──")
    if not issues:
        print("  未识别到已知问题模式，建议人工逐层分析调用树（-v 模式）")
    else:
        labels = {
            'db_slow': 'DB 慢查询',
            'cache_slow': '缓存慢/穿透',
            'rpc_slow': 'RPC 慢调用',
            'repeat': '高频重复调用',
            'error': '错误 Span',
        }
        found = [labels[i] for i in issues if i in labels]
        print(f"  发现 {len(found)} 类问题：{' | '.join(found)}")
        print(f"  慢 Span 共 {len(slow_spans)} 个，错误 Span 共 {len(err_spans)} 个")
    print("═" * 60)


# ─────────────────────────────────────────────
# 主输出入口
# ─────────────────────────────────────────────

def _format_trace(traces: list, verbose: bool = False,
                  span_filter: str = None, diagnose: bool = False,
                  slow_only: bool = False) -> None:
    if not traces:
        print("⚠️  未找到匹配的 span（appKey 可能不在此 trace 中）")
        return

    span_map = {s.get('spanId', ''): s for s in traces}
    roots, children = _build_tree(traces)

    slow_count = sum(1 for s in traces if _span_dur(s) >= SLOW_THRESHOLD)
    err_count  = sum(1 for s in traces if s.get('status','') not in ('SUCCESS','OK',''))

    print(f"✅ 共 {len(traces)} 个 span  |  慢 Span（≥{SLOW_THRESHOLD}ms）: {slow_count}  |  错误 Span: {err_count}\n")

    # ── 树形调用链 ──
    if span_filter:
        print(f"── 调用子树（spanId 前缀: {span_filter}）──")
    elif slow_only:
        print(f"── 慢调用树（只展示慢路径）──")
    else:
        print("── 调用链树形结构 ──")
        print("  🟢=正常  🟡=慢(≥500ms)  🔴=错误\n")

    if roots:
        for r in sorted(roots):
            _print_tree(span_map, children, r,
                        span_filter=span_filter, slow_only=slow_only or not verbose)
    else:
        # 找最浅的 span 作为根
        all_sids = sorted(span_map.keys())
        if all_sids:
            _print_tree(span_map, children, all_sids[0],
                        span_filter=span_filter, slow_only=slow_only or not verbose)

    # ── verbose：完整 span 详情 ──
    if verbose and not span_filter:
        print("\n── 完整 Span 列表 ──")
        for s in traces:
            name   = s.get('spanName', '')
            dur    = _span_dur(s)
            status = s.get('status', '')
            sstart = s.get('serverStart','') or s.get('clientStart','')
            caller = s.get('clientEndpoint',{}).get('appKey','')
            sip    = s.get('serverEndpoint',{}).get('ip','')
            sid    = s.get('spanId','')
            infra  = s.get('infraName','')
            anns   = _get_annotations(s)
            print(f"\n  [{status}] {sid}  {name}  [{dur}ms]")
            print(f"    caller={caller}  server={sip}  infra={infra}")
            if sstart:
                print(f"    start={sstart}")
            if anns:
                for k, v in anns.items():
                    print(f"    {k}: {v[:200]}")

    # ── 诊断分析 ──
    if diagnose:
        _diagnose(traces)


# ─────────────────────────────────────────────
# Command 类
# ─────────────────────────────────────────────

class TraceCommand(Command):
    name = "trace"
    help_text = "通过 traceId 查询调用链（树形展示 + 自动诊断）"

    def run(self, args):
        if not getattr(args, 'json', False):
            print(f"🔍 查询 trace: {args.trace_id}")
            if args.appkey:
                print(f"   过滤 appKey: {args.appkey}（精准模式）")
            else:
                print(f"   全量模式（无 appKey 过滤，数据量可能较大）")
            if args.span:
                print(f"   子树下钻: spanId 前缀 = {args.span}")
            print(f"   请稍候（约 15~20 秒）...\n")

        if args.appkey:
            traces = _call_mcp_trace(args.trace_id, args.appkey, timeout=args.timeout)
        else:
            traces = _call_mcp_trace_all(args.trace_id, timeout=args.timeout)

        if getattr(args, 'json', False):
            import json as _json
            print(_json.dumps(traces, indent=2, ensure_ascii=False))
        elif getattr(args, 'flame', False):
            _print_flame(traces, span_filter=args.span)
        else:
            _format_trace(
                traces,
                verbose=args.verbose,
                span_filter=args.span,
                diagnose=args.diagnose,
                slow_only=not args.verbose,
            )

    @staticmethod
    def add_parser(subparsers):
        import argparse
        p = subparsers.add_parser(
            "trace",
            help="通过 traceId 查询调用链（树形展示 + 自动诊断）",
            description="""
通过 traceId 查询调用链，以树形结构展示调用层级。

两种模式：
  1. 精准查询（-a 指定 appKey）：只看该 appKey 的 span，数据精准
  2. 全量查询（不传 -a）：查看完整链路所有 span，数据量大

默认只显示慢 Span（≥500ms）的路径，用 -v 显示完整树。
--span 指定 spanId 前缀可下钻查看子树。
--diagnose 自动识别 DB慢查询、RPC超时、缓存穿透、重复调用等问题并给出建议。

示例:
  raptor trace --id <traceId>                            → 全量查询所有 span
  raptor trace --id <traceId> -a com.sankuai.xxx         → 按 appKey 过滤
  raptor trace --id xxx -a order-service --diagnose
  raptor trace --id xxx -a order-service --span 0-22 -v
  raptor trace --id xxx -v
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        p.add_argument("--id", dest="trace_id", required=True,
                       help="TraceId（必填）")
        p.add_argument("-a", "--appkey", required=False, default=None,
                       help="过滤指定 appKey 的 span（不传则全量查询所有 span）")
        p.add_argument("-v", "--verbose", action="store_true",
                       help="显示完整调用树（含所有 span 详情）")
        p.add_argument("--span", default=None, metavar="SPAN_ID",
                       help="只显示指定 spanId 前缀的子树（下钻分析）")
        p.add_argument("--diagnose", "-d", action="store_true",
                       help="自动诊断：识别 DB慢查询/RPC超时/缓存穿透/重复调用等问题")
        p.add_argument("--timeout", type=int, default=30,
                       help="超时秒数（默认 30）")
        p.add_argument("--flame", "-f", action="store_true",
                       help="ASCII 甘特图（时间轴火焰图）")
        p.add_argument("--json", action="store_true",
                       help="输出原始 JSON（traces 数组）")
        return p


# ─────────────────────────────────────────────
# ASCII 甘特图（火焰图）
# ─────────────────────────────────────────────

def _print_flame(spans: list, width: int = 80, span_filter: str = None) -> None:
    """
    ASCII 甘特图：横轴=时间，纵轴=span（按开始时间排序）
    每个 span 用 ██ 块展示时间区间，标注耗时和接口名
    """
    if not spans:
        print("⚠️  无 span 数据")
        return

    # 过滤子树
    if span_filter:
        spans = [s for s in spans if s.get('spanId','').startswith(span_filter)]
        if not spans:
            print(f"⚠️  spanId 前缀 {span_filter} 下无 span")
            return

    # 提取时间戳（ms）
    def get_start_ms(s):
        v = s.get('serverStart') or s.get('clientStart') or ''
        try:
            # "2026-03-19 16:00:00.021" → ms
            from datetime import datetime
            if '.' in str(v):
                dt_str, ms_str = str(v).rsplit('.', 1)
                dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                return int(dt.timestamp() * 1000) + int(ms_str[:3].ljust(3, '0'))
            elif v:
                dt = datetime.strptime(str(v)[:19], '%Y-%m-%d %H:%M:%S')
                return int(dt.timestamp() * 1000)
        except Exception:
            pass
        return None

    def get_dur(s):
        try:
            return int(s.get('serverDuration') or s.get('clientDuration') or 0)
        except (ValueError, TypeError):
            return 0

    # 过滤掉无法解析时间的 span
    valid = []
    for s in spans:
        st = get_start_ms(s)
        if st is not None:
            valid.append((st, get_dur(s), s))

    if not valid:
        print("⚠️  无法解析 span 时间戳，无法绘制甘特图")
        return

    valid.sort(key=lambda x: x[0])

    t_min = valid[0][0]
    t_max = max(st + dur for st, dur, _ in valid)
    total_ms = max(t_max - t_min, 1)

    # 图宽（留出左侧标签区）
    label_w = 38   # 左侧接口名宽度
    bar_w   = width - label_w - 10  # 时间轴宽度

    # 时间轴刻度
    scale_ms_per_char = total_ms / bar_w

    def ms_to_pos(ms):
        return int((ms - t_min) / scale_ms_per_char)

    def dur_to_len(dur):
        return max(1, int(dur / scale_ms_per_char))

    # 色块字符
    BLOCK_SLOW  = '▓'   # 慢（≥500ms）
    BLOCK_ERR   = '░'   # 错误
    BLOCK_OK    = '█'   # 正常

    # 打印时间轴
    print(f"\n{'─' * (label_w + bar_w + 10)}")
    print(f"{'ASCII 甘特图（时间轴）':^{label_w + bar_w + 10}}")
    print(f"{'─' * (label_w + bar_w + 10)}")

    # 刻度行
    scale_line = ' ' * label_w + '|'
    marks = [0, 25, 50, 75, 100]
    tick_line = ' ' * label_w + '0ms'
    for pct in [25, 50, 75, 100]:
        ms_val = int(t_min + total_ms * pct / 100) - t_min
        label = f"{ms_val}ms" if ms_val < 1000 else f"{ms_val/1000:.1f}s"
        pos = int(bar_w * pct / 100)
        tick_line = tick_line.ljust(label_w + pos) + label

    print(tick_line[:label_w + bar_w + 10])

    # 时间轴线
    axis = ' ' * label_w
    for i in range(bar_w):
        pct = i * 100 // bar_w
        if pct in (0, 25, 50, 75, 100):
            axis += '┼'
        else:
            axis += '─'
    print(axis)

    # 每个 span 一行
    SLOW_THRESHOLD_LOCAL = 500
    for st, dur, s in valid:
        name   = s.get('spanName', '')
        sid    = s.get('spanId', '')
        status = s.get('status', '')
        is_slow = dur >= SLOW_THRESHOLD_LOCAL
        is_err  = status not in ('SUCCESS', 'OK', '')

        char = BLOCK_ERR if is_err else (BLOCK_SLOW if is_slow else BLOCK_OK)
        flag = '🔴' if is_err else ('🟡' if is_slow else '🟢')

        pos = ms_to_pos(st)
        bar_len = dur_to_len(dur)

        # 标签（截断到 label_w-2）
        short_name = name
        # 只取接口最后一段（类.方法 → 方法）
        if '.' in name:
            parts = name.split('.')
            short_name = f"{parts[-2]}.{parts[-1]}" if len(parts) >= 2 else parts[-1]
        label = f"{flag} {short_name}"
        if len(label) > label_w - 2:
            label = label[:label_w - 5] + '...'
        label = label.ljust(label_w)

        # bar
        bar = ' ' * pos + char * bar_len
        dur_tag = f" {dur}ms" if dur < 1000 else f" {dur/1000:.2f}s"

        print(f"{label}|{bar}{dur_tag}")

    # 图例
    print(f"\n  图例：{BLOCK_OK}=正常  {BLOCK_SLOW}=慢(≥500ms)  {BLOCK_ERR}=错误")
    print(f"  时间范围：0 ~ {total_ms}ms  |  总 span 数：{len(valid)}")
    if total_ms > 0:
        dominant = max(valid, key=lambda x: x[1])
        print(f"  最慢 Span：{dominant[2].get('spanName','')} [{dominant[1]}ms]  spanId={dominant[2].get('spanId','')}")
    print(f"{'─' * (label_w + bar_w + 10)}")
