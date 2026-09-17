"""模拟定位预设：城市坐标表与别名归一。"""



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
    if not loc:
        return loc
    return _LOCATION_ALIAS.get(loc, loc)
