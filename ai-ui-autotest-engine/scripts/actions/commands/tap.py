"""tap / tap-text 独立命令。"""

import json

from core.errors import DeviceError, UsageError
from context import get_platform_ops
from core.util.case_utils import resolve_case_path, _timer_start
from screen_state.inspect_tree import (
    inspect_tree_find_center, hit_nodes_at,
    invalidate_cache,
)
from actions.handlers.base import _collect_similar_texts
from actions.handlers.tap import _low_confidence_warning


def _cmd_tap_text(args):
    """独立命令：文本点击。"""
    if getattr(args, 'step_dir', None):
        _timer_start(resolve_case_path(args.step_dir))
    r = inspect_tree_find_center(args.text, detail=True)

    if r and r.get("unresolved"):
        print(f"AMBIGUOUS: 「{args.text}」命中文本节点但自身不可点击，且未找到可点击的祖先容器")
        subtree = r.get("subtree")
        if subtree:
            print(f"  目标周边的结构邻域（JSON 树，class 带\"(骨架)\"的节点仅用于连接结构，"
                  f"本身不是候选目标）：")
            print(f"  {json.dumps(subtree, ensure_ascii=False)}")
        raise UsageError(
            "请结合上方结构判断真实点击目标（可能是同级/子级的其他控件，如 CheckBox），"
            "改用 cli.py tap --x <x> --y <y> 指定精确坐标重试"
        )

    if not r or not r.get("center"):
        similar = _collect_similar_texts(args.text)
        print(f"NOT_FOUND: {args.text}")
        if similar:
            print(f"  💡 页面上未找到「{args.text}」，但发现以下相似文案：")
            for s_text, s_reason in similar[:5]:
                print(f"     · 「{s_text}」— {s_reason}")
            print(f"  💡 也可用 find-text --text \"{args.text}\" 查看详细匹配候选")
        else:
            print(f"  💡 页面上未找到「{args.text}」及任何相似文案，请确认目标页面是否正确加载")
        return 1

    c = r["center"]
    if r["overlap"]:
        print(f"AMBIGUOUS: 「{args.text}」目标区域被以下已知调试控件完全遮挡：")
        for h in r["overlap"]:
            print(f"     · 「{h['text']}」class={h['class_name']} "
                  f"center={h['center']} bounds={h['bounds']} area={h['area']}")
        raise UsageError(
            "请结合最新截图判断真实目标，改用 cli.py tap --x <x> --y <y> 指定精确坐标重试（换新 sid）"
        )

    ops = get_platform_ops()
    if not ops.tap(c[0], c[1]):
        raise DeviceError(f"TAP FAIL: {args.text} @ {c}")
    print(f"TAP {args.text} @ {c}")
    warning = _low_confidence_warning(args.text, r)
    if warning:
        print(f"  {warning}")


def _cmd_tap(args):
    """独立命令：坐标点击。"""
    ops = get_platform_ops()
    if not ops.tap(args.x, args.y):
        raise DeviceError(f"TAP FAIL @ ({args.x},{args.y})")
    print(f"TAP @ ({args.x},{args.y})")

    hits = hit_nodes_at(args.x, args.y)
    if hits:
        print(f"  [TAP-HIT] ({args.x},{args.y}) 命中 {len(hits)} 个节点:")
        for h in hits:
            c = "✅可点击" if h["clickable"] else " "
            t = f' text="{h["text"]}"' if h["text"] else ""
            print(f"    → {h['class']} id={h['id']} {c}{t}")
            print(f"       center={h['center']} bounds={h['bounds']}")
    else:
        print(f"  [TAP-HIT] ({args.x},{args.y}) 未命中任何节点")