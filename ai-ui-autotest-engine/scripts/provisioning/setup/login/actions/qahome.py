#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QAHome 验证码登录（alpha / 泳道 C·B 共用）：页态状态机 + 发码 / 取码 / 回填提交。

【对外契约】`QahomeAuthAction.perform(plan, ctx) -> AuthOutcome`
（`qahome_login` 是等价的函数式入口）。

【页态口径】登录页与验证码页是同一 Activity 内 Fragment 切换（窗口标识不变），页态只能由
`PageSpec.identity`（页面**内容**身份）判定：`detect_login_state() -> STATE_CODE_PAGE |
STATE_ACCOUNT_PAGE | STATE_NOT_LOGIN_AREA`。窗口名仅作诊断字段 `window_hint`，不参与判定。
硬规则：动作前先断言页态；**发码成功 = 账号页→验证码页的状态迁移**（不是"现在在验证码页"）。

【职责边界】本层做动作级轻量重试 + 码被拒就地重发换码；跨环境完整恢复（清数据冷重启）属
编排层（`orchestrator._perform_with_qahome_recovery`）。`reason` 是两层契约：
`page_state_invalid`（起点不可归一）会让本层跳过动作级重试、直接交编排层完整恢复。
"""
import time
from typing import List, Optional, Tuple

from platform.appmock.device import appmock_ready
from shared.context import get_app_descriptor, get_platform_ops
from shared.errors import soft_fail

from execution.screen.inspect_tree import (
    dump_inspect_tree, invalidate_cache, parse_inspect_tree, resolve, supports,
)
from provisioning.setup.app_lifecycle import _current_focus_window, wait_app_foreground
from provisioning.setup.login import evidence
from provisioning.setup.login.actions import AuthAction
from provisioning.setup.login.actions.sms import qahome_query_sms, select_code_for_request
from provisioning.setup.login.policy import AuthOutcome
from provisioning.setup.login.probes.android import check_login_state, login_go_home


# 登录页/验证码页的**身份判定与控件定位**全部来自 AppDescriptor 的 PageSpec 数据
# （devices/interfaces/page_spec.py）——本模块只按**语义名**取控件，不含任何
# 资源 id / 文案 / 平台判断：新增平台（iOS）= 补一份数据，本文件零改动。
_CTL_PHONE = "phone_input"
_CTL_SEND_CODE = "send_code"
_CTL_AGREEMENT = "agreement"
# 协议勾选**状态**的来源，与"点哪里"分离：平台没有可信状态源就不声明（→ 状态不可知）。
# 不能拿"点击目标"当"状态源"：鸿蒙勾选框是装饰性 Image（恒 checked=false），
# 误信会把"未暴露状态"当成"未勾选"，从而反复点击（实测踩过）。
_CTL_AGREEMENT_STATE = "agreement_state"
_CTL_CODE = "code_input"
# 简化版登录页（预填手机号）的"验证码登录"直入按钮；数据缺失即自然解不出。
_CTL_QUICK_LOGIN = "quick_login"
# 验证码页的两个**内容**语义（不是可点控件必命中项）：
#   · resend_code —— 码被拒后就地重发（文案随版本变，故为数据）
#   · code_error  —— "码被拒"的页面文案（失败态识别，text 选择器）
_CTL_RESEND = "resend_code"
_CTL_CODE_ERROR = "code_error"

# ── 页态常量（状态机取值）────────────────────────────────────────────
STATE_CODE_PAGE = "code_page"
STATE_ACCOUNT_PAGE = "account_page"
STATE_NOT_LOGIN_AREA = "not_login_area"

# ── 登录页交互稳定性参数 ────────────────────────────────────────────
_INPUT_SETTLE = 0.8            # 手机号输入框点击聚焦后的稳定等待
_TYPE_SETTLE = 1.0             # 输入法异步提交后的页面重排稳定等待
_AGREEMENT_MAX_ATTEMPTS = 3    # 协议勾选最多尝试次数（原坐标 + 左右微调）
_AGREEMENT_TAP_OFFSETS = ((0, 0), (-30, 0), (30, 0))  # 勾选点偏移，抵消坐标轻微漂移
_AGREEMENT_SETTLE = 0.8        # 勾选后等待状态更新的稳定等待
_GET_CODE_MAX_ATTEMPTS = 3     # "勾选协议 + 点获取验证码 + 校验迁移"最多尝试次数
_CODE_PAGE_TIMEOUT = 12.0      # 点"获取验证码"后等待页面迁移的最长时间（单次采集≈5s）
_STATE_POLL_INTERVAL = 1.2     # 页态轮询间隔
_BACK_MAX_ATTEMPTS = 2         # 从验证码页回退到账号页的返回键次数上限（非重启原语）

# ── 登录页采集与勾选态复读参数（统一口径，避免"定位强采集 / 复读弱采集"）────────
_LOGIN_DUMP_WAIT_SEC = 6             # 登录页统一采集等待
_LOGIN_DUMP_MAX_ATTEMPTS = 2         # 登录页统一采集重试
_AGREEMENT_STATE_READ_ATTEMPTS = 3   # 勾选态复读次数（单次采集可能瞬时落空）
_AGREEMENT_STATE_READ_SETTLE = 0.6   # 勾选态复读间隔

# ── 提交验证码后的等待与现场判定 ────────────────────────────────────
_SUBMIT_TIMEOUT = 25.0         # 输入验证码后等待前台自然回归的最长时间
_SUBMIT_POLL_INTERVAL = 2.0    # 前台轮询间隔（廉价查询，不必每次采集视图树）
_SUBMIT_VERDICT_AFTER = 3      # 连续 N 轮未回前台才开始"判现场"（避免刚提交就采集）
_MAX_INPLACE_RESEND = 1        # 码被拒后就地重发换码的最大次数（不重整轮触发）

# ── 短信轮询：阶梯退避 + 总时长预算 ─────────────────────────────────
_SMS_BUDGET_S = 75.0                        # 单次取码的总时长预算
_SMS_BACKOFF = (2.0, 3.0, 5.0, 8.0, 12.0)   # 阶梯退避（新码可能晚几秒入库）
_SMS_RATE_LIMIT_AFTER = 2                   # 连续 N 轮只见旧码 → 疑似网关频控
_SMS_RATE_LIMIT_INTERVAL = 30.0             # 疑似频控后的查询间隔（不再高频打网关）

# ── 动作级重试 ─────────────────────────────────────────────────────
_ACTION_MAX_ATTEMPTS = 2       # 本层轻量重试次数（点击/输入抖动）；跨环境重试属编排层


def _login_page_spec():
    from devices.interfaces.page_spec import PAGE_LOGIN
    return get_app_descriptor().page_specs.get(PAGE_LOGIN)


def _code_page_spec():
    from devices.interfaces.page_spec import PAGE_LOGIN_CODE
    return get_app_descriptor().page_specs.get(PAGE_LOGIN_CODE)


def _dump_nodes(wait_sec=4, max_attempts=1):
    """采集并解析当前页面节点（统一 dump 入口，避免各处重复参数）。"""
    invalidate_cache()
    raw = dump_inspect_tree(wait_sec=wait_sec, max_attempts=max_attempts)
    return parse_inspect_tree(raw) if raw else []


def _dump_login_nodes():
    """登录页统一采集入口：元素定位与状态读取共用**同一采集口径**。

    为什么必须统一：历史回归是"定位用强采集（wait=6/max_attempts=2）、复读用弱采集
    （wait=4/单次）"，点完复选框页面抖动时复读更容易落空 → checked=None → 误报
    "无法判定协议勾选状态"。所有登录页采集都走本入口，杜绝口径分叉。
    """
    return _dump_nodes(wait_sec=_LOGIN_DUMP_WAIT_SEC, max_attempts=_LOGIN_DUMP_MAX_ATTEMPTS)


def _resolve_control(name, spec=None, nodes=None, wait_sec=4):
    """按 PageSpec 的选择器解析语义控件；返回解析结果（point/text/…）或 None。"""
    page = spec or _login_page_spec()
    if page is None:
        return None
    selectors = page.control(name)
    if not selectors:
        return None
    return resolve(nodes if nodes is not None else _dump_nodes(wait_sec=wait_sec),
                   selectors)


def _texts_of(nodes) -> str:
    return " ".join((n.get("all_text") or "") for n in (nodes or []))


def _identity_hit(nodes, spec) -> bool:
    """页面内容是否命中该 PageSpec 的**身份**（纯内容判定，跨端可靠）。"""
    if spec is None or not nodes:
        return False
    return supports(_texts_of(nodes), spec.identity)


# ═══════════════════════════════════════════════════════════════════
# 页面状态机（本模块唯一的页态口径）
# ═══════════════════════════════════════════════════════════════════

def detect_login_state(nodes=None, *, wait_sec=4, max_attempts=1) -> Tuple[str, dict]:
    """判定当前登录区域页态；返回 `(state, evidence)`。

    判定顺序固定「验证码页 → 账号页 → 非登录区域」；`evidence["nodes"]` 复用本次采集，
    避免同一次操作重复采集（单次约 5s，是登录耗时主成本）。
    evidence 字段：`nodes` / `focus` / `window_hint`（窗口名，**仅诊断**）。
    """
    if nodes is None:
        nodes = _dump_nodes(wait_sec=wait_sec, max_attempts=max_attempts)
    focus = _current_focus_window()
    login_spec = _login_page_spec()
    info = {
        "nodes": nodes or [],
        "focus": focus,
        "window_hint": bool(login_spec and login_spec.matches_window(focus)),
    }
    if _identity_hit(nodes, _code_page_spec()):
        return STATE_CODE_PAGE, info
    if _identity_hit(nodes, login_spec):
        return STATE_ACCOUNT_PAGE, info
    return STATE_NOT_LOGIN_AREA, info


def _wait_for_state(target: str, *, timeout: float, trace=None,
                    interval: float = _STATE_POLL_INTERVAL) -> Tuple[bool, dict]:
    """等待页态变为 `target`；返回 `(是否到达, 末次证据)`。

    迁移语义由调用方保证：调用点点击前已断言在账号页，故"观测到验证码页"等价于
    "发码请求真的被受理"。
    """
    deadline = time.time() + timeout
    round_no = 0
    state, info = STATE_NOT_LOGIN_AREA, {}
    while True:
        state, info = detect_login_state()
        round_no += 1
        if state == target:
            return True, info
        if trace is not None:
            trace.event("state_poll", target=target, round=round_no, state=state)
        if time.time() >= deadline:
            info = dict(info or {})
            info["state"] = state
            return False, info
        time.sleep(interval)


def _return_to_account_page(ops, trace) -> bool:
    """从验证码页回退到账号页（**非重启原语**：返回键）。

    L3 不允许调用重启原语（架构守卫规则 15b：重启点必须声明在 L2 steps 上），因此
    "起点归一"在动作层只能靠返回键；回不去就交给编排层做完整恢复（冷重启）。
    """
    for i in range(1, _BACK_MAX_ATTEMPTS + 1):
        print(f"QAHOME-LOGIN: 返回键回退到账号页（第 {i}/{_BACK_MAX_ATTEMPTS} 次）")
        ops.press_back()
        time.sleep(1.0)
        state, _info = detect_login_state()
        trace.event("back_to_account", round=i, state=state)
        if state == STATE_ACCOUNT_PAGE:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════
# 账号页元素定位与协议勾选
# ═══════════════════════════════════════════════════════════════════

def _locate_login_elements(nodes=None):
    """一次采集批量定位登录页元素（避免逐控件各采一次，每次 3-6s）。

    Returns:
        dict: {"phone_input": (cx,cy)|None, "checkbox": {...}|None, "send_code_btn": (cx,cy)|None}
        `checkbox.checked` 为三值：True/False 为真实勾选态，None 表示未暴露勾选属性。
    """
    result = {"phone_input": None, "checkbox": None, "send_code_btn": None}
    page = _login_page_spec()
    if page is None:
        return result
    nodes = nodes if nodes is not None else _dump_login_nodes()
    if not nodes:
        return result
    # 语义名 → 选择器序列（来自 PageSpec）：Android 命中 id、鸿蒙命中 role/text，
    # 平台差异在这里退化为**数据顺序**，调用方无需分支。
    for key, control in (("phone_input", _CTL_PHONE),
                         ("send_code_btn", _CTL_SEND_CODE)):
        hit = resolve(nodes, page.control(control))
        if hit:
            result[key] = hit["point"]
    agree = resolve(nodes, page.control(_CTL_AGREEMENT))
    if agree:
        # 勾选态**只从状态源读**（未声明/未命中 → None = 不可知，调用方按"已点击"接受）
        state = resolve(nodes, page.control(_CTL_AGREEMENT_STATE)) or {}
        result["checkbox"] = {"center": agree["point"], "checked": state.get("checked")}
    return result


def _read_checkbox_state(max_attempts=_AGREEMENT_STATE_READ_ATTEMPTS):
    """读取协议勾选态：单次采集同时解析"点哪里"与"状态源"，落空时有界复读。

    Returns dict {"center", "checked": bool|None, "has_state_source", "found"}。
    `checked=None` 区分原因：`has_state_source=False` = 未声明状态源（合法未知，按已点击接受）；
    `has_state_source=True` 且 None = 确实读不到（采集落空，异常）。
    """
    page = _login_page_spec()
    if page is None:
        return {"center": None, "checked": None, "has_state_source": False, "found": False}
    state_selectors = page.control(_CTL_AGREEMENT_STATE)
    has_state_source = bool(state_selectors)
    center = None
    for i in range(max(1, max_attempts)):
        nodes = _dump_login_nodes()
        hit = resolve(nodes, page.control(_CTL_AGREEMENT)) if nodes else None
        if hit:
            center = hit["point"]
            if not has_state_source:
                # 未声明状态源 → 不可判定是**预期**行为，直接返回（不空转复读）
                return {"center": center, "checked": None,
                        "has_state_source": False, "found": True}
            checked = (resolve(nodes, state_selectors) or {}).get("checked")
            if checked is not None:
                return {"center": center, "checked": checked,
                        "has_state_source": True, "found": True}
            print(f"QAHOME-LOGIN: 勾选态读取落空（第 {i + 1}/{max_attempts} 次），复读…")
        else:
            print(f"QAHOME-LOGIN: 未定位到协议复选框（第 {i + 1}/{max_attempts} 次），复读…")
        if i + 1 < max_attempts:
            time.sleep(_AGREEMENT_STATE_READ_SETTLE)
    return {"center": center, "checked": None,
            "has_state_source": has_state_source, "found": center is not None}


def _ensure_agreement_checked(checkbox, ops):
    """确认协议已勾选；仅未勾选才点击，落空后在复选框周边微调重试（避免盲点取反）。

    Returns: True=已确认勾选（或未声明状态源，按已点击继续）；False=声明了状态源但
    多轮后仍未确认。
    """
    if not checkbox:
        print("QAHOME-LOGIN: ⚠️ 未定位到协议复选框（PageSpec 控件 agreement），跳过协议勾选")
        return True

    center = checkbox.get("center")
    if checkbox.get("checked") is True:
        print("QAHOME-LOGIN: 协议已勾选，跳过点击（避免误取消）")
        return True

    for i in range(_AGREEMENT_MAX_ATTEMPTS):
        dx, dy = _AGREEMENT_TAP_OFFSETS[min(i, len(_AGREEMENT_TAP_OFFSETS) - 1)]
        tap_xy = (center[0] + dx, center[1] + dy)
        print(f"QAHOME-LOGIN: 勾选协议 @ {tap_xy}（第 {i + 1}/{_AGREEMENT_MAX_ATTEMPTS} 次）")
        ops.tap(*tap_xy)
        time.sleep(_AGREEMENT_SETTLE)

        state = _read_checkbox_state()
        if state.get("checked") is True:
            print("QAHOME-LOGIN: ✅ 协议已确认勾选")
            return True
        if state.get("center"):
            center = state["center"]
        if not state.get("has_state_source"):
            # 未声明勾选态来源 → 按已点击接受（避免把"读不到状态"误当"未勾选"反复点击）
            print("QAHOME-LOGIN: ⚠️ 该页面未声明协议勾选态来源，按已点击继续")
            return True
        if not state.get("found"):
            print("QAHOME-LOGIN: ⚠️ 复读未定位到协议复选框（采集疑似异常），重试...")
        else:
            print(f"QAHOME-LOGIN: 协议仍未勾选（checked={state.get('checked')}），重试...")
    # 声明了状态源、多轮点击后仍读不到 = 要么没勾上、要么采集异常。
    # 不再"乐观地按已点击继续"：那会让后续"获取验证码"在按钮禁用时空点，
    # 产生"已发码"假象。宁可失败并上抛，也不伪造成功。
    print("QAHOME-LOGIN: ❌ 多轮尝试后仍未确认协议勾选（声明了状态源但读不到，疑似采集异常）")
    return False


def _settle_system_overlay() -> bool:
    """收敛抢占前台的**系统层引导**（如输入法首启向导），返回是否确有收敛。

    它带独立系统窗口接管前台，按包名过滤的视图树会采不到登录页。复用 L2 唯一入口自愈
    （L3 不自建弹窗实现，架构守卫规则 21/22）。
    """
    from provisioning.setup.environment_reconciler import reconcile_system_onboarding

    try:
        result = reconcile_system_onboarding(label="QAHOME-LOGIN:overlay")
    except Exception as e:  # noqa: BLE001 —— 自愈失败不改变原判定（仍按控件缺失处理）
        print(f"QAHOME-LOGIN: ⚠️ 系统引导收敛异常（忽略）: {e}")
        return False
    return bool(result and result.any_dismissed)


# ═══════════════════════════════════════════════════════════════════
# 导航到登录页
# ═══════════════════════════════════════════════════════════════════

def _navigate_route(route, ops) -> bool:
    """按一条 `Route` **逐跳**导航到登录页；每跳点完先判是否已到，再校验本跳生效才续跳。

    入口多态（底部登录横幅 / 我的 / 头像入口）是**数据**，由 `PageSpec.routes` 声明；
    本层不写死任何入口文案（守卫规则 21）。
    """
    for hop in route.hops:
        nodes = _dump_nodes(wait_sec=6, max_attempts=2)
        if not nodes:
            return False
        hit = resolve(nodes, hop.enter)
        if not hit:
            return False
        if not ops.tap(*hit["point"]):
            return False
        time.sleep(1)
        state, _info = detect_login_state()
        if state == STATE_ACCOUNT_PAGE:
            return True
        if not supports(_texts_of(_dump_nodes(wait_sec=2)), hop.expect):
            print("QAHOME-LOGIN: ⚠️ 本跳点击后未生效（expect 未出现），放弃该路径")
            return False
    state, _info = detect_login_state()
    return state == STATE_ACCOUNT_PAGE


def _navigate_to_login(ops) -> bool:
    """按 `PageSpec.routes` 逐条候选路径导航到登录页；全失败返回 False。"""
    page = _login_page_spec()
    if page is None or not page.routes:
        return False
    for route in page.routes:
        if _navigate_route(route, ops):
            return True
    return False


# ═══════════════════════════════════════════════════════════════════
# 步骤 1：账号页动作 + 发码（成功判据 = 状态迁移）
# ═══════════════════════════════════════════════════════════════════

def _request_code(phone, ops, trace) -> Tuple[bool, float, str]:
    """账号页动作：输入手机号 → 确认协议勾选 → 点获取验证码 → **校验状态迁移**。

    Returns:
        (True, click_ts, "") — 发码请求已受理（页面已从账号页迁移到验证码页）
        (False, 0, reason)   — reason ∈ {page_state_invalid, code_not_sent, send_code_missing}
    """
    # 1. 页态断言：只有在账号页才允许执行本动作（否则会误把验证码框当手机号框）
    state, info = detect_login_state()
    if state != STATE_ACCOUNT_PAGE:
        print(f"QAHOME-LOGIN: ❌ 页态不匹配（期望账号页，实得 {state}），拒绝执行账号页动作")
        trace.event("account_action_rejected", state=state)
        trace.shot("account_action_rejected")
        trace.tree("account_action_rejected", info.get("nodes"), {"state": state})
        return False, 0, "page_state_invalid"

    nodes = info.get("nodes")
    elements = _locate_login_elements(nodes=nodes)
    phone_field = elements.get("phone_input")
    if not phone_field:
        print("QAHOME-LOGIN: ❌ 未找到手机号输入框（PageSpec 控件 phone_input）")
        trace.shot("phone_input_missing")
        trace.tree("phone_input_missing", nodes, {"state": state})
        return False, 0, "page_state_invalid"

    # 2. 输入手机号（输入法异步提交，后置等待需覆盖输入 + 页面重排）
    print(f"QAHOME-LOGIN: 输入账号 @ {phone_field}")
    if not ops.tap(*phone_field):
        print("QAHOME-LOGIN: ❌ tap 手机号输入框失败")
        return False, 0, "page_state_invalid"
    time.sleep(_INPUT_SETTLE)
    ops.input_text(phone)          # 输入法由 PlatformOps 自理（不在输入后自动收键盘）
    time.sleep(_TYPE_SETTLE)

    # 3. 勾选协议 + 点获取验证码 + 校验迁移（有界重试，每轮复采坐标）
    for attempt in range(1, _GET_CODE_MAX_ATTEMPTS + 1):
        nodes = _dump_login_nodes()
        if not _identity_hit(nodes, _login_page_spec()):
            # 输入手机号后页面可能已被弹窗/系统引导顶掉：先收敛再重试（唯一入口）
            if attempt < _GET_CODE_MAX_ATTEMPTS and _settle_system_overlay():
                continue
            print(f"QAHOME-LOGIN: ❌ 第 {attempt} 轮已不在账号页（采集异常或页面被顶掉）")
            trace.shot("account_page_lost")
            trace.tree("account_page_lost", nodes)
            return False, 0, "page_state_invalid"

        echo = _verify_input_text(nodes, _CTL_PHONE, phone, trace, "手机号")
        if attempt == 1:
            trace.event("phone_entered", coord=list(phone_field), echo=echo)
            trace.shot("phone_entered")

        elements = _locate_login_elements(nodes=nodes)
        send_btn = elements.get("send_code_btn")
        if not send_btn:
            if attempt < _GET_CODE_MAX_ATTEMPTS and _settle_system_overlay():
                continue
            print(f"QAHOME-LOGIN: ❌ 第 {attempt} 轮未找到获取验证码按钮（PageSpec 控件 send_code）")
            trace.shot("send_code_missing")
            trace.tree("send_code_missing", nodes)
            return False, 0, "send_code_missing"

        if not _ensure_agreement_checked(elements.get("checkbox"), ops):
            print(f"QAHOME-LOGIN: ⚠️ 第 {attempt} 轮协议仍未勾选，重试...")
            time.sleep(0.5)
            continue

        print(f"QAHOME-LOGIN: 点击获取验证码 @ {send_btn}（第 {attempt}/{_GET_CODE_MAX_ATTEMPTS} 次）")
        ops.tap(*send_btn)
        click_ts = time.time()
        trace.event("code_requested", coord=list(send_btn), round=attempt)

        arrived, _vinfo = _wait_for_state(STATE_CODE_PAGE, timeout=_CODE_PAGE_TIMEOUT,
                                          trace=trace)
        if arrived:
            print(f"QAHOME-LOGIN: ✅ 已进入验证码输入页，验证码请求已受理 "
                  f"({time.strftime('%H:%M:%S')})")
            trace.event("code_page_arrived", coord=list(send_btn), round=attempt)
            trace.shot("code_page_arrived")
            return True, click_ts, ""
        print(f"QAHOME-LOGIN: ⚠️ 第 {attempt} 轮点击后 {_CODE_PAGE_TIMEOUT:.0f}s 内未迁移到验证码页，重试...")
        trace.event("code_page_not_arrived", round=attempt)
        time.sleep(0.5)

    print("QAHOME-LOGIN: ❌ 多轮尝试后仍未迁移到验证码页，判定验证码发送失败")
    trace.shot("code_not_sent")
    return False, 0, "code_not_sent"


def _verify_input_text(nodes, control_name, expect, trace, label) -> str:
    """尽力回读输入框文本做落地校验，返回 `ok` / `mismatch` / `unverifiable`。

    采集能力降级时读不到文本属预期（返回 unverifiable 并只记事件），不改变主流程判定。
    """
    spec = _code_page_spec() if control_name == _CTL_CODE else _login_page_spec()
    if spec is None:
        return "unverifiable"
    hit = resolve(nodes or [], spec.control(control_name)) or {}
    text = (hit.get("text") or "").strip()
    if not text:
        trace.event("input_echo", field=label, result="unverifiable")
        return "unverifiable"
    digits = "".join(ch for ch in text if ch.isdigit())
    want = "".join(ch for ch in str(expect) if ch.isdigit())
    hit_ok = bool(want) and (want in digits or want[-4:] in digits)
    print(f"QAHOME-LOGIN: 输入回显{'一致' if hit_ok else '不一致'}（{label}）")
    trace.event("input_echo", field=label, result="ok" if hit_ok else "mismatch")
    return "ok" if hit_ok else "mismatch"


# ═══════════════════════════════════════════════════════════════════
# 步骤 2：取码（阶梯退避 + 频控识别）
# ═══════════════════════════════════════════════════════════════════

def _log_code_selection(diagnostics):
    """把取码丢弃原因打进日志：区分「新码还没到」与「只查到旧码/脏数据」。"""
    print(f"QAHOME-LOGIN: 本批短信 {diagnostics.get('total', 0)} 条，"
          f"验证码类 {diagnostics.get('code_like', 0)} 条"
          f"（最新码时差 {diagnostics.get('skew_seconds', 0)}s）")
    for code, sms_time_str in diagnostics.get("stale", []):
        print(f"QAHOME-LOGIN: ⏭️ 跳过非本次请求的验证码: {code} ({sms_time_str})")
    for code, sms_time_str in diagnostics.get("unparsable", []):
        print(f"QAHOME-LOGIN: ⏭️ 跳过下发时刻不可解析的验证码: {code} ({sms_time_str!r})")


def qahome_login_wait_code(phone, click_ts, *, trace=None,
                           budget_s: float = _SMS_BUDGET_S) -> Tuple[bool, str, str]:
    """轮询短信池，取「本次请求下发」的验证码（取码规则见 `select_code_for_request`）。

    有界轮询 + 阶梯退避（2→3→5→8→12s）+ 总预算（默认 75s）；连续 `_SMS_RATE_LIMIT_AFTER`
    轮只见旧码 → 判疑似网关频控并拉长间隔。**不会**退而求其次用旧码（旧码已被作废）。
    """
    anchor = click_ts or time.time()
    deadline = time.time() + budget_s
    empty_rounds = 0
    round_no = 0
    print(f"QAHOME-LOGIN: 轮询获取验证码（总预算 {budget_s:.0f}s，只接受本次请求下发的验证码）...")
    while time.time() < deadline and empty_rounds < len(_SMS_BACKOFF) * 6:
        round_no += 1
        print(f"QAHOME-LOGIN: 查询验证码 {round_no}...")
        results = qahome_query_sms(phone, timeout=10)
        code, sms_time_str, diagnostics = select_code_for_request(results or [], anchor)
        if trace is not None:
            trace.event("sms_query", round=round_no, got_code=bool(code),
                        newest_sms_time=sms_time_str or "",
                        counts={k: v for k, v in diagnostics.items()
                                if k in ("total", "code_like")},
                        skew_seconds=diagnostics.get("skew_seconds", 0),
                        stale=[c for c, _t in diagnostics.get("stale", [])])
        if code:
            print(f"QAHOME-LOGIN: ✅ 验证码: {code} ({sms_time_str})")
            return True, code, ""
        _log_code_selection(diagnostics)
        empty_rounds += 1
        if empty_rounds >= _SMS_RATE_LIMIT_AFTER:
            interval = _SMS_RATE_LIMIT_INTERVAL
            print(f"QAHOME-LOGIN: ⚠️ 连续 {empty_rounds} 轮未取到新码，疑似网关频控 → "
                  f"查询间隔拉长到 {interval:.0f}s")
            if trace is not None:
                trace.event("sms_rate_limit_suspect", round=round_no, empty_rounds=empty_rounds)
        else:
            interval = _SMS_BACKOFF[min(empty_rounds - 1, len(_SMS_BACKOFF) - 1)]
        remain = deadline - time.time()
        if remain <= 0:
            break
        time.sleep(min(interval, remain))
    reason = "sms_rate_limited" if empty_rounds >= _SMS_RATE_LIMIT_AFTER else "no_new_sms"
    print(f"QAHOME-LOGIN: ❌ {budget_s:.0f}s 内未获取到本次请求的验证码（{reason}）")
    return False, "", reason


# ═══════════════════════════════════════════════════════════════════
# 步骤 3：回填验证码 + 提交（含"码被拒"就地自愈）
# ═══════════════════════════════════════════════════════════════════

def _find_code_input(nodes=None):
    """验证码输入框（选择器来自 PageSpec 的 `code_input`）；不在验证码页则返回 None。

    先确认页态是验证码页（**内容身份**），再解析输入框 —— 否则 `code_input` 的 `role`
    兜底会命中账号页的手机号框，把验证码输进手机号。
    """
    if nodes is None:
        nodes = _dump_nodes(wait_sec=4)
    if not _identity_hit(nodes, _code_page_spec()):
        return None
    spec = _code_page_spec()
    if spec is None:
        return None
    hit = resolve(nodes, spec.control(_CTL_CODE))
    if not hit:
        return None
    return {"center": hit["point"], "clickable": hit.get("clickable", False)}


def _has_code_error(nodes) -> bool:
    """验证码页是否出现「码被拒」失败态文案（**内容匹配**，文案是数据）。

    用 text 选择器而不是控件解析：失败态是**页面内容**，不是可点控件；也只认 text
    型选择器，避免 `role` 兜底把别的页面的元素当成"错误提示"（守卫规则 30 的口径）。
    """
    spec = _code_page_spec()
    if spec is None or not nodes:
        return False
    return supports(_texts_of(nodes), spec.control(_CTL_CODE_ERROR))


def _tap_resend(trace) -> bool:
    """在验证码页点「重新获取」（控件来自 PageSpec 数据；未声明即该路径不可用）。"""
    nodes = _dump_nodes(wait_sec=3)
    hit = _resolve_control(_CTL_RESEND, spec=_code_page_spec(), nodes=nodes)
    if not hit:
        print("QAHOME-LOGIN: ⚠️ 未定位到「重新获取」控件（PageSpec 未声明或文案变化），"
              "无法就地重发")
        return False
    print(f"QAHOME-LOGIN: 点击重新获取验证码 @ {hit['point']}")
    return bool(get_platform_ops().tap(*hit["point"]))


def _diagnose_submit_failure(code, trace) -> Tuple[str, dict]:
    """提交后未回前台时判一次现场，返回 `(reason, evidence)`。

    采集一次视图树即可回答：还在验证码页吗？在报"码被拒"吗？码真进框了吗？
    """
    state, info = detect_login_state()
    nodes = info.get("nodes") or []
    if state == STATE_CODE_PAGE:
        if _has_code_error(nodes):
            return "code_rejected", info
        echo = _verify_input_text(nodes, _CTL_CODE, code, trace, "验证码")
        return ("code_not_entered" if echo == "mismatch" else "submit_timeout"), info
    return "foreground_not_restored", info


def _submit_code_once(code, ops, trace) -> Tuple[bool, str]:
    """输入验证码 → 等待前台自然回归；返回 `(ok, reason)`。"""
    state, info = detect_login_state()
    if state != STATE_CODE_PAGE:
        print(f"QAHOME-LOGIN: ❌ 提交前页态不是验证码页（实得 {state}）")
        trace.event("submit_rejected", state=state)
        return False, "page_state_invalid"

    code_input = _find_code_input(nodes=info.get("nodes"))
    if not code_input:
        print("QAHOME-LOGIN: ❌ 未找到验证码输入框（PageSpec 控件 code_input）")
        trace.shot("code_input_missing")
        trace.tree("code_input_missing", info.get("nodes"), {"state": state})
        return False, "code_input_missing"

    print(f"QAHOME-LOGIN: 输入验证码 {code} @ {code_input['center']}")
    if not ops.tap(*code_input["center"]):
        print("QAHOME-LOGIN: ❌ tap 验证码输入框失败")
        return False, "code_input_missing"
    time.sleep(0.5)
    if not ops.input_text(code):
        print("QAHOME-LOGIN: ⚠️ 输入验证码命令执行失败")
    time.sleep(3)
    trace.event("code_input", coord=list(code_input["center"]))
    trace.shot("code_input")

    print(f"QAHOME-LOGIN: 等待登录自然完成（最多 {_SUBMIT_TIMEOUT:.0f}s）...")
    deadline = time.time() + _SUBMIT_TIMEOUT
    round_no = 0
    while time.time() < deadline:
        round_no += 1
        if get_app_descriptor().is_foreground(_current_focus_window()):
            print(f"QAHOME-LOGIN: 焦点已自然回到前台（第 {round_no} 轮）")
            trace.event("foreground_back", round=round_no)
            return True, ""
        print(f"QAHOME-LOGIN: 第 {round_no} 轮尚未回到 App 前台，{_SUBMIT_POLL_INTERVAL:.0f}s 后重试...")
        if round_no == _SUBMIT_VERDICT_AFTER:
            # 提交后长时间不回前台 → 判一次现场（可能码被拒，也可能只是慢）
            reason, _info = _diagnose_submit_failure(code, trace)
            trace.event("submit_verdict_midway", reason=reason, round=round_no)
            if reason == "code_rejected":
                trace.shot("code_rejected")
                trace.tree("code_rejected", _info.get("nodes"), {"state": STATE_CODE_PAGE})
                return False, reason
        time.sleep(_SUBMIT_POLL_INTERVAL)

    reason, info = _diagnose_submit_failure(code, trace)
    print(f"QAHOME-LOGIN: ❌ {_SUBMIT_TIMEOUT:.0f}s 内未回到 App 前台（现场判定={reason}）")
    trace.event("submit_timeout_verdict", reason=reason)
    trace.shot(f"stuck_{reason}")
    trace.tree(f"stuck_{reason}", info.get("nodes"), {"state": info.get("state", "")})
    return False, reason


def qahome_login_submit_code(phone, code, trace) -> Tuple[bool, str]:
    """回填验证码并确认登录态；码被拒时在验证码页就地重发换码（不重整轮触发）。
    """
    ops = get_platform_ops()
    for round_no in range(1, _MAX_INPLACE_RESEND + 2):
        ok, reason = _submit_code_once(code, ops, trace)
        if ok:
            time.sleep(2)
            is_logged_in, detail = check_login_state()
            if not is_logged_in:
                print(f"QAHOME-LOGIN: ❌ {detail}")
                trace.event("login_state_unconfirmed", detail=detail)
                trace.shot("state_unconfirmed")
                return False, "login_state_unconfirmed"
            print(f"QAHOME-LOGIN: ✅ {detail}")
            if not login_go_home():
                print("QAHOME-LOGIN: ❌ 跳回主页后前台未稳定，判定失败")
                trace.shot("go_home_failed")
                return False, "login_state_unconfirmed"
            trace.event("success", detail=detail)
            trace.shot("success")
            return True, ""
        if reason != "code_rejected":
            return False, reason
        if round_no > _MAX_INPLACE_RESEND:
            print("QAHOME-LOGIN: ❌ 就地重发换码后仍被拒，判定失败")
            return False, reason

        print("QAHOME-LOGIN: 🔁 验证码被拒 → 就地在验证码页重新获取（不重整轮触发）")
        trace.event("inplace_resend", round=round_no)
        if not _tap_resend(trace):
            return False, reason
        got, new_code, sms_reason = qahome_login_wait_code(phone, time.time(), trace=trace)
        if not got:
            return False, sms_reason
        code = new_code
        trace.event("inplace_resend_code", round=round_no)
    return False, "code_rejected"


# ═══════════════════════════════════════════════════════════════════
# 触发（起点归一 + 导航 + 发码）
# ═══════════════════════════════════════════════════════════════════

def qahome_login_trigger(phone, mock_enabled, trace) -> Tuple[bool, float, str]:
    """把 App 带到账号页并发出验证码请求；兼容简化版（预填手机号）与标准版登录页。

    起点归一：若停在验证码页先返回账号页（非重启原语），回不去 → `page_state_invalid`
    交编排层完整恢复。返回 `(True, click_ts, "")` 或 `(False, 0, reason)`。
    """
    ops = get_platform_ops()
    app = get_app_descriptor()

    focus = _current_focus_window()
    print(f"[LOGIN-DIAG] 初始焦点: {focus!r}, PID: {ops.pidof(app.package_name)!r}")
    if wait_app_foreground(timeout=10):
        print("QAHOME-LOGIN: ✅ App 在前台，开始登录流程")
    else:
        print("QAHOME-LOGIN: ⚠️ App 未在前台，仍继续尝试")

    # 环境澄清**复核**（与 password 动作同一契约）：L2 前置的澄清已排在最后一次冷重启
    # 之后，但本流程自己还会把 App 拉起 / 走一次导航，而系统一次性弹窗（通知/定位引导）
    # 是在 App 启动**之后**才出现的——不澄清会直接挡住登录页，使后面的元素定位与登录态
    # 判定双双失败。走**唯一入口**（同一实现，不重启），本层不自建第二套澄清。
    from provisioning.setup.environment_reconciler import reconcile_environment

    reconcile_environment(wait_for_popup_ms=3000, label="QAHOME-LOGIN")

    if mock_enabled:
        print("QAHOME-LOGIN: 保持 AppMock 开启状态...")
        # 语义判定走能力位（appmock_ready）：不可确认平台（鸿蒙）由 EnableAppMock
        # 负责下发、已下发即视为就绪；不得直接消费真实状态原语 check_appmock_sdk_enabled
        # （它在鸿蒙恒为 False，会把平台差异以隐式分支带进业务层）。
        if not appmock_ready():
            print("QAHOME-LOGIN: ❌ 设备端 AppMock SDK 未启用")
            return False, 0, "appmock_unconfirmed"
        print("QAHOME-LOGIN: ✅ AppMock SDK 已就绪")

    state, info = detect_login_state()
    trace.event("entry", state=state, focus=info.get("focus"),
                window_hint=info.get("window_hint"),
                pid=ops.pidof(app.package_name))
    trace.shot("entry")

    if state == STATE_CODE_PAGE:
        print("QAHOME-LOGIN: ⚠️ 当前停在验证码页（上次尝试未收尾）→ 先回退到账号页")
        if _return_to_account_page(ops, trace):
            state = STATE_ACCOUNT_PAGE
        else:
            state, info = detect_login_state()
            if state == STATE_CODE_PAGE:
                print("QAHOME-LOGIN: ❌ 无法从验证码页回到账号页（起点不可归一）")
                trace.event("state_invalid", state=state)
                trace.shot("state_invalid")
                trace.tree("state_invalid", info.get("nodes"), {"state": state})
                return False, 0, "page_state_invalid"
            print(f"QAHOME-LOGIN: 返回后已离开登录区域（{state}）→ 走导航路径")

    if state != STATE_ACCOUNT_PAGE:
        print(f"[LOGIN-DIAG] 不在账号页, state={state}, focus={info.get('focus')!r}")
        if not app.is_foreground(_current_focus_window()):
            print("QAHOME-LOGIN: App 不在前台，拉回首页...")
            if not ops.launch_app(app.main_activity):
                print("QAHOME-LOGIN: ❌ launch_app 失败")
                return False, 0, "not_login_page"
            time.sleep(2)
            print(f"[LOGIN-DIAG] launch_app 后焦点: {_current_focus_window()!r}")

        if not _navigate_to_login(ops):
            print("QAHOME-LOGIN: ❌ 导航到登录页失败（PageSpec.routes 候选路径均未生效）")
            trace.event("navigate_failed")
            trace.shot("navigate_failed")
            return False, 0, "not_login_page"
        state, _info = detect_login_state()
        if state != STATE_ACCOUNT_PAGE:
            print(f"QAHOME-LOGIN: ❌ 导航后仍未到达账号页（实得 {state}）")
            trace.shot("navigate_not_account_page")
            return False, 0, "not_login_page"
        print("QAHOME-LOGIN: ✅ 已确认进入账号页")

    # 简化版登录页（预填手机号）：直入按钮存在则直接点；仍以状态迁移为准
    simplified = _resolve_control(_CTL_QUICK_LOGIN)
    if simplified:
        print(f"QAHOME-LOGIN: 检测到简化版登录页（预填手机号），"
              f"直接点击验证码登录 @ {simplified['point']}")
        if ops.tap(*simplified["point"]):
            click_ts = time.time()
            try:
                if not bool(ops.pidof(app.package_name)):
                    print("QAHOME-LOGIN: ❌ App 进程在点击获取验证码后崩溃")
                    return False, 0, "app_crashed"
            except Exception as e:  # noqa: BLE001 —— 崩溃检查失败不改判定
                soft_fail("app", "QAHOME_CRASH_CHECK_FAILED", e)
            time.sleep(2)
            arrived, _vinfo = _wait_for_state(STATE_CODE_PAGE, timeout=_CODE_PAGE_TIMEOUT,
                                              trace=trace)
            if arrived:
                print(f"QAHOME-LOGIN: ✅ 已进入验证码输入页，验证码请求已受理 "
                      f"({time.strftime('%H:%M:%S')})")
                trace.event("code_page_arrived", via="quick_login")
                trace.shot("code_page_arrived")
                return True, click_ts, ""
            print("QAHOME-LOGIN: ⚠️ 简化版点击后未进入验证码页，回退标准登录流程")
        else:
            print("QAHOME-LOGIN: ⚠️ tap 验证码登录失败，回退标准登录流程")

    return _request_code(phone, ops, trace)


# ═══════════════════════════════════════════════════════════════════
# 动作级编排
# ═══════════════════════════════════════════════════════════════════

class _Trace:
    """一次登录尝试的证据收集器：截图 / 事件 / 视图树快照三件套。

    仅承载"把过程留痕"的意图，落盘细节全部在 `evidence` 模块；失败不阻断登录。

    "决定性证据"（`decisive`）约定：**最后一次拍摄 = 终态现场**。
    为何必须有这个区分：下游（`env_prepare`）用 `evidence[0]` 作为"登录结果截图"交给
    读图确认（`[NEEDS_VISUAL_CHECK]`），若把过程图按时间顺序整体上交，`evidence[0]`
    会是**登录前**的进场图 → 读图人看到未登录首页 → 把"已登录"误判为失败（实测踩过）。
    """

    __slots__ = ("attempt", "phone", "paths", "decisive")

    def __init__(self, attempt: int, phone: str):
        self.attempt = attempt
        self.phone = phone
        self.paths: List[str] = []
        self.decisive: Optional[str] = None

    def shot(self, tag: str) -> Optional[str]:
        """拍一张现场图；**每次拍摄都更新决定性证据**（最后一张即终态）。"""
        path = evidence.shot(f"a{self.attempt}_{tag}")
        if path:
            self.paths.append(path)
            self.decisive = path
        return path

    def ordered(self) -> Tuple[str, ...]:
        """证据序列：**决定性（终态）图排第一**，其余按新→旧排列（便于回溯失败过程）。"""
        if not self.decisive:
            return tuple(reversed(self.paths))
        rest = [p for p in reversed(self.paths) if p != self.decisive]
        return tuple([self.decisive] + rest)

    def event(self, kind: str, **fields) -> None:
        """记一条登录阶段事件（`kind` 即写入的 stage 字段）。

        统一注入 attempt/stage/account；整体包 try —— 证据失败只降级为日志。
        形参叫 `kind`（非 `stage`）：避免调用方传 `stage=` 触发 Python 参数重复错误。
        """
        try:
            payload = dict(fields)
            payload["attempt"] = self.attempt
            payload["stage"] = kind
            payload["account"] = self.phone
            evidence.event("login.stage", **payload)
        except Exception as e:  # noqa: BLE001 —— 旁路证据绝不阻断登录
            print(f"LOGIN-EVIDENCE: ⚠️ 阶段事件记录失败（忽略）{kind}: {e}")

    def tree(self, tag: str, nodes, extra: Optional[dict] = None) -> Optional[str]:
        return evidence.tree(f"a{self.attempt}_{tag}", nodes or [], extra)


def qahome_login(phone, mock_enabled=True,
                 max_attempts=_ACTION_MAX_ATTEMPTS) -> Tuple[bool, str, List[str]]:
    """QAHome 验证码登录完整流程（发码 → 取码 → 回填提交）；不含前置条件恢复（属 L2/编排层）。

    Returns `(ok, reason, evidence)`；`evidence[0]` 是决定性截图（成功=首页，失败=现场）。
    """
    for attempt in range(1, max_attempts + 1):
        trace = _Trace(attempt, phone)
        if attempt > 1:
            print(f"QAHOME-LOGIN: 🔄 第 {attempt} 次尝试...")

        ok, click_ts, reason = qahome_login_trigger(phone, mock_enabled, trace)
        if not ok:
            if reason == "page_state_invalid":
                # 起点无法在动作层归一（例如登录页被系统引导占住）→ 立刻交编排层完整恢复
                print("QAHOME-LOGIN: ⏭️ 起点不可归一，跳过动作层重试，交编排层完整恢复")
                return False, reason, list(trace.ordered())
            continue

        ok, code, reason = qahome_login_wait_code(phone, click_ts, trace=trace)
        if not ok:
            return False, reason, list(trace.ordered())

        ok, reason = qahome_login_submit_code(phone, code, trace)
        if ok:
            return True, "", list(trace.ordered())
        if reason == "page_state_invalid":
            return False, reason, list(trace.ordered())

    # 重试耗尽：返回最后一次尝试的现场证据（决定性截图见 evidence[0]）
    return False, reason or "qahome_login_failed", list(trace.ordered())


# ═══════════════════════════════════════════════════════════════════
# L3 认证动作包装（新架构入口）
# ═══════════════════════════════════════════════════════════════════

class QahomeAuthAction(AuthAction):
    """QAHome 验证码登录动作：手机号 → 勾选协议 → 获取验证码 → 查短信 → 输入 → 提交。

    前置条件恢复（AppMock / 环境切换 / 泳道）与跨环境重试属 L2/编排层。证据经
    `AuthOutcome.evidence` 回传，供失败时 AI 读图。
    """

    method = "qahome"

    def perform(self, plan, ctx) -> AuthOutcome:
        if not plan.account:
            return AuthOutcome(ok=False, detail="QAHome 登录缺少 account",
                               reason="missing_credential")

        ok, reason, paths = qahome_login(plan.account, mock_enabled=True)
        evidence_paths = tuple(paths)
        if ok:
            return AuthOutcome(ok=True, detail="QAHome 验证码登录成功",
                               evidence=evidence_paths)
        return AuthOutcome(ok=False, detail=f"QAHome 验证码登录失败（{reason}）",
                           reason=reason or "qahome_login_failed",
                           evidence=evidence_paths)


__all__ = [name for name in dir() if name.startswith(("qahome_", "_LOGIN", "_SMS"))] + [
    "QahomeAuthAction",
    "detect_login_state", "STATE_CODE_PAGE", "STATE_ACCOUNT_PAGE", "STATE_NOT_LOGIN_AREA",
]
