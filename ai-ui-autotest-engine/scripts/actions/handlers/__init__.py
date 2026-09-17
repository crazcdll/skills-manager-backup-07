"""Step action handlers — 按 action 类型拆分的执行函数。

step/step_action.py 和 commands/* 均调用本模块的 handler，确保
complex step 命令和独立命令行为一致。
"""
from actions.handlers.base import (
    SCROLL_DURATION_MS,
    _collect_similar_texts,
    _auto_scroll_coords_to_viewport,
)
from actions.handlers.tap import handle_tap, handle_tap_text
from actions.handlers.scroll import handle_scroll_to_target, handle_scroll_to_edge
from actions.handlers.navigation import handle_back, handle_open_url
from actions.handlers.input import handle_input_text, handle_blur_input

HANDLERS = {
    "tap": handle_tap,
    "tap-text": handle_tap_text,
    "scroll-until": handle_scroll_to_target,
    "scroll-edge": handle_scroll_to_edge,
    "back": handle_back,
    "blur-input": handle_blur_input,
    "open-url": handle_open_url,
    "input-text": handle_input_text,
}


def get_handler(action):
    """根据 action 名称获取对应的 handler 函数，未知 action 返回 None。"""
    return HANDLERS.get(action)