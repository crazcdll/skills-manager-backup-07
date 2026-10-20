"""DeviceLifecycle：设备获取与安装的生命周期契约。"""
from abc import ABC, abstractmethod
from devices.interfaces.platform_ops import PlatformOps


class DeviceLifecycle(ABC):
    """设备生命周期抽象基类。

    关注"怎么获取设备、怎么安装 App"——云模拟器走 yooz API create，
    本地真机只做探测（设备已物理连接）。

    实例化时可不持有状态，所有方法接受必要的参数（user_mis 等）。
    业务模块通过 context.get_device_lifecycle() 获取实例，不直接构造。

    注：**不提供"释放/销毁"能力**——设备复用优先；占用态由
    `resources/device_pool/` 的租约表达（只登记/清理租约，不销毁实例）。
    """

    @property
    @abstractmethod
    def device_type(self) -> str:
        """设备类型标识：sandbox/cloud_device/local。"""
        ...

    @abstractmethod
    def acquire(self, user_mis: str) -> dict:
        """获取设备实例。

        本地真机场景下，acquire() 自行完成设备探测（唯一在线设备校验）和
        前置可用性校验（如屏幕可交互），调用方无需感知探测细节。

        Args:
            user_mis: 用户 MIS（用于设备资源归属，本地真机场景不使用）
        Returns:
            dict: 至少包含 serial（设备地址），可选 sandbox_id 等
        Raises:
            LocalDeviceProbeError: 本地真机探测失败（可现场修复）
            Exception: 其余获取失败
        """
        ...

    @property
    def uses_local_artifact(self) -> bool:
        """安装通道是否使用**本地制品**（决定 L1 制品缓存是否适用）。

        默认 True：安装前先把制品落到 Skill 级缓存（`shared/artifact_cache.py`，
        跨 run / 跨子 Agent 共享）再投给设备——鸿蒙模拟器（L1+L2）、Android/iOS 本地
        与云真机都如此。
        置 False 的通道例如 sandbox（yooz 云模拟器）：制品由 yooz-server 自己下载并
        投递到实例，字节不经本地（见 `devices/lifecycle/sandbox.py`），因此 L1 缓存对它
        不适用——声明出来，安装日志/报告就不会出现“未命中，安装时下载一次”这种与实际
        不符的描述。判定时与 `PlatformOps.uses_local_artifact`（平台形态层面，如
        HarmonyOS 真机走企业安装页）**取与**：任一为 False 即视为不经本地制品。
        """
        return True

    @abstractmethod
    def install_app(self, ops: PlatformOps, artifact_url: str,
                    device_id: str = None) -> bool:
        """安装应用到设备（设备特定安装机制）。

        云模拟器通过 yooz proxy API 远程安装，
        本地真机通过 PlatformOps.install_app() 直接安装；
        `uses_local_artifact` 声明本通道是否属于“本地制品 → 设备”。

        Args:
            ops: PlatformOps 实例
            artifact_url: 应用文件 URL 或本地路径
            device_id: 设备特定标识（sandbox: sandbox_id，local: 忽略）
        Returns:
            bool: 安装命令是否成功执行
        """
        ...

    @abstractmethod
    def query_user_devices(self, user_mis: str) -> list:
        """查询用户名下的设备列表。

        Returns:
            list[dict]: 每项至少包含 sandboxId 和 adbAddress
        """
        ...
