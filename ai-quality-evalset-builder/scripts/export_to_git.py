#!/usr/bin/env python3
"""
export_to_git.py — 将学城评测集文档或本地 samples.json 导出为 Git 标准 JSON 格式

用法：
  # 从学城文档导出（推荐）
  python3 export_to_git.py --km-doc 2761965436 --output-dir /path/to/eval/cases

  # 从本地 samples.json 导出
  python3 export_to_git.py --input ~/.openclaw/workspace/eval-dataset/samples.json --output-dir /path/to/eval/cases

  # 同时创建 schema 文件和 README
  python3 export_to_git.py --km-doc 2761965436 --output-dir /path/to/eval/cases --create-schema --create-readme
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────

@dataclass
class Finding:
    id: str                        # F001, F002...
    severity: str                  # P0/P1/P2/P3
    defect_class: str              # C1~C7
    context_layer: str             # L1/L2/L3
    file: str                      # Java 文件名
    line_range: Optional[str]      # L45-L52 或 null
    description: str               # 问题描述
    key_concepts: list             # 语义匹配锚点关键词


@dataclass
class InputCase:
    eval_id: str
    title: str
    repo: str
    pr_number: int
    pr_url: str
    cr_doc_url: Optional[str]
    diff: None = None              # 固定 null，运行时动态拉取


@dataclass
class GroundTruth:
    eval_id: str
    verdict: str                   # ✅通过/💚通过有建议/🟠需修复/🔴需重新设计
    gt_source: str                 # human_verified/ai_detected/coe_regression
    annotator: str
    annotated_at: str
    confidence: float
    findings: list
    expected_absent: list = field(default_factory=list)


# ─────────────────────────────────────────────
# 关键词提取
# ─────────────────────────────────────────────

# 缺陷类别 → 中文关键词映射
DEFECT_KEYWORDS = {
    "C1": ["NPE", "空指针", "逻辑反转", "中间态", "边界条件", "硬编码", "越权修改"],
    "C2": ["并发", "线程安全", "竞态", "同步", "锁", "volatile", "double-check"],
    "C3": ["资源泄露", "连接泄露", "内存泄露", "默认true", "默认false", "开关"],
    "C4": ["吞异常", "事务不回滚", "浮点精度", "try-catch", "回滚", "资损"],
    "C5": ["越权", "SQL注入", "权限校验", "敏感数据", "XSS", "SSRF"],
    "C6": ["N+1", "全表扫描", "无限流", "无分页", "性能风险", "批量查询"],
    "C7": ["拼写错误", "测试缺失", "注释不符", "幂等", "规范"],
}

def extract_key_concepts(description: str, file: str) -> list:
    """从 description 中自动提取语义比对关键词"""
    concepts = []

    # 1. Java 类名/方法名（驼峰命名）
    java_names = re.findall(r'\b[A-Z][a-zA-Z0-9]+(?:\.[a-zA-Z][a-zA-Z0-9]+)*\b', description)
    concepts.extend(java_names[:3])

    # 2. 小驼峰方法名（get/set/is 等常见前缀）
    method_names = re.findall(r'\b(?:get|set|is|has|check|build|create|update|delete|process|handle|validate)[A-Z][a-zA-Z0-9]+\b', description)
    concepts.extend(method_names[:2])

    # 3. 异常类名
    exceptions = re.findall(r'\b\w+Exception\b|\bNPE\b|\bIOOBE\b|\bNullPointerException\b', description)
    concepts.extend(exceptions)

    # 4. 中文业务关键词（固定词表）
    cn_keywords = ["NPE", "逻辑反转", "越权", "事务", "资损", "幂等", "竞态", "拆箱",
                   "截断", "吞异常", "死代码", "N+1", "全量", "中间态", "浮点精度"]
    for kw in cn_keywords:
        if kw in description:
            concepts.append(kw)

    # 5. 注解名（@Xxx）
    annotations = re.findall(r'@[A-Z][a-zA-Z]+', description)
    concepts.extend(annotations[:2])

    # 6. 去重保序，取前 5 个
    seen = set()
    result = []
    for c in concepts:
        if c not in seen and len(c) > 1:
            seen.add(c)
            result.append(c)
        if len(result) >= 5:
            break

    # 兜底：至少有文件名（去掉 .java）
    if not result:
        result.append(file.replace(".java", ""))

    return result


# ─────────────────────────────────────────────
# 学城文档解析
# ─────────────────────────────────────────────

SEVERITY_MAP = {"🔴": "P0", "🟠": "P1", "🟡": "P2"}
CONFIDENCE_MAP = {"human_verified": 0.9, "ai_detected": 0.7, "coe_regression": 1.0}

def fetch_km_doc(content_id: str) -> str:
    """调用 oa-skills citadel 获取学城文档内容"""
    result = subprocess.run(
        ["oa-skills", "citadel", "getSimpleMarkdown", "--contentId", content_id],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"获取学城文档失败: {result.stderr}")
    # 去掉 CLI 头部提示，提取正文
    lines = result.stdout.split("\n")
    start = next((i for i, l in enumerate(lines) if l.startswith("---") and i > 5), 0)
    return "\n".join(lines[start+1:])


def parse_km_doc(content: str) -> list:
    """解析学城评测集文档，提取所有 EVAL 案例"""
    cases = []

    # 按 EVAL 块分割（支持 ##### EVAL-NNN 和 ##### EVAL-NN 格式）
    eval_pattern = re.compile(
        r'#{3,5}\s+(EVAL-\d+)[:\s]+(.*?)\s*(?:\(PR#(\d+)\))?\s*$',
        re.MULTILINE
    )
    eval_positions = [(m.start(), m.group(1), m.group(2), m.group(3))
                      for m in eval_pattern.finditer(content)]

    for idx, (pos, eval_id, title, pr_num_hint) in enumerate(eval_positions):
        end_pos = eval_positions[idx + 1][0] if idx + 1 < len(eval_positions) else len(content)
        block = content[pos:end_pos]

        # 提取仓库
        repo_match = re.search(r'\*\*仓库\*\*[：:]\s*`?([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+)`?', block)
        repo = repo_match.group(1) if repo_match else "unknown/unknown"

        # 提取 PR URL
        pr_url_match = re.search(
            r'https://dev\.sankuai\.com/code/repo-detail/[^\s\)\"\']+/pr/(\d+)/[^\s\)\"\']*',
            block
        )
        pr_url = pr_url_match.group(0).rstrip(')') if pr_url_match else ""
        pr_number = int(pr_url_match.group(1)) if pr_url_match else (int(pr_num_hint) if pr_num_hint else 0)

        # 提取 CR 文档 URL
        cr_doc_match = re.search(r'https://km\.sankuai\.com/collabpage/(\d+)', block)
        cr_doc_url = cr_doc_match.group(0) if cr_doc_match else None

        # 提取 findings 表格
        findings = parse_findings_table(block, eval_id)

        # 推断 verdict（有 P0 → 需修复，全 P2 → 通过有建议，无 findings → 通过）
        severities = [f.severity for f in findings]
        if "P0" in severities:
            verdict = "🟠需修复"
        elif "P1" in severities:
            verdict = "🟠需修复"
        elif findings:
            verdict = "💚通过有建议"
        else:
            verdict = "✅通过"

        # 推断 gt_source 和 confidence（有人工标注✅则 human_verified）
        annotated_count = sum(1 for f in findings if getattr(f, '_annotated', False))
        if annotated_count == len(findings) and findings:
            gt_source = "human_verified"
            confidence = 0.9
        else:
            gt_source = "ai_detected"
            confidence = 0.7

        cases.append({
            "input": InputCase(
                eval_id=eval_id,
                title=title.strip(),
                repo=repo,
                pr_number=pr_number,
                pr_url=pr_url,
                cr_doc_url=cr_doc_url,
                diff=None
            ),
            "gt": GroundTruth(
                eval_id=eval_id,
                verdict=verdict,
                gt_source=gt_source,
                annotator="mengmuzi",
                annotated_at="2026-05-13",
                confidence=confidence,
                findings=[asdict(f) for f in findings],
                expected_absent=[]
            )
        })

    return cases


def parse_findings_table(block: str, eval_id: str) -> list:
    """从 EVAL 块中解析 findings 表格"""
    findings = []
    # 匹配表格行：| # | Severity | Defect Class | Context Layer | Expected Finding | 人工标注 |
    row_pattern = re.compile(
        r'\|\s*(\d+)\s*\|\s*(P[0-3])\s*\|\s*(C[1-7])\s*\|\s*(L[1-3])\s*\|\s*(.+?)\s*\|\s*(✅|❌|待标注|—)?\s*\|',
        re.MULTILINE
    )
    for m in row_pattern.finditer(block):
        idx, severity, defect_class, context_layer, desc_raw, annotation = m.groups()

        # 解析 description：去掉 `文件名.java` 前缀和 emoji
        desc = re.sub(r'^`[^`]+`\s*[—–-]\s*', '', desc_raw.strip())
        desc = re.sub(r'[🔴🟠🟡💚✅❌⚠️]+', '', desc).strip()

        # 提取文件名
        file_match = re.search(r'`([A-Z][a-zA-Z]+\.java)`', desc_raw)
        file_name = file_match.group(1) if file_match else "Unknown.java"

        # 提取行号
        line_match = re.search(r'L(\d+)[-–]L?(\d+)', desc_raw)
        line_range = f"L{line_match.group(1)}-L{line_match.group(2)}" if line_match else None

        f = Finding(
            id=f"F{int(idx):03d}",
            severity=severity,
            defect_class=defect_class,
            context_layer=context_layer,
            file=file_name,
            line_range=line_range,
            description=desc[:200],  # 截断到 200 字
            key_concepts=extract_key_concepts(desc, file_name)
        )
        f._annotated = (annotation == "✅")
        findings.append(f)

    return findings


# ─────────────────────────────────────────────
# 写入文件
# ─────────────────────────────────────────────

def write_eval_case(case: dict, output_dir: str):
    """写入 input.json 和 ground_truth.json"""
    inp: InputCase = case["input"]
    gt: GroundTruth = case["gt"]

    case_dir = Path(output_dir) / inp.eval_id
    case_dir.mkdir(parents=True, exist_ok=True)

    # input.json
    input_data = {
        "$schema": "../../schema/input.schema.json",
        "eval_id": inp.eval_id,
        "title": inp.title,
        "repo": inp.repo,
        "pr_number": inp.pr_number,
        "pr_url": inp.pr_url,
        "cr_doc_url": inp.cr_doc_url,
        "diff": None
    }
    with open(case_dir / "input.json", "w", encoding="utf-8") as f:
        json.dump(input_data, f, ensure_ascii=False, indent=2)

    # ground_truth.json
    gt_data = {
        "$schema": "../../schema/ground_truth.schema.json",
        "eval_id": gt.eval_id,
        "verdict": gt.verdict,
        "gt_source": gt.gt_source,
        "annotator": gt.annotator,
        "annotated_at": gt.annotated_at,
        "confidence": gt.confidence,
        "findings": gt.findings,
        "expected_absent": gt.expected_absent
    }
    with open(case_dir / "ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(gt_data, f, ensure_ascii=False, indent=2)

    print(f"  ✅ {inp.eval_id}: {inp.title[:40]} → {case_dir}")


def create_schema_files(output_dir: str):
    """创建 JSON Schema 定义文件"""
    schema_dir = Path(output_dir).parent / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)

    input_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "AI-CR EvalCase Input",
        "type": "object",
        "required": ["eval_id", "repo", "pr_number", "pr_url"],
        "properties": {
            "eval_id": {"type": "string", "pattern": "^EVAL-\\d{3,}$"},
            "title": {"type": "string"},
            "repo": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$"},
            "pr_number": {"type": "integer", "minimum": 1},
            "pr_url": {"type": "string", "pattern": "^https://dev\\.sankuai\\.com"},
            "cr_doc_url": {"type": ["string", "null"]},
            "diff": {"type": "null", "description": "固定 null，评测时动态拉取"}
        }
    }

    gt_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "AI-CR Ground Truth",
        "type": "object",
        "required": ["eval_id", "verdict", "gt_source", "confidence", "findings"],
        "properties": {
            "eval_id": {"type": "string"},
            "verdict": {"type": "string", "enum": ["✅通过", "💚通过有建议", "🟠需修复", "🔴需重新设计"]},
            "gt_source": {"type": "string", "enum": ["human_verified", "ai_detected", "coe_regression"]},
            "annotator": {"type": "string"},
            "annotated_at": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "severity", "defect_class", "context_layer", "file", "description", "key_concepts"],
                    "properties": {
                        "id": {"type": "string", "pattern": "^F\\d{3}$"},
                        "severity": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
                        "defect_class": {"type": "string", "enum": ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]},
                        "context_layer": {"type": "string", "enum": ["L1", "L2", "L3"]},
                        "file": {"type": "string"},
                        "line_range": {"type": ["string", "null"]},
                        "description": {"type": "string", "maxLength": 200},
                        "key_concepts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 6
                        }
                    }
                }
            },
            "expected_absent": {
                "type": "array",
                "items": {"type": "string"},
                "description": "已知 clean 点描述；AI 如果报这些算 FP"
            }
        }
    }

    with open(schema_dir / "input.schema.json", "w", encoding="utf-8") as f:
        json.dump(input_schema, f, ensure_ascii=False, indent=2)
    with open(schema_dir / "ground_truth.schema.json", "w", encoding="utf-8") as f:
        json.dump(gt_schema, f, ensure_ascii=False, indent=2)

    print(f"  ✅ schema 文件已写入 {schema_dir}")


def create_readme(output_dir: str, cases: list):
    """创建 README.md"""
    readme_path = Path(output_dir).parent / "README.md"
    eval_ids = [c["input"].eval_id for c in cases]
    content = f"""# AI-CR 离线评测集

本目录为 `ai-cr-evaluator` pipeline 的标准评测集，由 `ai-quality-evalset-builder` 自动生成。

## 目录结构

```
eval/
├── cases/            # 每个 EVAL 一个子目录
│   ├── EVAL-001/
│   │   ├── input.json          # PR 元信息
│   │   └── ground_truth.json   # GT findings + key_concepts
│   └── ...
├── schema/
│   ├── input.schema.json
│   └── ground_truth.schema.json
├── results/          # CI 跑完后自动写入（不手动维护）
└── README.md
```

## 当前评测集

- **样本数**: {len(cases)}
- **覆盖 EVAL**: {eval_ids[0]} ~ {eval_ids[-1]}
- **最后更新**: 2026-05-13
- **来源文档**: https://km.sankuai.com/collabpage/2761965436

## 格式说明

### input.json
PR 元信息，`diff` 字段固定为 null，评测时由 pipeline 动态从 Code 平台拉取。

### ground_truth.json
- `findings`：GT 检出项，每条包含 `key_concepts`（语义比对锚点）
- `expected_absent`：已知 clean 点，AI 如果报了算 FP
- `confidence`：`human_verified`=0.9，`ai_detected`=0.7，`coe_regression`=1.0

## 语义匹配规则

AI-CR 输出 vs GT finding：命中 `key_concepts` 中 **≥2 个**关键词即判定 TP。

## 运行评测

```bash
# 等 ai-cr-evaluator skill 可用后执行
python3 run_eval.py --cases eval/cases --report-doc <km-contentId>
```
"""
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✅ README.md 已写入 {readme_path}")


# ─────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="将评测集导出为 Git 标准 JSON 格式")
    parser.add_argument("--km-doc", help="学城文档 contentId（如 2761965436）")
    parser.add_argument("--input", help="本地 samples.json 路径")
    parser.add_argument("--output-dir", required=True, help="输出目录（eval/cases）")
    parser.add_argument("--create-schema", action="store_true", help="同时生成 schema 文件")
    parser.add_argument("--create-readme", action="store_true", help="同时生成 README.md")
    args = parser.parse_args()

    if not args.km_doc and not args.input:
        print("错误：需要指定 --km-doc 或 --input", file=sys.stderr)
        sys.exit(1)

    print("🚀 开始导出评测集 JSON...")

    cases = []

    if args.km_doc:
        print(f"▶️  从学城文档 {args.km_doc} 读取...")
        doc_content = fetch_km_doc(args.km_doc)
        cases = parse_km_doc(doc_content)
        print(f"  解析到 {len(cases)} 个 EVAL 案例")
    elif args.input:
        print(f"▶️  从本地文件 {args.input} 读取...")
        with open(args.input, encoding="utf-8") as f:
            raw = json.load(f)
        # 假设 samples.json 已经是列表格式，做简单转换
        for item in raw:
            cases.append({
                "input": InputCase(**{k: item.get(k) for k in InputCase.__dataclass_fields__}),
                "gt": GroundTruth(**{k: item.get(k) for k in GroundTruth.__dataclass_fields__})
            })

    print(f"\n▶️  写入 {len(cases)} 个案例到 {args.output_dir}...")
    for case in cases:
        write_eval_case(case, args.output_dir)

    if args.create_schema:
        print("\n▶️  生成 schema 文件...")
        create_schema_files(args.output_dir)

    if args.create_readme:
        print("\n▶️  生成 README.md...")
        create_readme(args.output_dir, cases)

    print(f"\n✅ 导出完成！共 {len(cases)} 个案例")
    print(f"\n下一步：")
    print(f"  cd /path/to/mcp/ai-cr")
    print(f"  git add eval/")
    print(f'  git commit -m "feat(eval): add evalset cases [2026-05-13]"')
    print(f"  git push")


if __name__ == "__main__":
    main()
