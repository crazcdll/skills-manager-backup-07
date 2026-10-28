#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flow .md → 元数据参考 + 步骤骨架描述（轻量模式）。

职责：
1. 解析 Flow .md 文件的元数据（标题、场景、落地页 scheme、测试数据参考）
2. 提取步骤的语义化描述（操作/等待/校验），作为 AI 写步骤的参考
3. 输出元数据 JSON 和解析报告供 AI 参考（metadata-<TAG>.json，非 steps-input.json）
4. AI 根据语义化描述手动编写 steps 数组，通过 steps-generate 命令固化

使用方式：
  <入口> flow-convert --tag <tag>

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

from shared.errors import PayloadError, UsageError
from shared.json_utils import write_json_atomic, read_json
from shared.paths import SKILL_DIR, flows_dir, steps_input_dir

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

# 「可测性环境」表（测试环境配置的唯一落点：覆盖范围 / 环境 / AppMock / 泳道 / 域名映射）
# 与步骤同级的配置声明，flow-convert 显式提取为 env_hints，
# 避免「Flow 声明了却未被采纳」的静默遗漏（典型：AppMock → case 级 mock_ids）。
_ENV_SECTION_RE = re.compile(r'##\s*可测性环境\s*\n(.+?)(?=\n##\s|\Z)', re.DOTALL)
_ENV_TABLE_ROW_RE = re.compile(r'^\|\s*([^|\n]+?)\s*\|\s*([^|\n]*?)\s*\|\s*$', re.MULTILINE)
_BACKTICK_VALUE_RE = re.compile(r'`([^`]+)`')

# 「可测性环境」表左侧「项」→ env_hints 键
_ENV_HINT_KEY_MAP = {
    "覆盖范围": "scope",
    "环境": "env_name",
    "AppMock": "appmock_ids",
    "泳道名": "swim_lane",
    "泳道URL": "swim_url_pattern",
    "泳道 URL": "swim_url_pattern",
    "域名映射": "url_mappings",
    "目标锁包": "bundle_names",
    "MRN锁包": "bundle_names",
    "锁包": "bundle_names",
}

# env_hints 键 → 报告展示名（保持声明顺序）
_ENV_HINT_LABELS = {
    "scope": "覆盖范围",
    "env_name": "环境",
    "appmock_ids": "AppMock",
    "swim_lane": "泳道名",
    "swim_url_pattern": "泳道 URL",
    "url_mappings": "域名映射",
    "bundle_names": "目标锁包",
}


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
        # 「可测性环境」表提取的配置提示（非权威，仅供 AI 写入 CASES.env / 人工核对）
        self.env_hints: dict = {}
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

        # 「可测性环境」表：与步骤同级的配置声明，单独提取为 env_hints
        self._parse_env_hints()

    def _parse_env_hints(self):
        """解析「可测性环境」表 → env_hints。

        该表声明测试环境的关键配置（环境 / AppMock / 泳道 / 域名映射 / 锁包），
        其中 AppMock 是「测试环境下提单页必需」的场景 Mock，由 flow-init 落到
        对应 case 的 `mock_ids`（case 级）。本方法只做结构化提取与呈现，不做自动注入
        （派生由 `flow_init._resolve_case_mock_ids` 负责，采集层不再介入）。
        """
        section = _ENV_SECTION_RE.search(self.content)
        if not section:
            return
        for item, value in _ENV_TABLE_ROW_RE.findall(section.group(1)):
            item = item.strip()
            value = value.strip()
            if not item or not value:
                continue
            key = _ENV_HINT_KEY_MAP.get(item)
            if not key:
                continue
            if key == "appmock_ids":
                # AppMock 格：取反引号内 token（`16305525`（说明）→ 16305525）
                ids = []
                for token in _BACKTICK_VALUE_RE.findall(value):
                    for part in str(token).split(","):
                        part = part.strip()
                        if part and part not in ids:
                            ids.append(part)
                if ids:
                    self.env_hints[key] = ids
                continue
            # 其余行：优先取反引号内实际值（如泳道名 `sunhuace-bszge`、域名映射 JSON），
            # 无反引号时保留原文（如「环境 | 测试环境（alpha）」）
            tokens = [t.strip() for t in _BACKTICK_VALUE_RE.findall(value) if t.strip()]
            self.env_hints[key] = ", ".join(tokens) if tokens else value

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
            "env_hints": dict(self.env_hints),
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
        if doc.env_hints:
            lines.append("     🌐 可测性环境（须映射到 CASES.env）:")
            for key, label in _ENV_HINT_LABELS.items():
                if key not in doc.env_hints:
                    continue
                val = doc.env_hints[key]
                shown = ", ".join(str(v) for v in val) if isinstance(val, list) else str(val)
                suffix = ""
                if key == "appmock_ids":
                    suffix = "   → 落到该 Case 的 mock_ids（case 级启用，测试环境下提单页等场景必需）"
                elif key == "env_name":
                    suffix = "   → 须与 env_type 一致"
                lines.append(f"       · {label}: {shown}{suffix}")
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
    lines.append("    4. 【env 声明】把「可测性环境」表映射进 CASES.env：")
    lines.append("       · 环境 → 与 env_type 保持一致；泳道/域名映射 → 对应 env 字段")
    lines.append("       · AppMock → 无需写入 env：flow-init 自动派生到该 Case 的 mock_ids（case 级启用）")
    lines.append("    5. 执行 <入口> steps-generate ... 固化")
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
        # 默认模式：扫描 $STATE/run/tasks/<task>/inputs/flows/
        default_dir = flows_dir()
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

    # 1.5 P0 修复：将外部 Flow .md 幂等同步到 inputs/flows/
    #（仅 --flow-source/--flow-dir 显式传入且文件不在该目录内时拷贝；
    #   同名但内容不同 → 覆盖，保证 workspace 内副本与源一致；
    #   跳过解析失败（未入 flow_docs）的文件，与下游仅依赖有效 Flow 的语义一致）
    synced = _sync_flows_to_workspace(flow_docs)
    if synced:
        print(f"📂 已同步 Flow 原文到 workspace（供 flow_source 注入 / mock_ids 派生）: {flows_dir()}")
        for dest in synced:
            print(f"    · {os.path.basename(dest)}")

    # 2. 输出元数据 JSON（供 AI 参考）
    output_dir = steps_input_dir()
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


def _sync_flows_to_workspace(flow_docs):
    """把外部 Flow .md 幂等拷贝到 $STATE/run/tasks/<task>/inputs/flows/。

    目的：让 `flow-convert --flow-source/--flow-dir` 与 `flow-create` 两条入口等价——
    steps-generate 从该目录注入 case.flow_source，flow-init 据此派生 case 级 mock_ids；
    缺少此拷贝时外部路径入口会静默断裂（mock_union 为空、场景 Mock 不生效）。

    幂等规则：目标不存在 → 拷贝；目标存在且内容不同 → 覆盖；内容相同 → 跳过。
    返回实际拷贝（含覆盖）的目标路径列表。
    """
    import shutil

    dest_dir = flows_dir()
    os.makedirs(dest_dir, exist_ok=True)
    synced = []
    for doc in flow_docs:
        src = getattr(doc, "source_path", "") or ""
        if not src or not os.path.isfile(src):
            continue
        src_abs = os.path.abspath(src)
        dest = os.path.join(dest_dir, os.path.basename(src_abs))
        if os.path.abspath(dest) == src_abs:
            continue  # 源已在 workspace 目录内（flow-create 路径），无需拷贝
        try:
            need_copy = True
            if os.path.exists(dest):
                with open(dest, "r", encoding="utf-8") as _f:
                    existing = _f.read()
                with open(src_abs, "r", encoding="utf-8") as _f:
                    current = _f.read()
                need_copy = existing != current
            if need_copy:
                shutil.copy2(src_abs, dest)
                synced.append(dest)
        except OSError as e:
            # 拷贝失败不阻断解析主流程，但明确可见（非静默）
            print(f"⚠️  Flow 同步失败（不阻断流程）: {src_abs} → {dest}: {e}", file=sys.stderr)
    return synced


def cmd_flow_create(args):
    """flow-create 命令：创建空 Flow .md 文件。"""
    import os as _os
    name = args.name
    if not name.endswith(".md"):
        name += ".md"
    _os.makedirs(flows_dir(), exist_ok=True)
    path = _os.path.join(flows_dir(), name)
    if _os.path.exists(path):
        print(f"⚠️  文件已存在，跳过: {path}")
    else:
        with open(path, "w", encoding="utf-8") as _f:
            pass
        print(f"✅ 空文件已创建: {path}")
