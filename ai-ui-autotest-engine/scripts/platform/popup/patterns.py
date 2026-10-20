#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""弹窗场景词表与匹配（**纯数据 + 纯函数，零 I/O，零依赖**）。

每个场景由「识别条件」+「消除操作」两部分描述：
  · `context_texts` —— 「识别条件」：屏幕上出现其中任一文案，才认为"现在就是这个弹窗"
    （避免孤立按钮文案引发误点）
  · `dismiss`       —— 消除方式（缺省 `tap`）：
      `tap`  在 `tap_texts` 节点上点击（需能定位到按钮）
      `back` 用返回键关闭（用于"点了会跳走"的引导弹窗）——本方式**不使用**
            `tap_texts`，因此此类场景不需要写该字段
  · `tap_texts`     —— 「消除操作（dismiss=tap）」：在其中任一文案对应的可点击节点上点击
  · `kind`          —— 分类，用于日志与统计

放在 platform 层的原因：词表是**平台无关的业务语义**，且本模块不依赖
`devices`/`execution`（platform 层只允许依赖 shared/platform）。真正的
"采集 + 点击"动作在 `devices/popup.py` 里做。

词表来自鸿蒙云模拟器实测（首装/清数据后逐帧 dumpLayout 枚举得到）：
  1. 隐私协议「温馨提示」→ 同意                （模态门禁，必须处理）
  2. 通知权限「允许"美团"向你发送通知？」→ 不允许
  3. 定位服务引导「开启定位服务」→ **返回键关闭**（不点「快速开启定位」：
     点它会跳系统设置页并把被测 App 顶掉（实测），而引擎登录用的是 L1 可测性模拟
     定位，**不依赖**系统定位总开关（L2），跳过去纯负收益）
  4. 定位权限「允许"美团"访问你的位置？」→ 仅使用期间允许
  5. 系统输入法（华为 Celia Keyboard）首启向导「同意 → 选择键盘布局 → 完成」
     → 逐步点主按钮（输入后抢前台的系统层引导，见词表末尾注释）
"""
from typing import Optional, Sequence

# kind 取值：app-agreement / system-permission / app-guide / custom / close-btn
#            / system-ime-onboarding
POPUP_PATTERNS: tuple = (
    {
        "name": "隐私协议（温馨提示）",
        "kind": "app-agreement",
        "context_texts": ("温馨提示",),
        "tap_texts": ("同意",),
    },
    {
        "name": "通知权限",
        "kind": "system-permission",
        "context_texts": ("向你发送通知",),
        "tap_texts": ("不允许", "拒绝"),
    },
    {
        "name": "定位服务引导",
        "kind": "app-guide",
        "context_texts": ("开启定位服务",),
        # 用返回键关闭（**不点「快速开启定位」**）：后者会把 App 顶掉并跳到系统设置页
        # （实测），而登录用的是 L1 可测性模拟定位，不需要系统定位总开关（L2）。
        # 故本场景不提供 tap_texts（dismiss=back 不需要按钮）。
        "dismiss": "back",
    },
    {
        "name": "定位权限",
        "kind": "system-permission",
        "context_texts": ("访问你的位置",),
        "tap_texts": ("仅使用期间允许", "本次使用允许"),
    },
    # ── 系统输入法首启向导（华为 Celia Keyboard 实测）────────────────────
    # 新设备 / 清数据后**首次唤起键盘**时，输入法框架弹出多步向导，且它是**独立系统
    # 窗口**：被测 App 丢焦点，按 App 包名过滤的视图树采不到页面 → 任何"输入手机号后
    # 继续定位控件"的流程必然失败（实测：验证码登录连续 3 轮失败，B2 阶段被拖到十几
    # 分钟）。向导为英文、分多步，故按**各步页面标题**识别、按步点主按钮；消除器逐轮
    # 复采，一次调用即可走完「同意 → 选择布局 → 完成」。
    # 新增其他输入法/语言时按同样结构补词条即可（context 用页面上稳定出现的短串）。
    {
        "name": "输入法首启向导（隐私同意）",
        "kind": "system-ime-onboarding",
        "context_texts": ("Celia Keyboard",),
        "tap_texts": ("Agree", "同意"),
    },
    {
        "name": "输入法首启向导（选择键盘布局）",
        "kind": "system-ime-onboarding",
        # 标题在屏上会折行（Select a Chinese / keyboard layout），故取行内短串
        "context_texts": ("keyboard layout",),
        "tap_texts": ("Next", "Done", "下一步", "完成"),
    },
)

# 通用兜底：明确"关闭/跳过/以后/取消"类在前，「允许」类放最后
DEFAULT_CLOSE_TEXTS: tuple = (
    "关闭", "×", "X",
    "跳过", "以后再说", "稍后", "暂不", "下次", "不了",
    "取消", "解除",
    "知道了", "我知道了", "不再提示", "继续使用",
    "继续",
    "仅在使用期间允许", "仅使用期间允许", "始终允许", "允许",
)


def node_text(node: dict) -> str:
    """取节点的可匹配文案（`all_text` 优先，回退 `merged_text`）。"""
    return (node.get("all_text") or node.get("merged_text") or "").strip()


def node_center(node: dict):
    """节点中心坐标；缺几何信息时返回 None。"""
    x, y, w, h = node.get("x"), node.get("y"), node.get("w"), node.get("h")
    if None in (x, y, w, h):
        return None
    return int(x) + int(w) // 2, int(y) + int(h) // 2


def _find_by_texts(nodes: Sequence[dict], texts: Sequence[str], *, clickable_only: bool = True):
    """按文案找可点击节点（**精确匹配**）。

    ⚠️ 刻意**不做子串兑底**：弹窗按钮文案是精确的，而子串匹配会引入误点——
    例如「不同意」包含子串「同意」，若精确的「同意」节点不可点击（或被遮挡未标记
    clickable），子串兑底会错误点中「不同意」，造成与预期相反的结果。
    （识别用的 `context_texts` 仍用子串，因为它们是"页面出现这句话"的判据，
    如「向你发送通知」就只作为「允许“美团”向你发送通知？」的子串出现。）
    """
    for want in texts:
        for node in nodes:
            if clickable_only and not node.get("clickable"):
                continue
            if node_text(node) == want:
                return node
    return None


def match_popup(nodes: Sequence[dict], patterns: Sequence[dict] = POPUP_PATTERNS) -> Optional[dict]:
    """按场景库匹配当前页面，返回 `{node, kind, name, dismiss}`；未命中返回 None。

    匹配规则：**先确认"是这个弹窗"（context_texts，子串）**；
    再看消除方式：
      · `dismiss=tap`（缺省）—— 用精确文本找消除按钮（tap_texts），找不到则本场景不命中；
      · `dismiss=back`        —— 无需按钮，命中即返回（执行器用返回键关闭），
                                用于"点了会跳走"的引导类弹窗。
    """
    for pattern in patterns:
        has_context = any(
            any(ctx_text in node_text(n) for n in nodes)
            for ctx_text in pattern.get("context_texts", ())
        )
        if not has_context:
            continue
        dismiss = pattern.get("dismiss", "tap")
        if dismiss == "back":
            return {"node": None, "kind": pattern.get("kind", ""),
                    "name": pattern.get("name", ""), "dismiss": "back"}
        button = _find_by_texts(nodes, pattern.get("tap_texts", ()))
        if button is None:
            continue
        return {"node": button, "kind": pattern.get("kind", ""),
                "name": pattern.get("name", ""), "dismiss": "tap"}
    return None


def match_preferred(nodes: Sequence[dict], prefer_texts: Sequence[str]):
    """按调用方指定的优先文案匹配。"""
    node = _find_by_texts(nodes, tuple(prefer_texts or ()))
    return {"node": node, "kind": "custom", "name": "prefer-text"} if node else None


def match_generic_close(nodes: Sequence[dict]):
    """通用兜底：按 `DEFAULT_CLOSE_TEXTS` 找可点击的关闭/跳过按钮。"""
    node = _find_by_texts(nodes, DEFAULT_CLOSE_TEXTS)
    return {"node": node, "kind": "close-btn", "name": "通用关闭"} if node else None


__all__ = [
    "POPUP_PATTERNS", "DEFAULT_CLOSE_TEXTS",
    "node_text", "node_center", "match_popup", "match_preferred", "match_generic_close",
]
