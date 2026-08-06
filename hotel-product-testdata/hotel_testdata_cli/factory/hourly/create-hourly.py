#!/usr/bin/env python3
"""
场景层：钟点房创建（直调研发级 MeGoodsFacade#batchCreateGoods）
入口：factory/hourly/create-hourly.py

=== 设计范式===

1. 加载模板：从 templates/hourly-default.json 读取完整、已验证的默认参数
2. 替换占位符：__PARTNER_ID__ / __POI_ID__ / __ROOM_ID__ / __ROOM_NAME__ / __TODAY__ 等
3. --set 覆盖：支持点分路径覆盖任意字段，如 --set goodsDetailList.0.goodsBaseInfo.typeLimitValue=6
4. 约束校验：在调用 RPC 前拦截参数错误，给出可执行修复提示
5. 调用接口：直接将 dict 传给 interface 层，无参数重新组装

=== 与全日房关键差异 ===
- goodsType=2（固定）
- typeLimitValue 必填（可住时长，小时，默认4，范围1~23）
- paymentType 固定为 0（预付），不支持现付（paymentType=1/2 后端直接拦截）
- rpHourlyRoomUseModel 必填（接待时间，默认08:00-22:00）
- rpBreakFastModel=null（不支持早餐设置）
- rpSerialModel=null（不支持连住规则）
- 取消规则只支持：0=不可取消 / 1=入住前可取消（不支持收费取消 payCancelPeriodModels）
- 默认取消政策：免费取消（cancelItemType=1，全日房默认不可取消）
- 默认售价：8000分（80元）

=== 常用示例 ===

# 基础钟点房（4小时，最简）
python3 factory/hourly/create-hourly.py \\
  --partner-id 4550100 --poi-id 1090235108219575 \\
  --room-id 12345 --room-name "钟点房"

# 6小时钟点房
python3 factory/hourly/create-hourly.py \\
  --partner-id 4550100 --poi-id 1090235108219575 \\
  --room-id 12345 --room-name "钟点房" \\
  --set goodsDetailList.0.goodsBaseInfo.typeLimitValue=6

# 不可取消
python3 factory/hourly/create-hourly.py \\
  --partner-id 4550100 --poi-id 1090235108219575 \\
  --room-id 12345 --room-name "钟点房" \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=0

# 全天接待（00:00-23:59）
python3 factory/hourly/create-hourly.py \\
  --partner-id 4550100 --poi-id 1090235108219575 \\
  --room-id 12345 --room-name "24H钟点房" \\
  --set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeStart=00:00 \\
  --set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeEnd=23:59

# 下午场（14:00-20:00）
python3 factory/hourly/create-hourly.py \\
  --partner-id 4550100 --poi-id 1090235108219575 \\
  --room-id 12345 --room-name "钟点房" \\
  --set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeStart=14:00 \\
  --set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeEnd=20:00

# 附近专享（3公里内）
python3 factory/hourly/create-hourly.py \\
  --partner-id 4550100 --poi-id 1090235108219575 \\
  --room-id 12345 --room-name "钟点房" \\
  --set goodsDetailList.0.rpInfo.rpDisplayModel.normalRule.distanceRange=1

# 修改价格（单位：分，100元=10000）
python3 factory/hourly/create-hourly.py \\
  --partner-id 4550100 --poi-id 1090235108219575 \\
  --room-id 12345 --room-name "钟点房" \\
  --set goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos.0.priceInfo.salePrice=10000

# 仅美团渠道
python3 factory/hourly/create-hourly.py \\
  --partner-id 4550100 --poi-id 1090235108219575 \\
  --room-id 12345 --room-name "钟点房" \\
  --set goodsDetailList.0.goodsBaseInfo.sellChannel=9

# 泳道支持
python3 factory/hourly/create-hourly.py \\
  --partner-id 4550100 --poi-id 1090235108219575 \\
  --room-id 12345 --room-name "钟点房" \\
  --swimlane user-zhangsan

# dry-run 模式（只打印最终参数不执行）
python3 factory/hourly/create-hourly.py \\
  --partner-id 4550100 --poi-id 1090235108219575 \\
  --room-id 12345 --room-name "钟点房" \\
  --dry-run

# 查看完整参数 schema（字段说明/枚举/业务规则）
python3 factory/hourly/create-hourly.py --show-schema

# 查看模板默认值
python3 factory/hourly/create-hourly.py --show-template
"""

import argparse
import datetime
import importlib.util as ilu
import json
import os
import re
import sys
import time

# ── 根路径注入 ────────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)

TEMPLATE_PATH = os.path.join(_SCRIPT_DIR, "templates", "hourly-default.json")
SCHEMA_PATH   = os.path.join(_SCRIPT_DIR, "schema.json")

# ── 懒加载 interface 层 ────────────────────────────────────────────────────
# 钟点房与全日房共用同一 interface（底层同为 batchCreateGoods，call_raw 内部按 goodsType 区分）
def _load_interface():
    spec = ilu.spec_from_file_location(
        "goods_interface",
        os.path.join(ROOT, "interface/fullday/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════════════════════════
# 占位符替换
# ══════════════════════════════════════════════════════════════════════════

def _today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def _two_years_later() -> str:
    """
    服务端限制：endDate 只能在昨天至未来2年内（不含边界）。
    取 today + 2年 - 1天，确保不超出上限。
    """
    today = datetime.date.today()
    try:
        d = today.replace(year=today.year + 2) - datetime.timedelta(days=1)
    except ValueError:
        # 闰年2月29日特殊处理
        d = today.replace(year=today.year + 2, month=3, day=1) - datetime.timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _auto_goods_name(room_name: str) -> str:
    """根据房型名称和时间戳自动生成商品名（避免与已有商品重名）。"""
    ts = int(time.time())
    return f"{room_name}-{ts}"


def _fill_placeholders(obj, replacements: dict):
    """
    递归替换 JSON 结构中的所有占位符字符串。
    replacements 格式：{"__TODAY__": "2026-05-20", ...}
    """
    if isinstance(obj, str):
        for k, v in replacements.items():
            if obj == k:
                # 整个字符串就是占位符：替换为目标类型（可能是 int/float）
                return v
            obj = obj.replace(k, str(v))
        return obj
    elif isinstance(obj, dict):
        return {key: _fill_placeholders(val, replacements) for key, val in obj.items()}
    elif isinstance(obj, list):
        return [_fill_placeholders(item, replacements) for item in obj]
    else:
        return obj


def load_template(
    partner_id: str,
    poi_id: str,
    room_id: int,
    room_name: str,
    goods_name: str = "",
) -> dict:
    """
    加载 hourly-default.json 模板，替换所有占位符，返回完整的请求 dict。

    占位符说明：
        __PARTNER_ID__       → int(partner_id)
        __POI_ID__           → int(poi_id)
        __ROOM_ID__          → int(room_id)
        __ROOM_NAME__        → room_name
        __GOODS_NAME__       → goods_name（空时自动生成）
        __RP_CUSTOM_NAME__   → 时间戳（产品备注，用于区分同房型下多个产品）
        __TODAY__            → 今天日期
        __TWO_YEARS_LATER__  → 两年后日期
    """
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = json.load(f)

    ts = str(int(time.time()))
    _goods_name = goods_name if goods_name else _auto_goods_name(room_name)

    replacements = {
        "__PARTNER_ID__":       int(partner_id),
        "__POI_ID__":           int(poi_id),
        "__ROOM_ID__":          int(room_id),
        "__ROOM_NAME__":        room_name,
        "__GOODS_NAME__":       _goods_name,
        "__RP_CUSTOM_NAME__":   ts,
        "__TODAY__":            _today(),
        "__TWO_YEARS_LATER__":  _two_years_later(),
    }

    # 去掉元数据字段（以 _ 开头）
    data = {k: v for k, v in template.items() if not k.startswith("_")}
    return _fill_placeholders(data, replacements)


# ══════════════════════════════════════════════════════════════════════════
# --set 参数覆盖（点分路径）
# ══════════════════════════════════════════════════════════════════════════

def _set_nested(obj, path: str, value) -> None:
    """
    按点分路径设置嵌套值，支持数字列表索引。
    例：
        _set_nested(d, "goodsDetailList.0.goodsBaseInfo.typeLimitValue", 6)
        _set_nested(d, "goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeStart", "00:00")
    """
    keys = [k for k in path.split(".") if k]
    cur = obj
    for i, k in enumerate(keys[:-1]):
        if isinstance(cur, list):
            idx = int(k)
            while len(cur) <= idx:
                cur.append({})
            cur = cur[idx]
        else:
            if k not in cur:
                # 尝试预判下一段是数字（则创建 list）还是字符串（则创建 dict）
                next_key_idx = i + 1
                next_key = keys[next_key_idx] if next_key_idx < len(keys) else ""
                cur[k] = [] if next_key.isdigit() else {}
            cur = cur[k]

    last = keys[-1]
    if isinstance(cur, list):
        idx = int(last)
        while len(cur) <= idx:
            cur.append({})
        cur[idx] = value
    else:
        cur[last] = value


def _try_parse_value(v: str, key: str = ""):
    """
    对看起来像 JSON 数组/对象/数字的字符串尝试解析为 Python 类型；
    价格字段（salePrice / subRatio / newRatio 等）保持字符串，因为接口要求 String 类型。
    """
    _PRICE_FIELDS = {"salePrice", "subRatio", "newRatio", "basePrice", "subPrice"}
    tail = key.split(".")[-1]
    if tail in _PRICE_FIELDS:
        return v  # 价格字段保持字符串

    if isinstance(v, str):
        if re.fullmatch(r"-?\d+", v):
            return int(v)
        if re.fullmatch(r"-?\d+\.\d+", v):
            return float(v)
        if v.lower() == "true":
            return True
        if v.lower() == "false":
            return False
        if v.lower() == "null":
            return None
        if len(v) > 1 and v[0] in ("[", "{"):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                pass
    return v


def apply_overrides(params: dict, overrides: dict) -> None:
    """将 overrides（{点分路径: 值}）应用到 params dict。"""
    errors = []
    for path, value in overrides.items():
        try:
            _set_nested(params, path, value)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            errors.append((path, e))

    if errors:
        print("\n❌ [参数错误] 以下 --set 路径无效：", file=sys.stderr)
        for p, e in errors:
            print(f"   --set {p}  ({e})", file=sys.stderr)
        print(
            "\n   字段路径示例：\n"
            "     住时长  → --set goodsDetailList.0.goodsBaseInfo.typeLimitValue=6\n"
            "     接待时间 → --set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeStart=08:00\n"
            "     售价    → --set goodsDetailList.0.priceInfo.unifiedDatePriceInfos"
            ".weekPriceInfos.0.priceInfo.salePrice=10000\n"
            "\n   完整字段说明见 factory/hourly/schema.json 或 --show-schema\n",
            file=sys.stderr,
        )
        sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════
# 约束校验（本地，在 RPC 调用前拦截）
# ══════════════════════════════════════════════════════════════════════════

class ConstraintError(Exception):
    pass


def _get_val(params: dict, *path):
    """安全取嵌套值，任一层不存在则返回 None。"""
    cur = params
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


def validate_constraints(params: dict) -> None:
    """
    对完整 RPC 参数 dict 做本地约束校验。
    任一失败时抛出 ConstraintError，给出可执行修复提示。

    覆盖规则：
      C0  商品名称不能含「测试」字样（后端拦截）
      C0a 商品名称不能超过99个字符
      C0b 商品名称不能含4字节特殊字符（emoji等）
      C1  售价必须为正数（单位：分）
      C2  typeLimitValue 必须在 1~23 之间
      C2a paymentType 必须为 0（预付），钟点房不支持现付
      C3  取消政策：cancelItemType=1（可取消）时必须传 moveUpCancelDays
      C6  receiveTimeEnd 必须晚于 receiveTimeStart
      C6a typeLimitValue（可住时长）不能超过接待窗口时长
      C7  rpBreakFastModel 必须为 null（钟点房不支持早餐）
    """
    errors = []

    gd = _get_val(params, "goodsDetailList", "0") or {}
    base = gd.get("goodsBaseInfo") or {}
    rp = gd.get("rpInfo") or {}
    price_info = gd.get("priceInfo") or {}

    payment_type = base.get("paymentType", 0)

    # C0：商品名称禁词
    goods_name = base.get("goodsName", "")
    if goods_name and "测试" in goods_name:
        errors.append(
            f"C0: goodsName={goods_name!r} 包含'测试'字样，后端会拦截\n"
            f"   修复：--set goodsDetailList.0.goodsBaseInfo.goodsName=\"换个商品名\""
        )

    # C0a：商品名称长度限制（后端 MccConstants.MAX_GOODS_NAME_LENGTH = 99）
    if goods_name and len(goods_name) > 99:
        errors.append(
            f"C0a: goodsName 超长（{len(goods_name)} 字符），最大允许 99 个字符\n"
            f"   修复：--set goodsDetailList.0.goodsBaseInfo.goodsName=\"简短的商品名\""
        )

    # C0b：商品名称特殊字符（4字节字符，如 emoji）
    if goods_name:
        import re as _re
        _special_chars = [c for c in goods_name if ord(c) > 0xFFFF]
        if _special_chars:
            errors.append(
                f"C0b: goodsName 含4字节特殊字符（如 emoji）：{''.join(_special_chars)!r}，后端会拦截\n"
                f"   修复：删除特殊字符后重新传入 goodsName"
            )

    # C1：售价必须为正数
    sale_price_str = _get_val(
        price_info,
        "unifiedDatePriceInfos", "weekPriceInfos", "0", "priceInfo", "salePrice"
    )
    if sale_price_str is not None:
        try:
            sale_price = int(sale_price_str)
            if sale_price <= 0:
                errors.append(
                    f"C1: salePrice={sale_price} 非法，必须 > 0（单位：分，80元=8000）\n"
                    f"   修复：--set goodsDetailList.0.priceInfo.unifiedDatePriceInfos"
                    f".weekPriceInfos.0.priceInfo.salePrice=8000"
                )
        except (ValueError, TypeError):
            pass

    # C2：typeLimitValue 范围校验（后端 MIN=1 / MAX=23）
    type_limit = base.get("typeLimitValue")
    if type_limit is not None:
        try:
            tl = int(type_limit)
            if not (1 <= tl <= 23):
                errors.append(
                    f"C2: typeLimitValue={tl} 超出范围（必须 1~23，单位：小时）\n"
                    f"   修复：--set goodsDetailList.0.goodsBaseInfo.typeLimitValue=4"
                )
        except (ValueError, TypeError):
            errors.append(
                f"C2: typeLimitValue={type_limit} 不是整数\n"
                f"   修复：--set goodsDetailList.0.goodsBaseInfo.typeLimitValue=4"
            )
    else:
        errors.append(
            "C2: typeLimitValue 未设置（钟点房必填，默认模板已含4小时）\n"
            "   修复：--set goodsDetailList.0.goodsBaseInfo.typeLimitValue=4"
        )

    # C2a：钟点房只支持预付（paymentType 必须为 0）
    if payment_type != 0:
        errors.append(
            f"C2a: 钟点房不支持 paymentType={payment_type}（只允许预付 paymentType=0）\n"
            f"   修复：--set goodsDetailList.0.goodsBaseInfo.paymentType=0"
        )

    # C3：可取消时必须传 moveUpCancelDays
    cancel_model = (rp.get("rpCancelModel") or {}).get("normalRule") or {}
    cancel_type = cancel_model.get("cancelItemType")
    if cancel_type == 1 and cancel_model.get("moveUpCancelDays") is None:
        errors.append(
            "C3: cancelItemType=1（可取消）时必须传 moveUpCancelDays\n"
            "   修复：--set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelDays=0"
        )

    # C6：接待时间顺序校验
    hourly_model = (rp.get("rpHourlyRoomUseModel") or {}).get("normalRule") or {}
    receive_start = hourly_model.get("receiveTimeStart", "")
    receive_end = hourly_model.get("receiveTimeEnd", "")

    def _to_minutes(t: str) -> int:
        parts = t.strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h * 60 + m

    if receive_start and receive_end:
        try:
            start_min = _to_minutes(receive_start)
            # 23:59 视同 24:00（后端逻辑与此一致）
            end_str = "24:00" if receive_end.startswith("23:59") else receive_end
            end_min = _to_minutes(end_str)
            if start_min >= end_min:
                errors.append(
                    f"C6: receiveTimeEnd({receive_end}) 不能早于或等于 receiveTimeStart({receive_start})\n"
                    f"   修复：--set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeEnd=22:00\n"
                    f"   全天接待写法：receiveTimeStart=00:00 / receiveTimeEnd=23:59"
                )
            else:
                # C6a：可住时长不能超过接待窗口（后端 limitHours <= diffHours 校验）
                tl = int(type_limit) if type_limit is not None else None
                if tl is not None:
                    window_hours = (end_min - start_min) // 60
                    if tl > window_hours:
                        errors.append(
                            f"C6a: typeLimitValue={tl}h 超过接待窗口时长 {window_hours}h"
                            f"（{receive_start}~{receive_end}），后端会拦截\n"
                            f"   修复方案1：增大接待窗口，如 receiveTimeEnd=22:00（14小时窗口）\n"
                            f"   修复方案2：减小 typeLimitValue，如 --set "
                            f"goodsDetailList.0.goodsBaseInfo.typeLimitValue={window_hours}"
                        )
        except (ValueError, AttributeError, IndexError):
            pass

    # C7：钟点房不支持早餐规则
    rp_breakfast = rp.get("rpBreakFastModel")
    if rp_breakfast is not None:
        errors.append(
            "C7: 钟点房不支持 rpBreakFastModel，必须为 null\n"
            "   修复：--set goodsDetailList.0.rpInfo.rpBreakFastModel=null"
        )

    # C8：预订规则约束（同全日房，后端 ValidateGoodsServiceImpl.validRpEarlyBooking）
    early_booking = (rp.get("rpEarlyBookingModel") or {}).get("normalRule") or {}
    latest_days = early_booking.get("latestBookingDays")
    earliest_days = early_booking.get("earliestBookingDays")
    if latest_days is not None:
        try:
            ld = int(latest_days)
            if ld < -1:
                errors.append(
                    f"C8: latestBookingDays={ld} 非法（必须 >= -1，-1=不限制）\n"
                    f"   修复：--set goodsDetailList.0.rpInfo.rpEarlyBookingModel.normalRule.latestBookingDays=-1"
                )
        except (ValueError, TypeError):
            pass
    if earliest_days is not None:
        try:
            ed = int(earliest_days)
            if ed < -1:
                errors.append(
                    f"C8: earliestBookingDays={ed} 非法（必须 >= -1，-1=不限制）\n"
                    f"   修复：--set goodsDetailList.0.rpInfo.rpEarlyBookingModel.normalRule.earliestBookingDays=-1"
                )
        except (ValueError, TypeError):
            pass
    if latest_days is not None and earliest_days is not None:
        try:
            ld, ed = int(latest_days), int(earliest_days)
            if ld > 0 and ed > 0 and ld > ed:
                errors.append(
                    f"C8: latestBookingDays={ld}（最少提前）不能大于 earliestBookingDays={ed}（最多提前）\n"
                    f"   修复：调整两者使 latestBookingDays <= earliestBookingDays"
                )
        except (ValueError, TypeError):
            pass

    # C9：钟点房不支持连住规则（rpSerialModel 必须为 null）
    rp_serial = rp.get("rpSerialModel")
    if rp_serial is not None:
        errors.append(
            "C9: 钟点房不支持 rpSerialModel（连住规则），必须为 null\n"
            "   修复：--set goodsDetailList.0.rpInfo.rpSerialModel=null"
        )

    # C10：钟点房不支持收费取消（payCancelPeriodModels 必须为空/null）
    pay_cancel = cancel_model.get("payCancelPeriodModels")
    if pay_cancel is not None and pay_cancel != [] and pay_cancel != "null":
        errors.append(
            "C10: 钟点房不支持收费取消（payCancelPeriodModels），钟点房取消规则只支持：\n"
            "     cancelItemType=0（不可取消）或 cancelItemType=1（入住前可取消）\n"
            "   修复：移除 payCancelPeriodModels，或将 cancelItemType 设为 0/1"
        )

    if errors:
        msg = "\n".join(f"  {e}" for e in errors)
        raise ConstraintError(f"\n参数约束校验失败（共 {len(errors)} 项）：\n{msg}\n")


# ══════════════════════════════════════════════════════════════════════════
# 主逻辑
# ══════════════════════════════════════════════════════════════════════════

_INV_ERROR_KEYWORD = "最近90天内至少30天同时有价格和库存"


def _load_update_inventory():
    """加载 factory/inventory/update-inventory.py 模块，复用 open_and_set_inventory 函数。"""
    spec = ilu.spec_from_file_location(
        "update_inventory",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "../inventory/update-inventory.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _online_with_inventory_retry(
    iface,
    params: dict,
    partner_id: str,
    poi_id: str,
    room_id: int,
    goods_id: str,
    swimlane: str,
) -> None:
    """
    Step 6：恢复上线 + Step 7：缓存刷新。

    上线失败且原因为"最近90天内至少30天同时有价格和库存"时：
      - 调用 MeInventoryFacade#batchUpdateInventory 开房并设置库存（299 间），
        复用 factory/inventory/update-inventory.py 的 open_and_set_inventory 函数
      - 库存修改成功后，重新尝试上线 + 缓存刷新
    其他原因失败：打印警告后直接执行缓存刷新，不重试。

    注意：batchUpdateInventory 流程不会强制覆盖 invSwitch（与 batchCreateGoods 不同），
    因此传 invSwitch=1 会真正把房态置为"开"。
    """
    ops = iface._load_ops_interface()

    def _try_online(gid: str) -> tuple:
        """对指定 goodsId 尝试上线，返回 (success: bool, reason: str)"""
        print("\n── Step 6: 恢复上线（batchOnlineSwitch status=2）──────────────")
        try:
            switch_resp = ops.call_online_switch(
                partner_id=int(partner_id),
                poi_id=str(poi_id),
                goods_ids=[int(gid)],
                status=2,
                swimlane=swimlane,
            )
            sw_data = switch_resp.get("data") or {}
            if sw_data.get("successCount", 0) > 0 and sw_data.get("failCount", 0) == 0:
                print("  ✅ 上线成功")
                return True, ""
            else:
                details = sw_data.get("details") or []
                reason = details[0].get("reason", "未知原因") if details else "未知原因"
                return False, reason
        except Exception as e:
            return False, str(e)

    def _do_cache_refresh(gid: str) -> None:
        """Step 7: 缓存刷新。"""
        print("\n── Step 7: 缓存刷新（operationType=1）───────────────────────")
        try:
            ops.call(operation_type=1, product_id=int(gid))
            print("  ✅ 缓存刷新成功")
        except Exception as e:
            print(f"  ⚠️ 缓存刷新失败（可手动触发）: {e}")

    # ── 第一次尝试上线 ────────────────────────────────────────────────────
    success, reason = _try_online(goods_id)
    if success:
        _do_cache_refresh(goods_id)
        return

    # ── 其他失败原因，不重试 ──────────────────────────────────────────────
    if _INV_ERROR_KEYWORD not in reason:
        print(f"  ⚠️ 上线未成功: {reason}（可在 MTA 手动操作）")
        _do_cache_refresh(goods_id)
        return

    # ── 库存不足：调 batchUpdateInventory 开房并补库存，再重新上线 ─────────
    print(f"  ⚠️ 上线失败（{reason}）")
    print("  🔄 检测到库存不足，调用 batchUpdateInventory 开房并设置库存（invSwitch=1，limitChangeValue=299）...")

    # 取价格有效期作为库存日期范围
    try:
        dates = params["goodsDetailList"][0]["priceInfo"]["unifiedDatePriceInfos"]["dates"]
        start_date = dates[0]["startDate"]
        end_date   = dates[0]["endDate"]
    except (KeyError, IndexError, TypeError):
        start_date = _today()
        end_date   = _two_years_later()

    print(f"  [库存修改] 房型={room_id}，日期范围 {start_date} ~ {end_date}")
    try:
        upd_mod = _load_update_inventory()
        upd_mod.open_and_set_inventory(
            partner_id=partner_id,
            poi_id=poi_id,
            hour_room_ids=[int(room_id)],
            start_date=start_date,
            end_date=end_date,
            inv_switch=1,           # 开房
            count_type=1520,        # 设置余量（REMAIN_TOTAL_MODE），预留房不变
            limit_change_value=299, # 余量目标值，满足"90天≥30天有库存"校验
            count=1,                # 预留房不变，传 1 仅满足 @Positive 约束
            swimlane=swimlane,
        )
        print("  ✅ 库存修改成功，重新尝试上线...")
    except Exception as e:
        print(f"  ⚠️ 库存修改失败: {e}")
        print("  💡 可手动执行：python3 factory/inventory/update-inventory.py"
              f" --partner-id {partner_id} --poi-id {poi_id}"
              f" --hour-room-ids {room_id}"
              f" --start-date {start_date} --end-date {end_date}"
              f" --inv-switch 1 --limit-change-value 299")
        _do_cache_refresh(goods_id)
        return

    # 库存修改成功后，重新尝试上线
    success2, reason2 = _try_online(goods_id)
    if not success2:
        print(f"  ⚠️ 补库存后仍上线失败: {reason2}（可在 MTA 手动操作）")
    _do_cache_refresh(goods_id)


def _print_success(partner_id: str, poi_id: str, room_id: int,
                   room_name: str, goods_id: str, swimlane: str) -> None:
    print("\n" + "═" * 60)
    print("  ✅ 钟点房创建成功")
    print("═" * 60)
    print(f"  商品ID (goodsId) : {goods_id or '（异步处理中，请等待）'}")
    print(f"  供应商ID         : {partner_id}")
    print(f"  门店ID           : {poi_id}")
    print(f"  房型ID           : {room_id}")
    print(f"  房型名称         : {room_name}")
    print(f"  泳道             : {swimlane or '主干'}")
    print("═" * 60)


def _show_schema():
    print("""=== 钟点房创建（create-hourly）参数说明 ===

【与全日房关键差异】
  goodsType=2（固定）  paymentType 只能=0（预付），不支持现付担保(1)/非担保(2)
  rpBreakFastModel=null（不支持早餐设置）  rpSerialModel=null（不支持连住）
  取消规则只支持 0=不可取消 / 1=入住前可取消，不支持收费取消（payCancelPeriodModels）
  默认取消政策：免费取消（cancelItemType=1）

【必填参数】
  --partner-id    STR    供应商ID（partnerId）
  --poi-id        STR    门店ID（mtPoiId）
  --room-id       INT    逻辑房型ID（roomId）
  --room-name     STR    逻辑房型名称（与 create-room.py 输出的 roomName 一致）

【可选参数】
  --contract-no   STR    合同编号（字符串，如 ZSFW-A9-75178816）
                         通过 query-contract.py --platform-contract-id <id> 查询获得
                         ⚠️  接口实际校验需要此字段，建议传入
  --goods-name    STR    商品名称（不能含「测试」字样；不传则自动生成）
  --set KEY=VALUE        覆盖任意字段（点分路径），可多次使用

【--set 常用字段（点分路径）】
  可住时长（1~23小时，默认 4）：
    goodsDetailList.0.goodsBaseInfo.typeLimitValue

  接待时间（默认 08:00~22:00）：
    goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeStart
    goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeEnd

  取消政策（默认 cancelItemType=1 免费取消）：
    goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType
      0=不可取消  1=可取消（默认）
    goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelDays
      提前取消天数（cancelItemType=1 时必填）

  售价（单位：分，80元=8000，默认 8000）：
    goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos.0.priceInfo.salePrice

  销售渠道：
    goodsDetailList.0.goodsBaseInfo.sellChannel
      9=仅美团渠道

  附近专享：
    goodsDetailList.0.rpInfo.rpDisplayModel.normalRule.distanceRange
      1=3公里内专享

【执行控制】
  --swimlane      STR    泳道名称（不传=主干）
  --dry-run              只打印最终参数，不执行
  --show-template        打印模板默认值（templates/hourly-default.json）
  --skip-constraints     跳过本地约束校验（谨慎使用）

【本地约束校验（自动执行）】
  C2   typeLimitValue 必须在 1~23 之间
  C2a  paymentType 必须为 0（不支持现付担保/非担保）
  C3   cancelItemType=1 时必须传 moveUpCancelDays
  C6   receiveTimeEnd 必须晚于 receiveTimeStart
  C6a  typeLimitValue（可住时长）不能超过接待窗口时长
  C7   rpBreakFastModel 必须为 null（不支持早餐）
  C9   rpSerialModel 必须为 null（不支持连住）
  C10  payCancelPeriodModels 禁止传入（不支持收费取消）

【使用示例】
  # 4小时钟点房（带合同编号）
  python3 factory/hourly/create-hourly.py \\
    --partner-id 4550100 --poi-id 1090235108219575 \\
    --room-id 12345 --room-name "zhaoshichuan20260527153042" \\
    --contract-no ZSFW-A9-75178816

  # 6小时钟点房，全天接待
  python3 factory/hourly/create-hourly.py \\
    --partner-id 4550100 --poi-id 1090235108219575 \\
    --room-id 12345 --room-name "zhaoshichuan20260527153042" \\
    --contract-no ZSFW-A9-75178816 \\
    --set goodsDetailList.0.goodsBaseInfo.typeLimitValue=6 \\
    --set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeStart=00:00 \\
    --set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeEnd=23:59

  # 不可取消
  python3 factory/hourly/create-hourly.py \\
    --partner-id 4550100 --poi-id 1090235108219575 \\
    --room-id 12345 --room-name "zhaoshichuan20260527153042" \\
    --contract-no ZSFW-A9-75178816 \\
    --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=0
""")


def main():
    # 快速检测帮助类命令（避免 required 参数报错）
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)
    if "--show-template" in sys.argv:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            print(f.read())
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="钟点房创建（直调研发级 RPC：MeGoodsFacade#batchCreateGoods）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── 必填参数 ──────────────────────────────────────────────────────────
    g_req = parser.add_argument_group("必填参数")
    g_req.add_argument("--partner-id", required=True,           help="供应商ID（partnerId）")
    g_req.add_argument("--poi-id",     required=True,           help="门店ID（mtPoiId）")
    g_req.add_argument("--room-id",    required=True, type=int, help="逻辑房型ID（roomId）")
    g_req.add_argument("--room-name",  required=True,           help="逻辑房型名称（如：钟点房）")

    # ── 可选参数 ──────────────────────────────────────────────────────────
    g_opt = parser.add_argument_group("可选参数")
    g_opt.add_argument("--contract-no", default=None,
                        help="合同编号（字符串，如 ZSFW-A9-75178816），通过 query-contract.py 查询获得")
    g_opt.add_argument("--goods-name", default="",
                        help="商品名称（不能含「测试」字样；不传则自动生成 '<房型名>-<时间戳>'）")
    g_opt.add_argument(
        "--set", action="append", default=[], metavar="KEY=VALUE",
        help="覆盖任意字段，可多次使用。KEY 为点分路径，VALUE 自动解析类型。\n"
             "例：--set goodsDetailList.0.goodsBaseInfo.typeLimitValue=6\n"
             "    --set goodsDetailList.0.rpInfo.rpHourlyRoomUseModel.normalRule.receiveTimeStart=00:00",
    )

    # ── 执行控制 ──────────────────────────────────────────────────────────
    g_exec = parser.add_argument_group("执行控制")
    g_exec.add_argument("--swimlane",      default="",   help="泳道名称（不传=主干）")
    g_exec.add_argument("--dry-run",       action="store_true", help="只打印最终参数，不执行")
    g_exec.add_argument("--skip-constraints", action="store_true",
                         help="跳过本地约束校验（谨慎使用）")
    g_exec.add_argument("--poll-timeout",  type=int, default=60,
                         help="等待创建完成的最长秒数（默认60秒）")

    # ── 帮助类命令 ────────────────────────────────────────────────────────
    g_help = parser.add_argument_group("帮助命令")
    g_help.add_argument("--show-template", action="store_true",
                         help="打印模板默认值（templates/hourly-default.json）并退出")
    g_help.add_argument("--show-schema",   action="store_true",
                         help="打印字段 schema（schema.json，含含义/枚举/约束）并退出")

    args = parser.parse_args()

    # ── 帮助类命令处理 ────────────────────────────────────────────────────
    if args.show_template:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            print(f.read())
        sys.exit(0)

    if args.show_schema:
        _show_schema()
        sys.exit(0)

    print("═" * 60)
    print("  钟点房创建（直调研发级 RPC）")
    print(f"  供应商: {args.partner_id}  门店: {args.poi_id}")
    print(f"  房型: {args.room_id} ({args.room_name})")
    print(f"  合同: {args.contract_no or '（未传入，接口可能报「合同不能为空」）'}")
    print(f"  泳道: {args.swimlane or '主干'}")
    print("═" * 60)

    # ── 1. 加载模板并填充占位符 ────────────────────────────────────────────
    params = load_template(
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        room_id=args.room_id,
        room_name=args.room_name,
        goods_name=args.goods_name,
    )

    # ── 2. 解析并应用 --set 覆盖参数 ──────────────────────────────────────
    # 优先注入 --contract-no（与全日房保持一致，通过 --set 路径写入）
    overrides = {}
    if args.contract_no:
        overrides["goodsDetailList.0.goodsBaseInfo.contractNo"] = args.contract_no

    for item in args.set:
        if "=" not in item:
            print(f"❌ [参数错误] --set 格式必须为 KEY=VALUE，收到：{item}", file=sys.stderr)
            sys.exit(1)
        k, v = item.split("=", 1)
        overrides[k.strip()] = _try_parse_value(v.strip(), k.strip())

    if overrides:
        print(f"[覆盖参数] {json.dumps(overrides, ensure_ascii=False)}")
        apply_overrides(params, overrides)

    # ── 3. 约束校验 ────────────────────────────────────────────────────────
    if not args.skip_constraints:
        try:
            validate_constraints(params)
            print("[约束校验] ✅ 通过")
        except ConstraintError as e:
            print(f"[约束校验失败]{e}", file=sys.stderr)
            print("[提示] 使用 --skip-constraints 跳过校验（谨慎使用）", file=sys.stderr)
            sys.exit(1)

    # ── 打印最终参数 ───────────────────────────────────────────────────────
    print(f"[最终参数]\n{json.dumps(params, ensure_ascii=False, indent=2)}")

    if args.dry_run:
        print("\n[dry-run] 模拟完成，未实际执行。")
        return

    # ── 4. 调用接口 ────────────────────────────────────────────────────────
    iface = _load_interface()
    result = iface.call_raw(
        params=params,
        swimlane=args.swimlane,
        dry_run=False,
    )
    print(f"[RPC 原始返回]\n{json.dumps(result, ensure_ascii=False, indent=2)}")

    # ── 5. 处理异步结果 ───────────────────────────────────────────────────
    uuid_val = None
    data = result.get("data")
    if isinstance(data, str) and data:
        uuid_val = data
        print(f"\n📋 任务 UUID: {uuid_val}")
        print(f"   接口为异步，正在等待完成（最多 {args.poll_timeout} 秒）...")
    elif isinstance(data, dict):
        goods_id = data.get("goodsId") or data.get("productId")
        if goods_id:
            _print_success(args.partner_id, args.poi_id, args.room_id,
                           args.room_name, str(goods_id), args.swimlane)
            return

    goods_id = ""
    if uuid_val:
        goods_id = iface.wait_for_goods_id(
            partner_id=args.partner_id,
            poi_id=args.poi_id,
            uuid=uuid_val,
            swimlane=args.swimlane,
            timeout_sec=args.poll_timeout,
        )

    _print_success(args.partner_id, args.poi_id, args.room_id,
                   args.room_name, goods_id, args.swimlane)

    # ── 6. 恢复上线（含库存不足自动补库存重试）────────────────────────────
    _online_with_inventory_retry(
        iface=iface,
        params=params,
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        room_id=args.room_id,
        goods_id=goods_id,
        swimlane=args.swimlane,
    )


if __name__ == "__main__":
    main()

