#!/usr/bin/env python3
"""
factory/goods-state/goods_price_ops.py
────────────────────────────────────────
价格状态操作模块（Price-level state operations）

负责处理商品价格审核相关状态，包括：
  - merchant-auditing       : 商家改价审核中（已提交改价请求，待 BD 审核，已实测确认）
  - merchant-audit-rejected : 商家改价审核驳回（BD 主动驳回）
  - BD-auditing             : BD 改价审核中（BD 身份改卖价触发审核，默认使用全局固定测试
                              账号 crstest，2026-08-19 已实测确认）
  - BD-audit-rejected       : BD 改价审核驳回（在 BD-auditing 基础上追加 BD 驳回）

实现原理：
  价格审核只能通过"对已上线商品大幅改价"触发，不能在创建时直接设置审核状态。
  因此流程为：
    1. 先走完整正常上线流程（含库存重试、缓存刷新）
    2. 查询商品详情，取 preGoodsId / goodsName（queryGoodsInfo 返回体中存在这些字段）
    3. 调用 PlatformMeGoodsFacade#updatePriceV2 大幅提价（涨到当前售价的 5 倍，
       确保远超约 20% 的审核阈值）。⚠️ 2026-08-19 起改为「tdm-cli 真实登录换票 +
       HTTP 网关直连调用」（不再是 Thrift 直调伪造身份）：商家身份走
       `tdm token blogin` 换 mebsid（已实测验证），BD 身份走 `tdm token sso`
       换 messoid，默认使用全局固定测试账号 crstest（不按 partnerId 绑定权限，
       见 interface/ops/interface.py DEFAULT_BD_SSO_*，2026-08-19 已实测验证）+
       extendParam.priceAuditInfoModels 审核理由。
    4. auditing/BD-auditing：到此为止
       audit-rejected/BD-audit-rejected：额外调用对应审核驳回接口

使用方式（由 create-fullday.py / create-hourly.py 在完成正常上线后调用）：
    from factory.goods_state.goods_price_ops import apply_price_state

    apply_price_state(
        goods_state="merchant-auditing",
        iface=iface,
        params=params,          # 建品时的入参 dict（用于读取创建时的价格）
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        room_id=args.room_id,
        goods_id=goods_id,
        goods_type=1,           # 1=全日房  2=钟点房（影响 updatePriceV2 的 goodsType 字段）
        swimlane=args.swimlane,
        online_fn=_online_with_inventory_retry,  # 上线函数（由调用方传入）
    )

注意事项：
  - queryGoodsInfo（MeGoodsFacade）经实测只返回 goodsBaseInfo/roomInfo/rpInfo/goodsExtModel，
    不含 priceInfo 和价格审核状态字段，因此：
      · 当前售价直接从创建时的 params（Step 1 提交的入参）里读取，不反查
      · preGoodsId 仍需 queryGoodsInfo 查询
      · 不做"轮询确认审核状态"——改价请求提交成功后即视为已完成触发动作
  - 该接口异步处理，商品是否进入「待审核」状态需在 1~3 秒后自行核实

参考依据：
  2026-08-06 真实抓包实测（traceId=6147412944688422972 真实用户操作，
  traceId=8373777253166968808 脚本复现）
"""

import datetime
from typing import Optional, Callable


# ════════════════════════════════════════════════════════════════════════════
# 对外统一入口
# ════════════════════════════════════════════════════════════════════════════

def apply_price_state(
    goods_state: str,
    iface,
    params: dict,
    partner_id: str,
    poi_id: str,
    room_id: int,
    goods_id: str,
    goods_type: int,
    swimlane: str,
    online_fn: Callable,
    bd_sso_user: Optional[str] = None,
    bd_sso_password: Optional[str] = None,
    bd_client_id: Optional[str] = None,
    bd_client_secret: Optional[str] = None,
    audit_reason: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> None:
    """
    价格状态统一入口。

    根据 goods_state 分发到对应的处理函数：
      merchant-auditing        → handle_merchant_audit_state（只触发，不驳回）
      merchant-audit-rejected  → handle_merchant_audit_state（触发后商家驳回）
      BD-auditing               → handle_bd_audit_state（只触发，不驳回）
      BD-audit-rejected         → handle_bd_audit_state（触发后 BD 驳回）

    参数：
        goods_state  - 目标价格状态（见上方枚举）
        iface        - 建品脚本的 iface 对象
        params       - 建品时的完整入参 dict（用于读取创建时的售价）
        partner_id   - 供应商ID（字符串）
        poi_id       - 门店ID（字符串）
        room_id      - 逻辑房型ID（int）
        goods_id     - 目标商品ID（字符串）
        goods_type   - 商品类型：1=全日房  2=钟点房（影响 updatePriceV2 字段）
        swimlane     - 泳道名称
        online_fn    - 完整上线函数（由调用方传入，签名需与 _online_with_inventory_retry 一致）
                       传入 None 则跳过上线步骤（仅在确认商品已上线时使用）
        bd_sso_user      - BD 员工 SSO 账号（mis，仅 BD-auditing / BD-audit-rejected 生效，
                           不传时默认使用全局固定测试账号 "crstest"，已实测，一般无需传）
        bd_sso_password  - BD 员工 SSO 密码（仅 BD-auditing / BD-audit-rejected 生效，
                           不传时默认 "Ceshi123"）
        bd_client_id     - SSO 客户端 ID（可选，不传默认 "hotel_sc"）
        bd_client_secret - SSO 客户端密钥（可选，不传用默认值）
        audit_reason - BD 改价审核理由（仅 BD-auditing / BD-audit-rejected 生效，
                       不传默认"测试数据构造"）
        start_date   - 改价生效开始日期（YYYY-MM-DD），即触发审核对应的价格日期段起点。
                       不传默认today（仅当天）。⚠️ 商家改价审核已实测确认是按此日期段
                       进入审核（非整商品）；BD 改价审核是否整商品进审尚待重新验证
                       （旧方案时期的观察结论，旧方案已证伪，不一定仍成立），日期段字段
                       仍会传给接口。
        end_date     - 改价生效结束日期（YYYY-MM-DD）。不传默认=start_date（不传时即今天）。
    """
    if goods_state in ("merchant-auditing", "merchant-audit-rejected"):
        handle_merchant_audit_state(
            goods_state=goods_state,
            iface=iface,
            params=params,
            partner_id=partner_id,
            poi_id=poi_id,
            room_id=room_id,
            goods_id=goods_id,
            goods_type=goods_type,
            swimlane=swimlane,
            online_fn=online_fn,
            start_date=start_date,
            end_date=end_date,
        )
    elif goods_state in ("BD-auditing", "BD-audit-rejected"):
        handle_bd_audit_state(
            goods_state=goods_state,
            iface=iface,
            params=params,
            partner_id=partner_id,
            poi_id=poi_id,
            room_id=room_id,
            goods_id=goods_id,
            goods_type=goods_type,
            swimlane=swimlane,
            online_fn=online_fn,
            bd_sso_user=bd_sso_user,
            bd_sso_password=bd_sso_password,
            bd_client_id=bd_client_id,
            bd_client_secret=bd_client_secret,
            audit_reason=audit_reason,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        raise ValueError(
            f"goods_price_ops 不支持的 goods_state='{goods_state}'，"
            f"支持值：merchant-auditing / merchant-audit-rejected / "
            f"BD-auditing / BD-audit-rejected"
        )


# ════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════════════════════

def _today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def extract_goods_info_item(query_resp: dict, goods_id: int) -> Optional[dict]:
    """
    从 queryGoodsInfo 响应中提取目标 goodsId 对应的详情条目。

    兼容不同返回结构：
      - data 为 list：直接遍历
      - data 为 dict：取 goodsDetailInfoList / goodsInfoList / list
    查不到精确匹配时降级返回 candidates[0]（兜底）。
    """
    data = query_resp.get("data")
    candidates = []
    if isinstance(data, list):
        candidates = data
    elif isinstance(data, dict):
        candidates = (data.get("goodsDetailInfoList") or data.get("goodsInfoList")
                      or data.get("list") or [])
    for item in candidates:
        base_info = item.get("goodsBaseInfo") or {}
        if int(base_info.get("goodsId", -1)) == int(goods_id):
            return item
    return candidates[0] if candidates else None


def extract_price_fen_from_create_params(params: dict) -> Optional[int]:
    """
    从 Step 1 创建商品的入参 dict 中读取售价（单位：分）。

    路径：goodsDetailList[0].priceInfo.unifiedDatePriceInfos.weekPriceInfos[0].priceInfo.salePrice
    解析不到时返回 None（调用方应使用合理默认值）。
    """
    try:
        sale_price = (params["goodsDetailList"][0]["priceInfo"]["unifiedDatePriceInfos"]
                      ["weekPriceInfos"][0]["priceInfo"]["salePrice"])
        if sale_price:
            return int(sale_price)
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return None


# ════════════════════════════════════════════════════════════════════════════
# merchant-auditing / merchant-audit-rejected：商家改价触发审核
# ════════════════════════════════════════════════════════════════════════════

def handle_merchant_audit_state(
    goods_state: str,
    iface,
    params: dict,
    partner_id: str,
    poi_id: str,
    room_id: int,
    goods_id: str,
    goods_type: int,
    swimlane: str,
    online_fn: Optional[Callable],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> None:
    """
    goods-state=merchant-auditing / merchant-audit-rejected：
    先正常上线，再通过商家身份改价触发涨跌幅审核。

    【方案依据：2026-08-06 真实抓包实测（traceId=6147412944688422972）】
    商家在前端页面对已上线商品执行大幅改价（200元→1000元，涨幅4倍），服务端
    EbPrepayAuditServiceImpl.checkChangePriceRange 判定 needAudit=true，商品进入
    「待审核」状态并给 BD 推送审批消息。据此确认：审核只能通过"对已上线商品改价"
    触发，而不是"创建时设置极高售价再尝试上线"（后者行为未经验证，废弃）。

    ⚠️ 商家改价审核是**按日期段进入审核**（非整商品）：updatePriceV2 的
    calcPriceUnifiedDateModel.dates 字段直接决定了本次改价/审核生效的日期范围，
    因此可通过 start_date/end_date 指定任意日期段（不传则默认仅当天）。

    流程：
      Step A: 正常上线（复用 online_fn，含库存重试兜底）
      Step B: 查询商品详情（queryGoodsInfo），取 preGoodsId
      Step C: 改价触发审核（updatePriceV2，涨到当前售价的 5 倍，仅对 start_date~end_date
              范围内的日期生效）
      Step D（仅 merchant-audit-rejected）: 商家改价审核驳回
                                             （operation_type=3, audit_status=2）

    参数：
        goods_state  - "merchant-auditing" 或 "merchant-audit-rejected"
        online_fn    - 完整上线函数，签名：online_fn(iface, params, partner_id, poi_id,
                                                        room_id, goods_id, swimlane) -> None
                       传 None 则跳过上线步骤（商品已上线时使用）
        goods_type   - 1=全日房（默认售价 200 元）  2=钟点房（默认售价 80 元）
        start_date   - 改价生效开始日期（YYYY-MM-DD），不传默认today
        end_date     - 改价生效结束日期（YYYY-MM-DD），不传默认=start_date
    """
    ops = iface._load_ops_interface()
    label = ("merchant-auditing（商家改价审核中）"
             if goods_state == "merchant-auditing"
             else "merchant-audit-rejected（商家改价审核驳回）")

    print(f"\n── 目标状态: {label} ──────────────────────────────")

    # ── Step A: 正常上线（复用调用方传入的上线函数）─────────────────────────
    if online_fn is not None:
        online_fn(
            iface=iface,
            params=params,
            partner_id=partner_id,
            poi_id=poi_id,
            room_id=room_id,
            goods_id=goods_id,
            swimlane=swimlane,
        )
    else:
        print("  [跳过上线步骤，已假设商品处于上线状态]")

    # 当前售价直接取自创建时的入参（queryGoodsInfo 不返回价格字段，无法反查）
    default_price_yuan = 80.0 if goods_type == 2 else 200.0
    old_price_fen = extract_price_fen_from_create_params(params)
    old_price_yuan = old_price_fen / 100.0 if old_price_fen else default_price_yuan

    try:
        _gt = int(params["goodsDetailList"][0]["goodsBaseInfo"].get("goodsType") or goods_type)
        goods_type = _gt
    except (KeyError, IndexError, TypeError, ValueError):
        pass

    # ── Step B: 查询商品详情，取 preGoodsId / goodsName ─────────────────────
    print("\n── Step B: 查询商品详情（queryGoodsInfo）获取 preGoodsId ──────────")
    try:
        query_resp = iface.query_goods_info(
            partner_id=partner_id,
            poi_id=poi_id,
            goods_ids=[int(goods_id)],
            swimlane=swimlane,
        )
        item = extract_goods_info_item(query_resp, int(goods_id))
        if item is None:
            print(f"  ❌ 未查询到商品详情，无法继续改价触发审核：{query_resp}")
            return
        base_info = item.get("goodsBaseInfo") or {}
        pre_goods_id = base_info.get("preGoodsId") or ""
        goods_name = base_info.get("goodsName") or ""
        goods_status = base_info.get("goodsStatus") or 2
        print(f"  preGoodsId={pre_goods_id!r}  goodsName={goods_name!r}  "
              f"创建时售价={old_price_yuan}元")
    except Exception as e:
        print(f"  ❌ 查询商品详情异常：{e}")
        return

    # ── Step C: 改价触发审核（涨到创建价的 5 倍，远超约 20% 的审核阈值）─────
    new_price_yuan = round(old_price_yuan * 5, 2)
    effective_start = start_date or _today()
    effective_end = end_date or effective_start
    print(f"\n── Step C: 改价触发审核（updatePriceV2，{old_price_yuan}元 → {new_price_yuan}元，"
          f"日期段={effective_start}~{effective_end}）──")
    try:
        update_resp = ops.call_update_price_v2(
            partner_id=int(partner_id),
            poi_id=str(poi_id),
            goods_id=int(goods_id),
            goods_name=goods_name,
            pre_goods_id=pre_goods_id,
            goods_status=int(goods_status),
            goods_type=int(goods_type),
            sale_price_yuan=new_price_yuan,
            start_date=effective_start,
            end_date=effective_end,
            swimlane=swimlane,
        )
        print(f"  ✅ 改价请求已提交（异步）：{update_resp}")
        print("  💡 该接口异步处理，商品是否进入「待审核」状态请在1~3秒后自行核实"
              "（前端页面 / RD 提供的查询工具），本脚本不做轮询确认")
    except Exception as e:
        print(f"  ❌ 改价异常：{e}")
        return

    if goods_state == "merchant-auditing":
        print("\n── 目标已达成：改价请求已提交，商品预期进入「待审核」状态，不做任何审核动作 ──")
        print(f"  如需之后手动通过：python3 factory/ops/cache-refresh-audit.py "
              f"--op 3 --product-id {goods_id} --audit-status 3")
        print(f"  如需之后手动驳回：python3 factory/ops/cache-refresh-audit.py "
              f"--op 3 --product-id {goods_id} --audit-status 2")
        return

    # merchant-audit-rejected：主动调用商家改价审核驳回（operation_type=3, audit_status=2）
    print("\n── Step D: 商家改价审核驳回（operation_type=3，audit_status=2）──────")
    try:
        ops.call(operation_type=3, product_id=int(goods_id), audit_status=2)
        print(f"  ✅ 审核驳回成功  goodsId={goods_id}")
    except Exception as e:
        print(f"  ❌ 审核驳回异常：{e}")
        print(f"  💡 可手动执行：python3 factory/ops/cache-refresh-audit.py "
              f"--op 3 --product-id {goods_id} --audit-status 2")


# ════════════════════════════════════════════════════════════════════════════
# BD-auditing / BD-audit-rejected：BD 身份改价触发审核
# ════════════════════════════════════════════════════════════════════════════

def handle_bd_audit_state(
    goods_state: str,
    iface,
    params: dict,
    partner_id: str,
    poi_id: str,
    room_id: int,
    goods_id: str,
    goods_type: int,
    swimlane: str,
    online_fn: Optional[Callable],
    bd_sso_user: Optional[str] = None,
    bd_sso_password: Optional[str] = None,
    bd_client_id: Optional[str] = None,
    bd_client_secret: Optional[str] = None,
    audit_reason: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> None:
    """
    goods-state=BD-auditing / BD-audit-rejected：
    先正常上线，再通过 BD 身份改价（改卖价）触发审核。

    【方案依据：2026-08-19 修复 + 实测验证。此前曾有一版错误实现——Thrift 直调时
    手工拼一个 PlatformOrigin 冒充 BD 身份，结果编造的 BD 账号不真实，导致请求
    完全不生效（用户实测反馈 BD-auditing 完全没生效）。已改为「tdm-cli 真实 SSO
    登录换 messoid + HTTP 网关直连调用」，默认使用全局固定测试账号 crstest（参考
    hotel-crs 自动化仓库 LoginUtils.getBDHeaderMap()，BD 身份与商家不同，不按
    partnerId 绑定权限，是全局通用测试身份），见 interface/ops/interface.py
    call_update_price_v2() 的 identity="bd" 分支及 DEFAULT_BD_SSO_* 常量，
    2026-08-19 已对 partnerId=4576342 实测验证通过（code=10000）】
    与商家改价（merchant-auditing）共用同一个 updatePriceV2 接口，仅登录身份
    （Cookie）及部分录价方式字段不同：
      - 登录 Cookie: messoid=<BD SSO登录换取的token>，logintype: SSO
        （而非商家的 mebsid + logintype: Epassport）
      - 外层 priceRecordWay=1（BD模式），goodsBaseInfo.priceRecordWayList=[1,2,5,7]
      - ratioConfig.ratioType=1
      - extendParam.priceAuditInfoModels 携带审核理由（reason）

    ⚠️ BD 改价审核是否也像商家改价一样“按日期段进审”，还是旧方案下观察到的
    “整商品进审”，目前尚待用本次修复后的真实 BD 账号重新验证（旧结论基于已证伪
    的 Thrift 伪造身份方案，不一定仍然成立）。start_date/end_date 仍会传给
    updatePriceV2 接口（因为接口本身要求填这两个字段），具体影响范围待确认。

    流程：
      Step A: 正常上线（复用 online_fn，含库存重试兜底）
      Step B: 查询商品详情（queryGoodsInfo），取 preGoodsId
      Step C: 改价触发审核（updatePriceV2，identity="bd"，涨到当前售价的 5 倍）
      Step D（仅 BD-audit-rejected）: BD 改价审核驳回
                                      （operation_type=2, audit_status=2）

    参数：
        goods_state  - "BD-auditing" 或 "BD-audit-rejected"
        online_fn    - 完整上线函数，签名同 handle_merchant_audit_state
                       传 None 则跳过上线步骤（商品已上线时使用）
        goods_type   - 1=全日房（默认售价 200 元）  2=钟点房（默认售价 80 元）
        bd_sso_user      - BD 员工 SSO 账号（mis），不传默认使用全局固定测试账号 "crstest"（已实测）
        bd_sso_password  - BD 员工 SSO 密码，不传默认 "Ceshi123"
        bd_client_id     - SSO 客户端 ID（可选，不传默认 "hotel_sc"）
        bd_client_secret - SSO 客户端密钥（可选，不传用默认值）
        audit_reason - BD 改价审核理由，不传默认"测试数据构造"
        start_date   - 改价生效开始日期（YYYY-MM-DD），不传默认today
                       （BD 审核是否为整商品审核待重新验证，旧结论已不可靠）
        end_date     - 改价生效结束日期（YYYY-MM-DD），不传默认=start_date
    """
    ops = iface._load_ops_interface()
    label = ("BD-auditing（BD改价审核中）"
             if goods_state == "BD-auditing"
             else "BD-audit-rejected（BD改价审核驳回）")

    print(f"\n── 目标状态: {label} ──────────────────────────────")

    # ── Step A: 正常上线（复用调用方传入的上线函数）─────────────────────────
    if online_fn is not None:
        online_fn(
            iface=iface,
            params=params,
            partner_id=partner_id,
            poi_id=poi_id,
            room_id=room_id,
            goods_id=goods_id,
            swimlane=swimlane,
        )
    else:
        print("  [跳过上线步骤，已假设商品处于上线状态]")

    # 当前售价直接取自创建时的入参（queryGoodsInfo 不返回价格字段，无法反查）
    default_price_yuan = 80.0 if goods_type == 2 else 200.0
    old_price_fen = extract_price_fen_from_create_params(params)
    old_price_yuan = old_price_fen / 100.0 if old_price_fen else default_price_yuan

    try:
        _gt = int(params["goodsDetailList"][0]["goodsBaseInfo"].get("goodsType") or goods_type)
        goods_type = _gt
    except (KeyError, IndexError, TypeError, ValueError):
        pass

    # ── Step B: 查询商品详情，取 preGoodsId / goodsName ─────────────────────
    print("\n── Step B: 查询商品详情（queryGoodsInfo）获取 preGoodsId ──────────")
    try:
        query_resp = iface.query_goods_info(
            partner_id=partner_id,
            poi_id=poi_id,
            goods_ids=[int(goods_id)],
            swimlane=swimlane,
        )
        item = extract_goods_info_item(query_resp, int(goods_id))
        if item is None:
            print(f"  ❌ 未查询到商品详情，无法继续改价触发审核：{query_resp}")
            return
        base_info = item.get("goodsBaseInfo") or {}
        pre_goods_id = base_info.get("preGoodsId") or ""
        goods_name = base_info.get("goodsName") or ""
        goods_status = base_info.get("goodsStatus") or 2
        print(f"  preGoodsId={pre_goods_id!r}  goodsName={goods_name!r}  "
              f"创建时售价={old_price_yuan}元")
    except Exception as e:
        print(f"  ❌ 查询商品详情异常：{e}")
        return

    # ── Step C: BD 身份改价触发审核（涨到创建价的 5 倍，远超约 20% 的审核阈值）──
    new_price_yuan = round(old_price_yuan * 5, 2)
    effective_start = start_date or _today()
    effective_end = end_date or effective_start
    reason = audit_reason or "测试数据构造"
    print(f"\n── Step C: BD身份改价触发审核（updatePriceV2，identity=bd，"
          f"{old_price_yuan}元 → {new_price_yuan}元，日期段={effective_start}~{effective_end}，"
          f"reason={reason!r}）──")
    # ⚠️ 只在调用方确实传了值（非 None）时才显式覆盖，否则不传该形参，让
    # call_update_price_v2 使用其内置的 DEFAULT_BD_SSO_*（全局固定测试账号
    # crstest）默认值——若这里显式传 None 会直接覆盖掉那个默认值。
    bd_kwargs = {}
    if bd_sso_user is not None:
        bd_kwargs["bd_sso_user"] = bd_sso_user
    if bd_sso_password is not None:
        bd_kwargs["bd_sso_password"] = bd_sso_password
    if bd_client_id is not None:
        bd_kwargs["bd_client_id"] = bd_client_id
    if bd_client_secret is not None:
        bd_kwargs["bd_client_secret"] = bd_client_secret
    try:
        update_resp = ops.call_update_price_v2(
            partner_id=int(partner_id),
            poi_id=str(poi_id),
            goods_id=int(goods_id),
            goods_name=goods_name,
            pre_goods_id=pre_goods_id,
            goods_status=int(goods_status),
            goods_type=int(goods_type),
            sale_price_yuan=new_price_yuan,
            start_date=effective_start,
            end_date=effective_end,
            identity="bd",
            audit_reason=reason,
            swimlane=swimlane,
            **bd_kwargs,
        )
        print(f"  ✅ 改价请求已提交（异步）：{update_resp}")
        print("  💡 该接口异步处理，商品是否进入「待审核」状态请在1~3秒后自行核实"
              "（前端页面 / RD 提供的查询工具），本脚本不做轮询确认")
    except Exception as e:
        print(f"  ❌ 改价异常：{e}")
        return

    if goods_state == "BD-auditing":
        print("\n── 目标已达成：改价请求已提交，商品预期进入「待审核」状态，不做任何审核动作 ──")
        print(f"  如需之后手动通过：python3 factory/ops/cache-refresh-audit.py "
              f"--op 2 --product-id {goods_id} --audit-status 3")
        print(f"  如需之后手动驳回：python3 factory/ops/cache-refresh-audit.py "
              f"--op 2 --product-id {goods_id} --audit-status 2")
        return

    # BD-audit-rejected：主动调用 BD 改价审核驳回（operation_type=2, audit_status=2）
    print("\n── Step D: BD改价审核驳回（operation_type=2，audit_status=2）──────")
    try:
        ops.call(operation_type=2, product_id=int(goods_id), audit_status=2)
        print(f"  ✅ 审核驳回成功  goodsId={goods_id}")
    except Exception as e:
        print(f"  ❌ 审核驳回异常：{e}")
        print(f"  💡 可手动执行：python3 factory/ops/cache-refresh-audit.py "
              f"--op 2 --product-id {goods_id} --audit-status 2")

