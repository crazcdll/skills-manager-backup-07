# platform/lifecycle package —— 全部 DeviceLifecycle 实现的唯一落脚点。
#
# device_type（sandbox/local/cloud_device）与 platform（android/harmony/ios）
# 是两个独立正交的维度：前者关注"怎么获取/释放设备"，与目标操作系统无关
# （sandbox 的 yooz API、local 的探测逻辑、未来 cloud_device 的 Conan API
# 本身都不含平台专属代码），因此不应像早期那样把 SandboxDeviceLifecycle
# 挂在 platform/android/lifecycle/ 下造成"仅支持 Android"的架构假象——
# 某个 device_type 目前只覆盖哪些 platform，由 platform/registry.py 的
# _DEVICE_TYPE_REGISTRY 显式声明，与本目录下具体实现放在哪个文件无关。
#
# 只有当某个 device_type 出现真正的平台专属分支逻辑时（如未来鸿蒙云真机
# 需要独立于 Conan 通用流程的 Ability 拉起方式），才把那部分差异下沉到
# platform/<platform>/lifecycle/，本目录继续保留跨平台的公共骨架。
