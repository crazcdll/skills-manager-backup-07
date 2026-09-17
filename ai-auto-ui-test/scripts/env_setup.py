#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一环境准备入口（全自动启动器）。

只安装 ai-auto-ui-test 后，每次执行自动化测试前调用本脚本，自动完成：
  1. 当前 Skill 自身更新
  2. 安装/更新依赖的 Skill（ai-app-flow、ai-ui-autotest-engine）
  3. 输出环境就绪报告

省略下游运行时环境检测（ai-ui-autotest-engine 执行阶段 0 会自行 check-deps），
避免重复检测导致卡顿假象。

用法：
  python3 scripts/env_setup.py

本脚本本身只依赖 Python 标准库，零外部依赖。
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)
MAIN_SKILL_NAME = "ai-auto-ui-test"
REQUIRED_NODE_MAJOR = 20
NPM_REGISTRY = "http://r.npm.sankuai.com"

# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def _info(msg):
    print(f"  ℹ️  {msg}")

def _ok(msg):
    print(f"  ✅ {msg}")

def _warn(msg):
    print(f"  ⚠️  {msg}")

def _fail(msg):
    print(f"  ❌ {msg}")

def _step_header(step_num, total, title):
    print(f"\n{'=' * 55}")
    print(f"  [{step_num}/{total}] {title}")
    print(f"{'=' * 55}")

def run_cmd(cmd, cwd=None, timeout=300, capture=False):
    """执行 shell 命令，返回 (returncode, stdout, stderr)。

    默认 capture=False 让子进程输出直接透传到终端，用户可实时看到进度。
    需要解析输出内容时（如版本号提取）请传 capture=True。
    """
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd or SKILL_DIR,
            timeout=timeout,
            capture_output=capture,
            text=True,
        )
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"超时 ({timeout}s)"
    except FileNotFoundError as e:
        return -2, "", f"命令未找到: {e}"
    except Exception as e:
        return -3, "", str(e)

# ─── 工作区查找 ───────────────────────────────────────────────────────────────

def _find_workspace_root():
    """从 SKILL_DIR 向上查找项目根目录（包含 .claude 或 .catpaw 的目录）。

    SKILL_DIR 一定存在（脚本正在运行），os.getcwd() 仅作为额外候选，
    用 try/except 保护避免工作目录已被删除时崩溃。
    """
    candidates = [SKILL_DIR]
    try:
        candidates.append(os.getcwd())
    except FileNotFoundError:
        pass
    for candidate in candidates:
        cwd = candidate
        for _ in range(10):
            if os.path.isdir(os.path.join(cwd, '.claude')) or os.path.isdir(os.path.join(cwd, '.catpaw')):
                return os.path.abspath(cwd)
            parent = os.path.dirname(cwd)
            if parent == cwd:
                break
            cwd = parent
    return SKILL_DIR

def find_skill_dir(name):
    """在项目范围及全局范围内查找已安装的 Skill 目录。"""
    root = _find_workspace_root()
    home = os.path.expanduser("~")
    search_dirs = [
        # 项目级安装
        os.path.join(root, '.claude', 'skills', name),
        os.path.join(root, '.claude', 'skills', 'skills-market', name),
        os.path.join(root, '.catpaw', 'skills', name),
        os.path.join(root, '.catpaw', 'skills', 'skills-market', name),
        # 同级目录
        os.path.join(SKILL_DIR, '..', name),
        # 全局安装
        os.path.join(home, '.catpaw', 'skills', name),
        os.path.join(home, '.catpaw', 'skills', 'skills-market', name),
        os.path.join(home, '.claude', 'skills', name),
        os.path.join(home, '.claude', 'skills', 'skills-market', name),
        os.path.join(home, '.cursor', 'skills', name),
    ]
    seen = set()
    for d in search_dirs:
        normalized = os.path.normpath(d)
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.isfile(os.path.join(d, 'SKILL.md')):
            return d
    return None

def get_skill_version(skill_dir):
    """从 SKILL.md 的 Frontmatter（--- 之间的 YAML 块）中读取 skillhub.version。"""
    skill_md = os.path.join(skill_dir, 'SKILL.md')
    if not os.path.isfile(skill_md):
        return "未知"
    try:
        with open(skill_md, encoding='utf-8') as f:
            in_frontmatter = False
            for line in f:
                stripped = line.rstrip()
                if stripped == '---':
                    if in_frontmatter:
                        break  # Frontmatter 结束
                    in_frontmatter = True
                    continue
                if in_frontmatter and 'skillhub.version:' in stripped:
                    val = stripped.split('skillhub.version:', 1)[1].strip().strip('"\'')
                    if val:
                        return val
    except Exception:
        pass
    return "未知"

# ─── Node.js 版本管理 ─────────────────────────────────────────────────────────

def _current_node_major():
    """获取当前 PATH 中 node 的主版本号。"""
    try:
        r = subprocess.run(["node", "-v"], capture_output=True, text=True, timeout=15)
        ver = (r.stdout or "").strip().lstrip("v")
        return int(ver.split(".")[0]) if ver else None
    except Exception:
        return None

def _detect_node_manager():
    """探测可用的 Node 版本管理器，返回 shell 前缀。"""
    home = os.path.expanduser("~")
    nvm_script = os.path.join(home, ".nvm", "nvm.sh")
    if os.path.isfile(nvm_script):
        return f'source "{nvm_script}" && nvm install {REQUIRED_NODE_MAJOR} >/dev/null 2>&1 && nvm use {REQUIRED_NODE_MAJOR}'

    for mgr in ["fnm", "volta", "asdf"]:
        if shutil.which(mgr):
            if mgr == "fnm":
                return f'eval "$(fnm env --use-on-cd)" && fnm install {REQUIRED_NODE_MAJOR} >/dev/null && fnm use {REQUIRED_NODE_MAJOR}'
            elif mgr == "volta":
                return f'volta install node@{REQUIRED_NODE_MAJOR} >/dev/null 2>&1 && volta run node@{REQUIRED_NODE_MAJOR}'
            elif mgr == "asdf":
                return f'asdf install nodejs {REQUIRED_NODE_MAJOR}.x >/dev/null 2>&1 || true && asdf shell nodejs {REQUIRED_NODE_MAJOR}.x'
    return None

def _run_with_node(cmd, timeout=300, cwd=None, capture=False):
    """在 Node >= 20 环境下执行命令，低于要求时自动切换版本。"""
    major = _current_node_major()
    if major is not None and major >= REQUIRED_NODE_MAJOR:
        return run_cmd(cmd, timeout=timeout, cwd=cwd, capture=capture)

    prefix = _detect_node_manager()
    if prefix:
        return run_cmd(f'/bin/bash -lc \'{prefix} && {cmd}\'', timeout=timeout, cwd=cwd, capture=capture)
    else:
        return run_cmd(cmd, timeout=timeout, cwd=cwd, capture=capture)

# ─── mtskills CLI ─────────────────────────────────────────────────────────────

def _ensure_mtskills():
    """确保 mtskills CLI 可用，缺失时自动安装。"""
    if shutil.which("mtskills"):
        return True
    _info("正在安装 mtskills CLI...")
    rc, out, err = _run_with_node(
        f'npm i -g @mtfe/mtskills@latest --registry={NPM_REGISTRY}',
        timeout=120
    )
    if rc == 0 and shutil.which("mtskills"):
        _ok("mtskills CLI 安装完成")
        return True
    _warn(f"mtskills 安装失败，请手动执行: npm i -g @mtfe/mtskills@latest --registry={NPM_REGISTRY}")
    return False


def _ensure_oa_skills():
    """确保 oa-skills (citadel) CLI 可用，缺失时自动安装。"""
    if shutil.which("oa-skills"):
        return True
    _info("正在安装 oa-skills CLI...")
    rc, out, err = _run_with_node(
        f'npm i -g @it/oa-skills@latest --registry={NPM_REGISTRY}',
        timeout=120
    )
    if rc == 0 and shutil.which("oa-skills"):
        _ok("oa-skills CLI 安装完成")
        return True
    _warn(f"oa-skills 安装失败，请手动执行: npm i -g @it/oa-skills@latest --registry={NPM_REGISTRY}")
    return False

def _mtskills(args_str, timeout=120, capture=False):
    """执行 mtskills 命令，返回 (returncode, stdout, stderr)。

    使用项目根目录作为工作目录，确保依赖 Skill 安装到 `.claude/skills/` 同级目录。
    """
    ws_root = _find_workspace_root()
    return _run_with_node(f'mtskills {args_str}', timeout=timeout, cwd=ws_root, capture=capture)

# ─── 步骤 1：自身更新 ─────────────────────────────────────────────────────────

def _compare_versions(v1, v2):
    """比较两个版本号，v1 < v2 返回 -1，相等返回 0，v1 > v2 返回 1。"""
    if not v1 or not v2:
        return 0
    parts1 = re.sub(r'^v', '', v1).split('.')
    parts2 = re.sub(r'^v', '', v2).split('.')
    for i in range(max(len(parts1), len(parts2))):
        p1 = int(parts1[i]) if i < len(parts1) and parts1[i].isdigit() else 0
        p2 = int(parts2[i]) if i < len(parts2) and parts2[i].isdigit() else 0
        if p1 < p2:
            return -1
        if p1 > p2:
            return 1
    return 0

def _self_update():
    """检查当前 Skill 是否有远端更新，有则自动更新。"""
    _step_header(1, 3, "当前 Skill 自身更新")

    if not _ensure_mtskills():
        _warn("mtskills 不可用，跳过自身更新")
        return

    # 获取本地版本
    local_version = get_skill_version(SKILL_DIR)

    # 查询远端信息
    rc, out, err = _mtskills(f"search {MAIN_SKILL_NAME}", timeout=30, capture=True)
    if rc != 0:
        _warn(f"无法查询远端版本信息（exit={rc}），跳过自身更新")
        return

    # 解析远端版本号
    remote_version = None
    for line in out.split("\n"):
        if line.startswith("version:"):
            remote_version = line.split(":", 1)[1].strip()
            break

    if remote_version and local_version != "未知":
        if _compare_versions(local_version, remote_version) < 0:
            _info(f"发现新版本: {local_version} → {remote_version}，正在更新...")
            rc, _, _ = _mtskills(f"pull {MAIN_SKILL_NAME}", timeout=120)
            if rc == 0:
                new_ver = get_skill_version(SKILL_DIR)
                _ok(f"更新完成: {local_version} → {new_ver}")
                return
            else:
                _warn("自动更新失败，请手动执行: mtskills pull ai-auto-ui-test")
                return
        else:
            _ok(f"已是最新版本 ({local_version})")
            return

    # 无 version 字段时，回退到时间戳比对
    remote_ts = None
    for line in out.split("\n"):
        if line.startswith("updated:"):
            try:
                remote_ts = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
            break

    if remote_ts is None:
        _ok(f"当前版本 {local_version}（无法比对远端，跳过更新）")
        return

    # 用本地 SKILL.md 修改时间做 fallback 比对
    try:
        local_mtime = int(os.path.getmtime(os.path.join(SKILL_DIR, 'SKILL.md')) * 1000)
        if remote_ts > local_mtime:
            _info("检测到远端有更新，正在更新...")
            rc, _, _ = _mtskills(f"pull {MAIN_SKILL_NAME}", timeout=120)
            if rc == 0:
                new_ver = get_skill_version(SKILL_DIR)
                _ok(f"更新完成，当前版本: {new_ver}")
            else:
                _warn("自动更新失败，请手动执行: mtskills pull ai-auto-ui-test")
        else:
            _ok(f"已是最新版本 ({local_version})")
    except OSError:
        _ok(f"当前版本 {local_version}")

# ─── 步骤 2：安装/更新依赖 Skill ──────────────────────────────────────────────

def _install_or_update_skill(name):
    """安装或更新单个 Skill。已存在时检查版本，有更新则自动升级。"""
    skill_dir = find_skill_dir(name)

    if not skill_dir:
        # 不存在 → 安装
        _info(f"正在安装 {name}...")
        rc, out, err = _mtskills(f"i -y {name}", timeout=120)
        if rc != 0:
            _fail(f"{name} 安装失败（exit={rc}）")
            return False
        skill_dir = find_skill_dir(name)
        if skill_dir:
            _ok(f"{name} 安装完成，版本 v{get_skill_version(skill_dir)}")
            return True
        _warn(f"{name} 安装命令已执行，但未找到安装目录")
        return False

    # 已存在 → 检查版本
    local_version = get_skill_version(skill_dir)

    # 查询远端版本
    rc, out, err = _mtskills(f"search {name}", timeout=30, capture=True)
    if rc != 0:
        _ok(f"{name} 已存在（v{local_version}），无法查询远端版本，跳过更新")
        return True

    # 从远端搜索结果解析 version 字段
    remote_version = None
    for line in out.split("\n"):
        if line.startswith("version:"):
            remote_version = line.split(":", 1)[1].strip()
            break

    if remote_version and local_version != "未知":
        if _compare_versions(local_version, remote_version) < 0:
            _info(f"{name} 发现新版本: v{local_version} → v{remote_version}，正在更新...")
            rc, _, _ = _mtskills(f"pull {name}", timeout=120)
            if rc == 0:
                new_ver = get_skill_version(skill_dir)
                _ok(f"{name} 更新完成: v{local_version} → v{new_ver}")
                return True
            else:
                _warn(f"{name} 自动更新失败，请手动执行: mtskills pull {name}")
                return True
        else:
            _ok(f"{name} 已是最新版本（v{local_version}）")
            return True

    # 无 version 字段时，回退到时间戳比对
    remote_ts = None
    for line in out.split("\n"):
        if line.startswith("updated:"):
            try:
                remote_ts = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
            break

    if remote_ts is None:
        _ok(f"{name} 已存在（v{local_version}），无法比对远端，跳过更新")
        return True

    try:
        local_mtime = int(os.path.getmtime(os.path.join(skill_dir, 'SKILL.md')) * 1000)
        if remote_ts > local_mtime:
            _info(f"{name} 检测到远端有更新，正在更新...")
            rc, _, _ = _mtskills(f"pull {name}", timeout=120)
            if rc == 0:
                new_ver = get_skill_version(skill_dir)
                _ok(f"{name} 更新完成，当前版本: v{new_ver}")
            else:
                _warn(f"{name} 自动更新失败，请手动执行: mtskills pull {name}")
        else:
            _ok(f"{name} 已是最新版本（v{local_version}）")
    except OSError:
        _ok(f"{name} 已存在（v{local_version}）")

    return True

def _install_deps():
    """安装/更新所有依赖的 Skill。"""
    _step_header(2, 3, "安装/更新依赖的 Skill")

    if not _ensure_mtskills():
        _fail("mtskills 不可用，无法安装依赖")
        _warn("请确保网络通畅后手动安装: npm i -g @mtfe/mtskills@latest --registry={}".format(NPM_REGISTRY))
        sys.exit(1)

    deps = [
        {"name": "ai-app-flow", "required": True},
        {"name": "ai-ui-autotest-engine", "required": True},
    ]

    all_ok = True
    for dep in deps:
        if not _install_or_update_skill(dep["name"]):
            if dep["required"]:
                all_ok = False

    if not all_ok:
        _fail("部分必选依赖安装失败，请检查网络或手动安装")
        _info("手动安装: mtskills i -y ai-app-flow && mtskills i -y ai-ui-autotest-engine")
        sys.exit(1)

    _ok("依赖 Skill 安装/检查完成")

    # 安装 oa-skills（citadel CLI），用于读取学城文档
    _info("检查 oa-skills（citadel CLI）...")
    _ensure_oa_skills()


# ─── 步骤 3：环境就绪报告 ─────────────────────────────────────────────────────

def _report():
    """输出环境就绪报告。"""
    _step_header(3, 3, "环境就绪报告")

    all_ok = True
    checks = []

    for name in ["ai-app-flow", "ai-ui-autotest-engine"]:
        d = find_skill_dir(name)
        if d:
            ver = get_skill_version(d)
            checks.append((name, "✅ 已就绪", ver))
        else:
            checks.append((name, "❌ 未安装", "—"))
            all_ok = False

    print()
    for name, status, ver in checks:
        print(f"    {name:<30} {status:<12} v{ver}")

    oa_ok = shutil.which("oa-skills") is not None
    print(f"    {'oa-skills (citadel)':<30} {'✅ 可用' if oa_ok else '❌ 未安装':<12} {'—'}")

    rc, out, _ = run_cmd("python3 --version", capture=True, cwd=SKILL_DIR)
    py_ok = rc == 0 and out.strip()
    py_ver = out.strip() if py_ok else "未安装"
    print(f"    {'Python 3':<30} {'✅ 可用' if py_ok else '❌ 未安装':<12} {py_ver}")

    rc, out, _ = run_cmd("node --version", capture=True, cwd=SKILL_DIR)
    node_ok = rc == 0 and out.strip()
    node_ver = out.strip() if node_ok else "未安装"
    print(f"    {'Node.js':<30} {'✅ 可用' if node_ok else '❌ 未安装':<12} {node_ver}")

    print()
    if all_ok and py_ok and node_ok:
        print("  🎉 所有依赖已就绪，可以开始执行自动化测试！")
    else:
        print("  ⚠️  部分依赖未就绪，请手动处理后重试")

    return all_ok

# ─── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  🔧 自动化 UI 测试 — 全自动环境准备启动")
    print("  Skill: ai-auto-ui-test")
    print("=" * 55)

    # 强制 stdout 行缓冲，确保 print 实时显示
    sys.stdout.reconfigure(line_buffering=True)

    _self_update()
    _install_deps()
    ok = _report()

    print()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()