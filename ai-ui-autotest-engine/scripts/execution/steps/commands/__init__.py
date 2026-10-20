"""UI 交互独立命令 — 供 cli.py 注册 CLI 子命令。

与 step 模式不同，独立命令是一次性的 CLI 调用，执行后直接退出。
"""
from execution.steps.commands.tap import _cmd_tap_text, _cmd_tap
from execution.steps.commands.navigation import _cmd_open_url
from execution.steps.commands.scroll import _cmd_swipe, _cmd_scroll_to_edge, _cmd_scroll_to_target
from execution.steps.commands.input import _cmd_input_text, _cmd_blur_input
from execution.steps.commands.assert_cmd import _cmd_assert_text, _cmd_assert_multi, _cmd_assert_gone
from execution.steps.commands.screenshot import _cmd_screenshot
from execution.steps.commands.recce import _cmd_dismiss_recce

__all__ = [
    "_cmd_tap_text", "_cmd_tap",
    "_cmd_open_url",
    "_cmd_swipe", "_cmd_scroll_to_edge", "_cmd_scroll_to_target",
    "_cmd_input_text", "_cmd_blur_input",
    "_cmd_assert_text", "_cmd_assert_multi", "_cmd_assert_gone",
    "_cmd_screenshot",
    "_cmd_dismiss_recce",
]