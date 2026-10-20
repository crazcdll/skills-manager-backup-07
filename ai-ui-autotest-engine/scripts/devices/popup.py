#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""弹窗消除（平台无关）—— 引擎内**唯一**的弹窗消除实现。

【定位】把「采集视图树 → 按词表匹配 → 点击 → 复校」做成平台无关的一条路径，
Android 与 HarmonyOS 共用。平台差异由采集层吸收：`PlatformOps.inspect_tree`
按平台分派（Android `uiautomator dump` / HarmonyOS `uitest dumpLayout`），
本层不做平台分支。

【设计要点】
1. **单一路径**：不走 `control popup clear` CLI —— 该 CLI 在 HarmonyOS 不支持
   （`PLATFORM_NOT_SUPPORTED`），在 Android 上也是同一套 dump+tap 的等价物。
   保留两套只会让返回语义 / 日志 / 失败处理分叉，故统一走本模块。
2. **复用主链路采集**：`execution.screen.inspect_tree.get_current_nodes()`
   —— 自带 8s 缓存、重试、多渲染层合并（native 视图树 + WebView DOM 探针），
   不自造采集循环，保证与"目标模型"一致。
3. **词表与执行分离**：识别/消除词表在 `platform/popup/patterns.py`（平台无关数据），
   本模块只负责编排；首启引导、清数据后的隐私弹窗、系统权限弹窗全部走本模块。
4. **匹配用精确文案**（不做子串兜底）：「不同意」包含子串「同意」，子串兜底会在
   精确「同意」不可点击时误点「不同意」。

【接口】`wait_for_popup_ms`（首启等弹窗出现）/ `max_rounds` / `prefer_texts`；
结果三态 `clear / none-found / unresolvable`。
"""
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from platform.popup.patterns import (
    match_generic_close, match_popup, match_preferred, node_center,
)

# 点击后等待页面响应的稳定时间（弹窗关闭/栈变化）
_TAP_SETTLE_SEC = 2.0
# 轮询弹窗出现的间隔（wait_for_popup_ms 生效期间）
_WAIT_POLL_SEC = 0.5


@dataclass
class DismissResult:
    """弹窗消除结果（三态与 CLI 的 finalState 对齐）。"""

    dismissed: List[dict] = field(default_factory=list)
    final_state: str = "none-found"   # clear | none-found | unresolvable

    @property
    def any_dismissed(self) -> bool:
        return bool(self.dismissed)


def _nodes(wait_sec: float = 3):
    """取当前**全窗口**的 UiNode 列表（含系统进程窗口与各渲染层）；采集失败返回 None。

    必须全窗口（`whole_screen=True`）：系统权限弹窗（通知/定位）属**系统进程窗口**，
    按 App 过滤的采集里完全没有它（鸿蒙实测：带 `-b <bundle>` 的 dumpLayout 为空、
    不带才有弹窗节点），否则会出现"弹窗就在屏上、本模块却报 none-found"的假阴性。

    统一走 `execution.screen.inspect_tree.get_current_nodes`：引擎内"需要 UiNode 数据"
    的唯一入口（native 视图树 + 渲染探针合并；whole_screen 时不走 8s 缓存）。
    """
    from execution.screen.inspect_tree import get_current_nodes

    try:
        return get_current_nodes(wait_sec=wait_sec, whole_screen=True)
    except Exception as e:  # noqa: BLE001 — 采集失败按"未采集到"处理，交由调用方决定
        print(f"[popup] ⚠️ 视图树采集异常: {e}")
        return None


def _invalidate():
    """点击后作废采集缓存，保证下一轮重新采集而非命中旧树。"""
    try:
        from execution.screen.inspect_tree import invalidate_cache
        invalidate_cache()
    except Exception as e:  # noqa: BLE001 — 缓存失效失败不影响主流程
        print(f"[popup] ⚠️ 采集缓存失效失败（忽略）: {e}")


def _pick_target(nodes, prefer_texts: Tuple[str, ...], generic_fallback: bool = True):
    """选目标：场景库 → 调用方优先文案 → 通用兜底（优先级与 CLI 一致）。

    `generic_fallback=False` 时**不启用通用关闭兜底**（`DEFAULT_CLOSE_TEXTS`）：
    背景是业务正常页面时（如登录页有「×」返回），通用兜底会误点页面自身按钮。
    """
    target = (match_popup(nodes)
              or (match_preferred(nodes, prefer_texts) if prefer_texts else None))
    if target or not generic_fallback:
        return target
    return match_generic_close(nodes)


def _wait_for_target(prefer_texts: Tuple[str, ...], wait_for_popup_ms: int,
                     generic_fallback: bool = True):
    """等待弹窗出现（对齐 CLI `--wait-for-popup-ms`）：命中即返回 (nodes, target)。"""
    deadline = time.time() + max(0, wait_for_popup_ms) / 1000.0
    while True:
        nodes = _nodes()
        if nodes:
            target = _pick_target(nodes, prefer_texts, generic_fallback)
            if target:
                return nodes, target
        if time.time() >= deadline:
            return nodes, None
        _invalidate()
        time.sleep(_WAIT_POLL_SEC)


def dismiss_popups(*, max_rounds: int = 3, prefer_texts: Tuple[str, ...] = ("同意",),
                   wait_for_popup_ms: int = 0, quiet: bool = False,
                   generic_fallback: bool = True) -> DismissResult:
    """消除当前屏幕上的弹窗（最多 max_rounds 轮，每轮重新采集确认）。

    Args:
        max_rounds: 最多点击轮数（对齐 CLI 默认 5 的思路，这里默认 3）
        prefer_texts: 优先点击的文案（默认「同意」）
        wait_for_popup_ms: 首启场景下等待弹窗出现的最长毫秒数（0=不等待）
        quiet: 静默模式（不打印每轮日志）
        generic_fallback: 是否启用通用关闭兜底（`DEFAULT_CLOSE_TEXTS`）。
            默认 True（首启等"屏幕上只有弹窗"的场景）；背景是业务正常页面时
            必须置 False，否则可能误点页面自身的关闭/返回按钮。

    Returns:
        DismissResult: 已消除项 + 终态（clear / none-found / unresolvable）
    """
    nodes, target = _wait_for_target(prefer_texts, wait_for_popup_ms, generic_fallback)
    result = DismissResult()

    for round_no in range(1, max_rounds + 1):
        if target is None:
            if nodes is None:
                result.final_state = "unresolvable" if result.any_dismissed else "none-found"
                return result
            result.final_state = "clear" if result.any_dismissed else "none-found"
            return result

        if target.get("dismiss") == "back":
            # 引导类弹窗（如"开启定位服务"）：用返回键关闭。它的按钮会跳到系统设置页
            # 并把被测 App 顶掉（实测），而引擎用的是可测性模拟定位，不需要它。
            center = None
            if not quiet:
                print(f"[popup] 第 {round_no} 轮命中「{target['name']}」→ 返回键关闭")
            _back()
        else:
            center = node_center(target["node"])
            if center is None:
                result.final_state = "unresolvable"
                return result
            if not quiet:
                print(f"[popup] 第 {round_no} 轮命中「{target['name']}」→ 点击 {center}")
            _tap(center)
        result.dismissed.append({
            "round": round_no, "kind": target["kind"], "name": target["name"],
            "center": center, "dismiss": target.get("dismiss", "tap"),
        })
        time.sleep(_TAP_SETTLE_SEC)

        # 复校：重新采集后继续匹配（不需要 wait，弹窗已在屏上）
        _invalidate()
        nodes = _nodes()
        target = _pick_target(nodes, prefer_texts, generic_fallback) if nodes else None

    result.final_state = "unresolvable"
    return result


def resolve_system_onboarding(*, max_rounds: int = 6, quiet: bool = False) -> DismissResult:
    """走完**系统层引导**（典型：系统输入法首启向导）—— 场景限定的自愈入口。

    为什么单列一个入口而不复用 `reconcile_environment`：
      · 时机不同：这类引导是在**输入/操作之后**才抢走前台，此时"等待弹窗出现"
        （wait_for_popup_ms）无意义——它已经在屏上；
      · 背景不同：屏上除引导外还有被测 App 的**正常页面**，绝不能启用通用关闭
        兜底（`DEFAULT_CLOSE_TEXTS` 含「×/关闭」），否则会误点页面自身的返回按钮。
    因此本入口 = 只按场景词表精确匹配 + 多轮复采走完整条引导链。
    """
    return dismiss_popups(max_rounds=max_rounds, prefer_texts=(), quiet=quiet,
                          generic_fallback=False)


def _tap(center: Tuple[int, int]) -> bool:
    from shared.context import get_platform_ops

    try:
        return bool(get_platform_ops().tap(*center))
    except Exception as e:  # noqa: BLE001 — 点击失败交由上层按结果判定
        print(f"[popup] ⚠️ 点击 {center} 失败: {e}")
        return False


def _back() -> bool:
    """按返回键关闭当前弹窗（供 `dismiss=back` 的引导类弹窗使用）。"""
    from shared.context import get_platform_ops

    try:
        return bool(get_platform_ops().press_back())
    except Exception as e:  # noqa: BLE001 — 失败交由上层按结果判定
        print(f"[popup] ⚠️ 返回键失败: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# 说明：本模块只提供 `dismiss_popups`（多轮 + 复校）一种消除入口。
# 历史上的 `dismiss_first_match`（单点点击一个指定文案）已移除：首启场景的真正需求是
# “收敛整条弹窗链”（隐私协议 → 系统通知权限 → 定位引导/权限），单点点击会漏掉后续弹窗。
# ═══════════════════════════════════════════════════════════════


__all__ = ["DismissResult", "dismiss_popups", "resolve_system_onboarding"]
