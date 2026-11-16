"""
d2c_common.py - 设计稿分析脚本的共享工具函数

被 fetch_skeleton / search_nodes / inspect_node / extract_leaves 共用。
"""

import json
import sys
from typing import Dict, List, Optional, Set, Tuple

from _semantic import (
    resolve_preferred_json_path,
    load_raw_json,
    STRATEGY_MAP,
    EXPORT_REASONS,
    compact_style,
    compact_node as _compact_node,
)


def build_node_index(root: Dict) -> Dict[str, Dict]:
    """一次性遍历建立 id → node 字典，后续 O(1) 查找"""
    index = {}

    def _walk(node):
        nid = node.get("id")
        if nid:
            index[nid] = node
        for child in node.get("children", []):
            _walk(child)

    _walk(root)
    return index


def find_node_by_id(node: Dict, target_id: str) -> Optional[Dict]:
    """递归查找指定 ID 的节点（兼容旧调用，新代码请用 build_node_index）"""
    if node.get("id") == target_id:
        return node
    for child in node.get("children", []):
        result = find_node_by_id(child, target_id)
        if result:
            return result
    return None


def load_json(file_path: str, prefer_semantic: bool = True) -> Dict:
    """加载 JSON 文件，失败则打印错误并退出。

    默认优先读取 sibling ``*.semantic.json``，这样分析脚本会自动消费新的语义层。
    """
    try:
        path = resolve_preferred_json_path(file_path) if prefer_semantic else file_path
        return load_raw_json(path)
    except FileNotFoundError:
        print(f"错误: 文件不存在 - {file_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败 - {e}", file=sys.stderr)
        sys.exit(1)


def is_semantic_node(node: Dict) -> bool:
    return isinstance(node.get("semantic"), dict) or isinstance(node.get("d2c"), dict)


def _from_legacy_d2c(node: Dict) -> Dict:
    d2c = node.get("d2c", {}) if isinstance(node.get("d2c"), dict) else {}
    role = d2c.get("role", {}).get("primary")
    strategy = d2c.get("recommendation", {}).get("strategy")
    prefer = STRATEGY_MAP.get(strategy, strategy)
    reasons = list(d2c.get("recommendation", {}).get("reasons") or [])
    asset = None
    exports = d2c.get("assets", {}).get("exports") or []
    if exports:
        first = exports[0]
        asset = first.get("src") or first.get("cdnSrc") or first.get("localSrc")

    payload = {
        "role": role,
        "prefer": prefer,
        "why": reasons,
        "asset": asset,
    }
    return {k: v for k, v in payload.items() if v not in (None, [], {})}


def semantic_payload(node: Dict) -> Dict:
    if isinstance(node.get("semantic"), dict):
        return node["semantic"]
    if isinstance(node.get("d2c"), dict):
        return _from_legacy_d2c(node)
    return {}


def semantic_role(node: Dict) -> Optional[str]:
    semantic = semantic_payload(node)
    primary = semantic.get("role")
    if primary:
        return primary

    legacy = node.get("_autoTag")
    legacy_map = {
        "icon": "icon",
        "icon_composite": "icon",
        "deco": "decorative_graphic",
        "dynamic": "text_bearing_graphic",
        "statusbar": "system_ui",
    }
    return legacy_map.get(legacy)


def recommendation_strategy(node: Dict) -> Optional[str]:
    semantic = semantic_payload(node)
    prefer = semantic.get("prefer")
    if prefer:
        return prefer

    legacy = node.get("_autoTag")
    if legacy in ("icon", "icon_composite", "deco"):
        return "asset"
    if legacy == "dynamic":
        return "dom"
    if legacy == "statusbar":
        return "ignore"
    return None


def recommendation_risks(node: Dict) -> List[str]:
    semantic = semantic_payload(node)
    why = semantic.get("why")
    if not isinstance(why, list):
        return []
    return [item for item in why if item in {"asset_missing", "boundary_ambiguous", "text_loss"}]


def export_facts(node: Dict) -> Dict:
    semantic = semantic_payload(node)
    why = semantic.get("why") if isinstance(semantic.get("why"), list) else []
    matched_reason = next((item for item in why if item in EXPORT_REASONS), None)
    if matched_reason:
        return {
            "candidate": True,
            "reason": matched_reason,
            "designerMarked": matched_reason == "designer_marked" or bool(semantic.get("designerMarked")),
        }
    if node.get("_exportHint") == "slice":
        return {
            "candidate": True,
            "reason": node.get("_exportReason"),
            "designerMarked": node.get("_exportReason") == "designer_marked",
        }
    return {}


def asset_exports(node: Dict) -> List[Dict]:
    semantic = semantic_payload(node)
    asset = semantic.get("asset")
    if isinstance(asset, str):
        return [{"src": asset}]
    if isinstance(asset, dict):
        return [asset]

    if node.get("_exportSrc"):
        return [{
            "src": node.get("_exportSrc"),
        }]
    return []


def primary_export(node: Dict) -> Optional[Dict]:
    exports = asset_exports(node)
    return exports[0] if exports else None


def semantic_badges(node: Dict) -> List[str]:
    badges: List[str] = []
    role = semantic_role(node)
    strategy = recommendation_strategy(node)
    export = primary_export(node)
    risks = recommendation_risks(node)

    role_badges = {
        "icon": "icon",
        "decorative_graphic": "deco",
        "text_bearing_graphic": "text-graphic",
        "system_ui": "system",
        "content_image": "image",
    }
    if role in role_badges:
        badges.append(role_badges[role])
    if export:
        badges.append("asset")
    if strategy == "review" or risks:
        badges.append("review")
    if strategy == "ignore":
        badges.append("ignore")
    return badges


def precompute_hints(root: Dict) -> Dict[int, Dict]:
    """单次自底向上遍历，预计算所有节点的 hint 信息。"""
    cache: Dict[int, Dict] = {}

    def _compute(node) -> Tuple[List[str], Set[str], int, int, Optional[str]]:
        texts: List[str] = []
        texts_seen: Set[str] = set()
        image_count = 0
        exportable_count = 0
        layout: Optional[str] = None

        tc = node.get("textContent", "")
        if tc and tc.strip():
            t = tc.strip()
            texts_seen.add(t)
            texts.append(t)

        tag = node.get("tag", "")
        if tag == "img" or node.get("src") or node.get("style", {}).get("backgroundImage"):
            image_count += 1

        if export_facts(node).get("candidate"):
            exportable_count += 1

        style = node.get("style", {})
        display = style.get("display", "")
        fd = style.get("flexDirection", "")
        if display == "flex":
            layout = "flex-column" if fd == "column" else "flex-row"
        elif display == "grid":
            layout = "grid"
        elif display == "block":
            layout = "block"
        elif display in ("inline", "inline-block"):
            layout = "inline"

        for child in node.get("children", []):
            ct, cs, ci, ce, cl = _compute(child)
            for t in ct:
                if t not in texts_seen:
                    texts_seen.add(t)
                    texts.append(t)
            image_count += ci
            exportable_count += ce
            if layout is None:
                layout = cl

        hint: Dict = {}
        if texts:
            hint["texts"] = texts
        if image_count > 0:
            hint["images"] = image_count
        if exportable_count > 0:
            hint["exportable"] = exportable_count
        if layout:
            hint["layout"] = layout

        cache[id(node)] = hint
        return texts, texts_seen, image_count, exportable_count, layout

    _compute(root)
    return cache


def node_name(node: Dict) -> str:
    """获取节点显示名称（优先 mg-name）"""
    return node.get("mg-name", node.get("name", "unnamed"))


def should_collapse(node: Dict, collapse: bool) -> bool:
    """判断节点是否应被坍缩为 img"""
    if not collapse:
        return False
    strategy = recommendation_strategy(node)
    if strategy == "asset" and primary_export(node):
        return True
    if bool(node.get("_exportSrc")):
        return True
    return False


def should_collapse_deco(node: Dict) -> bool:
    """判断 deco 节点是否应折叠 children"""
    role = semantic_role(node)
    if role == "decorative_graphic":
        return True
    return node.get("_autoTag") == "deco"


def auto_tag_hint(node: Dict) -> Optional[str]:
    """返回节点语义对应的编码提示文案"""
    tag = semantic_role(node) or node.get("_autoTag")
    strategy = recommendation_strategy(node)
    hints = {
        "icon": "⚡ 图标：直接用切图",
        "decorative_graphic": "🎨 装饰图形：建议用资产实现",
        "text_bearing_graphic": "📝 含文本图形：优先保留 DOM",
        "system_ui": "⏭ 系统状态元素：跳过",
        "content_image": "🖼 内容图片：保留为图片资产",
    }
    if strategy == "review":
        return "🧐 建议先 inspect 再决定"
    return hints.get(tag)


def collapsed_fields(node: Dict) -> Dict:
    """构建坍缩节点的公共字段"""
    export = primary_export(node)
    src = None
    if export:
        src = export.get("src")
    else:
        src = node.get("_exportSrc")

    return {"src": src, "_collapsed": True}


def export_marker_fields(node: Dict) -> Dict:
    """构建非坍缩模式下的导出标记字段"""
    fields = {}
    export = primary_export(node)
    if export:
        fields["asset"] = export.get("src")
    elif node.get("_exportSrc"):
        fields["asset"] = node.get("_exportSrc")
    return fields


def build_parent_index(root: Dict) -> Dict[str, Dict]:
    """构建 child_id → parent_node 映射"""
    parents: Dict[str, Dict] = {}

    def _walk(node):
        for child in node.get("children", []):
            cid = child.get("id")
            if cid:
                parents[cid] = node
            _walk(child)

    _walk(root)
    return parents


def compact_node(node: Dict) -> Dict:
    """公共 compact 入口，委托给 _semantic.compact_node"""
    return _compact_node(node)


# ─── 空间计算（measure / crop_node / locate_at 共用） ───

def parse_px(value) -> float:
    """'750px' / 750 / None → float"""
    if value is None:
        return 0.0
    try:
        return float(str(value).rstrip("px"))
    except ValueError:
        return 0.0


def compute_abs_boxes(root: Dict) -> Dict[str, List[float]]:
    """计算各节点的绝对包围盒 {id: [x, y, w, h]}（相对 root 左上角，设计稿 px）。

    优先读节点的 ``_abs`` 字段（由 _normalize.py 在归一化时写入的帧相对绝对坐标）。
    ``_abs`` 缺失时回退到绝对定位链推导：仅每级都有 left/top 的节点可推导。
    """
    boxes: Dict[str, List[float]] = {}

    def _walk(node: Dict, off_x: float, off_y: float, known: bool, is_root: bool) -> None:
        style = node.get("style", {})
        abs_field = node.get("_abs")
        if is_root:
            ax, ay, k = 0.0, 0.0, True
        elif isinstance(abs_field, (list, tuple)) and len(abs_field) == 2:
            ax, ay, k = parse_px(abs_field[0]), parse_px(abs_field[1]), True
        elif known and ("left" in style or "top" in style):
            ax = off_x + parse_px(style.get("left"))
            ay = off_y + parse_px(style.get("top"))
            k = True
        else:
            ax, ay, k = off_x, off_y, False
        if k and node.get("id"):
            boxes[node["id"]] = [ax, ay, parse_px(style.get("width")), parse_px(style.get("height"))]
        for child in node.get("children", []):
            _walk(child, ax, ay, k, False)

    _walk(root, 0.0, 0.0, True, True)
    return boxes


def _subtree_size(node: Dict) -> int:
    return 1 + sum(_subtree_size(c) for c in node.get("children", []))


def is_ancestor(ancestor_id: str, node_id: str, parents: Dict[str, Dict]) -> bool:
    """parents: child_id → parent_node。判断 ancestor_id 是否是 node_id 的祖先。"""
    cur = node_id
    seen: Set[str] = set()
    while cur in parents and cur not in seen:
        seen.add(cur)
        cur = parents[cur].get("id")
        if cur == ancestor_id:
            return True
    return False


def resolve_node_ref(ref: str, index: Dict[str, Dict], parents: Dict[str, Dict],
                     up: int = 0) -> Tuple[Optional[Dict], List[Dict]]:
    """把节点引用解析为节点（id / text:子串 / name:子串）。

    多个匹配时，若其中一个是其余所有的祖先，取最外层；否则视为歧义。
    ``up>0`` 时在解析结果上再向上爬 ``up`` 层父节点。

    返回 ``(node, candidates)``：成功→(node,[])，未找到→(None,[])，歧义→(None,[候选...])
    """
    ref = (ref or "").strip()
    matches: List[Dict] = []
    if ref.startswith("text:"):
        val = ref[5:].strip().lower()
        if val:
            matches = [n for n in index.values()
                       if val in (n.get("textContent") or "").lower()]
    elif ref.startswith("name:"):
        val = ref[5:].strip().lower()
        if val:
            exact = [n for n in index.values() if node_name(n).lower() == val]
            matches = exact if exact else [n for n in index.values()
                                           if val in node_name(n).lower()]
    elif ref in index:
        matches = [index[ref]]

    if not matches:
        return None, []

    uniq: Dict[str, Dict] = {}
    for m in matches:
        uniq[m.get("id")] = m
    matches = list(uniq.values())

    if len(matches) == 1:
        node = matches[0]
    else:
        outer = [m for m in matches
                 if all(m.get("id") == o.get("id")
                        or is_ancestor(m.get("id"), o.get("id"), parents)
                        for o in matches)]
        if len(outer) == 1:
            node = outer[0]
        else:
            matches.sort(key=_subtree_size, reverse=True)
            return None, matches

    for _ in range(max(0, up)):
        parent = parents.get(node.get("id"))
        if not parent:
            break
        node = parent
    return node, []


def resolve_ref_or_die(ref: str, index: Dict[str, Dict], parents: Dict[str, Dict],
                       up: int = 0) -> Dict:
    """CLI 包装：解析节点引用，失败或歧义打印引导并退出。"""
    node, cands = resolve_node_ref(ref, index, parents, up)
    if node is not None:
        return node
    if cands:
        print(f"错误: 引用 '{ref}' 有歧义，{len(cands)} 个候选（外层在前），"
              f"请改用具体 id，或加 --up N 上提：", file=sys.stderr)
        for c in cands[:8]:
            print(f"  {c.get('id'):16} '{node_name(c)[:20]}'", file=sys.stderr)
    else:
        print(f"错误: 引用 '{ref}' 未匹配到任何节点（写法：id / text:子串 / name:子串）",
              file=sys.stderr)
    sys.exit(1)


def box_or_die(node: Dict, boxes: Dict[str, List[float]],
               parents: Dict[str, Dict]) -> List[float]:
    """取节点绝对盒；不可定位时报错并提示。"""
    nid = node.get("id")
    if nid in boxes:
        return boxes[nid]
    cur = nid
    while cur in parents:
        cur = parents[cur].get("id", "")
        if cur in boxes:
            break
    else:
        cur = ""
    print(f"错误: 节点 '{nid}' 无绝对坐标", file=sys.stderr)
    if cur:
        print(f"提示: 可改用最近的绝对定位祖先 '{cur}'", file=sys.stderr)
    else:
        print("提示: 确认 _normalize.py 已写入 _abs 字段（重新下载即可）", file=sys.stderr)
    sys.exit(1)


def neighbor_gaps(node: Dict, boxes: Dict[str, List[float]], parents: Dict[str, Dict],
                  tol: float = 1.5) -> Dict[str, Optional[Dict]]:
    """node 在同一父容器内四向最近邻 + 间距：{above/below/left/right: {id,name,gap}|None}。"""
    nid = node.get("id")
    if nid not in boxes:
        return {}
    tx0, ty0, tw, th = boxes[nid]
    tx1, ty1 = tx0 + tw, ty0 + th
    parent = parents.get(nid)
    sibs = []
    if parent:
        for c in parent.get("children", []):
            cid = c.get("id")
            if cid != nid and cid in boxes:
                sibs.append((c, boxes[cid]))

    def _ov(a0, a1, b0, b1):
        return min(a1, b1) - max(a0, b0)

    def _best(direction):
        chosen, gap_best = None, None
        for c, b in sibs:
            x0, y0, w, h = b
            x1, y1 = x0 + w, y0 + h
            if direction in ("above", "below"):
                if _ov(tx0, tx1, x0, x1) <= 0:
                    continue
            elif _ov(ty0, ty1, y0, y1) <= 0:
                continue
            if direction == "above":
                if y1 > ty0 + tol:
                    continue
                gap = ty0 - y1
            elif direction == "below":
                if y0 < ty1 - tol:
                    continue
                gap = y0 - ty1
            elif direction == "left":
                if x1 > tx0 + tol:
                    continue
                gap = tx0 - x1
            else:
                if x0 < tx1 - tol:
                    continue
                gap = x0 - tx1
            if gap_best is None or gap < gap_best:
                chosen, gap_best = c, gap
        if chosen is None:
            return None
        return {"id": chosen.get("id"), "name": node_name(chosen), "gap": round(gap_best, 1)}

    return {d: _best(d) for d in ("above", "below", "left", "right")}
