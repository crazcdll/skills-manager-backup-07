#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI-CR 外部审查能力 Skill 对接 Loader（ext-analyzer，四合一）
================================================
对应 SOP: https://km.sankuai.com/collabpage/2787539320 《AI-CR 外部审查能力 Skill 对接 SOP》
主 skill(LLM 编排)与本脚本的分工:
  Step 0F  → `discover` : 枚举 ext-analyzer-* → 校验 frontmatter → 运行时注册表
                        (懒加载:未落盘的预装项记入 pendingLazyLoad,不依赖其存在)
  Step 4-E → `run`     : 组装 AnalysisContextManifest → exec 业务 skill 子进程
                        → 硬超时/存活熔断 → 落盘 AnalyzerResult
                        (由 LLM 用 exec background 调起,与 4-A/4-B/4-C/4-D 并行,不等待)
  收口点    → `collect`: 读结果 → findings 契约校验(ruleId前缀/锚定/lineType/定级边界)
                        → 灰度阶段 P0/P1 → confirm 降级标记 → 写 step4e.json
                        (Step 4-Merge 前一次性收口,晚到不回填,超时即废弃)
  验收     → `self-test`: 用 mock analyzer 跑全场景,输出验收报告

铁律(与 SOP 第一章边界一致):
  - 任何失败 = 空结果,exit 0,绝不阻塞主 CR 流程
  - 外部 analyzer 只能追加 findings,不能修改内置四路任何结论
  - 灰度阶段 EXT findings 归入 confirm 统计,不计入 P0-P3 指标(collect 强制降级标记,保留原级证据)
  - 主流程永不等待: collect 时未 READY 就废弃
  - 硬超时默认 1500s(25min,可配 60~1500s);存活兜底:窗口内全静默 → 提前 ~5s kill
  - 输出限制: stdout 只有 JSON(日志全走 stderr),总输出 ≤ 16k chars

设计上镜像 external_kb_loader.py 的成熟模式(注册表/原子写/失败计数/摘除冷却)。
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time

# ---------------- 常量 ----------------
PROTOCOL_VERSION = "1.0"
PREFIX = "ext-analyzer-"
MAX_INPUT_CHARS = 4000          # SOP 输入契约很小(5 字段)
MAX_OUTPUT_CHARS = 16000        # SOP: 总输出 ≤ 16k chars
HARD_TIMEOUT_DEFAULT = 1500     # 硬超时默认 1500s(25min,可配 60~1500s) 2026-10-29 问题反馈#4 上调
LIVENESS_POLL = 1.0
RESULT_READ_LIMIT = 2 * 1024 * 1024
FAIL_STRIKE_OUT = 3
STRIKE_COOLDOWN_MS = 3600 * 1000
REGISTRY_PATH = os.environ.get("EXTAN_REGISTRY_PATH", "/tmp/extan_registry.json")

FRONTMATTER_REQUIRED = ["protocol-version", "entry", "repo-matchers"]

# ---------------- 契约新增(2026-11-02, PR#293 事故修复) ----------------
# mode: script=纯脚本零LLM(可子进程直跑) | agent=语义核验需会话层LLM(必须 spawn 子代理)
#       未声明 = auto → run 启动前引擎预检决定(无引擎拒绝直跑并指引子代理模式)
# required: true=失败/缺失时发布门禁强制降级结论; 缺省 REQUIRED_DEFAULT(试点期渐进转正)
# 转正硬规则: EXTAN_PROMOTED 名单内 analyzer 强制 required=true(计数入结论 ⇒ 失败拦结论)
VALID_MODES = ("script", "agent")
REQUIRED_DEFAULT = os.environ.get("EXTAN_REQUIRED_DEFAULT", "0") == "1"
ENGINE_CLI_PROBES = ("claude", "codex")

VALID_SEVERITIES = ("P0", "P1", "P2", "P3", "confirm")
VALID_LINETYPES = ("ADDED", "REMOVED")  # SOP: 禁 MODIFIED

# SOP 边界: 灰度阶段 EXT findings 不计入问题统计(P0-P3) → collect 时统一归入 confirm(待人工确认,保留原级)
PILOT_DOWNGRADE = os.environ.get("EXTAN_PILOT_DOWNGRADE", "1") == "1"

# 转正名单(2026-10-29): 名单内 analyzer 按原级定级直接计入 P0-P3 统计与 Review 结论;
# 仍不进 Step 4-Review 二次复审(EXT 复审豁免不变)。名单外 analyzer 维持灰度降级 confirm。
# 原级直计后 _origSeverity 不再写入(severity 即原级);issue_io 对 step4e 的
# P0/P1 三字段(reach_analysis 等)豁免继续有效,门禁不受影响。
EXTAN_PROMOTED = {"arch-pr-verifier"}


def _now_ms():
    return int(time.time() * 1000)


def _die_noop(msg):
    """降级输出: 永远 exit 0,不阻塞主流程"""
    print(json.dumps({"status": "FAILED", "dropReasons": [msg], "findings": []},
                     ensure_ascii=False))
    return 0


# ---------------- frontmatter 解析(复用 ext-kb 的成熟实现) ----------------
def _strip_yaml_comment(v):
    in_s = in_d = False
    for i, ch in enumerate(v):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d:
            return v[:i].strip()
    return v.strip()


def _parse_inline_dict(v):
    out, depth, cur, key, in_str = {}, 0, [], None, False
    for ch in v:
        if in_str:
            if ch == "'":
                in_str = False
            else:
                cur.append(ch)
            continue
        if ch == "'":
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                if key is not None:
                    out[key] = "".join(cur).strip()
                return out
        elif ch == ":" and depth == 1 and key is None:
            key = "".join(cur).strip()
            cur = []
        elif ch == "," and depth == 1:
            if key is not None:
                out[key] = "".join(cur).strip()
            key, cur = None, []
        else:
            cur.append(ch)
    return out


def parse_frontmatter(skill_md_path):
    """解析 SKILL.md 的 YAML frontmatter,提取 cr-external-analyzer 契约块
    (轻量实现,不依赖外部 yaml 库;引号/数组解析与 external_kb_loader 一致)"""
    try:
        with open(skill_md_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(65536)
    except OSError:
        return None
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return None
    fm = {}
    in_blk = False
    for line in m.group(1).split("\n"):
        if re.match(r"^[A-Za-z0-9_-]+:", line):
            in_blk = line.startswith("cr-external-analyzer:")
            # 顶层 name/version 也采集(skillVersion 标注用)
            kv = re.match(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$", line)
            if kv and kv.group(1) in ("version", "name"):
                v = _strip_yaml_comment(kv.group(2) or "")
                fm["_top_" + kv.group(1)] = v.strip("'\"") if v else ""
            continue
        if in_blk:
            kv = re.match(r"^\s+([a-zA-Z0-9_-]+):\s*(.+?)\s*$", line)
            if kv:
                k, v = kv.group(1), _strip_yaml_comment(kv.group(2))
                if not v:
                    fm[k] = None
                elif v.startswith("[") and v.endswith("]"):
                    fm[k] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
                else:
                    fm[k] = v.strip("'\"")
    if not any(k in fm for k in ("protocol-version", "entry")):
        return None
    return fm


# ---------------- Step 0F: discover ----------------
def discover(args):
    """0F: 枚举 ext-analyzer-* → 校验契约块 → 写注册表 → 播报摘要(stdout JSON)"""
    _old_health = {}
    try:
        with open(REGISTRY_PATH) as _f:
            _old = json.load(_f)
        _old_health = {k: {"consecutiveFailures": v.get("consecutiveFailures", 0),
                            "lastFailureMs": v.get("lastFailureMs", 0)}
                       for k, v in _old.get("registry", {}).items() if isinstance(v, dict)}
    except Exception:
        pass
    try:
        if os.path.exists(REGISTRY_PATH):
            os.remove(REGISTRY_PATH)
    except OSError:
        pass

    candidates = {}
    # ① 目录扫描: $ai_skill_directory/ext-analyzer-* 与 $SKILL_DIR/ext-analyzer-*
    roots = []
    for env in ("AI_SKILL_DIRECTORY", "ai_skill_directory"):
        v = os.environ.get(env)
        if v and os.path.isdir(v):
            roots.append(v)
    if args.skill_dir and os.path.isdir(args.skill_dir):
        roots.append(args.skill_dir)
    for root in roots:
        for d in sorted(glob.glob(os.path.join(root, PREFIX + "*"))):
            if os.path.isdir(d):
                candidates[os.path.basename(d)] = d
    # ② mtskills list 兜底(未落盘的预装项 → 懒加载待重试名单)
    if shutil_which("mtskills"):
        try:
            out = subprocess.run(["mtskills", "list"], capture_output=True, timeout=5).stdout
            for name in re.findall(PREFIX + r"[A-Za-z0-9_-]+", out.decode("utf-8", "ignore")):
                candidates.setdefault(name, None)
        except Exception:
            pass

    registry = {}
    pending, rejected = [], []
    for name, path in candidates.items():
        if path is None:
            pending.append(name)
            continue
        fm = parse_frontmatter(os.path.join(path, "SKILL.md"))
        if not fm:
            rejected.append({"name": name, "reason": "no-cr-external-analyzer-frontmatter"})
            continue
        blk = fm
        miss = [k for k in FRONTMATTER_REQUIRED if not blk.get(k)]
        if miss:
            rejected.append({"name": name, "reason": "missing:" + ",".join(miss)})
            continue
        if str(blk.get("protocol-version")) != PROTOCOL_VERSION:
            rejected.append({"name": name, "reason": "protocol-version-incompatible:" + str(blk.get("protocol-version"))})
            continue
        entry = str(blk.get("entry"))
        if not os.path.isfile(os.path.join(path, entry)):
            rejected.append({"name": name, "reason": "entry-not-found:" + entry})
            continue
        # ---- mode 声明解析(script|agent);未声明留空=auto(run 预检时决定) ----
        mode = str(blk.get("mode") or "").strip().lower()
        if mode and mode not in VALID_MODES:
            rejected.append({"name": name, "reason": "mode-invalid:%s" % mode})
            continue
        required_raw = str(blk.get("required") or "").strip().lower()
        if required_raw and required_raw not in ("true", "false"):
            rejected.append({"name": name, "reason": "required-invalid:%s" % required_raw})
            continue
        analyzer_short = name[len(PREFIX):] if name.startswith(PREFIX) else name
        # 转正硬规则: 计入结论(EXTRAN_PROMOTED)⇒ 失败必须拦结论,required 以名单优先
        required = True if analyzer_short in EXTAN_PROMOTED \
            else (required_raw == "true") if required_raw else REQUIRED_DEFAULT
        matchers = blk.get("repo-matchers")
        if isinstance(matchers, str):
            matchers = [matchers]
        registry[name] = {
            "path": path,
            "protocolVersion": str(blk.get("protocol-version")),
            "entry": entry,
            "mode": mode,
            "required": required,
            "repoMatchers": matchers or [],
            "timeoutSeconds": _safe_int(blk.get("timeout-seconds", HARD_TIMEOUT_DEFAULT), HARD_TIMEOUT_DEFAULT, 60, 1500),
            "skillVersion": str(fm.get("_top_version") or "") or str(blk.get("skill-version") or ""),
            "discoveredAt": _now_ms(),
        }
    for name, item in registry.items():
        if name in _old_health:
            item["consecutiveFailures"] = _old_health[name]["consecutiveFailures"]
            if _old_health[name]["lastFailureMs"]:
                item["lastFailureMs"] = _old_health[name]["lastFailureMs"]
    disabled = []
    for name in list(registry.keys()):
        if name in (args.disabled or []):
            disabled.append(name)
            del registry[name]
    payload = {"protocolVersion": PROTOCOL_VERSION, "generatedAt": _now_ms(),
               "registry": registry, "pendingLazyLoad": pending,
               "rejected": rejected, "disabled": disabled}
    _atomic_write_json(REGISTRY_PATH, payload)
    print(json.dumps({"status": "OK", "discovered": len(registry), "registry": sorted(registry.keys()),
                      "modes": {n: (i.get("mode") or "auto") for n, i in registry.items()},
                      "requiredAnalyzers": [n for n, i in registry.items() if i.get("required")],
                      "pendingLazyLoad": pending, "rejected": rejected, "disabled": disabled,
                      "registryPath": REGISTRY_PATH}, ensure_ascii=False, indent=2))
    return 0


def shutil_which(cmd):
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.isfile(os.path.join(p, cmd)):
            return True
    return False


def _engine_available():
    """引擎预检: 子进程可见的 tool-capable LLM 引擎探测。
    EXT_ARCH_ENGINE_CMD 环境变量 > claude CLI > codex CLI(与 analyzer 侧探测一致)。"""
    if os.environ.get("EXT_ARCH_ENGINE_CMD"):
        return True
    return any(shutil_which(c) for c in ENGINE_CLI_PROBES)


def _resolve_mode(item):
    """mode 三级解析: 显式声明 > 引擎预检默认 > auto。
    返回 (mode, precheck)。precheck 非 None 时表示由预检决定(auto 存量)。"""
    m = (item.get("mode") or "").strip().lower()
    if m in VALID_MODES:
        return m, None
    # auto(存量未声明): 预检决定——无引擎则按 agent 路由,子进程直跑必失败
    return ("agent", "no-engine") if not _engine_available() else ("script", "engine-present")


def _safe_int(v, default, lo, hi):
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        n = default
    return min(hi, max(lo, n))


def repo_match(matchers, repo):
    for pat in matchers:
        pat = pat.strip()
        if not pat:
            continue
        if re.fullmatch(pat.replace(".", r"\.").replace("*", ".*").replace("**", ".*"), repo):
            return True
        if fnmatch_simple(pat, repo):
            return True
    return False


def fnmatch_simple(pat, s):
    if pat == s:
        return True
    if "*" not in pat and "?" not in pat:
        return False
    rx = re.escape(pat).replace(r"\*", "[^/]*").replace(r"\?", ".")
    return re.match("^" + rx + "$", s) is not None


def pick_providers(registry, repo):
    """SOP 允许多个 analyzer 同时挂载: 返回全部 repo 匹配的(按 priority/name 排序)"""
    matched = [(n, i) for n, i in registry.items() if repo_match(i.get("repoMatchers") or [], repo)]
    matched.sort(key=lambda x: x[0])
    return [n for n, _ in matched]


# ---------------- Step 4-E: run ----------------
def _fail_run(out_path, provider, msg):
    payload = {"status": "FAILED", "queryId": None, "provider": provider,
               "elapsedMs": 0, "findings": [], "dropReasons": [msg]}
    if out_path:
        try:
            with open(out_path, "w") as f:
                json.dump(payload, f, ensure_ascii=False)
        except OSError:
            pass
        _unlink_stale(out_path + ".raw")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _fail_run_mode_guard(out_path, provider, why):
    """mode=agent 的 analyzer 被子进程直跑 → 受控拒绝 + 指引子代理模式。
    不计入失败计数(这不是 analyzer 的错,是路由误用);失败原因与修复指引完整落盘,
    供 collect 透传到发布门禁(不再静默蒸发)。"""
    msg = ("mode-guard:%s; fix: spawn subagent-ext-%s 子代理执行(会话层 LLM 在场), "
           "或 agent-bridge 三步法: main.py --emit-prompt 出任务书 → 子代理核验 → main.py --wrap 封装; "
           "script 直跑仅适用于纯脚本型 analyzer(当前环境子进程内无 tool-capable LLM 引擎)" % (
               why, provider[len(PREFIX):] if provider and provider.startswith(PREFIX) else (provider or "unknown")))
    return _fail_run(out_path, provider, msg)


def _record_failure(provider, reason):
    """连续 3 次失败自动摘除,冷却 1h 后恢复探测"""
    try:
        lock = _registry_lock()
    except Exception:
        lock = None
    try:
        full = json.load(open(REGISTRY_PATH))
        reg = full.get("registry", {})
        item = reg.get(provider)
        if item is not None:
            item["consecutiveFailures"] = int(item.get("consecutiveFailures", 0)) + 1
            item["lastFailureMs"] = _now_ms()
            full["registry"] = reg
            _save_registry_full(full)
    except Exception:
        pass
    finally:
        if lock is not None:
            try:
                lock.close()
            except OSError:
                pass


def _clear_failures(provider):
    try:
        lock = _registry_lock()
    except Exception:
        lock = None
    try:
        full = json.load(open(REGISTRY_PATH))
        reg = full.get("registry", {})
        item = reg.get(provider)
        if item is not None:
            item["consecutiveFailures"] = 0
            item["lastFailureMs"] = 0
            full["registry"] = reg
            _save_registry_full(full)
    except Exception:
        pass
    finally:
        if lock is not None:
            try:
                lock.close()
            except OSError:
                pass


def _striken_out(provider):
    try:
        reg = json.load(open(REGISTRY_PATH))["registry"]
        item = reg.get(provider)
        if item is None:
            return False
        if item.get("consecutiveFailures", 0) < FAIL_STRIKE_OUT:
            return False
        if _now_ms() - item.get("lastFailureMs", 0) > STRIKE_COOLDOWN_MS:
            return False  # 冷却期已过,可试探
        return True
    except Exception:
        return False


def _coerce_manifest(manifest):
    """manifest 字段类型宽容归一（问题反馈 #2/#3 根治）。

    LLM 手拼 JSON 偶发类型漂移（prId 写成数字是真实发生过的拦截案例），
    这里在严格校验前做归一化：数字/布尔 → str。归一化原地发生并返回
    是否发生修正，供调用方记录。changedFiles 为列表字段不做 str 归一。
    """
    fixed = []
    for fld in ("queryId", "repo", "prId", "targetCommit", "title"):
        v = manifest.get(fld)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            manifest[fld] = str(int(v)) if isinstance(v, int) else str(v)
            fixed.append(fld)
        elif isinstance(v, bool):
            manifest[fld] = str(v).lower()
            fixed.append(fld)
    return fixed


def build_manifest(args):
    """4-E-1: 命令行代拼 manifest（防 LLM 手拼类型漂移）。

    主 Agent 只传命令行参数，由本函数构造 JSON
    契约合规的 manifest 并落盘，从源头消除类型漂移（确定性修复）。
    """
    files = [f for f in (args.files or []) if f]
    if isinstance(args.files_file, str) and args.files_file:
        try:
            with open(args.files_file, encoding="utf-8") as fh:
                ff = json.load(fh)
            if isinstance(ff, list):
                files = [str(x) for x in ff if x]
        except Exception:
            pass  # 文件不可读时保留 --files 传入值
    manifest = {
        "queryId": args.query_id or ("%s/%s#%s@%s" % (
            args.org, args.repo, args.pr_id, (args.target_commit or "")[:8])
            if args.org else "%s#%s@%s" % (
                args.repo, args.pr_id, (args.target_commit or "")[:8])),
        "repo": "%s/%s" % (args.org, args.repo) if args.org else args.repo,
        "prId": str(args.pr_id),
        "targetCommit": args.target_commit,
        "title": args.title,
        "changedFiles": files,
    }
    if args.base_commit:
        # 权威基线透传(对外统一为"PR 审查区间左端点",不暴露内部全量/增量模式);
        # 消除 4-E diff 永远自证基线的问题(reviewRangeVerified:false 根因)
        manifest["baseCommit"] = args.base_commit
    out = args.output or "/tmp/cr_extan_input_%s_%s.json" % (
        args.pr_id, args.analyzer)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(json.dumps({"ok": True, "output": out,
                      "prIdType": type(manifest["prId"]).__name__}))
    return 0


def run(args):
    """4-E: 校验 manifest → spawn analyzer → 超时/熔断 → 落盘 AnalyzerResult"""
    try:
        manifest = json.load(open(args.input, encoding="utf-8"))
    except Exception as e:
        return _fail_run(args.output, None, "manifest-invalid:%s" % type(e).__name__)
    if not isinstance(manifest, dict):
        return _fail_run(args.output, None, "manifest-not-object")
    # 类型宽容：LLM 手拼 manifest 的数字 prId 等在此归一（不拦截，记录修正）
    _coerce_manifest(manifest)
    raw = json.dumps(manifest, ensure_ascii=False)
    if len(raw) > MAX_INPUT_CHARS * 2:  # 输入契约极小,宽裕上限
        return _fail_run(args.output, None, "input-over-budget:%d" % len(raw))
    for fld in ("queryId", "repo", "prId", "targetCommit", "title"):
        if not isinstance(manifest.get(fld), str) or not manifest.get(fld):
            return _fail_run(args.output, None, "manifest-missing-field:%s" % fld)
    try:
        reg = json.load(open(REGISTRY_PATH))["registry"]
    except Exception:
        return _fail_run(args.output, None, "registry-missing")

    providers = pick_providers(reg, manifest.get("repo", ""))
    if args.provider:
        providers = [p for p in providers if p == args.provider]
    if not providers:
        return _fail_run(args.output, None, "no-matching-provider")

    # 多 analyzer 时逐个串行执行(单次调用只处理一个;主 Agent 可并行发多个 run)
    provider = providers[0] if len(providers) == 1 else (args.provider or providers[0])
    if len(providers) > 1 and not args.provider:
        # 未指定且多个匹配: 提示由主 Agent 分别调 run --provider(全部都要跑)
        return _fail_run(args.output, None, "multiple-providers:%s" % ",".join(providers))
    if _striken_out(provider):
        # 摘除冷却期同样落 FAILED AnalyzerResult(dropReasons=provider-striken-out),
        # collect 后进 checks;required=true 时由 Step 7 门禁拦结论,不再静默空结果
        return _fail_run(args.output, provider, "provider-striken-out")

    item = reg[provider]
    # ---- mode 守卫: 需会话层 LLM 的 analyzer 禁止子进程直跑 ----
    resolved_mode, precheck = _resolve_mode(item)
    if resolved_mode == "agent":
        why = "mode:agent(explicit)" if precheck is None else "mode:auto→agent(engine-precheck:%s)" % precheck
        return _fail_run_mode_guard(args.output, provider, why)
    skill_path = item["path"]
    entry = os.path.join(skill_path, item["entry"])
    out_path = args.output or ("/tmp/cr_extan_result_%s_%s.json" % (manifest.get("prId", "x"), provider))
    err_path = out_path + ".err.log"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    except OSError:
        pass

    timeout = args.timeout or item["timeoutSeconds"]
    t0 = time.time()
    raw_path = out_path + ".raw"
    try:
        with open(args.input, "rb") as fin, open(raw_path, "wb") as fout, open(err_path, "wb") as ferr:
            proc = subprocess.Popen([sys.executable, entry], stdin=fin, stdout=fout, stderr=ferr)
            # 存活兜底(SOP 第4条): 硬超时窗口内持续静默 → 提前 ~5s kill
            liveness_deadline = time.time() + max(5, timeout - 5)
            while time.time() < liveness_deadline and proc.poll() is None:
                time.sleep(LIVENESS_POLL)
                if os.path.getsize(err_path) > 0 or os.path.getsize(raw_path) > 0:
                    break
            if proc.poll() is None and time.time() >= liveness_deadline \
                    and os.path.getsize(err_path) == 0 and os.path.getsize(raw_path) == 0:
                proc.kill()
                _record_failure(provider, "liveness-blowout")
                return _fail_run(out_path, provider, "liveness-blowout:silent-until-%ds" % int(liveness_deadline - t0))
            rc = proc.wait(timeout=max(1, timeout - (time.time() - t0)))
    except subprocess.TimeoutExpired:
        proc.kill()
        _record_failure(provider, "hard-timeout")
        return _fail_run(out_path, provider, "hard-timeout:%ds" % timeout)
    except FileNotFoundError:
        _record_failure(provider, "entry-missing")
        return _fail_run(out_path, provider, "entry-missing")
    elapsed = int((time.time() - t0) * 1000)
    if rc != 0:
        _record_failure(provider, "nonzero-exit:%d" % rc)
        return _fail_run(out_path, provider, "nonzero-exit:%d" % rc)

    # 读取 stdout(≤2MB + 16k chars 契约校验)
    try:
        if os.path.getsize(raw_path) > RESULT_READ_LIMIT:
            _record_failure(provider, "output-over-2mb")
            return _fail_run(out_path, provider, "output-over-read-limit")
        out_text = open(raw_path, encoding="utf-8", errors="replace").read()
        if len(out_text) > MAX_OUTPUT_CHARS:
            _record_failure(provider, "output-over-budget")
            return _fail_run(out_path, provider, "output-over-budget:%dc>%dc" % (len(out_text), MAX_OUTPUT_CHARS))
        result = json.loads(out_text)
    except json.JSONDecodeError as e:
        _record_failure(provider, "stdout-not-json")
        return _fail_run(out_path, provider, "stdout-not-json:%s" % type(e).__name__)
    except OSError as e:
        _record_failure(provider, "output-read-error")
        return _fail_run(out_path, provider, "output-read-error:%s" % type(e).__name__)
    if not isinstance(result, dict):
        _record_failure(provider, "stdout-not-object:%s" % type(result).__name__)
        return _fail_run(out_path, provider, "stdout-not-object:%s" % type(result).__name__)
    qid, mq = result.get("queryId"), manifest.get("queryId")
    if qid and mq and qid != mq:
        _record_failure(provider, "query-id-mismatch")
        return _fail_run(out_path, provider, "query-id-mismatch")
    result.setdefault("queryId", mq)
    result.setdefault("provider", provider)
    result.setdefault("elapsedMs", elapsed)
    result.setdefault("findings", [])
    if result.get("status") not in ("READY", "EMPTY", "FAILED", "REJECTED"):
        result["status"] = "FAILED"
        result.setdefault("dropReasons", []).append("status-invalid")
    if result.get("status") in ("FAILED", "REJECTED"):
        _record_failure(provider, "controlled-failure:%s" % result.get("status"))
    # 附带 changedFiles 锚定校验面(collect 用)
    result["_manifest"] = {
        "repo": manifest.get("repo", ""),
        "prId": manifest.get("prId", ""),
        "targetCommit": manifest.get("targetCommit", ""),
        "changedFiles": [f if isinstance(f, str) else str(f.get("path", "")) for f in (manifest.get("changedFiles") or [])],
    }
    _write_result_atomic(out_path, result)
    if result.get("status") in ("READY", "EMPTY"):
        _clear_failures(provider)
    print(json.dumps({"status": "INVOKED", "provider": provider, "elapsedMs": elapsed,
                      "resultPath": out_path}, ensure_ascii=False))
    return 0


def _unlink_stale(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _write_result_atomic(out_path, result):
    tmp = out_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(result, f, ensure_ascii=False)
    os.replace(tmp, out_path)


def _write_empty(path):
    """失败时写空数组(不删文件): 4-Merge-0 门禁要求 step4e.json 存在;
    若已有合法合并内容则保留不覆盖(单 analyzer 失败不能吞掉其他 analyzer 的结果)"""
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if os.path.exists(path):
            try:
                prev = json.load(open(path, encoding="utf-8"))
                if isinstance(prev, list) and prev:
                    return  # 已有合法内容,保留
            except Exception:
                pass  # 旧文件损坏 → 覆盖为空数组
        with open(path, "w") as f:
            json.dump([], f, ensure_ascii=False)
    except OSError:
        pass


# ---------------- step4e 状态封装体 ----------------
# step4e.json 为 {status, error, findings, checks, ...} 封装体。
# findings=[] 无法区分「检查了没问题」与「没跑成」; 状态必须贯穿到发布门禁,
# 禁止 FAILED 被空数组吞掉。findings 内部仍是 issue 数组。
STATUS_ENUM = ("READY", "FAILED", "UNKNOWN", "TIMEOUT")


def _any_required(checks):
    """checks 中任一 required=true 即整体 required(门禁仍逐条判定,此处为顶层概览)。"""
    for c in checks or []:
        if isinstance(c, dict) and c.get("required"):
            return True
    return False


def _write_status_envelope(path, status, error, findings, checks, required=None,
                           run_id="", target_commit=""):
    """落盘带状态的封装体(字段集: status/error/runId/targetCommit/required/findings/checks)。
    已有封装体时合并 checks(多 analyzer 逐个 collect 共写一文件);
    顶层 runId/targetCommit/required 保留最新非空值(新一轮 CR 覆盖旧值)。"""
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    except OSError:
        pass
    prev_checks = []
    prev_findings = []
    prev_status = None
    if os.path.exists(path):
        try:
            prev = json.load(open(path, encoding="utf-8"))
            if isinstance(prev, dict):
                prev_checks = list(prev.get("checks") or [])
                prev_findings = list(prev.get("findings") or [])
                prev_status = prev.get("status")
                run_id = run_id or str(prev.get("runId") or "")
                target_commit = target_commit or str(prev.get("targetCommit") or "")
            elif isinstance(prev, list):
                prev_findings = prev  # 旧格式迁移
        except Exception:
            pass  # 损坏 → 重建
    if checks:
        # 同 analyzer 重 collect 时替换旧条目
        keyed = {c.get("analyzer"): c for c in prev_checks if isinstance(c, dict)}
        for c in checks:
            keyed[c.get("analyzer")] = c
        prev_checks = list(keyed.values())
    merged_findings = prev_findings + [f for f in (findings or [])]
    # 总状态: 任一 REQUIRED 检查非 READY → 整体非 READY(门禁以 checks 逐条判定,此处仅展示用)
    overall = status
    if prev_status not in (None, "READY") and status == "READY":
        overall = prev_status
    envelope = {
        "schema": "step4e-envelope/v1",
        "status": overall,
        "error": error or "",
        "runId": run_id,
        "targetCommit": target_commit,
        "required": required if required is not None else _any_required(prev_checks),
        "findings": merged_findings,
        "checks": prev_checks,
    }
    with open(path, "w", encoding="utf-8") as fo:
        json.dump(envelope, fo, ensure_ascii=False, allow_nan=False)


def _load_registry_meta(provider):
    """从注册表读 analyzer 的 mode/required/skillVersion(collect 时无注册表也不阻塞)。
    EXTAN_PROMOTED 硬规则优先——arch-pr-verifier 等已转正 analyzer 无论注册表
    是否可读,required 恒为 True(注册表缺失兜底 required=False 会造成门禁 fail-open)。"""
    try:
        reg = json.load(open(REGISTRY_PATH, encoding="utf-8")).get("registry") or {}
        item = reg.get(provider) or {}
        required = bool(item.get("required"))
    except Exception:
        item, required = {}, False
    short = provider[len(PREFIX):] if provider.startswith(PREFIX) else provider
    if short in EXTAN_PROMOTED:
        required = True
    return {
        "mode": item.get("mode") or "auto",
        "required": required,
        "skillVersion": item.get("skillVersion") or "",
    }


def _registry_lock():
    import fcntl
    fd = open(REGISTRY_PATH + ".lock", "w")
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _atomic_write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def _save_registry_full(full):
    _atomic_write_json(REGISTRY_PATH, full)


# ---------------- 收口点: collect ----------------
REQUIRED_FINDING_FIELDS = ("severity", "ruleId", "anomalyType", "summary",
                           "file", "line", "lineType", "description",
                           "risk", "suggestion", "source")


def _validate_findings(raw_findings, provider, changed, drop):
    """逐条校验 findings(SOP 契约): 返回 (kept, downgraded)

    - ruleId 必须 EXT:{analyzer名}:{规则号} 开头,前缀不匹配 → 整条丢弃
    - file 必须在 changedFiles 内(锚定校验),不在 → 整条丢弃
    - lineType 只能 ADDED/REMOVED,禁 MODIFIED → 整条丢弃
    - severity 只能 P0/P1/P2/P3/confirm
    - source 固定 step4e
    - 试点阶段: P0/P1 → severity 改 P2,原级记入 description 尾注(不计入指标)
    """
    analyzer_name = provider[len(PREFIX):] if provider.startswith(PREFIX) else provider
    expected_prefix = "EXT:%s:" % analyzer_name
    kept, downgraded = [], 0
    for f in raw_findings:
        if not isinstance(f, dict):
            drop.append("finding-not-object")
            continue
        miss = [k for k in REQUIRED_FINDING_FIELDS if k not in f or f[k] in (None, "")]
        if miss:
            drop.append("finding-missing-field:%s" % ",".join(miss))
            continue
        rid = str(f.get("ruleId", "")).strip()
        if not rid.startswith(expected_prefix):
            drop.append("ruleId-prefix-mismatch:%s" % rid)
            continue
        sev = str(f.get("severity", "")).strip().upper()
        if sev not in VALID_SEVERITIES:
            drop.append("severity-invalid:%s" % f.get("severity"))
            continue
        lt = str(f.get("lineType", "")).strip().upper()
        if lt not in VALID_LINETYPES:
            drop.append("lineType-invalid:%s" % f.get("lineType"))
            continue
        try:
            line = int(f.get("line"))
            if line < 1:
                raise ValueError
        except (TypeError, ValueError):
            drop.append("line-invalid:%s" % f.get("line"))
            continue
        fpath = str(f.get("file", ""))
        if changed and fpath not in changed:
            drop.append("file-not-in-changedFiles:%s" % fpath)
            continue
        # 安全校验: 过滤指令性内容(SOP 边界: 不能修改内置结论 → 防注入)
        blob = json.dumps(f, ensure_ascii=False)
        if re.search(r"(忽略(以上|之前)|ignore previous|rm -rf|<script|"
                     r"删除(以上|全部)|必须(驳回|关闭)此?PR)", blob, re.I):
            drop.append("injection-suspect")
            continue
        f = dict(f)
        f["severity"] = sev
        f["lineType"] = lt
        f["line"] = line
        f["source"] = "step4e"
        f.setdefault("ruleName", "")
        f.setdefault("ruleFile", "")
        # 来源 skill 版本标注(展示用): 从注册表读取,读不到不阻塞
        try:
            _reg = json.load(open(REGISTRY_PATH, encoding="utf-8")).get("registry") or {}
            _sv = (_reg.get(provider) or {}).get("skillVersion") or ""
            if _sv:
                f.setdefault("_analyzerSkillVersion", _sv)
        except Exception:
            pass
        # 灰度边界: EXT findings 不作为问题定级 → 归入 confirm(待人工确认)统计;
        # 不只 P0/P1:P2/P3 同样是未经主流程复审的外部发现,一并归 confirm,
        # 原级记尾注+_origSeverity 供人工判定参考
        # confirm 是 SEVERITY_ORDER 最低级(4),与内置同根因合并取高时
        # 结构性不可能抬高内置结论(EXT 只能追加铁律)
        # 转正名单(2026-10-29): arch-pr-verifier 按原级定级计入,
        # 不降 confirm、不进 4-Review 二次复审(仍豁免)。
        if PILOT_DOWNGRADE and sev in ("P0", "P1", "P2", "P3") \
                and analyzer_name not in EXTAN_PROMOTED:
            if "_origSeverity" not in f:
                f["_origSeverity"] = sev
            f["description"] = "%s\n\n[外部审查能力灰度] 原 %s 级,灰度阶段不计入问题统计,归入待确认(confirm)待人工判定。" % (
                f.get("description", ""), sev)
            f["severity"] = "confirm"
            downgraded += 1
        kept.append(f)
    return kept, downgraded


def collect(args):
    """Step 4-Merge 前收口: 校验 findings 契约 → 灰度降级(confirm) → 写 step4e.json

    (2026-11-02, PR#293 事故修复): 输出从裸数组改为状态封装体。
    核心变化: FAILED/TIMEOUT/UNKNOWN 不再被 [] 吞掉——失败原因、dropReasons、
    required/mode 元数据全部进 checks 数组,供发布门禁逐条判定。
    "findings=[] + status!=READY" = 审查未完成,不得等同零发现。

    两种模式:
    A. subagent 模式(主推): --analyzer {名} --findings {子Agent返回的原始数组文件}
       [--manifest {manifest 文件,供锚定校验+产物身份}]
    B. SOP headless 模式(兼容): --result {run 产出的 AnalyzerResult 文件}

    校验规则(全部来自 SOP):
    - ruleId 必须 EXT:{analyzer名}:{规则号} 开头,前缀不匹配 → 整条丢弃
    - file 必须在 changedFiles 内(锚定校验),不在 → 整条丢弃
    - lineType 只能 ADDED/REMOVED,禁 MODIFIED → 整条丢弃
    - severity 只能 P0/P1/P2/P3/confirm
    - source 固定 step4e
    - 试点阶段: P0/P1 → severity 改 P2,原级记入 description 尾注(不计入指标)
    """
    if getattr(args, "status", None):
        # ---- 显式失败收割(4-E-2 超时/异常路径) ----
        # 超时≠空结果:TIMEOUT/FAILED/UNKNOWN 落封装体进 checks,required=true 时拦结论。
        # 严禁主 Agent 不调 collect 静默丢弃——那会让门禁读到旧 PR 残留或无 check,PR#293 重演。
        st = str(args.status).strip().upper()
        if st not in STATUS_ENUM:
            st = "UNKNOWN"
        if st == "READY":
            return _die_noop("collect --status 仅用于失败收割,READY 请走 --findings/--result 正常路径")
        provider = str(args.analyzer or "unknown")
        if not provider.startswith(PREFIX):
            provider = PREFIX + provider
        manifest_data = {}
        if getattr(args, "manifest", None):
            try:
                manifest_data = json.load(open(args.manifest, encoding="utf-8"))
            except Exception:
                manifest_data = {}
        check = _build_check(provider, st, str(args.error or "explicit-failure-collect"),
                             manifest_data, 0, 0, 0, ["explicit-%s" % st.lower()])
        _write_status_envelope(args.output, st, str(args.error or ""), [], [check],
                               run_id=str(manifest_data.get("queryId") or ""),
                               target_commit=str(manifest_data.get("targetCommit") or ""))
        # 归因说明: 不计 _record_failure——显式收割的失败源自编排层(子Agent超时/异常),
        # 非 analyzer 本体连续故障,计入会误触发"连续3次失败自动摘除冷却1h"
        print(json.dumps({"status": "COLLECTED", "provider": provider, "checkStatus": st,
                          "findingsKept": 0, "envelopeStatus": st,
                          "note": "explicit failure collected; gate will judge by required"}))
        return 0
    if getattr(args, "findings", None):
        # ---- A. subagent 模式: 校验子 Agent 直接返回的 findings ----
        provider = str(args.analyzer or "unknown")
        if not provider.startswith(PREFIX):
            provider = PREFIX + provider
        manifest_data = {}
        if getattr(args, "manifest", None):
            try:
                manifest_data = json.load(open(args.manifest, encoding="utf-8"))
            except Exception:
                manifest_data = {}
        try:
            raw_findings = json.load(open(args.findings, encoding="utf-8"))
        except Exception:
            _write_status_envelope(args.output, "UNKNOWN", "subagent-findings-unreadable", [], None,
                                   run_id=str(manifest_data.get("queryId") or ""),
                                   target_commit=str(manifest_data.get("targetCommit") or ""))
            _record_failure(provider, "subagent-findings-unreadable")
            return _die_noop("findings-unreadable")
        if not isinstance(raw_findings, list):
            _write_status_envelope(args.output, "UNKNOWN", "subagent-findings-not-list:%s" % type(raw_findings).__name__, [], None,
                                   run_id=str(manifest_data.get("queryId") or ""),
                                   target_commit=str(manifest_data.get("targetCommit") or ""))
            _record_failure(provider, "subagent-findings-not-list")
            return _die_noop("findings-not-list:%s" % type(raw_findings).__name__)
        changed = set(manifest_data.get("changedFiles") or [])
        drop = []
        kept, downgraded = _validate_findings(raw_findings, provider, changed, drop)
        check = _build_check(provider, "READY", "", manifest_data,
                             len(kept), len(raw_findings), downgraded, drop)
        _write_status_envelope(args.output, "READY", "", kept, [check],
                               run_id=str(manifest_data.get("queryId") or ""),
                               target_commit=str(manifest_data.get("targetCommit") or ""))
        print(json.dumps({"status": "COLLECTED", "provider": provider,
                          "checkStatus": "READY",
                          "findingsKept": len(kept), "findingsTotal": len(raw_findings),
                          "downgraded": downgraded, "dropReasons": drop,
                          "output": args.output}, ensure_ascii=False))
        return 0
    else:
        # ---- B. SOP headless 模式: 校验 run 产出的 AnalyzerResult ----
        try:
            result = json.load(open(args.result, encoding="utf-8"))
        except Exception:
            # 结果文件不存在/损坏 → UNKNOWN(不是零发现,防删除产物绕门禁)
            _write_status_envelope(args.output, "UNKNOWN", "result-unreadable", [], None)
            return _die_noop("result-unreadable")
        if not isinstance(result, dict):
            _write_status_envelope(args.output, "UNKNOWN", "result-not-object:%s" % type(result).__name__, [], None)
            return _die_noop("result-not-object")
        provider = result.get("provider") or "unknown"
        manifest = result.get("_manifest") or {}
        result_status = str(result.get("status") or "")
        # 状态机: READY/EMPTY=完成;FAILED/REJECTED=受控失败;
        # 超时类→TIMEOUT;其余(含 status-invalid 历史遗留)一律 UNKNOWN
        drop = list(result.get("dropReasons") or [])
        drop_blob = json.dumps(drop, ensure_ascii=False)
        if result_status in ("READY", "EMPTY"):
            changed = set(manifest.get("changedFiles") or [])
            raw_findings = result.get("findings")
            if not isinstance(raw_findings, list):
                check = _build_check(provider, "UNKNOWN", "findings-not-list:%s" % type(raw_findings).__name__,
                                     manifest, 0, 0, 0, drop)
                _write_status_envelope(args.output, "UNKNOWN", "findings-not-list", [], [check])
                return _die_noop("findings-not-list:%s" % type(raw_findings).__name__)
            kept, downgraded = _validate_findings(raw_findings, provider, changed, drop)
            check = _build_check(provider, "READY", "", manifest,
                                 len(kept), len(raw_findings), downgraded, drop)
            _write_status_envelope(args.output, "READY", "", kept, [check])
            if result_status == "READY":
                _clear_failures(provider)
            print(json.dumps({"status": "COLLECTED", "provider": provider,
                              "checkStatus": "READY",
                              "findingsKept": len(kept), "findingsTotal": len(raw_findings),
                              "downgraded": downgraded, "dropReasons": drop,
                              "output": args.output}, ensure_ascii=False))
            return 0
        # ---- 失败/TIMEOUT/非法状态: 原样透传,不再吞成空数组 ----
        if result_status == "TIMEOUT" or "timeout" in drop_blob.lower() or "hard-timeout" in drop_blob:
            check_status = "TIMEOUT"
        elif result_status in ("FAILED", "REJECTED"):
            check_status = "FAILED"
        else:
            check_status = "UNKNOWN"
        error_msg = str(result.get("message") or result.get("error") or
                        "; ".join(str(x) for x in drop) or
                        "status-%s" % result_status)
        _record_failure(provider, "%s:%s" % (check_status.lower(), result_status))
        check = _build_check(provider, check_status, error_msg, manifest,
                             0, 0, 0, drop)
        _write_status_envelope(args.output, check_status, error_msg, [], [check])
        print(json.dumps({"status": "COLLECTED-DEGRADED", "provider": provider,
                          "checkStatus": check_status, "error": error_msg,
                          "findingsKept": 0, "findingsTotal": 0,
                          "dropReasons": drop,
                          "output": args.output}, ensure_ascii=False))
        return 0


def _build_check(provider, status, error, manifest, kept, total, downgraded, drop):
    """构造单个 analyzer 的 check 条目(身份+状态+计数,发布门禁的判定单元)。"""
    meta = _load_registry_meta(provider)
    if not isinstance(manifest, dict):
        manifest = {}
    return {
        "analyzer": provider,
        "status": status,
        "error": error or "",
        "required": meta["required"],
        "mode": meta["mode"],
        "skillVersion": meta["skillVersion"],
        "runId": manifest.get("queryId", ""),
        "targetCommit": manifest.get("targetCommit", ""),
        "findingsKept": kept,
        "findingsTotal": total,
        "downgraded": downgraded,
        "dropReasons": list(drop or []),
        "collectedAt": _now_ms(),
    }


# ---------------- 验收: self-test ----------------
def self_test(args):
    """用 mock analyzer 跑全场景,输出验收报告(不依赖任何外部 skill)"""
    tmp = "/tmp/extan_selftest"
    os.makedirs(tmp, exist_ok=True)
    os.environ["EXTAN_REGISTRY_PATH"] = os.path.join(tmp, "registry.json")
    os.environ["EXTAN_PILOT_DOWNGRADE"] = "1"
    for stale in ("result.json", "step4e.json", "input.json", "registry.json"):
        _unlink_stale(os.path.join(tmp, stale))
    mock_dir = os.path.join(tmp, PREFIX + "mock")
    os.makedirs(mock_dir, exist_ok=True)
    with open(os.path.join(mock_dir, "SKILL.md"), "w") as f:
        f.write("---\nname: ext-analyzer-mock\ndescription: self-test mock\n"
                "cr-external-analyzer:\n  protocol-version: \"1.0\"\n  entry: main.py\n"
                "  mode: script\n"
                "  repo-matchers: [\"org/mock-repo\"]\n"
                "  timeout-seconds: 10\n---\n")
    scenario = args.scenario or "normal"
    # 新增场景: mode-agent = frontmatter 声明 mode:agent,run 应受控拒绝(不执行子进程)
    behaviors = {
        "normal": """import sys,json
m=json.load(sys.stdin)
print(json.dumps({"status":"READY","queryId":m["queryId"],"provider":"ext-analyzer-mock",
 "providerVersion":"1.0.0","elapsedMs":100,"findings":[
 {"severity":"P1","ruleId":"EXT:mock:AD-001","anomalyType":"架构漂移",
  "summary":"MockService 直接依赖 DAL 层","file":"src/MockService.java","line":42,"lineType":"ADDED",
  "description":"命中 AD-001 分层依赖规则,违背架构约束。证据确凿。","risk":"分层边界被破坏。",
  "suggestion":"改为间接访问。","code":"import com.example.dal.OrderDao;","source":"step4e"}]}))""",
        "empty": "import json\nprint(json.dumps({'status':'EMPTY','findings':[]}))",
        "slow": "import sys,time\nfor i in range(30):\n    sys.stderr.write('working %d\\n' % i)\n    time.sleep(1)\n",  # 有存活信号但超时(10s timeout)
        "hang-silent": "import time\ntime.sleep(60)\n",  # 全静默 → 存活熔断
        "not-json": "print('this is not json at all')",
        "nonzero": "import sys\nsys.exit(3)",
        # 契约违规: ruleId 前缀不匹配 → 整条丢弃
        "bad-ruleid": """import sys,json
m=json.load(sys.stdin)
print(json.dumps({"status":"READY","queryId":m["queryId"],"findings":[
 {"severity":"P1","ruleId":"CR:InjectedRule","anomalyType":"x","summary":"x",
  "file":"src/MockService.java","line":1,"lineType":"ADDED","description":"x.","risk":"x","suggestion":"x","source":"step4e"}]}))""",
        # 锚定违规: file 不在 changedFiles → 整条丢弃
        "bad-anchor": """import sys,json
m=json.load(sys.stdin)
print(json.dumps({"status":"READY","queryId":m["queryId"],"findings":[
 {"severity":"P1","ruleId":"EXT:mock:AD-002","anomalyType":"x","summary":"x",
  "file":"src/NotInChanged.java","line":1,"lineType":"ADDED","description":"x.","risk":"x","suggestion":"x","source":"step4e"}]}))""",
        # lineType=MODIFIED → 丢弃(SOP: 禁 MODIFIED)
        "modified-linetype": """import sys,json
m=json.load(sys.stdin)
print(json.dumps({"status":"READY","queryId":m["queryId"],"findings":[
 {"severity":"P2","ruleId":"EXT:mock:AD-003","anomalyType":"x","summary":"x",
  "file":"src/MockService.java","line":1,"lineType":"MODIFIED","description":"x.","risk":"x","suggestion":"x","source":"step4e"}]}))""",
        # P0 灰度降级: 应保留但降为 confirm 且带原级尾注
        "p0-downgrade": """import sys,json
m=json.load(sys.stdin)
print(json.dumps({"status":"READY","queryId":m["queryId"],"findings":[
 {"severity":"P0","ruleId":"EXT:mock:AD-004","anomalyType":"资损风险","summary":"x",
  "file":"src/MockService.java","line":1,"lineType":"ADDED","description":"x.","risk":"x","suggestion":"x","source":"step4e"}]}))""",
    }
    with open(os.path.join(mock_dir, "main.py"), "w") as f:
        f.write(behaviors.get(scenario, behaviors["normal"]))
    if scenario == "mode-agent":
        # 改写 frontmatter: 显式声明 agent 模式(模拟 arch-pr-verifier 形态)
        fm_path = os.path.join(mock_dir, "SKILL.md")
        fm = open(fm_path).read().replace("  mode: script\n", "  mode: agent\n")
        open(fm_path, "w").write(fm)
    elif scenario == "no-engine":
        # 去掉 mode 声明 → auto 路由;配合受控 PATH(无 claude/codex/EXT_ARCH_ENGINE_CMD)
        # 让 _resolve_mode 预检判定无引擎 → 按 agent 拒绝
        fm_path = os.path.join(mock_dir, "SKILL.md")
        fm = open(fm_path).read().replace("  mode: script\n", "")
        open(fm_path, "w").write(fm)
        os.environ.pop("EXT_ARCH_ENGINE_CMD", None)
    # 1) discover
    os.environ["AI_SKILL_DIRECTORY"] = tmp
    rc_d = os.system("%s %s discover --skill-dir %s >/dev/null 2>&1" % (sys.executable, __file__, tmp))
    # 2) run(短超时加速测试)
    manifest = {"queryId": "selftest", "repo": "org/mock-repo", "prId": "0",
                "targetCommit": "0" * 40, "title": "self-test",
                "changedFiles": ["src/MockService.java"]}
    inp = os.path.join(tmp, "input.json")
    outp = os.path.join(tmp, "result.json")
    json.dump(manifest, open(inp, "w"))
    rc_r = os.system("%s %s run --input %s --output %s --provider ext-analyzer-mock --timeout 10 >/dev/null 2>&1"
                     % (sys.executable, __file__, inp, outp))
    # 3) collect
    step4e = os.path.join(tmp, "step4e.json")
    _cl = subprocess.run([sys.executable, __file__, "collect", "--result", outp, "--output", step4e],
                         capture_output=True, text=True, timeout=120)
    rc_c = _cl.returncode
    try:
        collected = json.loads(_cl.stdout)
    except Exception:
        collected = {}
    issues = []
    envelope = {}
    try:
        _raw = json.load(open(step4e))
        if isinstance(_raw, dict):  # 封装体
            envelope = _raw
            issues = list(_raw.get("findings") or [])
        elif isinstance(_raw, list):  # 旧格式(不应再出现)
            issues = _raw
    except Exception:
        pass
    ok = True
    msgs = []
    if (rc_d, rc_r, rc_c) != (0, 0, 0):
        ok = False
        msgs.append("rc=(%d,%d,%d) != (0,0,0)" % (rc_d, rc_r, rc_c))
    if scenario == "normal":
        if envelope.get("status") != "READY" or not envelope.get("checks"):
            ok = False
            msgs.append("normal: envelope must be READY with checks, got status=%s checks=%d" % (
                envelope.get("status"), len(envelope.get("checks") or [])))
        elif len(issues) != 1:
            ok = False
            msgs.append("normal: expect 1 finding, got %d" % len(issues))
        elif issues[0]["severity"] != "confirm" or not issues[0].get("_origSeverity"):
            ok = False
            msgs.append("normal: P1 should downgrade to confirm with _origSeverity")
        elif not issues[0]["ruleId"].startswith("EXT:mock:"):
            ok = False
            msgs.append("normal: ruleId prefix wrong")
    elif scenario in ("slow", "hang-silent", "not-json", "nonzero"):
        # 失败类场景必须产出非 READY 封装体——findings 空且 status 透传
        if issues:
            ok = False
            msgs.append("%s: expect 0 findings, got %d" % (scenario, len(issues)))
        if envelope.get("status") == "READY":
            ok = False
            msgs.append("%s: envelope.status must not be READY, got READY" % scenario)
        elif not envelope.get("checks"):
            ok = False
            msgs.append("%s: envelope.checks missing (requires per-analyzer check)" % scenario)
    elif scenario == "empty":
        # EMPTY = 跑成功但零发现: 封装体必须 status=READY 且 findings=[]
        if envelope.get("status") != "READY":
            ok = False
            msgs.append("empty: EMPTY run should yield envelope.status=READY, got %s" % envelope.get("status"))
        if issues:
            ok = False
            msgs.append("empty: expect 0 findings, got %d" % len(issues))
    elif scenario == "bad-ruleid":
        if issues:
            ok = False
            msgs.append("bad-ruleid: expect 0 findings(前缀不匹配丢弃), got %d" % len(issues))
    elif scenario == "bad-anchor":
        if issues:
            ok = False
            msgs.append("bad-anchor: expect 0 findings(锚定失败丢弃), got %d" % len(issues))
    elif scenario == "modified-linetype":
        if issues:
            ok = False
            msgs.append("modified-linetype: expect 0 findings(禁MODIFIED), got %d" % len(issues))
    elif scenario == "p0-downgrade":
        if len(issues) != 1 or issues[0]["severity"] != "confirm":
            ok = False
            msgs.append("p0-downgrade: expect confirm downgraded, got %s" % (
                issues[0]["severity"] if issues else "none"))
    elif scenario == "mode-agent":
        # 守卫: run 拒绝直跑,输出含 mode-guard;collect 透传 FAILED 封装体
        try:
            run_out = json.load(open(outp))
        except Exception:
            run_out = {}
        if "mode-guard" not in json.dumps(run_out.get("dropReasons") or []):
            ok = False
            msgs.append("mode-agent: run must reject with mode-guard, got %s" % run_out.get("dropReasons"))
        if envelope.get("status") != "FAILED":
            ok = False
            msgs.append("mode-agent: envelope.status must be FAILED, got %s" % envelope.get("status"))
        if issues:
            ok = False
            msgs.append("mode-agent: expect 0 findings, got %d" % len(issues))
    elif scenario == "no-engine":
        # 预检: mode:auto + 无引擎 → auto 路由为 agent → 拒绝;
        # 若测试机恰有 claude/codex,auto 会按 script 直跑成功——此时跳过断言(环境不可控)
        _engine_here = os.environ.get("EXT_ARCH_ENGINE_CMD") or any(
            os.path.isfile(os.path.join(p, c)) for p in os.environ.get("PATH", "").split(os.pathsep) for c in ENGINE_CLI_PROBES)
        if not _engine_here:
            if envelope.get("status") == "READY":
                ok = False
                msgs.append("no-engine: auto mode without engine must not be READY")
            elif "mode-guard" not in json.dumps(envelope.get("checks") or []):
                ok = False
                msgs.append("no-engine: expected mode-guard in checks, got %s" % envelope.get("checks"))
    # bad-ruleid/bad-anchor 等: run 是 READY(校验在 collect 侧),所以 rc_r=0 是对的
    print(json.dumps({"status": "PASS" if ok else "FAIL", "scenario": scenario,
                      "rc": [rc_d, rc_r, rc_c], "collected": collected,
                      "envelopeStatus": envelope.get("status", ""),
                      "issuesKept": len(issues), "messages": msgs},
                     ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="AI-CR external analyzer loader (Step 0F/4-E/collect/self-test)")
    ap.add_argument("--skill-dir", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("discover", help="Step 0F: discover ext-analyzer-* and build registry")
    d.add_argument("--skill-dir", default=None)
    d.add_argument("--disabled", nargs="*", default=None)
    r = sub.add_parser("run", help="Step 4-E: invoke analyzer subprocess with timeouts")
    r.add_argument("--input", required=True)
    r.add_argument("--output", default=None)
    r.add_argument("--provider", default=None)
    r.add_argument("--timeout", type=int, default=None)
    b = sub.add_parser("build-manifest", help="Step 4-E-1: 命令行代拼 manifest(防 LLM 手拼类型漂移)")
    b.add_argument("--org", default=None, help="组织名(queryId 拼接用)")
    b.add_argument("--repo", required=True, help="仓库名(单传全称 org/repo 亦可)")
    b.add_argument("--pr-id", required=True, dest="pr_id")
    b.add_argument("--target-commit", required=True, dest="target_commit")
    b.add_argument("--title", required=True)
    b.add_argument("--files", nargs="*", default=None, help="变更文件列表")
    b.add_argument("--files-file", default=None, dest="files_file", help="变更文件 JSON 数组文件(优先于 --files)")
    b.add_argument("--analyzer", default=None, help="analyzer 名(默认路径名用)")
    b.add_argument("--query-id", default=None, dest="query_id", help="显式 queryId(缺省自动拼 org/repo#prId@commit8)")
    b.add_argument("--base-commit", default=None, dest="base_commit",
                   help="本轮 CR 审查区间的权威基线 commit(40位hex);缺省不写入 manifest;"
                        "analyzer 侧据此按 baseCommit..targetCommit 区间取 diff,而非自证基线")
    b.add_argument("--output", default=None)
    c = sub.add_parser("collect", help="collect point: validate findings + pilot downgrade + write step4e.json")
    c.add_argument("--result", default=None, help="SOP headless 模式: run 产出的 AnalyzerResult 文件")
    c.add_argument("--findings", default=None, help="subagent 模式: 子 Agent 返回的原始 findings JSON 数组文件")
    c.add_argument("--analyzer", default=None, help="subagent 模式: analyzer 名(ext-analyzer- 前缀可省)")
    c.add_argument("--manifest", default=None, help="subagent 模式: AnalysisContextManifest 文件(锚定校验+runId/targetCommit 身份,建议必带)")
    c.add_argument("--status", default=None, help="显式失败收割——4-E-2 超时/子Agent异常时,主 Agent 传 --status TIMEOUT|FAILED|UNKNOWN --error {原因} [--manifest {manifest}],落封装体供门禁拦截,严禁静默丢弃")
    c.add_argument("--error", default=None, help="--status 时的失败原因(透传进 check.error)")
    c.add_argument("--output", required=True)
    s = sub.add_parser("self-test", help="contract self-test with mock analyzer")
    s.add_argument("--scenario", default=None)
    args = ap.parse_args()
    if args.cmd == "discover":
        if not args.skill_dir:
            args.skill_dir = ap.get_default("skill_dir")
        return discover(args)
    if args.cmd == "run":
        return run(args)
    if args.cmd == "build-manifest":
        return build_manifest(args)
    if args.cmd == "collect":
        return collect(args)
    if args.cmd == "self-test":
        return self_test(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
