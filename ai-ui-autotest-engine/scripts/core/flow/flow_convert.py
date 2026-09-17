#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flow .md → 元数据参考 + 步骤骨架描述（轻量模式）。

职责：
1. 解析 Flow .md 文件的元数据（标题、场景、落地页 scheme、测试数据参考）
2. 提取步骤的语义化描述（操作/等待/校验），作为 AI 写步骤的参考
3. 输出元数据 JSON 和解析报告供 AI 参考（metadata-<TAG>.json，非 steps-input.json）
4. AI 根据语义化描述手动编写 steps 数组，通过 steps-generate 命令固化

使用方式：
  python3 scripts/cli.py flow-convert --tag <tag>

Flow 转换流程：
  1. flow-convert → 输出元数据解析报告 + metadata-<TAG>.json（AI 参考用）
  2. AI 审阅元数据后，基于 Flow 语义化步骤手动编写 CASES（含 steps 数组）
  3. steps-generate → 接收 AI 编写的 CASES，通过 StepsGenerator 完成：
     - sid 自动编号
     - blur-input 注入
     - 占位符替换
     - 两级校验
  4. 确认后执行 flow-init 载入引擎
"""
import json
import os
import re
import sys

from core.errors import PayloadError, UsageError
from core.util.json_utils import write_json_atomic, read_json
from core.util.paths import SKILL_DIR, FLOWS_DIR, STEPS_INPUT_DIR

# ═══════════════════════════════════════════════════════════════════
# Flow .md 解析正则
# ═══════════════════════════════════════════════════════════════════

# 场景标题：## 场景 A · 描述 或 ## 场景 A
_SCENE_RE = re.compile(r'^##\s+场景\s*([A-Z])?\s*[·.．]?\s*(.*)$', re.MULTILINE)

# 步骤标题：### S1. 或 ### S1. 描述 或 ### 1. 或 ### 1. 描述
_STEP_TITLE_RE = re.compile(r'^###\s+(?:S)?(\d+)\.?\s*(.*)$', re.MULTILINE)

# 操作：**操作**：xxxx
_OPERATION_RE = re.compile(r'\*\*操作\*\*\s*[：:]\s*(.*?)(?=\n\s*\*\*|\Z)', re.DOTALL)

# 等待：**等待**：xxxx
_WAIT_RE = re.compile(r'\*\*等待\*\*\s*[：:]\s*(.*?)(?=\n\s*\*\*|\Z)', re.DOTALL)

# 校验提取
_CHECK_TEXT_RE = re.compile(r'\*\*校验\*\*\s*[：:]\s*(.*?)(?=\n\s*\*\*|\Z)', re.DOTALL)

# 接口断言
_API_ASSERT_RE = re.compile(r'\*\*接口断言\*\*\s*[：:]\s*(.*?)(?=\n\s*\*\*|\Z)', re.DOTALL)

# 埋点断言
_TRACK_ASSERT_RE = re.compile(r'\*\*埋点断言\*\*\s*[：:]\s*(.*?)(?=\n\s*\*\*|\Z)', re.DOTALL)

# 证据要求
_EVIDENCE_RE = re.compile(r'\*\*证据要求\*\*\s*[：:]\s*(.*?)(?=\n\s*\*\*|\Z)', re.DOTALL)

# 标题提取
_TITLE_RE = re.compile(r'^#\s+(.+)$', re.MULTILINE)

# 落地页 scheme
_SCHEME_RE = re.compile(r'```\s*\n(imeituan://.+?)\n```', re.DOTALL)

# 执行类型
_EXEC_TYPE_RE = re.compile(r'>\s*执行类型[：:]\s*(.+?)(?:\n|$)')

# 前置条件
_PRECOND_RE = re.compile(r'>\s*前置条件[：:]\s*(.+?)(?:\n|$)')

# 测试数据
_TEST_DATA_RE = re.compile(r'>\s*测试数据参考[：:]\s*(.+?)(?:\n##|\Z)', re.DOTALL)

# 关联 EC 用例
_CASE_ID_RE = re.compile(r'<!--\s*caseId\s*=\s*(\d+)\s*-->')


class FlowStepMeta:
    """Flow 中一个步骤的元数据（用于 AI 写步骤参考）。"""
    def __init__(self, sid: str, desc: str, operation: str, wait: str,
                 check: str, api_assert: str, track_assert: str, evidence: str):
        self.sid = sid
        self.desc = desc
        self.operation = operation
        self.wait = wait
        self.check = check
        self.api_assert = api_assert
        self.track_assert = track_assert
        self.evidence = evidence

    def to_dict(self) -> dict:
        return {
            "sid": self.sid,
            "desc": self.desc,
            "operation": self.operation,
            "wait": self.wait,
            "check": self.check,
            "api_assert": self.api_assert,
            "track_assert": self.track_assert,
            "evidence": self.evidence,
        }


class FlowSceneMeta:
    """Flow 中一个场景的元数据。"""
    def __init__(self, scene_tag: str, scene_desc: str, landing_scheme: str):
        self.scene_tag = scene_tag
        self.scene_desc = scene_desc
        self.landing_scheme = landing_scheme
        self.steps: list[FlowStepMeta] = []

    def to_dict(self) -> dict:
        return {
            "scene_tag": self.scene_tag,
            "scene_desc": self.scene_desc,
            "landing_scheme": self.landing_scheme,
            "steps": [s.to_dict() for s in self.steps],
        }


class FlowDocumentMeta:
    """解析后的 Flow 文档元数据（仅做参考，不生成 steps）。"""
    def __init__(self, content: str, source_path: str = ""):
        self.content = content
        self.source_path = source_path
        self.title = ""
        self.case_id = ""
        self.exec_type = "deterministic"
        self.preconditions = ""
        self.test_data = ""
        self.scenes: list[FlowSceneMeta] = []
        self._parse()

    def _parse(self):
        # 提取标题
        title_m = _TITLE_RE.search(self.content)
        if title_m:
            self.title = title_m.group(1).strip()

        # 提取 caseId
        case_m = _CASE_ID_RE.search(self.content)
        if case_m:
            self.case_id = case_m.group(1)

        # 提取执行类型
        exec_m = _EXEC_TYPE_RE.search(self.content)
        if exec_m:
            self.exec_type = exec_m.group(1).strip()

        # 提取前置条件
        prec_m = _PRECOND_RE.search(self.content)
        if prec_m:
            self.preconditions = prec_m.group(1).strip()

        # 提取测试数据
        data_m = _TEST_DATA_RE.search(self.content)
        if data_m:
            self.test_data = data_m.group(1).strip()

        # 提取场景
        scene_positions = [(m.start(), m.group(1) or "", m.group(2).strip())
                           for m in _SCENE_RE.finditer(self.content)]

        if scene_positions:
            for i, (pos, tag, desc) in enumerate(scene_positions):
                end_pos = scene_positions[i + 1][0] if i + 1 < len(scene_positions) else len(self.content)
                scene_content = self.content[pos:end_pos]
                scheme = self._extract_scheme(scene_content)
                scene = FlowSceneMeta(tag, desc, scheme)
                self._parse_steps(scene, scene_content)
                self.scenes.append(scene)
        else:
            scheme = self._extract_scheme(self.content)
            scene = FlowSceneMeta("", "默认场景", scheme)
            self._parse_steps(scene, self.content)
            self.scenes.append(scene)

    def _extract_scheme(self, content: str) -> str:
        scheme_m = _SCHEME_RE.search(content)
        if scheme_m:
            return scheme_m.group(1).strip()
        return ""

    def _parse_steps(self, scene: FlowSceneMeta, content: str):
        step_positions = [(m.start(), int(m.group(1)), m.group(2).strip())
                          for m in _STEP_TITLE_RE.finditer(content)]

        for i, (pos, num, desc) in enumerate(step_positions):
            end_pos = step_positions[i + 1][0] if i + 1 < len(step_positions) else len(content)
            step_content = content[pos:end_pos]
            sid = f"S{num}"
            operation = self._extract_field(step_content, _OPERATION_RE)
            wait = self._extract_field(step_content, _WAIT_RE)
            check = self._extract_field(step_content, _CHECK_TEXT_RE) or ""
            api_assert = self._extract_field(step_content, _API_ASSERT_RE)
            track_assert = self._extract_field(step_content, _TRACK_ASSERT_RE)
            evidence = self._extract_field(step_content, _EVIDENCE_RE)
            scene.steps.append(FlowStepMeta(sid, desc, operation, wait, check,
                                            api_assert, track_assert, evidence))

    def _extract_field(self, content: str, pattern: re.Pattern) -> str:
        m = pattern.search(content)
        if m:
            return m.group(1).strip()
        return ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "case_id": self.case_id,
            "exec_type": self.exec_type,
            "preconditions": self.preconditions,
            "test_data": self.test_data,
            "source_path": self.source_path,
            "scenes": [s.to_dict() for s in self.scenes],
        }


def _build_metadata_report(flow_docs: list[FlowDocumentMeta]) -> str:
    """生成元数据解析报告（供 AI 写步骤参考）。"""
    lines = []
    lines.append("=" * 60)
    lines.append("  flow-convert 元数据解析报告（轻量模式）")
    lines.append("=" * 60)
    lines.append(f"  文件数: {len(flow_docs)}")
    for doc in flow_docs:
        lines.append(f"    · {os.path.basename(doc.source_path)} — {doc.title}")
        if doc.case_id:
            lines.append(f"      EC 用例: {doc.case_id}")
    lines.append("")

    for doc in flow_docs:
        lines.append(f"  📄 {os.path.basename(doc.source_path)}")
        lines.append(f"     标题: {doc.title}")
        if doc.case_id:
            lines.append(f"     EC 用例: {doc.case_id}")
        if doc.test_data:
            lines.append(f"     测试数据:")
            for line in doc.test_data.split("\n"):
                line = line.strip()
                if line:
                    lines.append(f"       {line.replace('- ', '• ')}")
        for scene in doc.scenes:
            tag_str = f"场景 {scene.scene_tag}" if scene.scene_tag else "默认场景"
            lines.append(f"    📌 {tag_str} · {scene.scene_desc}")
            if scene.landing_scheme:
                lines.append(f"       scheme: {scene.landing_scheme[:80]}...")
            for step in scene.steps:
                lines.append(f"      [{step.sid}] {step.desc}")
                if step.operation:
                    lines.append(f"        🖱 操作: {step.operation[:60]}")
                if step.wait:
                    lines.append(f"        ⏳ 等待: {step.wait[:60]}")
                if step.check:
                    # 只显示校验的前两行
                    check_lines = step.check.strip().split("\n")[:3]
                    for cl in check_lines:
                        cl = cl.strip()
                        if cl:
                            lines.append(f"        ✅ 校验: {cl[:60]}")
                    if len(step.check.strip().split("\n")) > 3:
                        remaining = len(step.check.strip().split("\n")) - 3
                        lines.append(f"        ... 还有 {remaining} 行")
                if step.api_assert:
                    lines.append(f"        🌐 接口: {step.api_assert[:60]}")
                if step.track_assert:
                    lines.append(f"        📊 埋点: {step.track_assert[:60]}")
    lines.append("")
    lines.append("  📋 下一步（AI 完成）:")
    lines.append("    1. 根据以上元数据，为每个 Case 编写 steps 数组")
    lines.append("    2. 参考 Action 选择映射表确定 action 字段")
    lines.append("    3. 填充测试数据参数到 params 字段")
    lines.append("    4. 执行 python3 scripts/cli.py steps-generate ... 固化")
    lines.append("=" * 60)
    return "\n".join(lines)


def flow_convert_main(args):
    """flow-convert 命令入口（轻量模式：只解析元数据，不生成 steps）。"""
    # 收集所有 Flow 文件路径
    flow_sources = list(getattr(args, 'flow_source', None) or [])
    flow_dir = getattr(args, 'flow_dir', None)

    if flow_dir:
        if os.path.isdir(flow_dir):
            flow_sources = sorted([
                os.path.join(flow_dir, f)
                for f in os.listdir(flow_dir)
                if f.endswith('.md') and os.path.isfile(os.path.join(flow_dir, f))
            ])
        else:
            raise PayloadError(f"Flow 目录不存在: {flow_dir}")
    elif not flow_sources:
        # 默认模式：扫描 .run-input/flows/
        default_dir = FLOWS_DIR
        if os.path.isdir(default_dir):
            flow_sources = sorted([
                os.path.join(default_dir, f)
                for f in os.listdir(default_dir)
                if f.endswith('.md') and os.path.isfile(os.path.join(default_dir, f))
            ])
            if flow_sources:
                print(f"📂 默认扫描目录: {default_dir}")
                for f in flow_sources:
                    print(f"    · {os.path.basename(f)}")
        else:
            raise PayloadError(f"未指定 Flow 文件，且默认目录不存在: {default_dir}")

    if not flow_sources:
        raise UsageError("未指定 Flow 文件。请使用 --flow-source 或 --flow-dir 指定。")

    tag = args.tag

    # 1. 解析所有 Flow 文件
    flow_docs = []
    for fp in flow_sources:
        if not os.path.isfile(fp):
            raise PayloadError(f"Flow 文件不存在: {fp}")
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()
        doc = FlowDocumentMeta(content, source_path=fp)
        if not doc.scenes:
            print(f"⚠️  警告: Flow 文件未解析到任何场景，跳过: {fp}", file=sys.stderr)
            continue
        flow_docs.append(doc)

    if not flow_docs:
        raise PayloadError("所有 Flow 文件均未解析到有效场景或步骤")

    # 2. 输出元数据 JSON（供 AI 参考）
    output_dir = STEPS_INPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    metadata = {
        "files": [doc.to_dict() for doc in flow_docs],
        "total_files": len(flow_docs),
        "total_scenes": sum(len(d.scenes) for d in flow_docs),
        "total_steps": sum(len(s.steps) for d in flow_docs for s in d.scenes),
    }
    metadata_path = os.path.join(output_dir, f"metadata-{tag}.json")
    write_json_atomic(metadata_path, metadata)

    # 3. 输出解析报告
    report = _build_metadata_report(flow_docs)
    print(report)
    print(f"\n✅ 元数据已写入: {metadata_path}")
    print(f"  files={len(flow_docs)} scenes={metadata['total_scenes']} steps={metadata['total_steps']}")
    print(f"💡 请 AI 根据元数据编写 CASES（含 steps），然后执行 steps-generate 固化")


def cmd_flow_create(args):
    """flow-create 命令：创建空 Flow .md 文件。"""
    import os as _os
    name = args.name
    if not name.endswith(".md"):
        name += ".md"
    _os.makedirs(FLOWS_DIR, exist_ok=True)
    path = _os.path.join(FLOWS_DIR, name)
    if _os.path.exists(path):
        print(f"⚠️  文件已存在，跳过: {path}")
    else:
        with open(path, "w", encoding="utf-8") as _f:
            pass
        print(f"✅ 空文件已创建: {path}")
