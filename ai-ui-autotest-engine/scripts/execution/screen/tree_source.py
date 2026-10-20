"""视图树采集与缓存：dump / 8s 缓存 / 失效。"""
import json
import os
import sys
import time
from shared.json_utils import read_json
from shared.errors import soft_fail
from shared.paths import ensure_dirs, inspect_tree_cache_path
from shared.context import get_platform_ops
from execution.screen.tree_parse import parse_inspect_tree


_last_dump_ts = 0.0
_last_tree = None
_last_dump_hash = None
# WebView 容器类名特征（与 WebViewProbe._screen_offset 的识别规则一致）。
# 有 DOM 节点时，容器节点的文本是整段 H5 文本的快照 —— 粒度错误（会把一大段
# H5 文本当成一个"目标"），因此在合并时抑制。
_WEBVIEW_CLASS_HINTS = ("WebView", "webview", "AwContents", "X5WebView",
                        "TitansWebView", "SonicWebView")
# 抑制容器文本的最小长度：短文本可能是容器自身的真实标签，不抑制。
_WEBVIEW_TEXT_SUPPRESS_MIN = 30


def _link_probe_nodes(nodes, base):
    """把探针导出的节点接入合并列表：parent 索引重基，补 children_idx 与 depth。

    探针只负责给"本层 parent 索引"。**跨渲染层不接链**（DOM 祖先链止于其根节点，
    不与 native 的 WebView 容器相连）—— 这是有意为之：上层只需知道"它在某个
    渲染层内部"，不需要把两层结构缝在一起。
    """
    n_local = len(nodes)
    for i, n in enumerate(nodes):
        p = n.get("parent")
        n["parent"] = (p + base) if isinstance(p, int) and 0 <= p < n_local else None
        n["children_idx"] = []
    for i, n in enumerate(nodes):
        p = n.get("parent")
        if isinstance(p, int) and base <= p < base + n_local:
            nodes[p - base]["children_idx"].append(i + base)
    for i, n in enumerate(nodes):
        depth, p, guard = 0, nodes[i].get("parent"), 0
        while isinstance(p, int) and base <= p < base + n_local and guard < 64:
            depth += 1
            guard += 1
            p = nodes[p - base].get("parent")
        nodes[i]["depth"] = depth


def _has_webview_container(nodes):
    """native 树里是否疑似存在 WebView 容器（用于决定要不要问探针）。

    **为什么必须闸门**：`get_current_nodes` 是每一步都会走的路径，且
    `invalidate_cache()` 每步都会重置探针的 CDP 不可达标记。若无差别询问
    `dump_nodes`，则每个步骤都会付一次 socket 扫描；App 内只要有任一 WebView
    （即使当前页不是 H5），还会加上端口转发 + CDP 往返 + DOM 枚举 —— 实测
    可达秒级，纯属浪费。

    WebView 容器在 native 树里必然是一个 View 节点（内部 DOM 才不可见），
    因此「native 里没有 WebView 节点」就可以安全跳过探针。
    **native 采不到时（nodes 为空）也跳过**：此时连容器屏幕偏移都拿不到
    （WebViewProbe._screen_offset 依赖同一个容器节点），CDP 坐标会退化为
    viewport 原点 —— 那是**错的坐标**，问了不如不问；同时避免采集失败的页面
    （如首页 MainActivity 必然超时）每步白扫一次 socket。
    与探针共用同一套类名 hints：hints 漏判时 offsets 同样拿不到，跳过的口径自洽。
    """
    if not nodes:
        return False  # 无法定位容器 → 偏移不可信，交给"纯 native"路径
    for n in nodes:
        cls = n.get("class_name") or ""
        if any(h in cls for h in _WEBVIEW_CLASS_HINTS):
            return True
    return False


def _probe_nodes(native_nodes):
    """聚合非 native 渲染层导出的节点（如 WebView DOM）。

    RendererProbe.dump_nodes 是可选能力：native 探针返回空列表（native 走
    inspect-tree 通道），因此这里可无差别遍历探针链。

    先过 `_has_webview_container` 闸门：无 WebView 容器就完全不问探针，
    保证非 H5 页面的执行开销与改造前一致。
    """
    if not _has_webview_container(native_nodes):
        return []
    from shared.context import get_probes
    merged = []
    for probe in get_probes():
        dump = getattr(probe, "dump_nodes", None)
        if not callable(dump):
            continue
        try:
            nodes = list(dump() or [])
        except Exception as e:
            name = getattr(probe, "probe_name", "probe")
            sys.stderr.write(f"  ⚠️  {name} 节点导出失败: {e}\n")
            continue
        if nodes:
            _link_probe_nodes(nodes, base=len(merged))
            merged.extend(nodes)
    return merged


def _dedup_key(node):
    """跨渲染层去重键：(文本, 中心坐标)。无文本且无坐标返回 None（不参与去重）。"""
    text = (node.get("text") or node.get("content_desc") or "").strip()
    x, y = node.get("x"), node.get("y")
    if x is None or y is None:
        return (text, None, None) if text else None
    return (text, int(x + (node.get("w") or 0) // 2), int(y + (node.get("h") or 0) // 2))


def _merge_renderer_nodes(native_nodes, probe_nodes):
    """native 与探针节点合并：抑制 WebView 容器文本 → 按 (文本, 中心) 去重。

    native 优先（保留原生语义与坐标精度）；探针节点仅在未重复时追加。
    """
    if not probe_nodes:
        return native_nodes
    merged = []
    for n in native_nodes:
        cls = n.get("class_name", "") or ""
        blob = n.get("all_text") or n.get("merged_text") or ""
        if any(h in cls for h in _WEBVIEW_CLASS_HINTS) and len(blob) >= _WEBVIEW_TEXT_SUPPRESS_MIN:
            n = dict(n)
            n["text"] = None
            n["content_desc"] = None
            n["all_text"] = ""
            n["merged_text"] = ""
        merged.append(n)
    seen = set()
    for n in merged:
        k = _dedup_key(n)
        if k:
            seen.add(k)
    for n in probe_nodes:
        k = _dedup_key(n)
        if k and k in seen:
            continue
        if k:
            seen.add(k)
        merged.append(n)
    return merged


def get_current_nodes(wait_sec=3, whole_screen=False):
    """获取当前**所有渲染层**的 UiNode 列表（native 视图树 + 各渲染探针）。

    统一入口：所有需要 UiNode 数据的调用方都应使用此函数。
    - native：dump_inspect_tree（8s 缓存；`whole_screen=True` 时不走缓存）；
    - 其它渲染层（如 WebView DOM）：探针链的 dump_nodes()，重基后合并去重。

    这样"目标模型"（tree_index）与依赖它的断言 T1/T1.5、目录、候选、邻域
    都对 H5 内容一致生效，不因渲染层不同而退化。

    Args:
        wait_sec: dump_inspect_tree 的超时时间
        whole_screen: True 时采全窗口（含系统进程窗口），供**遮挡/弹窗检测**使用——
            系统权限弹窗属系统进程窗口，按 App 过滤的采集里看不到它。

    Returns:
        list[dict] | None: UiNode 列表；所有渲染层都取不到时返回 None
    """
    raw = dump_inspect_tree(wait_sec=wait_sec, whole_screen=whole_screen)
    native_nodes = parse_inspect_tree(raw) if raw is not None else None
    if native_nodes is None:
        native_nodes = []
    probe_nodes = _probe_nodes(native_nodes)
    if probe_nodes:
        return _merge_renderer_nodes(native_nodes, probe_nodes)
    if not native_nodes and raw is None:
        return None
    return native_nodes
def _get_cached(max_age=8.0):
    if (_last_tree is not None
        and time.time() - _last_dump_ts < max_age):
        return _last_tree
    return None
def _update_cache(tree):
    global _last_dump_ts, _last_tree, _last_dump_hash
    _last_dump_ts = time.time()
    _last_tree = tree
    _last_dump_hash = hash(json.dumps(tree, sort_keys=True)) if tree else None
def invalidate_cache():
    """作废全部缓存（raw tree + 探针链）。

    UI 状态变更后调用，确保重新采集而非命中旧树。
    同时作废探针链——页面切换后渲染容器可能出现或消失，
    沿用旧链会导致对着已销毁的渲染器取 DOM。"""
    global _last_dump_ts, _last_tree
    _last_dump_ts = 0.0
    _last_tree = None
    from shared.context import invalidate_probes
    invalidate_probes()
def dump_inspect_tree(wait_sec=6, max_attempts=2, whole_screen=False):
    """调用 inspect-tree 获取视图树 JSON，返回 dict 或 None。

    结果自动缓存 8 秒——连续调用（如同一步骤的 tap + assert）不会重复采集。
    全部失败后返回 None。

    `whole_screen=True` 采**全窗口**节点（含系统进程窗口，遮挡/弹窗检测用）且
    **不读不写缓存**：遮挡检测要的是"此刻真实屏幕"，命中 8 秒前的旧树会把刚弹出的
    系统弹窗漏掉；同时也避免全窗口树污染 App 视图树缓存。
    """
    if not whole_screen:
        cached = _get_cached()
        if cached is not None:
            sys.stderr.write(f"[inspect_tree] 命中缓存 (age={time.time()-_last_dump_ts:.1f}s)\n")
            return cached

    ensure_dirs()

    ops = get_platform_ops()
    # imeituan CLI 的 --timeout 只接受整数，wait_sec 可能为 float（如 argparse --wait 3.0），
    # 直接相乘会得到 15.0 导致 CLI 报 "Expected an integer but received: 15.0"。
    # 统一 int() 归一，兜底至少 15 秒。
    timeout = max(int(wait_sec * 5), 15)
    for attempt in range(max_attempts):
        if os.path.isfile(inspect_tree_cache_path()):
            os.remove(inspect_tree_cache_path())
        _t0 = time.time()
        sys.stderr.write(f"[inspect_tree] 开始采集视图树 (wait_sec={wait_sec}, timeout={timeout}, attempt={attempt+1}/{max_attempts})...\n")
        r = ops.inspect_tree(inspect_tree_cache_path(), timeout=timeout,
                             whole_screen=whole_screen)
        _elapsed = time.time() - _t0
        sys.stderr.write(f"[inspect_tree] 采集完成: rc={r.returncode}, elapsed={_elapsed:.1f}s\n")

        _file_ok = os.path.isfile(inspect_tree_cache_path())
        if r.returncode != 0 or not _file_ok:
            # 区分两种失败：CLI 非零退出 vs 退出正常但未产出文件
            if r.returncode != 0:
                _reason = f"CLI 非零退出 (returncode={r.returncode})"
            else:
                _reason = f"CLI 退出码为 0 但未生成输出文件 {inspect_tree_cache_path()}"

            _err = (getattr(r, "stderr", "") or "").strip()
            _out = (getattr(r, "stdout", "") or "").strip()

            sys.stderr.write(
                f"⚠️  inspect-tree 失败（第{attempt+1}/{max_attempts}次）: {_reason}，耗时 {_elapsed:.1f}s\n"
                f"    CMD: imeituan control inspect-tree --timeout {timeout} -o {inspect_tree_cache_path()}\n")
            if _err:
                sys.stderr.write(f"    STDERR: {_err[:800]}\n")
            if _out:
                sys.stderr.write(f"    STDOUT: {_out[:800]}\n")
            if not _err and not _out:
                sys.stderr.write("    (CLI 无任何 stdout/stderr 输出)\n")

            if attempt < max_attempts - 1:
                sys.stderr.write("    → 重试...\n")
                time.sleep(0.5)
                continue
            sys.stderr.write(f"⚠️  inspect-tree: 共尝试 {max_attempts} 次，全部失败\n")
            try:
                from shared.observability.runtime_audit import append_event
                from shared.paths import get_active_run
                _case = get_active_run()
                if _case:
                    from shared.case_utils import resolve_case_path
                    append_event(resolve_case_path(_case), "engine.inspect.tree.retry", {
                        "attempts": max_attempts, "last_reason": _reason, "last_error": _err[:200],
                    })
            except Exception as e:
                soft_fail("infra", "INSPECT_TREE_RETRY_AUDIT_FAILED", e)
            return None

        try:
            tree = read_json(inspect_tree_cache_path(), default={})
        except (json.JSONDecodeError, OSError):
            if attempt < max_attempts - 1:
                sys.stderr.write(f"⚠️  inspect-tree: JSON 解析失败（第{attempt+1}/{max_attempts}次），重试...\n")
                time.sleep(0.5)
                continue
            sys.stderr.write(f"⚠️  inspect-tree: JSON 解析失败（{max_attempts}次均失败）\n")
            return None

        if not tree or not isinstance(tree, dict):
            if attempt < max_attempts - 1:
                sys.stderr.write(f"⚠️  inspect-tree: JSON 解析失败（第{attempt+1}/{max_attempts}次），重试...\n")
                time.sleep(0.5)
                continue
            sys.stderr.write(f"⚠️  inspect-tree: JSON 解析失败（{max_attempts}次均失败）\n")
            return None

        if not whole_screen:
            _update_cache(tree)
        return tree

    return None
