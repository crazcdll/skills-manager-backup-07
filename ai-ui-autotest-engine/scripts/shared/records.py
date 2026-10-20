#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤记录统一模型：steps.jsonl 的唯一写入契约。

设计原则（根治字段漂移与截图丢失）：
1. 所有写入端（UI/API/Track 引擎、override/log-record/assert-fields、effect_verified）
   必须通过 ``StepRecord`` 构造记录，禁止手拼 dict —— 字段名从此有单一真相。
2. 截图是一等资产：统一落在 ``case_workspace/frames/``，记录里只存 ``screenshots``
   列表（每项含 file/label/kind），彻底取代历史 ``img`` / ``evidence.screenshot`` 双写。
3. 报告端只经 ``resolve_screenshots`` 读截图（步骤级主图/多图列表由
   ``report.steps._canonical_screenshots`` 统一裁决），
   上传端只扫 ``frames/``，保证「上传集合 == 引用集合」。

字段规范（to_dict 输出）：
    sid / _src / type / d / ok / status / ms / ts / kind
    note / screenshots / asserts / extracted_fields / expected_fields / fa / raw_evidence
    + extra（业务扩展字段，如 http_code、matched、assert_verdicts 等）
"""

import json
import os
import re
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
# 归属型兜底操作（step --for-sid）：把补救动作（坐标点击等）绑到父步骤作为证据，
# 但不改父步骤结论（结论权在断言与 AI override）。
SRC_FALLBACK = "fallback"
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


SHOT_SEQ_FILENAME = ".shot_seq"


def alloc_shot_seq(case_workspace):
    """为「非步骤级自动截图」分配一个**在分配时即唯一**的序号（张级唯一键）。

    与历史实现 `next_execution_seq`（= 本 case 的 steps.jsonl 行数 + 1，**记录级**序号）
    的关键差异：截图是「张级」资产，而一条执行记录可能对应多张截图 —— 同一记录追加前
    连拍多张（一次步骤内多次诊断图、同一 tag 的 open-url 重试在同一记录前连拍等）时，
    记录级序号会返回同一个值 → 同名 → 覆盖，早拍的那张证据被静默替换、报告引用与语义不符。

    因此唯一键必须「以分配为原子操作」：每次调用即读取计数器 +1 并落盘，任何两次分配
    都不可能拿到同一个值。计数器文件 `<case_ws>/.shot_seq` 与 steps.jsonl 正交（它只记录
    「已分配过多少个张级序号」，不是证据本身）。
    """
    path = os.path.join(case_workspace, SHOT_SEQ_FILENAME)
    current = 0
    try:
        with open(path, encoding="utf-8") as f:
            current = int((f.read() or "0").strip() or 0)
    except (OSError, ValueError):
        current = 0
    current += 1
    try:
        os.makedirs(case_workspace, exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(str(current))
        os.replace(tmp, path)   # 原子替换：读写不在同一路径上，避免半写状态
    except OSError:
        pass
    return current


def case_prefix(case_workspace):
    """从 case 工作目录名推导 `case_NN_` 前缀（目录名即 `case_NN`）。"""
    base = os.path.basename(case_workspace or "")
    return f"{base}_" if re.fullmatch(r"case_\d+", base) else ""


def auto_shot_name(case_workspace, kind, seq, tag=""):
    """非步骤级「自动截图」的统一命名 —— 唯一实现。

    命名 = `[case_NN_]<kind>_[<tag>_]<seq>.png`，**唯一键是 seq**（张级分配序号，
    见 alloc_shot_seq）。理由：这类截图没有唯一 sid 可用（不是声明步骤），用固定名
    或秒级时间戳都会互相覆盖 —— 覆盖会让报告引用的证据与语义不符（实测：同一 case
    内第二次 open-url 覆盖了 C3 的落地证据图 `diag_open_url.png`）。

    seq 必须由 alloc_shot_seq 在分配时给出：它按「张」自增并落盘，而**不能**用
    「记录级」序号（steps.jsonl 行数 + 1）—— 同一记录追加前连拍多张会拿到同一个值
    → 同名覆盖。

    kind：`diag`（诊断现场图）/ `auto`（log-record、override 的自动截图）/
    `fallback`（归属型兜底操作的证据图）。
    """
    parts = [kind] + ([tag] if tag else []) + [str(seq)]
    return f"{case_prefix(case_workspace)}{'_'.join(parts)}.png"


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


def resolve_screenshots(record, url_map):
    """把一条记录（或 screenshots 列表）解析为 [{file, url, label, kind}]。

    record 可为 dict（取 record["screenshots"]）或 screenshots 列表。
    url_map: {文件名: url}，由上传端产出。

    `file` 一并返回：报告里的 steps[].screenshots[] 带 file + url，消费端（如平台时间线）
    据此把 **raw 记录**里的 `screenshots[].file` 映射回 url，从而展示「该记录自己的帧」，
    而不是借用同 sid 其它记录的图。
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
                "file": name,
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
