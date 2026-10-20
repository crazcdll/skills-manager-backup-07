#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 环境切换、泳道管理、域名映射联动、泳道环境验证。

生命周期（严格配对）：
  开启顺序：on（服务端规则）→ enable（设备端总开关）
  关闭顺序：off（关规则）→ disable（关总开关）
"""
import json
import os

from shared.errors import soft_fail
from shared.paths import ensure_dirs, auto_url_mapping_ids_path
from shared.json_utils import write_json_atomic, read_json
from shared.case_utils import resolve_mock_domain
from platform.appmock.session import (
    session_env_set,
    session_swimline_list,
    session_swimline_add,
    session_swimline_switch,
    session_swimline_off,
    session_swimline_remove,
    url_mapping_list,
    url_mapping_add,
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
    """切换「指定工作域」的 AppMock 代理环境。

    统一走 yooz 代理接口（代理 side 强制要求 userDomain）。

    Args:
        env: 环境名 (online/ote/beta/ppe/alpha)
        mis: 目标工作域 MIS 号
    Returns:
        True 成功，False 失败
    """
    if env not in _VALID_ENVS:
        print(f"APPMOCK ENV SET FAIL: 无效环境 '{env}'，可选: {', '.join(_VALID_ENVS)}")
        return False

    mis = resolve_mock_domain(mis)
    if not mis:
        print("APPMOCK ENV SET FAIL: 无法确定目标工作域 MIS")
        return False
    return session_env_set(env, mis)


# ═══════════════════════════════════════════════════════════════════
# 泳道管理
# ═══════════════════════════════════════════════════════════════════

def appmock_swimline_list(mis: str = None) -> list:
    """列出指定工作域的所有泳道规则。

    统一走 yooz 代理接口。

    Returns:
        泳道规则列表 [{"id": ..., "name": ..., "url": ...}, ...]
    """
    mis_resolved = resolve_mock_domain(mis)
    if not mis_resolved:
        print("APPMOCK SWIMLINE LIST: 无法确定目标工作域 MIS")
        return []
    return session_swimline_list(mis_resolved)


def _find_existing_swimline(url_pattern: str, lane_name: str, mis: str = None) -> dict:
    """从 swimline-list 查找匹配 url_pattern 和 lane_name 的已有泳道规则。"""
    items = appmock_swimline_list(mis=mis)
    for item in items:
        item_url = item.get("url", "") or item.get("urlPattern", "")
        item_name = item.get("configs", "") or item.get("name", "") or item.get("laneName", "")
        item_id = item.get("id") or item.get("ruleId")
        if item_url == url_pattern and item_name == lane_name and item_id:
            print(f"APPMOCK SWIMLINE ADD (幂等): 找到已有规则 ruleId={item_id}")
            return {"id": item_id}
    # url_pattern 匹配但 lane_name 不同也返回（同 URL 不能有两条规则）
    for item in items:
        item_url = item.get("url", "") or item.get("urlPattern", "")
        item_id = item.get("id") or item.get("ruleId")
        if item_url == url_pattern and item_id:
            item_name = item.get("configs", "") or item.get("name", "") or item.get("laneName", "")
            print(f"APPMOCK SWIMLINE ADD (幂等): 找到同 URL 规则 ruleId={item_id} (lane={item_name})")
            return {"id": item_id}
    print("APPMOCK SWIMLINE ADD: 未在已有规则中找到匹配项")
    return {}


def appmock_swimline_add(url_pattern: str, lane_name: str, mis: str = None) -> dict:
    """新增一条泳道规则（幂等：规则已存在时自动返回已有 ruleId）。

    统一走 yooz 代理接口（不再经过 imeituan CLI）。
    如果报错「已存在对应URL的泳道配置」，自动从 swimline-list 中
    查找匹配的已有规则并返回其 id，实现幂等语义。

    Args:
        url_pattern: URL 匹配模式（如 /* 或 /mapi/search.bin）
        lane_name: 泳道名称（如 feature-abc）
        mis: MIS 号
    Returns:
        {"id": <rule_id>}（失败返回空 dict）
    """
    mis = resolve_mock_domain(mis)
    if not mis:
        print("APPMOCK SWIMLINE ADD: 无法确定目标工作域 MIS")
        return {}

    result = session_swimline_add(url_pattern, lane_name, mis)
    if result:
        print(f"APPMOCK SWIMLINE ADD OK: url={url_pattern} lane={lane_name}")
        return result

    # 幂等：规则已存在（或代理未成功）时反查已有 ruleId
    existing = _find_existing_swimline(url_pattern, lane_name, mis)
    if existing:
        return existing
    print("APPMOCK SWIMLINE ADD FAIL: yooz 代理未成功")
    return {}


def appmock_swimline_switch(rule_id, mis: str = None) -> bool:
    """切换到指定泳道规则（自动将 env 切到 alpha）。

    统一走 yooz 代理接口（不再经过 imeituan CLI）。

    Args:
        rule_id: 泳道规则 ID
        mis: MIS 号
    Returns:
        True 成功，False 失败
    """
    mis = resolve_mock_domain(mis)
    if not mis:
        print("APPMOCK SWIMLINE SWITCH: 无法确定目标工作域 MIS")
        return False

    return session_swimline_switch(rule_id, mis)


def appmock_swimline_off(mis: str = None) -> bool:
    """关闭泳道并切回线上环境（自动 env=online）。

    统一走 yooz 代理接口；env/set 在代理侧强制要求目标工作域。
    """
    domain = resolve_mock_domain(mis)
    if not domain:
        print("APPMOCK SWIMLINE OFF: 无法确定目标工作域 MIS")
        return False
    return session_swimline_off(mis=domain)


def appmock_swimline_remove(rule_id, mis: str = None) -> bool:
    """删除一条泳道规则（不可恢复）。

    统一走 yooz 代理接口；上游 deleteConfig 强制要求 userDomain。
    """
    domain = resolve_mock_domain(mis)
    if not domain:
        print("APPMOCK SWIMLINE REMOVE: 无法确定目标工作域 MIS")
        return False
    return session_swimline_remove(rule_id, mis=domain)


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
            lane_name = (lane.get("configs", "") or lane.get("name", "")
                         or lane.get("laneName", "") or lane.get("userConfig", ""))
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
    # 注：getUserUrlMapping.api 不回读 spEnv，无法程序化确认激活态；这里只校验映射存在，
    #     激活由 ensure 的 updateUrlEnv 调用结果保证。
    if check_url_mappings:
        existing = url_mapping_list(mis)
        existing_urls = {m.get("url", ""): m for m in existing}
        for url in check_url_mappings:
            url = url.strip()
            m = existing_urls.get(url)
            if m:
                checks.append({
                    "item": f"url-mapping:{url}",
                    "ok": True,
                    "detail": f"映射存在（betaUrl={(m.get('betaUrl') or '')[:60]}）"
                })
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

# 自动创建的域名映射 ID 持久化文件（跨 CLI 调用共享，按 run 隔离）


def _load_auto_mapping_ids() -> list:
    """从磁盘加载自动创建的域名映射 ID 列表。"""
    if os.path.isfile(auto_url_mapping_ids_path()):
        try:
            ids = read_json(auto_url_mapping_ids_path(), default=[])
            if isinstance(ids, list):
                return ids
        except Exception as e:
            soft_fail("infra", "AUTO_MAPPING_IDS_READ_FAILED", e)
    return []


def _save_auto_mapping_ids(ids: list):
    """将自动创建的域名映射 ID 列表写入磁盘。"""
    ensure_dirs()
    try:
        write_json_atomic(auto_url_mapping_ids_path(), ids)
    except Exception as e:
        soft_fail("infra", "AUTO_MAPPING_IDS_WRITE_FAILED", e)
        print(f"URL_MAPPING: 持久化映射 ID 失败: {e}")


def appmock_ensure_url_mappings(mappings: list, mis: str = None) -> list:
    """确保域名映射已配置并激活（泳道切换时自动调用）。

    对 mappings 列表中的每一项，检查是否已存在同 url 的映射：
      - 已存在且目标地址一致 → 跳过写入，仍然激活
      - 已存在但目标地址不一致 → update
      - 不存在 → add
    写入后统一调 updateUrlEnv 激活（env=beta），保证映射真正生效。

    新增的映射 ID 会持久化到磁盘文件，供收尾时跨进程清理。

    Args:
        mappings: 域名映射配置列表，每项为 dict：
            {
                "url": "apihotel.meituan.com/xxx",     # 必需，线上 URL（不含协议）
                "betaUrl": "http://10.0.0.1:8080/xxx", # 测试环境 URL（带协议）
                "ppeUrl": ""                             # 预发环境 URL（带协议）
            }
            betaUrl / ppeUrl 至少一个；title 上游不接收，忽略。
        mis: MIS 号

    Returns:
        创建/更新的映射列表
    """

    if not mappings:
        return []

    mis = resolve_mock_domain(mis)
    if not mis:
        print("URL_MAPPING ENSURE: 无法确定目标工作域 MIS")
        return []
    results = []
    auto_ids = _load_auto_mapping_ids()

    # 获取当前工作域已有映射（按 url 建索引）
    existing = url_mapping_list(mis)
    existing_by_url = {m.get("url", ""): m for m in existing}

    for cfg in mappings:
        url = cfg.get("url", "").strip()
        beta_url = cfg.get("betaUrl", "").strip()
        ppe_url = cfg.get("ppeUrl", "").strip()

        if not url:
            print(f"URL_MAPPING ENSURE: 跳过无效配置（url 为空）: {cfg}")
            continue
        if not beta_url and not ppe_url:
            print(f"URL_MAPPING ENSURE: 跳过无效配置（betaUrl 和 ppeUrl 都为空）: {cfg}")
            continue

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
                print(f"URL_MAPPING ENSURE: 已存在但目标不一致，更新: {url} (id={mapping_id})")
                r = url_mapping_update(mapping_id, url, mis=mis,
                                       beta_url=beta_url, ppe_url=ppe_url)
                if not r:
                    print(f"URL_MAPPING ENSURE: 更新失败: {url}")
                    continue
                results.append(r)
        else:
            print(f"URL_MAPPING ENSURE: 不存在，新增: {url}")
            r = url_mapping_add(url, mis=mis, beta_url=beta_url, ppe_url=ppe_url)
            if not r:
                print(f"URL_MAPPING ENSURE: 新增失败: {url}")
                continue
            results.append(r)
            mapping_id = r.get("id")
            if mapping_id is not None and mapping_id not in auto_ids:
                auto_ids.append(mapping_id)

        # 激活域名映射（updateUrlEnv，env=beta）
        # 无论新建、更新还是跳过，都激活（映射可能是上次收尾时关闭但未删除，需重新激活）
        if mapping_id is not None:
            if url_mapping_set_env(mapping_id, "beta", mis=mis):
                print(f"URL_MAPPING ENSURE: 已激活映射 id={mapping_id} env=beta")
            else:
                print(f"URL_MAPPING ENSURE: ⚠️ 激活映射失败 id={mapping_id}，映射可能不生效")

    # 持久化到磁盘（跨 CLI 调用可用）
    _save_auto_mapping_ids(auto_ids)

    if auto_ids:
        print(f"URL_MAPPING ENSURE: 自动创建的映射 ID: {auto_ids}")

    return results


def appmock_cleanup_url_mappings(mis: str = None) -> int:
    """清理自动创建的域名映射（从磁盘文件读取 ID 列表）。

    在 swimline-off 收尾阶段调用。映射 ID 通过磁盘文件跨 CLI 调用共享，
    确保 ensure 和 cleanup 在不同进程中也能正确联动。

    Args:
        mis: 目标工作域 MIS 号（上游按 userDomain + id 删除）

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
        if url_mapping_delete(mid, mis=mis):
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
            os.remove(auto_url_mapping_ids_path())
        except OSError as e:
            soft_fail("infra", "AUTO_MAPPING_IDS_CLEANUP_FAILED", e)

    return deleted
