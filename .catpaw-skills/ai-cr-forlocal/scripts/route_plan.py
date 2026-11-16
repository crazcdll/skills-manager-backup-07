#!/usr/bin/env python3
"""
route_plan.py — 路由计划生成器（风险分档 + 条目级过滤）
输入：/tmp/cr_signal_rules.json + diff
输出：/tmp/cr_route_plan.json（spawn 计划）+ /tmp/cr_route_4a_*.md（路由版 checklist，4-A 注入用）

路由声明单一真源：references/rule-index.json（signal_weights + checklist_routing），本文件零路由数据。

- 分档 = diff 行数（基础档）⊕ 风险分（信号权重求和，权重见 rule-index.json）：高危信号命中 → 至少 standard；风险分 ≥8 → full
- 条目级过滤：触发关键词 ∩ diff 命中保留；无可评估 token 保守保留；关键词未命中但 section 映射的窄信号（权重≥2）活跃 → 保留
- 路由版 checklist 落盘 /tmp/cr_route_4a_{p0|p1|p3|all}.md（全局校验头 + 命中条目），4-A 直接注入
- guard：checklist 解析 <5 条 → 该文件回退全量；diff 缺失/空 → 退出非零（route_status=failed 回退固定路由）
"""
import json, re, sys, argparse
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
REFS = SKILL_ROOT / "references"

def load_routing():
    """路由声明全部来自 rule-index.json（单一真源），本文件零路由数据"""
    idx = json.loads((SKILL_ROOT / "references" / "rule-index.json").read_text(encoding="utf-8"))
    weights = {k: v for k, v in idx.get("signal_weights", {}).items() if not k.startswith("_")}
    cr = idx.get("checklist_routing", {})
    # 4-A checklist files and section→signal mappings (skip four_b and _comment)
    files = {role: cfg["checklist"] for role, cfg in cr.items()
             if not role.startswith("_") and isinstance(cfg, dict) and "checklist" in cfg}
    sigs = {role: cfg["sections"] for role, cfg in cr.items()
            if not role.startswith("_") and isinstance(cfg, dict) and "sections" in cfg and "checklist" in cfg}
    return weights, files, sigs, cr


SIG_RISK, CHECKLIST_FILES, CHECKLIST_SIG, CHECKLIST_ROUTING = load_routing()
HIGH_SIGS = {s for s, w in SIG_RISK.items() if w >= 3}
DEFAULT_WEIGHT = 1  # 表里没列的信号默认权重

# 常亮信号（任何 Java diff 几乎必中）——不作为条目级保留依据，只计 1 分
TOKEN_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_.@]*')


def has_code_token(kw):
    """可评估 = 含 ≥3 字符英文代码 token，或 ≥2 个连续汉字（中文关键词同样可判）。
    短符号 token（==、/）在注释/路径里必然误命中，不作为命中依据"""
    if any(len(m) >= 3 for m in TOKEN_RE.findall(kw)):
        return True
    return bool(re.search(r'[\u4e00-\u9fa5]{2,}', kw))


def parse_and_split(path):
    """checklist → (全局头行, sections[{name, lines, entries[{id,keywords,raw,keep}]}])"""
    lines = path.read_text(encoding="utf-8").splitlines()
    first_sec = next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))
    header, sections, cur = lines[:first_sec], [], None
    for ln in lines[first_sec:]:
        if ln.startswith("## "):
            cur = {"name": ln[3:].strip(), "lines": [], "entries": []}
            sections.append(cur)
        elif cur is not None:
            m = re.match(r"^\|\s*(CR:[A-Za-z0-9\-]+)\s*\|([^|]+)\|([^|]*)\|([^|]*)\|", ln)
            if m:
                eid, rule, judge, kws = m.groups()
                cur["entries"].append({
                    "id": eid.strip(), "rule": rule.strip(),
                    "keywords": [k.strip().strip("`") for k in kws.split(",") if k.strip()],
                    "raw": ln, "keep": False})
            else:
                cur["lines"].append(ln)
    return header, sections


def norm_section(name):
    """'3. 并发安全（CC）' → '并发安全'"""
    s = re.sub(r'^\d+\.\s*', '', name)
    s = re.sub(r'（[^）]*）$', '', s)
    return s.strip()


def kw_hit(kw, diff_text):
    """关键词命中判定：英文 token 用词边界（\b），中文子串。短符号 token（==、/）已被 has_code_token 过滤，不会到这里"""
    for tok in TOKEN_RE.findall(kw):
        if len(tok) < 3:
            continue
        if not re.search(r'(?<![A-Za-z0-9_])' + re.escape(tok) + r'(?![A-Za-z0-9_])', diff_text):
            return False
    for zh in re.findall(r'[\u4e00-\u9fa5]{2,}', kw):
        if zh not in diff_text:
            return False
    return True


def entry_keep(entry, diff_text, active_sigs, section_sigs):
    """条目级三判：① 关键词 token 命中 diff ② 无可评估 token → 保守保留
    ③ token 未命中 → 仅当 section 映射窄信号（权重≥2 的非常亮信号）活跃时保留"""
    usable = [kw for kw in entry["keywords"] if has_code_token(kw)]
    if not usable:
        return True, "no-token"
    if any(kw_hit(kw, diff_text) for kw in usable):
        return True, "kw-hit"
    sigs = section_sigs.get(entry["section"]) or section_sigs.get(norm_section(entry["section"])) or []
    narrow = [s for s in sigs if s in active_sigs and SIG_RISK.get(s, DEFAULT_WEIGHT) >= 2]
    if narrow:
        return True, "sig:" + ",".join(narrow)
    return False, ""


def build_trim(role, header, sections, active_sigs, diff_text, src_name):
    """过滤 + 生成路由版 checklist 文本。返回 (text, kept, total)"""
    section_sigs = CHECKLIST_SIG[role]
    # section 名挂到 entry 上
    for sec in sections:
        for e in sec["entries"]:
            e["section"] = sec["name"]
    all_entries = [e for sec in sections for e in sec["entries"]]
    total = len(all_entries)
    # guard：解析异常（条目过少）→ 全量保留
    fallback = total < 5
    reasons = []
    if not fallback:
        for e in all_entries:
            ok, why = entry_keep(e, diff_text, active_sigs, section_sigs)
            e["keep"] = ok
            if ok and why and why != "no-token":
                reasons.append(why)
    else:
        for e in all_entries:
            e["keep"] = True
    kept = sum(1 for e in all_entries if e["keep"])
    out = list(header)
    out.append(f"\n> ⚡ 路由路由版：基于信号+关键词命中保留 {kept}/{total} 条（完整版：references/{src_name}）。全局校验规则不变，照常执行。")
    for sec in sections:
        kept_es = [e for e in sec["entries"] if e["keep"]]
        if not kept_es:
            continue
        out.append(f"\n## {sec['name']}\n")
        out.extend(l for l in sec["lines"] if l.strip().startswith("|") or l.strip().startswith(">"))
        out.extend(e["raw"] for e in kept_es)
    return "\n".join(out) + "\n", kept, total, fallback


def parse_four_b_checklist(path):
    """解析 4-B 规则文件（Markdown 标题格式）→ (header, sections)

    格式：
    # 文件标题
    ## 说明
    ...
    ## 规则内容
    ### java-l1:JAVA-02.N001 [强制] 类成员与方法访问控制规范
    #### 规范说明
    ...
    ##### good case:
    ...
    ##### bad case:
    ...
    ### java-l1:JAVA-02.N002 [推荐] 内存泄漏预防
    ...

    兼容旧格式标题：### MT:N001 类成员与方法访问控制规范

    返回：(header_lines, sections[{name, rule_id, keywords, raw_lines, keep}])
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    # header = 第一个规则标题之前的所有行
    # 规则标题形态：### MT:xxx（旧）/ ### java-l1:XX-NN.YYY（新，mt-java-coding-standards 规则库）
    _RULE_HEADING = re.compile(r'^###\s+((?:MT:|java-l1:)\S+)\s+(.+)')
    first_rule = next((i for i, l in enumerate(lines) if _RULE_HEADING.match(l)), len(lines))
    header = lines[:first_rule]

    sections = []
    cur = None
    for ln in lines[first_rule:]:
        m = _RULE_HEADING.match(ln)
        if m:
            # 跳过示例标题（如 "### java-l1:DB-03.N001 表必须使用InnoDB引擎示例"）
            rule_name = m.group(2).strip()
            # 新格式规则名前带 [强制]/[推荐] 级别标注，剥离后提取名称
            rule_name = re.sub(r'^\[(?:强制|推荐|参考)\]\s*', '', rule_name)
            if rule_name.endswith('示例'):
                # 仍然是示例 section，归入上一个 section 的 raw_lines
                if cur:
                    cur["raw_lines"].append(ln)
                continue
            if cur:
                sections.append(cur)
            rule_id = m.group(1)
            # 从规则名提取关键词
            keywords = extract_keywords(rule_name)
            cur = {
                "name": rule_name,
                "rule_id": rule_id,
                "keywords": keywords,
                "raw_lines": [ln],
                "keep": False
            }
        elif cur is not None:
            cur["raw_lines"].append(ln)
    if cur:
        sections.append(cur)
    return header, sections


def extract_keywords(rule_name):
    """从规则名提取可评估关键词"""
    # 去掉常见无意义词
    stop_words = {"规范", "规则", "建议", "禁止", "必须", "应该", "优先", "避免", "防止",
                  "使用", "方法", "类型", "设计", "处理", "操作", "管理", "要求"}
    # 提取英文 camelCase / PascalCase / 大写缩写词
    en_tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', rule_name)
    # 提取中文词语（2~6 字连续汉字）
    zh_tokens = re.findall(r'[\u4e00-\u9fa5]{2,6}', rule_name)
    tokens = en_tokens + zh_tokens
    return [t for t in tokens if t not in stop_words and len(t) >= 2]


def strip_good_case(lines):
    """剥离 good case 代码块，保留 bad case。子 Agent 需要识别问题模式（bad case），
    不需要学习正确写法（good case）。"""
    result = []
    in_code = False
    prev_meaningful = ""  # 代码块前的最后一个标记行
    skip_current_block = False
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("```"):
            if in_code:
                in_code = False
                if skip_current_block:
                    continue  # 跳过结束标记
                result.append(ln)
                continue
            else:
                in_code = True
                # 判断是否 good case
                lower_prev = prev_meaningful.lower()
                if any(tag in lower_prev for tag in ("good case", "正确示例", "✅", "推荐做法", "正例")):
                    skip_current_block = True
                    continue  # 跳过开始标记
                else:
                    skip_current_block = False
                    result.append(ln)
                    continue
        if in_code and skip_current_block:
            continue  # 跳过 good case 代码行
        result.append(ln)
        if stripped and not stripped.startswith("|"):
            prev_meaningful = stripped
    return result


def build_trim_four_b(file_path, file_key, active_sigs, diff_text, four_b_routing):
    """4-B 条目级裁剪。返回 (text, kept, total, fallback)

    逻辑同 entry_keep：
    ① 规则名关键词命中 diff → 保留
    ② 无可评估关键词 → 保守保留
    ③ 关键词未命中 → section 映射的信号活跃 → 保留
    """
    path = Path(file_path)
    if not path.exists():
        return "", 0, 0, True

    header, sections = parse_four_b_checklist(path)

    # 获取该文件的 section→信号映射
    file_routing = four_b_routing.get("files", {}).get(file_key, {})
    section_sigs = file_routing.get("sections", {})

    total = len(sections)
    if total < 3:
        # 规则太少，全量保留
        for s in sections:
            s["keep"] = True
        return path.read_text(encoding="utf-8"), total, total, True

    for s in sections:
        usable = [kw for kw in s["keywords"] if has_code_token(kw)]
        if not usable:
            s["keep"] = True
            continue
        if any(kw_hit(kw, diff_text) for kw in usable):
            s["keep"] = True
            continue
        # 信号匹配
        sigs = section_sigs.get(s["name"]) or section_sigs.get(norm_section(s["name"])) or []
        narrow = [sig for sig in sigs if sig in active_sigs]
        if narrow:
            s["keep"] = True
            continue
        s["keep"] = False

    kept = sum(1 for s in sections if s["keep"])

    # 生成路由版文本（剥离 good case 代码块，保留 bad case 帮助识别问题模式）
    out = list(header)
    out.append(f"\n> ⚡ 路由版：基于信号+关键词命中保留 {kept}/{total} 条规则（完整版：{path.name}）。good case 示例已剥离以缩减上下文。")
    for s in sections:
        if s["keep"]:
            out.extend(strip_good_case(s["raw_lines"]))

    return "\n".join(out) + "\n", kept, total, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", default="/tmp/cr_signal_rules.json")
    ap.add_argument("--diff", default="/tmp/local_cr_diff.txt")
    ap.add_argument("--repo", default="", help="仓库路径（探测 .mdp/rules + .catpaw/rules）")
    ap.add_argument("--name", default="", help="仓库名基准（远程 remote 名；默认取路径 basename，与 cr-cli 的 REPO_NAME 对齐用）")
    ap.add_argument("--config", default=str(SKILL_ROOT / "cr-config.yaml"))
    ap.add_argument("--output", default="/tmp/cr_route_plan.json")
    args = ap.parse_args()

    # ── guard：diff 必须存在且非空 ──
    dp = Path(args.diff)
    if not dp.exists() or dp.stat().st_size == 0:
        print("FATAL: diff 文件缺失或为空，路由中止（走回退）", file=sys.stderr)
        sys.exit(1)
    diff_text = dp.read_text(encoding="utf-8", errors="replace")
    diff_lines = diff_text.count("\n") + 1

    try:
        sig = json.loads(Path(args.signals).read_text(encoding="utf-8"))
        active_sigs = set(sig.get("active_signals", []))
    except Exception:
        active_sigs, sig = set(), {}

    # config 阀
    max_sub, small_diff, full_diff = 5, 300, 1500
    risk_std_th, risk_full_th = 4, 8
    try:
        cfg = Path(args.config).read_text(encoding="utf-8")
        for key, var in [("max_subagents", "max_sub"), ("small_diff_lines", "small_diff"),
                         ("full_diff_lines", "full_diff"), ("risk_standard", "risk_std_th"),
                         ("risk_full", "risk_full_th")]:
            m = re.search(rf"{key}:\s*(\d+)", cfg)
            if m:
                v = int(m.group(1))
                if key in ("max_subagents",): max_sub = v
                elif key in ("small_diff_lines",): small_diff = v
                elif key in ("full_diff_lines",): full_diff = v
                elif key in ("risk_standard",): risk_std_th = v
                elif key in ("risk_full",): risk_full_th = v
    except Exception:
        pass

    # ── 风险分（分布 × 数量）──
    risk_detail = {s: SIG_RISK.get(s, DEFAULT_WEIGHT) for s in sorted(active_sigs)}
    risk_score = sum(risk_detail.values())
    high_hits = sorted(active_sigs & HIGH_SIGS)

    # ── 分档：行数基础档 + 风险加权 ──
    base = "lite" if diff_lines < small_diff else ("standard" if diff_lines <= full_diff else "full")
    tier, why = base, [f"lines={diff_lines}→{base}"]
    if high_hits:
        if tier == "lite":
            tier = "standard"
        why.append(f"高危信号{high_hits}→至少standard")
    if risk_score >= risk_full_th and tier != "full":
        tier = "full"
        why.append(f"风险分{risk_score}≥{risk_full_th}→full")
    elif risk_score >= risk_std_th and tier == "lite":
        tier = "standard"
        why.append(f"风险分{risk_score}≥{risk_std_th}→standard")

    # ── L3 条目级过滤 + 路由版 checklist ──
    trims = {}
    for role, fname in CHECKLIST_FILES.items():
        header, sections = parse_and_split(REFS / fname)
        text, kept, total, fb = build_trim(role, header, sections, active_sigs, diff_text, fname)
        out = Path(f"/tmp/cr_route_4a_{role}.md")
        out.write_text(text, encoding="utf-8")
        trims[role] = {"kept": kept, "total": total, "fallback": fb, "file": str(out)}

    # lite 档合一文件
    if tier == "lite":
        combined = [f"# 4-A 路由裁剪合并版（lite 档）\n"]
        for role in ("p0", "p1", "p3"):
            combined.append(Path(trims[role]["file"]).read_text(encoding="utf-8"))
            combined.append("\n---\n")
        allf = Path("/tmp/cr_route_4a_all.md")
        allf.write_text("\n".join(combined), encoding="utf-8")
        trims["all"] = {"kept": sum(t["kept"] for t in trims.values() if isinstance(t, dict)),
                        "total": sum(t["total"] for t in trims.values() if isinstance(t, dict)),
                        "file": str(allf)}

    # ── 4-A 拆分 ──
    four_a = []
    if tier == "lite":
        four_a = [{"agent": "4-A-all", "checklists": ["p0", "p1", "p3"],
                   "inject": trims["all"]["file"], "entries": trims["all"]["kept"],
                   "output": "main_p0.json"}]
    elif tier == "standard":
        # P1+P3 始终合并（V118）：释放槽位给 4-B
        groups = []
        if trims["p0"]["kept"]: groups.append(("4-A-P0", ["p0"], "main_p0.json"))
        p1k, p3k = trims["p1"]["kept"], trims["p3"]["kept"]
        if p1k and p3k:
            groups.append(("4-A-P1+P3", ["p1", "p3"], "main_p1.json"))
        elif p1k:
            groups.append(("4-A-P1", ["p1"], "main_p1.json"))
        elif p3k:
            groups.append(("4-A-P3", ["p3"], "main_p3.json"))
        for name, roles, out in groups:
            if len(roles) > 1:
                comb = [Path(trims[r]["file"]).read_text(encoding="utf-8") for r in roles]
                f = f"/tmp/cr_route_4a_{'+'.join(roles)}.md"
                Path(f).write_text("\n---\n".join(comb), encoding="utf-8")
            else:
                f = trims[roles[0]]["file"]
            four_a.append({"agent": name, "checklists": roles, "inject": f,
                           "entries": sum(trims[r]["kept"] for r in roles), "output": out})
    else:
        # full 档：P1+P3 始终合并（V118），释放 1 槽给 4-B
        groups = []
        if trims["p0"]["kept"]: groups.append(("4-A-P0", ["p0"], "main_p0.json"))
        p1k, p3k = trims["p1"]["kept"], trims["p3"]["kept"]
        if p1k and p3k:
            groups.append(("4-A-P1+P3", ["p1", "p3"], "main_p1.json"))
        elif p1k:
            groups.append(("4-A-P1", ["p1"], "main_p1.json"))
        elif p3k:
            groups.append(("4-A-P3", ["p3"], "main_p3.json"))
        for name, roles, out in groups:
            if len(roles) > 1:
                comb = [Path(trims[r]["file"]).read_text(encoding="utf-8") for r in roles]
                f = f"/tmp/cr_route_4a_{'+'.join(roles)}.md"
                Path(f).write_text("\n---\n".join(comb), encoding="utf-8")
            else:
                f = trims[roles[0]]["file"]
            four_a.append({"agent": name, "checklists": roles, "inject": f,
                           "entries": sum(trims[r]["kept"] for r in roles), "output": out})

    # ── 4-B 信号驱动分组（V115：重均衡为 3 逻辑域，按信号启动）──
    agent_files = sig.get("agent_files", {})
    SECURITY_SEARCH_HA = {"HA-12", "HA-13"}  # 安全编码 + 搜索引擎归 security-search
    GROUPS = {"code-data": {}, "runtime": {}, "security-search": {}}
    for source_agent, files in agent_files.items():
        for rule in files:
            rule_base = rule.rsplit(".", 1)[0]  # 去文件扩展名得规则号
            if source_agent in ("subagent-java", "subagent-db-dep"):
                GROUPS["code-data"][rule] = source_agent
            elif source_agent == "subagent-sec":
                GROUPS["security-search"][rule] = source_agent
            elif source_agent == "subagent-ha":
                target = "security-search" if rule_base in SECURITY_SEARCH_HA else "runtime"
                GROUPS[target][rule] = source_agent
            else:
                GROUPS["runtime"][rule] = source_agent

    matched_groups = [g for g in ("code-data", "runtime", "security-search") if GROUPS[g]]
    groups_rules = {g: sorted(GROUPS[g]) for g in matched_groups}

    def make_b(group):
        return {"agent": f"4-B-{group}", "groups": [group],
                "rules": [f"{group}:{r}" for r in groups_rules[group]],
                "output": f"step4b_{group}.json"}

    b_candidates = [make_b(g) for g in matched_groups]

    # 兜底：ACTIVE_SIGNALS 为空 → 只开 code-data 全规则（不再四组齐开）
    if not active_sigs:
        fallback_rules = [f"code-data:{r}" for r in
                          ("JAVA-01", "JAVA-02", "JAVA-03", "JAVA-04", "JAVA-05", "JAVA-06", "JAVA-07", "JAVA-08",
                           "DB-01", "DB-02", "DB-03", "DB-04", "DEP-01")]
        b_candidates = [{"agent": "4-B-code-data", "groups": ["code-data"],
                         "rules": fallback_rules, "output": "step4b_code-data.json"}]

    # lite 档 4-B 合一
    if tier == "lite" and len(b_candidates) > 1:
        all_rules = [r for b in b_candidates for r in b["rules"]]
        all_groups = [g for b in b_candidates for g in b["groups"]]
        b_candidates = [{"agent": "4-B-all", "groups": all_groups, "rules": all_rules,
                         "output": "step4b_all.json"}]
    four_b = b_candidates

    # ── 测试规范降权：生产代码为主时移除 JAVA-07（V118）──
    # 统计 diff 中测试文件 vs 生产文件比例
    test_patterns = ('Test.java', 'Tests.java', 'Spec.java', 'Specs.java', '/test/', 'IT.java')
    diff_files = []
    for ln in diff_text.splitlines():
        if ln.startswith('+++ ') or ln.startswith('--- '):
            fn = ln[4:].strip().strip('"')
            if fn != '/dev/null' and not fn.startswith('a/') and not fn.startswith('b/'):
                diff_files.append(fn)
            elif fn.startswith('a/') or fn.startswith('b/'):
                diff_files.append(fn[2:])
    test_count = sum(1 for f in diff_files if any(p in f for p in test_patterns))
    prod_count = len(diff_files) - test_count
    if prod_count > 0 and test_count > 0 and prod_count >= test_count:
        # 生产代码为主，从 4-B 规则中移除 JAVA-07
        for b in four_b:
            b["rules"] = [r for r in b["rules"] if not r.endswith("JAVA-07")]
        if not any(b["rules"] for b in four_b):
            # 移除后如果某路空了，删掉该路
            four_b = [b for b in four_b if b["rules"]]
        print(f"[route] 测试规范降权：生产{prod_count}/测试{test_count}，JAVA-07 跳过", file=sys.stderr)

    # ── 4-B 条目级裁剪（V116）──
    four_b_routing = CHECKLIST_ROUTING.get("four_b", {})
    if four_b_routing and active_sigs:
        CHECKLIST_DIR_4B = SKILL_ROOT / "references" / "checklists" / "mt-java-coding-standards"
        # 构建短码→完整文件名映射（如 JAVA-01 → JAVA-01-常量定义规范）
        idx_raw = json.loads((SKILL_ROOT / "references" / "rule-index.json").read_text(encoding="utf-8"))
        short_to_full = {}
        for gcfg in idx_raw.get("groups", {}).values():
            for rule_name in gcfg.get("rules", []):
                short_code = rule_name.split("-", 2)[0] + "-" + rule_name.split("-", 2)[1] if "-" in rule_name else rule_name
                # rule_name 如 "JAVA-01-常量定义规范"，短码为 "JAVA-01"
                parts = rule_name.split("-", 2)
                if len(parts) >= 3:
                    short = parts[0] + "-" + parts[1]
                elif len(parts) == 2:
                    short = parts[0] + "-" + parts[1]
                else:
                    short = rule_name
                short_to_full[short] = rule_name
        for b in four_b:
            trim_parts = []
            total_kept = 0
            total_rules = 0
            for rule_key in b["rules"]:
                # 去掉 group 前缀
                file_key = rule_key.split(":", 1)[1] if ":" in rule_key else rule_key
                # 短码→完整文件名
                full_key = short_to_full.get(file_key, file_key)
                file_path = CHECKLIST_DIR_4B / f"{full_key}.md"
                text, kept, total, fb_trim = build_trim_four_b(file_path, full_key, active_sigs, diff_text, four_b_routing)
                if text:
                    trim_parts.append(text)
                    total_kept += kept
                    total_rules += total
            if trim_parts and total_rules > 0:
                trim_file = f"/tmp/cr_route_4b_{b['agent'].replace('4-B-','')}.md"
                Path(trim_file).write_text("\n\n".join(trim_parts), encoding="utf-8")
                b["inject"] = trim_file
                b["entries"] = total_kept

    # ── 4-C 独立路（V117 恢复）：自定义规则(CU) + 平台L2规则统一消费 ──
    # 4-D 回归纯业务边界（业务逻辑+SDD），不再携带 CU（V115 并入→V117 摘出）
    cu_dirs = []
    if args.repo:
        for sub in (".mdp/rules/team", ".mdp/rules/project", ".catpaw/rules"):
            d = Path(args.repo) / sub
            if d.is_dir() and list(d.glob("*.md")):
                cu_dirs.append(str(d))
    # 命名基准统一：--name 优先（cr-cli 传 remote 名），否则回退路径 basename
    # 不统一会导致 3A2/3A3 写的文件（remote 名）与 route_plan 读的（路径名）错位 → L2/CU 静默失联
    repo_name = args.name or (Path(args.repo).name if args.repo else "")
    cu_input = ""
    if repo_name and cu_dirs:
        _cu_file = f"/tmp/cr_custom_rules_{repo_name}.md"
        # 以文件存在为准（prep 3A2 产出）；目录有 md 但 prep 未跑时不应引用
        # 不存在的文件（老 bug：只看目录，单测/断点续跑场景会注入空路径）
        if Path(_cu_file).is_file():
            cu_input = _cu_file
    # 平台L2规则：prep 3A3 产出（摘要 l2_rules 字段），失败/未装 → none → 不启用
    l2_input = f"/tmp/cr_l2_rules_{repo_name}.md" if repo_name and Path(f"/tmp/cr_l2_rules_{repo_name}.md").is_file() else ""
    four_d_mode = "core_only" if tier in ("standard", "full") else "full_scan"
    four_d_split = tier == "full"  # full 档拆为 4-D-core + 4-D-logic
    others = [{"agent": "4-D", "always": True,
               "mode": four_d_mode,
               "split": four_d_split}]
    if four_d_split:
        others[0]["split_agents"] = [
            {"agent": "4-D-core", "desc": "疑点清单验证 + SDD 契约检查"},
            {"agent": "4-D-logic", "desc": "业务逻辑全量扫描（full_scan 模式）"}
        ]

    # ── 4-C lane：CU ∪ L2 任一可注入即开（都无则不 spawn，零成本）──
    four_c_enabled = bool(cu_input or l2_input)
    four_c_shards = []
    if four_c_enabled:
        inject_c = []
        if cu_input:
            inject_c.append(cu_input)
        if l2_input:
            inject_c.append(l2_input)
        # 体积护栏（与 4-C 通用契约一致）：两缓存合计 > 30KB → 按段切分，上限 3 分片
        c_bytes = sum(Path(p).stat().st_size for p in inject_c if Path(p).is_file())
        if c_bytes > 30720:
            sections = []
            for p in inject_c:
                text = Path(p).read_text(encoding="utf-8", errors="replace")
                cur_title, cur_buf = "", []
                for line in text.splitlines():
                    if line.startswith("## "):
                        if cur_buf:
                            sections.append((f"{cur_title}\n" + "\n".join(cur_buf)))
                        cur_title, cur_buf = line, []
                    else:
                        cur_buf.append(line)
                if cur_buf:
                    sections.append((f"{cur_title}\n" + "\n".join(cur_buf)))
            if len(sections) <= 3:
                four_c_shards = ["_".join("".join(filter(str.isalnum, s.splitlines()[0][3:])).split())[:20] or f"s{i+1}"
                                 for i, s in enumerate(sections)]
                # 段数≤3 直接按段分片
                shard_files = []
                for i, s in enumerate(sections):
                    sf = f"/tmp/cr_4c_shard_{repo_name}_{i+1}.md"
                    Path(sf).write_text(s, encoding="utf-8")
                    shard_files.append(sf)
                four_c_shards = shard_files
            else:
                # 段数>3：均分 3 片
                per = (len(sections) + 2) // 3
                shard_files = []
                for i in range(0, len(sections), per):
                    sf = f"/tmp/cr_4c_shard_{repo_name}_{i//per+1}.md"
                    Path(sf).write_text("\n".join(sections[i:i+per]), encoding="utf-8")
                    shard_files.append(sf)
                four_c_shards = shard_files
    if four_c_enabled:
        c_lane = {"agent": "4-C", "always": False, "enabled": True,
                 "inject": four_c_shards if four_c_shards else ([cu_input] if cu_input else []) + ([l2_input] if l2_input else []),
                 "sources": {"cu": bool(cu_input), "l2": bool(l2_input)}}
        if four_c_shards:
            # 分片时只声明 shard_outputs(单一真源);不设 output 单值字段,避免主 Agent 误把单文件当分片总输出写 step4c.json
            c_lane["shard_outputs"] = [f"/tmp/cr_issues_{repo_name}_step4c_{i+1}.json" for i in range(len(four_c_shards))]
        else:
            c_lane["output"] = f"/tmp/cr_issues_{repo_name}_step4c.json"
        others.append(c_lane)

    # ── 全档位硬上限：lite/standard 上限 6（+1 为 4-C），full 档 4-D 拆分后需要 7 ──
    # 顺序不变量：先定 4-D 是否拆分（影响其占槽 1/2），再算 4-C 槽位。
    # 否则 max_sub=6+full 场景：4-C 按「D 占 2 槽」误判跳过，随后 D 降级只占 1 槽 → 4-C 被错误跳过。
    skipped_lanes = []
    if tier == "full" and four_d_split and max_sub >= 7:
        MAX_STEP4 = 7
    else:
        MAX_STEP4 = min(max_sub, 6 if four_c_enabled else 5)
        if four_d_split and max_sub < 7:
            # 降级：4-D 不拆分，保持 full_scan 模式
            four_d_split = False
            others[0]["split"] = False
            others[0]["mode"] = "full_scan"
            others[0].pop("split_agents", None)  # 清除拆分子 Agent 列表
    d_slots = 2 if four_d_split else 1
    c_slots = 1 if four_c_enabled else 0
    if four_c_shards and len(four_c_shards) > 1:
        c_slots = min(len(four_c_shards), 3)
    # 如果 max_sub 不够，4-C 降级跳过（P0/4-D 优先级高于 L2/CU）
    while c_slots > 0 and len(four_a) + d_slots + c_slots > MAX_STEP4:
        c_slots -= 1
    # 分片被槽位压缩时同步裁剪 c_lane 声明（防 plan/实际 spawn 不一致）:
    # 例：3 分片压到 2 槽 → shard 3 从 inject/shard_outputs 移除,对应分片文件不再消费
    if four_c_shards and c_slots > 0 and c_slots < len(four_c_shards):
        dropped = four_c_shards[c_slots:]
        for o in others:
            if o["agent"] == "4-C":
                o["inject"] = four_c_shards[:c_slots]
                if "shard_outputs" in o:
                    o["shard_outputs"] = o["shard_outputs"][:c_slots]
        skipped_lanes = skipped_lanes or []
        skipped_lanes.append({"agent": "4-C-shards", "reason": "slot_exhausted",
                              "dropped": len(dropped), "files": dropped})
        four_c_shards = four_c_shards[:c_slots]
    if four_c_enabled and c_slots == 0:
        # 4-C 降级跳过：V117 后 4-D 不再携带自定义/L2规则(模板已删 CU 节,4-D core 不再嵌入)，
        # 槽位不足时 4-C 整路跳过，规则检查本轮跳过，降级事件显式记录，不假装携带、不阻断。
        skipped_lanes = skipped_lanes or []
        skipped_lanes.append({"agent": "4-C", "reason": "slot_exhausted",
                             "sources": {"cu": bool(cu_input), "l2": bool(l2_input)}})
        others = [o for o in others if o["agent"] != "4-C"]
        four_c_enabled = False
        four_c_shards = []
    b_slots = max(0, MAX_STEP4 - len(four_a) - d_slots - c_slots)
    if len(four_b) > b_slots:
        if b_slots > 0:
            four_b.sort(key=lambda x: (-len(x["rules"]), x["agent"]))
            kept = four_b[:b_slots]
            for extra in four_b[b_slots:]:
                target = min(kept, key=lambda x: len(x["rules"]))
                target["groups"] = target["groups"] + extra["groups"]
                target["rules"] = target["rules"] + extra["rules"]
                target["agent"] = "4-B-" + "_".join(target["groups"])
                target["output"] = "step4b_" + "_".join(target["groups"]) + ".json"
            four_b = kept
        else:
            # 存量边界修复：b_slots=0 且 4-B 非空时，老代码会 raise 断流。
            # 按 never-block 原则改为 4-B 整体跳过（4-A/4-D 覆盖），不阻断。
            # 跳过必须显式入 plan.skipped_lanes（与 4-C 同标准：可审计、不假装覆盖）
            skipped_lanes = skipped_lanes or []
            skipped_lanes.append({"agent": "4-B(all)", "reason": "slot_exhausted",
                                  "groups": [b["groups"] for b in four_b]})
            four_b = []
    total_sub = len(four_a) + len(four_b) + d_slots + c_slots
    if total_sub > MAX_STEP4:
        raise RuntimeError(f"route plan exceeds cap: total={total_sub}, cap={MAX_STEP4}")

    # 收集 4-B 裁剪统计
    four_b_stats = {}
    for b in four_b:
        if "inject" in b and "entries" in b:
            # entries = kept sections count; total = count of rule files that were trimmed
            four_b_stats[b["agent"]] = {"kept": b["entries"], "total": len(b["rules"]), "fallback": False, "inject": b["inject"]}

    plan = {
        "tier": tier, "tier_reason": "; ".join(why), "diff_lines": diff_lines,
        "rule_filter": "removed (signal-driven, V115 rebalanced)",
        "risk": {"score": risk_score, "detail": risk_detail, "high_signals": high_hits},
        "active_signals": sorted(active_sigs),
        "four_a": four_a, "four_b": four_b, "others": others,
        "skipped_lanes": skipped_lanes,
        "total_subagents": total_sub,
        "entry_stats": {r: {"kept": t["kept"], "total": t["total"], "fallback": t["fallback"]}
                        for r, t in trims.items() if r != "all"},
        "four_b_stats": four_b_stats,
        "limits": {"max_subagents": max_sub, "small_diff_lines": small_diff,
                   "full_diff_lines": full_diff, "risk_standard": risk_std_th, "risk_full": risk_full_th},
    }
    Path(args.output).write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    es = plan["entry_stats"]
    fb_s = " ".join(f"{k}={v['kept']}rules" for k, v in four_b_stats.items()) if four_b_stats else "none"
    d_label = f"4-D-core+4-D-logic" if four_d_split else "4-D"
    c_label = f" 4-C({'CU' if cu_dirs else ''}{'+' if cu_dirs and l2_input else ''}{'L2' if l2_input else ''}{f'×{c_slots}' if c_slots > 1 else ''})" if four_c_enabled else ""
    print(f"route_plan: tier={tier}({';'.join(why)}) diff={diff_lines}L risk={risk_score} "
          f"4-A×{len(four_a)} 4-B×{len(four_b)} {d_label}{c_label} total={total_sub}/{MAX_STEP4} "
          f"entries kept p0={es['p0']['kept']}/{es['p0']['total']} p1={es['p1']['kept']}/{es['p1']['total']} p3={es['p3']['kept']}/{es['p3']['total']} "
          f"4B=[{fb_s}]")


if __name__ == "__main__":
    main()
