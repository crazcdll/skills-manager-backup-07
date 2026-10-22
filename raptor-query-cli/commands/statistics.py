"""
离线统计命令 (offline-stat)
"""
import json
import sys
import math
import argparse
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from client import RaptorClient

from commands.base import Command
from commands.utils import _parse_abs

# 离线统计专用 base（内网直连，无需 token/SSO）
STAT_BASE = "http://cat.service.sankuai.com"  # internal: .sankuai.com intranet, HTTP allowed

# 内部分页参数
_PAGE_SIZE = 50


def _align_start_ts(category: str) -> int:
    """根据 category 计算取整后的起始时间戳（毫秒）"""
    now = datetime.now()
    if category == "month":
        aligned = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif category == "week":
        # 本周一 00:00
        aligned = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif category == "day":
        aligned = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif category == "hour":
        aligned = now.replace(minute=0, second=0, microsecond=0)
    else:
        aligned = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return int(aligned.timestamp() * 1000)


def _time_label(start_ts: int, category: str) -> str:
    """根据时间戳和 category 生成可读标签"""
    dt = datetime.fromtimestamp(start_ts / 1000)
    if category == "month":
        return dt.strftime("%Y-%m")
    elif category == "week":
        end = dt + timedelta(days=6)
        return f"{dt.strftime('%m-%d')}~{end.strftime('%m-%d')}"
    elif category == "day":
        return dt.strftime("%Y-%m-%d")
    elif category == "hour":
        return dt.strftime("%Y-%m-%d %H:00")
    return str(dt)


def _fmt_num(n) -> str:
    """数字千分位格式化"""
    if isinstance(n, float):
        return f"{n:,.1f}"
    return f"{int(n):,}"


def _fmt_rate(rate) -> str:
    """成功率格式化"""
    pct = rate * 100
    if pct >= 99.99:
        return f"{pct:.4f}%"
    elif pct >= 99.9:
        return f"{pct:.3f}%"
    else:
        return f"{pct:.2f}%"


class OfflineStatCommand(Command):
    """离线统计命令"""
    name = "offline-stat"
    help_text = "查询离线统计（Event/Transaction/Problem 的 Appkey 请求统计）"

    def run(self, args):
        if args.list_mode:
            self._run_list(args)
        else:
            self._run_query(args)

    def _run_list(self, args):
        """列出所有离线统计指标（type × name）"""
        mode = args.mode
        url = f"{STAT_BASE}/cat/r/statistics/category"
        try:
            resp = self.client.session.get(url, params={"type": mode}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"❌ 获取指标列表失败: {e}", file=sys.stderr)
            sys.exit(1)

        items = data.get("data", [])

        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return

        # 按 type 分组
        grouped: Dict[str, List[str]] = {}
        for item in items:
            t = item.get("type", "")
            n = item.get("name", "")
            grouped.setdefault(t, []).append(n)

        total_types = len(grouped)
        total_items = len(items)
        mode_label = mode.capitalize()
        print(f"\n📊 {mode_label} 离线统计指标 - {total_types} 个 type，共 {total_items} 条")
        for t, names in sorted(grouped.items()):
            print(f"\n  ▸ {t}")
            for n in names:
                print(f"    - {n}")

    def _run_query(self, args):
        """查询离线统计结果"""
        if not args.type:
            print("❌ 查统计模式必须指定 --type（通过 --list 查看可选值）", file=sys.stderr)
            sys.exit(1)
        if not args.name:
            print("❌ 查统计模式必须指定 --name（通过 --list 查看可选值）", file=sys.stderr)
            sys.exit(1)

        mode = args.mode
        category = args.category
        # -s 支持可读格式（2026-04-20 / 20260420 等），内部转毫秒
        start_ts = self._resolve_start(args.start, category)
        sort_field = args.sort
        appkey_filter = args.appkey or []

        # 拉全量数据（内部翻页）
        all_items, total, raw_pages = self._fetch_all(
            mode=mode,
            type_name=args.type,
            name=args.name,
            start=start_ts,
            category=category,
            sort=sort_field,
            as_json=args.json,
        )

        if args.json:
            # --json 模式：输出合并后的原始数据
            merged = {
                "query": {
                    "type": args.type,
                    "name": args.name,
                    "category": category,
                    "start": start_ts,
                    "sort": sort_field,
                },
                "total": total,
                "statistic": all_items,
            }
            print(json.dumps(merged, indent=2, ensure_ascii=False))
            return

        # 过滤 appkey
        if appkey_filter:
            filter_set = set(appkey_filter)
            matched = [s for s in all_items if s.get("domain") in filter_set]
            matched_domains = {s.get("domain") for s in matched}
            unmatched = [a for a in appkey_filter if a not in matched_domains]
            display_items = matched
            filter_label = f"筛选 {len(appkey_filter)} 个 appkey"
            truncated = False
        else:
            # 分离 All 汇总行和其余行
            all_row = [s for s in all_items if s.get("domain") == "All"]
            rest = [s for s in all_items if s.get("domain") != "All"]
            top_n = args.top
            if top_n > 0 and len(rest) > top_n:
                display_items = all_row + rest[:top_n]
                truncated = True
                filter_label = f"共 {total} 个 appkey，展示 Top {top_n}"
            else:
                display_items = all_row + rest
                truncated = False
                filter_label = f"共 {total} 个 appkey"

        time_label = _time_label(start_ts, category)
        mode_label = mode.capitalize()
        print(f"\n📊 {mode_label} 离线统计 | {args.type} / {args.name} | {time_label} ({category}) | {filter_label}")

        if not display_items:
            print("\n  (无数据)")
            if appkey_filter:
                print(f"\n  未匹配: {', '.join(appkey_filter)}")
            return

        # 按 mode 渲染不同列
        self._render_table(display_items, mode)

        if appkey_filter and unmatched:
            print(f"\n  ⚠️ 未匹配: {', '.join(unmatched)}（不在统计结果中）")

        if truncated:
            print(f"\n  💡 已展示前 {args.top} 条（共 {total} 个 appkey），用 --top N 调整，--top 0 输出全量")

    @staticmethod
    def _render_table(items: list, mode: str):
        """按 mode 渲染不同列的表格"""
        idx = 0

        if mode == "transaction":
            # Transaction: 含耗时指标
            print(f"\n  {'#':<5} {'Appkey':<40} {'请求总量':>14} {'失败数':>10} {'成功率':>12} {'Avg(ms)':>10} {'TP90':>8} {'TP99':>8} {'QPS':>10}")
            print(f"  {'─'*5} {'─'*40} {'─'*14} {'─'*10} {'─'*12} {'─'*10} {'─'*8} {'─'*8} {'─'*10}")
            for item in items:
                domain = item.get("domain", "")
                if domain == "All":
                    rank = "ALL"
                else:
                    idx += 1
                    rank = str(idx)
                print(
                    f"  {rank:<5} {domain:<40} {_fmt_num(item.get('total', 0)):>14} "
                    f"{_fmt_num(item.get('failure', 0)):>10} {_fmt_rate(item.get('successRate', 0)):>12} "
                    f"{_fmt_num(item.get('avg', 0)):>10} {_fmt_num(item.get('tp90', 0)):>8} "
                    f"{_fmt_num(item.get('tp99', 0)):>8} {_fmt_num(item.get('qps', 0)):>10}"
                )

        elif mode == "problem":
            # Problem: 只有 domain + total
            print(f"\n  {'#':<5} {'Appkey':<50} {'总量':>14}")
            print(f"  {'─'*5} {'─'*50} {'─'*14}")
            for item in items:
                domain = item.get("domain", "")
                if domain == "All":
                    rank = "ALL"
                else:
                    idx += 1
                    rank = str(idx)
                print(f"  {rank:<5} {domain:<50} {_fmt_num(item.get('total', 0)):>14}")

        else:
            # Event（默认）
            print(f"\n  {'#':<5} {'Appkey':<45} {'请求总量':>14} {'失败数':>10} {'成功率':>12} {'QPS':>10}")
            print(f"  {'─'*5} {'─'*45} {'─'*14} {'─'*10} {'─'*12} {'─'*10}")
            for item in items:
                domain = item.get("domain", "")
                if domain == "All":
                    rank = "ALL"
                else:
                    idx += 1
                    rank = str(idx)
                print(
                    f"  {rank:<5} {domain:<45} {_fmt_num(item.get('total', 0)):>14} "
                    f"{_fmt_num(item.get('failure', 0)):>10} {_fmt_rate(item.get('successRate', 0)):>12} "
                    f"{_fmt_num(item.get('qps', 0)):>10}"
                )

    @staticmethod
    def _resolve_start(raw: str, category: str) -> int:
        """解析 -s 参数：支持可读时间格式或毫秒时间戳，None 则自动取整"""
        if raw is None:
            return _align_start_ts(category)
        # 纯数字且 >= 13 位 → 视为毫秒时间戳
        if raw.isdigit() and len(raw) >= 13:
            return int(raw)
        # 尝试可读时间格式
        dt = _parse_abs(raw)
        if dt is not None:
            return int(dt.timestamp() * 1000)
        # 兜底：可能是短纯数字（如 20260420），_parse_abs 已覆盖
        raise ValueError(
            f"无效时间格式: {raw}，支持 2026-04-20 / 20260420 / 毫秒时间戳"
        )

    def _fetch_all(
        self,
        mode: str,
        type_name: str,
        name: str,
        start: int,
        category: str,
        sort: str,
        as_json: bool = False,
    ) -> tuple:
        """内部翻页拉取全量数据，返回 (all_items, total, raw_pages)"""
        url = f"{STAT_BASE}/cat/r/statistics/{mode}"
        all_items = []
        raw_pages = []
        total = 0
        page = 0

        while True:
            params = {
                "start": start,
                "category": category,
                "sort": sort,
                "page": page,
                "count": _PAGE_SIZE,
                "order": 1,
                "type": type_name,
                "name": name,
            }
            try:
                resp = self.client.session.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                if page == 0:
                    print(f"❌ 查询失败: {e}", file=sys.stderr)
                    sys.exit(1)
                break

            raw_pages.append(data)
            result = data.get("data", {})
            total = result.get("total", total)
            items = result.get("statistic", [])

            if not items:
                break

            all_items.extend(items)

            # 已拉完
            # +1 是因为 API 返回的 total 包含 "All" 汇总行
            if len(all_items) >= total + 1 or len(items) < _PAGE_SIZE:
                break

            page += 1

            # 安全上限，防止无限循环
            if page > 200:
                break

        return all_items, total, raw_pages

    @staticmethod
    def add_parser(subparsers):
        p = subparsers.add_parser(
            "offline-stat",
            help="查询离线统计（Event/Transaction/Problem 的 Appkey 请求统计）",
            aliases=["ofs"],
        )
        # 统计维度
        p.add_argument(
            "-m", "--mode", default="event",
            choices=["event", "transaction", "problem"],
            help="统计维度（默认 event）"
        )
        # 模式
        p.add_argument(
            "--list", dest="list_mode", action="store_true",
            help="列出所有离线统计指标（type × name）"
        )
        # 查统计参数
        p.add_argument(
            "-t", "--type", default=None,
            help="指标类型（如 AccessHttpAuth.Fail.Client），通过 --list 查看"
        )
        p.add_argument(
            "-n", "--name", default=None,
            help="指标名称（如 *），通过 --list 查看"
        )
        p.add_argument(
            "-a", "--appkey", action="append", default=None,
            help="按 appkey 过滤（可多次指定 -a xxx -a yyy）"
        )
        p.add_argument(
            "-c", "--category", default="month",
            choices=["month", "week", "day", "hour"],
            help="时间粒度（默认 month）"
        )
        p.add_argument(
            "-s", "--start", type=str, default=None,
            help="起始时间（2026-04-20 / 20260420 / 毫秒时间戳），不传则自动取整到当前粒度起点"
        )
        p.add_argument(
            "--sort", default="total",
            choices=["total", "failure", "successRate", "qps"],
            help="排序字段（默认 total）"
        )
        p.add_argument(
            "--top", type=int, default=30,
            help="无 -a 过滤时最多展示前 N 条（默认 30，0=全量）"
        )
        p.add_argument("--json", action="store_true", help="输出原始 JSON")
        return p
