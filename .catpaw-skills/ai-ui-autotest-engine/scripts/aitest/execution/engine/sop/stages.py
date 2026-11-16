"""SOP 阶段编排：Batch 头/尾阶段、Case 循环体模板、占位符替换与阶段装配。"""
import copy
from aitest.execution.engine.sop.constants import CLEANUP_CMDS, POST_CLEAN_CMD
from aitest.execution.engine.sop.on_fail import ON_FAIL_ABORT, ON_FAIL_BEST_EFFORT, ON_FAIL_LOG_AND_CONTINUE, ON_FAIL_PAUSE, ON_FAIL_SKIP_TO_NEXT_CASE


# 结构化 on_fail 声明模板
_ON_FAIL_ABORT = {"policy": ON_FAIL_ABORT, "generate_report": True, "cleanup": True}
_ON_FAIL_PAUSE = {"policy": ON_FAIL_PAUSE}
_ON_FAIL_LOG_AND_CONTINUE = {"policy": ON_FAIL_LOG_AND_CONTINUE}
_ON_FAIL_BEST_EFFORT = {"policy": ON_FAIL_BEST_EFFORT}
_ON_FAIL_SKIP_TO_NEXT_CASE = {"policy": ON_FAIL_SKIP_TO_NEXT_CASE}

# ── Batch 头阶段（B0-B2）：设备 + 环境准备，只执行一次 ──
# 单一有序声明源：阶段的新增/调整都在本列表内完成，禁止在别处用 `+=` 拼接，
# 以免文件拆分或搬迁时整段阶段被静默丢失（SOP 装配仅消费本列表 + 能力位过滤）。
_BATCH_HEAD_STAGES = [
    {
        "id": "B0_mis_acquire",
        "desc": "领取 AppMock 运行域（虚拟 mis 租约）",
        "status": "pending",
        "cmd": "python3 scripts/cli.py mis acquire",
        "success_marker": '"ok": true',
        "on_fail": dict(_ON_FAIL_ABORT),
        "completion_check": {"type": "json_path_nonempty", "path": "meta.mock_runtime_domain"},
        "layer": "batch_head",
        "notes": "在任何 AppMock 操作之前，从虚拟 mis 池领取本 run 独占的运行域"
                 "（私有优先 → 公共兜底 → 池空直接终止）。后续规则开关 / 录制 / 环境 / "
                 "泳道全部用它；场景 mockId 属于规则库（全局唯一，执行期只读）。",
    },
    {
        "id": "B0_mock_preflight",
        "desc": "场景 Mock 预检（规则库→运行域物化 + 冲突检测 + 清场）",
        "status": "pending",
        "cmd": "python3 scripts/cli.py mock-preflight",
        "success_marker": "mock_preflight",
        "on_fail": dict(_ON_FAIL_ABORT),
        "condition": "meta.mock_union non-empty",
        "layer": "batch_head",
        "notes": "把每条 mockId 的母本**克隆**到运行域：字段搬运由服务端完成并读回自证"
                 "（verified=true 才放行，副本 desc=[ai-run] {mockId} {rule} 作归属标记），"
                 "映射落 mock-map.json；同 case 内同接口两规则 → fail-fast；最后 stop-all 清成确定初始态。"
                 "后续由 C1_mock_apply 逐 case 幂等刷新副本内容再收敛开关。",
    },
    {
        "id": "B1_device",
        "desc": "设备获取 + 初始化",
        "status": "pending",
        "cmds": [
            {"cmd": "python3 scripts/cli.py device create", "background": True},
            {"cmd": "python3 scripts/cli.py device setup", "background": True},
            "python3 scripts/cli.py ack --key device_info_shown",
        ],
        "success_marker": "\"ok\": true",
        "on_fail": dict(_ON_FAIL_ABORT),
        "notes": "create 完成后先向用户展示设备信息（sandboxId、adb 地址、围观链接 scrcpyUrl），"
                 "再调用 ack 写入证据，否则 flow-advance 会被拦截。",
        "completion_check": {"type": "json_path_nonempty", "path": "meta.device_serial"},
        "requires_ack": [
            {"key": "device_info_shown",
             "hint": "请先向用户展示 sandboxId/adb地址/围观链接，再调用 ack --key device_info_shown"},
        ],
        "layer": "batch_head",
    },
    {
        "id": "B2_login",
        "desc": "环境配置 + 登录",
        "status": "pending",
        "cmd": {"cmd": "python3 scripts/cli.py env-prepare", "background": True},
        "success_markers": ["login_input_code", "QAHOME-LOGIN", "[NEEDS_VISUAL_CHECK]"],
        "on_fail": dict(_ON_FAIL_ABORT),
        "notes": "凭证登录（A/C）输出 [NEEDS_VISUAL_CHECK] 需读图确认；"
                 "验证码登录（B/D）由 env-prepare 内部自动验证。"
                 "确认登录成功后调用 ack 写入证据，否则 flow-advance 会被拦截。",
        "requires_ack": [
            {"key": "login_completed",
             "hint": "请先确认 env-prepare 已成功登录（凭证登录需读图确认 [NEEDS_VISUAL_CHECK] 截图，"
                     "验证码登录确认 QAHOME-LOGIN 成功标记）。"
                     "MRN 锁包结果已由 env-prepare 自动通过 inspect-tree 验证——如果锁包失败，"
                     "env-prepare 会直接报错退出，不会到达此 ack 环节。"
                     "确认后直接 ack（凭证登录无需跳回首页，Case 首步 open-url 会直接覆盖当前页面）"},
        ],
        "layer": "batch_head",
    },
]
# OnboardingProfile.needs_device_acquire()=False（当前仅 local）时 B1_device 的覆盖版本：
# cmds 与 sandbox 一致，仅展示文案不同（不走云端 acquire 的设备类型恒无 sandboxId/
# scrcpyUrl）。resources/device_pool/commands.py::cmd_create 内部按 device_type 分流
# 具体探测/申请方式，SOP 层只关心「要不要展示云端设备信息」这一能力位，不感知底层分流细节——
# 新增设备类型时只要在 execution/engine/profile/onboarding.py 正确声明 needs_device_acquire()，
# 本文件不需要任何改动即可展示正确文案。
_B2_DEVICE_HINT_LOCAL = (
    "请先向用户展示本地设备序列号（meta.device_serial），再调用 ack --key device_info_shown。"
    "本地真机无 sandboxId/围观链接，无需展示。"
)
_B2_DEVICE_NOTES_LOCAL = (
    "本地真机场景：device create 会自动探测已连接设备（不向 yooz 申请实例）并写入 "
    "meta.device_serial。向用户展示该字段后调用 ack 写入证据，否则 flow-advance 会被拦截；"
    "本地真机恒无 sandboxId/scrcpyUrl，不要尝试展示。\n"
    "⚠️ 探测不到设备或熄屏/锁屏时，输出若带 guidance 字段（可现场修复的临时环境状态），"
    "应按 guidance.steps 引导用户处理并重试 guidance.retry_cmd，而非直接判失败。"
    "仅当用户放弃或报错不带 guidance 字段时才按 on_fail=abort 终止。"
)
_CASE_LOOP_TEMPLATE = [
    {
        "id": "C0_case_init_{ci}",
        "desc": "切换到 Case {ci}: {case_name}",
        "status": "pending",
        "cmd": "python3 scripts/cli.py case-init --case-index {ci}",
        "success_marker": "CASE-INIT OK",
        "on_fail": dict(_ON_FAIL_SKIP_TO_NEXT_CASE),
        "layer": "case_loop",
        "case_index": "{ci}",
    },
    {
        "id": "C1_mock_apply_{ci}",
        "desc": "收敛场景 Mock 到本 Case（差量开关 + 刷新运行域副本 body）",
        "status": "pending",
        "cmd": "python3 scripts/cli.py mock-apply --case-index {ci}",
        "success_marker": "mock_apply",
        "on_fail": dict(_ON_FAIL_ABORT),
        "layer": "case_loop",
        "case_index": "{ci}",
        "notes": "任一时刻 AppMock 开启的场景规则 = 本 Case 声明集合；同接口跳 Case 由差量开关隔离。",
    },
    {
        "id": "C2_record_start_{ci}",
        "desc": "启动录制（在目标页打开之前，仅捕获业务事件）",
        "status": "pending",
        "cmd": "python3 scripts/cli.py mock record-start",
        "success_marker": "APPMOCK RECORD START OK",
        "on_fail": dict(_ON_FAIL_LOG_AND_CONTINUE),
        "layer": "case_loop",
        "case_index": "{ci}",
    },
    {
        "id": "C4_walkthrough_{ci}",
        "desc": "多步 UI 走查",
        "status": "pending",
        "steps_ref": "steps",
        "on_fail": dict(_ON_FAIL_LOG_AND_CONTINUE),
        "on_warn": dict(_ON_FAIL_LOG_AND_CONTINUE),
        "layer": "case_loop",
        "case_index": "{ci}",
        "completion_check": {
            "type": "steps_all_done",
            "hint": "还有走查步骤未完成，请继续用 flow-next 推进，不要用 flow-advance 跳过"
        },
    },
    {
        "id": "C4_post_scan_{ci}",
        "desc": "Case 收尾补扫（向下补看 ≤N 屏 + 失败项二次复核）",
        "status": "pending",
        "cmd": "python3 scripts/cli.py case-post-scan",
        "success_markers": ["[POST-SCAN]", "[POST-SCAN SKIP]"],
        # 条件为计算型：仅当本 case 仍有 failed/pending 步骤或未落定断言时才执行。
        # 全通过的 case 直接跳过 —— 正常用例不付任何滚动/截图成本。
        "condition": "open_checks non-empty",
        "on_fail": dict(_ON_FAIL_LOG_AND_CONTINUE),
        "layer": "case_loop",
        "case_index": "{ci}",
        "notes": "从最后一步位置向下连拍最多 POST_SCAN_SCROLLS（默认 5）屏，**只截图不 dump**"
                 "（dump 一屏 8~25s，截图仅 ~1s）；相邻两帧一致即视为到底提前结束"
                 "（无限滚动由屏数上限兜住）。随后 AI 一次性读完所有帧，对失败的/"
                 "待判定的断言做二次改判：命中用 override-step-result 改写结论，"
                 "未命中保持原结论。判定完成后 flow-advance 进入 C5_report。",
    },
    {
        "id": "C5_report_{ci}",
        "desc": "生成 Case 报告并增量上报（Append 单个 Case）",
        "status": "pending",
        "cmd": "python3 scripts/cli.py gen-report",
        "success_markers": ["Case 报告已生成"],
        "completion_check": {
            "type": "file_exists",
            "base": "current_case_output_dir",
            "glob": "report.json",
        },
        "notes": "追加失败只告警（收尾会按台账补传），不视为阶段失败，也不要重跑本命令。",
        "on_fail": dict(_ON_FAIL_SKIP_TO_NEXT_CASE),
        "layer": "case_loop",
        "case_index": "{ci}",
    },
]
# T2_cleanup.cmds：收尾清理序列（唯一声明源在 sop/constants.py，与异常终止路径
# flow/lifecycle/fail.py 共用，避免两处漂移漏步骤）。
# device release 只归还本 run 的租约（不销毁实例）；非池化设备为安全 no-op。
_T2_CLEANUP_CMDS = [*CLEANUP_CMDS, POST_CLEAN_CMD]
_BATCH_TAIL_STAGES = [
    {
        "id": "T0_mock_restore",
        "desc": "运行域 Mock 清场（stop-all，随后随号池归还）",
        "status": "pending",
        "cmd": "python3 scripts/cli.py mock-restore",
        "success_markers": ["MOCK-RESTORE DONE", "MOCK-RESTORE SKIP", "MOCK-RESTORE PARTIAL"],
        "on_fail": dict(_ON_FAIL_BEST_EFFORT),
        "condition": "meta.mock_union non-empty",
        "layer": "batch_tail",
    },
    {
        "id": "T2_cleanup",
        "desc": "收尾清理",
        "status": "pending",
        "cmds": list(_T2_CLEANUP_CMDS),
        "notes": "flow-finalize 必须在 post-clean 之前执行：它标记 T2 completed、执行报告"
                 " **Close**（补传未成功的 Case + 写回最终 run_status + archive_run）。"
                 "各 Case 在 C5_report 已逐个 append，这里不再重发全量 cases，因此报告体积与"
                 "批次大小无关。archive_run 已将 本 workspace归档到"
                 " $STATE/reports/<batch>/<run>/run/，所以随后 post-clean 清空本 workspace 不会丢失执行产物。",
        "on_fail": dict(_ON_FAIL_BEST_EFFORT),
        "terminal": True,
        "layer": "batch_tail",
    },
]
def _replace_placeholders(obj, replacements):
    """递归替换数据结构中所有字符串的占位符。"""
    if isinstance(obj, str):
        for key, val in replacements.items():
            obj = obj.replace(key, val)
        return obj
    if isinstance(obj, dict):
        return {k: _replace_placeholders(v, replacements) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_placeholders(item, replacements) for item in obj]
    return obj


def iter_stage_commands(stage):
    """产出阶段的命令及其执行契约：`[(cmd_text, background), ...]`。

    命令声明支持两种形态：
      · 字符串                             —— 前台执行（默认）
      · `{"cmd": str, "background": True}` —— 长任务，必须后台执行并轮询日志

    解析统一收敛在此处，消费点（flow-next / flow-advance 渲染）不再各自遍历
    `cmd` / `cmds` / `cmd_template`，避免声明与解析漂移。
    """
    def _norm(item):
        if isinstance(item, dict):
            return item["cmd"], bool(item.get("background"))
        return item, False

    if stage.get("cmd"):
        yield _norm(stage["cmd"])
    for item in stage.get("cmds") or []:
        yield _norm(item)
    if stage.get("cmd_template"):
        yield _norm(stage["cmd_template"])


def make_fresh_sop_stages(cases_manifest=None, device_type="sandbox"):
    """生成 SOP 阶段列表：B0-B2 + 每个 case 循环体 + T0-T2。"""
    # 复用 context.create_onboarding_profile 同一份 execution.engine.profile.onboarding
    # 注册表（_DEVICE_TYPE_PROFILE_REGISTRY），不在本文件重复维护一份
    # device_type → 实现类的字典——新增设备类型时只需要在 onboarding.py 注册一次。
    from aitest.execution.engine.profile.onboarding import create_onboarding_profile
    onboarding_profile = create_onboarding_profile(device_type)

    stages = copy.deepcopy(_BATCH_HEAD_STAGES)

    if not onboarding_profile.needs_device_acquire():
        for stage in stages:
            if stage["id"] == "B1_device":
                stage["requires_ack"][0]["hint"] = _B2_DEVICE_HINT_LOCAL
                stage["notes"] = _B2_DEVICE_NOTES_LOCAL

    if not cases_manifest:
        # 默认：生成 index=0 的一组 case 循环体（cases 数组长度为 1 的场景）
        cases_manifest = [{"index": 0, "case_id": "", "case_name": "默认",
                           "dir": "", "run_id": "", "landing_scheme": ""}]

    for case in cases_manifest:
        ci = case["index"]
        replacements = {
            "{ci}": str(ci),
            "{case_name}": case.get("case_name", f"Case {ci}"),
            "{run_id}": case.get("run_id", ""),
            "{output_dir}": case.get("output_dir", ""),
            "{landing_scheme}": case.get("landing_scheme", ""),
        }
        for tmpl in copy.deepcopy(_CASE_LOOP_TEMPLATE):
            stage = _replace_placeholders(tmpl, replacements)
            stage["case_index"] = ci
            stages.append(stage)

    tail_stages = copy.deepcopy(_BATCH_TAIL_STAGES)
    # T2_cleanup 使用统一清理命令列表，device_type 不再影响清理逻辑
    stages.extend(tail_stages)
    return stages
