#!/usr/bin/env python3
"""
security-scan.py — SkillHub Skill 安全扫描工具

发布前可选运行，对 Skill 目录执行两阶段安全检查：
  Stage 1  通用静态扫描（30+ 规则，从 references/scan-rules.yaml 加载）
  Stage 2  美团内部专项规则（从 references/meituan-rules.yaml 加载，由 security-check.py 执行）

退出码约定：
  exit 0 → 全 PASS
  exit 1 → 有 WARN（无 FAIL）
  exit 2 → 有 FAIL

用法：
  python security-scan.py [<skill目录>]      # 默认：当前目录
  python security-scan.py /path/to/my-skill

支持平台：macOS / Linux / Windows
依赖：Python 3.8+，无需第三方包
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _load_yaml_rules(yaml_path: str) -> List[Dict[str, Any]]:
    """从 YAML 文件加载规则列表（无需 PyYAML，纯手写解析器）。"""
    # 支持字段：id, name, severity, scope, pattern, exclude_ref, note
    rules: List[Dict[str, Any]] = []
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
        rule: Dict[str, Any] = {}
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
# 静态扫描规则：从 references/scan-rules.yaml 加载
# =============================================================================

SCORING = {"FAIL": 40, "WARN": 10, "PASS": 0}
RISK_THRESHOLDS = [(0, "safe"), (25, "low"), (50, "medium"), (75, "high"), (100, "critical")]

_RULES_YAML = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "references", "scan-rules.yaml")
RULES: List[Dict[str, Any]] = _load_yaml_rules(_RULES_YAML)

# 预编译
_COMPILED_RULES: Dict[str, re.Pattern] = {}
for _rule in RULES:
    _pat = _rule.get("pattern")
    if _pat:
        try:
            _COMPILED_RULES[_rule["id"]] = re.compile(_pat)
        except re.error:
            pass

# =============================================================================
# 正则常量
# =============================================================================

INTERNAL_DOMAINS_RE = re.compile(
    r'\.sankuai\.com|\.meituan\.com|\.neixin\.cn|localhost|127\.0\.0\.1'
    r'|//10\.\d|//172\.(?:1[6-9]|2\d|3[01])\.'
    r'|//192\.168\.|//100\.\d'
)
SCHEMA_URL_RE = re.compile(
    r'http://schemas\.openxmlformats\.org|http://schemas\.microsoft\.com'
    r'|http://www\.w3\.org/|http://purl\.org/'
    r'|http://ns\.adobe\.com|http://xml\.org/'
    r'|xmlns[=:]'
)
CJK_RE = re.compile(
    r'[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\uAC00-\uD7AF\u3040-\u309F\u30A0-\u30FF]'
)
INVISIBLE_UNICODE_RE = re.compile(
    r'[\u200B\u200C\u200D\u200E\u200F\uFEFF\u2060\u2061\u2062\u2063\u2064'
    r'\u202A\u202B\u202C\u202D\u202E\u2066\u2067\u2068\u2069'
    r'\u00AD\u034F\u180E\u2800\u3164]'
)
DAN_RE = re.compile(
    r'do anything now|\bDAN\b|jailbreak|jailbroken|developer mode|chaos mode|unrestricted mode|'
    r'no (rules|restrictions|limits|boundaries|guidelines)|'
    r'bypass (safety|security|filter|restriction)|'
    r'without (restrictions|limits|rules|boundaries)',
    re.IGNORECASE,
)
DAN_SECURITY_WORDS = [
    'check', 'verify', 'verified', 'dangerous', 'error', "don't",
    'prevent', 'avoid', 'never', 'must not', 'should not', 'footgun', 'allows'
]
CRED_PAT_RE = re.compile(
    r'cookies\.json|\.ssh/|(?:^|[\s/])\.env[^a-zA-Z]'
    r'|\.aws/credentials|\.netrc|\.docker/config\.json'
)
EXFIL_RE = re.compile(r'curl |wget |\bfetch\(|requests\.(get|post|put)|urllib\.request')

MX_DANGEROUS_CMD_RE = re.compile(
    r'(?:^|[\s;|&])'
    r'(?:'
    r'(?:curl|wget)\s+[^\s]*(?:\$\(|`)'
    r'|(?:curl|wget)\s+.*data=\$'
    r'|(?:curl|wget)\s+https?://[^\s]*\.(?:com|net|org|io|xyz|tk|cc)[^\s]*\?[^\s]*='
    r')',
    re.IGNORECASE | re.MULTILINE,
)
MX_NETWORK_CMD_RE = re.compile(
    r'(?:curl|wget)\s+https?://(?!.*(?:\.sankuai\.com|\.meituan\.com|\.neixin\.cn|localhost|127\.0\.0\.1))',
    re.IGNORECASE,
)
MX_DATA_THEFT_RE = re.compile(
    r'\$\(\s*cat\s+[~/.]*(?:ssh|env|aws|\.env|passwd|shadow|netrc|docker)'
    r'|cat\s+[~/.]*\.ssh/id_'
    r'|cat\s+/etc/(?:passwd|shadow)',
    re.IGNORECASE,
)

CODE_EXTENSIONS = {'.py', '.sh', '.js', '.ts', '.bash', '.zsh', '.pl', '.rb'}
TEST_FILE_RE = re.compile(
    r'(^|/)test_[^/]*\.py$'
    r'|(^|/)[^/]*_test\.py$'
    r'|(^|/)tests/'
    r'|(^|/)conftest\.py$'
)

# =============================================================================
# 文件分类
# =============================================================================

Match = Dict[str, Any]


def classify_files(skill_dir: Path) -> Dict[str, List[str]]:
    """将 skill 目录下文件分类为 code/md/md_no_ref/ref_md/all。"""
    all_files: List[str] = []
    code_files: List[str] = []
    md_files: List[str] = []
    md_no_ref: List[str] = []
    ref_md_files: List[str] = []

    # 自排除：skillhub/scripts/ 下所有工具脚本均属于发布工具本身，不属于被扫描的 skill 内容
    _self_scripts_dir = Path(__file__).parent.resolve()
    _self_exclude = {
        str(p.resolve())
        for p in _self_scripts_dir.iterdir()
        if p.is_file()
    }

    for fpath in skill_dir.rglob('*'):
        if not fpath.is_file():
            continue
        rel = str(fpath.relative_to(skill_dir))
        abs_path = str(fpath)

        if str(fpath.resolve()) in _self_exclude:
            continue
        if TEST_FILE_RE.search(rel):
            continue
        all_files.append(abs_path)

        parts = Path(rel).parts
        if len(parts) > 0 and parts[0] == 'scripts':
            code_files.append(abs_path)
        elif len(parts) == 1 and fpath.suffix in CODE_EXTENSIONS:
            code_files.append(abs_path)
        elif '/scripts/' in abs_path and abs_path not in code_files:
            code_files.append(abs_path)

        if fpath.suffix == '.md':
            md_files.append(abs_path)
            if 'references' not in parts:
                md_no_ref.append(abs_path)

        if fpath.suffix == '.md' and len(parts) > 0 and parts[0] == 'references':
            ref_md_files.append(abs_path)

    return {
        "all": all_files,
        "code": code_files,
        "md": md_files,
        "md_no_ref": md_no_ref,
        "ref_md": ref_md_files,
    }


# =============================================================================
# 文件读取缓存
# =============================================================================

class FileCache:
    def __init__(self):
        self._cache: Dict[str, Optional[str]] = {}
        self._has_internal: Dict[str, bool] = {}
        self._has_cjk: Dict[str, bool] = {}

    def read(self, path: str) -> Optional[str]:
        if path not in self._cache:
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    self._cache[path] = f.read()
            except Exception:
                self._cache[path] = None
        return self._cache[path]

    def has_internal_domain(self, path: str) -> bool:
        if path not in self._has_internal:
            content = self.read(path)
            self._has_internal[path] = bool(content and INTERNAL_DOMAINS_RE.search(content))
        return self._has_internal[path]

    def has_cjk(self, path: str) -> bool:
        if path not in self._has_cjk:
            content = self.read(path)
            self._has_cjk[path] = bool(content and CJK_RE.search(content))
        return self._has_cjk[path]


# =============================================================================
# 扫描函数
# =============================================================================

def grep_fast(cache: FileCache, rule_id: str, pattern: str,
              files: List[str], skill_dir: str,
              max_matches: int = 50) -> List[Match]:
    compiled = _COMPILED_RULES.get(rule_id)
    if compiled is None:
        try:
            compiled = re.compile(pattern)
        except re.error:
            return []
    matches: List[Match] = []
    for fpath in files:
        content = cache.read(fpath)
        if content is None:
            continue
        rel = os.path.relpath(fpath, skill_dir) if skill_dir else fpath
        for lineno, line in enumerate(content.splitlines(), 1):
            if compiled.search(line):
                matches.append({"file": rel, "line": lineno, "content": line[:200]})
                if len(matches) >= max_matches:
                    return matches
    return matches


def grep_no_internal(cache: FileCache, rule_id: str, pattern: str,
                     files: List[str], skill_dir: str,
                     max_matches: int = 50) -> List[Match]:
    compiled = _COMPILED_RULES.get(rule_id)
    if compiled is None:
        try:
            compiled = re.compile(pattern)
        except re.error:
            return []
    matches: List[Match] = []
    for fpath in files:
        content = cache.read(fpath)
        if content is None:
            continue
        if INTERNAL_DOMAINS_RE.search(content):
            continue
        rel = os.path.relpath(fpath, skill_dir) if skill_dir else fpath
        for lineno, line in enumerate(content.splitlines(), 1):
            if compiled.search(line):
                if SCHEMA_URL_RE.search(line):
                    continue
                matches.append({"file": rel, "line": lineno, "content": line[:200]})
                if len(matches) >= max_matches:
                    return matches
    return matches


def scan_mx001(cache: FileCache, files: List[str], skill_dir: str) -> List[Match]:
    matches: List[Match] = []
    for fpath in files:
        content = cache.read(fpath)
        if content is None:
            continue
        rel = os.path.relpath(fpath, skill_dir) if skill_dir else fpath
        in_code_block = False
        for lineno, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if INTERNAL_DOMAINS_RE.search(line) and not MX_DATA_THEFT_RE.search(line):
                continue
            hit = False
            if MX_DANGEROUS_CMD_RE.search(line):
                hit = True
            elif MX_DATA_THEFT_RE.search(line):
                hit = True
            elif MX_NETWORK_CMD_RE.search(line):
                lower = line.lower()
                if any(w in lower for w in ['steal', 'exfil', 'secret', 'password',
                                             'token', 'key', 'cred', 'ssh', 'env',
                                             'passwd', 'shadow', '$(']):
                    hit = True
            if hit:
                matches.append({"file": rel, "line": lineno, "content": line[:200]})
                if len(matches) >= 50:
                    return matches
    return matches


# =============================================================================
# Stage 1 静态扫描主函数
# =============================================================================

def get_dir_size_kb(path: str) -> int:
    total = 0
    for root, _, fnames in os.walk(path):
        for fn in fnames:
            try:
                total += os.path.getsize(os.path.join(root, fn))
            except OSError:
                pass
    return max(total // 1024, 1)


def parse_frontmatter(skill_md_path: str) -> Optional[Dict[str, Any]]:
    """解析 SKILL.md YAML frontmatter，支持 block scalar（description: |）。"""
    try:
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return None
    m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return None
    fm: Dict[str, Any] = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        kv = re.match(r'^(\w[\w-]*):\s*(.*)', line)
        if kv:
            key, val = kv.group(1), kv.group(2).strip()
            # block scalar: description: | 或 description: >
            if val in ('|', '>', '|-', '>-', ''):
                block_lines = []
                i += 1
                while i < len(lines) and (lines[i].startswith(' ') or lines[i].startswith('\t')):
                    block_lines.append(lines[i].strip())
                    i += 1
                fm[key] = ' '.join(block_lines)
                continue
            else:
                if (val.startswith('"') and val.endswith('"')) or \
                   (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                fm[key] = val
        i += 1
    return fm or None


def count_skill_md_lines(skill_dir: str) -> int:
    """统计 SKILL.md 行数。"""
    skillmd = os.path.join(skill_dir, "SKILL.md")
    try:
        with open(skillmd, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def check_skillmd(skill_dir: str) -> int:
    """验证 SKILL.md 基本格式，返回 0=OK / 1=WARN / 2=ERROR。"""
    sd = os.path.realpath(skill_dir)
    skillmd_path = os.path.join(sd, "SKILL.md")

    print("▶ 验证 SKILL.md...")

    if not os.path.isfile(skillmd_path):
        print(f"  ❌ 未找到 SKILL.md：{skillmd_path}")
        return 2

    fm = parse_frontmatter(skillmd_path)
    if fm is None:
        print("  ❌ frontmatter 解析失败，请确认文件以 --- 开头和结尾")
        return 2

    missing = [f for f in ("name", "description") if not fm.get(f)]
    if missing:
        print(f"  ❌ frontmatter 缺少必填字段：{', '.join(missing)}")
        return 2

    name = fm.get("name", "")
    desc = fm.get("description", "")
    desc_len = len(desc)
    line_count = count_skill_md_lines(sd)
    rc = 0

    print(f"  ✅ name: {name}")
    print(f"  ✅ description: {desc_len} 字符")

    if desc_len < 20:
        print(f"  ⚠️  description 过短（{desc_len} 字符，建议 ≥ 20）")
        rc = 1
    elif desc_len > 500:
        print(f"  ⚠️  description 过长（{desc_len} 字符，建议 ≤ 500）")
        rc = 1

    if line_count > 500:
        print(f"  ⚠️  SKILL.md 行数 {line_count} > 500，建议拆分到 references 文件")
        rc = 1

    print()
    return rc


def run_static_scan(skill_dir: str) -> Dict[str, Any]:
    """执行 Stage 1 静态扫描，返回结果字典。"""
    sd = os.path.realpath(skill_dir)
    files = classify_files(Path(sd))
    cache = FileCache()
    checks: List[Dict[str, Any]] = []
    worst = "PASS"
    risk_score = 0

    def add_check(check_id: str, name: str, result: str, matches: List[Match]):
        nonlocal worst, risk_score
        checks.append({"id": check_id, "name": name, "result": result, "matches": matches})
        if result == "FAIL":
            worst = "FAIL"
            risk_score += SCORING["FAIL"]
        elif result == "WARN" and worst != "FAIL":
            worst = "WARN"
            risk_score += SCORING["WARN"]

    for rule in RULES:
        rid = rule["id"]
        name = rule["name"]
        severity = rule["severity"]
        scope = rule["scope"]
        pattern = rule.get("pattern")

        if scope in ("special",):
            target_files = []
        elif scope == "code":
            target_files = files["code"]
        elif scope == "code_no_internal":
            target_files = files["code"]
        elif scope == "md":
            target_files = files["md"]
        elif scope == "md_no_ref":
            target_files = files["md_no_ref"]
        elif scope == "ref_md":
            target_files = files["ref_md"]
        elif scope == "all":
            target_files = files["all"]
        else:
            target_files = []

        if rid == "PI-003":
            non_cjk = [f for f in files["all"] if not cache.has_cjk(f)]
            m: List[Match] = []
            for fpath in non_cjk:
                content = cache.read(fpath)
                if not content:
                    continue
                rel = os.path.relpath(fpath, sd)
                for lineno, line in enumerate(content.splitlines(), 1):
                    if INVISIBLE_UNICODE_RE.search(line):
                        m.append({"file": rel, "line": lineno, "content": line[:200]})
                        if len(m) >= 50:
                            break
                if len(m) >= 50:
                    break
            add_check(rid, name, "FAIL" if m else "PASS", m)
            continue

        if rid == "PI-005":
            m = []
            for fpath in files["md_no_ref"]:
                content = cache.read(fpath)
                if not content:
                    continue
                rel = os.path.relpath(fpath, sd)
                for lineno, line in enumerate(content.splitlines(), 1):
                    if DAN_RE.search(line):
                        lower = line.lower()
                        if not any(w in lower for w in DAN_SECURITY_WORDS):
                            m.append({"file": rel, "line": lineno, "content": line[:200]})
                            if len(m) >= 50:
                                break
                if len(m) >= 50:
                    break
            add_check(rid, name, "FAIL" if m else "PASS", m)
            continue

        if rid == "SL-001":
            m_code = grep_fast(cache, rid, CRED_PAT_RE.pattern, files["code"], sd)
            m_md = grep_fast(cache, rid, CRED_PAT_RE.pattern, files["md"], sd)
            all_m = m_code + m_md
            if all_m:
                has_exfil = False
                for fpath in files["code"]:
                    fc = cache.read(fpath)
                    if fc and CRED_PAT_RE.search(fc) and EXFIL_RE.search(fc):
                        if not INTERNAL_DOMAINS_RE.search(fc):
                            has_exfil = True
                            break
                add_check(rid, name, "FAIL" if has_exfil else "WARN",
                          m_code if has_exfil else all_m)
            else:
                add_check(rid, name, "PASS", [])
            continue

        if rid == "OP-001":
            skillmd = os.path.join(sd, "SKILL.md")
            content = cache.read(skillmd) or ""
            yaml_m = re.match(r'^---\n(.*?)^---', content, re.MULTILINE | re.DOTALL)
            if yaml_m:
                yaml_block = yaml_m.group(1)
                if re.search(r'allowed.tools', yaml_block, re.IGNORECASE):
                    dangerous = re.search(r'(?i)(Bash|Write|exec|shell)', yaml_block)
                    if dangerous:
                        add_check("OP-002", "High-risk tools", "WARN",
                                  [{"file": "SKILL.md", "line": 0,
                                    "content": f"High-risk tool: {dangerous.group(0)}"}])
                    else:
                        add_check(rid, name, "PASS", [])
                else:
                    add_check(rid, "No tool restrictions", "WARN",
                              [{"file": "SKILL.md", "line": 0,
                                "content": "No allowed-tools in frontmatter"}])
            else:
                add_check(rid, "No tool restrictions", "WARN",
                          [{"file": "SKILL.md", "line": 0,
                            "content": "No YAML frontmatter found"}])
            continue

        if rid == "QA-001":
            skillmd = os.path.join(sd, "SKILL.md")
            content = cache.read(skillmd) or ""
            desc = ""
            yaml_m = re.match(r'^---\n(.*?)^---', content, re.MULTILINE | re.DOTALL)
            if yaml_m:
                yaml_block = yaml_m.group(1)
                dm = re.search(
                    r'description:\s*>?-?\s*\n?(.*?)(?=\n[a-zA-Z_-]+:|\n---|\Z)',
                    yaml_block, re.DOTALL
                )
                if dm:
                    desc = ' '.join(dm.group(1).split())
                if not desc:
                    dm2 = re.search(r'description:\s*["\']?(.+?)["\']?\s*$', yaml_block, re.MULTILINE)
                    if dm2:
                        desc = dm2.group(1)
            dl = len(desc)
            if dl < 20:
                add_check("QA-001", "Description too short", "WARN",
                          [{"file": "SKILL.md", "line": 0,
                            "content": f"Description: {dl} chars (min 20)"}])
            elif dl > 500:
                add_check("QA-002", "Description too long", "WARN",
                          [{"file": "SKILL.md", "line": 0,
                            "content": f"Description: {dl} chars (max 500)"}])
            else:
                add_check("QA-001", name, "PASS", [])
            continue

        if rid == "QA-003":
            file_count = len(files["all"])
            size_kb = get_dir_size_kb(sd)
            items = []
            if file_count > 50:
                items.append({"file": ".", "line": 0, "content": f"Files: {file_count} (>50)"})
            if size_kb > 2048:
                items.append({"file": ".", "line": 0, "content": f"Size: {size_kb}KB (>2MB)"})
            add_check(rid, name, "WARN" if items else "PASS", items)
            continue

        if rid == "MX-001":
            m = scan_mx001(cache, files["md_no_ref"], sd)
            add_check(rid, name, "FAIL" if m else "PASS", m)
            continue

        if scope == "special" or pattern is None:
            continue

        if rule.get("exclude_ref"):
            target_files = [f for f in target_files
                            if '/references/' not in f and '\\references\\' not in f]

        if scope == "code_no_internal":
            m = grep_no_internal(cache, rid, pattern, target_files, sd)
        else:
            m = grep_fast(cache, rid, pattern, target_files, sd)

        add_check(rid, name, severity if m else "PASS", m)

    risk_score = min(risk_score, 100)
    risk_level = "critical"
    for threshold, level in RISK_THRESHOLDS:
        if risk_score <= threshold:
            risk_level = level
            break

    pass_c = sum(1 for c in checks if c["result"] == "PASS")
    warn_c = sum(1 for c in checks if c["result"] == "WARN")
    fail_c = sum(1 for c in checks if c["result"] == "FAIL")

    return {
        "skill_dir": sd,
        "scan_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": worst,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "checks": checks,
        "findings": [c for c in checks if c["result"] != "PASS"],
        "stats": {
            "total_files": len(files["all"]),
            "total_size_kb": get_dir_size_kb(sd),
            "pass": pass_c, "warn": warn_c, "fail": fail_c,
        },
    }


# =============================================================================
# 输出
# =============================================================================

def print_scan_result(result: Dict[str, Any]) -> None:
    print("==========================================")
    print("  Stage 1 静态安全扫描")
    print("==========================================")
    print(f"目录：{result['skill_dir']}")
    print(f"时间：{result['scan_time']}")
    print(f"文件：{result['stats']['total_files']}  大小：{result['stats']['total_size_kb']}KB")
    print(f"风险分：{result['risk_score']}/100 ({result['risk_level']})")
    print("------------------------------------------")

    for check in result["checks"]:
        r = check["result"]
        if r == "PASS":
            continue
        icon = {"WARN": "⚠️ ", "FAIL": "❌"}.get(r, "?")
        print(f"{icon} [{r}] {check['id']} — {check['name']}")
        for m in check["matches"][:5]:
            content = m["content"][:120]
            print(f"     → {m['file']}:{m['line']}  {content}")

    print()
    print("------------------------------------------")
    s = result["stats"]
    print(f"汇总：{result['summary']}  (PASS:{s['pass']}  WARN:{s['warn']}  FAIL:{s['fail']})")
    print("==========================================")


def run_security_check(skill_dir: str) -> Tuple[int, str]:
    """调用 security-check.py，返回 (exit_code, output)。"""
    sc_path = Path(__file__).parent / "security-check.py"
    if not sc_path.exists():
        return 0, "⚠️  security-check.py 未找到，跳过内部专项检查"
    try:
        result = subprocess.run(
            [sys.executable, str(sc_path), skill_dir],
            capture_output=True, text=True, timeout=60
        )
        output = result.stdout + result.stderr
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 0, "⚠️  security-check.py 超时，跳过"
    except Exception as e:
        return 0, f"⚠️  security-check.py 执行失败：{e}"


# =============================================================================
# 主流程
# =============================================================================

def do_scan(skill_dir: str) -> int:
    """执行完整安全扫描，返回退出码。"""
    sd = os.path.realpath(skill_dir)

    print(f"\n{'='*50}")
    print(f"  SkillHub 安全扫描")
    print(f"{'='*50}")
    print(f"Skill 目录：{sd}")
    print()

    # Step 0：验证 SKILL.md 基本格式
    skillmd_rc = check_skillmd(sd)
    if skillmd_rc == 2:
        return 2

    # Stage 1：通用静态扫描
    print("▶ Stage 1: 静态安全扫描...")
    scan_result = run_static_scan(sd)
    print_scan_result(scan_result)

    stage1_summary = scan_result["summary"]

    # Stage 2：美团内部专项规则
    print("▶ Stage 2: 美团内部专项安全检查...")
    mt_rc, mt_output = run_security_check(sd)
    print(mt_output.rstrip())

    has_fail = stage1_summary == "FAIL" or mt_rc == 2
    has_warn = skillmd_rc == 1 or stage1_summary == "WARN" or mt_rc == 1

    print()
    if has_fail:
        print("❌ 扫描发现 FAIL 级问题，建议修复后再发布。")
        print("   详细规则说明：references/security-scan-rules.md")
        return 2
    elif has_warn:
        print("⚠️  扫描完成，有警告（无 FAIL）。")
        return 1
    else:
        print("✅ 扫描完成，全部 PASS。")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="security-scan.py — SkillHub Skill 安全扫描工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python security-scan.py                        # 扫描当前目录
  python security-scan.py /path/to/my-skill      # 扫描指定目录

退出码：
  0 — 全 PASS
  1 — 有 WARN（无 FAIL）
  2 — 有 FAIL
        """,
    )
    parser.add_argument(
        "skill_dir",
        nargs="?",
        default=None,
        metavar="<skill目录>",
        help="Skill 目录路径（默认：当前工作目录）",
    )
    args = parser.parse_args()

    skill_dir = args.skill_dir or os.getcwd()
    if not os.path.isdir(skill_dir):
        print(f"❌ 目录不存在：{skill_dir}", file=sys.stderr)
        return 2

    return do_scan(skill_dir)


if __name__ == "__main__":
    sys.exit(main())
