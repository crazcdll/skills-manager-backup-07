#!/usr/bin/env python3
"""上线后刷新 SPU 套餐产品缓存与 POI-SPU 映射缓存。

通过 goodsoperator-cli（hthotel-ops-product）触发缓存同步：
  1. SPU 套餐产品缓存（按 SPU 维度）
       hthotel-ops-product --env <env> goodsquery query-spu --spu-id <spuId> --sync
  2. POI-SPU 映射缓存（按 POI 维度，对每个 poiId 逐个刷新）
       hthotel-ops-product --env <env> goodsquery query-poi-spu-mapping --poi-id <poiId> --sync

设计为 best-effort 后置动作：
  - CLI 未安装时打印安装提示并返回 False，不抛异常、不中断主流程。
  - 单条刷新失败仅记录告警，继续刷新其余 POI，最终返回汇总成功标志。
"""

from __future__ import annotations

import shutil
import subprocess
import sys

# goodsoperator-cli 安装路径（按用户环境约定）
_INSTALL_HINT = (
    "pip3 install -e "
    "/Users/baichenyu/.catpaw/skills/skills-market/goodsoperator-cli -q"
)

# CLI 返回 exit 0 但把后端错误包在 stdout 里打印的失败特征。
# goodsoperator-cli 同步成功输出形如 `同步完成: {'data': {...}, 'status': 0}`，
# 认证/业务失败时 status=401 且含 auth failed 等关键词，但退出码仍为 0，
# 因此不能仅看 returncode，必须额外检测这些关键词。
_FAILURE_MARKERS = (
    "auth failed",
    "ssoid 不存在",
    "'status': 401",
    "'code': 30002",
    "未授权",
    "未登录",
)


def _run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    """执行命令并实时回显输出，返回 CompletedProcess。"""
    print(f"    $ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _is_failure(result: subprocess.CompletedProcess) -> tuple[bool, str]:
    """判断单条刷新是否失败。

    goodsoperator-cli 即使后端 401 也返回 exit 0，需结合 stdout/stderr 关键词
    综合判断。返回 (是否失败, 失败摘要)。
    """
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        return True, output.strip()
    for marker in _FAILURE_MARKERS:
        if marker in output:
            return True, output.strip()
    return False, ""


# 认证失败子集（用于触发自动 reauth 重试）
_AUTH_FAILURE_MARKERS = (
    "auth failed",
    "ssoid 不存在",
    "'status': 401",
    "'code': 30002",
)


def _is_auth_failure(msg: str) -> bool:
    """判断失败是否源于认证过期（可重试 reauth）。"""
    return any(marker in msg for marker in _AUTH_FAILURE_MARKERS)


def _try_reauth(cli: str, env: str) -> bool:
    """Cookie 过期时自动调用 auth refresh 重新获取（不传 cookie，走 CLI 自动获取）。

    成功前提（goodsoperator-cli macOS 逻辑）：
      - prod 环境：可走 MOA SSO 无感换票
      - test 环境：需 Chrome 已登录 goodsoperator.hotel.test.sankuai.com 且已装 pycryptodome
    成功返回 True；失败打印手动获取指引后返回 False。
    """
    cmd = [cli, "--env", env, "auth", "refresh"]
    print(f"    $ {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode == 0 and "成功" in out and "无法自动获取" not in out:
        print(f"  ✓ Cookie 自动刷新成功", file=sys.stderr)
        return True
    domain = (
        "goodsoperator.hotel.test.sankuai.com"
        if env == "test"
        else "goodsoperator.hotel.sankuai.com"
    )
    print(f"  ✗ Cookie 自动刷新失败，请手动执行：", file=sys.stderr)
    print(
        f'    {cli} --env {env} auth refresh --cookie "<你的_cookie>"',
        file=sys.stderr,
    )
    print(f"  获取方式：浏览器打开 https://{domain} 登录，", file=sys.stderr)
    print(
        f"    F12 → Network → 任意请求 → Headers → Cookie，复制完整值",
        file=sys.stderr,
    )
    return False


def refresh_spu_cache(
    spu_id: str,
    poi_ids: list[str] | None,
    env: str = "test",
) -> bool:
    """刷新 SPU 缓存 + POI-SPU 映射缓存。

    参数:
        spu_id:  超团 spuId
        poi_ids: 需要刷新 POI-SPU 映射缓存的门店ID列表；非通兑超团传 [poiId]，
                 通兑超团传所有 shopIds；为空则仅刷新 SPU 缓存。
        env:     goodsoperator-cli 环境，test 或 prod（默认 test，与本 skill
                 创建商品所用的 mta.hotel.test.sankuai.com 环境一致）

    返回:
        全部刷新成功返回 True；任一失败或 CLI 缺失返回 False。
        始终不抛异常，调用方无需 try/except。
    """
    if not spu_id:
        print("  ⚠️ spuId 为空，跳过 SPU 缓存刷新", file=sys.stderr)
        return False

    cli = shutil.which("hthotel-ops-product")
    if not cli:
        print("  ⚠️ 未找到 hthotel-ops-product，跳过 SPU 缓存刷新", file=sys.stderr)
        print(f"    请先安装 goodsoperator-cli：{_INSTALL_HINT}", file=sys.stderr)
        return False

    all_ok = True
    reauth_attempted = False

    def _refresh_one(cmd: list[str]) -> tuple[bool, str]:
        """执行单条刷新；遇认证失败且未重认证过时，自动 auth refresh 后重试一次。

        返回 (是否成功, 失败摘要)。reauth_attempted 保证整个流程最多自动重认证一次。
        """
        nonlocal reauth_attempted
        result = _run_cmd(cmd)
        failed, msg = _is_failure(result)
        if failed and not reauth_attempted and _is_auth_failure(msg):
            reauth_attempted = True
            print(
                "  ⚠️ 检测到认证失败，尝试自动刷新 Cookie（auth refresh）...",
                file=sys.stderr,
            )
            if _try_reauth(cli, env):
                result = _run_cmd(cmd)
                failed, msg = _is_failure(result)
        return (not failed), msg

    # ── 1. 刷新 SPU 套餐产品缓存 ──────────────────────────────────────────
    print(f"\n  ⏳ 刷新 SPU 套餐产品缓存（spuId={spu_id}, env={env}）...", file=sys.stderr)
    cmd = [
        cli, "--env", env,
        "goodsquery", "query-spu",
        "--spu-id", str(spu_id),
        "--sync",
    ]
    ok, msg = _refresh_one(cmd)
    if not ok:
        all_ok = False
        print(f"  ✗ SPU 缓存刷新失败: {msg}", file=sys.stderr)
    else:
        print(f"  ✓ SPU 缓存刷新完成", file=sys.stderr)

    # ── 2. 刷新 POI-SPU 映射缓存（逐个门店）──────────────────────────────
    for poi_id in poi_ids or []:
        if not poi_id:
            continue
        print(
            f"  ⏳ 刷新 POI-SPU 映射缓存（poiId={poi_id}, env={env}）...",
            file=sys.stderr,
        )
        cmd = [
            cli, "--env", env,
            "goodsquery", "query-poi-spu-mapping",
            "--poi-id", str(poi_id),
            "--sync",
        ]
        ok, msg = _refresh_one(cmd)
        if not ok:
            all_ok = False
            print(
                f"  ✗ POI-SPU 映射缓存刷新失败(poiId={poi_id}): {msg}",
                file=sys.stderr,
            )
        else:
            print(
                f"  ✓ POI-SPU 映射缓存刷新完成(poiId={poi_id})",
                file=sys.stderr,
            )

    return all_ok

