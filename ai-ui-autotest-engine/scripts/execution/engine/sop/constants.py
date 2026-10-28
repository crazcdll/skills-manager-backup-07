"""SOP 通用常量：flow-context 文件名、断言判定规则。

环境类型映射（env.type ↔ env_name）的事实来源在
environment.validators.env_validator（ENV_TYPE_MAP / ENV_NAME_TO_TYPE），
本模块不再重复声明类型名，避免新增环境类型时漂移。
"""


FLOW_CONTEXT_FILENAME = "flow-context.json"

# ═══════════════════════════════════════════════════════════════════
# 收尾清理序列 —— 唯一声明源
# ═══════════════════════════════════════════════════════════════════
# 正常收尾阶段 T2_cleanup（本层 stages.py）与异常终止路径
# （上层 flow/lifecycle/fail.py::_run_cleanup）**共用本序列**。
#
# 历史上两处各自声明一份：T2 有 `device release`，而 abort 路径漏掉，导致每次
# `flow-fail --cleanup` 都泄漏一个设备租约（占用设备池直到租约过期，且 post-clean
# 已抹掉 active_run，使事后手动 `device release` 也无从定位 owner）。把序列收敛到
# 此一处后，任一消费者都不可能再漏步骤。
#
# ⚠️ 顺序不变式：`device release` 必须排在 `post-clean` 之前。
#    post-clean = 删除本 workspace 工作区与入口（含 active_run 指针），而 device release 依赖
#    active_run 定位本 run 的租约 owner；一旦先 post-clean，归还租约将因 owner 为空
#    而静默失败（released=0）。
CLEANUP_CMDS = (
    "python3 scripts/cli.py mock record-stop",
    "python3 scripts/cli.py mock reset-env",
    # 会话回收必须先于租约归还：disconnect 依赖 flow-context 的 session_id，
    # 而 release 之后设备可能被其他 run 领走，再断会话会误伤对方。
    # 忘记断开会让 ~/.imeituan/sessions 累积 pid=0 残留，污染后续注册
    # （legacy 记录 → ADB_SERVER_LEGACY_IDENTITY_UNKNOWN）。
    "python3 scripts/cli.py device disconnect",
    "python3 scripts/cli.py device release",
    "python3 scripts/cli.py mis release",
    "python3 scripts/cli.py flow-finalize",
)
# post-clean 单独声明：终止路径在「证据尚未落盘」时需跳过它以保住本 workspace 现场。
POST_CLEAN_CMD = "python3 scripts/cli.py post-clean"
# ═══════════════════════════════════════════════════════════════════
# 断言判定口径 —— 唯一声明（desc / cli_hint / 报告 / 文档共用同一份表述）
# ═══════════════════════════════════════════════════════════════════
# result 与 verdict 是两个正交维度：result = 判成什么，verdict = 怎么判出来的。
# 形态差异（截断/省略/跨节点拆分/全半角差异/子串）一律归入 pass + semantic，
# 与 tap 侧「action_arg 与页面节点不完全一致」的处理保持同一口径。
ASSERTION_VERDICT_RULES = (
    "判定口径（result = 判成什么，verdict = 怎么判出来的），按断言自己的 match 选方向：\n"
    "  match=present（期望出现）\n"
    "   result=pass, verdict=exact    —— 页面文案与 expect 完全一致\n"
    "   result=pass, verdict=semantic —— 形态差异但语义等价：截断/省略/跨节点拆分/"
    "空白或全半角差异，或 expect 是页面复合文案的子串\n"
    "   result=fail                   —— 文案不存在，或语义不等价\n"
    "  match=gone（期望消失，方向相反）\n"
    "   result=pass, verdict=exact    —— 页面已完全找不到 expect（含子串形态）\n"
    "   result=fail                   —— expect 仍以任何形态存在，reason 写清实测值"
)
_ASSERTION_WRITE_ONCE = (
    "   ⚠️ 一个步骤的所有断言（text + visual）只写一次 override：两个 hook\n"
    "      共用同一份 --assert-verdict，逐条按 id 给出 result / verdict。\n"
    "   ⚠️ 断言判定是步骤结论的唯一依据：全部 pass 才可 --pass，有任意 result=fail\n"
    "      则必须 --fail，不得出现「断言失败但步骤通过」。\n"
    "   ⚠️ result=fail 时必须在 reason 写清「实测值 vs 期望（expect / criteria）」。"
)
