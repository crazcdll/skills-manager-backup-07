#!/usr/bin/env python3
"""
score_commit.py — AI-Ready 仓库 commit 程序化评分 CLI

工作流：
  1) 浅克隆 (repo, commit) 到本地缓存目录
  2) 识别是否为 mono-repo；单仓评分根目录，mono-repo 评分每个清单成员
  3) 为每个评分单元写 prompt，并调用 `mc --code -p --output-format json`
  4) 校验成员结果；mono-repo 对全部成员综合分取等权平均值

使用：
  python3 score_commit.py \\
      --repo ssh://git@git.dianpingoa.com/fun/scp-dzbiz-process-server.git \\
      --commit a3b416d04811 \\
      --out /tmp/scoring.json

  # 输出（JSON 写入 --out 同时打印到 stdout）：
  # {
  #   "version": "1.0",
  #   "repo": "...",
  #   "commit": "a3b416d0...",
  #   "repo_type": "backend",
  #   "score": 71.4,
  #   "level": "及格",
  #   "dim_scores": { "dim1a": 75, "dim1b": 60, ... },
  #   "elapsed_ms": 132456,
  #   "_status": "ok",
  #   "_raw_text_path": "/tmp/...txt"
  # }

设计约束：
  - mono-repo 成员发现与聚合规则由 monorepo.py 单独负责
  - 子 agent 通过 --add-dir 拿到 ai-ready-repo skill 的 references 目录
  - 输出必须是机器可解析 JSON，校验失败时 _status=error 并保留 _raw_text 以便调试
  - 不强制依赖 catpaw-claude-code-dev 的 wrapper 脚本，直接调 mc/claude
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

# 同目录浅克隆模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
from clone_at_commit import clone_at_commit, CloneError, DEFAULT_WORKDIR  # noqa: E402
from monorepo import (  # noqa: E402
    level_for_score,
    score_checkout,
)

SKILL_ROOT = Path(__file__).resolve().parent.parent  # ai-ready-repo/
WEIGHT_PROFILES_PATH = SKILL_ROOT / "references" / "weight-profiles.json"
DEFAULT_AGENT_TIMEOUT = 1200  # 20 min

# 权重档案兜底常量（与 references/weight-profiles.json 保持一致；
# 配置文件缺失/损坏时退化使用，避免子 agent 失去权重指引）
_FALLBACK_WEIGHT_PROFILES: dict = {
    "profiles": {
        "backend": {
            "weights": {
                "dim1a": 6, "dim1b": 6, "dim2": 12, "dim3": 8, "dim4": 7,
                "dim5": 5, "dim6": 14, "dim7": 12, "dim8": 8, "dim9": 12, "dim10": 10,
            }
        },
        "frontend": {
            "weights": {
                "dim1a": 6.7, "dim1b": 6.7, "dim2": 13.4, "dim3": 8.9, "dim4": 7.8,
                "dim5": 5.6, "dim6": 15.5, "dim7": 13.4, "dim8": 8.9, "dim9": 2, "dim10": 11.1,
            }
        },
    },
    "repo_type_to_profile": {
        "backend": "backend", "unknown": "backend",
        "frontend": "frontend", "frontend-mono": "frontend", "nodejs": "frontend",
    },
}


def load_weight_profiles() -> dict:
    """读取权重档案（单一真相源）；缺失或损坏时退化到内置常量。"""
    try:
        cfg = json.loads(WEIGHT_PROFILES_PATH.read_text(encoding="utf-8"))
        # 最小完整性校验：两档都存在且权重之和均为 100
        for prof in ("backend", "frontend"):
            w = cfg["profiles"][prof]["weights"]
            if abs(sum(w.values()) - 100) > 1e-6:
                raise ValueError(f"profile {prof} 权重之和 != 100")
        cfg.setdefault("repo_type_to_profile", _FALLBACK_WEIGHT_PROFILES["repo_type_to_profile"])
        return cfg
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 读取 {WEIGHT_PROFILES_PATH} 失败({e})，使用内置兜底权重", file=sys.stderr)
        return _FALLBACK_WEIGHT_PROFILES


def _format_weight_block(cfg: dict) -> str:
    """把两档权重渲染成给子 agent 看的文本块。"""
    order = ["dim1a", "dim1b", "dim2", "dim3", "dim4", "dim5",
             "dim6", "dim7", "dim8", "dim9", "dim10"]
    lines: list[str] = []
    mapping = cfg.get("repo_type_to_profile", _FALLBACK_WEIGHT_PROFILES["repo_type_to_profile"])
    lines.append("repo_type → 权重档案映射：" +
                 ", ".join(f"{rt}={p}" for rt, p in mapping.items()))
    for prof in ("backend", "frontend"):
        w = cfg["profiles"][prof]["weights"]
        body = ", ".join(f"{k} {w[k]}%" for k in order)
        total = sum(w[k] for k in order)
        lines.append(f"  [{prof} 档] {body}（合计 {total:g}%）")
    return "\n".join(lines)

# 默认评分模型候选链：glm-5.2 → LongCat-2.0
#   - 优先国产模型：runtime（CatPaw / Multica 定制版）网关广泛支持，
#     不像 claude-sonnet-4-7 在部分 runtime 网关报 400「不支持的模型类型」导致全仓降级
#   - 候选链自动回退：某模型不支持/超时/400 时自动换下一个，全部不可用才判失败
#   - 计算量评估不需要 opus 级别推理，选性价比模型即可
DEFAULT_AGENT_MODEL_CHAIN: list[str] = ["glm-5.2", "LongCat-2.0"]
# 兼容旧引用：单值默认取候选链首个
DEFAULT_AGENT_MODEL = DEFAULT_AGENT_MODEL_CHAIN[0]

# mc --code 网关实测可用模型清单（供 CLI --help 展示）
# 可通过 `python3 score_commit.py --list-models` 查看
KNOWN_MODELS: dict[str, list[str]] = {
    "国产 (默认候选链)": ["glm-5.2", "LongCat-2.0"],
    "Claude": [
        "claude-opus-4-7","claude-opus-4-6",
        "claude-sonnet-4-7", "claude-sonnet-4-6",
        "claude-haiku-4-5",
        "opus", "sonnet", "haiku",  # alias
    ],
    "OpenAI GPT": ["gpt-5.4", "gpt-5.4-xhigh"],
    "智谱 GLM": ["glm-5", "glm-5.2"],
    "Moonshot Kimi": ["kimi-k2.6"],
    "DeepSeek": ["deepseek-v4-pro"],
    "MiniMax": ["MiniMax-M2.7"],
}


def _parse_model_chain(model: "str | list[str] | None") -> list[str]:
    """把 model 参数规整为候选模型列表。

    - None / 空 → 默认候选链 DEFAULT_AGENT_MODEL_CHAIN
    - "glm-5.2,LongCat-2.0" → ["glm-5.2", "LongCat-2.0"]（逗号分隔，去空白/去重保序）
    - ["a","b"] → 原样清洗
    """
    if model is None:
        return list(DEFAULT_AGENT_MODEL_CHAIN)
    raw = model if isinstance(model, list) else str(model).split(",")
    chain: list[str] = []
    for m in raw:
        m = m.strip()
        if m and m not in chain:
            chain.append(m)
    return chain or list(DEFAULT_AGENT_MODEL_CHAIN)


# 判定 stderr 是否属于「模型不可用」——可回退换下一候选（而非其它硬错）
_MODEL_UNAVAILABLE_PAT = re.compile(
    r"不支持的模型|不支持|unsupported|not\s+support|invalid\s+model|unknown\s+model|"
    r"model\s+not\s+found|\b400\b|超时|timeout|timed\s+out",
    re.IGNORECASE,
)


def _is_model_unavailable_error(msg: str) -> bool:
    return bool(_MODEL_UNAVAILABLE_PAT.search(msg or ""))

# ----------------------------------------------------------------------------
# 子 agent 输出 JSON Schema
# ----------------------------------------------------------------------------
_DIM_KEYS = [
    "dim1a", "dim1b", "dim2", "dim3", "dim4",
    "dim5", "dim6", "dim7", "dim8", "dim9", "dim10",
]

JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "score", "level", "repo_type", "dim_scores", "highlights", "main_gaps",
    ],
    "properties": {
        "score": {
            "type": "number", "minimum": 0, "maximum": 100,
            "description": "11 维加权后的综合分（0–100），保留 1 位小数",
        },
        "level": {
            "type": "string",
            "enum": ["优秀", "良好", "及格", "不及格"],
        },
        "repo_type": {
            "type": "string",
            "enum": ["backend", "frontend", "frontend-mono", "nodejs", "unknown"],
        },
        "dim_scores": {
            "type": "object",
            "additionalProperties": False,
            "required": _DIM_KEYS,
            "properties": {k: {"type": "integer", "minimum": 0, "maximum": 100} for k in _DIM_KEYS},
        },
        "dim_notes": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "可选：每 dim 的扣分简述（一行字）",
        },
        "highlights": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 6,
        },
        "main_gaps": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 6,
        },
    },
}

# ----------------------------------------------------------------------------
# Prompt 构造
# ----------------------------------------------------------------------------
_PROMPT_TEMPLATE = """\
你现在执行一次 AI-Ready 仓库评估任务，目标是对当前工作目录中的代码仓库快照
（commit={commit_short}）做出 11 维度量化评分。这是一次**纯评估**任务，
**禁止**进行任何代码改动、Git 操作、依赖安装、网络请求或文件写入（除评估结果外）。

{scope_block}

## 必读

1. 阅读评估 SKILL：`{skill_root}/SKILL.md`
2. 阅读 11 个维度细则（按需懒加载）：`{skill_root}/references/dim*.md`
3. 你**不需要**执行 step0-precheck、step7-callback、step7-remote-mode 流程，
   也**不需要**生成 markdown 报告或保存到学城——本任务只关心 11 维分数。

## 工作目录

{repo_dir}

## 输出契约（强约束）

最终请且仅请输出**一个 JSON 对象**，字段如下（顺序不限）：

```json
{{
  "score": 71.4,
  "level": "及格",
  "repo_type": "backend",
  "dim_scores": {{
    "dim1a": 75, "dim1b": 60, "dim2": 70, "dim3": 80, "dim4": 65,
    "dim5": 70, "dim6": 55, "dim7": 80, "dim8": 50, "dim9": 75, "dim10": 60
  }},
  "dim_notes": {{
    "dim1a": "AGENTS.md 缺业务边界",
    "...": "..."
  }},
  "highlights": ["..."],
  "main_gaps": ["..."]
}}
```

权重提醒（**务必先检测 repo_type，再按对应档案加权**，匹配 SKILL.md 第三步）：
{weight_block}
  注意：前端类仓库（frontend / frontend-mono / nodejs）测试维度 dim9 已降权至 2%，
  请勿沿用后端 12%；务必用与你判定的 repo_type 对应的那一档权重计算 score。
  所选档案 11 个权重之和必为 100，加权累加得到的 score 落在 [0,100]。

`level` 与 `score` 关系：
  - score ≥ 90 → 优秀
  - 75 ≤ score < 90 → 良好
  - 50 ≤ score < 75 → 及格
  - score < 50 → 不及格

## 执行约束

- **不可写**：除标准输出最终 JSON 外，禁止 Edit/Write/Bash 中任何对仓库的写操作。
- **节能**：抽样阅读，不需要逐文件审计；目标是 5–15 分钟内给出可信打分。
- **诚实**：拿不准的维度用 60–70 中位分，并在 `dim_notes` 注明 "uncertain"。
"""


def build_prompt(
    repo_dir: Path,
    commit: str,
    skill_root: Path,
    *,
    mono_member: bool = False,
    repository_root: Path | None = None,
) -> str:
    weight_block = _format_weight_block(load_weight_profiles())
    scope_block = ""
    if mono_member:
        scope_block = (
            "## 评分范围\n\n"
            "当前目录是父 mono-repo 的一个构建清单一级成员。只把当前成员作为单仓执行 "
            "11 维评分，不再递归识别其内部 workspace；可以沿父仓导航读取共享治理文档。\n"
            f"父仓根目录：{repository_root}\n"
        )
    return _PROMPT_TEMPLATE.format(
        commit_short=commit[:12],
        skill_root=str(skill_root),
        repo_dir=str(repo_dir),
        scope_block=scope_block,
        weight_block=weight_block,
    )


# ----------------------------------------------------------------------------
# 子 agent 调用
# ----------------------------------------------------------------------------
def _resolve_mc_bin() -> str:
    """优先取 PATH 里的 mc；找不到时 fallback 到 claude。"""
    for cand in ("mc", "claude"):
        if shutil.which(cand):
            return cand
    raise FileNotFoundError("未找到 mc 或 claude 命令，请先安装 Claude Code")


class ModelUnavailable(RuntimeError):
    """某个模型在网关不可用（不支持/超时/400），可回退到下一候选。"""


def _run_one_model(
    repo_dir: Path,
    commit: str,
    *,
    model: str,
    timeout: int,
    skill_root: Path,
    extra_add_dir: list[Path] | None,
    prompt_text: str,
    prompt_file: Path,
) -> str:
    """用单个模型跑一次子 agent 评分，返回 raw_stdout。
    模型不可用（不支持/超时/400）抛 ModelUnavailable（可回退），其它硬错抛 RuntimeError。
    """
    bin_name = _resolve_mc_bin()
    cmd: list[str] = []
    if bin_name == "mc":
        cmd += ["mc", "--code"]
    else:
        cmd += [bin_name]

    cmd += [
        "-p", prompt_text,
        "--output-format", "json",
        "--json-schema", json.dumps(JSON_SCHEMA, ensure_ascii=False),
        "--add-dir", str(skill_root),
        "--dangerously-skip-permissions",
    ]
    if model:
        cmd += ["--model", model]
    for d in extra_add_dir or []:
        cmd += ["--add-dir", str(d)]

    print(
        f"$ {bin_name} --code -p [prompt] --model {model} --output-format json ...",
        file=sys.stderr,
    )
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # 超时归为「模型不可用」——可回退下一候选
        raise ModelUnavailable(f"子 agent 评分超时 {timeout}s（模型 {model}）")

    if proc.returncode != 0:
        tail = proc.stderr.strip()[-500:]
        sys.stderr.write(f"[stderr] {proc.stderr[-2000:]}\n")
        detail = f"子 agent 进程退出码 {proc.returncode}（模型 {model}），stderr 末尾: {tail}"
        if _is_model_unavailable_error(proc.stderr):
            raise ModelUnavailable(detail)
        raise RuntimeError(detail)
    return proc.stdout


def run_agent_scoring(
    repo_dir: Path,
    commit: str,
    *,
    timeout: int = DEFAULT_AGENT_TIMEOUT,
    model: "str | list[str]" = DEFAULT_AGENT_MODEL,
    skill_root: Path = SKILL_ROOT,
    extra_add_dir: list[Path] | None = None,
    mono_member: bool = False,
    repository_root: Path | None = None,
) -> tuple[str, str, str]:
    """
    跑子 agent 评分（支持模型候选链自动回退）。
    返回 (raw_stdout, prompt_path, used_model)。
    - `model` 可为单个模型名、逗号分隔字符串或列表；按序尝试，某候选报
      「不支持/超时/400」自动回退下一候选，全部不可用才抛最后一个错误。
    raw_stdout 是 `--output-format json` 的 wrapper，解析在外层做。
    """
    prompt_text = build_prompt(
        repo_dir,
        commit,
        skill_root,
        mono_member=mono_member,
        repository_root=repository_root,
    )
    prompt_file = Path(tempfile.mkstemp(prefix="ai-ready-prompt-", suffix=".md")[1])
    prompt_file.write_text(prompt_text, encoding="utf-8")

    chain = _parse_model_chain(model)
    last_err: Exception | None = None
    for idx, m in enumerate(chain):
        try:
            raw = _run_one_model(
                repo_dir, commit,
                model=m, timeout=timeout, skill_root=skill_root,
                extra_add_dir=extra_add_dir,
                prompt_text=prompt_text, prompt_file=prompt_file,
            )
            if idx > 0:
                print(f"[model-fallback] 已回退到候选模型 {m}（前 {idx} 个不可用）", file=sys.stderr)
            return raw, str(prompt_file), m
        except ModelUnavailable as e:
            last_err = e
            nxt = chain[idx + 1] if idx + 1 < len(chain) else None
            if nxt:
                print(f"[model-fallback] 模型 {m} 不可用，回退下一候选 {nxt} …：{e}", file=sys.stderr)
                continue
            # 已是最后一个候选
            break
        except RuntimeError as e:
            # 非模型类硬错：不回退，直接上抛
            raise
    raise RuntimeError(
        f"所有候选模型均不可用（已试：{', '.join(chain)}）；最后错误：{last_err}"
    )


# ----------------------------------------------------------------------------
# 输出解析
# ----------------------------------------------------------------------------
def _extract_inner_json(wrapper_stdout: str) -> dict:
    """
    `claude -p --output-format json` 输出的 wrapper 形如：
      {
        "type": "result", "subtype": "success",
        "result": "<人类摘要文本>",
        "structured_output": { ... },   # 当 --json-schema 启用时由 Claude Code 校验后填入
        ...
      }
    优先取 `structured_output`（schema 强约束产物），不存在时退化到 `result`。
    """
    try:
        outer = json.loads(wrapper_stdout)
    except json.JSONDecodeError as e:
        raise ValueError(f"wrapper JSON 解析失败: {e}; first 300: {wrapper_stdout[:300]}")

    # 路径 1：--json-schema 直接给到的结构化输出（最稳）
    so = outer.get("structured_output")
    if isinstance(so, dict) and so:
        return so

    # 路径 2：result 字段里嵌 JSON（兜底）
    result_field = outer.get("result")
    if isinstance(result_field, dict):
        return result_field
    if isinstance(result_field, str):
        text = result_field.strip()
        if text.startswith("```"):
            text = "\n".join(
                ln for ln in text.splitlines() if not ln.strip().startswith("```")
            ).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            l, r = text.find("{"), text.rfind("}")
            if l >= 0 and r > l:
                try:
                    return json.loads(text[l : r + 1])
                except json.JSONDecodeError:
                    pass
        raise ValueError(
            f"既无 structured_output，result 字段也非 JSON: {text[:300]}"
        )
    raise ValueError(
        f"wrapper 既无 structured_output 也无 result: keys={list(outer.keys())}"
    )


def _validate_inner(payload: dict) -> list[str]:
    """轻量 schema 校验（避免引入 jsonschema 依赖）。返回错误列表，空表示通过。"""
    errs: list[str] = []
    if not isinstance(payload.get("score"), (int, float)):
        errs.append("score 缺失或非数值")
    elif not (0 <= float(payload["score"]) <= 100):
        errs.append("score 超出 [0,100]")
    if payload.get("level") not in ("优秀", "良好", "及格", "不及格"):
        errs.append("level 非法")
    dim_scores = payload.get("dim_scores")
    if not isinstance(dim_scores, dict):
        errs.append("dim_scores 缺失或非 object")
    else:
        for k in _DIM_KEYS:
            v = dim_scores.get(k)
            if not isinstance(v, int):
                errs.append(f"dim_scores.{k} 缺失或非整数")
            elif not (0 <= v <= 100):
                errs.append(f"dim_scores.{k} 超出 [0,100]")
    return errs


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def _score_one_checkout(
    repo_dir: Path,
    commit: str,
    *,
    timeout: int,
    model: "str | list[str]",
    raw_dump_dir: Path | None,
    repository_root: Path,
) -> dict:
    """Run and validate one logical repository score inside a checkout."""
    started = time.time()
    mono_member = repo_dir.resolve() != repository_root.resolve()
    raw_stdout, prompt_path, used_model = run_agent_scoring(
        repo_dir,
        commit,
        timeout=timeout,
        model=model,
        mono_member=mono_member,
        repository_root=repository_root if mono_member else None,
    )

    raw_text_path = ""
    if raw_dump_dir:
        raw_dump_dir.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        member_token = re.sub(r"[^A-Za-z0-9_.-]+", "-", repo_dir.name)
        output_path = raw_dump_dir / f"agent-raw-{member_token}-{commit[:8]}-{ts}.json"
        output_path.write_text(raw_stdout, encoding="utf-8")
        raw_text_path = str(output_path)

    try:
        inner = _extract_inner_json(raw_stdout)
    except Exception as exc:  # noqa: BLE001
        return {
            "_status": "parse_error",
            "_error": str(exc),
            "_raw_text_path": raw_text_path,
            "_model": used_model,
            "elapsed_ms": int((time.time() - started) * 1000),
        }

    errors = _validate_inner(inner)
    return {
        "repo_type": inner.get("repo_type", "unknown"),
        "score": round(float(inner.get("score", 0)), 1),
        "level": inner.get("level"),
        "dim_scores": inner.get("dim_scores", {}),
        "dim_notes": inner.get("dim_notes", {}),
        "highlights": inner.get("highlights", []),
        "main_gaps": inner.get("main_gaps", []),
        "_status": "ok" if not errors else "schema_error",
        "_schema_errors": errors,
        "_raw_text_path": raw_text_path,
        "_prompt_path": prompt_path,
        "_model": used_model,
        "elapsed_ms": int((time.time() - started) * 1000),
    }


def score_commit(
    repo: str,
    commit: str,
    *,
    workdir: Path = DEFAULT_WORKDIR,
    timeout: int = DEFAULT_AGENT_TIMEOUT,
    model: "str | list[str]" = DEFAULT_AGENT_MODEL,
    raw_dump_dir: Path | None = None,
) -> dict:
    """端到端：浅克隆 + 评分 + 校验。model 支持候选链自动回退。"""
    started = time.time()

    # 1) 浅克隆
    clone_result = clone_at_commit(repo, commit, workdir=workdir)

    def score_one(repo_dir: Path, resolved_commit: str) -> dict:
        return _score_one_checkout(
            repo_dir,
            resolved_commit,
            timeout=timeout,
            model=model,
            raw_dump_dir=raw_dump_dir,
            repository_root=clone_result.repo_dir,
        )

    score_result = score_checkout(clone_result.repo_dir, clone_result.commit, score_one)
    version = "1.1" if score_result.get("repo_type") == "mono-repo" else "1.0"
    return {
        "version": version,
        "repo": clone_result.repo_url,
        "commit": clone_result.commit,
        **score_result,
        "elapsed_ms": int((time.time() - started) * 1000),
    }


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="AI-Ready 仓库 commit 程序化评分（浅克隆 + Claude Code 子 agent）"
    )
    # 注意：--list-models 时不需要 --repo/--commit，这里不设 required，下方手动校验
    ap.add_argument("--repo", help="ssh / git@host:path / group/name")
    ap.add_argument("--commit", help="完整或短 commit hash（≥7 位）")
    ap.add_argument(
        "--workdir", default=str(DEFAULT_WORKDIR),
        help=f"浅克隆缓存根目录，默认 {DEFAULT_WORKDIR}",
    )
    ap.add_argument("--out", help="结果 JSON 写入此文件；不传则只打印到 stdout")
    ap.add_argument("--timeout", type=int, default=DEFAULT_AGENT_TIMEOUT)
    ap.add_argument(
        "--model",
        default=",".join(DEFAULT_AGENT_MODEL_CHAIN),
        help=(
            "评分子 agent 使用的模型，支持逗号分隔的候选链（前者不可用自动回退后者）。"
            f"默认候选链 {','.join(DEFAULT_AGENT_MODEL_CHAIN)}（优先国产模型，"
            "避免 claude-* 在部分 runtime 网关报 400 导致全仓降级）。"
            "常用：glm-5.2 / LongCat-2.0 / claude-sonnet-4-7 / gpt-5.4-xhigh / kimi-k2.6 。"
            "完整清单运行：--list-models"
        ),
    )
    ap.add_argument(
        "--list-models",
        action="store_true",
        help="打印 mc --code 网关实测可用模型清单后退出",
    )
    ap.add_argument(
        "--dump-raw-dir",
        help="把子 agent 原始输出 dump 到这个目录，方便排查",
    )
    args = ap.parse_args(argv)

    if args.list_models:
        print("mc --code 网关可用模型（实测）\n")
        chain_rank = {m: i + 1 for i, m in enumerate(DEFAULT_AGENT_MODEL_CHAIN)}
        for group, models in KNOWN_MODELS.items():
            print(f"  [{group}]")
            for m in models:
                if m in chain_rank:
                    marker = f" ← 默认候选链 #{chain_rank[m]}"
                else:
                    marker = ""
                print(f"    - {m}{marker}")
            print()
        print(
            f"默认候选链：{' → '.join(DEFAULT_AGENT_MODEL_CHAIN)}"
            "（前者不可用/超时/400 自动回退后者，全部失败才判定评分失败）。\n"
            "提示：claude alias （opus/sonnet/haiku）会被 mc 网关路由到对应家族的最新版本。\n"
            "如需查询实时清单，请参考 mc --code 网关文档或使用 `mc --code --list-models`（以网关实际返回为准）。"
        )
        return 0

    # 非 list-models 模式：必须显式给 repo + commit
    if not args.repo or not args.commit:
        ap.error("--repo 与 --commit 在评分模式下必填（仅 --list-models 时可省略）")

    try:
        result = score_commit(
            args.repo,
            args.commit,
            workdir=Path(args.workdir),
            timeout=args.timeout,
            model=args.model,
            raw_dump_dir=Path(args.dump_raw_dir) if args.dump_raw_dir else None,
        )
    except CloneError as e:
        result = {
            "version": "1.0",
            "repo": args.repo,
            "commit": args.commit,
            "_status": "clone_error",
            "_error": str(e),
        }
    except Exception as e:  # noqa: BLE001
        result = {
            "version": "1.0",
            "repo": args.repo,
            "commit": args.commit,
            "_status": "error",
            "_error": f"{type(e).__name__}: {e}",
        }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(text)
    else:
        print(text)
    return 0 if result.get("_status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(_main())
