#!/usr/bin/env python3
"""
模块注册表 - 动态加载 factory/ 场景脚本

供 cli/ 编排层调用，避免复制 factory 脚本里的业务函数。

用法（在 cli/goods/ 里）：
    from scripts.registry import get_factory

    mod = get_factory("fullday")          # 加载 factory/fullday/create-fullday.py
    params = mod.load_template(...)
    mod.validate_constraints(params)
    mod.apply_overrides(params, overrides)

约定：
    factory/<scene>/create-<scene>.py  为每个场景的脚本路径

路径查找顺序：
    1. importlib.resources（打包安装后，从 hotel_testdata_cli.factory 包数据里找）
    2. 文件系统相对路径（本地开发 -e 模式，直接读源码目录）
"""

import importlib.util
import os
import sys
from types import ModuleType

# 本地开发时的 fallback 路径（pip install -e . 场景）
_SKILL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_FACTORY_DIR = os.path.join(_SKILL_ROOT, "factory")

_cache: dict[str, ModuleType] = {}


def _resolve_script_path(scene: str) -> str:
    """
    查找 factory/<scene>/create-<scene>.py 的绝对路径。

    优先从已安装包的数据文件里找（打包发布场景），
    找不到则降级到本地文件系统（本地开发 -e 场景）。
    """
    script_name = f"create-{scene}.py"

    # ── 方式1：importlib.resources（pip install 正式安装后） ──────────────
    try:
        from importlib.resources import files  # Python 3.9+
        pkg_path = files("hotel_testdata_cli.factory").joinpath(scene).joinpath(script_name)
        # as_file() 保证在 zip 包等环境下也能得到真实文件路径
        from importlib.resources import as_file
        with as_file(pkg_path) as p:
            if p.exists():
                return str(p)
    except (ModuleNotFoundError, TypeError, FileNotFoundError):
        pass

    # ── 方式2：文件系统（本地 -e 开发模式） ──────────────────────────────
    fs_path = os.path.join(_FACTORY_DIR, scene, script_name)
    if os.path.isfile(fs_path):
        return fs_path

    raise FileNotFoundError(
        f"[registry] factory 脚本不存在: {scene}/{script_name}\n"
        f"  已尝试包数据路径（hotel_testdata_cli.factory.{scene}）\n"
        f"  已尝试文件系统路径：{fs_path}"
    )


def get_factory(scene: str) -> ModuleType:
    """
    按场景名加载对应的 factory 脚本，返回模块对象。

    参数：
        scene - 场景名，如 "fullday"、"hourly"
                对应 factory/<scene>/create-<scene>.py

    返回：
        加载后的模块，可直接调用 load_template / validate_constraints /
        apply_overrides / _try_parse_value / _online_with_inventory_retry 等函数

    异常：
        FileNotFoundError - 脚本不存在
        ImportError       - 模块加载失败
    """
    if scene in _cache:
        return _cache[scene]

    script_path = _resolve_script_path(scene)

    module_name = f"_hotel_factory_{scene.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"[registry] 无法加载 factory 脚本: {script_path}")

    mod = importlib.util.module_from_spec(spec)
    # 注入 sys.modules 防止 factory 脚本内部的相对 import 出错
    sys.modules[module_name] = mod

    # factory 脚本依赖 sys.path 里有 skill 根目录（用于 from scripts.xxx import）
    if _SKILL_ROOT not in sys.path:
        sys.path.insert(0, _SKILL_ROOT)

    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    except Exception as e:
        sys.modules.pop(module_name, None)
        raise ImportError(f"[registry] 加载 factory/{scene} 失败: {e}") from e

    _cache[scene] = mod
    return mod

