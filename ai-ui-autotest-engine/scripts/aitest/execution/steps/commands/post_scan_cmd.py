#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""case-post-scan 命令：Case 收尾补扫取证 + 待复核项清单（判定交给 AI）。

设计原则（与断言内 sweep 一致）：引擎只产证据，不做语义判定。
  · 本 case 无失败/待判定项 → 直接 SKIP，不产生任何设备操作（零成本）；
  · 有则**先把页面快速滚回顶部**（纯手势、不截图），再从顶部自上而下连拍最多 N 帧
    （默认 POST_SCAN_SCROLLS=5，到底即停），并把「待复核项 + 帧清单 + 改判命令模板」
    一次性打印出来；
  · AI 一次性读完所有帧后统一改判（override-step-result --assert-verdict），
    命中才写，未命中保持原结论。

为什么先回顶：走查结束时的页面位置取决于最后一步，从那里向下补看只能拿到「最后一步
以下的片段」。回顶后补扫证据固定是「顶部 → 向下」的完整序列，复核读图顺序与页面阅读
顺序一致，也避免漏掉顶部区域（如页面首屏的权益/标题）。

为什么不在这里自动改判：改判需要「当时在验什么」的语义（expect 文本 / 失败原因），
且多帧比对只有 AI 能做；引擎自动改判会引入不可解释的结论。
"""

import json
import os

from aitest.execution.engine.flow.flow_context import (
    collect_open_checks,
    load_context as fc_load,
)
from aitest.execution.screen.post_scan import (
    POST_SCAN_SCROLLS, SCROLL_TO_TOP, capture_frames,
)
from aitest.shared.case_utils import current_case_workspace, resolve_case_path
from aitest.shared.errors import FlowStateError
from aitest.shared.observability.runtime_audit import append_event
from aitest.shared.records import frame_path
from aitest.shared.workspace import render_cmd


EVIDENCE_DIRNAME = os.path.join("diagnostics", "post-scan")
EVIDENCE_FILENAME = "post_scan.json"

# 断言结果 → 控制台标记。本模块不引 assertions 包：assertions/__init__ 会拉起 registry
# → 策略 → handlers.base，与 handlers.base 存在循环导入，此处只需三个字面量。
_RESULT_LABELS = {"pass": "✅", "fail": "❌", "pending": "📍"}


def _write_evidence(case_ws, payload):
    """落补扫证据（失败不阻断：证据是辅助产物，主流程不能因此报错）。"""
    try:
        path = os.path.join(case_ws, EVIDENCE_DIRNAME)
        os.makedirs(path, exist_ok=True)
        full = os.path.join(path, EVIDENCE_FILENAME)
        with open(full, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return full
    except (OSError, TypeError):
        return ""


def _print_frames(frames, scrolls, stopped_reason, reset_to_top=True):
    """打印帧清单（帧序 = 页面自上而下）；末尾说明是「滚满了」还是「已到底提前结束」。"""
    total = len(frames)
    if not total:
        print(f"  ⚠️ 未产出补看帧（reason={stopped_reason}）—— 本次无法补扫，"
              f"请仍按各步骤原有截图证据判定")
        return
    origin = "页面顶部" if reset_to_top else "当前位置"
    print(f"  📷 补看帧 {total} 张（按页面自上而下顺序 = {origin}向下第 1~{total} 屏）:")
    for item in frames:
        # 同时给绝对路径与 --img 用的文件名：--img 只接受 frames/ 下的文件名
        print(f"     {item['index']}. {item['path']}")
        print(f"        --img {item['name']}")
    if stopped_reason == "boundary":
        if total == 1:
            print("  ↳ 页面不足一屏或不可滚动（回顶后再向下滑无变化），仅顶部 1 帧")
        else:
            print(f"  ↳ 再向下滑一屏时画面未变化（已到底），该重复帧已丢弃；上限 {scrolls} 帧")
    elif stopped_reason == "max_scrolls":
        if scrolls <= 1:
            print("  ↳ 帧数上限为 1，本次仅取证页面顶部画面")
        else:
            print(f"  ↳ 已滑满上限 {scrolls - 1} 次（页面仍可继续滚动，未到底）")


def _print_checks(checks, case_ws):
    """打印待复核项：步骤结论 + 该步自身截图 + 未落定断言 + 悬空 hook。"""
    print(f"  🔎 待二次复核 {len(checks)} 项:")
    for item in checks:
        head = f"     · {item['sid']}「{item['desc']}」 status={item['status']}"
        if item.get("reason"):
            head += f" reason={item['reason']}"
        print(head)
        shot = item.get("screenshot") or ""
        if shot:
            # 补扫帧现在是「页面顶部 → 向下」的序列，首帧=页面顶部，不再等于该步结束时的画面
            print(f"         该步自身截图: {frame_path(case_ws, shot)}")
        if item.get("pending_hooks"):
            print(f"         未完成 hook: {', '.join(item['pending_hooks'])}")
        for a in item.get("asserts") or []:
            label = _RESULT_LABELS.get(a["result"], a["result"])
            expect = a.get("expect") or ""
            line = f"         断言 {a['id']} [{a['kind']}/{a['match']}] 期望「{expect}」 → {label} {a['result']}"
            if a.get("actual"):
                line += f" / actual: {a['actual']}"
            print(line)


def _print_review_guide(has_frames):
    """一次性 review 指引 + 可直接照抄的改判命令模板。"""
    if not has_frames:
        print(f"  [REVIEW] 补扫未产出帧，无需改判；直接执行 "
              f"{render_cmd('flow-advance')} 推进到 C5_report")
        return
    print("  [REVIEW] 补看帧已按页面自上而下排序，一次性按顺序读完后对上面每一项做二次判定"
          "（只判一次，不要逐帧重复截图/滚动）:")
    print("     · 帧中出现预期内容 → 改判通过（证据引用命中帧）:")
    print("         " + render_cmd(
        'override-step-result --sid <sid> --pass '
        '--desc "post-scan 补扫命中（第 N 帧）: <看到的内容>" '
        '--img <命中帧文件名> '
        '--assert-verdict \'{"<断言id>": {"result": "pass", "verdict": "visual", '
        '"actual": "<帧中实测>"}}\''))
    print("     · 帧中出现相反证据（如售罄/报错/与期望不符）→ 不要改判通过，保持原失败结论即可")
    print("     · 帧中仍未出现 → 保持原结论，不需要执行任何命令")
    print(f"  判定完成后执行 {render_cmd('flow-advance')} 推进到 C5_report")


def cmd_case_post_scan(args):
    """case-post-scan 命令入口。"""
    root_dir = resolve_case_path(args.dir)
    ctx = fc_load(root_dir)
    if ctx is None:
        raise FlowStateError("POST-SCAN ABORT: flow-context.json 不存在")

    case_ws = current_case_workspace(root_dir, ctx)
    case_index = (ctx.get("current_case") or {}).get("index", 0)
    scrolls = getattr(args, "scrolls", None)
    scrolls = POST_SCAN_SCROLLS if scrolls is None else max(int(scrolls), 1)
    reset_to_top = SCROLL_TO_TOP and not getattr(args, "no_reset_top", False)

    checks = collect_open_checks(ctx)
    if not checks:
        # 关键：无失败/待判定项时**不碰设备**——正常通过的 case 不付任何补扫成本
        print("[POST-SCAN SKIP] 本 case 无失败/待判定项（断言全部落定），跳过滚动补扫")
        _write_evidence(case_ws, {
            "skipped": True, "reason": "no_open_checks", "case_index": case_index,
        })
        append_event(root_dir, "case.post_scan",
                     {"case_index": case_index, "skipped": True, "checks": 0})
        return

    print(f"[POST-SCAN] Case {case_index} 收尾补扫："
          f"{'先快速回到页面顶部，再' if reset_to_top else '从当前位置'}自上而下补看最多 {scrolls} 屏"
          f"（仅截图，不 dump 视图树）")
    outcome = capture_frames(case_ws, scrolls=scrolls, reset_to_top=reset_to_top)
    frames = outcome.get("frames") or []
    stopped_reason = outcome.get("stopped_reason", "")

    _print_frames(frames, scrolls, stopped_reason, reset_to_top=reset_to_top)
    _print_checks(checks, case_ws)
    _print_review_guide(bool(frames))

    evidence_path = _write_evidence(case_ws, {
        "skipped": False,
        "case_index": case_index,
        "scrolls": scrolls,
        "reset_to_top": reset_to_top,
        "stopped_reason": stopped_reason,
        "frames": frames,
        "checks": checks,
    })
    if evidence_path:
        print(f"  📝 补扫证据: {evidence_path}")
    append_event(root_dir, "case.post_scan", {
        "case_index": case_index,
        "skipped": False,
        "checks": len(checks),
        "reset_to_top": reset_to_top,
        "frames": [f["name"] for f in frames],
        "stopped_reason": stopped_reason,
    })


__all__ = ["cmd_case_post_scan"]
