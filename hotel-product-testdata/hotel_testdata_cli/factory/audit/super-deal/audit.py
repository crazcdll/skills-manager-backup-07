#!/usr/bin/env python3
"""
审核 - 非通兑超团图文信息审核（independentSpuDeal）

非通兑超团 autoPublish=true，创建时基础信息审核已自动完成并上线。
但图文信息审核不会自动执行，需手动调用 RPC 补做，否则 SPU 卡在"待入库"。

直接调用 sp-tdm 的 ProductMakeService.auditProduct Thrift RPC：
  1. approvedSpuAndAddGraphicDetails — 图文信息审核
  2. spuAuditUpdate                  — 基础信息审核（已自动完成时返回 code=2024，正常）

使用方式：
  # 图文信息审核（默认）
  python3 factory/audit/super-deal/audit.py --spu-id 2256022534 --partner-id 4485030

  # dry-run
  python3 factory/audit/super-deal/audit.py --spu-id 2256022534 --partner-id 4485030 --dry-run

  # 指定泳道
  python3 factory/audit/super-deal/audit.py --spu-id 2256022534 --partner-id 4485030 --swimlane mylane
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from scripts.runner import invoke as rpc_invoke  # noqa


# ── 图文信息审核 RPC 配置 ────────────────────────────────────────────────────
APPKEY   = "com.sankuai.qatool.productmanage"
SERVICE  = "com.meituan.nibqa.tdm.api.service.ProductMakeService"
METHOD   = "auditProduct"
DEFAULT_CONFIG_KEY = "independentSpuDeal"  # 非通兑超团；通兑超团用 spuDeal


def _show_schema():
    print("""=== 非通兑超团图文信息审核（audit/super-deal）参数说明 ===

【必填参数】
  --spu-id        INT    非通兑超团 spuId（由 factory/super-deal/create-super-deal.py 创建后获得）
  --partner-id    STR    供应商ID（partnerId）

【可选参数】
  --swimlane      STR    泳道名（默认主干）
  --dry-run              只打印 RPC 参数，不实际调用

【审核方式】
  直接调用 Thrift RPC：
    appkey : com.sankuai.qatool.productmanage
    service: com.meituan.nibqa.tdm.api.service.ProductMakeService
    method : auditProduct
    configKey: independentSpuDeal（非通兑超团，默认）/ spuDeal（通兑超团）

  内部执行两步（HotelSpuDealBuilder.auditSpu）：
    1. approvedSpuAndAddGraphicDetails — 提交图文信息
    2. spuAuditUpdate(nextAuditStatus=4) — 更新基础信息审核状态为通过
       ⚠️ Step 2 是图文详情真正"审核通过"的关键步骤！

  ⚠️ 非通兑超团 autoPublish=true，创建时基础信息审核已自动完成并上线。
     但图文信息审核不会自动执行，需手动调用本脚本补做，否则 SPU 卡在"待入库"。
     通兑超团 autoPublish=false，BPM 基础信息审核通过后图文详情仍可能卡在
     「审核中」，此时可用 --config-key spuDeal 补做图文详情审核。

【使用示例】
  # 图文信息审核
  python3 factory/audit/super-deal/audit.py --spu-id 2256022534 --partner-id 4485030

  # dry-run
  python3 factory/audit/super-deal/audit.py --spu-id 2256022534 --partner-id 4485030 --dry-run
""")


def _do_graphic_audit(spu_id: str, partner_id: str, swimlane: str = "", dry_run: bool = False, config_key: str = None) -> dict:
    """
    调用 sp-tdm 的 auditProduct RPC 完成图文信息审核。

    内部执行：
      1. approvedSpuAndAddGraphicDetails — 图文信息审核
      2. spuAuditUpdate                  — 基础信息审核（已审核过时返回 code=2024，正常）

    返回：{"success": bool, "code": int|None, "result": dict}
    """
    ck = config_key or DEFAULT_CONFIG_KEY
    rpc_params = {
        "configKey":  ck,
        "spuId":      int(spu_id),
        "partnerId":  int(partner_id),
    }

    print(f"\n[图文信息审核] spuId={spu_id}, partnerId={partner_id}", file=sys.stderr)
    print(f"  appkey    : {APPKEY}", file=sys.stderr)
    print(f"  service   : {SERVICE}", file=sys.stderr)
    print(f"  method    : {METHOD}", file=sys.stderr)
    print(f"  configKey : {ck}", file=sys.stderr)
    print(f"  泳道      : {swimlane or '主干'}", file=sys.stderr)

    try:
        result = rpc_invoke(
            appkey=APPKEY,
            service=SERVICE,
            method=METHOD,
            params=rpc_params,
            swimlane=swimlane,
            timeout_ms=60000,
            dry_run=dry_run,
            raise_on_biz_error=False,
            progress_hint=f"图文信息审核 spuId={spu_id} partnerId={partner_id}...",
        )
    except Exception as e:
        print(f"  [ERROR] RPC 调用异常: {e}", file=sys.stderr)
        return {"success": False, "graphicDone": False, "result": {"error": str(e)}}

    if dry_run:
        return {"success": False, "graphicDone": False, "result": result}

    # 检查结果
    # success=true / code=0 → 图文+基础信息均成功（SPU 可上线）
    # code=2023 → 图文信息提交失败（Step 1 失败）
    # code=2024 → 基础信息审核更新失败（Step 2 失败）
    #   ⚠️ code=2024 时图文详情并未真正审核通过！
    success = False
    rpc_code = None
    if isinstance(result, dict):
        rpc_code = result.get("code")
        if result.get("success") is True or rpc_code == 0:
            success = True

    if success:
        print(f"  ✓ auditProduct 成功（图文+基础信息一步完成）", file=sys.stderr)
    elif rpc_code == 2024:
        print(f"  ✗ auditProduct 失败 code=2024（spuAuditUpdate 冲突）", file=sys.stderr)
    elif rpc_code == 2023:
        print(f"  ✗ auditProduct 失败 code=2023（图文信息提交失败）", file=sys.stderr)
    else:
        print(f"  ✗ auditProduct 失败: {result}", file=sys.stderr)

    return {"success": success, "code": rpc_code, "result": result}


def main():
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="非通兑超团图文信息审核（直接 RPC）")
    parser.add_argument("--spu-id",     required=True, type=int, help="超团 spuId")
    parser.add_argument("--partner-id", required=True, type=str, help="供应商ID（partnerId）")
    parser.add_argument("--swimlane",   default="", help="泳道（默认主干）")
    parser.add_argument("--config-key", default=DEFAULT_CONFIG_KEY,
                        help="configKey: independentSpuDeal=非通兑超团（默认）, spuDeal=通兑超团")
    parser.add_argument("--dry-run",    action="store_true", help="只打印 RPC 参数，不实际调用")
    args = parser.parse_args()

    print("=" * 60, file=sys.stderr)
    print(f"  超团图文信息审核", file=sys.stderr)
    print(f"  超团ID    : {args.spu_id}", file=sys.stderr)
    print(f"  供应商ID  : {args.partner_id}", file=sys.stderr)
    print(f"  configKey : {args.config_key}", file=sys.stderr)
    print(f"  泳道      : {args.swimlane or '主干'}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    graphic_result = _do_graphic_audit(
        args.spu_id, args.partner_id, args.swimlane, args.dry_run, args.config_key
    )
    graphic_audit_success = graphic_result.get("success", False)

    # ---- 输出结构化结果 ----
    result = {
        "spuId":               args.spu_id,
        "partnerId":           args.partner_id,
        "configKey":           args.config_key,
        "graphicAuditSuccess": graphic_audit_success,
        "rpcResult":           graphic_result.get("result"),
    }
    print(json.dumps(result, ensure_ascii=False))

    print("\n" + "=" * 60, file=sys.stderr)
    if args.dry_run:
        print("  [dry-run] 未实际执行", file=sys.stderr)
    elif graphic_audit_success:
        print(f"  审核完成 ✓（auditProduct 一步完成图文+基础信息）", file=sys.stderr)
    else:
        print(f"  审核失败 ✗", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  超团ID    : {args.spu_id}", file=sys.stderr)
    print(f"  供应商ID  : {args.partner_id}", file=sys.stderr)
    print(f"  configKey : {args.config_key}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    if not args.dry_run and not graphic_audit_success:
        sys.exit(1)


if __name__ == "__main__":
    main()

