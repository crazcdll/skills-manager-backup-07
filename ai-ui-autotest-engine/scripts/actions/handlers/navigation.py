"""back / open-url handler — 页面导航。"""

import time

from context import get_platform_ops
from screen_state.page_stability import wait_page_stable
from screen_state.inspect_tree import invalidate_cache


def handle_back(action_arg, args):
    """执行返回操作（平台无关，委托 PlatformOps.press_back()）。"""
    ops = get_platform_ops()
    if not ops.press_back():
        print("  BACK FAIL")
        return {"ok": False, "reason": "press_back 设备执行失败",
                "ctx": {"action": "back"},
                "inspect_tree_impact": "none"}
    print("  BACK pressed")
    time.sleep(0.8)
    return {"ok": True, "reason": "", "ctx": {}, "inspect_tree_impact": "full"}


def handle_open_url(action_arg, args):
    """通过 scheme 重新加载页面。"""
    url = action_arg or ""
    if not url:
        print("STEP ACTION FAIL: open-url 需要 --action-arg <url>")
        return {"ok": False, "reason": "open-url 缺少 URL 参数",
                "ctx": {"action": "open-url", "reason": "MISSING_URL"},
                "inspect_tree_impact": "full"}
    ops = get_platform_ops()
    print(f"  OPEN-URL: {url[:80]}...")
    r = ops.open_url(url)
    if not r:
        print(f"  ⚠️ open-url 推送失败")
        return {"ok": False, "reason": "open_url_failed",
                "ctx": {"action": "open-url", "reason": "PUSH_FAILED"},
                "inspect_tree_impact": "full"}
    wait_page_stable()
    invalidate_cache()
    return {"ok": True, "reason": "", "ctx": {},
            "inspect_tree_impact": "full"}