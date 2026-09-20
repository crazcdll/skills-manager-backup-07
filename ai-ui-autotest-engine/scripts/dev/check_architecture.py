#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""架构守卫 —— 用静态检查固化错误体系与分层约束，防止回退。

六项检查：

  1. no-sys-exit            （硬失败）除 CLI 边界外，任何模块不得调用 `sys.exit()`
                            —— 业务/核心层只 raise core.errors.AutotestError 或返回退出码，
                               由 cli_utils.run_with_guard 唯一决定进程退出码。
  2. no-silent-swallow      （棘轮）`except ...: pass` 只允许在显式白名单内；
                            总数不得超过 SWALLOW_BASELINE（只许减少）。
  3. layering               （硬失败）跨包模块级强连通分量（SCC）必须为 0，
                            即不允许出现相互 import 的模块环。
  4. all-modules-import     （硬失败）逐个 import 所有模块，不得有导入错误；
                            抓「漏再导出 / 破损导入」（只看 import cli 或编译发现不了）。
  5. staged-deletion-referenced（硬失败）git 暂存区里删除的模块不得仍被引用；
                            固化「删除旧模块必须在所有引用方改完之后」这条纪律。
  6. placeholder-single-entry（硬失败）`resolve_placeholders` 只允许在 flow_init.py 调用。
                            steps-input 在 flow-init 时被解析并落盘为唯一事实来源，
                            运行期读者只读解析后的产物；其它模块各自解析会让
                            C0 case-init 重载时又把未解析原文带回来（历史回归根因）。

用法：
    python3 scripts/dev/check_architecture.py                  # 检查
    python3 scripts/dev/check_architecture.py --list-swallow   # 列出全部吞噬点
退出码：0 通过 / 1 失败。
"""
import ast
import importlib
import os
import re
import subprocess
import sys
from collections import defaultdict

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_ROOT = os.path.dirname(SCRIPTS_DIR)
# 向上探测到的候选起点；真正的 git 仓库根由 git rev-parse 确定，
# 因为 `git diff --name-only` 输出的路径是相对**仓库根**而非 cwd 的。
GIT_CWD = os.path.dirname(SKILL_ROOT)

# ── 规则 1：允许调用 sys.exit 的模块（仅 CLI 边界）────────────────────
SYS_EXIT_ALLOWLIST = {
    "cli_utils.py",  # 唯一错误边界：把异常 / 返回码转成进程退出码
}

# ── 规则 2：允许 `except: pass` 的模块（有意自保护 / 解析兜底）────────
# 逐条理由见文件内注释；白名单外的新增吞噬会被守卫拦截。
SWALLOW_ALLOWLIST = {
    "core/errors.py",                                  # soft_fail 自身：审计失败不得反向炸主流程
    "cli_utils.py",                                    # 错误边界自保护：落盘 / 上报失败不得反向抛出
    "context/__init__.py",                             # 平台解析失败时静默跳过（与 ImportError 兜底等价）
    "core/audit/runtime_audit.py",                     # 审计失败不得反向炸主流程
    "core/audit/usage_reporter.py",                    # 上报 fire-and-forget
    "core/audit/exception_reporter.py",                # 上报 fire-and-forget
    "core/util/json_utils.py",                         # 读文件失败返回默认值（类型化 API）
    "core/util/paths.py",                              # 清理目录 best-effort
    "core/flow/step_scheduler.py",                     # steps.jsonl 读取容错
    "core/flow/flow_init.py",                          # 归档清理 best-effort
    "core/flow/steps_generator.py",                    # 目录创建容错
    "environment/helpers/question_utils.py",           # 类型转换兜底（int/float 解析失败保留原值）
    "assertions/data/track.py",                        # JSON 解析失败保留原值（数据断言容错）
    "assertions/data/api.py",                          # 同上
    "device_platform/android/ops.py",                  # 可选平台钩子探测（ImportError）
    "device_platform/android/probes/webview.py",       # CDP 链路多级降级 + JSON 容错
    "device_platform/harmony/ops.py",                  # JSON 容错
    "device_platform/harmony/probes/inspect_tree.py",  # 设备临时目录清理
    "infra/ssl_helper.py",                             # SSL 上下文降级
    "infra/node_env.py",                               # 环境探测兜底
    "infra/check_deps.py",                             # 依赖探测多路径尝试
    "infra/appmock_auth.py",                           # 缓存 / 降级路径
    "infra/app_installer.py",                          # 安装探测多路径尝试
    "report/data_collector.py",                        # 报告层 I/O：文件缺失/不可读即降级并留痕
    "device_platform/ios/ops.py",                      # iOS 骨架：WDA / imeituan 双路径降级
}

# ── 规则 2 棘轮基线：当前存量吞噬点数量，只允许下降 ────────────────
SWALLOW_BASELINE = 57

# ── 规则 6：允许调用 resolve_placeholders 的模块（占位符解析唯一入口）────
# flow_init.py        流初始化边界：解析后落盘为唯一事实来源
# placeholder_resolver.py  解析器定义处（内部递归自调）
PLACEHOLDER_RESOLVE_ALLOWLIST = {
    "core/flow/flow_init.py",
    "core/placeholder/placeholder_resolver.py",
}

_TOP_PKGS = {
    "actions", "assertions", "context", "core", "device_platform",
    "environment", "infra", "mock", "report", "screen_state",
}


def _iter_py_files():
    for root, dirs, files in os.walk(SCRIPTS_DIR):
        if "__pycache__" in root:
            continue
        rel_root = os.path.relpath(root, SCRIPTS_DIR).replace(os.sep, "/")
        if rel_root == "dev" or rel_root.startswith("dev/"):
            continue
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


def _rel(path):
    return os.path.relpath(path, SCRIPTS_DIR).replace(os.sep, "/")


def _parse(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return ast.parse(fh.read())
    except (OSError, SyntaxError):
        return None


def check_no_sys_exit():
    """规则 1：非边界模块不得调用 sys.exit(...)。"""
    bad = []
    for path in _iter_py_files():
        tree = _parse(path)
        if tree is None:
            continue
        rel = _rel(path)
        if rel in SYS_EXIT_ALLOWLIST:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "exit"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "sys"):
                bad.append(f"{rel}:{node.lineno}")
    return bad


def _is_bare_pass(body):
    """body 是否为单个 `pass`。"""
    return len(body) == 1 and isinstance(body[0], ast.Pass)


def find_silent_swallows():
    """返回 [(rel, lineno)]，标记所有 `except ...: pass`。"""
    found = []
    for path in _iter_py_files():
        tree = _parse(path)
        if tree is None:
            continue
        rel = _rel(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _is_bare_pass(node.body):
                found.append((rel, node.lineno))
    return found


def check_layering():
    """规则 3：跨包模块级 import 环（SCC）必须为 0。"""
    mods = {}
    for path in _iter_py_files():
        key = _rel(path)[:-3].replace("/", ".")
        mods[key] = path
        if key.endswith(".__init__"):
            mods[key[: -len(".__init__")]] = path

    def resolve(name):
        if not name:
            return None
        if name in mods:
            return name
        parts = name.split(".")
        for i in range(len(parts), 0, -1):
            cand = ".".join(parts[:i])
            if cand in mods:
                return cand
        return None

    graph = defaultdict(set)
    for mod, path in mods.items():
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                t = resolve(node.module)
                if t and t != mod:
                    graph[mod].add(t)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    t = resolve(a.name)
                    if t and t != mod:
                        graph[mod].add(t)

    index, low, on, stack, comps = {}, {}, {}, [], []

    def strongconnect(v):
        index[v] = low[v] = len(index)
        stack.append(v)
        on[v] = True
        for w in graph.get(v, ()):
            if w not in index:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif on.get(w):
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on[w] = False
                comp.append(w)
                if w == v:
                    break
            comps.append(comp)

    sys.setrecursionlimit(20000)
    for v in list(mods):
        if v not in index:
            strongconnect(v)

    def pkg(m):
        return m.split(".")[0]

    return [c for c in comps
            if len(c) > 1 and len({pkg(x) for x in c}) > 1]


def check_all_modules_importable():
    """规则4：逐个 import 所有模块，返回失败列表。

    只看 `import cli` 或 `compileall` 发现不了「漏再导出 / 破损导入」：
    例如 facade 漏再导出某个仍被外部引用的私有符号，会导致数十个模块 ImportError，
    而入口模块可能仍能导入（只在实际调用时才崩）。逐模块导入才能暴露。
    """
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    bad = []
    for path in _iter_py_files():
        mod = _rel(path)[:-3].replace("/", ".")
        if mod.endswith(".__init__"):
            mod = mod[: -len(".__init__")]
        try:
            importlib.import_module(mod)
        except Exception as exc:  # noqa: BLE001 — 导入失败一律报出（附类型与摘要）
            bad.append(f"{mod} -> {type(exc).__name__}: {str(exc)[:100]}")
    return bad


def _git_repo_root():
    """返回 git 仓库根绝对路径；非 git 仓库返回 None。"""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=GIT_CWD, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def check_staged_deletions_not_referenced():
    """规则5：git 暂存区里被删除的模块，不得仍被任何模块引用。

    固化「删除旧模块必须放在所有引用方改完之后」这条纪律——否则会留下
    ImportError 破损态（曾因先删 login_primitives.py 导致 cli 起不来）。
    非 git 仓库 / 无暂存改动时静默跳过。
    """
    repo_root = _git_repo_root()
    if not repo_root:
        return []
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--diff-filter=D", "--name-only"],
            cwd=repo_root, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []

    # git 输出的路径相对仓库根；换算成本仓库内的 scripts/ 相对路径前缀
    prefix = os.path.relpath(SCRIPTS_DIR, repo_root).replace(os.sep, "/") + "/"
    bad = []
    for line in proc.stdout.splitlines():
        staged = line.strip()
        if not staged.endswith(".py") or not staged.startswith(prefix):
            continue
        rel_deleted = staged[len(prefix):]
        mod = rel_deleted[:-3].replace("/", ".")
        if mod.endswith(".__init__"):
            mod = mod[: -len(".__init__")]
        pattern = re.compile(r"\b" + re.escape(mod) + r"\b")
        for path in _iter_py_files():
            if _rel(path) == rel_deleted:
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            if pattern.search(text):
                bad.append(f"{mod} 已 staged 删除，但仍被 {_rel(path)} 引用")
    return bad


def check_placeholder_resolve_single_entry():
    """规则6：resolve_placeholders 只允许在 flow_init.py 调用。

    steps-input 被 flow-init 解析后落盘为唯一事实来源（原文档另存 raw），
    运行期读者（case-init / 报告等）只读解析后的产物。此规则固化
    「解析收敛在边界」这条纪律，防止读者各自解析 / 漏解析而复发回归。
    """
    bad = []
    for path in _iter_py_files():
        if _rel(path) in PLACEHOLDER_RESOLVE_ALLOWLIST:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "resolve_placeholders"):
                bad.append(f"{_rel(path)}:{node.lineno}")
    return bad


def main():
    list_swallow = "--list-swallow" in sys.argv
    failures = []

    bad_exit = check_no_sys_exit()
    if bad_exit:
        failures.append(
            "规则1 失败：以下模块调用了 sys.exit()（应改为 raise core.errors 错误 / "
            "由 CLI 边界统一退出）\n  " + "\n  ".join(bad_exit)
        )

    swallows = find_silent_swallows()
    if len(swallows) > SWALLOW_BASELINE:
        failures.append(
            f"规则2 失败：静默吞噬 {len(swallows)} 处 > 基线 {SWALLOW_BASELINE}（只许减少）"
        )
    if list_swallow:
        unlisted = [s for s in swallows if s[0] not in SWALLOW_ALLOWLIST]
        print(f"[swallow] 共 {len(swallows)} 处（白名单外 {len(unlisted)} 处）")
        for rel, ln in sorted(swallows):
            mark = "  " if rel in SWALLOW_ALLOWLIST else "! "
            print(f"  {mark}{rel}:{ln}")

    sccs = check_layering()
    if sccs:
        lines = ["  SCC: " + " <-> ".join(sorted(c)) for c in sccs]
        failures.append("规则3 失败：存在跨包模块级循环依赖\n" + "\n".join(lines))

    import_bad = check_all_modules_importable()
    if import_bad:
        failures.append(
            "规则4 失败：以下模块无法导入（漏再导出 / 破损导入）\n  "
            + "\n  ".join(import_bad)
        )

    del_bad = check_staged_deletions_not_referenced()
    if del_bad:
        failures.append(
            "规则5 失败：被删除的模块仍被引用（应先改完所有引用方再删）\n  "
            + "\n  ".join(del_bad)
        )

    resolve_bad = check_placeholder_resolve_single_entry()
    if resolve_bad:
        failures.append(
            "规则6 失败：resolve_placeholders 只允许在 flow_init.py 调用"
            "（steps-input 由 flow-init 统一解析并落盘，其它模块不得再各自解析）\n  "
            + "\n  ".join(resolve_bad)
        )

    if failures:
        print("❌ 架构守卫未通过：\n")
        for f in failures:
            print(f + "\n")
        return 1

    print(f"✅ 架构守卫通过"
          f"（sys.exit 违规 0；静默吞噬 {len(swallows)}/{SWALLOW_BASELINE}；跨包循环 0；"
          f"模块导入 {len(list(_iter_py_files()))} 全通；无破损删除引用；"
          f"占位符解析单一入口 0 违规）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
