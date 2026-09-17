"""Hook 渲染：模板占位符裁剪、hook 实例规范化、hook-info CLI 提示渲染。"""
import string
from core.sop.hook_templates import get_hook_template


def _hook_closing(hook_id):
    """统一的 hook 收尾指令（标记完成）——避免各模板手工拼写 hook id。"""
    return ("\n"
            "4️⃣ 标记完成\n"
            f"   python3 scripts/cli.py flow-next --done-hooks {hook_id}")
def _template_fields(text):
    """提取模板里真正用到的 {name} 占位符（忽略 {{ }} 转义与位置参数）。

    用途：为每个 hook 裁剪 hint_params，保证「模板占位符 ⇔ hint_params」严格一致。
    如果模板引用了未提供的参数，render_hook_cli_hint 的 .format() 会整体抛错并
    回退为未渲染原文（带花括号的模板原文对 AI 完全不可读），这是必须从根上避免的。
    """
    names = set()
    for _literal, field_name, _spec, _conv in string.Formatter().parse(text or ""):
        if field_name:
            names.add(field_name.split(".")[0].split("[")[0])
    return names
def _select_params(cli_hint, values):
    """按模板实际占位符裁剪参数，返回 (params, missing)。

    missing 非空意味着模板与调用方不一致（编码错误），用可读占位串显式暴露，
    而不是让整段提示静默回退为未渲染原文。
    """
    params = {}
    missing = []
    for name in sorted(_template_fields(cli_hint)):
        if name == "sid":
            continue
        if name in values and values[name] not in (None, ""):
            params[name] = values[name]
        elif name in values:
            params[name] = values[name]
        else:
            params[name] = f"(缺少参数 {name})"
            missing.append(name)
    return params, missing
def _finalize_hooks(hooks):
    """hook 实例持久化前的规范化：剥离 cli_hint 全文，只保留 hint_params。

    hook 落盘字段：id / desc / required / hint_params（运行时参数 dict）。
    cli_hint 全文在查询时由 render_hook_cli_hint 用模板 + hint_params 现场渲染，
    避免 flow-context.json 膨胀与同一文本的多次重复打印。
    """
    for h in hooks:
        h.pop("cli_hint", None)
    return hooks
def _build_expected_fields_list(expected_fields, is_api=True):
    """构建待校验字段清单的格式化字符串。"""
    if not expected_fields:
        return "   (无待校验字段)"
    lines = []
    if is_api:
        # API 模式：expected_fields 是 [{"source":"request","field":"name","expected":"value"}, ...]
        for i, item in enumerate(expected_fields, 1):
            source = item.get("source", "?")
            field = item.get("field", "?")
            exp = item.get("expected", "?")
            lines.append(f"   [{i}] source={source} field={field} expected={exp}")
    else:
        # Track 模式：expected_fields 是 {"field_name": "expected_value", ...}
        for i, (field, exp) in enumerate(expected_fields.items(), 1):
            lines.append(f"   [{i}] field={field} expected={exp}")
    return "\n".join(lines)
def render_hook_cli_hint(hook, sid):
    """按需渲染 hook 的 cli_hint：模板 + hint_params → 完整提示文本。

    hook 实例（flow-context 持久化侧）只携带 id/hint_params，不含 cli_hint 全文；
    本函数是唯一的渲染入口，查询时现场拼接，并替换 {sid} 占位符。
    """
    hook_id = hook.get("id", "")
    params = dict(hook.get("hint_params") or {})
    tmpl = get_hook_template(hook_id)
    raw = tmpl.get("cli_hint", "") if tmpl else hook.get("cli_hint", "")
    if not raw:
        return []
    try:
        rendered = raw.format(sid="{sid}", **params)
    except (KeyError, IndexError, ValueError):
        rendered = raw  # 模板含非常规花括号（如 JSON 示例）→ 跳过参数填充，仅替换 sid
    rendered = rendered.replace("{sid}", sid)
    return rendered.split("\n")
