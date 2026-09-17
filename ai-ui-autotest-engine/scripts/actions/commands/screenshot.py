"""screenshot 独立命令。

--out 为纯文件名时归档到当前 case 的 frames/（与步骤截图统一）；为绝对/相对路径时按原路径落盘。
"""

import os

from core.errors import DeviceError
from context import get_platform_ops
from core.util.paths import get_active_case
from core.util.case_utils import current_case_workspace, resolve_case_path
from core.flow.flow_context import load_context
from core.util.records import frame_path


def _resolve_out(out_arg):
    """纯文件名 → 当前 case 的 frames/；含目录的路径 → 原样使用。"""
    if os.path.isabs(out_arg) or os.path.dirname(out_arg):
        out = os.path.abspath(out_arg)
        out_dir = os.path.dirname(out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        return out
    case_name = get_active_case()
    if case_name:
        root_dir = resolve_case_path(case_name)
        ctx = load_context(root_dir)
        if ctx:
            return frame_path(current_case_workspace(root_dir, ctx), out_arg)
    return os.path.abspath(out_arg)


def _cmd_screenshot(args):
    """独立命令：截图。"""
    out = _resolve_out(args.out)
    ops = get_platform_ops()
    if not ops.screenshot(out):
        raise DeviceError(f"SHOT FAIL -> {out}")
    print(f"SHOT -> {out}")
