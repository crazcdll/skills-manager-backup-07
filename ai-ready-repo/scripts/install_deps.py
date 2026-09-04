#!/usr/bin/env python3
"""
AI-Ready Assessor 依赖安装引导脚本

用法：
  python3 scripts/install_deps.py              # 检测并引导安装所有依赖
  python3 scripts/install_deps.py playwright   # 仅处理指定依赖（可多个）
"""
import subprocess
import sys
import os

SKILL_DIRS = [
    os.path.expanduser("~/.claude/skills"),
    os.path.expanduser("~/.openclaw/workspace/.claude/skills"),
    "/root/.openclaw/workspace/.claude/skills",
    os.path.expanduser("~/.catpaw/skills/skills-market"),
]


def _skill_installed(name):
    return any(os.path.isdir(os.path.join(d, name)) for d in SKILL_DIRS)


def _check_playwright():
    r = subprocess.run(
        ["python3", "-c", "from playwright.sync_api import sync_playwright"],
        capture_output=True,
    )
    if r.returncode != 0:
        return False
    r2 = subprocess.run(
        [
            "python3",
            "-c",
            (
                "from playwright.sync_api import sync_playwright\n"
                "p=sync_playwright().start()\n"
                "b=p.chromium.launch()\n"
                "b.close()\n"
                "p.stop()"
            ),
        ],
        capture_output=True,
    )
    return r2.returncode == 0


def _check_pyyaml():
    result = subprocess.run(
        ["python3", "-c", "import yaml"],
        capture_output=True,
    )
    return result.returncode == 0


DEPS = {
    "pyyaml": {
        "description": "解析 pnpm workspace 清单",
        "install_cmd": "pip3 install 'PyYAML>=6,<7'",
        "check": _check_pyyaml,
    },
    "code-repo-search": {
        "description": "远程仓库模式必须",
        "install_cmd": "mtskills i code-repo-search",
        "check": lambda: _skill_installed("code-repo-search"),
    },
    "citadel": {
        "description": "报告保存到学城（缺失时降级为本地保存）",
        "install_cmd": "npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com",
        "check": lambda: _skill_installed("citadel"),
    },
    "playwright": {
        "description": "上报时自动弹出 SSO 登录浏览器（缺失时回退手动输入 token）",
        "install_cmd": "pip3 install playwright && playwright install chromium",
        "check": _check_playwright,
    },
}


def prompt_install(name):
    dep = DEPS[name]
    print(f"\n⚠️  {name} 未安装 — {dep['description']}")
    print(f"   安装命令：{dep['install_cmd']}")
    try:
        answer = input("   是否现在安装？[Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n   ⏭️  非交互环境，跳过安装")
        return False
    if answer in ("", "y", "yes"):
        print(f"   正在安装 {name}...")
        result = subprocess.run(dep["install_cmd"], shell=True)
        if result.returncode == 0:
            print(f"   ✅ {name} 安装成功")
            return True
        else:
            print(f"   ❌ 安装失败，请手动执行：{dep['install_cmd']}")
            return False
    else:
        print(f"   ⏭️  跳过安装 {name}")
        return False


def check_all(targets=None):
    results = {}
    for name, dep in DEPS.items():
        if targets and name not in targets:
            continue
        if dep["check"]():
            print(f"✅ {name} 已就绪")
            results[name] = True
        else:
            installed = prompt_install(name)
            # 安装后重新检测，而非直接信任退出码
            results[name] = dep["check"]() if installed else False
    return results


if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else None
    unknown = [t for t in (targets or []) if t not in DEPS]
    if unknown:
        print(f"❌ 未知依赖名称：{', '.join(unknown)}")
        print(f"   可用：{', '.join(DEPS.keys())}")
        sys.exit(2)

    results = check_all(targets)
    missing = [k for k, v in results.items() if not v]
    if missing:
        print(f"\n⚠️  以下依赖仍未就绪：{', '.join(missing)}")
        sys.exit(1)
    else:
        print("\n✅ 所有依赖已就绪")
        sys.exit(0)
