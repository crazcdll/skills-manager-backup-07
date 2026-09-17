"""SOP 阶段编排：Batch 头/尾阶段、Case 循环体模板、占位符替换与阶段装配。"""
import copy
from core.sop.on_fail import ON_FAIL_ABORT, ON_FAIL_BEST_EFFORT, ON_FAIL_LOG_AND_CONTINUE, ON_FAIL_PAUSE, ON_FAIL_SKIP_TO_NEXT_CASE


# 结构化 on_fail 声明模板
_ON_FAIL_ABORT = {"policy": ON_FAIL_ABORT, "generate_report": True, "cleanup": True}
_ON_FAIL_PAUSE = {"policy": ON_FAIL_PAUSE}
_ON_FAIL_LOG_AND_CONTINUE = {"policy": ON_FAIL_LOG_AND_CONTINUE}
_ON_FAIL_BEST_EFFORT = {"policy": ON_FAIL_BEST_EFFORT}
_ON_FAIL_SKIP_TO_NEXT_CASE = {"policy": ON_FAIL_SKIP_TO_NEXT_CASE}

# ── Batch 头阶段（B0-B3）：设备 + 环境准备，只执行一次 ──
# 单一有序声明源：阶段的新增/调整都在本列表内完成，禁止在别处用 `+=` 拼接，
# 以免文件拆分或搬迁时整段阶段被静默丢失（SOP 装配仅消费本列表 + 能力位过滤）。
_BATCH_HEAD_STAGES = [
    {
        "id": "B0_mock_snapshot",
        "desc": "预设 Mock 基线快照（仅有 mock_ids 时执行，在所有修改前捕获真实状态）",
        "status": "pending",
        "cmds": [
            "python3 scripts/cli.py mock-snapshot --mock-ids {mock_ids_str}",
        ],
        "success_marker": "mock_setup",
        "on_fail": dict(_ON_FAIL_ABORT),
        "condition": "env.mock_ids non-empty",
        "layer": "batch_head",
    },
    {
        "id": "B1_device",
        "desc": "设备获取 + 初始化",
        "status": "pending",
        "cmds": [
            "python3 scripts/cli.py device create",
            "python3 scripts/cli.py device setup",
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
        "build_cmd": "env_prepare",
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
                     "确认后直接 ack（凭证登录无需跳回首页，后续 open-url scheme 可直接覆盖当前页面）"},
        ],
        "layer": "batch_head",
    },
    {
        "id": "B3_mock_enable",
        "desc": "启用预设 Mock 规则（在 B2_login 的 reset-env 之后执行，避免被 stop-all 覆盖）",
        "status": "pending",
        "cmd_template": "python3 scripts/cli.py mock on --mock-id {mock_id}",
        "iterable": "mock_ids",
        "success_marker": "mock_on",
        "on_fail": dict(_ON_FAIL_ABORT),
        "condition": "env.mock_ids non-empty",
        "layer": "batch_head",
        "notes": "mock on 延迟到 B2_login 之后执行，因 env-prepare 内部的 reset-env 会无条件"
                 " stop-all 清理残留状态，提前 enable 会被覆盖；此处确保 C2_landing 时 Mock 已生效。",
    },
]
# OnboardingProfile.needs_device_acquire()=False（当前仅 local）时 B1_device 的覆盖版本：
# cmds 与 sandbox 一致，仅展示文案不同（不走云端 acquire 的设备类型恒无 sandboxId/
# scrcpyUrl）。device_lifecycle.cmd_create 内部按 device_type 分流具体探测/申请方式，
# SOP 层只关心「要不要展示云端设备信息」这一能力位，不感知底层分流细节——
# 新增设备类型时只要在 core/onboarding.py 正确声明 needs_device_acquire()，本文件
# 不需要任何改动即可展示正确文案。
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
        "id": "C1_record_start_{ci}",
        "desc": "启动录制（在目标页打开之前，仅捕获业务事件）",
        "status": "pending",
        "cmd": "python3 scripts/cli.py mock record-start",
        "success_marker": "APPMOCK RECORD START OK",
        "on_fail": dict(_ON_FAIL_LOG_AND_CONTINUE),
        "layer": "case_loop",
        "case_index": "{ci}",
    },
    {
        "id": "C2_landing_{ci}",
        "desc": "跳转目标页",
        "status": "pending",
        "cmd": "python3 scripts/cli.py open-url --url \"{landing_scheme}\"",
        "success_marker": "open_url",
        "on_fail": dict(_ON_FAIL_SKIP_TO_NEXT_CASE),
        "needs_visual_check": True,
        "visual_check_hint": "上面的 CMD（open-url）执行后会在输出中打印 [NEEDS_VISUAL_CHECK] 及截图绝对路径——"
                              "该图已在页面渲染就绪后自动拍摄，直接读取该路径判定即可，"
                              "不要 sleep 等待或另行调用 screenshot 命令重新截图。"
                              "如截图中 Recce 浮层遮挡主体内容，调用 dismiss-recce 拖离后重拍截图再确认"
                              "（走查步骤中 tap-text 遇 Recce 遮挡会自动处理）。"
                              "如有系统弹窗可用 tap 处理。"
                              "如果 CMD 执行失败（exit 1），可手动重试 open-url，最多 3 次。"
                              "确认后调用 ack 写入证据，否则 flow-advance 会被拦截。",
        "requires_ack": [
            {"key": "landing_page_opened_{ci}",
             "hint": "请先读图确认已成功跳转到目标落地页，再调用 ack"},
        ],
        "layer": "case_loop",
        "case_index": "{ci}",
    },
    {
        "id": "C3_walkthrough_{ci}",
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
        "id": "C4_report_{ci}",
        "desc": "生成 Case 报告（暂存本地）",
        "status": "pending",
        "cmd": "python3 scripts/cli.py gen-report",
        "success_markers": ["report.json 已生成"],
        "completion_check": {
            "type": "file_exists",
            "base": "current_case_output_dir",
            "glob": "report.json",
        },
        "on_fail": dict(_ON_FAIL_SKIP_TO_NEXT_CASE),
        "layer": "case_loop",
        "case_index": "{ci}",
    },
    {
        "id": "C5_mock_restore_{ci}",
        "desc": "Case 级 Mock 响应体回滚（仅恢复 response body，保持启用状态）",
        "status": "pending",
        "cmd": "python3 scripts/cli.py mock-restore --response-only",
        "success_markers": ["RESTORE DONE", "RESTORE SKIP"],
        "on_fail": dict(_ON_FAIL_BEST_EFFORT),
        "condition": "env.mock_ids non-empty",
        "layer": "case_loop",
        "case_index": "{ci}",
    },
]
# T2_cleanup.cmds：mock 清理 + 流程终结 + 本地工作目录清理。
# 设备释放由用户在 DevOps 层面管理，不在 SOP 自动清理范围内。
_T2_CLEANUP_CMDS = [
    "python3 scripts/cli.py mock record-stop",
    "python3 scripts/cli.py mock reset-env",
    "python3 scripts/cli.py flow-finalize",
    "python3 scripts/cli.py post-clean",
]
_BATCH_TAIL_STAGES = [
    {
        "id": "T0_mock_restore",
        "desc": "Batch 级 Mock 回滚",
        "status": "pending",
        "cmd": "python3 scripts/cli.py mock-restore",
        "success_markers": ["RESTORE DONE", "RESTORE SKIP"],
        "on_fail": dict(_ON_FAIL_BEST_EFFORT),
        "condition": "env.mock_ids non-empty",
        "layer": "batch_tail",
    },
    {
        "id": "T2_cleanup",
        "desc": "收尾清理",
        "status": "pending",
        "cmds": list(_T2_CLEANUP_CMDS),
        "notes": "flow-finalize 必须在 post-clean 之前执行：它标记 T2 completed、执行唯一的"
                 " batch-upload（生成报告 + 入库 + archive_run）。archive_run 已将 .run/ 归档到"
                 " output/run-<ts>/run/，所以随后 post-clean 清空 .run/ 不会丢失执行产物。",
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
def make_fresh_sop_stages(cases_manifest=None, device_type="sandbox"):
    """生成 SOP 阶段列表：B0-B3 + 每个 case 循环体 + T0-T2。"""
    # 复用 context.create_mock_lifecycle_policy/create_onboarding_profile 同一份
    # core.onboarding 注册表（_DEVICE_TYPE_PROFILE_REGISTRY），不在本文件重复
    # 维护一份 device_type → 实现类的字典——新增设备类型时只需要在
    # core/onboarding.py 注册一次。
    from core.profile.onboarding import create_mock_lifecycle_policy, create_onboarding_profile
    mock_policy = create_mock_lifecycle_policy(device_type)
    onboarding_profile = create_onboarding_profile(device_type)

    stages = copy.deepcopy(_BATCH_HEAD_STAGES)

    if not mock_policy.needs_mock_baseline_snapshot():
        stages = [s for s in stages if s["id"] != "B0_mock_snapshot"]

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
