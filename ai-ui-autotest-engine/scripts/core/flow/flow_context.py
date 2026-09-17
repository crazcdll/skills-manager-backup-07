#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flow-context.json 数据访问层：JSON 读写、条件评估、完成校验。

所有对 flow-context.json 的底层逻辑集中在此，供其他 core 模块及外部消费者依赖。
"""
import glob
import json
import os
import sys
import time

from core.util.case_utils import resolve_case_path
from core.util.json_utils import write_json_atomic, read_json
from core.util.paths import OUTPUT_DIR
from core.sop.constants import FLOW_CONTEXT_FILENAME


# ═══════════════════════════════════════════════════════════════════
# JSON 读写
# ═══════════════════════════════════════════════════════════════════

def _context_path(run_dir):
    return os.path.join(run_dir, FLOW_CONTEXT_FILENAME)

def load_context(run_dir):
    """读取 flow-context.json，不存在返回 None。"""
    run_dir = resolve_case_path(run_dir)
    path = _context_path(run_dir)
    if not os.path.isfile(path):
        return None
    try:
        return read_json(path, default=None)
    except (json.JSONDecodeError, IOError) as e:
        sys.stderr.write(f"[flow_context] load_context JSON 损坏 ({path}): {e}\n")
        return None

def save_context(run_dir, ctx):
    """写入 flow-context.json（原子写入）。"""
    run_dir = resolve_case_path(run_dir)
    path = _context_path(run_dir)
    os.makedirs(run_dir, exist_ok=True)
    ctx["meta"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    write_json_atomic(path, ctx)

# ═══════════════════════════════════════════════════════════════════
# 轻量 meta 读写（不需要加载完整 context 的场景）
# ═══════════════════════════════════════════════════════════════════

def update_meta_fields(path, fields: dict):
    ctx = read_json(path)
    if not ctx:
        sys.stderr.write(f"[flow_context] 警告：读取 meta 失败 ({path})\n")
        return
    ctx.setdefault("meta", {}).update(fields)
    ctx["meta"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        write_json_atomic(path, ctx)
    except OSError as e:
        sys.stderr.write(f"[flow_context] 警告：写入 meta 失败 ({path}): {e}\n")

def read_meta_fields(path) -> dict:
    return read_json(path, {}).get("meta", {})

# ═══════════════════════════════════════════════════════════════════
# 阶段查找
# ═══════════════════════════════════════════════════════════════════

def _find_stage(ctx, stage_id):
    """在 sop.stages 列表中查找指定 stage。"""
    for s in ctx.get("sop", {}).get("stages", []):
        if s.get("id") == stage_id:
            return s
    return None

# ═══════════════════════════════════════════════════════════════════
# 点路径取值
# ═══════════════════════════════════════════════════════════════════

def _get_by_path(ctx, dotpath):
    """按点路径从 ctx 取值，如 'meta.device_serial' → ctx['meta']['device_serial']。
    路径不存在时返回 None（不抛异常）。"""
    cur = ctx
    for part in dotpath.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


# ═══════════════════════════════════════════════════════════════════
# 条件评估（统一提取，消除重复硬编码）
# ═══════════════════════════════════════════════════════════════════

def _evaluate_condition(ctx, cond):
    """评估阶段条件声明，返回 (should_execute: bool, reason: str)。

    支持："<prefix>.<field> non-empty"（检查字段非空）、空字符串（无条件）。
    """
    if not cond:
        return True, ""

    if " non-empty" in cond:
        path_part = cond.replace(" non-empty", "").strip()
        val = _get_by_path(ctx, path_part)
        if val is not None and val != "" and val != [] and val != {}:
            return True, ""
        return False, f"{path_part} 为空"

    # 未知条件类型：告警后默认放行（避免阶段被静默跳过），
    # SOP 作者看到告警后应检查条件声明是否拼写错误或需扩展 _evaluate_condition
    sys.stderr.write(
        f"⚠️  _evaluate_condition: 未知条件类型 '{cond}'，"
        f"已默认放行（请检查条件声明是否正确，或是否需要扩展 _evaluate_condition 支持）\n")
    return True, ""

# ═══════════════════════════════════════════════════════════════════
# 完成证据校验
# ═══════════════════════════════════════════════════════════════════

def _check_json_path_nonempty(ctx, spec):
    """校验指定 JSON path 存在且不为空（用精确判断避免 0/False 被误判为未填写）。"""
    path = spec.get("path", "")
    val = _get_by_path(ctx, path)
    if val is not None and val != "" and val != [] and val != {}:
        return True, ""
    return False, (f"{path} 为空/不存在 —— 该阶段声明的命令似乎从未被真正执行过"
                    f"（正常执行后该字段应被回写到 flow-context.json）")

def _check_json_path_truthy(ctx, spec):
    """校验指定 JSON path 的值为 truthy（区别于 nonempty：truthy 要求布尔语义为 True）。
    可选 hint 字段定制不同阶段的补救提示。
    """
    path = spec.get("path", "")
    val = _get_by_path(ctx, path)
    if val is True or (isinstance(val, str) and val.lower() in ("true", "confirmed")):
        return True, ""
    hint = spec.get("hint", "请先用 AskQuestion 让用户确认，然后调用 ack --key 写入证据")
    return False, f"{path} 未设置为 true —— 该阶段需要先完成前置操作（{hint}）"

_FILE_EXISTS_BASE_RESOLVERS = {
    "run_dir": lambda ctx: ctx.get("meta", {}).get("run_dir", ""),
    "skill_scripts_output": lambda ctx: OUTPUT_DIR,
    "current_case_output_dir": lambda ctx: ctx.get("current_case", {}).get("output_dir", ""),
}

def _check_file_exists(ctx, spec):
    """校验指定根目录下是否存在匹配 glob 模式的文件。"""
    base_key = spec.get("base")
    pattern = spec.get("glob", "")
    if not base_key or not pattern:
        return False, ("completion_check 声明不完整：file_exists 类型必须同时提供 "
                        "base（run_dir / skill_scripts_output / current_case_output_dir）"
                        "和 glob，这是 Skill 配置错误，需修复声明而非重跑命令")
    resolver = _FILE_EXISTS_BASE_RESOLVERS.get(base_key)
    if resolver is None:
        return False, f"未知的 base 取值 {base_key!r}，可选值：{sorted(_FILE_EXISTS_BASE_RESOLVERS)}（Skill 配置错误）"
    base_dir = resolver(ctx)
    if not base_dir:
        return True, ""  # base 解析结果为空不阻塞，视为其他前置问题
    matches = glob.glob(os.path.join(base_dir, pattern))
    if matches:
        return True, ""
    return False, (f"未找到匹配 {pattern} 的文件（base={base_key} -> {base_dir}）—— "
                    f"该阶段声明的命令似乎未成功执行或未产出预期文件")

def _check_steps_all_done(ctx, spec):
    """校验当前 case 的所有走查步骤是否已完成。
    
    防止 AI 误用 flow-advance 跳过未完成的步骤。
    """
    steps = ctx.get("steps", [])
    pending = [s for s in steps if s.get("status") in ("pending", "in_progress")]
    if pending:
        sids = ", ".join(s["sid"] for s in pending)
        hint = spec.get("hint", "还有走查步骤未完成")
        return False, f"步骤 {sids} 未完成 —— {hint}"
    return True, ""

_COMPLETION_CHECKERS = {
    "json_path_nonempty": _check_json_path_nonempty,
    "json_path_truthy": _check_json_path_truthy,
    "file_exists": _check_file_exists,
    "steps_all_done": _check_steps_all_done,
}

def _run_single_check(ctx, check):
    """执行单条 completion_check 声明，返回 (ok, reason)。"""
    checker = _COMPLETION_CHECKERS.get(check.get("type", ""))
    if not checker:
        return True, ""
    return checker(ctx, check)

def _requires_ack_checks(stage):
    """把 stage.requires_ack 声明转换成等价的 json_path_truthy 校验列表。"""
    out = []
    for item in stage.get("requires_ack", []):
        key = item.get("key", "")
        if not key:
            continue
        out.append({
            "type": "json_path_truthy",
            "path": f"runtime.acks.{key}",
            "hint": item.get("hint", f"请先完成 {key} 对应的操作，再调用 "
                                      f"`ack --key {key}` 写入证据"),
        })
    return out

def _run_completion_check(ctx, stage):
    """校验 stage 的完成证据声明是否通过（未声明则直接放行）。
    completion_check/completion_checks/requires_ack 可同时使用，取 AND 语义。
    """
    all_checks = []
    single = stage.get("completion_check")
    if single:
        all_checks.append(single)
    all_checks.extend(stage.get("completion_checks", []))
    all_checks.extend(_requires_ack_checks(stage))

    if not all_checks:
        return True, ""

    reasons = []
    for check in all_checks:
        ok, reason = _run_single_check(ctx, check)
        if not ok:
            reasons.append(reason)
    if reasons:
        return False, "；".join(reasons)
    return True, ""
