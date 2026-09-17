"""视图树解析与几何原语：原始树 → UiNode、滚动裁剪、节点几何/调试控件判定。"""
import re
from context import get_platform_ops, get_app_descriptor


_SCROLL_CLASS_RE = re.compile(
    r'(?i)(scroll\\w*view|listview|recyclerview|nestedscrollview|'
    r'collectionview|viewpager|tableview)'
)
def _is_scroll_container(node):
    """判断节点是否是滚动容器。

    两个信号取或集：
      1. scrollable=True（平台 adapter 直接设定，iOS 优先走此路径）
      2. class_name 按精确模式匹配（覆盖 React Native 混淆后的 ScrollView，
         其 isScrollable 在 inspect-tree 中不可靠，但类名始终含 ScrollView）

    模式匹配覆盖：
      - RN: com.facebook.react.views.scroll.React[Horizontal]ScrollView
      - Android 原生: ScrollView/ListView/RecyclerView/NestedScrollView/ViewPager
      - iOS: XCUIElementTypeScrollView/CollectionView/Table/WebView

    Arg:
        node: UiNode 字典
    Returns:
        bool: 是否滚动容器
    """
    if node.get("scrollable"):
        return True
    cls = node.get("class_name") or ""
    return bool(_SCROLL_CLASS_RE.search(cls))
def _clip_by_scrollable_parent(node, nodes):
    """检查节点是否被最近的滚动容器祖先裁剪。

    原理：React Native HorizontalScrollView / ScrollView 预渲染全部子节点，
    子节点的屏幕绝对坐标可能落在容器可视 bounds 之外——视觉上被裁剪但
    视图树中坐标仍在屏幕范围内。

    两个关键发现：
      1. RN ScrollView 的 misc.isScrollable 不可靠（混淆后类名如
         com.facebook.react.views.scroll.d 的 scrollable=False）
      2. 节点的 bounding box（而非中心点）超出容器可视 bounds 才被裁剪

    检测策略：
      - 用 class_name 含 "scroll" 替代不可靠的 scrollable 属性做容器识别
      - 用完整 bound box（四边）而非中心点判断是否超出容器可视区域
      - 跳过自身也是 scroll 容器的情况

    Returns:
        bool: True 表示被裁剪（视觉上不可见）
    """
    # 自身是滚动容器的不做裁剪检测
    if _is_scroll_container(node):
        return False

    nx = node.get("x")
    ny = node.get("y")
    nw = node.get("w")
    nh = node.get("h")
    if None in (nx, ny, nw, nh):
        return False
    node_right = nx + nw
    node_bottom = ny + nh

    parent_idx = node.get("parent")
    while parent_idx is not None:
        parent = nodes[parent_idx]
        if _is_scroll_container(parent):
            px, py, pw, ph = (parent.get("x"), parent.get("y"),
                              parent.get("w"), parent.get("h"))
            if None not in (px, py, pw, ph):
                # 节点整体必须在容器可视区域内，超出任一边界视为被裁剪。
                # 嵌套 scroll 容器场景（如内容 ScrollView 宽度大于外层裁剪
                # ScrollView），不信任单个容器的判定，遇到嵌套 scroll 容器
                # 继续上溯——只要有一个祖先 scroll 容器限制了就返回 True。
                if not (px <= nx and ny >= py
                        and node_right <= px + pw
                        and node_bottom <= py + ph):
                    return True
        parent_idx = parent.get("parent")
    return False
def parse_inspect_tree(tree):
    """原始视图树 JSON → UiNode 列表（前序 DFS 顺序），标注视口可见性信息。

    两层视口检测：
      1. 屏幕物理边界（现有）— 节点是否在设备屏幕范围内
      2. 滚动容器裁剪（新增）— 节点是否在最近的 scrollable 祖先可视 bounds 内
    两层都通过的节点才标记为 in_viewport=True。
    """
    from device_platform.base import get_platform_module
    platform = get_app_descriptor().platform
    nodes = get_platform_module(platform).parse_tree(tree)

    # 为每个节点标注视口可见性
    try:
        from screen_state.screen_layout import ScreenLayout
        layout = ScreenLayout.from_ops(get_platform_ops())
        for node in nodes:
            cx = node.get("x", 0) + (node.get("w", 0) or 0) // 2
            cy = node.get("y", 0) + (node.get("h", 0) or 0) // 2
            # 第一层：屏幕物理边界
            node["in_viewport"] = layout.is_in_viewport(cy, cx)
            node["viewport_offset"] = layout.viewport_offset(cy) if not node["in_viewport"] else 0
            node["viewport_offset_x"] = layout.viewport_offset_x(cx) if not node["in_viewport"] else 0

        # 第二层：滚动容器裁剪检测（仅对通过第一层的节点）
        for node in nodes:
            if not node.get("in_viewport", True):
                continue
            if _clip_by_scrollable_parent(node, nodes):
                node["in_viewport"] = False
                cx = node.get("x", 0) + (node.get("w", 0) or 0) // 2
                cy = node.get("y", 0) + (node.get("h", 0) or 0) // 2
                node["viewport_offset"] = layout.viewport_offset(cy)
                node["viewport_offset_x"] = layout.viewport_offset_x(cx)
    except (ImportError, OSError, AttributeError, TypeError):
        # 获取不到屏幕尺寸时，默认所有节点可见
        for node in nodes:
            node["in_viewport"] = True
            node["viewport_offset"] = 0
            node["viewport_offset_x"] = 0
    return nodes
def _center_of(node):
    """节点屏幕中心坐标 (cx, cy)，坐标缺失返回 None。"""
    if None in (node["x"], node["y"], node["w"], node["h"]):
        return None
    return node["x"] + node["w"] // 2, node["y"] + node["h"] // 2
def _bounds_of(node):
    if None in (node["x"], node["y"], node["w"], node["h"]):
        return None
    return node["x"], node["y"], node["x"] + node["w"], node["y"] + node["h"]
def _geometry(node):
    """节点几何信息 (cx, cy, w, h)，坐标缺失返回 None。"""
    if None in (node["x"], node["y"], node["w"], node["h"]):
        return None
    return (node["x"] + node["w"] // 2, node["y"] + node["h"] // 2,
            node["w"], node["h"])
def is_debug_overlay(node):
    cls = node.get("class_name", "")
    prefixes = get_app_descriptor().debug_overlay_prefixes
    return any(cls.startswith(p) for p in prefixes)
