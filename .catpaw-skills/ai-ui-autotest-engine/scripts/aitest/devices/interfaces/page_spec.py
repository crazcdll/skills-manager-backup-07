#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PageSpec：页面描述契约（**纯数据**）—— 页面身份 + 控件选择器 + 到达路径。

【定位】把"这个页面长什么样 / 控件怎么找 / 从哪些入口能到达"从**代码**变成**数据**，
按 `(app, platform)` 注册（挂在 `AppDescriptor.page_specs` 上）。与弹窗词表
（`platform/popup/patterns.py`）同构：**改行为 = 改数据，不改流程**。

【为什么必须是数据】同一份登录流程要跨 Android / HarmonyOS / iOS：
  · Android 登录页是独立 Activity、暴露 resource-id → 选择器 `id` 优先；
  · 鸿蒙同一 Ability 内路由、几乎无 resource-id（实测登录页仅 3 个 id）→ `role`/`text` 优先；
把差异压进"选择器先后顺序"（见 `execution/screen/selectors.py`），登录业务层就只剩意图。

【分层】本模块属 `devices`，**不得依赖 `execution`**：因此这里只做纯数据与**字符串级**
判定（`matches_window`）；基于页面内容的判定由消费方调 `selectors.supports(texts, spec.identity)`。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Hop:
    """到达页面路径中的**一跳**。

    字段：
      enter  进入本跳要**点击**的入口选择器列表（顺序即尝试顺序；命中即点）
      expect 点完应出现的**文本选择器**（确认本跳是否生效，决定是否继续下一跳）
    """

    enter: tuple = ()
    expect: tuple = ()


@dataclass(frozen=True)
class Route:
    """到达页面的**一条候选路径**：按序逐跳「点击 → 校验」，任一跳不生效即整条放弃。

    多条 `Route` 互为候选（首页形态随版本/机型/登录态而变），业务层逐条尝试。
    """

    hops: tuple = ()


class PageSpec:
    """一个页面的声明式描述。

    字段：
      name     页面标识（日志/排查用）
      identity 页面身份选择器（**内容判定**，跨端可靠；`text` 型）
      markers  窗口名标记（**可选快速信号**，平台相关：Android 登录页 Activity 名含 login，
               鸿蒙同一 Ability 路由切换不改窗口标识 → 传空）
      controls 语义名 → 选择器列表（顺序即优先级；见 selectors 支持的选择器）
      routes   到达该页的**候选路径**列表（顺序即尝试顺序；逐跳点-校验，任一跳失败即换下一条）
    """

    __slots__ = ("name", "identity", "markers", "controls", "routes")

    def __init__(self, name, identity=(), markers=(), controls=None, routes=()):
        self.name = name
        self.identity = tuple(identity)
        self.markers = tuple(markers)
        self.controls = dict(controls or {})
        self.routes = tuple(routes)

    def control(self, name) -> tuple:
        """取某语义控件的选择器列表（未知控件返回空元组 → 调用方按"缺失"处理）。"""
        return tuple(self.controls.get(name) or ())

    def matches_window(self, focus: str) -> bool:
        """窗口名快速判定（纯字符串；无 markers 时恒 False）。"""
        return bool(focus) and any(m in focus for m in self.markers)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "identity": list(self.identity),
            "markers": list(self.markers),
            "controls": {k: list(v) for k, v in self.controls.items()},
            "routes": [
                {"hops": [{"enter": list(hop.enter), "expect": list(hop.expect)}
                          for hop in route.hops]}
                for route in self.routes
            ],
        }


# 约定的页面键（各 AppDescriptor 提供；缺省表示该 App/平台未声明）
PAGE_LOGIN = "login"
PAGE_LOGIN_CODE = "login_code"

__all__ = ["PageSpec", "Hop", "Route", "PAGE_LOGIN", "PAGE_LOGIN_CODE"]
