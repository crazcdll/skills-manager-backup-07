#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一驱动 —— input-next / input-answer / input-status 的核心逻辑。

决策流程（框架内统一，provider 零参与）：

  1. 汇总所有 provider 的 questions
  2. schema 校验（引用完整性 / 类型）
  3. 拓扑排序（depends_on + group/order）
  4. provider.derive + source=derived → 派生回填（不提问）
  5. 求值 depends_on（不满足 → 不适用，跳过）
  6. 返回第一个「适用且未解决」的 ask 问题；全部解决 → done

AI 侧只需一个固定循环：`input-next → AskQuestion → input-answer`。

**稳定性机制（命令驱动 + 强指针 + 硬门禁）**：

  · `input-next` 每次只下发 **1 题**，并在输出里带**结构化 `next` 指针**
    （`kind=ask/next/proceed` + 可直接执行的 `cmd`）—— AI 照抄即可，无需自行编排；
  · `input-next` 把下发的题 id 记为「下发指针」，`input-answer` **只接受该指针所指的题**
    （批量 / 跳答 / 未先 `input-next` 一律拒绝）—— 把「一题一答」变成机制事实；
  · 提交一题后清空指针，AI 必须回到 `input-next` 取下一题。
"""
from shared.intake import IntakeContext
from provisioning.questions.registry import (
    all_providers, all_questions, all_derived_keys,
)
from provisioning.questions.schema import (
    GROUPS, MANUAL_INPUT_VALUE, SKIP_VALUE, parse_dep, question_view,
    referenced_ids, validate_questions, validate_value,
)
from shared.errors import ContractError, UsageError


# ═══════════════════════════════════════════════════════════════════
# 条件求值 / 拓扑排序
# ═══════════════════════════════════════════════════════════════════

def _gate_state(q: dict, ctx: IntakeContext) -> str:
    """depends_on 求值三态。

      · "ok"           —— 依赖全部就绪且谓词通过（可问 / 可预置 / 可派生）
      · "waiting"      —— 存在尚未解决的依赖（稍后可能变为 ok）
      · "inapplicable" —— 存在谓词为假（永不适用）

    "waiting" 与 "inapplicable" 必须区分：前者用于**挂起**预置值（待依赖
    就绪后自动落值），后者用于**拒绝**（如 A 环境下的 B-only 泳道题，不得落值）。
    """
    state = "ok"
    for expr in q["depends_on"]:
        qid, op, literal = parse_dep(expr)
        if not ctx.is_resolved(qid):
            if state == "ok":
                state = "waiting"
            continue
        if op is None:
            continue
        actual = "" if ctx.get(qid) is None else str(ctx.get(qid))
        if op == "==" and actual != literal:
            return "inapplicable"
        if op == "!=" and actual == literal:
            return "inapplicable"
        if op == "in" and actual not in literal:
            return "inapplicable"
    return state


def _depends_on_ok(q: dict, ctx: IntakeContext) -> bool:
    """依赖是否满足（等价于 `_gate_state(q, ctx) == "ok"`）。"""
    return _gate_state(q, ctx) == "ok"


def _sort_key(q: dict):
    return (GROUPS.index(q["group"]), q["order"], q["id"])


def _topological_order(questions: list) -> list:
    """按 depends_on 拓扑排序，同层按 (group, order, id) 稳定排序。"""
    by_id = {q["id"]: q for q in questions}
    indeg = {qid: 0 for qid in by_id}
    out_edges = {qid: [] for qid in by_id}
    for q in questions:
        for dep in referenced_ids(q):
            if dep not in by_id:
                continue          # 外部依赖（如 provider 派生键）：不参与拓扑，仅由就绪判定控制
            out_edges[dep].append(q["id"])
            indeg[q["id"]] += 1

    ready = sorted((qid for qid, d in indeg.items() if d == 0),
                   key=lambda qid: _sort_key(by_id[qid]))
    ordered = []
    while ready:
        qid = ready.pop(0)
        ordered.append(by_id[qid])
        for nxt in out_edges[qid]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
        ready.sort(key=lambda i: _sort_key(by_id[i]))

    if len(ordered) != len(questions):
        raise ContractError("depends_on 存在环，无法拓扑排序")
    return ordered


def _gather(ctx: IntakeContext):
    """汇总声明问题 + provider 派生值，并拓扑排序。

    depends_on 可引用「声明问题」或「provider 派生键」（如 `device_type`）。
    Returns:
        (ordered_questions, derived_values)
    """
    questions = all_questions(ctx)
    derived = {}
    for provider in all_providers():
        derived.update(provider.derive(ctx) or {})
    # 派生键：静态声明（稳定）+ 当轮实际产出（保险）一起作为允许引用的 id
    known = all_derived_keys() | set(derived)
    ordered = _topological_order(validate_questions(questions, known_ids=known))
    return ordered, derived


# ═══════════════════════════════════════════════════════════════════
# 派生回填
# ═══════════════════════════════════════════════════════════════════

def _apply_derived(ordered: list, derived: dict, ctx: IntakeContext) -> list:
    """让派生值反映**当前输入**（派生值 = 当前输入的纯函数）。

    历史语义是「首次求值后冻结（已有值不覆盖）」，这会让上游变更后下游读到过期
    派生值 —— 例如 `env_type` 由 A 改到 C 后，`auth_method` 仍是 `password`，使
    以派生键为条件的字段（`password`）既非 `inapplicable` 也无法被级联失效。
    故改为每轮重算、值变化即覆盖。

    例外：用户显式覆盖过的派生题（`overridable` + 已 `pin`，如 `resource_mis`
    允许改用其他 MIS）尊重用户值，不重算。
    """
    changed = []
    pinned = ctx.pinned
    for qid, value in derived.items():            # provider.derive 键（引擎所有）
        if ctx.get(qid) != value:
            ctx.answers[qid] = value
            changed.append(qid)
    for q in ordered:
        if q["source"] != "derived" or q["id"] in pinned:
            continue
        if not _depends_on_ok(q, ctx):
            continue
        value = q["resolve"](ctx)
        if ctx.get(q["id"]) != value:
            ctx.answers[q["id"]] = value
            changed.append(q["id"])
    if changed:
        ctx.save()
    return changed


# ═══════════════════════════════════════════════════════════════════
# 级联失效：环境/依赖变更后的失效传播
# ═══════════════════════════════════════════════════════════════════

def _reconcile(ctx: IntakeContext) -> list:
    """统一收口：① 让派生值反映最新输入 → ② 清理「已落库但当前不适用」的字段。

    背景：`inapplicable` 只在「求值当时」拒绝新值，不会清理**已落库**的旧值。
    当 `env_type` 从 A 切到 C 时，先落的 `ptest`（仅线上适用）会残留于 intake，
    随后被 `build_env_from_intake` 重新带入 env —— 这正是「配置与实际不符」的
    漏网路径。此处补齐：凡当前 `inapplicable` 的字段，其已落库答案、挂起的
    预置值与覆盖标记一并清除。

    必须**先重算派生值**：`password` 这类字段的条件是派生键 `auth_method`，只有
    派生值跟随 `env_type` 更新后，其适用性判定才正确。

    只清理 `inapplicable`（谓词为假、永不适用）；`waiting`（依赖尚未就绪）
    一律保留，否则会误删稍后才有效的值。

    Returns:
        被移除的字段 id 列表（供调用方留痕）。
    """
    ordered, derived = _gather(ctx)
    _apply_derived(ordered, derived, ctx)
    stale = [q["id"] for q in ordered if _gate_state(q, ctx) == "inapplicable"]
    return ctx.invalidate(stale)


# ═══════════════════════════════════════════════════════════════════
# 对外协议
# ═══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# 预置（seed）—— 收集循环开始前，把「用户已明确提供的值」一次性落库
# ══════════════════════════════════════════════════════════════════

def _settle_seeds(ctx: IntakeContext) -> tuple:
    """把 `pending_seeds` 中「依赖已就绪」的值落库，返回 (applied, rejected)。

    每轮重新 `_gather`（含派生），先落的预置值参与后题的 depends_on / 派生求值；
    "waiting" 的题保留挂起，下一轮 / 下一次调用再试；"inapplicable" 的题拒绝。
    直到某轮无进展或挂起清空为止（轮数上界 = 挂起数 + 1）。
    """
    pending = ctx.pending_seeds
    if not pending:
        return {}, []
    derived_keys = set(all_derived_keys())
    applied, rejected = {}, []
    for _ in range(len(pending) + 1):
        if not pending:
            break
        ordered, derived = _gather(ctx)
        _apply_derived(ordered, derived, ctx)
        by_id = {q["id"]: q for q in ordered}
        progressed = False
        for qid in list(pending):
            q = by_id.get(qid)
            if q is None:
                reason = ("派生键（引擎自动计算），不可预置" if qid in derived_keys
                          else "未知问题 id（见 input-schema）")
                rejected.append({"id": qid, "reason": reason})
                pending.pop(qid)
                progressed = True
                continue
            if q["source"] == "derived" and not q.get("overridable"):
                # 派生值 = 当前输入的纯函数，不接受外部注入（仅 overridable 派生题例外）
                rejected.append({"id": qid,
                                 "reason": "派生题（引擎自动计算），不可预置"})
                pending.pop(qid)
                progressed = True
                continue
            state = _gate_state(q, ctx)
            if state == "waiting":
                continue                         # 依赖未就绪 → 继续挂起
            if state == "inapplicable":
                rejected.append({"id": qid,
                                 "reason": "depends_on 条件不满足，当前环境不适用"})
                pending.pop(qid)
                progressed = True
                continue
            try:
                value = validate_value(q, pending[qid])
            except UsageError as exc:
                rejected.append({"id": qid, "reason": str(exc)})
                pending.pop(qid)
                progressed = True
                continue
            ctx.answers[qid] = value
            if q["source"] == "derived":
                ctx.pin(qid)          # 用户显式覆盖的派生题 → 后续不再重算
            applied[qid] = value
            pending.pop(qid)
            progressed = True
        if progressed:
            ctx.save()
        else:
            break
    if applied or rejected:
        ctx.save()
    return applied, rejected


def seed(ctx: IntakeContext, provided: dict) -> dict:
    """批量预置用户已明确提供的值（收集循环的**前置阶段**）。

    与 `input-answer` 共用同一套校验（白名单 + 类型容错 + depends_on），差异：
      · 不依赖 / 不占用「下发指针」——可一次提交多条，与逐题作答解耦；
      · 幂等 upsert（重复预置覆盖旧值）；
      · 依赖未就绪的值挂起于 `pending_seeds`，依赖就绪后自动落库，**不重复提问**；
      · 谓词为假（如 A 环境的 B-only 题）直接拒绝，避免污染。

    返回 `{seeded, deferred, rejected, remaining, done, next}`：AI 据此直接进
    `input-next` 只问 `remaining` 里的题。
    """
    provided = {str(k): v for k, v in dict(provided or {}).items()}
    ctx.pending_seeds.update(provided)         # 幂等 upsert
    ctx.save()
    applied, rejected = _settle_seeds(ctx)

    ordered, derived = _gather(ctx)
    _apply_derived(ordered, derived, ctx)
    _reconcile(ctx)
    if ctx.dispatched_id() and str(ctx.dispatched_id()) in applied:
        ctx.clear_dispatched()                 # 预置掉的题正好是当前下发题 → 指针失效

    remaining = [q["id"] for q in ordered
                 if q["source"] == "ask" and _gate_state(q, ctx) == "ok"
                 and not ctx.is_resolved(q["id"])]
    return {
        "ok": True,
        "seeded": applied,
        "deferred": sorted(ctx.pending_seeds),
        "rejected": rejected,
        "remaining": remaining,
        "done": not remaining,
        "next": _next_pointer() if remaining else _proceed_pointer(),
    }


def schema_view(ctx: IntakeContext) -> dict:
    """问题目录（预置前的发现入口）：全部声明问题（含选项）+ 派生键。"""
    ordered = _gather(ctx)[0]
    return {
        "derived_keys": sorted(all_derived_keys()),
        "questions": [question_view(q) for q in ordered],
    }


# 强指针里的固定约束文案（AI 只照抄，不自行编排）
_LOCKSTEP_NOTE = (
    "严格按本输出执行：只把 question.render.options 这 1 题交给 AskQuestion，"
    "再按其 cmd 提交；不得合并 / 跳答 / 自行编排。"
)


def _ask_pointer(q: dict) -> dict:
    """已下发某一题：给出「提问 + 提交」的强指针。"""
    qid = q["id"]
    return {
        "kind": "ask",
        "id": qid,
        "must_ask_only_this": True,
        "ask": {"prompt": q.get("prompt", ""), "render": q.get("render")},
        "cmd": (f"python3 scripts/cli.py input-answer --id {qid} "
                f"--value '<用户所选的 value>'"),
        "note": _LOCKSTEP_NOTE + " 提交后回到 input-next 取下一题。",
    }


def _next_pointer() -> dict:
    """仍有待收集项：要求 AI 回到 input-next（未下发前不得 input-answer）。"""
    return {
        "kind": "next",
        "cmd": "python3 scripts/cli.py input-next",
        "note": "还有待收集项：执行 input-next 取下一题（未下发前不得 input-answer）。",
    }


def _proceed_pointer() -> dict:
    """信息收集完成：给出阶段 0 后续命令（强指针）。"""
    return {
        "kind": "proceed",
        "note": ("信息收集完成，进入 Flow 转换与流程初始化；"
                 "把 {tag} / {run-name} / {Flow名} 替换为实际值。"),
        "cmds": [
            "python3 scripts/cli.py flow-convert --tag {tag}",
            "python3 scripts/cli.py cases-create --tag {tag}",
            "python3 scripts/cli.py steps-generate --input 'cases-{tag}.json' --tag {tag}",
            "python3 scripts/cli.py flow-init --dir {run-name} "
            "--input 'steps-input-{tag}.json' --flow-name {Flow名}",
            "python3 scripts/cli.py flow-next",
        ],
    }


def _remaining(ctx: IntakeContext) -> bool:
    """是否仍有「适用且未解决」的问题（不产生下发副作用）。"""
    _settle_seeds(ctx)                          # 依赖刚就绪的预置值先落库
    ordered, derived = _gather(ctx)
    _apply_derived(ordered, derived, ctx)
    return any(
        q["source"] == "ask" and _gate_state(q, ctx) == "ok" and not ctx.is_resolved(q["id"])
        for q in ordered
    )


def next_question(ctx: IntakeContext) -> dict:
    """下发下一个待解决问题（含 render/hint + 强指针）；全部解决 → done。

    每调用一次即把下发的题记为「下发指针」（硬门禁状态），并返回结构化 `next`。
    """
    seed_rejected = _settle_seeds(ctx)[1]
    ordered, derived = _gather(ctx)
    _apply_derived(ordered, derived, ctx)
    _reconcile(ctx)

    applicable = [q for q in ordered
                  if q["source"] == "ask" and _gate_state(q, ctx) == "ok"]
    resolved = sum(1 for q in applicable if ctx.is_resolved(q["id"]))
    pending = [q for q in applicable if not ctx.is_resolved(q["id"])]

    progress = {
        "total": len(applicable),
        "resolved": resolved,
        "pending": len(pending),
    }
    if not pending:
        ctx.clear_dispatched()
        result = {"done": True, "question": None, "progress": progress,
                  "next": _proceed_pointer()}
        if seed_rejected:
            result["seed_rejected"] = seed_rejected
        return result

    q = pending[0]
    ctx.set_dispatched(q["id"])          # ← 硬门禁：记录本次下发指针
    progress["group"] = q["group"]
    progress["index"] = resolved + 1
    result = {"done": False, "question": question_view(q), "progress": progress,
              "next": _ask_pointer(q)}
    if seed_rejected:
        result["seed_rejected"] = seed_rejected
    return result


def answer(ctx: IntakeContext, qid: str, value) -> dict:
    """提交一条答案（**只接受当前下发指针所指的题**），并返回下一步强指针。

    渲染信号（与 schema.build_render 的固定选项对应）：
      · __manual_input__ —— 不落值；保持下发指针，要求 AI 收真实值后重提；
      · __skip__         —— 仅 required=false 可跳过（按 default 落值），required 直接拒绝。

    硬门禁：只能提交「当前 input-next 刚下发」的那一题；批量 / 跳答 /
    未先 input-next 一律 UsageError —— 由引擎强制「一题一答」。
    """
    by_id = {q["id"]: q for q in _gather(ctx)[0]}
    if qid not in by_id:
        raise UsageError(f"input-answer: 未知问题 id={qid}")
    q = by_id[qid]
    if not _depends_on_ok(q, ctx):
        raise UsageError(f"input-answer: 问题 {qid} 的 depends_on 条件不满足")

    # ── 硬门禁：只接受当前下发指针所指的题 ──
    dispatched = ctx.dispatched_id()
    if not dispatched:
        raise UsageError(
            "input-answer: 当前没有已下发的问题。请先执行 `input-next` 获取当前题，"
            "再提交该题答案（禁止未下发直接作答 / 批量提交）。")
    if str(qid) != str(dispatched):
        raise UsageError(
            f"input-answer: 一次只能答一题，且只能是当前 input-next 下发的题"
            f"（当前下发: {dispatched}；收到: {qid}）。"
            f"请对 {dispatched} 提交答案，或先执行 `input-next` 取顺序中的当前题。")

    if value == MANUAL_INPUT_VALUE:
        # 保持下发指针：等待 AI 收取真实值后对同一题重提
        return {
            "ok": True, "resolved": None, "deferred": "manual_input",
            "id": qid, "done": False,
            "next": _ask_pointer(q),
            "hint": f"在对话中向用户收取 {qid} 的真实值，再执行 "
                    f"input-answer --id {qid} --value <值>（仍只答这一题）",
        }
    if value == SKIP_VALUE:
        if q.get("required"):
            raise UsageError(
                f"input-answer: 问题 {qid} 为必填，不能跳过；请提供真实值")
        ctx.resolve(qid, q.get("default"))
        ctx.clear_dispatched()
        _reconcile(ctx)
        has_more = _remaining(ctx)
        return {
            "ok": True, "resolved": qid, "skipped": True,
            "done": not has_more,
            "next": _next_pointer() if has_more else _proceed_pointer(),
        }

    validated = validate_value(q, value)
    ctx.resolve(qid, validated)
    ctx.clear_dispatched()
    _reconcile(ctx)
    has_more = _remaining(ctx)
    return {
        "ok": True,
        "resolved": qid,
        "done": not has_more,
        "next": _next_pointer() if has_more else _proceed_pointer(),
    }


def status(ctx: IntakeContext) -> dict:
    """总览：已解析 / 待问（**不回传答案值**，敏感字段不进任何输出）。"""
    _settle_seeds(ctx)
    ordered, _ = _gather(ctx)
    _reconcile(ctx)
    items = []
    for q in ordered:
        items.append({
            "id": q["id"],
            "group": q["group"],
            "prompt": q["prompt"],
            "source": q["source"],
            "required": q["required"],
            "applicable": _depends_on_ok(q, ctx),
            "resolved": ctx.is_resolved(q["id"]),
        })
    pending = [i["id"] for i in items
               if i["applicable"] and not i["resolved"] and i["source"] == "ask"]
    return {
        "questions": items,
        "resolved": sum(1 for i in items if i["resolved"]),
        "pending": pending,
        "pending_seeds": sorted(ctx.pending_seeds),
        "dispatched": ctx.dispatched_id(),
    }
