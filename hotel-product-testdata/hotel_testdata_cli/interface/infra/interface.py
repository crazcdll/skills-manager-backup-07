#!/usr/bin/env python3
"""
接口层：基础实体创建（POI / 供应商 / 房型）及合同查询、门店配置

工具26  CreatePoi               创建酒店门店（返回 mtPoiId）
工具49  createHotelCustomer     创建可上单客户/供应商（异步，返回 partnerId + platformContractId）
工具534 门店私海认领             将门店认领到 crstest（empId=2196240）
工具777 供应商绑定门店           将供应商与门店绑定
工具498 供应商门店资质审核       门店进行资质审核（通过）
工具476 住宿-门店资质添加         为门店添加资质（住宿客户平台）
工具906 切换合同价格模式（境内） 切换境内供应商价格模式（底价/卖价）
工具928 切换境外门店价格模式     切换境外供应商价格模式（底价/卖价）
工具464 客户ID互查               业务客户ID（partnerId）与平台客户ID 双向互查
工具465 合同ID互查               业务合同ID（originalContractId）与平台合同ID 双向互查

Thrift  IMtaContractService#getContractBaseInfosByPartnerIdAndBusinessType
        根据供应商ID查询合同列表（取 contractNum 作为上单合同编号）
        appkey: com.sankuai.hotel.biz.contract

Thrift  CustomerIdMappingService#getOriginCustomerByCustomerIdAndBusinessLine
        根据平台合同ID查询原始合同编号（contractNo）
        appkey: com.sankuai.nibcus.inf.idmapping

Thrift  CustomerIdMappingService#getCustomerIdByOriginCustomerIdAndBusinessLine
        通过原始客户ID（partnerId）查询业务客户ID（customerId）
        appkey: com.sankuai.nibcus.inf.idmapping


⚠️ 工具49为异步接口，返回后供应商仍需约1分钟才就绪，创建房型若失败请等待后重试。
"""

import sys
import os
import time as _time
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from scripts.du_runner import run_tool, get_result, check_ok, DuError  # noqa


TOOL_POI              = 26
TOOL_PARTNER          = 49
TOOL_ROOM             = 43
TOOL_CLAIM_POI        = 534
TOOL_BIND_PARTNER_POI = 777
TOOL_AUDIT_POI_QUAL   = 498
TOOL_ADD_POI_QUAL     = 476
TOOL_SWITCH_PRICE_DOMESTIC    = 906
TOOL_SWITCH_PRICE_OVERSEAS    = 928
TOOL_TRANSFORM_CUSTOMER_ID    = 464
TOOL_TRANSFORM_CONTRACT_ID    = 465


# ════════════════════════════════════════════════════════════════════════════
# 工具26 - 创建门店（POI）
# ════════════════════════════════════════════════════════════════════════════

def validate_poi(params: dict) -> None:
    """V1 city 必填，V2 poiName 必填"""
    errors = []
    if not params.get("city"):
        errors.append("V1: city 必填（如：北京、上海、东京）")
    if not params.get("poiName"):
        errors.append("V2: poiName 必填")
    if errors:
        raise ValueError(f"[POI] 参数校验失败：\n" + "\n".join(f"  {e}" for e in errors))


def call_poi(
    city: str = "北京",
    poi_name: Optional[str] = None,
    is_overseas: bool = False,
    category_id: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    创建酒店门店（工具26）。

    参数：
        city         - 城市名（默认"北京"）
        poi_name     - 门店名称（默认：<mis>酒店门店_<时间戳>）
        is_overseas  - 是否境外（默认False）
        category_id  - 门店品类ID（境内默认352=四星级，境外默认387=其他酒店）
        dry_run      - True 时只打印不执行

    返回：DataUnity 原始响应，其中 get_result(resp, "mtPoiId") 为门店ID
    """
    from scripts.utils import get_operator  # noqa
    operator = get_operator()
    _poi_name = poi_name or f"{operator}酒店门店_{int(_time.time())}"
    _cat_id = category_id or ("387" if is_overseas else "352")

    params = {
        "bizLine":       "20",
        "useMode":       "1",
        "poiIdType":     "1",
        "poiName":       _poi_name,
        "poiCategoryId": _cat_id,
        "overseas":      "true" if is_overseas else "false",
        "city":          city,
    }
    validate_poi(params)
    return run_tool(TOOL_POI, params, dry_run=dry_run)


# ════════════════════════════════════════════════════════════════════════════
# 工具49 - 创建供应商
# ════════════════════════════════════════════════════════════════════════════

def validate_partner(params: dict) -> None:
    """
    V1  mtaVpoiIds 必填
    V2  partnerType 必须是合法枚举值（2/3/4/5/6/7/9）
    V3  通兑超团（entity_type=2）时 mtaVpoiIds 必须包含 >=2 个门店
    """
    errors = []
    poi_ids_raw = str(params.get("mtaVpoiIds", ""))
    if not poi_ids_raw.strip():
        errors.append("V1: mtaVpoiIds（绑定门店ID）必填")
    pt = params.get("partnerType")
    valid_partner_types = (2, 3, 4, 5, 6, 7, 9)
    if pt not in valid_partner_types:
        errors.append(
            f"V2: partnerType={pt} 非法，合法值：\n"
            "      2=可上单-境内非女娲纸质供应商（境内自采预付）\n"
            "      3=可上单-境外非女娲纸质供应商\n"
            "      4=不可上单-只创建供应商-境内女娲纸质供应商\n"
            "      5=不可上单-只创建供应商-境内女娲电子供应商\n"
            "      6=不可上单-只创建供应商-境外非女娲纸质供应商\n"
            "      7=不可上单-只创建供应商-境内非女娲纸质供应商\n"
            "      9=可上单-境内女娲普通供应商（境内代理预付，总店结算）"
        )
    # entity_type=2（单体酒店）时用于通兑超团，需 >=2 门店
    if params.get("type") == 2:
        ids = [s.strip() for s in poi_ids_raw.split(",") if s.strip()]
        if len(ids) < 2:
            errors.append("V3: 通兑超团（type=2 单体酒店）供应商需绑定 >=2 个门店，"
                          f"当前只有 {len(ids)} 个")
    if errors:
        raise ValueError(f"[供应商] 参数校验失败：\n" + "\n".join(f"  {e}" for e in errors))


def call_partner(
    poi_id: str,
    partner_type: int = 2,
    entity_type: int = 0,
    is_overseas: bool = False,
    partner_name: Optional[str] = None,
    currency: str = "CNY",
    cooperation_type: int = 2,
    prepay_price_change_mode: int = 8,
    settle_date_type: int = 18,
    access_type: int = 0,
    invoice_mode: str = "0",
    is_open_meituan_pay: int = 0,
    is_open_vcc: int = 0,
    bizcode: Optional[str] = None,
    overseas_protocol: Optional[int] = None,
    dry_run: bool = False,
) -> dict:
    """
    创建可上单客户/供应商（工具49，异步）。

    参数：
        poi_id                   - 绑定门店ID（多门店逗号分隔；通兑超团需 >=2 个）
        partner_type             - 客户类型（默认2）：
                                     2=可上单-境内非女娲纸质供应商
                                     3=可上单-境外非女娲纸质供应商
                                     4=不可上单-境内女娲纸质供应商
                                     5=不可上单-境内女娲电子供应商
                                     6=不可上单-境外非女娲纸质供应商
                                     7=不可上单-境内非女娲纸质供应商
                                     9=可上单-境内女娲普通供应商
        entity_type              - 实体类型（默认0）：
                                     0=酒店集团, 1=第三方渠道, 2=单体酒店（通兑超团必填）, 3=多店老板
        is_overseas              - 是否境外（默认False，partner_type=3/6 时建议传True）
        partner_name             - 供应商名称（默认：<mis>可上单客户）
        currency                 - 结算币种（默认CNY；境外可改 JPY/USD/HKD/KWD/VND 等）
        cooperation_type         - 合作类型（默认2=团购+预订合同，即通常语义的"预付"）：
                                     1=直连, 2=团购+预订合同, 4=现付, 6=预付包销合同
                                     （用户未明确说"预付包销"时按默认2处理，不要臆测成6）
        prepay_price_change_mode - 价格模式-境内（默认8=卖价；境外供应商不支持此字段）
        settle_date_type         - 结算周期（默认18=每2周按实际新增消费）：
                                     8=每周, 12=每4周, 18=每2周
        access_type              - 接入类型（默认0=非手工直连）：
                                     0=非手工直连, 1=手工直连
        invoice_mode             - 发票模式（默认"0"=北京酷讯）：
                                     "0"=北京酷讯, "1"=商家给用户开发票, "2"=美团给用户开发票
                                   （仅 partnerType=9/7/4 时生效）
        is_open_meituan_pay      - 同步创建美开（默认0=暂不创建）：
                                     0=暂不创建, 1=一键创建
                                   （仅 partnerType=3 境外时生效）
        is_open_vcc              - 是否进行VCC开卡（默认0=否）：
                                     0=否, 1=是
                                   （仅 partnerType=3 境外时生效）
        bizcode                  - VCC开卡参数（默认"nib.hotel.prepay.zl.ld"）
                                   （仅 is_open_vcc=1 且 partnerType=3 时传入）
        overseas_protocol        - 对接协议（仅 cooperation_type=1 直连且境外时生效）：
                                     1=直连-老开放平台（默认）, 2=直连-新开放平台, 3=直连-VIP
        dry_run                  - True 时只打印不执行

    返回：DataUnity 原始响应
        get_result(resp, "partnerId")          → 供应商ID
        get_result(resp, "platformContractId") → 平台合同ID
    """
    from scripts.utils import get_operator  # noqa
    operator = get_operator()
    _partner_name = partner_name or f"{operator}可上单客户"

    params = {
        "misId":                 operator,
        "partnerType":           partner_type,
        "partnerName":           _partner_name,
        "type":                  entity_type,
        "cooperationType":       cooperation_type,
        "prepayPriceChangeMode": prepay_price_change_mode,
        "currency":              currency,
        "mtaVpoiIds":            poi_id,
        "settleDateType":        settle_date_type,
        "accessType":            access_type,
        "isOpenMeituanPay":      is_open_meituan_pay,
        "isOpenVcc":             is_open_vcc,
    }

    # invoiceMode：仅境内（partnerType=9/7/4）时传入；境外显式置 None 清空模板默认值
    if is_overseas:
        params["invoiceMode"] = None
    else:
        params["invoiceMode"] = invoice_mode

    # bizcode：仅 is_open_vcc=1 且境外时传入；否则显式置 None
    if is_open_vcc == 1 and is_overseas:
        params["bizcode"] = bizcode or "nib.hotel.prepay.zl.ld"
    else:
        params["bizcode"] = None

    # overSeaPartnerOpenProtocol：
    #   - 境外直连（cooperation_type=1）时传入
    #   - 境外非直连 或 境内：显式置 None 清空工具49模板默认值（否则 code:10001）
    if is_overseas and cooperation_type == 1:
        params["overSeaPartnerOpenProtocol"] = str(overseas_protocol) if overseas_protocol is not None else "1"
    else:
        # 工具49模板中 overSeaPartnerOpenProtocol 默认值为 1，必须显式清空，
        # 否则该字段会被带入请求，导致接口返回"系统错误"（code:10001）
        params["overSeaPartnerOpenProtocol"] = None

    validate_partner(params)
    return run_tool(TOOL_PARTNER, params, dry_run=dry_run)


# ════════════════════════════════════════════════════════════════════════════
# HTTP - 创建房型（fd.banma createRoomAction，统一接口内部封装完整流程）
#
# 接口：POST http://fd.banma.test.sankuai.com/api/autoCase/run
# sceneId=47034, actionId=356285
# 内部自动串联：创建物理房型 → 审核 → 上传图片 → 查询 roomInfoId
# ════════════════════════════════════════════════════════════════════════════

import json as _json
import subprocess as _subprocess

_FD_BANMA_URL = "http://fd.banma.test.sankuai.com/api/autoCase/run"
_FD_SCENE_ID  = "47034"
_FD_ACTION_ID = "356285"
_FD_MIS_ID    = "zhuwenjing06"


def validate_room(params: dict) -> None:
    """V1 partnerId 必填，V2 poiId 必填"""
    errors = []
    if not params.get("partnerId"):
        errors.append("V1: partnerId 必填")
    if not params.get("poiId"):
        errors.append("V2: poiId 必填")
    if errors:
        raise ValueError(f"[房型] 参数校验失败：\n" + "\n".join(f"  {e}" for e in errors))


def call_room(
    partner_id: str,
    poi_id: str,
    room_name: Optional[str] = None,
    is_overseas: bool = False,
    room_type: int = 0,
    room_area: Optional[str] = None,
    capacity: Optional[int] = None,
    window_type: Optional[int] = None,
    floor: Optional[int] = None,
    dry_run: bool = False,
) -> dict:
    """
    创建酒店房型（fd.banma createRoomAction 统一接口）。

    接口内部自动串联完整流程：
        创建物理房型 → 获取最大 realRoomId → 审核物理房型
        → 上传房型图片 → 查询 roomInfoId（逻辑房型ID）

    参数：
        partner_id  - 供应商ID（必填）
        poi_id      - 门店ID（必填）
        room_name   - 房型名称前缀（选填）。始终自动追加时间戳保证全局唯一：
                      不传 → 「<mis><时间戳>」；传了 → 「<传入值><时间戳>」
        is_overseas - 是否境外（默认False）
        room_type   - 房间类型：0=大床间,1=单人间,2=双床间,3=三人间,4=套房,5=独栋,6=床位房（默认0）
        room_area   - 房间面积范围，如 "11-15"（默认 None，接口默认 11-15）
        capacity    - 最大入住人数（默认 None，接口默认 2）
        window_type - 窗户情况：0=全部有窗,1=部分有窗,2=全部无窗（默认 None，接口默认 2）
        floor       - 楼层（默认 None，接口默认 1）
        dry_run     - True 时只打印不执行

    返回：接口原始响应 dict，包含：
        resp["success"]    → True/False
        resp["message"]    → 结果描述
        resp["roomInfoId"] → 逻辑房型ID（上单必填，等同于旧版 roomId）
        resp["realRoomId"] → 物理房型ID
        resp["roomName"]   → 最终使用的房型名称
        resp["poiId"]      → 门店ID
        resp["partnerId"]  → 供应商ID
    """
    validate_room({"partnerId": partner_id, "poiId": poi_id})

    param_json = {
        "poiId":      int(poi_id),
        "partnerId":  int(partner_id),
        "roomName":   room_name,
        "isOverSea":  is_overseas,
        "roomType":   room_type,
        "roomArea":   room_area,
        "capacity":   capacity,
        "windowType": window_type,
        "floor":      floor,
    }

    payload = {
        "sceneId":   _FD_SCENE_ID,
        "actionId":  _FD_ACTION_ID,
        "misId":     _FD_MIS_ID,
        "paramJson": _json.dumps(param_json, ensure_ascii=False),
    }

    if dry_run:
        print(f"\n[dry-run] 创建房型（fd.banma createRoomAction）")
        print(f"  POST {_FD_BANMA_URL}")
        print(f"  body: {_json.dumps(payload, ensure_ascii=False, indent=2)}")
        return {"dry_run": True}

    cmd = [
        "curl", "-s", "--location", "--request", "POST", _FD_BANMA_URL,
        "--header", "Content-Type: application/json",
        "--data-raw", _json.dumps(payload, ensure_ascii=False),
    ]
    r = _subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        outer = _json.loads(r.stdout)
    except _json.JSONDecodeError:
        return {"success": False, "message": f"响应解析失败: {r.stdout[:300]}"}

    # 外层结构：{"resultCode":"0000","data":{"356285":"<inner JSON字符串>"},...}
    # 需要二次解析 data[actionId] 字段，取出真正的业务响应
    outer_trace_id = outer.get("traceId", "")
    try:
        inner_str = outer.get("data", {}).get(_FD_ACTION_ID)
        if inner_str:
            inner = _json.loads(inner_str)
            # 将外层 traceId 注入内层，方便调用方打印排查
            if isinstance(inner, dict) and "traceId" not in inner:
                inner["traceId"] = outer_trace_id
            return inner
    except (_json.JSONDecodeError, AttributeError):
        pass

    # 外层本身失败或无 data 字段，直接返回外层
    if outer.get("resultCode") != "0000":
        return {"success": False, "message": outer.get("resultMsg", str(outer)[:200]), "traceId": outer_trace_id}

    return outer


# ════════════════════════════════════════════════════════════════════════════
# Thrift - 根据平台合同ID查询原始合同编号（contractNo）
# ════════════════════════════════════════════════════════════════════════════

_APPKEY_CONTRACT   = "com.sankuai.contract.mtcontract"
_SERVICE_CONTRACT  = "com.sankuai.meituan.contract.service.ContractService"
_METHOD_GET_CONTRACT_MAPPING = "getContractIdMapping"


def query_contract_no(
    platform_contract_id: int,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    根据平台合同ID查询原始合同编号（contractNo）。

    接口：
        com.sankuai.meituan.contract.service.ContractService#getContractIdMapping
        appkey: com.sankuai.meituan.contract

    参数：
        platform_contract_id - 平台合同ID（工具49返回的 platformContractId）
        swimlane             - 泳道（空字符串=主干）
        dry_run              - True 时只打印不执行

    返回：接口原始响应 dict
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    from scripts.runner import invoke  # noqa

    # 接口签名：getContractIdMapping(Long contractId)
    # 使用 parameter_values 位置参数模式
    return invoke(
        appkey=_APPKEY_CONTRACT,
        service=_SERVICE_CONTRACT,
        method=_METHOD_GET_CONTRACT_MAPPING,
        swimlane=swimlane,
        timeout_ms=15000,
        dry_run=dry_run,
        raise_on_biz_error=False,
        progress_hint=f"查询合同编号（platformContractId={platform_contract_id}）...",
        parameter_values=[
            str(int(platform_contract_id)),   # 参数1：contractId（Long）
        ],
        parameter_types=[
            "java.lang.Long",
        ],
    )


# ════════════════════════════════════════════════════════════════════════════
# 工具584 - 根据供应商ID查询客户合同详细信息（contractNo）
# ════════════════════════════════════════════════════════════════════════════

def query_contract_by_partner_id(
    partner_id: str,
    dry_run: bool = False,
) -> dict:
    """
    根据供应商ID（业务客户ID）查询客户合同详细信息。

    工具584：查询客户合同详细信息
    真实入参（来自抓包）：
        originCustomerId  - 业务客户ID（即 partnerId，如 "4549866"）
        businessLineId    - 业务线ID，住宿固定传 3（整数）
    真实出参 results 关键字段：
        itemKey="客户合同信息列表"  itemType="table"
            value = [{..., "number": "ZSFW-A9-80181637", "status": "1", ...}, ...]
        itemKey="返回值_1"  itemType="JSON"
            value = ["ZSFW-A9-80181637"]   # 合同编号简单数组，最方便提取

    参数：
        partner_id - 供应商ID
        dry_run    - True 时只打印不执行

    返回：DataUnity 工具执行响应（原始 JSON）
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    from scripts.du_runner import run_tool  # noqa

    return run_tool(
        tool_id=584,
        overrides={
            "originCustomerId": str(partner_id),
            "businessLineId":   3,            # 住宿业务线固定为整数 3
        },
        dry_run=dry_run,
    )


# ════════════════════════════════════════════════════════════════════════════
# Thrift - 根据供应商ID查询合同列表（IMtaContractService）
#
# 接口：com.meituan.hotel.contract.mta.service.IMtaContractService
#        #getContractBaseInfosByPartnerIdAndBusinessType
# appkey：com.sankuai.hotel.biz.contract
#
# 说明：
#   路径B/C/D 合同就绪环节使用。
#   businessType 固定传 [2,4,5]（预付/现付/预付包销），取 contractNum 字段作为上单合同编号。
# ════════════════════════════════════════════════════════════════════════════

_APPKEY_MTA_CONTRACT  = "com.sankuai.hotel.biz.contract"
_SERVICE_MTA_CONTRACT = "com.meituan.hotel.contract.thrift.service.IMtaContractService"
_METHOD_GET_CONTRACTS = "getLastAuditPassContract"


def query_contracts_by_partner(
    partner_id: str,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    根据供应商ID查询最新审核通过的合同（Thrift RPC）。

    接口：
        com.meituan.hotel.contract.thrift.service.IMtaContractService
            #getLastAuditPassContract
        appkey: com.sankuai.hotel.biz.contract

    参数：
        partner_id - 供应商ID（业务客户ID）
        swimlane   - 泳道（空字符串=主干）
        dry_run    - True 时只打印不执行

    返回：接口原始响应 dict
        resp["data"]["basicInfo"]["contractNum"] → 上单合同编号
        resp["data"]["basicInfo"]["auditStatus"] → 3=审核通过
        resp["data"]["basicInfo"]["onlineStatus"] → 1=上线
    """
    from scripts.runner import invoke  # noqa

    return invoke(
        appkey=_APPKEY_MTA_CONTRACT,
        service=_SERVICE_MTA_CONTRACT,
        method=_METHOD_GET_CONTRACTS,
        swimlane=swimlane,
        timeout_ms=15000,
        dry_run=dry_run,
        raise_on_biz_error=False,
        progress_hint=f"查询最新审核通过合同（partnerId={partner_id}）...",
        parameter_values=[
            str(int(partner_id)),
        ],
        parameter_types=[
            "java.lang.Integer",
        ],
    )


# ════════════════════════════════════════════════════════════════════════════
# 工具534 - 门店私海认领
# ════════════════════════════════════════════════════════════════════════════

def validate_claim_poi(params: dict) -> None:
    """V1 poiId 必填"""
    if not params.get("poiId"):
        raise ValueError("[门店私海认领] 参数校验失败：V1: poiId 必填")


def call_claim_poi(
    poi_id: str,
    emp_id: str = "2196240",
    dry_run: bool = False,
) -> dict:
    """
    门店私海认领（工具534）。

    将门店从私海认领到指定 EmpId（默认 crstest=2196240），
    是供应商绑定门店（工具777）的前置步骤。

    参数：
        poi_id  - 门店ID（create-poi.py 返回的 mtPoiId）
        emp_id  - 认领人 EmpId，固定填 2196240（crstest），不建议修改
        dry_run - True 时只打印不执行

    返回：DataUnity 原始响应
    """
    params = {
        "poiId": poi_id,
        "empId": emp_id,
    }
    validate_claim_poi(params)
    return run_tool(TOOL_CLAIM_POI, params, dry_run=dry_run)


# ════════════════════════════════════════════════════════════════════════════
# 工具777 - 供应商绑定门店
# ════════════════════════════════════════════════════════════════════════════

def validate_bind_partner_poi(params: dict) -> None:
    """V1 poiIds 必填，V2 partnerId 必填"""
    errors = []
    if not params.get("poiIds"):
        errors.append("V1: poiIds（美团门店ID）必填")
    if not params.get("partnerId"):
        errors.append("V2: partnerId（供应商ID）必填")
    if errors:
        raise ValueError(f"[供应商绑定门店] 参数校验失败：\n" + "\n".join(f"  {e}" for e in errors))


def call_bind_partner_poi(
    poi_id: str,
    partner_id: str,
    dry_run: bool = False,
) -> dict:
    """
    供应商绑定门店（工具777）。



    参数：
        poi_id     - 美团门店ID
        partner_id - 供应商ID
        dry_run    - True 时只打印不执行

    返回：DataUnity 原始响应
    """
    params = {
        "hotelCustomertype": "1",  # 固定：供应商ID
        "poiIds":    poi_id,
        "partnerId": partner_id,
    }
    validate_bind_partner_poi(params)
    return run_tool(TOOL_BIND_PARTNER_POI, params, dry_run=dry_run)


# ════════════════════════════════════════════════════════════════════════════
# 工具498 - 供应商门店资质审核
# ════════════════════════════════════════════════════════════════════════════

def validate_audit_poi_qualification(params: dict) -> None:
    """V1 poiId 必填"""
    if not params.get("poiId"):
        raise ValueError("[供应商门店资质审核] 参数校验失败：V1: poiId 必填")


def call_audit_poi_qualification(
    poi_id: str,
    audit_type: str = "供应商门店资质审核",
    audit_result: str = "通过",
    dry_run: bool = False,
) -> dict:
    """
    供应商门店资质审核（工具498）。

    供应商绑定门店（工具777）成功后，必须执行本步骤完成资质审核，
    否则门店无法正常上单。

    参数：
        poi_id       - 门店ID
        audit_type   - 审核类型，固定"供应商门店资质审核"
        audit_result - 审核结果，固定"通过"
        dry_run      - True 时只打印不执行

    返回：DataUnity 原始响应
    """
    params = {
        "poiId":       poi_id,
        "auditType":   audit_type,
        "auditResult": audit_result,
    }
    validate_audit_poi_qualification(params)
    return run_tool(TOOL_AUDIT_POI_QUAL, params, dry_run=dry_run)


# ════════════════════════════════════════════════════════════════════════════
# 工具476 - 住宿-门店资质添加
# ════════════════════════════════════════════════════════════════════════════

def validate_add_poi_qualification(params: dict) -> None:
    """V1 poiIds 必填"""
    if not params.get("poiIds"):
        raise ValueError("[门店资质添加] 参数校验失败：V1: poiIds 必填")


def call_add_poi_qualification(
    poi_id: str,
    dry_run: bool = False,
) -> dict:
    """
    住宿-门店资质添加（工具476）。

    为门店添加资质（住宿客户平台），使门店满足上单的资质要求。
    接口：POST http://datamanagement.nibcus.test.sankuai.com/api/hotel/poiSaveQualitification

    参数：
        poi_id  - 门店ID（美团 mtPoiId），必填
        dry_run - True 时只打印不执行

    返回：DataUnity 原始响应
    """
    params = {
        "poiIds": poi_id,
    }
    validate_add_poi_qualification(params)
    return run_tool(TOOL_ADD_POI_QUAL, params, dry_run=dry_run)


# ════════════════════════════════════════════════════════════════════════════
# 工具906/928 - 价格模式切换（底价/卖价）
# ════════════════════════════════════════════════════════════════════════════

# 价格模式枚举（工具906 境内）
PRICE_MODE_BASE_PRICE   = "BASE_PRICE"    # 底价模式
PRICE_MODE_SELLING      = "SELLING_PRICE" # 卖价模式

# 工具928 境外 priceMode 枚举
PRICE_MODE_OVERSEAS_BASE    = "2"  # 底价/结算价佣金率
PRICE_MODE_OVERSEAS_SELLING = "1"  # 卖价/美团价佣金率


def validate_switch_price_mode(params: dict, is_overseas: bool) -> None:
    """校验价格模式切换参数"""
    errors = []
    if is_overseas:
        if not params.get("partnerId"):
            errors.append("V1: partnerId 必填（境外）")
        if not params.get("poiId"):
            errors.append("V2: poiId 必填（境外）")
        if params.get("priceMode") not in ("1", "2"):
            errors.append("V3: priceMode 非法（境外），合法值：1=卖价, 2=底价")
    else:
        if not params.get("contractId"):
            errors.append("V1: contractId（platformContractId）必填（境内）")
        if params.get("prepayPriceChangeMode") not in (PRICE_MODE_BASE_PRICE, PRICE_MODE_SELLING):
            errors.append(
                f"V2: prepayPriceChangeMode 非法（境内），合法值："
                f"{PRICE_MODE_BASE_PRICE} / {PRICE_MODE_SELLING}"
            )
    if errors:
        raise ValueError(f"[价格模式切换] 参数校验失败：\n" + "\n".join(f"  {e}" for e in errors))


def call_switch_price_mode(
    mode: str,
    is_overseas: bool = False,
    contract_id: Optional[str] = None,
    partner_id: Optional[str] = None,
    poi_id: Optional[str] = None,
    pricing_power: Optional[str] = None,
    switch_status_enum: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    切换价格模式（工具906境内 / 工具928境外）。

    境内（工具906）：
        mode        - "BASE_PRICE" 底价 或 "SELLING_PRICE" 卖价
        contract_id - platformContractId（供应商创建时返回）
        pricing_power / switch_status_enum - 可选，传 None 时由工具默认值处理

    境外（工具928）：
        mode       - "2" 底价/结算价佣金率 或 "1" 卖价/美团价佣金率
        partner_id - 供应商ID
        poi_id     - 门店ID

    参数：
        mode               - 目标价格模式
        is_overseas        - True=境外（工具928），False=境内（工具906）
        contract_id        - 境内必填，platformContractId
        partner_id         - 境外必填，供应商ID
        poi_id             - 境外必填，门店ID
        pricing_power      - 境内可选
        switch_status_enum - 境内可选
        dry_run            - True 时只打印不执行

    返回：DataUnity 原始响应
    """
    if is_overseas:
        params = {
            "partnerId": partner_id,
            "poiId":     poi_id,
            "priceMode": mode,
        }
        validate_switch_price_mode(params, is_overseas=True)
        return run_tool(TOOL_SWITCH_PRICE_OVERSEAS, params, dry_run=dry_run)
    else:
        params = {
            "contractId":              contract_id,
            "prepayPriceChangeMode":   mode,
        }
        if pricing_power is not None:
            params["pricingPower"] = pricing_power
        if switch_status_enum is not None:
            params["switchStatusEnum"] = switch_status_enum
        validate_switch_price_mode(params, is_overseas=False)
        return run_tool(TOOL_SWITCH_PRICE_DOMESTIC, params, dry_run=dry_run)


# ════════════════════════════════════════════════════════════════════════════
# Thrift - 通过原始客户ID（partnerId）查询业务客户ID（customerId）
#
# 接口：com.sankuai.nibcus.inf.idmapping.client.service.CustomerIdMappingService
#        #getCustomerIdByOriginCustomerIdAndBusinessLine
# appkey：com.sankuai.nibcus.inf.idmapping
#
# 说明：
#   工具49（createHotelCustomer）返回的是 partnerId，这是「原始客户ID」。
#   上单时部分接口（如非房/套餐）实际需要的是「业务客户ID」（customerId）。
#   本接口完成 partnerId → customerId 的映射转换。
# ════════════════════════════════════════════════════════════════════════════

_APPKEY_ID_MAPPING   = "com.sankuai.nibcus.inf.idmapping"
_SERVICE_ID_MAPPING  = "com.sankuai.nibcus.inf.idmapping.client.service.CustomerIdMappingService"
_METHOD_GET_CUSTOMER_ID = "getCustomerIdByOriginCustomerIdAndBusinessLine"

# 酒店业务线 ID（CustomerIdMappingService 专用，与 DataUnity bizLine=20 不同）
_BIZ_LINE_HOTEL = 3


def query_customer_id_by_origin(
    origin_customer_id: int,
    business_line_id: int = _BIZ_LINE_HOTEL,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    通过原始客户ID（partnerId）查询业务客户ID（customerId）。

    接口：
        com.sankuai.nibcus.inf.idmapping.client.service.CustomerIdMappingService
            #getCustomerIdByOriginCustomerIdAndBusinessLine
        appkey: com.sankuai.nibcus.inf.idmapping

    参数：
        origin_customer_id - 原始客户ID，即工具49返回的 partnerId
        business_line_id   - 业务线ID（默认3=酒店，CustomerIdMappingService 枚举值，≠ DataUnity bizLine）
        swimlane           - 泳道（空字符串=主干）
        dry_run            - True 时只打印不执行

    返回：接口原始响应 dict，正常结果结构：
        {
            "result": <customerId: Long>,  // 业务客户ID
            "success": true
        }
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    from scripts.runner import invoke  # noqa

    return invoke(
        appkey=_APPKEY_ID_MAPPING,
        service=_SERVICE_ID_MAPPING,
        method=_METHOD_GET_CUSTOMER_ID,
        swimlane=swimlane,
        timeout_ms=15000,
        dry_run=dry_run,
        raise_on_biz_error=False,
        progress_hint=f"查询 customerId（originCustomerId={origin_customer_id}, bizLine={business_line_id}）...",
        parameter_values=[
            str(int(origin_customer_id)),   # 参数1：originCustomerId（Long）
            str(int(business_line_id)),     # 参数2：businessLineId（Long）
        ],
        parameter_types=[
            "java.lang.Long",
            "java.lang.Long",
        ],
    )


# ════════════════════════════════════════════════════════════════════════════
# 工具464 - 客户ID互查（业务客户ID ↔ 平台客户ID）
#
# 接口：GET http://datamanagement.nibcus.test.sankuai.com/platform/transformCustomerID
# 说明：
#   工具49（createHotelCustomer）返回的是 partnerId（业务客户ID/originCustomerId）。
#   本工具支持双向互查：
#     - partnerId  → platformCustomerId
#     - platformCustomerId → partnerId
#   bizLine=3 对应住宿业务线（区别于 DataUnity 的 bizLine=20）。
# ════════════════════════════════════════════════════════════════════════════

# bizLine 枚举（工具464专用，与 DataUnity bizLine=20 不同）
BIZ_LINE_MAP_DINING   = "1"   # 到餐
BIZ_LINE_MAP_ZHONGZONG = "2"  # 到综
BIZ_LINE_MAP_HOTEL    = "3"   # 住宿
BIZ_LINE_MAP_TICKET   = "4"   # 门票


def validate_transform_customer_id(
    origin_customer_id_str: Optional[str],
    platform_customer_id_str: Optional[str],
) -> None:
    """V1 originCustomerIdStr 与 platformCustomerIdStr 至少传一个"""
    if not origin_customer_id_str and not platform_customer_id_str:
        raise ValueError(
            "[客户ID互查] 参数校验失败：V1: originCustomerIdStr 和 platformCustomerIdStr "
            "至少填写一个"
        )


def call_transform_customer_id(
    origin_customer_id_str: Optional[str] = None,
    platform_customer_id_str: Optional[str] = None,
    biz_line: str = BIZ_LINE_MAP_HOTEL,
    dry_run: bool = False,
) -> dict:
    """
    客户ID互查（工具464）。

    业务客户ID（partnerId/originCustomerId）与平台客户ID（platformCustomerId）双向互查。
    两个 ID 参数二选一传入，查询对应的另一个。

    参数：
        origin_customer_id_str   - 业务客户ID（partnerId），与 platform_customer_id_str 二选一
        platform_customer_id_str - 平台客户ID，与 origin_customer_id_str 二选一
        biz_line                 - 业务线（默认"3"=住宿）：
                                     "1"=到餐, "2"=到综, "3"=住宿, "4"=门票
                                   ⚠️ 此 bizLine 是工具464内部枚举，≠ DataUnity bizLine=20
        dry_run                  - True 时只打印不执行

    返回：DataUnity 原始响应
        get_result(resp, "platformCustomerId") → 平台客户ID
        get_result(resp, "originCustomerId")   → 业务客户ID（partnerId）
    """
    validate_transform_customer_id(origin_customer_id_str, platform_customer_id_str)
    params = {
        "originCustomerIdStr":   origin_customer_id_str,
        "bizLine":               biz_line,
        "platformCustomerIdStr": platform_customer_id_str,
    }
    return run_tool(TOOL_TRANSFORM_CUSTOMER_ID, params, dry_run=dry_run)


# ════════════════════════════════════════════════════════════════════════════
# 工具465 - 合同ID互查（业务合同ID ↔ 平台合同ID）
#
# 接口：GET http://datamanagement.nibcus.test.sankuai.com/platform/transformContractID
# 说明：
#   工具49（createHotelCustomer）返回的是 platformContractId（平台合同ID）。
#   本工具支持双向互查：
#     - originalContractId（业务合同ID）→ platformContractId + contractNumber（合同编号字符串）
#     - platformContractId → originalContractId + contractNumber
#   bizLine=3 对应住宿业务线（区别于 DataUnity 的 bizLine=20）。
# ════════════════════════════════════════════════════════════════════════════


def validate_transform_contract_id(
    original_contract_id_str: Optional[str],
    platform_contract_id_str: Optional[str],
) -> None:
    """V1 originalContractIdStr 与 platformContractIdStr 至少传一个"""
    if not original_contract_id_str and not platform_contract_id_str:
        raise ValueError(
            "[合同ID互查] 参数校验失败：V1: originalContractIdStr 和 platformContractIdStr "
            "至少填写一个"
        )


def call_transform_contract_id(
    original_contract_id_str: Optional[str] = None,
    platform_contract_id_str: Optional[str] = None,
    biz_line: str = BIZ_LINE_MAP_HOTEL,
    dry_run: bool = False,
) -> dict:
    """
    合同ID互查（工具465）。

    业务合同ID（originalContractId）与平台合同ID（platformContractId）双向互查，
    同时返回合同编号字符串（contractNumber，如 ZSFW-A9-75178816）。

    参数：
        original_contract_id_str - 业务合同ID，与 platform_contract_id_str 二选一
        platform_contract_id_str - 平台合同ID（工具49返回的 platformContractId），
                                   与 original_contract_id_str 二选一
        biz_line                 - 业务线（默认"3"=住宿）：
                                     "1"=到餐, "2"=到综, "3"=住宿, "4"=门票
                                   ⚠️ 此 bizLine 是工具465内部枚举，≠ DataUnity bizLine=20
        dry_run                  - True 时只打印不执行

    返回：DataUnity 原始响应
        get_result(resp, "平台合同ID")  → platformContractId（数字字符串）
        get_result(resp, "合同编号")    → contractNumber（如 ZSFW-A9-75178816）
        get_result(resp, "客户合同ID")  → originalContractId
    """
    validate_transform_contract_id(original_contract_id_str, platform_contract_id_str)
    params = {
        "originalContractIdStr":  original_contract_id_str,
        "bizLine":                biz_line,
        "platformContractIdStr":  platform_contract_id_str,
    }
    return run_tool(TOOL_TRANSFORM_CONTRACT_ID, params, dry_run=dry_run)

