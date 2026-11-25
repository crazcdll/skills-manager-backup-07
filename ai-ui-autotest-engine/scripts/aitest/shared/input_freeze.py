#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""输入冻结：把业务真源 `steps.json` 从上游目录固化进本 workspace。

为什么只能在初始化期（`steps-generate`）做
------------------------------------------
上游 `ai-app-flow/.docs/` 与编排层 `.orchestration/` 都按 keep-latest-N 滚动清理（各保留
最近 10 份），执行之后再按原路径读取随时可能 404；用户本地目录也会被移动 / 改名。
`steps-generate` 是「输入进入引擎」的唯一边界：冻结之后，`case-init` / `gen-report` /
`archive_run` / 事后审计只认 workspace 内相对路径，不再依赖任何外部目录。

产物（随 workspace 被 `archive_run` 整树拷进 `$STATE/reports/<batch>/<run>/run/`）
--------------------------------------------------------------------------------
    <task>/inputs/<tag>/steps.json        业务真源（逐字节复制，占位符未解析）
    <task>/inputs/<tag>/steps-input.json  引擎输入（steps-generate 产物，占位符未解析）
    <task>/inputs/<tag>/manifest.json     索引：来源路径 / 大小 / 关联 case_id

`manifest.json` 是唯一索引：报告阶段按 `case_id` 反查，不靠目录名猜。
"""
import os
import shutil
import time

from aitest.shared.json_utils import read_json, write_json_atomic
from aitest.shared.paths import task_dir

INPUTS_DIRNAME = "inputs"
MANIFEST_FILENAME = "manifest.json"
STEPS_JSON_NAME = "steps.json"
STEPS_INPUT_NAME = "steps-input.json"

# 报告包里正文内联的上限：仅作为提示阈值（超限不降级、不截断），用于尽早暴露异常输入
INLINE_HINT_BYTES = 64 * 1024


def inputs_dir(tag):
    """本 tag 的冻结目录：`$STATE/run/tasks/<task>/inputs/<tag>/`。"""
    return os.path.join(task_dir(), INPUTS_DIRNAME, str(tag))


def _entry(kind, name, path, source_path):
    return {
        "kind": kind,
        "name": name,
        "path": os.path.relpath(path, task_dir()).replace(os.sep, "/"),
        "source_path": os.path.abspath(source_path) if source_path else "",
        "size_bytes": os.path.getsize(path),
    }


def freeze_inputs(source_steps_path, tag, steps_input_path=None, case_ids=None):
    """把业务真源（+ 引擎输入）复制进 workspace，并写 manifest。

    幂等：同 tag 重跑直接覆盖（同一 tag 的输入只有一份，后跑的版本即准）。
    返回 manifest dict；源文件不可读时抛 OSError（初始化期必须失败，不能带病继续）。
    """
    target_dir = inputs_dir(tag)
    os.makedirs(target_dir, exist_ok=True)

    files = []
    steps_dst = os.path.join(target_dir, STEPS_JSON_NAME)
    shutil.copy2(source_steps_path, steps_dst)
    files.append(_entry("steps_json", STEPS_JSON_NAME, steps_dst, source_steps_path))

    if steps_input_path and os.path.isfile(steps_input_path):
        input_dst = os.path.join(target_dir, STEPS_INPUT_NAME)
        shutil.copy2(steps_input_path, input_dst)
        files.append(_entry("steps_input", STEPS_INPUT_NAME, input_dst, steps_input_path))

    manifest = {
        "tag": str(tag),
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "case_ids": [str(item) for item in (case_ids or []) if item],
        "files": files,
    }
    write_json_atomic(os.path.join(target_dir, MANIFEST_FILENAME), manifest)
    return manifest


def iter_manifests():
    """遍历 workspace 内全部冻结清单（按冻结时间升序）。"""
    root = os.path.join(task_dir(), INPUTS_DIRNAME)
    if not os.path.isdir(root):
        return []
    manifests = []
    for name in sorted(os.listdir(root)):
        payload = read_json(os.path.join(root, name, MANIFEST_FILENAME), None)
        if isinstance(payload, dict) and payload.get("files"):
            manifests.append(payload)
    manifests.sort(key=lambda item: str(item.get("frozen_at") or ""))
    return manifests


def find_manifest(case_id):
    """按 case_id 反查冻结清单；多份命中时取最后冻结的那份。"""
    case_id = str(case_id or "")
    if not case_id:
        return None
    matched = [item for item in iter_manifests() if case_id in (item.get("case_ids") or [])]
    return matched[-1] if matched else None


def manifest_file(manifest, kind):
    """取清单里某个 kind 的文件条目（含绝对路径解析结果）。"""
    for item in (manifest or {}).get("files") or []:
        if item.get("kind") == kind:
            resolved = dict(item)
            resolved["abs_path"] = os.path.join(task_dir(), item.get("path", ""))
            return resolved
    return None
