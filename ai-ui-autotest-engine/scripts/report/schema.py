from core.util.records import resolve_screenshots

STATUS_LABELS = {1: "PASS", 2: "WARN", 0: "FAIL"}
VERDICT_STRING = {1: "pass", 0: "fail", 2: "warn", None: "pending"}

EVIDENCE_META_KEYS = (
    "matched", "http_code", "val_cid", "val_bid",
    "event_nm", "appmock_url",
    "host", "path", "method",
    "req_headers", "resp_headers",
    "text_mismatch",
)

# raw_evidence 体积庞大，单独存放，不混入 metadata
RAW_EVIDENCE_KEY = "raw_evidence"

# 提取 reason 的优先级：fa.error（人话描述）> fa.reason（机器码）> fa.note
def _extract_reason(fa):
    if not fa:
        return ""
    return fa.get("error") or fa.get("reason") or fa.get("note") or ""


def verdict(value):
    if value == 1:
        return 1
    if value == 2:
        return 2
    if value is None:  # PENDING（AI 待确认，T2/T3 断言或 api/track 步骤数据抓取阶段）
        return 2
    return 0


def status_label(value):
    return STATUS_LABELS[verdict(value)]


def summary(total=0, passed=0, warned=0, failed=0):
    return {
        "total": total,
        "pass": passed,
        "warn": warned,
        "fail": failed,
        "pass_rate": round(passed / total, 4) if total else None,
    }


def assertion_summary(steps):
    """从 steps[].evidence.assertions 聚合断言统计。

    返回三个正交维度：
      results      — 判成什么：{"pass": N, "fail": N, "pending": N}
      verdicts     — 怎么判出来的：{"exact": N, "semantic": N, "visual": N}
      needs_review — 需人工复核的断言数（AI 主观判定通过，见 compute_needs_review）
    """
    results = {"pass": 0, "fail": 0, "pending": 0}
    verdicts = {"exact": 0, "semantic": 0, "visual": 0}
    needs_review = 0
    for step in steps or []:
        for item in (step.get("evidence") or {}).get("assertions") or []:
            result_value = item.get("result")
            if result_value in results:
                results[result_value] += 1
            mode = item.get("verdict")
            if mode in verdicts:
                verdicts[mode] += 1
            if item.get("needs_review"):
                needs_review += 1
    return {"results": results, "verdicts": verdicts, "needs_review": needs_review}


def aggregate_assertion_summaries(summaries):
    """把多个 case 的断言统计聚合到 batch 维度。

    入参为 case 的 {"results": {...}, "verdicts": {...}}（或含它们的 summary）。
    """
    agg = {
        "results": {"pass": 0, "fail": 0, "pending": 0},
        "verdicts": {"exact": 0, "semantic": 0, "visual": 0},
        "needs_review": 0,
    }
    for item in summaries or []:
        if not isinstance(item, dict):
            continue
        source_map = {
            "results": item.get("assert_results") or {},
            "verdicts": item.get("assert_verdicts") or {},
        }
        for bucket in ("results", "verdicts"):
            source = source_map[bucket]
            for key in agg[bucket]:
                agg[bucket][key] += source.get(key, 0)
        agg["needs_review"] += int(item.get("assert_needs_review") or 0)
    return agg


def build_evidence(record, images):
    if not record:
        return None
    ok_val = verdict(record.get("ok"))
    fa = record.get("fa") if isinstance(record.get("fa"), dict) else None

    # 提取结论描述：
    # - fa.error/reason/note 是 FAIL/WARN 场景的机器可读失败原因，优先展示；
    # - followup 记录的 d 字段是 AI 显式写入的分析结论（如 override-step-result --desc "..."），
    #   在 fa 为空时（PASS 场景）作为通过说明；
    # - 普通 step 记录的 d 是步骤描述，作为最后兜底（让 EvidenceCard 始终有说明文字展示）。
    is_followup = record.get("_src") == "followup"
    step_desc = record.get("d") or ""
    followup_desc = step_desc if is_followup else ""
    fa_reason = _extract_reason(fa)
    reason = fa_reason or followup_desc or step_desc
    # record.note 是 AI 通过 --note 写入的「结论之外的关键说明」（例如：断言已通过，
    # 但实测值与 Flow 期望存在差异）。追加到 reason 末尾，使其随判定结论卡片一并展示，
    # 前端无需单独适配 note 字段。
    note = (record.get("note") or "").strip()
    if note and note not in reason:
        reason = f"{reason}\n{note}" if reason else note

    # 截图：统一从 record.screenshots（数组）解析，不再读取历史单字段 img
    shots = resolve_screenshots(record, images)
    screenshot = shots[0]["url"] if shots else None

    # 元数据：只取精简的关键字段
    metadata = {}
    for k in EVIDENCE_META_KEYS:
        v = record.get(k)
        if v is not None:
            metadata[k] = v

    # 原始 fa 数据（去掉 screenshot 避免重复）
    raw = None
    if fa:
        raw = {k: v for k, v in fa.items() if k != "screenshot"}

    # raw_evidence（完整录制数据）合并到 raw 中
    raw_evidence = record.get(RAW_EVIDENCE_KEY)
    if raw_evidence is not None:
        if raw is None:
            raw = {}
        raw[RAW_EVIDENCE_KEY] = raw_evidence

    # 字段
    fields = record.get("extracted_fields") or {}

    # API / Track 断言的 expected_fields 和 field_results
    expected_fields = record.get("expected_fields") or None
    field_results = None
    if fa and "field_results" in fa:
        field_results = fa["field_results"]

    # 无有效内容时不生成 evidence（reason 存在则始终生成）
    if not reason and not fa and not metadata and not fields and not expected_fields:
        if ok_val == 1 and screenshot:
            return {
                "verdict": VERDICT_STRING.get(ok_val, "pending"),
                "reason": "",
                "raw": None,
                "fields": {},
                "screenshot": screenshot,
                "screenshots": shots,
                "metadata": {},
            }
        return None

    result = {
        "verdict": VERDICT_STRING.get(ok_val, "pending"),
        "reason": reason,
        "raw": raw,
        "fields": fields,
        "screenshot": screenshot,
        "screenshots": shots,
        "metadata": metadata,
    }
    if expected_fields is not None:
        result["expected_fields"] = expected_fields
    if field_results is not None:
        result["field_results"] = field_results
    return result
