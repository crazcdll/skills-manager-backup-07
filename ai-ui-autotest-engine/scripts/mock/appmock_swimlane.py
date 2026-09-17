#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 环境切换、泳道管理、域名映射联动、泳道环境验证。

生命周期（严格配对）：
  开启顺序：on（服务端规则）→ enable（设备端总开关）
  关闭顺序：off（关规则）→ disable（关总开关）
"""
import json
import os

from infra.imeituan_cli import imeituan_exec
from core.errors import soft_fail
from core.util.paths import RUN_DIR, ensure_dirs, AUTO_URL_MAPPING_IDS
from core.util.json_utils import write_json_atomic, read_json
from core.util.case_utils import resolve_mis
from mock.appmock_core import (
    _cli_or_proxy,
    _cli_out, _is_sso_failure,
)
from mock.appmock_session import (
    session_env_set,
    session_swimline_list,
    session_swimline_add,
    session_swimline_switch,
    session_swimline_off,
    session_swimline_remove,
    url_mapping_list,
    url_mapping_update,
    url_mapping_set_env,
    url_mapping_delete,
)

# ═══════════════════════════════════════════════════════════════════
# 环境切换
# ═══════════════════════════════════════════════════════════════════

# 有效环境名
_VALID_ENVS = ("online", "ote", "beta", "ppe", "alpha")


def appmock_env_set(env: str, mis: str = None) -> bool:
    """切换 AppMock 代理环境。

    优先 CLI，SSO 失败走 yooz 代理。

    Args:
        env: 环境名 (online/ote/beta/ppe/alpha)
        mis: MIS 号
    Returns:
        True 成功，False 失败
    """
    if env not in _VALID_ENVS:
        print(f"APPMOCK ENV SET FAIL: 无效环境 '{env}'，可选: {', '.join(_VALID_ENVS)}")
        return False

    cli_args = ["inject", "mock", "env", "set", env]
    mis = resolve_mis(mis)
    if mis:
        cli_args += ["--user", mis]

    return _cli_or_proxy(
        f"ENV SET env={env}",
        cli_args,
        lambda: session_env_set(env),
        parse_cli=lambda r, out: print(f"APPMOCK ENV SET OK: env={env}") or True,
    )


# ═══════════════════════════════════════════════════════════════════
# 泳道管理
# ═══════════════════════════════════════════════════════════════════

def appmock_swimline_list(mis: str = None) -> list:
    """列出当前用户的所有泳道规则。

    优先 CLI，SSO 失败走 yooz 代理。

    Returns:
        泳道规则列表 [{"id": ..., "name": ..., "url": ...}, ...]
    """
    def _parse(r, out):
        try:
            result = json.loads(r.stdout)
            items = result if isinstance(result, list) else result.get("data", [])
            print(f"APPMOCK SWIMLINE LIST OK: {len(items)} rule(s)")
            return items
        except Exception:
            return []

    def _proxy():
        mis_resolved = resolve_mis(mis)
        if not mis_resolved:
            print("APPMOCK SWIMLINE LIST PROXY: 无法确定 MIS 号")
            return []
        return session_swimline_list(mis_resolved)

    return _cli_or_proxy(
        "SWIMLINE LIST",
        ["inject", "mock", "swimline", "list"],
        _proxy,
        parse_cli=_parse,
        fail_value=[],
    )


def _find_existing_swimline(url_pattern: str, lane_name: str, mis: str = None) -> dict:
    """从 swimline-list 查找匹配 url_pattern 和 lane_name 的已有泳道规则。"""
    items = appmock_swimline_list(mis=mis)
    for item in items:
        item_url = item.get("url", "") or item.get("urlPattern", "")
        item_name = item.get("name", "") or item.get("laneName", "")
        item_id = item.get("id") or item.get("ruleId")
        if item_url == url_pattern and item_name == lane_name and item_id:
            print(f"APPMOCK SWIMLINE ADD (幂等): 找到已有规则 ruleId={item_id}")
            return {"id": item_id}
    # url_pattern 匹配但 lane_name 不同也返回（同 URL 不能有两条规则）
    for item in items:
        item_url = item.get("url", "") or item.get("urlPattern", "")
        item_id = item.get("id") or item.get("ruleId")
        if item_url == url_pattern and item_id:
            item_name = item.get("name", "") or item.get("laneName", "")
            print(f"APPMOCK SWIMLINE ADD (幂等): 找到同 URL 规则 ruleId={item_id} (lane={item_name})")
            return {"id": item_id}
    print("APPMOCK SWIMLINE ADD: 未在已有规则中找到匹配项")
    return {}


def appmock_swimline_add(url_pattern: str, lane_name: str, mis: str = None) -> dict:
    """新增一条泳道规则（幂等：规则已存在时自动返回已有 ruleId）。

    优先 CLI，SSO 失败走 yooz 代理。
    如果报错「已存在对应URL的泳道配置」，自动从 swimline-list 中
    查找匹配的已有规则并返回其 id，实现幂等语义。

    Args:
        url_pattern: URL 匹配模式（如 /* 或 /mapi/search.bin）
        lane_name: 泳道名称（如 feature-abc）
        mis: MIS 号
    Returns:
        {"id": <rule_id>}（失败返回空 dict）
    """
    r = imeituan_exec(["inject", "mock", "swimline", "add", url_pattern, lane_name])
    out = _cli_out(r)
    if r.returncode == 0:
        print(f"APPMOCK SWIMLINE ADD OK: url={url_pattern} lane={lane_name}")
        # 尝试解析返回的规则 ID
        try:
            result = json.loads(r.stdout)
            return result
        except Exception:
            return {"raw": out}

    # ── 幂等处理：规则已存在时查找已有 ruleId ──
    if "已存在" in out or "already exist" in out.lower() or "duplicate" in out.lower():
        print(f"APPMOCK SWIMLINE ADD: 规则已存在，查找已有 ruleId...")
        existing = _find_existing_swimline(url_pattern, lane_name, mis)
        if existing:
            return existing

    # fallback to yooz proxy + ssoCookie
    if _is_sso_failure(out):
        print("APPMOCK SWIMLINE ADD: CLI SSO 失败，走 yooz 代理 + ssoCookie...")
        mis = resolve_mis(mis)
        if not mis:
            print("APPMOCK SWIMLINE ADD PROXY: 无法确定 MIS 号")
            return {}
        result = session_swimline_add(url_pattern, lane_name, mis)
        # 代理也可能返回已存在错误，再次尝试幂等查找
        if not result:
            existing = _find_existing_swimline(url_pattern, lane_name, mis)
            if existing:
                return existing
            print(f"APPMOCK SWIMLINE ADD FAIL: CLI SSO 失败且 yooz 代理也未成功")
        return result
    else:
        print(f"APPMOCK SWIMLINE ADD FAIL: {out}")
    return {}


def appmock_swimline_switch(rule_id, mis: str = None) -> bool:
    """切换到指定泳道规则（自动将 env 切到 alpha）。

    优先 CLI，SSO 失败走 yooz 代理。

    Args:
        rule_id: 泳道规则 ID
        mis: MIS 号
    Returns:
        True 成功，False 失败
    """
    cli_args = ["inject", "mock", "swimline", "switch", str(rule_id)]
    mis = resolve_mis(mis)
    if mis:
        cli_args += ["--user", mis]

    return _cli_or_proxy(
        f"SWIMLINE SWITCH ruleId={rule_id}",
        cli_args,
        lambda: session_swimline_switch(rule_id, mis),
        parse_cli=lambda r, out: print(f"APPMOCK SWIMLINE SWITCH OK: ruleId={rule_id}") or True,
    )


def appmock_swimline_off(mis: str = None) -> bool:
    """关闭泳道并切回线上环境（自动 env=online）。

    优先 CLI，SSO 失败走 yooz 代理。
    """
    return _cli_or_proxy(
        "SWIMLINE OFF",
        ["inject", "mock", "swimline", "off"],
        session_swimline_off,
    )


def appmock_swimline_remove(rule_id, mis: str = None) -> bool:
    """删除一条泳道规则（不可恢复）。

    优先 CLI，SSO 失败走 yooz 代理。

    Args:
        rule_id: 泳道规则 ID
    """
    return _cli_or_proxy(
        f"SWIMLINE REMOVE ruleId={rule_id}",
        ["inject", "mock", "swimline", "remove", str(rule_id)],
        lambda: session_swimline_remove(rule_id),
        parse_cli=lambda r, out: print(f"APPMOCK SWIMLINE REMOVE OK: ruleId={rule_id}") or True,
    )


# ═══════════════════════════════════════════════════════════════════
# 泳道环境验证
# ═══════════════════════════════════════════════════════════════════

def verify_swimlane_env(expected_lane: str = None, expected_rule_id=None,
                        check_url_mappings: list = None,
                        mis: str = None) -> dict:
    """程序化验证泳道环境是否正确生效。

    在 swimline-add → swimline-switch → url-mapping-ensure 全部执行完成后调用，
    主动查询服务端实际状态并与预期比对，输出明确的 VERIFY OK / VERIFY FAIL 标记。

    Args:
        expected_lane: 预期的泳道名称（如 feature-abc）
        expected_rule_id: 预期的泳道规则 ID（swimline-add 返回的 id）
        check_url_mappings: 需要验证的域名映射 URL 列表（如 ["apihotel.meituan.com/xxx"]）
        mis: MIS 号

    Returns:
        {
            "ok": bool,           # 整体是否通过
            "checks": [...],      # 每项检查的详情
            "summary": str        # 可读摘要
        }
    """
    checks = []
    all_ok = True

    # ── 1. 验证泳道规则存在且已激活 ──
    lanes = appmock_swimline_list(mis=mis)
    if not lanes:
        checks.append({
            "item": "swimline-list",
            "ok": False,
            "detail": "查询泳道列表返回空，泳道可能未配置或查询失败"
        })
        all_ok = False
    else:
        # 查找匹配的规则
        found = False
        for lane in lanes:
            lane_id = lane.get("id") or lane.get("ruleId")
            lane_name = lane.get("name", "") or lane.get("laneName", "") or lane.get("userConfig", "")
            lane_url = lane.get("url", "") or lane.get("urlPattern", "")

            # 按 rule_id 匹配（优先）
            if expected_rule_id and str(lane_id) == str(expected_rule_id):
                found = True
                checks.append({
                    "item": "swimline-rule-exists",
                    "ok": True,
                    "detail": f"规则 {lane_id} 存在（lane={lane_name}, url={lane_url}）"
                })
                # 如果同时指定了 lane name，校验是否一致
                if expected_lane and lane_name and expected_lane != lane_name:
                    checks.append({
                        "item": "swimline-lane-name-match",
                        "ok": False,
                        "detail": f"泳道名不一致：预期 '{expected_lane}'，实际 '{lane_name}'"
                    })
                    all_ok = False
                break

            # 按 lane name 匹配
            if expected_lane and lane_name == expected_lane:
                found = True
                checks.append({
                    "item": "swimline-rule-exists",
                    "ok": True,
                    "detail": f"规则 {lane_id} 存在（lane={lane_name}, url={lane_url}）"
                })
                break

        if not found:
            match_key = f"ruleId={expected_rule_id}" if expected_rule_id else f"lane={expected_lane}"
            checks.append({
                "item": "swimline-rule-exists",
                "ok": False,
                "detail": f"未找到匹配的泳道规则（{match_key}），"
                          f"当前列表: {json.dumps(lanes, ensure_ascii=False)[:300]}"
            })
            all_ok = False

    # ── 2. 验证域名映射（如有） ──
    if check_url_mappings:
        existing = url_mapping_list()
        existing_urls = {m.get("url", ""): m for m in existing}
        for url in check_url_mappings:
            url = url.strip()
            if url in existing_urls:
                m = existing_urls[url]
                sp_env = m.get("spEnv", "")
                beta_url = m.get("betaUrl", "")
                if sp_env in ("beta", "alpha"):
                    checks.append({
                        "item": f"url-mapping:{url}",
                        "ok": True,
                        "detail": f"映射已激活（spEnv={sp_env}, betaUrl={beta_url[:60]}）"
                    })
                else:
                    checks.append({
                        "item": f"url-mapping:{url}",
                        "ok": False,
                        "detail": f"映射存在但未激活（spEnv={sp_env}），请求仍走线上"
                    })
                    all_ok = False
            else:
                checks.append({
                    "item": f"url-mapping:{url}",
                    "ok": False,
                    "detail": "映射不存在，请求仍走线上"
                })
                all_ok = False

    # ── 输出结果 ──
    summary_parts = []
    for c in checks:
        mark = "✅" if c["ok"] else "❌"
        summary_parts.append(f"  {mark} {c['item']}: {c['detail']}")
    summary = "\n".join(summary_parts)

    if all_ok:
        print(f"SWIMLINE VERIFY OK\n{summary}")
    else:
        print(f"SWIMLINE VERIFY FAIL\n{summary}")

    return {"ok": all_ok, "checks": checks, "summary": summary}


# ═══════════════════════════════════════════════════════════════════
# 域名映射与泳道联动
# ═══════════════════════════════════════════════════════════════════

# 自动创建的域名映射 ID 持久化文件（跨 CLI 调用共享）
_AUTO_MAPPING_IDS_FILE = AUTO_URL_MAPPING_IDS


def _load_auto_mapping_ids() -> list:
    """从磁盘加载自动创建的域名映射 ID 列表。"""
    if os.path.isfile(_AUTO_MAPPING_IDS_FILE):
        try:
            ids = read_json(_AUTO_MAPPING_IDS_FILE, default=[])
            if isinstance(ids, list):
                return ids
        except Exception as e:
            soft_fail("infra", "AUTO_MAPPING_IDS_READ_FAILED", e)
    return []


def _save_auto_mapping_ids(ids: list):
    """将自动创建的域名映射 ID 列表写入磁盘。"""
    ensure_dirs()
    try:
        write_json_atomic(_AUTO_MAPPING_IDS_FILE, ids)
    except Exception as e:
        soft_fail("infra", "AUTO_MAPPING_IDS_WRITE_FAILED", e)
        print(f"URL_MAPPING: 持久化映射 ID 失败: {e}")


def appmock_ensure_url_mappings(mappings: list, mis: str = None,
                                sp_env: str = "beta") -> list:
    """确保域名映射已配置（泳道切换时自动调用）。

    对 mappings 列表中的每一项，检查是否已存在同 url 的映射：
      - 已存在且目标地址一致 → 跳过
      - 已存在但目标地址不一致 → 更新
      - 不存在 → 新增

    新增的映射 ID 会持久化到磁盘文件，供收尾时跨进程清理。

    Args:
        mappings: 域名映射配置列表，每项为 dict：
            {
                "url": "apihotel.meituan.com/xxx",   # 必需，线上 URL（不含协议）
                "title": "酒店预订接口映射",           # 必需，描述
                "betaUrl": "http://10.0.0.1:8080/xxx", # 测试环境 URL（带协议）
                "ppeUrl": ""                           # 预发环境 URL（带协议）
            }
        mis: MIS 号
        sp_env: 域名映射激活环境。"beta"=创建即激活（B2 默认），
                None=不设置 spEnv 字段（B1 由 swimline-switch 控制激活）。

    Returns:
        创建/更新成功的映射列表
    """

    if not mappings:
        return []

    mis = resolve_mis(mis)
    results = []
    auto_ids = _load_auto_mapping_ids()

    # 获取当前已有映射
    existing = url_mapping_list()
    existing_by_url = {m.get("url", ""): m for m in existing}

    for cfg in mappings:
        url = cfg.get("url", "").strip()
        title = cfg.get("title", "").strip()
        beta_url = cfg.get("betaUrl", "").strip()
        ppe_url = cfg.get("ppeUrl", "").strip()

        if not url or not title:
            print(f"URL_MAPPING ENSURE: 跳过无效配置（url 或 title 为空）: {cfg}")
            continue
        if not beta_url and not ppe_url:
            print(f"URL_MAPPING ENSURE: 跳过无效配置（betaUrl 和 ppeUrl 都为空）: {cfg}")
            continue

        # 检查是否已存在
        old = existing_by_url.get(url)
        mapping_id = None
        if old:
            old_beta = (old.get("betaUrl") or "").strip()
            old_ppe = (old.get("ppeUrl") or "").strip()
            mapping_id = old.get("id")
            if old_beta == beta_url and old_ppe == ppe_url:
                print(f"URL_MAPPING ENSURE: 已存在且一致，跳过: {url}")
                results.append({"action": "skipped", "url": url, "id": mapping_id})
            else:
                print(f"URL_MAPPING ENSURE: 已存在但目标不一致，更新: {url}")
                r = url_mapping_update(url, title, mis=mis, beta_url=beta_url, ppe_url=ppe_url,
                                       sp_env=sp_env)
                if not r:
                    print(f"URL_MAPPING ENSURE: 配置失败: {url}")
                    continue
                results.append(r)
                # 更新后重新查一下拿到新 ID（用于收尾清理）
                if not old:
                    refreshed = url_mapping_list()
                    for m in refreshed:
                        if m.get("url") == url and m.get("id") not in auto_ids:
                            mapping_id = m["id"]
                            auto_ids.append(mapping_id)
                            break
                else:
                    # 更新已有映射，ID 不变
                    refreshed = url_mapping_list()
                    for m in refreshed:
                        if m.get("url") == url:
                            mapping_id = m.get("id")
                            break
        else:
            # 新增
            r = url_mapping_update(url, title, mis=mis, beta_url=beta_url, ppe_url=ppe_url,
                                   sp_env=sp_env)
            if r:
                results.append(r)
                # 更新后重新查一下拿到新 ID（用于收尾清理）
                refreshed = url_mapping_list()
                for m in refreshed:
                    if m.get("url") == url and m.get("id") not in auto_ids:
                        mapping_id = m["id"]
                        auto_ids.append(mapping_id)
                        break
            else:
                print(f"URL_MAPPING ENSURE: 配置失败: {url}")
                continue

        # 激活域名映射（设置 spEnv）
        # 无论新建、更新还是跳过，都需要确保 spEnv 处于激活状态
        # 因为已存在的映射可能 spEnv=close（上次收尾时关闭了但未删除）
        if mapping_id and sp_env:
            env_value = sp_env if sp_env != "alpha" else "beta"
            if url_mapping_set_env(mapping_id, env_value):
                print(f"URL_MAPPING ENSURE: 已激活映射 id={mapping_id} env={env_value}")
            else:
                print(f"URL_MAPPING ENSURE: ⚠️ 激活映射失败 id={mapping_id}，映射可能不生效")

    # 持久化到磁盘（跨 CLI 调用可用）
    _save_auto_mapping_ids(auto_ids)

    if auto_ids:
        print(f"URL_MAPPING ENSURE: 自动创建的映射 ID: {auto_ids}")

    return results


def appmock_cleanup_url_mappings() -> int:
    """清理自动创建的域名映射（从磁盘文件读取 ID 列表）。

    在 swimline-off 收尾阶段调用。映射 ID 通过磁盘文件跨 CLI 调用共享，
    确保 ensure 和 cleanup 在不同进程中也能正确联动。

    Returns:
        成功删除的数量
    """

    auto_ids = _load_auto_mapping_ids()
    if not auto_ids:
        print("URL_MAPPING CLEANUP: 无需清理（无自动创建的域名映射）")
        return 0

    deleted = 0
    remaining = []
    for mid in auto_ids:
        if url_mapping_delete(mid):
            deleted += 1
        else:
            remaining.append(mid)

    # 更新磁盘文件（删除成功的移除，失败的保留）
    _save_auto_mapping_ids(remaining)

    total = deleted + len(remaining)
    print(f"URL_MAPPING CLEANUP: 已删除 {deleted}/{total} 条映射")

    # 全部删除成功时清理持久化文件
    if not remaining:
        try:
            os.remove(_AUTO_MAPPING_IDS_FILE)
        except OSError as e:
            soft_fail("infra", "AUTO_MAPPING_IDS_CLEANUP_FAILED", e)

    return deleted
