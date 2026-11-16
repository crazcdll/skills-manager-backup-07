"""模拟定位：城市预设坐标表、别名归一，以及可下发的可测性 action。

定位是**所有"要登录"环境的统一前置步骤**（`login/steps.py::PushLocation`）：App 在
"没有任何定位"时会卡在「定位中，请稍候」，首页渲染不出「去登录」入口，登录导航直接失败
（实测）。`DEFAULT_LOCATION` 提供兜底城市，保证 plan 一定有定位。

本模块保持**纯数据 + 纯函数**：预设、别名归一、"预设 → action"映射都在这里；真正的
下发在 `PushLocation`（经通用可测性 scheme，通道选择理由见 `build_location_action`）。
"""


# 未显式配置定位时的兜底城市（保证 App 一定有定位可用）
DEFAULT_LOCATION = "beijing"

LOCATION_PRESETS = {
    "beijing": {"lat": 39.9042, "lng": 116.4074, "label": "北京"},
    "shanghai": {"lat": 31.2304, "lng": 121.4737, "label": "上海"},
    "shenzhen": {"lat": 22.5431, "lng": 114.0579, "label": "深圳"},
    "guangzhou": {"lat": 23.1291, "lng": 113.2644, "label": "广州"},
    "hangzhou": {"lat": 30.2741, "lng": 120.1551, "label": "杭州"},
    "chengdu": {"lat": 30.5728, "lng": 104.0668, "label": "成都"},
    "wuhan": {"lat": 30.5928, "lng": 114.3055, "label": "武汉"},
}
_LOCATION_ALIAS = {
    "北京": "beijing", "上海": "shanghai", "深圳": "shenzhen",
    "广州": "guangzhou", "杭州": "hangzhou", "成都": "chengdu", "武汉": "wuhan",
}


def normalize_location(loc):
    """中文别名 → 预设名；其余（含 None）原样返回。"""
    if not loc:
        return loc
    return _LOCATION_ALIAS.get(loc, loc)


def _location_action(info):
    """构造 `testability_location` action（字段与官方通道**逐字一致**）。"""
    return [{
        "index": 1,
        "type": "testability_location",
        "info": info,
        "priority": 90,
        "serial": False,
        "disabled": False,
    }]


def build_location_action(loc):
    """定位预设 → pillow `testability_location` action（下发模拟定位，`open=1`）。

    **为什么用 action 而不是 `imeituan control location`**：后者走 Pillow-**H5**
    （`pillow.sankuai.com/pillow/m/qrconfig`）——独立 H5 页，内容**不在原生视图树里**，
    只能靠"焦点变化 / 探针 DOM"去猜页面是否就绪；而同一条 action 经通用可测性 scheme
    （`AppDescriptor.testability_scheme_prefix` = `.../travel/debugconfig`）下发时，
    承载页是 **MRN 容器**（`mrn.container.mrnbaseactivity`），内容**直接进原生视图树**，
    可判定、可复核。实测（Android 云模拟器）：经该通道下发并冷重启后，首页即
    「成功定位到 <城市>」。

    payload 字段与官方 H5 通道**逐字一致**（从官方 H5 URL 的 `encode` 反解得到），
    保证与线上可测性协议吻合。

    Args:
        loc: `LOCATION_PRESETS` 中的一项（含 lat / lng）。
    Returns:
        pillow 可测性 action 列表（`[{index,type,info,priority,serial,disabled}]`）。
    """
    return _location_action({"open": 1, "latitude": str(loc["lat"]),
                             "longitude": str(loc["lng"])})


def build_location_clear_action():
    """清除模拟定位 → 同一 action（`open=0`）。

    与官方 `imeituan control location --clear` 的 payload **逐字一致**（含
    `latitude/longitude="0"`），但同样经**通用可测性 scheme**（MRN 承载页）下发，
    **不走 Pillow-H5** —— 与 `build_location_action` 同源同通道。
    """
    return _location_action({"open": 0, "latitude": "0", "longitude": "0"})
