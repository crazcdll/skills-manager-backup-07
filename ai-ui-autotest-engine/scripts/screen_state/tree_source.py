"""视图树采集与缓存：dump / 8s 缓存 / 失效。"""
import json
import os
import sys
import time
from core.util.json_utils import read_json
from core.errors import soft_fail
from core.util.paths import ensure_dirs, INSPECT_TREE_CACHE
from context import get_platform_ops
from screen_state.tree_parse import parse_inspect_tree


_CACHE_JSON = INSPECT_TREE_CACHE
_last_dump_ts = 0.0
_last_tree = None
_last_dump_hash = None
def get_current_nodes(wait_sec=3):
    """获取当前视图树的 UiNode 列表。

    统一入口：所有需要 UiNode 数据的调用方都应使用此函数。
    内部依赖 dump_inspect_tree 的 raw tree 缓存（8s），不做二次解析缓存。

    Args:
        wait_sec: dump_inspect_tree 的超时时间

    Returns:
        list[dict] | None: UiNode 列表，采集失败返回 None
    """
    raw = dump_inspect_tree(wait_sec=wait_sec)
    if raw is None:
        return None
    return parse_inspect_tree(raw)
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
    from context import invalidate_probes
    invalidate_probes()
def dump_inspect_tree(wait_sec=6, max_attempts=2):
    """调用 inspect-tree 获取视图树 JSON，返回 dict 或 None。

    结果自动缓存 8 秒——连续调用（如同一步骤的 tap + assert）不会重复采集。
    全部失败后返回 None。
    """
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
        if os.path.isfile(_CACHE_JSON):
            os.remove(_CACHE_JSON)
        _t0 = time.time()
        sys.stderr.write(f"[inspect_tree] 开始采集视图树 (wait_sec={wait_sec}, timeout={timeout}, attempt={attempt+1}/{max_attempts})...\n")
        r = ops.inspect_tree(_CACHE_JSON, timeout=timeout)
        _elapsed = time.time() - _t0
        sys.stderr.write(f"[inspect_tree] 采集完成: rc={r.returncode}, elapsed={_elapsed:.1f}s\n")

        _file_ok = os.path.isfile(_CACHE_JSON)
        if r.returncode != 0 or not _file_ok:
            # 区分两种失败：CLI 非零退出 vs 退出正常但未产出文件
            if r.returncode != 0:
                _reason = f"CLI 非零退出 (returncode={r.returncode})"
            else:
                _reason = f"CLI 退出码为 0 但未生成输出文件 {_CACHE_JSON}"

            _err = (getattr(r, "stderr", "") or "").strip()
            _out = (getattr(r, "stdout", "") or "").strip()

            sys.stderr.write(
                f"⚠️  inspect-tree 失败（第{attempt+1}/{max_attempts}次）: {_reason}，耗时 {_elapsed:.1f}s\n"
                f"    CMD: imeituan control inspect-tree --timeout {timeout} -o {_CACHE_JSON}\n")
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
                from core.audit.runtime_audit import append_event
                from core.util.paths import get_active_case
                _case = get_active_case()
                if _case:
                    from core.util.case_utils import resolve_case_path
                    append_event(resolve_case_path(_case), "engine.inspect.tree.retry", {
                        "attempts": max_attempts, "last_reason": _reason, "last_error": _err[:200],
                    })
            except Exception as e:
                soft_fail("infra", "INSPECT_TREE_RETRY_AUDIT_FAILED", e)
            return None

        try:
            tree = read_json(_CACHE_JSON, default={})
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

        _update_cache(tree)
        return tree

    return None
