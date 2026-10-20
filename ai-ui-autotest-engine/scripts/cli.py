#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI 交互辅助 CLI — 唯一入口。

设计原则：
  1. 所有命令按依赖层级分三层（Level 0/1/2）
  2. 复合命令组（mock / step / device）使用独立 subparser，
     每个子命令只声明自己的参数，零泄漏
  3. 公共参数定义抽取为共享函数，消除拷贝重复
  4. 互斥参数用 add_mutually_exclusive_group 约束
  5. 参数命名统一：--input / --output / --answers 语义一致
"""

import argparse
import os
import sys

# 源树零字节码（进程入口层）：入口脚本已用 `python3 -B` + 环境变量；此处覆盖
# 「直接运行本文件」的引导场景（`python3 scripts/cli.py ws-init`），并把开关导出给
# 子进程（`-B` 不继承，环境变量才继承）。
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

# ── 确保 scripts/ 在 sys.path 中（唯一一处路径管理） ──────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from cli_utils import resolve_active_context, auto_log_command, run_with_guard
from shared.errors import UsageError, soft_fail

# ── 所有 handler 的导入 ───────────────────────────────────────
from shared.case_utils import resolve_case_path, set_current_user_mis, resolve_mock_domain
from execution.engine.flow.flow_context import read_meta_fields
from execution.engine.sop.constants import FLOW_CONTEXT_FILENAME
from provisioning.prereq.check_deps import main as _check_deps_main
from shared.paths import (
    preflight_clean, clean_post_test, get_active_run, get_active_task, require_active_task,
)
from shared.workspace import cmd_ws_init as _cmd_ws_init

from provisioning.questions.commands import (
    cmd_input_next, cmd_input_answer, cmd_input_status,
    cmd_input_seed, cmd_input_schema,
)
from execution.engine.flow.flow_convert import flow_convert_main, cmd_flow_create
from execution.engine.flow.steps_generator import cmd_steps_generate, cmd_cases_create
from execution.engine.flow.commands.init_cmd import _cmd_flow_init, _cmd_flow_add_case, _cmd_case_init
from execution.engine.flow.commands.validate_cmd import _cmd_validate
from execution.engine.flow.commands.status_cmd import _cmd_flow_status, _cmd_flow_case_status
from execution.engine.flow.commands.hook_info_cmd import _cmd_hook_info
from execution.engine.flow.commands.next_cmd import _cmd_flow_next, _cmd_flow_advance
from execution.engine.flow.commands.ack_cmd import _cmd_ack
from execution.engine.flow.commands.finalize_cmd import _cmd_flow_finalize
from execution.engine.flow.commands.fail_cmd import _cmd_flow_fail, _cmd_skip_case
from execution.engine.flow.commands.event_cmd import _cmd_record_event

from platform.appmock.cli import _cmd_mock, _cmd_cleanup
from execution.engine.flow.lifecycle.mock_lifecycle import (
    cmd_mock_preflight, cmd_mock_apply, cmd_mock_restore,
)
from provisioning.setup.env_prepare import cmd_env_prepare
from reporting.gen_report import generate_case_report as _cmd_gen_report
from devices.device_commands import cmd_device as cmd_device_secondary
from resources.device_pool.commands import cmd_device as cmd_device_pooled, POOLED_SUBCMDS
from resources.device_pool.device_lease import DeviceLeaseManager as _DeviceLeaseManager
from resources.device_pool.lease_store import LocalFileLeaseStore as _LocalFileLeaseStore
from resources.mis_pool.commands import cmd_mis, maybe_heartbeat_mis

from execution.steps.locators import (
    _cmd_inspect_tree, _cmd_find_text, _cmd_find_icon, _cmd_find_input,
    _cmd_probe_status,
)
from execution.steps.device_cmds import (
    _cmd_install_app, _cmd_force_stop, _cmd_launch, _cmd_set_location,
    _cmd_disconnect, _cmd_shell,
)
from execution.steps.commands.tap import _cmd_tap_text, _cmd_tap
from execution.steps.commands.navigation import _cmd_open_url
from execution.steps.commands.screenshot import _cmd_screenshot
from execution.steps.commands.scroll import _cmd_swipe, _cmd_scroll_to_edge, _cmd_scroll_to_target, _cmd_screen_info
from execution.steps.commands.input import _cmd_input_text, _cmd_blur_input
from execution.steps.commands.assert_cmd import _cmd_assert_multi
from execution.steps.commands.recce import _cmd_dismiss_recce
from execution.steps.pipeline.engine import _cmd_step
from execution.steps.recording.log_cmd import _cmd_log_record
from execution.steps.recording.override_cmd import _cmd_override_step_result
from execution.steps.recording.relay_cmd import _cmd_relay_hook_result
from execution.steps.recording.assert_fields_cmd import _cmd_assert_fields
from execution.steps.api import cmd_response_search

from shared.observability.exception_reporter import cmd_report_error


# ═══════════════════════════════════════════════════════════════════
# 公共参数组：步骤结果（log-record / override-step-result 共用）
# ═══════════════════════════════════════════════════════════════════

def _add_step_result_args(parser, require_sid=True):
    """添加步骤结果公共参数。

    --sid 一律注册（required 由调用方决定）：override-step-result 必填；
    log-record 可选——用于把兜底操作（坐标点击等）绑定到声明的步骤。
    若仅在 require_sid 时注册，HOOK 指引中的 `log-record --sid <SID>`
    会直接被 argparse 拒收（unrecognized arguments: --sid）。
    """
    parser.add_argument("--sid", required=require_sid,
                        help="绑定的步骤 SID" + ("" if require_sid else "（可选：绑定到声明的步骤）"))
    parser.add_argument("--desc", required=True, help="结果描述")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--pass", dest="passed", action="store_true", help="标记结果为 PASS")
    group.add_argument("--fail", dest="failed", action="store_true", help="标记结果为 FAIL")
    parser.add_argument("--ok", type=int, default=None, help="显式指定结果值（0=fail/1=pass/2=warn）")
    parser.add_argument("--ms", type=int, default=None, help="耗时毫秒数")
    parser.add_argument("--started", type=float, default=None, help="操作开始时间戳")
    parser.add_argument("--img", default=None, help="引用的截图文件名（frames/ 下，不传则自动截当前画面）")
    parser.add_argument("--note", default="", help="附加备注")
    parser.add_argument("--error", default="", help="失败原因简述")
    parser.add_argument("--cause", action="append", default=[], help="失败原因列表")
    parser.add_argument("--suggest", action="append", default=[], help="修复建议列表")
    parser.add_argument("--fa", default=None, help="evidence JSON")


# ═══════════════════════════════════════════════════════════════════
# 复合命令构建函数
# ═══════════════════════════════════════════════════════════════════

def _build_mock_parser(sub):
    """构建 mock 子命令组：每个子命令独立 subparser，零参数泄漏。"""
    p = sub.add_parser("mock", help="AppMock 接口 Mock 管理")
    s = p.add_subparsers(dest="mock_subcmd")
    s.required = True

    # ── 设备端开关 ──
    s.add_parser("enable")
    s.add_parser("disable")

    # ── 服务端规则开关 ──
    po = s.add_parser("on")
    po.add_argument("--mock-id", required=True)
    pf = s.add_parser("off")
    pf.add_argument("--mock-id", required=True)

    # ── 规则 CRUD ──
    pc = s.add_parser("create")
    pc.add_argument("--rule", required=True)
    pc.add_argument("--response-file", default=None)
    pc.add_argument("--response", default=None)
    pc.add_argument("--desc", default="")
    pc.add_argument("--status-code", type=int, default=200)
    pc.add_argument("--force-add", action="store_true")
    pc.add_argument("--example-url", default=None, dest="example_url",
                    help="正则/非全匹配 rule 的示例 URL（带此字段可直接新建正则规则）")

    pu = s.add_parser("upsert")
    pu.add_argument("--mock-id", default=None)
    pu.add_argument("--rule", default=None)
    pu.add_argument("--response-file", default=None)
    pu.add_argument("--response", default=None)
    pu.add_argument("--desc", default="")
    pu.add_argument("--status-code", type=int, default=200)
    pu.add_argument("--force-add", action="store_true")
    pu.add_argument("--example-url", default=None, dest="example_url",
                    help="正则/非全匹配 rule 的示例 URL（带此字段可直接新建正则规则）")

    pud = s.add_parser("update")
    pud.add_argument("--mock-id", required=True)
    pud.add_argument("--rule", default=None)
    pud.add_argument("--response-file", default=None)
    pud.add_argument("--response", default=None)
    pud.add_argument("--desc", default="")
    pud.add_argument("--status-code", type=int, default=200)

    pp = s.add_parser("patch-field")
    pp.add_argument("--mock-id", required=True)
    pp.add_argument("--field", required=True)
    pp.add_argument("--value", required=True)

    pg = s.add_parser("get")
    pg.add_argument("--mock-id", required=True)

    s.add_parser("list")
    s.add_parser("stop-all")

    peff = s.add_parser("effective")
    peff.add_argument("--mock-ids", default=None,
                      help="场景 Mock id 列表（逗号分隔）；省略则只报 ptest 规则。"
                           "聚合展示 ptest 规则 + 场景规则 + 是否仍被 ptest 遮蔽")

    # ── 录制 ──
    prs = s.add_parser("record-start")
    prs.add_argument("--filter", default=None)
    prs.add_argument("--add-mock", action="store_true")

    s.add_parser("record-stop")

    prd = s.add_parser("record-data")
    prd.add_argument("--filter", default=None)
    prd.add_argument("--page", type=int, default=1)
    prd.add_argument("--page-size", type=int, default=100)
    prd.add_argument("--save", default=None)
    prd.add_argument("--no-save", action="store_true")
    prd.add_argument("--no-filter", action="store_true")
    prd.add_argument("--exclude-noise", action="store_true")

    # ── 环境切换 ──
    pes = s.add_parser("env-set")
    pes.add_argument("--env", required=True)

    s.add_parser("reset-env")

    # ── 泳道管理 ──
    s.add_parser("swimline-list")

    psa = s.add_parser("swimline-add")
    psa.add_argument("--url-pattern", required=True)
    psa.add_argument("--lane-name", required=True)

    pss = s.add_parser("swimline-switch")
    pss.add_argument("--rule-id", required=True)

    s.add_parser("swimline-off")

    psr = s.add_parser("swimline-remove")
    psr.add_argument("--rule-id", required=True)

    psv = s.add_parser("swimline-verify")
    psv.add_argument("--lane-name", default=None)
    psv.add_argument("--rule-id", default=None)
    psv.add_argument("--response", default=None)

    # ── 域名映射 ──
    pue = s.add_parser("url-mapping-ensure")
    pue.add_argument("--response", default=None)
    pue.add_argument("--response-file", default=None)

    s.add_parser("url-mapping-cleanup")

    pul = s.add_parser("url-mapping-list")
    pul.add_argument("--keyword", default=None)

    puu = s.add_parser("url-mapping-update")
    puu.add_argument("--url", required=True, dest="mapping_url")
    puu.add_argument("--beta-url", default="", dest="beta_url")
    puu.add_argument("--ppe-url", default="", dest="ppe_url")

    pudel = s.add_parser("url-mapping-delete")
    pudel.add_argument("--mapping-id", type=int, required=True)

    puf = s.add_parser("url-mapping-find")
    puf.add_argument("--keyword", required=True)

    puse = s.add_parser("url-mapping-set-env")
    puse.add_argument("--mapping-id", type=int, required=True)
    puse.add_argument("--env", default="beta", help="''遵循大环境/beta/ppe/close")

    # ── MRN 锁包 ──
    pbl = s.add_parser("bundle-lock")
    pbl.add_argument("--bundles", required=True)
    pbl.add_argument("--bundle-env", default="stage")

    return p


def _build_step_parser(sub):
    """构建 step 复合命令：每个 action 独立 subparser + 公共参数 parents。"""
    # 公共参数：所有 step action 共享
    # 注意：--sid 只注册在 step 解析器层面，不放在 common 中。
    # 放在 common 会导致 subparser 的 default(None) 覆盖 step 解析器已解析的 --sid 值。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--screenshot", default=None)
    common.add_argument("--no-screenshot", action="store_true")
    common.add_argument("--asserts", default=None, help="断言 JSON 数组")
    common.add_argument("--step-type", default="misc")
    common.add_argument("--desc", default="")
    common.add_argument("--page-ready", action="store_true", default=False,
                        help="操作后等待页面稳定再截图")
    common.add_argument("--debug-shot", action="store_true", dest="debug_shot",
                        help="action 执行完成后额外截一张 <sid>_after_action.png")

    p = sub.add_parser("step", help="执行声明步骤（复合命令：操作→等待→截图→断言→日志）")
    # --sid / --for-sid 只注册在 step 解析器层面（必须写在 action 之前）。
    # _build_step_command 确保 --sid 始终在 action 之前，因此 subparser 层面不需要 --sid，
    # 避免 default 值覆盖已解析结果。
    #   --sid      ：本命令就是该声明步骤（走完整管道，可改写结论）；
    #   --for-sid  ：归属型兜底操作（记录归入该步骤证据，但**不改变其结论**）。
    sid_group = p.add_mutually_exclusive_group()
    sid_group.add_argument("--sid", default=None)
    sid_group.add_argument("--for-sid", default=None, dest="for_sid",
                           help="兜底操作归属的声明步骤 SID：记录归入该步骤 attempts/证据，"
                                "不改变其结论（坐标兜底等补救动作用）")
    s = p.add_subparsers(dest="step_action")
    s.required = True

    # tap
    # 两种合法形态：--action-anchor（锚点定位，声明步骤用）或 --action-x/--action-y（坐标兜底）。
    # 因此二者都不能 required；完整性由 ACTION_SPECS 的 any_of 统一校验。
    tap_p = s.add_parser("tap", parents=[common])
    tap_p.add_argument("--action-x", type=int, default=None)
    tap_p.add_argument("--action-y", type=int, default=None)
    tap_p.add_argument("--action-anchor", default=None,
                       help="锚点文案：引擎点击锚点行唯一可点击目标（无文案图标）；"
                            "多候选/无候选转 AI 消歧")

    # tap-text
    tt_p = s.add_parser("tap-text", parents=[common])
    tt_p.add_argument("--action-arg", required=True)

    # scroll-until
    su_p = s.add_parser("scroll-until", parents=[common])
    su_p.add_argument("--action-arg", required=True)
    su_p.add_argument("--direction", default=None, choices=["up", "down", "left", "right"],
                      help="想看的方向（用户语义）：down(下方)/up(上方)/right(右侧)/left(左侧）。纵向默认由 viewport_offset 自动推断")

    # scroll-edge
    sb_p = s.add_parser("scroll-edge", parents=[common])
    sb_p.add_argument("--direction", default=None, choices=["up", "down", "left", "right"],
                      help="想看的方向（用户语义）：down(下方)/up(上方)/right(右侧)/left(左侧），默认 down")

    # back
    s.add_parser("back", parents=[common])

    # blur-input
    bl_p = s.add_parser("blur-input", parents=[common])
    # 统一用 --action-arg：生成器（_build_step_command）/ 动作参数契约（ACTION_SPECS）
    # 与 handler（handle_blur_input 读位置参数 action_arg）均已按 action_arg 对齐；
    # 曾经这里写的是 --action-anchor，导致生成的命令 argparse 报错、且锚点被静默丢弃。
    bl_p.add_argument("--action-arg", default=None)

    # open-url
    ou_p = s.add_parser("open-url", parents=[common])
    ou_p.add_argument("--action-arg", required=True)

    # assert-text（--asserts 由 common parents 提供）
    s.add_parser("assert-text", parents=[common])

    # input-text
    # 两种形态（与 tap 对称）：锚点/语义描述（声明步骤用）或坐标兜底（hook 回写 AI 找到的输入框坐标）。
    # 声明步骤不写坐标（R-CFL-002），坐标仅由运行期 hook 回填（step_scheduler 已支持）。
    it_p = s.add_parser("input-text", parents=[common])
    it_p.add_argument("--action-arg", required=True)
    it_p.add_argument("--action-x", type=int, default=None)
    it_p.add_argument("--action-y", type=int, default=None)

    return p


# ═══════════════════════════════════════════════════════════════════
# argparse 定义
# ═══════════════════════════════════════════════════════════════════

def build_parser():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True

    # ════════════════════════════════════════════════════════════════
    # Level 0：不需要 active_run
    # ════════════════════════════════════════════════════════════════

    p = sub.add_parser("set-mis", help="设置当前用户 MIS（一般由 flow-init 自动解析）")
    p.add_argument("--mis", required=True)

    p = sub.add_parser("check-deps", help="前置依赖自动检测与安装")
    p.add_argument("--platform", default="android", choices=["android", "harmony"],
                   help="仅用于标记上报的 platform 字段；依赖默认全量安装（含 hdc），不再按平台裁剪")

    sub.add_parser("ws-init", help="分配 workspace 并生成入口脚本；之后所有命令都用该入口执行")

    p = sub.add_parser("console", help="统一控制台服务（多设备实时监控 + 动态日志；跨会话共享）")
    _cs = p.add_subparsers(dest="console_subcmd")
    _cs.add_parser("ensure", help="幂等启动（已启动则复用，其他会话据此跳过）")
    _cs.add_parser("up", help="同 ensure")
    _cs.add_parser("status", help="查看运行状态")
    _cs.add_parser("url", help="打印访问地址")
    _cs.add_parser("down", help="停止服务（一般不需要，服务设计为常驻）")

    sub.add_parser("preflight-clean", help="启动预检清理：清空【本 workspace】工作区内容")
    sub.add_parser("post-clean", help="测试完成后清理：清空【本 workspace】内容并删除入口")

    sub.add_parser("input-next", help="信息收集：返回下一个待解决问题")

    p = sub.add_parser("input-seed", help="信息收集：批量预置用户已知值（收集循环前）")
    p.add_argument("--answers", required=True, help='JSON 对象 {问题id: 值}')

    sub.add_parser("input-schema", help="信息收集：问题目录（可预置/待问的字段与选项）")

    p = sub.add_parser("input-answer", help="信息收集：提交一条答案")
    p.add_argument("--id", required=True, help="问题 ID")
    p.add_argument("--value", required=True,
                   help="答案值（true/false/数组/对象按 JSON，其余按字符串）")

    sub.add_parser("input-status", help="信息收集：总览已解析/待问")


    p = sub.add_parser("flow-create", help="创建空 Flow .md 文件")
    p.add_argument("--name", required=True, help="文件名（不含 .md 后缀）")

    p = sub.add_parser("flow-convert", help="解析 Flow .md 元数据，输出解析报告")
    p.add_argument("--flow-source", default=None, nargs="+", help="Flow 文件路径，支持多个")
    p.add_argument("--flow-dir", default=None, help="Flow 文件目录")
    p.add_argument("--tag", required=True, help="输出文件 tag")
    p.add_argument("--batch-name", default=None, help="批次名称")

    p = sub.add_parser("steps-generate", help="接收 CASES JSON，输出最终 steps-input.json")
    p.add_argument("--input", required=True, dest="json", help="CASES JSON 文件路径")
    p.add_argument("--tag", required=True, help="输出文件 tag")

    p = sub.add_parser("cases-create", help="创建空 CASES JSON 文件（强制约定：AI 写内容前必须先创建）")
    p.add_argument("--tag", required=True, help="输出文件 tag")
    p.add_argument("--force", action="store_true", help="已存在时重置为空文件")

    p = sub.add_parser("validate", help="Dry-run 校验 steps-input.json")
    p.add_argument("--input", default=None, dest="json", help="steps-input.json 文件路径")

    p = sub.add_parser("report-error", help="异常终止诊断上报")
    p.add_argument("--message", required=True, help="结果摘要")
    p.add_argument("--code", default="", help="错误码")
    p.add_argument("--stage", default="", help="发生阶段")
    p.add_argument("--category", default="unknown", help="归因分类")
    p.add_argument("--severity", default="error", help="error/fatal")
    p.add_argument("--raw", default="", help="原始错误详情")
    p.add_argument("--mis", default="", help="用户 MIS")
    p.add_argument("--analysis", default="", help="AI 归因诊断 JSON")
    p.add_argument("--extra", default="", help="附加结构化上下文 JSON（并入 context）")

    # ════════════════════════════════════════════════════════════════
    # Level 1：需要 run_dir（active_run）
    # ════════════════════════════════════════════════════════════════

    p = sub.add_parser("flow-init", help="初始化 flow-context.json")
    p.add_argument("--dir", required=True, help="用例目录名")
    p.add_argument("--input", required=True, dest="json", help="steps-input.json 文件路径")
    p.add_argument("--flow-name", default="", help="Flow 名称")
    p.add_argument("--mis", default="", help="用户 MIS 号")

    p = sub.add_parser("flow-add-case", help="追加一个 case 到 steps-input.json")
    p.add_argument("--dir", required=True, help="用例目录名")
    p.add_argument("--input", required=True, dest="json", help="单个 case 的 JSON 文件路径")

    p = sub.add_parser("flow-status", help="获取当前执行状态；--sid 查单步详情")
    p.add_argument("--sid", default=None, help="步骤 ID，提供时输出该步骤精简详情")
    sub.add_parser("flow-case-status", help="显示 batch 执行进度")
    sub.add_parser("flow-finalize", help="终结阶段收口")

    p = sub.add_parser("hook-info", help="按需查询单个 hook 的完整操作指引（cli_hint）")
    p.add_argument("--hook-id", required=True, help="Hook ID，如 resolve_scroll_target_not_found")
    p.add_argument("--sid", default=None, help="步骤 ID（用于关联该步骤的运行时参数，可选）")

    p = sub.add_parser("flow-next", help="获取当前阶段内下一步命令")
    p.add_argument("--done-hooks", default=None, help="标记当前步骤的单个 hook 完成")

    p = sub.add_parser("flow-advance", help="标记当前 SOP 阶段完成并推进到下一阶段")
    p.add_argument("--force", action="store_true", help="跳过完成证据校验强制推进")

    p = sub.add_parser("ack", help="通用门禁确认")
    p.add_argument("--key", required=True, help="requires_ack 声明的 key")
    p.add_argument("--result", default=None, help="AI 断言结论 JSON 字符串")

    p = sub.add_parser("flow-fail", help="SOP 阶段失败收口")
    p.add_argument("--stage", required=True, help="失败的阶段 ID")
    p.add_argument("--error", required=True, help="失败原因描述")
    p.add_argument("--cleanup", action="store_true", help="强制执行完整清理")

    p = sub.add_parser("gen-report", help="生成 Case 报告 + 批次聚合上传")
    p.add_argument("--output-dir", default=None, help="报告输出目录")
    p.add_argument("--no-db", action="store_true", help="跳过数据库写入")

    p = sub.add_parser("skip-case", help="AI 主动结束当前 Case")
    p.add_argument("--reason", required=True, help="结束当前 Case 的原因")

    p = sub.add_parser("case-init", help="切换到指定 Case（batch 模式专用）")
    p.add_argument("--case-index", required=True, type=int, help="Case 索引（0-based）")

    sub.add_parser("mock-preflight", help="场景 Mock 预检（快照 union + 冲突检测 + 清场）")

    p = sub.add_parser("mock-apply", help="收敛场景 Mock 到指定 case")
    p.add_argument("--case-index", required=True, type=int, dest="case_index")

    sub.add_parser("mock-restore", help="场景 Mock 回滚（恢复 union 到执行前状态）")

    p = sub.add_parser("record-event", help="向 run-events.jsonl 记录一条事件")
    p.add_argument("--event", required=True, help="事件类型")
    p.add_argument("--details", default="", help="事件详情 JSON 字符串")
    p.add_argument("--severity", default="info", help="严重程度")
    p.add_argument("--screenshots", nargs="*", default=[], help="关联截图路径列表")
    p.add_argument("--evidence-type", default=None, help="证据类型")
    p.add_argument("--method", default=None, help="证据采集方法")
    p.add_argument("--status", default="recorded", help="证据状态")
    p.add_argument("--artifacts", nargs="*", default=[], help="关联文件路径列表")
    p.add_argument("--stage", default="", help="所属阶段")
    p.add_argument("--case-index", type=int, default=None, help="关联的 Case 索引")

    # log-record：纯日志（不修改 flow-context），sid 可选
    p = sub.add_parser("log-record", help="记录纯日志到 steps.jsonl（不修改 flow-context）")
    _add_step_result_args(p, require_sid=False)

    # override-step-result：覆盖终态结论（修改 flow-context），sid 必填
    p = sub.add_parser("override-step-result", help="覆盖已声明步骤的终态结论（修改 flow-context）")
    _add_step_result_args(p, require_sid=True)
    p.add_argument("--log-type", default="override", help="记录类型标签")
    p.add_argument("--assert-verdict", default=None,
                   help='JSON dict：逐断言判定，键=断言 id。'
                        '值可为 "pass"/"fail"/"pending"，或结构化对象 '
                        '{"result":"fail","verdict":"visual","actual":"实测值","reason":"原因",'
                        '"targets":[{"expect":"券码为 11 位数字","result":"fail","actual":"13 位"}]}。'
                        '示例: \'{"A1":{"result":"pass","verdict":"exact","actual":"待使用"},'
                        '"A3":{"result":"fail","verdict":"visual","actual":"实测 13 位"}}\'')

    p = sub.add_parser("relay-hook-result", help="AI 将 Hook 执行结果（ai_result）写回 flow-context")
    p.add_argument("--sid", required=True, help="绑定的步骤 SID")
    p.add_argument("--hook-id", required=True, help="Hook ID，如 resolve_text_not_found")
    p.add_argument("--verdict", default="resolved",
                   choices=["resolved", "partially", "unresolved"],
                   help="Hook 执行结论（默认 resolved）")
    p.add_argument("--resolution", default="", help="解决方案描述，如 semantic_match / viewport_scroll")
    p.add_argument("--anomalies", default=None,
                   help='JSON 数组，偏差记录，如 \'[{"type":"TEXT_MISMATCH","detail":"..."}]\'')
    p.add_argument("--note", default=None, help="附加备注")

    p = sub.add_parser("assert-fields", help="AI 断言字段结果")
    p.add_argument("--sid", required=True, help="绑定的步骤 SID")
    p.add_argument("--desc", required=True, help="结果描述")
    p.add_argument("--results", required=True, help="JSON 数组，字段级别断言结果")
    p.add_argument("--picked", type=int, default=None,
                   help="埋点多候选消歧：选定目标事件序号（1-based，见 track_candidates_<sid>.json）。"
                        "仅当步骤命中多个候选时必填")

    # response-search：在 API 证据的原始响应里按关键字/路径检索
    p = sub.add_parser("response-search", help="在 API 步骤原始响应里按关键字/路径检索")
    p.add_argument("--sid", default=None, help="API 步骤 SID（缺省取最新证据文件）")
    _resp = p.add_mutually_exclusive_group(required=True)
    _resp.add_argument("--query", default=None, help="按键名或值子串检索（大小写不敏感）")
    _resp.add_argument("--path", default=None, help="按点号路径精确取值，如 response.data.price")
    _resp.add_argument("--skeleton", action="store_true", help="输出响应浅骨架（结构总览）")
    p.add_argument("--limit", type=int, default=50, help="检索条数上限（默认 50）")

    sub.add_parser("cleanup", help="异常中断后的资源清理（泳道关闭+Mock 状态清理）")

    p = sub.add_parser("env-prepare", help="一键环境准备")
    p.add_argument("--mis", default=None, help="用户 MIS 号")
    p.add_argument("--env", default=None, choices=["online", "alpha", "swimline", "noop"],
                   help="环境类型")
    p.add_argument("--ptest", action="store_true", default=None,
                   help="开启 ptest（仅线上环境 A 生效；其他环境会校验失败）")
    p.add_argument("--account", default=None, help="登录账号")
    p.add_argument("--password", default=None, help="登录凭证")
    p.add_argument("--location", default=None, help="城市预设名")
    p.add_argument("--bundles", default=None, help="MRN 锁包列表")
    p.add_argument("--bundle-env", default="stage", help="锁包环境")
    p.add_argument("--lane-name", default=None, help="泳道名称")
    p.add_argument("--url-pattern", default=None, help="泳道 URL 匹配模式")
    p.add_argument("--url-mapping", default=None, help="域名映射 JSON 数组")

    # ── device 子命令组 ──
    p = sub.add_parser("device", help="设备生命周期管理")
    p.add_argument("device_subcmd", choices=[
        "create", "setup", "query",
        "check-version", "register",
        "release", "pool-gc", "clean-tmp",
    ])
    p.add_argument("--force-reinstall", action="store_true",
                   help="setup 时强制卸载重装")

    # ── mis 子命令组（虚拟 mis 池）──
    p = sub.add_parser("mis", help="虚拟 mis 池（AppMock 工作域）")
    p.add_argument("mis_subcmd", choices=["acquire", "status", "release", "release-stale"])
    p.add_argument("--mis", default=None, help="acquire 时显式指定真实 mis（默认取 resource_mis）")
    p.add_argument("--pool", action="store_true", help="status 时看全池（默认只看本人私有）")
    p.add_argument("--hours", type=int, default=6, help="release-stale 阈值（小时，默认 6）")

    # ── mock 子命令组（独立 subparser） ──
    _build_mock_parser(sub)

    # ════════════════════════════════════════════════════════════════
    # Level 2：需要设备 + 自动记录
    # ════════════════════════════════════════════════════════════════

    # ── step 复合命令（subparser 模式） ──
    _build_step_parser(sub)

    p = sub.add_parser("open-url", help="打开 Scheme 落地页")
    p.add_argument("--url", required=True, help="目标 Scheme URL")

    p = sub.add_parser("tap-text", help="点击指定文案元素")
    p.add_argument("--text", required=True, help="目标可点击文案")
    p.add_argument("--step-dir", default=None, help="启动步骤耗时的 case 目录（写入 .timer），非截图目录")

    p = sub.add_parser("tap", help="点击精确坐标")
    p.add_argument("--x", type=int, required=True, help="目标点击坐标 x")
    p.add_argument("--y", type=int, required=True, help="目标点击坐标 y")

    p = sub.add_parser("screenshot", help="手动截图")
    p.add_argument("--out", required=True, help="截图输出的完整文件路径")

    p = sub.add_parser("swipe", help="语义滑动: --direction down --step 0.7")
    p.add_argument("--direction", default=None, choices=["up", "down", "left", "right"],
                   help="滑动方向")
    p.add_argument("--step", type=float, default=None,
                   help="步进比例（0~1，相对手势区域全幅）")
    p.add_argument("--x1", type=int, default=None, help="起点 x（兼容坐标模式）")
    p.add_argument("--y1", type=int, default=None, help="起点 y（兼容坐标模式）")
    p.add_argument("--x2", type=int, default=None, help="终点 x（兼容坐标模式）")
    p.add_argument("--y2", type=int, default=None, help="终点 y（兼容坐标模式）")
    p.add_argument("--duration", type=int, default=None, help="滑动持续时间（ms）")

    p = sub.add_parser("screen-info", help="打印屏幕布局参数，供 AI 决策滚动策略")

    p = sub.add_parser("scroll-edge", help="快速滚动到内容边界。--direction 用户语义：想看的方向(down/up/right/left)")
    p.add_argument("--times", type=int, default=4, help="滑动次数")
    p.add_argument("--direction", default=None, choices=["up", "down", "left", "right"],
                   help="想看的方向（用户语义）：down(下方)/up(上方)/right(右侧)/left(左侧），默认 down")
    p.add_argument("--y-from", type=int, default=None, help="滑动起点 y")
    p.add_argument("--y-to", type=int, default=None, help="滑动终点 y")

    p = sub.add_parser("scroll-until", help="定位目标文案并滚动到视口内。--direction 用户语义：想看的方向(down/up/right/left)")
    p.add_argument("--text", required=True, help="目标文案")
    p.add_argument("--direction", default=None, choices=["up", "down", "left", "right"],
                   help="想看的方向（用户语义）：down(下方)/up(上方)/right(右侧)/left(左侧）。纵向默认由 viewport_offset 自动推断")

    p = sub.add_parser("input-text", help="输入文本")
    p.add_argument("--text", required=True, help="输入文本")
    p.add_argument("--x", type=int, required=True, help="坐标 x")
    p.add_argument("--y", type=int, required=True, help="坐标 y")

    p = sub.add_parser("blur-input", help="让输入框失焦触发校验")
    p.add_argument("--anchor", required=True, help="输入框附近的任意文本")

    # assert-multi 统一入口（合并 assert-text / assert-gone 能力）
    p = sub.add_parser("assert-multi", help="多项断言（合并 assert-text/assert-gone 功能）")
    p.add_argument("--present", action="append", default=[], help="断言存在的文案")
    p.add_argument("--gone", action="append", default=[], help="断言消失的文案")

    p = sub.add_parser("inspect-tree", help="采集 Native 视图树并落盘")
    p.add_argument("--wait", type=int, default=3, help="采集超时秒数")

    p = sub.add_parser("find-text", help="按文案定位元素，返回可点击坐标")
    p.add_argument("--text", required=True, help="目标文案")
    p.add_argument("--wait", type=int, default=3, help="采集超时秒数")

    p = sub.add_parser("find-icon", help="定位无文案的图标按钮")
    p.add_argument("--anchor", required=True, help="邻近锚点文案")
    p.add_argument("--wait", type=int, default=3, help="采集超时秒数")

    p = sub.add_parser("find-input", help="定位输入框")
    p.add_argument("--anchor", required=True, help="邻近锚点文案")
    p.add_argument("--wait", type=int, default=3, help="采集超时秒数")

    p = sub.add_parser("probe-status", help="输出探针链健康状态")
    p.add_argument("--texts", action="store_true", default=False,
                   help="额外输出页面可见文本预览")

    sub.add_parser("dismiss-recce", help="拖离 Recce 浮层")
    sub.add_parser("disconnect", help="断开 imeituan session")

    p = sub.add_parser("set-location", help="预设设备 GPS 模拟定位")
    p.add_argument("preset", help="城市预设: beijing/shanghai/... 或 off")

    p = sub.add_parser("force-stop", help="强制停止 App 进程")
    p.add_argument("--package", default=None, help="App 包名")

    p = sub.add_parser("launch", help="启动 App 到首页")
    p.add_argument("--package", default=None, help="App 包名")
    p.add_argument("--activity", default=None, help="指定 Activity")
    p.add_argument("--wait", type=float, default=5.0, help="启动后等待秒数")

    p = sub.add_parser("install-app", help="安装/更新被测 App")
    p.add_argument("--url", default=None, help="APK URL")
    p.add_argument("--timeout", type=int, default=300, help="安装超时秒数")

    p = sub.add_parser("shell", help="在设备上执行原始 adb shell 命令")
    p.add_argument("shell_cmd", nargs="+", help="要执行的 shell 命令及参数")

    return ap


# ═══════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════

def _bind_device_session():
    """进程边界：把本进程的设备命令绑定到当前 run 的 imeituan session。

    并发隔离的关键：每个 cli 进程服务一个 run（AI_UITEST_TASK），因此把
    flow-context.json 的 session_id 绑定到进程环境，后续所有 imeituan 设备命令
    都路由到本 run 的设备，不再依赖 ~/.imeituan 的全局活跃 session（那个是全局
    单例，并发 run 会互相抢走）。

    无 active run / 无 session_id 时是 no-op；任何异常都不得影响主流程。
    """
    try:
        case_name = get_active_run()
        if not case_name:
            return
        fc_path = os.path.join(resolve_case_path(case_name), FLOW_CONTEXT_FILENAME)
        sid = (read_meta_fields(fc_path) or {}).get("session_id", "")
        if sid:
            from devices.toolchain.imeituan_cli import bind_session
            bind_session(sid)
    except Exception as e:
        soft_fail("infra", "DEVICE_SESSION_BIND_FAILED", e)


def _maybe_attach_console(args):
    """best-effort：服务在线时把本命令的 stdout/stderr 镜像到控制台（零侵入）。

    服务未启动时 `maybe_install_tee()` 直接返回，**不包裹任何流、零开销**。
    """
    if getattr(args, "cmd", "") in ("console", "ws-init", "check-deps"):
        return
    try:
        from console.telemetry import maybe_install_tee
        maybe_install_tee(task=get_active_task(), run=get_active_run(),
                          cmd=getattr(args, "cmd", "") or "")
    except Exception:
        pass


def _print_console_link():
    """会话起点（ws-init）打印实时控制台链接，便于用户随时查看设备画面与日志。"""
    try:
        from console.commands import banner_link
        link = banner_link()
        if link:
            print(f"  🖥  实时控制台（多设备画面 + 动态日志）: {link}")
    except Exception:
        pass


def main():
    ap = build_parser()
    args = ap.parse_args()
    _maybe_attach_console(args)
    _bind_device_session()
    run_with_guard(args, dispatch)


# ═══════════════════════════════════════════════════════════════════
# 查表分发
# ═══════════════════════════════════════════════════════════════════

def _heartbeat_lease():
    """命令级心跳：刷新当前 run 的**设备租约**与**虚拟 mis 占用**（best-effort）。

    CLI 每次调用都是独立进程，靠这条心跳让资源池知道该 run 仍活着：
      · 设备租约（本地文件，廉价）—— 每次命令都刷；
      · 虚拟 mis（网络调用）—— **限流**（≥30min 一次），避免拖慢每条命令。
    无 run / 无租约 / 无 mock_domain 时是 no-op；任何异常都不得影响主流程。
    """
    owner = get_active_run()
    if owner:
        try:
            _DeviceLeaseManager(store=_LocalFileLeaseStore()).renew(owner)
        except Exception as e:
            soft_fail("infra", "LEASE_HEARTBEAT_FAILED", e)
    try:
        md = resolve_mock_domain()
        if md:
            maybe_heartbeat_mis(md)
    except Exception as e:
        soft_fail("infra", "MIS_HEARTBEAT_FAILED", e)


# ════════════════════════════════════════════════════════════════
# workspace 门禁白名单
# ════════════════════════════════════════════════════════════════
# 除白名单外，**所有命令**都必须在 workspace 内执行（统一门禁，不逐个命令判断）。
# 唯一例外是 `ws-init`：它负责分配 workspace 本身，自然不能要求已有 workspace。
WORKSPACE_FREE_CMDS = ("ws-init", "console")


def dispatch(args):
    """命令路由。

    必须把 handler 的返回值原样回传给错误边界（run_with_guard）：
    handler 通过【返回非 0 退出码】表达「正常执行的负面结论」
    （如 find-text 未命中、shell 透传设备返回码、assert 判定失败），
    返回值若被丢弃，这些失败会被错误地当作成功（exit 0）。
    错误则通过 raise shared.errors.AutotestError 表达。
    """
    cmd = args.cmd

    # ── workspace 门禁（统一，白名单之外一律需要）──
    # 无 workspace 直接报错，不回落默认值：
    #   ① 回落会让多个 Agent 静默共用同一个工作区；
    #   ② 统一在此判断，新命令默认即受限，不可能遗漏。
    if cmd not in WORKSPACE_FREE_CMDS:
        require_active_task()

    # ── Level 0：不依赖 active_run（但依赖 workspace）──
    if cmd == "set-mis":
        return set_current_user_mis(args.mis)
    if cmd == "check-deps":
        return _check_deps_main(platform=getattr(args, "platform", "android"))
    if cmd == "ws-init":
        result = _cmd_ws_init(args)
        _print_console_link()
        return result
    if cmd == "console":
        from console.commands import cmd_console
        return cmd_console(args)
    if cmd == "preflight-clean":
        preflight_clean()
        print("Preflight cleanup done")
        return None
    if cmd == "post-clean":
        clean_post_test()
        print("Post-test cleanup done")
        return None
    if cmd == "input-next":
        return cmd_input_next(args)
    if cmd == "input-seed":
        return cmd_input_seed(args)
    if cmd == "input-schema":
        return cmd_input_schema(args)
    if cmd == "input-answer":
        return cmd_input_answer(args)
    if cmd == "input-status":
        return cmd_input_status(args)
    if cmd == "flow-create":
        return cmd_flow_create(args)
    if cmd == "flow-convert":
        return flow_convert_main(args)
    if cmd == "steps-generate":
        return cmd_steps_generate(args)
    if cmd == "cases-create":
        return cmd_cases_create(args)
    if cmd == "validate":
        return _cmd_validate(args)
    if cmd == "report-error":
        # 将 namespace 传给 cmd_report_error（其内部有独立 parser 支持 standalone 调用）
        return cmd_report_error(args)

    # ── Level 1：需要 run_dir（active_run） ──
    if cmd == "flow-init":
        return _cmd_flow_init(args)
    if cmd == "flow-add-case":
        return _cmd_flow_add_case(args)
    if cmd == "device":
        _heartbeat_lease()
        if args.device_subcmd in POOLED_SUBCMDS:
            return cmd_device_pooled(args)
        return cmd_device_secondary(args)
    if cmd == "mis":
        _heartbeat_lease()
        return cmd_mis(args)
    if cmd == "cleanup":
        return _cmd_cleanup(args)
    if cmd == "env-prepare":
        resolve_active_context(args, need_serial=True)
        _heartbeat_lease()
        return cmd_env_prepare(args)
    if cmd == "mock":
        resolve_active_context(args, need_serial=False)
        return _cmd_mock(args)
    if cmd in _LEVEL1_HANDLERS:
        resolve_active_context(args, need_serial=False)
        return _LEVEL1_HANDLERS[cmd](args)

    # ── Level 2：需要设备 + 自动记录 ──
    if cmd in _LEVEL2_HANDLERS:
        resolve_active_context(args, need_serial=True)
        _heartbeat_lease()
        auto_log_command(args)
        return _LEVEL2_HANDLERS[cmd](args)

    raise UsageError(f"未知命令 '{cmd}'")


# ═══════════════════════════════════════════════════════════════════
# 查表（避免长 if/elif 链）
# ═══════════════════════════════════════════════════════════════════

_LEVEL1_HANDLERS = {
    "flow-status": _cmd_flow_status,
    "hook-info": _cmd_hook_info,
    "flow-next": _cmd_flow_next,
    "flow-advance": _cmd_flow_advance,
    "ack": _cmd_ack,
    "flow-fail": _cmd_flow_fail,
    "flow-finalize": _cmd_flow_finalize,
    "gen-report": _cmd_gen_report,
    "skip-case": _cmd_skip_case,
    "case-init": _cmd_case_init,
    "flow-case-status": _cmd_flow_case_status,
    "mock-preflight": cmd_mock_preflight,
    "mock-apply": cmd_mock_apply,
    "mock-restore": cmd_mock_restore,
    "record-event": _cmd_record_event,
    "log-record": _cmd_log_record,
    "override-step-result": _cmd_override_step_result,
    "relay-hook-result": _cmd_relay_hook_result,
    "assert-fields": _cmd_assert_fields,
    "response-search": cmd_response_search,
}

_LEVEL2_HANDLERS = {
    "open-url": _cmd_open_url,
    "tap-text": _cmd_tap_text,
    "tap": _cmd_tap,
    "screenshot": _cmd_screenshot,
    "swipe": _cmd_swipe,
    "scroll-edge": _cmd_scroll_to_edge,
    "scroll-until": _cmd_scroll_to_target,
    "screen-info": _cmd_screen_info,
    "input-text": _cmd_input_text,
    "blur-input": _cmd_blur_input,
    "assert-multi": _cmd_assert_multi,
    "inspect-tree": _cmd_inspect_tree,
    "find-text": _cmd_find_text,
    "find-icon": _cmd_find_icon,
    "find-input": _cmd_find_input,
    "probe-status": _cmd_probe_status,
    "dismiss-recce": _cmd_dismiss_recce,
    "disconnect": _cmd_disconnect,
    "set-location": _cmd_set_location,
    "force-stop": _cmd_force_stop,
    "launch": _cmd_launch,
    "install-app": _cmd_install_app,
    "shell": _cmd_shell,
    "step": _cmd_step,
}


if __name__ == "__main__":
    main()