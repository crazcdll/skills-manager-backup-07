"""步骤截图：命名归一、case 前缀、frame 落盘。

命名规则（唯一键来自「执行事实账本」，不做目录扫描推断）：
  · 声明步骤 / 重试：`case_NN_<sid>.png` —— sid 本身唯一，天然不冲突；
  · 归属型兜底（--for-sid）：`case_NN_fallback_<sid>_<seq>.png` —— 同一父步骤可能执行多次，
    用张级分配序号保证互不覆盖（见 records.alloc_shot_seq / auto_shot_name）。
"""
import time

from shared.records import (
    auto_shot_name, frame_path, alloc_shot_seq, normalize_name,
)


def _take_step_screenshot(args, case_workspace, case_index, ops):
    """执行截图。"""
    if getattr(args, "no_screenshot", False):
        return None, None
    screenshot_delay = 0.5 if getattr(args, "page_ready", False) else 1.5
    time.sleep(screenshot_delay)
    screenshot_name = normalize_name(args.screenshot) if args.screenshot else ""
    auto_named = False
    if not screenshot_name:
        for_sid = getattr(args, "for_sid", None) or ""
        sid = getattr(args, "sid", None) or for_sid or ""
        if for_sid:
            # 归属型兜底：同一父步骤可多次执行 → 执行序号命名（不覆盖，且已含 case 前缀）
            screenshot_name = auto_shot_name(
                case_workspace, "fallback", alloc_shot_seq(case_workspace), tag=for_sid,
            )
            auto_named = True
        else:
            screenshot_name = f"{sid}.png" if sid else "step.png"
    if not auto_named and case_index is not None:
        screenshot_name = f"case_{case_index + 1:02d}_{screenshot_name}"
    screenshot_path = frame_path(case_workspace, screenshot_name)
    if not ops.screenshot(screenshot_path):
        print(f"  ⚠️ 截图失败 -> {screenshot_path}")
        return None, None
    print(f"  SHOT -> {screenshot_path}")
    return screenshot_name, screenshot_path
