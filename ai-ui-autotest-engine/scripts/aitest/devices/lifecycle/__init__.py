# devices/lifecycle package —— 全部 DeviceLifecycle 实现的唯一落脚点。
#
# device_type（sandbox / local / local-emulator / cloud_device / cloud-emulator）
# 与 platform（android / harmony / ios）是两个独立正交的维度：前者关注"怎么获取
# 设备"，与目标操作系统无关（yooz 云模拟器的 API、本地设备探测、Conan 云设备 /
# 云模拟器的占用逻辑本身都不含平台专属代码），因此本目录按 device_type 一文件，
# 不按 platform 分目录。某个 device_type 覆盖哪些 platform，由 devices/registry.py
# 的 _DEVICE_TYPE_REGISTRY 显式声明，与本目录文件位置无关。
#
# 注意：本包只放"设备怎么获取"（acquire / install_app / query_user_devices）的实现；
# 设备级命令（setup / check-version / register）在 devices/device_commands.py，
# 不要混入本包。
#
# 只有当某个 device_type 出现真正的平台专属分支逻辑时，才把那部分差异下沉到
# devices/<platform>/，本目录继续保留跨平台的公共骨架。
