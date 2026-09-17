#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 环境配置 CLI —— 泳道管理、域名映射、MRN 锁包。

从 appmock_cli.py 拆出，聚焦环境配置类子命令。
appmock_cli.py 保留规则 CRUD、录制和 CLI 分发入口；
可测性 Scheme 推送 / 环境重置等可复用编排逻辑下沉至 appmock_ops.py。

【错误约定】命令 handler 不调用 sys.exit，失败一律抛 core.errors 中的领域错误
（UsageError / MockError），由 CLI 边界 cli_utils.run_with_guard 统一转成退出码。
"""
import json
import os

from core.errors import MockError, UsageError
from core.util.json_utils import read_json
from core.util.case_utils import resolve_mis
from mock.appmock_swimlane import (
    appmock_env_set,
    appmock_swimline_list, appmock_swimline_add, appmock_swimline_switch,
    appmock_swimline_off, appmock_swimline_remove,
    appmock_ensure_url_mappings, appmock_cleanup_url_mappings,
    verify_swimlane_env,
)
from mock.appmock_session import (
    url_mapping_list, url_mapping_update, url_mapping_delete, url_mapping_find,
    url_mapping_set_env,
)
from mock.appmock_ops import push_testability_scheme, reset_appmock_environment

# ── 环境切换 ──

def _mock_env_set(args):
    env = args.env or getattr(args, "mock_id", None)
    if not env:
        raise UsageError("mock env-set 需要 --env <env> 或 --mock-id <mockId>")
    if not appmock_env_set(env, mis=resolve_mis()):
        raise MockError(f"mock env-set 失败: env={env}")

def _mock_reset_env(args):
    if not reset_appmock_environment(mis=resolve_mis()):
        raise MockError("mock reset-env 部分步骤失败，见上方日志")

# ── 泳道管理 ──

def _mock_swimline_list(args):
    items = appmock_swimline_list(mis=resolve_mis())
    print(json.dumps(items, ensure_ascii=False, indent=2))

def _mock_swimline_add(args):
    url_pat = args.url_pattern
    lane = args.lane_name
    if not url_pat or not lane:
        raise UsageError("mock swimline-add 需要 --url-pattern <pattern> --lane-name <name>")
    result = appmock_swimline_add(url_pat, lane, mis=resolve_mis())
    if not result:
        raise MockError(f"mock swimline-add 失败: pattern={url_pat} lane={lane}")
    print(json.dumps(result, ensure_ascii=False, indent=2))

def _mock_swimline_switch(args):
    rid = args.rule_id or getattr(args, "mock_id", None)
    if not rid:
        raise UsageError("mock swimline-switch 需要 --rule-id <id> 或 --mock-id <mockId>")
    if not appmock_swimline_switch(rid, mis=resolve_mis()):
        raise MockError(f"mock swimline-switch 失败: ruleId={rid}")

def _mock_swimline_off(args):
    appmock_cleanup_url_mappings()
    if not appmock_swimline_off(mis=resolve_mis()):
        raise MockError("mock swimline-off 失败（可能无残留）")

def _mock_swimline_remove(args):
    rid = args.rule_id or getattr(args, "mock_id", None)
    if not rid:
        raise UsageError("mock swimline-remove 需要 --rule-id <id> 或 --mock-id <mockId>")
    if not appmock_swimline_remove(rid, mis=resolve_mis()):
        raise MockError(f"mock swimline-remove 失败: ruleId={rid}")

def _mock_swimline_verify(args):
    lane = getattr(args, "lane_name", None)
    rid = getattr(args, "rule_id", None) or getattr(args, "mock_id", None)
    url_mappings = None
    if args.response:
        try:
            url_mappings = json.loads(args.response)
            if isinstance(url_mappings, str):
                url_mappings = [url_mappings]
        except json.JSONDecodeError:
            url_mappings = [u.strip() for u in args.response.split(",") if u.strip()]
    result = verify_swimlane_env(
        expected_lane=lane,
        expected_rule_id=rid,
        check_url_mappings=url_mappings,
        mis=resolve_mis(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise MockError("mock swimline-verify 校验未通过")

# ── 域名映射 ──

def _mock_url_mapping_ensure(args):
    cfg_src = args.response or args.response_file
    if not cfg_src:
        raise UsageError("mock url-mapping-ensure 需要 --response '<JSON数组>' 或 --response-file <路径>")
    try:
        if args.response_file and os.path.isfile(args.response_file):
            mapping_list = read_json(args.response_file, default=[])
        else:
            mapping_list = json.loads(cfg_src)
    except (json.JSONDecodeError, ValueError, OSError) as e:
        raise UsageError(f"域名映射配置解析失败: {e}") from e
    if not isinstance(mapping_list, list):
        mapping_list = [mapping_list]
    results = appmock_ensure_url_mappings(mapping_list, mis=resolve_mis(), sp_env=getattr(args, "sp_env", "beta"))
    print(json.dumps(results, ensure_ascii=False, indent=2))
    expected_count = len([m for m in mapping_list if m.get("url") and m.get("title")
                         and (m.get("betaUrl") or m.get("ppeUrl"))])
    if not results:
        raise MockError("URL_MAPPING ENSURE: 全部配置失败")
    if len(results) < expected_count:
        raise MockError(f"URL_MAPPING ENSURE: 部分配置失败（成功 {len(results)}/{expected_count}）")

def _mock_url_mapping_cleanup(args):
    deleted = appmock_cleanup_url_mappings()
    print(f"已清理 {deleted} 条自动创建的域名映射")

def _mock_url_mapping_list(args):
    mappings = url_mapping_list()
    print(json.dumps(mappings, ensure_ascii=False, indent=2))

def _mock_url_mapping_update(args):
    url = args.mapping_url
    title = args.title
    if not url or not title:
        raise UsageError("mock url-mapping-update 需要 --url <线上URL> --title <描述>")
    if not args.beta_url and not args.ppe_url:
        raise UsageError("mock url-mapping-update 需要 --beta-url 或 --ppe-url 至少一个")
    result = url_mapping_update(
        url=url, title=title, mis=resolve_mis(),
        beta_url=args.beta_url, ppe_url=args.ppe_url, sp_env=args.sp_env
    )
    if not result:
        raise MockError(f"mock url-mapping-update 失败: url={url}")
    print(json.dumps(result, ensure_ascii=False, indent=2))

def _mock_url_mapping_delete(args):
    mid = args.mapping_id
    if not mid:
        raise UsageError("mock url-mapping-delete 需要 --mapping-id <id>")
    if not url_mapping_delete(mid):
        raise MockError(f"mock url-mapping-delete 失败: mappingId={mid}")

def _mock_url_mapping_find(args):
    kw = args.keyword
    if not kw:
        raise UsageError("mock url-mapping-find 需要 --keyword <关键词>")
    matched = url_mapping_find(kw)
    print(json.dumps(matched, ensure_ascii=False, indent=2))

def _mock_url_mapping_set_env(args):
    mid = args.mapping_id
    env_val = args.sp_env or "beta"
    if not mid:
        raise UsageError("mock url-mapping-set-env 需要 --mapping-id <id>")
    if not url_mapping_set_env(mid, env_val):
        raise MockError(f"mock url-mapping-set-env 失败: mappingId={mid} env={env_val}")

# ── MRN 锁包（可测性 Scheme） ──

def _mock_bundle_lock(args):
    bundles_str = args.bundles
    if not bundles_str:
        raise UsageError(
            "mock bundle-lock 需要 --bundles 参数\n"
            "  格式: --bundles 'bundleName:bundleVersion[,bundleName:bundleVersion,...]'\n"
            "  示例: --bundles 'rn_hotel_hotelchannel-order-detail:3.1017.734'\n"
            "  多包: --bundles 'rn_hotel_xxx:1.0.0,rn_hotel_yyy:2.0.0'"
        )
    is_stage = 1 if args.bundle_env == "stage" else 0
    config = []
    for item in bundles_str.split(","):
        item = item.strip()
        if ":" not in item:
            raise UsageError(f"锁包格式错误 '{item}'，应为 bundleName:bundleVersion")
        name, version = item.split(":", 1)
        name, version = name.strip(), version.strip()
        if not name or not version:
            raise UsageError(f"锁包参数不完整 '{item}'")
        config.append({"type": "mrnbundle", "info": {
            "isStage": is_stage,
            "bundleName": name,
            "bundleVersion": version,
        }})
    ok, scheme_url, detail = push_testability_scheme(config, verify=True, verify_wait=3.0)
    if not ok:
        raise MockError(f"BUNDLE-LOCK FAIL: {detail}")
    env_label = "stage" if is_stage else "prod"
    for c in config:
        info = c["info"]
        print(f"  📦 {info['bundleName']} -> {info['bundleVersion']} ({env_label})")
    print(f"BUNDLE-LOCK: ✅ {len(config)} 个 MRN bundle 已锁定并验证成功")

# ── 环境配置子命令分发表 ──

ENV_MOCK_DISPATCH = {
    "env-set":              _mock_env_set,
    "reset-env":            _mock_reset_env,
    "swimline-list":        _mock_swimline_list,
    "swimline-add":         _mock_swimline_add,
    "swimline-switch":      _mock_swimline_switch,
    "swimline-off":         _mock_swimline_off,
    "swimline-remove":      _mock_swimline_remove,
    "swimline-verify":      _mock_swimline_verify,
    "url-mapping-ensure":   _mock_url_mapping_ensure,
    "url-mapping-cleanup":  _mock_url_mapping_cleanup,
    "url-mapping-list":     _mock_url_mapping_list,
    "url-mapping-update":   _mock_url_mapping_update,
    "url-mapping-delete":   _mock_url_mapping_delete,
    "url-mapping-find":     _mock_url_mapping_find,
    "url-mapping-set-env":  _mock_url_mapping_set_env,
    "bundle-lock":          _mock_bundle_lock,
}
