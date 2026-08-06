#!/usr/bin/env python3
"""
接口层：全日房/通用商品创建
协议：Thrift RPC
appKey：com.sankuai.hotel.biz.platform
service：com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade
method：batchCreateGoods
HTTP路由：/api/gw/v1/product/goods/batchCreateGoods

支持前端页面可传的所有参数，完整对应：
  - GoodsBaseInfoModel（商品基本信息）
  - RoomInfoModel（房型信息）
  - RpInfoModel（所有规则：取消/早餐/连住/预订/担保/礼包/限时售卖/专客专享/入住人群）
  - GoodsPriceUpdateModel（价格信息）

⚠️ batchCreateGoods 为异步接口，返回 uuid 后需轮询
   MeGoodsFacade#getProcessRate(partnerId, poiId, uuid) 或等待10~30秒后 queryGoodsInfo。
"""

import json
import sys
import os
import time
import datetime
import importlib.util as _ilu
from typing import Optional, List, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from scripts.runner import invoke, InvokeError  # noqa
from scripts.utils import get_operator, make_product_name  # noqa

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def _today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def _two_years_later() -> str:
    d = datetime.date.today()
    try:
        d = d.replace(year=d.year + 2)
    except ValueError:
        # 闰年 2 月 29 日特殊处理
        d = d.replace(year=d.year + 2, day=28)
    return d.strftime("%Y-%m-%d")


# ── 接口配置 ────────────────────────────────────────────────────────────────
APPKEY  = "com.sankuai.hotel.biz.platform"
SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade"
METHOD  = "batchCreateGoods"


# ════════════════════════════════════════════════════════════════════════════
# 参数强校验（能用代码表达的联动规则，在组装 RPC 之前执行）
# 对应文档：references/playbook/{fullday,hourly}.md 中的联动约束节
# ════════════════════════════════════════════════════════════════════════════

def validate(params: dict) -> None:
    """
    高级 API（call() 函数）的参数联动强校验。
    接收 snake_case 扁平参数字典，校验失败时直接抛出 ValueError，阻断执行。

    ⚠️ 本函数仅由 call() 调用，不用于 call_raw() 路径（factory 层走 validate_constraints）。

    覆盖规则（来源：playbook 文档中"联动约束"节）：
      V1  商品名称不能含"测试"字样
      V2  钟点房必须传 type_limit_value（1~23）
      V3  钟点房不支持早餐规则
      V4  钟点房不支持连住规则
      V5  钟点房不支持 paid-cancel（由 factory 层拦截，此处兜底）
      V6  payment_type=2（非担保）时 arrival_hour 必填
      V7  连住：min/max 范围约束，且 max >= min
      V8  价格必须为正数
      V9  接待时间：钟点房必填，且 start < end（字符串比较，格式 HH:MM）
    """
    errors = []
    goods_type = params.get("goods_type", 1)
    payment_type = params.get("payment_type", 0)
    goods_name = params.get("goods_name", "")

    # V1：商品名称禁词
    if goods_name and "测试" in goods_name:
        errors.append("V1: goods_name 不能包含'测试'字样（后端拦截）")

    # V2：钟点房必须传可住时长
    type_limit_value = params.get("type_limit_value")
    if goods_type == 2:
        if type_limit_value is None:
            errors.append("V2: 钟点房必须传 type_limit_value（--stay-hours）")
        elif not (1 <= int(type_limit_value) <= 23):
            errors.append(f"V2: type_limit_value={type_limit_value} 超出合法范围 1~23")

    # V3：钟点房不支持早餐
    if goods_type == 2 and params.get("breakfast_num", 0) > 0:
        errors.append("V3: 钟点房不支持早餐规则（breakfast_num 应为 0）")

    # V4：钟点房不支持连住
    if goods_type == 2 and (
        params.get("serial_checkin_min", 0) > 0
        or params.get("serial_checkin_max", 0) > 0
    ):
        errors.append("V4: 钟点房不支持连住规则（serial_checkin_min/max 应为 0）")

    # V5：钟点房不支持 paid-cancel（pay_cancel_period_models 不为空视为 paid-cancel）
    if goods_type == 2 and params.get("pay_cancel_period_models"):
        errors.append("V5: 钟点房不支持收费取消（paid-cancel）")

    # V6：现付非担保必须有 arrival_hour
    if payment_type == 2 and not params.get("arrival_hour"):
        errors.append("V6: payment_type=2（现付非担保）必须传 arrival_hour（如 '14:00:00'）")

    # V7：连住规则范围约束
    serial_min = params.get("serial_checkin_min", 0)
    serial_max = params.get("serial_checkin_max", 0)
    if serial_min != 0 and not (2 <= serial_min <= 30):
        errors.append(f"V7: serial_checkin_min={serial_min} 非法，合法值为 0 或 2~30")
    if serial_max != 0 and not (2 <= serial_max <= 30):
        errors.append(f"V7: serial_checkin_max={serial_max} 非法，合法值为 0 或 2~30")
    if serial_min > 0 and serial_max > 0 and serial_max < serial_min:
        errors.append(f"V7: serial_checkin_max({serial_max}) 不能小于 serial_checkin_min({serial_min})")

    # V8：价格必须为正数
    price = params.get("price", 200.0)
    if price is not None and float(price) <= 0:
        errors.append(f"V8: price={price} 非法，价格必须为正数（单位：元）")

    # V9：钟点房接待时间校验
    if goods_type == 2:
        start = params.get("receive_time_start", "08:00")
        end = params.get("receive_time_end", "22:00")
        if start and end and start >= end:
            errors.append(f"V9: receive_time_start({start}) 必须早于 receive_time_end({end})")

    if errors:
        msg = "\n".join(f"  {e}" for e in errors)
        raise ValueError(f"参数校验失败（共 {len(errors)} 项），请修正后重试：\n{msg}")


def _validate_raw(params: dict) -> None:
    """
    call_raw() 路径（factory 层）的参数联动强校验。
    接收完整的嵌套 dict（CreateOrUpdateGoodsParam 结构），校验失败时抛出 ValueError。

    此函数作为 factory 层 validate_constraints 的接口层兜底，
    两层校验规则对齐，防止 factory 层遗漏的参数错误到达 RPC 层。

    覆盖规则：
      R1  商品名称不能含"测试"字样
      R2  钟点房必须传 typeLimitValue（1~23）
      R3  钟点房不支持早餐（rpBreakFastModel 必须为 null）
      R4  现付非担保（paymentType=2）时 arrivalHour 必须在 rpGuaranteeModel 中设置
      R5  售价（salePrice）必须为正数（单位：分）
    """
    def _get(obj, *path):
        """安全取嵌套值。"""
        cur = obj
        for k in path:
            if isinstance(cur, list):
                try:
                    cur = cur[int(k)]
                except (IndexError, ValueError, TypeError):
                    return None
            elif isinstance(cur, dict):
                cur = cur.get(k)
            else:
                return None
        return cur

    errors = []
    gd = _get(params, "goodsDetailList", "0") or {}
    base = gd.get("goodsBaseInfo") or {}
    rp = gd.get("rpInfo") or {}
    price_info = gd.get("priceInfo") or {}

    goods_type   = base.get("goodsType", 1)
    payment_type = base.get("paymentType", 0)
    goods_name   = base.get("goodsName", "")

    # R1：商品名称禁词
    if goods_name and "测试" in goods_name:
        errors.append(
            "R1: goodsName 不能包含'测试'字样（后端拦截）\n"
            "   修复：--set goodsDetailList.0.goodsBaseInfo.goodsName=\"换个商品名\""
        )

    # R2：钟点房必须传 typeLimitValue（1~12）
    if goods_type == 2:
        type_limit = base.get("typeLimitValue")
        if type_limit is None:
            errors.append(
                "R2: 钟点房必须传 typeLimitValue（可住时长，小时）\n"
                "   修复：--set goodsDetailList.0.goodsBaseInfo.typeLimitValue=4"
            )
        else:
            try:
                tl = int(type_limit)
                if not (1 <= tl <= 23):
                    errors.append(
                        f"R2: typeLimitValue={tl} 超出范围（必须 1~23）\n"
                        f"   修复：--set goodsDetailList.0.goodsBaseInfo.typeLimitValue=4"
                    )
            except (ValueError, TypeError):
                errors.append(
                    f"R2: typeLimitValue={type_limit} 不是整数\n"
                    f"   修复：--set goodsDetailList.0.goodsBaseInfo.typeLimitValue=4"
                )

    # R3：钟点房不支持早餐（rpBreakFastModel 必须为 null）
    if goods_type == 2 and rp.get("rpBreakFastModel") is not None:
        errors.append(
            "R3: 钟点房不支持 rpBreakFastModel，必须为 null\n"
            "   修复：--set goodsDetailList.0.rpInfo.rpBreakFastModel=null"
        )

    # R4：现付非担保时 arrivalHour 必填
    if payment_type == 2:
        guarantee_model = (rp.get("rpGuaranteeModel") or {}).get("normalRule") or {}
        if not guarantee_model.get("arrivalHour"):
            errors.append(
                "R4: paymentType=2（现付非担保）时 arrivalHour 必填\n"
                "   修复：--set goodsDetailList.0.rpInfo.rpGuaranteeModel.normalRule.arrivalHour=\"14:00:00\""
            )

    # R5：售价必须为正数（单位：分）
    sale_price_str = _get(
        price_info, "unifiedDatePriceInfos", "weekPriceInfos", "0", "priceInfo", "salePrice"
    )
    if sale_price_str is not None:
        try:
            sp = int(sale_price_str)
            if sp <= 0:
                errors.append(
                    f"R5: salePrice={sp} 非法，必须 > 0（单位：分，200元=20000）\n"
                    f"   修复：--set goodsDetailList.0.priceInfo.unifiedDatePriceInfos"
                    f".weekPriceInfos.0.priceInfo.salePrice=20000"
                )
        except (ValueError, TypeError):
            pass

    if errors:
        msg = "\n".join(f"  {e}" for e in errors)
        raise ValueError(f"接口层参数校验失败（共 {len(errors)} 项），请修正后重试：\n{msg}")


# ════════════════════════════════════════════════════════════════════════════
# 规则构建辅助函数（对应前端 RpModel<T> 结构）
# ════════════════════════════════════════════════════════════════════════════

def _wrap_rp_model(normal_rule: dict, weekend_rule: dict = None, special_rules: list = None) -> dict:
    """将规则包装为 RpModel<T> 结构。"""
    result = {"normalRule": normal_rule, "updateType": 0}
    if weekend_rule is not None:
        result["weekendRule"] = weekend_rule
    if special_rules is not None:
        result["specialRules"] = special_rules
    return result


def build_rp_base(
    is_auto_relay: int = 0,
    auto_relay_days: int = None,
    rp_name: str = None,
    rp_custom_name: str = None,
    custom_name_type: int = 0,
    sale_strategy: List[int] = None,
) -> dict:
    """
    构建 RpBaseModel（基本规则）。

    参数：
        is_auto_relay    - 0=自动延期（默认） 1=不自动延期
        auto_relay_days  - 自动延期天数（is_auto_relay=0 时有效）
        rp_name          - 产品规则名称（如「含单早-不可取消-标准价111」），真实请求必传
        rp_custom_name   - 产品备注文字（追加在 rpName 后，不能含"测试"字样）
        custom_name_type - 0=未自定义 1=自定义
        sale_strategy    - 售卖渠道，[0]=全日房，[1]=套餐；默认 [0,1]
    """
    model = {
        "isAutoRelay": is_auto_relay,
        "customNameType": custom_name_type,
        # saleStrategyInfo 必传，默认 [0,1]（全日房+套餐均可售）
        "saleStrategyInfo": {
            "blackWhiteStatus": 0,
            "saleStrategy": sale_strategy if sale_strategy is not None else [0, 1],
        },
    }
    if auto_relay_days is not None:
        model["autoRelayDays"] = auto_relay_days
    if rp_name is not None:
        model["rpName"] = rp_name
    if rp_custom_name is not None:
        model["rpCustomName"] = rp_custom_name
    return model


def build_rp_cancel(
    cancel_item_type: int,
    move_up_cancel_days: int = None,
    move_up_cancel_hour: str = None,
    pay_cancel_period_models: List[dict] = None,
    effective_times: List[dict] = None,
) -> dict:
    """
    构建取消规则 RpModel<RpCancelModel>。

    参数：
        cancel_item_type        - 0=不可取消 1=可取消
        move_up_cancel_days     - 免费取消提前天数（0=当天）
        move_up_cancel_hour     - 免费取消提前时间，格式 "18:00:00"
        pay_cancel_period_models - 付费取消模型列表，每项：
            {"advanceDays": 0, "advanceHour": "14:00:00", "penaltyRate": 20}
        effective_times         - 特殊日期生效时间（仅 specialRules 用）
    """
    normal_rule = {"cancelItemType": cancel_item_type}
    if move_up_cancel_days is not None:
        normal_rule["moveUpCancelDays"] = move_up_cancel_days
    if move_up_cancel_hour is not None:
        normal_rule["moveUpCancelHour"] = move_up_cancel_hour
    if pay_cancel_period_models:
        normal_rule["payCancelPeriodModels"] = pay_cancel_period_models
    if effective_times:
        normal_rule["effectiveTimes"] = effective_times
    return _wrap_rp_model(normal_rule)


def build_rp_breakfast(num: int, weekend_num: int = None) -> dict:
    """
    构建早餐规则 RpModel<RpFoodModel>。

    参数：
        num         - 早餐份数（0=无 1=单份 2=双份）
        weekend_num - 周末早餐份数（None=不区分平日周末）
    """
    normal_rule = {"num": num}
    weekend_rule = {"num": weekend_num} if weekend_num is not None else None
    return _wrap_rp_model(normal_rule, weekend_rule)


def build_rp_hourly_use(
    receive_time_start: str,
    receive_time_end: str,
) -> dict:
    """
    构建钟点房入住规则 RpModel<RpHourlyRoomUseModel>。

    参数：
        receive_time_start - 开始接待时间，格式 "08:00"；24小时传 "00:00"
        receive_time_end   - 结束接待时间，格式 "22:00"；24小时传 "23:59"
    """
    normal_rule = {
        "receiveTimeStart": receive_time_start,
        "receiveTimeEnd": receive_time_end,
    }
    return _wrap_rp_model(normal_rule)


def build_rp_early_booking(
    latest_booking_days: int = -1,
    earliest_booking_days: int = -1,
    is_daybreak_booking: int = 1,
) -> dict:
    """
    构建预订规则 RpModel<RpEarlyBookingModel>。

    参数：
        latest_booking_days   - 最晚预订天数（至少提前N天，-1=未设置）
        earliest_booking_days - 最早预订天数（至多提前N天，-1=未设置）
        is_daybreak_booking   - 是否支持0点后预订当天：1=支持（默认）
    """
    normal_rule = {
        "latestBookingDays": latest_booking_days,
        "earliestBookingDays": earliest_booking_days,
        "isDaybreakBooking": is_daybreak_booking,
    }
    return _wrap_rp_model(normal_rule)


def build_rp_guarantee(
    is_guarantee: int,
    guarantee_type: int,
    arrival_hour: str = None,
) -> dict:
    """
    构建担保规则 RpModel<RpGuaranteeModel>（现付产品必填）。

    参数：
        is_guarantee   - 0=非担保 1=担保（现付担保传1）
        guarantee_type - 1=首晚担保 2=整单担保
        arrival_hour   - 到店时间，格式 "14:00:00"（现付非担保必填）
    """
    normal_rule = {
        "isGuarantee": is_guarantee,
        "guaranteeType": guarantee_type,
    }
    if arrival_hour is not None:
        normal_rule["arrivalHour"] = arrival_hour
    return _wrap_rp_model(normal_rule)


def build_rp_serial(
    serial_checkin_min: int = 0,
    serial_checkin_max: int = 0,
) -> dict:
    """
    构建连住规则 RpModel<RpSerialModel>。

    参数：
        serial_checkin_min - 最小连住天数（0=不限制）
        serial_checkin_max - 最大连住天数（0=不限制）
    """
    normal_rule = {
        "serialCheckinMin": serial_checkin_min,
        "serialCheckinMax": serial_checkin_max,
    }
    return _wrap_rp_model(normal_rule)


def build_rp_service(service_tmpl_ids: List[int]) -> dict:
    """
    构建礼包规则 RpModel<RpServiceModel>。

    参数：
        service_tmpl_ids - 礼包模板ID列表，如 [12345, 67890]
    """
    normal_rule = {
        "serviceModels": [{"serviceTmplId": tid} for tid in service_tmpl_ids]
    }
    return _wrap_rp_model(normal_rule)


def build_rp_display(
    hotel_member: int = 0,
    total_gmv: int = 0,
    city: int = 0,
    stu_special: int = 0,
    distance_range: int = 0,
    risk_control: int = 0,
    employee_exclusive: int = 0,
    flagship_new_user: int = 0,
    business_travel: int = 0,
    length_of_stay: dict = None,
    address_multi_restriction: dict = None,
    effective_time: dict = None,
) -> dict:
    """
    构建专客专享规则 RpModel<RpDisplayModel>。

    参数（均为 0=不限制）：
        hotel_member        - 会员可见性：0全部 1一档会员 2二档会员
        total_gmv           - GMV可见性：0全部 1一档GMV 2二档GMV
        city                - 城市可见性：0全城市 1下单在poi城市 2下单不在poi城市
        stu_special         - 学生专享：0全部 1仅学生
        distance_range      - 附近专享：0全部 1酒店3公里内
        risk_control        - 风控：0全部 1黑名单不可见
        employee_exclusive  - 员工专享：0全部 1仅美团员工
        length_of_stay      - 连住可见：{"lengthOfStayType":0,"minSerialDays":2,"maxSerialDays":7}
        address_multi_restriction - 地址规则：{"addressMultiRestrictionType":0,"addressModelList":[]}
        effective_time      - 生效时间：{"effectiveTimeType":0,"effectiveTimeModelList":[]}
    """
    normal_rule = {
        "hotelMember": hotel_member,
        "totalGmv": total_gmv,
        "city": city,
        "stuSpecial": stu_special,
        "distanceRange": distance_range,
        "riskControl": risk_control,
        "flagshipNewUser": flagship_new_user,
        "businessTravel": business_travel,
        "employeeExclusive": employee_exclusive,
    }
    if length_of_stay is not None:
        normal_rule["lengthOfStay"] = length_of_stay
    if address_multi_restriction is not None:
        normal_rule["addressMultiRestriction"] = address_multi_restriction
    if effective_time is not None:
        normal_rule["effectiveTime"] = effective_time
    return _wrap_rp_model(normal_rule)


def build_rp_time_limit_sale(
    enable_booking_type: int,
    time_limit_sale_models: List[dict],
) -> dict:
    """
    构建限时售卖规则 RpModel<RpTimeLimitSaleModel>。

    参数：
        enable_booking_type    - 0=未设置日期全天售卖 1=未设置日期全天不售卖
        time_limit_sale_models - 限时售卖规则列表，每项：
            {
                "date": {"startDate": "2024-04-01", "endDate": "2024-04-30"},
                "normalRule": [{"enableBookingTimeStart": "06:00", "enableBookingTimeEnd": "23:59"}],
                "weekendRule": null
            }
    """
    normal_rule = {
        "enableBookingType": enable_booking_type,
        "timeLimitSaleModels": time_limit_sale_models,
    }
    return _wrap_rp_model(normal_rule)


def build_rp_booking(
    max_adult_admissibility: int = None,
    target_user: dict = None,
) -> dict:
    """
    构建入住规则 RpModel<RpBookingModel>（境外BD/商家传）。

    参数：
        max_adult_admissibility - 最大可入住成人数
        target_user - 适用人群：
            {"targetUserRule": 0, "targetUserRestrictionList": [...]}
            targetUserRule: 0=不限制 1=适用 2=不适用
    """
    normal_rule = {}
    if max_adult_admissibility is not None:
        normal_rule["maxAdultAdmissibility"] = max_adult_admissibility
    if target_user is not None:
        normal_rule["targetUser"] = target_user
    return _wrap_rp_model(normal_rule)


# ════════════════════════════════════════════════════════════════════════════
# 名称自动拼接辅助函数
# ════════════════════════════════════════════════════════════════════════════

def _breakfast_label(num: int) -> str:
    """
    根据早餐份数返回早餐描述文字。
      0 → 不含早
      1 → 含单早
      2 → 含双早
      5 → 含五早
      其他 → 含N早
    """
    mapping = {0: "不含早", 1: "含单早", 2: "含双早", 5: "含五早"}
    return mapping.get(num, f"含{num}早")


def _cancel_label(
    cancel_item_type: int,
    move_up_cancel_days: int = None,
    move_up_cancel_hour: str = None,
    pay_cancel_period_models: list = None,
) -> str:
    """
    根据取消规则参数计算取消规则描述。

    cancelItemType=0 → 不可取消
    cancelItemType=1 →
      moveUpCancelDays=0 → 入住当天{HH:MM}前免费取消
      moveUpCancelDays>0 → 入住前{N}天{HH:MM}前免费取消
      若有 payCancelPeriodModels → 追加"-收费取消"
    """
    if cancel_item_type == 0:
        return "不可取消"

    days = move_up_cancel_days if move_up_cancel_days is not None else 0
    hour_str = move_up_cancel_hour or ""
    # 只取 HH:MM 部分（去掉秒）
    hm = ":".join(hour_str.split(":")[:2]) if hour_str else ""

    if days == 0:
        base = f"入住当天{hm}前免费取消" if hm else "入住当天免费取消"
    else:
        base = f"入住前{days}天{hm}前免费取消" if hm else f"入住前{days}天免费取消"

    if pay_cancel_period_models:
        base += "-收费取消"

    return base


def _build_names_from_params(
    room_name: str,
    breakfast_num: int = 0,
    cancel_item_type: int = 0,
    move_up_cancel_days: int = None,
    move_up_cancel_hour: str = None,
    pay_cancel_period_models: list = None,
    rp_custom_name: str = None,
) -> tuple:
    """
    根据早餐/取消规则参数，自动拼接：
      rpCustomName → 标准价{时间戳}（不传时自动生成，不含"测试"）
      rpName       → {早餐描述}-{取消规则描述}-{rpCustomName}
      goodsName    → {roomName}-{rpName}

    规则：
      goodsName = roomName + "-" + rpName
      rpName    = 早餐描述 + "-" + 取消规则描述 + "-" + rpCustomName
      早餐描述：0=不含早, 1=含单早, 2=含双早, 5=含五早, 其他=含N早
      取消规则描述：
        cancelItemType=0 → 不可取消
        cancelItemType=1, moveUpCancelDays=0 → 入住当天HH:MM前免费取消
        cancelItemType=1, moveUpCancelDays>0 → 入住前N天HH:MM前免费取消
        含 payCancelPeriodModels → 追加-收费取消

    返回 (goodsName, rpName, rpCustomName)
    """
    import time as _time
    if rp_custom_name is None:
        rp_custom_name = f"标准价{int(_time.time())}"

    breakfast_part = _breakfast_label(breakfast_num)
    cancel_part = _cancel_label(
        cancel_item_type=cancel_item_type,
        move_up_cancel_days=move_up_cancel_days,
        move_up_cancel_hour=move_up_cancel_hour,
        pay_cancel_period_models=pay_cancel_period_models,
    )

    rp_name = f"{breakfast_part}-{cancel_part}-{rp_custom_name}"
    goods_name = f"{room_name}-{rp_name}"

    return goods_name, rp_name, rp_custom_name


# ════════════════════════════════════════════════════════════════════════════
# 主调用函数
# ════════════════════════════════════════════════════════════════════════════

def call(
    # ── 必填基础 ────────────────────────────────────────────────────────
    partner_id: str,
    poi_id: str,
    room_id: int,
    room_name: str,
    room_capacity: int = 0,       # 已废弃：后端从逻辑房型继承，固定传 0，此参数无实际效果
    # ── 商品基本信息 ─────────────────────────────────────────────────────
    goods_type: int = 1,              # 1=全日房 2=钟点房
    goods_name: str = "",             # 不能含"测试"字样，默认自动生成
    payment_type: int = 0,            # 0=预付 1=现付担保 2=现付非担保
    sell_channel: int = None,         # None/0=全平台 9=仅美团 10=仅点评
    channel_nos: Dict[str, List[str]] = None,  # 渠道号，如 {"4": ["差旅企业号"]}
    single_channel_reason: str = None,
    price_same_tag: int = None,       # 境外多人多价：0=多价 1=同价
    type_limit_value: int = None,     # 钟点房住时长（小时，钟点房必填）
    max_adult_admissibility: int = None,  # 最大可入住人数（goodsBaseInfo层）
    contract_no: str = None,          # 合同编号
    super_deal_re_sale_status: int = None,  # 是否转售 0不转售 1转售
    # ── 价格信息 ─────────────────────────────────────────────────────────
    price: float = 200.0,             # 价格（元，会自动转换为分）
    price_record_way: int = 1,        # 1=卖价 2=底价
    ratio_new: str = "1100",          # 佣金率，千分比（1100=11%）
    ratio_type: int = 1,              # 佣金率类型
    # ── 基本规则 ─────────────────────────────────────────────────────────
    is_auto_relay: int = 0,           # 0=自动延期 1=不自动延期
    auto_relay_days: int = None,
    rp_custom_name: str = None,       # 产品备注
    custom_name_type: int = 0,        # 0=未自定义 1=自定义
    sale_strategy: List[int] = None,  # [0]=全日房 [1]=套餐
    # ── 取消规则 ─────────────────────────────────────────────────────────
    cancel_item_type: int = None,     # None=不设置 0=不可取消 1=可取消
    move_up_cancel_days: int = None,
    move_up_cancel_hour: str = None,
    pay_cancel_period_models: List[dict] = None,
    # ── 早餐规则（全日房）────────────────────────────────────────────────
    breakfast_num: int = 0,           # 0=不含早 1=含单早 2=含双早 5=含五早（其他正整数均支持）
    breakfast_weekend_num: int = None,
    # ── 钟点房入住规则 ────────────────────────────────────────────────────
    receive_time_start: str = "08:00",
    receive_time_end: str = "22:00",
    # ── 预订规则 ─────────────────────────────────────────────────────────
    latest_booking_days: int = None,  # 至少提前N天（None=不设置）
    earliest_booking_days: int = None,  # 至多提前N天（None=不设置）
    # ── 担保规则（现付）──────────────────────────────────────────────────
    is_guarantee: int = None,         # None=不设置 0=非担保 1=担保
    guarantee_type: int = None,       # 1=首晚 2=整单
    arrival_hour: str = None,         # 到店时间，格式"14:00:00"（现付非担保）
    # ── 连住规则 ─────────────────────────────────────────────────────────
    serial_checkin_min: int = 0,      # 最小连住（0=不限）
    serial_checkin_max: int = 0,      # 最大连住（0=不限）
    # ── 礼包规则 ─────────────────────────────────────────────────────────
    service_tmpl_ids: List[int] = None,  # 礼包模板ID列表
    # ── 专客专享规则 ─────────────────────────────────────────────────────
    display_hotel_member: int = 0,
    display_total_gmv: int = 0,
    display_city: int = 0,
    display_stu_special: int = 0,
    display_distance_range: int = 0,
    display_risk_control: int = 0,
    display_employee_exclusive: int = 0,
    display_length_of_stay: dict = None,
    display_address_restriction: dict = None,
    display_effective_time: dict = None,
    # ── 限时售卖 ─────────────────────────────────────────────────────────
    time_limit_sale_enable_booking_type: int = None,  # None=不设置
    time_limit_sale_models: List[dict] = None,
    # ── 入住规则（境外）──────────────────────────────────────────────────
    booking_max_adult: int = None,
    booking_target_user: dict = None,
    # ── 执行控制 ─────────────────────────────────────────────────────────
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    创建酒店商品（全日房/钟点房），直调研发级 MeGoodsFacade#batchCreateGoods。

    前端页面可传的所有参数均在此函数中得到支持。

    必填参数：
        partner_id      - 供应商ID
        poi_id          - 门店ID（mtPoiId）
        room_id         - 上单房型ID（逻辑房型ID）
        room_name       - 上单房型名称
        room_capacity   - 房型可容纳人数

    返回：
        dict，其中 data 字段为 uuid（异步任务ID）
        后续可用 getProcessRate(partnerId, poiId, uuid) 轮询进度
    """
    # ── 参数强校验（联动规则兜底，dry_run 下也执行） ────────────────────────
    validate({
        "goods_type": goods_type,
        "goods_name": goods_name,
        "payment_type": payment_type,
        "arrival_hour": arrival_hour,
        "type_limit_value": type_limit_value,
        "breakfast_num": breakfast_num,
        "serial_checkin_min": serial_checkin_min,
        "serial_checkin_max": serial_checkin_max,
        "pay_cancel_period_models": pay_cancel_period_models,
        "price": price,
        "receive_time_start": receive_time_start,
        "receive_time_end": receive_time_end,
    })

    # ── 商品名称 / rpName / rpCustomName 自动拼接 ─────────────────────────
    # 规则：goodsName = roomName-rpName，rpName = 早餐描述-取消规则描述-rpCustomName
    # 用户若显式传入 goods_name，则以传入值为准（跳过自动拼接）
    _auto_rp_name = None
    _auto_rp_custom_name = None
    if not goods_name:
        auto_goods_name, _auto_rp_name, _auto_rp_custom_name = _build_names_from_params(
            room_name=room_name,
            breakfast_num=breakfast_num if breakfast_num is not None else 0,
            cancel_item_type=cancel_item_type if cancel_item_type is not None else 0,
            move_up_cancel_days=move_up_cancel_days,
            move_up_cancel_hour=move_up_cancel_hour,
            pay_cancel_period_models=pay_cancel_period_models,
            rp_custom_name=rp_custom_name,
        )
        goods_name = auto_goods_name
        # rp_custom_name 同步为自动生成的值（供后续 build_rp_base 使用）
        rp_custom_name = _auto_rp_custom_name

    # ── 构建 GoodsBaseInfoModel ───────────────────────────────────────────
    goods_base_info: Dict[str, Any] = {
        "goodsName": goods_name,
        "goodsType": int(goods_type),
        "paymentType": int(payment_type),
        # 以下字段后端必须有值，使用默认值兜底
        "priceChangeMode": 8,        # 8=预付
        "pricingPower": 0,
        "priceRecodeWay": 1,
        "switchStatus": 0,
        "expectPriceChangeMode": 8,
        "deductionAudit": False,
        "superDealReSale": False,
        "canAdjustPrice": False,
        "poiId": int(poi_id),
        "partnerId": int(partner_id),
    }
    if sell_channel is not None:
        goods_base_info["sellChannel"] = int(sell_channel)
    # channelNos 必传（不传后端报"参数错误"），默认传分销渠道 {"8":["001","002"]}
    goods_base_info["channelNos"] = channel_nos if channel_nos is not None else {"8": ["001", "002"]}
    goods_base_info["singleChannelReason"] = single_channel_reason or ""
    if price_same_tag is not None:
        goods_base_info["priceSameTag"] = int(price_same_tag)
    if type_limit_value is not None:
        goods_base_info["typeLimitValue"] = int(type_limit_value)
    if max_adult_admissibility is not None:
        goods_base_info["maxAdultAdmissibility"] = int(max_adult_admissibility)
    if contract_no is not None:
        goods_base_info["contractNo"] = contract_no
    if super_deal_re_sale_status is not None:
        goods_base_info["superDealReSaleStatus"] = int(super_deal_re_sale_status)

    # ── 构建 RoomInfoModel ────────────────────────────────────────────────
    room_info = {
        "roomId": int(room_id),
        "roomName": room_name,
        "capacity": 0,  # 后端从逻辑房型继承，此处固定传 0
    }

    # ── 构建 RpInfoModel ─────────────────────────────────────────────────
    rp_info: Dict[str, Any] = {}

    # 基本规则（始终设置）
    # rp_name / rp_custom_name 由自动拼接逻辑生成（goods_name 未传时）
    # 若用户显式传入 goods_name，则 _auto_rp_name/_auto_rp_custom_name 为 None，
    # 此时 rp_custom_name 使用用户传入值（或时间戳兜底）
    import time as _time
    _rp_custom = rp_custom_name if rp_custom_name is not None else f"标准价{int(_time.time())}"
    _rp_name_final = _auto_rp_name  # 自动生成时有值；用户传了 goods_name 时为 None
    rp_info["rpBaseModel"] = build_rp_base(
        is_auto_relay=is_auto_relay,
        auto_relay_days=auto_relay_days,
        rp_name=_rp_name_final,
        rp_custom_name=_rp_custom,
        custom_name_type=custom_name_type if custom_name_type else 1,
        sale_strategy=sale_strategy,
    )

    # 取消规则（始终传递，默认不可取消）
    rp_info["rpCancelModel"] = build_rp_cancel(
        cancel_item_type=cancel_item_type if cancel_item_type is not None else 0,
        move_up_cancel_days=move_up_cancel_days,
        move_up_cancel_hour=move_up_cancel_hour,
        pay_cancel_period_models=pay_cancel_period_models,
    )

    # 早餐规则（全日房必传，不传会触发后端系统内部错误；默认 num=0 表示无早餐）
    if goods_type == 1:
        rp_info["rpBreakFastModel"] = build_rp_breakfast(
            num=breakfast_num if breakfast_num is not None else 0,
            weekend_num=breakfast_weekend_num,
        )

    # 钟点房入住规则（仅钟点房必填）
    if goods_type == 2:
        rp_info["rpHourlyRoomUseModel"] = build_rp_hourly_use(
            receive_time_start=receive_time_start,
            receive_time_end=receive_time_end,
        )

    # 预订规则（始终传递默认值）
    rp_info["rpEarlyBookingModel"] = build_rp_early_booking(
        latest_booking_days=latest_booking_days if latest_booking_days is not None else -1,
        earliest_booking_days=earliest_booking_days if earliest_booking_days is not None else -1,
    )

    # 担保规则（现付产品必填）
    if is_guarantee is not None:
        rp_info["rpGuaranteeModel"] = build_rp_guarantee(
            is_guarantee=is_guarantee,
            guarantee_type=guarantee_type or 2,
            arrival_hour=arrival_hour,
        )
    elif payment_type == 1:
        # 现付担保：自动设置整单担保
        rp_info["rpGuaranteeModel"] = build_rp_guarantee(
            is_guarantee=1,
            guarantee_type=2,
        )
    elif payment_type == 2:
        # 现付非担保：整单担保 + 到店时间
        rp_info["rpGuaranteeModel"] = build_rp_guarantee(
            is_guarantee=0,
            guarantee_type=2,
            arrival_hour=arrival_hour or "14:00:00",
        )

    # 连住规则（始终传递默认值）
    rp_info["rpSerialModel"] = build_rp_serial(
        serial_checkin_min=serial_checkin_min,
        serial_checkin_max=serial_checkin_max,
    )

    # 礼包规则
    if service_tmpl_ids:
        rp_info["rpServiceModel"] = build_rp_service(service_tmpl_ids)

    # 专客专享（始终传递，全为0即不限制）
    rp_info["rpDisplayModel"] = build_rp_display(
        hotel_member=display_hotel_member,
        total_gmv=display_total_gmv,
        city=display_city,
        stu_special=display_stu_special,
        distance_range=display_distance_range,
        risk_control=display_risk_control,
        employee_exclusive=display_employee_exclusive,
        length_of_stay=display_length_of_stay,
        address_multi_restriction=display_address_restriction,
        effective_time=display_effective_time,
    )

    # 限时售卖
    if time_limit_sale_enable_booking_type is not None and time_limit_sale_models:
        rp_info["rpTimeLimitSaleModel"] = build_rp_time_limit_sale(
            enable_booking_type=time_limit_sale_enable_booking_type,
            time_limit_sale_models=time_limit_sale_models,
        )

    # 入住规则（境外）
    # 当传了 priceSameTag（境外多人多价/同价）且未显式传 booking_max_adult 时，
    # 自动从 max_adult_admissibility 补全 rpBookingModel（后端必须有此字段）
    if booking_max_adult is not None or booking_target_user is not None:
        rp_info["rpBookingModel"] = build_rp_booking(
            max_adult_admissibility=booking_max_adult,
            target_user=booking_target_user,
        )
    elif price_same_tag is not None and max_adult_admissibility is not None:
        # 境外多人多价/同价场景：自动补全 rpBookingModel
        rp_info["rpBookingModel"] = build_rp_booking(
            max_adult_admissibility=max_adult_admissibility,
        )

    # ── 构建 GoodsPriceUpdateModel ────────────────────────────────────────
    price_in_fen = int(float(price) * 100)
    price_info = {
        "priceRecordWay": price_record_way,
        "ratioConfig": {
            "newRatio": ratio_new,
            "ratioChange": True,
            "ratioType": ratio_type,
        },
        "priceInfos": None,
        # unifiedDatePriceInfos：后端要求 dates + weekPriceInfos 结构
        # dates 不能为 null，需要传具体日期范围；默认从今天开始向后两年
        "unifiedDatePriceInfos": {
            "dates": [
                {
                    "startDate": _today(),
                    "endDate": _two_years_later(),
                }
            ],
            "weekPriceInfos": [
                {
                    "inWeek": [1, 2, 3, 4, 5, 6, 7],
                    "priceInfo": {
                        "salePrice": str(price_in_fen),
                        "basePrice": "",
                        "subPrice": "",
                        "subRatio": ratio_new,
                    },
                    "priceFactorInfos": None,
                }
            ],
        },
    }

    # ── 组装 GoodsCreateDetailModel ───────────────────────────────────────
    goods_detail = {
        "goodsBaseInfo": goods_base_info,
        "roomInfo": room_info,
        "rpInfo": rp_info,
        "priceInfo": price_info,
    }

    # ── 组装顶层 CreateOrUpdateGoodsParam ────────────────────────────────
    # 境外多人多价/同价（priceSameTag 非 null）+ 卖价模式（priceChangeMode=8）时，
    # 需自动构建 priceAuditInfos，否则后端报「产品进审核，但没有提交审核信息」
    # goodsNameList 必须是 roomName + "-" + rpName 的拼接（不是 goodsName！）
    _price_audit_infos = None
    if price_same_tag is not None:
        # 取 rpName（由 _build_names_from_params 生成，或用 goods_name 兜底）
        _rp_name_for_audit = _auto_rp_name or goods_name
        _full_name_for_audit = f"{room_name}-{_rp_name_for_audit}" if _auto_rp_name else goods_name
        _price_audit_infos = [
            {
                "goodsNameList": [_full_name_for_audit],
                "materials": [],
                "reason": "其他",
                "type": "其它：需备注",
            }
        ]

    full_params = {
        "poiId": int(poi_id),
        "partnerId": int(partner_id),
        "createFlag": True,
        "goodsDetailList": [goods_detail],
        "priceAuditInfos": _price_audit_infos,
    }

    # 统一走 call_raw()，避免重复的 invoke 调用逻辑
    return call_raw(params=full_params, swimlane=swimlane, dry_run=dry_run)


def call_raw(
    params: dict,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    直接将完整的 batchCreateGoods 请求 dict 传给 RPC，不做任何参数组装。

    这是 food 范式的核心入口：
        factory 层负责加载模板、替换占位符、应用 --set 覆盖、约束校验，
        然后将最终 dict 传入此函数直接发送 RPC。

    参数：
        params   - 完整的 CreateOrUpdateGoodsParam dict（来自 factory 层组装）
        swimlane - 泳道（空字符串=主干）
        dry_run  - True 时只打印不执行

    返回：
        dict，其中 data 字段为 uuid（异步任务ID）
        后续可用 getProcessRate(partnerId, poiId, uuid) 轮询进度
    """
    # 接口层兜底校验（factory 层已做 validate_constraints，此处二次保障）
    _validate_raw(params)

    partner_id = str(params.get("partnerId", ""))
    poi_id = str(params.get("poiId", ""))
    goods_type = 1
    try:
        goods_type = int(
            (params.get("goodsDetailList") or [{}])[0]
            .get("goodsBaseInfo", {})
            .get("goodsType", 1)
        )
    except (IndexError, AttributeError, TypeError, ValueError):
        pass

    return invoke(
        appkey=APPKEY,
        service=SERVICE,
        method=METHOD,
        params=params,
        swimlane=swimlane,
        timeout_ms=120000,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint=f"创建{'全日房' if goods_type == 1 else '钟点房'}（研发接口）中，约30秒...",
    )


def query_goods_info(
    partner_id: str,
    poi_id: str,
    goods_ids: list,
    swimlane: str = "",
) -> dict:
    """
    查询商品详情（MeGoodsFacade#queryGoodsInfo）。

    参数：
        partner_id - 供应商ID
        poi_id     - 门店ID（mtPoiId）
        goods_ids  - 商品ID列表，如 [600000784334]
        swimlane   - 泳道（空字符串=主干）

    返回：商品详情，data 中包含 goodsDetailInfoList 等字段
    """
    params = {
        "partnerId": int(partner_id),
        "poiId": str(poi_id),
        "goodsIds": [int(gid) for gid in goods_ids],
    }
    return invoke(
        appkey=APPKEY,
        service=SERVICE,
        method="queryGoodsInfo",
        params=params,
        swimlane=swimlane,
        timeout_ms=30000,
        raise_on_biz_error=False,
        progress_hint="查询商品详情...",
    )


def query_process_rate(partner_id: str, poi_id: str, uuid: str, swimlane: str = "") -> dict:
    """
    查询创建进度（batchCreateGoods 异步接口的轮询方法）。

    参数：
        partner_id - 供应商ID
        poi_id     - 门店ID
        uuid       - batchCreateGoods 返回的任务ID
        swimlane   - 泳道

    返回：进度信息，data.status: 0=处理中 1=成功 2=失败
    """
    # getProcessRate(Long partnerId, Long poiId, String uuid) — 三个散列参数，不能用 body 模式
    # body 模式会把整个 dict 当作第一个参数反序列化为 Long，导致 MismatchedInputException。
    # parameter_values 模式：String 类型必须加引号包裹（du_thrift 文档要求），否则报 Unrecognized token。
    return invoke(
        appkey=APPKEY,
        service=SERVICE,
        method="getProcessRate",
        parameter_values=[str(int(partner_id)), str(int(poi_id)), f'"{uuid}"'],
        parameter_types=["java.lang.Long", "java.lang.Long", "java.lang.String"],
        swimlane=swimlane,
        timeout_ms=30000,
        raise_on_biz_error=False,
        progress_hint="查询创建进度...",
    )


# ════════════════════════════════════════════════════════════════════════════
# 创建后置操作：轮询 + 上线 + 缓存刷新
# ════════════════════════════════════════════════════════════════════════════

def wait_for_goods_id(
    partner_id: str,
    poi_id: str,
    uuid: str,
    swimlane: str = "",
    timeout_sec: int = 120,
) -> str:
    """
    轮询等待 batchCreateGoods 异步任务完成，返回 goodsId。

    每5秒轮询一次 getProcessRate，最多等待 timeout_sec 秒。

    返回结构（getProcessRate）：
    {
      "data": {
        "over": true/false,                              # 完成标志
        "errorType": 0/非0,                              # 0=成功，非0=失败
        "result": "[{\"goodsId\":xxx,...}]",             # JSON 字符串，需二次解析
        "message": "错误信息"                             # 失败时有值
      }
    }

    返回：goodsId 字符串；任务失败时 sys.exit(1)；超时返回空字符串。
    """
    interval = 5
    max_attempts = max(1, timeout_sec // interval)
    for attempt in range(1, max_attempts + 1):
        try:
            rate_result = query_process_rate(partner_id, poi_id, uuid, swimlane)
            data = rate_result.get("data") or {}
            if data.get("over", False):
                error_type = data.get("errorType", 0)
                if error_type != 0:
                    err_msg = data.get("message") or "创建失败"
                    print(f"❌ 商品创建失败: {err_msg}", file=sys.stderr)
                    # 识别「产品进审核，但没有提交审核信息」错误，给出精确修复指引
                    if "产品进审核" in err_msg and "没有提交审核信息" in err_msg:
                        # 从错误消息中提取商品全名（格式：[商品全名]产品进审核...）
                        import re as _re
                        _name_match = _re.search(r"\[([^\]]+)\]", err_msg)
                        _full_name = _name_match.group(1) if _name_match else "<roomName>-<rpName>"
                        print(
                            "\n💡 【修复指引：priceAuditInfos 未正确提交】\n"
                            "   触发原因：境外多人多价（priceFactorInfos 按档位定价）+ 卖价模式（priceChangeMode=8）\n"
                            "            后端要求在顶层传入 priceAuditInfos 才能提交改价审核\n"
                            "\n"
                            "   ⚠️ goodsNameList 的名字必须是 roomName + \"-\" + rpName 的拼接\n"
                            "      （rpName = rpBaseModel.rpName，不是 goodsName！）\n"
                            f"   当前商品全名（从错误消息提取）：{_full_name!r}\n"
                            "\n"
                            "   修复步骤：在命令中加入如下参数：\n"
                            f"   export AUDIT_JSON='[{{\"goodsNameList\":[\"{_full_name}\"],"
                            "\"materials\":[],\"reason\":\"其他\",\"type\":\"其它：需备注\"}}]'\n"
                            "   --set \"priceAuditInfos=$AUDIT_JSON\"\n"
                            "\n"
                            "   完整命令示例（请按实际参数替换）：\n"
                            f"   export AUDIT_JSON='[{{\"goodsNameList\":[\"{_full_name}\"],"
                            "\"materials\":[],\"reason\":\"其他\",\"type\":\"其它：需备注\"}}]'\n"
                            "   python3 factory/fullday/create-fullday.py \\\n"
                            "     --partner-id <partnerId> --poi-id <poiId> \\\n"
                            "     --room-id <roomId> --room-name \"<roomName>\" \\\n"
                            "     --set \"goodsDetailList.0.rpInfo.rpBaseModel.rpName=<rpName>\" \\\n"
                            "     ... （其他参数） \\\n"
                            "     --set \"priceAuditInfos=$AUDIT_JSON\"",
                            file=sys.stderr,
                        )
                    sys.exit(1)
                # 成功：goodsId 在 result JSON 字符串中
                result_str = data.get("result") or ""
                goods_id = ""
                if result_str:
                    try:
                        result_list = json.loads(result_str)
                        if isinstance(result_list, list) and result_list:
                            goods_id = str(
                                result_list[0].get("goodsId")
                                or result_list[0].get("productId")
                                or ""
                            )
                        elif isinstance(result_list, dict):
                            goods_id = str(
                                result_list.get("goodsId")
                                or result_list.get("productId")
                                or ""
                            )
                    except Exception:
                        goods_id = ""
                return goods_id
            else:
                print(f"   第{attempt}/{max_attempts}次轮询：处理中...（等待{interval}秒）")
        except Exception as e:
            print(f"   轮询异常（{attempt}/{max_attempts}次）: {e}")
        if attempt < max_attempts:
            time.sleep(interval)

    print(f"⚠️ 已轮询 {max_attempts} 次（{timeout_sec}秒）仍未完成，商品可能仍在处理中。")
    return ""


def _load_ops_interface():
    """内部加载 ops interface 模块。"""
    spec = _ilu.spec_from_file_location(
        "ops_interface",
        os.path.join(_ROOT, "interface/ops/interface.py"),
    )
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def post_create_ops(
    partner_id: str,
    poi_id: str,
    goods_id: str,
    swimlane: str = "",
) -> None:
    """
    商品创建成功后的标准后置操作：① 上线 ② 缓存刷新。

    参数：
        partner_id - 供应商ID
        poi_id     - 门店ID
        goods_id   - 商品ID（空字符串时跳过）
        swimlane   - 泳道
    """
    if not goods_id:
        print("\n⚠️ 未获取到 goodsId，跳过上线和缓存刷新。")
        return

    ops = _load_ops_interface()

    # ── Step 6: 恢复上线 ─────────────────────────────────────────────────
    print("\n── Step 6: 恢复上线（batchOnlineSwitch status=2）──────────────")
    try:
        switch_resp = ops.call_online_switch(
            partner_id=int(partner_id),
            poi_id=str(poi_id),
            goods_ids=[int(goods_id)],
            status=2,
            swimlane=swimlane,
        )
        sw_data = switch_resp.get("data") or {}
        if sw_data.get("successCount", 0) > 0 and sw_data.get("failCount", 0) == 0:
            print("  ✅ 上线成功")
        else:
            details = sw_data.get("details") or []
            reason = details[0].get("reason", "未知原因") if details else "未知原因"
            print(
                f"  ⚠️ 上线未成功（successCount={sw_data.get('successCount', 0)}, "
                f"failCount={sw_data.get('failCount', 0)}）: {reason}（可在 MTA 手动操作）"
            )
    except Exception as e:
        print(f"  ⚠️ 上线异常（可在 MTA 手动操作）: {e}")

    # ── Step 7: 缓存刷新 ─────────────────────────────────────────────────
    print("\n── Step 7: 缓存刷新（operationType=1）───────────────────────")
    try:
        ops.call(
            operation_type=1,
            product_id=int(goods_id),
        )
        print("  ✅ 缓存刷新成功")
    except Exception as e:
        print(f"  ⚠️ 缓存刷新失败（可手动触发）: {e}")

