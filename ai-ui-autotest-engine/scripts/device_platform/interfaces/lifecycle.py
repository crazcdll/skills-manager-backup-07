"""DeviceLifecycle：设备获取、安装、释放的生命周期契约。"""
from abc import ABC, abstractmethod
from device_platform.interfaces.platform_ops import PlatformOps


class DeviceLifecycle(ABC):
    """设备生命周期抽象基类。

    关注"怎么获取和释放设备"——云模拟器走 yooz API create/destroy，
    云真机走 Conan API occupy/release，本地真机不需要获取和释放。

    实例化时可不持有状态，所有方法接受必要的参数（user_mis、device_info 等）。
    业务模块通过 context.get_device_lifecycle() 获取实例，不直接构造。
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

    @abstractmethod
    def install_app(self, ops: PlatformOps, artifact_url: str,
                    device_id: str = None) -> bool:
        """安装应用到设备（设备特定安装机制）。

        云模拟器通过 yooz proxy API 远程安装，
        本地真机通过 PlatformOps.install_app() 直接安装。

        Args:
            ops: PlatformOps 实例
            artifact_url: 应用文件 URL 或本地路径
            device_id: 设备特定标识（sandbox: sandbox_id，local: 忽略）
        Returns:
            bool: 安装命令是否成功执行
        """
        ...

    @abstractmethod
    def release(self, device_info: dict) -> bool:
        """释放设备实例。

        Args:
            device_info: 设备信息（至少包含 sandbox_id 或 serial）
        Returns:
            bool: 释放是否成功
        """
        ...

    @abstractmethod
    def query_user_devices(self, user_mis: str) -> list:
        """查询用户名下的设备列表。

        Returns:
            list[dict]: 每项至少包含 sandboxId 和 adbAddress
        """
        ...

    @abstractmethod
    def cleanup_user_devices(self, user_mis: str) -> dict:
        """清理用户名下的所有设备。

        Returns:
            dict: {released: list, errors: list}
        """
        ...
