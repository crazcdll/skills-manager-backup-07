"""QAHome 验证码登录流程（alpha/swimline 共用）：登录页定位、触发验证码、等待与回填、完整登录。"""
import time
from context import get_platform_ops, get_app_descriptor
from mock.appmock_device import check_appmock_sdk_enabled
from core.errors import soft_fail
from screen_state.inspect_tree import inspect_tree_find_center, inspect_tree_find_by_id
from environment.setup.app_lifecycle import _current_focus_window, wait_app_foreground
from environment.setup.login_sms import _LOGIN_CODE_KEYWORDS, _SMS_CODE_RE, _parse_sms_time, qahome_query_sms
from environment.setup.login_state import check_login_state, login_go_home


_LOGIN_WINDOW_MARKERS = ("login",)
_LOGIN_ELEMENT_IDS = {
    "phone_input": "passport_mobile_phone",       # 手机号输入框
    "checkbox": "dynamic_checkbox",               # 同意协议复选框
    "send_code_btn": "passport_mobile_next",      # 获取验证码按钮
    "country_code": "passport_country_code",      # 国家码
    "agreement_text": "passport_index_tip_term_agree",  # 协议文案
    "password_login_link": "user_password_login", # 密码登录入口
}

# ── 登录页交互稳定性参数 ────────────────────────────────────────────
# 旧实现三连点固定间隔 0.5s、点完"获取验证码"即无条件判成功，
# 导致偶发"协议未勾选 → 按钮禁用点击无效 → 却进入验证码死轮询"。
# 现改为"动作 + 状态校验 + 有界重试"。
_INPUT_SETTLE = 0.8            # 手机号输入框点击聚焦后的稳定等待
_TYPE_SETTLE = 1.0             # ADB Keyboard 异步提交后的页面重排稳定等待
_AGREEMENT_MAX_ATTEMPTS = 3    # 协议勾选最多尝试次数（原坐标 + 左右微调）
_AGREEMENT_TAP_OFFSETS = ((0, 0), (-30, 0), (30, 0))  # 勾选点偏移，抵消坐标轻微漂移
_AGREEMENT_SETTLE = 0.8        # 勾选后等待状态更新的稳定等待
_GET_CODE_MAX_ATTEMPTS = 3     # "勾选协议 + 点获取验证码 + 校验跳转"最多尝试次数
_CODE_PAGE_TIMEOUT = 12.0      # 点"获取验证码"后等待跳转的最长时间（单次 dump≈5s，需覆盖≥2次采集）
_CODE_PAGE_INTERVAL = 1.2      # 页面跳转轮询间隔


def _locate_login_element(name):
    """通过 resource-id 定位登录页元素，返回 center/detail 或 None。"""
    eid = _LOGIN_ELEMENT_IDS.get(name)
    if not eid:
        return None
    from screen_state.inspect_tree import invalidate_cache
    invalidate_cache()
    return inspect_tree_find_by_id(eid)
def _locate_login_elements():
    """一次 dump 视图树，批量定位所有登录页元素。

    相比逐个调用 _locate_login_element（每次 3-6 秒），
    一次 dump 解析全部节点，从 3 次 dump 优化到 1 次。

    Returns:
        dict: {
          "phone_input": (cx,cy) | None,
          "checkbox": {"center": (cx,cy), "checked": bool|None} | None,
          "send_code_btn": (cx,cy) | None,
        }
        任一元素缺失时对应值为 None（而非整体返回 None），
        调用方自行判断必填元素是否存在。
        checkbox.checked 为三值：True/False 为真实勾选态，None 表示未暴露勾选属性。
    """
    from screen_state.inspect_tree import dump_inspect_tree, parse_inspect_tree, invalidate_cache
    invalidate_cache()
    raw = dump_inspect_tree(wait_sec=6, max_attempts=2)
    if not raw:
        return {"phone_input": None, "checkbox": None, "send_code_btn": None}
    nodes = parse_inspect_tree(raw)

    result = {"phone_input": None, "checkbox": None, "send_code_btn": None}
    for n in nodes:
        m_id = n.get("m_id", "")
        center = _center_of_node(n)
        if not center:
            continue
        if m_id == "passport_mobile_phone":
            result["phone_input"] = center
        elif m_id == "dynamic_checkbox":
            result["checkbox"] = {"center": center, "checked": n.get("checked")}
        elif m_id == "passport_mobile_next":
            result["send_code_btn"] = center
    return result
def _center_of_node(node):
    """从 UiNode 字典提取屏幕中心坐标，坐标缺失返回 None。"""
    x, y, w, h = node.get("x"), node.get("y"), node.get("w"), node.get("h")
    if None in (x, y, w, h):
        return None
    return x + w // 2, y + h // 2
def _read_checkbox_state():
    """复采视图树，读取协议复选框的当前勾选态。

    Returns:
        dict {"center": (cx,cy), "checked": bool|None} 或 None（未定位到复选框）。
        checked=None 表示视图树未暴露勾选属性（不可判定），按"已点击"处理。
    """
    from screen_state.inspect_tree import invalidate_cache
    invalidate_cache()
    node = inspect_tree_find_by_id(_LOGIN_ELEMENT_IDS["checkbox"], wait_sec=4, max_attempts=1)
    if not node:
        return None
    return {"center": node.get("center"), "checked": node.get("checked")}


def _ensure_agreement_checked(checkbox, ops):
    """确认协议已勾选；未勾选时点击，并在复选框周边微调重试。

    规避两个坑：
      - 已勾选仍盲点 → 会把勾选"取反"取消：这里先读状态，仅未勾选才点击；
      - 点击落空后在同一点死磕 → 原坐标失败后在左右微调重试。

    Returns:
        True — 已确认勾选（或状态不可判定，按已点击继续）
        False — 多次尝试后仍确认未勾选
    """
    if not checkbox:
        print("QAHOME-LOGIN: ⚠️ 未定位到复选框 (dynamic_checkbox)，跳过协议勾选")
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
        if state is None or state.get("checked") is None:
            # 复选框节点没暴露勾选属性（不可判定）→ 已点击一次即接受，
            # 避免把"读不到状态"误当成"未勾选"而反复点击、把已勾选的协议又点掉
            print("QAHOME-LOGIN: ⚠️ 无法判定协议勾选状态，按已点击继续")
            return True
        if state.get("checked") is True:
            print("QAHOME-LOGIN: ✅ 协议已确认勾选")
            return True
        if state.get("center"):
            center = state["center"]
        print(f"QAHOME-LOGIN: 协议仍未勾选（checked={state.get('checked')}），重试...")
    print("QAHOME-LOGIN: ❌ 多次尝试后协议仍未勾选")
    return False


def _wait_code_page(timeout=_CODE_PAGE_TIMEOUT, interval=_CODE_PAGE_INTERVAL):
    """等待页面跳转到"输入验证码"页（验证码发送成功的可靠信号）。

    手机号页与验证码页同处 passport LoginActivity（Fragment 切换），焦点窗口不变，
    因此只能按页面内容判定：出现验证码输入框（mID=edit_text_view）或「输入验证码」文案。
    返回 True 才算发送成功，避免"空点击"被误判为已发送。
    """
    from screen_state.inspect_tree import dump_inspect_tree, parse_inspect_tree, invalidate_cache
    deadline = time.time() + timeout
    while True:
        invalidate_cache()
        raw = dump_inspect_tree(wait_sec=1, max_attempts=1)
        if raw:
            for n in parse_inspect_tree(raw):
                if n.get("m_id") == "edit_text_view":
                    return True
                if "输入验证码" in (n.get("all_text") or ""):
                    return True
        if time.time() >= deadline:
            return False
        time.sleep(interval)


def _login_page_action(phone, ops):
    """在登录页执行完整操作：输入手机号 → 确认协议勾选 → 点获取验证码并校验跳转。

    相比旧实现（固定 0.5s 间隔、点完即判成功），本实现按"动作 + 状态校验 + 有界重试"：
      1. 手机号输入后等页面稳定再复采坐标，避免用输入前的旧坐标点击；
      2. 勾选协议后读回 checked 状态确认，未生效时在复选框周边微调重试；
      3. 点"获取验证码"后校验页面是否跳到"输入验证码"页，只有跳转成功才判成功，
         否则重试（有界）——这是拦住"空点击 → 死轮询验证码"的关键一环。

    Returns:
        (True, click_ts) — 验证码已成功发送（页面已进入验证码输入页）
        (False, 0) — 失败
    """
    # 1. 首次 dump：定位手机号输入框
    elements = _locate_login_elements()
    phone_field = elements.get("phone_input")
    if not phone_field:
        print("QAHOME-LOGIN: ❌ 未找到手机号输入框 (passport_mobile_phone)")
        return False, 0

    # 2. 输入手机号（ADB Keyboard 异步提交，后置等待需覆盖输入+页面重排）
    print(f"QAHOME-LOGIN: 输入账号 @ {phone_field}")
    if not ops.tap(*phone_field):
        print("QAHOME-LOGIN: ❌ tap 手机号输入框失败")
        return False, 0
    time.sleep(_INPUT_SETTLE)
    ops.input_text(phone)
    time.sleep(_TYPE_SETTLE)

    # 3. 勾选协议 + 点获取验证码 + 校验跳转（有界重试，每轮复采坐标）
    for attempt in range(1, _GET_CODE_MAX_ATTEMPTS + 1):
        elements = _locate_login_elements()
        send_btn = elements.get("send_code_btn")
        if not send_btn:
            print(f"QAHOME-LOGIN: ❌ 第 {attempt} 轮未找到获取验证码按钮 (passport_mobile_next)")
            return False, 0

        # 3a. 协议：读状态 → 仅在未勾选时点击 → 复核
        if not _ensure_agreement_checked(elements.get("checkbox"), ops):
            print(f"QAHOME-LOGIN: ⚠️ 第 {attempt} 轮协议仍未勾选，重试...")
            time.sleep(0.5)
            continue

        # 3b. 点击获取验证码
        print(f"QAHOME-LOGIN: 点击获取验证码 @ {send_btn}（第 {attempt}/{_GET_CODE_MAX_ATTEMPTS} 次）")
        ops.tap(*send_btn)
        click_ts = time.time()

        # 3c. 校验是否跳到"输入验证码"页
        if _wait_code_page():
            print(f"QAHOME-LOGIN: ✅ 已进入验证码输入页，验证码请求已发送 ({time.strftime('%H:%M:%S')})")
            return True, click_ts
        print(f"QAHOME-LOGIN: ⚠️ 第 {attempt} 轮点击后 {_CODE_PAGE_TIMEOUT}s 内未进入验证码输入页，重试...")
        time.sleep(0.5)

    print("QAHOME-LOGIN: ❌ 多轮尝试后仍未进入验证码输入页，判定验证码发送失败")
    return False, 0


def qahome_login_trigger(phone, mock_enabled=False):
    """检测 App 状态 → 导航到登录页 → 发送验证码。

    基于视图树动态定位，兼容两种登录页变体：
      - 简化版（复用设备，预填手机号）：直接点击"验证码登录"按钮
      - 标准版（全新安装）：输入手机号 → 勾选协议 → 获取验证码
    首次登录页不在前台时，自动从首页导航到登录页（通过"我的"或"去登录"入口）。

    Returns:
        (True, click_ts) — 验证码已发送
        (False, 0) — 失败
    """
    ops = get_platform_ops()
    app = get_app_descriptor()

    focus = _current_focus_window()
    print(f"[LOGIN-DIAG] 初始焦点: {focus!r}, PID: {ops.pidof(app.package_name)!r}")
    if not any(marker in focus for marker in _LOGIN_WINDOW_MARKERS):
        if wait_app_foreground(timeout=10):
            print("QAHOME-LOGIN: ✅ App 在前台，开始登录流程")
        else:
            print("QAHOME-LOGIN: ⚠️ App 未在前台，仍继续尝试")

    if mock_enabled:
        print("QAHOME-LOGIN: 保持 AppMock 开启状态...")
        if not check_appmock_sdk_enabled():
            print("QAHOME-LOGIN: ❌ 设备端 AppMock SDK 未启用")
            return False, 0
        print("QAHOME-LOGIN: ✅ AppMock SDK 已确认启用")

    # 1. 检测是否已在登录页（焦点判断）
    focus = _current_focus_window()
    if any(marker in focus for marker in _LOGIN_WINDOW_MARKERS):
        print("QAHOME-LOGIN: ✅ 已在登录页")
        simplified = inspect_tree_find_center("验证码登录", detail=True)
        print(f"[LOGIN-DIAG] 定位 '验证码登录': {simplified!r}")
        if simplified:
            print(f"QAHOME-LOGIN: 检测到简化版登录页（预填手机号），直接点击验证码登录 @ {simplified['center']}")
            if not ops.tap(*simplified["center"]):
                print("QAHOME-LOGIN: ❌ tap 验证码登录失败，回退标准登录流程")
            else:
                click_ts = time.time()
                time.sleep(2)
                _post_focus = _current_focus_window()
                _post_pid = ops.pidof(app.package_name)
                print(f"[LOGIN-DIAG] 点击后焦点: {_post_focus!r}, PID: {_post_pid!r}")
                try:
                    if not bool(_post_pid):
                        print("QAHOME-LOGIN: ❌ App 进程在点击获取验证码后崩溃")
                        return False, 0
                except Exception as e:
                    soft_fail("app", "QAHOME_CRASH_CHECK_FAILED", e)
                # 校验页面是否真的跳到验证码输入页（与标准流程同一道"防死轮询"闸门）
                if _wait_code_page():
                    print(f"QAHOME-LOGIN: ✅ 已进入验证码输入页，验证码请求已发送 ({time.strftime('%H:%M:%S')})")
                    return True, click_ts
                print("QAHOME-LOGIN: ⚠️ 简化版点击后未进入验证码输入页，回退标准登录流程")
    else:
        print(f"[LOGIN-DIAG] 不在登录页, focus={focus!r}, is_foreground={app.is_foreground(focus)}")
        if not app.is_foreground(focus):
            print("QAHOME-LOGIN: App 不在首页，拉回首页...")
            if not ops.launch_app(app.main_activity):
                print("QAHOME-LOGIN: ❌ launch_app 失败")
                return False, 0
            time.sleep(2)
            print(f"[LOGIN-DIAG] launch_app 后焦点: {_current_focus_window()!r}")

        go_login = inspect_tree_find_center("去登录", detail=True) or inspect_tree_find_center("我的", detail=True)
        print(f"[LOGIN-DIAG] 定位 '去登录'/'我的': {go_login!r}")
        if not go_login:
            print("QAHOME-LOGIN: ❌ 未找到'去登录'或'我的'按钮，无法导航到登录页")
            return False, 0
        print(f"QAHOME-LOGIN: 点击'去登录' @ {go_login['center']}")
        if not ops.tap(*go_login["center"]):
            print("QAHOME-LOGIN: ❌ tap 失败")
            return False, 0
        time.sleep(1)
        print(f"[LOGIN-DIAG] 点击后焦点: {_current_focus_window()!r}, PID: {ops.pidof(app.package_name)!r}")
        time.sleep(3)
        deadline = time.time() + 8
        while time.time() < deadline:
            focus = _current_focus_window()
            if focus and any(m in focus for m in _LOGIN_WINDOW_MARKERS):
                break
            time.sleep(1)
        if not focus or not any(m in focus for m in _LOGIN_WINDOW_MARKERS):
            print("QAHOME-LOGIN: ❌ 点击'去登录'后未进入登录页")
            return False, 0
        print("QAHOME-LOGIN: ✅ 已确认进入登录页")
        print(f"[LOGIN-DIAG] 进入登录页焦点: {focus!r}")

    # 3. 执行登录页操作：resource-id 定位，不依赖文案
    return _login_page_action(phone, ops)
def qahome_login_wait_code(phone, click_ts, max_attempts=10, interval=2.0, freshness_seconds=120):
    """从 QAHome 轮询获取验证码。

    按时间过滤：只取最近 freshness_seconds 秒内发送的验证码，避免使用过期验证码。
    """
    now = time.time()
    # 新鲜度锚点用"点击获取验证码"的时刻（而非轮询开始时刻），
    # 避免把点击前发送、轮询时才查到的旧验证码误判为本次验证码。
    anchor = click_ts or now
    print(f"QAHOME-LOGIN: 轮询获取验证码（最多 {max_attempts} 次，只取 {freshness_seconds}s 内发送的）...")
    for i in range(max_attempts):
        print(f"QAHOME-LOGIN: 查询验证码 {i+1}/{max_attempts}...")
        results = qahome_query_sms(phone, timeout=10)
        if results:
            for sms in results:
                msg = sms.get("message", "")
                sms_time_str = sms.get("addTimeFormat", "")
                if any(kw in msg for kw in _LOGIN_CODE_KEYWORDS):
                    # 时间过滤：只取最近 freshness_seconds 秒内发送的验证码
                    sms_ts = _parse_sms_time(sms_time_str)
                    if sms_ts > 0 and (anchor - sms_ts) > freshness_seconds:
                        code_match = _SMS_CODE_RE.search(msg)
                        matched_code = code_match.group(1) if code_match else "?"
                        print(f"QAHOME-LOGIN: ⏭️ 跳过过期验证码: {matched_code} ({sms_time_str})")
                        continue
                    m = _SMS_CODE_RE.search(msg)
                    if m:
                        sms_code = m.group(1)
                        print(f"QAHOME-LOGIN: ✅ 验证码: {sms_code} ({sms_time_str})")
                        return True, sms_code
        print(f"QAHOME-LOGIN: 未匹配到验证码，{interval}s 后重试...")
        time.sleep(interval)
    print(f"QAHOME-LOGIN: ❌ {max_attempts} 次查询后仍未获取到验证码")
    return False, ""
def qahome_login_input_code(sms_code):
    """输入验证码 → 等待登录自然完成 → 确认登录态。

    基于视图树动态定位验证码输入框（mID=edit_text_view），
    不依赖固定坐标。
    ⚠️ 禁止用 LAUNCHER intent 拉回——会绕过登录流程，Activity 切换但登录态未写入。
    """
    ops = get_platform_ops()
    app = get_app_descriptor()

    # [DIAG] 输入验证码前检查页面状态
    _focus = _current_focus_window()
    _pid = ops.pidof(app.package_name)
    print(f"[LOGIN-DIAG] input_code 入口: focus={_focus!r}, PID={_pid!r}")

    # 作废缓存：点击"验证码登录"后页面可能在同一个 Activity 内切换 Fragment
    from screen_state.inspect_tree import invalidate_cache
    invalidate_cache()

    # 优先通过 resource-id 定位 VerificationEditText
    code_input = inspect_tree_find_by_id("edit_text_view", wait_sec=3, max_attempts=1)
    if not code_input:
        # fallback：通过文案定位
        print("QAHOME-LOGIN: ⚠️ 未通过 mID 找到验证码输入框，尝试文案定位...")
        invalidate_cache()
        time.sleep(1)
        code_input = inspect_tree_find_center("输入验证码", detail=True, wait_sec=3, max_attempts=1)
    if not code_input:
        # 兜底：打印当前视图树中所有带文案的节点，帮助定位
        print("QAHOME-LOGIN: ❌ 未找到验证码输入框，dump 当前视图树节点...")
        try:
            from screen_state.inspect_tree import dump_inspect_tree, parse_inspect_tree
            invalidate_cache()
            time.sleep(1)
            raw = dump_inspect_tree(wait_sec=3, max_attempts=1)
            if raw:
                nodes = parse_inspect_tree(raw)
                print(f"[LOGIN-DIAG] 当前页面共 {len(nodes)} 个节点，列出全部带文案/ID 的节点：")
                for n in nodes:
                    text = n.get("text", "") or n.get("all_text", "")
                    m_id = n.get("m_id", "")
                    cls = n.get("class_name", "")
                    clickable = n.get("clickable", False)
                    x, y = n.get("x"), n.get("y")
                    if text or m_id:
                        print(f"  [node] text={text!r:30s} m_id={m_id!r:40s} cls={cls!r:30s} "
                              f"clickable={clickable} pos=({x},{y})")
                print(f"[LOGIN-DIAG] 全部节点坐标分布：")
                for n in nodes[:50]:
                    x, y, w, h = n.get("x"), n.get("y"), n.get("w"), n.get("h")
                    if x is not None and y is not None:
                        print(f"  [coord] cls={n.get('class_name','')!r:30s} m_id={n.get('m_id','')!r:40s} "
                              f"rect=({x},{y},{w},{h}) clickable={n.get('clickable')}")
        except Exception as e:
            print(f"  [dump failed] {e}")
        return False
    print(f"[LOGIN-DIAG] 定位 edit_text_view: {code_input!r}")
    print(f"QAHOME-LOGIN: 输入验证码 {sms_code} @ {code_input['center']}")
    if not ops.tap(*code_input["center"]):
        print("QAHOME-LOGIN: ❌ tap 验证码输入框失败")
        return False
    time.sleep(0.5)
    if not ops.input_text(sms_code):
        print("QAHOME-LOGIN: ⚠️ input_text 验证码命令执行失败")
    time.sleep(3)

    print(f"[LOGIN-DIAG] 输入验证码后焦点: {_current_focus_window()!r}, PID: {ops.pidof(app.package_name)!r}")

    print("QAHOME-LOGIN: 等待登录自然完成（最多 30s）...")
    poll_timeout = 30
    poll_interval = 2
    deadline = time.time() + poll_timeout
    attempt = 0
    focus_reached_main = False
    while time.time() < deadline:
        attempt += 1
        focus = _current_focus_window()
        if app.is_foreground(focus):
            print(f"QAHOME-LOGIN: 焦点已自然回到前台（第 {attempt} 轮）")
            focus_reached_main = True
            break
        if focus and not any(m in focus for m in _LOGIN_WINDOW_MARKERS):
            print(f"QAHOME-LOGIN: 第 {attempt} 轮焦点在中间页，继续等待...")
        else:
            print(f"QAHOME-LOGIN: 第 {attempt} 轮焦点仍在登录页，{poll_interval}s 后重试...")
        time.sleep(poll_interval)

    if not focus_reached_main:
        print(f"QAHOME-LOGIN: ❌ {poll_timeout}s 内焦点未自然回到 MainActivity，登录失败")
        print(f"[LOGIN-DIAG] 超时后最终状态: focus={_current_focus_window()!r}, PID={ops.pidof(app.package_name)!r}")
        return False

    time.sleep(2)
    is_logged_in, detail = check_login_state()
    if is_logged_in:
        print(f"QAHOME-LOGIN: ✅ {detail}")
        if not login_go_home():
            print("QAHOME-LOGIN: ❌ 跳回主页后前台未稳定，判定失败")
            return False
        return True
    print(f"QAHOME-LOGIN: ❌ {detail}")
    return False
def qahome_login(phone, mock_enabled=True, max_attempts=2):
    """QAHome 验证码登录完整流程（trigger → wait_code → input_code）。

    纯登录函数，不负责前置条件恢复（AppMock 启用、环境切换等）。
    重试由调用方（QahomeLoginStrategy）在完整上下文中执行。
    max_attempts 用于 trigger 和 input_code 阶段的轻量重试（点击/输入操作可能不稳定），
    wait_code 失败不重试（由策略层在完整上下文中恢复前置条件后重试）。
    """
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            print(f"QAHOME-LOGIN: 🔄 第 {attempt} 次尝试...")

        ok, click_ts = qahome_login_trigger(phone, mock_enabled)
        if not ok:
            if attempt < max_attempts:
                continue
            return False
        if click_ts == -1:
            print("QAHOME-LOGIN: ✅ 已登录，跳过")
            return True

        ok2, code = qahome_login_wait_code(phone, click_ts)
        if not ok2:
            print("QAHOME-LOGIN: ❌ 验证码轮询彻底失败，判定登录失败并结束")
            return False

        if qahome_login_input_code(code):
            return True
        elif attempt < max_attempts:
            continue
        else:
            return False

    return False
