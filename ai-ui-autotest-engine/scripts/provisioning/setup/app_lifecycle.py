"""App 生命周期原语：前台检测、等待前台、冷重启、环境切换后重启。

环境澄清（前台就绪 + 遮挡弹窗消除）**不在本模块**——已收口为唯一入口：
`provisioning/setup/environment_reconciler.reconcile_environment()`。
本模块只保留"设备态变更"（冷重启）与前台判定原语，避免出现第二个澄清入口
（守卫规则 22 锁定：`dismiss_popups` 只允许执行器与唯一入口引用）。
"""
import time
from shared.context import get_platform_ops, get_app_descriptor

# 唯一澄清入口（同层；反向引用只在函数内延迟导入，不构成模块级环）
from provisioning.setup.environment_reconciler import reconcile_environment


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
    """清数据后首启的弹窗澄清（隐私协议等），独立于 wait_app_foreground。

    清数据后首次启动会弹隐私协议，阻塞后续 debugconfig/登录页操作；本函数把澄清与
    前台检测解耦：即使 wait_app_foreground 因 inspect-tree 不支持而超时，仍会尝试澄清。

    实现委托唯一入口 `environment_reconciler.reconcile_environment`（本模块不再自带
    第二套澄清实现）；等待窗口 12s 用于覆盖"首启弹窗渲染出来"的时间。

    Returns:
        bool: **契约语义（勿改）** —— 除采集/点击过程抛异常外**恒返回 True**。
              调用方 `_cold_restart_app` 据此决定"再冷重启一次让同意状态生效"；
              改这里会改变冷重启次数（规则 15 以基线锁定重启点，只增不减）。
    """
    print("COLD-RESTART: 消除弹窗（隐私协议等）...")
    vr = reconcile_environment(label="COLD-RESTART", wait_for_popup_ms=12000)
    return vr is not None
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
            # 能力闸（唯一判定点）：预授权能力实测非 available（典型：鸿蒙 `atm` 无 `perm`
            # 子命令）→ 不发起注定失败的设备命令，直接走弹窗澄清降级。
            # 用 `state_of` 而非平台分支：平台差异收敛在能力表（capabilities 模块约定），
            # 同时满足规则 14（登录层禁平台/设备类型分支）。
            from shared.capabilities import CAP_RUNTIME_GRANT, CapabilityState, state_of

            if state_of(CAP_RUNTIME_GRANT) is not CapabilityState.AVAILABLE:
                print("COLD-RESTART: ⚠️ 运行时权限预授权不可用（能力实测降级）"
                      "→ 由弹窗澄清降级")
            else:
                results = ops.grant_permissions(app.package_name, _perms)
                granted = [perm for perm, ok in zip(_perms, results) if ok]
                for perm in granted:
                    print(f"COLD-RESTART: ✅ 已授予权限: {perm.split('.')[-1]}")
                if len(granted) == len(_perms):
                    print("COLD-RESTART: ✅ 运行时权限已全部预授予")
                else:
                    # 不把「已下发」当「已达成」：能力位可用时个别权限仍可能失败，
                    # 此时如实说明并由**弹窗澄清**降级，而不是打“已预授予”（假成功会误导排查）。
                    print(f"COLD-RESTART: ⚠️ 运行时权限预授予 {len(granted)}/{len(_perms)}"
                          "（平台不支持或失败 → 由弹窗澄清降级）")

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
        # 如果成功澄清了弹窗（返回 False 仅表示澄清过程异常），需要再次冷重启使"同意"生效
        if _dismiss_privacy_popup():
            print("COLD-RESTART: 隐私协议已同意，冷重启使状态生效...")
            ops.force_stop(app.package_name)
            time.sleep(1)
            ops.launch_app(app.main_activity)
            wait_app_foreground(timeout=timeout)
            # 自产自清：这次启动本身也可能拉起一次性系统弹窗（通知/定位权限），
            # 不澄清它会留在屏上挡住后续的登录判定与取证截图。
            reconcile_environment(label="COLD-RESTART")

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
