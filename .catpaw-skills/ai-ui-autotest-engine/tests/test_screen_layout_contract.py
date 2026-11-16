#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ScreenLayout 契约 + 坐标兜底滚动的回归测试（stdlib unittest，零外部依赖、不需要设备）。

背景：坐标兜底路径曾引用不存在的 ``ScreenLayout.default_step``，只有在「坐标在视口外
且 |viewport_offset| > 50」时才会走到该行，于是表现为运行期 AttributeError，整条 step
命令被 run_with_guard 归类为 fatal（script 缺陷）。本测试锁三件事：

  1. 引擎内所有 ``layout.<attr>`` 访问都真实存在于 ScreenLayout —— 防止同类改名漏改；
  2. 视口外坐标会真的发起滑动且不抛异常（直接复现原故障分支）；
  3. 滚动步长的上下界（MIN_SCROLL_STEP 下限、手势区高度上限）。

运行（在 Skill 根目录）：

    python3 -B -m unittest discover -s tests -t . -v
"""
import ast
import pathlib
import sys
import unittest
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import aitest.cli  # noqa: E402,F401 —— 先加载完整命令树，规避 handlers 包的循环导入
from aitest.execution.screen.screen_layout import ScreenLayout  # noqa: E402
from aitest.execution.steps.handlers import base as handler_base  # noqa: E402


class LayoutAttributeContractTest(unittest.TestCase):
    """静态契约：引擎里出现的每个 layout.* 属性都必须存在于 ScreenLayout。"""

    SEARCH_ROOT = SCRIPTS / "aitest"

    def _collect_layout_attributes(self):
        """收集源码中 ``layout.xxx`` / ``xxx_layout.xxx`` 形式的属性访问。"""
        found = {}
        for path in sorted(self.SEARCH_ROOT.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            # 只在真正用 ScreenLayout 的文件里做约束，避免把同名局部变量误判
            if "ScreenLayout" not in source:
                continue
            try:
                tree = ast.parse(source)
            except SyntaxError:  # pragma: no cover —— 语法错误交给 CI 其它环节
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Attribute):
                    continue
                owner = node.value
                if not isinstance(owner, ast.Name):
                    continue
                if owner.id != "layout" and not owner.id.endswith("_layout"):
                    continue
                found.setdefault(node.attr, set()).add(
                    f"{path.relative_to(SCRIPTS)}:{node.lineno}")
        return found

    def test_layout_attributes_exist_on_screen_layout(self):
        attributes = self._collect_layout_attributes()
        self.assertTrue(attributes, "未采集到任何 layout.* 访问，扫描逻辑失效")

        missing = {
            attr: sorted(where)
            for attr, where in attributes.items()
            if not hasattr(ScreenLayout, attr)
        }
        self.assertEqual(
            {}, missing,
            "存在 ScreenLayout 上不存在的属性访问（改名漏改会在运行期抛 "
            "AttributeError）：" + "; ".join(
                f"{attr} @ {', '.join(where)}" for attr, where in missing.items()))


class AutoScrollCoordsToViewportTest(unittest.TestCase):
    """行为回归：坐标兜底滚动必须真的滑动，且不得抛异常。"""

    class _RecordingOps:
        def __init__(self):
            self.swipes = []

        def swipe(self, **kwargs):
            self.swipes.append(kwargs)

    def _layout(self):
        # 视口 [48, 1184]，与线上故障现场（坐标 293,1258 / offset≈642）一致
        return ScreenLayout(1080, 1250, top_inset=48, bottom_inset=66)

    def _run(self, ax, ay, layout):
        ops = self._RecordingOps()
        with mock.patch.object(handler_base, "get_platform_ops", return_value=ops), \
                mock.patch.object(handler_base, "dump_inspect_tree", return_value=None), \
                mock.patch.object(handler_base, "invalidate_cache", return_value=None), \
                mock.patch.object(handler_base.time, "sleep", return_value=None):
            result = handler_base._auto_scroll_coords_to_viewport(
                ax, ay, layout, label="TAP")
        return result, ops

    def test_out_of_viewport_coordinate_scrolls(self):
        layout = self._layout()
        self.assertFalse(layout.is_in_viewport(1258, 293))
        self.assertGreater(abs(layout.viewport_offset(1258)), 50)

        result, ops = self._run(293, 1258, layout)

        self.assertEqual((293, 1258), result)
        self.assertTrue(ops.swipes, "坐标在视口外时应至少发起一次滑动")
        for swipe in ops.swipes:
            self.assertEqual(layout.center_x, swipe["from_x"])
            self.assertEqual(layout.center_x, swipe["to_x"])
            self.assertGreater(swipe["from_y"], swipe["to_y"],
                               "目标在下方时应物理上滑（y 由大到小）")
            self.assertGreaterEqual(swipe["from_y"], layout.swipe_area_top)
            self.assertLessEqual(swipe["from_y"], layout.swipe_area_bottom)

    def test_in_viewport_coordinate_is_untouched(self):
        layout = self._layout()
        self.assertTrue(layout.is_in_viewport(600, 293))

        result, ops = self._run(293, 600, layout)

        self.assertEqual((293, 600), result)
        self.assertEqual([], ops.swipes, "坐标已在视口内时不应滑动")

    def test_upward_target_swipes_down(self):
        layout = self._layout()

        _, ops = self._run(293, 30, layout)

        self.assertTrue(ops.swipes)
        for swipe in ops.swipes:
            self.assertLess(swipe["from_y"], swipe["to_y"],
                            "目标在上方时应物理下滑（y 由小到大）")


class ScrollStepTest(unittest.TestCase):
    """步长契约：唯一实现在 ScreenLayout.scroll_step 内。"""

    def test_step_never_exceeds_gesture_area(self):
        layout = ScreenLayout(1080, 1250)
        self.assertEqual(layout.swipe_area_bottom - layout.swipe_area_top,
                         layout.max_scroll_step)
        self.assertEqual(layout.max_scroll_step, layout.scroll_step(100000))

    def test_step_never_below_min_step(self):
        layout = ScreenLayout(1080, 3000)
        self.assertEqual(layout.MIN_SCROLL_STEP, layout.scroll_step(1))

    def test_step_scales_with_offset(self):
        layout = ScreenLayout(1080, 3000)  # 手势区高度 1200
        self.assertEqual(700, layout.scroll_step(1000, step_ratio=0.7, min_step=200))

    def test_half_screen_floor_used_by_coordinate_fallback(self):
        layout = ScreenLayout(1080, 1250)
        self.assertEqual(layout.default_scroll_step,
                         int(layout.height * ScreenLayout.DEFAULT_SCROLL_STEP_RATIO))
        # 半屏(625) > 手势区(500) → 实际步长被手势区高度封顶
        self.assertEqual(layout.max_scroll_step,
                         layout.scroll_step(74, min_step=layout.default_scroll_step))

    def test_calc_vertical_swipe_uses_shared_step(self):
        layout = ScreenLayout(1080, 3000)
        s_from, s_to = layout.calc_vertical_swipe("down", 1000)
        self.assertEqual(layout.swipe_area_bottom, s_from)
        self.assertEqual(layout.scroll_step(1000), abs(s_to - s_from))


if __name__ == "__main__":
    unittest.main()
