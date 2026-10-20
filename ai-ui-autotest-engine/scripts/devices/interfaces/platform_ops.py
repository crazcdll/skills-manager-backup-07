"""PlatformOps：设备交互能力契约（点击/滑动/截图/视图树/包管理/平台专属能力）。"""
from abc import ABC, abstractmethod
import subprocess

from devices.interfaces.artifact_spec import BuildKind


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
    def inspect_tree(self, output_path: str, *, timeout: int = 30,
                     whole_screen: bool = False) -> subprocess.CompletedProcess:
        """采集 Native 视图树 JSON，输出到指定文件路径。

        `whole_screen=False`（默认）：只采目标 App 窗口的节点（元素定位 / 文案断言用，
        避免系统窗口噪音）。
        `whole_screen=True`：采**全窗口合并**节点（遮挡 / 弹窗检测用）——系统权限弹窗
        （通知 / 定位）属**系统进程窗口**，按 App 过滤的采集里完全看不到它（鸿蒙实测：
        带 `-b <bundle>` 的 dumpLayout 为空、不带才有弹窗节点）。
        """
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

    def installed_build_kind(self, package: str) -> BuildKind:
        """已装包的构建类型（可测性/正式/不可确认）。

        默认实现按**鸿蒙口径**读取 `get_installed_version()` 的可选键
        `provisionType` / `debug`（不同系统版本 `bm dump` 的字段位置与命名有差异，
        PlatformOps 侧已归一为这两个键）：`debug is True` 或
        `provisionType in ("debug", "test")` → TESTABILITY；`debug is False` 或
        `provisionType in ("release", "os_integration")` → RELEASE；两者都拿不到
        → UNKNOWN（不可确认）。

        实测口径（鸿蒙池内设备）：`appProvisionType=debug` 即**可测性包**；布尔
        `debug` 表示**可调试性**（实测会与 provisionType 不一致），因此以
        provisionType 为准。

        平台差异：HarmonyOS 直接复用本默认实现（`HarmonyOps` 不再覆写）；
        Android 的 `get_installed_version()` 只返回 versionName/versionCode，
        无法可靠判定构建类型 → 由 `AndroidOps` 覆写为 UNKNOWN
        （见 devices/android/ops.py）。
        """
        installed = self.get_installed_version(package)
        if installed.get("debug") is True:
            return BuildKind.TESTABILITY
        provision = str(installed.get("provisionType") or "").strip().lower()
        if provision in ("debug", "test"):
            return BuildKind.TESTABILITY
        if installed.get("debug") is False or provision in ("release", "os_integration"):
            return BuildKind.RELEASE
        return BuildKind.UNKNOWN

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
            app_path: 安装制品定位符，随平台/设备形态而异：
                - Android：本地 .apk 路径或远程 URL；
                - HarmonyOS 真机/云真机（form=real）：HPX 企业安装页 HTML URL
                  （企业签名包 `hdc install` 易因签名失败，须系统浏览器安装页触发）；
                - HarmonyOS 模拟器（form=emulator）：非 enterprise 的**可测性(debug)
                  HAP** 直链（模拟器忽略签名，落到设备侧缓存后 `bm install -p`；
                  release 包缺 MSI 能力，登录会静默卡 Loading）。
                详见 devices/harmony/ops.py::HarmonyOps.install_app。

        **远程 URL 必经 L1 制品缓存**：实现先经 `shared/artifact_cache.resolve()` 解析为
        本地文件（跨 run / 跨子 Agent 共享，命中即免重下；并发 install 只下载一次），
        再交给各平台的安装通道；本地路径（随仓制品 / 预设名）原样透传。
        不走本地制品的通道必须声明 `uses_local_artifact=False`（如 sandbox、
        HarmonyOS form=real），使安装日志/报告不出现与实际不符的缓存描述。
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
        devices/harmony/ops.py::HarmonyOps.check_foreground）。调用方
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

    @property
    def uses_local_artifact(self) -> bool:
        """本平台/形态的安装通道是否使用**本地制品**（决定 L1 制品缓存是否适用）。

        默认 True：远程 URL 先落 L1 缓存（`shared/artifact_cache.py`）再投给设备。
        置 False 的形态声明的含义是“制品不经本地”——例如 HarmonyOS form=real 走 HPX
        企业安装页，下载由设备系统安装器完成（见 devices/harmony/ops.py 覆盖）。
        """
        return True

    @property
    def can_verify_appmock_state(self) -> bool:
        """设备端 AppMock 开关状态是否可程序化确认（平台差异的唯一声明点）。

        默认 True = 可确认：
          · Android：通过 AppMock ContentProvider（`content call getStatus`）可确认
          · HarmonyOS：无状态查询通道 ⇒ 恒不可确认（见 HarmonyOps 覆盖）

        影响点：`provisioning/setup/login/steps.py::EnableAppMock` 的
        「清数据 + 预授权」执行落点 —— 不可确认的平台走不到"已确认"分支，
        因此必须在该分支内完成数据/权限准备，否则 clear+grant 永不执行。
        """
        return True

    # ═══════════════════════════════════════════════════════════
    # 设备临时目录清理（共享设备的历史遗留）
    # ═══════════════════════════════════════════════════════════

    # 只清理"传输/安装中间产物"这类可再生成的垃圾：hap/apk/分包/日志/dump。
    # 刻意不含未知后缀，避免误删别人的工作产物。
    DEFAULT_TEMP_ARTIFACT_PATTERNS = (
        "*.hap", "*.apk", "*.hsp", "*.part", "part.*",
        "*.log", "*.json", "*.jpeg", "*.jpg", "*.png",
    )

    # 本 Skill 自己写入设备侧临时目录的文件名前缀（如视图树 dump），清理时跳过。
    PROTECTED_NAME_PREFIXES = ("ai_ui_autotest_engine",)

    @property
    def device_temp_keep_paths(self) -> tuple:
        """清理设备临时目录时必须保留的路径（如本 Skill 自己的安装包缓存目录）。"""
        return ()

    def clean_device_temp_artifacts(self, *, path: str = "/data/local/tmp",
                                    patterns: tuple = None,
                                    include_dirs: bool = True,
                                    dry_run: bool = False) -> dict:
        """清理设备临时目录里历次占用遗留的产物：白名单文件 + 非保留子目录。

        为什么默认就清（不做容量判断）：云模拟器/云手机是**共享设备**，实例归还后
        `/data/local/tmp` 里的传输/安装产物与日志目录（`hilog_tmp_*`、`debugserver`
        等）仍保留，历次占用会持续累积直到撑满设备（实测 10G 实例被塞到 100%，
        安装直接失败）。共享设备被本会话独占、遗留内容都是历次已释放会话的产物，
        因此"占用后默认清一次"比"装不下再补救"更可靠。

        与"是否已安装"无关：App 的安装路径由系统决定（`hdc install` / `bm install`
        均不能指定安装目录），目录里有 hap ≠ 已安装；版本判定必须走 `bm dump`
        （见 devices/toolchain/app_installer.check_version）。

        保留边界（安全且不可协商）：
          · `device_temp_keep_paths`（本 Skill 的设备侧安装包缓存 = **预热资产**）
            及其下全部内容始终保留——删掉它等于把预热省下的重传又丢回去；
          · `PROTECTED_NAME_PREFIXES` 前缀的本 Skill 自有文件保留。
        """
        pats = tuple(patterns or self.DEFAULT_TEMP_ARTIFACT_PATTERNS)
        keep = tuple(self.device_temp_keep_paths)
        base = path.rstrip("/") + "/"

        def _is_kept(p: str) -> bool:
            return any(p == k or p.startswith(k.rstrip("/") + "/") for k in keep)

        # ① 文件：白名单后缀，不递归
        find_args = ["find", path, "-maxdepth", "1", "-type", "f", "("]
        for i, p in enumerate(pats):
            if i:
                find_args.append("-o")
            find_args += ["-name", p]
        find_args.append(")")
        found = self.shell(*find_args).stdout or ""
        candidates = [line.strip() for line in found.splitlines()
                      if line.strip().startswith(base)]
        files = [p for p in candidates if not _is_kept(p)
                 and not p[len(base):].startswith(self.PROTECTED_NAME_PREFIXES)]

        # ② 目录：/data/local/tmp 下的子目录。非保留的（历次占用遗留）待删；
        #    保留的（本 Skill 设备侧安装包缓存 = 预热资产）只统计、不删。
        dirs, kept_dirs = [], []
        if include_dirs:
            out = self.shell("find", path, "-maxdepth", "1", "-mindepth", "1",
                             "-type", "d").stdout or ""
            for line in out.splitlines():
                d = line.strip()
                if not d.startswith(base):
                    continue
                (kept_dirs if _is_kept(d) else dirs).append(d)

        sizes = {}
        for p in files:
            out = (self.shell("stat", "-c", "%s", p).stdout or "").strip()
            if out.isdigit():
                sizes[p] = int(out)

        result = {
            "path": path,
            "dryRun": bool(dry_run),
            "patterns": list(pats),
            "keptPaths": [p for p in candidates if _is_kept(p)] + kept_dirs,
            "matched": files + dirs,
            "files": files,
            "dirs": dirs,
            "bytes": sum(sizes.values()) or None,
        }
        if dry_run or not (files or dirs):
            return result
        deleted, deleted_dirs = [], []
        for p in dirs:
            if self.shell("rm", "-rf", p).returncode == 0:
                deleted_dirs.append(p)
        for p in files:
            if self.shell("rm", "-rf", p).returncode == 0:
                deleted.append(p)
        result["deleted"] = deleted
        result["deletedDirs"] = deleted_dirs
        return result

    # ═══════════════════════════════════════════════════════════
    # 共享设备清理：卸载其它用例遗留的大 App
    # ═══════════════════════════════════════════════════════════

    # 「其它被测 App」的包名前缀。这些包体积大（数百 MB ~ 1G+）且与当前用例无关，
    # 却是共享实例上最占盘的东西（实测池内实例残留 com.sankuai.dianping）。
    # 只匹配这些前缀 → 系统包（com.huawei.* / com.android.* / ohos.* 等）永不入列。
    CLEANABLE_APP_PREFIXES = ("com.sankuai.", "com.dianping.", "com.meituan.")

    def installed_packages(self) -> list:
        """列出设备上已安装的包名（精确包名），供批量清理判定。

        默认返回空列表 = 该平台不支持枚举（跳过 App 清理，best-effort）；
        支持枚举的平台自行覆盖。`is_package_installed` 应基于本方法实现，
        避免"列表"逻辑散落多处。
        """
        return []

    def clean_device_unused_apps(self, *, prefixes: tuple = None,
                                 exclude_packages: tuple = (),
                                 keep_testability: bool = True,
                                 dry_run: bool = False) -> dict:
        """卸载共享设备上**与本用例无关**的遗留 App；可测性构建一律保留。

        为什么需要：云模拟器/云手机是**共享实例**，历次占用会留下大体量 App，
        与当前用例无关却把磁盘吃掉（实测 19G 实例上就装着 com.sankuai.dianping）。

        职责边界（本能力只管"清理"，不管"目标包该不该留"）：
          本方法只负责清理与本用例**无关**的历史遗留；**目标包的去留由安装链路
          决定**（`app_installer.check_version` → `decide_app_action` 判"复用/安装/
          重装"）。调用方通过 `exclude_packages` 把目标包排除在卸载候选之外——
          排除的包**永不出现在卸载候选里**（直接跳过，不计入 targets），
          从根本上避免"清理误伤目标包 → 每轮重装"这一历史根因。

        卸载口径（`exclude_packages` 之外、命中 `prefixes` 的包）：
          · **可测性(debug/test)构建 → 保留**：那是别的用例已下发的大包（如可测性点评，
            重装要重下 1G+），也是本用例"可复用时直接用"的前提；构建类型由
            `installed_build_kind()` 判定（鸿蒙据 `bm dump` 的 provisionType/debug；
            Android 无法确认 → UNKNOWN）；
          · **非可测性（正式/release、或构建类型不可确认）→ 卸载**：这类包对测试无用
            （鸿蒙 release 包缺 MSI/pillowConfig handler，登录会静默卡 Loading），
            却最占空间；
          · 系统包（com.huawei.* / com.android.* 等）不在 `prefixes` 内 → 永不触碰。

        Returns:
            dict: {"installedCount", "candidates", "excluded", "keptTestability",
                   "targets", "dryRun"[, "uninstalled"]}
        """
        pats = tuple(prefixes or self.CLEANABLE_APP_PREFIXES)
        excluded = set(exclude_packages or ())
        installed = self.installed_packages() or []
        candidates = [p for p in installed
                      if any(p.startswith(x) for x in pats) and p not in excluded]
        targets, kept_testability = [], []
        for p in candidates:
            if keep_testability and self.installed_build_kind(p) is BuildKind.TESTABILITY:
                kept_testability.append(p)
            else:
                targets.append(p)
        result = {"installedCount": len(installed), "candidates": candidates,
                  "excluded": sorted(excluded),
                  "keptTestability": kept_testability,
                  "targets": targets, "dryRun": bool(dry_run)}
        if dry_run or not targets:
            return result
        result["uninstalled"] = [p for p in targets if self.uninstall_app(p)]
        return result

    def stop_running_apps(self, *, extra_packages: tuple = (), prefixes: tuple = None,
                          dry_run: bool = False) -> dict:
        """强制停止设备上残留运行中的被测 App 进程（不碰系统进程）。

        为什么：共享实例上，上一个会话退出后被测 App 进程可能仍在后台跑（实测
        10027 上 `com.sankuai.hmeituan` 常驻 233M），把设备起始状态带脏；而本次流程
        稍后本就会重新启动 App（首启收敛 / 前台校验），所以"先归零"安全且幂等。

        "关哪些"**由运行时算出、不维护 App 名单**：
            `installed_packages()` ∩ `prefixes`（默认 `CLEANABLE_APP_PREFIXES`）
            ∪ `extra_packages`（如当前目标包）
            中**确实在运行**（`pidof` 非空）的那些。
        平台差异：鸿蒙 `aa force-stop <bundle>` 按包精确停；Android 的 `force_stop`
        走 session 级 `imeituan device app-stop`（等价于停当前目标包）。
        """
        pats = tuple(prefixes or self.CLEANABLE_APP_PREFIXES)
        installed = self.installed_packages() or []
        candidates = [p for p in installed if any(p.startswith(x) for x in pats)]
        for p in extra_packages or ():
            if p and p not in candidates:
                candidates.append(p)
        running = [p for p in candidates if str(self.pidof(p) or "").strip()]
        result = {"candidates": candidates, "running": running, "dryRun": bool(dry_run)}
        if dry_run or not running:
            return result
        result["stopped"] = [p for p in running if self.force_stop(p)]
        return result

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
