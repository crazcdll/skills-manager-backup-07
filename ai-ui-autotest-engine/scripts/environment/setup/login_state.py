"""登录态原语：判断是否已登录、跳回首页。"""
import time
from context import get_platform_ops, get_app_descriptor
from environment.setup.app_lifecycle import _current_focus_window, wait_app_foreground


def login_go_home():
    """登录后跳回主页，确认焦点稳定停留在 MainActivity。"""
    ops = get_platform_ops()
    app = get_app_descriptor()
    print("LOGIN-GO-HOME: 跳回主页...")
    if not ops.launch_app(app.main_activity, launcher_intent=True):
        print("LOGIN-GO-HOME: ⚠️ launch_app 首次拉回失败")
    time.sleep(2)

    if wait_app_foreground(timeout=8, interval=1.0):
        print("LOGIN-GO-HOME OK: 已跳回主页并确认前台稳定")
        return True

    print("LOGIN-GO-HOME: ⚠️ 焦点未能稳定停留在 MainActivity，重试拉回一次...")
    if not ops.launch_app(app.main_activity, launcher_intent=True):
        print("LOGIN-GO-HOME: ⚠️ launch_app 重试拉回失败")
    time.sleep(2)
    if wait_app_foreground(timeout=8, interval=1.0):
        print("LOGIN-GO-HOME OK: 重试后已跳回主页并确认前台稳定")
        return True

    print("LOGIN-GO-HOME: ❌ 重试后焦点仍未稳定停留在 MainActivity，App 可能退到后台")
    return False
def check_login_state():
    """检查当前是否在首页（登录态确认）。
    不在前台时先尝试拉起 App 再复检一次。
    """
    app = get_app_descriptor()
    focus = _current_focus_window()
    ok, detail = app.describe_foreground_state(focus)
    if ok:
        return True, detail

    print(f"CHECK-LOGIN-STATE: App 不在前台（焦点窗口: {focus}），尝试自动拉起后复检...")
    ops = get_platform_ops()
    ops.launch_app(app.main_activity)
    time.sleep(3)
    focus = _current_focus_window()
    ok, detail = app.describe_foreground_state(focus, auto_relaunched=True)
    if ok:
        print("CHECK-LOGIN-STATE: ✅ 自动拉起后 App 已在前台")
    return ok, detail
