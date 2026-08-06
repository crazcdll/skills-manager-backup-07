#!/usr/bin/env python3
"""
场景层：全日房创建（直调研发级 MeGoodsFacade#batchCreateGoods）
入口：factory/fullday/create-fullday.py

=== 设计范式===

1. 加载模板：从 templates/fullday-default.json 读取完整、已验证的默认参数
2. 替换占位符：__PARTNER_ID__ / __POI_ID__ / __ROOM_ID__ / __ROOM_NAME__ / __TODAY__ 等
3. --set 覆盖：支持点分路径覆盖任意字段，如 --set goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num=1
4. 约束校验：在调用 RPC 前拦截参数错误，给出可执行修复提示
5. 调用接口：直接将 dict 传给 interface 层，无参数重新组装

=== 取消规则说明（rpCancelModel）===

rpCancelModel 结构：
  normalRule  = 平日取消政策（周一~周五）
  weekendRule = 周末取消政策（周六、周日），不区分时传 null
  updateType  = 固定传 0

cancelItemType 枚举：
  0 = 不可取消
  1 = 可取消（免费或收费）；需同时传 moveUpCancelDays 和 moveUpCancelHour

=== 早餐规则说明（rpBreakFastModel）===

rpBreakFastModel 结构：
  normalRule  = 平日早餐份数
  weekendRule = 周末早餐份数，不区分时传 null
  updateType  = 固定传 0

num 枚举：0=无早餐  1=单份  2=双份  5=五份（其他正整数均支持）

⚠️ 周末差异用 weekendRule，不要用 specialRules：
  weekendRule = 永久性的周末（每周六日）规则，写法简单
  specialRules = 仅在指定日期范围内生效的特殊规则，写法复杂，一般不需要

=== 常用示例 ===

# 1. 普通全日房（不可取消，无早餐）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房"

# 2. 含单早（平日/周末相同）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num=1

# 3. 含双早（平日/周末相同）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num=2

# 4. 平日单早 + 周末双早（用 weekendRule）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num=1 \\
  --set 'goodsDetailList.0.rpInfo.rpBreakFastModel.weekendRule={"effectiveTimes":null,"num":2}'

# 5. 免费取消（平日/周末相同，当天23:59前可取消）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=1 \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelDays=0 \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelHour=23:59:00

# 6. 平日不可取消 + 周末入住前18:00免费取消（用 weekendRule）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=0 \\
  --set 'goodsDetailList.0.rpInfo.rpCancelModel.weekendRule={"cancelItemType":1,"moveUpCancelDays":0,"moveUpCancelHour":"18:00:00"}'

# 7. 收费取消-单时段（入住前3天18:00前免费，此后至当天18:00前扣10%）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=1 \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelDays=3 \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelHour=18:00:00 \\
  --set 'goodsDetailList.0.rpInfo.rpCancelModel.normalRule.payCancelPeriodModels=[{"advanceDays":0,"advanceHour":"18:00:00","penaltyRate":10}]'

# 7b. 收费取消-多时段（入住前3天18:00前免费，当天18:00前扣10%，当天21:00前扣30%，之后不可取消）
# advanceHour/penaltyRate 第二段可按需修改
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=1 \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelDays=3 \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelHour=18:00:00 \\
  --set 'goodsDetailList.0.rpInfo.rpCancelModel.normalRule.payCancelPeriodModels=[{"advanceDays":0,"advanceHour":"18:00:00","penaltyRate":10},{"advanceDays":0,"advanceHour":"21:00:00","penaltyRate":30}]'

# 7c. 收费取消-自定义（入住前3天18:00前免费，此后至入住前N天18:00前扣10%，之后不可取消）
# advanceDays 可改（N=入住前N天，如 1=入住前1天，2=入住前2天）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=1 \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelDays=3 \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelHour=18:00:00 \\
  --set 'goodsDetailList.0.rpInfo.rpCancelModel.normalRule.payCancelPeriodModels=[{"advanceDays":1,"advanceHour":"18:00:00","penaltyRate":10}]'

# 8. 组合：平日不可取消+周末免费取消 + 平日单早+周末双早（已验证）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=0 \\
  --set 'goodsDetailList.0.rpInfo.rpCancelModel.weekendRule={"cancelItemType":1,"moveUpCancelDays":0,"moveUpCancelHour":"18:00:00"}' \\
  --set goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num=1 \\
  --set 'goodsDetailList.0.rpInfo.rpBreakFastModel.weekendRule={"effectiveTimes":null,"num":2}'

# 9. 修改价格（单位：分，200元=20000）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos.0.priceInfo.salePrice=30000

# 10. 现付担保产品
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.goodsBaseInfo.paymentType=1

# 11. 现付非担保产品（需传 arrivalHour）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.goodsBaseInfo.paymentType=2 \\
  --set goodsDetailList.0.rpInfo.rpGuaranteeModel.normalRule.isGuarantee=0 \\
  --set goodsDetailList.0.rpInfo.rpGuaranteeModel.normalRule.arrivalHour=14:00:00

# 12. 附近专享（3公里内）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.rpInfo.rpDisplayModel.normalRule.distanceRange=1

# 13. 仅美团渠道
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --set goodsDetailList.0.goodsBaseInfo.sellChannel=9

# 14. 泳道支持
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --swimlane user-zhangsan

# dry-run 模式（只打印最终参数不执行）
python3 factory/fullday/create-fullday.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --room-id 77671480 --room-name "标准大床房" \\
  --dry-run

# 查看完整参数 schema（字段说明/枚举/业务规则）
python3 factory/fullday/create-fullday.py --show-schema

# 查看模板默认值
python3 factory/fullday/create-fullday.py --show-template
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

TEMPLATE_PATH = os.path.join(_SCRIPT_DIR, "templates", "fullday-default.json")
SCHEMA_PATH   = os.path.join(_SCRIPT_DIR, "schema.json")

# ── 懒加载 interface 层 ────────────────────────────────────────────────────
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


def _cancel_label(cancel_rule: dict) -> str:
    """
    根据 rpCancelModel.normalRule 计算取消规则描述。

    cancelItemType=0 → 不可取消
    cancelItemType=1 →
      moveUpCancelDays=0 → 入住当天{HH:MM}前免费取消
      moveUpCancelDays>0 → 入住前{N}天{HH:MM}前免费取消
      若有 payCancelPeriodModels → 追加"-收费取消"
    """
    cancel_type = cancel_rule.get("cancelItemType", 0)
    if cancel_type == 0:
        return "不可取消"

    days = cancel_rule.get("moveUpCancelDays", 0)
    hour_str = cancel_rule.get("moveUpCancelHour", "")
    # 只取 HH:MM 部分（去掉秒）
    hm = ":".join(hour_str.split(":")[:2]) if hour_str else ""

    if days == 0:
        base = f"入住当天{hm}前免费取消" if hm else "入住当天免费取消"
    else:
        base = f"入住前{days}天{hm}前免费取消" if hm else f"入住前{days}天免费取消"

    if cancel_rule.get("payCancelPeriodModels"):
        base += "-收费取消"

    return base


def _build_names(room_name: str, params: dict) -> tuple:
    """
    根据 params 中的早餐/取消规则，自动拼接：
      rpCustomName → 标准价{时间戳}（随机，不含"测试"）

      境内：
        rpName    → {早餐描述}-{取消规则描述}-{rpCustomName}
        goodsName → {roomName}-{rpName}

      境外多人多价/同价（priceSameTag 非 null）：
        rpName    → 可入住{maxAdultAdmissibility}人-{早餐描述}-{取消规则描述}-{rpCustomName}
        goodsName → {rpCustomName}-{roomName}-最大可住{maxAdultAdmissibility}人-{早餐描述}-{取消规则描述}
        （priceAuditInfos.goodsNameList = roomName-rpName）

    返回 (goodsName, rpName, rpCustomName)
    """
    ts = int(time.time())
    rp_custom_name = f"标准价{ts}"

    # 读取早餐份数
    try:
        breakfast_num = (
            params["goodsDetailList"][0]["rpInfo"]["rpBreakFastModel"]["normalRule"]["num"]
        )
    except (KeyError, IndexError, TypeError):
        breakfast_num = 0

    # 读取取消规则
    try:
        cancel_normal_rule = (
            params["goodsDetailList"][0]["rpInfo"]["rpCancelModel"]["normalRule"]
        )
    except (KeyError, IndexError, TypeError):
        cancel_normal_rule = {}

    breakfast_part = _breakfast_label(breakfast_num)
    cancel_part = _cancel_label(cancel_normal_rule)

    # 判断是否境外多人多价/同价
    try:
        price_same_tag = params["goodsDetailList"][0]["goodsBaseInfo"].get("priceSameTag")
        max_adult = params["goodsDetailList"][0]["goodsBaseInfo"].get("maxAdultAdmissibility", 0) or 0
    except (KeyError, IndexError, TypeError):
        price_same_tag = None
        max_adult = 0

    if price_same_tag is not None:
        # 境外多人多价/同价命名规则（来自真实成功参数）：
        #   rpName    = 可入住N人-早餐-取消-rpCustomName
        #   goodsName = rpCustomName-roomName-最大可住N人-早餐-取消
        #   priceAuditInfos.goodsNameList = roomName-rpName（由 C8 约束自动构建）
        rp_name = f"可入住{max_adult}人-{breakfast_part}-{cancel_part}-{rp_custom_name}"
        goods_name = f"{rp_custom_name}-{room_name}-最大可住{max_adult}人-{breakfast_part}-{cancel_part}"
    else:
        # 境内命名规则
        rp_name = f"{breakfast_part}-{cancel_part}-{rp_custom_name}"
        goods_name = f"{room_name}-{rp_name}"

    return goods_name, rp_name, rp_custom_name


# ══════════════════════════════════════════════════════════════════════════
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
    contract_no: str = None,
) -> dict:
    """
    加载 fullday-default.json 模板，替换所有占位符，返回完整的请求 dict。

    占位符说明：
        __PARTNER_ID__       → int(partner_id)
        __POI_ID__           → int(poi_id)
        __ROOM_ID__          → int(room_id)
        __ROOM_NAME__        → room_name
        __GOODS_NAME__       → goods_name（空时用临时占位符，main() 中会在 --set 覆盖后重新计算）
        __TODAY__            → 今天日期
        __TWO_YEARS_LATER__  → 两年后日期
        __CONTRACT_NO__      → contract_no（合同号，不传时替换为 null）

    注意：__RP_NAME__ / __RP_CUSTOM_NAME__ / __GOODS_NAME__ 由 main() 在 --set 覆盖后
    根据早餐份数+取消规则自动拼接（_build_names），不在此处填入。
    """
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = json.load(f)

    replacements = {
        "__PARTNER_ID__":       int(partner_id),
        "__POI_ID__":           int(poi_id),
        "__ROOM_ID__":          int(room_id),
        "__ROOM_NAME__":        room_name,
        "__GOODS_NAME__":       goods_name,    # 非空时直接用用户传入值；空时保留占位符
        "__RP_NAME__":          goods_name,    # 同上，main() 中 goods_name 空时会覆盖
        "__RP_CUSTOM_NAME__":   goods_name,    # 同上
        "__TODAY__":            _today(),
        "__TWO_YEARS_LATER__":  _two_years_later(),
        "__CONTRACT_NO__":      contract_no,  # None → JSON null
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
        _set_nested(d, "goodsDetailList.0.goodsBaseInfo.goodsName", "大床房")
        _set_nested(d, "goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos.0.priceInfo.salePrice", "30000")
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

    ⚠️ 当值以 { 或 [ 开头但 json.loads 失败时，打印警告而非静默回退为字符串——
       静默回退会导致 RPC 收到字符串类型，服务端报反序列化错误（MismatchedInputException）。
       常见原因：shell 引号嵌套导致转义符混入，推荐改用环境变量传值：
           PRICE_JSON='{"key":"val"}' && --set "path=$PRICE_JSON"
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
                print(
                    f"\n⚠️  [--set {key}] 值以 '{v[0]}' 开头，疑似 JSON，但解析失败！\n"
                    f"   将作为字符串传入，可能导致 RPC 报 MismatchedInputException。\n"
                    f"   建议改用环境变量方式传整块 JSON，例如：\n"
                    f"   JSON_VAL='{{...}}' && python3 ... --set \"{key}=$JSON_VAL\"",
                    file=sys.stderr,
                )
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
            "     商品名  → --set goodsDetailList.0.goodsBaseInfo.goodsName=\"含单早\"\n"
            "     售价    → --set goodsDetailList.0.priceInfo.unifiedDatePriceInfos"
            ".weekPriceInfos.0.priceInfo.salePrice=30000\n"
            "     早餐    → --set goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num=1\n"
            "\n   完整字段说明见 factory/fullday/schema.json 或 --show-schema\n",
            file=sys.stderr,
        )
        sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════
# 名称自动拼接
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
      C0a 商品名称不能超过99个字符（后端 MccConstants.MAX_GOODS_NAME_LENGTH=99）
      C0b 商品名称不能含4字节特殊字符（emoji等，后端 SPECIAL_CHAR 正则拦截）
      C1  售价必须为正数（单位：分）
      C2  全日房必须包含 rpBreakFastModel（num=0~2）
      C3  取消政策：cancelItemType=1（可取消）时必须传 moveUpCancelDays 和 moveUpCancelHour
      C4  paymentType=1（现付担保）时必须设置 rpGuaranteeModel
      C5  paymentType=2（现付非担保）时 arrivalHour 必须在 rpGuaranteeModel 中设置
      C6  预订规则：latestBookingDays / earliestBookingDays 必须 >= -1；且同时>0时 latest<=earliest
      C7  境外多人多价/同价约束：
          - priceSameTag 传了（非 null）时，priceFactorInfos 不能为 null（必须按档位传数组）
      C7b 境外多人多价/同价（priceSameTag 非 null）时，自动补全 rpBookingModel：
          - 若 rpBookingModel 为 null，从 goodsBaseInfo.maxAdultAdmissibility 自动补全
          - maxAdultAdmissibility 未设置时报错提示
      C8  境外多人多价/同价（priceSameTag 非 null）+ 卖价模式（priceChangeMode=8）时：
          - 自动构建顶层 priceAuditInfos（若用户未传），否则后端报「产品进审核，但没有提交审核信息」
          - goodsNameList 格式（境外专用）：rpCustomName-roomName-最大可住N人-早餐描述-取消规则描述
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

    # C0b：商品名称特殊字符（4字节字符，如 emoji，后端 SPECIAL_CHAR=[^\u0000-\uFFFF] 正则拦截）
    if goods_name:
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
                    f"C1: salePrice={sale_price} 非法，必须 > 0（单位：分，200元=20000）\n"
                    f"   修复：--set goodsDetailList.0.priceInfo.unifiedDatePriceInfos"
                    f".weekPriceInfos.0.priceInfo.salePrice=20000"
                )
        except (ValueError, TypeError):
            pass

    # C2：全日房必须包含 rpBreakFastModel
    rp_breakfast = rp.get("rpBreakFastModel")
    if rp_breakfast is None:
        errors.append(
            "C2: 全日房必须传 rpBreakFastModel（不传会触发「系统内部错误」）\n"
            "   模板已包含默认值（num=0，无早餐），请勿将此字段设为 null\n"
            "   修复：--set goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num=0"
        )

    # C3：可取消时必须传 moveUpCancelDays 和 moveUpCancelHour
    # 后端 ValidateGoodsServiceImpl.validateRpCancelRule：goodsType=1 且 cancelItemType=1 时校验 moveUpCancelHour 不能为空
    cancel_model = (rp.get("rpCancelModel") or {}).get("normalRule") or {}
    cancel_type = cancel_model.get("cancelItemType")
    if cancel_type == 1:
        if cancel_model.get("moveUpCancelDays") is None:
            errors.append(
                "C3: cancelItemType=1（可取消）时必须传 moveUpCancelDays（当天可取消传 0）\n"
                "   修复：--set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelDays=0"
            )
        if not cancel_model.get("moveUpCancelHour"):
            errors.append(
                "C3: cancelItemType=1（可取消）时必须传 moveUpCancelHour（全日房必填，后端拦截）\n"
                "   修复：--set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelHour=\"23:59:00\""
            )

    # C4：现付担保时自动构建 rpGuaranteeModel（若未设置）
    if payment_type == 1 and rp.get("rpGuaranteeModel") is None:
        # 自动填充默认的整单担保模型，不报错（与 interface 层 call() 行为对齐）
        rp["rpGuaranteeModel"] = {
            "normalRule": {
                "isGuarantee": 1,
                "guaranteeType": 2,
            },
            "updateType": 0,
        }
        # 同步回 gd（_get_val 取的是引用，rp 已是 gd["rpInfo"] 的引用，无需再赋值）
        print("[自动补全] paymentType=1（现付担保）已自动设置 rpGuaranteeModel（整单担保）")

    # C5：现付非担保时 arrivalHour 必填，且自动补全默认值
    if payment_type == 2:
        if rp.get("rpGuaranteeModel") is None:
            # 自动填充非担保模型
            rp["rpGuaranteeModel"] = {
                "normalRule": {
                    "isGuarantee": 0,
                    "guaranteeType": 2,
                    "arrivalHour": "14:00:00",
                },
                "updateType": 0,
            }
            print("[自动补全] paymentType=2（现付非担保）已自动设置 rpGuaranteeModel（arrivalHour=14:00:00）")
        else:
            guarantee_model = (rp.get("rpGuaranteeModel") or {}).get("normalRule") or {}
            if not guarantee_model.get("arrivalHour"):
                errors.append(
                    "C5: paymentType=2（现付非担保）时 arrivalHour 必填\n"
                    "   修复：--set goodsDetailList.0.rpInfo.rpGuaranteeModel.normalRule.arrivalHour=\"14:00:00\""
                )

    # C6：预订规则约束（后端 ValidateGoodsServiceImpl.validRpEarlyBooking）
    # latestBookingDays / earliestBookingDays 必须 >= -1
    # 当两者都 > 0 时，latestBookingDays（最晚=最少提前）不能大于 earliestBookingDays（最早=最多提前）
    early_booking = (rp.get("rpEarlyBookingModel") or {}).get("normalRule") or {}
    latest_days = early_booking.get("latestBookingDays")   # 至少提前N天
    earliest_days = early_booking.get("earliestBookingDays")  # 至多提前N天
    if latest_days is not None:
        try:
            ld = int(latest_days)
            if ld < -1:
                errors.append(
                    f"C6: latestBookingDays={ld} 非法（必须 >= -1，-1=不限制）\n"
                    f"   修复：--set goodsDetailList.0.rpInfo.rpEarlyBookingModel.normalRule.latestBookingDays=-1"
                )
        except (ValueError, TypeError):
            pass
    if earliest_days is not None:
        try:
            ed = int(earliest_days)
            if ed < -1:
                errors.append(
                    f"C6: earliestBookingDays={ed} 非法（必须 >= -1，-1=不限制）\n"
                    f"   修复：--set goodsDetailList.0.rpInfo.rpEarlyBookingModel.normalRule.earliestBookingDays=-1"
                )
        except (ValueError, TypeError):
            pass
    if latest_days is not None and earliest_days is not None:
        try:
            ld, ed = int(latest_days), int(earliest_days)
            # 两者都 > 0 时，latestBookingDays（最少提前）必须 <= earliestBookingDays（最多提前）
            if ld > 0 and ed > 0 and ld > ed:
                errors.append(
                    f"C6: latestBookingDays={ld}（最少提前）不能大于 earliestBookingDays={ed}（最多提前）\n"
                    f"   示例：latestBookingDays=1（至少提前1天），earliestBookingDays=7（最多提前7天）\n"
                    f"   修复：调整两者使 latestBookingDays <= earliestBookingDays"
                )
        except (ValueError, TypeError):
            pass

    # C7b：境外多人多价/同价（priceSameTag 非 null）时，rpInfo.rpBookingModel 必须传
    #      包含 maxAdultAdmissibility，后端用此字段确定价格档位数量
    #      若用户未设置 rpBookingModel，自动从 goodsBaseInfo.maxAdultAdmissibility 补全
    price_same_tag_check = base.get("priceSameTag")
    if price_same_tag_check is not None:
        max_adult = base.get("maxAdultAdmissibility")
        existing_booking_model = rp.get("rpBookingModel")
        if existing_booking_model is None and max_adult is not None:
            rp["rpBookingModel"] = {
                "normalRule": {
                    "maxAdultAdmissibility": int(max_adult),
                },
                "updateType": 0,
            }
            print(
                f"[自动补全] 境外多人多价/同价（priceSameTag={price_same_tag_check}）已自动设置 rpBookingModel\n"
                f"  maxAdultAdmissibility = {max_adult}"
            )
        elif existing_booking_model is None and max_adult is None:
            errors.append(
                "C7b: 境外多人多价/同价（priceSameTag 已设置）时，必须同时设置 maxAdultAdmissibility\n"
                "   修复：--set goodsDetailList.0.goodsBaseInfo.maxAdultAdmissibility=5\n"
                "   说明：maxAdultAdmissibility 决定 priceFactorInfos 的档位数量（如5人则需1~5档）"
            )

    # C8：境外多人多价/同价（priceSameTag 非 null）+ 卖价模式（priceChangeMode=8）时
    #     必须提供顶层 priceAuditInfos，否则后端会报「产品进审核，但没有提交审核信息」
    #     境外商品 goodsNameList 格式（与境内不同！）：
    #       rpCustomName-roomName-最大可住N人-早餐描述-取消规则描述
    price_same_tag = base.get("priceSameTag")
    price_change_mode = base.get("priceChangeMode", 8)
    if price_same_tag is not None and price_change_mode == 8:
        # 取当前 priceAuditInfos
        current_audit = params.get("priceAuditInfos")
        if not current_audit:
            # 自动构建 priceAuditInfos
            # 境外商品 goodsNameList 格式（来自真实成功参数）：roomName-rpName
            #   rpName = 可入住N人-早餐描述-取消规则描述-rpCustomName
            room_info = gd.get("roomInfo") or {}
            _room_name = room_info.get("roomName", "")
            _rp_base = rp.get("rpBaseModel") or {}
            _rp_custom_name = _rp_base.get("rpCustomName", "") or ""
            _max_adult = base.get("maxAdultAdmissibility", 0)
            # 早餐描述
            try:
                _bf_num = params["goodsDetailList"][0]["rpInfo"]["rpBreakFastModel"]["normalRule"]["num"]
            except (KeyError, IndexError, TypeError):
                _bf_num = 0
            _bf_label = _breakfast_label(_bf_num)
            # 取消规则描述
            try:
                _cancel_rule = params["goodsDetailList"][0]["rpInfo"]["rpCancelModel"]["normalRule"]
            except (KeyError, IndexError, TypeError):
                _cancel_rule = {}
            _cancel_label_str = _cancel_label(_cancel_rule)
            # goodsNameList = roomName-rpName
            # rpName = 可入住N人-早餐-取消-rpCustomName（境外专用格式）
            _rp_name_for_audit = f"可入住{_max_adult}人-{_bf_label}-{_cancel_label_str}-{_rp_custom_name}"
            _full_name = f"{_room_name}-{_rp_name_for_audit}"
            auto_audit = [
                {
                    "goodsNameList": [_full_name],
                    "materials": [],
                    "reason": "其他",
                    "type": "其它：需备注",
                }
            ]
            params["priceAuditInfos"] = auto_audit
            print(
                f"[自动补全] 境外多人多价/同价（priceSameTag={price_same_tag}）已自动构建 priceAuditInfos\n"
                f"  goodsNameList = [\"{_full_name}\"]\n"
                f"  （格式：roomName-rpName，rpName=可入住N人-早餐-取消-rpCustomName）"
            )

    if errors:
        msg = "\n".join(f"  {e}" for e in errors)
        raise ConstraintError(f"\n参数约束校验失败（共 {len(errors)} 项）：\n{msg}\n")


# ══════════════════════════════════════════════════════════════════════════
# 主逻辑
# ══════════════════════════════════════════════════════════════════════════

_INV_ERROR_KEYWORD = "最近90天内至少30天同时有价格和库存"


def _today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def _inv_end_date() -> str:
    """
    库存日期上限：服务端限制 endDate 只能在昨天至未来2年内（不含边界）。
    取 today + 2年 - 1天。
    """
    today = datetime.date.today()
    try:
        end = today.replace(year=today.year + 2) - datetime.timedelta(days=1)
    except ValueError:
        end = today.replace(year=today.year + 2, month=3, day=1) - datetime.timedelta(days=1)
    return end.strftime("%Y-%m-%d")


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

    注意：batchUpdateInventory 不会强制覆盖 invSwitch，传 invSwitch=1 会真正开房。
    """
    ops = iface._load_ops_interface()

    def _try_online(gid: str) -> tuple:
        """尝试上线，返回 (success: bool, reason: str)"""
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

    # 判断是否为境外多人多价/同价（需在上线前主动做一次 BD 改价审核）
    _price_same_tag = None
    try:
        _price_same_tag = params["goodsDetailList"][0]["goodsBaseInfo"].get("priceSameTag")
    except (KeyError, IndexError, TypeError):
        pass

    # ── Step 6.5（前置）：境外多人多价/同价 → 主动触发 BD 改价审核 ──────────
    # 原因：境外多人多价在创建时提交了 priceAuditInfos，后端会将商品置为「待审核」状态，
    #       必须先审核通过才能上线，否则上线会因库存/价格检查而失败。
    #       主动提前做而不是等上线失败后再补，避免浪费一次上线请求。
    if _price_same_tag is not None:
        print(f"\n── Step 6.5: BD 改价审核（operation_type=2，audit_status=3）──────")
        print(f"  原因：境外多人多价/同价商品（priceSameTag={_price_same_tag}）须先通过改价审核再上线")
        try:
            ops.call(operation_type=2, product_id=int(goods_id), audit_status=3)
            print("  ✅ BD 改价审核通过")
        except Exception as e:
            print(f"  ⚠️ BD 改价审核失败: {e}")
            print(f"  💡 可手动执行：python3 factory/ops/cache-refresh-audit.py --op 2 --product-id {goods_id} --audit-status 3")

    # ── 第一次尝试上线 ────────────────────────────────────────────────────
    success, reason = _try_online(goods_id)
    if success:
        _do_cache_refresh(goods_id)
        return

    # ── 上线失败后兜底：若原因含"审核"字样（非库存问题），再补一次审核重试 ────
    _AUDIT_KEYWORDS = ("审核", "audit", "price audit")
    _audit_in_reason = any(kw in reason.lower() for kw in _AUDIT_KEYWORDS)
    if _audit_in_reason and _INV_ERROR_KEYWORD not in reason:
        print(f"\n── Step 6.5（兜底）: 上线失败含审核字样，重新执行 BD 改价审核 ──────")
        try:
            ops.call(operation_type=2, product_id=int(goods_id), audit_status=3)
            print("  ✅ BD 改价审核通过，重新尝试上线...")
        except Exception as e:
            print(f"  ⚠️ BD 改价审核失败: {e}")
            print(f"  💡 可手动执行：python3 factory/ops/cache-refresh-audit.py --op 2 --product-id {goods_id} --audit-status 3")
            _do_cache_refresh(goods_id)
            return
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

    # 取价格有效期作为库存日期范围，但不能超过2年-1天
    try:
        dates = params["goodsDetailList"][0]["priceInfo"]["unifiedDatePriceInfos"]["dates"]
        start_date = dates[0]["startDate"]
        end_date   = dates[0]["endDate"]
        # 服务端限制 endDate 不能超过今天+2年，做截断保护
        max_end = _inv_end_date()
        if end_date > max_end:
            end_date = max_end
    except (KeyError, IndexError, TypeError):
        start_date = _today()
        end_date   = _inv_end_date()

    print(f"  [库存修改] 房型={room_id}，日期范围 {start_date} ~ {end_date}")
    try:
        upd_mod = _load_update_inventory()
        upd_mod.open_and_set_inventory(
            partner_id=partner_id,
            poi_id=poi_id,
            day_room_ids=[int(room_id)],   # 全日房用 day_room_ids
            start_date=start_date,
            end_date=end_date,
            inv_switch=1,           # 开房
            count_type=1121,        # 设置库存总量+预留房绝对量（初次/已有均可）
            limit_change_value=299,
            count=1,
            swimlane=swimlane,
        )
        print("  ✅ 库存修改成功，重新尝试上线...")
    except Exception as e:
        print(f"  ⚠️ 库存修改失败: {e}")
        print("  💡 可手动执行：python3 factory/inventory/update-inventory.py"
              f" --partner-id {partner_id} --poi-id {poi_id}"
              f" --day-room-ids {room_id}"
              f" --start-date {start_date} --end-date {end_date}"
              f" --inv-switch 1 --limit-change-value 299")
        _do_cache_refresh(goods_id)
        return

    # 库存修改成功后重新尝试上线
    success2, reason2 = _try_online(goods_id)
    if not success2:
        print(f"  ⚠️ 补库存后仍上线失败: {reason2}（可在 MTA 手动操作）")
    _do_cache_refresh(goods_id)


def _print_success(partner_id: str, poi_id: str, room_id: int,
                   room_name: str, goods_id: str, swimlane: str) -> None:
    print("\n" + "═" * 60)
    print("  ✅ 全日房创建成功")
    print("═" * 60)
    print(f"  商品ID (goodsId) : {goods_id or '（异步处理中，请等待）'}")
    print(f"  供应商ID         : {partner_id}")
    print(f"  门店ID           : {poi_id}")
    print(f"  房型ID           : {room_id}")
    print(f"  房型名称         : {room_name}")
    print(f"  泳道             : {swimlane or '主干'}")
    print("═" * 60)


def _show_schema():
    # 境外多人多价帮助文本（含单引号，单独拼接避免三引号截断）
    print("""=== 全日房创建（create-fullday）参数说明 ===

【必填参数】
  --partner-id    STR    供应商ID（partnerId，由 factory/infra/create-partner.py 创建）
  --poi-id        STR    门店ID（mtPoiId，由 factory/infra/create-poi.py 创建）
  --room-id       INT    逻辑房型ID（roomId，由 factory/infra/create-room.py 创建）
  --room-name     STR    逻辑房型名称（需与 roomId 对应，如：标准大床房）

【可选参数】
  --goods-name    STR    商品名称（不能含「测试」字样；不传则自动生成 '<房型名>-<时间戳>'）
  --set KEY=VALUE        覆盖任意字段（点分路径），可多次使用

【--set 常用字段（点分路径）】
  取消政策：
    goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType
      0=不可取消（默认）  1=可取消
    goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelDays
      提前取消天数（cancelItemType=1 时必填，当天取消传 0）
    goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelHour
      取消截止时间（cancelItemType=1 时必填，如 23:59:00）

  早餐：
    goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num
      0=无早餐（默认）  1=含单早  2=含双早  5=含五早（其他正整数均支持，名称自动拼接为「含N早」）

  付款类型：
    goodsDetailList.0.goodsBaseInfo.paymentType
      0=预付（默认）  1=现付担保  2=现付非担保

  售价（单位：分，200元=20000）：
    goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos.0.priceInfo.salePrice

  合同编号：
    goodsDetailList.0.goodsBaseInfo.contractNo

  销售渠道：
    goodsDetailList.0.goodsBaseInfo.sellChannel
      9=仅美团渠道

  附近专享：
    goodsDetailList.0.rpInfo.rpDisplayModel.normalRule.distanceRange
      1=3公里内专享

【境外多人多价/同价（--set 联动，三个字段必须同时设置）】
  ① goodsBaseInfo.priceSameTag

【境外产品价格模式（提示）】
  境外产品价格模式定义在 VPOI 上，需在创建产品前于 W8 基础实体准备阶段
  通过工具928 切换（见 factory/infra/switch-price-mode.py --overseas），
  本脚本不负责价格模式切换，仅负责创建产品。
  ⚠️ 若 VPOI 已切换为底价模式，创建产品时价格字段须用 basePrice（而非
     salePrice），并自行通过 --set 传入 priceChangeMode=9 /
     priceRecodeWay=2 / expectPriceChangeMode=9 / priceInfo.priceRecordWay=2
     等底价相关字段，否则可能报"参数错误"。

【执行控制】
  --swimlane      STR    泳道名称（不传=主干）
  --dry-run              只打印最终参数，不执行
  --show-template        打印模板默认值（templates/fullday-default.json）
  --skip-constraints     跳过本地约束校验（谨慎使用）

【本地约束校验（自动执行）】
  C0  商品名称不能含「测试」字样
  C1  售价必须 > 0（单位：分）
  C2  必须包含 rpBreakFastModel（默认 num=0）
  C3  cancelItemType=1 时必须传 moveUpCancelDays 和 moveUpCancelHour
  C4/C5  现付担保/非担保时自动补全 rpGuaranteeModel

【使用示例】
  # 不可取消，无早餐（最简）
  python3 factory/fullday/create-fullday.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --room-id 77671480 --room-name "标准大床房"

  # 含单早 + 免费取消
  python3 factory/fullday/create-fullday.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --room-id 77671480 --room-name "标准大床房" \\
    --set goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num=1 \\
    --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.cancelItemType=1 \\
    --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelDays=0 \\
    --set goodsDetailList.0.rpInfo.rpCancelModel.normalRule.moveUpCancelHour=23:59:00

  # 现付担保（paymentType=1）
  python3 factory/fullday/create-fullday.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --room-id 77671480 --room-name "标准大床房" \\
    --set goodsDetailList.0.goodsBaseInfo.paymentType=1
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
        description="全日房创建（直调研发级 RPC：MeGoodsFacade#batchCreateGoods）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── 必填参数 ──────────────────────────────────────────────────────────
    g_req = parser.add_argument_group("必填参数")
    g_req.add_argument("--partner-id", required=True,         help="供应商ID（partnerId）")
    g_req.add_argument("--poi-id",     required=True,         help="门店ID（mtPoiId）")
    g_req.add_argument("--room-id",    required=True, type=int, help="逻辑房型ID（roomId）")
    g_req.add_argument("--room-name",  required=True,         help="逻辑房型名称（如：标准间）")

    # ── 可选参数 ──────────────────────────────────────────────────────────
    g_opt = parser.add_argument_group("可选参数")
    g_opt.add_argument("--goods-name", default="",
                        help="商品名称（不能含「测试」字样；不传则根据早餐+取消规则自动拼接）")
    g_opt.add_argument(
        "--set", action="append", default=[], metavar="KEY=VALUE",
        help="覆盖任意字段，可多次使用。KEY 为点分路径，VALUE 自动解析类型。\n"
             "例：--set goodsDetailList.0.rpInfo.rpBreakFastModel.normalRule.num=1\n"
             "    --set goodsDetailList.0.goodsBaseInfo.sellChannel=9",
    )

    # ── 执行控制 ──────────────────────────────────────────────────────────
    g_exec = parser.add_argument_group("执行控制")
    g_exec.add_argument("--swimlane",      default="",   help="泳道名称（不传=主干）")
    g_exec.add_argument("--dry-run",       action="store_true", help="只打印最终参数，不执行")
    g_exec.add_argument("--skip-constraints", action="store_true",
                         help="跳过本地约束校验（谨慎使用）")
    g_exec.add_argument("--poll-timeout",  type=int, default=120,
                         help="等待创建完成的最长秒数（默认120秒）")

    # ── 帮助类命令 ────────────────────────────────────────────────────────
    g_help = parser.add_argument_group("帮助命令")
    g_help.add_argument("--show-template", action="store_true",
                         help="打印模板默认值（templates/fullday-default.json）并退出")
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
    print("  全日房创建（直调研发级 RPC）")
    print(f"  供应商: {args.partner_id}  门店: {args.poi_id}")
    print(f"  房型: {args.room_id} ({args.room_name})")
    print(f"  泳道: {args.swimlane or '主干'}")
    print("═" * 60)

    # ── 1. 加载模板并填充占位符 ────────────────────────────────────────────
    # goods_name 为空时先不替换名称占位符（保持空字符串），等 --set 覆盖后再自动拼接
    params = load_template(
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        room_id=args.room_id,
        room_name=args.room_name,
        goods_name=args.goods_name,
    )

    # ── 2. 解析并应用 --set 覆盖参数 ──────────────────────────────────────
    overrides = {}
    for item in args.set:
        if "=" not in item:
            print(f"❌ [参数错误] --set 格式必须为 KEY=VALUE，收到：{item}", file=sys.stderr)
            sys.exit(1)
        k, v = item.split("=", 1)
        parsed = _try_parse_value(v.strip(), k.strip())
        overrides[k.strip()] = parsed

    if overrides:
        # 打印覆盖参数，标注每个值的实际解析类型，便于提前发现 JSON 解析失败
        print("[覆盖参数]")
        for _k, _parsed in overrides.items():
            _type_tag = type(_parsed).__name__
            if isinstance(_parsed, (dict, list)):
                _preview = json.dumps(_parsed, ensure_ascii=False)
                if len(_preview) > 80:
                    _preview = _preview[:77] + "..."
                print(f"  {_k} = ({_type_tag}) {_preview}")
            else:
                print(f"  {_k} = ({_type_tag}) {_parsed}")
        apply_overrides(params, overrides)

    # ── 2b. 自动拼接名称（--set 覆盖后，基于最终早餐/取消规则计算）────────
    # 判断用户是否手动传了名称相关参数
    _user_set_name = any(
        k.strip().endswith("goodsName") or k.strip().endswith("rpName") or k.strip().endswith("rpCustomName")
        for k in overrides
    )
    # 检测是否为境外多人多价/同价场景（priceSameTag 非 null）
    _gd0 = params["goodsDetailList"][0]
    _is_overseas_multi = _gd0.get("goodsBaseInfo", {}).get("priceSameTag") is not None

    # 条件：用户未手动指定 rpName/rpCustomName，且为境外多人多价场景时，
    # 无论是否传了 --goods-name，都强制自动生成带描述的 rpName/rpCustomName，
    # 并将 goodsName 设为 roomName-rpName（后端 goodsNameList 匹配格式）。
    # 原因：境外多人多价 priceAuditInfos.goodsNameList 必须是 roomName-rpName，
    # 若 rpName=goodsName（无描述），则后端无法正确匹配审核信息。
    _need_auto_name = not _user_set_name and (not args.goods_name or _is_overseas_multi)

    if _need_auto_name:
        auto_goods_name, auto_rp_name, auto_rp_custom_name = _build_names(
            args.room_name, params
        )
        _gd0["goodsBaseInfo"]["goodsName"] = auto_goods_name
        _gd0["rpInfo"]["rpBaseModel"]["rpName"] = auto_rp_name
        _gd0["rpInfo"]["rpBaseModel"]["rpCustomName"] = auto_rp_custom_name
        if _is_overseas_multi and args.goods_name:
            print(
                f"[自动命名] 境外多人多价场景，忽略 --goods-name，自动生成规范名称\n"
                f"  （原因：priceAuditInfos.goodsNameList 必须是 roomName-rpName，\n"
                f"   rpName 必须含早餐/取消规则描述，才能被后端正确匹配审核信息）"
            )
        print(f"[自动命名]")
        print(f"  goodsName    = {auto_goods_name}")
        print(f"  rpName       = {auto_rp_name}")
        print(f"  rpCustomName = {auto_rp_custom_name}")

    # ── 2c. 境外多人多价自动补全 sellChannel + capacity ────────────────────
    if _is_overseas_multi:
        _base = _gd0.get("goodsBaseInfo", {})
        _max_adult = _base.get("maxAdultAdmissibility", 0) or 0
        # 境外商品销售渠道用 11（国际渠道），模板默认 15 需覆盖
        # 仅当用户未手动覆盖 sellChannel 时自动补全
        _user_set_sell_channel = any(
            "sellChannel" in k for k in overrides
        )
        if not _user_set_sell_channel:
            _gd0["goodsBaseInfo"]["sellChannel"] = 11
            print(f"[自动补全] 境外商品 sellChannel 自动设为 11（国际渠道）")
        # capacity 应与 maxAdultAdmissibility 一致，模板默认 0 需覆盖
        _user_set_capacity = any(
            "capacity" in k for k in overrides
        )
        if not _user_set_capacity and _max_adult > 0:
            _gd0["roomInfo"]["capacity"] = _max_adult
            print(f"[自动补全] 境外商品 roomInfo.capacity 自动设为 {_max_adult}（= maxAdultAdmissibility）")

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
        print(f"   接口为异步，正在等待完成（最多 {args.poll_timeout} 秒，每5秒一次）...")
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

    # ── 6+7. 上线（含库存不足自动补库存重试）+ 缓存刷新 ───────────────────
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

