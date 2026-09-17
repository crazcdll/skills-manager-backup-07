#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""失败收口：SOP 阶段失败处理。

终止（abort）路径的不变式：**先落盘证据（报告 + 归档），再清理本地工作区**。

`post-clean` 会整目录删掉 `.run/`，而 `.run/` 是本次运行唯一的原始证据源
（flow-context、各 case 的 frames、timeline）。因此：

  - 一旦进入 abort（包括 AI 强制终止一个 on_fail=log_and_continue 的阶段），
    就先生成报告：`gen-report` 在 aborted 状态下会顺带完成 `.run/` 归档
    （archive_run → output/run-<ts>/run/）与入库，且 run_status=aborted；
  - 还没进 Case（环境准备阶段失败）时代理不了 Case 报告，则退化为只归档原始产物；
  - 两者都失败时**不执行 post-clean**，把现场留在 `.run/` 供人工取证。

历史缺陷（本模块就是因它而改）：报告生成被 `on_fail.generate_report` 门控，
被强制终止的阶段没这个字段 → 不生成报告；而 cleanup 里的 `flow-finalize`
又假设「报告已由 flow-fail 生成」→ 跳过归档；最后 post-clean 无条件删库，
报告与截图证据一并丢失，引擎提示的 `gen-report` 也再无法执行。
"""
import os
import subprocess
import time

from core.util.paths import ACTIVE_CASE_FILE, SKILL_DIR
from core.audit.runtime_audit import append_event, archive_run
from core.flow.flow_context import load_context, save_context, _find_stage
from core.sop.on_fail import _get_on_fail_config
from core.flow.state.status import _advance_to_next_case


def _generate_report():
    """生成报告（内部完成 .run/ 归档 + 入库）。

    Returns:
        (state, detail)：ok（detail=report.json 路径）/ no_case / failed（detail=错误摘要）
    """
    if not os.path.isfile(ACTIVE_CASE_FILE):
        return "no_case", ""

    try:
        result = subprocess.run(
            ["python3", "scripts/cli.py", "gen-report"],
            capture_output=True, text=True, timeout=180,
            cwd=SKILL_DIR,
        )
    except Exception as e:
        return "failed", str(e)

    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "report.json" in line and "file://" in line:
                return "ok", line.split("file://")[-1].strip()
        return "ok", ""

    lines = (result.stderr or result.stdout or "").strip().splitlines()
    return "failed", (lines[-1] if lines else "gen-report 非零退出")


def _archive_only(ctx, run_dir):
    """只归档 `.run/` 原始产物（无 Case 报告可用时的退化路径）。"""
    batch_output_dir = (ctx.get("meta") or {}).get("batch_output_dir")
    if not batch_output_dir:
        return "failed", "flow-context 缺少 batch_output_dir"
    try:
        archive_dir = archive_run(run_dir, batch_output_dir)
        return "archived_only", archive_dir
    except Exception as e:
        return "failed", f"archive_run 失败: {e}"


def _deliver_evidence(ctx, run_dir):
    """终止前必须落盘证据：优先生成报告（含归档），无报告可生成时至少归档原始产物。"""
    if os.path.isfile(ACTIVE_CASE_FILE):
        state, detail = _generate_report()
        if state in ("ok", "failed"):
            return state, detail
        # no_case：还没进 Case，没有 Case 报告可生成 → 走归档兜底
    return _archive_only(ctx, run_dir)


def _run_cleanup(safe_to_clean):
    """收尾清理：reset-env → flow-finalize → post-clean。

    Args:
        safe_to_clean: 证据是否已落盘；False 时**跳过 post-clean**，保住 .run/ 现场。

    Returns:
        {"ok": bool, "details": [...], "skipped_post_clean": str|None}
    """
    steps = [
        (["python3", "scripts/cli.py", "mock", "reset-env"], 60),
        (["python3", "scripts/cli.py", "flow-finalize"], 60),
    ]
    if safe_to_clean:
        steps.append((["python3", "scripts/cli.py", "post-clean"], 30))

    result = {"ok": True, "details": [], "skipped_post_clean": None}
    for cmd, timeout in steps:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout, cwd=SKILL_DIR)
            ok = r.returncode == 0
            entry = {"cmd": " ".join(cmd[-2:]), "ok": ok}
            if not ok:
                entry["error"] = (r.stderr or r.stdout or "").strip()[:200]
            result["details"].append(entry)
            result["ok"] = result["ok"] and ok
        except Exception as e:
            result["details"].append(
                {"cmd": " ".join(cmd[-2:]), "ok": False, "error": str(e)})
            result["ok"] = False

    if not safe_to_clean:
        result["skipped_post_clean"] = (
            "证据未落盘，已保留 .run/ 现场；处理后手动执行 "
            "python3 scripts/cli.py gen-report 再 post-clean"
        )
    return result


def fail_stage(run_dir, stage_id, error_msg, generate_report=False, cleanup=False):
    """记录 SOP 阶段失败，根据 on_fail 策略决定后续行为。

    策略行为：abort(终止)/skip_to_next_case(跳过)/pause/log_and_continue/best_effort。
    """
    ctx = load_context(run_dir)
    if ctx is None:
        return {"ok": False, "reason": "flow-context.json 不存在"}

    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    stage = _find_stage(ctx, stage_id)
    if stage:
        stage["status"] = "failed"
        stage["failed_at"] = now
        stage["error"] = error_msg

    errors = ctx.setdefault("errors", [])
    errors.append({"stage": stage_id, "error": error_msg, "ts": now})

    on_fail_config = _get_on_fail_config(stage) if stage else {}
    policy = on_fail_config.get("policy", "abort")
    aborted = False
    skipped_to_next = False
    best_effort = False

    if policy == "skip_to_next_case":
        _advance_to_next_case(ctx, now, verdict="failed", error_msg=error_msg)
        skipped_to_next = ctx["sop"]["current_stage"] != "done"
    elif policy == "best_effort":
        next_stage = None
        for s in ctx.get("sop", {}).get("stages", []):
            if s.get("status") in ("completed", "skipped", "failed"):
                continue
            next_stage = s
            break
        if next_stage:
            next_stage["status"] = "in_progress"
            next_stage["started_at"] = now
            ctx["sop"]["current_stage"] = next_stage["id"]
            best_effort = True
        else:
            ctx["sop"]["current_stage"] = "done"
    else:
        ctx["sop"]["current_stage"] = "aborted"
        aborted = True

    ctx["meta"]["last_updated"] = now
    save_context(run_dir, ctx)

    evidence_state, evidence_detail = "skipped", ""
    report_path = None
    if aborted:
        # 终止即交付：只要进入 abort 就必须先落盘证据，不受 stage 的
        # generate_report 门控（被强制终止的 log_and_continue 阶段没有该字段），
        # 否则随后 cleanup 的 post-clean 会删掉 .run/，证据不可恢复。
        evidence_state, evidence_detail = _deliver_evidence(ctx, run_dir)
        if evidence_state == "ok":
            report_path = evidence_detail or os.path.join(
                (ctx.get("meta") or {}).get("batch_output_dir", ""), "report.json")

    cleanup_result = None
    if cleanup:
        cleanup_result = _run_cleanup(
            safe_to_clean=evidence_state in ("ok", "archived_only"))

    return {
        "ok": True,
        "stage_id": stage_id,
        "aborted": aborted,
        "skipped_to_next": skipped_to_next,
        "best_effort": best_effort,
        "error": error_msg,
        "report_path": report_path,
        "evidence": {"state": evidence_state, "detail": evidence_detail},
        "cleanup": cleanup_result,
    }