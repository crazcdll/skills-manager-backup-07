"""Hook 渲染：模板占位符裁剪、hook 实例规范化、hook-info CLI 提示渲染。"""
import string
from execution.engine.sop.hook_templates import get_hook_template
from shared.workspace import render_text


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
def _format_track_candidates(candidates, limit=10):
    """埋点候选事件清单（精简）。

    数据源：断言层写入 track_fields.candidates 的精简清单（index/nm/val_bid）。
    完整字段在 track_candidates_<sid>.json，由 hook 指引 AI read_file —— 这里只给
    判别用的最小信息，避免多候选详情把 flow-context.json 撑大。
    """
    if not candidates:
        return "   （唯一命中，无需选择）"
    lines = []
    for c in candidates[:limit]:
        lines.append(
            f"   [{c.get('index')}] nm={c.get('nm') or '-'} "
            f"val_bid={c.get('val_bid') or '(无)'}"
        )
    if len(candidates) > limit:
        lines.append(f"   … 其余 {len(candidates) - limit} 条见候选人文件")
    return "\n".join(lines)


def _element_catalog_block(path):
    """元素目录证据块 —— 统一挂载到所有「需 AI 定位 / 选择元素」的 hook。

    元素目录（`element_index_{sid}.catalog.md`，由 execution.screen.tree_index.dump_index
    统一落盘）是 AI 侧定位元素的**唯一权威视图**。这里由渲染层集中追加，
    模板不再各自声明 {element_index_path} 占位符 —— 避免个别模板漏挂导致 AI 拿不到
    结构视图树，只能重新采集 / 重新分析（"说没有 → 重采" 的根因）。

    只要 hook 携带 element_index_path（由 handler 落盘后经 router 透传），
    其指引末尾必带本块；无目录的 hook（如设备级失败）不受影响。
    """
    return (
        "\n\n📐 元素目录（页面全量节点 + 视口分区 + center 坐标；AI 定位元素的唯一权威视图）：\n"
        f"   {path}\n"
        "   用 read_file 直接读取，扫「文案」列做语义匹配即可；不要另行 inspect-tree 重新采集。"
    )


def render_hook_cli_hint(hook, sid):
    """按需渲染 hook 的 cli_hint：模板 + hint_params → 完整提示文本。

    hook 实例（flow-context 持久化侧）只携带 id/hint_params，不含 cli_hint 全文；
    本函数是唯一的渲染入口，查询时现场拼接，并替换 {sid} 占位符。

    元素目录证据块在此集中追加（见 _element_catalog_block），模板正文不再重复引用。
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
    element_index = params.get("element_index_path")
    if element_index:
        rendered += _element_catalog_block(element_index)
    # 提示文本里的引擎调用统一渲染为 workspace 入口（唯一出口，见 shared/workspace.py）
    return render_text(rendered).split("\n")
