"""AppMock SDK 启用原语：启用可测性 SDK 并冷重启 App。"""
import time
from mock.appmock_device import appmock_enable, check_appmock_sdk_enabled
from environment.setup.app_lifecycle import _cold_restart_app


def sdk_enable_and_restart(mis, max_attempts=3):
    """Enable AppMock SDK 并冷重启 App。信任层次：enable_ok > sdk_verified。"""
    for attempt in range(1, max_attempts + 1):
        enable_ok = appmock_enable(mis)
        sdk_verified = check_appmock_sdk_enabled()

        if enable_ok and sdk_verified:
            print(f"SDK-ENABLE: ✅ AppMock SDK 已确认启用（第 {attempt} 轮）")
            print("SDK-ENABLE: 清除 App 数据 + 重启 App 使网络栈完全走代理通道...")
            if _cold_restart_app(clear_data=True):
                print("SDK-ENABLE: ✅ App 已冷启动完成（数据已清除）")
            else:
                print("SDK-ENABLE: ⚠️ App 前台等待超时，继续执行")
            # 冷重启后 AppMock 代理可能丢失，重新启用确保生效
            # appmock_enable 现已使用 ContentProvider 直连，不依赖 Mpium
            print("SDK-ENABLE: 冷重启后重新启用 AppMock...")
            appmock_enable(mis)
            return True

        if enable_ok and not sdk_verified:
            # scheme 下发成功但无法通过设备端查询确认（如鸿蒙无状态查询通道）
            print(f"SDK-ENABLE: ⚠️ AppMock SDK 已下发启用（第 {attempt} 轮），但设备端状态无法查询确认")
            print("SDK-ENABLE: 冷重启 App 使网络栈走代理通道...")
            if _cold_restart_app():
                print("SDK-ENABLE: ✅ App 已冷启动完成")
            else:
                print("SDK-ENABLE: ⚠️ App 前台等待超时，继续执行")
            return True

        # enable_ok=False：命令明确失败。此时 sdk_verified 即使为 True 也视为假阳性，
        # 因为 enable 命令失败意味着设备端实际未启用，状态查询结果不可信。
        if attempt < max_attempts:
            hint = "（状态查询显示启用，疑似假阳性）" if sdk_verified else ""
            print(f"SDK-ENABLE: ⚠️ 第 {attempt} 轮 AppMock 启用失败{hint}，冷重启 App 后重试...")
            _cold_restart_app()
            time.sleep(2)

    print(f"SDK-ENABLE: ❌ {max_attempts} 轮尝试后 AppMock 仍无法启用，中止")
    return False
