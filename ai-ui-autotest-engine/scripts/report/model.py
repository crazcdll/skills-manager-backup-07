"""运行事实到报告投影之间的归一化模型。

steps.jsonl 是不可变的原始执行事实。本模块按 Flow SID 聚合，并保证一条不变量：
任何携带判定（ok 非空）的记录都是结论证据，必须进入统计口径。未声明 SID 的
判定记录归入 findings，与已声明步骤同权参与汇总，不允许静默降级为附注。
"""

from core.util.records import merge_screenshots, SRC_NOTE

# "retry"：重试步骤（如 S2b）的归属源。写入时 sid 已映射为父 sid，直接债入父步骤的 bucket
EXECUTION_SOURCES = {"step", "followup", "retry", "assert_fields"}
# 无判定备注（log-record --note）的归属源：只作展示，不进 executions 桶
ANNOTATION_SOURCE = SRC_NOTE

def _source(record):
    return record.get("_src", "step")


def _is_execution(record, has_matching_sid):
    """执行记录判定：来源在白名单中，或属于声明步骤且携带判定（ok != None）。

    不变量：任何携带判定的记录都是结论证据，不论 _src 是什么。
    这样后续新增 auto-correct / verified / auto_pass 等记录类型时，
    只需确保写入时设置 ok 字段即可自动进入执行桶，无需同步修改本模块。
    """
    if _source(record) in EXECUTION_SOURCES:
        return True
    if has_matching_sid and has_verdict(record):
        return True
    return False


def has_verdict(record):
    return record.get("ok") is not None


def _select_conclusion(executions):
    """conclusion 选取优先级：followup > retry > effect_verified > 其他（取最后一条）。

    同类型多条取最后一条（时序最新）。
    effect_verified 是自动修正的 PASS 记录，由 mark-hook-done 在 PENDING 步骤
    所有 required hooks 完成后自动追加，优先级高于原始 step 记录。
    """
    if not executions:
        return None
    followups = [r for r in executions if _source(r) == "followup"]
    if followups:
        return followups[-1]
    retries = [r for r in executions if _source(r) == "retry"]
    if retries:
        return retries[-1]
    # effect_verified: 自动修正 PASS 记录，优先级低于 retry 但高于原始 step
    verified = [r for r in executions if _source(r) == "effect_verified"]
    if verified:
        return verified[-1]
    return executions[-1]


def coalesce_evidence(executions, field, default=None):
    """从所有 executions 中取指定字段的第一个有效值（非 None、非空列表）。"""
    for record in executions:
        val = record.get(field)
        if val is not None and val != []:
            return val
    return default


def normalize_step_records(records, declared_sids):
    """归一化为逻辑步骤模型。

    返回 (normalized, findings, notes)：
    findings 是未绑定已声明 SID 但携带判定的记录，参与统计；
    notes 是无判定的游离记录，仅作展示。

    normalized[sid] 包含：
      conclusion  — 终态结论记录（followup > retry > step 优先级），用于取 ok/screenshot/fa
      executions  — 所有执行记录（step + followup + retry），用于 coalesce 证据字段
      attempts    — 有判定（ok 非 null）且非结论的记录，即「之前失败的尝试历史」；ok=null 的 PENDING 数据抓取记录不在此列
      annotations — log 类附注
    """
    declared_sids = set(declared_sids)
    grouped = {
        sid: {"executions": [], "annotations": []}
        for sid in declared_sids
    }
    findings = []
    notes = []

    for record in records:
        bucket = grouped.get(record.get("sid"))
        if bucket is None:
            if has_verdict(record):
                findings.append(record)
            else:
                notes.append(record)
            continue

        if _is_execution(record, has_matching_sid=True):
            bucket["executions"].append(record)
        else:
            bucket["annotations"].append(record)

    normalized = {}
    for sid, bucket in grouped.items():
        executions = bucket["executions"]
        conclusion = _select_conclusion(executions)
        # attempts 是「前几次失败尝试的历史记录」，语义要求：有判定（ok 非 null）且不是结论。
        # ok=null 的记录（api/track 数据抓取阶段，PENDING 等待 AI 判定）不是一次"尝试"，不进入 attempts。
        attempts = [r for r in executions if r is not conclusion and has_verdict(r)]
        normalized[sid] = {
            "conclusion": conclusion,
            "executions": executions,
            "attempts": attempts,
            "annotations": bucket["annotations"],
            # 截图证据：跨该 sid 的所有执行记录合并，conclusion 缺图时自动从其他记录补齐，
            # 彻底消除「conclusion 选中无图记录（override/log/assert-fields）→ 步骤截图丢失」。
            "screenshots": merge_screenshots(executions),
        }
    return normalized, findings, notes
