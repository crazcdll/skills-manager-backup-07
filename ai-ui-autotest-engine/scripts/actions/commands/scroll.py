"""swipe / scroll-edge / scroll-until 独立命令。

swipe 命令设计原则：引擎只做执行，AI 凭上下文信息做决策。
  swipe --direction down --step 0.7
    AI 指定方向和幅度比例，引擎翻译为设备坐标执行。
    --step 指相对手势区域全幅的比例（0~1），例如 step=0.3 表示滑 30% 的手势区域。
    AI 通过 screen-info 命令获取屏幕布局参数来决策方向和幅度。
"""

import time
from core.errors import DeviceError, UsageError
from context import get_platform_ops
from screen_state.screen_layout import ScreenLayout
from actions.handlers.base import _do_swipe, _do_h_swipe, SCROLL_DURATION_MS
from actions.handlers.scroll import handle_scroll_to_target
from actions.assertion_utils import _try_shoot_for_diagnosis, format_visual_check_hint


def _cmd_swipe(args):
    """执行一次滑动。

    引擎只做两件事：
      1. 把 AI 指定的 direction + step 翻译为设备坐标
      2. 执行滑动操作

    AI 通过 screen-info 获取屏幕布局上下文，自行决策方向、幅度和截图时机。
    滑完后 AI 应主动 screenshot 确认效果。

    方向统一用户语义：direction 表示想看的目标方向。
      direction="down" → 想看下方 → 引擎翻译为物理上滑（内容上移）
      direction="up"   → 想看上方 → 引擎翻译为物理下滑（内容下移）
      direction="right" → 想看右侧 → 引擎翻译为物理左滑（内容右移）
      direction="left"  → 想看左侧 → 引擎翻译为物理右滑（内容左移）
    step 语义：step=1.0 为手势区域全幅，step=0.3 为 30% 幅度。
    """
    dur = args.duration if args.duration is not None else SCROLL_DURATION_MS
    ops = get_platform_ops()
    direction = getattr(args, "direction", None)
    step = getattr(args, "step", None)

    # ── 语义模式：direction + step ───────────────────────────
    if direction is not None:
        layout = ScreenLayout.from_ops(ops)

        if direction in ("up", "down"):
            # direction=用户语义：想看的方向
            #   "down" = 想看下方 → 物理上滑（y大→y小）
            #   "up"   = 想看上方 → 物理下滑（y小→y大）
            if direction == "down":
                y_from = layout.swipe_area_bottom
                y_to = layout.swipe_area_top
            else:
                y_from = layout.swipe_area_top
                y_to = layout.swipe_area_bottom

            if step is not None and 0 < step < 1:
                full_step = abs(y_from - y_to)
                limited_step = int(full_step * step)
                if direction == "down":
                    y_from = layout.swipe_area_bottom
                    y_to = layout.swipe_area_bottom - limited_step
                else:
                    y_from = layout.swipe_area_top
                    y_to = layout.swipe_area_top + limited_step

            print(f"SWIPE direction={direction} step={step or '1.0'}"
                  f" ({y_from}→{y_to}, {dur}ms)")
            print(f"  💡 想看{direction}方 → 引擎内部翻译为{'物理上滑(手指从下→上)' if direction == 'down' else '物理下滑(手指从上→下)'}")
            print(f"  💡 已执行，请截图确认目标内容是否已进入视口")
            ops.swipe(from_x=layout.center_x, from_y=y_from,
                      to_x=layout.center_x, to_y=y_to,
                      duration_ms=dur)
            return

        else:  # left / right
            swipe_y = layout.h_swipe_y
            margin = int(layout.width * 0.08)

            # direction=用户语义：想看右侧(right)→物理左滑；想看左侧(left)→物理右滑
            if direction == "right":
                from_x = layout.width - margin
                to_x = margin
            else:
                from_x = margin
                to_x = layout.width - margin

            if step is not None and 0 < step < 1:
                full_step = abs(from_x - to_x)
                limited_step = int(full_step * step)
                if direction == "right":
                    to_x = from_x - limited_step
                else:
                    to_x = from_x + limited_step

            ops.swipe(from_x=from_x, from_y=swipe_y,
                      to_x=to_x, to_y=swipe_y,
                      duration_ms=dur)
            print(f"SWIPE direction={direction} step={step or '1.0'}"
                  f" ({from_x}→{to_x} @ y={swipe_y}, {dur}ms)")
            print(f"  💡 想看{direction}方 → 引擎内部翻译为{'物理左滑' if direction == 'right' else '物理右滑'}")
            print(f"  💡 已执行，请截图确认效果后再决定下一步")
            return

    # ── 坐标模式（兼容） ─────────────────────────────────────
    x1 = getattr(args, "x1", None)
    y1 = getattr(args, "y1", None)
    x2 = getattr(args, "x2", None)
    y2 = getattr(args, "y2", None)
    if x1 is None or y1 is None or x2 is None or y2 is None:
        raise UsageError("SWIPE USAGE: swipe --direction up/down/left/right --step 0.7")
    if not ops.swipe(x1, y1, x2, y2, duration_ms=dur):
        raise DeviceError(f"SWIPE FAIL ({x1},{y1}) -> ({x2},{y2})")
    print(f"SWIPE ({x1},{y1}) -> ({x2},{y2}) {dur}ms")


def _cmd_screen_info(args):
    """打印当前屏幕布局参数，供 AI 决策滚动方向和幅度时参考。"""
    ops = get_platform_ops()
    layout = ScreenLayout.from_ops(ops)
    sw_h = layout.swipe_area_bottom - layout.swipe_area_top
    print(f"屏幕参数:")
    print(f"  分辨率: {layout.width}×{layout.height}")
    print(f"  视口范围: y=[{layout.viewport_top}, {layout.viewport_bottom}]")
    print(f"  手势区域: y=[{layout.swipe_area_top}, {layout.swipe_area_bottom}] (全幅 {sw_h}px)")
    print(f"  纵向滑动中心 x={layout.center_x}")
    print(f"  横向滑动中心 y={layout.h_swipe_y}")
    print(f"")
    print(f"参考：step 对应的实际滑动距离")
    print(f"  step=0.3 → {int(sw_h * 0.3)}px（微调）")
    print(f"  step=0.5 → {int(sw_h * 0.5)}px（半屏）")
    print(f"  step=0.7 → {int(sw_h * 0.7)}px（大幅）")
    print(f"  step=1.0 → {sw_h}px（全幅）")
    print(f"")
    print(f"💡 AI 根据当前截图判断需要滚动的方向和幅度，然后执行：")
    print(f"   python3 scripts/cli.py swipe --direction down --step 0.7")
    print(f"   滑完后 screenshot 确认效果，不够再继续")
    print(f"  ⚠️ 方向统一用户语义：swipe --direction down = 想看下方 → 引擎翻译为物理上滑；swipe --direction up = 想看上方 → 引擎翻译为物理下滑")



def _cmd_scroll_to_edge(args):
    """独立命令：快速滚动到底部/侧边。

    scroll-edge --direction 统一用户语义：想看目标所在的方向
      down → _do_swipe("down") → 引擎翻译为物理上滑，看到下方
      up   → _do_swipe("up")   → 引擎翻译为物理下滑，看到上方
      right → _do_h_swipe("right") → 引擎翻译为物理左滑
      left  → _do_h_swipe("left")  → 引擎翻译为物理右滑
    """
    direction = getattr(args, "direction", "down")
    for _ in range(args.times):
        if direction in ("left", "right"):
            _do_h_swipe(direction=direction)
        else:
            _do_swipe(direction=direction)
        time.sleep(0.4)
    print(f"SCROLLED x{args.times} direction={direction} (用户语义→引擎自动翻译物理方向)")


def _cmd_scroll_to_target(args):
    """独立命令：滚动定位目标文本。"""
    result = handle_scroll_to_target(args.text, args)
    # 只在成功（ok=True）时截图确认，handoff 场景让 AI 自己决策截图时机
    if result and result.get("ok") is True:
        shot = _try_shoot_for_diagnosis(f"scroll_until_{args.text}_final")
        if shot:
            print(format_visual_check_hint("SCROLL-UNTIL", shot, "确认目标文案已进入可视区域"))