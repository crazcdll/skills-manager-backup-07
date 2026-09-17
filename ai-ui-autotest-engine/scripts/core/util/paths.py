#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ai-ui-autotest-engine 统一路径管理。

四目录分离：
  .run-input/ 运行时输入源（Flow .md，由 AI 每轮用 flow-create 重新写入，预检/收尾清理时清空）；
  .config/    机器相关配置（预检/收尾清理时一并清空，运行期重新收集）；
  .run/       运行时工作区（可整目录清空）；
  output/     产物归档（跨执行保留）。
本地目录由本模块管，云端设备由 device_lifecycle.py 管，两者解耦。
"""
import os
import shutil
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ─── 四个顶层目录 ────────────────────────────────────────────
RUN_INPUT_DIR = os.path.join(SKILL_DIR, ".run-input")
CONFIG_DIR = os.path.join(SKILL_DIR, ".config")
RUN_DIR = os.path.join(SKILL_DIR, ".run")
OUTPUT_DIR = os.path.join(SKILL_DIR, "output")

# ─── .run-input/ 子目录 ──────────────────────────────────────
FLOWS_DIR = os.path.join(RUN_INPUT_DIR, "flows")

# ─── .run/ 子目录 ────────────────────────────────────────────
DUMPS_DIR = os.path.join(RUN_DIR, "dumps")
CASES_DIR = os.path.join(RUN_DIR, "cases")
MOCK_BASELINE_DIR = os.path.join(RUN_DIR, "mock_baseline")
STEPS_INPUT_DIR = os.path.join(RUN_DIR, "tmp")

# ─── 文件路径 ────────────────────────────────────────────────
RECORD_DATA_JSON = os.path.join(RUN_DIR, "record_data.json")
ENV_PATCH_JSON = os.path.join(CONFIG_DIR, "env_patch.json")
ACTIVE_CASE_FILE = os.path.join(RUN_DIR, "active_case")
ENV_ANSWERS_FILE = os.path.join(CONFIG_DIR, "env_answers.json")
INSPECT_TREE_CACHE = os.path.join(RUN_DIR, "inspect_tree.json")
CHECK_DEPS_RESULT = os.path.join(RUN_DIR, "check_deps_result.json")
PTEST_MOCK_ID_FILE = os.path.join(RUN_DIR, "ptest_mock_id.json")
RECORDING_ACTIVE = os.path.join(RUN_DIR, "recording_active")
AUTO_URL_MAPPING_IDS = os.path.join(RUN_DIR, "auto_url_mapping_ids.json")
APPMOCK_SESSION_COOKIE = os.path.join(CONFIG_DIR, "appmock_session_cookie.json")
INSPECT_TREE_PARSED = os.path.join(RUN_DIR, "inspect_tree_parsed.txt")
REFERENCES_DIR = os.path.join(SKILL_DIR, "references")
SKILL_MD_PATH = os.path.join(SKILL_DIR, "SKILL.md")


def ensure_dirs():
    for d in (RUN_DIR, CASES_DIR, DUMPS_DIR, MOCK_BASELINE_DIR, STEPS_INPUT_DIR,
              CONFIG_DIR, RUN_INPUT_DIR, FLOWS_DIR):
        os.makedirs(d, exist_ok=True)


def get_active_case():
    """读取 .run/active_case 文件，返回当前激活的 case 目录名。"""
    try:
        with open(ACTIVE_CASE_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def set_active_case(case_name: str):
    """写入 .run/active_case，标记当前激活的 case。"""
    ensure_dirs()
    tmp_path = ACTIVE_CASE_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(case_name.strip())
    os.replace(tmp_path, ACTIVE_CASE_FILE)


def active_case_context_path():
    """返回当前 active_case 的 flow-context.json 路径，不存在则返回 None。"""
    case_name = get_active_case()
    if not case_name:
        return None
    case_dir = os.path.join(CASES_DIR, case_name) if not os.path.isabs(case_name) else case_name
    path = os.path.join(case_dir, "flow-context.json")
    return path if os.path.isfile(path) else None


def _clear_dir(d):
    if os.path.isdir(d):
        for name in os.listdir(d):
            item = os.path.join(d, name)
            try:
                if os.path.isfile(item) or os.path.islink(item):
                    os.remove(item)
                elif os.path.isdir(item):
                    shutil.rmtree(item, ignore_errors=True)
            except OSError:
                pass


def _clean_run_and_config():
    """清空运行级本地状态：.run/ 与 .config/ 全量。

    .config/ 下当前两类文件都是运行级的：
      env_answers.json             用户输入，每轮重新收集；
      appmock_session_cookie.json  SSO 凭证缓存，每轮重新授权。
    因此不设例外一并清空，保证每轮测试都从干净状态开始。
    """
    _clear_dir(RUN_DIR)
    _clear_dir(CONFIG_DIR)
    os.makedirs(CONFIG_DIR, exist_ok=True)


def preflight_clean():
    """启动预检清理：清空 .run/、.config/、.run-input/ 并重建。
    仅清理本地文件，云端设备/AppMock 清理由阶段 1（SOP B1/B2）负责。
    env_answers.json 一并清空，由 env-required 在阶段 0 重新收集。

    ⚠️ 必须在本轮 check-deps 之前执行：check-deps 会写 .run/check_deps_result.json
    与 .config/appmock_session_cookie.json，被清理后再写才不会丢。
    """
    _clean_run_and_config()
    _clear_dir(RUN_INPUT_DIR)
    os.makedirs(FLOWS_DIR, exist_ok=True)
    sys.stderr.write("[paths] preflight-clean 完成\n")


def clean_post_test():
    """测试完成后清理：清空 .run/、.config/、.run-input/。
    至此一次完整测试运行结束，所有本地状态被清理干净。
    """
    _clean_run_and_config()
    if os.path.isdir(RUN_INPUT_DIR):
        for name in os.listdir(RUN_INPUT_DIR):
            item = os.path.join(RUN_INPUT_DIR, name)
            try:
                if os.path.isfile(item) or os.path.islink(item):
                    os.remove(item)
                elif os.path.isdir(item):
                    shutil.rmtree(item, ignore_errors=True)
            except OSError:
                pass
    os.makedirs(FLOWS_DIR, exist_ok=True)
    sys.stderr.write("[paths] post-clean 完成\n")

def get_steps_input_dir() -> str:
    """返回 steps-input.json 存放目录（绝对路径），供 SKILL.md 引用。"""
    ensure_dirs()
    return STEPS_INPUT_DIR


def get_flows_dir() -> str:
    """返回原始 Flow .md 文件存放目录（绝对路径），供 SKILL.md 引用。"""
    ensure_dirs()
    return FLOWS_DIR