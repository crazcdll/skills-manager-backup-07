"""PlatformOps：设备交互能力契约（点击/滑动/截图/视图树/包管理/平台专属能力）。"""
from abc import ABC, abstractmethod
import subprocess


class PlatformOps(ABC):
    """平台交互抽象基类。

    实例化时传入 device_serial，所有方法内部使用该 serial。
    业务模块通过 context.get_platform_ops() 获取实例，不直接构造。
    """

    @property
    @abstractmethod
    def serial(self) -> str:
        """当前设备标识（设备 serial/地址，session-based 模型下仅用于日志和 ADB 连接）。"""
        ...

    # ═══════════════════════════════════════════════════════════
    # 感知
    # ═══════════════════════════════════════════════════════════

    @abstractmethod
    def inspect_tree(self, output_path: str, *, timeout: int = 30) -> subprocess.CompletedProcess:
        """采集 Native 视图树 JSON，输出到指定文件路径。"""
        ...

    # ═══════════════════════════════════════════════════════════
    # 交互原语
    # ═══════════════════════════════════════════════════════════

    @abstractmethod
    def tap(self, x: int, y: int) -> bool:
        """坐标点击。"""
        ...

    @abstractmethod
    def swipe(self, from_x: int, from_y: int, to_x: int, to_y: int,
              duration_ms: int = 500) -> bool:
        """滑动手势。"""
        ...

    @abstractmethod
    def input_text(self, text: str) -> bool:
        """输入文本（基础输入，不含 CJK 降级逻辑）。"""
        ...

    @abstractmethod
    def press_back(self) -> bool:
        """按下返回键。"""
        ...

    @abstractmethod
    def press_home(self) -> bool:
        """按下 Home 键。"""
        ...

    @abstractmethod
    def screenshot(self, path: str) -> bool:
        """截图保存到指定路径。"""
        ...

    # ═══════════════════════════════════════════════════════════
    # App 管理
    # ═══════════════════════════════════════════════════════════

    @abstractmethod
    def launch_app(self, component: str, *, launcher_intent: bool = False) -> bool:
        """启动 App 到指定 Activity。

        Args:
            component: 组件名，格式 "pkg/activity"
            launcher_intent: True 使用 LAUNCHER intent（模拟从桌面图标启动），
                            False 直接 am start -n component。
        """
        ...

    @abstractmethod
    def force_stop(self, package: str) -> bool:
        """强制停止 App。"""
        ...

    @abstractmethod
    def launch_scheme(self, scheme_url: str) -> bool:
        """通过 am start 推送 scheme URL。"""
        ...

    @abstractmethod
    def open_url(self, url: str) -> bool:
        """通过 imeituan CLI device open-url 打开 URL。"""
        ...

    # ═══════════════════════════════════════════════════════════
    # App 生命周期管理
    # ═══════════════════════════════════════════════════════════

    @abstractmethod
    def is_package_installed(self, package: str) -> bool:
        """检查指定包名是否已安装（精确匹配，非前缀模糊）。"""
        ...

    @abstractmethod
    def get_installed_version(self, package: str) -> dict:
        """获取已安装应用的版本信息。

        Returns:
            dict: {"installed": bool, "versionName": str|None, "versionCode": str|None}
        """
        ...

    @abstractmethod
    def uninstall_app(self, package: str) -> bool:
        """卸载指定包。语义为「确保设备上不存在该包」，成功返回 True。

        包本就未安装时视为空操作，直接返回 True。
        """
        ...

    @abstractmethod
    def install_app(self, app_path: str, timeout: int = 300) -> bool:
        """安装应用到设备。

        Args:
            app_path: 安装制品定位符，随平台实现而异（Android: 本地 .apk 文件
                路径或远程 URL；HarmonyOS: 必须是 HPX 生成的企业安装页 HTML
                URL，不支持本地 .hap 路径——企业签名包 `hdc install` 易因签名
                校验失败，只有系统浏览器安装页触发的系统级安装器才稳定，详见
                platform/harmony/ops.py::HarmonyOps.install_app）。
            timeout: 安装超时秒数
        Returns:
            bool: 安装成功返回 True。

        Raises:
            Exception: 安装失败时应抛出异常携带失败原因，不能静默返回 False
                ——底层命令 returncode 不总是可靠（真机实测可能 returncode=0
                但失败原因只体现在 stdout/stderr），各平台实现须额外解析输出
                内容/UI 状态；调用方统一按"抛异常=失败"处理重试与报错收集。
        """
        ...

    # ═══════════════════════════════════════════════════════════
    # 环境配置
    # ═══════════════════════════════════════════════════════════

    @abstractmethod
    def setup_keyboard(self) -> bool:
        """配置测试输入法（Android: ADBKeyboard, 其他平台: 空操作返回 True）。"""
        ...

    # ═══════════════════════════════════════════════════════════
    # 状态查询
    # ═══════════════════════════════════════════════════════════

    @abstractmethod
    def check_foreground(self) -> str:
        """读取当前前台/焦点窗口标识，具体格式随平台实现而异（Android:
        `dumpsys window` 的 mCurrentFocus 行，小写；HarmonyOS: 见
        platform/harmony/ops.py::HarmonyOps.check_foreground）。调用方
        应只做 `package in fg_line` 子串匹配，不应假设具体格式。

        Returns:
            str: 前台窗口标识文本；查询失败或未探测到返回空串。
        """
        ...

    @abstractmethod
    def screen_size(self) -> tuple:
        """获取设备屏幕分辨率。

        Returns:
            tuple: (width, height)
        """
        ...

    def viewport_insets(self) -> dict:
        """获取视口安全区域 insets：各平台系统级遮挡物（状态栏/导航栏/刘海等）。

        各平台应尽量从系统 API 获取真实值（如 Android dumpsys window），
        无法获取时返回空 dict（ScreenLayout 兜底使用类属性的默认值）。
        未来横向滚动场景需提供 left/right。

        Returns:
            dict: {"top": int, "bottom": int, "left": int, "right": int}
                  各方向遮挡区域像素数，缺失的方向由 ScreenLayout 兜底。
        """
        return {}

    @abstractmethod
    def device_alive(self) -> bool:
        """轻量级设备连通性检查。"""
        ...

    @abstractmethod
    def screen_state(self) -> str:
        """查询设备当前电源/屏幕状态（原始状态值，用于日志与诊断）。

        本地真机场景专用：设备物理熄屏后 adb/hdc shell 通道仍在线
        （device_alive 返回 True），但 tap/inspect-tree 等依赖"当前可见
        UI 层"的操作会静默转向锁屏/桌面窗口，表现为"找不到预期文案"的
        业务失败而非清晰的环境异常，因此需要单独探测屏幕状态。

        Returns:
            str: 归一化状态值。取值集合两平台不同（Android: AWAKE/SLEEP/
                 DOZE/DREAMING；HarmonyOS: AWAKE/DIM/FREEZE/INACTIVE/
                 STAND_BY/DOZE/SLEEP/HIBERNATE/SHUTDOWN），查询/解析失败时
                 返回 "UNKNOWN"（不抛异常，调用方不能等同于"熄屏"或"正常"，
                 避免瞬时抖动导致自动化被误终止）。
        """
        ...

    @abstractmethod
    def is_screen_interactive(self) -> bool:
        """判断当前屏幕是否处于可交互状态（未熄屏/未待机/未锁屏保护态）。

        是 screen_state() 之上的语义封装：上层调用方只需要"能不能继续做
        UI 自动化"这个布尔结论，不需要感知两平台完全不同的状态机差异。

        screen_state() 返回 "UNKNOWN" 时视为可交互（保守放行，避免探测
        本身的偶发失败误判为熄屏而终止自动化）。
        """
        ...

    @abstractmethod
    def pidof(self, package: str) -> str:
        """查询进程 PID。

        Returns:
            str: PID 字符串；进程不存在返回空串。
        """
        ...

    # ═══════════════════════════════════════════════════════════
    # 文本输入语义操作（平台无关，各平台自行实现 keycode 细节）
    # ═══════════════════════════════════════════════════════════

    @abstractmethod
    def clear_text(self, x: int, y: int, max_del: int = 20) -> bool:
        """清空输入框：tap 聚焦 → 移到末尾 → 批量删除。

        各平台实现自己的按键序列，调用方无需知悉 keycode 细节。

        Args:
            x: 输入框 tap 坐标 x
            y: 输入框 tap 坐标 y
            max_del: 最大退格次数（默认 20）
        """
        ...

    @abstractmethod
    def supports_cjk_input(self) -> bool:
        """input_text() 是否原生支持 CJK 字符输入。

        Returns:
            True  = 直接调 input_text 即可（如鸿蒙 uitest uiInput inputText）
            False = 需要 ADBKeyboard broadcast 等外部机制辅助（如 Android）
        """
        ...

    # ═══════════════════════════════════════════════════════════
    # 结构化设备命令
    # ═══════════════════════════════════════════════════════════

    @abstractmethod
    def broadcast(self, action: str, **extras) -> bool:
        """发送 am broadcast。

        Args:
            action: broadcast action 名称（如 ADB_INPUT_TEXT）
            **extras: --es key=value 参数
        """
        ...

    @abstractmethod
    def content_call(self, uri: str, method: str, *args) -> tuple:
        """执行 content call，操作 ContentProvider。

        Args:
            uri: content provider URI
            method: 方法名（如 enable / disable / getStatus）
            *args: --arg 参数值列表
        Returns:
            (bool, str): (成功与否, 合并输出)
        """
        ...

    @abstractmethod
    def keyevent(self, *keycodes) -> bool:
        """发送 input keyevent。

        Args:
            *keycodes: KEYCODE 名称或数字（如 KEYCODE_BACK, 67）
        """
        ...

    @abstractmethod
    def get_setting(self, namespace: str, key: str) -> str:
        """读取 settings get {namespace} {key}。

        Returns:
            str: 设置值（strip 后），查询失败返回空串。
        """
        ...

    @abstractmethod
    def clear_app_data(self, package: str) -> bool:
        """清除 App 数据（移除残留登录态/缓存）。

        Args:
            package: App 包名
        Returns:
            bool: 是否成功
        """
        ...

    @abstractmethod
    def grant_permissions(self, package: str, permissions: list[str]) -> list[bool]:
        """预授予运行时权限（避免弹窗干扰）。

        Args:
            package: App 包名
            permissions: 权限列表
        Returns:
            list[bool]: 每个权限的授予结果
        """
        ...

    @property
    def default_permissions_to_grant(self) -> list[str]:
        """各平台默认需要预授予的权限列表（登录前授予，避免弹窗干扰）。
        基类返回空列表，各平台按需覆盖。
        """
        return []

    # ═══════════════════════════════════════════════════════════
    # 逃逸通道
    # ═══════════════════════════════════════════════════════════

    @abstractmethod
    def shell(self, *args) -> subprocess.CompletedProcess:
        """在设备上执行任意 shell 命令（仅用于无法归类的场景）。"""
        ...

    @abstractmethod
    def disconnect(self) -> bool:
        """断开设备连接。"""
        ...
