#!/usr/bin/env python3
"""
审核 - 通兑超团审核（auditProduct 图文信息审核，无需 BPM）

✅ 已实测验证（2026-07-22，spuId=2257204683）：通兑超团审核只需调用 auditProduct
一步即可，不需要先走 BPM 基础信息审核。推荐直接用 --graphic-only 参数。

推荐流程（仅一步）：
  auditProduct RPC 图文信息审核（--graphic-only，跳过 BPM）
    - 调用 sp-tdm 的 ProductMakeService.auditProduct
    - 内部执行 approvedSpuAndAddGraphicDetails（添加默认图文并提交审核，
      同时完成 couponAuditStatus/giftCardAuditStatus/sieveAuditStatus 均变为 4）
    - 返回 success:true, code:200 即代表审核完成，可紧接着上线
    - 残留现象：spuAuditModel.auditStatus 会停留在 8（不会变成4），不影响上线

⚠️ 关键约束：
   1. submitSpu 创建时不能带 spuImageInfoModel，否则 auditProduct 会把图文推到「审核中」
   2. 上线（onlineSwitch）存在明显异步索引延迟，可能报「套餐缺少图文详情」，需多次重试等待
      （--auto-online 内置递增重试，最长可达数分钟）
   3. auditProduct 短间隔内重复调用同一 spuId 可能返回不稳定结果（一次 success:true，
      另一次 success:false/code:2024/message:"SPU基础信息审核失败"），若已确认成功
      不要重复调用，否则可能把状态打回卡死态（couponAuditStatus 卡在非4的中间态且无法自愈）

⚠️ BPM 基础信息审核仍保留作为可选/备用路径（--step bpm/all），但存在已知坑：
  taskform complete 校验的是当前 BPM 登录 Cookie 所属账号是否在任务候选组内，与委托目标无关；
  默认委托对象（BPM 变量 userLogin 或固定兜底账号 DELEGATE_USER_ID）都不是当前登录人，
  若都不在候选组内会报「该任务可处理的组是:xxx, 你无权操作！」，此时应传
  --delegate-user-id <当前登录浏览器账号自己的 userId>。

使用方式：
  # 推荐：仅 auditProduct 图文审核 + 自动上线（无需 BPM）
  python3 factory/audit/super-deal-unified/audit.py --spu-id 2256392932 --partner-id 4570390 --graphic-only --auto-online

  # 图文审核已确认通过，只需单独手动触发一次上线（不重新走 auditProduct，不做多次重试等待）
  python3 factory/audit/super-deal-unified/audit.py --spu-id 2256392932 --partner-id 4570390 --online-only

  # 备用：完整流程（BPM + 图文，需要时才用）
  python3 factory/audit/super-deal-unified/audit.py --spu-id 2256392932 --partner-id 4570390 --action pass --delegate-user-id <自己userId>

  # 审核驳回（仅 BPM，不执行图文审核）
  python3 factory/audit/super-deal-unified/audit.py --spu-id 2256392932 --action reject

  # 仅查询任务（不委托、不审核）
  python3 factory/audit/super-deal-unified/audit.py --spu-id 2256392932 --step query

输出：
  脚本最后输出 JSON 到 stdout，包含 taskId、processInstanceId、
  partnerId、poiId、spuName、auditCompleted、graphicAuditSuccess 等信息。
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from scripts.bpm_utils import (  # noqa
    ensure_bpm_login, query_bpm_task, delegate_bpm_task, complete_bpm_task,
    DELEGATE_USER_ID, BPM_BASE,
)
from scripts.runner import invoke as rpc_invoke  # noqa
from datetime import datetime


DEFAULT_PARTNER_ID = "4485030"
DEFAULT_POI_ID = "67101"

# ── 图文信息审核 RPC 配置 ────────────────────────────────────────────────────
GRAPHIC_APPKEY   = "com.sankuai.qatool.productmanage"
GRAPHIC_SERVICE  = "com.meituan.nibqa.tdm.api.service.ProductMakeService"
GRAPHIC_METHOD   = "auditProduct"
GRAPHIC_CONFIG_KEY = "spuDeal"  # 通兑超团


def _load_super_deal_unified_interface():
    """动态加载 interface/super-deal-unified/interface.py（目录名含连字符，无法直接 import）。"""
    import importlib.util as ilu

    _iface_path = os.path.join(os.path.dirname(__file__), "../../../interface/super-deal-unified/interface.py")
    _spec = ilu.spec_from_file_location("super_deal_unified_interface", _iface_path)
    _mod = ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    return _mod


def _show_schema():
    print("""=== 通兑超团审核（audit/super-deal-unified）参数说明 ===

【必填参数】
  --spu-id        STR    通兑超团 spuId（由 factory/super-deal-unified/create-super-deal-unified.py 创建后获得）

【可选参数】
  --action        STR    审核动作（默认 pass）
                           pass    通过（默认，执行 BPM + 图文审核）
                           reject  驳回（仅 BPM，不执行图文审核）
  --mis           STR    操作人MIS（默认从 config 读取）
  --bpm-cookie    STR    直接传入 BPM Cookie（格式：ssoid=xxx; JSESSIONID=yyy，跳过浏览器获取）
  --partner-id    STR    供应商ID（图文审核必填；不传则从 BPM 任务变量提取）
  --step          STR    执行范围（默认 all）
                           query   仅查询 BPM 任务（不委托、不审核）
                           bpm     查询 + 委托（不审核）
                           all     查询 + 委托 + BPM审核 + 图文审核（默认，完整流程）
  --skip-graphic         跳过图文信息审核（仅执行 BPM 基础信息审核）
  --graphic-only         仅执行图文信息审核（跳过 BPM，用于 BPM 已完成的场景）
  --online-only          跳过审核，直接单次调用 updateSpuStatus RPC 上线接口（Thrift 直调，
                           不重试，用于审核已确认通过、仅需手动触发/重试上线动作的场景）

【审核流程说明】
  Step 1: BPM 基础信息审核（查询 → 委托当前用户 → taskform complete）
  Step 2: auditProduct RPC 图文信息审核（仅 action=pass 时执行）

  ⚠️ BPM 必须先做！BPM 通过后 auditProduct 返回 code=2024 是预期行为。
     approvedSpuAndAddGraphicDetails 会添加默认图文并提交审核，
     图文状态变为「编审修改后通过」，SPU 可正常上线。

【使用示例】
  # 完整审核流程（通过：BPM + 图文）
  python3 factory/audit/super-deal-unified/audit.py --spu-id 2256392932 --partner-id 4570390 --action pass

  # 驳回（仅 BPM）
  python3 factory/audit/super-deal-unified/audit.py --spu-id 2256392932 --action reject

  # 仅执行图文审核（BPM 已完成）
  python3 factory/audit/super-deal-unified/audit.py --spu-id 2256392932 --partner-id 4570390 --graphic-only
""")


def build_complete_form(task_id: str, task_info: dict, action: str, mis: str, delegate_user_id: str) -> dict:
    """
    构造通兑超团审核的 BPM taskform complete 表单数据。

    auditStatus: 1=通过, 0=驳回
    """
    spu_id      = task_info.get("spuId", "")
    spu_name    = task_info.get("spuName", "")
    partner_id  = task_info.get("partnerId", DEFAULT_PARTNER_ID)
    partner_name = task_info.get("partnerName", "")
    package_id  = task_info.get("packageId", "null")
    package_title = task_info.get("packageTitle", "null")
    mt_price    = task_info.get("mtPrice", "")

    submit_time  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    audit_status = "1" if action == "pass" else "0"

    if action == "pass":
        comment_result = "<span style='color:green'>同意</span>"
    else:
        comment_result = "<span style='color:red'>驳回</span>"

    sys_process_comment = json.dumps({
        "taskName": "人工审核",
        "result": comment_result,
        "message": "",
    }, ensure_ascii=False)

    return {
        "type":             "超级团购SPU套餐",
        "partner":          partner_name if partner_name else f"({partner_id})",
        "spu":              str(spu_id),
        "spuName":          spu_name,
        "packageId":        package_id,
        "packageTitle":     package_title,
        "submitUser":       f"{mis}({delegate_user_id})",
        "submitTime":       submit_time,
        "rejectReason":     "",
        "mtPrice":          mt_price,
        "reason":           "",
        "auditStatus":      audit_status,
        "nowrap":           "false",
        "SYS_PROCESS_COMMENT": sys_process_comment,
        "SYS_WORKBENCH_ID": "",
    }


def _do_graphic_audit(spu_id: str, partner_id: str) -> dict:
    """
    调用 sp-tdm 的 auditProduct RPC，提交图文信息审核。

    ⚠️ 必须在 BPM 基础信息审核通过后调用！

    内部执行（HotelSpuDealBuilder.auditSpu）：
      1. approvedSpuAndAddGraphicDetails — 添加默认图文并提交审核
         → 图文状态变为「编审修改后通过」
      2. spuAuditUpdate(nextAuditStatus=4) — 更新基础信息审核状态
         → 因 BPM 已完成，返回 code=2024（预期行为，不影响图文提交）

    返回：{"success": bool, "code": int|None, "result": dict}
    """
    rpc_params = {
        "configKey":  GRAPHIC_CONFIG_KEY,
        "spuId":      int(spu_id),
        "partnerId":  int(partner_id),
    }

    print(f"\n[Step 2] auditProduct RPC 图文信息审核: spuId={spu_id}, partnerId={partner_id}", file=sys.stderr)
    print(f"  appkey    : {GRAPHIC_APPKEY}", file=sys.stderr)
    print(f"  service   : {GRAPHIC_SERVICE}", file=sys.stderr)
    print(f"  method    : {GRAPHIC_METHOD}", file=sys.stderr)
    print(f"  configKey : {GRAPHIC_CONFIG_KEY}", file=sys.stderr)

    try:
        result = rpc_invoke(
            appkey=GRAPHIC_APPKEY,
            service=GRAPHIC_SERVICE,
            method=GRAPHIC_METHOD,
            params=rpc_params,
            timeout_ms=60000,
            raise_on_biz_error=False,
            progress_hint=f"auditProduct spuId={spu_id} partnerId={partner_id}...",
        )
    except Exception as e:
        print(f"  [ERROR] RPC 调用异常: {e}", file=sys.stderr)
        return {"success": False, "code": None, "result": {"error": str(e)}}

    # 检查结果
    # code=200 / code=0 / success=true → 图文+基础信息均成功
    # code=2024 → spuAuditUpdate 冲突（BPM 已完成），但 approvedSpuAndAddGraphicDetails 成功
    #   ⚠️ code=2024 是预期行为！图文已成功提交为「编审修改后通过」
    # code=2023 → 图文信息提交失败（approvedSpuAndAddGraphicDetails 失败）
    success = False
    rpc_code = None
    if isinstance(result, dict):
        rpc_code = result.get("code")
        if result.get("success") is True or rpc_code in (0, 200):
            success = True
        elif rpc_code == 2024:
            # BPM 已完成基础信息审核，spuAuditUpdate 冲突是预期行为
            # approvedSpuAndAddGraphicDetails 已成功提交图文 → 视为成功
            success = True

    if success:
        if rpc_code == 2024:
            print(f"  ✓ auditProduct 完成（code=2024 预期：BPM 已完成基础信息审核，图文已提交为「编审修改后通过」）", file=sys.stderr)
        else:
            print(f"  ✓ auditProduct 成功（图文+基础信息一步完成）", file=sys.stderr)
    elif rpc_code == 2023:
        print(f"  ✗ auditProduct 失败 code=2023（图文信息提交失败）", file=sys.stderr)
    else:
        print(f"  ✗ auditProduct 失败: {result}", file=sys.stderr)

    return {"success": success, "code": rpc_code, "result": result}


def _do_online_switch(spu_id: str, partner_id: str) -> dict:
    """上线通兑超团，带重试等待。

    ✅ 已实测验证（2026-07-22，spuId=2257204835）：优先直接调用
    MeResourceFacade#updateSpuStatus RPC（Thrift 直调，与非通兑超团/套餐共用同一
    已注册 OCTO 接口），比走 mtcurl + MTA HTTP 网关的 online_switch 更快更稳定，
    不依赖浏览器 ssoid。若 Thrift RPC 调用本身异常（如缺少 du_thrift 依赖等环境问题），
    再 fallback 到 online_switch（HTTP 网关）保证兼容性。

    审核通过后 SPU 基本信息/选单/魔盒入库是异步的，若返回"未入库"等关键词则等待重试
    （最多 10 次，间隔递增 10~30 秒）。

    返回：{"success": bool, "result": dict|None, "error": str|None}
    """
    import time

    _mod = _load_super_deal_unified_interface()

    def _call_online() -> dict:
        """优先 Thrift 直调 updateSpuStatus，异常时 fallback 到 HTTP 网关 online_switch。"""
        try:
            return _mod.update_spu_status(partner_id, spu_id, status=1)
        except Exception as thrift_err:
            print(f"  ⚠️ updateSpuStatus RPC 调用异常，fallback 到 online_switch（HTTP网关）: {thrift_err}", file=sys.stderr)
            return _mod.online_switch(partner_id, spu_id, status=1)

    # 审核通过后 SPU 入库是异步的，需要等待 SPU/红包/选单/魔盒等全部入库完成才能上线
    # 不同入库步骤的报错关键词不同，均需重试等待
    # 最多重试 10 次，首次等 10 秒，之后每次递增
    wait_times = [10, 10, 15, 15, 20, 20, 25, 25, 30, 30]
    max_retries = len(wait_times)
    # 可重试的错误关键词（均为异步入库未完成的表现）
    retryable_keywords = ["未入库", "未上线", "未审核", "processing", "处理中", "修改状态失败"]
    for attempt in range(1, max_retries + 1):
        try:
            online_result = _call_online()
            data = online_result.get("data") if isinstance(online_result, dict) else None
            success = (
                data is True
                or online_result.get("success") is True
                or online_result.get("status") in (0, None)
            )
            if success:
                return {"success": True, "result": online_result, "error": None}
            print(f"  ✗ 上线失败（第{attempt}次）: {online_result}", file=sys.stderr)
            err_msg = json.dumps(online_result, ensure_ascii=False)
        except Exception as e:
            err_msg = str(e)
            print(f"  ✗ 上线异常（第{attempt}次）: {err_msg}", file=sys.stderr)
        # 判断是否可重试
        should_retry = attempt < max_retries and any(kw in err_msg for kw in retryable_keywords)
        if should_retry:
            wait = wait_times[attempt - 1]
            print(f"  ⏳ 等待 {wait} 秒后重试（{attempt}/{max_retries}）...", file=sys.stderr)
            time.sleep(wait)
            continue
        if attempt >= max_retries:
            break
        # 不可重试的错误（如参数错误、权限不足等）直接返回
        return {"success": False, "result": None, "error": err_msg}
    return {"success": False, "result": None, "error": "重试次数已用完（SPU/红包/选单/魔盒入库超时）"}


def _do_online_switch_once(spu_id: str, partner_id: str) -> dict:
    """直接单次调用 MeResourceFacade#updateSpuStatus RPC（Thrift 直调）上线通兑超团，不做重试等待。

    用于审核（couponAuditStatus/giftCardAuditStatus/sieveAuditStatus）已确认为 4 通过、
    mboxId 已生成（基本信息模块已入库），仅需手动触发一次显式上线动作的场景，避免
    --auto-online 自带的多次递增等待重试耗时过长，同时避免依赖 mtcurl + 浏览器 ssoid
    的 MTA HTTP 网关（online_switch）。

    ⚠️ 若 SPU 仍处于「基本信息模块未入库」（13001提交审核失败）等未完全入库状态，
    直调本函数大概率复现同样报错，此时应改走 edit_spu 修复（详见 workflow 文档）。

    返回：{"success": bool, "result": dict|None, "error": str|None}
    """
    _mod = _load_super_deal_unified_interface()

    try:
        status_result = _mod.update_spu_status(partner_id, spu_id, status=1)
    except Exception as e:
        err_msg = str(e)
        print(f"  ✗ 上线异常（updateSpuStatus RPC）: {err_msg}", file=sys.stderr)
        return {"success": False, "result": None, "error": err_msg}

    data = status_result.get("data") if isinstance(status_result, dict) else None
    success = data is True or status_result.get("success") is True
    if success:
        return {"success": True, "result": status_result, "error": None}

    print(f"  ✗ 上线失败（updateSpuStatus RPC）: {status_result}", file=sys.stderr)
    return {"success": False, "result": status_result, "error": json.dumps(status_result, ensure_ascii=False)}


def main():
    # 快速检测帮助类命令（避免 required 参数报错）
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="通兑超团审核（推荐 --graphic-only 仅走 auditProduct 图文信息审核，无需 BPM）")
    parser.add_argument("--spu-id",       required=True, help="通兑超团 spuId")
    parser.add_argument("--action",       choices=["pass", "reject"], default="pass",
                        help="审核动作: pass=通过(结合--step/--graphic-only决定是否走BPM), reject=驳回(仅BPM)（默认 pass）")
    parser.add_argument("--mis",          default=None, help="操作人 MIS")
    parser.add_argument("--bpm-cookie",   default=None, help="直接传入 BPM Cookie（跳过浏览器获取）")
    parser.add_argument("--partner-id",   default=None, help="供应商ID（图文审核必填；不传则从 BPM 任务变量提取）")
    parser.add_argument("--step",         choices=["query", "bpm", "all"], default="all",
                        help="执行范围: query=仅查询, bpm=查询+委托, all=完整流程（默认 all）")
    parser.add_argument("--skip-graphic", action="store_true",
                        help="跳过图文信息审核（仅执行 BPM 基础信息审核）")
    parser.add_argument("--graphic-only", action="store_true",
                        help="仅执行图文信息审核（跳过 BPM，用于 BPM 已完成的场景）")
    parser.add_argument("--online-only", action="store_true",
                        help="跳过审核，直接单次调用 updateSpuStatus RPC 上线接口（Thrift 直调，不重试）")
    parser.add_argument("--auto-online", action="store_true",
                        help="审核通过后自动触发上线（调用 MTA onlineSwitch 接口）")
    parser.add_argument("--delegate-user-id", default=None,
                        help="BPM 任务委托目标 userId（优先级最高）。⚠️ taskform complete 校验的是当前 "
                             "BPM 登录 Cookie 所属账号是否在任务候选组内，与委托目标无关；若默认委托对象"
                             "（BPM变量 userLogin / 固定兜底账号）报「该任务可处理的组是:xxx, 你无权操作!」，"
                             "应改传当前登录浏览器账号自己的 userId")
    args = parser.parse_args()

    if args.mis is None:
        try:
            from scripts.utils import get_audit_operator
            args.mis = get_audit_operator()
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    action_text = "通过" if args.action == "pass" else "驳回"
    print("=" * 60, file=sys.stderr)
    print(f"  通兑超团审核（BPM + 图文）", file=sys.stderr)
    print(f"  超团ID  : {args.spu_id}", file=sys.stderr)
    print(f"  审核动作: {action_text}", file=sys.stderr)
    print(f"  操作人  : {args.mis}", file=sys.stderr)
    print(f"  执行范围: {args.step}", file=sys.stderr)
    if args.partner_id:
        print(f"  partnerId: {args.partner_id}", file=sys.stderr)
    if args.online_only:
        print(f"  模式    : 仅上线（跳过审核，直接调用 updateSpuStatus RPC）", file=sys.stderr)
    elif args.graphic_only:
        print(f"  模式    : 仅图文审核（跳过 BPM）", file=sys.stderr)
    else:
        print(f"  图文审核: {'跳过' if args.skip_graphic else '执行(BPM后追加auditProduct RPC)' if args.action == 'pass' else '不执行(reject)'}", file=sys.stderr)
    if args.auto_online:
        print(f"  自动上线: ✓（审核通过后自动触发 onlineSwitch）", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # ---- --online-only 模式：跳过审核，直接单次调用 updateSpuStatus RPC 上线 ----
    if args.online_only:
        if not args.partner_id:
            print("[ERROR] --online-only 模式下必须传 --partner-id", file=sys.stderr)
            sys.exit(1)
        print(f"\n[Step 1] 直接调用 updateSpuStatus RPC 上线: spuId={args.spu_id}, partnerId={args.partner_id}", file=sys.stderr)
        online_res = _do_online_switch_once(args.spu_id, args.partner_id)
        online_success = online_res.get("success", False)

        result = {
            "spuId":         args.spu_id,
            "partnerId":     args.partner_id,
            "onlineOnly":    True,
            "onlineSuccess": online_success,
            "rpcResult":     online_res.get("result"),
            "error":         online_res.get("error"),
        }
        print(json.dumps(result, ensure_ascii=False))

        print("\n" + "=" * 60, file=sys.stderr)
        print(f"  上线结果  : {'✓ 成功' if online_success else '✗ 失败'}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        if not online_success:
            sys.exit(1)
        return

    # ---- --graphic-only 模式：直接执行 auditProduct，跳过 BPM ----
    if args.graphic_only:
        if not args.partner_id:
            print("[ERROR] --graphic-only 模式下必须传 --partner-id", file=sys.stderr)
            sys.exit(1)
        graphic_result = _do_graphic_audit(args.spu_id, args.partner_id)
        graphic_audit_success = graphic_result.get("success", False)

        # --graphic-only + --auto-online：图文审核成功后自动上线
        online_success = False
        online_done = False
        if args.auto_online and graphic_audit_success:
            print(f"\n[Step 3] 自动上线: spuId={args.spu_id}, partnerId={args.partner_id}", file=sys.stderr)
            online_res = _do_online_switch(args.spu_id, args.partner_id)
            online_done = True
            online_success = online_res.get("success", False)
            if online_success:
                print(f"  ✓ 上线成功", file=sys.stderr)
            else:
                print(f"  请手动在 MTA 上单系统点击上线", file=sys.stderr)

        result = {
            "spuId":               args.spu_id,
            "partnerId":           args.partner_id,
            "action":              args.action,
            "graphicOnly":         True,
            "graphicAuditSuccess": graphic_audit_success,
            "rpcCode":             graphic_result.get("code"),
            "rpcResult":           graphic_result.get("result"),
            "onlineDone":          online_done,
            "onlineSuccess":       online_success,
        }
        print(json.dumps(result, ensure_ascii=False))

        print("\n" + "=" * 60, file=sys.stderr)
        if graphic_audit_success:
            print(f"  图文审核完成 ✓（图文状态：编审修改后通过）", file=sys.stderr)
        else:
            print(f"  图文审核失败 ✗", file=sys.stderr)
        if online_done:
            print(f"  自动上线  : {'✓' if online_success else '✗'}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        if not graphic_audit_success:
            sys.exit(1)
        return

    # ================================================================
    # BPM 流程（Step 1: 基础信息审核）
    # ================================================================
    bpm_cookie = args.bpm_cookie or ensure_bpm_login()
    if not bpm_cookie:
        print("[ERROR] 无法获取有效的 BPM Cookie", file=sys.stderr)
        sys.exit(1)

    # ---- 查询审核任务 ----
    print(f"\n[Step 1] BPM 基础信息审核: 查询任务 spuId={args.spu_id}", file=sys.stderr)
    task = query_bpm_task(
        args.spu_id, bpm_cookie,
        entity_desc=f"通兑超团spuId={args.spu_id}"
    )
    if not task:
        print("\n[FAIL] 未能查询到审核任务", file=sys.stderr)
        sys.exit(1)

    task_id    = str(task.get("taskId", ""))
    process_id = str(task.get("processInstanceId", ""))
    var_dict   = task.get("_var_dict", {})
    partner_id  = str(var_dict.get("partnerId", args.partner_id or DEFAULT_PARTNER_ID))
    poi_id      = str(var_dict.get("poiId", DEFAULT_POI_ID))
    spu_name    = str(var_dict.get("spuName", ""))
    partner_name = str(var_dict.get("partner", ""))
    package_id  = str(var_dict.get("packageId", "null"))
    package_title = str(var_dict.get("packageTitle", "null"))
    mt_price    = str(var_dict.get("mtPrice", ""))

    # 从 BPM 变量中提取「超团提交人」的 userId（变量名 userLogin，值为数字 userId）
    # 该账号是发起超团 BPM 流程的人，必然在任务候选组（如 SPU审核组/组687）内，
    # 具备审核权限。委托给它可确保 taskform complete 能通过组权限校验。
    # DELEGATE_USER_ID 仅在 userLogin 缺失时作为兜底委托目标。
    submitter_user_id = str(var_dict.get("userLogin", ""))

    print(f"  ✓ 找到任务: taskId={task_id}, processId={process_id}", file=sys.stderr)
    print(f"  ✓ partnerId={partner_id}, poiId={poi_id}", file=sys.stderr)
    print(f"  ✓ spuName={spu_name}", file=sys.stderr)
    if submitter_user_id:
        print(f"  ✓ 超团提交人: userLogin={submitter_user_id}", file=sys.stderr)

    # ---- 委托任务 ----
    # 优先级：显式传入的 --delegate-user-id > 超团提交人（userLogin） > 固定兜底 DELEGATE_USER_ID
    # ⚠️ taskform complete 校验的是当前 BPM 登录 Cookie 所属账号是否在任务候选组内，与委托目标无关，
    #    委托 API 只是修改任务 assignee；若默认委托对象没有候选组权限会报「你无权操作」，
    #    此时应显式传 --delegate-user-id <当前登录账号自己的userId>
    delegated = False
    delegate_user_id = args.delegate_user_id or submitter_user_id or DELEGATE_USER_ID
    if args.step in ("bpm", "all"):
        if not delegate_bpm_task(task_id, bpm_cookie, delegate_user_id):
            print("\n[FAIL] 任务委托失败", file=sys.stderr)
            sys.exit(1)
        delegated = True

    # ---- BPM 审核提交（仅 all）----
    audit_completed = False
    if args.step == "all":
        print(f"\n[Step 1] BPM taskform complete: taskId={task_id}, action={args.action}", file=sys.stderr)
        task_info = {
            "spuId":        args.spu_id,
            "spuName":      spu_name,
            "partnerId":    partner_id,
            "partnerName":  partner_name,
            "packageId":    package_id,
            "packageTitle": package_title,
            "mtPrice":      mt_price,
        }
        form_data = build_complete_form(task_id, task_info, args.action, args.mis, delegate_user_id)
        if not complete_bpm_task(task_id, form_data, bpm_cookie):
            print("\n[FAIL] BPM 审核提交失败", file=sys.stderr)
            sys.exit(1)
        audit_completed = True

    # ================================================================
    # Step 2: 图文信息审核（auditProduct RPC）
    # 仅在 action=pass、step=all、未跳过图文审核时执行
    # ⚠️ 必须在 BPM 基础信息审核通过后执行
    # ================================================================
    graphic_audit_success = False
    graphic_audit_done = False
    rpc_code = None
    if (args.step == "all"
            and args.action == "pass"
            and audit_completed
            and not args.skip_graphic):
        graphic_result = _do_graphic_audit(args.spu_id, partner_id)
        graphic_audit_success = graphic_result.get("success", False)
        graphic_audit_done = True
        rpc_code = graphic_result.get("code")

        if not graphic_audit_success:
            print(f"\n  ⚠️ 图文信息审核失败（code={rpc_code}）", file=sys.stderr)
            print(f"  基础信息审核已完成，请手动处理图文审核：", file=sys.stderr)
            print(f"  python3 factory/audit/super-deal-unified/audit.py --spu-id {args.spu_id} --partner-id {partner_id} --graphic-only", file=sys.stderr)

    # ================================================================
    # Step 3: 自动上线（可选）
    # 仅在 --auto-online 且图文审核成功时执行
    # 调用 MTA HTTP 网关 onlineSwitch 接口，status=1 上线
    # ================================================================
    online_success = False
    online_done = False
    if args.auto_online and graphic_audit_success:
        print(f"\n[Step 3] 自动上线: spuId={args.spu_id}, partnerId={partner_id}", file=sys.stderr)
        online_res = _do_online_switch(args.spu_id, partner_id)
        online_done = True
        online_success = online_res.get("success", False)
        if online_success:
            print(f"  ✓ 上线成功", file=sys.stderr)
        else:
            print(f"  请手动在 MTA 上单系统点击上线", file=sys.stderr)

    # ---- 输出结构化结果 ----
    result = {
        "taskId":            task_id,
        "processInstanceId": process_id,
        "spuId":             args.spu_id,
        "spuName":           spu_name,
        "partnerId":         partner_id,
        "poiId":             poi_id,
        "partnerName":       partner_name,
        "packageId":         package_id,
        "packageTitle":      package_title,
        "mtPrice":           mt_price,
        "action":            args.action,
        "auditStatus":       1 if args.action == "pass" else 0,
        "delegated":         delegated,
        "auditCompleted":    audit_completed,
        "graphicAuditDone":  graphic_audit_done,
        "graphicAuditSuccess": graphic_audit_success,
        "rpcCode":           rpc_code,
        "onlineDone":        online_done,
        "onlineSuccess":     online_success,
    }
    print(json.dumps(result, ensure_ascii=False))

    print("\n" + "=" * 60, file=sys.stderr)
    print("  通兑超团审核完成", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  超团ID    : {args.spu_id}", file=sys.stderr)
    print(f"  spuName   : {spu_name}", file=sys.stderr)
    print(f"  taskId    : {task_id}", file=sys.stderr)
    print(f"  processId : {process_id}", file=sys.stderr)
    print(f"  partnerId : {partner_id}", file=sys.stderr)
    print(f"  poiId     : {poi_id}", file=sys.stderr)
    print(f"  已委托    : {'✓' if delegated else '✗'}", file=sys.stderr)
    print(f"  BPM审核   : {'✓' if audit_completed else '✗'}", file=sys.stderr)
    if audit_completed:
        print(f"  审核结果  : {action_text}", file=sys.stderr)
    if graphic_audit_done:
        print(f"  图文审核  : {'✓ (编审修改后通过)' if graphic_audit_success else '✗'}", file=sys.stderr)
        if rpc_code == 2024:
            print(f"  RPC code  : 2024（预期：BPM已完成，spuAuditUpdate冲突，图文已提交）", file=sys.stderr)
    elif args.action == "pass" and args.step == "all" and not args.skip_graphic:
        print(f"  图文审核  : 未执行（BPM未完成）", file=sys.stderr)
    if online_done:
        print(f"  自动上线  : {'✓' if online_success else '✗'}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    main()

