"""
Utilities for building and consuming semantic companion files.

The main companion schema is intentionally thin: keep the original design tree,
and only add a compact ``semantic`` object when a node carries stable,
agent-useful meaning.
"""

import copy
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


SEMANTIC_VERSION = "2.0"
SEMANTIC_SUFFIX = ".semantic.json"
SEMANTIC_META_SUFFIX = ".semantic.meta.json"

LEGACY_MAGIC_FIELDS = {
    "_exportHint",
    "_exportReason",
    "_autoTag",
    "_exportSrc",
    "_exportLocal",
    "_exportCdn",
    "_exportFormat",
    "_exportScale",
    "_renderHint",
    "_childrenHint",
}

SVG_TYPES = {"PEN", "VECTOR", "STAR", "POLYGON", "LINE"}
VECTOR_LIKE_TYPES = SVG_TYPES | {"BOOLEAN_OPERATION"}

ROLE_FROM_LEGACY = {
    "icon": "icon",
    "icon_composite": "icon",
    "deco": "decorative_graphic",
    "dynamic": "text_bearing_graphic",
    "statusbar": "system_ui",
}

STRATEGY_MAP = {
    "prefer_asset": "asset",
    "prefer_dom": "dom",
    "allow_both": "either",
    "needs_review": "review",
    "ignore": "ignore",
}

EXPORT_REASONS = {
    "designer_marked",
    "svg_node",
    "svg_majority_group",
    "auto_tag_icon",
    "auto_tag_icon_composite",
    "auto_tag_deco",
}

# ─── Compact: essential CSS keys for minimal-context output ───

COMPACT_STYLE_KEYS = {
    "width", "height", "left", "top", "right", "bottom",
    "display", "flexDirection", "gap", "flexWrap",
    "justifyContent", "alignItems", "flexGrow", "alignSelf",
    "fontSize", "fontWeight", "color", "textAlign", "lineHeight",
    "backgroundColor", "borderRadius", "padding", "opacity", "overflow",
    "border", "boxShadow", "background",
}


def compact_style(style: dict) -> dict:
    """Keep only essential CSS keys for minimal output."""
    if not style:
        return {}
    return {k: v for k, v in style.items() if k in COMPACT_STYLE_KEYS}


def compact_node(node: dict) -> dict:
    """Strip non-essential metadata from a single node dict (mutates a copy)."""
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


# ─── File I/O ──────────────────────────────────────────────────


def _read_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, payload: Dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def semantic_json_path(raw_json_path: str) -> str:
    if raw_json_path.endswith(SEMANTIC_SUFFIX):
        return raw_json_path
    if raw_json_path.endswith(".json"):
        return raw_json_path[:-5] + SEMANTIC_SUFFIX
    return raw_json_path + SEMANTIC_SUFFIX


def semantic_meta_path(raw_json_path: str) -> str:
    semantic_path = semantic_json_path(raw_json_path)
    if semantic_path.endswith(SEMANTIC_SUFFIX):
        return semantic_path[: -len(SEMANTIC_SUFFIX)] + SEMANTIC_META_SUFFIX
    return semantic_path + ".meta.json"


def resolve_preferred_json_path(input_path: str) -> str:
    if input_path.endswith(SEMANTIC_SUFFIX):
        return input_path
    sibling = semantic_json_path(input_path)
    if os.path.exists(sibling):
        return sibling
    return input_path


def load_raw_json(input_path: str) -> Dict:
    return _read_json(input_path)


def load_export_manifest(raw_json_path: str) -> Dict[str, Dict]:
    manifest_path = os.path.join(os.path.dirname(os.path.abspath(raw_json_path)), "_exports.json")
    if not os.path.exists(manifest_path):
        return {}
    try:
        data = _read_json(manifest_path)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_px(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.endswith("px"):
        text = text[:-2]
    try:
        return float(text)
    except ValueError:
        return 0.0


def _clean_payload(payload: Dict) -> Dict:
    cleaned = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, dict):
            nested = _clean_payload(value)
            if nested:
                cleaned[key] = nested
        elif isinstance(value, list):
            nested = []
            for item in value:
                if isinstance(item, dict):
                    item_clean = _clean_payload(item)
                    if item_clean:
                        nested.append(item_clean)
                elif item not in (None, "", [], {}):
                    nested.append(item)
            if nested:
                cleaned[key] = nested
        else:
            cleaned[key] = value
    return cleaned


def _looks_like_system_ui(node: Dict) -> bool:
    if node.get("_autoTag") == "statusbar":
        return True
    name = (node.get("name") or "").lower()
    keywords = ("statusbar", "status bar", "wifi", "cellular", "battery", "9:41", "信号", "电池")
    return any(keyword in name for keyword in keywords)


def _build_primary_asset(node: Dict, manifest_entry: Optional[Dict]) -> Optional[str]:
    if manifest_entry:
        return manifest_entry.get("cdnUrl") or manifest_entry.get("file")
    if node.get("_exportSrc"):
        return node.get("_exportSrc")
    return None


def _text_scope(has_text: bool, has_text_subtree: bool, mixed_text: bool) -> str:
    if mixed_text:
        return "mixed"
    if has_text:
        return "self"
    if has_text_subtree:
        return "subtree"
    return "none"


def _role_from_traits(node: Dict, traits: Dict) -> Tuple[str, str]:
    legacy = node.get("_autoTag")
    if legacy in ROLE_FROM_LEGACY:
        return ROLE_FROM_LEGACY[legacy], f"legacy_auto_tag:{legacy}"

    if traits["looks_system_ui"]:
        return "system_ui", "system_ui"
    if traits["has_image_source"]:
        return "content_image", "image_source"
    if traits["has_text"] and node.get("tag") == "span":
        return "text", "contains_text"
    if not traits["has_children"] and traits["vector_self"] and traits["text_scope"] != "none":
        return "text_bearing_graphic", "vector_with_text"
    if not traits["has_children"] and traits["vector_self"]:
        return "vector_graphic", "vector_node"
    return "composite", "derived"


def _prefer_from_traits(role: str, traits: Dict, asset: Optional[str], role_reason: str) -> Tuple[str, List[str]]:
    why: List[str] = []

    export_reason = traits["export_reason"]
    if export_reason:
        why.append(export_reason)
    if asset:
        why.append("asset_available")
    if role_reason and role_reason != "derived":
        why.append(role_reason)

    if role == "system_ui":
        return "ignore", list(dict.fromkeys(why))
    if role in {"icon", "decorative_graphic"}:
        return "asset", list(dict.fromkeys(why))
    if role in {"text", "text_bearing_graphic"}:
        return "dom", list(dict.fromkeys(why))
    if role == "content_image":
        return "asset", list(dict.fromkeys(why))
    if role == "vector_graphic":
        if asset or traits["export_candidate"]:
            if not asset:
                why.append("asset_missing")
            return "asset", list(dict.fromkeys(why))
        why.append("asset_missing")
        return "review", list(dict.fromkeys(why))

    if traits["export_candidate"]:
        why.append("boundary_ambiguous")
        return "review", list(dict.fromkeys(why))
    return "either", list(dict.fromkeys(why))


def _build_semantic(role: str, prefer: str, why: List[str], asset: Optional[str], traits: Dict) -> Optional[Dict]:
    if role == "text" and prefer == "dom":
        return None
    if role == "content_image" and prefer == "asset":
        return None

    payload = {
        "role": role,
        "prefer": prefer,
        "why": why,
        "asset": asset,
    }

    cleaned = _clean_payload(payload)
    if cleaned.get("role") == "composite" and cleaned.get("prefer") == "either" and "asset" not in cleaned:
        return None
    return cleaned


def normalize_tree(raw_root: Dict, export_manifest: Optional[Dict[str, Dict]] = None) -> Dict:
    export_manifest = export_manifest or {}

    def _walk(node: Dict) -> Tuple[Dict, Dict]:
        raw_children = node.get("children", [])
        child_results = [_walk(child) for child in raw_children]
        children = [item[0] for item in child_results]
        style = node.get("style", {})
        node_id = node.get("id")
        manifest_entry = export_manifest.get(node_id) if node_id else None
        asset = _build_primary_asset(node, manifest_entry)

        has_text = bool((node.get("textContent") or "").strip())
        has_text_subtree = has_text or any(item[1]["has_text_subtree"] for item in child_results)
        mixed_text = len(node.get("textSegments", [])) > 1
        vector_self = node.get("tag") == "svg" or (node.get("_mgType") in VECTOR_LIKE_TYPES)
        has_vector_subtree = vector_self or any(item[1]["has_vector_subtree"] for item in child_results)

        traits = {
            "export_candidate": node.get("_exportHint") == "slice",
            "export_reason": node.get("_exportReason"),
            "designer_marked": node.get("_exportReason") == "designer_marked",
            "has_children": bool(raw_children),
            "has_text": has_text,
            "has_text_subtree": has_text_subtree,
            "text_scope": _text_scope(has_text, has_text_subtree, mixed_text),
            "vector_self": vector_self,
            "has_vector_subtree": has_vector_subtree,
            "has_image_source": bool(node.get("src")),
            "looks_system_ui": _looks_like_system_ui(node),
            "is_instance": node.get("_mgType") == "INSTANCE",
            "size": [round(_parse_px(style.get("width")), 2), round(_parse_px(style.get("height")), 2)],
        }

        role, role_reason = _role_from_traits(node, traits)
        prefer, why = _prefer_from_traits(role, traits, asset, role_reason)
        semantic = _build_semantic(role, prefer, why, asset, traits)

        normalized = {}
        for key, value in node.items():
            if key == "children":
                continue
            if key in LEGACY_MAGIC_FIELDS:
                continue
            normalized[key] = copy.deepcopy(value)
        if children:
            normalized["children"] = children
        if semantic:
            normalized["semantic"] = semantic

        internal = {
            "has_text_subtree": has_text_subtree,
            "has_vector_subtree": has_vector_subtree,
        }
        return normalized, internal

    normalized_root, _ = _walk(raw_root)
    return normalized_root


def build_semantic_payload(raw_json_path: str) -> Tuple[Dict, Dict]:
    raw = load_raw_json(raw_json_path)
    manifest = load_export_manifest(raw_json_path)
    semantic = normalize_tree(raw, manifest)
    meta = {
        "kind": "explore-design-tree-semantic-companion",
        "semanticVersion": SEMANTIC_VERSION,
        "inputFile": os.path.abspath(raw_json_path),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "hasExportManifest": bool(manifest),
        "manifestEntries": len(manifest),
        "schema": {"field": "semantic", "keys": ["role", "prefer", "why", "asset"]},
    }
    return semantic, meta


def normalize_file(raw_json_path: str, output_path: Optional[str] = None,
                   meta_path: Optional[str] = None) -> Tuple[str, str]:
    semantic, meta = build_semantic_payload(raw_json_path)
    semantic_path = output_path or semantic_json_path(raw_json_path)
    semantic_meta = meta_path or semantic_meta_path(raw_json_path)
    _write_json(semantic_path, semantic)
    _write_json(semantic_meta, meta)
    return semantic_path, semantic_meta
