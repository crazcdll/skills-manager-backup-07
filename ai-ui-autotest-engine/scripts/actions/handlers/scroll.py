"""scroll-until / scroll-edge handler — 语义滚动定位与快速滚动。

scroll-until 设计（按优先级）：
  1. 精确匹配目标 → 已在视口内 → 居中微调后直接成功
  2. 精确匹配目标 → 在视口外 → 渐进多轮纵向/横向滚动直到进入视口（最多 5 次）
  3. 未精确匹配 → 子串双向包含回退（仅 scroll-until 使用）
     a. 唯一候选 → 走 1/2 流程自动处理
     b. 多候选 → SUBSTRING_AMBIGUOUS → handoff AI 从候选列表中选择
  4. 子串未匹配 → 纵向渐进滚动搜索（默认向下最多 5 次，每滚一次重查目标）
  5. 滚动搜索耗尽 → SCROLL_TARGET_NOT_FOUND → handoff AI 读图定位
  6. 精确匹配但坐标不可解析 → handoff AI 决策
  7. 渐进滚动耗尽（VERTICAL/HORIZONTAL_SCROLL_EXHAUSTED）→ 独立 hook

核心原则：引擎做确定的事（坐标已知就渐进滚动到位），不确定的交 AI 决策 + 提供上下文。
每个 reason_code 路由到独立 Hook，AI 无需自行判断场景。

方向约定（统一用户语义）：
  所有 direction 参数均表示「想看目标所在的方向」：
  - "down"  = 目标在下方 → 引擎翻译为物理上滑（内容上移，露出下方）
  - "up"    = 目标在上方 → 引擎翻译为物理下滑（内容下移，露出上方）
  - "right" = 目标在右侧 → 引擎翻译为物理左滑
  - "left"  = 目标在左侧 → 引擎翻译为物理右滑
  引擎内部（_do_swipe / _do_h_swipe / calc_vertical_swipe）负责方向翻译，
  调用方只需传递用户语义方向。
"""

import hashlib
import json
import os
import sys
import time

from context import get_platform_ops
from screen_state.screen_layout import ScreenLayout
from screen_state.inspect_tree import (
    get_current_nodes, inspect_tree_find_scroll_target, invalidate_cache,
)
from actions.handlers.base import _do_swipe, _do_h_swipe, _center_adjust, _h_center_adjust
from assertions.ui.pipeline.vts import build_element_index, write_element_catalog
from core.util.case_utils import active_case_diagnostics_dir


# ─── 常量 ──────────────────────────────────────────────────────────

MAX_VERTICAL_SWIPES = 5       # 纵向最大渐进滚动次数
MAX_HORIZONTAL_SWIPES = 5     # 横向最大渐进滚动次数
SWIPE_INTERVAL = 0.5          # 每次滚动后等待页面稳定的时间


# ─── Reason Code 定义 ────────────────────────────────────────────

_REASON_LABELS = {
    "SCROLL_TARGET_NOT_FOUND": "精确匹配未命中，已 handoff AI 读元素目录做语义匹配定位",
    "UNRESOLVED": "精确命中目标文本但坐标不可解析",
    "TARGET_Y_OUT_OF_VIEWPORT": "横向滚动目标 y 坐标不在视口内，需 AI 先纵向滚动定位横向容器",
    "VERTICAL_SCROLL_EXHAUSTED": f"纵向渐进滚动{MAX_VERTICAL_SWIPES}次后目标仍未进入视口，需 AI 排查",
    "HORIZONTAL_SCROLL_EXHAUSTED": f"横向渐进滚动{MAX_HORIZONTAL_SWIPES}次后目标未找到，需 AI 排查",
}


def _handoff(reason_code, action_arg="", **kw):
    """标准化 handoff 返回 — 机器→AI 的正常交接点，不是失败。"""
    ctx = {"action": "scroll-until", "arg": action_arg, "reason": reason_code}
    ctx.update(kw)
    label = _REASON_LABELS.get(reason_code, reason_code)
    print(f"  SCROLL-UNTIL {reason_code}: '{action_arg}' — {label}")
    return {
        "ok": None,
        "reason": f"scroll-until '{action_arg}' {label}",
        "ctx": ctx,
        "inspect_tree_impact": "none",
    }


# ─── 辅助函数 ──────────────────────────────────────────────────


def _get_case_diag_dir():
    """获取当前 Case 的 diagnostics 目录（与断言策略 sidecar 同源）。

    ⚠️ 必须走 active_case_diagnostics_dir()：active_case 存的是 run 目录名，
    用 resolve_case_path(get_active_case()) 会落到 run 级 diagnostics，
    与断言策略写的 case_NN/diagnostics 分叉成两份重复目录。
    """
    try:
        return active_case_diagnostics_dir() or None
    except Exception as e:
        print(f"  ⚠️ 定位当前 Case 的 diagnostics 目录失败: {e}", file=sys.stderr)
        return None


def _dump_element_index_sidecar(diag_dir):
    """构建 element_index 并落盘 catalog.md，返回 (index, catalog_path)。

    只有真正写盘成功才返回 path；否则返回空串，避免把不存在的文件路径
    作为 evidence 交给 AI（AI 照着 read_file 必然读不到）。
    """
    try:
        idx = build_element_index(wait_sec=1)
    except Exception as e:
        print(f"  ⚠️ element_index 构建失败: {e}", file=sys.stderr)
        return None, ""
    if not idx or not idx.get("available"):
        print("  ⚠️ element_index 不可用，元素目录未生成", file=sys.stderr)
        return None, ""
    path = os.path.join(diag_dir, "element_index_scroll.catalog.md")
    try:
        write_element_catalog(idx, path)
    except Exception as e:
        print(f"  ⚠️ 元素目录落盘失败: {e}", file=sys.stderr)
        return idx, ""
    return idx, path


def _build_and_dump_element_index():
    """构建并落盘 element_index sidecar，返回 (index, catalog_path)。"""
    diag_dir = _get_case_diag_dir()
    if not diag_dir:
        return None, ""
    return _dump_element_index_sidecar(diag_dir)


def _content_fingerprint():
    """当前页面内容的轻量指纹（节点数 + 文案摘要）。

    用于判定「再滚也不会出现新内容」：连续两次滑动后指纹不变，说明已到边界
    或该容器内容已加载完毕，目标不可能靠继续滚动出现。
    """
    try:
        nodes = get_current_nodes(wait_sec=1)
    except Exception:
        return None
    if nodes is None:
        return None
    texts = [n.get("text") or n.get("content_desc") or "" for n in nodes]
    digest = hashlib.md5("\u0001".join(texts).encode("utf-8")).hexdigest()[:12]
    return f"{len(nodes)}:{digest}"


def _check_content_exhausted(fingerprint, attempt):
    """滑动后判定内容是否已耗尽，返回 (should_stop, new_fingerprint)。

    精确匹配失败时引擎只能盲目滑动，但盲滑的前提是「下面还有没渲染出来的内容」
    （虚拟列表、懒加载）。一旦滑动后页面节点集合完全没变，说明已到边界或内容
    已全部加载，再滑也不会出现新内容 —— 立即停止，把截图 + 元素目录交给 AI，
    避免把 5 次无效滑动（实测单次 ~30s）全部跑完。
    """
    new_fingerprint = _content_fingerprint()
    if new_fingerprint is not None and new_fingerprint == fingerprint:
        print(f"  ⏹️ 第{attempt}次滑动后页面内容无变化（已到边界/内容已加载完），停止无意义滚动")
        return True, fingerprint
    return False, new_fingerprint


def _print_element_index_overview(idx, layout=None):
    """打印 element_index 结构概览：视口内/上方/下方元素数量。"""
    if not idx or not idx.get("available"):
        return
    els = idx.get("elements", [])
    _in = sum(1 for e in els if e.get("in_viewport"))
    vp_top = layout.viewport_top if layout else 0
    _above = sum(1 for e in els
                 if not e.get("in_viewport")
                 and e.get("bounds")
                 and e["bounds"][1] < vp_top)
    _below = sum(1 for e in els
                 if not e.get("in_viewport")
                 and e.get("bounds")
                 and e["bounds"][1] >= vp_top)
    print(f"  📋 页面布局结构: 共 {len(els)} 个语义元素, "
          f"视口内 {_in} 个, 上方 ~{_above} 个, 下方 ~{_below} 个")


# ═══════════════════════════════════════════════════════════════════
# 纵向渐进滚动
# ═══════════════════════════════════════════════════════════════════

def _vp_offset_to_swipe_dir(vp_offset: int) -> str:
    """用 viewport_offset 推导用户语义方向。

    vp_offset>0 = 目标在视口下方 → 想看下方（down）
    vp_offset<0 = 目标在视口上方 → 想看上方的（up）
    """
    return "down" if vp_offset > 0 else "up"


def _scroll_vertical_progressive(action_arg, layout, vp_offset, step_ratio=0.7):
    """纵向渐进滚动：纯几何驱动。

    根据 vp_offset 自动推导手势方向：目标在下方→物理上滑，在上方→物理下滑。
    每次滚动后检查目标是否进入视口；viewport_offset 未变→RN 坐标冻结→handoff。
    """
    abs_offset = abs(vp_offset)
    swipe_dir = _vp_offset_to_swipe_dir(vp_offset)

    print(f"  SCROLL-UNTIL '{action_arg}' 目标在{'下方' if vp_offset > 0 else '上方'} "
          f"({abs_offset}px)，{swipe_dir}(用户语义：想向{'下' if vp_offset > 0 else '上'}看)")

    for attempt in range(1, MAX_VERTICAL_SWIPES + 1):
        s_from, s_to = layout.calc_vertical_swipe(swipe_dir, abs_offset, step_ratio)
        print(f"  第{attempt}次/{MAX_VERTICAL_SWIPES}: "
              f"{abs(s_from - s_to)}px ({s_from}→{s_to})")

        _do_swipe(direction=swipe_dir, y_from=s_from, y_to=s_to, dur=500)
        time.sleep(SWIPE_INTERVAL)
        invalidate_cache()

        post_info = inspect_tree_find_scroll_target(action_arg, detail=True)
        if not post_info or not post_info.get("center"):
            break

        _, cy = post_info["center"]
        if not post_info.get("out_of_viewport", False):
            _center_adjust(cy, layout)
            print(f"  ✅ SCROLL-UNTIL '{action_arg}' 第{attempt}次后已在视口内 (y={cy})")
            return {"ok": True, "reason": "", "ctx": {"swipes": attempt},
                    "inspect_tree_impact": "viewport"}

        new_abs = abs(post_info.get("viewport_offset", 0))
        if new_abs < abs_offset:
            abs_offset = new_abs
            continue

        # RN 坐标冻结 → handoff
        print(f"  🌀 viewport_offset 未变化 ({vp_offset}→{new_abs})，handoff AI")
        break

    _idx_ex, _ei_path = _build_and_dump_element_index()
    if _ei_path:
        print(f"  📋 页面布局结构已写入: {_ei_path}")
    return _handoff("VERTICAL_SCROLL_EXHAUSTED", action_arg,
                    swipes=MAX_VERTICAL_SWIPES, direction=swipe_dir,
                    element_index_path=_ei_path or "")

    # ═══════════════════════════════════════════════════════════════════
# 横向渐进滚动
# ═══════════════════════════════════════════════════════════════════

def _scroll_horizontal_progressive(action_arg, swipe_dir, layout, swipe_y):
    """横向渐进滚动（最多 MAX_HORIZONTAL_SWIPES 次）。

    RN HorizontalScrollView 在 inspect-tree 中不更新子节点 DOM 坐标——
    滚动后子节点的屏幕绝对坐标保持不变。因此不能依赖 out_of_viewport
    来验证滑动效果。每次滑动后通过检查目标文本是否出现在视图树中
    来判断滚动是否到位。
    """
    for attempt in range(1, MAX_HORIZONTAL_SWIPES + 1):
        print(f"  SCROLL-UNTIL '{action_arg}' 横向滚动第{attempt}次/{MAX_HORIZONTAL_SWIPES} "
              f"{swipe_dir} (y={swipe_y})")

        _do_h_swipe(direction=swipe_dir, swipe_y=swipe_y)
        time.sleep(SWIPE_INTERVAL)
        invalidate_cache()

        post_info = inspect_tree_find_scroll_target(action_arg, detail=True)
        if post_info and post_info.get("center"):
            pcx, pcy = post_info["center"]
            _center_adjust(pcy, layout)
            _h_center_adjust(pcx, layout)
            print(f"  SCROLL-UNTIL '{action_arg}' 横向第{attempt}次滚动后已定位 (x={pcx})")
            return {"ok": True, "reason": "", "ctx": {"swipes": attempt, "direction": swipe_dir},
                    "inspect_tree_impact": "viewport"}

    print(f"  💡 横向滚动耗尽，可能原因：已到边界/目标不在当前横向容器中")
    print(f"     1. inspect-tree 确认横向容器是否可滚动")
    print(f"     2. screenshot 确认是否已到边界")
    print(f"     3. 如越界 → override-step-result 记录结果")
    return _handoff("HORIZONTAL_SCROLL_EXHAUSTED", action_arg,
                    direction=swipe_dir, swipes=MAX_HORIZONTAL_SWIPES)


# ═══════════════════════════════════════════════════════════════════
# 语义滚动主入口
# ═══════════════════════════════════════════════════════════════════

def handle_scroll_to_target(action_arg, args):
    """语义滚动：定位目标 → 渐进滚动直到进入视口或达到上限。"""

    direction = getattr(args, "direction", None)
    step_ratio = getattr(args, "step", 0.7)

    # ── 1. 精确匹配定位目标 ─────────────────────────────────
    info = inspect_tree_find_scroll_target(action_arg, detail=True)

    # ═══════════════════════════════════════════════════════════════
    # 分支 A: SCROLL_TARGET_NOT_FOUND — 未在视图树中找到精确匹配
    # → 先尝试渐进滚动搜索（若 direction 已指定方向），每次滚动后重新查找
    #   直到耗尽 MAX_VERTICAL_SWIPES 次后再 handoff AI
    # ═══════════════════════════════════════════════════════════════
    if info is None:
        layout = ScreenLayout.from_ops(get_platform_ops())
        search_dir = direction or "down"  # 默认向下搜索

        if search_dir in ("left", "right"):
            # _do_h_swipe 接受物理手指方向，需翻译用户语义
            _user_to_h_physical = {"right": "left", "left": "right"}
            h_physical_dir = _user_to_h_physical.get(search_dir, search_dir)
            swipe_y = layout.h_swipe_y
            fingerprint = _content_fingerprint()
            for attempt in range(1, MAX_HORIZONTAL_SWIPES + 1):
                print(f"  SCROLL-UNTIL '{action_arg}' 未找到，横向搜索第{attempt}次/{MAX_HORIZONTAL_SWIPES} "
                      f"{search_dir} (用户语义) → physical={h_physical_dir} (y={swipe_y})")
                _do_h_swipe(direction=h_physical_dir, swipe_y=swipe_y)
                time.sleep(SWIPE_INTERVAL)
                invalidate_cache()
                info = inspect_tree_find_scroll_target(action_arg, detail=True)
                if info is not None:
                    break
                _stop, fingerprint = _check_content_exhausted(fingerprint, attempt)
                if _stop:
                    break
        else:
            # _do_swipe 接受物理手指方向，而 search_dir 是用户语义方向，需要翻译
            _user_to_physical = {"down": "up", "up": "down"}
            physical_dir = _user_to_physical.get(search_dir, search_dir)
            fingerprint = _content_fingerprint()
            for attempt in range(1, MAX_VERTICAL_SWIPES + 1):
                print(f"  SCROLL-UNTIL '{action_arg}' 未找到，纵向搜索第{attempt}次/{MAX_VERTICAL_SWIPES} "
                      f"direction={search_dir} (用户语义) → physical={physical_dir}")
                _do_swipe(direction=physical_dir)
                time.sleep(SWIPE_INTERVAL)
                invalidate_cache()
                info = inspect_tree_find_scroll_target(action_arg, detail=True)
                if info is not None:
                    break
                _stop, fingerprint = _check_content_exhausted(fingerprint, attempt)
                if _stop:
                    break

        if info is not None:
            # 滚动搜索找到了目标，继续后续流程
            if info.get("unresolved"):
                reason = info.get("unresolved_reason", "")
                if reason == "substring_ambiguous":
                    candidates = info.get("candidates", [])
                    _idx_ex, _ei_path = _build_and_dump_element_index()
                    return _handoff("SUBSTRING_AMBIGUOUS", action_arg,
                                    matched_text=info.get("matched_text", ""),
                                    candidates_count=info.get("candidates_count", 0),
                                    candidates=candidates,
                                    element_index_path=_ei_path or "",
                                    resolution_approach=(
                                        "子串匹配出多候选，请 AI 读 element_index 并结合结构视图树分析："
                                        "从候选中筛选语义上正确的滚动目标元素，"
                                        "然后根据其 in_viewport 状态决定下一步"
                                        "——在视口内直接成功，在视口外执行 scroll-until 滚动到位"
                                    ))
                return _handoff("UNRESOLVED", action_arg,
                                matched_text=info.get("matched_text", ""))
            cx, cy = info["center"]
            if not info.get("out_of_viewport", False):
                _center_adjust(cy, layout)
                _h_center_adjust(cx, layout)
                print(f"  SCROLL-UNTIL '{action_arg}' 滚动搜索后已在视口内 (x={cx}, y={cy})")
                return {"ok": True, "reason": "", "ctx": {"search_swipes": attempt},
                        "inspect_tree_impact": "viewport"}
            # 滚动后在视口外，走渐进滚动
            vp_offset = info.get("viewport_offset", 0)
            return _scroll_vertical_progressive(action_arg, layout, vp_offset, step_ratio)

        # 滚动搜索耗尽，handoff AI
        _idx, _ei_path = _build_and_dump_element_index()
        _print_element_index_overview(_idx, layout)
        return _handoff("SCROLL_TARGET_NOT_FOUND", action_arg,
                        screen_size=f"{layout.width}×{layout.height}",
                        viewport_y_range=[layout.viewport_top, layout.viewport_bottom],
                        gesture_full_step=f"纵向{layout.swipe_area_bottom - layout.swipe_area_top}px",
                        element_index_path=_ei_path or "",
                        search_direction=search_dir,
                        resolution_approach=(
                            "滚动搜索已停止（滑动次数用尽或页面内容无变化），"
                            "请读元素目录做语义匹配：从目录表格的「文案」列找到语义上"
                            "符合目标文案的元素（允许文本截断/省略/跨节点聚合），"
                            "确认其在哪个分区（视口内/下方/上方）和 center 坐标后由 AI 决定下一步"
                        ))

    # ═══════════════════════════════════════════════════════════════
    # 分支 B: 精确匹配但坐标缺失 / 子串多候选 — 无法自动处理
    #   - 缺失坐标 → UNRESOLVED，handoff AI 读图定位
    #   - 子串多候选 → SUBSTRING_AMBIGUOUS，handoff AI 读 element_index
    #     结合结构视图树从候选中筛选正确的滚动目标元素
    # ═══════════════════════════════════════════════════════════════
    if info.get("unresolved"):
        reason = info.get("unresolved_reason", "")
        if reason == "substring_ambiguous":
            candidates = info.get("candidates", [])
            _idx_ex, _ei_path = _build_and_dump_element_index()
            return _handoff("SUBSTRING_AMBIGUOUS", action_arg,
                            matched_text=info.get("matched_text", ""),
                            candidates_count=info.get("candidates_count", 0),
                            candidates=candidates,
                            element_index_path=_ei_path or "",
                            resolution_approach=(
                                "子串匹配出多候选，请 AI 读 element_index 并结合结构视图树分析："
                                "从候选中筛选语义上正确的滚动目标元素，"
                                "然后根据其 in_viewport 状态决定下一步"
                                "——在视口内直接成功，在视口外执行 scroll-until 滚动到位"
                            ))
        return _handoff("UNRESOLVED", action_arg,
                        matched_text=info.get("matched_text", ""))

    # ── 唯一精确匹配 — 取坐标 ────────────────────────────────
    cx, cy = info["center"]
    layout = ScreenLayout.from_ops(get_platform_ops())

    # ═══════════════════════════════════════════════════════════════
    # 分支 D: 已在视口内 → 居中微调后直接成功
    # ═══════════════════════════════════════════════════════════════
    if not info.get("out_of_viewport", False):
        _center_adjust(cy, layout)
        _h_center_adjust(cx, layout)
        print(f"  SCROLL-UNTIL '{action_arg}' 已在视口内 (x={cx}, y={cy})")
        return {"ok": True, "reason": "", "ctx": {"in_viewport": True},
                "inspect_tree_impact": "viewport"}

    # ═══════════════════════════════════════════════════════════════
    # 分支 E: 视口外 → 渐进多轮滚动
    # ═══════════════════════════════════════════════════════════════
    vp_offset = info.get("viewport_offset", 0)

    # E1: 显式横向
    if direction in ("left", "right"):
        if not layout.is_y_in_viewport(cy):
            vp_off = layout.viewport_offset(cy)
            print(f"  💡 目标 y={cy} 不在视口内，需先纵向滚动到目标所在行，再横向滚动")
            print(f"     1. step scroll-until --action-arg '{action_arg}' (先纵向滚动)")
            print(f"     2. 确认目标 y 已在视口内后，重新执行 scroll-until --direction {direction}")
            return _handoff("TARGET_Y_OUT_OF_VIEWPORT", action_arg,
                            center=[cx, cy],
                            viewport_offset=vp_off,
                            vp_range=[layout.viewport_top, layout.viewport_bottom])
        # _do_h_swipe 现在接受用户语义方向，直接透传
        return _scroll_horizontal_progressive(action_arg, direction, layout, cy)

    # E2: 纵向 — 纯几何驱动，自动推导手势方向
    return _scroll_vertical_progressive(action_arg, layout, vp_offset, step_ratio)


def handle_scroll_to_edge(action_arg, args):
    """快速滚动到底部/侧边。

    scroll-edge --direction 统一用户语义：想看目标所在的方向
      direction="down" → 想看下方 → 物理上滑 (content up) → 露出下方
      direction="up"   → 想看上方的 → 物理下滑 (content down) → 露出上方
      direction="right" → 想看右侧 → 物理左滑 (content left) → 露出右侧
      direction="left"  → 想看左侧 → 物理右滑 (content right) → 露出左侧

    _do_swipe/_do_h_swipe 的参数是物理手指方向，与用户语义相反，
    因此需要做一次方向反转翻译。
    """
    times = 5
    direction = getattr(args, "direction", None)
    if direction is None:
        direction = "down"

    # 用户语义 → 物理手指方向映射
    _physical_map = {"down": "up", "up": "down", "left": "right", "right": "left"}
    physical_dir = _physical_map.get(direction, direction)

    for _ in range(times):
        if direction in ("left", "right"):
            _do_h_swipe(direction=physical_dir)
        else:
            _do_swipe(direction=physical_dir)
        time.sleep(0.3)

    print(f"  SCROLL-EDGE x{times} direction={direction} (用户语义={direction} → 物理={physical_dir})")
    return {"ok": True, "reason": "", "ctx": {}, "inspect_tree_impact": "viewport"}