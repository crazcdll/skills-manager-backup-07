#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一目标模型守卫 —— 固化本次重构的口径，防止回退。

用法：
    python3 scripts/dev/check_target_model.py

覆盖三组不变量：

  A. 跨渲染层节点聚合（tree_source）
     parent 索引重基 / children_idx / depth / (文本,中心) 去重 / WebView 容器文本抑制
  B. 目标模型（tree_index）
     role 推导（显式优先 + 类名大小写无关）/ source 透传 / parent_chain（跨层不接链）/
     三个渲染出口（目录 md / 聚焦候选 / 锚点邻域）/ 统一落盘命名
  C. 结论口径
     needs_review（通过且非 exact）/ 动作命中方式 action_hit /
     hook 路由按 (动作意图, reason)

退出码：0 全部通过 / 1 有失败。

【为什么需要它】这几轮重构连续改动了两层结构（目标模型 + 探针契约），
其中「唯一子串兜底算不算确定性」「输入动作能否复用点击模板」「H5 节点如何并入」
都是易回退的口径。本脚本把它们固化为一条命令，改坏了立刻可见。
单测不触碰设备：节点由测试自行构造，`_get_viewport` 被短路。
"""
import argparse
import contextlib
import io
import os
import re
import sys
import tempfile
import traceback

# 源树零字节码：本文件是进程入口，开关必须在引擎包导入之前生效。
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.steps.handlers.base import action_hit_from_info, hit_verdict
from execution.steps.pipeline.step_context import _resolve_sid_conflict
from execution.assertions.engine import action_hit_needs_review, compute_needs_review
from execution.engine.sop.on_fail import intent_of_action, reason_hook_template
from execution.screen import tree_index
from execution.screen.tree_index import (
    build_targets, dump_index, find_anchor, render_candidates,
    render_neighborhood, render_targets_md, _role_of, _is_target,
    resolve_anchor_clickable, render_anchor_resolution,
)
from execution.screen.tree_source import (
    _dedup_key, _link_probe_nodes, _merge_renderer_nodes,
)

# 单测不触碰设备：绕开 _get_viewport() 的平台查询（真实运行时它自带 try/except）
tree_index._get_viewport = lambda: None


# ═══════════════════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════════════════

def _node(text=None, x=0, y=0, w=100, h=40, clickable=False, class_name="",
          parent=None, source=None, role=None, scrollable=False,
          content_desc=None, children_idx=None):
    """构造一个符合 UiNode 契约的节点（默认按 native 形状）。"""
    node = {
        "text": text,
        "content_desc": content_desc,
        "all_text": text if text else content_desc,
        "merged_text": "",
        "x": x, "y": y, "w": w, "h": h,
        "clickable": clickable,
        "checked": None,
        "depth": 0,
        "parent": parent,
        "children_idx": children_idx if children_idx is not None else [],
        "class_name": class_name,
        "m_id": None,
        "scrollable": scrollable,
        "scroll_dir": None,
        "in_viewport": True,
        "viewport_offset": 0,
    }
    if source is not None:
        node["source"] = source
    if role is not None:
        node["role"] = role
    return node


# ═══════════════════════════════════════════════════════════════════
# A. 跨渲染层节点聚合（tree_source）
# ═══════════════════════════════════════════════════════════════════

def test_link_probe_nodes_rebases_parent_and_builds_tree():
    probe = [
        _node(text="父", parent=-1, source="webview"),
        _node(text="子", parent=0, source="webview"),
        _node(text="孙", parent=1, source="webview"),
    ]
    _link_probe_nodes(probe, base=5)
    assert [n["parent"] for n in probe] == [None, 5, 6], "parent 需重基到合并列表索引"
    assert probe[0]["children_idx"] == [6], "children_idx 需重基"
    assert probe[1]["children_idx"] == [7]
    assert [n["depth"] for n in probe] == [0, 1, 2], "depth 需沿 parent 链累计"


def test_link_probe_nodes_tolerates_bad_parent_index():
    probe = [_node(text="A", parent=99, source="webview")]
    _link_probe_nodes(probe, base=0)
    assert probe[0]["parent"] is None, "越界 parent 必须置 None，避免脏索引"

    probe2 = [_node(text="B", parent=None, source="webview")]
    _link_probe_nodes(probe2, base=3)
    assert probe2[0]["parent"] is None and probe2[0]["depth"] == 0


def test_dedup_key_shape():
    assert _dedup_key(_node(text="x", x=0, y=0, w=10, h=10)) == ("x", 5, 5)
    assert _dedup_key(_node(text="x", x=None, y=None)) == ("x", None, None)
    assert _dedup_key(_node(text=None, content_desc="d", x=None, y=None)) == ("d", None, None)
    assert _dedup_key(_node(text=None, x=None, y=None)) is None, "无文本无坐标不参与去重"


def test_merge_keeps_native_and_drops_exact_duplicates():
    native = [_node(text="已优惠¥175", x=100, y=1000, w=200, h=40, clickable=True)]
    probe = [
        _node(text="已优惠¥175", x=100, y=1000, w=200, h=40, clickable=True, source="webview"),
        _node(text="房费", x=100, y=1100, w=80, h=30, source="webview"),
    ]
    merged = _merge_renderer_nodes(native, probe)
    assert len(merged) == 2, "同 (文本,中心) 的元素只保留 native 一份"
    assert merged[0].get("source") in (None, "native")
    assert merged[1]["text"] == "房费" and merged[1]["source"] == "webview"


def test_merge_without_probe_nodes_is_noop():
    native = [_node(text="A")]
    assert _merge_renderer_nodes(native, []) is native


def test_webview_gate_skips_when_native_unavailable():
    """闸门：native 采不到时也跳过探针（偏移不可信，且避免每步白扫 socket）。"""
    from execution.screen.tree_source import _has_webview_container as gate
    assert gate([]) is False, "native 为空 → 无法定位容器 → 不问探针"
    assert gate(None) is False
    assert gate([_node(text="提交", class_name="Button")]) is False, "无 WebView 容器 → 不问探针"
    assert gate([_node(class_name="com.x.X5WebView")]) is True, "有 WebView 容器 → 必须问探针"
    assert gate([_node(class_name="com.x.CustomWebViewImpl")]) is True


def test_merge_suppresses_webview_container_blob_text():
    blob = "预约须知" * 20  # 长文本（≥阈值）→ 视为容器文本快照，需抑制
    native = [
        _node(text="通用文案", x=0, y=0, w=100, h=30, class_name="ReactTextView"),
        _node(text=blob, x=0, y=200, w=700, h=400, class_name="com.x.X5WebView"),
        _node(text="短标签", x=0, y=300, w=100, h=30, class_name="com.x.X5WebView"),
    ]
    probe = [_node(text="H5 按钮", x=10, y=210, w=100, h=40, clickable=True, source="webview")]
    merged = _merge_renderer_nodes(native, probe)
    container = merged[1]
    assert container["all_text"] == "" and container["text"] is None, "长容器文本需抑制"
    assert merged[2]["all_text"] == "短标签", "短文本不抑制（可能是容器自身标签）"
    assert merged[-1]["text"] == "H5 按钮"


# ═══════════════════════════════════════════════════════════════════
# B-1. role 推导与目标筛选
# ═══════════════════════════════════════════════════════════════════

def test_role_explicit_wins_over_class_guess():
    # DOM 适配器会显式给 role：input 元素即使 clickable 也必须是 input
    assert _role_of(_node(class_name="input", clickable=True, role="input")) == "input"
    assert _role_of(_node(class_name="a", clickable=True, role="button")) == "button"
    assert _role_of(_node(class_name="span", role="text")) == "text"


def test_role_class_rules_case_insensitive():
    assert _role_of(_node(class_name="com.x.EditText", clickable=True)) == "input"
    assert _role_of(_node(class_name="edittext", clickable=True)) == "input", "类名小写也要命中"
    assert _role_of(_node(class_name="com.facebook.react.ReactTextView")) == "text"
    assert _role_of(_node(class_name="android.widget.Button")) == "button"
    assert _role_of(_node(class_name="X5WebView", scrollable=True)) == "scrollable"


def test_role_fallbacks():
    assert _role_of(_node(class_name="Unknown", clickable=True)) == "button"
    assert _role_of(_node(class_name="Unknown", scrollable=True)) == "scrollable"
    assert _role_of(_node(class_name="Unknown")) == "text", "无类名无 clickable → 默认 text"


def test_role_recognizes_react_native_textinput():
    """RN 输入框类名带混淆尾段：com.facebook.react.views.textinput.f 必须识别为 input。

    回归：此前 _short_class 只取最后一段（→ "f"），role 规则按后缀匹配 →
    输入框被漏判成 button/text，导致「表单识别不到」。
    """
    from execution.screen.tree_index import _short_class
    assert _short_class("com.facebook.react.views.textinput.f") == "textinput.f"
    assert _short_class("com.facebook.react.views.text.j") == "text.j"
    assert _role_of(_node(class_name="com.facebook.react.views.textinput.f", clickable=True)) == "input"
    assert _role_of(_node(class_name="com.facebook.react.views.textinput.ReactEditText", clickable=True)) == "input"
    # 空输入框也要进目标集合（class 含 textinput，即使无文案）
    assert _is_target(_node(class_name="com.facebook.react.views.textinput.f")) is True


def test_resolve_anchor_editable_from_react_native_row():
    """RN 表单行（标签 + textinput）→ 引擎能从锚点行内自行选中输入框，无需 hook。"""
    from execution.screen.tree_index import build_targets, resolve_anchor_editable, render_anchor_row
    nodes = [
        _node(text=None, x=0, y=180, w=700, h=40,
              class_name="com.facebook.react.views.view.f", parent=None),                      # 行容器（被过滤）
        _node(text="中文姓名", x=20, y=185, w=100, h=30, parent=0,
              class_name="com.facebook.react.views.text.j"),                                   # 标签
        _node(text=None, x=140, y=185, w=480, h=30, parent=0,
              class_name="com.facebook.react.views.textinput.f", clickable=True),             # 输入框
    ]
    targets = build_targets(nodes=nodes, wait_sec=0)
    r = resolve_anchor_editable(targets, "中文姓名")
    assert r["found"] is True
    assert r["picked"] is not None, "textinput.f 必须被识别为 role=input 并选中"
    assert r["picked"]["role"] == "input"

    # 选择器行（无输入框）→ picked=None，给宽度降序的 guess 供「截图+结构」推断
    sel = [
        _node(text="住客姓名", x=20, y=185, w=100, h=30, parent=None,
              class_name="com.facebook.react.views.text.j"),
        _node(text="王事成", x=300, y=185, w=300, h=30, clickable=True, parent=None,
              class_name="com.facebook.react.views.view.f"),
    ]
    targets2 = build_targets(nodes=sel, wait_sec=0)
    r2 = resolve_anchor_editable(targets2, "住客姓名")
    assert r2["picked"] is None
    assert r2["guess"] and r2["guess"][0]["text"] == "王事成", "最宽成员排第一（疑似输入区域）"
    assert "width=300" in render_anchor_row(targets2, "住客姓名")


def test_is_target_filters_layout_and_debug_nodes():
    assert _is_target(_node(text="有文案")) is True
    assert _is_target(_node(class_name="EditText")) is True, "空输入框也要保留"
    assert _is_target(_node(clickable=True)) is True, "空的可点击图标按钮要保留"
    assert _is_target(_node(scrollable=True)) is True
    assert _is_target(_node(class_name="com.x.DebugPanel")) is False, "调试控件过滤"
    assert _is_target(_node()) is False, "纯布局容器（无文案不可点）过滤"


# ═══════════════════════════════════════════════════════════════════
# B-2. build_targets：编号 / 排序 / 上下文 / 祖先链 / source
# ═══════════════════════════════════════════════════════════════════

def _sample_nodes():
    """2 行布局：行容器（不可点） + 子元素；另有一个 H5 输入框 + 一个调试控件。"""
    return [
        _node(text=None, x=0, y=0, w=700, h=100, class_name="ReactView", parent=None),      # 0 容器（被过滤）
        _node(text="联系手机", x=80, y=760, w=120, h=30, parent=0, class_name="j"),          # 1 标签
        _node(text="请输入手机号", x=400, y=760, w=200, h=40, parent=0,
              class_name="input", clickable=True, role="input", source="webview"),           # 2 H5 输入框
        _node(text="提交", x=400, y=900, w=120, h=44, parent=None,
              clickable=True, class_name="button"),                                          # 3 native 按钮
        _node(text=None, x=0, y=1200, w=700, h=80, parent=None,
              class_name="com.x.DebugOverlay"),                                              # 4 调试控件（被过滤）
    ]


def test_build_targets_structure():
    result = build_targets(nodes=_sample_nodes(), wait_sec=0)
    assert result["available"] is True
    targets = result["targets"]
    assert result["total"] == len(targets) == 3, "容器与调试控件需被过滤，只剩 3 个目标"

    # 排序：按 y 从上到下；编号连续
    assert [t["id"] for t in targets] == ["e1", "e2", "e3"]
    ys = [t["center"][1] for t in targets]
    assert ys == sorted(ys), "需按 y 从上到下排序"

    by_text = {t["text"]: t for t in targets}
    # source：native 缺省补 native，H5 透传 webview
    assert by_text["联系手机"]["source"] == "native"
    assert by_text["请输入手机号"]["source"] == "webview"
    assert by_text["请输入手机号"]["role"] == "input"
    # bounds 由 x/y/w/h 推出（目标模型的坐标契约）
    input_box = by_text["请输入手机号"]
    assert input_box["bounds"] == [400, 760, 600, 800]
    assert input_box["center"] == [500, 780]


def test_build_targets_context_and_parent_chain():
    targets = build_targets(nodes=_sample_nodes(), wait_sec=0)["targets"]
    by_text = {t["text"]: t for t in targets}
    # context：顺序上下文（前 2 个目标 id）
    assert by_text["请输入手机号"]["context"] == ["e1"]
    assert by_text["提交"]["context"] == ["e1", "e2"]
    # parent_chain：仅收录"也在目标集合中"的祖先
    assert by_text["联系手机"]["parent_chain"] == [], "父容器被过滤 → 链为空"
    # 跨渲染层不接链：H5 节点的祖先在 DOM 层，不与 native 容器相连
    assert by_text["请输入手机号"]["parent_chain"] == []


def test_build_targets_carries_parent_chain_when_ancestor_is_target():
    nodes = [
        _node(text="整行容器", x=0, y=0, w=700, h=80, clickable=True, class_name="button"),
        _node(text="行内文案", x=20, y=20, w=200, h=40, parent=0, class_name="j"),
    ]
    targets = build_targets(nodes=nodes, wait_sec=0)["targets"]
    by_text = {t["text"]: t for t in targets}
    assert by_text["行内文案"]["parent_chain"] == ["e1"], "父容器本身是目标时必须入链"


def test_build_targets_unavailable_when_no_nodes():
    assert build_targets(nodes=[], wait_sec=0)["available"] is True
    assert build_targets(nodes=[], wait_sec=0)["targets"] == []


# ═══════════════════════════════════════════════════════════════════
# B-3. 出口：候选 / 邻域 / 目录
# ═══════════════════════════════════════════════════════════════════

def _cand_targets():
    return build_targets(nodes=_sample_nodes(), wait_sec=0)


def test_render_candidates_substring_prefers_clickable_and_marks_source():
    out = render_candidates(_cand_targets(), "substring", anchor="请输入手机号")
    assert "请输入手机号" in out and "[webview]" in out, "H5 来源需标注"
    assert out.splitlines()[0].startswith("   [1] ✅"), "可点击候选置顶"


def test_render_candidates_substring_needs_anchor():
    out = render_candidates(_cand_targets(), "substring", anchor="")
    assert out.startswith("（无："), "无锚点应给空提示而不是抛错"


def test_render_candidates_editable_profile():
    out = render_candidates(_cand_targets(), "editable")
    assert "请输入手机号" in out
    assert "联系手机" not in out, "editable 只列 role=input"


def test_render_candidates_editable_falls_back_when_role_missing():
    # 没有任何 role=input 时，不能静默返回空：要给页面文本目标清单
    nodes = [_node(text="姓名", x=0, y=0, w=80, h=30, class_name="j")]
    out = render_candidates(build_targets(nodes=nodes, wait_sec=0), "editable")
    assert "未识别出 role=input" in out and "姓名" in out


def test_render_candidates_non_clickable_and_clickable_near():
    targets = _cand_targets()
    out_nc = render_candidates(targets, "non_clickable")
    assert "联系手机" in out_nc and "提交" not in out_nc

    out_near = render_candidates(targets, "clickable_near", anchor_y=760, limit=5)
    assert "请输入手机号" in out_near, "同行（y=760）可点击目标应入选"
    assert "提交" not in out_near, "y=900 超出 ±150 邻域，不应入选"


def test_render_candidates_unknown_profile():
    assert render_candidates(_cand_targets(), "no_such_profile") == "（无候选）"


def test_blur_anchor_candidates_exclude_covered_texts():
    """元守卫：失焦候选必须是「惰性落点」——不可点击，且落点未被可点击容器覆盖。

    真实缺陷：纯文本常嵌在整行按钮里（「预计到店」在「预计到店09月28日…」按钮行内），
    点它的坐标会命中覆盖在上面的可点击容器 → 打开时间选择弹窗，污染后续步骤的页面状态
    与步骤截图。候选清单必须与 inspect_tree_find_blur_anchor 的落点校验同口径，否则 AI
    从清单里二次选中的仍是引擎必然拒绝的候选 → 空转。
    """
    nodes = [
        _node(text="预计到店", x=80, y=860, w=140, h=30, parent=None, class_name="j"),
        _node(text="预计到店09月28日 06:00前 房间将整晚保留", x=0, y=850, w=700, h=60,
              parent=None, clickable=True, class_name="button"),
        _node(text="联系手机", x=80, y=760, w=120, h=30, parent=None, class_name="j"),
    ]
    out = render_candidates(build_targets(nodes=nodes, wait_sec=0), "non_clickable")
    assert "联系手机" in out, "真正的惰性文本应保留为候选"
    assert "预计到店" not in out, "被可点击行覆盖的文本不得作为失焦候选（点它会误触弹窗）"


def test_render_neighborhood_clickable_and_editable():
    targets = _cand_targets()
    out = render_neighborhood(targets, "联系手机")
    assert "祖先链" in out and "联系手机" in out
    assert "请输入手机号" in out, "同行可点击目标应列出"

    out_ed = render_neighborhood(targets, "联系手机", profile="editable")
    assert "请输入手机号" in out_ed and "提交" not in out_ed, "editable 只列输入框"


def test_render_neighborhood_anchor_miss_gives_clickables():
    out = render_neighborhood(_cand_targets(), "不存在的锚点")
    assert "未在目标集合中命中锚点" in out
    assert "提交" in out, "未命中时要给页面可点击目标兜底"


def test_render_targets_md_marks_role_scrollable_and_source():
    nodes = [
        _node(text="横向列表", x=0, y=200, w=700, h=200, class_name="RecyclerView", scrollable=True),
        _node(text="H5 文案", x=10, y=210, w=100, h=30, source="webview", role="text"),
    ]
    md = render_targets_md(build_targets(nodes=nodes, wait_sec=0), source="assert=present")
    assert "> source: assert=present" in md, "目录需带来源行，便于追溯"
    assert "(可滚动)" in md
    assert "(webview)" in md


def test_dump_index_requires_sid_and_writes_md():
    _, path = dump_index("", "assert=present", nodes=_sample_nodes(), wait_sec=0)
    assert path == "", "空 sid 不应落盘（避免 element_index_.catalog.md）"

    with tempfile.TemporaryDirectory() as d:
        _, path = dump_index("S9", "action=tap-text",
                             nodes=_sample_nodes(), wait_sec=0, diag_dir=d)
        assert path.endswith("element_index_S9.catalog.md"), \
            f"统一命名：element_index_{{sid}}.catalog.md，实际 {path}"
        assert os.path.isfile(path)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "请输入手机号" in content
        assert "> source: action=tap-text" in content


def test_find_anchor_exact_then_overlap():
    targets = _cand_targets()
    assert find_anchor(targets, "联系手机")["text"] == "联系手机"
    assert find_anchor(targets, "手机") is not None, "精确未命中时应回退有效重叠"
    assert find_anchor(targets, "压根不存在") is None


# ═══════════════════════════════════════════════════════════════════
# C. 结论口径
# ═══════════════════════════════════════════════════════════════════

def test_compute_needs_review_rule():
    assert compute_needs_review(True, "exact") is False, "字面精确命中是确定性结论"
    assert compute_needs_review(True, "semantic") is True, "语义等价（含引擎唯一子串推断）需复核"
    assert compute_needs_review(True, "visual") is True
    assert compute_needs_review(False, "semantic") is False, "未通过不算待确认"


def test_action_hit_needs_review_rule():
    assert action_hit_needs_review({}) is False, "无 action_hit = 字面精确命中"
    assert action_hit_needs_review({"verdict": "exact"}) is False
    assert action_hit_needs_review({"verdict": "semantic"}) is True


def test_action_hit_from_info_only_for_non_exact():
    assert action_hit_from_info("x", {"match_level": 0, "matched_text": "x"}) is None
    assert action_hit_from_info("x", {"match_level": 1, "matched_text": "x"}) is None
    hit = action_hit_from_info("已优惠", {"match_level": 2, "matched_text": "已优惠¥175"})
    assert hit and hit["verdict"] == "semantic" and hit["actual"] == "已优惠¥175"
    probe_hit = action_hit_from_info("手机号", {"match_level": 0, "probe_name": "webview"})
    assert probe_hit and probe_hit["verdict"] == "semantic", "非 native 探针命中不可视为确定性"
    assert hit_verdict(0) == "exact" and hit_verdict(2) == "semantic"


def test_reason_hook_template_routes_by_intent():
    assert intent_of_action("tap-text") == "click"
    assert intent_of_action("scroll-until") == "click"
    assert intent_of_action("input-text") == "input"
    assert intent_of_action("blur-input") == "blur"

    assert reason_hook_template("tap-text", "TEXT_NOT_FOUND") == "on_text_not_found"
    assert reason_hook_template("scroll-until", "SCROLL_TARGET_NOT_FOUND") == "on_scroll_target_not_found"
    # tap 锚点形态：reason 必须路由到 tap 专用模板（不是 tap-text 的）
    assert reason_hook_template("tap", "ANCHOR_AMBIGUOUS") == "on_tap_anchor_ambiguous"
    assert reason_hook_template("tap", "ANCHOR_NOT_FOUND") == "on_tap_anchor_not_found"
    assert reason_hook_template("tap", "ANCHOR_NO_CLICKABLE") == "on_tap_anchor_not_found"
    # ANCHOR_NOT_FOUND 在 tap（点击意图）与 blur（失焦意图）下必须路由到不同模板
    assert reason_hook_template("blur-input", "ANCHOR_NOT_FOUND") == "on_blur_anchor_not_found"
    # 同一 reason 在不同动作下必须路由到不同模板（输入不能用坐标点击替代）
    assert reason_hook_template("input-text", "TEXT_NOT_FOUND") == "on_input_anchor_not_found"
    assert reason_hook_template("input-text", "INPUT_TARGET_UNRESOLVED") == "on_input_box_resolve"
    assert reason_hook_template("blur-input", "ANCHOR_NOT_FOUND") == "on_blur_anchor_not_found"
    # 未覆盖组合兜底到 click 意图，避免 hook 静默丢失
    assert reason_hook_template("blur-input", "BLOCKED") == "on_target_blocked"
    assert reason_hook_template("input-text", "SCROLL_TARGET_NOT_FOUND") == "on_scroll_target_not_found"


def test_hook_templates_present_for_new_intents():
    from execution.engine.sop.hook_templates import HOOK_TEMPLATES
    for key in ("on_input_anchor_not_found", "on_input_box_resolve",
                "on_input_anchor_viewport", "on_blur_anchor_not_found",
                "on_scroll_substring_ambiguous"):
        assert key in HOOK_TEMPLATES, f"缺少模板 {key}"
        assert HOOK_TEMPLATES[key][0].get("cli_hint")
    # 邻域树占位符已退场：不应再被任何模板引用
    for key, templates in HOOK_TEMPLATES.items():
        for t in templates:
            assert "neighbor_tree" not in (t.get("cli_hint") or ""), f"{key} 仍引用 neighbor_tree"


def test_element_catalog_is_centrally_surfaced():
    """元守卫：元素目录由渲染层统一挂载，模板不得再各自声明占位符。

    历史缺陷：动作类 hook（如 resolve_text_not_found）模板没引用
    {element_index_path}，渲染器又只填模板占位符 → 目录虽已落盘却到不了 AI，
    AI 只能重新 inspect-tree 重新分析（"说没有 → 重采" 的根因）。

    口径：目录是 AI 定位元素的唯一权威视图；凡 handler 已落盘的，hook 必须携带，
    由 render_hook_cli_hint 集中追加 —— 因此：
      ① 模板正文不得再出现 {element_index_path} / {sidecar_path}（统一由证据块承载）；
      ② 携带 element_index_path 的 hook，渲染后必含目录路径；
      ③ 未携带的 hook 不得凭空出现目录块。
    """
    from execution.engine.sop.hook_render import render_hook_cli_hint
    from execution.engine.sop.hook_templates import HOOK_TEMPLATES

    # ① 占位符已退场（含断言类的 sidecar_path）
    for key, templates in HOOK_TEMPLATES.items():
        for t in templates:
            hint = t.get("cli_hint") or ""
            assert "{element_index_path}" not in hint, f"{key} 仍内联引用 element_index_path"
            assert "{sidecar_path}" not in hint, f"{key} 仍内联引用 sidecar_path"

    # ② 携带目录 → 渲染后必含路径
    with_catalog = {"id": "resolve_text_not_found", "hint_params": {
        "target_text": "已优惠", "screenshot_path": "/tmp/s.png",
        "candidate_list": "   （无）",
        "element_index_path": "/tmp/element_index_S1.catalog.md"}}
    rendered = "\n".join(render_hook_cli_hint(with_catalog, "S1"))
    assert "/tmp/element_index_S1.catalog.md" in rendered, "元素目录必须出现在渲染结果中"

    # ③ 未携带 → 不得凭空出现
    without = {"id": "resolve_open_url_failed", "hint_params": {
        "target_text": "imeituan://x", "screenshot_path": "/tmp/s.png"}}
    assert "元素目录" not in "\n".join(render_hook_cli_hint(without, "S1")), \
        "未落盘目录的 hook 不应出现元素目录块"


def test_all_reason_mappings_resolve_to_existing_templates():
    """元守卫：任何 (意图, reason) 路由都必须落到**真实存在**的模板。

    历史死端：`SUBSTRING_AMBIGUOUS` 漏配映射 → 该步 PENDING 却无任何 hook 指引。
    这条检查能让同类遗漏在提交前暴露。
    """
    from execution.engine.sop.hook_templates import HOOK_TEMPLATES
    from execution.engine.sop.on_fail import INTENT_REASON_HOOK_MAP, _CLICK_REASON_HOOK_MAP
    keys = set(_CLICK_REASON_HOOK_MAP.values())
    for table in INTENT_REASON_HOOK_MAP.values():
        keys |= set(table.values())
    missing = sorted(k for k in keys if k not in HOOK_TEMPLATES)
    assert not missing, f"reason 映射指向不存在的模板（会造成无指引死端）：{missing}"


def test_action_reason_registry_covers_hooks_and_labels():
    """元守卫：**动作 → reason 注册表**（`execution/engine/sop/actions.ACTION_REASONS`）是唯一事实来源。

    双向校验（只查一向会漏）：
      ① 注册表里的每个 (action, reason) 都能路由到 hook（或显式声明为引擎内部错误）；
      ② 每个 handler 模块的 `_REASON_LABELS` 与注册表**逐字一致** ——
         多 = 有 reason 没注册（漏配映射的高风险点），少 = 注册了却没人 emit。

    为什么必须校验：ok=False（真失败）还有通用 on_fail 兜底，只是丢精度；
    但 ok=None（**handoff**）没有映射就一条操作指引都不给，AI 只能空转
    （历史上 SUBSTRING_AMBIGUOUS 漏配过）。
    """
    import importlib

    from execution.steps.handlers import HANDLERS
    from execution.engine.sop.actions import ACTION_REASONS
    from execution.engine.sop.hook_templates import HOOK_TEMPLATES
    from execution.engine.sop.on_fail import REASONS_WITHOUT_HOOK, reason_hook_template

    assert set(ACTION_REASONS) == set(HANDLERS), (
        f"注册表与 handler 表不一致（差集）：{set(ACTION_REASONS) ^ set(HANDLERS)}"
    )

    # ① 注册表 → hook 指引
    missing = []
    for action, reasons in ACTION_REASONS.items():
        for reason in sorted(reasons):
            if reason in REASONS_WITHOUT_HOOK:
                continue
            key = reason_hook_template(action, reason)
            if not key or key not in HOOK_TEMPLATES:
                missing.append(f"{action}+{reason} → {key or '(无映射)'}")
    assert not missing, ("以下 (action, reason) 无 hook 指引（handoff 时会静默死端）："
                         + "; ".join(missing))

    # ② 注册表 ↔ handler 的 emit 声明（_REASON_LABELS）逐字一致
    expect_by_mod = {}
    for action, handler in HANDLERS.items():
        expect_by_mod.setdefault(handler.__module__, set()).update(ACTION_REASONS[action])
    drift = []
    for modname, expect in expect_by_mod.items():
        labels = set(getattr(importlib.import_module(modname), "_REASON_LABELS", {}) or {})
        if labels != expect:
            drift.append(f"{modname}: 未注册 labels={sorted(labels - expect)} / "
                         f"未 emit 注册={sorted(expect - labels)}")
    assert not drift, "注册表与 handler 声明漂移：\n" + "\n".join(drift)

    # ③ 白名单不能悄悄过期：被声明「无 hook」的 reason 若已被映射，说明该挪出白名单
    stale = [r for r in REASONS_WITHOUT_HOOK
             if any(reason_hook_template(a, r) for a in HANDLERS)]
    assert not stale, f"REASONS_WITHOUT_HOOK 已过期（这些 reason 其实有映射）：{stale}"


# 各动作的 handler 实际会把 candidate_list 放进 ctx 的 reason（见 handlers/*.py）
_CANDIDATE_PROVIDERS = {
    "tap-text": {"TEXT_NOT_FOUND", "UNRESOLVED", "AMBIGUOUS"},
    "tap": {"ANCHOR_NOT_FOUND", "ANCHOR_NO_CLICKABLE", "ANCHOR_AMBIGUOUS"},
    "scroll-until": {"SUBSTRING_AMBIGUOUS", "SCROLL_TARGET_NOT_FOUND",
                     "VERTICAL_SCROLL_EXHAUSTED", "HORIZONTAL_SCROLL_EXHAUSTED"},
    "input-text": {"TEXT_NOT_FOUND", "INPUT_TARGET_UNRESOLVED"},
    "blur-input": {"ANCHOR_NOT_FOUND"},
}
# 引用 {candidate_list} 的模板（on_track_fields_assertion 由 hook_router 自身提供）
_CANDIDATE_TEMPLATES = {
    "on_text_not_found", "on_target_unresolved", "on_target_ambiguous",
    "on_tap_anchor_not_found", "on_tap_anchor_ambiguous",
    "on_input_anchor_not_found", "on_input_box_resolve",
    "on_blur_anchor_not_found", "on_scroll_substring_ambiguous",
}
_HOOK_ROUTER_PROVIDED_TEMPLATES = {"on_track_fields_assertion"}


def test_candidate_list_templates_all_have_providers():
    """元守卫：引用 {candidate_list} 的模板，必须真的有人提供该字段。

    否则模板会渲染成「（无候选）」，AI 拿到空清单——历史上这正是 input 场景的错配来源。
    """
    from execution.engine.sop.hook_templates import HOOK_TEMPLATES
    provided = {"on_track_fields_assertion"}  # 由 hook_router 的 track 分支提供
    for action, reasons in _CANDIDATE_PROVIDERS.items():
        for r in reasons:
            t = reason_hook_template(action, r)
            if t:
                provided.add(t)

    # 反向：扫模板正文，找出所有引用 candidate_list 的键，确认都在 provided 里
    referenced = set()
    for key, templates in HOOK_TEMPLATES.items():
        for t in templates:
            if "{candidate_list}" in (t.get("cli_hint") or ""):
                referenced.add(key)
    missing = sorted(referenced - provided)
    assert not missing, f"模板引用 {{candidate_list}} 但无人提供：{missing}"
    # 顺带锁定本守卫自身的假设（模板集合变化时应同步更新）
    assert referenced == _CANDIDATE_TEMPLATES | _HOOK_ROUTER_PROVIDED_TEMPLATES, \
        f"引用 candidate_list 的模板集合已变化，请同步 _CANDIDATE_TEMPLATES：{sorted(referenced)}"


def test_get_current_nodes_end_to_end_with_stubs():
    """端到端冒烟：native 聚合两条路径都要能跑通。

    这类守卫能抓住「调用方与服务方签名不一致」——本次就真实出现过
    `_probe_nodes(native_nodes)` 调用 vs `def _probe_nodes()` 定义的不一致，
    会导致每步都 TypeError（整个 get_current_nodes 路径崩溃）。
    """
    import shared.context as ctx
    import execution.screen.tree_source as ts

    orig_dump, orig_parse, orig_probes = (
        ts.dump_inspect_tree, ts.parse_inspect_tree, ctx.get_probes)
    try:
        # 1) 无 WebView：native 结果原样返回，且绝不触达探针链
        ts.dump_inspect_tree = lambda wait_sec=6, max_attempts=2, whole_screen=False: {"raw": 1}
        ts.parse_inspect_tree = lambda raw: [_node(text="提交", class_name="Button", clickable=True)]

        def _no_probes():
            raise AssertionError("无 WebView 页面不应触达探针链（性能回归）")

        ctx.get_probes = _no_probes
        assert [n["text"] for n in ts.get_current_nodes(wait_sec=0)] == ["提交"]

        # 2) 有 WebView：合并探针节点（探针 stub 掉，不碰设备）
        ts.parse_inspect_tree = lambda raw: [
            _node(text="漫曲酒店", class_name="ReactTextView", x=0, y=100, w=700, h=40),
            _node(text=None, class_name="com.x.X5WebView", x=0, y=200, w=700, h=400),
        ]

        class _StubProbe:
            probe_name = "webview"

            def dump_nodes(self):
                return [_node(text="H5 按钮", x=10, y=210, w=100, h=40,
                              clickable=True, source="webview", role="button")]

        ctx.get_probes = lambda: [_StubProbe()]
        texts = [n.get("text") for n in ts.get_current_nodes(wait_sec=0)]
        assert "H5 按钮" in texts, "有 WebView 容器时必须合并探针节点"
        assert "漫曲酒店" in texts, "native 节点不得丢"
    finally:
        ts.dump_inspect_tree, ts.parse_inspect_tree = orig_dump, orig_parse
        ctx.get_probes = orig_probes


def test_action_command_exit_code_convention():
    """独立动作命令的统一收口：handoff ≠ 错误，且必须是非零退出码。

    历史问题：input-text/blur-input 把 handoff 当设备错误抛（误导诊断）；
    scroll-until 把 handoff/失败静默当成功（exit 0）。此守卫锁定统一语义。
    """
    import contextlib
    import io

    from cli_utils import finish_action_result
    from shared import exit_codes
    from shared.errors import DeviceError

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert finish_action_result("T", "x", {"ok": True}) is None, "完成 → 无需退出码"
        code = finish_action_result("T", "x", {"ok": None, "ctx": {
            "reason": "TEXT_NOT_FOUND",
            "candidate_list": "   [1] ✅「已优惠¥175」",
            "element_index_path": "/tmp/element_index_S1.catalog.md",
        }})
    assert code == exit_codes.HANDOFF and code != 0, "handoff 必须是非零的专用退出码"
    assert code not in (exit_codes.ERROR, exit_codes.USAGE), "不得与错误/用法码混用"
    out = buf.getvalue()
    assert "HANDOFF" in out and "已优惠¥175" in out and "element_index_S1" in out, \
        "handoff 必须把候选与元素目录一并交出，否则调用方无法换策略"

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            finish_action_result("T", "x", {"ok": False, "reason": "boom"})
    except DeviceError:
        pass
    else:
        raise AssertionError("ok=False 必须 raise DeviceError（真失败走统一错误出口）")


def test_verdict_uses_containment_not_overlap():
    """元守卫：判定口径用「包含关系」，召回口径才用「有效重叠」，两者必须分离。

    历史缺陷（三次真实运行共暴露 4 次假 PENDING + 1 类假 pass 风险）：
    · gone：`房型设施详情` vs 页面残留词 `房型详情`（共享「房型/详情」）被判「仍有残留」
      → 假 PENDING，每次全流程白耗 2 轮 AI 判定；
    · present：`满30减10` vs `满30减8`（共享「满30减」）会被判「语义等价」→ 假 pass（更危险）。
    · 单字符包含（本轮跑测暴露）：`入离时间` vs 独立节点 `间` 被判「仍有残留」→ gone 假 PENDING。
    """
    from execution.screen.tree_match import _has_meaningful_overlap as recall
    from execution.screen.tree_match import _is_containment as verdict
    from execution.screen.tree_match import find_substring_candidates

    # 判定：非包含 → 不得认定等价/残留
    assert verdict("房型设施详情", "房型详情") is False, "共享无关字符不算残留（gone 假 PENDING 根因）"
    assert verdict("满30减10", "满30减8") is False, "部分重叠不算语义等价（present 假 pass 风险）"
    # 判定：单字符包含 → 同样不得算残留（必须与「互为包含」互补，缺一即误报）
    assert verdict("入离时间", "间") is False, "单字符包含不算残留（gone 假 PENDING 回归）"
    assert find_substring_candidates([{"text": "间"}], "入离时间") == []
    # 判定：真包含 → 认定等价
    assert verdict("没有更多了", "- 没有更多了 -") is True, "装饰符形态差异应判语义等价"
    assert verdict("9月28日", "9月28日周一") is True, "跨节点聚合的前缀等价应命中"
    assert verdict("入离时间", "入离时间") is True, "完全相等始终成立"
    # 召回：仍保持宽松（给 AI 更多线索）
    assert recall("满30减10", "满30减8") is True, "召回口径必须保持宽松"
    # 候选（判定用）必须已按包含关系过滤
    assert find_substring_candidates([{"text": "房型详情"}], "房型设施详情") == []
    assert len(find_substring_candidates([{"text": "- 没有更多了 -"}], "没有更多了")) == 1


def test_generated_step_command_is_shell_executable():
    """元守卫：flow-next 生成的 step 指令必须可直接执行（shell 转义正确）。

    历史缺陷：`--asserts` 裸写（JSON 含空格 → 被 shell 拆成多个参数）、
    `--action-arg` 用双引号包裹 JSON（内层引号被吃掉 → JSON 非法）
    → AI 若照抄 "CMD:" 必然执行失败。
    """
    import shlex

    from execution.engine.flow.step_scheduler import _build_step_command

    step = {
        "sid": "S1", "kind": "ui", "action": "input-text",
        "action_anchor": "姓名",
        "action_arg": '{"anchor":"姓名","text":"李明"}',
        "step-type": "interaction",
        "asserts": [{"kind": "text", "match": "present", "expect": "住客姓名"}],
        "desc": "输入入住人姓名",
    }
    cmd = _build_step_command(step, {})
    assert cmd, "input-text 命令不得为 None（锚点在 action_arg 里，命令本身是完整的）"
    argv = shlex.split(cmd)          # 用 shlex 还原 argv = 证明可被 shell 正确解析
    assert "--action-arg" in argv, f"缺少 --action-arg: {cmd}"
    idx = argv.index("--action-arg")
    assert argv[idx + 1] == '{"anchor":"姓名","text":"李明"}', f"action_arg 转义有误: {cmd}"
    assert "--asserts" in argv, f"缺少 --asserts: {cmd}"
    assert argv[argv.index("--asserts") + 1].startswith("[{"), f"asserts 被拆参: {cmd}"

    # tap 锚点形态：命令必须可直接执行，且不得混入坐标（坐标为 hook 兜底专用）
    tap_step = {
        "sid": "S2", "kind": "ui", "action": "tap",
        "action_anchor": "入住信息",
        "step-type": "interaction",
        "asserts": [{"kind": "visual", "expect": "房间数减少"}],
        "desc": "点击「入住信息」行减号（无文案图标）",
    }
    cmd2 = _build_step_command(tap_step, {})
    assert cmd2, "tap 锚点形态命令不得为 None（锚点行由引擎运行期解析）"
    argv2 = shlex.split(cmd2)
    assert "--action-anchor" in argv2, f"缺少 --action-anchor: {cmd2}"
    assert argv2[argv2.index("--action-anchor") + 1] == "入住信息", f"锚点转义有误: {cmd2}"
    assert "--action-x" not in argv2, f"锚点形态不应带坐标: {cmd2}"


def test_action_flag_contract_consistency():
    """元守卫：ACTION_SPECS / step parser / handler 三方的 action 传参名必须一致。

    历史缺陷：`step blur-input` 的 parser 定义 `--action-anchor`，而生成器发 `--action-arg`
    → ① 生成的命令 argparse 报错 ② 即便传 --action-anchor，handler 读的是 action_arg（空）
    → 锚点被静默丢弃。
    """
    import cli
    from execution.engine.sop.actions import ACTION_SPECS

    assert ACTION_SPECS["input-text"]["required"] == ["action_arg"]
    assert "--action-arg" in ACTION_SPECS["blur-input"]["usage"]

    parser = cli.build_parser()
    cases = [
        ("blur-input", "姓名"),
        ("input-text", '{"anchor":"姓名","text":"李明"}'),
    ]
    for action, value in cases:
        ns = parser.parse_args(["step", "--sid", "S1", action, "--action-arg", value])
        assert getattr(ns, "action_arg", None) == value, \
            f"step {action} 未接住 --action-arg（parser 与契约不一致）"

    # tap 的锚点传参名也必须三方一致（ACTION_SPECS / parser / handler）
    ns_tap = parser.parse_args(["step", "--sid", "S1", "tap", "--action-anchor", "入住信息"])
    assert ns_tap.action_anchor == "入住信息", \
        "step tap 未接住 --action-anchor（parser 与契约不一致）"


def _anchor_nodes():
    """锚点行场景：唯一图标行（房型设施 + 箭头）+ 多图标行（入住信息）。"""
    return [
        _node(text="房型设施", x=40, y=300, w=120, h=30, class_name="text"),
        _node(text=None, x=650, y=300, w=40, h=30, clickable=True, class_name="ImageView"),
        _node(text="入住信息", x=80, y=600, w=120, h=30, class_name="text"),
        _node(text=None, x=520, y=600, w=40, h=40, clickable=True, class_name="ImageView"),
        _node(text="1间", x=575, y=600, w=60, h=40, clickable=True, class_name="Button"),
        _node(text=None, x=650, y=600, w=40, h=40, clickable=True, class_name="ImageView"),
    ]


def test_resolve_anchor_clickable_unique_vs_ambiguous():
    """元守卫：tap 锚点选取口径 —— 形态唯一才自动，多/无候选一律交 AI。

    与断言 T1.5「唯一子串才判语义等价」同口径：引擎不得在形态不唯一时择一，
    否则会静默点错目标（比 handoff 更危险）。
    """
    targets = build_targets(nodes=_anchor_nodes(), wait_sec=0)

    uniq = resolve_anchor_clickable(targets, "房型设施")
    assert uniq["found"] is True
    assert len(uniq["candidates"]) == 1, f"唯一图标行应只有 1 个可点击目标：{uniq['candidates']}"
    assert uniq["picked"] is not None and uniq["picked"]["clickable"] is True, \
        "形态唯一 → 必须给出可直接点击的目标"

    multi = resolve_anchor_clickable(targets, "入住信息")
    assert len(multi["candidates"]) == 3, f"多图标行应有 3 个可点击目标：{multi['candidates']}"
    assert multi["picked"] is None, "多候选时引擎不得擅自择一（交 AI）"

    miss = resolve_anchor_clickable(targets, "压根不存在")
    assert miss["found"] is False and miss["picked"] is None

    # 锚点存在但该行没有可点击目标 → 同样 handoff（候选为空）
    nodes = [_node(text="纯文案行", x=0, y=100, w=200, h=30, class_name="text")]
    none_clk = resolve_anchor_clickable(build_targets(nodes=nodes, wait_sec=0), "纯文案行")
    assert none_clk["found"] is True and none_clk["candidates"] == [] and none_clk["picked"] is None


def test_row_members_excludes_adjacent_row():
    """同一视觉行判定：相邻字段行（纵向不重叠、但落在旧 ±150px 带内）不得混入锚点行。

    回归：此前 tap 锚点用固定 ±150px 像素带 → 相邻行（间距 <150px）被卷入，
    使「锚点行唯一目标」几乎永不成立（Flow02 每步都要 AI 坐标兜底）。
    """
    from execution.screen.tree_index import _row_members, _NEAR_Y_RANGE
    nodes = [
        _node(text="入住信息", x=80, y=600, w=120, h=40, class_name="text"),
        _node(text=None, x=520, y=600, w=40, h=40, clickable=True, class_name="ImageView"),   # 同行图标
        _node(text="住客姓名", x=80, y=660, w=120, h=40, class_name="text"),                   # 相邻字段行
        _node(text="王事成", x=520, y=660, w=120, h=40, clickable=True, class_name="Button"),  # 相邻字段行
    ]
    targets = build_targets(nodes=nodes, wait_sec=0)
    items = targets["targets"]
    anchor = next(e for e in items if e["text"] == "入住信息")
    row_texts = {(e.get("text") or e["id"]) for e in _row_members(items, anchor)}
    assert "王事成" not in row_texts, "相邻行（660）不得混入锚点行（600）"

    # 锚点行唯一可点击目标 → 自动点（不再因相邻行噪声 handoff）
    r = resolve_anchor_clickable(targets, "入住信息")
    assert len(r["candidates"]) == 1, f"锚点行只有 1 个可点击图标：{r['candidates']}"
    assert r["picked"] is not None, "视觉行口径下应能自动选中唯一目标"

    # 旧的 ±150 像素带确实会把 660 行卷进来（证明回归点存在）
    assert abs(660 - 620) <= _NEAR_Y_RANGE

    # clickable_near 也必须同源：给了锚点文案就按同一视觉行取候选
    from execution.screen.tree_index import render_candidates
    near = render_candidates(targets, "clickable_near", anchor="入住信息")
    assert "王事成" not in near, "clickable_near 带锚点时不得混入相邻行"


def test_render_anchor_resolution_matches_selection():
    """元守卫：选取与渲染必须同源（候选清单就是引擎判定所用的那一份）。"""
    targets = build_targets(nodes=_anchor_nodes(), wait_sec=0)
    resolution = resolve_anchor_clickable(targets, "入住信息")
    out = render_anchor_resolution(resolution, targets)
    assert "入住信息" in out and "1间" in out, "候选清单必须列出锚点行的可点击目标"
    assert out.count("tap=(") == len(resolution["candidates"]), \
        "引擎判定用几条就应展示几条（避免“点了 A 却显示 B”）"

    miss = render_anchor_resolution(resolve_anchor_clickable(targets, "压根不存在"), targets)
    assert "未在目标集合中命中锚点" in miss and "1间" in miss, "锚点未命中要给页面可点击兜底"


def test_tap_anchor_contract_accepts_anchor_or_coords():
    """元守卫：tap 契约是“锚点或坐标”二选一（可验证、可报错），不允许两者皆空。"""
    import cli
    from execution.engine.sop.actions import ACTION_SPECS, validate_action_args

    assert ACTION_SPECS["tap"].get("any_of") == [["action_x", "action_y"], ["action_anchor"]]
    assert "--action-anchor" in ACTION_SPECS["tap"]["usage"]

    parser = cli.build_parser()
    ns_anchor = parser.parse_args(["step", "--sid", "S1", "tap", "--action-anchor", "入住信息"])
    assert validate_action_args("tap", ns_anchor) is None
    ns_xy = parser.parse_args(["step", "--sid", "S1", "tap", "--action-x", "10", "--action-y", "20"])
    assert validate_action_args("tap", ns_xy) is None

    ns_empty = parser.parse_args(["step", "--sid", "S1", "tap"])
    err = validate_action_args("tap", ns_empty)
    assert err and "--action-anchor" in err, f"缺锚点与坐标应报错：{err}"
    # 只给半个坐标不算满足坐标组
    ns_half = parser.parse_args(["step", "--sid", "S1", "tap", "--action-x", "10"])
    assert validate_action_args("tap", ns_half) is not None, "只给 --action-x 不应通过"


def test_tap_handler_anchor_dispatch():
    """元守卫：tap 锚点 handler 的运行时行为 —— 唯一→直接点(标 action_hit)，多/无→handoff。

    用桩替换设备与视图树（不碰真实设备），验证"形态唯一才自动、否则交 AI"，
    并锁定 reason hook 必须按 tap 意图路由（否则会被错配到 tap-text 模板）。
    """
    from execution.steps.handlers import tap as tap_handler

    calls = []

    class _Ops:
        def tap(self, x, y):
            calls.append((x, y))
            return True

    class _Args:
        action_anchor = "房型设施"
        action_x = None
        action_y = None
        sid = "S1"

    nodes = _anchor_nodes()
    orig_ops = tap_handler.get_platform_ops
    orig_dump = tap_handler.dump_index
    try:
        tap_handler.get_platform_ops = _Ops
        tap_handler.dump_index = lambda sid, source, **kw: (
            build_targets(nodes=nodes, wait_sec=0), "")

        with contextlib.redirect_stdout(io.StringIO()):  # 静音 handler 的控制台输出
            r = tap_handler.handle_tap("", _Args())
        assert r["ok"] is True, "唯一图标行必须直接点击"
        assert len(calls) == 1, f"应只点一次，实际 {calls}"
        hit = r["ctx"]["action_hit"]
        assert hit["verdict"] == "semantic" and hit["target"] == "房型设施", \
            "自动命中必须记 action_hit 待人工复核（推断命中不得当确定性结论）"

        calls.clear()
        _Args.action_anchor = "入住信息"
        with contextlib.redirect_stdout(io.StringIO()):
            r2 = tap_handler.handle_tap("", _Args())
        assert r2["ok"] is None, "多候选必须 handoff（ok=None），不得擅自点击"
        assert calls == [], "多候选时不得发生任何点击"
        assert r2["ctx"]["reason"] == "ANCHOR_AMBIGUOUS"
        assert r2["ctx"]["action"] == "tap", "reason hook 必须按 tap 意图路由（不是 tap-text）"
        assert "1间" in r2["ctx"]["candidate_list"]

        calls.clear()
        _Args.action_anchor = "压根不存在"
        with contextlib.redirect_stdout(io.StringIO()):
            r3 = tap_handler.handle_tap("", _Args())
        assert r3["ok"] is None and r3["ctx"]["reason"] == "ANCHOR_NOT_FOUND"
        assert calls == [], "锚点未命中时不得发生任何点击"
    finally:
        tap_handler.get_platform_ops = orig_ops
        tap_handler.dump_index = orig_dump


def test_hook_template_coordinate_commands_are_attributed():
    """元守卫：hook 模板里的坐标兜底命令必须可执行且绑定父步骤。

    历史缺陷（Run …T124636 / flow02）：模板给的是裸 `step tap --action-x/--action-y`，
    未绑定 sid → 报告层按「未声明 SID」归入 findings（3 步显示成 5 条），
    两条兜底还共用同一截图 → 证据互相覆盖、不可追溯；
    另有 `on_scroll_exhausted` 写成 `tap --action-x`（独立 tap 只接受 --x/--y）→ 照抄必报错。
    """
    from execution.engine.sop.hook_templates import HOOK_TEMPLATES

    bad = []
    for key, templates in HOOK_TEMPLATES.items():
        for t in templates:
            for line in (t.get("cli_hint") or "").splitlines():
                if "--action-x" not in line and "--action-y" not in line:
                    continue
                stripped = line.strip()
                # 坐标兜底必须走 `step` 子命令（独立 tap 只接受 --x/--y，写 --action-x 必然 argparse 报错）
                if not _TEMPLATE_STEP_CMD_RE.search(stripped):
                    bad.append((key, stripped, "坐标点击必须走 `step`（独立 tap 只接受 --x/--y）"))
                elif "--for-sid {{sid}}" not in stripped and "--sid {{sid}}" not in stripped:
                    bad.append((key, stripped, "坐标兜底必须绑定父步骤（--for-sid）"))
    assert not bad, "hook 模板坐标命令不合规：\n" + "\n".join(
        f"  [{k}] {l}  ← {why}" for k, l, why in bad
    )


def test_fallback_attribution_and_conclusion():
    """元守卫：归属型兜底（_src=fallback）必须进父步骤证据，且不得主导结论 / 落成 finding。

    `--for-sid` 的语义：兜底操作只是「动作已发出」的证据，步骤结论权在断言与 AI override；
    若让它当结论，会把兜底点击的 ok 直接当成步骤结论（提前宣布通过）。
    """
    from shared.records import SRC_FALLBACK, SRC_FOLLOWUP, SRC_STEP
    from reporting.model import normalize_step_records

    records = [
        {"sid": "S1", "_src": SRC_STEP, "ok": None, "d": "引擎 handoff"},
        {"sid": "S1", "_src": SRC_FALLBACK, "ok": 1, "d": "坐标点击兜底"},
        {"sid": "S1", "_src": SRC_FOLLOWUP, "ok": 1, "d": "断言判定通过"},
    ]
    normalized, findings, _ = normalize_step_records(records, ["S1"])
    assert findings == [], "兜底记录必须绑定父步骤，不得落成孤立 finding"
    bucket = normalized["S1"]
    assert bucket["conclusion"]["_src"] == SRC_FOLLOWUP, "结论必须来自 override，不是兜底点击"
    assert any(r["_src"] == SRC_FALLBACK for r in bucket["executions"]), "兜底记录须作为父步骤证据"
    assert any(r["_src"] == SRC_FALLBACK for r in bucket["attempts"]), "兜底记录须进 attempts"

    # 无 override 时：兜底点击的 ok=1 不得把 PENDING 顶成 PASS
    only = [
        {"sid": "S1", "_src": SRC_STEP, "ok": None},
        {"sid": "S1", "_src": SRC_FALLBACK, "ok": 1},
    ]
    n2, f2, _ = normalize_step_records(only, ["S1"])
    assert f2 == [], "绑定父步骤后不得再产生 finding"
    assert n2["S1"]["conclusion"]["_src"] == SRC_STEP, \
        "无 override 时结论必须回到声明的 step 记录（PENDING），不被兜底点击顶成 PASS"

    # 重跑可追溯：首轮「无判定」的记录必须进 attempts_unjudged（不进 attempts / retry_count）
    rerun = [
        {"sid": "S1", "_src": SRC_STEP, "ok": None, "d": "首轮 PENDING"},
        {"sid": "S1", "_src": SRC_STEP, "ok": 1, "d": "重跑通过"},
    ]
    n3, f3, _ = normalize_step_records(rerun, ["S1"])
    assert f3 == [], "同 sid 重跑不得产生 finding"
    assert len(n3["S1"]["attempts_unjudged"]) == 1, "无判定的首轮记录必须可追溯"
    assert n3["S1"]["attempts"] == [], "无判定记录不得进入 attempts（不污染 retry_count）"
    assert n3["S1"]["conclusion"]["ok"] == 1, "结论取重跑那次"


def test_step_primary_screenshot_is_conclusion():
    """主图唯一真相：step.screenshot == evidence.screenshot == canonical[0]（结论图）。

    场景：首轮在错误页面（如误触打开的弹窗）拍的图，不得成为步骤主图 —— 重试/结论
    截图才是主图，首轮图退居为带 role 的过程图。历史缺陷：step.screenshot 取「跨执行
    记录合并后的第 0 张」= 首轮失败图，evidence.screenshot 取结论图，两个主图字段互相矛盾。
    """
    from reporting.model import normalize_step_records
    from reporting.steps import build_step

    records = [
        {"sid": "S3", "_src": "step", "ok": 2, "d": "输入手机号",
         "screenshots": [{"file": "case_02_S3.png", "label": "步骤截图", "kind": "step"}]},
        {"sid": "S3", "_src": "retry", "ok": 0, "d": "坐标重试",
         "screenshots": [{"file": "case_02_S3b.png", "label": "步骤截图", "kind": "step"}]},
        {"sid": "S3", "_src": "followup", "ok": 1, "d": "判定通过",
         "screenshots": [{"file": "case_02_S3b.png", "label": "结论截图", "kind": "auto"}]},
    ]
    images = {
        "case_02_S3.png": "https://u/S3.png",
        "case_02_S3b.png": "https://u/S3b.png",
    }
    normalized, findings, _ = normalize_step_records(records, ["S3"])
    assert findings == [], "同 sid 的重试/override 不得产生 finding"
    step = {"sid": "S3", "kind": "ui", "desc": "输入手机号", "status": "completed"}
    projected = build_step(step, normalized["S3"], images)

    assert projected["screenshot"] == "https://u/S3b.png", \
        "主图必须是结论图（不能是首轮错误页图）"
    assert projected["evidence"]["screenshot"] == projected["screenshot"], \
        "step.screenshot 与 evidence.screenshot 必须同源（唯一真相）"
    shots = projected["screenshots"]
    assert shots and shots[0]["url"] == projected["screenshot"] and shots[0]["is_conclusion"], \
        "canonical[0] 必须是结论图且标 is_conclusion"
    assert sum(1 for s in shots if s["is_conclusion"]) == 1, "结论图必须唯一"
    assert any(s["url"] == "https://u/S3.png" for s in shots), "首轮过程图必须保留（可追溯）"


def test_for_sid_binds_to_declared_step():
    """元守卫：--for-sid 与 --sid 互斥；只接受已声明 SID；解析为归属（不走 retry/结论）。"""
    import cli
    from execution.steps.pipeline.step_context import _resolve_sid_conflict
    from shared.errors import UsageError

    parser = cli.build_parser()
    flow = {"steps": [{"sid": "S1"}, {"sid": "S2"}]}

    ns = parser.parse_args(["step", "--for-sid", "S1", "tap", "--action-x", "1", "--action-y", "2"])
    sid_arg, step_def, retry_parent, for_sid = _resolve_sid_conflict(ns, flow)
    assert for_sid == "S1" and sid_arg == "S1", f"兜底应归属 S1：{for_sid}/{sid_arg}"
    assert retry_parent is None and step_def is None, "兜底归属不得走 retry / 不得当成本步声明"

    ns2 = parser.parse_args(["step", "--for-sid", "S9", "tap", "--action-x", "1", "--action-y", "2"])
    try:
        _resolve_sid_conflict(ns2, flow)
    except UsageError:
        pass
    else:
        raise AssertionError("--for-sid 指向未声明步骤必须报错")

    with contextlib.redirect_stderr(io.StringIO()):
        try:
            parser.parse_args(["step", "--sid", "S1", "--for-sid", "S2", "tap",
                               "--action-x", "1", "--action-y", "2"])
        except SystemExit:
            pass
        else:
            raise AssertionError("--sid 与 --for-sid 必须互斥")


def _subparser(parser, name):
    """取子命令 parser（argparse 未提供公开 API，守卫里用其 subparsers action）。"""
    if parser is None:
        return None
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices.get(name)
    return None


# 模板里的「命令」形态：`python3 scripts/cli.py step …`，或 `→ step …` / `：step …`。
# 必须收紧：模板正文里会**提到** step（如「不要用 step --sid 重跑…」），
# 若把散文当命令会误报。这里是"什么算命令行"的唯一判定，两个模板守卫共用。
_TEMPLATE_STEP_CMD_RE = re.compile(r"(?:^|→|：|cli\.py)\s*step\s")


def _iter_template_step_commands():
    """从 hook 模板 cli_hint 中抽取 `step …` 命令行 → (模板 key, 原始行)。"""
    from execution.engine.sop.hook_templates import HOOK_TEMPLATES

    for key, templates in HOOK_TEMPLATES.items():
        for t in templates:
            for line in (t.get("cli_hint") or "").splitlines():
                if _TEMPLATE_STEP_CMD_RE.search(line):
                    yield key, line.strip()


def _unknown_step_flags(line, step_parser):
    """校验模板 `step …` 行：返回 CLI 不认识的 (flag, action) 列表（空 = 合规）。

    动作名定位：跳过 `--flag <value>` 对后，第一个非 flag token 即动作
    （`step --sid {{sid}}b tap …` 的动作是 tap，不是 {{sid}}b）。
    """
    tokens = line.split()
    si = next((i for i, tk in enumerate(tokens) if tk == "step"), None)
    if si is None:
        return []
    after, action, i = tokens[si + 1:], None, 0
    while i < len(after):
        if after[i].startswith("--"):
            i += 2
            continue
        action = after[i]
        break
    action_parser = _subparser(step_parser, action)
    if action_parser is None:
        return [(f"未知动作 {action!r}", action)]
    valid = set()
    for parser in (step_parser, action_parser):
        for a in parser._actions:
            valid.update(a.option_strings)
    return [(f, action) for f in re.findall(r"--[a-z][a-z0-9-]*", line) if f not in valid]


def test_hook_template_step_flags_are_structurally_valid():
    """元守卫：模板 `step …` 命令里的每个 flag 必须是该动作 parser **真正认识**的。

    为什么不能只做文本检查：历史缺陷 `on_scroll_exhausted` 写成 `tap --action-x` ——
    独立 tap 只接受 --x/--y，`--action-x` 是 `step` 层 flag → 照抄必然 argparse 报错。
    「这行有没有 step」这类文本判断发现不了 flag 组合错误；必须对照真实 parser 的 flag 表。
    """
    import cli

    step_parser = _subparser(cli.build_parser(), "step")
    bad = [(key, line, f, a)
           for key, line in _iter_template_step_commands()
           for f, a in _unknown_step_flags(line, step_parser)]
    assert not bad, "模板命令含 CLI 不认识的 flag / 动作：\n" + "\n".join(
        f"  [{k}] action={a} {f} ← {l}" for k, l, f, a in bad
    )

    # 自证区分力：把历史缺陷形态喂进去必须被识别，避免"守卫判定失效却永远通过"
    for probe in (
        "python3 scripts/cli.py step --sid S1 blur-input --action-anchor 姓名",  # ④ blur 曾用 --action-anchor
        "python3 scripts/cli.py step --sid S1 tap --anchor 入住信息",             # 不存在 --anchor
        "python3 scripts/cli.py step --sid S1 tap --action-x 1 --action-y 2 --no-such-flag",
    ):
        assert _unknown_step_flags(probe, step_parser), f"守卫未能识别非法 flag：{probe}"


# ═══════════════════════════════════════════════════════════════════
# 运行器
# ═══════════════════════════════════════════════════════════════════

def test_non_idempotent_rerun_is_blocked():
    """元守卫：不可重跑动作（back / input-text）在**已执行过**的步骤上禁止原地重跑。

    真实缺陷（本轮跑测暴露）：重跑 pending 的 `back` 会多退一页、把页面退出目标页，
    后续断言全部失准；而引擎当时只拦 completed/failed，pending 态可随意重跑。
    同时锁定"不误伤"：首次执行、幂等动作、换新 sid 的重试都必须放行。
    """
    import cli
    from shared.errors import FlowStateError
    from execution.engine.sop.actions import NON_IDEMPOTENT_ACTIONS, STEP_ACTIONS

    # 契约自证：集合是已注册动作，且包含实测的两个、不含无副作用动作
    assert NON_IDEMPOTENT_ACTIONS <= STEP_ACTIONS, "不可重跑集合必须是已注册动作"
    assert {"back", "input-text"} <= NON_IDEMPOTENT_ACTIONS
    assert "assert-text" not in NON_IDEMPOTENT_ACTIONS, "无副作用动作不得被拦"

    parser = cli.build_parser()

    def _flow(started=True):
        step = {"sid": "S3", "status": "pending"}
        if started:
            step["started_at"] = "2026-09-18T14:00:00"
        return {"steps": [step]}

    ns_back = parser.parse_args(["step", "--sid", "S3", "back"])
    try:
        _resolve_sid_conflict(ns_back, _flow())
    except FlowStateError as e:
        assert "不可原地重跑" in str(e) and "S3b" in str(e), f"报错须给出换新 sid 的出路：{e}"
    else:
        raise AssertionError("已执行过的 back 原地重跑必须被拦")

    # 未执行过（无 started_at）→ 放行
    sid_arg, _, retry_parent, _ = _resolve_sid_conflict(ns_back, _flow(started=False))
    assert sid_arg == "S3" and retry_parent is None, "首次执行不得被拦"

    # 幂等动作已执行过 → 放行（允许重跑复核）
    ns_assert = parser.parse_args(["step", "--sid", "S3", "assert-text", "--asserts", "[]"])
    _resolve_sid_conflict(ns_assert, _flow())

    # 换新 sid 的重试（S3b）→ 放行（这是确需再执行时的正确出路）
    ns_retry = parser.parse_args(["step", "--sid", "S3b", "back"])
    _, _, retry_parent, _ = _resolve_sid_conflict(ns_retry, _flow())
    assert retry_parent == "S3", "换新 sid 的重试必须可执行"


def test_auto_shot_name_is_unique_per_execution():
    """元守卫：非步骤级自动截图必须以「执行序号」为唯一键（禁止固定名 / 秒级时间戳）。

    真实缺陷（本轮跑测暴露）：`diag_open_url.png` 是固定名 —— 同一 case 内第二次 open-url
    （恢复目标页）直接覆盖了 C3 的落地证据图，报告引用的证据与语义不符且不可追溯。
    """
    import inspect

    from shared.records import auto_shot_name, case_prefix

    ws = "/tmp/run/case_01"
    assert case_prefix(ws) == "case_01_"
    assert case_prefix("/tmp/run") == "", "非 case 目录不应加前缀"

    n1 = auto_shot_name(ws, "diag", 3, tag="open_url")
    n2 = auto_shot_name(ws, "diag", 4, tag="open_url")
    assert n1 == "case_01_diag_open_url_3.png", f"命名格式错：{n1}"
    assert n1 != n2 and n2.endswith("_4.png"), "同一 tag 的不同执行必须得到不同文件名"
    assert auto_shot_name(ws, "fallback", 9, tag="S1") == "case_01_fallback_S1_9.png"

    # 接线守卫：调用点必须走统一命名，**且模块已导入该符号**
    # （只查调用点会漏掉"调用了但没 import" → NameError，本次真实发生过）
    from execution.steps import assertion_utils
    from execution.steps.recording import common as recording_common

    for module, fn_name in ((assertion_utils, "_try_shoot_for_diagnosis"),
                            (recording_common, "_auto_capture_screenshot")):
        assert "auto_shot_name(" in inspect.getsource(getattr(module, fn_name)), \
            f"{fn_name} 未使用统一自动命名（可能回退到固定名 → 证据覆盖）"
        for sym in ("auto_shot_name", "alloc_shot_seq"):
            assert hasattr(module, sym), f"{module.__name__} 未导入 {sym}（调用点会 NameError）"


def test_alloc_shot_seq_is_unique_at_allocation_time():
    """元守卫：非步骤级截图序号必须在「分配时」即唯一，不能用记录级序号。

    真实缺陷：旧实现用 steps.jsonl 行数 + 1 当序号（**记录级**），而同一条记录追加前
    可能连拍多张截图 → 序号相同 → 同名 → 覆盖，早拍证据被静默替换。张级资产要张级键。
    """
    import tempfile

    from shared.records import alloc_shot_seq, auto_shot_name

    with tempfile.TemporaryDirectory() as ws:
        seqs = [alloc_shot_seq(ws) for _ in range(5)]
        assert len(set(seqs)) == 5, f"分配序号必须两两不同：{seqs}"
        assert seqs == sorted(seqs), f"分配序号必须单调递增：{seqs}"
        # 同一 tag 连拍多张（同一 open-url 重试 / 同一记录内的多次诊断）→ 文件名必须不同
        names = [auto_shot_name(ws + "/case_01", "diag", s, tag="open_url") for s in seqs]
        assert len(set(names)) == len(names), f"同名覆盖：{names}"
        # 跨「伪重启」持久化：再次分配继续递增，不回退到 1
        assert alloc_shot_seq(ws) == 6, "计数器未持久化（重进后应继续 +1）"


def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅ {name}")
        except AssertionError as e:
            failed.append((name, e))
            print(f"  ❌ {name}: {e}")
        except Exception as e:  # noqa: BLE001 — 守卫需暴露真实异常
            failed.append((name, e))
            print(f"  💥 {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
    total = len(tests)
    print(f"\n{total - len(failed)}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
