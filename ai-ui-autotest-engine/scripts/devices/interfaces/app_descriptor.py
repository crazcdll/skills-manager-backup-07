"""AppDescriptor：被测 App 元数据契约（包名/主 Activity/调试控件/可测性 scheme）。"""
from abc import ABC, abstractmethod


class AppDescriptor(ABC):
    """目标 App 描述符抽象基类。

    封装目标 App 的包名、Activity、Content Provider URI、Scheme 等常量，
    消除各模块中散落的硬编码 App 维度常量。

    三个正交维度：Platform（怎么交互）、Device（怎么获取/释放）、App（目标 App 是什么）。
    AppDescriptor 关注"目标 App 是什么"——包名、首页 Activity、AppMock URI、
    调试控件类名、Scheme 前缀等。

    业务模块通过 context.get_app_descriptor() 获取实例，不直接构造。

    注意：同一个 App（如美团）在不同 OS 平台上是完全独立的安装包——包名、
    Activity/Ability、调试控件类名均不同，因此 AppDescriptor
    具体实现类同时承载 app 和 platform 两个维度信息，platform 属性用于
    需要感知"当前描述符对应哪个平台"的场景（如按平台读取安装包配置）。

    设备形态 form（real/emulator）也参与"这个 App 是什么"——同一 App 在同一
    平台的不同形态上可能是**不同的安装包**（包名不同，如鸿蒙真机
    com.sankuai.hmeituan.beta vs 模拟器 com.sankuai.hmeituan），因此实例化时
    注入 form，供包名解析使用。form 由 devices/registry.py 从 device_type 派生。
    """

    def __init__(self, form: str = "real"):
        self._form = form

    @property
    def form(self) -> str:
        """设备形态：real（真机）/ emulator（模拟器），默认 real。"""
        return self._form

    @property
    def platform(self) -> str:
        """该描述符对应的操作系统平台（android/harmony），默认 android。"""
        return "android"

    @property
    @abstractmethod
    def package_name(self) -> str:
        """App 包名（如 com.sankuai.meituan）。"""
        ...

    @property
    @abstractmethod
    def main_activity_class(self) -> str:
        """首页 Activity 类路径（不含包名前缀）。"""
        ...

    @property
    def main_activity(self) -> str:
        """首页完整组件名（pkg/activity_class），用于 am start -n。"""
        return f"{self.package_name}/{self.main_activity_class}"

    @property
    @abstractmethod
    def appmock_content_uri(self) -> str:
        """AppMock content provider URI（如 content://pkg.appmock/mock）。"""
        ...

    @property
    @abstractmethod
    def debug_overlay_prefixes(self) -> tuple:
        """inspect-tree 噪声过滤的调试控件类名前缀元组。"""
        ...

    @property
    @abstractmethod
    def scheme_prefix(self) -> str:
        """App scheme URL 前缀（如 imeituan://www.meituan.com）。"""
        ...

    @property
    def testability_scheme_prefix(self) -> str:
        """可测性 debugconfig scheme 完整前缀（含 path，不含 payload）。"""
        return f"{self.scheme_prefix}/travel/debugconfig?encode="

    @property
    def uninspectable_activities(self) -> tuple:
        """不支持 imeituan inspect-tree 的 Activity 标识列表（小写），用于降级 uiautomator。"""
        return ()

    @property
    def page_specs(self) -> dict:
        """页面描述表（`{页面键: PageSpec}`）；默认空 = 该 App/平台未声明。

        常见页面键见 `devices/interfaces/page_spec.py::PAGE_LOGIN / PAGE_LOGIN_CODE`。
        这里是"页面长什么样 / 控件怎么找 / 从哪些入口到达"的**唯一来源**：
        登录等业务层只按**语义名**取控件，不出现资源 id / 文案 / 平台判断 ——
        新增平台（如 iOS）= 在自己描述符里补一份数据，业务流程零改动。
        """
        return {}

    def is_foreground(self, focus: str) -> bool:
        """按平台语义判定 focus 窗口字符串是否代表当前 App 已在前台。

        默认实现（Android 语义）：MainActivity 是可精确识别的独立窗口标识，
        用 "mainactivity" 关键词判断能区分"在首页"与"在其他 Activity"。
        HarmonyOS 等单 Ability 多路由架构无此颗粒度，需要覆写为包名匹配
        （见 devices/harmony/apps/meituan.py）。
        """
        return "mainactivity" in focus.lower()

    def foreground_confirmed_hint(self) -> str:
        """前台判定为 True 时附加的场景说明文案（平台颗粒度差异提示）。

        默认（Android）判定颗粒度可精确到 MainActivity，无需额外说明；
        HarmonyOS 等只能判定"App 在前台"、无法区分具体页面的平台应覆写，
        提示调用方这一判定局限性，避免误以为已定位到具体页面。
        """
        return ""

    def describe_foreground_state(self, focus: str, *, auto_relaunched: bool = False) -> tuple:
        """判定前台状态并给出人类可读描述，供登录态确认等场景统一复用。

        取代过去在登录原语模块（现 provisioning/setup/ 下的 app_lifecycle 等）里按平台重复展开的
        if/else 分支——前台判定规则（is_foreground）与其文案表述是同一个
        平台差异点的两面，收口到同一处，新增平台不需要再去业务模块里找
        所有判断该平台的地方。

        Args:
            focus: 当前焦点窗口字符串（通常来自 dumpsys window / hidumper）
            auto_relaunched: 是否是"检测到不在前台后自动拉起"这次复检，
                仅影响返回文案措辞，不影响判定逻辑
        Returns:
            (is_foreground: bool, detail: str)
        """
        if not self.is_foreground(focus):
            action = "已尝试自动拉起仍未生效" if auto_relaunched else "请求判定"
            return False, f"App 不在前台（焦点窗口: {focus}，{action}）"
        prefix = "已自动拉起并确认" if auto_relaunched else "已"
        hint = self.foreground_confirmed_hint()
        suffix = f"（{hint}）" if hint else ""
        return True, f"{prefix}在前台，登录态确认{suffix}"
