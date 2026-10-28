#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告层唯一 I/O 入口。

builders 拆分为纯构建模块后，所有文件读取集中于此，便于离线单测与 mock。"""
import json
import os

from shared.errors import soft_fail
from shared.json_utils import read_json, read_jsonl
from shared.paths import SKILL_DIR, check_deps_result_path
from shared.selfupdate import read_skill_version


def skill_version():
    """平台版本号（SKILL.md frontmatter 的 skillhub.version，如 V187）；无则 None。

    实现只有一份：`shared.selfupdate.read_skill_version`（自更新也要用它比对远端），
    这里只是把 SKILL_DIR 绑定好，供报告层直接调用。
    """
    return read_skill_version(SKILL_DIR)


def load_case_data(case_workspace):
    return read_jsonl(os.path.join(case_workspace, "steps.jsonl"))


def load_audit(run_dir):
    audit_dir = os.path.join(run_dir, "audit")
    return read_jsonl(os.path.join(audit_dir, "run-events.jsonl"))


def _load_check_deps():
    """从本 workspace 的 check_deps_result.json 读取 check-deps 结果（无则返回 None）。"""
    path = check_deps_result_path()
    if not os.path.isfile(path):
        return None
    try:
        return read_json(path, default=None)
    except (json.JSONDecodeError, OSError) as e:
        soft_fail("infra", "CHECK_DEPS_READ_FAILED", e)
        return None


def list_dir(path) -> list:
    """列出目录内容（已排序）；不可读时返回 [] 并留痕。"""
    try:
        if not os.path.isdir(path):
            return []
        return sorted(os.listdir(path))
    except OSError as e:
        soft_fail("infra", "REPORT_LIST_DIR_FAILED", f"{path}: {e}")
        return []
