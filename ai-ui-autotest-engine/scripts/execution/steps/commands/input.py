"""input-text / blur-input 独立命令。"""

import json

from cli_utils import finish_action_result
from execution.steps.handlers.input import handle_input_text, handle_blur_input


def _cmd_input_text(args):
    """独立命令：文本输入。"""
    text = args.text or ""
    anchor = getattr(args, "anchor", None) or ""
    if anchor:
        action_arg = json.dumps({"anchor": anchor, "text": text}, ensure_ascii=False)
    else:
        action_arg = text
    # tri-state 统一收口（见 cli_utils.finish_action_result）：
    #   完成 → 退出码 0；handoff（如锚点找不到）→ HANDOFF 码 + 交接说明，**不抛异常**；
    #   真失败（设备/参数）→ DeviceError。
    # 曾经把 handoff 一律 raise DeviceError，会把「需换策略」误报成设备错误。
    return finish_action_result("INPUT-TEXT", anchor or text,
                                handle_input_text(action_arg, args))


def _cmd_blur_input(args):
    """独立命令：输入框失焦。"""
    return finish_action_result("BLUR-INPUT", args.anchor or "",
                                handle_blur_input(args.anchor, args))
