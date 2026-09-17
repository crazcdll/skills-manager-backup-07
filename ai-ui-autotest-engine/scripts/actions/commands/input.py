"""input-text / blur-input 独立命令。"""

import json

from core.errors import DeviceError
from actions.handlers.input import handle_input_text, handle_blur_input


def _cmd_input_text(args):
    """独立命令：文本输入。"""
    text = args.text or ""
    anchor = getattr(args, "anchor", None) or ""
    if anchor:
        action_arg = json.dumps({"anchor": anchor, "text": text}, ensure_ascii=False)
    else:
        action_arg = text
    result = handle_input_text(action_arg, args)
    if not result["ok"]:
        raise DeviceError(result.get("reason", "input-text 失败"))


def _cmd_blur_input(args):
    """独立命令：输入框失焦。"""
    result = handle_blur_input(args.anchor, args)
    if not result["ok"]:
        raise DeviceError(result.get("reason", "blur-input 失败"))