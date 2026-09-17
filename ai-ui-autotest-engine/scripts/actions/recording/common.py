"""记录命令共享工具。"""
import json
import os
import sys
import time

from core.util.case_utils import _timer_read_and_clear, _infer_ms_from_last_step
from context import get_platform_ops
from core.flow.flow_context import load_context as fc_load
from core.util.records import SHOT_AUTO, frame_path, normalize_name

from assertions.constants import STEP_OK_STATUS, NOTE_STATUS


def _declared_sids(flow_context):
    """返回已声明的步骤 SID 集合。"""
    return {step.get("sid") for step in (flow_context or {}).get("steps", []) if step.get("sid")}


def _resolve_duration(args, case_workspace):
    """解析步骤耗时（ms），优先级：--ms > --started 计算 > 自动计时器 > 上一步推断。
    返回 (duration_ms, is_inferred)。
    """
    ms = getattr(args, "ms", None)
    if ms is not None:
        return ms, False
    started = getattr(args, "started", None)
    if started is not None:
        return int((time.time() - started) * 1000), False
    elapsed = _timer_read_and_clear(case_workspace)
    if elapsed is not None:
        return elapsed, False
    last_sid_ms = _infer_ms_from_last_step(case_workspace)
    if last_sid_ms is not None:
        return last_sid_ms, True
    return 0, True


def _validate_screenshot_reference(img_name, case_workspace):
    """验证截图引用合法（必须引用 frames/ 下已真实存在的文件）。"""
    if not img_name:
        return True
    abs_path = frame_path(case_workspace, img_name)
    exists = os.path.isfile(abs_path)
    if not exists:
        sys.stderr.write(f"⚠️  截图引用不存在: {abs_path}（将记录但标记异常）\n")
    return exists


def _build_failure_analysis_from_args(args):
    """从 args 组装 evidence JSON（AI 分析的 extracted_fields 结论）。"""
    fa = getattr(args, "fa", None)
    if fa:
        return json.loads(fa)
    error = getattr(args, "error", "") or ""
    causes = getattr(args, "cause", []) or []
    suggests = getattr(args, "suggest", []) or []
    if error or causes or suggests:
        return {
            "error_summary": error,
            "causes": causes,
            "suggestions": suggests,
        }
    return None


def _auto_capture_screenshot(args, case_workspace, force=False):
    """自动截图：img 未指定时，截取当前画面并归档到 case_workspace/frames/，返回文件名。

    force=True 时即使已指定 img 也重新截图。截图失败返回 None（不再"假有图"）。
    """
    img_name = getattr(args, "img", None)
    if img_name and not force:
        return normalize_name(img_name)
    name = f"auto_{time.strftime('%Y%m%d_%H%M%S')}.png"
    abs_path = frame_path(case_workspace, name)
    try:
        ops = get_platform_ops()
        if not ops.screenshot(abs_path):
            sys.stderr.write("  ⚠️  自动截图失败（截图命令返回非成功，不写入记录）\n")
            return None
        sys.stderr.write(f"  📸 自动截图: {name}\n")
        return name
    except Exception as e:
        sys.stderr.write(f"  ⚠️  自动截图失败: {e}\n")
        return None


def _report_step_binding(sid, owner_info, log_type):
    """输出步骤绑定提醒。"""
    if sid:
        sys.stderr.write(f"  → 已绑定步骤: {sid}\n")
    else:
        sys.stderr.write(f"  → 未绑定 SID（将作为独立 finding 计入统计）\n")
