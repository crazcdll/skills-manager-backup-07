#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Skill 自更新统一逻辑（三端一致）。

⚠️ 本文件在三个 Skill 各存一份（Skill 之间无法互相 import）：
     ai-ui-autotest-engine/scripts/shared/selfupdate.py
     ai-app-flow/scripts/selfupdate.py
     ai-auto-ui-test/scripts/selfupdate.py
   **修改任一，请三份同步**（内容完全一致）。

策略：**按版本号判定 + 按来源记录定位**
  · 本地版本：SKILL.md 的 skillhub.version；本地 skill id：skillhub.skill_id。
  · 远端版本：`mtskills fetchdata detail <skill_id>` 的 currentVisibleVersion。
  · 本地 < 远端 → `mtskills pull`。**只更新传入的这一处安装**：cwd 取 `.claude`/`.agent`
    的父目录，使 `<cwd>/.claude/skills` 命中本容器（mtskills 扫描顺序中它先于 `~/.claude/skills`），
    否则会退化成更新全局安装。
  · 无来源记录（非 mtskills 安装）→ 不拉取，直接给出手动命令。

不做本地改动检测：本地未提交的改动由开发者自行管理（与"重新安装"语义一致）。
"""
import json
import os
import re
import subprocess

_VERSION_RE = re.compile(r'"currentVisibleVersion"\s*:\s*"([^"]+)"')


def _default_runner(cmd, timeout=120):
    """默认执行器：返回 (ok, stdout)。"""
    try:
        r = subprocess.run(["sh", "-c", cmd], capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout or "")
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _call(runner, cmd, timeout):
    """统一调用 runner，兼容 (ok, out) 与 (ok, out, err) 两种返回。"""
    res = runner(cmd, timeout)
    if isinstance(res, tuple) and len(res) == 3:
        ok, out, _err = res
        return ok, out
    ok, out = res
    return ok, out


def _frontmatter(skill_dir):
    """读取 SKILL.md frontmatter（首个 `---` 到下一个 `---`）；无则 None。"""
    path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    body, started = [], False
    for line in lines:
        if line.strip() == "---":
            if started:
                return body
            started = True
            continue
        if started:
            body.append(line)
    return None


def _field(lines, key):
    """frontmatter 里按 key 取标量值（要求 key 后紧跟 ':'）。"""
    for line in lines or []:
        stripped = line.strip()
        if stripped.startswith(key + ":"):
            return stripped[len(key) + 1:].strip().strip('"\'') or None
    return None


def read_skill_version(skill_dir):
    """本地版本号（SKILL.md 的 skillhub.version）；无则 None。"""
    fm = _frontmatter(skill_dir)
    return _field(fm, "skillhub.version") if fm else None


def read_skill_id(skill_dir):
    """本地 skill id（SKILL.md 的 skillhub.skill_id）；无则 None。"""
    fm = _frontmatter(skill_dir)
    return _field(fm, "skillhub.skill_id") if fm else None


def compare_versions(a, b):
    """语义化比较：a<b→-1，a==b→0，a>b→1（去前导 v/V，逐段取前导数字）。"""
    def parts(v):
        out = []
        for seg in re.sub(r"^[vV]", "", str(v or "")).split("."):
            m = re.match(r"\d+", seg)
            out.append(int(m.group(0)) if m else 0)
        return out

    pa, pb = parts(a), parts(b)
    for i in range(max(len(pa), len(pb))):
        x = pa[i] if i < len(pa) else 0
        y = pb[i] if i < len(pb) else 0
        if x != y:
            return -1 if x < y else 1
    return 0


def mtskills_root(skill_dir):
    """mtskills 定位根：`<root>/.claude|.agent/skills/<name>` 的 `<root>`（即 pull 的 cwd）。
    其它容器（如 `.catpaw/skills`）mtskills 不识别 → 返回 None。"""
    d = skill_dir
    for _ in range(4):
        d = os.path.dirname(d)
        if os.path.basename(d) in (".claude", ".agent"):
            return os.path.dirname(d)
    return None


def can_pull(skill_dir, skill_name):
    """能否 `mtskills pull` 到**本安装**：需 `<容器>/.mtskills-source.jsonl` 中存在
    skillName 匹配、且 targetDir（realpath 归一化，兼容软链路径）指向本容器的记录。"""
    container = os.path.realpath(os.path.dirname(skill_dir))
    record = os.path.join(container, ".mtskills-source.jsonl")
    if not os.path.isfile(record):
        return False
    try:
        with open(record, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                target = os.path.realpath(rec.get("targetDir") or "")
                if rec.get("skillName") == skill_name and target == container:
                    return True
    except OSError:
        return False
    return False


def remote_version(skill_id, runner=_default_runner):
    """远端当前版本（`mtskills fetchdata detail <id>` 的 currentVisibleVersion）；失败返回 None。"""
    if not skill_id:
        return None
    ok, out = _call(runner, f"mtskills fetchdata detail {skill_id} 2>/dev/null", 30)
    if not ok or not out:
        return None
    m = _VERSION_RE.search(out)
    return m.group(1) if m else None


def sync_self(skill_dir, skill_name, runner=None, log=None):
    """统一的自更新入口：只负责 `skill_dir` 这一处安装（多安装由调用方遍历）。

    Args:
        skill_dir:  本安装目录（含 SKILL.md）
        skill_name: Skill 名称（mtskills 标识）
        runner:     可选执行器 cmd→(ok, out[, err])；默认 sh -c
        log:        可选日志回调 str→None

    Returns:
        dict: action ∈ {up-to-date, updated, unknown-remote, unknown-local, update-failed}
    """
    runner = runner or _default_runner
    log = log or (lambda _m: None)

    local_ver = read_skill_version(skill_dir)
    remote_ver = remote_version(read_skill_id(skill_dir), runner)

    if not local_ver:
        return {"action": "unknown-local", "detail": "无法读取本地版本（SKILL.md 缺 skillhub.version）"}
    if not remote_ver:
        return {"action": "unknown-remote", "detail": "无法查询远端版本（mtskills fetchdata 失败）"}
    if compare_versions(local_ver, remote_ver) >= 0:
        return {"action": "up-to-date", "detail": f"已是最新（本地 {local_ver} ≥ 远端 {remote_ver}）"}

    root = mtskills_root(skill_dir)
    if not root or not can_pull(skill_dir, skill_name):
        return {"action": "update-failed", "detail": "无法安全定位本安装（缺 mtskills 来源记录）",
                "hint": f"请手动执行: mtskills pull {skill_name}"}

    log(f"检测到远端新版本 {remote_ver}（本地 {local_ver}），正在更新 {skill_name} ...")
    ok, _out = _call(runner, f"cd {root} && mtskills pull {skill_name} 2>/dev/null", 120)
    if ok:
        return {"action": "updated", "detail": f"已更新 {local_ver} → {remote_ver}"}
    return {"action": "update-failed", "detail": "自动更新失败",
            "hint": f"请手动执行: mtskills pull {skill_name}"}
