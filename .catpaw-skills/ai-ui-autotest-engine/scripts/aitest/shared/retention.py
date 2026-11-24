#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机器级产物滚动保留（keep-latest-N）。

只清理**可再生的运行态产物**：`$STATE/reports/` 下的历史报告归档。
不碰：用例资产（`cases/`）、编排产物（`orchestration/`，由编排层自己回收）、
凭据、工具链/制品缓存、常驻 console —— 它们要么不可再生，要么有独立生命周期。

策略：
  · 默认保留最近 `AI_UITEST_KEEP_REPORTS`（缺省 5）个批次目录；
  · 设 0 关闭自动清理（`prune` 手动命令仍可用）；
  · `max_age_days > 0` 时，超出保留位且超过该天数的目录也一并删除。

调用时机：`flow-init`（每次 run 开始）前自动跑一次（best-effort，失败不影响测试结论）；
正在写入的批次（默认 60 分钟内）即使超出保留位也不会被删。
也可手动 `python3 scripts/cli.py prune [--keep N] [--dry-run]`。
"""
import os
import shutil
import time

from aitest.shared.paths import OUTPUT_DIR

DEFAULT_KEEP_REPORTS = 5
# 保护窗口：刚写入/仍在跑的批次不删（多分片各自建批次时尤其重要）
DEFAULT_MIN_AGE_MINUTES = 60
ENV_KEEP_REPORTS = "AI_UITEST_KEEP_REPORTS"


def keep_from_env(default=DEFAULT_KEEP_REPORTS):
    """读取保留份数：非法/空 → 默认值；0 → 关闭自动清理。"""
    raw = (os.environ.get(ENV_KEEP_REPORTS) or "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _dir_size(path):
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                continue
    return total


def _human(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024.0


def _entries(root):
    """一级子目录，按最近修改时间倒序（最新在前）。"""
    if not os.path.isdir(root):
        return []
    items = []
    for name in os.listdir(root):
        if name.startswith("."):
            continue
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        try:
            items.append((os.path.getmtime(path), path))
        except OSError:
            continue
    items.sort(key=lambda item: item[0], reverse=True)
    return [path for _mtime, path in items]


def prune_root(root, keep=DEFAULT_KEEP_REPORTS, max_age_days=0, min_age_minutes=0,
               dry_run=False, label="产物"):
    """滚动保留 root 下最近 keep 个子目录，返回删除清单摘要。"""
    keep = max(0, int(keep))
    paths = _entries(root)
    if keep == 0:
        return {"root": root, "kept": len(paths), "removed": [], "freed": 0, "skipped": True}

    now = time.time()
    kept, dropped = [], []
    for index, path in enumerate(paths):
        age_minutes = (now - os.path.getmtime(path)) / 60.0
        age_days = age_minutes / 1440.0
        if (
            index < keep
            or age_minutes < min_age_minutes
            or (max_age_days > 0 and age_days <= max_age_days)
        ):
            kept.append(path)
        else:
            dropped.append(path)

    removed, freed = [], 0
    for path in dropped:
        size = _dir_size(path)
        if not dry_run:
            shutil.rmtree(path, ignore_errors=True)
            if os.path.exists(path):
                print(f"  ⚠️ {label}删除失败（权限 / 被占用）: {path}")
                continue
        removed.append(path)
        freed += size

    return {"root": root, "kept": len(kept), "removed": removed, "freed": freed, "skipped": False}


def prune_reports(keep=DEFAULT_KEEP_REPORTS, max_age_days=0, dry_run=False, verbose=True,
                  min_age_minutes=DEFAULT_MIN_AGE_MINUTES):
    """清理 `$STATE/reports/` 历史归档（keep-latest-N）。"""
    if keep <= 0 and not dry_run:
        return {"root": OUTPUT_DIR, "kept": 0, "removed": [], "freed": 0, "skipped": True}
    summary = prune_root(
        OUTPUT_DIR,
        keep=keep,
        max_age_days=max_age_days,
        min_age_minutes=min_age_minutes,
        dry_run=dry_run,
        label="报告归档",
    )
    if verbose:
        verb = "将删除" if dry_run else "已删除"
        print(
            f"  🧹 报告归档: 保留 {summary['kept']} 个批次，"
            f"{verb} {len(summary['removed'])} 个（{_human(summary['freed'])}）"
        )
        if dry_run:
            for path in summary["removed"]:
                print(f"      - {os.path.basename(path)}")
    return summary
