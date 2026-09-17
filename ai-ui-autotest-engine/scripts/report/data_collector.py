#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告层唯一 I/O 入口。

builders 拆分为纯构建模块后，所有文件读取集中于此，便于离线单测与 mock。"""
import functools
import json
import os

from core.errors import soft_fail
from core.util.json_utils import read_json, read_jsonl
from core.util.paths import SKILL_MD_PATH, CHECK_DEPS_RESULT


def load_case_data(case_workspace):
    return read_jsonl(os.path.join(case_workspace, "steps.jsonl"))


def load_audit(run_dir):
    audit_dir = os.path.join(run_dir, "audit")
    return read_jsonl(os.path.join(audit_dir, "run-events.jsonl"))


_SKILL_MD = SKILL_MD_PATH


@functools.lru_cache(maxsize=1)
def _read_skill_version():
    """从 SKILL.md 的 YAML 头部读取 Friday Skillhub 注入的平台版本号（skillhub.version，如 V96）。"""
    if not os.path.isfile(_SKILL_MD):
        return None
    try:
        with open(_SKILL_MD, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if "skillhub.version:" in stripped:
                    val = stripped.split("skillhub.version:", 1)[1].strip().strip('"\'')
                    if val:
                        return val
    except OSError as e:
        soft_fail("infra", "SKILL_VERSION_READ_FAILED", e)
    return None


def _load_check_deps():
    """从 .run/check_deps_result.json 读取 check-deps 结果（无则返回 None）。"""
    path = CHECK_DEPS_RESULT
    if not os.path.isfile(path):
        return None
    try:
        return read_json(path, default=None)
    except (json.JSONDecodeError, OSError) as e:
        soft_fail("infra", "CHECK_DEPS_READ_FAILED", e)
        return None


def read_text_file(path) -> str:
    """读取文本文件内容；不存在或不可读时返回 "" 并留痕（报告层唯一文本读取入口）。"""
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        soft_fail("infra", "REPORT_READ_TEXT_FAILED", f"{path}: {e}")
        return ""


def list_dir(path) -> list:
    """列出目录内容（已排序）；不可读时返回 [] 并留痕。"""
    try:
        if not os.path.isdir(path):
            return []
        return sorted(os.listdir(path))
    except OSError as e:
        soft_fail("infra", "REPORT_LIST_DIR_FAILED", f"{path}: {e}")
        return []
