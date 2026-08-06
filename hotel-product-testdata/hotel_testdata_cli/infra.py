#!/usr/bin/env python3
"""
infra 层 - 基础实体原子操作 + 底层接口调用

原 infra/infra.py 和 interface/infra/interface.py 合并于此。

工具清单：
  工具26   CreatePoi               创建酒店门店
  工具49   createHotelCustomer     创建供应商（异步）
  工具43   createRoomAction        创建房型（fd.banma HTTP）
  工具534  门店私海认领
  工具777  供应商绑定门店
  工具476  住宿-门店资质添加
  工具498  供应商门店资质审核
  工具447  新建合同
  工具906/928 价格模式切换
  工具464/465 ID互查
  Thrift   IMtaContractService#getLastAuditPassContract
"""

import json
import subprocess
import time
from datetime import datetime
from typing import Optional

from hotel_testdata_cli.scripts.du_runner import run_tool, get_result, check_ok, DuError
from hotel_testdata_cli.scripts.runner import StepError, poll_until_ready

# ════════════════════════════════════════════════════════════════════════════
# 工具 ID 常量
# ════════════════════════════════════════════════════════════════════════════

TOOL_POI              = 26
TOOL_PARTNER          = 49
TOOL_ROOM             = 43
TOOL_CLAIM_POI        = 534
TOOL_BIND_PARTNER_POI = 777
TOOL_AUDIT_POI_QUAL   = 498
TOOL_ADD_POI_QUAL     = 476
TOOL_CREATE_CONTRACT  = 447
TOOL_SWITCH_PRICE_DOMESTIC  = 906
TOOL_SWITCH_PRICE_OVERSEAS  = 928
TOOL_TRANSFORM_CUSTOMER_ID  = 464
TOOL_TRANSFORM_CONTRACT_ID  = 465

# 房型 fd.banma 接口配置
_FD_BANMA_URL = "http://fd.banma.test.sankuai.com/api/autoCase/run"
_FD_SCENE_ID  = "47034"
_FD_ACTION_ID = "356285"
_FD_MIS_ID    = "zhuwenjing06"

# 合同 Thrift 配置
_APPKEY_MTA_CONTRACT  = "com.sankuai.hotel.biz.contract"
_SERVICE_MTA_CONTRACT = "com.meituan.hotel.contract.thrift.service.IMtaContractService"
_METHOD_GET_CONTRACTS = "getLastAuditPassContract"


# ════════════════════════════════════════════════════════════════════════════
# 一、门店（POI）
# ════════════════════════════════════════════════════════════════════════════

def create_poi(
    city: str = "北京",
    poi_name: Optional[str] = None,
    is_overseas: bool = False,
    dry_run: bool = False,
) -> dict:
    """创建门店（工具26）。返回 {"poiId": str}"""
    from hotel_testdata_cli.scripts.utils import get_operator
    operator = get_operator()
    _poi_name = poi_name or f"{operator}酒店门店_{int(time.time())}"
    _cat_id = "387" if is_overseas else "352"
    params = {
        "bizLine":       "20",
        "useMode":       "1",
        "poiIdType":     "1",
        "poiName":       _poi_name,
        "poiCategoryId": _cat_id,
        "overseas":      "true" if is_overseas else "false",
        "city":          city,
    }
    if not params.get("city"):
        raise ValueError("city 必填")

    try:
        resp = run_tool(TOOL_POI, params, dry_run=dry_run)
    except DuError as e:
        raise StepError("create_poi", str(e), detail=e.resp)

    if dry_run:
        return {"dry_run": True}

    def _clean(v):
        """将 'null'/'None'/空字符串统一视为 None。"""
        return v if v and str(v).lower() not in ("null", "none") else None

    poi_id = _clean(get_result(resp, "mtPoiId")) or _clean(get_result(resp, "poiId"))
    if not poi_id:
        check_ok(resp, "创建门店")
        raise StepError("create_poi", f"未能获取 poiId，resp={json.dumps(resp)[:300]}")

    print(f"✅ 门店创建成功 poiId={poi_id}")
    return {"poiId": poi_id}


# ════════════════════════════════════════════════════════════════════════════
# 二、私海认领
# ════════════════════════════════════════════════════════════════════════════

def claim_poi(
    poi_id: str,
    emp_id: str = "2196240",
    dry_run: bool = False,
) -> dict:
    """门店私海认领（工具534）。"""
    if not dry_run and not poi_id:
        raise ValueError("poiId 必填")

    try:
        resp = run_tool(TOOL_CLAIM_POI, {"poiId": poi_id, "empId": emp_id}, dry_run=dry_run)
    except DuError as e:
        raise StepError("claim_poi", str(e), detail=e.resp)

    if dry_run:
        return {"dry_run": True}

    try:
        check_ok(resp, "私海认领")
    except DuError as e:
        err_text = str(e)
        if "已占" in err_text or "已认领" in err_text or "已经认领" in err_text:
            print(f"⚠️  门店已认领（跳过）: {err_text}")
            return {"poiId": poi_id, "skipped": True}
        raise StepError("claim_poi", err_text, detail=e.resp)

    print(f"✅ 私海认领成功 poiId={poi_id}")
    return {"poiId": poi_id}


# ════════════════════════════════════════════════════════════════════════════
# 三、绑定门店
# ════════════════════════════════════════════════════════════════════════════

def bind_partner_poi(
    poi_id: str,
    partner_id: str,
    dry_run: bool = False,
) -> dict:
    """供应商绑定门店（工具777）。"""
    if not dry_run and (not poi_id or not partner_id):
        raise ValueError("poiId 和 partnerId 均必填")

    try:
        resp = run_tool(TOOL_BIND_PARTNER_POI, {
            "hotelCustomertype": "1",
            "poiIds":    poi_id,
            "partnerId": partner_id,
        }, dry_run=dry_run)
    except DuError as e:
        raise StepError("bind_partner_poi", str(e), detail=e.resp)

    if dry_run:
        return {"dry_run": True}

    try:
        check_ok(resp, "绑定门店")
    except DuError as e:
        raise StepError("bind_partner_poi", str(e), detail=e.resp)

    print(f"✅ 绑定门店成功 partnerId={partner_id} poiId={poi_id}")
    return {"poiId": poi_id, "partnerId": partner_id}


# ════════════════════════════════════════════════════════════════════════════
# 四、创建供应商
# ════════════════════════════════════════════════════════════════════════════

def create_partner(
    poi_id: str,
    partner_type: int = 2,
    entity_type: int = 0,
    is_overseas: bool = False,
    currency: str = "CNY",
    cooperation_type: int = 2,
    dry_run: bool = False,
) -> dict:
    """创建可上单客户（工具49，异步）。返回 {"partnerId": str, "platformContractId": str}"""
    from hotel_testdata_cli.scripts.utils import get_operator
    operator = get_operator()
    params = {
        "misId":                 operator,
        "partnerType":           partner_type,
        "partnerName":           f"{operator}可上单客户",
        "type":                  entity_type,
        "cooperationType":       cooperation_type,
        "prepayPriceChangeMode": 8,
        "currency":              currency,
        "mtaVpoiIds":            poi_id,
        "settleDateType":        18,
        "accessType":            0,
        "isOpenMeituanPay":      0,
        "isOpenVcc":             0,
        "invoiceMode":           None if is_overseas else "0",
        "overSeaPartnerOpenProtocol": None,
        "bizcode": None,
    }

    try:
        resp = run_tool(TOOL_PARTNER, params, dry_run=dry_run)
    except DuError as e:
        raise StepError("create_partner", str(e), detail=e.resp)

    if dry_run:
        return {"dry_run": True}

    try:
        check_ok(resp, "创建供应商")
    except DuError as e:
        raise StepError("create_partner", str(e), detail=e.resp)

    partner_id           = get_result(resp, "partnerId") or get_result(resp, "bpCustomerId")
    platform_contract_id = get_result(resp, "platformContractId") or get_result(resp, "contractId")

    # 工具49 的结果嵌套在 itemKey="返回值" 的 JSON 字符串里，需要二次解析
    if not partner_id or partner_id in ("null", "None", "0"):
        raw_val = get_result(resp, "返回值")
        if raw_val:
            try:
                biz = raw_val if isinstance(raw_val, dict) else json.loads(raw_val)
                inner = biz.get("data") or {}
                partner_id           = str(inner.get("partnerId", "")) or partner_id
                platform_contract_id = str(inner.get("platformContractId", "")) or platform_contract_id
            except Exception:
                pass

    if not partner_id or partner_id in ("null", "None", "0"):
        raise StepError("create_partner", f"未能获取 partnerId，resp={json.dumps(resp)[:300]}")

    print(f"✅ 供应商创建成功（异步，约1分钟就绪）")
    print(f"   partnerId           = {partner_id}")
    print(f"   platformContractId  = {platform_contract_id}")
    return {"partnerId": partner_id, "platformContractId": platform_contract_id}


# ════════════════════════════════════════════════════════════════════════════
# 五、查询合同
# ════════════════════════════════════════════════════════════════════════════

def _query_contracts_by_partner(
    partner_id: str,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    from hotel_testdata_cli.scripts.runner import invoke
    return invoke(
        appkey=_APPKEY_MTA_CONTRACT,
        service=_SERVICE_MTA_CONTRACT,
        method=_METHOD_GET_CONTRACTS,
        swimlane=swimlane,
        timeout_ms=15000,
        dry_run=dry_run,
        raise_on_biz_error=False,
        progress_hint=f"查询最新审核通过合同（partnerId={partner_id}）...",
        parameter_values=[str(int(partner_id)) if partner_id else "0"],
        parameter_types=["java.lang.Integer"],
    )


def _extract_contract_basic_info(resp: dict) -> Optional[dict]:
    data = resp.get("data")
    if isinstance(data, dict):
        basic = data.get("basicInfo")
        if isinstance(basic, dict):
            return basic
    return None



def _query_contract_no_via_tool465(
    platform_contract_id: str,
    dry_run: bool = False,
) -> Optional[str]:
    """
    方式二实现：工具465（合同ID互查）根据 platformContractId 查 contractNo。

    返回 contractNo 字符串，失败返回 None（不抛异常，供调用方降级）。
    """
    try:
        resp = run_tool(TOOL_TRANSFORM_CONTRACT_ID, {
            "originalContractIdStr":  None,
            "bizLine":                "3",
            "platformContractIdStr":  str(platform_contract_id),
        }, dry_run=dry_run)
    except DuError as e:
        print(f"  ⚠️  工具465查合同编号失败（降级到方式一）: {e}")
        return None

    if dry_run:
        return None

    # 工具465 返回结构：results 中 itemKey="合同编号" 的 value
    contract_no = get_result(resp, "合同编号") or get_result(resp, "contractNumber")
    if contract_no and str(contract_no) not in ("null", "None", ""):
        return str(contract_no)
    return None


def query_contract(
    partner_id: str,
    platform_contract_id: str = "",
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    查询供应商最新审核通过的合同。返回 {"contractNo": str, "contractId": str}

    查询策略：
      - 若传入 platform_contract_id（路径A 创建供应商后已知），优先用工具465（方式二）
        查 contractNo；成功则直接返回，失败则自动降级到方式一。
      - 方式一：Thrift getLastAuditPassContract(partnerId)（通用）。
    """
    # ── 方式二（优先）：工具465，仅当 platform_contract_id 有值时尝试 ──────────
    if platform_contract_id and platform_contract_id not in ("", "0", "None", "null"):
        print(f"\n📋 [P2] 查询合同（方式二：工具465 platformContractId={platform_contract_id}）...")
        contract_no = _query_contract_no_via_tool465(
            platform_contract_id=platform_contract_id,
            dry_run=dry_run,
        )
        if contract_no:
            print(f"✅ 合同查询成功（方式二）contractNo={contract_no}")
            return {"contractNo": contract_no, "contractId": platform_contract_id}
        print(f"  ⚠️  方式二未能取到 contractNo，降级到方式一（Thrift）...")

    # ── 方式一（通用）：Thrift getLastAuditPassContract(partnerId) ────────────
    print(f"\n📋 查询合同（方式一：Thrift partnerId={partner_id}）...")
    try:
        resp = _query_contracts_by_partner(partner_id=partner_id, swimlane=swimlane, dry_run=dry_run)
    except Exception as e:
        raise StepError("query_contract", str(e))

    if dry_run:
        return {"dry_run": True}

    success = resp.get("success")
    status  = resp.get("status")
    if success is False or (status is not None and int(status) != 0):
        raise StepError("query_contract", f"接口返回错误: {resp.get('message', str(resp)[:200])}")

    basic = _extract_contract_basic_info(resp)
    if not basic:
        print(f"⚠️  供应商 {partner_id} 暂无审核通过的合同")
        return {"contractNo": None, "contractId": None}

    contract_no = basic.get("contractNum")
    contract_id = basic.get("id") or basic.get("contractId")
    if not contract_no:
        print(f"⚠️  合同查询成功但未提取到 contractNo")
        return {"contractNo": None, "contractId": contract_id}

    print(f"✅ 合同查询成功（方式一）contractNo={contract_no}")
    return {"contractNo": contract_no, "contractId": contract_id}


# ════════════════════════════════════════════════════════════════════════════
# 六、新建合同
# ════════════════════════════════════════════════════════════════════════════

def create_contract(
    partner_id: str,
    contract_name: Optional[str] = None,
    price_mod: int = 8,
    contract_type: int = 2,
    is_audit: int = 1,
    is_overseas: bool = False,
    dry_run: bool = False,
) -> dict:
    """新建纸质合同（工具447）。返回 {"contractNo": str, "platformContractId": str}"""
    _name = contract_name or f"skill构造合同_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    try:
        resp = run_tool(TOOL_CREATE_CONTRACT, {
            "partnerId":    partner_id,
            "contractName": _name,
            "priceMod":     price_mod,
            "contractType": contract_type,
            "isAudit":      is_audit,
            "oversea":      is_overseas,
        }, dry_run=dry_run)
    except DuError as e:
        raise StepError("create_contract", str(e), detail=e.resp)

    if dry_run:
        return {"dry_run": True}

    try:
        check_ok(resp, "创建合同")
    except DuError as e:
        raise StepError("create_contract", str(e), detail=e.resp)

    raw_response = get_result(resp, "response")
    contract_no = None
    platform_contract_id = None

    if raw_response:
        try:
            biz = raw_response if isinstance(raw_response, dict) else json.loads(raw_response)
            biz_code = biz.get("code")
            if biz_code is not None and biz_code not in (0, 10000):
                raise StepError(
                    "create_contract",
                    f"业务错误 code={biz_code}: {biz.get('msg') or biz.get('message', str(biz)[:200])}",
                )
            data = biz.get("data")
            if isinstance(data, dict):
                contract_no = data.get("contractNum") or data.get("contractNo")
                platform_contract_id = data.get("platformContractId")
            elif isinstance(data, list) and data:
                contract_no = data[0].get("contractNum") or data[0].get("contractNo")
                platform_contract_id = data[0].get("platformContractId")
            if not contract_no:
                contract_no = biz.get("contractNum") or biz.get("contractNo")
        except StepError:
            raise
        except Exception:
            pass

    if not contract_no:
        raise StepError("create_contract", "合同创建成功但未能提取 contractNo，请查看原始响应")

    print(f"✅ 合同创建成功 contractNo={contract_no}")
    return {"contractNo": contract_no, "platformContractId": platform_contract_id}


# ════════════════════════════════════════════════════════════════════════════
# 七、创建房型
# ════════════════════════════════════════════════════════════════════════════

def create_room(
    partner_id: str,
    poi_id: str,
    room_name: Optional[str] = None,
    room_type: int = 0,
    is_overseas: bool = False,
    room_area: Optional[str] = None,
    capacity: Optional[int] = None,
    window_type: Optional[int] = None,
    floor_num: Optional[int] = None,
    dry_run: bool = False,
) -> dict:
    """创建房型（fd.banma HTTP）。返回 {"roomInfoId": str, "realRoomId": str, "roomName": str}"""
    from hotel_testdata_cli.scripts.utils import get_operator
    operator = get_operator()
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    _room_name = f"{room_name}{ts}" if room_name else f"{operator}{ts}"

    if not dry_run and not partner_id:
        raise ValueError("partnerId 必填")
    if not dry_run and not poi_id:
        raise ValueError("poiId 必填")

    param_json = {
        "poiId":      int(poi_id) if poi_id and str(poi_id).lstrip("-").isdigit() else 0,
        "partnerId":  int(partner_id) if partner_id and str(partner_id).lstrip("-").isdigit() else 0,
        "roomName":   _room_name,
        "isOverSea":  is_overseas,
        "roomType":   room_type,
        "roomArea":   room_area,
        "capacity":   capacity,
        "windowType": window_type,
        "floor":      floor_num,
    }
    payload = {
        "sceneId":   _FD_SCENE_ID,
        "actionId":  _FD_ACTION_ID,
        "misId":     _FD_MIS_ID,
        "paramJson": json.dumps(param_json, ensure_ascii=False),
    }

    if dry_run:
        print(f"\n[dry-run] 创建房型（fd.banma createRoomAction）")
        print(f"  POST {_FD_BANMA_URL}")
        print(f"  body: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        return {"dry_run": True}

    cmd = [
        "curl", "-s", "--location", "--request", "POST", _FD_BANMA_URL,
        "--header", "Content-Type: application/json",
        "--data-raw", json.dumps(payload, ensure_ascii=False),
    ]
    import subprocess as _sp
    r = _sp.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        outer = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise StepError("create_room", f"响应解析失败: {r.stdout[:300]}")

    outer_trace_id = outer.get("traceId", "")
    resp = outer
    try:
        inner_str = outer.get("data", {}).get(_FD_ACTION_ID)
        if inner_str:
            inner = json.loads(inner_str)
            if isinstance(inner, dict) and "traceId" not in inner:
                inner["traceId"] = outer_trace_id
            resp = inner
    except (json.JSONDecodeError, AttributeError):
        pass

    if not isinstance(resp, dict) or not resp.get("success"):
        msg = resp.get("message") or resp.get("error") or resp.get("resultMsg") or str(resp)[:200]
        trace_id = resp.get("traceId", "")
        raise StepError(
            "create_room",
            f"房型创建失败: {msg}" + (f" (traceId={trace_id})" if trace_id else ""),
        )

    room_info_id = resp.get("roomInfoId")
    real_room_id = resp.get("realRoomId")
    actual_name  = resp.get("roomName") or _room_name

    if not room_info_id:
        raise StepError("create_room", f"未获取到 roomInfoId，resp={json.dumps(resp)[:300]}")

    print(f"✅ 房型创建成功")
    print(f"   roomInfoId = {room_info_id}  ← 上单必填")
    print(f"   realRoomId = {real_room_id}")
    print(f"   roomName   = {actual_name}")
    return {"roomInfoId": room_info_id, "realRoomId": real_room_id, "roomName": actual_name}


# ════════════════════════════════════════════════════════════════════════════
# 八、等待供应商就绪
# ════════════════════════════════════════════════════════════════════════════

def wait_for_partner_ready(
    partner_id: str,
    max_retries: int = 8,
    interval_sec: int = 10,
    timeout_sec: Optional[int] = None,
) -> bool:
    """轮询检查供应商是否就绪（路径A新建后调用）。

    判断逻辑：查询合同接口能正常响应（success=True）即视为就绪，
    无论有无合同——有合同直接用，无合同后续会新建。
    接口报错（网络异常 / 供应商数据尚未同步）返回 False 继续等待。

    参数：
        timeout_sec  - 若传入，则用 ceil(timeout_sec / interval_sec) 覆盖 max_retries，
                       方便调用方直接指定最大等待秒数（如 120 = 2分钟）。
    """
    if timeout_sec is not None:
        import math
        max_retries = max(1, math.ceil(timeout_sec / interval_sec))

    def _check():
        try:
            r = _query_contracts_by_partner(partner_id=partner_id)
            # 接口能正常响应（无论有无合同）→ 供应商数据已同步，视为就绪
            if r.get("success") is True:
                return True
        except Exception:
            pass
        # 接口异常或尚未就绪，继续轮询
        return False

    return poll_until_ready(
        check_fn=_check,
        max_retries=max_retries,
        interval_sec=interval_sec,
        desc=f"等待供应商就绪（partnerId={partner_id}）",
    )


# ════════════════════════════════════════════════════════════════════════════
# 九、门店资质
# ════════════════════════════════════════════════════════════════════════════

def add_poi_qualification(
    poi_id: str,
    dry_run: bool = False,
) -> dict:
    """门店资质添加（工具476）。"""
    if not dry_run and not poi_id:
        raise ValueError("poiId 必填")
    try:
        resp = run_tool(TOOL_ADD_POI_QUAL, {"poiIds": poi_id}, dry_run=dry_run)
    except DuError as e:
        raise StepError("add_poi_qualification", str(e), detail=e.resp)
    if dry_run:
        return {"dry_run": True}
    try:
        check_ok(resp, "门店资质添加")
    except DuError as e:
        raise StepError("add_poi_qualification", str(e), detail=e.resp)
    print(f"✅ 门店资质添加成功 poiId={poi_id}")
    return {"poiId": poi_id}


def audit_poi_qualification(
    poi_id: str,
    audit_type: str = "供应商门店资质审核",
    audit_result: str = "通过",
    dry_run: bool = False,
) -> dict:
    """供应商门店资质审核（工具498）。"""
    if not dry_run and not poi_id:
        raise ValueError("poiId 必填")
    try:
        resp = run_tool(TOOL_AUDIT_POI_QUAL, {
            "poiId":       poi_id,
            "auditType":   audit_type,
            "auditResult": audit_result,
        }, dry_run=dry_run)
    except DuError as e:
        raise StepError("audit_poi_qualification", str(e), detail=e.resp)
    if dry_run:
        return {"dry_run": True}
    try:
        check_ok(resp, "门店资质审核")
    except DuError as e:
        raise StepError("audit_poi_qualification", str(e), detail=e.resp)
    print(f"✅ 门店资质审核成功 poiId={poi_id}")
    return {"poiId": poi_id}


# ════════════════════════════════════════════════════════════════════════════
# 十、价格模式切换 / ID互查（按需工具）
# ════════════════════════════════════════════════════════════════════════════

PRICE_MODE_BASE_PRICE       = "BASE_PRICE"
PRICE_MODE_SELLING          = "SELLING_PRICE"
PRICE_MODE_OVERSEAS_BASE    = "2"
PRICE_MODE_OVERSEAS_SELLING = "1"


def switch_price_mode(
    mode: str,
    is_overseas: bool = False,
    contract_id: Optional[str] = None,
    partner_id: Optional[str] = None,
    poi_id: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    if is_overseas:
        return run_tool(TOOL_SWITCH_PRICE_OVERSEAS, {
            "partnerId": partner_id,
            "poiId":     poi_id,
            "priceMode": mode,
        }, dry_run=dry_run)
    else:
        return run_tool(TOOL_SWITCH_PRICE_DOMESTIC, {
            "contractId":            contract_id,
            "prepayPriceChangeMode": mode,
        }, dry_run=dry_run)


def transform_customer_id(
    origin_customer_id_str: Optional[str] = None,
    platform_customer_id_str: Optional[str] = None,
    biz_line: str = "3",
    dry_run: bool = False,
) -> dict:
    return run_tool(TOOL_TRANSFORM_CUSTOMER_ID, {
        "originCustomerIdStr":   origin_customer_id_str,
        "bizLine":               biz_line,
        "platformCustomerIdStr": platform_customer_id_str,
    }, dry_run=dry_run)


def transform_contract_id(
    original_contract_id_str: Optional[str] = None,
    platform_contract_id_str: Optional[str] = None,
    biz_line: str = "3",
    dry_run: bool = False,
) -> dict:
    return run_tool(TOOL_TRANSFORM_CONTRACT_ID, {
        "originalContractIdStr":  original_contract_id_str,
        "bizLine":                biz_line,
        "platformContractIdStr":  platform_contract_id_str,
    }, dry_run=dry_run)


# ════════════════════════════════════════════════════════════════════════════
# 十一、数据池查询 / 存入（testdata-cli 封装）
# ════════════════════════════════════════════════════════════════════════════

import re as _re


def _ensure_testdata_cli() -> bool:
    """
    检测 testdata-cli 是否可用，不可用时自动安装。

    返回 True=可用（已安装或安装成功），False=安装失败。
    """
    # 先用 --version 探测是否已安装
    probe = subprocess.run(
        ["testdata-cli", "--version"],
        capture_output=True, text=True,
    )
    if probe.returncode == 0:
        return True

    print("   ⚙️  testdata-cli 未安装，正在自动安装...")
    print("   $ npm install -g @cscqa/testdata-cli --registry=http://r.npm.sankuai.com")
    result = subprocess.run(
        [
            "npm", "install", "-g", "@cscqa/testdata-cli",
            "--registry=http://r.npm.sankuai.com",
        ],
        capture_output=False,   # 直接输出到终端，让用户能看到进度
        text=True,
    )
    if result.returncode != 0:
        print("   ❌ testdata-cli 安装失败，请手动执行：")
        print("      npm install -g @cscqa/testdata-cli --registry=http://r.npm.sankuai.com")
        return False

    # 安装后再探测一次确认可用
    verify = subprocess.run(
        ["testdata-cli", "--version"],
        capture_output=True, text=True,
    )
    if verify.returncode == 0:
        print(f"   ✅ testdata-cli 安装成功（{verify.stdout.strip()}）")
        return True

    print("   ❌ testdata-cli 安装后仍无法调用，请检查 npm 全局 bin 是否在 PATH 中")
    return False


def query_data_pool(
    is_overseas: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    从数据池查询可用的供应商基础实体，两阶段策略：

    第一阶段：--mis-id <MIS> --occupier <MIS>，只查自己历史存入的数据；
    第二阶段：--mis-id <MIS>（不带 --occupier），查全量可用数据（count=0 时触发）。

    返回第一条符合条件的记录::

        {
            "partner_id":           str,   # bpCustomerId
            "poi_id":               str,   # poiIds 中第一个
            "contract_no":          str,   # contract
            "platform_contract_id": str,   # contractId
        }

    未命中时返回空 dict ``{}``。
    """
    from hotel_testdata_cli.scripts.utils import get_operator
    mis = get_operator()

    inland_tag = "境外供应商" if is_overseas else "境内供应商"
    tags_str = f"107={inland_tag}"

    def _build_cmd(with_occupier: bool) -> list:
        cmd = [
            "testdata-cli", "query-testdata", "query",
            "--query-tab", "1", "--biz-line", "20",
            "--tags", tags_str,
            "--mis-id", mis,
            "--limit", "5", "--pretty",
        ]
        if with_occupier:
            cmd += ["--occupier", mis]
        return cmd

    def _run_query(cmd: list) -> dict:
        """执行一次查询，返回第一条命中记录（dict），未命中返回 {}。"""
        print(f"   $ {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        raw = result.stdout.strip()
        if not raw:
            return {}

        lines = raw.splitlines()
        item: dict = {}
        in_record = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if _re.search(r'第\s*\d+\s*条', stripped):
                in_record = True
                item = {}
                continue
            if not in_record:
                continue
            m = _re.match(r'^(\w+)\s{2,}(.*)$', stripped)
            if m:
                item[m.group(1).strip()] = m.group(2).strip()
            elif stripped and not stripped.startswith("━"):
                m2 = _re.match(r'^(\w+)\s*$', stripped)
                if m2:
                    item[m2.group(1).strip()] = ""

        return item

    def _to_pool_result(item: dict) -> dict:
        partner_id = item.get("bpCustomerId", "")
        if not partner_id:
            return {}
        poi_raw   = item.get("poiIds", "")
        first_poi = next((p.strip() for p in poi_raw.split(",") if p.strip()), "")
        return {
            "partner_id":           partner_id,
            "poi_id":               first_poi,
            "contract_no":          item.get("contract", ""),
            "platform_contract_id": item.get("contractId", ""),
        }

    print(f"\n🔍 [数据池] 查询供应商（{inland_tag}）...")

    if dry_run:
        print(f"   $ {' '.join(_build_cmd(with_occupier=True))}")
        print("   [dry-run] 跳过数据池查询")
        return {}

    # ── 确保 testdata-cli 可用（不可用时自动安装）─────────────────────────
    if not _ensure_testdata_cli():
        print("   ⚠️  testdata-cli 不可用，跳过数据池查询")
        return {}

    try:
        # ── 第一阶段：查自己历史存入的数据（--occupier）────────────────────
        print("   [阶段一] 查自己历史数据（--occupier）...")
        item = _run_query(_build_cmd(with_occupier=True))
        pool_result = _to_pool_result(item)

        # ── 第二阶段：未命中时查全量（不带 --occupier）──────────────────────
        if not pool_result:
            print("   [阶段一] 未命中，[阶段二] 查全量数据...")
            item = _run_query(_build_cmd(with_occupier=False))
            pool_result = _to_pool_result(item)

        if not pool_result:
            print("   未命中（两阶段均无结果）")
            return {}

        print(f"   ✅ 数据池命中！")
        print(f"      partnerId           = {pool_result['partner_id']}")
        print(f"      poiId               = {pool_result['poi_id'] or '(无)'}")
        print(f"      contractNo          = {pool_result['contract_no'] or '(无)'}")
        print(f"      platformContractId  = {pool_result['platform_contract_id'] or '(无)'}")
        return pool_result

    except Exception as e:
        print(f"   ⚠️  数据池查询异常（跳过）: {e}")
        return {}


def save_to_pool(
    partner_id: str,
    platform_contract_id: str,
    poi_id: str,
    dry_run: bool = False,
) -> bool:
    """
    将新构造的供应商数据存入数据池（testdata-cli tag customer-contract-poi）。

    返回 True=成功，False=失败（不阻塞主流程）。
    """
    from hotel_testdata_cli.scripts.utils import get_operator
    mis = get_operator()

    cmd = [
        "testdata-cli", "tag",
        "--subject-type", "customer-contract-poi",
        "--customer-id",  str(partner_id),
        "--contract-id",  str(platform_contract_id),
        "--poi-id",       str(poi_id),
        "--biz-line",     "20",
        "--occupier",     mis,
    ]

    print(f"\n📦 [数据池] 存入供应商数据...")
    print(f"   partnerId           = {partner_id}")
    print(f"   platformContractId  = {platform_contract_id}")
    print(f"   poiId               = {poi_id}")
    print(f"   occupier            = {mis}")

    if dry_run:
        print(f"   [dry-run] 将执行命令：")
        print(f"   $ {' '.join(cmd)}")
        return True

    # ── 确保 testdata-cli 可用（不可用时自动安装）─────────────────────────
    if not _ensure_testdata_cli():
        print("   ⚠️  testdata-cli 不可用，跳过存入数据池")
        print(f"   如需手动执行，运行：")
        print(f"   $ {' '.join(cmd)}")
        return False

    try:
        result = subprocess.run(cmd, capture_output=False, text=True, timeout=60)
        if result.returncode == 0:
            print("   ✅ 存入数据池成功")
            return True
        else:
            print(f"   ❌ testdata-cli tag 执行失败（exit={result.returncode}）")
            return False
    except Exception as e:
        print(f"   ❌ 存入数据池异常: {e}")
        return False

