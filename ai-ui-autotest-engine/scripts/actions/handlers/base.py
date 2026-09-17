"""Handler 共享工具：滑动、文本相似度、视口自动滚动。"""

import time
import unicodedata as _ud
import re

from context import get_platform_ops
from screen_state.screen_layout import ScreenLayout
from screen_state.inspect_tree import (
    dump_inspect_tree, parse_inspect_tree,
    invalidate_cache,
)

SCROLL_DURATION_MS = 500


def _do_swipe(direction="down", y_from=None, y_to=None, dur=None):
    """纵向滑动。

    方向命名=物理手指方向：
      "up"   = 手指从下向上滑（y大→y小）= 内容上移，露出页面下方的内容 — 对应滑动后看到下方
      "down" = 手指从上向下滑（y小→y大）= 内容下移，露出页面上方的内容 — 对应滑动后看到上方
    Args:
        direction: "up"（物理上滑）或 "down"（物理下滑）。
        y_from/y_to: 自定义起止 y 坐标，默认使用 ScreenLayout 滑动区域。
        dur: 滑动持续时间（毫秒）。
    """
    ops = get_platform_ops()
    layout = ScreenLayout.from_ops(ops)
    cx = layout.center_x
    if direction == "up":
        # 物理上滑：手指从下→上（y大→y小）
        fy = y_from if y_from is not None else layout.swipe_area_bottom
        ty = y_to if y_to is not None else layout.swipe_area_top
    else:
        # 物理下滑：手指从上→下（y小→y大）
        fy = y_from if y_from is not None else layout.swipe_area_top
        ty = y_to if y_to is not None else layout.swipe_area_bottom
    ops.swipe(from_x=cx, from_y=fy, to_x=cx, to_y=ty,
              duration_ms=dur or SCROLL_DURATION_MS)


def _do_h_swipe(direction="left", dur=SCROLL_DURATION_MS, swipe_y=None):
    """横向滑动。

    Args:
        direction: "left"（手指从右向左=内容向右移）或 "right"（手指从左向右）。
        dur: 滑动持续时间（毫秒）。
        swipe_y: 滑动 y 坐标，默认视口垂直中心。
    """
    ops = get_platform_ops()
    layout = ScreenLayout.from_ops(ops)
    cy = swipe_y if swipe_y is not None else layout.h_swipe_y
    cy = layout.clamp_swipe_y(cy)  # 防御：防止目标 y 超出屏幕范围
    margin = int(layout.width * 0.08)
    if direction == "left":
        ops.swipe(from_x=layout.width - margin, from_y=cy,
                  to_x=margin, to_y=cy, duration_ms=dur)
    else:
        ops.swipe(from_x=margin, from_y=cy,
                  to_x=layout.width - margin, to_y=cy, duration_ms=dur)


def _collect_similar_texts(query, min_overlap=2):
    """从 inspect-tree 收集与 query 共享子串的文本，帮助发现文案不一致。"""
    raw = dump_inspect_tree(wait_sec=3, max_attempts=1)
    if raw is None:
        return []
    nodes = parse_inspect_tree(raw)

    q_norm = _ud.normalize('NFKC', query)
    q_subs = set()
    for length in range(min_overlap, len(q_norm) + 1):
        for start in range(len(q_norm) - length + 1):
            q_subs.add(q_norm[start:start + length])

    seen = set()
    candidates = []
    for n in nodes:
        text = (n.get("all_text") or "").strip()
        if not text or len(text) < min_overlap or len(text) > 30:
            continue
        if text in seen or re.match(r'^[\d\s.,:;+\-*/=]+$', text):
            continue
        t_norm = _ud.normalize('NFKC', text)
        best_sub = ""
        for sub in q_subs:
            if sub in t_norm and len(sub) > len(best_sub):
                best_sub = sub
        if best_sub:
            seen.add(text)
            candidates.append((text, best_sub, len(best_sub)))

    candidates.sort(key=lambda c: -c[2])
    return [(text, f"共享子串「{sub}」(长度{ln})")
            for text, sub, ln in candidates[:10]]


# ─── 视口自动滚动（供 handle_tap / handle_input_text 坐标安全 + scroll.py 使用） ──
# tap-text 的视口外目标不再走内部滚动，已改为 reason_code → Hook 路径。

def _center_adjust(node_center, layout: ScreenLayout):
    """居中微调：当目标偏离视口中心时，执行小幅度滑动将其居中。"""
    offset = node_center - layout.viewport_center
    if abs(offset) > layout.CENTER_ADJUST_THRESHOLD:
        swipe_mid = layout.center_y
        swipe_from = swipe_mid + offset // 2
        swipe_to = swipe_mid - offset // 2
        swipe_from = max(layout.swipe_area_top, min(swipe_from, layout.swipe_area_bottom))
        swipe_to = max(layout.swipe_area_top, min(swipe_to, layout.swipe_area_bottom))
        ops = get_platform_ops()
        ops.swipe(from_x=layout.center_x, from_y=swipe_from,
                  to_x=layout.center_x, to_y=swipe_to, duration_ms=300)
        time.sleep(0.4)
    invalidate_cache()


def _h_center_adjust(node_center_x, layout: ScreenLayout):
    """水平居中微调：当目标偏离视口水平中心时，执行小幅度横向滑动将其居中。

    RN 横向滚动后 DOM 坐标可能不更新，但仍然提供偏移方向参考：
    如果 DOM x 偏右（x > 视口中心），说明需要再向左滑一点把内容拉回中间，
    反之偏左则向右滑一一点。滑动量取偏移量的一半 + 安全余量。
    """
    cx = layout.viewport_x_center
    offset = node_center_x - cx
    if abs(offset) > layout.CENTER_ADJUST_THRESHOLD:
        h_swipe_y = layout.h_swipe_y
        margin = int(layout.width * 0.08)
        # 偏移为正（偏右）→ 手指从右向左滑（内容左移，把目标拉到中间）
        if offset > 0:
            step = min(offset, layout.width // 2)
            s_from = layout.width - margin
            s_to = max(margin, s_from - step)
        else:
            step = min(-offset, layout.width // 2)
            s_from = margin
            s_to = min(layout.width - margin, s_from + step)
        ops = get_platform_ops()
        ops.swipe(from_x=s_from, from_y=h_swipe_y,
                  to_x=s_to, to_y=h_swipe_y, duration_ms=300)
        time.sleep(0.4)
    invalidate_cache()


def _auto_scroll_coords_to_viewport(ax: int, ay: int, layout: "ScreenLayout",
                                     max_swipes: int = 5, label: str = "") -> tuple:
    """将坐标位置滚动到视口内，返回滚动后的新坐标。"""
    if layout.is_in_viewport(ay, ax):
        return (ax, ay)

    tag = f" {label}" if label else ""
    print(f"  {tag}VIEWPORT: 坐标 ({ax},{ay}) 超出视口 "
          f"[{layout.viewport_top}, {layout.viewport_bottom}]，直接滚动到目标位置")

    offset = layout.viewport_offset(ay)
    abs_offset = abs(offset)

    if abs_offset <= 50:
        _center_adjust(ay, layout)
        return (ax, ay)

    # offset>0=目标在视口下方 → 需要看到下方 → 物理上滑(up)让内容上移露出下方
    # offset<0=目标在视口上方 → 需要看到上方 → 物理下滑(down)让内容下移露出上方
    direction = "up" if offset > 0 else "down"
    mid_y = layout.center_y

    for i in range(max_swipes):
        step = min(layout.max_scroll_step, max(layout.default_step, int(abs_offset * 0.7)))
        step = max(200, step)

        if direction == "down":
            # 物理下滑：从上→下
            s_from = max(layout.swipe_area_top, mid_y - step // 2)
            s_to = min(layout.swipe_area_bottom, s_from + step)
        else:
            # 物理上滑：从下→上
            s_from = min(layout.swipe_area_bottom, mid_y + step // 2)
            s_to = max(layout.swipe_area_top, s_from - step)

        ops = get_platform_ops()
        ops.swipe(from_x=layout.center_x, from_y=s_from,
                  to_x=layout.center_x, to_y=s_to, duration_ms=500)
        time.sleep(max(0.5, 0.3))

        invalidate_cache()
        raw = dump_inspect_tree(wait_sec=0.3, max_attempts=1)
        if raw:
            nodes = parse_inspect_tree(raw)
            for n in nodes:
                cx = n.get("x", 0) + (n.get("w", 0) or 0) // 2
                cy = n.get("y", 0) + (n.get("h", 0) or 0) // 2
                if abs(cx - ax) < 30 and abs(cy - ay) < 30:
                    if layout.is_in_viewport(cy, cx):
                        print(f"  {tag}VIEWPORT: 已滚动 {i+1} 次，目标坐标 ({ax},{ay}) 现在视口内")
                        return (ax, ay)

        remaining = abs_offset - (i + 1) * step * 0.7
        if remaining <= 50:
            break
        abs_offset = remaining

    print(f"  {tag}VIEWPORT: 滚动 {max_swipes} 次后目标坐标可能仍在视口外，保留原坐标")
    return (ax, ay)