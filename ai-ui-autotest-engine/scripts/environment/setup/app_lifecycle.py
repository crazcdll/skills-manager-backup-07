"""App 生命周期原语：前台检测、等待前台、隐私弹窗关闭、冷重启、环境切换后重启。"""
import time
import json
import subprocess
from context import get_platform_ops, get_app_descriptor


def _current_focus_window():
    """读取当前焦点窗口标识（mCurrentFocus 行，小写）。"""
    return get_platform_ops().check_foreground()
def wait_app_foreground(timeout=10, interval=1.0):
    """等待 App 回到前台，超时尝试 LAUNCHER 拉回。

    前台判定委托给 AppDescriptor.is_foreground()，由各平台实现按自身语义
    判断（Android 用 MainActivity 关键词，HarmonyOS 用包名匹配）。
    """
    app = get_app_descriptor()
    deadline = time.time() + timeout
    while time.time() < deadline:
        if app.is_foreground(_current_focus_window()):
            return True
        time.sleep(interval)

    print("WAIT-FOREGROUND: App 不在前台，尝试 LAUNCHER 拉回...")
    ops = get_platform_ops()
    if not ops.launch_app(app.main_activity, launcher_intent=True):
        print("WAIT-FOREGROUND: ⚠️ launch_app 失败")
        return False
    time.sleep(3)
    if app.is_foreground(_current_focus_window()):
        print("WAIT-FOREGROUND: ✅ App 已拉回前台")
        return True
    print("WAIT-FOREGROUND: ⚠️ 拉回后焦点仍非 MainActivity")
    return False
def _dismiss_privacy_popup():
    """尝试消除隐私协议弹窗（独立于 wait_app_foreground）。

    清除 App 数据后首次启动会弹出隐私协议弹窗，阻塞后续 debugconfig 操作。
    此函数将弹窗消除逻辑与前台检测解耦，即使 wait_app_foreground 因
    inspect-tree 不支持（MainActivity）而超时，仍能尝试消除弹窗。

    Returns:
        bool: 是否成功消除了弹窗（True=有弹窗并消除/无弹窗，False=异常）
    """
    try:
        print("COLD-RESTART: 消除弹窗（隐私协议等）...")
        r = subprocess.run(
            ["imeituan", "control", "popup", "clear",
             "--wait-for-popup-ms", "12000",
             "--prefer-text", "同意",
             "--max-rounds", "3",
             "--format", "json"],
            capture_output=True, text=True, timeout=30
        )
        result = json.loads(r.stdout)
        data = result.get("data", {})
        final_state = data.get("finalState", "none-found")
        dismissed = data.get("dismissed", [])
        if dismissed:
            print(f"COLD-RESTART: ✅ 已消除 {len(dismissed)} 个弹窗")
            print("COLD-RESTART: 隐私协议已同意，冷重启使状态生效...")
            return True  # 调用方需据此决定是否再次冷重启
        elif final_state == "unresolvable":
            print("COLD-RESTART: ⚠️ 存在无法消除的弹窗，继续")
        else:
            print("COLD-RESTART: 无弹窗，跳过")
        return True
    except Exception as e:
        print(f"COLD-RESTART: ⚠️ popup clear 异常: {e}，继续")
        return False
def _cold_restart_app(timeout=12, clear_data=False):
    """force-stop → 冷启动 → 等待前台就绪 → 消除隐私弹窗。

    Args:
        timeout: 等待前台就绪的超时时间
        clear_data: 是否在重启前清除 App 数据（移除残留登录态，避免预填手机号不匹配）

    注意：隐私弹窗消除与 wait_app_foreground 解耦。即使前台检测超时（如
    MainActivity 不支持 inspect-tree），仍会尝试消除弹窗，避免 signin scheme
    被隐私协议页阻塞。
    """
    ops = get_platform_ops()
    app = get_app_descriptor()

    if clear_data:
        print(f"COLD-RESTART: 清除 {app.package_name} 数据（移除残留登录态）...")
        if ops.clear_app_data(app.package_name):
            print("COLD-RESTART: ✅ App 数据已清除")
        else:
            print("COLD-RESTART: ⚠️ 清除 App 数据失败，继续冷重启")
        time.sleep(1)

        # 授予运行时权限，避免弹窗干扰登录流程
        # 权限列表由各平台 ops 模块的 default_permissions_to_grant 属性定义
        _perms = ops.default_permissions_to_grant
        if _perms:
            results = ops.grant_permissions(app.package_name, _perms)
            for perm, ok in zip(_perms, results):
                if ok:
                    print(f"COLD-RESTART: ✅ 已授予权限: {perm.split('.')[-1]}")
            print("COLD-RESTART: ✅ 运行时权限已预授予")

    if not ops.force_stop(app.package_name):
        print("COLD-RESTART: ⚠️ force_stop 失败")
    time.sleep(1)
    if not ops.launch_app(app.main_activity):
        print("COLD-RESTART: ⚠️ launch_app 失败")
        return False

    # 等待前台就绪（可能因 MainActivity 不支持 inspect-tree 而超时）
    foreground_ok = wait_app_foreground(timeout=timeout)

    # ════════════════════════════════════════════════════════
    #  弹窗消除与前台检测解耦：无论前台检测是否成功都尝试消除
    # ════════════════════════════════════════════════════════
    if clear_data:
        dismissed = _dismiss_privacy_popup()
        # 如果成功消除了弹窗，需要再次冷重启使"同意"状态生效
        if dismissed and isinstance(dismissed, bool) and dismissed:
            ops.force_stop(app.package_name)
            time.sleep(1)
            ops.launch_app(app.main_activity)
            wait_app_foreground(timeout=timeout)

    return foreground_ok or True  # 弹窗已消除时允许继续（前台检测可能因 inspect-tree 限制而失败）
def restart_app_after_env_switch(label="env-switch"):
    """环境切换后冷重启 App，确保网络栈重新初始化走新环境路由。"""
    print(f"RESTART-AFTER-{label.upper()}: 环境切换后冷重启 App，网络栈重新初始化...")
    ok = _cold_restart_app()
    if ok:
        print(f"RESTART-AFTER-{label.upper()}: ✅ App 已冷启动完成")
    else:
        print(f"RESTART-AFTER-{label.upper()}: ⚠️ App 前台等待超时，继续执行")
    return ok
