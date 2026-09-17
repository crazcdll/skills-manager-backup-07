#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤记录统一模型：steps.jsonl 的唯一写入契约。

设计原则（根治字段漂移与截图丢失）：
1. 所有写入端（UI/API/Track 引擎、override/log-record/assert-fields、effect_verified）
   必须通过 ``StepRecord`` 构造记录，禁止手拼 dict —— 字段名从此有单一真相。
2. 截图是一等资产：统一落在 ``case_workspace/frames/``，记录里只存 ``screenshots``
   列表（每项含 file/label/kind），彻底取代历史 ``img`` / ``evidence.screenshot`` 双写。
3. 报告端只经 ``resolve_screenshots`` / ``merge_screenshots`` 读截图，
   上传端只扫 ``frames/``，保证「上传集合 == 引用集合」。

字段规范（to_dict 输出）：
    sid / _src / type / d / ok / status / ms / ts / kind
    note / screenshots / asserts / extracted_fields / expected_fields / fa / raw_evidence
    + extra（业务扩展字段，如 http_code、matched、assert_verdicts 等）
"""

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

FRAMES_DIRNAME = "frames"
STEPS_FILENAME = "steps.jsonl"

# ── 记录来源（_src）常量，供 normalize/hook 路由等处统一引用 ──
SRC_STEP = "step"
SRC_FOLLOWUP = "followup"
SRC_RETRY = "retry"
SRC_EFFECT_VERIFIED = "effect_verified"
SRC_ASSERT_FIELDS = "assert_fields"
SRC_NOTE = "log"           # 无判定备注：只作展示，不进 steps/findings 统计

# ── 截图类型（kind）常量 ──
SHOT_STEP = "step"          # 引擎每步自动截图
SHOT_DEBUG = "debug"        # debug-shot / 操作后调试图
SHOT_AUTO = "auto"          # 记录命令自动截图
SHOT_ASSERT = "assert"      # 断言诊断图
SHOT_DIAGNOSTIC = "diagnostic"
SHOT_LOGIN = "login"        # 登录结果证据


# ═══════════════════════════════════════════════════════════════════
# 截图资产：统一存储与寻址
# ═══════════════════════════════════════════════════════════════════

def normalize_name(path_or_name):
    """把任意截图引用（绝对路径 / 子目录路径 / 纯文件名）归一到纯文件名。"""
    if not path_or_name:
        return ""
    return os.path.basename(str(path_or_name).strip())


def frames_dir(case_workspace):
    """返回并确保 case_workspace/frames/ 存在。"""
    path = os.path.join(case_workspace, FRAMES_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def frame_path(case_workspace, name):
    """返回 frames/ 下某截图的完整落盘路径（自动建目录 + 归一文件名）。"""
    return os.path.join(frames_dir(case_workspace), normalize_name(name))


@dataclass
class Screenshot:
    """单张截图资产。file 恒为 frames/ 下的纯文件名。"""
    file: str
    label: str = ""
    kind: str = SHOT_STEP


def make_screenshot(path_or_name, label="", kind=SHOT_STEP):
    """构造 Screenshot；路径为空时返回 None。"""
    name = normalize_name(path_or_name)
    return Screenshot(name, label, kind) if name else None


def merge_screenshots(records):
    """跨多条记录合并 screenshots（保序去重，按 file）。

    用于报告层：conclusion 缺图时可从同 sid 的其他执行记录补齐，
    彻底消除「conclusion 选中无图记录 → 步骤截图丢失」的问题。
    """
    seen = set()
    merged = []
    for record in records or []:
        for shot in (record.get("screenshots") or []):
            name = shot.get("file")
            if name and name not in seen:
                seen.add(name)
                merged.append(shot)
    return merged


def resolve_screenshots(record, url_map):
    """把一条记录（或 screenshots 列表）解析为 [{url, label, kind}]。

    record 可为 dict（取 record["screenshots"]）或 screenshots 列表。
    url_map: {文件名: url}，由上传端产出。
    """
    if isinstance(record, dict):
        shots = record.get("screenshots") or []
    else:
        shots = record or []
    resolved = []
    for shot in shots:
        name = shot.get("file")
        url = url_map.get(name) if name else None
        if url:
            resolved.append({
                "url": url,
                "label": shot.get("label", ""),
                "kind": shot.get("kind", SHOT_STEP),
            })
    return resolved


# ═══════════════════════════════════════════════════════════════════
# 步骤记录
# ═══════════════════════════════════════════════════════════════════

@dataclass
class StepRecord:
    """一条步骤执行事实。所有写入端唯一入口。"""
    sid: str = ""
    src: str = SRC_STEP
    type: str = ""
    desc: str = ""
    ok: Optional[int] = None
    status: str = ""
    ms: int = 0
    ts: str = ""
    kind: str = "ui"
    note: str = ""
    screenshots: list = field(default_factory=list)   # list[Screenshot]
    asserts: list = field(default_factory=list)
    fields: dict = field(default_factory=dict)         # → extracted_fields
    expected_fields: object = None                      # list | dict | None
    failure: dict = None                                # → fa
    raw_evidence: object = None                         # → raw_evidence
    extra: dict = field(default_factory=dict)           # 业务扩展字段

    # ── 便捷方法 ──────────────────────────────────────────────

    def shot(self, path_or_name, label="", kind=SHOT_STEP):
        """登记一张截图资产（自动归一到 frames/ 下文件名）。"""
        shot = make_screenshot(path_or_name, label, kind)
        if shot:
            self.screenshots.append(shot)
        return self

    def screenshots_list(self):
        """返回 screenshots 的纯 dict 列表（供 flow-context 等复用）。"""
        return [asdict(s) for s in self.screenshots]

    def to_dict(self):
        d = {
            "sid": self.sid or None,
            "_src": self.src,
            "d": self.desc,
            "ok": self.ok,
            "status": self.status,
            "ms": self.ms,
            "ts": self.ts or time.strftime("%Y-%m-%dT%H:%M:%S"),
            "kind": self.kind,
        }
        if self.type:
            d["type"] = self.type
        if self.note:
            d["note"] = self.note
        if self.screenshots:
            d["screenshots"] = [asdict(s) for s in self.screenshots]
        if self.asserts:
            d["asserts"] = self.asserts
        if self.fields:
            d["extracted_fields"] = self.fields
        if self.expected_fields is not None:
            d["expected_fields"] = self.expected_fields
        if self.failure:
            d["fa"] = self.failure
        if self.raw_evidence is not None:
            d["raw_evidence"] = self.raw_evidence
        d.update(self.extra)
        return d

    def append(self, case_workspace):
        """唯一落盘入口：追加一行到 case_workspace/steps.jsonl。"""
        payload = self.to_dict()
        path = os.path.join(case_workspace, STEPS_FILENAME)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return payload
