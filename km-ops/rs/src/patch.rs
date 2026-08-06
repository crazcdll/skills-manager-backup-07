use std::collections::HashMap;
use serde_json::{json, Value};
use uuid::Uuid;
use crate::parse::{parse_inline, unesc};

fn nid() -> String {
    Uuid::new_v4().to_string().replace('-', "")
}

// ── 构建 PM 节点（支持所有学城节点类型）──────────────────────────────────────

/// 从 HTML 属性中提取对齐方式，用于回写 PM attrs.align。
/// 优先读 `align` 属性，其次从 `style` 中解析 `text-align: x`。
/// "" / "left" 视为默认，返回 None（不写入 align）。
fn extract_align(attrs: &HashMap<String, String>) -> Option<String> {
    let mut align: Option<String> = attrs.get("align").map(|s| s.trim().to_lowercase());
    if align.as_deref().map_or(true, |s| s.is_empty()) {
        // align 为空或不存在时，回退到 style 中的 text-align
        if let Some(style) = attrs.get("style") {
            for decl in style.split(';') {
                let decl = decl.trim();
                if let Some(rest) = decl.strip_prefix("text-align") {
                    let val = rest.trim_start_matches([' ', ':']).trim().to_lowercase();
                    align = if val.is_empty() { None } else { Some(val) };
                    break;
                }
            }
        } else {
            align = None;
        }
    }
    match align.as_deref() {
        None | Some("") | Some("left") => None,
        // 白名单放行合法对齐值；未知值忽略，不写入 align
        Some(v @ ("center" | "right" | "justify" | "start" | "end")) => Some(v.to_string()),
        Some(_) => None,
    }
}

pub fn build_pm_node(tag: &str, attrs: &HashMap<String, String>, inner_html: &str) -> Option<Value> {
    let tag_lower = tag.to_lowercase();
    match tag_lower.as_str() {
        // ── 标题节点
        "h1" => Some(json!({ "type": "title", "attrs": { "nodeId": nid() }, "content": parse_inline(inner_html) })),
        "h2" | "h3" | "h4" | "h5" | "h6" => {
            let level: u64 = tag_lower[1..].parse().unwrap_or(2);
            let align = extract_align(attrs).unwrap_or_default();
            let pm_attrs = json!({
                "level": level,
                "align": align,
                "indent": 0,
                "dataDiffId": Value::Null,
                "nodeId": nid()
            });
            Some(json!({ "type": "heading", "attrs": pm_attrs, "content": parse_inline(inner_html) }))
        }

        // ── 段落和块级
        "p" => {
            let align = extract_align(attrs).unwrap_or_default();
            let pm_attrs = json!({ "indent": 0, "align": align, "dataDiffId": Value::Null, "nodeId": nid() });
            let mut node = json!({ "type": "paragraph", "attrs": pm_attrs });
            let content = parse_inline(inner_html);
            if !content.is_empty() { node["content"] = Value::Array(content); }
            Some(node)
        }
        "blockquote" => {
            let children = build_block_nodes(inner_html);
            let content = if children.is_empty() {
                vec![json!({"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":Value::Null,"nodeId":nid()},"content":[]})]
            } else {
                children
            };
            Some(json!({ "type": "blockquote", "attrs": { "dataDiffId": Value::Null, "nodeId": nid() }, "content": content }))
        }
        "hr" => Some(json!({ "type": "horizontal_rule", "attrs": { "dataDiffId": Value::Null, "nodeId": nid() } })),

        // ── 列表容器
        "ul" => {
            let is_task = attrs.get("class").map(|c| c.contains("task-list")).unwrap_or(false);
            if is_task {
                Some(json!({ "type": "task_list", "attrs": { "dataDiffId": Value::Null, "indent": 0, "nodeId": nid() }, "content": build_task_items(inner_html) }))
            } else {
                Some(json!({ "type": "bullet_list", "attrs": { "dataDiffId": Value::Null, "indent": 0, "nodeId": nid() }, "content": build_list_items(inner_html) }))
            }
        }
        "ol" => Some(json!({ "type": "ordered_list", "attrs": { "dataDiffId": Value::Null, "indent": 0, "nodeId": nid() }, "content": build_list_items(inner_html) })),
        "li" => {
            let inner_para = json!({ "type": "paragraph", "attrs": {"indent":0,"align":"","dataDiffId":Value::Null,"nodeId":nid()}, "content": parse_inline(inner_html) });
            Some(json!({ "type": "list_item", "attrs": { "dataListItemDiffId": Value::Null, "fontSize": Value::Null, "hidden": false, "level": 0, "nodeId": nid(), "value": Value::Null }, "content": [inner_para] }))
        }

        // ── 代码块
        "pre" => {
            let lang = attrs.get("language").or_else(|| attrs.get("data-language")).cloned().unwrap_or_else(|| "Plain Text".into());
            let code_match = extract_code_from_pre(inner_html);
            let code = if !code_match.is_empty() { unesc(&code_match) } else { unesc(inner_html) };
            Some(json!({
                "type": "code_block",
                "attrs": { "language": lang, "title": "代码块", "theme": "xq-light", "nodeId": nid() },
                "content": if code.is_empty() { json!([]) } else { json!([{ "type": "text", "text": code }]) }
            }))
        }

        // ── 表格
        "table" => Some(json!({ "type": "table", "attrs": { "nodeId": nid(), "dataDiffId": Value::Null, "indent": 0 }, "content": build_table_rows(inner_html) })),
        "tr" => build_table_row(inner_html),
        "td" | "th" => {
            let pm_type = if tag_lower == "td" { "table_cell" } else { "table_header" };
            let mut content = build_block_nodes(inner_html);
            if content.is_empty() {
                content.push(json!({"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":Value::Null,"nodeId":nid()},"content":[]}));
            }
            Some(json!({ "type": pm_type, "attrs": { "nodeId": nid(), "colspan": 1, "rowspan": 1, "numCell": Value::Null, "bgColor": Value::Null, "color": Value::Null, "textAlign": Value::Null, "verticalAlign": Value::Null }, "content": content }))
        }

        // ── 图片
        "img" => Some(json!({
            "type": "image",
            "attrs": {
                "src": attrs.get("src").cloned().unwrap_or_default(),
                "name": attrs.get("alt").or_else(|| attrs.get("name")).cloned().unwrap_or_default(),
                "width": attrs.get("width").and_then(|v| v.parse::<f64>().ok()),
                "height": attrs.get("height").and_then(|v| v.parse::<f64>().ok()),
            }
        })),

        // ── 富媒体节点
        "km-drawio" => Some(json!({
            "type": "drawio",
            "attrs": {
                "src": attrs.get("src").cloned().unwrap_or_default(),
                "width": attrs.get("width").and_then(|v| v.parse::<f64>().ok()),
                "height": attrs.get("height").and_then(|v| v.parse::<f64>().ok()),
            }
        })),
        "km-video" | "km-audio" => {
            let pm_type = if tag_lower == "km-video" { "video" } else { "audio" };
            Some(json!({
                "type": pm_type,
                "attrs": {
                    "url": attrs.get("src").or_else(|| attrs.get("url")).cloned().unwrap_or_default(),
                    "name": attrs.get("name").cloned().unwrap_or_default(),
                    "nodeId": nid(),
                }
            }))
        }
        "km-attachment" => Some(json!({
            "type": "attachment",
            "attrs": {
                "name": attrs.get("name").cloned().unwrap_or_default(),
                "src": attrs.get("src").cloned().unwrap_or_default(),
                "size": attrs.get("size").and_then(|v| v.parse::<f64>().ok()),
            }
        })),
        "km-xtable" => Some(json!({
            "type": "xtable",
            "attrs": { "xtableId": attrs.get("xtable-id").cloned().unwrap_or_default() }
        })),
        "km-minder" => Some(json!({ "type": "minder", "attrs": {} })),
        "km-plantuml" => Some(json!({ "type": "plantuml", "attrs": {} })),
        "km-latex" => {
            let text = unesc(inner_html);
            Some(json!({ "type": "latex_block", "attrs": {}, "content": [{ "type": "text", "text": text }] }))
        }

        // ── 框体节点（km-note 和 km-collapse）
        "km-note" => {
            let note_type = attrs.get("type").cloned().unwrap_or_else(|| "info".into());
            build_note_node(inner_html, &note_type)
        }
        "km-collapse" => build_collapse_node(inner_html),

        // ── 目录 / 脚注（保留原始结构，不进行内容重建）
        "km-catalog" => Some(json!({
            "type": "catalog",
            "attrs": { "dataDiffId": Value::Null, "nodeId": nid(), "style": "none" }
        })),
        "km-footnote-list" => Some(json!({
            "type": "footnote_list",
            "attrs": { "nodeId": nid() }
        })),

        // ── 不支持的标签
        _ => None,
    }
}

/// 从 <pre><code>...</code></pre> 中提取代码内容
fn extract_code_from_pre(html: &str) -> String {
    if let Some(start) = html.find("<code") {
        if let Some(content_start) = html[start..].find('>') {
            let code_start = start + content_start + 1;
            if let Some(code_end) = html[code_start..].find("</code>") {
                return html[code_start..code_start + code_end].to_string();
            }
        }
    }
    html.to_string()
}

/// 把块级 HTML 解析成 PM 节点列表（用于 blockquote/note/collapse 等容器的 body）
/// 比 parse_inline 正确：能保留 ul/ol/table/p 等块级结构
fn build_block_nodes(html: &str) -> Vec<Value> {
    let nodes = crate::myers::parse_nodes(html);
    let mut result: Vec<Value> = nodes.iter()
        .filter_map(|n| build_pm_node(&n.tag, &n.attrs, &n.inner_html))
        .collect();
    if result.is_empty() && !html.trim().is_empty() {
        // fallback: 纯文本/行内内容，包一个 paragraph
        result.push(json!({"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":Value::Null,"nodeId":nid()},"content":parse_inline(html.trim())}));
    }
    result
}

/// 构建任务列表项数组（task_item）
/// <li><input type="checkbox" checked/>text</li> → task_item {checked: true/false}
fn build_task_items(html: &str) -> Vec<Value> {
    extract_tag_children(html, &["li"])
        .into_iter()
        .map(|(_, inner)| {
            // 检测是否有选中的 checkbox
            let checked = if inner.contains("type=\"checkbox\" checked") || inner.contains("type='checkbox' checked") {
                true
            } else {
                false
            };
            // 去除 checkbox 本身，保留文本内容
            let text_html = inner
                .replacen("<input type=\"checkbox\" checked/>", "", 1)
                .replacen("<input type=\"checkbox\"/>", "", 1)
                .replacen("<input type=\"checkbox\" checked>", "", 1)
                .replacen("<input type=\"checkbox\">", "", 1);
            let mut content = build_block_nodes(text_html.trim());
            if content.is_empty() {
                content.push(json!({"type":"paragraph","attrs":{"indent":0,"align":"left","dataDiffId":Value::Null,"nodeId":nid()},"content":[]}));
            }
            json!({
                "type": "task_item",
                "attrs": {
                    "checked": checked,
                    "dataListItemDiffId": Value::Null,
                    "fontSize": Value::Null,
                    "level": 0,
                    "nodeId": nid()
                },
                "content": content
            })
        })
        .collect()
}

/// 构建列表项数组
/// 用 build_block_nodes 处理 li 内容，支持复杂列表项（内含 km-collapse / table / p 等块级元素）
fn build_list_items(html: &str) -> Vec<Value> {
    extract_tag_children(html, &["li"])
        .into_iter()
        .map(|(_, inner)| {
            let mut content = build_block_nodes(&inner);
            // 空 li：插入一个带 nodeId 的空段落
            if content.is_empty() {
                content.push(json!({"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":Value::Null,"nodeId":nid()},"content":[]}));
            }
            json!({ "type": "list_item", "attrs": { "dataListItemDiffId": Value::Null, "fontSize": Value::Null, "hidden": false, "level": 0, "nodeId": nid(), "value": Value::Null }, "content": content })
        })
        .collect()
}

/// 构建表格行数组（用 parse_nodes 保留 tr attrs）
fn build_table_rows(html: &str) -> Vec<Value> {
    crate::myers::parse_nodes(html).into_iter()
        .filter(|n| n.tag == "tr")
        .filter_map(|n| build_table_row_from_cells(&n.inner_html))
        .collect()
}

/// 从 CSS style 字符串中提取指定属性值。
/// 例如 extract_style_prop("width:96px;background-color:red", "width") → Some("96px")
fn extract_style_prop<'a>(style: &'a str, prop: &str) -> Option<&'a str> {
    for decl in style.split(';') {
        let decl = decl.trim();
        if let Some(rest) = decl.strip_prefix(prop) {
            let val = rest.trim_start_matches([' ', ':']).trim();
            if !val.is_empty() { return Some(val); }
        }
    }
    None
}

/// 构建单个表格行（用 parse_nodes 保留 td/th 的 colspan/rowspan/colwidth/bgColor）
fn build_table_row_from_cells(html: &str) -> Option<Value> {
    let cells: Vec<Value> = crate::myers::parse_nodes(html).into_iter()
        .filter(|n| n.tag == "td" || n.tag == "th")
        .map(|n| {
            let cell_type = if n.tag == "th" { "table_header" } else { "table_cell" };
            let colspan = n.attrs.get("colspan").and_then(|v| v.parse::<u64>().ok()).unwrap_or(1);
            let rowspan = n.attrs.get("rowspan").and_then(|v| v.parse::<u64>().ok()).unwrap_or(1);
            let mut attrs = serde_json::Map::new();
            attrs.insert("nodeId".into(), json!(nid()));
            attrs.insert("colspan".into(), json!(colspan));
            attrs.insert("rowspan".into(), json!(rowspan));
            attrs.insert("numCell".into(), Value::Null);
            attrs.insert("bgColor".into(), Value::Null);
            attrs.insert("color".into(), Value::Null);
            attrs.insert("textAlign".into(), Value::Null);
            attrs.insert("verticalAlign".into(), Value::Null);
            // data-colwidth="99,99,122" 存多值（colspan > 1），优先于 style width
            if let Some(dw) = n.attrs.get("data-colwidth") {
                let vals: Vec<u64> = dw.split(',')
                    .filter_map(|s| s.trim().parse::<u64>().ok())
                    .collect();
                if !vals.is_empty() {
                    attrs.insert("colwidth".into(), json!(vals));
                }
            } else if let Some(style) = n.attrs.get("style") {
                // 没有 data-colwidth 时从 width:Xpx 提取单列宽
                if let Some(width_str) = extract_style_prop(style, "width") {
                    if let Some(w) = width_str.trim_end_matches("px").trim().parse::<u64>().ok() {
                        attrs.insert("colwidth".into(), json!([w]));
                    }
                }
            }
            // bgColor / verticalAlign / color (字体色) 从 style 提取（覆盖上面设置的 null）
            if let Some(style) = n.attrs.get("style") {
                if let Some(bg) = extract_style_prop(style, "background-color") {
                    attrs.insert("bgColor".into(), json!(bg));
                }
                if let Some(va) = extract_style_prop(style, "vertical-align") {
                    attrs.insert("verticalAlign".into(), json!(va));
                }
                if let Some(fc) = extract_style_prop(style, "color") {
                    attrs.insert("color".into(), json!(fc));
                }
            }
            {
                let mut content = build_block_nodes(&n.inner_html);
                if content.is_empty() {
                    content.push(json!({"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":Value::Null,"nodeId":nid()},"content":[]}));
                }
                json!({ "type": cell_type, "attrs": attrs, "content": content })
            }
        })
        .collect();
    if cells.is_empty() { return None; }
    Some(json!({ "type": "table_row", "attrs": { "nodeId": nid(), "dataRowDiffId": Value::Null }, "content": cells }))
}

/// 兼容旧调用（patch.rs 内部 apply_change_to_node 用）
fn build_table_row(html: &str) -> Option<Value> {
    build_table_row_from_cells(html)
}

/// 从 `<summary>…</summary><div>…</div>` 结构中提取 body：
/// 1. 跳过 `</summary>`（即使 summary 为空也跳过，修复空 summary 时 body 包含 summary 标签的 bug）
/// 2. 剥掉 render 加的 `<div>…</div>` 外壳，返回其内部 HTML
fn extract_body_html(html: &str) -> String {
    let after_summary = if let Some(pos) = html.find("</summary>") {
        html[pos + 10..].trim()
    } else {
        html.trim()
    };
    // 剥掉 <div>…</div> wrapper（render 给 note_content/collapse_content 加的）
    let inner = after_summary;
    if inner.starts_with("<div") {
        if let Some(gt) = inner.find('>') {
            let content_start = gt + 1;
            let content = if let Some(end) = inner.rfind("</div>") {
                &inner[content_start..end]
            } else {
                &inner[content_start..]
            };
            return content.to_string();
        }
    }
    inner.to_string()
}

/// 构建 note 节点（必须包含 title 和 content）
fn build_note_node(html: &str, note_type: &str) -> Option<Value> {
    let (title_text, align) = extract_summary_tag(html);
    let body_html = extract_body_html(html);
    let paragraphs = build_block_nodes(&body_html);

    let align_val = align.unwrap_or_default();
    let title = json!({
        "type": "note_title",
        "attrs": { "align": align_val, "nodeId": nid() },
        "content": parse_inline(&title_text)
    });

    Some(json!({
        "type": "note",
        "attrs": { "dataDiffId": Value::Null, "hiddenTitle": false, "nodeId": nid(), "type": note_type },
        "content": [
            title,
            { "type": "note_content", "attrs": { "nodeId": nid() }, "content": paragraphs }
        ]
    }))
}

/// 构建 collapse 节点
fn build_collapse_node(html: &str) -> Option<Value> {
    let (title_text, align) = extract_summary_tag(html);
    let body_html = extract_body_html(html);
    let paragraphs = build_block_nodes(&body_html);

    let align_val = align.unwrap_or_else(|| "left".to_string());
    let title = json!({
        "type": "collapse_title",
        "attrs": { "align": align_val, "nodeId": nid() },
        "content": parse_inline(&title_text)
    });

    Some(json!({
        "type": "collapse",
        "attrs": { "active": false, "dataDiffId": Value::Null, "id": Uuid::new_v4().to_string(), "nodeId": nid() },
        "content": [
            title,
            { "type": "collapse_content", "attrs": { "nodeId": nid() }, "content": paragraphs }
        ]
    }))
}

/// 从 HTML 中提取 <summary> 标签内容与对齐属性。
/// 支持 <summary> 和带属性的 <summary style="..."> / <summary align="...">。
/// 返回 (内部 HTML 文本, 对齐值或 None)。
fn extract_summary_tag(html: &str) -> (String, Option<String>) {
    // 找到 <summary 后必须是 '>' 或空白，才算是 summary 开标签
    if let Some(start) = html.find("<summary") {
        let after = start + "<summary".len();
        if after < html.len() && matches!(html.as_bytes()[after], b'>' | b' ' | b'/') {
            // 开标签到 '>'
            if let Some(gt) = html[after..].find('>') {
                let open_tag_end = after + gt + 1;
                let open_tag = &html[start..open_tag_end];
                let attrs_str = &open_tag["<summary".len()..open_tag.len() - 1];
                let summary_attrs = crate::parse::parse_attrs(attrs_str.trim());
                let align = extract_align(&summary_attrs);
                let close = "</summary>";
                if let Some(end) = html[open_tag_end..].find(close) {
                    let inner = html[open_tag_end..open_tag_end + end].to_string();
                    return (inner, align);
                }
                return (String::new(), align);
            }
        }
    }
    (String::new(), None)
}

/// 从 HTML 字符串中提取直接子标签及其内容
fn extract_tag_children(html: &str, tags: &[&str]) -> Vec<(String, String)> {
    let mut results = Vec::new();
    let mut pos = 0;

    while pos < html.len() {
        let mut found = false;
        for tag in tags {
            let open_tag = format!("<{}", tag);
            if let Some(idx) = html[pos..].find(&open_tag) {
                let actual_pos = pos + idx;
                if let Some(tag_end_offset) = html[actual_pos..].find('>') {
                    let tag_end = actual_pos + tag_end_offset + 1;
                    let close_tag = format!("</{}>", tag);
                    let mut depth = 1;
                    let mut search_pos = tag_end;
                    let mut inner_end = None;

                    while search_pos < html.len() && depth > 0 {
                        let next_open = html[search_pos..].find(&open_tag).map(|i| search_pos + i);
                        let next_close = html[search_pos..].find(&close_tag).map(|i| search_pos + i);

                        match (next_open, next_close) {
                            (Some(o), Some(c)) if o < c => {
                                depth += 1;
                                search_pos = o + 1;
                            }
                            (_, Some(c)) => {
                                depth -= 1;
                                if depth == 0 {
                                    inner_end = Some(c);
                                }
                                search_pos = c + 1;
                            }
                            (_, None) => break,
                        }
                    }

                    if let Some(end) = inner_end {
                        let inner = html[tag_end..end].to_string();
                        results.push((tag.to_string(), inner));
                        pos = end + close_tag.len();
                        found = true;
                        break;
                    }
                }
            }
        }
        if !found {
            pos += 1;
        }
    }

    results
}

// ── applyDiff ─────────────────────────────────────────────────────────────────

pub fn apply_diff(pm_doc: &Value, diff_result: &crate::diff::DiffResult) -> Value {
    let mut doc = pm_doc.clone();

    // 1. Handle changes: use nodeId when available, otherwise fall back to positional matching
    for change in &diff_result.changed {
        if change.pm_node_id.is_some() {
            apply_change_recursive(&mut doc, change);
        } else if let Some(content_arr) = doc.get_mut("content").and_then(|v| v.as_array_mut()) {
            // No nodeId: match by old_idx position
            if let Some(idx) = change.old_idx {
                if idx < content_arr.len() {
                    apply_change_to_node(&mut content_arr[idx], change);
                }
            }
        }
    }

    // 2. Handle deletes: by nodeId when available, by old_idx position when not
    for del in &diff_result.deleted {
        if let Some(id) = &del.pm_node_id {
            delete_by_node_id(&mut doc, id);
        } else if let Some(arr) = doc.get_mut("content").and_then(|v| v.as_array_mut()) {
            if let Some(idx) = del.old_idx {
                // Delete at the specific position
                if idx < arr.len() {
                    arr.remove(idx);
                }
            } else if !arr.is_empty() {
                // Fallback: remove last element (for backward compat)
                arr.pop();
            }
        }
    }

    // 3. Handle adds at root level
    if let Some(arr) = doc.get_mut("content").and_then(|v| v.as_array_mut()) {
        for add in &diff_result.added {
            if let Some(mut new_node) = crate::patch::build_pm_node(&add.tag, &add.attrs, &add.inner_html) {
                // 文档只能有一个 title 节点（服务端 schema 约束）。
                // 若已存在 title 且新增节点也是 title（源文档用 <h1> 作章节标题），
                // 降级为 heading level 1 以避免服务端静默拒绝写入。
                let already_has_title = arr.iter().any(|n| {
                    n.get("type").and_then(|v| v.as_str()) == Some("title")
                });
                if already_has_title && new_node.get("type").and_then(|v| v.as_str()) == Some("title") {
                    new_node["type"] = serde_json::Value::String("heading".to_string());
                    new_node["attrs"] = serde_json::json!({ "level": 1 });
                }
                let terminal_pos = arr.iter().rposition(|n| {
                    matches!(n.get("type").and_then(|v| v.as_str()), Some("footnote_list"))
                });
                if let Some(pos) = terminal_pos {
                    arr.insert(pos, new_node);
                } else {
                    arr.push(new_node);
                }
            }
        }
    }

    doc
}

fn delete_by_node_id(node: &mut Value, node_id: &str) -> bool {
    if let Some(content_arr) = node.get_mut("content").and_then(|v| v.as_array_mut()) {
        if let Some(pos) = content_arr.iter().position(|n| {
            n.get("attrs").and_then(|a| a.get("nodeId")).and_then(|v| v.as_str()) == Some(node_id)
        }) {
            content_arr.remove(pos);
            return true;
        }
        // Need to collect indices to avoid borrow issues
        let len = content_arr.len();
        for i in 0..len {
            // Get mutable reference via index each iteration
            if let Some(child) = content_arr.get_mut(i) {
                if delete_by_node_id(child, node_id) {
                    return true;
                }
            }
        }
    }
    false
}

fn apply_change_recursive(node: &mut Value, change: &crate::diff::ChangeOp) {
    // First try to match by nodeId if provided
    if let Some(node_id) = &change.pm_node_id {
        if node.get("attrs").and_then(|a| a.get("nodeId")).and_then(|v| v.as_str()) == Some(node_id) {
            apply_change_to_node(node, change);
            return;
        }
    }

    // Recursively search in children
    if let Some(content_arr) = node.get_mut("content").and_then(|v| v.as_array_mut()) {
        for child in content_arr.iter_mut() {
            apply_change_recursive(child, change);
        }
    }
}

fn is_deep_container(pm_type: &str) -> bool {
    matches!(pm_type,
        "blockquote" | "note" | "note_content" | "collapse" | "collapse_content" |
        "table" | "table_row" | "bullet_list" | "ordered_list" | "list"
    )
}

fn apply_change_to_node(node: &mut Value, change: &crate::diff::ChangeOp) {
    // Handle type change: replace entire node but preserve nodeId
    if change.type_changed {
        let node_id = node.get("attrs").and_then(|a| a.get("nodeId")).and_then(|v| v.as_str()).map(String::from);
        if let Some(mut new_node) = build_pm_node(&change.tag, &change.attrs, &change.inner_html) {
            if let Some(id) = node_id {
                match new_node.get_mut("attrs") {
                    Some(a) if a.is_object() => { a["nodeId"] = serde_json::Value::String(id); }
                    _ => { new_node["attrs"] = serde_json::json!({"nodeId": id}); }
                }
            }
            *node = new_node;
        }
        return;
    }

    let pm_type = node.get("type").and_then(|v| v.as_str()).unwrap_or("").to_string();

    // Deep containers: recursively diff inner HTML and patch
    if is_deep_container(&pm_type) {
        let temp_doc = serde_json::json!({"type": "doc", "content": node["content"].clone()});
        let old_inner = crate::render::render(&temp_doc).html;
        let new_inner = &change.inner_html;
        let inner_diff = crate::diff::diff(&old_inner, new_inner, node);
        let updated = apply_diff(node, &inner_diff);
        *node = updated;
        return;
    }

    // Terminal containers (table_cell, table_header, list_item): rebuild content from inner_html
    // These typically have no nodeIds on their inner paragraphs
    if matches!(pm_type.as_str(), "table_cell" | "table_header") {
        // inner_html is the full content of the <td>/<th>
        // Use build_block_nodes to handle cells that contain km-collapse, lists, etc.
        node["content"] = serde_json::Value::Array(build_block_nodes(&change.inner_html));
        return;
    }

    if pm_type == "list_item" {
        // inner_html is the list item's inline content (text)
        let content = crate::parse::parse_inline(&change.inner_html);
        node["content"] = serde_json::json!([{"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":Value::Null,"nodeId":nid()},"content":content}]);
        return;
    }

    // Simple terminal nodes
    match pm_type.as_str() {
        "paragraph" | "title" | "heading" | "note_title" | "collapse_title" => {
            node["content"] = serde_json::to_value(crate::parse::parse_inline(&change.inner_html)).unwrap_or_default();
            // 同步对齐属性：AI 若在 HTML 上调整了 text-align/align，回写到 PM attrs.align。
            // 注意双向：有新对齐则写入；新 HTML 为默认对齐（extract_align 返回 None）时，
            // 必须显式清除已有 align，否则 center→默认 会残留。
            if matches!(pm_type.as_str(), "paragraph" | "heading" | "note_title" | "collapse_title") {
                match extract_align(&change.attrs) {
                    Some(align) => {
                        if node.get("attrs").is_none() {
                            node["attrs"] = serde_json::json!({});
                        }
                        if let Some(attrs) = node.get_mut("attrs") {
                            attrs["align"] = serde_json::Value::String(align);
                        }
                    }
                    None => {
                        if let Some(attrs) = node.get_mut("attrs") {
                            // align="" 也算默认，统一按清除处理
                            let is_default = attrs.get("align").and_then(|v| v.as_str())
                                .map_or(true, |s| s.is_empty() || s == "left");
                            if !is_default {
                                attrs["align"] = serde_json::Value::String(String::new());
                            }
                        }
                    }
                }
            }
        }
        "drawio" | "video" | "audio" | "image" | "attachment" | "xtable" => {
            if let Some(src) = change.attrs.get("src") {
                if let Some(attrs) = node.get_mut("attrs") {
                    attrs["src"] = serde_json::Value::String(src.clone());
                }
            }
        }
        "code_block" => {
            let code = extract_code_from_pre(&change.inner_html);
            let code = crate::parse::unesc(if code.is_empty() { &change.inner_html } else { &code });
            node["content"] = serde_json::to_value(
                vec![serde_json::json!({"type": "text", "text": code})]
            ).unwrap_or_default();
        }
        _ => {}
    }
}

/// Parse the inner HTML of a table cell into PM paragraph nodes
/// 已被 build_block_nodes 替代，保留供参考
#[allow(dead_code)]
fn parse_cell_inner_html(html: &str) -> Vec<serde_json::Value> {
    let trimmed = html.trim();
    if trimmed.is_empty() {
        return vec![serde_json::json!({"type":"paragraph","content":[]})];
    }
    // If content starts with <p>, parse multiple paragraphs
    if trimmed.starts_with("<p>") || trimmed.starts_with("<p ") {
        let mut result = Vec::new();
        let mut pos = 0;
        while pos < trimmed.len() {
            if let Some(start) = trimmed[pos..].find("<p") {
                let abs_start = pos + start;
                if let Some(tag_end) = trimmed[abs_start..].find('>') {
                    let content_start = abs_start + tag_end + 1;
                    if let Some(close) = trimmed[content_start..].find("</p>") {
                        let inner = &trimmed[content_start..content_start + close];
                        let content = crate::parse::parse_inline(inner);
                        result.push(serde_json::json!({"type":"paragraph","content":content}));
                        pos = content_start + close + 4;
                        continue;
                    }
                }
            }
            break;
        }
        if !result.is_empty() { return result; }
    }
    // Fallback: treat entire string as inline content of a single paragraph
    let content = crate::parse::parse_inline(trimmed);
    vec![serde_json::json!({"type":"paragraph","content":content})]
}

/// 按 nodeId 在 content 数组中查找索引。当前生产代码未直接调用（apply_diff 走递归），
/// 保留供测试与潜在复用。
#[allow(dead_code)]
fn find_node_index(_doc: &Value, pm_node_id: &Option<String>, content: &[Value]) -> Option<usize> {
    let node_id = pm_node_id.as_ref()?;
    for (idx, node) in content.iter().enumerate() {
        if node.get("attrs").and_then(|a| a.get("nodeId")).and_then(|v| v.as_str()) == Some(node_id) {
            return Some(idx);
        }
    }
    None
}

// ── findByNodeId ──────────────────────────────────────────────────────────────

pub fn find_by_node_id<'a>(root: &'a Value, node_id: &str) -> Option<&'a Value> {
    if node_id.is_empty() || root.is_null() { return None; }
    if root.get("attrs").and_then(|a| a.get("nodeId")).and_then(|v| v.as_str()) == Some(node_id) {
        return Some(root);
    }
    if let Some(content) = root.get("content").and_then(|v| v.as_array()) {
        for child in content {
            if let Some(found) = find_by_node_id(child, node_id) {
                return Some(found);
            }
        }
    }
    None
}


// ── 测试 ──────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    // ── build_pm_node ────────────────────────────────────────────────────

    #[test]
    fn test_build_pm_node_p() {
        let attrs = HashMap::new();
        let node = build_pm_node("p", &attrs, "内容").unwrap();
        assert_eq!(node["type"], "paragraph");
        assert_eq!(node["content"][0]["text"], "内容");
    }

    #[test]
    fn test_build_pm_node_h2() {
        let attrs = HashMap::new();
        let node = build_pm_node("h2", &attrs, "标题").unwrap();
        assert_eq!(node["type"], "heading");
        assert_eq!(node["attrs"]["level"], 2);
    }

    #[test]
    fn test_build_pm_node_h1_title() {
        let attrs = HashMap::new();
        let node = build_pm_node("h1", &attrs, "文档标题").unwrap();
        assert_eq!(node["type"], "title");
    }

    #[test]
    fn test_build_pm_node_img() {
        let mut attrs = HashMap::new();
        attrs.insert("src".into(), "a.png".into());
        attrs.insert("alt".into(), "pic".into());
        attrs.insert("width".into(), "600".into());
        attrs.insert("height".into(), "400".into());
        let node = build_pm_node("img", &attrs, "").unwrap();
        assert_eq!(node["type"], "image");
        assert_eq!(node["attrs"]["src"], "a.png");
        assert_eq!(node["attrs"]["width"], 600.0);
    }

    #[test]
    fn test_build_pm_node_drawio() {
        let mut attrs = HashMap::new();
        attrs.insert("src".into(), "https://cdn/f.svg".into());
        let node = build_pm_node("km-drawio", &attrs, "").unwrap();
        assert_eq!(node["type"], "drawio");
    }

    #[test]
    fn test_build_pm_node_video() {
        let mut attrs = HashMap::new();
        attrs.insert("src".into(), "v.mp4".into());
        attrs.insert("name".into(), "demo.mp4".into());
        let node = build_pm_node("km-video", &attrs, "").unwrap();
        assert_eq!(node["type"], "video");
    }

    #[test]
    fn test_build_pm_node_attachment() {
        let mut attrs = HashMap::new();
        attrs.insert("name".into(), "f.pdf".into());
        attrs.insert("src".into(), "file.pdf".into());
        attrs.insert("size".into(), "1024".into());
        let node = build_pm_node("km-attachment", &attrs, "").unwrap();
        assert_eq!(node["type"], "attachment");
        assert_eq!(node["attrs"]["name"], "f.pdf");
        assert_eq!(node["attrs"]["size"], 1024.0);
    }

    // ── parse vs build_pm_node 一致性 ─────────────────────────────────────

    #[test]
    fn test_consistency_img() {
        let mut attrs = HashMap::new();
        attrs.insert("src".into(), "a.png".into());
        attrs.insert("alt".into(), "pic".into());
        let block = build_pm_node("img", &attrs, "").unwrap();

        let inline = crate::parse::inline_block_pm_node("img", &attrs).unwrap();
        assert_eq!(block["type"], inline["type"]);
        assert_eq!(block["attrs"]["src"], inline["attrs"]["src"]);
    }

    #[test]
    fn test_consistency_drawio() {
        let mut attrs = HashMap::new();
        attrs.insert("src".into(), "https://cdn/f.svg".into());
        let block = build_pm_node("km-drawio", &attrs, "").unwrap();
        let inline = crate::parse::inline_block_pm_node("km-drawio", &attrs).unwrap();
        assert_eq!(block["type"], inline["type"]);
        assert_eq!(block["attrs"]["src"], inline["attrs"]["src"]);
    }

    // ── find_by_node_id ──────────────────────────────────────────────────

    #[test]
    fn test_find_by_node_id_top_level() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "title", "attrs": { "nodeId": "t1" }, "content": [{ "type": "text", "text": "标题" }] }
            ]
        });
        let found = find_by_node_id(&doc, "t1").unwrap();
        assert_eq!(found["type"], "title");
    }

    #[test]
    fn test_find_by_node_id_nested() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "nodeId": "p1" },
                  "content": [
                    { "type": "drawio", "attrs": { "nodeId": "dr1", "src": "a.svg" } }
                  ]
                }
            ]
        });
        let found = find_by_node_id(&doc, "dr1").unwrap();
        assert_eq!(found["type"], "drawio");
    }

    #[test]
    fn test_find_node_index() {
        let content = vec![
            json!({ "type": "title", "attrs": { "nodeId": "t1" } }),
            json!({ "type": "paragraph", "attrs": { "nodeId": "p1" } }),
            json!({ "type": "heading", "attrs": { "nodeId": "h1" } }),
        ];
        assert_eq!(find_node_index(&Value::Null, &Some("t1".to_string()), &content), Some(0));
        assert_eq!(find_node_index(&Value::Null, &Some("p1".to_string()), &content), Some(1));
        assert_eq!(find_node_index(&Value::Null, &Some("h1".to_string()), &content), Some(2));
        assert_eq!(find_node_index(&Value::Null, &Some("nonexistent".to_string()), &content), None);
        assert_eq!(find_node_index(&Value::Null, &None, &content), None);
    }

    // ── 容器节点测试 ─────────────────────────────────────────────────────

    #[test]
    fn test_build_pm_node_ul() {
        let attrs = HashMap::new();
        let node = build_pm_node("ul", &attrs, "<li>项目1</li><li>项目2</li>").unwrap();
        assert_eq!(node["type"], "bullet_list");
        assert_eq!(node["content"].as_array().unwrap().len(), 2);
        assert_eq!(node["content"][0]["type"], "list_item");
    }

    #[test]
    fn test_build_pm_node_ol() {
        let attrs = HashMap::new();
        let node = build_pm_node("ol", &attrs, "<li>第一</li><li>第二</li>").unwrap();
        assert_eq!(node["type"], "ordered_list");
        assert_eq!(node["content"].as_array().unwrap().len(), 2);
    }

    #[test]
    fn test_build_pm_node_table() {
        let attrs = HashMap::new();
        let html = "<tr><th>姓名</th><th>年龄</th></tr><tr><td>张三</td><td>30</td></tr>";
        let node = build_pm_node("table", &attrs, html).unwrap();
        assert_eq!(node["type"], "table");
        let rows = node["content"].as_array().unwrap();
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0]["type"], "table_row");
        assert_eq!(rows[0]["content"][0]["type"], "table_header");
        assert_eq!(rows[1]["content"][0]["type"], "table_cell");
    }

    #[test]
    fn test_build_pm_node_tr() {
        let attrs = HashMap::new();
        let node = build_pm_node("tr", &attrs, "<td>单元格1</td><td>单元格2</td>").unwrap();
        assert_eq!(node["type"], "table_row");
        assert_eq!(node["content"][0]["type"], "table_cell");
    }

    #[test]
    fn test_build_pm_node_td() {
        let attrs = HashMap::new();
        let node = build_pm_node("td", &attrs, "内容").unwrap();
        assert_eq!(node["type"], "table_cell");
        assert_eq!(node["content"][0]["type"], "paragraph");
    }

    #[test]
    fn test_build_pm_node_th() {
        let attrs = HashMap::new();
        let node = build_pm_node("th", &attrs, "标题").unwrap();
        assert_eq!(node["type"], "table_header");
    }

    // ── 块级节点测试 ─────────────────────────────────────────────────────

    #[test]
    fn test_build_pm_node_pre() {
        let mut attrs = HashMap::new();
        attrs.insert("language".into(), "python".into());
        let html = "<code>print('hello')</code>";
        let node = build_pm_node("pre", &attrs, html).unwrap();
        assert_eq!(node["type"], "code_block");
        assert_eq!(node["attrs"]["language"], "python");
        assert_eq!(node["attrs"]["theme"], "xq-light");
    }

    #[test]
    fn test_build_pm_node_pre_without_code_tag() {
        let attrs = HashMap::new();
        let node = build_pm_node("pre", &attrs, "console.log('hello');").unwrap();
        assert_eq!(node["type"], "code_block");
        assert_eq!(node["attrs"]["language"], "Plain Text");
    }

    // ── 富媒体节点测试 ──────────────────────────────────────────────────

    #[test]
    fn test_build_pm_node_minder() {
        let attrs = HashMap::new();
        let node = build_pm_node("km-minder", &attrs, "").unwrap();
        assert_eq!(node["type"], "minder");
    }

    #[test]
    fn test_build_pm_node_plantuml() {
        let attrs = HashMap::new();
        let node = build_pm_node("km-plantuml", &attrs, "").unwrap();
        assert_eq!(node["type"], "plantuml");
    }

    #[test]
    fn test_build_pm_node_latex() {
        let attrs = HashMap::new();
        let node = build_pm_node("km-latex", &attrs, "x^2 + y^2 = z^2").unwrap();
        assert_eq!(node["type"], "latex_block");
        assert_eq!(node["content"][0]["text"], "x^2 + y^2 = z^2");
    }

    // ── 框体节点测试 ─────────────────────────────────────────────────────

    #[test]
    fn test_build_pm_node_note() {
        let mut attrs = HashMap::new();
        attrs.insert("type".into(), "warning".into());
        let html = "<summary>注意</summary><p>内容描述</p>";
        let node = build_pm_node("km-note", &attrs, html).unwrap();
        assert_eq!(node["type"], "note");
        assert_eq!(node["attrs"]["type"], "warning");
        assert_eq!(node["content"][0]["type"], "note_title");
        assert_eq!(node["content"][1]["type"], "note_content");
    }

    #[test]
    fn test_build_pm_node_collapse() {
        let attrs = HashMap::new();
        let html = "<summary>展开内容</summary><p>详细信息</p>";
        let node = build_pm_node("km-collapse", &attrs, html).unwrap();
        assert_eq!(node["type"], "collapse");
        assert_eq!(node["content"][0]["type"], "collapse_title");
        assert_eq!(node["content"][1]["type"], "collapse_content");
    }

    #[test]
    fn test_build_pm_node_note_summary_with_attrs() {
        // 回归：<summary> 带属性（style/align）时不得丢失标题文本
        let mut attrs = HashMap::new();
        attrs.insert("type".into(), "info".into());
        let html = "<summary style=\"text-align: center\">注意</summary><p>内容</p>";
        let node = build_pm_node("km-note", &attrs, html).unwrap();
        assert_eq!(node["content"][0]["type"], "note_title");
        assert_eq!(node["content"][0]["content"][0]["text"], "注意",
            "title text must not be lost when summary has attrs");
        assert_eq!(node["content"][0]["attrs"]["align"], "center",
            "summary style text-align should propagate to note_title attrs.align");
    }

    #[test]
    fn test_build_pm_node_collapse_summary_align_attr() {
        let attrs = HashMap::new();
        let html = "<summary align=\"right\">标题</summary><p>体</p>";
        let node = build_pm_node("km-collapse", &attrs, html).unwrap();
        assert_eq!(node["content"][0]["attrs"]["align"], "right");
        assert_eq!(node["content"][0]["content"][0]["text"], "标题");
    }

    // ── 错误处理测试 ─────────────────────────────────────────────────────

    #[test]
    fn test_build_pm_node_unsupported_tag() {
        let attrs = HashMap::new();
        assert!(build_pm_node("div", &attrs, "content").is_none());
        assert!(build_pm_node("section", &attrs, "content").is_none());
        assert!(build_pm_node("span", &attrs, "content").is_none());
    }

    #[test]
    fn test_build_pm_node_audio() {
        let mut attrs = HashMap::new();
        attrs.insert("src".into(), "audio.mp3".into());
        attrs.insert("name".into(), "音频文件".into());
        let node = build_pm_node("km-audio", &attrs, "").unwrap();
        assert_eq!(node["type"], "audio");
        // audio PM JSON 必须用 url 字段（schema 要求）
        assert_eq!(node["attrs"]["url"], "audio.mp3");
    }

    // ── apply_diff 测试 ──────────────────────────────────────────────────

    #[test]
    fn test_apply_diff_delete_by_node_id() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "title", "attrs": { "nodeId": "t1" }, "content": [{ "type": "text", "text": "标题" }] },
                { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [{ "type": "text", "text": "第一段" }] },
                { "type": "paragraph", "attrs": { "nodeId": "p2" }, "content": [{ "type": "text", "text": "第二段" }] }
            ]
        });
        let diff = crate::diff::DiffResult {
            changed: vec![],
            deleted: vec![crate::diff::DeleteOp {
                pm_node_id: Some("p1".to_string()),
                old_idx: None,
            }],
            added: vec![],
        };
        let result = apply_diff(&doc, &diff);
        assert_eq!(result["content"].as_array().unwrap().len(), 2);
        assert_eq!(result["content"][0]["attrs"]["nodeId"], "t1");
        assert_eq!(result["content"][1]["attrs"]["nodeId"], "p2");
    }

    #[test]
    fn test_find_by_node_id_deeply_nested() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [
                    { "type": "drawio", "attrs": { "nodeId": "dr1" } }
                ] }
            ]
        });
        let found = find_by_node_id(&doc, "dr1").unwrap();
        assert_eq!(found["type"], "drawio");
    }

    #[test]
    fn test_apply_diff_no_mutation() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [{ "type": "text", "text": "原内容" }] }
            ]
        });
        let original_text = doc["content"][0]["content"][0]["text"].as_str().unwrap().to_string();

        let diff = crate::diff::DiffResult {
            changed: vec![crate::diff::ChangeOp {
                pm_node_id: Some("p1".to_string()),
                tag: "p".to_string(),
                inner_html: "修改后".to_string(),
                attrs: HashMap::new(),
                type_changed: false,
                old_idx: None,
            }],
            deleted: vec![],
            added: vec![],
        };
        let _result = apply_diff(&doc, &diff);

        // 原文档不变
        assert_eq!(doc["content"][0]["content"][0]["text"].as_str().unwrap(), original_text);
    }

    #[test]
    fn test_build_pm_node_table_with_rows() {
        let attrs = HashMap::new();
        let html = "<tr><th>列1</th><th>列2</th></tr><tr><td>单元格1</td><td>单元格2</td></tr>";
        let node = build_pm_node("table", &attrs, html).unwrap();
        assert_eq!(node["type"], "table");
    }

    #[test]
    fn test_build_pm_node_nested_ul() {
        let attrs = HashMap::new();
        let html = "<li>项目1<ul><li>子项1</li></ul></li>";
        let node = build_pm_node("ul", &attrs, html).unwrap();
        assert_eq!(node["type"], "bullet_list");
    }

    #[test]
    fn test_build_pm_node_ul_empty() {
        let attrs = HashMap::new();
        let node = build_pm_node("ul", &attrs, "").unwrap();
        assert_eq!(node["type"], "bullet_list");
    }

    #[test]
    fn test_consistency_video() {
        let mut attrs = HashMap::new();
        attrs.insert("src".into(), "https://cdn/v.mp4".into());
        attrs.insert("name".into(), "demo.mp4".into());

        let node = build_pm_node("km-video", &attrs, "").unwrap();
        assert_eq!(node["type"], "video");
        // video 必须用 url 字段（schema 要求，对齐 oaskills）
        assert_eq!(node["attrs"]["url"], "https://cdn/v.mp4");
    }

    #[test]
    fn test_consistency_audio() {
        let mut attrs = HashMap::new();
        attrs.insert("src".into(), "https://cdn/a.mp3".into());
        attrs.insert("name".into(), "music.mp3".into());

        let node = build_pm_node("km-audio", &attrs, "").unwrap();
        assert_eq!(node["type"], "audio");
        // audio 必须用 url 字段（schema 要求，对齐 oaskills）
        assert_eq!(node["attrs"]["url"], "https://cdn/a.mp3");
    }

    #[test]
    fn test_apply_diff_multiple_changes() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [{ "type": "text", "text": "段落1" }] },
                { "type": "paragraph", "attrs": { "nodeId": "p2" }, "content": [{ "type": "text", "text": "段落2" }] }
            ]
        });

        let diff = crate::diff::DiffResult {
            changed: vec![
                crate::diff::ChangeOp {
                    pm_node_id: Some("p1".to_string()),
                    tag: "p".to_string(),
                    inner_html: "修改1".to_string(),
                    attrs: HashMap::new(),
                    type_changed: false,
                    old_idx: None,
                },
                crate::diff::ChangeOp {
                    pm_node_id: Some("p2".to_string()),
                    tag: "p".to_string(),
                    inner_html: "修改2".to_string(),
                    attrs: HashMap::new(),
                    type_changed: false,
                    old_idx: None,
                }
            ],
            deleted: vec![],
            added: vec![],
        };

        let result = apply_diff(&doc, &diff);
        let p1 = find_by_node_id(&result, "p1").unwrap();
        let p2 = find_by_node_id(&result, "p2").unwrap();

        // 注意：这些断言需要parse和rebuild的逻辑正确
        assert!(result["content"].as_array().unwrap().len() >= 2);
        // 两个段落的文本均被原地修改
        assert_eq!(p1["content"][0]["text"], "修改1");
        assert_eq!(p2["content"][0]["text"], "修改2");
    }

    // ── 对齐（align）构建与回写 ── 已用真实学城文档验证 schema：
    //    paragraph / heading 的 attrs.align 取值 "center"/"left"/"start"/""
    //    image / drawio 自身无 align，居中靠外层 paragraph.align

    #[test]
    fn test_build_pm_node_p_with_style_text_align() {
        let mut attrs = HashMap::new();
        attrs.insert("style".into(), "text-align: center".into());
        let node = build_pm_node("p", &attrs, "居中段落").unwrap();
        assert_eq!(node["type"], "paragraph");
        assert_eq!(node["content"][0]["text"], "居中段落");
        // 应从 style 属性提取对齐，写入 attrs.align
        assert_eq!(node["attrs"]["align"], "center",
            "p with style=text-align:center should produce attrs.align=center");
    }

    #[test]
    fn test_build_pm_node_p_with_align_attr() {
        let mut attrs = HashMap::new();
        attrs.insert("align".into(), "right".into());
        let node = build_pm_node("p", &attrs, "右对齐段落").unwrap();
        assert_eq!(node["type"], "paragraph");
        // align="right" 应写入 attrs.align
        assert_eq!(node["attrs"]["align"], "right",
            "p with align=right should produce attrs.align=right");
    }

    #[test]
    fn test_build_pm_node_h2_with_text_align() {
        let mut attrs = HashMap::new();
        attrs.insert("style".into(), "text-align: center".into());
        let node = build_pm_node("h2", &attrs, "居中标题").unwrap();
        assert_eq!(node["type"], "heading");
        assert_eq!(node["attrs"]["align"], "center",
            "heading with text-align should preserve align attr");
        // level 也应保留
        assert_eq!(node["attrs"]["level"], 2, "level attr must be preserved alongside align");
    }

    #[test]
    fn test_build_pm_node_p_without_style_no_align() {
        let attrs = HashMap::new();
        let node = build_pm_node("p", &attrs, "普通段落").unwrap();
        // 没有 style/align 的话不应产生非默认 align
        let align = node.get("attrs").and_then(|a| a.get("align")).and_then(|v| v.as_str()).unwrap_or("");
        assert!(align.is_empty() || align == "left",
            "no style should not produce non-default align, got: {align}");
    }

    #[test]
    fn test_build_pm_node_p_align_unknown_value_ignored() {
        let mut attrs = HashMap::new();
        attrs.insert("align".into(), "center\"><script>".into());
        let node = build_pm_node("p", &attrs, "t").unwrap();
        // 未知/脏 align 值不得原样写回；现在 attrs.align 始终存在，脏值被替换为 ""
        let align_val = node.get("attrs").and_then(|a| a.get("align")).and_then(|v| v.as_str()).unwrap_or("");
        assert!(align_val != "center\"><script>",
            "XSS align value must not be written back, got: {align_val}");
        // 值必须是空字符串（非法 align 被白名单过滤为默认值）
        assert_eq!(align_val, "", "unknown align must default to empty string");
    }

    #[test]
    fn test_apply_diff_preserves_align_on_paragraph() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "nodeId": "p1", "align": "center" },
                  "content": [{ "type": "text", "text": "原内容" }] }
            ]
        });
        // 真实流程：render 出 <p style="text-align: center">，AI 改文字但保留 style
        let mut attrs = HashMap::new();
        attrs.insert("style".to_string(), "text-align: center".to_string());
        let diff = crate::diff::DiffResult {
            changed: vec![
                crate::diff::ChangeOp {
                    pm_node_id: Some("p1".to_string()),
                    tag: "p".to_string(),
                    inner_html: "修改后内容".to_string(),
                    attrs,
                    type_changed: false,
                    old_idx: None,
                }
            ],
            deleted: vec![],
            added: vec![],
        };

        let result = apply_diff(&doc, &diff);
        let node = find_by_node_id(&result, "p1").unwrap();
        // 内容更新，且 align 属性保留
        assert_eq!(node["attrs"]["align"], "center",
            "existing align must survive content-only change");
    }

    #[test]
    fn test_apply_diff_preserves_align_on_heading() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "heading", "attrs": { "nodeId": "h1", "level": 3, "align": "right" },
                  "content": [{ "type": "text", "text": "原标题" }] }
            ]
        });
        // 真实流程：render 出 <h3 style="text-align: right">，AI 改文字但保留 style
        let mut attrs = HashMap::new();
        attrs.insert("style".to_string(), "text-align: right".to_string());
        let diff = crate::diff::DiffResult {
            changed: vec![
                crate::diff::ChangeOp {
                    pm_node_id: Some("h1".to_string()),
                    tag: "h3".to_string(),
                    inner_html: "新标题".to_string(),
                    attrs,
                    type_changed: false,
                    old_idx: None,
                }
            ],
            deleted: vec![],
            added: vec![],
        };

        let result = apply_diff(&doc, &diff);
        let node = find_by_node_id(&result, "h1").unwrap();
        assert_eq!(node["attrs"]["align"], "right",
            "existing align on heading must survive content-only change");
        assert_eq!(node["attrs"]["level"], 3, "level attr must survive too");
    }

    #[test]
    fn test_apply_diff_clears_align_when_html_has_no_alignment() {
        // 取消对齐：原段落居中，AI 改成默认对齐（无 style/align）→
        // extract_align 返回 None，必须显式清除已有 align，否则 center 残留
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "nodeId": "p1", "align": "center" },
                  "content": [{ "type": "text", "text": "hello" }] }
            ]
        });
        let diff = crate::diff::DiffResult {
            changed: vec![
                crate::diff::ChangeOp {
                    pm_node_id: Some("p1".to_string()),
                    tag: "p".to_string(),
                    inner_html: "hello".to_string(),
                    attrs: HashMap::new(), // 无 style/align → 默认对齐
                    type_changed: false,
                    old_idx: None,
                }
            ],
            deleted: vec![],
            added: vec![],
        };
        let result = apply_diff(&doc, &diff);
        let node = find_by_node_id(&result, "p1").unwrap();
        let align = node["attrs"]["align"].as_str().unwrap_or("NOT_FOUND");
        assert!(align.is_empty() || align == "left",
            "canceling center alignment must clear align, got: {align}");
    }

    #[test]
    fn test_apply_diff_clears_align_on_note_title() {
        // note_title 取消对齐：原居中，AI 去掉 style → summary 无 align → 应清除
        let doc = json!({
            "type": "doc",
            "content": [{
                "type": "note", "attrs": { "type": "info", "nodeId": "n1" },
                "content": [
                    { "type": "note_title", "attrs": { "align": "center", "nodeId": "nt1" },
                      "content": [{ "type": "text", "text": "标题" }] }
                ]
            }]
        });
        let diff = crate::diff::DiffResult {
            changed: vec![
                crate::diff::ChangeOp {
                    pm_node_id: Some("nt1".to_string()),
                    tag: "summary".to_string(),
                    inner_html: "标题".to_string(),
                    attrs: HashMap::new(), // 无 style/align → 默认对齐
                    type_changed: false,
                    old_idx: None,
                }
            ],
            deleted: vec![],
            added: vec![],
        };
        let result = apply_diff(&doc, &diff);
        let nt = &result["content"][0]["content"][0];
        let align = nt["attrs"]["align"].as_str().unwrap_or("NOT_FOUND");
        assert!(align.is_empty() || align == "left",
            "canceling note_title center alignment must clear align, got: {align}");
    }

    // ── no-nodeId 位置匹配测试（Bug 3 回归）────────────────────────────────────
    // 场景：km create 创建的文档节点没有 attrs.nodeId，
    // apply_diff 必须通过 old_idx 按位置匹配，而非跳过操作。

    #[test]
    fn test_change_by_position_when_no_node_id() {
        // 节点无 nodeId，靠 old_idx=0 定位并修改标题内容
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "title", "content": [{ "type": "text", "text": "原标题" }] },
                { "type": "paragraph", "content": [] }
            ]
        });
        let diff = crate::diff::DiffResult {
            changed: vec![crate::diff::ChangeOp {
                pm_node_id: None,
                tag: "h1".to_string(),
                inner_html: "新标题".to_string(),
                attrs: HashMap::new(),
                type_changed: false,
                old_idx: Some(0),
            }],
            deleted: vec![],
            added: vec![],
        };
        let result = apply_diff(&doc, &diff);
        let content = result["content"].as_array().unwrap();
        // 节点数量不变（不应 append 成 3 个）
        assert_eq!(content.len(), 2, "change-by-position must not append, got: {content:?}");
        // 第 0 个节点内容被更新
        assert_eq!(content[0]["content"][0]["text"], "新标题",
            "title text must be updated in-place");
    }

    #[test]
    fn test_delete_by_position_when_no_node_id() {
        // 节点无 nodeId，靠 old_idx=1 定位并删除空段落
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "title", "content": [{ "type": "text", "text": "标题" }] },
                { "type": "paragraph", "content": [] }
            ]
        });
        let diff = crate::diff::DiffResult {
            changed: vec![],
            deleted: vec![crate::diff::DeleteOp {
                pm_node_id: None,
                old_idx: Some(1),
            }],
            added: vec![],
        };
        let result = apply_diff(&doc, &diff);
        let content = result["content"].as_array().unwrap();
        assert_eq!(content.len(), 1, "paragraph at idx=1 must be removed");
        assert_eq!(content[0]["type"], "title");
    }

    #[test]
    fn test_no_duplicate_title_on_fresh_doc_full_pipeline() {
        // 回归测试：km create 后写入内容不应产生两个 title
        // 新建文档的初始 body：title + 空段落，均无 nodeId
        let empty_body = json!({
            "type": "doc",
            "content": [
                { "type": "title", "content": [{ "type": "text", "text": "文档标题" }] },
                { "type": "paragraph", "content": [] }
            ]
        });
        let new_html = "<h1>hello</h1>";
        let old_html = crate::render::render(&empty_body).html;
        let diff_result = crate::diff::diff(&old_html, new_html, &empty_body);
        let patched = apply_diff(&empty_body, &diff_result);

        let content = patched["content"].as_array().unwrap();
        let title_count = content.iter()
            .filter(|n| n["type"] == "title")
            .count();
        assert_eq!(title_count, 1,
            "must have exactly 1 title, got {title_count}. content: {content:?}");
        assert_eq!(content[0]["content"][0]["text"], "hello",
            "title must be updated to new content");
    }

    #[test]
    fn test_no_duplicate_nodes_multi_para_full_pipeline() {
        // 回归：无 nodeId 文档写入多段内容不应重复追加
        let empty_body = json!({
            "type": "doc",
            "content": [
                { "type": "title", "content": [{ "type": "text", "text": "标题" }] },
                { "type": "paragraph", "content": [] }
            ]
        });
        let new_html = "<h1>标题</h1><p>第一段</p><p>第二段</p>";
        let old_html = crate::render::render(&empty_body).html;
        let diff_result = crate::diff::diff(&old_html, new_html, &empty_body);
        let patched = apply_diff(&empty_body, &diff_result);

        let content = patched["content"].as_array().unwrap();
        // 期望：1 title + 2 paragraphs = 3 节点，而非 4/5 个
        assert_eq!(content.len(), 3,
            "expected 3 nodes (title+p+p), got {}. content: {content:?}", content.len());
        assert_eq!(content[0]["type"], "title");
        assert_eq!(content[1]["type"], "paragraph");
        assert_eq!(content[2]["type"], "paragraph");
    }
}
