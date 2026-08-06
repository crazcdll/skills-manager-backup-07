#!/usr/bin/env python3
"""
D2C Measure - 测量节点间的距离、间隙、对齐关系

依赖序列化时写入的 `_abs` 绝对坐标（覆盖全节点，含 flex 子节点）。Diff 阶段
发现"这两块间距不对 / 没对齐"时，直接量出设计稿里的真实值，不靠肉眼估。

节点引用（任意位置可用）:
    id        纯节点 id，如 "457:89615"
    text:子串  textContent 含该子串的节点
    name:子串  显示名含该子串（命中"模块"和内部同名"标题"时，自动取最外层模块）
    --up N    解析后再向上爬 N 层父节点（手动上提到模块层）

用法:
    # 单节点：到 Frame 四边的边距
    python measure.py <json> <ref>

    # 两节点：水平/垂直间隙 + 中心偏移 + 对齐边 + 包含关系
    python measure.py <json> <refA> <refB>

    # 多节点（≥3）：自动判主轴，输出相邻间距 + 是否等距
    python measure.py <json> <ref1> <ref2> <ref3> ...

    # 关系模式（单引用）：自动找兄弟/邻居，免去手动定位
    python measure.py <json> <ref> --prev        # 与上/左相邻兄弟量距
    python measure.py <json> <ref> --next        # 与下/右相邻兄弟量距
    python measure.py <json> <ref> --neighbors   # 上/下/左/右四向最近邻 + 间距

示例:
    python measure.py frame.json "457:89615" "457:89650"
    python measure.py frame.json name:做任务赢积分 --prev   # = 和上一个模块的距离
    python measure.py frame.json name:积分钱包 --neighbors
"""

import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import (
    load_json, build_node_index, build_parent_index,
    compute_abs_boxes, parse_px, node_name,
    resolve_ref_or_die, box_or_die, neighbor_gaps,
)

TOL = 1.5  # 对齐/等距判定容差（设计稿 px）


def _r(v) -> float:
    return round(v, 1)


def _axis_gap(a0: float, a1: float, b0: float, b1: float):
    """一维区间关系。返回 {gap, overlap, order}。

    gap>0：两区间分离，nearest 边到 nearest 边的距离；
    gap<=0：两区间重叠，overlap=重叠长度，gap=-overlap。
    order: 'a-first' / 'b-first' / 'coincide'（沿该轴谁的起点更靠前）。
    """
    if a1 <= b0:
        return {"gap": _r(b0 - a1), "overlap": 0.0, "order": "a-first"}
    if b1 <= a0:
        return {"gap": _r(a0 - b1), "overlap": 0.0, "order": "b-first"}
    overlap = min(a1, b1) - max(a0, b0)
    order = "a-first" if a0 < b0 - TOL else ("b-first" if b0 < a0 - TOL else "coincide")
    return {"gap": _r(-overlap), "overlap": _r(overlap), "order": order}


def _node_brief(node, box):
    return {"id": node.get("id"), "name": node_name(node), "box": [_r(v) for v in box]}


def measure_pair(na, ba, nb, bb):
    ax0, ay0, aw, ah = ba
    bx0, by0, bw, bh = bb
    ax1, ay1 = ax0 + aw, ay0 + ah
    bx1, by1 = bx0 + bw, by0 + bh

    horizontal = _axis_gap(ax0, ax1, bx0, bx1)
    vertical = _axis_gap(ay0, ay1, by0, by1)

    acx, acy = ax0 + aw / 2, ay0 + ah / 2
    bcx, bcy = bx0 + bw / 2, by0 + bh / 2

    aligned = []
    if abs(ax0 - bx0) <= TOL: aligned.append("left")
    if abs(ax1 - bx1) <= TOL: aligned.append("right")
    if abs(acx - bcx) <= TOL: aligned.append("center-x")
    if abs(ay0 - by0) <= TOL: aligned.append("top")
    if abs(ay1 - by1) <= TOL: aligned.append("bottom")
    if abs(acy - bcy) <= TOL: aligned.append("center-y")

    containment = None
    if ax0 <= bx0 + TOL and ay0 <= by0 + TOL and ax1 >= bx1 - TOL and ay1 >= by1 - TOL:
        containment = "a-contains-b"
    elif bx0 <= ax0 + TOL and by0 <= ay0 + TOL and bx1 >= ax1 - TOL and by1 >= ay1 - TOL:
        containment = "b-contains-a"

    return {
        "a": _node_brief(na, ba),
        "b": _node_brief(nb, bb),
        "horizontal": horizontal,  # x 轴：a-first=A在左
        "vertical": vertical,      # y 轴：a-first=A在上
        "centerOffset": {"dx": _r(bcx - acx), "dy": _r(bcy - acy)},
        "aligned": aligned,
        "containment": containment,
    }


def measure_to_frame(node, box, root):
    x, y, w, h = box
    rw = parse_px(root.get("style", {}).get("width"))
    rh = parse_px(root.get("style", {}).get("height"))
    return {
        "node": _node_brief(node, box),
        "frame": [_r(rw), _r(rh)],
        "margin": {
            "left": _r(x),
            "top": _r(y),
            "right": _r(rw - (x + w)),
            "bottom": _r(rh - (y + h)),
        },
    }


def measure_sequence(nodes, boxes_list):
    """≥3 节点：自动判主轴，输出排序后的相邻间距 + 等距判定。"""
    centers = [(b[0] + b[2] / 2, b[1] + b[3] / 2) for b in boxes_list]
    x_spread = max(c[0] for c in centers) - min(c[0] for c in centers)
    y_spread = max(c[1] for c in centers) - min(c[1] for c in centers)
    axis = "row" if x_spread >= y_spread else "column"

    items = list(zip(nodes, boxes_list))
    key = (lambda nb: nb[1][0]) if axis == "row" else (lambda nb: nb[1][1])
    items.sort(key=key)

    gaps = []
    for (n0, b0), (n1, b1) in zip(items, items[1:]):
        if axis == "row":
            rel = _axis_gap(b0[0], b0[0] + b0[2], b1[0], b1[0] + b1[2])
        else:
            rel = _axis_gap(b0[1], b0[1] + b0[3], b1[1], b1[1] + b1[3])
        gaps.append({"from": n0.get("id"), "to": n1.get("id"), "gap": rel["gap"]})

    gap_vals = [g["gap"] for g in gaps]
    uniform = bool(gap_vals) and (max(gap_vals) - min(gap_vals) <= TOL)
    return {
        "axis": axis,
        "order": [n.get("id") for n, _ in items],
        "gaps": gaps,
        "uniform": uniform,
        "uniformGap": _r(sum(gap_vals) / len(gap_vals)) if uniform and gap_vals else None,
    }


def _sorted_siblings(target, boxes, parents):
    """返回 (sorted[(node, box)], axis)。axis 由父 flex 方向定，否则按中心点 spread 判。"""
    parent = parents.get(target.get("id"))
    if not parent:
        return [], "row"
    items = [(c, boxes[c["id"]]) for c in parent.get("children", [])
             if c.get("id") in boxes]
    pstyle = parent.get("style", {})
    if pstyle.get("display") == "flex":
        axis = "column" if pstyle.get("flexDirection") == "column" else "row"
    else:
        cx = [b[0] + b[2] / 2 for _, b in items]
        cy = [b[1] + b[3] / 2 for _, b in items]
        xs = (max(cx) - min(cx)) if cx else 0
        ys = (max(cy) - min(cy)) if cy else 0
        axis = "row" if xs >= ys else "column"
    items.sort(key=(lambda nb: nb[1][0]) if axis == "row" else (lambda nb: nb[1][1]))
    return items, axis


def measure_sibling(target, boxes, parents, which):
    """量 target 与其上/下（或左/右）相邻兄弟的距离。which: 'prev' | 'next'。"""
    items, axis = _sorted_siblings(target, boxes, parents)
    ids = [n.get("id") for n, _ in items]
    tid = target.get("id")
    if tid not in ids:
        print(f"错误: 节点 '{tid}' 没有可定位的父容器或兄弟", file=sys.stderr)
        sys.exit(1)
    i = ids.index(tid)
    j = i - 1 if which == "prev" else i + 1
    if j < 0 or j >= len(items):
        edge = "第一个" if which == "prev" else "最后一个"
        rel = "上一个" if which == "prev" else "下一个"
        print(f"错误: 节点 '{tid}' 在该容器内是{edge}，没有{rel}兄弟", file=sys.stderr)
        sys.exit(1)
    sib = items[j][0]
    a, b = (sib, target) if j < i else (target, sib)  # 视觉顺序：a 在前
    res = measure_pair(a, boxes[a["id"]], b, boxes[b["id"]])
    res["axis"] = axis
    res["relation"] = which
    return res


def measure_neighbors(target, boxes, parents):
    """列出 target 在同一父容器内、上/下/左/右四向各自最近的兄弟 + 间距。"""
    result = {"target": _node_brief(target, boxes[target["id"]])}
    result.update(neighbor_gaps(target, boxes, parents, TOL))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="测量节点间的距离、间隙、对齐关系",
        epilog="节点引用支持 id / text:子串 / name:子串；--up N 上提到模块层。",
    )
    parser.add_argument("json_file", help="设计稿 JSON 文件路径")
    parser.add_argument("node_refs", nargs="+",
                        help="一个或多个节点引用（id / text:子串 / name:子串）")
    parser.add_argument("--up", type=int, default=0, metavar="N",
                        help="解析后向上爬 N 层父节点（把内部文本上提到模块层）")
    rel = parser.add_mutually_exclusive_group()
    rel.add_argument("--prev", action="store_true", help="量与上/左相邻兄弟的距离（单引用）")
    rel.add_argument("--next", action="store_true", help="量与下/右相邻兄弟的距离（单引用）")
    rel.add_argument("--neighbors", action="store_true",
                     help="列出上/下/左/右四向最近邻 + 间距（单引用）")
    args = parser.parse_args()

    data = load_json(args.json_file)
    index = build_node_index(data)
    parents = build_parent_index(data)
    boxes = compute_abs_boxes(data)

    nodes = [resolve_ref_or_die(r, index, parents, args.up) for r in args.node_refs]

    if args.prev or args.next or args.neighbors:
        if len(nodes) != 1:
            print("错误: --prev/--next/--neighbors 只接受一个节点引用", file=sys.stderr)
            sys.exit(1)
        target = nodes[0]
        box_or_die(target, boxes, parents)  # 校验 target 有绝对盒
        if args.neighbors:
            result = measure_neighbors(target, boxes, parents)
        else:
            result = measure_sibling(target, boxes, parents, "prev" if args.prev else "next")
    else:
        boxes_list = [box_or_die(n, boxes, parents) for n in nodes]
        if len(nodes) == 1:
            result = measure_to_frame(nodes[0], boxes_list[0], data)
        elif len(nodes) == 2:
            result = measure_pair(nodes[0], boxes_list[0], nodes[1], boxes_list[1])
        else:
            result = measure_sequence(nodes, boxes_list)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
