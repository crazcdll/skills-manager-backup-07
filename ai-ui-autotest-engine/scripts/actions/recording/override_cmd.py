"""override-step-result 命令：覆盖已声明步骤的终态结论（含逐断言结构化判定）。"""

import json
import sys

from core.errors import FlowStateError, UsageError
from core.util.case_utils import resolve_case_path, current_case_workspace
from core.flow.flow_context import load_context as fc_load
from core.flow.step_scheduler import apply_followup_result as fc_apply_followup
from core.util.records import StepRecord, SRC_FOLLOWUP, SHOT_AUTO
from actions.assertion_utils import _resolve_step_ok
from actions.recording.common import (
    _resolve_duration, _validate_screenshot_reference,
    _build_failure_analysis_from_args, _auto_capture_screenshot,
    _report_step_binding,
    STEP_OK_STATUS,
)
from assertions.constants import RESULT_PASS, RESULT_FAIL, RESULT_PENDING


def _normalize_assert_verdicts(raw_verdicts):
    """归一化 AI 的 --assert-verdict（键=断言 id）。

    支持两种写法：
      "A1": "pass"                       —— 只给结果
      "A3": {"result": "fail", "verdict": "visual",
             "actual": "实测 13 位",
             "reason": "未满足 criteria：券码为 11 位数字",
             "targets": [{"expect": "二维码可见", "result": "pass", "actual": "可见"}]}

    归一化后每条固定为：{result, verdict, actual, reason, targets}
    """
    normalized = {}
    if not isinstance(raw_verdicts, dict):
        return normalized
    for key, value in raw_verdicts.items():
        aid = str(key or "").strip()
        if not aid:
            continue
        if isinstance(value, str):
            entry = {"result": value.strip().lower()}
        elif isinstance(value, dict):
            entry = dict(value)
            entry["result"] = str(entry.get("result") or RESULT_PENDING).strip().lower()
        else:
            continue
        if entry["result"] not in (RESULT_PASS, RESULT_FAIL, RESULT_PENDING):
            entry["result"] = RESULT_PENDING
        entry["verdict"] = str(entry.get("verdict") or "").strip().lower()
        entry["actual"] = str(entry.get("actual") or "").strip()
        entry["reason"] = str(entry.get("reason") or "").strip()
        targets = entry.get("targets")
        entry["targets"] = (
            [t for t in targets if isinstance(t, dict)] if isinstance(targets, list) else []
        )
        normalized[aid] = entry
    return normalized


def _enforce_step_ok(ok, assert_verdicts):
    """护栏：存在 result=fail 的断言时，步骤终态必须为 FAIL（0）。

    护栏规则复用 assertions.engine.compute_result_from_entries（单一实现），
    与 flow-context 回写层、报告层保持完全一致的语义。

    Returns: (ok, notices)
    """
    notices = []
    if not assert_verdicts:
        return ok, notices
    from assertions.engine import compute_result_from_entries

    entries = []
    for value in assert_verdicts.values():
        entries.append(value if isinstance(value, dict) else {"result": value})
    has_fail = compute_result_from_entries(entries) == 0
    if has_fail and ok != 0:
        ok = 0
        notices.append("断言含 result=fail → 步骤强制 FAIL")
    return ok, notices


def _declared_assertion_ids(flow_context, sid):
    """取出步骤声明的断言 id 列表（快照自 flow-context）。"""
    for step in (flow_context or {}).get("steps", []) or []:
        if step.get("sid") != sid:
            continue
        ids = []
        for items in (step.get("assertions") or {}).values():
            for item in items or []:
                if isinstance(item, dict) and item.get("id"):
                    ids.append(str(item["id"]))
        return ids
    return []


def _pending_assertion_ids(flow_context, sid):
    """取出仍为 pending 的断言 id。"""
    pending = []
    for step in (flow_context or {}).get("steps", []) or []:
        if step.get("sid") != sid:
            continue
        for items in (step.get("assertions") or {}).values():
            for item in items or []:
                if isinstance(item, dict) and item.get("result") == RESULT_PENDING:
                    pending.append(str(item.get("id") or ""))
    return pending


def _report_verdict_issues(known_ids, pending_ids, assert_verdicts):
    """把「断言 id 写错」与「断言未判定却给步骤终态」两类问题显式暴露。

    两者都会让报告出现「步骤结论与断言判定不一致」的隐性错误：
      - 错写的键会被静默忽略（旧 schema 用 "{type}.{长文案}" 作键时极容易发生）
      - 未判定的断言会以 pending 计入断言统计
    """
    if known_ids and assert_verdicts:
        unknown = [aid for aid in assert_verdicts if aid not in known_ids]
        if unknown:
            print(f"  ⚠️ --assert-verdict 含未声明的断言 id: {unknown}"
                  f"（本步骤声明的 id: {known_ids}）；这些键不会生效，请改用声明 id",
                  file=sys.stderr)
    if pending_ids and not assert_verdicts:
        print(f"  ⚠️ 本步骤仍有 {len(pending_ids)} 条断言未判定: {pending_ids}；"
              f"未传 --assert-verdict 时它们会以 pending 计入断言统计，"
              f"请用 --assert-verdict 一次性给出判定", file=sys.stderr)


def _cmd_override_step_result(args):
    """override-step-result 命令入口。"""
    root_dir = resolve_case_path(args.dir)
    flow_context = fc_load(root_dir)
    if flow_context is None:
        raise FlowStateError("OVERRIDE ABORT: flow-context.json 不存在")
    case_workspace = current_case_workspace(root_dir, flow_context)

    sid = getattr(args, "sid", None)
    if not sid:
        raise UsageError("OVERRIDE ABORT: --sid 是必填参数")

    desc = getattr(args, "desc", "")
    note = getattr(args, "note", "") or ""
    log_type = getattr(args, "log_type", "override") or "override"

    ok = _resolve_step_ok(args)
    duration, _ = _resolve_duration(args, case_workspace)

    # ── 读取 --assert-verdict（JSON dict：键=断言 id，值=结构化判定） ────
    assert_verdict = getattr(args, "assert_verdict", None)
    raw_verdicts = None
    if assert_verdict:
        try:
            raw_verdicts = json.loads(assert_verdict)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"  ⚠️ --assert-verdict JSON 解析失败: {e}", file=sys.stderr)

    assert_verdicts_dict = _normalize_assert_verdicts(raw_verdicts)

    # ── 护栏：断言含 fail 时步骤终态必须为 FAIL ──
    notices = []
    if assert_verdicts_dict:
        ok, ok_notices = _enforce_step_ok(ok, assert_verdicts_dict)
        notices.extend(ok_notices)
        for item in notices:
            print(f"  ⚠️ VERDICT 护栏: {item}")
    if notices:
        note = (note + " | " if note else "") + "；".join(notices)

    status_label = STEP_OK_STATUS.get(ok, "❌ FAIL")
    fa = _build_failure_analysis_from_args(args)
    img_name = _auto_capture_screenshot(args, case_workspace)
    _validate_screenshot_reference(img_name, case_workspace)
    # ── 统一记录契约（StepRecord）────────────────────────────
    record = StepRecord(
        sid=sid,
        src=SRC_FOLLOWUP,
        type=log_type,
        desc=desc,
        ok=ok,
        status=status_label,
        ms=duration,
        note=note,
        failure=fa,
    )
    if assert_verdicts_dict:
        record.extra["assert_verdicts"] = assert_verdicts_dict
    record.shot(img_name, label="结论截图", kind=SHOT_AUTO)
    record.append(case_workspace)

    # 更新 flow-context：步骤终态 + 逐断言判定一并回写。
    # 只写终态会让 flow-status / flow-case-status 永远显示断言 pending，
    # 使 AI 误判「判定没生效」而重复 override（污染 attempts / retry_count）。
    _report_verdict_issues(
        _declared_assertion_ids(flow_context, sid),
        _pending_assertion_ids(flow_context, sid),
        assert_verdicts_dict,
    )
    fc_apply_followup(root_dir, sid, ok, assert_verdicts_dict or None)

    print(f"OVERRIDE [{sid}]: {desc} → {status_label} ({duration}ms)")
    _report_step_binding(sid, "override-step-result", log_type)
