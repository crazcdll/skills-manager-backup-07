#!/usr/bin/env python3
"""
商品构造 - 创建套餐（直调研发接口 MeResourceFacade#submitSpu）

服务：com.sankuai.hotel.biz.platform
接口：MeResourceFacade#submitSpu
协议：Thrift RPC 直调（同步，直接返回 spuId）

====================================================================
【前置说明】

  全日房产品（goodsId）请先通过 W1 流程（factory/fullday/create-fullday.py）创建，
  再将 goodsId、goodsName、realRoomName 传入本脚本。

  非房由本脚本自动新建，无需手动操作。

  submitSpu 接口默认审核通过并发布上线，无需额外审核步骤。
  创建成功后自动调用 querySpuListPage 验证 B 端数据生效。

====================================================================
【执行流程】

  Step 1: 自动新建非房（MeResourceFacade#submitXgoods）→ 同步返回 xGoodsId
  Step 2: submitSpu（MeResourceFacade#submitSpu）→ 同步返回 spuId
  Step 3: 查询验证（MeResourceFacade#querySpuListPage）
          → auditStatus=4 且 status=1 → B 端数据生效 ✅

====================================================================
【使用示例】

  # 基础用法（先走 W1 拿到 goodsId）
  python3 factory/package/create-package.py \\
    --partner-id 4569870 --poi-id 1090269468142396 \\
    --goods-id 600003843247 \\
    --goods-name "标准大床房-不含早-入住当天18:00前免费取消" \\
    --real-room-name "标准大床房"

  # 境外套餐
  python3 factory/package/create-package.py \\
    --partner-id 4569870 --poi-id 1090269468142396 \\
    --goods-id 600003843247 \\
    --goods-name "标准大床房-不含早" \\
    --real-room-name "标准大床房" --overseas

  # 指定泳道
  python3 factory/package/create-package.py \\
    --partner-id 4569870 --poi-id 1090269468142396 \\
    --goods-id 600003843247 \\
    --goods-name "标准大床房-不含早" \\
    --real-room-name "标准大床房" --swimlane feature-xxx

  # 仅打印参数不执行
  python3 factory/package/create-package.py \\
    --partner-id 4569870 --poi-id 1090269468142396 \\
    --goods-id 600003843247 \\
    --goods-name "标准大床房-不含早" \\
    --real-room-name "标准大床房" --dry-run

  # 直连模式：先通过 zl-hotel-testdata skill 创建直连产品拿到 goodsId，再传入
  python3 factory/package/create-package.py \\
    --partner-id 4569870 --poi-id 1090269468142396 \\
    --goods-source direct-land \\
    --goods-id <直连产品goodsId> \\
    --goods-name "<直连产品名称>" \\
    --real-room-name "<真实房型名称>"

  # 查看字段说明
  python3 factory/package/create-package.py --show-schema
"""

import argparse
import importlib.util as ilu
import json
import sys
import os
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)

from scripts.utils import get_operator  # noqa

# ── 接口常量 ────────────────────────────────────────────────────────────────
APPKEY  = "com.sankuai.hotel.biz.platform"
SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"

# ── MTA 查询链接 ────────────────────────────────────────────────────────────
MTA_SPU_LINK      = "https://mta.hotel.test.sankuai.com/v2/index.html#/spu-manage/spu"
MTA_NON_ROOM_LINK = "https://mta.hotel.test.sankuai.com/v2/index.html#/non-room/list"

# ── goodsSource 枚举 ────────────────────────────────────────────────────────
# 1=预付自建（默认，走 W1 全日房）
# 2=直连落地（境外=手工直连）
# 3=直连不落地
GOODS_SOURCE_MAP = {
    "1": 1, "prepaid": 1,
    "2": 2, "direct-land": 2,
    "3": 3, "direct-noland": 3,
}


# ════════════════════════════════════════════════════════════════════════════
# 接口加载工具
# ════════════════════════════════════════════════════════════════════════════

def _load_module(name: str, path: str):
    """通用动态 importlib 加载器（处理目录名含连字符的模块）。"""
    spec = ilu.spec_from_file_location(name, path)
    mod  = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_non_room_interface():
    return _load_module(
        "nonroom_interface",
        os.path.join(ROOT, "interface/non-room/interface.py"),
    )


def _load_submit_spu_interface():
    return _load_module(
        "submit_spu_interface",
        os.path.join(ROOT, "interface/package/submit_spu_interface.py"),
    )


def _load_fullday_interface():
    return _load_module(
        "fullday_interface",
        os.path.join(ROOT, "interface/fullday/interface.py"),
    )


# ════════════════════════════════════════════════════════════════════════════
# 步骤函数
# ════════════════════════════════════════════════════════════════════════════

def _step0_query_goods_info(
    partner_id: str,
    poi_id: str,
    goods_id: int,
    swimlane: str,
) -> dict:
    """
    Step 0（直连模式）：用 goodsId 调 queryGoodsInfo 查询商品详情，
    自动获取 goodsName 和 sourceRoomCode（作为 realRoomName 传入 submitSpu）。

    sourceRoomCode 从 preGoodsId 中解析：
      格式 ZL-{partnerId}-{poiId}-{ratePlanCode}-{sourceRoomCode}
      或   ZD-{partnerId}-{poiId}-{ratePlanCode}-{sourceRoomCode}

    返回：{"goodsName": str, "realRoomName": str}
    """
    print("\n" + "─" * 60)
    print("  Step 0: 查询直连产品详情（MeGoodsFacade#queryGoodsInfo）")
    print(f"  goodsId={goods_id}")
    print("─" * 60)

    iface = _load_fullday_interface()
    resp = iface.query_goods_info(
        partner_id=partner_id,
        poi_id=poi_id,
        goods_ids=[goods_id],
        swimlane=swimlane,
    )

    data_list = resp.get("data")
    if not data_list or not isinstance(data_list, list):
        raise RuntimeError(f"queryGoodsInfo 未返回商品详情: {resp}")

    item = data_list[0]
    base_info = item.get("goodsBaseInfo") or {}
    goods_name = base_info.get("goodsName") or ""
    pre_goods_id = base_info.get("preGoodsId") or ""

    if not goods_name:
        raise RuntimeError(f"queryGoodsInfo 返回中未找到 goodsName: {resp}")

    # 从 preGoodsId 解析 sourceRoomCode（最后一段）
    # 格式: ZL-4549536-1090256583195470-aceUY-VuvFv
    parts = pre_goods_id.split("-")
    if len(parts) >= 5:
        real_room_name = parts[-1]
    else:
        raise RuntimeError(
            f"无法从 preGoodsId='{pre_goods_id}' 解析 sourceRoomCode，"
            f"请通过 --real-room-name 手动传入 sourceRoomCode"
        )

    print(f"  ✅ 查询成功")
    print(f"     goodsName   = {goods_name}")
    print(f"     preGoodsId  = {pre_goods_id}")
    print(f"     sourceRoomCode(→realRoomName) = {real_room_name}")
    return {"goodsName": goods_name, "realRoomName": real_room_name}


def _step1_create_non_room(
    partner_id: str,
    poi_id: str,
    xgoods_name: str,
    swimlane: str,
    dry_run: bool,
) -> dict:
    """
    Step 1：创建非房（MeResourceFacade#submitXgoods）。

    返回：{"xGoodsId": int, "name": str}
    """
    print("\n" + "─" * 60)
    print("  Step 1: 创建非房（MeResourceFacade#submitXgoods）")
    print("─" * 60)

    iface = _load_non_room_interface()
    resp  = iface.call(
        partner_id=partner_id,
        poi_id=poi_id,
        product_name=xgoods_name,
        xgoods_type="catering",
        swimlane=swimlane,
        dry_run=dry_run,
    )

    if dry_run:
        print("  [dry-run] 非房创建跳过，使用虚拟 xGoodsId=0")
        return {"xGoodsId": 0, "name": xgoods_name}

    xgoods_id = (
        resp.get("xGoodsId")
        or resp.get("xgoodsId")
        or resp.get("id")
        or resp.get("data")
    )
    if not xgoods_id:
        print(f"  [WARN] 非房创建完成，但 xGoodsId 未在响应中找到。原始返回：{resp}")
        raise RuntimeError("非房创建失败：xGoodsId 未返回")

    print(f"  ✅ 非房创建成功  xGoodsId={xgoods_id}  名称={xgoods_name}")
    print(f"  MTA 查询: {MTA_NON_ROOM_LINK}?partnerId={partner_id}")
    return {"xGoodsId": int(xgoods_id), "name": xgoods_name}


def _step2_submit_spu(
    partner_id: str,
    poi_id: str,
    xgoods_id: int,
    xgoods_name: str,
    goods_id: int,
    goods_name: str,
    real_room_name: str,
    check_days: int,
    goods_source: int,
    swimlane: str,
    dry_run: bool,
    title: str = "",
) -> dict:
    """
    Step 2：调用 submitSpu 创建套餐（同步直调 RPC）。
    接口默认审核通过并发布上线，无需额外审核步骤。

    返回：{"spuId": int}（或 dry_run 时返回 {"spuId": 0}）
    """
    print("\n" + "─" * 60)
    print("  Step 2: 创建套餐（MeResourceFacade#submitSpu）")
    print("─" * 60)
    print(f"  partnerId     : {partner_id}")
    print(f"  poiId         : {poi_id}")
    print(f"  title         : {title or '(空字符串)'}")
    print(f"  xGoodsId      : {xgoods_id}  ({xgoods_name})")
    print(f"  goodsId       : {goods_id}  ({goods_name})")
    print(f"  realRoomName  : {real_room_name}")
    print(f"  goodsSource   : {goods_source}  ({'预付自建' if goods_source == 1 else '直连落地' if goods_source == 2 else '直连不落地'})")
    print(f"  入住晚数       : {check_days}")

    if dry_run:
        print("  [dry-run] submitSpu 跳过，使用虚拟 spuId=0")
        return {"spuId": 0}

    iface = _load_submit_spu_interface()
    resp  = iface.call(
        partner_id=partner_id,
        poi_id=poi_id,
        title=title,
        xgoods_id=xgoods_id,
        xgoods_name=xgoods_name,
        goods_id=goods_id,
        goods_name=goods_name,
        real_room_name=real_room_name,
        check_days=check_days,
        goods_source=goods_source,
        swimlane=swimlane,
        dry_run=False,
    )

    # data 字段可能是 {"spuId": 123, ...} dict，也可能直接是数字
    data_field = resp.get("data")
    if isinstance(data_field, dict):
        spu_id = data_field.get("spuId") or data_field.get("id")
    else:
        spu_id = resp.get("spuId") or resp.get("id") or data_field

    if not spu_id:
        print(f"  [WARN] submitSpu 完成，但 spuId 未在响应中找到。原始返回：{resp}")
        raise RuntimeError("套餐创建失败：spuId 未返回")

    print(f"  ✅ 套餐创建成功  spuId={spu_id}")
    return {"spuId": int(spu_id)}


def _step3_verify_spu(
    partner_id: str,
    poi_id: str,
    spu_id: int,
    swimlane: str,
    max_retries: int = 6,
    interval_sec: int = 3,
) -> bool:
    """
    Step 3：调用 querySpuListPage 验证套餐 B 端数据生效。

    判断条件：
      - data.list[0].spuBaseModel.status == 1   （已上线）
      - data.list[0].spuAuditModel.auditStatus == 4  （审核通过）

    最多轮询 max_retries 次（默认 6 次，每次间隔 3 秒，总计约 18 秒）。
    返回：True=验证通过，False=超时未通过
    """
    print("\n" + "─" * 60)
    print("  Step 3: 查询验证（MeResourceFacade#querySpuListPage）")
    print(f"  验证条件：spuBaseModel.status=1 且 spuAuditModel.auditStatus=4")
    print("─" * 60)

    from scripts.runner import invoke, InvokeError  # noqa

    query_params = {
        "poiId":         str(poi_id),
        "partnerId":     int(partner_id),
        "spuType":       0,
        "pageNum":       1,
        "pageSize":      10,
        "spuId":         int(spu_id),
        "spuSecondType": None,
        "onLineStatus":  None,
        "goodsId":       None,
        "xgoodsId":      None,
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = invoke(
                appkey=APPKEY,
                service=SERVICE,
                method="querySpuListPage",
                params=query_params,
                swimlane=swimlane,
                timeout_ms=10000,
                raise_on_biz_error=False,
                progress_hint=f"查询套餐状态（第 {attempt}/{max_retries} 次）spuId={spu_id}...",
            )

            # 提取 list[0]
            data  = resp.get("data") or {}
            items = data.get("list") or []
            if not items:
                print(f"  ⏳ 暂未查到数据，{interval_sec}s 后重试...")
                time.sleep(interval_sec)
                continue

            spu_item      = items[0]
            base_model    = spu_item.get("spuBaseModel") or {}
            audit_model   = spu_item.get("spuAuditModel") or {}
            status        = base_model.get("status")
            audit_status  = audit_model.get("auditStatus")

            print(f"  查询结果：spuBaseModel.status={status}  spuAuditModel.auditStatus={audit_status}")

            if status == 1 and audit_status == 4:
                print("  ✅ 验证通过：套餐 B 端数据已生效（status=1 上线，auditStatus=4 审核通过）")
                return True
            else:
                # 给出明确的未达标原因
                reasons = []
                if status != 1:
                    status_desc = {0: "待上线", 1: "已上线", 2: "已下线"}.get(status, f"未知({status})")
                    reasons.append(f"status={status}（{status_desc}，期望 1=已上线）")
                if audit_status != 4:
                    audit_desc = {1: "待审核", 2: "审核中", 3: "审核驳回", 4: "审核通过"}.get(audit_status, f"未知({audit_status})")
                    reasons.append(f"auditStatus={audit_status}（{audit_desc}，期望 4=审核通过）")
                print(f"  ⏳ 条件未满足：{' | '.join(reasons)}，{interval_sec}s 后重试...")
                time.sleep(interval_sec)

        except Exception as e:
            print(f"  ⚠️  查询异常（第{attempt}次）: {e}，{interval_sec}s 后重试...")
            time.sleep(interval_sec)

    print(f"  ❌ 验证超时（已等待约 {max_retries * interval_sec}s），套餐状态未达预期")
    print(f"  💡 可手动在 MTA 查看：{MTA_SPU_LINK}?spuId={spu_id}")
    return False


# ════════════════════════════════════════════════════════════════════════════
# --show-schema
# ════════════════════════════════════════════════════════════════════════════

def _show_schema():
    print("""=== 套餐创建（create-package）参数说明 ===

接口：MeResourceFacade#submitSpu（同步直调，直接返回 spuId）
接口默认审核通过并发布上线，创建后自动轮询 querySpuListPage 验证 B 端生效。

【前置说明】
  预付模式（goods-source=1）：
    全日房产品（goodsId）请先通过 W1（factory/fullday/create-fullday.py）创建，
    再将 goodsId、goodsName、realRoomName 传入本脚本。
  直连模式（goods-source=2/3）：
    先通过 zl-hotel-testdata skill 创建直连产品，拿到 goodsId 后传入本脚本。
    --goods-name / --real-room-name 可省略，脚本自动调 queryGoodsInfo 从 preGoodsId 解析 sourceRoomCode 补全。
  非房由本脚本自动新建，无需手动操作。

【必填参数】
  --partner-id     STR    供应商ID（partnerId）
  --poi-id         STR    门店ID（poiId）
  --goods-id       INT    全日房/直连产品ID（goodsId）
  --goods-name     STR    产品名称（预付模式必填；直连模式可省略，自动查询补全）
  --real-room-name STR    关联的真实房型名称（预付模式必填；直连模式可省略，自动从 preGoodsId 解析 sourceRoomCode）

【可选参数】
  --goods-source   STR    商品来源：1/prepaid=预付自建（默认），2/direct-land=直连落地，3/direct-noland=直连不落地
  --xgoods-id      INT    非房ID（xGoodsId）。传入时跳过 Step 1 直接复用已审核通过的非房
  --xgoods-name    STR    非房名称（仅在 --xgoods-id 指定时使用）
  --poi-name       STR    门店名称。仅用于拼接套餐展示名称 title："<门店名><间夜数>晚+<非房名>"
                          （接口不支持自定义任意 title，也不会自动拼接兜底；不传则 title 为空字符串）
  --check-days     INT    入住晚数（spuCheckDays，默认 2）
  --overseas             境外套餐（flag）
  --swimlane       STR    泳道名称（默认主干）
  --dry-run              仅打印参数，不执行

【执行链路】
  Step 0: 直连模式查询商品详情（仅 --goods-name/--real-room-name 缺失时执行）→ goodsName + sourceRoomCode(→realRoomName)
  Step 1: 自动新建非房 → 同步返回 xGoodsId（传入 --xgoods-id 时跳过此步）
  Step 2: submitSpu   → 同步返回 spuId（接口默认审核通过并上线）
  Step 3: querySpuListPage 轮询验证
          → spuBaseModel.status=1（已上线）
          → spuAuditModel.auditStatus=4（审核通过）
          → B 端数据生效 ✅

【使用示例】
  # 预付模式
  python3 factory/package/create-package.py \\
    --partner-id 4569870 --poi-id 1090269468142396 \\
    --goods-id 600003843247 \\
    --goods-name "标准大床房-不含早-入住当天18:00前免费取消" \\
    --real-room-name "标准大床房"

  # 直连模式（只需 goodsId，名称自动查询）
  python3 factory/package/create-package.py \\
    --partner-id 4569870 --poi-id 1090269468142396 \\
    --goods-source direct-land \\
    --goods-id <直连产品goodsId>
""")


# ════════════════════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════════════════════

def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        _show_schema()
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="创建套餐（MeResourceFacade#submitSpu 同步直调，直接返回 spuId）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    g_req = parser.add_argument_group("必填参数")
    g_req.add_argument("--partner-id",     required=True,
                       help="供应商ID（partnerId）")
    g_req.add_argument("--poi-id",         required=True,
                       help="门店ID（poiId）")
    g_req.add_argument("--goods-id",       required=True, type=int,
                       help="全日房/直连产品ID（goodsId）。预付模式先走 W1 创建；直连模式由 zl-hotel-testdata skill 创建后传入")
    g_req.add_argument("--goods-name",     required=False, default=None,
                       help="产品名称。预付模式必填；直连模式可省略，自动调 queryGoodsInfo 查询补全")
    g_req.add_argument("--real-room-name", required=False, default=None,
                       help="关联的真实房型名称。预付模式必填；直连模式可省略，自动从 preGoodsId 解析 sourceRoomCode")

    g_opt = parser.add_argument_group("可选参数")
    g_opt.add_argument("--goods-source", default="1",
                       choices=list(GOODS_SOURCE_MAP.keys()),
                       help="商品来源：1/prepaid=预付自建（默认，走W1全日房），2/direct-land=直连落地，3/direct-noland=直连不落地")
    g_opt.add_argument("--xgoods-id",   type=int, default=None,
                       help="非房 ID（xGoodsId）。传入时跳过 Step 1 直接复用已审核通过的非房；不传时自动新建")
    g_opt.add_argument("--xgoods-name", default=None,
                       help="非房名称（仅在 --xgoods-id 指定时使用，需与已审核非房名称一致）")
    g_opt.add_argument("--poi-name",   default=None,
                       help="门店名称（仅用于拼接套餐展示名称 title：<门店名><间夜数>晚+<非房名>）。"
                            "不传则 title 为空字符串（后端不会报错但也不会自动拼接）")
    g_opt.add_argument("--check-days", type=int, default=2,
                       help="套餐入住晚数（spuCheckDays，默认 2）")
    g_opt.add_argument("--overseas",   action="store_true", help="境外套餐")
    g_opt.add_argument("--swimlane",   default="", help="泳道名称（默认主干）")
    g_opt.add_argument("--dry-run",    action="store_true", help="仅打印参数，不执行")

    args = parser.parse_args()

    # ── 解析 goodsSource ─────────────────────────────────────────────────────
    goods_source = GOODS_SOURCE_MAP[args.goods_source]
    is_direct_mode = goods_source in (2, 3)

    # ── 参数校验：预付模式必须传 goods-name 和 real-room-name ──────────────────
    if not is_direct_mode:
        if not args.goods_name or not args.real_room_name:
            parser.error("预付模式（goods-source=1）必须传 --goods-name 和 --real-room-name")

    # ── 生成默认名称 ──────────────────────────────────────────────────────────
    operator    = get_operator()
    ts          = str(int(time.time()))[-5:]
    xgoods_name = f"{operator}非房_{ts}"  # 非房每次自动新建，名称自动生成

    # 套餐展示名称（giftsName/title）：接口不支持用户自定义任意值，也不会自动拼接兜底，
    # 不传则落库为空字符串。若传入 --poi-name，则按约定格式自动拼接："<门店名><间夜数>晚+<非房名>"
    # 该 title 值会在 Step 1 拿到非房名称后才能最终确定，此处先生成预览文案用于打印
    spu_title_preview = f"{args.poi_name}{args.check_days}晚+<非房名>" if args.poi_name else "(未传 --poi-name，title 将为空字符串)"

    # ── 打印执行计划 ──────────────────────────────────────────────────────────
    source_desc = '预付自建' if goods_source == 1 else '直连落地' if goods_source == 2 else '直连不落地'
    print("═" * 60)
    print("  套餐创建（MeResourceFacade#submitSpu）")
    print("═" * 60)
    print(f"  partnerId  : {args.partner_id}")
    print(f"  poiId      : {args.poi_id}")
    print(f"  套餐展示名称(title) : {spu_title_preview}")
    print(f"  goodsId    : {args.goods_id}")
    if is_direct_mode and (not args.goods_name or not args.real_room_name):
        print(f"  goodsName  : (未传，自动查询 queryGoodsInfo 补全)")
        print(f"  realRoom   : (未传，自动从 preGoodsId 解析 sourceRoomCode)")
    else:
        print(f"  goodsName  : {args.goods_name}")
        print(f"  realRoom   : {args.real_room_name}")
    print(f"  goodsSource: {goods_source}  ({source_desc})")
    print(f"  入住晚数   : {args.check_days}")
    print(f"  境外标志   : {'是' if args.overseas else '否'}")
    print(f"  泳道       : {args.swimlane or '主干'}")
    if args.xgoods_id:
        print(f"  xGoodsId   : {args.xgoods_id}  (复用已有非房，跳过 Step 1)")
    print("═" * 60)

    # ════════════════════════════════════════════════════════════════════════
    # Step 0：直连模式查询商品详情（--goods-name/--real-room-name 缺失时执行）
    #         从 queryGoodsInfo 的 preGoodsId 中解析 sourceRoomCode 作为 realRoomName
    # ════════════════════════════════════════════════════════════════════════
    goods_name = args.goods_name
    real_room_name = args.real_room_name
    if is_direct_mode and (not goods_name or not real_room_name):
        q_result = _step0_query_goods_info(
            partner_id=args.partner_id,
            poi_id=args.poi_id,
            goods_id=args.goods_id,
            swimlane=args.swimlane,
        )
        if not goods_name:
            goods_name = q_result["goodsName"]
        if not real_room_name:
            real_room_name = q_result["realRoomName"]

    # ════════════════════════════════════════════════════════════════════════
    # Step 1：创建非房（若传入 --xgoods-id 则跳过，直接复用已审核通过的非房）
    # ════════════════════════════════════════════════════════════════════════
    if args.xgoods_id:
        xgoods_id   = args.xgoods_id
        xgoods_name = args.xgoods_name or xgoods_name
        print(f"\n  ⏭️  跳过 Step 1，复用已有非房  xGoodsId={xgoods_id}  ({xgoods_name})")
        print(f"  MTA 查询: {MTA_NON_ROOM_LINK}?partnerId={args.partner_id}")
    else:
        non_room_result = _step1_create_non_room(
            partner_id=args.partner_id,
            poi_id=args.poi_id,
            xgoods_name=xgoods_name,
            swimlane=args.swimlane,
            dry_run=args.dry_run,
        )
        xgoods_id   = non_room_result["xGoodsId"]
        xgoods_name = non_room_result["name"]

    # 套餐展示名称（title/giftsName）最终拼接：需等 xgoods_name 确定后才能拼完整
    # 格式：<门店名><间夜数>晚+<非房名>（仅在传入 --poi-name 时拼接，否则保持空字符串）
    spu_title = f"{args.poi_name}{args.check_days}晚+{xgoods_name}" if args.poi_name else ""

    # ════════════════════════════════════════════════════════════════════════
    # Step 2：调用 submitSpu 创建套餐
    # ════════════════════════════════════════════════════════════════════════
    spu_result = _step2_submit_spu(
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        title=spu_title,
        xgoods_id=xgoods_id,
        xgoods_name=xgoods_name,
        goods_id=args.goods_id,
        goods_name=goods_name,
        real_room_name=real_room_name,
        check_days=args.check_days,
        goods_source=goods_source,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
    )
    spu_id = spu_result["spuId"]

    # ════════════════════════════════════════════════════════════════════════
    # Step 3：查询验证 B 端数据生效（仅非 dry-run 时执行）
    # ════════════════════════════════════════════════════════════════════════
    verified = False
    if not args.dry_run:
        verified = _step3_verify_spu(
            partner_id=args.partner_id,
            poi_id=args.poi_id,
            spu_id=spu_id,
            swimlane=args.swimlane,
        )

    # ════════════════════════════════════════════════════════════════════════
    # 汇总输出
    # ════════════════════════════════════════════════════════════════════════
    print(f"\n{'═' * 60}")
    print(f"  📋 构造结果汇总（套餐）")
    print(f"{'═' * 60}")
    print(f"  partnerId  : {args.partner_id}")
    print(f"  poiId      : {args.poi_id}")
    print(f"  xGoodsId   : {xgoods_id}  ({xgoods_name})")
    print(f"  goodsId    : {args.goods_id}  ({goods_name})")
    print(f"  goodsSource: {goods_source}  ({source_desc})")
    print(f"  realRoom   : {real_room_name}")
    print(f"  spuId      : {spu_id}")
    print(f"  套餐展示名称(title) : {spu_title or '(空字符串，未传 --poi-name)'}")
    print(f"  泳道       : {args.swimlane or '主干'}")
    if not args.dry_run:
        status_tag = "✅ B 端数据已生效" if verified else "⚠️  验证超时，请手动确认"
        print(f"  验证状态   : {status_tag}")
    print(f"{'═' * 60}")
    print(f"  MTA 查询套餐：{MTA_SPU_LINK}?partnerId={args.partner_id}&poiId={args.poi_id}")
    print(f"{'═' * 60}\n")


if __name__ == "__main__":
    main()