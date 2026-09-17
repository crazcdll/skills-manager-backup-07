"""步骤截图：命名归一、case 前缀、frame 落盘。"""
import time
from core.util.records import frame_path, normalize_name


def _take_step_screenshot(args, case_workspace, case_index, ops):
    """执行截图。"""
    if getattr(args, "no_screenshot", False):
        return None, None
    screenshot_delay = 0.5 if getattr(args, "page_ready", False) else 1.5
    time.sleep(screenshot_delay)
    screenshot_name = normalize_name(args.screenshot) if args.screenshot else ""
    if not screenshot_name:
        sid = getattr(args, "sid", None) or ""
        screenshot_name = f"{sid}.png" if sid else "step.png"
    if case_index is not None:
        screenshot_name = f"case_{case_index + 1:02d}_{screenshot_name}"
    screenshot_path = frame_path(case_workspace, screenshot_name)
    if not ops.screenshot(screenshot_path):
        print(f"  ⚠️ 截图失败 -> {screenshot_path}")
        return None, None
    print(f"  SHOT -> {screenshot_path}")
    return screenshot_name, screenshot_path
