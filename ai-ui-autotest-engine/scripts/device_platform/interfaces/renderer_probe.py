"""RendererProbe：渲染层感知探针契约（native / webview 等）。"""
from abc import ABC, abstractmethod


class RendererProbe(ABC):
    """渲染层感知探针抽象基类。

    第四个正交维度：内容由谁渲染。

    native 视图树只覆盖 Android View 体系。
    其内部 DOM 由浏览器内核绘制，不向 View 系统注册子节点。因此"文本是否存在"
    这个问题在不同渲染层需要不同的采集手段。

    上层（断言/定位/输入校验）只依赖本接口，不感知内容来自 native 还是 H5。
    """

    @property
    @abstractmethod
    def probe_name(self) -> str:
        """探针名称标识，用于日志与证据标注。"""
        ...

    @abstractmethod
    def available(self) -> bool:
        """当前页面下本探针是否可用。

        不可用时 Probe 链跳过该探针，不产生副作用也不报错。
        """
        ...

    @abstractmethod
    def find_text(self, text: str) -> bool:
        """文本存在性判断。"""
        ...

    @abstractmethod
    def find_center(self, text: str) -> tuple:
        """文本 → 可点击元素中心坐标。

        Returns:
            tuple: (cx, cy) 设备物理像素坐标；未命中返回 None。

实现约定：返回值必须是设备物理坐标，可直接交给 PlatformOps.tap。
        """
        ...

    @abstractmethod
    def list_texts(self) -> list:
        """列出当前渲染层的全部可见文本，用于诊断与候选提示。"""
        ...

    def close(self) -> None:
        """释放探针持有的资源（连接、端口转发等）。默认空操作。"""
        return None
