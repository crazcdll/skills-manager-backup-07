"""open-url 独立命令。"""

from core.errors import DeviceError
from context import get_platform_ops
from screen_state.page_stability import wait_page_stable
from actions.assertion_utils import _try_shoot_for_diagnosis, format_visual_check_hint


def _cmd_open_url(args):
    """独立命令：通过 scheme 加载页面。"""
    ops = get_platform_ops()
    url = args.url
    print(f"  OPEN-URL: {url}")
    ok = ops.open_url(url)
    if not ok:
        raise DeviceError("open-url 推送失败")
    wait_page_stable()
    shot_path = _try_shoot_for_diagnosis("open_url")
    if shot_path:
        print(f"  SHOT -> {shot_path}")
    print(f"OPEN-URL DONE: {url}")
    if shot_path:
        print(format_visual_check_hint(
            "OPEN-URL", shot_path,
            "判定是否已进入目标页，而非仍停留在原页面/出现报错弹窗/加载失败兜底页",
        ))
    else:
        print("OPEN-URL: 截图失败，请用 find-text --text \"<页面锚点文案>\" 确认跳转结果")