#!/usr/bin/env python3
"""
security-check.py — 美团内部专项安全规则检查

在 friday-skill-scanner 通用规则之外，针对美团内部安全合规要求进行专项检测：
  MT-001  内网域名硬编码（WARN）
  MT-002  美团 AK/SK 泄露（FAIL）
  MT-003  Appkey 硬编码（WARN）
  MT-004  命令注入风险 — eval/exec + 用户输入（FAIL）
  MT-005  PII 数据合规 — 处理 PII 但未在 frontmatter 声明（WARN）

退出码约定（与 publish.py 一致）：
  exit 0 → 全 PASS
  exit 1 → 有 WARN（无 FAIL）
  exit 2 → 有 FAIL

用法：
  python security-check.py <skill目录>
  python security-check.py <skill目录> --json

支持平台：macOS / Linux / Windows
依赖：Python 3.8+，无需第三方包
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_yaml_rules(yaml_path):
    """从 YAML 文件加载规则列表（无需 PyYAML，纯手写解析器）。"""
    rules = []
    try:
        with open(yaml_path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"❌ 规则文件未找到：{yaml_path}", file=sys.stderr)
        sys.exit(2)

    rules_match = re.search(r'^rules:\s*$', text, re.MULTILINE)
    if not rules_match:
        print(f"❌ 规则文件格式错误（未找到 'rules:' 块）：{yaml_path}", file=sys.stderr)
        sys.exit(2)
    rules_text = text[rules_match.end():]

    blocks = re.split(r'(?m)^  - (?=id:)', rules_text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        rule = {}
        for line in block.splitlines():
            m = re.match(r'^    (\w+):\s*(.*)', line)
            if not m:
                m = re.match(r'^(\w+):\s*(.*)', line)
            if not m:
                continue
            key, val = m.group(1), m.group(2).strip()
            val = re.sub(r'\s+#.*$', '', val)
            if val.startswith(("'", '"')) and val.endswith(("'", '"')):
                val = val[1:-1]
            if val.lower() == 'true':
                val = True
            elif val.lower() == 'false':
                val = False
            elif val == '' or val.lower() == 'null':
                val = None
            rule[key] = val
        if 'id' in rule:
            rules.append(rule)
    return rules


# =============================================================================
# 美团内部专项规则：从 references/meituan-rules.yaml 加载
# =============================================================================

_MT_RULES_YAML = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "references", "meituan-rules.yaml")
MEITUAN_RULES = _load_yaml_rules(_MT_RULES_YAML)

# 预编译规则
_COMPILED = {}
for _rule in MEITUAN_RULES:
    try:
        _COMPILED[_rule["id"]] = re.compile(_rule["pattern"], re.IGNORECASE)
    except re.error:
        pass

# 代码文件扩展名
CODE_EXTENSIONS = {'.py', '.sh', '.js', '.ts', '.bash', '.zsh', '.pl', '.rb'}

# 跳过测试文件
TEST_FILE_RE = re.compile(
    r'(^|/)test_[^/]*\.py$'
    r'|(^|/)[^/]*_test\.py$'
    r'|(^|/)tests/'
    r'|(^|/)conftest\.py$'
)


# =============================================================================
# 文件分类
# =============================================================================

def classify_files(skill_dir: Path) -> Dict[str, List[Path]]:
    """将 skill 目录下的文件分为 code / all 两类。"""
    code_files: List[Path] = []
    all_files: List[Path] = []

    # 自排除：skillhub/scripts/ 下所有工具脚本均属于发布工具本身，不属于被扫描的 skill 内容
    # 用脚本所在目录精确匹配，避免基于文件名/内容的不准确启发式排除
    _self_scripts_dir = Path(__file__).parent.resolve()
    _self_exclude = {
        str(p.resolve())
        for p in _self_scripts_dir.iterdir()
        if p.is_file()
    }

    for fpath in skill_dir.rglob('*'):
        if not fpath.is_file():
            continue
        if str(fpath.resolve()) in _self_exclude:
            continue
        rel = str(fpath.relative_to(skill_dir))
        # 跳过测试文件
        if TEST_FILE_RE.search(rel):
            continue
        all_files.append(fpath)
        parts = Path(rel).parts
        # code files: scripts/ 目录下 + 顶层代码扩展名文件
        if len(parts) > 0 and parts[0] == 'scripts':
            code_files.append(fpath)
        elif len(parts) == 1 and fpath.suffix in CODE_EXTENSIONS:
            code_files.append(fpath)

    return {"code": code_files, "all": all_files}


# =============================================================================
# 扫描核心
# =============================================================================

Match = Dict[str, Any]  # {"file": str, "line": int, "content": str}


def scan_rule(rule: Dict[str, Any], files: List[Path],
              skill_dir: Path, max_matches: int = 30) -> List[Match]:
    """对一批文件运行单条规则，返回匹配列表。"""
    rule_id = rule["id"]
    compiled = _COMPILED.get(rule_id)
    if compiled is None:
        return []

    matches: List[Match] = []
    for fpath in files:
        try:
            content = fpath.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        rel = str(fpath.relative_to(skill_dir))
        for lineno, line in enumerate(content.splitlines(), 1):
            if compiled.search(line):
                matches.append({
                    "file": rel,
                    "line": lineno,
                    "content": line[:200],
                })
                if len(matches) >= max_matches:
                    return matches
    return matches


def run_checks(skill_dir: str) -> Dict[str, Any]:
    """执行所有美团内部专项规则检查，返回结果字典。"""
    sd = Path(skill_dir).resolve()
    if not sd.is_dir():
        return {
            "error": f"目录不存在：{skill_dir}",
            "summary": "FAIL",
            "findings": [],
        }

    files = classify_files(sd)
    checks: List[Dict[str, Any]] = []
    worst = "PASS"
    risk_score = 0

    def add_check(check_id: str, name: str, result: str,
                  matches: List[Match], note: str = ""):
        nonlocal worst, risk_score
        checks.append({
            "id": check_id,
            "name": name,
            "result": result,
            "matches": matches,
            "note": note,
        })
        if result == "FAIL":
            worst = "FAIL"
            risk_score += 40
        elif result == "WARN" and worst != "FAIL":
            worst = "WARN"
            risk_score += 10

    for rule in MEITUAN_RULES:
        rid = rule["id"]
        scope = rule["scope"]
        severity = rule["severity"]
        note = rule.get("note", "")

        if scope == "code":
            target = files["code"]
        else:  # "all"
            target = files["all"]

        matches = scan_rule(rule, target, sd)
        result = severity if matches else "PASS"
        add_check(rid, rule["name"], result, matches, note)

    findings = [c for c in checks if c["result"] != "PASS"]
    pass_count = sum(1 for c in checks if c["result"] == "PASS")
    warn_count = sum(1 for c in checks if c["result"] == "WARN")
    fail_count = sum(1 for c in checks if c["result"] == "FAIL")

    return {
        "skill_dir": str(sd),
        "summary": worst,
        "risk_score": min(risk_score, 100),
        "checks": checks,
        "findings": findings,
        "stats": {
            "total_files": len(files["all"]),
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
        },
    }


# =============================================================================
# 输出格式
# =============================================================================

def print_human(result: Dict[str, Any]) -> None:
    """输出可读报告。"""
    print("==========================================")
    print("  美团内部专项安全检查（security-check.py）")
    print("==========================================")
    if "error" in result:
        print(f"❌ 错误：{result['error']}")
        return

    print(f"目录：{result['skill_dir']}")
    print(f"文件数：{result['stats']['total_files']}")
    print("------------------------------------------")

    for check in result["checks"]:
        r = check["result"]
        icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}.get(r, "?")
        print(f"{icon} [{r}] {check['id']} — {check['name']}")
        if r != "PASS":
            if check.get("note"):
                print(f"     💡 {check['note']}")
            for m in check["matches"][:5]:
                content = m["content"][:120]
                print(f"     → {m['file']}:{m['line']}  {content}")

    print()
    print("------------------------------------------")
    s = result["stats"]
    print(f"结果：{result['summary']}  (PASS:{s['pass']}  WARN:{s['warn']}  FAIL:{s['fail']})")
    print("==========================================")


# =============================================================================
# 主入口
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="security-check.py — 美团内部专项安全规则检查",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
退出码：
  0 — 全 PASS
  1 — 有 WARN（无 FAIL）
  2 — 有 FAIL

示例：
  python security-check.py /path/to/my-skill
  python security-check.py /path/to/my-skill --json
        """,
    )
    parser.add_argument("skill_dir", help="要检查的 Skill 目录路径")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出结果")
    args = parser.parse_args()

    result = run_checks(args.skill_dir)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human(result)

    summary = result.get("summary", "FAIL")
    if summary == "PASS":
        return 0
    elif summary == "WARN":
        return 1
    else:
        return 2


if __name__ == "__main__":
    sys.exit(main())
