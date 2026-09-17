"""SOP 通用常量：flow-context 文件名、断言判定规则。

环境类型映射（env.type ↔ env_name）的事实来源在
environment.validators.env_validator（ENV_TYPE_MAP / ENV_NAME_TO_TYPE），
本模块不再重复声明类型名，避免新增环境类型时漂移。
"""


FLOW_CONTEXT_FILENAME = "flow-context.json"
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
