#!/usr/bin/env python3
"""
运维操作 - 近线价缓存同步 / 查询（hotel-goodsquery 近线价）

本脚本封装用户提供的近线价相关后门接口。2026-11-02 实测并对照本地
hotel-goodsquery master：goodsprice/sync、syncGoodsPriceByGoodsIds、poiSimplePrice、
multiPoiSimplePrice 操作的是价格预测缓存；到手价均值近线价另有
 goodsSimplePrice/sync、multiPoiSimplePriceV2，不能将两套缓存混为一谈。

接口形态：RD 自测 HTTP 后门，挂在 hotel-goodsquery 服务实例的 IP:port 上，
不走域名网关、不接 SSO 鉴权，curl 直连即可。唯一需要鉴权的环节是查节点 IP
时调用 OCTO serverNodes 接口需要 MOA 换票。

五种接口形态（均为 GET，同步操作会写缓存）：
  1. 门店同步：/cache/goodsprice/sync/{poiId}
  2. 单门店查询：/cache/poiSimplePrice/{poiId}/{checkIn}/{checkOut}
  3. 商品同步：/cache/syncGoodsPriceByGoodsIds/sync/{goodsId}/{dateString}
  4. 商品同步（指定起日，暂不可用）：上述路径追加 /{startDate}
     2026-11-02 测试主干返回404，按用户要求禁用。--start-date 在查 IP 和
     HTTP 调用前被拦截（含 --dry-run）；研发确认上线并实测回读通过后再开放。
  5. 单门店连住查询：/cache/multiPoiSimplePrice/{poiId}/{startDay}/{endDay}
     multi 指多晚/连住，不是多门店；服务端只接受单个 POI。
     日期均为 yyyyMMdd，dateString 为逗号分隔的变更日期集合，实际同步窗口
     由服务端及 Lion 控制；返回 SUCCESS 不代表缓存一定更新，必须回读验证。

使用方式：
  # 同步近线价缓存（触发写入）
  python3 factory/ops/nearline-price-cache.py sync --poi-id 1090239403220093

  # 泳道场景：严格匹配泳道节点，找不到时报错，不回退主干
  python3 factory/ops/nearline-price-cache.py sync --poi-id 1090239403220093 \
      --swimlane feifang-sphua-liantiao

  # 查询近线价缓存（验证写入是否成功 / 平均值是否正确）
  python3 factory/ops/nearline-price-cache.py query --poi-id 1090239403220093 \
      --check-in 20261020 --check-out 20261021

  # 已知节点 IP 时跳过 OCTO 查询直连
  python3 factory/ops/nearline-price-cache.py sync --poi-id 1090239403220093 \
      --node-ip 10.60.1.23

  # 商品同步；--start-date 暂不可用，传入即报错，不得绕过禁用
  python3 factory/ops/nearline-price-cache.py sync-goods --goods-id 600008267820 \
      --dates 20261102,20261103,20261104

  # 单门店连住查询；--poi-ids 为兼容旧 CLI 名称，实际仅允许一个 ID
  python3 factory/ops/nearline-price-cache.py query-multi \
      --poi-ids 1090269458208127 \
      --start-day 20261102 --end-day 20261105

  # 仅预览 URL，不换票、不查节点、不调用业务接口；未传 IP 时显示占位符
  python3 factory/ops/nearline-price-cache.py sync --poi-id 1090239403220093 --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime

# hotel-goodsquery 被测服务 appkey（OCTO serverNodes 查询用）
DEFAULT_APPKEY = "com.sankuai.hotelcrs.goodsquery"
# 近线价后门接口所在端口（HTTP 服务端口，非 Thrift 端口）
DEFAULT_PORT = 8080
# OCTO 测试环境 serverNodes 查询地址
OCTO_NODES_URL = (
    "https://octo.mws-test.sankuai.com/api/octo/v2/thriftcheck/serverNodes"
    "?appkey={appkey}&env=test&cell=&swimlane=&grouptags="
)
# MOA 换票 audience（OCTO 平台）
MOA_AUDIENCE = "60921859"


def _err(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)


def _curl(url: str, headers: dict | None = None, timeout_s: int = 15) -> str:
    """curl GET 直连，返回响应文本。"""
    cmd = ["curl", "--silent", "--show-error", "--fail", "--max-time", str(timeout_s), url]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    # 不打印鉴权请求头，避免 OCTO 查询票据泄漏到日志。
    print(f"    $ curl GET {url}", file=sys.stderr)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 5)
    if r.returncode != 0:
        raise RuntimeError(f"curl 执行失败：{(r.stderr or '').strip()[:300]}")
    return (r.stdout or "").strip()


def _moa_token() -> str:
    """MOA 免浏览器换票（查 OCTO 节点 IP 需要）。"""
    cmd = ["npx", "--yes", "mtsso-moa-local-exchange", "--audience", MOA_AUDIENCE]
    print(f"    $ {' '.join(cmd)}", file=sys.stderr)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(
            "MOA 换票失败：请确认官方 SSO 的 Agent 凭据及 MOA 登录态已就绪；"
            "也可先用 mtdev octo nodes 查询测试节点后显式传 --node-ip。详情："
            f"{(r.stderr or r.stdout or '').strip()[:300]}"
        )
    try:
        return json.loads(r.stdout)["access_token"]
    except (json.JSONDecodeError, KeyError):
        raise RuntimeError(f"MOA 换票返回解析失败：{(r.stdout or '').strip()[:300]}")


def _find_nodes(obj, out: list) -> None:
    """递归搜索 JSON 中包含 ip 字段的节点条目（兼容 serverNodes 返回结构变化）。"""
    if isinstance(obj, dict):
        if "ip" in obj:
            out.append(obj)
        for v in obj.values():
            _find_nodes(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _find_nodes(item, out)


def _node_swimlane(node: dict) -> str:
    for key in ("swimlane", "lane", "swimlaneName", "group"):
        v = node.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def resolve_node_ip(appkey: str, swimlane: str = "") -> str:
    """查 OCTO 测试环境节点：指定泳道严格匹配，否则只选无泳道节点。"""
    token = _moa_token()
    url = OCTO_NODES_URL.format(appkey=appkey)
    raw = _curl(url, headers={"Cookie": f"yun_portal_ssoid={token}"})
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"OCTO serverNodes 返回非 JSON：{raw[:300]}")

    nodes: list = []
    _find_nodes(payload, nodes)
    if not nodes:
        raise RuntimeError(f"OCTO serverNodes 未返回任何节点（appkey={appkey}）：{raw[:300]}")

    if swimlane:
        for n in nodes:
            if _node_swimlane(n) == swimlane and n.get("ip"):
                print(f"  命中泳道节点：{n['ip']}（swimlane={swimlane}）", file=sys.stderr)
                return str(n["ip"])
        raise RuntimeError(
            f"未找到泳道 {swimlane} 的节点（appkey={appkey}），禁止回退主干；"
            "请检查泳道部署或用 --node-ip 指定已确认的节点 IP"
        )

    for n in nodes:
        if n.get("ip") and not _node_swimlane(n):
            return str(n["ip"])
    raise RuntimeError(
        f"未找到主干节点（appkey={appkey}）；请用 --swimlane 或 --node-ip 指定目标节点"
    )


def _positive_id(value: str) -> int:
    if not re.fullmatch(r"[0-9]+", value) or int(value) <= 0:
        raise argparse.ArgumentTypeError(f"ID 必须是正整数，当前值：{value}")
    return int(value)


def _date(value: str) -> str:
    try:
        if not re.fullmatch(r"[0-9]{8}", value):
            raise ValueError
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"日期必须是有效的 yyyyMMdd，当前值：{value}")
    return value


def _dates(value: str) -> str:
    """保留日期列表的顺序及重复项，不猜测服务端日期范围语义。"""
    return ",".join(_date(item.strip()) for item in value.split(","))


def _poi_ids(value: str) -> str:
    return ",".join(str(_positive_id(item.strip())) for item in value.split(","))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="近线价缓存同步 / 查询（hotel-goodsquery 后门接口，IP 直连）"
    )
    sub = parser.add_subparsers(dest="action", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--appkey", default=DEFAULT_APPKEY,
                        help=f"OCTO 查询用 appkey（默认 {DEFAULT_APPKEY}）")
    common.add_argument("--swimlane", default="", help="泳道名（严格匹配，找不到则报错）")
    common.add_argument("--node-ip", default="",
                        help="已知节点 IP（传了跳过 MOA 换票 + OCTO 查询）")
    common.add_argument("--port", default=DEFAULT_PORT, type=int,
                        help=f"后门接口端口（默认 {DEFAULT_PORT}）")
    common.add_argument("--dry-run", action="store_true",
                        help="仅预览 URL，不换票、不查节点、不调用接口")

    p_sync = sub.add_parser("sync", parents=[common],
                            help="门店维度同步近线价缓存（触发写入）")
    p_sync.add_argument("--poi-id", required=True, type=_positive_id, help="门店 ID")

    p_query = sub.add_parser("query", parents=[common],
                             help="查询单门店近线价缓存（验证写入/平均值）")
    p_query.add_argument("--poi-id", required=True, type=_positive_id, help="门店 ID")
    p_query.add_argument("--check-in", required=True, type=_date, help="入住日期 yyyyMMdd")
    p_query.add_argument("--check-out", required=True, type=_date, help="离店日期 yyyyMMdd")

    p_goods = sub.add_parser("sync-goods", parents=[common],
                             help="商品变更日期同步（实际窗口由服务端/Lion 控制，写缓存）")
    p_goods.add_argument("--goods-id", required=True, type=_positive_id,
                         help="单个商品 ID（暂不开放批量商品）")
    p_goods.add_argument("--dates", required=True, type=_dates,
                         help="dateString：逗号分隔的 yyyyMMdd 变更日期集合，原序透传")
    p_goods.add_argument("--start-date", type=_date,
                         help="暂不可用：指定起日同步已禁用，待研发上线并验证后开放")

    p_multi = sub.add_parser("query-multi", parents=[common],
                             help="单门店连住/多晚价格预测查询（非多门店）")
    p_multi.add_argument("--poi-ids", required=True, nargs="+", type=_poi_ids,
                         help="单个门店 ID（保留旧参数名，禁止多个 POI）")
    p_multi.add_argument("--start-day", required=True, type=_date, help="开始日期 yyyyMMdd")
    p_multi.add_argument("--end-day", required=True, type=_date, help="结束日期 yyyyMMdd")

    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port 必须在 1～65535 范围内")

    if args.action == "query":
        if args.check_in >= args.check_out:
            parser.error("--check-out 必须晚于 --check-in")
        path = f"/cache/poiSimplePrice/{args.poi_id}/{args.check_in}/{args.check_out}"
        action_desc = "查询近线价缓存"
        target_desc = f"poiId={args.poi_id}"
    elif args.action == "query-multi":
        if args.start_day > args.end_day:
            parser.error("--end-day 不能早于 --start-day")
        poi_ids = ",".join(args.poi_ids)
        if "," in poi_ids:
            parser.error("multiPoiSimplePrice 仅支持单个 POI；multi 指连住/多晚，不是多门店")
        path = f"/cache/multiPoiSimplePrice/{poi_ids}/{args.start_day}/{args.end_day}"
        action_desc = "单门店连住价格预测查询"
        target_desc = f"poiIds={poi_ids}"
    elif args.action == "sync-goods":
        if args.start_date is not None:
            parser.error(
                "--start-date 暂不可用：指定起日商品同步接口尚未确认上线，已禁用；"
                "待研发确认目标环境已上线并实测回读通过后再开放。"
                "禁止直接调用后门绕过，或删除起日参数静默切换为其他同步形态。"
            )
        path = f"/cache/syncGoodsPriceByGoodsIds/sync/{args.goods_id}/{args.dates}"
        action_desc = "商品维度同步近线价缓存（触发写入）"
        target_desc = f"goodsId={args.goods_id}"
    else:
        path = f"/cache/goodsprice/sync/{args.poi_id}"
        action_desc = "同步近线价缓存（触发写入）"
        target_desc = f"poiId={args.poi_id}"

    print(f"=== {action_desc}（hotel-goodsquery 近线价）===")
    print(f"  目标     : {target_desc}")
    if args.action == "query":
        print(f"  checkIn  : {args.check_in}")
        print(f"  checkOut : {args.check_out}")
    elif args.action == "query-multi":
        print(f"  startDay : {args.start_day}")
        print(f"  endDay   : {args.end_day}")
    elif args.action == "sync-goods":
        print(f"  dates    : {args.dates}")
        print("  startDate: 不传，实际窗口由服务端/Lion 控制")
    if args.swimlane:
        print(f"  swimlane : {args.swimlane}")
    if args.node_ip and args.swimlane:
        print("  提示：--node-ip 优先使用，不查询或校验该 IP 所属泳道", file=sys.stderr)

    try:
        if args.dry_run:
            node_ip = args.node_ip or "{节点IP}"
        else:
            node_ip = args.node_ip or resolve_node_ip(args.appkey, args.swimlane)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        _err(str(exc))
        sys.exit(1)

    url = f"http://{node_ip}:{args.port}{path}"
    print(f"  节点     : {node_ip}:{args.port}")
    print(f"  URL      : GET {url}")

    if args.dry_run:
        print("\n[dry-run] 不实际调用")
        return

    try:
        raw = _curl(url)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        _err(str(exc))
        sys.exit(1)

    print("\n响应原文：")
    try:
        print(json.dumps(json.loads(raw), ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        print(raw)

    print(f"\n{action_desc} HTTP 调用完成（{target_desc}），业务结果请以响应及回读为准")
    if args.action in ("sync", "sync-goods"):
        print("  提示：同步属于写缓存操作，勿因超时直接重试；请用 query / query-multi 回读验证")


if __name__ == "__main__":
    main()

