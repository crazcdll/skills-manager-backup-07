#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤级报告投影：单步/记录/备注 → 报告字段，并做证据合并与断言展开。"""
from core.util.records import resolve_screenshots
from report.model import coalesce_evidence
from report.schema import (
    EVIDENCE_META_KEYS, build_evidence, status_label, summary, verdict,
)
from report.timefmt import duration_ms


def _collect_text_mismatch(step):
    """从 hooks 的 ai_result.anomalies 中收集 TEXT_MISMATCH 详情。"""
    details = []
    for hook in step.get("hooks", []) or []:
        ai_result = hook.get("ai_result") or {}
        for anomaly in ai_result.get("anomalies") or []:
            if isinstance(anomaly, dict) and str(anomaly.get("type", "")).upper() == "TEXT_MISMATCH":
                detail = str(anomaly.get("detail", "")).strip()
                if detail:
                    details.append(detail)
    return details


def _record_action_text_mismatch(step, evidence):
    """把 hooks 中 `ai_result.anomalies` 的 TEXT_MISMATCH 记为「action 级口径差异」。

    语义边界：TEXT_MISMATCH 描述的是「action_arg 与页面节点文案不一致」（用例编写的口径
    问题），不是断言判定结果，因此：
      - 只写入 evidence.metadata.text_mismatch（机器可检索）与 evidence.reason（人可读）
      - 绝不修改断言条目的 result / verdict / reason

    历史实现会把该异常回写到断言（并用「仅一条断言→整条接锅」兜底匹配），曾把
    「费用明细」这种精确命中的断言错误降级为 semantic 并挂上与之无关的原因。
    """
    details = _collect_text_mismatch(step)
    if not details:
        return
    summary = " | ".join(details)[:300]
    evidence.setdefault("metadata", {})["text_mismatch"] = summary
    if not evidence.get("reason"):
        evidence["reason"] = "action 文案口径差异：" + summary

def _stage_report(stage):
    start = stage.get("started_at")
    end = stage.get("completed_at") or stage.get("failed_at")
    return {
        "_type": "sop_stage",
        "id": stage.get("id", ""),
        "desc": stage.get("desc", ""),
        "layer": stage.get("layer", ""),
        "case_index": stage.get("case_index"),
        "status": stage.get("status", "pending"),
        "started_at": start,
        "completed_at": stage.get("completed_at"),
        "failed_at": stage.get("failed_at"),
        "duration_ms": duration_ms(start, end),
        "error": stage.get("error") or None,
        "skip_reason": stage.get("skip_reason") or None,
        "command": stage.get("command") or None,
    }


def _record_report(record, images, kind="ui"):
    if not record:
        return {}
    value = verdict(record.get("ok"))
    shots = resolve_screenshots(record, images)
    return {
        "sid": record.get("sid") or None,
        "source": record.get("_src", "step"),
        "kind": kind,
        "desc": record.get("d", ""),
        "ok": value,
        "ok_label": status_label(value),
        # 与 step 记录对齐的 status 字段（step 为 completed/failed），便于前端/下游
        # 用同一套逻辑取色，不必区分 step 与 finding 两种记录结构。
        "status": {1: "completed", 0: "failed", 2: "warning"}.get(value, "pending"),
        "timestamp": record.get("ts"),
        "duration_ms": record.get("ms"),
        "duration_ms_inferred": bool(record.get("ms_inferred")),
        "screenshot": shots[0]["url"] if shots else None,
        "screenshots": shots,
        "note": record.get("note") or None,
        "evidence": build_evidence(record, images),
    }


def _note_report(record, images, kind="ui"):
    """无判定备注（log-record --note）的报告投影。

    与 _record_report 的关键差异：备注不携带判定，绝不能被 verdict() /
    status_label() 折叠成 WARN（verdict(None) == 2）。ok/ok_label 置 None、
    status 用 "note"，与 ack 人工结论保持同一形状，前端可直接按无判定展示。
    """
    if not record:
        return {}
    shots = resolve_screenshots(record, images)
    return {
        "sid": record.get("sid") or None,
        "source": record.get("_src", "step"),
        "kind": kind,
        "desc": record.get("d", ""),
        "ok": None,
        "ok_label": None,
        "status": "note",
        "timestamp": record.get("ts"),
        "duration_ms": record.get("ms"),
        "duration_ms_inferred": bool(record.get("ms_inferred")),
        "screenshot": shots[0]["url"] if shots else None,
        "screenshots": shots,
        "note": record.get("note") or None,
        "evidence": None,
    }


def _group_fields(fields, kind):
    if not fields:
        return {"groups": [], "highlighted": []}

    GROUP_RULES = [
        {"prefix": "api_assert.", "label": "数据断言", "collapsed": False},
        {"prefix": "val_lab.", "label": "业务标签"},
        {"prefix": "tag.", "label": "事件标签"},
        {"prefix": "lx_", "label": "内部字段", "collapsed": True},
        {"prefix": "request.", "label": "请求参数", "collapsed": True},
        {"prefix": "response.bizReq.", "label": "业务请求参数", "collapsed": True},
        {"prefix": "response.bizRes.", "label": "业务响应数据", "collapsed": True},
        {"prefix": "response.data.", "label": "页面数据", "collapsed": True},
        {"prefix": "response.", "label": "响应数据", "collapsed": True},
        {"prefix": "query.", "label": "查询参数", "collapsed": True},
        {"prefix": "req_headers.", "label": "请求头", "collapsed": True},
        {"prefix": "resp_headers.", "label": "响应头", "collapsed": True},
        {"prefix": "_", "label": "元数据", "collapsed": True},
    ]

    grouped = {}
    ungrouped = []

    for key, value in fields.items():
        matched_group = False
        for rule in GROUP_RULES:
            if key.startswith(rule["prefix"]):
                group_label = rule["label"]
                if group_label not in grouped:
                    grouped[group_label] = {"label": group_label, "fields": [], "collapsed": rule.get("collapsed", False)}
                grouped[group_label]["fields"].append({"key": key, "value": value})
                matched_group = True
                break
        if not matched_group:
            ungrouped.append({"key": key, "value": value})

    result_groups = list(grouped.values())
    if ungrouped:
        result_groups.append({"label": "其他", "fields": ungrouped})

    return {"groups": result_groups}


def _merge_evidence_fields(evidence, executions):
    """合并 evidence.fields 与 extracted_fields，补充 metadata 和 raw_evidence。

    以 EVIDENCE_META_KEYS 为唯一来源，从所有 executions 中 coalesce 补充
    conclusion 记录中缺失的元数据字段，消除手工维护字段子集导致的不一致。
    """
    merged_fields = evidence.get("fields") or coalesce_evidence(executions, "extracted_fields", {})
    if merged_fields and (not evidence.get("fields") or evidence["fields"] != merged_fields):
        evidence["fields"] = merged_fields

    existing_meta = evidence.get("metadata", {})
    for mk in EVIDENCE_META_KEYS:
        if mk in existing_meta:
            continue
        mv = coalesce_evidence(executions, mk, None)
        if mv is not None:
            evidence["metadata"][mk] = mv

    raw_ev = coalesce_evidence(executions, "raw_evidence", None)
    if raw_ev is not None:
        if not evidence.get("raw"):
            evidence["raw"] = {}
        if "raw_evidence" not in evidence["raw"]:
            evidence["raw"]["raw_evidence"] = raw_ev

    # expected_fields（API / Track 断言待校验字段清单）
    # 仅在 field_results 不存在时才合并 expected_fields，避免平台用 expected_fields 做
    # 自动匹配（字段路径可能不匹配 extracted_fields 的 key 命名，如 "bizType" vs "query.bizType"）。
    # 当 field_results 已存在时，AI 的 assert-fields 结果才是准确结论。
    if "expected_fields" not in evidence:
        # 检查是否已有 field_results（说明 AI 已完成字段断言）
        has_field_results = False
        if evidence.get("raw") and evidence["raw"].get("field_results"):
            has_field_results = True
        if not has_field_results:
            fr = coalesce_evidence(executions, "fa", None)
            if fr and isinstance(fr, dict) and fr.get("field_results"):
                has_field_results = True
        if not has_field_results:
            ef = coalesce_evidence(executions, "expected_fields", None)
            if ef is not None:
                evidence["expected_fields"] = ef


def _build_assertions(evidence, normalized, conclusion_report):
    """把运行时 asserts（结构化断言）与 AI 逐条判定（assert_verdicts，键=断言 id）合并。

    输出 evidence["assertions"] = [结构化断言结果]，文本/视觉同构：
      {id, kind, match?, expect, targets, criteria?, on_fail?,
       result, verdict, actual, reason, evidence, available}

    断言 id 由引擎在 parse_asserts 阶段按序分配（A1/A2…），AI 判定按 id 引用，
    不再用「{type}.{长文本}」拼接 key。合并逻辑与 flow-context 回写层共用
    assertions.engine.apply_verdicts（单一实现）。
    """
    conclusion = normalized.get("conclusion") or {}
    asserts_list = conclusion.get("asserts") or []
    if not asserts_list:
        asserts_list = coalesce_evidence(normalized["executions"], "asserts", [])
    if not asserts_list:
        return

    # 延迟导入：报告模块不在 import 期拉起断言包（断言包会拉起策略与探针）
    from assertions.engine import apply_verdicts

    ai_verdicts = conclusion.get("assert_verdicts") or {}
    merged = apply_verdicts(
        [dict(item) for item in asserts_list if isinstance(item, dict)],
        ai_verdicts,
    )
    for entry in merged:
        entry.setdefault("kind", "text")
        entry.setdefault("result", "pending")

    if merged:
        evidence["assertions"] = merged


def _expand_field_results_to_fields(evidence):
    """将 API 步骤的 field_results（AI hook 断言结果）展平到 evidence.fields 中。

    field_results 存储在 evidence.raw.field_results 中，格式为：
      [{"field":"字段名","expected":"预期值","actual":"实际值","pass":true,"reason":""}]
    展平后 key 为 "api_assert.{field}"，value 为 "pass"/"fail"。

    注意：不再单独写入 api_expected.* 和 api_actual.* 字段，因为：
    1. assert-fields 命令的结论已展示字段断言概要
    2. 断言通过时 expected == actual，展示完全相同的值无意义
    3. 断言失败时用户可通过 assert-fields 的详细证据查看具体值
    这三个维度分散到三个分组展示，导致报告中同样字段信息重复出现。
    """
    raw = evidence.get("raw")
    if not raw:
        return
    field_results = raw.get("field_results")
    if not field_results:
        return

    if not evidence.get("fields"):
        evidence["fields"] = {}

    for fr in field_results:
        field_name = fr.get("field", "unknown")
        passed = fr.get("pass", False)
        key = f"api_assert.{field_name}"
        evidence["fields"][key] = "pass" if passed else "fail"




def build_step(step, normalized, images):
    sid = step.get("sid", "")
    kind = step.get("kind", "ui")
    normalized_conclusion = normalized["conclusion"]
    executions = normalized["executions"]
    conclusion_report = _record_report(normalized_conclusion, images, kind)
    attempts = [_record_report(r, images, kind) for r in normalized["attempts"]]
    annotations = [_record_report(r, images, kind) for r in normalized["annotations"]]
    # 步骤截图：跨该 sid 全部执行记录合并，conclusion 缺图自动从其他记录补齐
    step_shots = resolve_screenshots(normalized.get("screenshots") or [], images)

    evidence = conclusion_report.get("evidence")
    if evidence:
        _merge_evidence_fields(evidence, executions)
        _build_assertions(evidence, normalized, conclusion_report)
        _expand_field_results_to_fields(evidence)
        # 异常回写：action 级 TEXT_MISMATCH → evidence.metadata/reason（不入断言）
        _record_action_text_mismatch(step, evidence)
        # 证据截图对齐合并后的步骤截图（conclusion 自身缺图时补齐，避免 step.screenshot 有图而 evidence 无图）
        if step_shots:
            if not evidence.get("screenshots"):
                evidence["screenshots"] = step_shots
            if not evidence.get("screenshot"):
                evidence["screenshot"] = step_shots[0]["url"]

    assertions = (evidence or {}).get("assertions") or []
    # 步骤级「待人工确认」：存在 AI 主观判定（语义/视觉）通过的断言。
    # 派生自断言层的 needs_review（唯一实现见 assertions.engine.compute_needs_review），
    # 供报告/平台在步骤上打标，提示人工复核，避免主观判定被当作确定通过。
    needs_review = any(
        bool(a.get("needs_review")) for a in assertions if isinstance(a, dict)
    )

    # 一致性护栏（双向一致性的唯一实现见 assertions.engine.compute_result_from_entries）：
    # 断言含 result=fail 时步骤结论不得为 PASS，否则报告自相矛盾
    # （卡片显示「断言失败」而步骤显示「通过」）。单向：不把 AI 的 FAIL 提升为 PASS。
    from assertions.engine import compute_result_from_entries

    step_ok = conclusion_report.get("ok")
    failed_assertions = [a for a in assertions if a.get("result") == "fail"]
    if failed_assertions and compute_result_from_entries(assertions) == 0 and step_ok == 1:
        step_ok = 0
        if isinstance(evidence, dict):
            hint = f"断言存在失败项（{len(failed_assertions)} 项），步骤结论已按断言校正为失败"
            evidence["reason"] = f"{evidence.get('reason')}\n{hint}" if evidence.get("reason") else hint

    # 非断言类字段（api_assert.* / val_lab.* 等），断言已走 evidence.assertions
    fields = (evidence or {}).get("fields") or coalesce_evidence(executions, "extracted_fields", {})

    return {
        "sid": sid,
        "kind": kind,
        "desc": step.get("desc", ""),
        "action": step.get("action") if kind == "ui" else None,
        "action_arg": step.get("action_arg") if kind == "ui" else None,
        "action_anchor": step.get("action_anchor") if kind == "ui" else None,
        "step_type": step.get("step-type") if kind == "ui" else None,
        "status": step.get("status", "pending"),
        "hooks": step.get("hooks", []),
        "ok": step_ok,
        "ok_label": status_label(step_ok) if step_ok is not None else conclusion_report.get("ok_label"),
        # 存在 AI 判定通过的断言 → 步骤待人工确认（平台据此特殊标识）
        "needs_review": needs_review,
        # 步骤级说明（AI 通过 override-step-result --note 写入）。此前仅存在于 raw_records，
        # 投影到步骤对象后，报告与前端可直接追溯到“为什么”
        "note": conclusion_report.get("note") or None,
        "started_at": step.get("started_at") or conclusion_report.get("timestamp"),
        "completed_at": step.get("completed_at"),
        "duration_ms": conclusion_report.get("duration_ms"),
        "duration_ms_inferred": conclusion_report.get("duration_ms_inferred", False),
        "screenshot": step_shots[0]["url"] if step_shots else None,
        "screenshots": step_shots,
        "evidence": evidence,
        "fields_grouped": _group_fields(fields, kind),
        "attempts": attempts,
        "retry_count": len(attempts),
        "annotations": annotations,
    }
