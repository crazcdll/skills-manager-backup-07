#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重构迁移校验器 —— 固化「跨模块搬迁」的三项校验，替代手工比对。

用法：
    # 校验一次拆分：旧文件（git ref 或路径）→ 若干新文件
    python3 scripts/dev/check_refactor.py \\
        --old HEAD:scripts/report/builders.py \\
        --new scripts/report/steps.py scripts/report/case_report.py ...

    # 允许多个旧文件（多合一场景）：--old 可重复
    python3 scripts/dev/check_refactor.py --old HEAD:a.py --old HEAD:b.py --new c.py

校验项：
  1. 符号完备性     旧文件的每个顶层符号（def / class / 模块级赋值）必须能在新文件集合中找到
                    → 缺失即 **失败**（搬家丢东西）
  2. 函数体逐字比对 同名 def/class（以及模块级常量）的 `ast.unparse` 必须一致
                    → 默认 **告警**（列出差异，便于确认是否为有意改造）；加 `--strict` 转为失败
  3. 全模块导入     逐个 import 所有模块，确认无破损导入 / 循环依赖
                    → 失败（漏再导出这类问题只在逐模块导入时才暴露）

退出码：0 通过（可能带告警） / 1 失败。

【为什么需要它】跨模块搬迁曾三次踩坑：别名丢失（NameError）、漏再导出（38 模块 ImportError）、
删旧文件过早（破损态）。这三项校验每次都手写一遍，本脚本把「符号完备性 + 函数体比对 + 导入扫描」
固化为一条命令。
"""
import argparse
import ast
import importlib
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_HINT = os.path.dirname(os.path.dirname(SCRIPTS_DIR))


# ═══════════════════════════════════════════════════════════════════
# 读取旧文件（支持 git ref:path）
# ═══════════════════════════════════════════════════════════════════

def _git_root():
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=_REPO_HINT, capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _read_old(spec):
    """spec 形如 'HEAD:path/to.py' 或普通文件路径；返回源码文本。

    git 路径必须相对**仓库根**；但调用方更习惯写 skill 内的 `scripts/xxx.py`，
    因此依次尝试 `path` 与 `<skill 相对仓库根>/path` 两种写法。
    """
    if ":" in spec:
        ref, _, path = spec.partition(":")
        cwd = _git_root() or "."
        root = _git_root()
        skill_prefix = ""
        if root:
            skill_prefix = os.path.relpath(
                os.path.dirname(SCRIPTS_DIR), root
            ).replace(os.sep, "/") + "/"
        candidates = [path]
        if skill_prefix and not path.startswith(skill_prefix):
            candidates.append(skill_prefix + path)
        last_err = ""
        for cand in candidates:
            try:
                proc = subprocess.run(
                    ["git", "show", f"{ref}:{cand}"],
                    cwd=cwd, capture_output=True, text=True, timeout=15,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise SystemExit(f"ERROR: 读取 {spec} 失败: {exc}")
            if proc.returncode == 0:
                return proc.stdout
            last_err = proc.stderr.strip()
        raise SystemExit(
            f"ERROR: git show {spec} 失败（已尝试 {candidates}）: {last_err[:200]}"
        )
    p = Path(spec)
    if not p.is_file():
        raise SystemExit(f"ERROR: 文件不存在: {spec}")
    return p.read_text(encoding="utf-8")


def _resolve_new(path):
    """新文件路径解析：依次尝试 cwd / scripts/ / 仓库根。"""
    cands = [Path(path), Path(SCRIPTS_DIR) / path]
    root = _git_root()
    if root:
        cands.append(Path(root) / path)
    for c in cands:
        if c.is_file():
            return c
    return None


# ═══════════════════════════════════════════════════════════════════
# 符号提取与比对
# ═══════════════════════════════════════════════════════════════════

def _extract(src):
    """返回 (defs, consts)：{name: ast node}。"""
    tree = ast.parse(src)
    defs, consts = {}, {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs[n.name] = n
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = n
    return defs, consts


def check_symbols(old_defs, old_consts, new_defs, new_consts):
    """返回缺失符号列表。"""
    missing = []
    for name in sorted(old_defs):
        if name not in new_defs:
            missing.append(f"def/class `{name}`")
    for name in sorted(old_consts):
        if name not in new_consts:
            missing.append(f"常量 `{name}`")
    return missing


def check_bodies(old_defs, old_consts, new_defs, new_consts):
    """返回实现体有差异的符号列表。"""
    changed = []
    for name in sorted(set(old_defs) & set(new_defs)):
        if ast.unparse(old_defs[name]) != ast.unparse(new_defs[name]):
            changed.append(f"def/class `{name}`")
    for name in sorted(set(old_consts) & set(new_consts)):
        if ast.unparse(old_consts[name]) != ast.unparse(new_consts[name]):
            changed.append(f"常量 `{name}`")
    return changed


# ═══════════════════════════════════════════════════════════════════
# 全模块导入扫描
# ═══════════════════════════════════════════════════════════════════

def scan_imports():
    """逐个 import 所有模块（排除 dev/ 与 __pycache__），返回失败列表。"""
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    bad = []
    count = 0
    for root, dirs, files in os.walk(SCRIPTS_DIR):
        if "__pycache__" in root:
            continue
        rel_root = os.path.relpath(root, SCRIPTS_DIR).replace(os.sep, "/")
        if rel_root == "dev" or rel_root.startswith("dev/"):
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            rel = (rel_root + "/" + f) if rel_root != "." else f
            mod = rel[:-3].replace("/", ".")
            if mod.endswith(".__init__"):
                mod = mod[: -len(".__init__")]
            count += 1
            try:
                importlib.import_module(mod)
            except Exception as exc:  # noqa: BLE001 — 导入失败一律报出
                bad.append(f"{mod} -> {type(exc).__name__}: {str(exc)[:100]}")
    return count, bad


# ═══════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(
        description="重构迁移校验：符号完备性 + 函数体逐字比对 + 全模块导入扫描",
    )
    ap.add_argument("--old", action="append", required=True,
                    help="旧文件：'<git-ref>:<path>'（如 HEAD:scripts/x.py）或普通路径；可重复")
    ap.add_argument("--new", nargs="+", required=True, help="新文件路径（1 个或多个）")
    ap.add_argument("--strict", action="store_true", help="函数体有差异时也判为失败")
    ap.add_argument("--no-import", action="store_true", help="跳过全模块导入扫描")
    args = ap.parse_args()

    new_paths = []
    for raw in args.new:
        p = _resolve_new(raw)
        if p is None:
            raise SystemExit(f"ERROR: 新文件不存在: {raw}")
        new_paths.append(p)

    old_defs, old_consts = {}, {}
    for spec in args.old:
        d, c = _extract(_read_old(spec))
        old_defs.update(d)
        old_consts.update(c)

    new_defs, new_consts = {}, {}
    for p in new_paths:
        d, c = _extract(p.read_text(encoding="utf-8"))
        new_defs.update(d)
        new_consts.update(c)

    print(f"旧文件: {len(args.old)} 个 → 符号 {len(old_defs)} def/class + {len(old_consts)} 常量")
    print(f"新文件: {len(new_paths)} 个 → 符号 {len(new_defs)} def/class + {len(new_consts)} 常量")

    failures, warnings = [], []

    missing = check_symbols(old_defs, old_consts, new_defs, new_consts)
    if missing:
        failures.append("符号完备性失败：以下符号在迁移后丢失\n  " + "\n  ".join(missing))
    else:
        print("  [1/3] 符号完备性：无丢失 ✅")

    changed = check_bodies(old_defs, old_consts, new_defs, new_consts)
    if changed:
        msg = ("实现体有差异（请逐条确认是否为有意改造）:\n  " + "\n  ".join(changed))
        (failures if args.strict else warnings).append(msg)
        print(f"  [2/3] 函数体比对：{len(changed)} 个符号有差异 "
              f"（{'严格模式→失败' if args.strict else '告警'}）")
    else:
        print("  [2/3] 函数体比对：全部逐字一致 ✅")

    if args.no_import:
        print("  [3/3] 全模块导入：已跳过（--no-import）")
    else:
        count, bad = scan_imports()
        if bad:
            failures.append(f"全模块导入失败（{len(bad)} 个）\n  " + "\n  ".join(bad))
        else:
            print(f"  [3/3] 全模块导入：{count} 个模块全部可导入 ✅")

    if warnings:
        print("\n⚠️  告警：")
        for w in warnings:
            print(w + "\n")

    if failures:
        print("\n❌ 迁移校验未通过：")
        for f in failures:
            print(f + "\n")
        return 1

    print("\n✅ 迁移校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
