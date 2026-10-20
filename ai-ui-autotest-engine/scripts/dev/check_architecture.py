#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""架构守卫 —— 用静态检查固化错误体系与分层约束，防止回退。

三十项检查：

  1. no-sys-exit            （硬失败）除 CLI 边界外，任何模块不得调用 `sys.exit()`
                            —— 业务/核心层只 raise shared.errors.AutotestError 或返回退出码，
                               由 cli_utils.run_with_guard 唯一决定进程退出码。
  2. no-silent-swallow      （硬失败）`except ...: pass` 只允许在显式白名单（SWALLOW_ALLOWLIST）内；
                            白名单外出现即失败——新增吞噬必须逐条定性并登记理由。
  3. layering               （硬失败）跨包模块级强连通分量（SCC）必须为 0，
                            即不允许出现相互 import 的模块环。
  4. all-modules-import     （硬失败）逐个 import 所有模块，不得有导入错误；
                            抓「漏再导出 / 破损导入」（只看 import cli 或编译发现不了）。
  5. staged-deletion-referenced（硬失败）git 暂存区里删除的模块不得仍被引用；
                            固化「删除旧模块必须在所有引用方改完之后」这条纪律。
  6. placeholder-single-entry（硬失败）`resolve_placeholders` 只允许在 flow_init.py 调用。
                            steps-input 在 flow-init 时被解析并落盘为唯一事实来源，
                            运行期读者只读解析后的产物；其它模块各自解析会让
                            C0 case-init 重载时又把未解析原文带回来（历史回归根因）。
  7. layer-direction        （棘轮）分层依赖方向：跳层 import 不得超过基线（只许下降）。
  8. no-device-destroy      （硬失败）不得重新引入「设备销毁」能力（T2：复用优先、不销毁实例）。
  9. forbidden-edges        （硬失败）`devices → resources` 等反向依赖直接失败（不受规则 7 棘轮保护）。
 10. lease-single-entry     （硬失败）`device_pool_leases_path` 只允许在租约存储后端调用。
 11. appmock-contract       （硬失败）AppMock 代理契约（离线，stub 掉网络）：
                            CLI 边界必须显式传 mis（多 shard 隔离）；信封解析 / mockId 提取 /
                            请求形状（userDomain、无 title）/ list 读 {items} / create 透传 exampleUrl / ensure 激活 /
                            **ptest 规则按场景 Mock 路径做负向前瞻排除**（防 catch-all 遮蔽回归）
 12. question-framework     （硬失败）信息收集框架契约（离线）：schema 校验 / 拓扑与条件（==/!=/in）/
                           派生延迟求值 / 封闭选项白名单 / 真实 provider 问题集与顺序 /
                           **可选能力按环境能力矩阵门控（ptest 仅 A、泳道仅 B）** /
                           **派生值 = 当前输入的纯函数（上游变更即重算；用户覆盖的派生题不重算）** /
                           **环境变更后的级联失效**
 13. device-session-isolation（硬失败）设备会话并发隔离：禁止 `all_sessions`/`disconnect --all`
                           （会踢掉并发 run 的会话）；设备命令出口必须实现会话绑定
                           （bind_session + IMEITUAN_SESSION），CLI 入口必须按 active run 绑定
 14. login-layer-no-platform-branch（硬失败）登录层不得出现平台 / 设备类型分支
                           （平台差异必须走 PlatformOps 或策略注册表）
 15. login-restart-declared（硬失败）登录前置步骤必须声明重启策略，
                           且重启点数量不得低于基线（F-2：重启点一个不减）
 16. login-android-probe-frozen（硬失败）Android 登录态探针必须保持前台判定语义
                           （`check_login_state` + `authoritative_for_password = False`）
 17. popup-single-implementation（硬失败）弹窗消除只有一条路径：
                           词表 `platform/popup/patterns.py` + 执行器 `devices/popup.py`，
                           不得在代码里发 CLI `control popup clear`
 18. restart-reason-required（硬失败）登录步骤声明了非 `NONE` 的 `RestartPolicy`
                           必须同时给出 `restart_reason`（"为什么这里必须重启"可读）
 19. artifact-cache-single-entry（硬失败）L1 制品缓存只能经 `shared/artifact_cache.py`
                           访问：其它模块不得出现 `.cache` 字面量（详见该规则注释）
 20. appmock-state-primitive-single-entry（硬失败）AppMock 设备端**真实状态原语**
                           `check_appmock_sdk_enabled` 只允许「必须知道真实状态才能决策」
                           的模块消费（原语定义处 + `login/steps.py::EnableAppMock`）；
                           业务层必须走能力位语义入口 `appmock_ready()`
                           （否则平台差异会以隐式分支漏进业务层，绕过规则 14）
 21. login-action-no-platform-literal（硬失败）认证动作层（L3，`login/actions/**`）
                           不得出现**平台 / 控件字面量**（资源 id、平台工具/组件类、平台目录）：
                           控件选择器必须来自 `PageSpec` 数据、平台差异必须走 `PlatformOps`
 22. reconcile-single-entry（硬失败）环境澄清（前台 + 遮挡弹窗）业务层只能经唯一入口
                           `provisioning/setup/environment_reconciler.py::reconcile_environment()`；
                           执行器 `devices.popup.dismiss_popups` 不得被业务层直接调用
                           （否则等待窗口/返回语义/日志口径会分叉）
 23. reconcile-after-last-restart（硬失败）澄清必须排在所有重启类步骤**之后**：
                           L2 管线 pre 的末位必须是 `SettlePopups`（且其后不得再有重启步骤）；
                           post 阶段实际发生冷重启时编排层必须有澄清复核
 24. page-spec-contract（硬失败）`PageSpec` 数据契约（"新增平台 = 补一份数据"的门禁）：
                           必须是非空字面量数据 / 页面身份非空 / 控件名为语义名 / 选择器
                           `by` 在白名单内且 `value` 类型正确；`routes` 每条路径非空、
                           每跳 `enter`/`expect` 均为合法选择器列表且 `enter` 非空
                           （写错会静默永不命中）
 25. no-local-import-shadowing（硬失败）函数内 import 不得与模块级绑定同名：
                           同名会让该名字在整个函数内变成**局部变量**，条件分支里的
                           同名 import 若不执行，后续使用会抛 `UnboundLocalError`，
                           把真实错误掩盖成脚本缺陷。必须直接用模块级绑定。
 26. no-pagespec-legacy-fields（硬失败）不得再访问 `PageSpec` 已移除的字段（如 `entries`）：
                           PageSpec 字段演进（entries → routes）时若忘记同步消费者，
                           导入/编译都不会报错，只在**运行期**抛 AttributeError。
                           本规则把旧字段名固化为黑名单，出现 `X.<旧字段>` 即失败。
 27. no-implicit-platform-default（硬失败）`platform` 参数不得设默认值
                           （`devices/lifecycle/**` 与 `shared/context.py` 的工厂函数）：
                           默认值会让"漏传/漏配置"静默按某个平台处理
                           （实测：create_device_lifecycle(device_type) 用默认 android
                           处理鸿蒙云模拟器）。平台必须显式传入。
 28. platform-login-probe-registered（硬失败）`SUPPORTED_DEVICE_COMBINATIONS` 中
                           出现的每个 platform 必须在 `LOGIN_STATE_PROBES` 显式登记
                           （否则登录态判定会静默回落到前台探针，语义可能与平台不符）。
 29. clear-data-reprovision（硬失败）任何「清数据冷重启」之后必须重建登录前置不变量
                           （定位 + 澄清）：`EnableAppMock` 会 clear_data ⇒ 设备侧丢失定位/
                           弹窗同意态，漏重建则首页渲染不出「去登录」入口 ⇒ 登录导航失败。
                           守卫同时锁定 `registry.build_repair_pipeline` 的合法性，以及
                           「qahome 恢复必须经它派生步骤」（禁止手挑）。
 30. page-arrival-by-identity（硬失败）登录动作层的「到达/停留判定」函数
                           （`_wait_*` / `_on_*`）不得用控件选择器（`PageSpec.control(...)`）
                           作为判据：控件选择器可能含过宽的 `role` 兜底，会命中其它页面的
                           同角色元素（实测：登录页手机号 EditText 被当成验证码输入框）
                           → 到达判定假阳性（"空点"被误报成"发码成功"）。必须用 `identity`。
 31. no-bytecode-in-tree    （硬失败）源树内不得出现 `__pycache__` / `*.pyc`：
                           零字节码由**进程入口层**保证（workspace 入口脚本的 `python3 -B`
                           + `PYTHONDONTWRITEBYTECODE`，cli.py 与 dev 脚本的入口开关），
                           包内不得再用 rmtree 自我补偿（挡不住其它写入者，还藏住漏点）。

用法：
    python3 scripts/dev/check_architecture.py                  # 检查
    python3 scripts/dev/check_architecture.py --list-swallow   # 列出全部吞噬点
退出码：0 通过 / 1 失败。
"""
import ast
import importlib
import os
import re
import subprocess
import sys
from collections import defaultdict

# 源树零字节码：本文件是进程入口，开关必须在引擎包导入之前生效。
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_ROOT = os.path.dirname(SCRIPTS_DIR)
# 向上探测到的候选起点；真正的 git 仓库根由 git rev-parse 确定，
# 因为 `git diff --name-only` 输出的路径是相对**仓库根**而非 cwd 的。
GIT_CWD = os.path.dirname(SKILL_ROOT)

# ── 规则 1：允许调用 sys.exit 的模块（仅 CLI 边界）────────────────────
SYS_EXIT_ALLOWLIST = {
    "cli_utils.py",  # 唯一错误边界：把异常 / 返回码转成进程退出码
}

# ── 规则 2：允许 `except: pass` 的模块（有意自保护 / 解析兜底）────────
# 白名单是**门禁**：白名单外出现任何 `except ...: pass` 即失败；新增须逐条定性并在此登记理由。
SWALLOW_ALLOWLIST = {
    "shared/errors.py",                                  # soft_fail 自身：审计失败不得反向炸主流程
    "cli_utils.py",                                    # 错误边界自保护：落盘 / 上报失败不得反向抛出
    "shared/context.py",                             # 平台解析失败时静默跳过（与 ImportError 兜底等价）
    "shared/observability/runtime_audit.py",                     # 审计失败不得反向炸主流程
    "shared/observability/usage_reporter.py",                    # 上报 fire-and-forget
    "shared/observability/exception_reporter.py",                # 上报 fire-and-forget
    "shared/json_utils.py",                         # 读文件失败返回默认值（类型化 API）
    "shared/paths.py",                              # 清理目录 best-effort
    "execution/engine/flow/step_scheduler.py",                     # steps.jsonl 读取容错
    "execution/engine/flow/flow_init.py",                          # 归档清理 best-effort
    "execution/engine/flow/steps_generator.py",                    # 目录创建容错
    "execution/assertions/data/track.py",                        # JSON 解析失败保留原值（数据断言容错）
    "execution/assertions/data/api.py",                          # 同上
    "devices/android/ops.py",                  # 可选平台钩子探测（ImportError）
    "devices/android/probes/webview.py",       # CDP 链路多级降级 + JSON 容错
    "devices/harmony/ops.py",                  # JSON 容错
    "devices/harmony/probes/inspect_tree.py",  # 设备临时目录清理
    "platform/ssl_helper.py",                             # SSL 上下文降级
    "provisioning/prereq/node_env.py",                               # 环境探测兜底
    "provisioning/prereq/check_deps.py",                             # 依赖探测多路径尝试
    "platform/auth.py",                           # 缓存 / 降级路径
    "devices/toolchain/app_installer.py",                          # 安装探测多路径尝试
    "reporting/data_collector.py",                        # 报告层 I/O：文件缺失/不可读即降级并留痕
    "devices/ios/ops.py",                      # iOS 骨架：WDA / imeituan 双路径降级
    "cli.py",                                  # CLI 边界：控制台横幅 / token 自保护（不得影响命令主流程）
    "resources/mis_pool/commands.py",          # 虚拟 mis 归还 / 状态查询 best-effort（不影响收尾）
    "provisioning/questions/schema.py",        # 问题目录解析容错：非法项跳过，不中断信息收集
    "shared/records.py",                       # 记录 / 帧 IO 容错（缺文件即跳过）
    "devices/capabilities.py",                 # 设备能力探测 best-effort
    "console/server.py",                       # HTTP 层：客户端断连静音 + 后台循环 best-effort + Ctrl-C
    "console/service.py",                      # 服务生命周期自保护：token 落盘 / kill / remove best-effort
    "console/discovery.py",                    # 只读发现层 IO 容错（缺文件即跳过）
    "console/telemetry.py",                    # 遥测 tee 必须零侵入（队列满 / 落盘失败不得影响主流程）
    "console/tailer.py",                       # 增量日志读取容错（文件消失 / 半行 JSON 跳过）
    "console/store.py",                        # 订阅者推送满即丢（fire-and-forget 广播）
    "console/preview/base.py",                 # 预览帧 IO 容错
    "console/preview/manager.py",              # 预览帧抓取 best-effort
    "console/preview/relay.py",                # 预览流转发 best-effort
}


# ── 规则 6：允许调用 resolve_placeholders 的模块（占位符解析唯一入口）────
# flow_init.py        流初始化边界：解析后落盘为唯一事实来源
# placeholder_resolver.py  解析器定义处（内部递归自调）
PLACEHOLDER_RESOLVE_ALLOWLIST = {
    "execution/engine/flow/flow_init.py",
    "execution/engine/placeholder/placeholder_resolver.py",
}

_TOP_PKGS = {
    "devices", "execution", "platform", "provisioning", "reporting", "shared",
}

# ── 规则 7：分层依赖方向（阶段 0 目标分层）──
LAYER_DEPS = {
    "shared":        {"shared"},
    "platform":      {"shared", "platform"},
    "devices":       {"shared", "platform", "devices"},
    "provisioning":  {"shared", "platform", "devices", "provisioning"},
    "resources":     {"shared", "platform", "devices", "provisioning", "resources"},
    "execution":     {"shared", "platform", "devices", "execution"},
    "reporting":     {"shared", "platform", "execution", "reporting"},
    "orchestration": {"shared", "platform", "devices", "provisioning",
                      "resources", "execution", "reporting", "orchestration"},
}

# 规则 7 棘轮基线：只允许下降
LAYER_COUPLING_BASELINE = 53

# ── 规则 8：禁止「设备销毁」能力回归（T2 决策：复用优先、不销毁实例）────
DESTROY_FORBIDDEN_TOKENS = ("sandbox/destroy", "cleanup_user_devices")
DEVICE_LIFECYCLE_ABC = "devices/interfaces/lifecycle.py"
DESTROY_FORBIDDEN_METHODS = {"release", "cleanup_user_devices"}

# ── 规则 9：硬禁止的反向依赖边（规则 7 只计数；这些直接失败）────────
FORBIDDEN_EDGES = {("devices", "resources")}

# ── 规则 14/15：登录流程重构约束（重启点不减 / 登录层禁平台分支）──
LOGIN_LAYER_DIR = "provisioning/setup/login"
# 平台/设备类型分支必须走 PlatformOps 或策略注册表，不得写在登录业务层
LOGIN_PLATFORM_BRANCH_RE = re.compile(
    r"\bif\s+(?:[A-Za-z_][\w\.]*\.)?(?:platform|device_type)\s*==")
# 重启原语：只能出现在「已声明 RestartPolicy 的前置步骤」里
RESTART_PRIMITIVES = ("_cold_restart_app(", "restart_app_after_env_switch(")
LOGIN_STEPS_FILE = "provisioning/setup/login/steps.py"
# 冻结项 F-2（重启点一个不减）：steps.py 的重启调用点数基线，只许不少于此值
RESTART_SITE_BASELINE_LOGIN_STEPS = 7


def check_login_android_probe_frozen():
    """规则 16：Android 登录态探针必须保持「前台判定」语义。

    探针契约（按平台注册）：
      · 前台判定型（android/ios）：`probes/android.py` 提供前台判定（平台无关原语），`ForegroundProbe` 调用它，
        且 `authoritative_for_password=False`（凭证登录由读图确认兜底）
      · Harmony：`HarmonyMpiumProbe` 走 `imeituan control auth status`
    误改会让 Android 的登录成功判定换成另一套语义，改变既有行为。
    """
    bad = []
    init_rel = f"{LOGIN_LAYER_DIR}/probes/__init__.py"
    android_rel = f"{LOGIN_LAYER_DIR}/probes/android.py"
    init_text = _read_text(os.path.join(SCRIPTS_DIR, init_rel))
    android_text = _read_text(os.path.join(SCRIPTS_DIR, android_rel))

    if "def check_login_state(" not in android_text:
        bad.append(f"{android_rel} 缺少 check_login_state（前台判定实现）")
    if "authoritative_for_password = False" not in init_text:
        bad.append(f"{init_rel} 的 Android 探针必须声明 authoritative_for_password = False")
    if "check_login_state" not in init_text:
        bad.append(f"{init_rel} 的 Android 探针未调用 check_login_state")
    # Android 探针**类体**内不得使用真登录态通道（限定范围，避免误判模块 docstring）
    if "class ForegroundProbe" in init_text and "class HarmonyMpiumProbe" in init_text:
        android_body = init_text.split("class ForegroundProbe", 1)[1].split(
            "class HarmonyMpiumProbe", 1)[0]
        if "auth status" in android_body or "imeituan_exec" in android_body:
            bad.append(f"{init_rel} 的 Android 探针类不得使用真登录态通道（auth status）")
    return bad


POPUP_EXECUTOR_REL = "devices/popup.py"
CACHE_ENTRY_REL = "shared/artifact_cache.py"


def check_popup_single_implementation():
    """规则 17：弹窗消除只有一条路径（`devices/popup.py` 的单一执行器）。

    检测形态：**可执行代码**里出现 CLI 形式的弹窗消除 argv（字符串列表，或
    字符串实参）——即 `control popup clear` 这条路。它鸿蒙明确不支持，且在
    Android 上就是同一套 dump+tap 的等价物，保留两套只会让返回语义 / 日志 /
    失败处理分叉（词表在 `platform/popup/patterns.py`，执行只在 `devices/popup.py`）。

    只查可执行代码：注释与文档字符串里的说明性引用不算违规（约定本身需要被写下来）。
    """
    bad = []
    for path in _iter_py_files():
        rel = _rel(path)
        if rel == POPUP_EXECUTOR_REL:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.List) and node.elts and all(
                    isinstance(e, ast.Constant) and isinstance(e.value, str)
                    for e in node.elts):
                argv = " ".join(e.value for e in node.elts)
            elif isinstance(node, ast.Call):
                argv = " ".join(
                    a.value for a in node.args
                    if isinstance(a, ast.Constant) and isinstance(a.value, str))
            else:
                continue
            low = argv.lower()
            if "popup" in low and ("clear" in low or "prevent" in low):
                bad.append(
                    f"{rel}:{node.lineno} 出现 CLI 弹窗消除调用"
                    f"（应走 {POPUP_EXECUTOR_REL} 的执行器）")
    return bad


def check_login_restart_reason_required():
    """规则 18：非 `NONE` 的重启声明必须同时给出 `restart_reason`。

    `ProvisionStep.restart_reason` 的契约是"声明了重启就必须说明为什么"（读者不必
    去翻实现才知道重启的不可替代性），而数据类型上的默认空串没有任何强制力，
    所以在这里静态守住：遍历 `login/steps.py` 里的 `ProvisionStep(...)` 调用，
    `restart=` 不是 `RestartPolicy.NONE` 时必须有非空字符串 `restart_reason`。
    """
    bad = []
    tree = _parse(os.path.join(SCRIPTS_DIR, LOGIN_STEPS_FILE))
    if tree is None:
        return [f"{LOGIN_STEPS_FILE} 解析失败（无法校验 restart_reason）"]
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "ProvisionStep"):
            continue
        keywords = {k.arg: k.value for k in node.keywords if k.arg}
        restart = keywords.get("restart")
        if restart is None:
            continue
        if isinstance(restart, ast.Attribute) and restart.attr == "NONE":
            continue
        reason = keywords.get("restart_reason")
        has_reason = (isinstance(reason, ast.Constant) and isinstance(reason.value, str)
                      and reason.value.strip())
        if not has_reason:
            bad.append(
                f"{LOGIN_STEPS_FILE}:{node.lineno} restart 非 NONE 但缺 restart_reason")
    return bad


def check_artifact_cache_single_entry():
    """规则 19：L1 制品缓存只能经 `shared/artifact_cache.py` 访问。

    为什么固化：`.cache` 是**跨 run / 跨子 Agent 共享且引擎永不自动清理**的目录
    （分层模型见该模块 docstring）。一旦别处自己拼 `.cache/...` 路径或自己下载，
    就会出现两类回退——① “各写一份缓存”，并行 run 重复拉同一大包；② 清理逻辑
    误删共享制品，让正在跑的 run 丢缓存。故：除该模块外，代码里不得出现 `.cache`
    字面量（注释里加也是信号：说明这段逻辑“想自己碰缓存”）。
    """
    bad = []
    for path in _iter_py_files():
        rel = _rel(path)
        if rel == CACHE_ENTRY_REL:
            continue
        for i, line in enumerate(_read_text(path).splitlines(), 1):
            if ".cache" in line:
                bad.append(
                    f"{rel}:{i} 直接引用 .cache（应经 {CACHE_ENTRY_REL}）: "
                    f"{line.strip()[:80]}")
    return bad


def check_login_layer_platform_branch_free():
    """规则 14：登录层不得出现平台/设备类型分支。

    平台差异必须通过 `PlatformOps`（原子能力）或策略注册表（同一能力多实现）
    表达；在业务层写 `if platform == ...` 会让新增平台时改动散落到多处，
    正是登录流程重构要消除的问题。
    """
    bad = []
    for path in _iter_py_files():
        rel = _rel(path)
        if not rel.startswith(LOGIN_LAYER_DIR + "/"):
            continue
        for i, line in enumerate(_read_text(path).splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            if LOGIN_PLATFORM_BRANCH_RE.search(line):
                bad.append(f"平台分支: {rel}:{i}  {line.strip()[:90]}")
    return bad


def check_login_restart_declared():
    """规则 15：登录层重启必须声明，且重启点数量不得减少。

    (a) `login/actions/**`（认证动作）与 `login/probes/**`（登录态探针）不得调用重启原语
        —— 对齐冻结清单：认证动作下发后不重启；探针只读。
    (b) `login/steps.py` 的重启调用点数不得少于基线
        —— F-2「重启点一个不减」：允许重命名/重构，不允许删点。
    """
    bad = []
    steps_sites = 0
    for path in _iter_py_files():
        rel = _rel(path)
        if not rel.startswith(LOGIN_LAYER_DIR + "/"):
            continue
        count = sum(_read_text(path).count(p) for p in RESTART_PRIMITIVES)
        if not count:
            continue
        if (rel.startswith(LOGIN_LAYER_DIR + "/actions/")
                or rel.startswith(LOGIN_LAYER_DIR + "/probes/")):
            bad.append(f"认证动作/探针中不得重启: {rel}（{count} 处）")
        if rel == LOGIN_STEPS_FILE:
            steps_sites = count
    if steps_sites < RESTART_SITE_BASELINE_LOGIN_STEPS:
        bad.append(
            f"登录前置步骤重启点减少: {steps_sites} < 基线 "
            f"{RESTART_SITE_BASELINE_LOGIN_STEPS}"
            "（F-2：重启点一个不减 —— 评审冻结项）"
        )
    return bad

# ── 规则 10：设备池租约访问单一入口（防绕过 LeaseStore 直接读写租约文件）──
LEASE_PATH_FN = "device_pool_leases_path"
LEASE_PATH_ALLOWLIST = {"resources/device_pool/lease_store.py"}


def _iter_py_files():
    for root, dirs, files in os.walk(SCRIPTS_DIR):
        if "__pycache__" in root:
            continue
        rel_root = os.path.relpath(root, SCRIPTS_DIR).replace(os.sep, "/")
        if rel_root == "dev" or rel_root.startswith("dev/"):
            continue
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


def _rel(path):
    return os.path.relpath(path, SCRIPTS_DIR).replace(os.sep, "/")


def _parse(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return ast.parse(fh.read())
    except (OSError, SyntaxError):
        return None


def check_no_sys_exit():
    """规则 1：非边界模块不得调用 sys.exit(...)。"""
    bad = []
    for path in _iter_py_files():
        tree = _parse(path)
        if tree is None:
            continue
        rel = _rel(path)
        if rel in SYS_EXIT_ALLOWLIST:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "exit"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "sys"):
                bad.append(f"{rel}:{node.lineno}")
    return bad


def _import_bound_names(node):
    """遍历 Import / ImportFrom 节点，返回其绑定的名字列表。"""
    names = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            names.append(alias.asname or alias.name.split(".")[0])
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            if alias.name == "*":
                continue
            names.append(alias.asname or alias.name)
    return names


def _module_level_bindings(tree):
    """模块级绑定的名字集合（import / 赋值 / 函数 / 类定义）。"""
    names = set()
    for node in tree.body:
        names.update(_import_bound_names(node))
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def check_no_local_import_shadowing():
    """规则 25：函数内 import 不得与模块级绑定同名。

    同名会让该名字在整个函数内变成**局部变量**：若该 import 处于条件分支
    （可能不执行），后续对该名字的使用（如 `raise DeviceError(...)`）会抛
    `UnboundLocalError`，把真实错误掩盖成脚本缺陷。唯一正确做法是删掉函数内
    的重复 import，直接用模块级绑定。
    """
    bad = []
    for path in _iter_py_files():
        tree = _parse(path)
        if tree is None:
            continue
        rel = _rel(path)
        module_names = _module_level_bindings(tree)
        if not module_names:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for sub in ast.walk(node):
                if not isinstance(sub, (ast.Import, ast.ImportFrom)):
                    continue
                for name in _import_bound_names(sub):
                    if name in module_names:
                        bad.append(
                            f"{rel}:{sub.lineno} 函数 {node.name}() 内 import `{name}` "
                            f"与模块级绑定同名（会变成局部变量 → UnboundLocalError）")
    return sorted(set(bad))


# ── 规则 26：PageSpec 已移除字段不得再被访问（跨文件属性访问守卫）──
# PageSpec 是"纯数据契约"，字段演进时（如 `entries` → `routes`）若忘记同步消费者，
# 静态导入/编译都不会报错，只在**运行期**抛 AttributeError（实测踩过：PageSpec 移除
# entries 后 qahome.py 仍 `page.entries`、且调用点已改而定义未加）。本规则把"已移除的旧
# 字段名"固化为黑名单：任何模块出现 `X.<旧字段>` 的属性访问即失败，迫使消费者同步迁移。
PAGESPEC_LEGACY_FIELDS = {"entries"}


def check_no_pagespec_legacy_fields():
    """规则 26：不得再访问 `PageSpec` 已移除的字段（如 `entries`）。

    现役字段从 `devices/interfaces/page_spec.py::PageSpec.__slots__` 读取，与黑名单
    求交应为空（防止"黑名单字段又被加回 __slots__"的自相矛盾）。
    """
    bad = []
    page_spec_path = os.path.join(SCRIPTS_DIR, "devices", "interfaces", "page_spec.py")
    tree = _parse(page_spec_path)
    slots = set()
    if tree is not None:
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ClassDef) and node.name == "PageSpec"):
                continue
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                if not any(isinstance(t, ast.Name) and t.id == "__slots__"
                           for t in stmt.targets):
                    continue
                if isinstance(stmt.value, (ast.Tuple, ast.List)):
                    slots = {e.value for e in stmt.value.elts if isinstance(e, ast.Constant)}
    overlap = PAGESPEC_LEGACY_FIELDS & slots
    if overlap:
        bad.append(
            f"page_spec.py PageSpec.__slots__ 重新包含了已移除字段 {sorted(overlap)}"
            "（应同步更新规则 26 黑名单）")
    for path in _iter_py_files():
        t = _parse(path)
        if t is None:
            continue
        rel = _rel(path)
        if rel == "devices/interfaces/page_spec.py":
            continue
        for node in ast.walk(t):
            if isinstance(node, ast.Attribute) and node.attr in PAGESPEC_LEGACY_FIELDS:
                bad.append(
                    f"{rel}:{node.lineno} 访问了 PageSpec 已移除字段 `.{node.attr}`"
                    "（字段已改为 routes，请同步消费者）")
    return sorted(set(bad))


# ── 规则 27：platform 参数不得有默认值（防"漏传即隐式平台"）──
IMPLICIT_PLATFORM_DEFAULT_FILES = {"shared/context.py"}
IMPLICIT_PLATFORM_DEFAULT_DIRS = ("devices/lifecycle/",)


def check_no_implicit_platform_default():
    """规则 27：`platform` 参数不得设默认值（devices/lifecycle/ 与 shared/context.py）。

    隐式平台默认值会让"漏传/漏配置"静默按某个平台处理（实测：
    `create_device_lifecycle(device_type)` 用默认 android 处理鸿蒙云模拟器）。
    """
    bad = []
    for path in _iter_py_files():
        rel = _rel(path)
        if not (rel in IMPLICIT_PLATFORM_DEFAULT_FILES
                or any(rel.startswith(d) for d in IMPLICIT_PLATFORM_DEFAULT_DIRS)):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            pos = node.args.args
            n_defaults = len(node.args.defaults)
            for i, a in enumerate(pos):
                if a.arg == "platform" and i >= len(pos) - n_defaults:
                    bad.append(f"{rel}:{node.lineno} {node.name}() 的 platform 参数不得有默认值")
            for a, d in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if a.arg == "platform" and d is not None:
                    bad.append(f"{rel}:{node.lineno} {node.name}() 的 platform 参数不得有默认值")
    return sorted(set(bad))


# ── 规则 28：白名单平台必须已注册登录态探针（防"新平台静默借用他平台语义"）──
def check_platform_login_probe_registered():
    """规则 28：`SUPPORTED_DEVICE_COMBINATIONS` 里的 platform 必须在 `LOGIN_STATE_PROBES` 登记。"""
    bad = []
    dv = _parse(os.path.join(SCRIPTS_DIR, "provisioning", "validators", "device_validator.py"))
    platforms = set()
    if dv is not None:
        for node in ast.walk(dv):
            if not (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "SUPPORTED_DEVICE_COMBINATIONS"
                            for t in node.targets)):
                continue
            for elt in getattr(node.value, "elts", []):
                if not isinstance(elt, ast.Dict):
                    continue
                for k, v in zip(elt.keys, elt.values):
                    if (isinstance(k, ast.Constant) and k.value == "platform"
                            and isinstance(v, ast.Constant)):
                        platforms.add(v.value)
    probes = _parse(os.path.join(
        SCRIPTS_DIR, "provisioning", "setup", "login", "probes", "__init__.py"))
    registered = set()
    if probes is not None:
        for node in ast.walk(probes):
            if not (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                    and node.target.id == "LOGIN_STATE_PROBES"):
                continue
            for k in getattr(node.value, "keys", []):
                if isinstance(k, ast.Constant):
                    registered.add(k.value)
    for pf in sorted(platforms - registered):
        bad.append(
            f"platform={pf} 在 SUPPORTED_DEVICE_COMBINATIONS 中但未在 LOGIN_STATE_PROBES 登记"
            "（登录态判定会静默回落到前台探针，语义可能与平台不符）")
    return bad


def _is_bare_pass(body):
    """body 是否为单个 `pass`。"""
    return len(body) == 1 and isinstance(body[0], ast.Pass)


def find_silent_swallows():
    """返回 [(rel, lineno)]，标记所有 `except ...: pass`。"""
    found = []
    for path in _iter_py_files():
        tree = _parse(path)
        if tree is None:
            continue
        rel = _rel(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _is_bare_pass(node.body):
                found.append((rel, node.lineno))
    return found


def check_layering():
    """规则 3：跨包模块级 import 环（SCC）必须为 0。"""
    mods = {}
    for path in _iter_py_files():
        key = _rel(path)[:-3].replace("/", ".")
        mods[key] = path
        if key.endswith(".__init__"):
            mods[key[: -len(".__init__")]] = path

    def resolve(name):
        if not name:
            return None
        if name in mods:
            return name
        parts = name.split(".")
        for i in range(len(parts), 0, -1):
            cand = ".".join(parts[:i])
            if cand in mods:
                return cand
        return None

    graph = defaultdict(set)
    for mod, path in mods.items():
        tree = _parse(path)
        if tree is None:
            continue
        # 仅统计模块级（顶层）import：函数内延迟 import 是打破环的标准手段。
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                t = resolve(node.module)
                if t and t != mod:
                    graph[mod].add(t)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    t = resolve(a.name)
                    if t and t != mod:
                        graph[mod].add(t)

    index, low, on, stack, comps = {}, {}, {}, [], []

    def strongconnect(v):
        index[v] = low[v] = len(index)
        stack.append(v)
        on[v] = True
        for w in graph.get(v, ()):
            if w not in index:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif on.get(w):
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on[w] = False
                comp.append(w)
                if w == v:
                    break
            comps.append(comp)

    sys.setrecursionlimit(20000)
    for v in list(mods):
        if v not in index:
            strongconnect(v)

    def pkg(m):
        return m.split(".")[0]

    return [c for c in comps
            if len(c) > 1 and len({pkg(x) for x in c}) > 1]


def check_no_bytecode_in_source_tree():
    """规则31：源树内零字节码（`__pycache__` / `*.pyc`）。

    零字节码必须由进程入口层保证：入口脚本 `python3 -B` + `PYTHONDONTWRITEBYTECODE`（子进程
    靠环境变量继承），cli.py 与 dev 脚本各自在引擎包导入前打开开关。包内不再用"打开开关后
    rmtree 自己那份"的方式补偿——它挡不住本进程以外的写入者，也会把"谁在漏写"藏起来。
    因此源树里出现字节码 ⇒ 只可能是某个入口漏了开关。
    """
    bad = []
    for root, dirs, files in os.walk(SKILL_ROOT):
        if ".git" in root.split(os.sep) or "node_modules" in root.split(os.sep):
            dirs[:] = []
            continue
        for name in dirs:
            if name == "__pycache__":
                bad.append(os.path.relpath(os.path.join(root, name), SKILL_ROOT) + "/")
        for name in files:
            if name.endswith((".pyc", ".pyo")):
                bad.append(os.path.relpath(os.path.join(root, name), SKILL_ROOT))
    return sorted(bad)


def check_all_modules_importable():
    """规则4：逐个 import 所有模块，返回失败列表。

    只看 `import cli` 或 `compileall` 发现不了「漏再导出 / 破损导入」：
    例如 facade 漏再导出某个仍被外部引用的私有符号，会导致数十个模块 ImportError，
    而入口模块可能仍能导入（只在实际调用时才崩）。逐模块导入才能暴露。
    """
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    bad = []
    for path in _iter_py_files():
        mod = _rel(path)[:-3].replace("/", ".")
        if mod.endswith(".__init__"):
            mod = mod[: -len(".__init__")]
        try:
            importlib.import_module(mod)
        except Exception as exc:  # noqa: BLE001 — 导入失败一律报出（附类型与摘要）
            bad.append(f"{mod} -> {type(exc).__name__}: {str(exc)[:100]}")
    return bad


def _git_repo_root():
    """返回 git 仓库根绝对路径；非 git 仓库返回 None。"""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=GIT_CWD, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def check_staged_deletions_not_referenced():
    """规则5：git 暂存区里被删除的模块，不得仍被任何模块引用。

    固化「删除旧模块必须放在所有引用方改完之后」这条纪律——否则会留下
    ImportError 破损态（曾因先删 login_primitives.py 导致 cli 起不来）。
    非 git 仓库 / 无暂存改动时静默跳过。
    """
    repo_root = _git_repo_root()
    if not repo_root:
        return []
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--diff-filter=D", "--name-only"],
            cwd=repo_root, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []

    # git 输出的路径相对仓库根；换算成本仓库内的 scripts/ 相对路径前缀
    prefix = os.path.relpath(SCRIPTS_DIR, repo_root).replace(os.sep, "/") + "/"
    bad = []
    for line in proc.stdout.splitlines():
        staged = line.strip()
        if not staged.endswith(".py") or not staged.startswith(prefix):
            continue
        rel_deleted = staged[len(prefix):]
        mod = rel_deleted[:-3].replace("/", ".")
        if mod.endswith(".__init__"):
            mod = mod[: -len(".__init__")]
        for path in _iter_py_files():
            if _rel(path) == rel_deleted:
                continue
            tree = _parse(path)
            if tree is None:
                continue
            # 精确判定：只认真正的 import 语句引用（含函数内延迟 import）。
            hit = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    m = node.module or ""
                    if m == mod or m.startswith(mod + "."):
                        hit = True
                elif isinstance(node, ast.Import):
                    for a in node.names:
                        if a.name == mod or a.name.startswith(mod + "."):
                            hit = True
            if hit:
                bad.append(f"{mod} 已 staged 删除，但仍被 {_rel(path)} 引用")
    return bad


def check_placeholder_resolve_single_entry():
    """规则6：resolve_placeholders 只允许在 flow_init.py 调用。

    steps-input 被 flow-init 解析后落盘为唯一事实来源（原文档另存 raw），
    运行期读者（case-init / 报告等）只读解析后的产物。此规则固化
    「解析收敛在边界」这条纪律，防止读者各自解析 / 漏解析而复发回归。
    """
    bad = []
    for path in _iter_py_files():
        if _rel(path) in PLACEHOLDER_RESOLVE_ALLOWLIST:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "resolve_placeholders"):
                bad.append(f"{_rel(path)}:{node.lineno}")
    return bad


def check_layer_direction():
    """规则 7（棘轮）：跳层 import 方向违规（如 shared 反向依赖 execution）。"""
    warnings = []
    for path in _iter_py_files():
        rel = _rel(path)
        if "/" not in rel:
            continue
        layer = rel.split("/", 1)[0]
        allowed = LAYER_DEPS.get(layer)
        if not allowed:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            elif isinstance(node, ast.Import):
                names.extend(a.name for a in node.names)
            for nm in names:
                dep = nm.split(".")[0]
                if dep in LAYER_DEPS and dep not in allowed:
                    warnings.append(f"{layer} -> {dep}  ({nm})  {rel}:{node.lineno}")
    return warnings


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def check_no_device_destroy():
    """规则 8：不得重新引入设备销毁能力（端点 / 标识符 / 契约方法）。

    T2 决定设备复用优先、不销毁实例（`cleanup_user_devices` 等销毁能力均已删除）。
    任何人重新引入销毁端点 / 标识符，或给 DeviceLifecycle 加回 release/cleanup，
    都视为回退。
    """
    bad = []
    for path in _iter_py_files():
        rel = _rel(path)
        text = _read_text(path)
        for token in DESTROY_FORBIDDEN_TOKENS:
            if token in text:
                bad.append(f"{rel}: 出现禁用符号 {token!r}（不销毁实例）")
        if rel != DEVICE_LIFECYCLE_ABC:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            methods = {n.name for n in node.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for name in sorted(DESTROY_FORBIDDEN_METHODS & methods):
                bad.append(f"{rel}:{node.lineno} DeviceLifecycle 不得定义 {name}()（不提供销毁能力）")
    return bad


def check_forbidden_edges():
    """规则 9：硬禁止的反向依赖边（不受规则 7 棘轮保护）。

    `resources` 只可单向依赖 `devices`；反向 import 直接失败——否则会把池化内核
    重新拖回 devices 层（T2 §六 的迁移就会被悄悄推翻）。
    """
    bad = []
    for path in _iter_py_files():
        rel = _rel(path)
        if "/" not in rel:
            continue
        layer = rel.split("/", 1)[0]
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            elif isinstance(node, ast.Import):
                names.extend(a.name for a in node.names)
            for nm in names:
                dep = nm.split(".")[0]
                if (layer, dep) in FORBIDDEN_EDGES:
                    bad.append(f"{layer} -> {dep}  ({nm})  {rel}:{node.lineno}")
    return bad


def check_lease_path_single_entry():
    """规则 10：`device_pool_leases_path` 只允许在租约存储后端调用。

    绕过 LeaseStore 直读/直写租约文件会破坏 flock 串行化与原子写，
    使并发选机重新变得不安全。固定「租约只能经存储后端访问」这条纪律。
    """
    bad = []
    for path in _iter_py_files():
        rel = _rel(path)
        if rel in LEASE_PATH_ALLOWLIST:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == LEASE_PATH_FN):
                bad.append(f"{rel}:{node.lineno}")
    return bad


# ═══════════════════════════════════════════════════════════════════
# 规则 11：AppMock 代理契约（离线，不打真实网络）
# ═══════════════════════════════════════════════════════════════════

# 这些函数的「工作域」必须显式传入，否则多 shard 并行会互相踩到操作者的泳道 / 规则 / 映射。
APPMOCK_DOMAIN_SCOPED_FNS = {
    "appmock_on", "appmock_off", "appmock_get", "appmock_list",
    "appmock_stop_all", "appmock_patch_field", "appmock_create",
    "appmock_swimline_list", "appmock_swimline_add", "appmock_swimline_switch",
    "appmock_swimline_off", "appmock_swimline_remove",
    "url_mapping_list", "url_mapping_add", "url_mapping_update",
    "url_mapping_upsert", "url_mapping_set_env", "url_mapping_delete", "url_mapping_find",
    "appmock_ensure_url_mappings", "appmock_cleanup_url_mappings", "appmock_env_set",
}

_APPMOCK_CLI_FILES = ("platform/appmock/cli.py", "platform/appmock/env_cli.py")


def check_appmock_domain_threading():
    """规则 11a：AppMock CLI 边界必须显式传 mis（多 shard 隔离）。

    历史上非域感知的调用会让并行 shard 操作到「操作者本人」的泳道 / 规则 / 映射。
    要求 CLI 边界对域相关能力一律带 `mis=`；域无关的（如按 mockId 的 update）不在列。
    """
    bad = []
    for rel in _APPMOCK_CLI_FILES:
        tree = _parse(os.path.join(SCRIPTS_DIR, rel))
        if tree is None:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in APPMOCK_DOMAIN_SCOPED_FNS):
                if "mis" not in {kw.arg for kw in node.keywords}:
                    bad.append(f"{rel}:{node.lineno} {node.func.id}() 未显式传 mis")
    return bad


# AppMock 侧（平台接口 + 设备端 + 录制断言）—— 必须以 mock_domain 为工作域
_APPMOCK_IDENTITY_FILES = (
    "platform/appmock/record.py",
    "platform/appmock/client.py",
    "platform/appmock/rules.py",
    "platform/appmock/session.py",
    "platform/appmock/swimlane.py",
    "platform/appmock/device.py",
    "platform/appmock/cli.py",
    "platform/appmock/env_cli.py",
    "provisioning/setup/env_prepare.py",
    "provisioning/setup/login/orchestrator.py",
    "provisioning/setup/login/steps.py",
    "provisioning/setup/login/actions/password.py",
    "execution/steps/api.py",
    "execution/steps/track.py",
    "execution/engine/flow/lifecycle/mock_lifecycle.py",
    "execution/steps/recording/assert_fields_cmd.py",
)


def check_appmock_mock_domain_isolation():
    """规则 11c：AppMock 侧必须用 `mock_domain`，禁用 `resource_mis`。

    AppMock 能力（平台接口 / 设备端 / 录制断言）一律以 **虚拟 mis（mock_domain）**
    为工作域；出现 `resolve_mis()` / `set_current_user_mis()`（resource_mis）即为
    “资源 mis 与工作域串味”回归 —— 破坏多 Agent 并发隔离。
    """
    bad = []
    for rel in _APPMOCK_IDENTITY_FILES:
        tree = _parse(os.path.join(SCRIPTS_DIR, rel))
        if tree is None:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("resolve_mis", "set_current_user_mis")):
                bad.append(
                    f"{rel}:{node.lineno} 使用了 {node.func.id}()"
                    "（AppMock 侧应使用 resolve_mock_domain / set_mock_domain）"
                )
    return bad


def check_appmock_contract():
    """规则 11b：AppMock 代理信封 / id / 请求形状契约（离线，stub 掉网络）。

    固化本轮修复的易回退口径：
      - unwrap_proxy_response 信封解析（内层 code 必须为 0；非 dict / 外层非 0 判失败）
      - extract_mock_id 不得把 None / '' 变成 'None'
      - url_mapping_* / session_swimline_* 请求必须带 userDomain、不夹带上游不支持的 title
      - appmock_list 从 yooz 归一化后的 {items:[...]} 取规则
      - appmock_create 透传 exampleUrl / paramRule
      - ensure 对不存在的映射 = add + updateUrlEnv 激活
    """
    bad = []
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    import contextlib
    import io
    import json as _json

    try:
        import requests as _requests
        from platform.appmock import client as _client
        from platform.appmock import rules as _rules
        from platform.appmock import session as _sess
        from platform.appmock import swimlane as _sw
    except Exception as e:
        return [f"AppMock 模块导入失败：{e}"]

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        # ── 1) 信封解析 ──
        unwrap = _client.unwrap_proxy_response
        for payload, want in [
            ({"code": 0, "data": {"code": 0, "data": {"mockId": 1}}}, True),
            ({"code": 0, "data": {"mockId": 1}}, True),               # 无内层信封
            ({"code": 0, "data": {"code": 1, "data": {}}}, False),    # 内层 code=1（yooz 必须归一化）
            ({"code": 500, "data": {}}, False),
            ({"code": 0, "data": [1, 2]}, False),                      # data 非 dict
        ]:
            got, _, _ = unwrap(payload)
            if got != want:
                bad.append(f"unwrap_proxy_response({_json.dumps(payload, ensure_ascii=False)})"
                           f" -> {got}，期望 {want}")

        # ── 2) mockId 提取 ──
        for payload, want in [
            ({"mockId": 1}, "1"),
            ({"id": 2}, "2"),
            ({"ruleId": 3}, "3"),
            ({"data": {"data": {"mockId": {"mockId": 4}}}}, "4"),
            ({"mockId": None}, ""),
            ({"mockId": ""}, ""),
            ({}, ""),
        ]:
            got = _rules.extract_mock_id(payload)
            if got != want:
                bad.append(f"extract_mock_id({payload}) -> {got!r}，期望 {want!r}")

        # ── 3) 请求形状（stub _proxy_call）──
        calls = []

        def _fake_proxy(method, path, *, params=None, json_body=None, timeout=15):
            calls.append((method, path, params or {}, json_body or {}))
            if path == "/url-mapping/list":
                return {"mappings": []}
            if path == "/url-mapping/add":
                return {"id": 99}
            if path == "/swimline/list":
                return {"items": [{"id": 1, "configs": "lane"}]}
            return {}

        orig_proxy = _sess._proxy_call
        _sess._proxy_call = _fake_proxy
        try:
            _sess.url_mapping_list("D")
            _sess.url_mapping_add("u", mis="D", beta_url="b")
            _sess.url_mapping_update(5, "u", mis="D", beta_url="b")
            _sess.url_mapping_set_env(5, "beta", mis="D")
            _sess.url_mapping_delete(5, mis="D")
            _sess.url_mapping_upsert("u", mis="D", beta_url="b")
            _sess.session_swimline_list("D")
            _sess.session_swimline_add("/x", "lane", "D")
            _sess.session_swimline_switch(1, mis="D", user_config="lane")
            _sess.session_swimline_off(1, mis="D")
            _sess.session_swimline_remove(1, mis="D")
        finally:
            _sess._proxy_call = orig_proxy

        for method, path, params, body in calls:
            if {**params, **body}.get("userDomain") != "D":
                bad.append(f"{method} {path} 未携带 userDomain=D")
            if "title" in body:
                bad.append(f"{method} {path} 夹带了上游不支持的 title")

        # ── 4/5) list 形状 与 create 透传（stub requests.post）──
        class _Resp:
            def __init__(self, payload):
                self._p = payload

            def json(self):
                return self._p

        orig_post = _requests.post
        try:
            _requests.post = lambda url, **kw: _Resp(
                {"code": 0, "data": {"code": 0, "data": {"items": [{"id": 1, "rule": "/r$"}]}}})
            items = _rules.appmock_list("D")
            if not (isinstance(items, list) and items and items[0].get("rule") == "/r$"):
                bad.append(f"appmock_list 未从 {{items:[...]}} 解析出规则：{items!r}")

            captured = {}

            def _capt(url, data=None, json=None, **kw):
                captured.update(url=url, payload=json)
                return _Resp({"code": 0, "data": {"mockId": 1887}})

            _requests.post = _capt
            res = _rules.appmock_create(rule="/.*?$", response_body="{}", mis="D",
                                        desc="d", example_url="/x.bin", param_rule="p")
            if (captured.get("payload") or {}).get("exampleUrl") != "/x.bin":
                bad.append("appmock_create 未透传 exampleUrl")
            if (captured.get("payload") or {}).get("paramRule") != "p":
                bad.append("appmock_create 未透传 paramRule")
            if res.get("mockId") != "1887":
                bad.append(f"appmock_create 返回值异常：{res!r}")
        finally:
            _requests.post = orig_post

        # ── 6) ensure = add + updateUrlEnv 激活（stub _proxy_call + 落盘）──
        calls2 = []

        def _fake_proxy2(method, path, *, params=None, json_body=None, timeout=15):
            calls2.append((method, path, params or {}, json_body or {}))
            if path == "/url-mapping/list":
                return {"mappings": []}
            if path == "/url-mapping/add":
                return {"id": 42}
            return {}

        orig_load, orig_save = _sw._load_auto_mapping_ids, _sw._save_auto_mapping_ids
        _sess._proxy_call = _fake_proxy2
        _sw._load_auto_mapping_ids = lambda: []
        _sw._save_auto_mapping_ids = lambda ids: None
        try:
            ensured = _sw.appmock_ensure_url_mappings([{"url": "u", "betaUrl": "b"}], mis="D")
        finally:
            _sess._proxy_call = orig_proxy
            _sw._load_auto_mapping_ids = orig_load
            _sw._save_auto_mapping_ids = orig_save

        paths = [p for _, p, _, _ in calls2]
        if "/url-mapping/add" not in paths:
            bad.append("ensure 对不存在的映射未调用 add")
        if "/url-mapping/set-env" not in paths:
            bad.append("ensure 未调用 updateUrlEnv 激活")
        for _, path, params, body in calls2:
            if {**params, **body}.get("userDomain") != "D":
                bad.append(f"ensure 调用 {path} 未携带 userDomain")
        if not (isinstance(ensured, list) and ensured and ensured[0].get("action") == "added"):
            bad.append(f"ensure 返回结构异常：{ensured!r}")

        # ── 7) ptest 规则：排除场景 Mock 路径 + 遮蔽判定（防 catch-all 遮蔽回归）──
        from platform.appmock import ptest as _pt
        import re as _re

        if _pt.build_ptest_rule(()) != "/.*?$":
            bad.append(f"ptest 无排除项时应全量匹配，实得 {_pt.build_ptest_rule(())!r}")
        _excluded = _pt.build_ptest_rule(["/hotelorder/trade/precreate/preview$"])
        if _excluded != "^(?!.*(?:/hotelorder/trade/precreate/preview$)).*$":
            bad.append(f"ptest 排除规则构造异常：{_excluded!r}")
        _probe = "/hotelorder/trade/precreate/preview"
        if _re.search(_excluded, _probe) is not None:
            bad.append("ptest 排除规则仍命中被排除的场景 Mock 路径（遮蔽未消除）")
        if _re.search(_excluded, "/mapi/other.bin") is None:
            bad.append("ptest 排除规则应仍命中未排除路径")
        if _re.search(_excluded, _pt._PTEST_EXAMPLE_URL) is None:
            bad.append("ptest example URL 不得落在排除集内（否则平台正则校验不命中）")
        if _pt.build_ptest_desc([]) != _pt.build_ptest_desc(()):
            bad.append("ptest desc 对空排除集应稳定")
        if _pt.build_ptest_desc(["/a$"]) == _pt.build_ptest_desc(["/b$"]):
            bad.append("ptest desc 应随排除集变化（避免平台误复用同一规则）")

    return bad


# ═══════════════════════════════════════════════════════════════════
# 规则 12：Question Framework 契约（离线，不打真实网络 / 设备）
# ═══════════════════════════════════════════════════════════════════

_QF_TASK = "__guard_questions__"


def check_question_framework_contract():
    """规则 12：信息收集框架契约（schema / driver / intake / providers，离线）。

    固化本轮修复的易回退口径：
      - schema：悬空依赖 / 重复 id / 白名单 / derived 必须可调用 / `in` 集合门控解析
      - driver：拓扑（裸 id 依赖参与、外部派生键不参与）/ 谓词求值（==/!=/in）/
        **派生只在依赖就绪后求值** / done 判定 / **封闭选项白名单拒绝** /
        **环境变更后的级联失效**
      - intake：workspace 级落盘、presence=resolved、invalidate 级联清除
      - providers（真实）：问题集与顺序 / **可选能力按环境能力矩阵门控**
        （ptest 仅 A、泳道仅 B）/ auth_method 派生 / 占位符排除日期
      - 派生值：**派生值 = 当前输入的纯函数**（上游变更即重算），
        用户显式覆盖的派生题（overridable）不被重算；不可覆盖派生题预置被拒
      - 组合校验：env 块显式声明不匹配环境的可选能力必须报错
      - 命令层：`_parse_value` 类型解析
    """
    bad = []
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)

    import contextlib
    import io
    import shutil

    try:
        from provisioning.questions import driver as _drv
        from provisioning.questions import registry as _reg
        from provisioning.questions import schema as _sch
        from provisioning.questions.commands import _parse_value
        from provisioning.questions.providers import env as _env_provider
        from shared.errors import ContractError, UsageError
        from shared.intake import IntakeContext
        from shared.paths import flows_dir, task_dir
        from provisioning.validators.env_validator import infer_auth_method
        from provisioning.validators import auth_validator as _av
    except Exception as e:
        return [f"Question Framework 导入失败：{e}"]

    # 固定身份，避免守卫结果依赖本机（SSO cookie / git 配置）；resource_mis 因此走
    # derived 分支（下方断言）；无法解析时的回退分支也在下方单独覆盖；退出时还原。
    _orig_current_user_mis = _env_provider.current_user_mis
    _env_provider.current_user_mis = lambda: "guard_mis"

    prev_task = os.environ.get("AI_UITEST_TASK")
    snapshot = dict(_reg._REGISTRY)
    task_home = task_dir(_QF_TASK)
    buf = io.StringIO()

    with contextlib.redirect_stdout(buf):
        try:
            # ── A. schema / driver 契约（隔离：只挂一个测试 provider）──
            _reg._REGISTRY.clear()
            _reg._LOADED = True          # 抑制内置 provider 加载

            @_reg.register_provider
            class _GuardProvider(_reg.QuestionProvider):
                name = "guard-test"
                derived_keys = ("dtype",)

                def questions(self, ctx):
                    return [
                        {"id": "q", "group": "env", "order": 10, "prompt": "q",
                         "input_type": "single", "required": True,
                         "options": [{"value": "A", "label": "A"},
                                     {"value": "B", "label": "B"}]},
                        {"id": "gated", "group": "scope", "order": 20, "prompt": "gated",
                         "depends_on": ["q == 'B'"]},
                        {"id": "d", "group": "config", "order": 30, "prompt": "d",
                         "source": "derived", "depends_on": ["q"],
                         "resolve": lambda c: f"d-{c.get('q')}"},
                        {"id": "x", "group": "config", "order": 40, "prompt": "x",
                         "depends_on": ["dtype"]},   # 外部派生键（provider.derive 产出）
                    ]

                def derive(self, ctx):
                    return {"dtype": f"t-{ctx.get('q')}"} if ctx.is_resolved("q") else {}

            ctx = IntakeContext(_QF_TASK)
            first = (_drv.next_question(ctx).get("question") or {}).get("id")
            if first != "q":
                bad.append(f"driver: 首题应为 q，实得 {first}")
            if ctx.is_resolved("d"):
                bad.append("driver: 派生题 d 在依赖 q 未答时被提前求值（应延迟）")

            try:
                _drv.answer(ctx, "q", "C")
                bad.append("driver: 非法选项 C 未被拒绝")
            except UsageError:
                pass

            _drv.answer(ctx, "q", "A")
            if ctx.get("d") != "d-A":
                bad.append(f"driver: 派生题求值异常 d={ctx.get('d')!r}（应在 q 就绪后求值）")
            nxt = (_drv.next_question(ctx).get("question") or {}).get("id")
            if nxt == "gated":
                bad.append("driver: 谓词不满足的题 gated（q=='B'）仍被提问")

            try:
                _sch.validate_questions([{"id": "y", "depends_on": ["nope == 'z'"]}],
                                        known_ids=set())
                bad.append("schema: 悬空 depends_on 未报错")
            except ContractError:
                pass

            # `in` 集合门控：解析 + 求值（正/负两向）
            if _sch.parse_dep("k in ('A', 'D')") != ("k", "in", ("A", "D")):
                bad.append("schema: `in` 集合门控解析异常")

            class _StubCtx:
                def __init__(self, vals): self._v = vals
                def is_resolved(self, qid): return qid in self._v
                def get(self, qid, default=None): return self._v.get(qid, default)

            _gate_q = {"depends_on": ["k in ('A', 'D')"]}
            if _drv._gate_state(_gate_q, _StubCtx({"k": "A"})) != "ok":
                bad.append("driver: 集合门控 k in ('A','D') 在 k=='A' 时应适用")
            if _drv._gate_state(_gate_q, _StubCtx({"k": "C"})) != "inapplicable":
                bad.append("driver: 集合门控 k in ('A','D') 在 k=='C' 时应不适用")
            if _drv._gate_state(_gate_q, _StubCtx({})) != "waiting":
                bad.append("driver: 集合门控依赖未就绪时应为 waiting")

            # ── B. 真实 provider 契约 ──
            _reg._REGISTRY.clear()
            _reg._REGISTRY.update(snapshot)
            _reg._LOADED = True
            os.environ["AI_UITEST_TASK"] = _QF_TASK
            shutil.rmtree(task_home, ignore_errors=True)
            os.makedirs(flows_dir(), exist_ok=True)
            with open(os.path.join(flows_dir(), "guard-flow.md"), "w",
                      encoding="utf-8") as fh:
                fh.write("# 守卫用例\n\n| 目标锁包 | rn_hotel_guard |\n"
                         "| AppMock | `16305525` |\n\n"
                         "跳链: imeituan://x?id={order_id}&t={T+1}\n")

            ctx2 = IntakeContext(_QF_TASK)
            values = {
                "device_combo": "sandbox-android-meituan",
                "resource_mis": "guard_mis", "env_type": "B",
                "swim_lane_name": "",
                "swim_url_mappings": "", "bundle_lock": [],
                "order_id": "12345",
            }

            # 渲染契约：每题 render.options 恒 ≥2（AskQuestion 硬性要求）；
            # 非封闭选择题必须 free_text（否则 AI 无法原样渲染）
            for _q in _reg.all_questions(ctx2):
                _render = _sch.build_render(_q)
                if len(_render.get("options") or []) < 2:
                    bad.append(f"render: 题目 {_q['id']} 的 render.options < 2（AskQuestion 无法渲染）")
                if _q.get("input_type") not in ("single", "multi") and _render["mode"] != "free_text":
                    bad.append(f"render: 文本题 {_q['id']} 应为 free_text，实得 {_render['mode']!r}")

            # 硬门禁：未 input-next 下发前不得作答
            try:
                _drv.answer(ctx2, "resource_mis", "x")
                bad.append("driver: 未 input-next 下发前不应允许作答（硬门禁失效）")
            except UsageError:
                pass

            # 资源 MIS：能解析身份时必须为派生题（自动落库、不提问）
            _rm_q = next((q for q in _reg.all_questions(ctx2) if q.get("id") == "resource_mis"), None)
            if not _rm_q or _rm_q.get("source") != "derived" or not callable(_rm_q.get("resolve")):
                bad.append(f"providers: 可解析身份时 resource_mis 应为 derived+resolve，实得 {_rm_q}")
            # 无法解析身份时必须退回必答（不得静默留空）
            _env_provider.current_user_mis = lambda: ""
            _rm_fb = next((q for q in _reg.all_questions(ctx2) if q.get("id") == "resource_mis"), None)
            _env_provider.current_user_mis = lambda: "guard_mis"
            if not _rm_fb or _rm_fb.get("source") != "ask" or not _rm_fb.get("required"):
                bad.append(f"providers: 无法解析身份时 resource_mis 应退回 ask+required，实得 {_rm_fb}")

            # 场景 AppMock 不再是采集层问题（case 级，由 flow-init 从 Flow 派生）
            if any(q.get("id") == "mock_ids" for q in _reg.all_questions(ctx2)):
                bad.append("providers: mock_ids 不应作为采集层问题（场景 AppMock 已下沉为 case 级）")

            # 下发首题后再验证信号契约（resource_mis 已派生 → 首题为 device_combo）
            _first2 = (_drv.next_question(ctx2).get("question") or {}).get("id")
            if _first2 != "device_combo":
                bad.append(f"driver: 首题应为 device_combo（resource_mis 已派生），实得 {_first2}")

            _drv.answer(ctx2, "device_combo", _sch.MANUAL_INPUT_VALUE)
            if ctx2.is_resolved("device_combo"):
                bad.append("driver: __manual_input__ 不应把题目标记为已解析")
            # 批量 / 跳答：答非当前下发题（resource_mis 非当题）应被硬门禁拒绝
            try:
                _drv.answer(ctx2, "resource_mis", "guard_mis")
                bad.append("driver: 批量/跳答未被硬门禁拒绝")
            except UsageError:
                pass
            # 必填题不得跳过（device_combo 为必填且当前下发）
            try:
                _drv.answer(ctx2, "device_combo", _sch.SKIP_VALUE)
                bad.append("driver: required 题不应允许 __skip__")
            except UsageError:
                pass

            sequence = []
            while True:
                res = _drv.next_question(ctx2)
                if res["done"]:
                    break
                qid = (res.get("question") or {}).get("id")
                sequence.append(qid)
                if qid not in values:
                    bad.append(f"providers: 出现未预期的问题 {qid}")
                    break
                _drv.answer(ctx2, qid, values[qid])

            # 场景 AppMock 已下沉为 case 级，故不出现在提问序列中；
            # B（验证码登录）账号自动生成，不上问（account / test_account 均不入序列）
            expected = ["device_combo", "env_type",
                        "swim_lane_name", "swim_url_mappings",
                        "bundle_lock", "order_id"]
            if sequence != expected:
                bad.append(f"providers: 提问顺序异常 {sequence}（期望 {expected}）")
            if "ptest" in sequence:
                bad.append("providers: B（泳道）环境不应提问 ptest（仅线上 A 适用）")
            ans = ctx2.answers
            if ans.get("auth_method") != "qahome":
                bad.append(f"providers: auth_method 派生异常 {ans.get('auth_method')!r}")

            # 自动测试号：派生（不提问）+ 格式合法 + 同 workspace 确定性
            _auto = ans.get("test_account")
            if not _av.is_valid_test_account(_auto):
                bad.append(f"providers: B（qahome）应自动生成合法测试号，实得 {_auto!r}")
            if _av.generate_test_account(_QF_TASK) != _auto:
                bad.append("providers: 测试号应确定性生成（同 workspace 重算不变）")
            if ctx2.is_resolved("account"):
                bad.append("providers: B（qahome）不应落 account（手填账号仅凭证登录适用）")
            if "password" in sequence:
                bad.append("providers: B 环境(qahome) 不应问 password")
            if "T+1" in ans or "T+1" in sequence:
                bad.append("providers: 日期占位符 {T+1} 不应上问")
            if ans.get("device_type") != "sandbox" or ans.get("app") != "meituan":
                bad.append(f"providers: device_combo 拆分异常 {ans.get('device_type')}")

            if infer_auth_method("A", "local") != "noop":
                bad.append("providers: local 设备应锁定 auth_method=noop")

            if (_parse_value("true") is not True or _parse_value("[]") != []
                    or _parse_value("13800000000") != "13800000000"
                    or _parse_value("shicheng") != "shicheng"):
                bad.append("commands: _parse_value 类型解析异常")

            # ── C. input-seed：批量预置（用户已给的值不再逐题问）──
            _intake_file = IntakeContext(_QF_TASK).path

            def _fresh_ctx():
                if os.path.isfile(_intake_file):
                    os.remove(_intake_file)
                return IntakeContext(_QF_TASK)

            ctx3 = _fresh_ctx()
            seeded = _drv.seed(ctx3, {
                "device_combo": "sandbox-android-meituan",
                "env_type": "B", "resource_mis": "guard_mis",
                "test_account": "13800000000",   # 覆盖自动生成号 → 应接受并 pin
                "account": "13800000000",        # 手填账号仅凭证登录 → 应拒绝
                "swim_lane_name": "",
                "swim_url_mappings": "", "ptest": True, "bundle_lock": [],
                "order_id": "12345",
                "device_type": "sandbox",        # 派生键 → 应拒绝
                "no_such_q": "x",                # 未知 id → 应拒绝
            })
            rej = [r["id"] for r in seeded["rejected"]]
            if "device_type" not in rej or "no_such_q" not in rej:
                bad.append(f"seed: 派生键 / 未知 id 未被拒绝 {seeded['rejected']}")
            if "ptest" not in rej:
                bad.append("seed: B 环境下 ptest 应被拒绝（仅线上 A 适用）")
            if "account" not in rej:
                bad.append("seed: B（qahome）下手填 account 应被拒绝（仅凭证登录适用）")
            if ctx3.get("test_account") != "13800000000" or "test_account" not in ctx3.pinned:
                bad.append("seed: test_account 的覆盖应被保留并 pin，"
                           f"实得 {ctx3.get('test_account')!r}")
            if ctx3.get("device_type") != "sandbox":
                bad.append("seed: device_combo 未触发 device_type 派生")
            if seeded["remaining"] or seeded["deferred"]:
                bad.append(f"seed: 全量预置后应无剩余 / 挂起 {seeded}")
            if not _drv.next_question(ctx3)["done"]:
                bad.append("seed: 全量预置后 next_question 应直接 done（不得再逐题问）")

            # 三态门控：A 环境下 B-only 泳道题应被拒（防泄漏）；password 应落值
            ctx4 = _fresh_ctx()
            _drv.seed(ctx4, {
                "device_combo": "sandbox-android-meituan",
                "env_type": "A", "resource_mis": "guard_mis",
                "account": "13800000000", "password": "pw",
                "swim_lane_name": "lane-x",      # A 环境不适用 → 应拒绝
            })
            if ctx4.is_resolved("swim_lane_name"):
                bad.append("seed: A 环境下 B-only 泳道题不应落值（depends_on 泄漏）")
            if not ctx4.is_resolved("password"):
                bad.append("seed: A 环境（password 登录）应预置 password")

            # 依赖未就绪 → 挂起 pending_seeds；依赖补齐后自动落库（不重复问）
            ctx5 = _fresh_ctx()
            _drv.seed(ctx5, {"password": "pw"})   # auth_method 未就绪 → waiting
            if ctx5.is_resolved("password") or "password" not in ctx5.pending_seeds:
                bad.append("seed: 依赖未就绪的值应挂起于 pending_seeds（不得落值）")
            _drv.seed(ctx5, {"device_combo": "sandbox-android-meituan",
                             "env_type": "A", "resource_mis": "guard_mis",
                             "account": "13800000000"})
            if not ctx5.is_resolved("password"):
                bad.append("seed: 依赖就绪后挂起的 password 应自动落库")
            if ctx5.pending_seeds:
                bad.append(f"seed: 依赖就绪后 pending_seeds 应清空，实得 {ctx5.pending_seeds}")

            # ── D. 环境能力门控 + 级联失效 + 组合校验 ──
            # ptest 仅线上(A)适用：A 应适用且可落值；C 不适用且预置被拒
            ctx6 = _fresh_ctx()
            _drv.seed(ctx6, {"device_combo": "sandbox-android-meituan",
                             "env_type": "A", "resource_mis": "guard_mis",
                             "account": "13800000000", "password": "pw", "ptest": True})
            _st6 = {i["id"]: i["applicable"] for i in _drv.status(ctx6)["questions"]}
            if not _st6.get("ptest"):
                bad.append("providers: A（线上）环境 ptest 应适用")
            if not ctx6.is_resolved("ptest") or ctx6.get("ptest") is not True:
                bad.append("seed: A（线上）环境应允许预置 ptest")
            if _st6.get("swim_lane_name"):
                bad.append("providers: A 环境泳道题不应适用")

            ctx7 = _fresh_ctx()
            _drv.seed(ctx7, {"device_combo": "sandbox-android-meituan",
                             "env_type": "C", "resource_mis": "guard_mis",
                             "test_account": "13800000000", "ptest": True})
            _st7 = {i["id"]: i["applicable"] for i in _drv.status(ctx7)["questions"]}
            if _st7.get("ptest"):
                bad.append("providers: C（alpha）环境 ptest 不应适用")
            if ctx7.is_resolved("ptest"):
                bad.append("seed: C（alpha）环境不应允许 ptest 落值（depends_on 泄漏）")
            if not _st7.get("test_account") or not _av.is_valid_test_account(ctx7.get("test_account")):
                bad.append("providers: C（qahome）环境应自动生成合法测试号")
            if _st7.get("account"):
                bad.append("providers: C（qahome）环境手填账号题不应适用")

            # 级联失效：A+ptest 落库后把环境改成 C → ptest 应被清除
            ctx8 = _fresh_ctx()
            _drv.seed(ctx8, {"device_combo": "sandbox-android-meituan",
                             "env_type": "A", "resource_mis": "guard_mis",
                             "account": "13800000000", "password": "pw", "ptest": True})
            if not ctx8.is_resolved("ptest"):
                bad.append("级联前置：A 环境 ptest 应先落库")
            _drv.seed(ctx8, {"env_type": "C"})
            if ctx8.is_resolved("ptest"):
                bad.append("seed: 环境由 A 切到 C 后 ptest 应级联失效（invalidate 未生效）")
            if ctx8.is_resolved("account"):
                bad.append("级联: A→C 后手填 account 应失效（凭证登录题不再适用）")
            if not _av.is_valid_test_account(ctx8.get("test_account")):
                bad.append("级联: A→C 后应自动生成合法测试号（test_account 派生）")

            # 组合校验：env 块显式声明 C + ptest=true 必须报错（不得静默放行）
            from provisioning.validators.env_validator import validate_env_config as _vec
            from shared.errors import ConfigError as _CfgErr
            try:
                _vec({"type": "C", "ptest": True}, app="meituan", device_type="sandbox")
                bad.append("validate_env_config: C + ptest=true 未报错（组合校验缺失）")
            except _CfgErr:
                pass
            try:
                _vec({"type": "A", "ptest": True}, app="meituan", device_type="sandbox")
            except _CfgErr as exc:
                bad.append(f"validate_env_config: A + ptest=true 不应报错（{exc}）")

            # 环境能力矩阵与环境类型定义必须同域（新增环境类型必须显式登记能力，
            # 否则新环境会「静默无任何可选能力」而与直觉不符）
            from provisioning.validators import env_validator as _ev
            if set(_ev.ENV_CAPABILITIES) != set(_ev._ENV_TYPE_DEFS):
                bad.append(
                    "providers: ENV_CAPABILITIES 与 _ENV_TYPE_DEFS 环境集合不一致 "
                    f"{sorted(set(_ev.ENV_CAPABILITIES) ^ set(_ev._ENV_TYPE_DEFS))}"
                )

            # 派生值：上游变更（A→C）→ 派生键重算 + 以派生键为条件的字段级联失效
            ctx9 = _fresh_ctx()
            _drv.seed(ctx9, {"device_combo": "sandbox-android-meituan",
                             "env_type": "A", "resource_mis": "guard_mis",
                             "account": "13800000000", "password": "pw"})
            if not ctx9.is_resolved("password"):
                bad.append("派生重算前置：A（password 登录）环境 password 应先落库")
            _drv.seed(ctx9, {"env_type": "C"})          # A(password) → C(qahome)
            if ctx9.get("auth_method") != "qahome":
                bad.append("派生重算：auth_method 应跟随 env_type 重算为 qahome，"
                           f"实得 {ctx9.get('auth_method')!r}")
            if ctx9.is_resolved("password"):
                bad.append("派生重算：环境切到 C 后，以派生键 auth_method 为条件的 password 应级联失效")
            if ctx9.is_resolved("account"):
                bad.append("派生重算：环境切到 C 后手填 account 应级联失效")
            if not _av.is_valid_test_account(ctx9.get("test_account")):
                bad.append("派生重算：环境切到 C 后应自动生成合法测试号")

            # 用户显式覆盖的派生题（resource_mis）必须被尊重（pinned）
            ctx10 = _fresh_ctx()
            _drv.seed(ctx10, {"device_combo": "sandbox-android-meituan",
                              "env_type": "A", "resource_mis": "my_mis",
                              "account": "13800000000", "password": "pw"})
            if ctx10.get("resource_mis") != "my_mis" or "resource_mis" not in ctx10.pinned:
                bad.append("派生覆盖：resource_mis 的覆盖应被保留并 pin，"
                           f"实得 {ctx10.get('resource_mis')!r}")
            # 不可覆盖的派生题（auth_method）预置必须被拒绝
            _rej10 = [r["id"] for r in _drv.seed(ctx10, {"auth_method": "password"})["rejected"]]
            if "auth_method" not in _rej10:
                bad.append("派生题：不可覆盖的 auth_method 预置应被拒绝")
            # 自动测试号仅验证码登录适用：A（password）下预置 test_account 应被拒绝
            _rej10b = [r["id"] for r in _drv.seed(ctx10, {"test_account": "13900000000"})["rejected"]]
            if "test_account" not in _rej10b:
                bad.append("派生题：A（password）环境下 test_account 预置应被拒绝（门控失效）")
        finally:
            _reg._REGISTRY.clear()
            _reg._REGISTRY.update(snapshot)
            _reg._LOADED = True
            _env_provider.current_user_mis = _orig_current_user_mis
            if prev_task is None:
                os.environ.pop("AI_UITEST_TASK", None)
            else:
                os.environ["AI_UITEST_TASK"] = prev_task
            shutil.rmtree(task_home, ignore_errors=True)

    return bad


# ═══════════════════════════════════════════════════════════════════
# 规则 13：设备会话并发隔离（离线静态）
# ═══════════════════════════════════════════════════════════════════

DEVICE_SESSION_ENV = "IMEITUAN_SESSION"


def _has_identifier(tree, name):
    """AST 中是否出现指定标识符（名称/参数/关键字/属性）——忽略注释与字符串。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.arg) and node.arg == name:
            return True
        if isinstance(node, ast.keyword) and node.arg == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
    return False


def _has_str_literal(tree, value):
    """AST 中是否出现精确等于 value 的字符串字面量——忽略注释。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == value:
            return True
    return False


def check_device_session_isolation():
    """规则 13：设备命令必须绑定「本 run 的会话」，禁止全量断会话。

    并发 run 下 imeituan CLI 的「活跃 session」是 ~/.imeituan 下的全局单例：若不显式
    绑定会话，设备命令会被静默路由到别的 run 的设备（历史故障：inspect-tree 打到
    他人设备 → 元素目录/截图全是别人设备的画面）。固化三条不变量：
      · 禁止代码里出现 `all_sessions` 标识符 / `"--all"` 字面量（会踢掉并发 run 的会话）；
      · 设备命令出口 imeituan_cli.py 必须实现会话绑定（bind_session + IMEITUAN_SESSION），
        且未绑定时对需会话命令直接失败（不得静默路由）；
      · CLI 入口 cli.py 必须按 active run 的 flow-context.session_id 绑定会话。
    """
    bad = []
    exit_rel = "devices/toolchain/imeituan_cli.py"
    entry_rel = "cli.py"
    found_exit = found_entry = False

    for path in _iter_py_files():
        rel = _rel(path)
        tree = _parse(path)
        if tree is not None:
            if _has_identifier(tree, "all_sessions"):
                bad.append(f"{rel}: 出现 all_sessions（全量断会话会踢掉并发 run 的会话）")
            if _has_str_literal(tree, "--all"):
                bad.append(f"{rel}: 出现 \"--all\" 字面量（全量断会话）")
        if rel in (exit_rel, entry_rel):
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            if rel == exit_rel:
                found_exit = True
                missing = [n for n in ("bind_session", DEVICE_SESSION_ENV, "def needs_session")
                           if n not in text]
                if missing:
                    bad.append(f"{rel}: 会话绑定出口缺失 {missing}")
            if rel == entry_rel:
                found_entry = True
                if "bind_session" not in text:
                    bad.append(f"{rel}: 入口未按 active run 绑定设备会话（应调用 bind_session）")

    if not found_exit:
        bad.append(f"未找到设备命令出口 {exit_rel}")
    if not found_entry:
        bad.append(f"未找到 CLI 入口 {entry_rel}")

    # ── 行为自测（离线）：stub imeituan_run，验证「绑定 → 注入」与未绑定即失败 ──
    try:
        from devices.toolchain import imeituan_cli as _ic

        calls = []

        def _fake_run(args, capture=True, timeout=30, env_extra=None):
            calls.append({"args": list(args),
                          "session": (env_extra or {}).get(DEVICE_SESSION_ENV)})
            return subprocess.CompletedProcess(
                args=list(args), returncode=0, stdout="{}", stderr="")

        orig_run = _ic.imeituan_run
        _ic.imeituan_run = _fake_run
        try:
            _ic.bind_session("sess-A")
            _ic.imeituan_inspect_tree("/tmp/catpaw_sess_probe.json")
            _ic.bind_session("sess-B")
            _ic.imeituan_shell("echo", "hi")
            _ic.unbind_session()

            if calls[-2]["session"] != "sess-A":
                bad.append(f"自测: A 的设备命令未携带 sess-A（实得 {calls[-2]['session']}）")
            if calls[-1]["session"] != "sess-B":
                bad.append(f"自测: B 的设备命令未携带 sess-B（实得 {calls[-1]['session']}）")

            try:
                _ic.imeituan_shell("echo", "hi")   # 未绑定 → 必须显式失败
                bad.append("自测: 未绑定会话时设备命令未失败（存在静默串台风险）")
            except Exception:
                pass

            try:
                _ic.imeituan_register_device("1.2.3.4:5555", platform="android")   # 不需会话 → 应放行
            except Exception as e:
                bad.append(f"自测: device register 不应要求会话（{e}）")
        finally:
            _ic.imeituan_run = orig_run
            _ic.unbind_session()
    except Exception as e:
        bad.append(f"会话隔离自测异常：{e}")

    return bad


# ── 规则 20：AppMock 设备端「真实状态原语」单一消费点（业务层走能力位语义）──
APPMOCK_STATE_PRIMITIVE = "check_appmock_sdk_enabled"
# 允许直接消费该原语的模块：原语定义处 + 必须知道真实状态才能决策的前置步骤
APPMOCK_STATE_PRIMITIVE_ALLOWLIST = {
    "platform/appmock/device.py",            # 原语定义处（含 appmock_ready 内部使用）
    "provisioning/setup/login/steps.py",     # EnableAppMock：按真实状态选「清数据+预授权」分支
}


def check_appmock_state_primitive_single_entry():
    """规则 20：`check_appmock_sdk_enabled`（设备端 AppMock 真实状态原语）只允许被
    「必须知道真实状态才能决策」的模块消费；业务层统一走能力位语义入口
    `platform.appmock.device.appmock_ready()`。

    为什么固化：该原语在**不可确认平台（鸿蒙）恒返回 False**，而它表达的是「查不到」
    而非「没开」。业务层若直接拿它做前置判定，就等于把「平台是否可确认」这条平台
    差异以**隐式分支**的形式带进业务层——鸿蒙必然恒失败，且能绕过规则 14（它只拦
    显式的 `if platform == ...`）。平台差异的唯一声明点是
    `PlatformOps.can_verify_appmock_state`，业务层只消费由其派生的语义 API。
    """
    bad = []
    for path in _iter_py_files():
        rel = _rel(path)
        if rel in APPMOCK_STATE_PRIMITIVE_ALLOWLIST:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(
                    a.name == APPMOCK_STATE_PRIMITIVE for a in node.names):
                bad.append(
                    f"{rel}:{node.lineno} 直接导入 "
                    f"{APPMOCK_STATE_PRIMITIVE}（业务层请改用 appmock_ready()）")
            elif isinstance(node, ast.Name) and node.id == APPMOCK_STATE_PRIMITIVE:
                bad.append(
                    f"{rel}:{node.lineno} 直接消费 {APPMOCK_STATE_PRIMITIVE}"
                    f"（业务层请改用 appmock_ready()）")
    return bad


# ── 规则 21：认证动作层（L3）不得出现平台 / 控件字面量 ──────────────────
LOGIN_ACTION_DIR = f"{LOGIN_LAYER_DIR}/actions"
# 资源 id 形态（真机实测）、平台工具、平台组件类名、平台目录/包名。
# 为什么固化：这些字面量一旦散进业务层，新增平台就要改流程（而不是补数据），且
# 写错的 id 不会报错、只会**静默永不命中**（历史上"元素定位失败"多为此类）。
L3_FORBIDDEN_LITERALS = (
    "passport_",            # Android 登录页资源 id 前缀
    "edit_text_view",       # Android 验证码输入框 id
    "dynamic_checkbox",     # Android 协议复选框 id
    "normaltextinput",      # 鸿蒙登录页唯一可用 id
    "navroot", "ffproot",   # 鸿蒙页面根 id
    "inputmethod",          # 系统输入法窗口标识（鸿蒙）
    "uiautomator", "adb shell", "adb keyboard", "hdc ",  # 平台工具
    "textinput", "edittext", "imageview",                 # 平台 UI 组件类名
    "com.sankuai.", "com.android.", "com.huawei.",        # 平台包名/进程名
)
L3_FORBIDDEN_IDENTS = ("passport_", "edit_text_view", "dynamic_checkbox", "inputmethod")


def _iter_string_literals(tree):
    """遍历字符串字面量，**跳过 docstring**（约定本身需要被写下来）。"""
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings):
            yield node


def check_login_action_no_platform_literal():
    """规则 21：认证动作层只表达意图，平台/控件差异必须来自数据或 PlatformOps。

    允许的是：语义名（`phone_input` / `send_code` / `agreement` / `code_input`）、
    `PageSpec` 查询、`PlatformOps` 原语；不允许的是资源 id、平台工具/组件类名、
    平台包名等"平台事实"直接写进 L3（含日志字符串里的 id —— 它会把平台细节
    重新散回排查口径）。
    """
    bad = []
    for path in _iter_py_files():
        rel = _rel(path)
        if not rel.startswith(LOGIN_ACTION_DIR + "/"):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in _iter_string_literals(tree):
            low = node.value.lower()
            hit = next((t for t in L3_FORBIDDEN_LITERALS if t in low), None)
            if hit:
                bad.append(f"{rel}:{node.lineno} 字符串含平台/控件字面量 {hit!r}"
                           "（应放进 PageSpec / PlatformOps）")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name):
                continue
            low = node.id.lower()
            hit = next((t for t in L3_FORBIDDEN_IDENTS if t in low), None)
            if hit:
                bad.append(f"{rel}:{node.lineno} 标识符含平台/控件字面量 {hit!r}")
    return bad


# ── 规则 22：环境澄清单一入口 ────────────────────────────────────────
RECONCILE_ENTRY_REL = "provisioning/setup/environment_reconciler.py"
POPUP_EXECUTOR_OWNER_LAYERS = ("devices", "platform")


def check_reconcile_single_entry():
    """规则 22：业务层只能经 `reconcile_environment()` 澄清环境。

    执行器 `devices.popup.dismiss_popups` 属实现细节，只允许 `devices` / `platform`
    层引用（这两层是"设备原语"所在层，分层上不能上引 `provisioning`）；其余层
    （provisioning / execution / reporting / orchestration）一律走唯一入口，
    否则等待窗口、返回语义（None/三态）与日志口径会各自分叉，排查时无法按阶段过滤。
    """
    bad = []
    for path in _iter_py_files():
        rel = _rel(path)
        layer = rel.split("/", 1)[0]
        if layer in POPUP_EXECUTOR_OWNER_LAYERS or rel == RECONCILE_ENTRY_REL:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(
                    a.name == "dismiss_popups" for a in node.names):
                bad.append(f"{rel}:{node.lineno} 直接导入 dismiss_popups"
                           f"（业务层应走 {RECONCILE_ENTRY_REL}::reconcile_environment）")
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "dismiss_popups"):
                bad.append(f"{rel}:{node.lineno} 直接调用 dismiss_popups（应走唯一入口）")
    return bad


# ── 规则 23：澄清必须排在所有重启类步骤之后 ──────────────────────────
SETTLE_STEP_CLS = "SettlePopups"
ORCHESTRATOR_REL = f"{LOGIN_LAYER_DIR}/orchestrator.py"
POST_RECONCILE_MARK = 'reconcile_environment(label="login:post"'


def check_reconcile_after_last_restart():
    """规则 23：系统弹窗出现在 App 启动**之后**，故澄清必须在最后一次重启之后。

    (a) 运行时校验：每条环境管线的 `pre` 末位必须是 `SettlePopups`，且其**之后**
        不得再有声明了重启的步骤（否则澄清会被其后的冷重启作废）；
    (b) `post` 阶段（域名映射激活等）同样会冷重启，编排层必须在实际发生重启后
        用同一入口复核屏幕干净度（否则登录后的页面被弹窗盖住，Android 前台判定/
        取证都会失真）。
    """
    bad = []
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    try:
        from provisioning.setup.login.plan import TARGET_ENV_SWIMLINE
        from provisioning.setup.login.policy import RestartPolicy
        from provisioning.setup.login.registry import ENV_STEPS, build_pipeline
        from provisioning.setup.login.steps import SettlePopups
    except Exception as e:  # noqa: BLE001 —— 导入失败一律报出
        return [f"登录管线导入失败（无法校验澄清时机）：{e}"]

    def _check_pipe(name, pipe):
        pre = tuple(pipe.pre)
        if not pre:
            bad.append(f"{name}: pre 管线为空（至少需要 ResetMockEnv / EnableAppMock）")
            return
        if pre[-1] is not SettlePopups:
            bad.append(
                f"{name}: pre 末位必须是 {SETTLE_STEP_CLS}（澄清须在所有重启之后），"
                f"实得 {getattr(pre[-1], '__name__', pre[-1])}")
            return
        for cls in pre:
            policy = getattr(getattr(cls, "step", None), "restart", None)
            if policy is not None and policy is not RestartPolicy.NONE and cls is SettlePopups:
                bad.append(f"{name}: 澄清步骤本身不得声明重启（{policy}）")

    for env, pipe in ENV_STEPS.items():
        _check_pipe(env, pipe)

    class _StubPlan:
        """仅用于取"泳道但无 lane_name"的分流管线（build_pipeline 只读这两个字段）。"""
        target_env = TARGET_ENV_SWIMLINE
        swimline = None

    _check_pipe("swimline(no-lane)", build_pipeline(_StubPlan()))

    orch_text = _read_text(os.path.join(SCRIPTS_DIR, ORCHESTRATOR_REL))
    if POST_RECONCILE_MARK not in orch_text:
        bad.append(f"{ORCHESTRATOR_REL}: post 阶段实际重启后缺少澄清复核"
                   f"（应调用 {POST_RECONCILE_MARK}…)）")
    return bad


# ── 规则 29：清数据冷重启后必须重建登录前置不变量（定位 + 澄清）──────────
CLEAR_DATA_STEP_NAME = "EnableAppMock"
REPAIR_FN_NAME = "build_repair_pipeline"


def check_clear_data_reprovision():
    """规则 29：任何「清数据冷重启」之后必须重建登录前置不变量（定位 + 澄清）。

    背景（实测回归）：`EnableAppMock` 以 `COLD_CLEAR_DATA` 清数据冷重启，设备侧随之
    丢失「定位」与「弹窗同意态」；若某条路径（尤其认证失败恢复）只做 EnableAppMock
    却漏 `PushLocation` ⇒ 首页渲染不出「去登录」入口 ⇒ 登录导航失败。

    (a) ENV_STEPS 里「要登录」的管线（含 EnableAppMock）必须同时含 PushLocation；
    (b) 失败恢复管线 `build_repair_pipeline(plan)` 对每个环境都必须含 PushLocation
        且以 SettlePopups 收尾（澄清须在所有重启之后，与规则 23 同口径）；
    (c) 编排层的 qahome 恢复必须**经 `build_repair_pipeline` 派生步骤**，不得手挑 ——
        手挑正是历史漏步（漏 PushLocation）的来源。
    """
    bad = []
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    try:
        from provisioning.setup.login.plan import TARGET_ENV_NONE
        from provisioning.setup.login.registry import ENV_STEPS, build_repair_pipeline
        from provisioning.setup.login.steps import (
            EnableAppMock, PushLocation, SettlePopups,
        )
    except Exception as e:  # noqa: BLE001 —— 导入失败一律报出
        return [f"登录管线导入失败（无法校验清数据重建不变量）：{e}"]

    for env, pipe in ENV_STEPS.items():
        if env == TARGET_ENV_NONE:
            continue
        pre = tuple(pipe.pre)
        if EnableAppMock in pre and PushLocation not in pre:
            bad.append(
                f"{env}: pre 含 {CLEAR_DATA_STEP_NAME}（清数据冷重启）却缺 PushLocation"
                "（清数据后无定位 ⇒ 首页渲染不出「去登录」入口 ⇒ 登录导航失败）")

    class _StubPlan:
        """仅提供 build_repair_pipeline 需要的两个字段。"""

        def __init__(self, target_env, url_mappings=()):
            self.target_env = target_env
            self.url_mappings = url_mappings

    for env in ENV_STEPS:
        if env == TARGET_ENV_NONE:
            continue
        repair_pre = tuple(build_repair_pipeline(_StubPlan(env)).pre)
        if PushLocation not in repair_pre:
            bad.append(f"{env}: build_repair_pipeline 缺 PushLocation（清数据恢复后无定位）")
        if not repair_pre or repair_pre[-1] is not SettlePopups:
            bad.append(
                f"{env}: build_repair_pipeline 末位必须是 {SETTLE_STEP_CLS}"
                "（澄清须在最后一次重启之后）")

    orch_text = _read_text(os.path.join(SCRIPTS_DIR, ORCHESTRATOR_REL))
    if REPAIR_FN_NAME not in orch_text:
        bad.append(
            f"{ORCHESTRATOR_REL}: qahome 完整恢复未经 {REPAIR_FN_NAME} 派生步骤"
            "（手挑步骤会再次漏掉清数据后的定位/澄清）")
    return bad


# ── 规则 30：页面到达/停留判定必须用内容身份（identity），不得用控件选择器 ──
# 背景（实测回归）：`_wait_code_page` 曾用 `code_input` 控件判定"是否到达验证码页"，
# 而 `code_input` 的 `role: [EditText, TextInput]` 兜底会命中**登录页的手机号输入框**
# → 页面没变也被判为"已到达" → "空点"被误报成"发码成功"，掩盖了真正没发码。
ARRIVAL_FN_PREFIXES = ("_wait_", "_on_")
ARRIVAL_FORBIDDEN_SELECTOR_ATTR = "control"


def check_page_arrival_uses_identity():
    """规则 30：登录动作层的"到达/停留判定"函数（`_wait_*` / `_on_*`）不得用控件选择器。

    控件选择器（`PageSpec.control(...)`）可能含过宽的 `role` 兜底，会命中**其它页面**的
    同角色元素 → 到达判定假阳性。到达判定只认 `PageSpec.identity`（内容身份）或窗口 `markers`。
    """
    bad = []
    for path in _iter_py_files():
        rel = _rel(path)
        if not rel.startswith(LOGIN_LAYER_DIR + "/actions/"):
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.FunctionDef)
                    and node.name.startswith(ARRIVAL_FN_PREFIXES)):
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == ARRIVAL_FORBIDDEN_SELECTOR_ATTR):
                    bad.append(
                        f"{rel}:{sub.lineno} {node.name}() 用控件选择器（.control(...)）"
                        "判定页面到达/停留；到达判定必须用 PageSpec.identity"
                        "（控件选择器的 role 兜底会命中其它页面 → 假阳性）")
    return bad


# ── 规则 24：PageSpec 数据契约 ───────────────────────────────────────
SELECTOR_KINDS = ("id", "role", "text", "left_clickable_in_row")
_NOT_LITERAL = object()


def _ast_literal(node):
    """把 AST 字面量（常量 / 列表 / 元组 / 字典）还原为 Python 值。

    含任何非字面量（Name / Call / f-string…）时返回 `_NOT_LITERAL` —— 数据类型必须是
    **纯数据**（同 `platform/popup/patterns.py` 的定位）：能静态校验、可被守卫固化。
    """
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        vals = [_ast_literal(e) for e in node.elts]
        return vals if all(v is not _NOT_LITERAL for v in vals) else _NOT_LITERAL
    if isinstance(node, ast.Dict):
        out = {}
        for k, v in zip(node.keys, node.values):
            kk, vv = _ast_literal(k), _ast_literal(v)
            if kk is _NOT_LITERAL or vv is _NOT_LITERAL or not isinstance(kk, str):
                return _NOT_LITERAL
            out[kk] = vv
        return out
    return _NOT_LITERAL


def _check_selector(sel, where, bad):
    """校验单个选择器：`by` 在白名单内且 `value` 类型/取值正确。"""
    if not isinstance(sel, dict):
        bad.append(f"{where} 选择器应为 dict（by/value），实得 {sel!r}")
        return
    kind, value = sel.get("by"), sel.get("value")
    if kind not in SELECTOR_KINDS:
        bad.append(f"{where} 未知选择器类型 by={kind!r}（合法：{SELECTOR_KINDS}）")
        return
    if kind == "role":
        if not (isinstance(value, list) and value and all(isinstance(v, str) for v in value)):
            bad.append(f"{where} role 选择器的 value 应为非空角色名列表，实得 {value!r}")
    elif not (isinstance(value, str) and value.strip()):
        bad.append(f"{where} {kind} 选择器的 value 应为非空字符串，实得 {value!r}")


def _check_hop_ast(hop_node, where, bad):
    """静态校验一个 `Hop(...)`：`enter` 非空，`enter`/`expect` 均为合法选择器列表。"""
    if not (isinstance(hop_node, ast.Call) and isinstance(hop_node.func, ast.Name)
            and hop_node.func.id == "Hop"):
        bad.append(f"{where} route.hops 的每一项应为 Hop(...)，实得非 Hop 调用")
        return
    kw = {k.arg: k.value for k in hop_node.keywords if k.arg}
    for field in ("enter", "expect"):
        node = kw.get(field)
        if node is None:
            bad.append(f"{where} Hop 缺少 {field}（进入本跳的点击目标 / 生效证据）")
            continue
        vals = _ast_literal(node)
        if vals is _NOT_LITERAL:
            bad.append(f"{where} Hop.{field} 含非字面量（必须是纯数据）")
            continue
        if not isinstance(vals, (list, tuple)) or not vals:
            bad.append(f"{where} Hop.{field} 必须是非空选择器列表")
            continue
        for sel in vals:
            _check_selector(sel, f"{where} Hop.{field}", bad)


def _check_route_ast(route_node, where, bad):
    """静态校验一个 `Route(...)`：`hops` 非空（到达页面至少一跳），逐跳校验。"""
    if not (isinstance(route_node, ast.Call) and isinstance(route_node.func, ast.Name)
            and route_node.func.id == "Route"):
        bad.append(f"{where} PageSpec.routes 的每一项应为 Route(...)，实得非 Route 调用")
        return
    kw = {k.arg: k.value for k in route_node.keywords if k.arg}
    hops = kw.get("hops")
    if not (isinstance(hops, (ast.List, ast.Tuple)) and hops.elts):
        bad.append(f"{where} Route.hops 必须是非空 Hop 列表（到达页面至少一跳）")
        return
    for hop_node in hops.elts:
        _check_hop_ast(hop_node, where, bad)


def check_page_spec_contract():
    """规则 24：`PageSpec` 数据契约 —— "新增平台 = 补一份数据"的门禁。

    校验形态：所有 `devices/*/apps/*.py` 里的 `PageSpec(...)` 字面量必须
      · 是**纯数据**（identity/routes/controls 均为字面量，可被静态校验）；
      · `identity` 非空（没有身份判定的页面等于不可判定"是否已在该页"）；
      · 控件名是语义名（`snake_case`，与 L3 的调用口径一致）；
      · 每个选择器 `by` 在白名单内、`value` 类型正确、选择器列表非空；
      · `routes` 的每条 `Route.hops` 非空、每跳 `enter` 非空、
        `enter`/`expect` 均为合法选择器列表（"到达页面 = 可校验的多跳路径"）。
    写错 `by`/`value` 不会报错、只会**静默永不命中**（历史上"元素定位失败"多源于此），
    因此必须在这里挡住。iOS 等新平台接入时只需补一份合法数据即可通过（无需改流程）。
    """
    bad = []
    found = 0
    for path in _iter_py_files():
        rel = _rel(path)
        if "/apps/" not in rel:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "PageSpec"):
                continue
            found += 1
            where = f"{rel}:{node.lineno}"
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            identity = kw.get("identity")
            if not (isinstance(identity, (ast.List, ast.Tuple)) and identity.elts):
                bad.append(f"{where} PageSpec.identity 必须是非空选择器列表（页面身份判定依据）")
            if identity is not None:
                id_vals = _ast_literal(identity)
                if id_vals is _NOT_LITERAL:
                    bad.append(f"{where} PageSpec.identity 含非字面量（必须是纯数据）")
                else:
                    for sel in id_vals:
                        _check_selector(sel, f"{where} identity", bad)
            routes_v = kw.get("routes")
            if routes_v is not None:
                if not isinstance(routes_v, (ast.List, ast.Tuple)):
                    bad.append(f"{where} PageSpec.routes 应为 Route 列表")
                else:
                    for route_node in routes_v.elts:
                        _check_route_ast(route_node, where, bad)
            ctl_v = kw.get("controls")
            if ctl_v is None:
                continue
            controls = _ast_literal(ctl_v)
            if controls is _NOT_LITERAL:
                bad.append(f"{where} PageSpec.controls 含非字面量（必须是纯数据）")
                continue
            for name, sels in controls.items():
                if not re.fullmatch(r"[a-z][a-z0-9_]*", str(name)):
                    bad.append(f"{where} 控件名 {name!r} 不是语义名（应为 snake_case，如 send_code）")
                if not isinstance(sels, list) or not sels:
                    bad.append(f"{where} 控件 {name!r} 的选择器必须是非空列表（顺序即优先级）")
                    continue
                for sel in sels:
                    _check_selector(sel, f"{where} controls[{name}]", bad)

    if not found:
        bad.append("未找到任何 PageSpec 声明（登录页/验证码页必须由数据描述）")

    # ── 运行时冒烟：逐个已注册描述符产出真实对象，校验"补数据即接入"这条路 ──
    # 覆盖静态检查看不到的形态（如从常量/函数拼装）。未声明 page_specs 的平台（如 iOS
    # 走 scheme 登录、无 UI 验证码登录页）**允许为空**；一旦声明了 PAGE_LOGIN，就必须
    # 备齐认证动作按语义名要用的控件，否则运行时必然定位失败（且旧行为是静默失败）。
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    try:
        from devices.interfaces.page_spec import PAGE_LOGIN, PageSpec
        from devices.registry import (all_apps, get_app_descriptor_class,
                                      get_supported_platforms_for_app)
    except Exception as e:  # noqa: BLE001 —— 导入失败一律报出
        bad.append(f"描述符冒烟导入失败：{type(e).__name__}: {e}")
        return bad

    for app_name in all_apps():
        for platform in get_supported_platforms_for_app(app_name):
            tag = f"{app_name}@{platform}"
            try:
                specs = get_app_descriptor_class(app_name, platform)().page_specs
            except Exception as e:  # noqa: BLE001 —— 实例化/取数失败即回退信号
                bad.append(f"{tag}: 描述符 page_specs 冒烟失败：{type(e).__name__}: {e}")
                continue
            if not isinstance(specs, dict):
                bad.append(f"{tag}: page_specs 应为 dict，实得 {type(specs).__name__}")
                continue
            for key, spec in specs.items():
                if not isinstance(spec, PageSpec):
                    bad.append(f"{tag}: page_specs[{key!r}] 应为 PageSpec，"
                               f"实得 {type(spec).__name__}")
                    continue
                if not spec.identity:
                    bad.append(f"{tag}: PageSpec[{key!r}] identity 为空（页面不可判定）")
                for sel in spec.identity:
                    _check_selector(sel, f"{tag}:PageSpec[{key!r}].identity", bad)
                for route in spec.routes:
                    if not route.hops:
                        bad.append(f"{tag}: PageSpec[{key!r}] 存在空 Route（到达页面至少一跳）")
                    for hop in route.hops:
                        if not hop.enter:
                            bad.append(f"{tag}: PageSpec[{key!r}] Hop.enter 为空（本跳无点击目标）")
                        if not hop.expect:
                            bad.append(f"{tag}: PageSpec[{key!r}] Hop.expect 为空（无法确认本跳生效）")
                        for sel in tuple(hop.enter) + tuple(hop.expect):
                            _check_selector(sel, f"{tag}:PageSpec[{key!r}].routes", bad)
                for ctl_name, selectors in spec.controls.items():
                    if not selectors:
                        bad.append(f"{tag}: PageSpec[{key!r}] 控件 {ctl_name!r} 选择器为空")
                    for sel in selectors:
                        _check_selector(
                            sel, f"{tag}:PageSpec[{key!r}].{ctl_name}", bad)
                if key == PAGE_LOGIN:
                    missing = [c for c in ("phone_input", "send_code", "agreement")
                               if not spec.control(c)]
                    if missing:
                        bad.append(f"{tag}: PAGE_LOGIN 缺少认证动作必需控件 {missing}"
                                   "（L3 按语义名取控件，缺一个即定位失败）")
    return bad


def main():
    list_swallow = "--list-swallow" in sys.argv
    failures = []

    bad_exit = check_no_sys_exit()
    if bad_exit:
        failures.append(
            "规则1 失败：以下模块调用了 sys.exit()（应改为 raise shared.errors 错误 / "
            "由 CLI 边界统一退出）\n  " + "\n  ".join(bad_exit)
        )

    swallows = find_silent_swallows()
    unlisted_swallows = [s for s in swallows if s[0] not in SWALLOW_ALLOWLIST]
    if unlisted_swallows:
        failures.append(
            "规则2 失败：以下模块存在 `except ...: pass` 但不在白名单内"
            "（新增吞噬须逐条定性并登记 SWALLOW_ALLOWLIST）\n  "
            + "\n  ".join(f"{rel}:{ln}" for rel, ln in sorted(unlisted_swallows))
        )
    if list_swallow:
        print(f"[swallow] 共 {len(swallows)} 处（白名单外 {len(unlisted_swallows)} 处）")
        for rel, ln in sorted(swallows):
            mark = "  " if rel in SWALLOW_ALLOWLIST else "! "
            print(f"  {mark}{rel}:{ln}")

    sccs = check_layering()
    if sccs:
        lines = ["  SCC: " + " <-> ".join(sorted(c)) for c in sccs]
        failures.append("规则3 失败：存在跨包模块级循环依赖\n" + "\n".join(lines))

    import_bad = check_all_modules_importable()
    if import_bad:
        failures.append(
            "规则4 失败：以下模块无法导入（漏再导出 / 破损导入）\n  "
            + "\n  ".join(import_bad)
        )

    bytecode_bad = check_no_bytecode_in_source_tree()
    if bytecode_bad:
        failures.append(
            "规则31 失败：源树内出现字节码缓存（零字节码应由进程入口层保证）\n  "
            + "\n  ".join(bytecode_bad)
            + "\n  提示：入口需带 `python3 -B`（或 `PYTHONDONTWRITEBYTECODE=1`）；"
              "清理：find scripts -name __pycache__ -type d -prune -exec rm -rf {} +"
        )

    del_bad = check_staged_deletions_not_referenced()
    if del_bad:
        failures.append(
            "规则5 失败：被删除的模块仍被引用（应先改完所有引用方再删）\n  "
            + "\n  ".join(del_bad)
        )

    resolve_bad = check_placeholder_resolve_single_entry()
    if resolve_bad:
        failures.append(
            "规则6 失败：resolve_placeholders 只允许在 flow_init.py 调用"
            "（steps-input 由 flow-init 统一解析并落盘，其它模块不得再各自解析）\n  "
            + "\n  ".join(resolve_bad)
        )

    layer_warn = check_layer_direction()
    if len(layer_warn) > LAYER_COUPLING_BASELINE:
        failures.append(
            f"规则7（棘轮）失败：跳层依赖 {len(layer_warn)} 处 > 基线 "
            f"{LAYER_COUPLING_BASELINE}（只许下降）"
        )
    if layer_warn:
        from collections import Counter
        pairs = Counter(w.split("  ", 1)[0] for w in layer_warn)
        print(f"⚠️ 规则7：跳层依赖 {len(layer_warn)}/{LAYER_COUPLING_BASELINE}"
              f"（棘轮基线，只许下降）")
        for pair, n in pairs.most_common():
            print(f"    {pair}  ×{n}")

    destroy_bad = check_no_device_destroy()
    if destroy_bad:
        failures.append(
            "规则8 失败：检测到设备销毁能力回归（T2：复用优先、不销毁实例）\n  "
            + "\n  ".join(destroy_bad)
        )

    edge_bad = check_forbidden_edges()
    if edge_bad:
        failures.append(
            "规则9 失败：存在硬禁止的反向依赖\n  " + "\n  ".join(edge_bad)
        )

    lease_bad = check_lease_path_single_entry()
    if lease_bad:
        failures.append(
            "规则10 失败：device_pool_leases_path 只允许在租约存储后端调用"
            "（防绕过 LeaseStore 直读写租约文件）\n  " + "\n  ".join(lease_bad)
        )

    appmock_bad = check_appmock_domain_threading() + check_appmock_contract() + check_appmock_mock_domain_isolation()
    if appmock_bad:
        failures.append(
            "规则11 失败：AppMock 代理契约（域透传 / 信封解析 / 请求形状）\n  "
            + "\n  ".join(appmock_bad)
        )

    qf_bad = check_question_framework_contract()
    if qf_bad:
        failures.append(
            "规则12 失败：Question Framework 契约（schema / driver / providers）\n  "
            + "\n  ".join(qf_bad)
        )

    sess_bad = check_device_session_isolation()
    if sess_bad:
        failures.append(
            "规则13 失败：设备会话并发隔离（禁止全量断会话 / 必须按 run 绑定会话）\n  "
            + "\n  ".join(sess_bad)
        )

    login_branch_bad = check_login_layer_platform_branch_free()
    if login_branch_bad:
        failures.append(
            "规则14 失败：登录层出现平台/设备类型分支"
            "（平台差异必须走 PlatformOps / 策略注册表）\n  "
            + "\n  ".join(login_branch_bad)
        )

    login_restart_bad = check_login_restart_declared()
    if login_restart_bad:
        failures.append(
            "规则15 失败：登录层重启未声明或重启点减少\n  "
            + "\n  ".join(login_restart_bad)
        )

    probe_bad = check_login_android_probe_frozen()
    if probe_bad:
        failures.append(
            "规则16 失败：Android 登录态探针语义被改变\n  "
            + "\n  ".join(probe_bad)
        )

    popup_bad = check_popup_single_implementation()
    if popup_bad:
        failures.append(
            "规则17 失败：弹窗消除出现第二条路径（CLI 调用）\n  "
            + "\n  ".join(popup_bad)
        )

    reason_bad = check_login_restart_reason_required()
    if reason_bad:
        failures.append(
            "规则18 失败：非 NONE 的重启未声明 restart_reason\n  "
            + "\n  ".join(reason_bad)
        )

    cache_bad = check_artifact_cache_single_entry()
    if cache_bad:
        failures.append(
            "规则19 失败：出现制品缓存的第二条访问路径\n  "
            + "\n  ".join(cache_bad)
        )

    appmock_state_bad = check_appmock_state_primitive_single_entry()
    if appmock_state_bad:
        failures.append(
            "规则20 失败：AppMock 真实状态原语被业务层直接消费"
            "（业务层请走能力位语义入口 appmock_ready()）\n  "
            + "\n  ".join(appmock_state_bad)
        )

    l3_literal_bad = check_login_action_no_platform_literal()
    if l3_literal_bad:
        failures.append(
            "规则21 失败：认证动作层出现平台/控件字面量"
            "（控件选择器必须来自 PageSpec，平台差异必须走 PlatformOps）\n  "
            + "\n  ".join(l3_literal_bad)
        )

    reconcile_bad = check_reconcile_single_entry()
    if reconcile_bad:
        failures.append(
            "规则22 失败：环境澄清出现第二个入口"
            "（业务层应走 environment_reconciler.reconcile_environment）\n  "
            + "\n  ".join(reconcile_bad)
        )

    reconcile_timing_bad = check_reconcile_after_last_restart()
    if reconcile_timing_bad:
        failures.append(
            "规则23 失败：澄清未排在最后一次重启之后（或 post 重启后未复核）\n  "
            + "\n  ".join(reconcile_timing_bad)
        )

    pagespec_bad = check_page_spec_contract()
    if pagespec_bad:
        failures.append(
            "规则24 失败：PageSpec 数据契约（身份/语义名/选择器合法性/到达路径 routes）\n  "
            + "\n  ".join(pagespec_bad)
        )

    shadow_bad = check_no_local_import_shadowing()
    if shadow_bad:
        failures.append(
            "规则25 失败：函数内 import 与模块级绑定同名"
            "（会变成局部变量 → UnboundLocalError）\n  "
            + "\n  ".join(shadow_bad)
        )

    legacy_bad = check_no_pagespec_legacy_fields()
    if legacy_bad:
        failures.append(
            "规则26 失败：访问了 PageSpec 已移除字段（导入/编译不报错，运行期才炸）\n  "
            + "\n  ".join(legacy_bad)
        )

    plat_default_bad = check_no_implicit_platform_default()
    if plat_default_bad:
        failures.append(
            "规则27 失败：platform 参数不得有默认值（隐式平台会让漏传静默走错平台）\n  "
            + "\n  ".join(plat_default_bad)
        )

    probe_reg_bad = check_platform_login_probe_registered()
    if probe_reg_bad:
        failures.append(
            "规则28 失败：白名单 platform 未在 LOGIN_STATE_PROBES 登记\n  "
            + "\n  ".join(probe_reg_bad)
        )

    clear_reprovision_bad = check_clear_data_reprovision()
    if clear_reprovision_bad:
        failures.append(
            "规则29 失败：清数据冷重启后未重建登录前置不变量（定位 + 澄清）\n  "
            + "\n  ".join(clear_reprovision_bad)
        )

    arrival_bad = check_page_arrival_uses_identity()
    if arrival_bad:
        failures.append(
            "规则30 失败：到达/停留判定用了控件选择器（应只用 PageSpec.identity）\n  "
            + "\n  ".join(arrival_bad)
        )

    if failures:
        print("❌ 架构守卫未通过：\n")
        for f in failures:
            print(f + "\n")
        return 1

    print(f"✅ 架构守卫通过"
          f"（sys.exit 违规 0；静默吞噬 {len(swallows)} 处全部白名单内；跨包循环 0；"
          f"模块导入 {len(list(_iter_py_files()))} 全通；无破损删除引用；"
          f"占位符解析单一入口 0 违规；无设备销毁回归；无反向依赖；租约访问单一入口 0 违规；"
          f"AppMock 代理契约 0 违规；Question Framework 契约 0 违规；"
          f"设备会话并发隔离 0 违规；登录层无平台分支 0 违规；"
          f"登录重启已声明且不减（基线 {RESTART_SITE_BASELINE_LOGIN_STEPS}）；"
          f"Android 探针语义锁定；弹窗消除单一实现；重启理由必填；"
          f"制品缓存单一入口；AppMock 状态原语单一消费点；"
          f"认证动作层无平台字面量；澄清单一入口且排在最后一次重启之后；"
          f"PageSpec 数据契约合法；PageSpec 已移除字段无访问残留；"
          f"platform 无隐式默认；白名单平台已注册登录态探针；"
          f"清数据冷重启后已重建登录前置不变量（定位 + 澄清）；"
          f"页面到达判定只用 identity）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
