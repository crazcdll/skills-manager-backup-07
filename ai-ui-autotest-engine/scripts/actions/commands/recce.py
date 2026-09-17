"""dismiss-recce 独立命令。"""

from actions.assertion_utils import auto_dismiss_recce


def _cmd_dismiss_recce(args):
    """独立命令：移除 Recce 调试浮层。"""
    dismissed = auto_dismiss_recce()
    if dismissed:
        print("DISMISS-RECCE OK: Recce 已拖动到右上角")
    else:
        print("DISMISS-RECCE OK: 无需处理")