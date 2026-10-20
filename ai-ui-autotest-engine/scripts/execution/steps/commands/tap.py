"""tap / tap-text 独立命令。"""

from cli_utils import finish_action_result
from shared.errors import DeviceError
from shared.context import get_platform_ops
from shared.case_utils import resolve_case_path, _timer_start
from execution.screen.inspect_tree import (
    inspect_tree_find_center, hit_nodes_at,
    invalidate_cache,
)
from execution.screen.tree_index import build_targets, render_candidates
from execution.steps.handlers.base import _collect_similar_texts, action_hit_from_info


def _cmd_tap_text(args):
    """独立命令：文本点击。"""
    if getattr(args, 'step_dir', None):
        _timer_start(resolve_case_path(args.step_dir))
    r = inspect_tree_find_center(args.text, detail=True)

    if r and r.get("unresolved"):
        print(f"AMBIGUOUS: 「{args.text}」命中文本节点但自身不可点击，且未找到可点击的祖先容器")
        _anchor_y = r.get("center")[1] if r.get("center") else None
        _targets = build_targets(wait_sec=1)
        print("  🔍 锚点行（同一视觉行）的可点击目标（✅=可点击，坐标为设备绝对坐标）：")
        print(render_candidates(_targets, "clickable_near", anchor=args.text, anchor_y=_anchor_y))
        # handoff（需换策略，非错误）→ 统一收口：HANDOFF 码 + 「改用坐标点击」建议
        return finish_action_result("TAP-TEXT", args.text,
                                    {"ok": None, "ctx": {"reason": "UNRESOLVED"}})

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
        return finish_action_result("TAP-TEXT", args.text,
                                    {"ok": None, "ctx": {"reason": "TEXT_NOT_FOUND"}})

    c = r["center"]
    if r["overlap"]:
        print(f"AMBIGUOUS: 「{args.text}」目标区域被以下已知调试控件完全遮挡：")
        for h in r["overlap"]:
            print(f"     · 「{h['text']}」class={h['class_name']} "
                  f"center={h['center']} bounds={h['bounds']} area={h['area']}")
        return finish_action_result("TAP-TEXT", args.text,
                                    {"ok": None, "ctx": {"reason": "BLOCKED"}})

    ops = get_platform_ops()
    if not ops.tap(c[0], c[1]):
        raise DeviceError(f"TAP FAIL: {args.text} @ {c}")
    print(f"TAP {args.text} @ {c}")
    # 非字面精确命中（子串语义等价 / 非 native 探针）→ 提示人工确认。
    # 独立命令不落步骤记录，与 step 路径的 action_hit 同一判定实现。
    hit = action_hit_from_info(args.text, r)
    if hit:
        print(f"  ⚠️  {hit['reason']}（独立命令不落步骤记录，仅提示）")


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