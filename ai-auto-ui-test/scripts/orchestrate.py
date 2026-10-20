#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多 Agent 编排层 CLI —— 拆分 + 调度编排（plan）。

职责边界：
  · 编排层（本 Skill = ai-auto-ui-test）负责「拆分 / 派发 / 汇总」；
  · 本脚本只承担其中的 **拆分与调度编排**（纯本地、确定性、零外部依赖）；
  · 「派发子 Agent」由 AI 按 SKILL.md 执行（并行 Task）；子 Agent 执行完成后，结果
    **随 Task 直接返回编排层** —— 无需回写状态文件（Task 同步并行模型，子 Agent 非游离进程）；
  · 报告 **各自独立**（阶段 5「原子追加 / 汇总成一份」未落地前，不做预置与聚合）。

输入（单一标准）：**用例目录** —— 目录下每个 `*.md` = 一个用例（递归）；`case_id` = 文件名去扩展名。
规范位置 `<ai-app-flow>/.docs/{需求名}/flows/`；约定外目录告警。
共享环境信息经 `--env` / `--env-file` 传入。

调度模型（滚动补位 / 滑动窗口）：
  · **启用门槛**：用例数 < 3（1~2 个）时**不使用子 Agent**（单份直接执行），plan 会拒绝；
  · **每 Agent 用例上限** `--max-cases`（默认 2）→ 分片 = 按该上限连续切块（有序 = 待跑队列）；
  · **并发上限** `--concurrency`（默认 4）→ 同时在跑的子 Agent 上限；
  · AI 滚动派发：先起 `concurrency` 个，**谁先跑完就立刻从队首补下一个**，直到队列跑空且全部结束
    （一个慢分片不拖住其他分片）。

编排产物目录：<SKILL_DIR>/.orchestration/<task_id>/
  manifest.json          任务级索引：task 元信息 + 共享环境 + 分片列表（= 待跑队列）
  cases/                 原始用例快照（plan 时从 --cases 拷贝，本任务只读副本）
  shards/shard-NN.json   分片输入：env + cases（flow_path 指向 cases/ 快照，子 Agent 只读）

滚动保留（keep-latest-N）—— 默认各保留「最近 10 份」，按最近修改时间倒序：
  · `.orchestration/` 的一级 task 目录；
  · `<ai-app-flow>/.docs/` 的一级需求目录（用例资产根，`--cases` 的上级）。
  超出份数在 `plan` 成功后自动清理（可用 `--no-prune` 关闭）；本次任务的产物目录与
  `--cases` 所在的需求目录**恒被保护**，永不清理；也可单独执行 `prune` 手动滚动清理。

用法：
  python3 scripts/orchestrate.py plan --cases <用例目录> [--max-cases 2] [--concurrency 4] [--env '<json>']
                                 [--keep 10] [--no-prune]
  python3 scripts/orchestrate.py prune [--keep 10] [--dry-run]
"""

import argparse
import glob
import json
import os
import shutil
import sys
import time
import uuid

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)
ORCH_ROOT = os.path.join(SKILL_DIR, ".orchestration")
# 用例资产根：同级 Skill `ai-app-flow` 的 .docs/（一级子目录 = 一个需求记录）
DOCS_ROOT = os.path.join(os.path.dirname(SKILL_DIR), "ai-app-flow", ".docs")

DEFAULT_MAX_CASES = 2
DEFAULT_CONCURRENCY = 4
MIN_CASES_FOR_ORCHESTRATION = 3
# 滚动保留份数（.orchestration 与 .docs 各自保留的最近记录数）
DEFAULT_KEEP = 10


# ─── 通用工具 ───────────────────────────────────────────────────────────────

def _task_dir(task_id):
    return os.path.join(ORCH_ROOT, task_id)


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _new_task_id():
    return "orch-" + time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _chunk(seq, size):
    """按固定大小连续切块（最后一块可不足 size）。"""
    size = max(1, int(size))
    return [seq[i:i + size] for i in range(0, len(seq), size)]


# ─── 滚动保留（keep-latest-N）───────────────────────────────────────────────

def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _list_records(root):
    """列出一级子目录「记录」，按最近修改倒序（最近的在前）。"""
    if not os.path.isdir(root):
        return []
    items = []
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if name.startswith(".") or not os.path.isdir(p):
            continue
        items.append((p, _mtime(p)))
    items.sort(key=lambda t: (t[1], os.path.basename(t[0])), reverse=True)
    return [p for p, _ in items]


def _is_ancestor(ancestor, path):
    """ancestor 是 path 本身或其祖先目录时返回 True。"""
    ancestor = os.path.abspath(ancestor)
    path = os.path.abspath(path)
    return path == ancestor or path.startswith(ancestor + os.sep)


def _top_record(root, path):
    """返回 path 在 root 下所属的一级记录目录；不在 root 下则 None。"""
    if not path:
        return None
    root_abs, path_abs = os.path.abspath(root), os.path.abspath(path)
    rel = os.path.relpath(path_abs, root_abs)
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return None
    return os.path.join(root_abs, rel.split(os.sep)[0])


def _prune(root, keep, protect=(), dry_run=False):
    """把 root 下的一级记录滚动保留最近 keep 份，返回 (保留列表, 清理列表)。

    protect 中的记录（及其后代）永不被清理 —— 用于保护本次任务产物与用例源目录。
    """
    records = _list_records(root)
    protected = [os.path.abspath(p) for p in protect if p]
    kept, dropped = [], []
    for p in records:
        ap = os.path.abspath(p)
        if len(kept) < keep or any(_is_ancestor(pp, ap) for pp in protected):
            kept.append(p)
        else:
            dropped.append(p)
    for p in dropped:
        if not dry_run:
            shutil.rmtree(p, ignore_errors=True)
    return kept, dropped


def _report_prune(label, root, kept, dropped, dry_run):
    if not os.path.isdir(root):
        print(f"  · {label}: 目录不存在，跳过")
        return
    verb = "将清理" if dry_run else "已清理"
    print(f"  · {label}: 保留 {len(kept)} 份 / {verb} {len(dropped)} 份")
    print(f"      {root}")
    for p in dropped:
        print(f"      - {os.path.basename(p)}")


# ─── 用例目录位置约定（护栏）─────────────────────────────────────────────────

# 约定：用例资产在所属 Skill 安装目录内（路径含 skills/ 段）；落在项目根、但不在 skills/ 下 → 告警。
_CONVENTION_HINT = "   约定：<某 Skill 安装目录>/.docs/{需求名}/flows/"


def _project_root(start):
    """向上查找项目根（含 .claude / .catpaw 的最近祖先）；找不到返回 None。"""
    d = os.path.abspath(start)
    for _ in range(15):
        if (os.path.isdir(os.path.join(d, ".claude"))
                or os.path.isdir(os.path.join(d, ".catpaw"))):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _convention_warning(cases_dir):
    """用例目录不在约定位置（项目根内、但不在 skills/ 下）时返回告警文案；否则 None。"""
    if "skills" in cases_dir.split(os.sep):
        return None
    if not _project_root(cases_dir):
        return None
    return (
        f"⚠️  用例目录不在约定位置：{cases_dir}\n"
        f"{_CONVENTION_HINT}\n"
        f"   项目根自建目录不被 gitignore、无清理流程接管；建议迁移后重跑。"
    )


# ─── 输入解析（单一标准：用例目录）────────────────────────────────────────

def _scan_cases(cases_dir):
    """扫描用例目录：每个 *.md = 一个用例；返回 (目录绝对路径, cases)。"""
    d = os.path.abspath(cases_dir)
    if not os.path.isdir(d):
        raise SystemExit(f"❌ --cases 必须是「用例目录」: {d} 不是目录")
    paths = sorted(glob.glob(os.path.join(d, "**", "*.md"), recursive=True))
    if not paths:
        raise SystemExit(f"❌ 用例目录下没有 .md 文件: {d}")

    cases = []
    seen = {}
    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        seen.setdefault(name, []).append(p)

    dupes = {n: ps for n, ps in seen.items() if len(ps) > 1}
    if dupes:
        detail = "\n".join(f"  - {n}: {', '.join(ps)}" for n, ps in dupes.items())
        raise SystemExit(
            f"❌ 用例目录存在重名文件（case_id 会冲突）：\n{detail}\n"
            f"   请确保每个用例的 .md 文件名唯一（子目录亦据此判定）。"
        )

    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        cases.append({"case_id": name, "case_name": name, "flow_path": p})
    return d, cases


def _snapshot_cases(cases, dest_dir, source_root):
    """把原始用例拷入本任务目录（运行快照），返回 flow_path 指向副本的 cases。

    快照的意义：同一 task 的各分片读到同一份内容，运行期源目录被改动不影响本任务。
    保留源目录的相对结构（如 `cases/提单页/flow-01-x.md`）；原路径留在 `source_path` 便于追溯。
    """
    snapshot = []
    for c in cases:
        dst = os.path.join(dest_dir, os.path.relpath(c["flow_path"], source_root))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(c["flow_path"], dst)
        snapshot.append({**c, "flow_path": dst, "source_path": c["flow_path"]})
    return snapshot


def _load_env(args):
    """共享环境信息：--env-file 先，--env 后（后者覆盖前者）。缺省 {}。"""
    env = {}
    if args.env_file:
        env.update(_read_json(args.env_file))
    if args.env:
        try:
            env.update(json.loads(args.env))
        except json.JSONDecodeError as e:
            raise SystemExit(f"❌ --env 不是合法 JSON: {e}")
    return env


# ─── plan ───────────────────────────────────────────────────────────────────

def cmd_plan(args):
    cases_dir, cases = _scan_cases(args.cases)

    warning = _convention_warning(cases_dir)
    if warning:
        print(warning, file=sys.stderr)

    env = _load_env(args)

    # 启用门槛：用例数 < 3 不需要子 Agent（单份直接执行）
    if len(cases) < MIN_CASES_FOR_ORCHESTRATION:
        raise SystemExit(
            f"❌ 用例数 {len(cases)} < {MIN_CASES_FOR_ORCHESTRATION}，无需多 Agent 编排。\n"
            f"   请走「单份执行」：由当前 AI 直接执行 ai-ui-autotest-engine（见 SKILL.md 执行规则 5）。"
        )

    max_cases = int(args.max_cases or DEFAULT_MAX_CASES)
    concurrency = int(args.concurrency or DEFAULT_CONCURRENCY)
    if max_cases < 1:
        raise SystemExit("❌ --max-cases 必须 ≥ 1")
    if concurrency < 1:
        raise SystemExit("❌ --concurrency 必须 ≥ 1")

    task_id = args.task or _new_task_id()
    tdir = _task_dir(task_id)
    if os.path.exists(tdir):
        raise SystemExit(f"❌ 任务已存在: {task_id}（换 --task 或先删除 {tdir}）")

    # ⓪ 用例快照：拷入本任务目录，分片只引用副本（源目录运行期被改不影响本任务）
    cases = _snapshot_cases(cases, os.path.join(tdir, "cases"), cases_dir)

    # ① 按「每 Agent 用例上限」连续切分片
    groups = _chunk(cases, max_cases)
    os.makedirs(os.path.join(tdir, "shards"), exist_ok=True)

    manifest_shards = []
    for idx, group in enumerate(groups, 1):
        sid = f"shard-{idx:02d}"
        shard = {
            "task_id": task_id,
            "shard_id": sid,
            "env": env,
            "cases": group,
        }
        _write_json(os.path.join(tdir, "shards", f"{sid}.json"), shard)
        manifest_shards.append({
            "shard_id": sid,
            "case_count": len(group),
            "case_ids": [c["case_id"] for c in group],
        })

    # 分片按序号有序 = 待跑队列；并发上限由 `concurrency` 表达（AI 滚动补位，不再分轮）
    manifest = {
        "task_id": task_id,
        "created_at": _now(),
        "source": cases_dir,
        "cases_dir": os.path.join(tdir, "cases"),
        "case_count": len(cases),
        "shard_count": len(manifest_shards),
        "max_cases_per_agent": max_cases,
        "concurrency": concurrency,
        "env": env,
        "shards": manifest_shards,
    }
    _write_json(os.path.join(tdir, "manifest.json"), manifest)
    _print_plan(manifest, tdir)
    _auto_prune(args, tdir, cases_dir)
    return 0


def _auto_prune(args, task_dir, cases_dir):
    """plan 结束后的滚动保留：编排产物 + 用例资产各保留最近 N 份。"""
    if getattr(args, "no_prune", False):
        print("  [滚动保留] 已通过 --no-prune 关闭\n")
        return
    keep = int(getattr(args, "keep", DEFAULT_KEEP) or DEFAULT_KEEP)
    docs_root = getattr(args, "docs_root", "") or DOCS_ROOT
    print(f"  [滚动保留 · 各保留最近 {keep} 份（本次产物与用例源目录恒受保护）]")

    kept, dropped = _prune(ORCH_ROOT, keep, protect=[_top_record(ORCH_ROOT, task_dir)])
    _report_prune("编排产物 .orchestration/", ORCH_ROOT, kept, dropped, False)

    kept, dropped = _prune(docs_root, keep, protect=[_top_record(docs_root, cases_dir)])
    _report_prune("用例资产 ai-app-flow/.docs/", docs_root, kept, dropped, False)
    print()


def _print_plan(manifest, tdir):
    print("=" * 60)
    print("  多 Agent 编排 · 派发计划")
    print("=" * 60)
    print(f"  task_id : {manifest['task_id']}")
    print(f"  用例源  : {manifest['source']}")
    print(f"  用例快照: {manifest['cases_dir']}")
    print(f"  用例数  : {manifest['case_count']}")
    print(f"  分片数  : {manifest['shard_count']}（每个 ≤ {manifest['max_cases_per_agent']} 用例）")
    print(f"  并发上限: {manifest['concurrency']}")
    print(f"  编排产物目录: {tdir}")
    print()
    print(f"  [待跑队列 · 维持 ≤ {manifest['concurrency']} 个在跑，谁先完成谁补下一个]")
    for i, s in enumerate(manifest["shards"], 1):
        path = os.path.join(tdir, "shards", f"{s['shard_id']}.json")
        print(f"    {i}. {s['shard_id']}  cases={s['case_count']}  → {path}")
        print(f"         {', '.join(s['case_ids'])}")
    print()
    print("  [下一步 · AI]")
    print(f"    滚动补位派发（滑动窗口 = {manifest['concurrency']}）——")
    print(f"      · 先并行启动队列前 {manifest['concurrency']} 个分片（各 1 个子 Agent）；")
    print("      · 之后谁先跑完，就立刻从队首取下一个分片补上，保持同时在跑 ≤ 上限；")
    print("      · 子 Agent 读自己的 shards/<shard>.json（env + cases），")
    print("        按 SKILL.md「子 Agent 派发契约」执行 ai-ui-autotest-engine 单份路径；")
    print("      · 直到队列跑空且全部结束；结果随 Task 直接返回，无需回写（报告各自独立入库）。")
    print()


# ─── prune ──────────────────────────────────────────────────────────────────

def cmd_prune(args):
    keep = int(args.keep or DEFAULT_KEEP)
    if keep < 1:
        raise SystemExit("❌ --keep 必须 ≥ 1")
    docs_root = args.docs_root or DOCS_ROOT

    print("=" * 60)
    print("  滚动保留 · keep-latest-N")
    print("=" * 60)
    print(f"  保留份数: {keep}" + ("    [DRY-RUN：只预览，不删除]" if args.dry_run else ""))
    print()

    kept, dropped = _prune(ORCH_ROOT, keep, dry_run=args.dry_run)
    _report_prune("编排产物 .orchestration/", ORCH_ROOT, kept, dropped, args.dry_run)

    kept, dropped = _prune(docs_root, keep, dry_run=args.dry_run)
    _report_prune("用例资产 ai-app-flow/.docs/", docs_root, kept, dropped, args.dry_run)
    print()
    return 0


# ─── 入口 ───────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(description="多 Agent 编排层：拆分 + 调度编排（plan）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="扫描用例目录 → 拆分为待跑队列（滚动补位派发）")
    p.add_argument("--cases", required=True, help="用例目录（递归；每个 *.md = 一个用例）")
    p.add_argument("--max-cases", type=int, default=DEFAULT_MAX_CASES,
                   help=f"每个子 Agent 的用例上限（默认 {DEFAULT_MAX_CASES}）")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                   help=f"同时在跑的子 Agent 上限（默认 {DEFAULT_CONCURRENCY}）")
    p.add_argument("--env", default="", help="共享环境信息 JSON（所有子 Agent 共享）")
    p.add_argument("--env-file", default="", help="共享环境信息 JSON 文件")
    p.add_argument("--task", default="", help="任务 id（默认自动生成）")
    p.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                   help=f"滚动保留份数（默认 {DEFAULT_KEEP}）")
    p.add_argument("--no-prune", action="store_true",
                   help="关闭 plan 成功后的自动滚动保留清理")
    p.add_argument("--docs-root", default="",
                   help="用例资产根目录（默认 <ai-app-flow>/.docs）")

    q = sub.add_parser("prune", help="滚动保留最近 N 份：编排产物 + 用例资产")
    q.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                   help=f"保留份数（默认 {DEFAULT_KEEP}）")
    q.add_argument("--dry-run", action="store_true",
                   help="只预览将清理的目录，不实际删除")
    q.add_argument("--docs-root", default="",
                   help="用例资产根目录（默认 <ai-app-flow>/.docs）")

    return parser


def main():
    args = build_parser().parse_args()
    if args.cmd == "prune":
        sys.exit(cmd_prune(args))
    sys.exit(cmd_plan(args))


if __name__ == "__main__":
    main()
