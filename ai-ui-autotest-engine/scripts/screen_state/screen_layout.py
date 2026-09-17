#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ScreenLayout — 屏幕几何布局计算。

从实际屏幕尺寸推导视口区域、手势参数、安全坐标，
消除 scroll.py / handlers/base.py / commands/scroll.py 中散落的 magic numbers。

所有比例常量集中在此类的类属性上，便于统一调整。

跨端设计：
  - 视口 insets（顶部/底部/左侧/右侧的遮挡区域）优先从平台层获取真实值
    （PlatformOps.viewport_insets()），各端实现各自读取系统 API
  - 平台无法获取时，兜底使用类属性的默认值（Android 经验值）
  - 手势区域仍使用比例常量（与屏幕尺寸相关，无需平台感知）
"""
import typing
from device_platform.base import PlatformOps


class ScreenLayout:
    """屏幕几何布局 —— 从实际屏幕尺寸计算视口区域和手势参数。"""

    # 视口边距默认值（像素）：平台无法提供真实值时兜底使用
    # 各端可在 PlatformOps.viewport_insets() 中返回各自真实值
    VIEWPORT_TOP_MARGIN = 90        # Android 默认状态栏高度
    VIEWPORT_BOTTOM_MARGIN = 120    # Android 默认导航栏高度
    VIEWPORT_LEFT_MARGIN = 0        # 默认无横向遮挡
    VIEWPORT_RIGHT_MARGIN = 0       # 默认无横向遮挡

    # 手势区域比例（相对屏幕高度）
    SWIPE_AREA_TOP_RATIO = 0.15
    SWIPE_AREA_BOTTOM_RATIO = 0.55

    # 默认滚动步长比例（相对屏幕高度）
    DEFAULT_SCROLL_STEP_RATIO = 0.5

    # 居中微调阈值（像素）：目标偏离视口中心超过此值才触发微调
    CENTER_ADJUST_THRESHOLD = 60

    # 视口检测安全余量（像素）：元素中心距视口边界 < 此值视为"边缘可见"
    VIEWPORT_EDGE_TOLERANCE = 10

    # Recce 浮层"已在右上角"判定比例
    RECCE_CORNER_X_RATIO = 0.85
    RECCE_CORNER_Y_RATIO = 0.08
    RECCE_CORNER_MARGIN = 20
    RECCE_CORNER_Y = 40

    def __init__(self, width: int, height: int, top_inset: int = 0,
                 bottom_inset: int = 0, left_inset: int = 0, right_inset: int = 0):
        self._w = width
        self._h = height
        # 视口 insets：平台真实值优先，0 或缺失时兜底为类属性默认值
        self._top = top_inset if top_inset > 0 else self.VIEWPORT_TOP_MARGIN
        self._bottom = bottom_inset if bottom_inset > 0 else self.VIEWPORT_BOTTOM_MARGIN
        self._left = left_inset if left_inset > 0 else self.VIEWPORT_LEFT_MARGIN
        self._right = right_inset if right_inset > 0 else self.VIEWPORT_RIGHT_MARGIN

    @classmethod
    def from_ops(cls, ops: PlatformOps) -> "ScreenLayout":
        """从 PlatformOps 构造，自动获取屏幕尺寸和视口 insets。"""
        w, h = ops.screen_size()
        insets = ops.viewport_insets() if hasattr(ops, "viewport_insets") else {}
        return cls(w, h,
                   top_inset=insets.get("top", 0),
                   bottom_inset=insets.get("bottom", 0),
                   left_inset=insets.get("left", 0),
                   right_inset=insets.get("right", 0))

    @property
    def width(self) -> int:
        return self._w

    @property
    def height(self) -> int:
        return self._h

    @property
    def center_x(self) -> int:
        """屏幕水平中心（纵向滑动手势的 x 坐标）。"""
        return self._w // 2

    @property
    def center_y(self) -> int:
        """屏幕垂直中心。"""
        return self._h // 2

    @property
    def viewport_top(self) -> int:
        """可视区域上边界（避开状态栏/导航栏/刘海）。"""
        return self._top

    @property
    def viewport_bottom(self) -> int:
        """可视区域下边界（避开底部导航栏/手势条）。"""
        return self._h - self._bottom

    @property
    def viewport_left(self) -> int:
        """可视区域左边界（预留横向安全区，默认 0）。"""
        return self._left

    @property
    def viewport_right(self) -> int:
        """可视区域右边界（预留横向安全区，默认 0）。"""
        return self._w - self._right

    @property
    def viewport_center(self) -> int:
        """可视区域垂直中心。"""
        return (self.viewport_top + self.viewport_bottom) // 2

    @property
    def viewport_x_center(self) -> int:
        """可视区域水平中心。"""
        return (self.viewport_left + self.viewport_right) // 2

    @property
    def h_swipe_y(self) -> int:
        """横向滑动时的 y 坐标（视口垂直中心，大多数横向容器在屏幕中部）。"""
        return (self.viewport_top + self.viewport_bottom) // 2

    def viewport_offset_x(self, x: int) -> int:
        """水平偏移，正=在右侧，负=在左侧。"""
        return x - self.viewport_x_center

    def clamp_swipe_y(self, y: int) -> int:
        """将 y 坐标夹紧到视口范围内，防止越界手势。"""
        return max(self.viewport_top, min(y, self.viewport_bottom))

    def calc_vertical_swipe(self, direction: str, offset: int,
                            step_ratio: float = 0.7,
                            min_step: int = 200) -> tuple[int, int]:
        """计算纵向一次滑动的 (from_y, to_y)，消除重复坐标计算。

        方向=用户语义（目标方向），引擎内部翻译为物理手指方向：
          "down" = 想看下方 → 物理上滑（y大→y小），内容上移露出下方
          "up"   = 想看上方的 → 物理下滑（y小→y大），内容下移露出上方

        注意：手势起止点从手势区边缘（顶部/底部）开始，而非居中。
        RN ScrollView 需要完整手势行程才生效，居中算法会使滑动区域过短。
        Args:
            direction: "down"（想看下方）或 "up"（想看上方）。
            offset: viewport_offset 值（像素绝对值），仅用于计算幅度。
            step_ratio: 步长比例（0~1），默认 0.7。
            min_step: 最小步长（像素），默认 200。
        Returns:
            (from_y, to_y) 供 _do_swipe 调用。
        """
        full_step = self.swipe_area_bottom - self.swipe_area_top
        step = min(self.max_scroll_step, max(min_step, int(abs(offset) * step_ratio)))
        if direction == "down":
            # 想看下方 → 物理上滑：finger 从下→上（y大→y小）
            s_from = self.swipe_area_bottom
            s_to = max(self.swipe_area_top, s_from - step)
        else:
            # 想看上方向 → 物理下滑：finger 从上→下（y小→y大）
            s_from = self.swipe_area_top
            s_to = min(self.swipe_area_bottom, s_from + step)
        return s_from, s_to

    @property
    def swipe_area_top(self) -> int:
        """滑动手势起始区域上边界。"""
        return int(self._h * self.SWIPE_AREA_TOP_RATIO)

    @property
    def swipe_area_bottom(self) -> int:
        """滑动手势起始区域下边界。"""
        return int(self._h * self.SWIPE_AREA_BOTTOM_RATIO)

    @property
    def max_scroll_step(self) -> int:
        """最大滚动步长（手势区域高度）。"""
        return self.swipe_area_bottom - self.swipe_area_top

    @property
    def default_scroll_step(self) -> int:
        """默认滚动步长。"""
        return int(self._h * self.DEFAULT_SCROLL_STEP_RATIO)

    @property
    def recce_corner_x(self) -> int:
        """Recce 浮层拖拽目标 x 坐标（屏幕右侧边缘）。"""
        return self._w - self.RECCE_CORNER_MARGIN

    @property
    def recce_corner_y(self) -> int:
        """Recce 浮层拖拽目标 y 坐标（屏幕顶部边缘）。"""
        return self.RECCE_CORNER_Y

    def is_in_recce_corner(self, cx: int, cy: int) -> bool:
        """判断坐标是否已在 Recce 浮层的目标角落区域。"""
        return (cx > self._w * self.RECCE_CORNER_X_RATIO
                and cy < self._h * self.RECCE_CORNER_Y_RATIO)

    # ═══════════════════════════════════════════════════════════════
    # 视口检测方法 — 全仓库唯一视口判定入口，消除各处 inline 判断
    # ═══════════════════════════════════════════════════════════════

    def is_in_viewport(self, y: int, x: typing.Optional[int] = None) -> bool:
        """判断坐标是否在当前视口可见区域内（含容差）。

        全仓库统一的视口判定入口，同时检查 y 轴和 x 轴。
        未来支持横向滚动后，x 检查自动生效，无需修改调用方。

        判定逻辑：
        - y 坐标在 [viewport_top, viewport_bottom] 范围内（含容差）
        - x 坐标（若提供）在 [viewport_left, viewport_right] 范围内（含容差）
        - 使用中心坐标判定，因为 inspect-tree 返回的 center 是节点几何中心

        Args:
            y: 节点中心 y 坐标
            x: 节点中心 x 坐标（可选，横向滚动场景必须提供）

        Returns:
            True 表示坐标在视口可见区域内
        """
        top = self.viewport_top - self.VIEWPORT_EDGE_TOLERANCE
        bottom = self.viewport_bottom + self.VIEWPORT_EDGE_TOLERANCE
        if not (top <= y <= bottom):
            return False
        if x is not None:
            left = self.viewport_left - self.VIEWPORT_EDGE_TOLERANCE
            right = self.viewport_right + self.VIEWPORT_EDGE_TOLERANCE
            if not (left <= x <= right):
                return False
        return True

    def is_y_in_viewport(self, y: int) -> bool:
        """仅按 y 坐标判断是否在视口内（含容差），
        用于不需要 x 轴检查的场景（纯纵向滚动）。

        Args:
            y: 节点中心 y 坐标

        Returns:
            True 表示 y 坐标在视口可见区域内
        """
        top = self.viewport_top - self.VIEWPORT_EDGE_TOLERANCE
        bottom = self.viewport_bottom + self.VIEWPORT_EDGE_TOLERANCE
        return top <= y <= bottom

    def viewport_offset(self, y: int) -> int:
        """返回 y 坐标相对视口中心的偏移量（正=在下方，负=在上方）。

        用于推断滚动方向：
          偏移为正 → 目标在下方 → direction="down"（想看下方，引擎翻译为物理上滑）
          偏移为负 → 目标在上方 → direction="up"（想看上方，引擎翻译为物理下滑）
        """
        return y - self.viewport_center

    def scroll_distance_to_center(self, y: int) -> int:
        """返回将 y 坐标滚动到视口中心所需的滚动距离（像素）。

        正值表示目标在下方（用户语义 direction="down"），
        负值表示目标在上方（用户语义 direction="up"）。
        """
        return y - self.viewport_center