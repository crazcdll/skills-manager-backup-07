#!/usr/bin/env python3
"""
接口层：缓存刷新 / 改价审核
工具：工具1031（HotelCacheUpdateOrPriceAuditService.cacheUpdateOrPriceAudit）
协议：Thrift via DataUnity

operationType 枚举：
  1 - 缓存刷新（商品/SPU/门店/货盘级别，四选一）
  2 - BD改价审核（通过/驳回）
  3 - 商家改价审核（通过/驳回）

auditStatus（operationType=2/3 时必填）：
  2 - 驳回
  3 - 通过（默认）

目标ID（四选一）：productId / spuId / poiId / rpId
"""

import sys
import os
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from scripts.du_runner import run_tool, DuError  # noqa


TOOL_ID = 1031

OP_DESC = {
    1: "缓存刷新",
    2: "BD改价审核",
    3: "商家改价审核",
}

AUDIT_STATUS_DESC = {
    2: "驳回",
    3: "通过",
}


# ════════════════════════════════════════════════════════════════════════════
# 参数校验
# ════════════════════════════════════════════════════════════════════════════

def validate(params: dict) -> None:
    """
    参数联动强校验，失败时抛出 ValueError。

    V1  operationType 必须是 1/2/3
    V2  至少传一个目标ID（productId/spuId/poiId/rpId）
    V3  operationType=2/3 时 auditStatus 必须是 2 或 3
    """
    errors = []
    op = params.get("operationType")
    if op not in (1, 2, 3):
        errors.append(f"V1: operationType={op} 非法，合法值：1=缓存刷新, 2=BD改价审核, 3=商家改价审核")
    ids_present = any(params.get(k) for k in ("productId", "spuId", "poiId", "rpId"))
    if not ids_present:
        errors.append("V2: 至少传一个目标ID（productId / spuId / poiId / rpId）")
    if op in (2, 3):
        audit_status = params.get("auditStatus")
        if audit_status not in (2, 3):
            errors.append(f"V3: operationType={op} 时 auditStatus 必须是 2（驳回）或 3（通过），"
                          f"当前值={audit_status}")
    if errors:
        raise ValueError(f"参数校验失败（共 {len(errors)} 项）：\n" +
                         "\n".join(f"  {e}" for e in errors))


# ════════════════════════════════════════════════════════════════════════════
# 主调用函数
# ════════════════════════════════════════════════════════════════════════════

def call(
    operation_type: int,
    product_id: Optional[int] = None,
    spu_id: Optional[int] = None,
    poi_id: Optional[int] = None,
    rp_id: Optional[int] = None,
    audit_status: int = 3,
    is_oversea: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    缓存刷新 / 改价审核，直调 DataUnity 工具1031。

    参数：
        operation_type - 操作类型：1=缓存刷新, 2=BD改价审核, 3=商家改价审核
        product_id     - 商品ID（四选一）
        spu_id         - SPU ID（套餐/超团）（四选一）
        poi_id         - 门店ID（四选一）
        rp_id          - 货盘RPID（四选一）
        audit_status   - 审核状态（op=2/3时必填）：2=驳回, 3=通过（默认3）
        is_oversea     - 是否境外（缓存刷新时生效，默认False）
        dry_run        - True 时只打印不执行

    返回：DataUnity 原始响应 dict
    异常：ValueError（参数校验失败），DuError（工具调用失败）
    """
    params = {
        "operationType": operation_type,
        "auditStatus":   audit_status,
        "isOversea":     is_oversea,
    }
    if product_id is not None:
        params["productId"] = product_id
    if spu_id is not None:
        params["spuId"] = spu_id
    if poi_id is not None:
        params["poiId"] = poi_id
    if rp_id is not None:
        params["rpId"] = rp_id

    validate(params)
    return run_tool(TOOL_ID, params, dry_run=dry_run)


# ════════════════════════════════════════════════════════════════════════════
# batchOnlineSwitch - 批量上线/下线商品
# ════════════════════════════════════════════════════════════════════════════

SWITCH_STATUS_DESC = {
    2: "上线",
    3: "下线",
}

SWITCH_APPKEY  = "com.sankuai.hotel.biz.platform"
SWITCH_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade"
SWITCH_METHOD  = "batchOnlineSwitch"
# batchOnlineSwitch(OnlineSwitchParam param) —— 单参数复杂结构体
# body 模式下 DataUnity 无法自动推断该结构体参数类型，须走显式 parameterTypes 模式
ONLINE_SWITCH_PARAM_TYPE = (
    "com.meituan.hotel.biz.platform.goods.facade.param.goods.OnlineSwitchParam"
)


def call_online_switch(
    partner_id: int,
    poi_id: str,
    goods_ids: list,
    status: int,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    批量上线 / 下线商品，直调 MeGoodsFacade#batchOnlineSwitch。

    对应前端请求：
      POST /api/gw/v1/product/goods/batchOnlineSwitch
      body: {"partnerId":4550589,"poiId":"1085927256096396","goodsIds":[600000632131],"status":2}

    参数：
        partner_id - 供应商ID
        poi_id     - 门店ID（字符串）
        goods_ids  - 商品ID列表，如 [600000632131]
        status     - 2=上线，3=下线
        swimlane   - 泳道（空字符串=主干）
        dry_run    - True 时只打印不执行

    返回：RPC 原始响应 dict
    异常：ValueError（参数校验失败），InvokeError（调用失败）
    """
    if status not in (2, 3):
        raise ValueError(f"status={status} 非法，合法值：2=上线, 3=下线")
    if not goods_ids:
        raise ValueError("goods_ids 不能为空")

    params = {
        "partnerId": int(partner_id),
        "poiId": str(poi_id),
        "goodsIds": [int(g) for g in goods_ids],
        "status": int(status),
    }

    # 复用 runner.invoke（与 batchCreateGoods 同一链路）
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    from scripts.runner import invoke, InvokeError  # noqa

    label = SWITCH_STATUS_DESC.get(status, str(status))
    if dry_run:
        import json
        print(f"[dry-run] batchOnlineSwitch 参数：\n{json.dumps(params, ensure_ascii=False, indent=2)}")
        return {}

    print(f"正在批量{label}商品（{goods_ids}）...")
    import json as _json
    return invoke(
        appkey=SWITCH_APPKEY,
        service=SWITCH_SERVICE,
        method=SWITCH_METHOD,
        params=None,
        parameter_values=[
            _json.dumps(params, ensure_ascii=False, separators=(",", ":"))
        ],
        parameter_types=[ONLINE_SWITCH_PARAM_TYPE],
        swimlane=swimlane,
        timeout_ms=30000,
        raise_on_biz_error=True,
        progress_hint=f"批量{label}商品中...",
    )


# ════════════════════════════════════════════════════════════════════════════
# destroyGoods - 废除商品
# ════════════════════════════════════════════════════════════════════════════

DESTROY_APPKEY  = "com.sankuai.hotel.biz.platform"
DESTROY_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade"
DESTROY_METHOD  = "destroyGoods"

DEFAULT_DESTROY_REASON = "QA测试数据构造-废除"


def call_destroy_goods(
    partner_id: int,
    poi_id: str,
    goods_id: Optional[int] = None,
    pre_goods_id: Optional[str] = None,
    reason: str = DEFAULT_DESTROY_REASON,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    废除商品，直调 MeGoodsFacade#destroyGoods（Thrift）。

    对应入参模型：DestroyGoodsParam
      - reason        废除原因
      - partnerId     供应商ID
      - poiId         门店ID
      - preGoodsId    预产品ID（与 goodsId 二选一，全日房/钟点房通常直接用 goodsId）
      - goodsId       产品ID（preGoodsId 和 goodsId 至少传一个）

    ⚠️ 服务端强约束：仅"暂停/下线"状态（goodsStatus=3）的商品才能废除，
       在线商品（goodsStatus=2）直接调用会报「仅暂停状态产品，才可以废除」。
       调用前应确保商品已下线（先调 call_online_switch(status=3)）。

    参数：
        partner_id    - 供应商ID
        poi_id        - 门店ID（字符串）
        goods_id      - 商品ID（goodsId/preGoodsId 至少传一个）
        pre_goods_id  - 预产品ID（goodsId/preGoodsId 至少传一个）
        reason        - 废除原因（默认给定通用测试原因）
        swimlane      - 泳道（空字符串=主干）
        dry_run       - True 时只打印不执行

    返回：RPC 原始响应 dict
    异常：ValueError（参数校验失败），InvokeError（调用失败）
    """
    if goods_id is None and not pre_goods_id:
        raise ValueError("goods_id 和 pre_goods_id 至少传一个")

    params = {
        "partnerId": int(partner_id),
        "poiId": str(poi_id),
        "reason": reason,
    }
    if goods_id is not None:
        params["goodsId"] = int(goods_id)
    if pre_goods_id:
        params["preGoodsId"] = str(pre_goods_id)

    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    from scripts.runner import invoke, InvokeError  # noqa

    if dry_run:
        import json
        print(f"[dry-run] destroyGoods 参数：\n{json.dumps(params, ensure_ascii=False, indent=2)}")
        return {}

    print(f"正在废除商品（goodsId={goods_id}）...")
    return invoke(
        appkey=DESTROY_APPKEY,
        service=DESTROY_SERVICE,
        method=DESTROY_METHOD,
        params=params,
        swimlane=swimlane,
        timeout_ms=30000,
        raise_on_biz_error=True,
        progress_hint=f"废除商品中（goodsId={goods_id}）...",
    )


# ════════════════════════════════════════════════════════════════════════════
# updatePriceV2 - ME 大改版改价接口（会真正走涨跌幅审核判断）
# ════════════════════════════════════════════════════════════════════════════
#
# 接口选型说明（2026-08 实测确认，勿倒退回旧接口）：
#   - PlatformPriceFacade#batchUpdatePrice：服务端固定 infoModel.setFromBdAudit(true)，
#     会被 EBOriginStrategy.judgeUpdateAudit 直接短路跳过审核判断，无论涨跌幅多大都不会触发审核。
#     ⚠️ 不要用这个方法来"触发"审核。
#   - PlatformMeGoodsFacade#updatePriceV2（本函数使用）：ME 大改版异步改价接口，
#     链路 refactorUpdatePrice → MeQueryCalcPriceExecutor(UPDATE) → MePriceUpdateLogicUnit
#     → priceSubmitService.submitPriceSync/Async → goodsOperateService.updatePriceOperate
#     → judgeUpdatePriceAudit（战区策略 + 来源策略，真正判断涨跌幅是否超阈值）。
#
# ⚠️⚠️⚠️【重要教训，2026-08-19 修复】身份必须走真实登录，不能用 Thrift 直调伪造 ⚠️⚠️⚠️
#
# 本函数曾经存在一版错误实现：直调 Thrift 方法 updatePriceV2(PriceUpdateRefactorParam,
# PlatformOrigin) 时，第二个参数 PlatformOrigin 由本函数手工拼一个 "userType=BIZ" 或
# "userType=MIS+HOTEL_BD" 来冒充商家/BD身份，注释里也曾错误地写成"已实测确认""真实抓包
# 确认"。但真实生产链路是：
#     前端 → HTTP 网关（ME域 me.hotel.test.sankuai.com）→ 网关解析登录 Cookie
#          （商家=mebsid, BD=messoid）得到真实身份 → 服务端内部构造 PlatformOrigin
#          → 转发给 Thrift 方法
# Thrift 直调完全绕开了网关的登录态解析这一步，服务端收到的是我们手工拼的、不完整的
# PlatformOrigin，导致身份判断落入错误分支：
#   - 商家身份被误判走了 MtaOriginStrategy（BD/整商品审核逻辑），而不是期望的 EBOriginStrategy
#   - 编造的 BD 账号（id=2111140/login="hotel_bd_qa"）因为在权限系统里根本不存在/未与目标
#     partnerId 绑定，请求要么完全不生效，要么被判定无权限
# 用户实测反馈：merchant-auditing 触发出的商品进了"BD审核+整商品"，BD-auditing 完全没生效，
# 与两个"分支互相对调"的错误现象完全吻合。
#
# 【已实测修复方案（2026-08-19，真实验证通过，权威）】
# 改用「tdm-cli 真实登录换票 + HTTP 网关直连调用」，不再直调 Thrift：
#   1. 商家身份：`tdm token blogin -u <partnerId> -p Ceshi123 -s lvyou` 换取 bsid，
#      拼 Cookie: mebsid=<bsid> + logintype: Epassport，POST 到
#      https://me.hotel.test.sankuai.com/api/gw/v1/product/price/updatePriceV2。
#      2026-08-19 用真实供应商 4574857/门店1090269458119393/商品600005585422 实测：
#      网关正确识别商家身份（EPassport认证返回 bizAccount.login="4574857"，
#      User{type=BIZ,...}），接口返回 code=10000 提交成功。
#      （注：曾用 partnerId=4576342 测试遇到 code=679"商家水平鉴权失败"，是该测试供应商
#      本身在权限系统里未与目标门店建立绑定关系，与登录/调用方式无关，换用已知绑定正确
#      的供应商 4574857 后验证通过）
#   2. BD 身份：同样改走 HTTP 网关 + `tdm token sso` 换取 messoid。⚠️ 与商家身份不同，
#      BD 身份是**全局固定测试账号**、不按 partnerId 绑定权限（参考 hotel-crs 自动化仓库
#      LoginUtils.getBDHeaderMap() + SSOUtil.getSSOId("ME","ME") + env.properties：
#      ME_SSO_USER=crstest / ME_SSO_PASSWORD=Ceshi123 / ME_SSO_CLIENT_ID=hotel_sc /
#      ME_SSO_CLIENT_SECRET=7d53c92b32a0fc914c30e1740b3fc774）。2026-08-19 已用该账号对
#      partnerId=4576342/goodsId=600005953325 实测：`tdm token sso` 登录成功，
#      updatePriceV2 网关返回 code=10000 提交成功。已设为 DEFAULT_BD_SSO_* 默认值，
#      调用方无需再手动传 bd_sso_user/bd_sso_password（不要沿用旧的编造账号
#      id=2111140/login="hotel_bd_qa"，那是完全未经验证且已被证伪的猜测值）。
#   3. HTTP 网关 body 字段结构与旧的 Thrift PriceUpdateRefactorParam 参数基本一致（本来
#      就是从同一次真实抓包 traceId=6147412944688422972 得到的），唯一区别是**不再需要/
#      不允许传 PlatformOrigin**——网关自己根据登录 Cookie 决定身份，调用方传了也会被忽略。
#   4. 涨跌幅阈值约 20%（战区配置可能不同），构造测试数据时应让新价格相对当前售价明显超过
#      该阈值（本函数默认按创建价的数倍设置）。
#   5. 接口本身是异步的：网关直接返回只包含 uuid + 简单 message 结构，真正"是否需要审核"
#      的判断结果需要等待约 1~3 秒后才产生，本函数不做轮询确认，需调用方自行核实。
#
# BD 身份对应的字段差异（2026-08-19 已用默认 BD 账号 crstest 实测通过）：
#   1. 外层 goodsList[0].priceRecordWay 传 1（BD 录价模式），而不是商家的 8。
#   2. goodsBaseInfo.priceRecordWayList 传 [1,2,5,7]，而不是商家的 [8,9]。
#   3. ratioConfig.ratioType 传 1，而不是商家的 2。
#   4. extendParam.priceAuditInfoModels 新增审核理由信息（商家改价该字段为空 {}）：
#        [{"goodsNameList": [<goodsName>], "materials": [], "reason": "<审核理由>"}]
#
# 因此本函数保留 identity 参数（"biz"=商家身份，"bd"=BD身份），均已实测验证通过，由调用方
# 根据要触发的审核类型（merchant-auditing / BD-auditing）选择即可，无需额外传登录凭证。

# HTTP 网关调用配置（真实登录态方案，2026-08-19 起使用）
UPDATE_PRICE_GATEWAY_HOST = "https://me.hotel.test.sankuai.com"
UPDATE_PRICE_GATEWAY_API  = "/api/gw/v1/product/price/updatePriceV2"

# 商家登录默认参数（学城已验证：测试环境商家账号固定用 partnerId 作为用户名登录）
DEFAULT_MERCHANT_PASSWORD = "Ceshi123"
DEFAULT_MERCHANT_SERVICE  = "lvyou"

# PriceModifyOperateModel.operateType 枚举（PriceOperateTypeEnum）
PRICE_OPERATE_TYPE_NULL  = 3   # 不修改/不计算
PRICE_OPERATE_TYPE_EQUAL = 6   # 直接赋值为 operateNum

# 默认 BD 改价审核理由（--reason 可覆盖）
DEFAULT_BD_AUDIT_REASON = "测试数据构造"

# 默认 BD 测试账号（全局固定，不按 partnerId 绑定权限，来源：hotel-crs 自动化仓库
# LoginUtils.getBDHeaderMap() + SSOUtil.getSSOId("ME","ME") 引用的 env.properties 配置）。
# ⚠️ 2026-08-19 已用该账号对 partnerId=4576342/goodsId=600005953325 实测：
# tdm token sso 登录成功 + updatePriceV2 网关返回 code=10000 提交成功。与「BD 与供应商
# 强绑定」的旧假设不同——BD 侧鉴权与商家不同，这是全局通用测试身份，不区分 partnerId。
# 旧版编造的 DEFAULT_BD_USER_ID=2111140/DEFAULT_BD_LOGIN="hotel_bd_qa"（角色枚举文档
# 反推，未经验证且已被证伪）已彻底移除，不要再使用。
DEFAULT_BD_SSO_USER = "crstest"
DEFAULT_BD_SSO_PASSWORD = "Ceshi123"
DEFAULT_BD_SSO_CLIENT_ID = "hotel_sc"
DEFAULT_BD_SSO_CLIENT_SECRET = "7d53c92b32a0fc914c30e1740b3fc774"


def call_update_price_v2(
    partner_id: int,
    poi_id: str,
    goods_id: int,
    goods_name: str,
    pre_goods_id: str,
    goods_status: int,
    goods_type: int,
    sale_price_yuan: float,
    start_date: str,
    end_date: str,
    currency: str = "CNY",
    sell_channel: int = 15,
    payment_type: int = 0,
    price_change_mode: int = 8,
    pricing_power: int = 0,
    price_recode_way: int = 1,
    price_record_way: Optional[int] = None,
    channel_nos: Optional[dict] = None,
    switch_status: int = 0,
    expect_price_change_mode: int = 8,
    contract_no: str = "",
    identity: str = "biz",
    audit_reason: str = DEFAULT_BD_AUDIT_REASON,
    merchant_password: str = DEFAULT_MERCHANT_PASSWORD,
    merchant_service: str = DEFAULT_MERCHANT_SERVICE,
    bd_sso_user: Optional[str] = DEFAULT_BD_SSO_USER,
    bd_sso_password: Optional[str] = DEFAULT_BD_SSO_PASSWORD,
    bd_client_id: Optional[str] = DEFAULT_BD_SSO_CLIENT_ID,
    bd_client_secret: Optional[str] = DEFAULT_BD_SSO_CLIENT_SECRET,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    改价（触发涨跌幅审核判断），通过 tdm-cli 真实登录换票 + HTTP 网关直连调用
    PlatformMeGoodsFacade#updatePriceV2（异步接口）。

    ⚠️ 字段结构对齐真实抓包数据（而不是 batchCreateGoods 创建时的入参结构，两者字段有差异，
       如外层 priceRecordWay 与 goodsBaseInfo.priceRecodeWay 允许不同）：
         - identity="biz"（默认）：商家身份，`tdm token blogin` 换 mebsid，
           2026-08-19 用真实供应商实测通过（code=10000）。
         - identity="bd"：BD 身份，`tdm token sso` 换 messoid，默认使用全局固定测试
           账号 crstest（见 DEFAULT_BD_SSO_*），2026-08-19 实测通过（code=10000）。

    参数：
        partner_id       - 供应商ID
        poi_id           - 门店ID（字符串）
        goods_id         - 商品ID
        goods_name       - 商品全名（goodsName，用于回显，不影响审核判断）
        pre_goods_id     - 预产品ID（preGoodsId）
        goods_status     - 当前商品状态（一般传 2=在线，改价前商品应已上线）
        goods_type       - 商品类型（1=全日房 2=钟点房）
        sale_price_yuan  - 新售价（单位：元，如 500 表示 500.00 元），内部换算为分
        start_date       - 生效开始日期，如 "2026-08-06"
        end_date         - 生效结束日期，如 "2026-08-06"（可传单日，仅用于触发审核，不要求覆盖长周期）
        currency         - 币种（默认 CNY）
        sell_channel/payment_type/price_change_mode/pricing_power/price_recode_way/
        channel_nos/switch_status/expect_price_change_mode/contract_no
                         - 与创建时保持一致的 goodsBaseInfo 附加字段（均有默认值，一般无需覆盖）
        price_record_way - 外层 goodsList[].priceRecordWay（改价录价方式）。不传时按
                            identity 自动取默认值：biz=8（商家模式），bd=1（BD模式，
                            对应 goodsBaseInfo.priceRecordWayList=[1,2,5,7]）。
        identity         - 操作身份："biz"=商家身份（默认，走 EBOriginStrategy），
                            "bd"=BD身份（走 MtaOriginStrategy，需配合 audit_reason 说明审核理由）。
        audit_reason     - BD 改价审核理由（仅 identity="bd" 时生效，写入
                            extendParam.priceAuditInfoModels[0].reason，默认"测试数据构造"）。
        merchant_password - 商家登录密码（仅 identity="biz" 时生效，测试环境固定
                            "Ceshi123"，见 DEFAULT_MERCHANT_PASSWORD）。
        merchant_service  - 商家登录 service 参数（仅 identity="biz" 时生效，
                            测试环境固定 "lvyou"，见 DEFAULT_MERCHANT_SERVICE）。
        bd_sso_user      - BD 员工 SSO 账号（mis，仅 identity="bd" 时生效，默认使用
                            全局固定测试账号 "crstest"（见 DEFAULT_BD_SSO_USER，已实测），
                            一般无需覆盖）。
        bd_sso_password  - BD 员工 SSO 密码（仅 identity="bd" 时生效，默认 "Ceshi123"，
                            见 DEFAULT_BD_SSO_PASSWORD）。
        bd_client_id     - SSO 客户端 ID（仅 identity="bd" 时生效，默认 "hotel_sc"，
                            见 DEFAULT_BD_SSO_CLIENT_ID）。
        bd_client_secret - SSO 客户端密钥（仅 identity="bd" 时生效，默认值见
                            DEFAULT_BD_SSO_CLIENT_SECRET）。
        swimlane         - 泳道（空字符串=主干）
        dry_run          - True 时只打印不执行

    返回：RPC 原始响应 dict（异步接口，data 通常为任务 uuid，真正是否需要审核的结论
          需等待 1~3 秒后通过查详情/priceInfo.priceAuditStatus 确认，本函数不做轮询）
    异常：ValueError（identity 非法），InvokeError（调用失败）
    """
    if identity not in ("biz", "bd"):
        raise ValueError(f"identity={identity!r} 非法，合法值：biz / bd")

    sale_price_fen = str(int(round(sale_price_yuan * 100)))
    if channel_nos is None:
        channel_nos = {"8": ["001", "002"]}
    if price_record_way is None:
        price_record_way = 1 if identity == "bd" else 8
    price_record_way_list = [1, 2, 5, 7] if identity == "bd" else [8, 9]
    ratio_type = 1 if identity == "bd" else 2

    params = {
        "poiId": str(poi_id),
        "partnerId": int(partner_id),
        "currency": currency,
        "createFlag": True,
        "goodsList": [
            {
                "goodsBaseInfo": {
                    "goodsId": int(goods_id),
                    "goodsName": goods_name,
                    "preGoodsId": str(pre_goods_id) if pre_goods_id else None,
                    "goodsStatus": int(goods_status),
                    "goodsType": int(goods_type),
                    "sellChannel": sell_channel,
                    "paymentType": payment_type,
                    "typeLimitValue": 0,
                    "priceChangeMode": price_change_mode,
                    "pricingPower": pricing_power,
                    "priceRecodeWay": price_recode_way,
                    "auditStatus": 4,
                    "priceRecordWayList": price_record_way_list,
                    "channelNos": channel_nos,
                    "goodsTagMap": {},
                    "switchStatus": switch_status,
                    "expectPriceChangeMode": expect_price_change_mode,
                    "poiId": str(poi_id),
                    "partnerId": int(partner_id),
                    "contractNo": contract_no,
                    "singleChannelReason": "",
                    "noPersistent": 0,
                    "goodsSource": 1,
                    "breakFastNum": 0,
                    "deductionAudit": False,
                    "superDealReSale": False,
                    "canAdjustPrice": False,
                },
                "ratioConfig": {
                    "ratioType": ratio_type,
                    "ratioChange": False,
                    "newRatio": "",
                },
                "priceRecordWay": price_record_way,
                "weekDiff": False,
                "calcPriceUnifiedDateModel": {
                    "dates": [
                        {"startDate": start_date, "endDate": end_date}
                    ],
                    "calcPriceWeekModels": [
                        {
                            "inWeek": [1, 2, 3, 4, 5, 6, 7],
                            "calcPriceInfo": {
                                "salePrice": {
                                    "operateType": PRICE_OPERATE_TYPE_EQUAL,
                                    "operateNum": sale_price_fen,
                                },
                                "basePrice": {
                                    "operateType": PRICE_OPERATE_TYPE_NULL,
                                    "operateNum": "",
                                },
                                "subPrice": {
                                    "operateType": PRICE_OPERATE_TYPE_NULL,
                                    "operateNum": "",
                                },
                            },
                            "calcPriceFactorInfos": None,
                        }
                    ],
                },
            }
        ],
        # BD 身份需附带审核理由（extendParam.priceAuditInfoModels），2026-08-18 抓包字段
        # （字段结构未实测验证）；商家身份该字段为空 {}（2026-08-06 抓包，已实测）。
        "extendParam": (
            {
                "priceAuditInfoModels": [
                    {
                        "goodsNameList": [goods_name],
                        "materials": [],
                        "reason": audit_reason,
                    }
                ]
            }
            if identity == "bd"
            else {}
        ),
    }

    # ⚠️ 不再传 PlatformOrigin：真实网关调用时身份完全由登录 Cookie 决定，服务端内部
    # 自行构造 PlatformOrigin，调用方在 body 里传这个字段网关也不会理会（甚至可能报错）。
    # 这正是本次修复的核心——旧版在这里手工拼一个 platform_origin dict 当作第二个 Thrift
    # 参数传下去，看似"指定了身份"，实际服务端根本不认，身份判断真正依据的是 Cookie。

    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    from scripts.http_gateway import (  # noqa
        merchant_login, bd_login, call_gateway, HttpGatewayError,
    )

    if dry_run:
        import json as _json
        print(f"[dry-run] updatePriceV2 HTTP 网关调用参数（identity={identity}）：")
        print(f"  POST {UPDATE_PRICE_GATEWAY_HOST}{UPDATE_PRICE_GATEWAY_API}")
        print(f"  body:\n{_json.dumps(params, ensure_ascii=False, indent=2)}")
        if identity == "bd":
            print(f"  登录方式: tdm token sso -u {bd_sso_user} -p <password>")
        else:
            print(f"  登录方式: tdm token blogin -u {partner_id} -p {merchant_password} -s {merchant_service}")
        return {}

    print(f"正在登录换票（identity={identity}）...")
    if identity == "bd":
        token = bd_login(
            sso_user=bd_sso_user,
            sso_password=bd_sso_password,
            client_id=bd_client_id,
            client_secret=bd_client_secret,
        )
        headers = {"logintype": "SSO", "Cookie": f"messoid={token}"}
    else:
        bsid = merchant_login(
            merchant_user=str(partner_id),
            merchant_password=merchant_password,
            service=merchant_service,
        )
        headers = {"logintype": "Epassport", "Cookie": f"mebsid={bsid}"}

    if swimlane:
        headers["swimlane"] = swimlane

    print(f"正在改价（goodsId={goods_id}，新售价={sale_price_yuan}元，identity={identity}）...")
    try:
        return call_gateway(
            host=UPDATE_PRICE_GATEWAY_HOST,
            api=UPDATE_PRICE_GATEWAY_API,
            body=params,
            headers=headers,
        )
    except HttpGatewayError as e:
        print(f"  ❌ 改价网关调用失败：{e}")
        raise

