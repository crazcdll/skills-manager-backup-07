"""back / open-url handler — 页面导航。"""

import time

from shared.context import get_platform_ops
from execution.screen.page_stability import wait_page_stable
from execution.screen.inspect_tree import invalidate_cache

# reason_code → 说明。本模块是 back / open-url 的 **emit 全集声明**：
# 每个 code 都必须能路由到 hook（引擎内部错误列在 on_fail.REASONS_WITHOUT_HOOK），
# 否则 check_target_model 的元守卫会报红（避免 handoff 时「无指引」静默死端）。
_REASON_LABELS = {
    "BACK_FAILED": "press_back 设备执行失败（返回键未生效）",
    "MISSING_URL": "open-url 缺少 URL 参数",
    "PUSH_FAILED": "open-url scheme 推送失败",
}


def _fail(reason_code, action, impact="none", **kw):
    """结构化失败返回：ctx.reason 是引擎的 hook 路由键（不能只给自然语言 reason）。"""
    ctx = {"action": action, "reason": reason_code}
    ctx.update(kw)
    return {"ok": False, "reason": _REASON_LABELS.get(reason_code, reason_code),
            "ctx": ctx, "inspect_tree_impact": impact}


def handle_back(action_arg, args):
    """执行返回操作（平台无关，委托 PlatformOps.press_back()）。"""
    ops = get_platform_ops()
    if not ops.press_back():
        print("  BACK FAIL")
        return _fail("BACK_FAILED", "back")
    print("  BACK pressed")
    time.sleep(0.8)
    return {"ok": True, "reason": "", "ctx": {}, "inspect_tree_impact": "full"}


def handle_open_url(action_arg, args):
    """通过 scheme 重新加载页面。"""
    url = action_arg or ""
    if not url:
        print("STEP ACTION FAIL: open-url 需要 --action-arg <url>")
        return _fail("MISSING_URL", "open-url", impact="full")
    ops = get_platform_ops()
    print(f"  OPEN-URL: {url[:80]}...")
    if not ops.open_url(url):
        print("  ⚠️ open-url 推送失败")
        return _fail("PUSH_FAILED", "open-url", impact="full")
    wait_page_stable()
    invalidate_cache()
    return {"ok": True, "reason": "", "ctx": {},
            "inspect_tree_impact": "full"}