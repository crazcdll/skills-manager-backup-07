#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 编排操作 —— 可测性 Scheme 推送、环境重置、ptest 状态持久化。

本模块位于 appmock_cli（CLI 命令层）与 appmock_rules / appmock_session /
appmock_swimlane（AppMock 业务能力层）之间，承载被「CLI 层」与「业务层」
共同复用的编排逻辑，因此只做业务动作，不含参数解析与 sys.exit。

【为什么需要本模块】

历史上 push_testability_scheme / reset_appmock_environment / ptest mockId
持久化等函数都定义在 appmock_cli.py 中，导致 appmock_env_cli.py、
ptest_mock.py、env_prepare.py、login_password.py 反向依赖 CLI 模块并引用
其私有函数（下划线前缀），形成 appmock_cli ↔ appmock_env_cli 的模块级循环依赖：

    appmock_env_cli --(顶层 import)--> appmock_cli --(延迟 import)--> appmock_env_cli

当前只是靠「一侧顶层、一侧延迟导入」才没触发 ImportError，属于脆弱隐式契约。
拆分到本模块后，依赖方向变为单向：

    appmock_cli ───────┐
    appmock_env_cli ───┤
    ptest_mock ────────┼──> appmock_ops ──> appmock_rules / session / swimlane
    env_prepare ───────┤
    login_password ────┘

CLI 命令函数与业务函数统一以公开命名对外暴露，不再有跨模块引用私有符号。
"""
import os
import sys
import time

from core.errors import soft_fail
from core.util.paths import ensure_dirs, PTEST_MOCK_ID_FILE
from core.util.json_utils import write_json_atomic, read_json
from core.util.case_utils import encode_scheme_payload
from screen_state.inspect_tree import dump_inspect_tree, parse_inspect_tree
from mock.appmock_rules import (
    extract_mock_id, appmock_list, appmock_off, appmock_stop_all,
)
from mock.appmock_session import url_mapping_list, url_mapping_set_env
from mock.appmock_swimlane import (
    appmock_cleanup_url_mappings, appmock_swimline_off, appmock_env_set,
)
from context import get_app_descriptor, get_platform_ops

# ═══════════════════════════════════════════════════════════════════
# ptest mockId 持久化（供 reset-env 时精准关闭 ptest 规则）
# ═══════════════════════════════════════════════════════════════════

def save_ptest_mock_id(mock_id: str):
    """记录 ptest mockId，供后续精准关闭。空 id 不落盘。"""
    if not mock_id:
        return
    try:
        ensure_dirs()
        write_json_atomic(PTEST_MOCK_ID_FILE, {"mockId": str(mock_id)})
    except Exception as e:
        # 非关键，失败不阻断主流程，但需留痕
        soft_fail("infra", "PTEST_MOCK_ID_SAVE_FAILED", e)

def load_ptest_mock_id():
    """读取已记录的 ptest mockId，无记录或记录无效时返回 None。"""
    try:
        return extract_mock_id(read_json(PTEST_MOCK_ID_FILE, default={})) or None
    except Exception:
        return None

def clear_ptest_mock_id():
    """清除 ptest mockId 记录。"""
    try:
        if os.path.isfile(PTEST_MOCK_ID_FILE):
            os.remove(PTEST_MOCK_ID_FILE)
    except Exception as e:
        soft_fail("infra", "PTEST_MOCK_ID_CLEAR_FAILED", e)

# ═══════════════════════════════════════════════════════════════════
# 可测性 Scheme 辅助（ptest 等）
# ═══════════════════════════════════════════════════════════════════

def push_testability_scheme(config_list: list, verify=True, verify_wait=3.0):
    """生成可测性配置 scheme 并推送到设备，可选验证设备端执行结果。

    编码格式与 Pillow 平台完全兼容：JSON → zlib → urlsafe_base64
    通过 PlatformOps.open_url() 推送到设备。

    Args:
        config_list: 配置列表，如 [{"type": "htptest", "info": {"value": 1}}]
        verify: 是否通过 inspect-tree 验证设备端执行结果（默认 True）
        verify_wait: 推送后等待结果页渲染的秒数（默认 3.0）
    Returns:
        (ok: bool, scheme_url: str, detail: str)
    """
    encoded = encode_scheme_payload(config_list)
    scheme_url = get_app_descriptor().testability_scheme_prefix + encoded
    try:
        ops = get_platform_ops()
        ok = ops.open_url(scheme_url)
        if not ok:
            return False, scheme_url, "推送失败（open-url 命令返回非零退出码）"
    except Exception as e:
        return False, scheme_url, f"推送异常: {e}"

    if not verify:
        return True, scheme_url, ""

    time.sleep(verify_wait)
    failures = verify_testability_result(config_list)
    if failures:
        detail = "; ".join(failures)
        return False, scheme_url, f"设备端执行失败: {detail}"
    return True, scheme_url, ""

def verify_testability_result(config_list: list):
    """通过 inspect-tree 检查「扫码配置」结果页，返回失败项描述列表（空=全部成功）。

    inspect-tree 采集失败时返回空列表——采集不到不等于配置执行失败，
    由调用方通过截图做最终判断（NEEDS_VISUAL_CHECK）。
    """
    raw = dump_inspect_tree(wait_sec=4, max_attempts=2)
    if raw is None:
        sys.stderr.write("⚠️  verify_testability_result: inspect-tree 采集失败，跳过自动校验\n")
        return []

    nodes = parse_inspect_tree(raw)
    all_texts = [n.get("all_text", "") for n in nodes if n.get("all_text")]

    has_failure = any("失败" in t or "fail" in t.lower() for t in all_texts)
    if not has_failure:
        return []

    failures = []
    for cfg in config_list:
        cfg_type = cfg.get("type", "")
        info = cfg.get("info", {})

        if cfg_type == "mrnbundle":
            bundle_id = f"{info.get('bundleName', '')}/{info.get('bundleVersion', '')}"
            for t in all_texts:
                if bundle_id in t and ("失败" in t or "fail" in t.lower()):
                    error_msg = t[t.index("失败"):] if "失败" in t else t
                    failures.append(f"mrnbundle {info.get('bundleName')}:{info.get('bundleVersion')} {error_msg[:120]}")
                    break
        else:
            for t in all_texts:
                if cfg_type in t and ("失败" in t or "fail" in t.lower()):
                    failures.append(f"{cfg_type}: {t[:120]}")
                    break

    if not failures and has_failure:
        fail_texts = [t for t in all_texts if "失败" in t or "fail" in t.lower()]
        failures.append(f"配置执行存在失败项: {fail_texts[0][:150]}")

    return failures

# ═══════════════════════════════════════════════════════════════════
# 环境重置 / 清理
# ═══════════════════════════════════════════════════════════════════

def reset_appmock_environment(mis: str = None) -> bool:
    """执行测试前的 AppMock 环境重置：清理上一次执行可能残留的全部状态。

    AppMock 的泳道路由规则、代理环境、接口 Mock 规则、域名映射均为账号级别
    全局状态，跨设备、跨执行持久化在服务端。四步清理确保进入测试前
    AppMock 处于已知的干净状态：
      1) 列出当前生效的全部 Mock 规则（仅日志展示）
      2) stop-all 无条件关闭所有接口 Mock 规则
      3) 独立盘点域名映射并清理
      4) swimline-off + env-set online

    每步独立 try/except，一步失败不影响后续步骤。
    """
    print("RESET-ENV: 开始执行前环境重置...", flush=True)
    all_ok = True

    # 1) 列出当前 Mock 规则（日志展示）
    try:
        rules = appmock_list(mis=mis)
        if rules:
            print(f"  ℹ️  发现 {len(rules)} 条现有 Mock 规则，即将全部关闭")
        else:
            print("  ℹ️  当前无生效的 Mock 规则")
    except Exception as e:
        print(f"  ⚠️  查询现有 Mock 规则失败（不影响后续清理）: {e}")

    # 2) 无条件关闭所有接口 Mock 规则
    try:
        ok = appmock_stop_all(mis=mis)
        if ok:
            print("  ✅ 已关闭全部接口 Mock 规则")
        else:
            print("  ⚠️  关闭全部接口 Mock 规则失败或无规则可关")
    except Exception as e:
        all_ok = False
        print(f"  ⚠️  stop-all 异常: {e}")

    # 2.5) 精准清理 ptest partMock 规则（stop-all 可能不覆盖 partMock 类型）
    ptest_mid = load_ptest_mock_id()
    if ptest_mid:
        try:
            appmock_off(ptest_mid)
            clear_ptest_mock_id()
            print(f"  ✅ ptest 规则已关闭 (mockId={ptest_mid})")
        except Exception as e:
            print(f"  ⚠️  ptest 规则清理失败: {e}")

    # 3) 盘点并清理域名映射
    try:
        mappings = url_mapping_list()
        if mappings:
            print(f"  ℹ️  发现 {len(mappings)} 条域名映射，尝试关闭激活状态")
            for m in mappings:
                mapping_id = m.get("id") or m.get("mappingId")
                if mapping_id is None:
                    continue
                try:
                    url_mapping_set_env(mapping_id, "close")
                except Exception as e:
                    print(f"    ⚠️  关闭映射 {mapping_id} 失败: {e}")
            print("  ✅ 域名映射已全部关闭激活状态")
        else:
            print("  ℹ️  当前无域名映射记录")
    except Exception as e:
        print(f"  ⚠️  域名映射盘点/清理失败（不影响后续清理）: {e}")

    # 3.5) 清理自动创建的域名映射（幂等）
    try:
        deleted = appmock_cleanup_url_mappings()
        if deleted:
            print(f"  ✅ 已删除 {deleted} 条自动创建的域名映射")
    except Exception as e:
        print(f"  ⚠️  自动创建映射清理失败: {e}")

    # 4) 关闭泳道 + 环境重置为线上
    try:
        appmock_swimline_off(mis=mis)
        print("  ✅ 泳道关闭")
    except Exception as e:
        all_ok = False
        print(f"  ⚠️  泳道关闭失败（可能无残留）: {e}")

    try:
        env_ok = appmock_env_set("online", mis=mis)
        if env_ok:
            print("  ✅ 环境重置为线上")
        else:
            all_ok = False
            print("  ⚠️  环境重置为线上失败（CLI 返回非成功，reset-env 可能未生效）")
    except Exception as e:
        all_ok = False
        print(f"  ⚠️  环境重置为线上失败: {e}")

    print(f"RESET-ENV: 完成（{'全部成功' if all_ok else '部分步骤失败，见上方日志'}）")
    return all_ok
