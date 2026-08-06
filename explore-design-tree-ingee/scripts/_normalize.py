"""
Normalize Ingee MCP JSON → IMD-compatible design tree format.

Converts:
  objectId       → id
  objectName     → name
  objectType     → tag (FRAME→div, TEXT→span, etc.)
  rect.{x,y,w,h} → style.{left,top,width,height}
  css[]          → style{} (parsed key:value pairs)
  content        → textContent
  image_urls[]   → _exportSrc on root node

Auto-detects:
  - _exportHint / _exportReason (from image_urls presence)
  - _autoTag (icon/deco/dynamic/statusbar from heuristics)
  - textSegments (from content + style)
"""

import json
import re
import os
import sys
from typing import Dict, List, Optional, Tuple

# ─── Type → HTML tag mapping ───
TYPE_TO_TAG = {
    "FRAME": "div",
    "GROUP": "div",
    "COMPONENT": "div",
    "INSTANCE": "div",
    "SECTION": "div",
    "SLICE": "div",
    "TEXT": "span",
    "RECTANGLE": "div",
    "ELLIPSE": "div",
    "LINE": "hr",
    "PEN": "svg",
    "VECTOR": "svg",
    "STAR": "svg",
    "POLYGON": "svg",
    "BOOLEAN_OPERATION": "svg",
}

# ─── CSS parsing ───

_CSS_KV_RE = re.compile(r'^\s*([a-zA-Z-]+)\s*:\s*(.+)\s*$')

def parse_css_array(css_array: List[str]) -> Dict[str, str]:
    """Parse Ingee css[] array into a style dict.

    Skips comment lines (// ...), handles multi-value properties like
    background: linear-gradient(...), border: 1px solid #CCC, etc.
    """
    style = {}
    if not css_array:
        return style

    for line in css_array:
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        # Handle properties that look like comments but have values
        # e.g. "//." as a font-size marker
        if line.startswith("//") and ":" not in line:
            continue

        m = _CSS_KV_RE.match(line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip().rstrip(";")
            # Normalize key: convert kebab-case to camelCase for CSS-in-JS compat
            # but keep standard CSS keys for IMD format compat
            style[key] = value

    return style


def _normalize_style_key(key: str) -> str:
    """Convert kebab-case CSS key to camelCase for IMD format."""
    if "-" not in key:
        return key
    parts = key.split("-")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def normalize_style_keys(style: Dict[str, str]) -> Dict[str, str]:
    """Convert CSS kebab-case keys to camelCase (IMD format expectation)."""
    return {_normalize_style_key(k): v for k, v in style.items()}


# ─── Auto-tag heuristics ───

VECTOR_TYPES = {"PEN", "VECTOR", "STAR", "POLYGON", "BOOLEAN_OPERATION", "LINE"}
SMALL_ICON_THRESHOLD = 48  # px

def _looks_like_system_ui(name: str) -> bool:
    keywords = ("statusbar", "status bar", "wifi", "cellular", "battery", "9:41")
    return any(kw in name.lower() for kw in keywords)


def _has_text_content(node: Dict) -> bool:
    content = node.get("content", "")
    return bool(content and content.strip())


def _subtree_has_text(node: Dict) -> bool:
    if _has_text_content(node):
        return True
    for child in node.get("children", []):
        if _subtree_has_text(child):
            return True
    return False


def _subtree_has_vector(node: Dict) -> bool:
    if node.get("objectType") in VECTOR_TYPES:
        return True
    for child in node.get("children", []):
        if _subtree_has_vector(child):
            return True
    return False


def detect_export_hint(node: Dict, has_image_urls: bool, is_root: bool) -> Tuple[Optional[str], Optional[str]]:
    """Detect _exportHint and _exportReason for a node."""
    object_type = node.get("objectType", "")
    rect = node.get("rect", {})
    w = rect.get("width", 0)
    h = rect.get("height", 0)
    name = node.get("objectName", "")

    # Designer-marked exports: image_urls on root covers the whole frame
    if is_root and has_image_urls:
        return "slice", "designer_marked"

    # SVG nodes are exportable
    if object_type in VECTOR_TYPES:
        return "slice", "svg_node"

    # Groups where majority children are vectors
    if object_type == "GROUP":
        children = node.get("children", [])
        if children:
            vector_count = sum(1 for c in children if c.get("objectType") in VECTOR_TYPES)
            if vector_count >= len(children) * 0.5 and len(children) >= 2:
                return "slice", "svg_majority_group"

    return None, None


def detect_auto_tag(node: Dict) -> Optional[str]:
    """Auto-detect _autoTag based on heuristics (mirrors IMD logic)."""
    object_type = node.get("objectType", "")
    rect = node.get("rect", {})
    w = rect.get("width", 0)
    h = rect.get("height", 0)
    max_dim = max(w, h)
    name = node.get("objectName", "")

    if _looks_like_system_ui(name):
        return "statusbar"

    if object_type in VECTOR_TYPES:
        has_text = _subtree_has_text(node)
        if max_dim <= SMALL_ICON_THRESHOLD:
            return "icon_composite" if object_type in ("GROUP", "BOOLEAN_OPERATION") else "icon"
        if not has_text:
            return "deco"
        if has_text:
            return "dynamic"

    # Groups
    if object_type == "GROUP":
        has_text = _subtree_has_text(node)
        has_vector = _subtree_has_vector(node)
        if has_vector and max_dim <= SMALL_ICON_THRESHOLD:
            return "icon_composite"
        if has_vector and not has_text:
            return "deco"
        if has_text and has_vector:
            return "dynamic"

    return None


# ─── Main normalization ───

def normalize_node(
    node: Dict,
    has_image_urls: bool = False,
    is_root: bool = False,
    depth: int = 0,
    _abs_x: float = 0.0,
    _abs_y: float = 0.0,
) -> Dict:
    """Convert a single Ingee node → IMD-compatible format."""

    object_type = node.get("objectType", "FRAME")
    rect = node.get("rect", {})
    css_array = node.get("css", [])
    content = node.get("content", "")
    is_visible = node.get("isVisible", True)

    # Parse style
    style = parse_css_array(css_array)

    # Add rect dimensions to style
    if rect.get("width"):
        style["width"] = f"{rect['width']}px"
    if rect.get("height"):
        style["height"] = f"{rect['height']}px"
    if not is_root:
        # Prefer relativeX/relativeY (parent-relative coords), fall back to x/y
        raw_x = rect.get("relativeX") if rect.get("relativeX") is not None else rect.get("x")
        raw_y = rect.get("relativeY") if rect.get("relativeY") is not None else rect.get("y")
        if raw_x is not None and raw_x != 0:
            style["left"] = f"{raw_x}px"
        if raw_y is not None and raw_y != 0:
            style["top"] = f"{raw_y}px"

    # Normalize keys to camelCase
    style = normalize_style_keys(style)

    # Map tag
    tag = TYPE_TO_TAG.get(object_type, "div")

    # Detect export hints
    export_hint, export_reason = detect_export_hint(node, has_image_urls, is_root)

    # Detect auto tag
    auto_tag = detect_auto_tag(node)

    # Compute this node's frame-relative absolute position for spatial tools
    # Root is always at (0,0); non-root uses parent's abs position + this node's relative offset
    if is_root:
        node_abs_x, node_abs_y = 0.0, 0.0
    else:
        node_abs_x, node_abs_y = _abs_x, _abs_y

    # Build normalized node
    normalized = {
        "id": node.get("objectId", "unknown"),
        "name": node.get("objectName", "unnamed"),
        "tag": tag,
        "style": style,
        "_mgType": object_type,
    }

    # Write _abs for all nodes (enables measure.py / crop_node.py / locate_at.py)
    # Root is always [0, 0]; non-root carries frame-relative absolute coords
    normalized["_abs"] = [node_abs_x, node_abs_y]

    # Text
    if content and content.strip():
        normalized["textContent"] = content
        # Build basic textSegments if not present
        font_size = style.get("fontSize", "")
        font_weight = style.get("fontWeight", "")
        color = style.get("color", "")
        seg_style = {}
        if font_size:
            seg_style["fontSize"] = font_size
        if font_weight:
            seg_style["fontWeight"] = font_weight
        if color:
            seg_style["color"] = color
        normalized["textSegments"] = [{"text": content, "style": seg_style}]

    # Visibility
    if not is_visible:
        if "style" not in normalized:
            normalized["style"] = {}
        normalized["style"]["display"] = "none"

    # Export hints
    if export_hint:
        normalized["_exportHint"] = export_hint
    if export_reason:
        normalized["_exportReason"] = export_reason
    if auto_tag:
        normalized["_autoTag"] = auto_tag

    # Per-node image_urls → _exportSrc / _exportHint
    # Ingee attaches image_urls on each node that has exportable assets (PEN, GROUP, etc.)
    node_image_urls = node.get("image_urls", [])
    if node_image_urls:
        first_img = node_image_urls[0]
        cdn_url = first_img.get("url") or first_img.get("path", "")
        if cdn_url:
            normalized["_exportSrc"] = cdn_url
            if not export_hint:
                normalized["_exportHint"] = "slice"
                normalized["_exportReason"] = "ingee_image_urls"
            # Also store all available formats/scales
            if len(node_image_urls) > 1:
                normalized["_exportVariants"] = [
                    {"url": img.get("url") or img.get("path", ""), "format": img.get("format", "png"), "name": img.get("name", "")}
                    for img in node_image_urls
                ]

    # Children — each child checks its own image_urls and receives its absolute position
    children = node.get("children", [])
    if children:
        normalized_children = []
        for child in children:
            child_rect = child.get("rect", {})
            # relativeX/Y is the child's offset from its parent (this node)
            child_rel_x = child_rect.get("relativeX") if child_rect.get("relativeX") is not None else child_rect.get("x", 0)
            child_rel_y = child_rect.get("relativeY") if child_rect.get("relativeY") is not None else child_rect.get("y", 0)
            child_abs_x = node_abs_x + (child_rel_x or 0)
            child_abs_y = node_abs_y + (child_rel_y or 0)
            normalized_children.append(
                normalize_node(
                    child,
                    has_image_urls=bool(child.get("image_urls")),
                    is_root=False,
                    depth=depth + 1,
                    _abs_x=child_abs_x,
                    _abs_y=child_abs_y,
                )
            )
        normalized["children"] = normalized_children

    # Sizing hints for flex containers
    if style.get("display") == "flex":
        sizing_w = "fixed" if style.get("width") else "hug"
        sizing_h = "fixed" if style.get("height") else "hug"
        normalized["_sizing"] = {"w": sizing_w, "h": sizing_h}

        # Layout summary
        fd = "column" if style.get("flexDirection") == "column" else "row"
        parts = [f"{'vertical' if fd == 'column' else 'horizontal'} flex"]
        gap = style.get("gap")
        if gap:
            parts.append(f"{gap} gap")
        ai = style.get("alignItems")
        if ai:
            parts.append(f"{ai}-aligned")
        normalized["_layoutSummary"] = ", ".join(parts)

    return normalized


def normalize_ingee_data(raw_data: Dict, tree_index: Optional[str] = None) -> Dict:
    """Convert full Ingee MCP response → IMD-compatible tree.

    Handles both response formats:
      - Full: {"layersTree": {...}, "image_urls": [...], ...}
      - Alternative: {"trees": [{...}], "image_urls": [...], ...}

    Multi-tree support:
      - If multiple trees exist, creates a virtual root (tag: div, name: "artboard")
        wrapping all normalized trees as children.
      - If only one tree (layersTree or trees[0]), returns it directly (no wrapper).
      - tree_index: "all" (default) or comma-separated indices like "0,2" to select specific trees.
    """
    # Check for image_urls (CDN exports)
    image_urls = raw_data.get("image_urls", [])

    # Determine tree source(s)
    single_root = raw_data.get("layersTree") or raw_data.get("layers_tree")
    trees = raw_data.get("trees", [])

    if single_root and not trees:
        # Single layersTree — normalize directly
        all_trees = [single_root]
    elif trees:
        all_trees = trees
    elif single_root:
        all_trees = [single_root]
    else:
        raise ValueError("Cannot find layersTree or trees in Ingee response")

    # Filter by tree_index if specified
    if tree_index and tree_index != "all":
        indices = [int(i.strip()) for i in tree_index.split(",") if i.strip().isdigit()]
        selected = [all_trees[i] for i in indices if 0 <= i < len(all_trees)]
        if not selected:
            raise ValueError(f"No valid trees for indices {tree_index} (available: 0-{len(all_trees)-1})")
        all_trees = selected

    def _adjust_abs(node: Dict, dx: float, dy: float) -> None:
        """Recursively offset all _abs values in the subtree by (dx, dy).

        Used for multi-tree artboards so each tree's nodes carry artboard-relative
        absolute coordinates instead of tree-local coordinates.
        """
        abs_val = node.get("_abs")
        if isinstance(abs_val, (list, tuple)) and len(abs_val) == 2:
            node["_abs"] = [abs_val[0] + dx, abs_val[1] + dy]
        for child in node.get("children", []):
            _adjust_abs(child, dx, dy)

    # Normalize each tree
    normalized_trees = []
    for i, tree_node in enumerate(all_trees):
        is_first = (i == 0)
        norm = normalize_node(tree_node, has_image_urls=bool(image_urls) and is_first, is_root=True)
        normalized_trees.append(norm)

    # Build final root
    if len(normalized_trees) == 1:
        # Single tree — return directly (no virtual wrapper)
        normalized = normalized_trees[0]
    else:
        # Multiple trees — inject top/left from original rect (lost because is_root=True
        # skips coordinate writing) and sort by visual position (rect.y ascending)
        for i, (tree_node, norm) in enumerate(zip(all_trees, normalized_trees)):
            rect = tree_node.get("rect", {})
            raw_x = float(rect.get("x", 0))
            raw_y = float(rect.get("y", 0))
            if raw_x:
                norm["style"]["left"] = f"{int(raw_x)}px"
            if raw_y:
                norm["style"]["top"] = f"{int(raw_y)}px"
            # Fix _abs: each tree was normalized as is_root=True (abs=[0,0]),
            # so we need to add the tree's canvas offset to all nodes in the subtree.
            if raw_x or raw_y:
                _adjust_abs(norm, raw_x, raw_y)

        # Sort by rect.y ascending so children follow visual top-to-bottom order
        paired = list(zip(all_trees, normalized_trees))
        paired.sort(key=lambda p: p[0].get("rect", {}).get("y", 0))
        all_trees = [p[0] for p in paired]
        normalized_trees = [p[1] for p in paired]

        # Create virtual artboard root
        design_w = raw_data.get("width", 0)
        design_h = raw_data.get("height", 0)
        virtual_style = {}
        if design_w:
            virtual_style["width"] = f"{design_w}px"
        if design_h:
            virtual_style["height"] = f"{design_h}px"

        normalized = {
            "id": f"artboard_{raw_data.get('imageId', 'root')}",
            "name": "artboard",
            "tag": "div",
            "style": virtual_style,
            "_mgType": "ARTBOARD",
            "children": normalized_trees,
        }

    # Attach image_urls as export info on root
    if image_urls:
        first_img = image_urls[0]
        normalized["_exportSrc"] = first_img.get("url") or first_img.get("path", "")
        normalized["_exportHint"] = "slice"
        normalized["_exportReason"] = "designer_marked"
        normalized["_renderHint"] = "whole-node-image-available"
        normalized["_childrenHint"] = "same-module"

    # Add metadata (include per-tree info with rect for multi-tree layout understanding)
    tree_summaries = []
    for i, (orig, norm) in enumerate(zip(all_trees, normalized_trees)):
        summary = {
            "index": i,
            "name": orig.get("objectName", "unnamed"),
            "type": orig.get("objectType", "unknown"),
            "totalNodes": count_nodes(norm),
            "exportCount": count_exportable(norm),
            "cdnCount": count_cdn(norm),
        }
        # Include rect info so consumers can understand spatial layout
        orig_rect = orig.get("rect", {})
        if orig_rect:
            summary["rect"] = {
                "x": orig_rect.get("x", 0),
                "y": orig_rect.get("y", 0),
                "width": orig_rect.get("width", 0),
                "height": orig_rect.get("height", 0),
            }
        tree_summaries.append(summary)

    normalized["_meta"] = {
        "imageId": raw_data.get("imageId", ""),
        "imagePath": raw_data.get("imagePath", ""),
        "width": raw_data.get("width", 0),
        "height": raw_data.get("height", 0),
        "imageUrls": image_urls,
        "treeCount": len(all_trees),
        "trees": tree_summaries,
    }

    return normalized


# ─── Semantic companion (mirrors _semantic.py logic) ───

COMPACT_STYLE_KEYS = {
    "width", "height", "left", "top", "right", "bottom",
    "display", "flexDirection", "gap", "flexWrap",
    "justifyContent", "alignItems", "flexGrow", "alignSelf",
    "fontSize", "fontWeight", "color", "textAlign", "lineHeight",
    "backgroundColor", "borderRadius", "padding", "opacity", "overflow",
    "border", "boxShadow", "background",
}


def compact_style(style: dict) -> dict:
    if not style:
        return {}
    return {k: v for k, v in style.items() if k in COMPACT_STYLE_KEYS}


def compact_node(node: dict) -> dict:
    """Strip non-essential metadata (same as _semantic.compact_node)."""
    result = {}
    keep = {"id", "name", "tag", "style", "textContent", "children",
            "src", "_exportSrc", "_exportHint", "_renderHint", "_childrenHint",
            "textSegments", "_layoutRole", "semantic"}
    for k, v in node.items():
        if k in keep:
            result[k] = v
    if "style" in result:
        result["style"] = compact_style(result["style"])
    if "semantic" in result and isinstance(result["semantic"], dict):
        s = result["semantic"]
        result["semantic"] = {k: s[k] for k in ("role", "prefer", "asset") if k in s}
    if "children" in result:
        result["children"] = [compact_node(c) for c in result["children"]]
    return result


def count_nodes(tree: dict) -> int:
    c = 1
    for child in tree.get("children", []):
        c += count_nodes(child)
    return c


def count_exportable(tree: dict) -> int:
    """Count nodes that should be exported as assets.
    Checks both legacy _exportHint and semantic.prefer fields."""
    sem = tree.get("semantic", {})
    is_export = (
        tree.get("_exportHint") == "slice"
        or sem.get("prefer") in ("asset", "review")
    )
    c = 1 if is_export else 0
    for child in tree.get("children", []):
        c += count_exportable(child)
    return c


def count_cdn(tree: dict) -> int:
    """Count nodes that have a CDN link (_exportSrc)."""
    c = 1 if tree.get("_exportSrc") else 0
    for child in tree.get("children", []):
        c += count_cdn(child)
    return c


# ─── Entry point ───

def normalize_file(input_path: str, output_path: Optional[str] = None,
                   tree_index: Optional[str] = None,
                   run_semantic: bool = True) -> str:
    """Read Ingee raw JSON, write normalized IMD-compatible JSON.
    
    If run_semantic=True (default), applies _semantic.py's normalize_tree
    as a second pass to annotate each node with semantic role/prefer/asset.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    normalized = normalize_ingee_data(raw, tree_index=tree_index)

    # Second pass: semantic annotation (role/prefer/asset)
    if run_semantic:
        try:
            from _semantic import normalize_tree as semantic_normalize, load_export_manifest
            manifest = load_export_manifest(input_path)
            normalized = semantic_normalize(normalized, manifest)
        except ImportError:
            # _semantic.py not available, skip
            pass
        except Exception as e:
            print(f"Warning: semantic annotation failed: {e}", file=sys.stderr)

    out = output_path or input_path.replace(".json", ".normalized.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    return out


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Normalize Ingee JSON → IMD-compatible format")
    parser.add_argument("input", help="Raw Ingee JSON file path")
    parser.add_argument("--output", "-o", help="Output path (default: *.normalized.json)")
    parser.add_argument("--compact", action="store_true", help="Output compact format")
    parser.add_argument("--ready", action="store_true", help="Print _ready.json summary")
    parser.add_argument("--tree-index", default="all",
                        help="Which trees to normalize: 'all' (default) or comma-separated indices like '0,2'")
    args = parser.parse_args()

    out = normalize_file(args.input, args.output, tree_index=args.tree_index)

    if args.ready:
        with open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        total = count_nodes(data)
        exportable = count_exportable(data)
        meta = data.get("_meta", {})
        tree_summaries = meta.get("trees", [])

        summary = {
            "file": out,
            "totalNodes": total,
            "exportCount": exportable,
            "frameName": data.get("name", ""),
            "treeCount": meta.get("treeCount", 1),
        }
        if tree_summaries:
            summary["trees"] = tree_summaries

        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Normalized: {out}")


if __name__ == "__main__":
    main()
