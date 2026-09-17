#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""页面稳定等待 — 统一 open-url 和 tap-text 跳转后的页面渲染等待。

独立命令（_cmd_open_url）和 step handler 共用此模块，
确保两处行为一致。

页面是否正常由 AI 读截图判定，本模块仅负责等待页面渲染出基本内容。
"""
import sys
import time

from screen_state.inspect_tree import dump_inspect_tree, parse_inspect_tree, invalidate_cache


def wait_page_stable(timeout: float = 12.0, stable_rounds: int = 2, zone: int = 5) -> bool:
    """等待页面稳定：文本节点数在 zone 范围内连续 stable_rounds 次不变。

    轮询采集视图树，检测文本节点数。当节点数变化在 ±zone 内且
    连续 stable_rounds 次满足条件时，认为页面已稳定。
    页面是否正确由 AI 读截图判定，本函数只保证"页面不再大幅变化"。

    Args:
        timeout: 总超时秒数
        stable_rounds: 连续稳定轮数（每轮间隔约 2-4s）
        zone: 容许的波动范围，节点数变化在 ±zone 内算稳定

    Returns:
        True: 页面已稳定；False: 超时仍未稳定
    """
    deadline = time.time() + timeout
    prev_count = None
    stable_count = 0

    while time.time() < deadline:
        invalidate_cache()
        raw = dump_inspect_tree(wait_sec=2, max_attempts=1)
        if not raw:
            stable_count = 0
            remaining = deadline - time.time()
            if remaining > 0:
                time.sleep(min(1.0, remaining))
            if remaining > 0 and time.time() < deadline - 2:
                sys.stderr.write("[page_stability] 视图树采集返回空，等待重试...\n")
            continue

        nodes = parse_inspect_tree(raw)
        current_count = len([n for n in nodes if n.get("text")])

        if prev_count is not None and abs(current_count - prev_count) <= zone:
            stable_count += 1
            if stable_count >= stable_rounds:
                return True
        else:
            stable_count = 0

        prev_count = current_count
        remaining = deadline - time.time()
        if remaining > 0:
            time.sleep(min(2.0, remaining))

    return False