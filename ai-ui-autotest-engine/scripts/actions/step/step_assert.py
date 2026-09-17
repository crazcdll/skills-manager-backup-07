"""步骤断言管道（数据收集模式）：解析 asserts → 引擎执行 → 打印/汇总。"""
import json
import sys
from screen_state.inspect_tree import invalidate_cache
from assertions.engine import AssertionEngine, parse_asserts, ExecutionContext, build_assertions_dict
from assertions.constants import RESULT_LABELS, VERDICT_LABELS, KIND_LABELS, RESULT_PENDING, KIND_TEXT, MATCH_GONE


def _execute_assertion_pipeline(args, ops, case_workspace, screenshot_path, sid_arg, inspect_tree_impact):
    """执行断言数据收集，返回断言结果。"""
    assertion_results = []
    assertions_dict = {}
    execute_results = []

    raw_asserts = getattr(args, "asserts", None)
    if not raw_asserts:
        return assertion_results, assertions_dict, execute_results

    if inspect_tree_impact != "none":
        invalidate_cache()

    if isinstance(raw_asserts, str):
        try:
            raw_asserts = json.loads(raw_asserts)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"  ⚠️ asserts JSON 解析失败: {e}", file=sys.stderr)
            raw_asserts = []

    specs = parse_asserts(raw_asserts)
    engine = AssertionEngine()
    context = ExecutionContext(
        ops=ops,
        case_ws=case_workspace,
        sid=getattr(args, "sid", ""),
        screenshot_path=screenshot_path or "",
    )
    execute_results = engine.execute(specs, context)
    assertion_results = [result.to_dict() for result in execute_results]
    assertions_dict = build_assertions_dict(execute_results)

    for result in assertion_results:
        _print_assertion_result(result)

    return assertion_results, assertions_dict, execute_results
def _print_assertion_result(result):
    """打印单条断言结果（结构化：id / kind / expect / result / verdict / evidence）。"""
    kind = result.get("kind", KIND_TEXT)
    result_value = result.get("result", RESULT_PENDING)
    verdict = result.get("verdict", "")
    available = result.get("available", False)
    evidence = result.get("evidence") or {}
    kind_label = KIND_LABELS.get(kind, kind)
    status = RESULT_LABELS.get(result_value, "❓")
    if verdict:
        status += f" {VERDICT_LABELS.get(verdict, verdict)}"
    if result_value == RESULT_PENDING and not available:
        status = "❌"
    detail = f" [{kind_label}] {result.get('id', '')} {result.get('expect', '')}"
    if evidence.get("matched_text"):
        # gone 断言用「确认消失」替代「匹配」，避免日志歧义
        match_label = "确认消失" if result.get("match") == MATCH_GONE else "匹配"
        detail += f" → {match_label}「{evidence['matched_text']}」"
    if evidence.get("match_level", -1) >= 0:
        detail += f" (level={evidence['match_level']})"
    for idx, target in enumerate(result.get("targets") or [], 1):
        if isinstance(target, dict):
            detail += f"\n       {idx}. {target.get('expect', '')} → {target.get('result', '')}"
    print(f"  {status} {detail}")
    if result.get("reason"):
        print(f"    └ 原因: {result['reason']}")
    if evidence.get("sidecar"):
        print(f"    └ 元素索引: {evidence['sidecar']}")
    if evidence.get("screenshot"):
        print(f"    └ 截图: {evidence['screenshot']}")
def _collect_unavailable_assertions(assertion_results):
    """收集数据不可用的断言。"""
    unavailable = [r for r in assertion_results if not r.get("available", False)]
    if not unavailable:
        return [], ""
    failure_reasons = [f"「{f.get('expect', '')}」数据不可用" for f in unavailable]
    return unavailable, "; ".join(failure_reasons)
