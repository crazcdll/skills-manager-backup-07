#!/usr/bin/env python3
"""
基础实体 - 创建可上单客户（供应商）

工具：工具49（createHotelCustomer）
协议：HTTP POST DataUnity（异步，约1分钟就绪）
接口：createHotelCustomer

返回 partnerId + platformContractId，是创建房型、商品的前提。

⚠️ 工具49为异步接口，返回 partnerId 后供应商创建仍需约1分钟，
   后续创建房型时若失败请等待后重试。

使用方式：
  # 境内供应商（partnerType=2，绑定单门店）
  python3 create-partner.py --poi-id 1085918666109517

  # 境内女娲供应商（partnerType=9）
  python3 create-partner.py --poi-id 1085918666109517 --partner-type 9

  # 境外供应商（partnerType=3，绑定境外门店）
  python3 create-partner.py --poi-id 1234567890 --partner-type 3 --overseas

  # 通兑超团：供应商绑定多门店（逗号分隔）
  python3 create-partner.py --poi-id 111,222 --entity-type 2 --partner-type 2

  # 境外直连供应商（指定对接协议）
  python3 create-partner.py --poi-id 123 --partner-type 3 --overseas --cooperation-type 1 --overseas-protocol 2

  # 仅打印参数
  python3 create-partner.py --poi-id 123 --dry-run
"""

import argparse
import importlib.util as ilu
import json
import sys
import os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)

def _load_interface():
    spec = ilu.spec_from_file_location(
        "infra_interface",
        os.path.join(ROOT, "interface/infra/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_iface = _load_interface()
call_partner = _iface.call_partner

from scripts.du_runner import get_result, check_ok  # noqa
from scripts.utils import get_operator  # noqa


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        print("""工具49 - 创建可上单客户（供应商）[createHotelCustomer]

【必填参数】
  --poi-id <poiId>
      绑定的门店ID（create-poi.py 输出的 mtPoiId）
      多门店场景（通兑超团）用逗号分隔，如：111,222,333

【可选参数 - 核心】
  --partner-type <类型>          默认: 2
      客户类型枚举：
        2 = 可上单-境内非女娲纸质供应商（境内自采预付）  ← 默认
        3 = 可上单-境外非女娲纸质供应商
        4 = 不可上单-只创建供应商-境内女娲纸质供应商
        5 = 不可上单-只创建供应商-境内女娲电子供应商
        6 = 不可上单-只创建供应商-境外非女娲纸质供应商
        7 = 不可上单-只创建供应商-境内非女娲纸质供应商
        9 = 可上单-境内女娲普通供应商（境内代理预付，总店结算）
      加 --overseas 时建议同步传 --partner-type 3

  --entity-type <类型>           默认: 0
      实体类型枚举：
        0 = 酒店集团  ← 默认
        1 = 第三方渠道
        2 = 单体酒店（通兑超团必须用 2）
        3 = 多店老板

  --overseas
      Flag，加上则创建境外供应商（建议配合 --partner-type 3 使用）

  --partner-name <名称>          默认: <mis>可上单客户
      供应商名称

  --currency <币种>              默认: CNY
      结算币种，境外可改为：
        JPY=日圆, USD=美元, HKD=港币, KWD=科威特第纳尔, VND=越南盾

【可选参数 - 合同配置】
  --cooperation-type <类型>      默认: 2
      合作类型枚举：
        1 = 直连
        2 = 团购+预订合同  ← 默认（用户未明确说"预付包销"时的通用"预付"口径）
        4 = 现付
        6 = 预付包销合同（仅用户明确要求"预付包销"时使用）

  --prepay-price-change-mode <模式>  默认: 8
      价格模式-境内（境外供应商不支持此字段）：
        8 = 卖价  ← 默认（当前唯一可选值）

  --settle-date-type <类型>      默认: 18
      结算周期枚举：
        8  = 每周按实际新增消费
        12 = 每4周按实际新增消费
        18 = 每2周按实际新增消费  ← 默认

  --access-type <类型>           默认: 0
      接入类型枚举：
        0 = 非手工直连  ← 默认
        1 = 手工直连

【可选参数 - 发票与支付（按 partnerType 生效）】
  --invoice-mode <模式>          默认: 0
      发票模式（仅境内 partnerType=9/7/4 时生效，境外不传）：
        0 = 北京酷讯  ← 默认
        1 = 商家给用户开发票
        2 = 美团给用户开发票

  --is-open-meituan-pay <值>     默认: 0
      同步创建美开-美团支付（仅 partnerType=3 境外时生效）：
        0 = 暂不创建  ← 默认
        1 = 一键创建

  --is-open-vcc <值>             默认: 0
      是否进行VCC开卡（仅 partnerType=3 境外时生效）：
        0 = 否  ← 默认
        1 = 是

  --bizcode <参数>               默认: nib.hotel.prepay.zl.ld
      VCC开卡参数（仅 --is-open-vcc 1 且境外时传入）

【可选参数 - 境外直连协议】
  --overseas-protocol <协议>     默认: 1
      对接协议（仅境外 --cooperation-type 1 直连时传入，境外非直连不传）：
        1 = 直连-老开放平台  ← 默认
        2 = 直连-新开放平台
        3 = 直连-VIP

【调试参数】
  --dry-run
      仅打印参数，不实际执行

【输出】
  partnerId          供应商ID，后续创建房型/商品时必填
  platformContractId 平台合同ID（数字），查询 contractNo 时需要

【注意事项】
  ⚠️  工具49 为异步接口，返回后供应商创建仍需约 1 分钟才就绪
      立即创建房型会报「TDC创建房型异常」，请等待后重试

【使用示例】
  # 境内供应商（默认，partnerType=2）
  python3 factory/infra/create-partner.py --poi-id 1085927256096396

  # 境内女娲供应商（partnerType=9）
  python3 factory/infra/create-partner.py --poi-id 1085927256096396 --partner-type 9

  # 境外供应商
  python3 factory/infra/create-partner.py --poi-id 123 --partner-type 3 --overseas --currency JPY

  # 通兑超团（单体酒店 + 多门店）
  python3 factory/infra/create-partner.py --poi-id 111,222 --entity-type 2

  # 境外直连供应商（新开放平台协议）
  python3 factory/infra/create-partner.py --poi-id 123 --partner-type 3 --overseas --cooperation-type 1 --overseas-protocol 2

  # 境外供应商开通VCC
  python3 factory/infra/create-partner.py --poi-id 123 --partner-type 3 --overseas --is-open-vcc 1""")
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="创建可上单客户（供应商）")
    # 核心参数
    parser.add_argument("--poi-id", required=True,
                        help="绑定门店ID（多门店通兑场景用逗号分隔）")
    parser.add_argument("--partner-type", default=None,
                        help="客户类型（2=境内非女娲纸质, 3=境外, 4=不可上单境内女娲纸质, "
                             "5=不可上单境内女娲电子, 6=不可上单境外, 7=不可上单境内非女娲, "
                             "9=境内女娲普通；境内默认2）")
    parser.add_argument("--entity-type", default="0",
                        help="实体类型（0=酒店集团, 1=第三方渠道, 2=单体酒店, 3=多店老板，默认0）")
    parser.add_argument("--overseas", action="store_true", help="境外供应商")
    parser.add_argument("--partner-name", default=None, help="供应商名称")
    parser.add_argument("--currency", default=None,
                        help="结算币种（默认CNY，境外可指定JPY/USD/HKD/KWD/VND等）")
    # 合同配置参数
    parser.add_argument("--cooperation-type", default=None,
                        help="合作类型（1=直连, 2=团购+预订合同, 4=现付, 6=预付包销，默认2；"
                             "用户未明确说\"预付包销\"时按默认2处理，不要臆测成6）")
    parser.add_argument("--prepay-price-change-mode", default=None,
                        help="价格模式-境内（8=卖价，默认8；境外不支持）")
    parser.add_argument("--settle-date-type", default=None,
                        help="结算周期（8=每周, 12=每4周, 18=每2周，默认18）")
    parser.add_argument("--access-type", default=None,
                        help="接入类型（0=非手工直连, 1=手工直连，默认0）")
    # 发票与支付参数
    parser.add_argument("--invoice-mode", default=None,
                        help="发票模式（0=北京酷讯, 1=商家开票, 2=美团开票，默认0）")
    parser.add_argument("--is-open-meituan-pay", default=None,
                        help="同步创建美开（0=暂不创建, 1=一键创建，默认0；仅境外生效）")
    parser.add_argument("--is-open-vcc", default=None,
                        help="是否进行VCC开卡（0=否, 1=是，默认0；仅境外生效）")
    parser.add_argument("--bizcode", default=None,
                        help="VCC开卡参数（默认nib.hotel.prepay.zl.ld；仅--is-open-vcc 1且境外时传入）")
    # 境外直连协议参数
    parser.add_argument("--overseas-protocol", default=None,
                        help="对接协议（1=老开放平台, 2=新开放平台, 3=VIP，默认1；仅境外直连时生效）")
    # 调试参数
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    operator = get_operator()
    is_overseas = args.overseas

    # 确定 partnerType
    if args.partner_type:
        partner_type = int(args.partner_type)
    else:
        partner_type = 3 if is_overseas else 2

    partner_name = args.partner_name or f"{operator}可上单客户"
    currency = args.currency or "CNY"

    # 解析可选整型参数（未传时使用 interface 层默认值）
    cooperation_type         = int(args.cooperation_type)         if args.cooperation_type         is not None else 2
    prepay_price_change_mode = int(args.prepay_price_change_mode) if args.prepay_price_change_mode is not None else 8
    settle_date_type         = int(args.settle_date_type)         if args.settle_date_type         is not None else 18
    access_type              = int(args.access_type)              if args.access_type              is not None else 0
    invoice_mode             = args.invoice_mode                  if args.invoice_mode             is not None else "0"
    is_open_meituan_pay      = int(args.is_open_meituan_pay)      if args.is_open_meituan_pay      is not None else 0
    is_open_vcc              = int(args.is_open_vcc)              if args.is_open_vcc              is not None else 0
    overseas_protocol        = int(args.overseas_protocol)        if args.overseas_protocol        is not None else None

    # 合作类型描述
    cooperation_type_label = {1: "直连", 2: "团购+预订合同", 4: "现付", 6: "预付包销合同"}.get(cooperation_type, str(cooperation_type))

    print(f"=== 创建{'境外' if is_overseas else '境内'}可上单客户（工具49）===")
    print(f"  供应商名称        : {partner_name}")
    print(f"  partnerType       : {partner_type}")
    print(f"  entityType        : {args.entity_type}")
    print(f"  绑定门店          : {args.poi_id}")
    print(f"  结算币种          : {currency}")
    print(f"  合作类型          : {cooperation_type}（{cooperation_type_label}）")
    print(f"  价格模式          : {prepay_price_change_mode}")
    print(f"  结算周期          : {settle_date_type}")
    print(f"  接入类型          : {access_type}")
    if not is_overseas:
        print(f"  发票模式          : {invoice_mode}")
    print(f"  美开              : {is_open_meituan_pay}")
    print(f"  VCC开卡           : {is_open_vcc}")
    if is_open_vcc == 1 and is_overseas:
        print(f"  bizcode           : {args.bizcode or 'nib.hotel.prepay.zl.ld'}")
    if is_overseas and cooperation_type == 1:
        print(f"  对接协议          : {overseas_protocol or 1}")
    print(f"  ⚠️  异步接口，约1分钟后供应商才就绪")

    resp = call_partner(
        poi_id=args.poi_id,
        partner_type=partner_type,
        entity_type=int(args.entity_type),
        is_overseas=is_overseas,
        partner_name=partner_name,
        currency=currency,
        cooperation_type=cooperation_type,
        prepay_price_change_mode=prepay_price_change_mode,
        settle_date_type=settle_date_type,
        access_type=access_type,
        invoice_mode=invoice_mode,
        is_open_meituan_pay=is_open_meituan_pay,
        is_open_vcc=is_open_vcc,
        bizcode=args.bizcode,
        overseas_protocol=overseas_protocol,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    check_ok(resp, "创建供应商")
    print(f"\n=== 接口原始响应 ===")
    print(json.dumps(resp, ensure_ascii=False, indent=2))

    # 工具49的结果：partnerId 在 itemKey="返回值" 的嵌套 JSON 里
    # 尝试直接按 itemKey 查（兜底），再从 "返回值" JSON 里解析
    partner_id   = get_result(resp, "partnerId")
    contract_id  = get_result(resp, "platformContractId")

    if not partner_id or partner_id == "null":
        # 从 "返回值" JSON 嵌套里提取
        raw_val = get_result(resp, "返回值")
        if raw_val:
            try:
                data = json.loads(raw_val)
                inner = data.get("data") or {}
                partner_id  = str(inner.get("partnerId", ""))
                contract_id = str(inner.get("platformContractId", ""))
            except Exception:
                pass

    if not partner_id or partner_id in ("null", "None", "0"):
        print("[ERROR] 未获取到 partnerId，完整响应已打印在上方")
        sys.exit(1)

    print(f"\n✅ 供应商创建成功（异步，等待约1分钟后可创建房型）")
    print(f"  partnerId          : {partner_id}")
    print(f"  platformContractId : {contract_id}")
    print(f"  绑定门店           : {args.poi_id}")


if __name__ == "__main__":
    main()

