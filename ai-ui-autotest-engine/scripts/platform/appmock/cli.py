#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock CLI 命令层 —— 设备端开关、规则 CRUD、录制、清理入口。

本模块只保留「参数解析 → 调用底层能力 → 格式化输出」的 CLI 职责。

分层：
  appmock_cli / appmock_env_cli   CLI 命令层（本文件 + 环境配置子命令）
  appmock_ops                     业务编排层（可测性 Scheme / 环境重置 / ptest 状态）
  appmock_rules / appmock_session / appmock_swimlane / appmock_record / appmock_device
                                  AppMock 能力层

【错误约定】命令 handler 不调用 sys.exit，失败一律抛 shared.errors 中的领域错误
（UsageError / MockError），由 CLI 边界 cli_utils.run_with_guard 统一转成退出码。

环境配置类子命令（泳道、域名映射、MRN 锁包）拆至 appmock_env_cli.py。
"""
import json
import os

from shared.case_utils import resolve_mock_domain
from shared.errors import MockError, UsageError, soft_fail
from shared.paths import ensure_dirs, recording_active_path
from platform.appmock.device import appmock_enable, appmock_disable
from platform.appmock.rules import (
    extract_mock_id,
    appmock_on, appmock_off, appmock_get, appmock_list, appmock_stop_all,
    appmock_create, appmock_update, appmock_patch_field,
)
from platform.appmock.record import (
    appmock_record_start, appmock_record_stop, appmock_record_data,
    appmock_record_data_filter,
)
from platform.appmock.swimlane import (
    appmock_swimline_off, appmock_env_set, appmock_cleanup_url_mappings,
)
# 单向依赖：CLI 分发入口合并环境配置子命令表（appmock_env_cli 不再反向依赖本模块）
from platform.appmock.env_cli import ENV_MOCK_DISPATCH


def _cmd_cleanup(args):
    """异常中断后的「本工作域」AppMock 状态清理。

    处理服务端残留状态（均按当前工作域 mis，多 shard 互不影响）：
    域名映射清理 → stop-all → swimline-off → env-set online。
    清理属 best-effort：单步失败不中断，但必须留痕（soft_fail）。
    """
    print("CLEANUP: 开始资源清理（AppMock 账号级状态）...")
    cleaned = []
    errors = []
    mis = resolve_mock_domain()
    if not mis:
        print("  ⚠️  CLEANUP: 无法确定当前工作域 MIS，跳过依赖工作域的清理步骤")

    try:
        deleted = appmock_cleanup_url_mappings(mis=mis)
        if deleted:
            cleaned.append("url-mapping-cleanup")
            print(f"  ✅ 已删除 {deleted} 条自动创建的域名映射")
    except Exception as e:
        errors.append(f"url-mapping-cleanup: {e}")
        soft_fail("infra", "CLEANUP_URL_MAPPING_FAILED", e)
        print(f"  ⚠️  域名映射清理失败: {e}")

    try:
        if appmock_stop_all(mis=mis):
            cleaned.append("stop-all")
            print("  ✅ 已关闭全部接口 Mock 规则")
        else:
            print("  ℹ️  关闭全部 Mock 规则返回非成功（可能无规则）")
    except Exception as e:
        errors.append(f"stop-all: {e}")
        soft_fail("infra", "CLEANUP_STOP_ALL_FAILED", e)
        print(f"  ⚠️  关闭 Mock 规则失败: {e}")

    try:
        if appmock_swimline_off(mis=mis):
            cleaned.append("swimline-off")
            print("  ✅ 泳道关闭")
        else:
            print("  ℹ️  泳道关闭返回非成功（可能无残留）")
    except Exception as e:
        errors.append(f"swimline-off: {e}")
        soft_fail("infra", "CLEANUP_SWIMLINE_FAILED", e)
        print(f"  ⚠️  泳道关闭失败（可能无残留）: {e}")

    try:
        env_ok = appmock_env_set("online", mis=mis)
        if env_ok:
            cleaned.append("env-set-online")
            print("  ✅ 环境重置为线上")
        else:
            errors.append("env-set: yooz 代理返回非成功")
            soft_fail("infra", "CLEANUP_ENV_SET_FAILED", "yooz 代理返回非成功")
            print("  ⚠️  环境重置为线上失败（yooz 代理返回非成功）")
    except Exception as e:
        errors.append(f"env-set: {e}")
        soft_fail("infra", "CLEANUP_ENV_SET_FAILED", e)
        print(f"  ⚠️  环境重置失败: {e}")

    print(f"CLEANUP: 完成 — 成功 {len(cleaned)} 项, 异常 {len(errors)} 项")
    if errors:
        for err in errors:
            print(f"  ❌ {err}")

# ═══════════════════════════════════════════════════════════════════
# AppMock 子命令分发
# ═══════════════════════════════════════════════════════════════════

def _resolve_mock_response(args) -> str:
    """从 --response 或 --response-file 解析 mock 响应体。"""
    if args.response_file:
        with open(args.response_file, "r", encoding="utf-8") as f:
            return f.read()
    if args.response:
        return args.response
    return '{}'

# ── 设备端开关 ──

def _mock_enable(args):
    if not appmock_enable():
        raise MockError("AppMock SDK 启用失败")

def _mock_disable(args):
    if not appmock_disable():
        raise MockError("AppMock SDK 停用失败")

# ── 服务端规则开关 ──

def _mock_on(args):
    if not args.mock_id:
        raise UsageError("mock on 需要 --mock-id <mockId>")
    if not appmock_on(args.mock_id, mis=resolve_mock_domain()):
        raise MockError(f"mock on 失败: mockId={args.mock_id}")

def _mock_off(args):
    if not args.mock_id:
        raise UsageError("mock off 需要 --mock-id <mockId>")
    if not appmock_off(args.mock_id, mis=resolve_mock_domain()):
        raise MockError(f"mock off 失败: mockId={args.mock_id}")

# ── 规则 CRUD ──

def _mock_create(args):
    if not args.rule:
        raise UsageError("mock create 需要 --rule <uri_pattern>")
    resp_body = _resolve_mock_response(args)
    result = appmock_create(
        rule=args.rule, response_body=resp_body, mis=resolve_mock_domain(),
        desc=args.desc, status=1, status_code=args.status_code,
        force_add=args.force_add,
        example_url=getattr(args, "example_url", None),
    )
    if not result.get("mockId"):
        raise MockError(f"mock create 失败: rule={args.rule}")
    print(json.dumps(result))

def _mock_upsert(args):
    # ── 智能 upsert：有已有规则就 update，没有就 create ──
    # 优先级：--mock-id（预设/已知 ID）> 同 rule 现有规则 > 新建
    if not args.rule and not args.mock_id:
        raise UsageError("mock upsert 需要 --rule <uri_pattern> 或 <mockId>")
    resp_body = _resolve_mock_response(args)
    target_id = args.mock_id
    # 如果没有指定 mockId，按 rule 在已有规则中查找
    if not target_id and args.rule:
        items = appmock_list(mis=resolve_mock_domain())
        for item in items:
            if item.get("rule") == args.rule:
                target_id = extract_mock_id(item)
                if not target_id:
                    continue
                print(f"UPSERT: 找到已有规则 mockId={target_id} rule={args.rule}")
                break
    if target_id:
        # update 已有规则
        ok = appmock_update(
            mock_id=target_id, response_body=resp_body,
            desc=args.desc if args.desc else None,
            status=1,  # upsert 时默认开启
            status_code=args.status_code if args.status_code != 200 else None,
        )
        if not ok:
            raise MockError(f"mock upsert 更新失败: mockId={target_id}")
        # 确保规则处于开启状态
        appmock_on(target_id, mis=resolve_mock_domain())
        print(json.dumps({"mockId": target_id, "action": "updated"}))
    else:
        # 没有已有规则，创建新规则
        result = appmock_create(
            rule=args.rule, response_body=resp_body, mis=resolve_mock_domain(),
            desc=args.desc, status=1, status_code=args.status_code,
            example_url=getattr(args, "example_url", None),
        )
        if not result.get("mockId"):
            raise MockError(f"mock upsert 创建失败: rule={args.rule}")
        # 确保开启
        appmock_on(result["mockId"], mis=resolve_mock_domain())
        result["action"] = "created"
        print(json.dumps(result))

def _mock_update(args):
    if not args.mock_id:
        raise UsageError("mock update 需要 --mock-id <mockId>")
    resp_body = _resolve_mock_response(args) if (args.response or args.response_file) else None
    ok = appmock_update(
        mock_id=args.mock_id, response_body=resp_body,
        rule=args.rule, desc=args.desc if args.desc else None,
        status_code=args.status_code if args.status_code != 200 else None,
    )
    if not ok:
        raise MockError(f"mock update 失败: mockId={args.mock_id}")

def _mock_patch_field(args):
    # ── 动态 Mock：修改已有规则响应体中的指定字段 ──
    if not args.mock_id:
        raise UsageError("mock patch-field 需要 --mock-id <mockId>")
    if not args.field:
        raise UsageError("mock patch-field 需要 --field <dotpath>")
    if args.value is None:
        raise UsageError("mock patch-field 需要 --value <new_value>")
    # 尝试解析 value 为 JSON 类型（数字/bool/null），失败则保持字符串
    raw_val = args.value
    try:
        parsed_val = json.loads(raw_val)
    except (json.JSONDecodeError, TypeError):
        parsed_val = raw_val
    ok = appmock_patch_field(
        mock_id=args.mock_id, field_path=args.field,
        new_value=parsed_val, mis=resolve_mock_domain(),
    )
    if not ok:
        raise MockError(f"mock patch-field 失败: mockId={args.mock_id} field={args.field}")

def _mock_get(args):
    if not args.mock_id:
        raise UsageError("mock get 需要 --mock-id <mockId>")
    data = appmock_get(args.mock_id, mis=resolve_mock_domain())
    if not data:
        raise MockError(f"mock get 失败: mockId={args.mock_id}")
    print(json.dumps(data, ensure_ascii=False, indent=2))

def _mock_list(args):
    items = appmock_list(mis=resolve_mock_domain())
    print(json.dumps(items, ensure_ascii=False, indent=2))

def _mock_stop_all(args):
    if not appmock_stop_all(mis=resolve_mock_domain()):
        raise MockError("mock stop-all 失败")


# ── 生效集总览（ptest 规则 + 场景 Mock 的共存关系）──

def _ptest_still_covers(ptest_rule, scenario_rule) -> bool:
    """ptest 规则是否仍会命中某场景 Mock 路径（命中即遮蔽该场景 Mock）。"""
    import re
    probe = str(scenario_rule or "").rstrip("$") or "/"
    try:
        return re.search(str(ptest_rule or ""), probe) is not None
    except re.error:
        return True


def _mock_effective(args):
    """聚合报告本次生效的 Mock 集：ptest 规则 + 场景 Mock 规则 + 遮蔽判定。

    为什么需要：`mock list` 只列当前 userDomain 自有的规则，场景 Mock 常归属其他
    分组而不出现 —— 「谁真正生效」在引擎侧不可见（历史事故排查耗时的原因之一）。
    本命令按已知 id 逐个查询，给出引擎自己的生效集视图，并显式标出**仍被 ptest
    全量规则遮蔽**的场景 Mock。
    """
    from platform.appmock.ptest import build_ptest_rule, load_ptest_mock_id

    report = {"mock_domain": resolve_mock_domain(), "ptest": None, "scenario_mocks": []}
    ptest_id = load_ptest_mock_id()
    if ptest_id:
        detail = appmock_get(ptest_id, mis=resolve_mock_domain()) or {}
        report["ptest"] = {
            "mockId": ptest_id,
            "rule": detail.get("rule") or build_ptest_rule(),
            "status": detail.get("status"),
        }
    ptest_rule = (report["ptest"] or {}).get("rule")
    for mid in [i.strip() for i in str(args.mock_ids or "").split(",") if i.strip()]:
        detail = appmock_get(mid, mis=resolve_mock_domain()) or {}
        rule = detail.get("rule")
        report["scenario_mocks"].append({
            "mockId": mid,
            "rule": rule,
            "status": detail.get("status"),
            "desc": detail.get("desc"),
            "shadowed_by_ptest": bool(ptest_rule and _ptest_still_covers(ptest_rule, rule)),
        })
    print(json.dumps(report, ensure_ascii=False, indent=2))

# ── 录制 ──

def _mock_record_start(args):
    ok = appmock_record_start(
        filter_str=args.filter or "",
        add_mock=args.add_mock,
    )
    if not ok:
        raise MockError("mock record-start 失败")
    ensure_dirs()
    open(recording_active_path(), "w").close()

def _mock_record_stop(args):
    ok = appmock_record_stop()
    if not ok:
        raise MockError("mock record-stop 失败")
    if os.path.isfile(recording_active_path()):
        os.remove(recording_active_path())

def _mock_record_data(args):
    auto_filter = not getattr(args, "no_filter", False)
    no_save = getattr(args, "no_save", False)
    exclude_noise = getattr(args, "exclude_noise", False)
    # 默认保存到 <run>/record_data.json；--save 指定路径；--no-save 不保存
    if no_save:
        save_path = None
    else:
        save_path = getattr(args, "save", None)  # None 时 appmock_record_data 使用默认路径
    filter_kw = args.filter
    if filter_kw:
        # 客户端过滤：按关键词筛选录制数据
        keywords = [k.strip() for k in filter_kw.split(",") if k.strip()]
        items = appmock_record_data_filter(
            keywords=keywords,
            page=args.page,
            page_size=args.page_size,
        )
        data = {"items": items, "count": len(items)}
    else:
        data = appmock_record_data(
            page=args.page,
            page_size=args.page_size,
            auto_filter=auto_filter,
            save_path=save_path,
            exclude_noise=exclude_noise,
        )
    if not data:
        raise MockError("mock record-data 未取到录制数据")
    print(json.dumps(data, ensure_ascii=False, indent=2))

# ═══════════════════════════════════════════════════════════════════
# 子命令 → 处理函数 分发表
# ═══════════════════════════════════════════════════════════════════

_MOCK_DISPATCH = {
    # 设备端开关
    "enable":               _mock_enable,
    "disable":              _mock_disable,
    # 服务端规则开关
    "on":                   _mock_on,
    "off":                  _mock_off,
    # 规则 CRUD
    "create":               _mock_create,
    "upsert":               _mock_upsert,
    "update":               _mock_update,
    "patch-field":          _mock_patch_field,
    "get":                  _mock_get,
    "list":                 _mock_list,
    "stop-all":             _mock_stop_all,
    "effective":            _mock_effective,
    # 录制
    "record-start":         _mock_record_start,
    "record-stop":          _mock_record_stop,
    "record-data":          _mock_record_data,
}

def _cmd_mock(args):
    """AppMock 子命令分发。

    规则管理：    create / upsert / update / get / list / stop-all / effective
    录制：        record-start / record-stop / record-data
    环境配置类子命令（泳道/域名映射/锁包/env-set）由 appmock_env_cli 提供，
    其分发表 ENV_MOCK_DISPATCH 在本模块顶层导入（单向依赖，无循环）。
    """
    sub = args.mock_subcmd
    handler = _MOCK_DISPATCH.get(sub)
    if handler is None:
        handler = ENV_MOCK_DISPATCH.get(sub)
    if handler is None:
        raise UsageError(f"未知 mock 子命令: {sub}")
    handler(args)
