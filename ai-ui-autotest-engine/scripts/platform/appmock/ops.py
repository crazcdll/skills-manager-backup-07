#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 编排操作 —— 可测性 Scheme 推送、环境重置、ptest 状态持久化。

本模块位于 appmock_cli（CLI 命令层）与 appmock_rules / appmock_session /
appmock_swimlane（AppMock 业务能力层）之间，承载被「CLI 层」与「业务层」
共同复用的编排逻辑，因此只做业务动作，不含参数解析与 sys.exit。

【为什么需要本模块】

历史上 push_testability_scheme / reset_appmock_environment / ptest mockId
持久化等函数都定义在 appmock_cli.py 中，导致 appmock_env_cli.py、
ptest_mock.py、env_prepare.py、login/actions/password.py 反向依赖 CLI 模块并引用
其私有函数（下划线前缀），形成 appmock_cli ↔ appmock_env_cli 的模块级循环依赖：

    appmock_env_cli --(顶层 import)--> appmock_cli --(延迟 import)--> appmock_env_cli

当前只是靠「一侧顶层、一侧延迟导入」才没触发 ImportError，属于脆弱隐式契约。
拆分到本模块后，依赖方向变为单向：

    appmock_cli ───────┐
    appmock_env_cli ───┤
    ptest_mock ────────┼──> appmock_ops ──> appmock_rules / session / swimlane
    env_prepare ───────┤
    login/actions/password ─┘

CLI 命令函数与业务函数统一以公开命名对外暴露，不再有跨模块引用私有符号。
"""
import os
import re
import sys
import time

from shared.errors import soft_fail
from shared.paths import ensure_dirs, ptest_mock_id_path
from shared.json_utils import write_json_atomic, read_json
from shared.case_utils import encode_scheme_payload
from execution.screen.inspect_tree import dump_inspect_tree, parse_inspect_tree
from platform.appmock.rules import (
    extract_mock_id, appmock_list,
)
from platform.appmock.session import url_mapping_list, url_mapping_set_env
from platform.appmock.swimlane import (
    appmock_cleanup_url_mappings, appmock_swimline_off, appmock_env_set,
)
from shared.context import get_app_descriptor, get_platform_ops

# ═══════════════════════════════════════════════════════════════════
# ptest mockId 持久化（供 reset-env 时精准关闭 ptest 规则）
# ═══════════════════════════════════════════════════════════════════

def save_ptest_mock_id(mock_id: str):
    """记录 ptest mockId，供后续精准关闭。空 id 不落盘。"""
    if not mock_id:
        return
    try:
        ensure_dirs()
        write_json_atomic(ptest_mock_id_path(), {"mockId": str(mock_id)})
    except Exception as e:
        # 非关键，失败不阻断主流程，但需留痕
        soft_fail("infra", "PTEST_MOCK_ID_SAVE_FAILED", e)

def load_ptest_mock_id():
    """读取已记录的 ptest mockId，无记录或记录无效时返回 None。"""
    try:
        return extract_mock_id(read_json(ptest_mock_id_path(), default={})) or None
    except Exception:
        return None

def clear_ptest_mock_id():
    """清除 ptest mockId 记录。"""
    try:
        if os.path.isfile(ptest_mock_id_path()):
            os.remove(ptest_mock_id_path())
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

# ═══════════════════════════════════════════════════════════════════
# 可测性结果页校验
# ═══════════════════════════════════════════════════════════════════
#
# 判定原则：**只以「本次下发的 config 自身的结果行」为准**。
# 结果页（travel/debugconfig 承载的 MRN 页）是**共享窗口**，同屏可能混入与本次
# 下发无关的文本：瞬时 Toast（实测：鸿蒙模拟器上 SDK 的 IDFA token 校验提示
# 「Token校验失败…PermissionID:IDFA…」）、其它配置或历史残留结果。若做「全屏任一
# 含『失败』即失败」的扫描，就会把无关文本误判成本次配置失败（实测：把已成功的
# 定位下发误判为失败，直接中断整个登录前置）。
#
# 结果页每条执行结果形如 "<type> : <message>"，例如：
#   "testability_location : 模拟定位成功,cityId:1,cityName:北京,status: 2"
# 因此按 config 的 type 锚定其自身结果行；**结果行缺失 = 未确认**（采集不到 ≠
# 执行失败，与 inspect-tree 采集失败的处理口径一致），不臆造失败。

# 结果行：<type> : <message>（type 为 config 类型标识，如 testability_location）
_RESULT_LINE_RE = re.compile(r"^\s*(?P<type>[A-Za-z_][\w.\-]*)\s*:\s*(?P<msg>\S.*)$")

# 结果消息中判定为「执行失败」的特征词（不区分大小写）
_FAILURE_MARKERS = ("失败", "fail", "error", "错误码")

# 不承载「配置执行结果」的节点类型：Toast 属瞬时提示，不作为结果判定依据
_NON_RESULT_NODE_TYPES = ("toast",)


def _is_toast_node(node) -> bool:
    """节点是否为 Toast 类瞬时提示。"""
    cls = str(node.get("class_name") or "").strip().lower()
    return any(cls == t or cls.endswith(t) for t in _NON_RESULT_NODE_TYPES)


def _non_result_indices(nodes: list) -> set:
    """标记「非结果」节点（Toast 容器**及其整棵子树**）的索引集合。

    Toast 的文本既挂在 Toast 容器节点上，也会镜像到其内部的 Text 子节点，
    因此只剔除容器本身不够——需连同子树一并排除，避免其文本继续参与判定。
    """
    toast = {i for i, n in enumerate(nodes) if _is_toast_node(n)}
    excluded = set(toast)
    for i, n in enumerate(nodes):
        p = n.get("parent")
        while p is not None:
            if p in toast:
                excluded.add(i)
                break
            p = nodes[p].get("parent")
    return excluded


def _looks_like_failure(message: str) -> bool:
    """结果消息是否含失败特征。"""
    low = message.lower()
    return any(marker in message or marker in low for marker in _FAILURE_MARKERS)


def _config_result_messages(cfg: dict, result_texts: list) -> list:
    """取「归属该 config」的结果消息；无法归属时返回空（视为未确认）。

    归属口径：
      · 一般 config：锚定 "<type> : <message>" 结果行（type 精确等于 cfg.type）；
      · mrnbundle：结果页以 "bundleName/version" 标注，按该标识归属。
    """
    cfg_type = cfg.get("type", "")
    info = cfg.get("info", {}) or {}

    if cfg_type == "mrnbundle":
        bundle_id = f"{info.get('bundleName', '')}/{info.get('bundleVersion', '')}"
        if not bundle_id.strip("/"):
            return []
        return [t for t in result_texts if bundle_id in t]

    messages = []
    for t in result_texts:
        m = _RESULT_LINE_RE.match(t)
        if m and m.group("type").strip() == cfg_type:
            messages.append(m.group("msg").strip())
    return messages


def verify_testability_result(config_list: list):
    """检查「扫码配置」结果页，返回失败项描述列表（空=未发现失败）。

    判定**锚定到本次下发的每个 config 自身的结果行**（见本段开头说明）：
      · 结果行存在且含失败特征 → 记为该 config 失败；
      · 结果行存在且无失败特征 → 视为成功；
      · 结果行缺失             → 视为未确认，不判失败。
    同屏的瞬时 Toast（class_name=Toast）不参与判定，避免无关文本污染结论。

    inspect-tree 采集失败时返回空列表——采集不到不等于配置执行失败，
    由调用方通过截图做最终判断（NEEDS_VISUAL_CHECK）。
    """
    raw = dump_inspect_tree(wait_sec=4, max_attempts=2)
    if raw is None:
        sys.stderr.write("⚠️  verify_testability_result: inspect-tree 采集失败，跳过自动校验\n")
        return []

    nodes = parse_inspect_tree(raw)
    excluded = _non_result_indices(nodes)
    result_texts = [
        (n.get("all_text") or "").strip()
        for i, n in enumerate(nodes)
        if i not in excluded and (n.get("all_text") or "").strip()
    ]

    failures = []
    for cfg in config_list:
        for msg in _config_result_messages(cfg, result_texts):
            if _looks_like_failure(msg):
                failures.append(f"{cfg.get('type', '')}: {msg[:120]}")
                break
    return failures

# ═══════════════════════════════════════════════════════════════════
# 环境重置 / 清理
# ═══════════════════════════════════════════════════════════════════

def reset_appmock_environment(mis: str = None) -> bool:
    """执行测试前的 AppMock 环境重置：清理上一次执行可能残留的状态。

    泳道路由规则、代理环境、域名映射均为账号级别全局状态，跨设备、跨执行
    持久化在服务端。清理确保进入测试前 AppMock 处于已知干净状态：
      1) 盘点当前 Mock 规则（仅日志展示，**不做 stop-all**）
      2) 精准关闭 ptest partMock 规则并对称回滚设备侧 htptest 开关
      3) 独立盘点域名映射并清理；swimline-off + env-set online

    **不做 blanket stop-all**：场景 Mock 现为 case 级，由 B0_mock_preflight /
    C1_mock_apply 精确管理；接口 Mock 规则属「本 Skill 声明的 union」之外的
    领域，全量关闭会误伤同域（公共兜底域）他人规则且无法恢复。

    每步独立 try/except，一步失败不影响后续步骤。
    """
    print("RESET-ENV: 开始执行前环境重置...", flush=True)
    all_ok = True

    # 1) 盘点当前 Mock 规则（仅日志展示；不做 stop-all）
    try:
        rules = appmock_list(mis=mis)
        if rules:
            print(f"  ℹ️  当前域内 {len(rules)} 条 Mock 规则（交由 case 级生命周期管理，不 stop-all）")
        else:
            print("  ℹ️  当前无生效的 Mock 规则")
    except Exception as e:
        print(f"  ⚠️  查询现有 Mock 规则失败（不影响后续清理）: {e}")

    # 2) 精准清理 ptest partMock 规则（stop-all 不覆盖 partMock 类型），并**对称回滚**
    #      设备侧 htptest 开关 —— 统一走 disable_ptest_mock 单一入口，避免两处口径漂移。
    try:
        from platform.appmock.ptest import disable_ptest_mock
        disable_ptest_mock(mis=mis)
    except Exception as e:
        print(f"  ⚠️  ptest 规则清理失败: {e}")

    # 3) 盘点并清理域名映射
    try:
        mappings = url_mapping_list(mis)
        if mappings:
            print(f"  ℹ️  发现 {len(mappings)} 条域名映射，尝试关闭激活状态")
            for m in mappings:
                mapping_id = m.get("id") or m.get("mappingId")
                if mapping_id is None:
                    continue
                try:
                    url_mapping_set_env(mapping_id, "close", mis=mis)
                except Exception as e:
                    print(f"    ⚠️  关闭映射 {mapping_id} 失败: {e}")
            print("  ✅ 域名映射已全部关闭激活状态")
        else:
            print("  ℹ️  当前无域名映射记录")
    except Exception as e:
        print(f"  ⚠️  域名映射盘点/清理失败（不影响后续清理）: {e}")

    # 3.5) 清理自动创建的域名映射（幂等）
    try:
        deleted = appmock_cleanup_url_mappings(mis=mis)
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
            print("  ⚠️  环境重置为线上失败（yooz 代理返回非成功，reset-env 可能未生效）")
    except Exception as e:
        all_ok = False
        print(f"  ⚠️  环境重置为线上失败: {e}")

    print(f"RESET-ENV: 完成（{'全部成功' if all_ok else '部分步骤失败，见上方日志'}）")
    return all_ok
