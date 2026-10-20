#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""弹窗执行器守卫 —— 固化"唯一执行器 + 词表"的口径，防止回退。

用法：
    python3 scripts/dev/check_popup_executor.py

覆盖不变量（注入假节点 + 真实词表 `platform/popup/patterns.py`，不连设备）：

  A. 命中   隐私协议（「温馨提示」+「同意」）→ 点击中心一次 → `clear`
  B. 无弹窗 空节点 → `none-found`，零动作（不得误点）
  C. 返回键 定位服务引导 → 按返回键（**不点「快速开启定位」**）→ `clear`
  D. 不可解 命中但节点无几何信息 → `unresolvable`，不点击
  E. 上限   弹窗点不掉 → 到 `max_rounds` 停止并报 `unresolvable`
  F. 弹窗链 首启链（隐私 → 通知 → 定位权限）逐轮复校，共 3 次点击 → `clear`
  G. 防误点 只有「不同意」时不得命中（精确匹配，无子串兜底）→ `none-found`
  H. 向导链 场景限定模式（`generic_fallback=False`）走完输入法首启向导 3 步 → `clear`
  I. 场景限定 背景是业务页面时不得触发通用关闭（登录页「×」不被点）→ `none-found`
  J. 优先级 场景命中优先于通用兜底（「×」在屏也不会被点）→ `clear`

退出码：0 全部通过 / 1 有失败。

【为什么需要它】弹窗消除的四个易回退口径都没有编译期保护：
  1. "引擎内单一实现"（不走 CLI `control popup clear`）；
  2. 匹配用**精确**文案（子串兜底会点「不同意」）；
  3. `dismiss=back` 的引导类弹窗**不点按钮**（点它会跳系统设置并顶掉 App）；
  4. 三态语义（`clear / none-found / unresolvable`）与 `max_rounds` 上限。
本脚本把上述口径固化成一条命令，改坏了立即可见。
"""
import os
import sys

# 源树零字节码：本文件是进程入口，开关必须在引擎包导入之前生效。
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import devices.popup as popup  # noqa: E402


def _node(text, clickable=True, box=(100, 200, 40, 20)):
    """构造 UiNode 形状的假节点；box=None 表示缺几何信息（unresolved 场景）。"""
    node = {"all_text": text, "clickable": clickable}
    if box is not None:
        node.update({"x": box[0], "y": box[1], "w": box[2], "h": box[3]})
    return node


def _case(name, scenes, expect_state, expect_taps=0, expect_backs=0, **kwargs):
    """scenes: 第 N 次采集返回的节点列表（超出则复用最后一个）。"""
    taps, backs = [], []
    originals = (popup._nodes, popup._invalidate, popup._tap, popup._back)
    popup._tap = lambda center: (taps.append(center), True)[1]
    popup._back = lambda: (backs.append(1), True)[1]
    popup._invalidate = lambda: None
    calls = {"n": 0}

    def fake_nodes(wait_sec=3):
        idx = min(calls["n"], len(scenes) - 1)
        calls["n"] += 1
        return scenes[idx]

    popup._nodes = fake_nodes
    try:
        result = popup.dismiss_popups(quiet=True, **kwargs)
    finally:
        popup._nodes, popup._invalidate, popup._tap, popup._back = originals

    ok = (result.final_state == expect_state
          and len(taps) == expect_taps and len(backs) == expect_backs)
    mark = "✅" if ok else "❌"
    print(f"{mark} {name}: state={result.final_state} taps={len(taps)} "
          f"backs={len(backs)} dismissed={[d['kind'] for d in result.dismissed]}"
          f"（期望 state={expect_state} taps={expect_taps} backs={expect_backs}）")
    return ok


def main():
    cases = [
        ("A 命中隐私弹窗 → clear",
         [[_node("温馨提示"), _node("同意", box=(140, 1949, 977, 140))], []],
         "clear", 1, 0, {"max_rounds": 3}),
        ("B 无弹窗 → none-found（零动作）",
         [[]], "none-found", 0, 0, {}),
        ("C 定位引导 → 返回键（不点按钮）",
         [[_node("开启定位服务"), _node("快速开启定位", box=(642, 1458, 454, 140))], []],
         "clear", 0, 1, {}),
        ("D 命中但无坐标 → unresolvable",
         [[_node("温馨提示"), _node("同意", box=None)]],
         "unresolvable", 0, 0, {}),
        ("E 点不掉的弹窗 → 到上限报 unresolvable",
         [[_node("温馨提示"), _node("同意")]],
         "unresolvable", 3, 0, {"max_rounds": 3}),
        ("F 首启弹窗链（3 个）→ clear",
         [[_node("温馨提示"), _node("同意")],
          [_node("允许“美团”向你发送通知？"), _node("不允许")],
          [_node("允许“美团”访问你的位置？"), _node("仅使用期间允许")],
          []],
         "clear", 3, 0, {"max_rounds": 5, "prefer_texts": ("同意",)}),
        ("G 只有「不同意」→ 不误点（none-found）",
         [[_node("温馨提示"), _node("不同意")]],
         "none-found", 0, 0, {}),
        ("H 输入法首启向导（3 步）→ 场景限定模式走完",
         [[_node("Celia Keyboard"), _node("Fast, accurate, safe, and fun."), _node("Agree")],
          [_node("Select a Chinese keyboard layout"), _node("Next")],
          [_node("Select a Chinese keyboard layout"), _node("Done")],
          []],
         "clear", 3, 0, {"max_rounds": 6, "prefer_texts": (), "generic_fallback": False}),
        ("I 场景限定模式不得触发通用关闭（登录页「×」不被点）",
         [[_node("欢迎登录美团"), _node("请输入手机号"), _node("×")]],
         "none-found", 0, 0, {"prefer_texts": (), "generic_fallback": False}),
        ("J 场景命中优先于通用兜底（屏上有「×」也只点向导按钮）",
         [[_node("Celia Keyboard"), _node("Agree"), _node("×")], []],
         "clear", 1, 0, {"max_rounds": 3}),
    ]
    passed = 0
    for name, scenes, state, taps, backs, kwargs in cases:
        if _case(name, scenes, state, taps, backs, **kwargs):
            passed += 1
    total = len(cases)
    print(f"\n{'✅ 全部通过' if passed == total else '❌ 存在失败'}: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
