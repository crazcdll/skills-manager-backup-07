//! 学城文档 PM JSON 结构校验器（对标 oaskills doc-json-validator.js）
//!
//! 在提交 create/update 前校验 PM JSON 结构合法性，
//! 避免触发服务端 code=2600001 告警。

use serde_json::Value;
use uuid::Uuid;

pub struct ValidationResult {
    pub valid: bool,
    pub errors: Vec<String>,
}

// ─── 常量集合 ─────────────────────────────────────────────────────────────────

// ⚠️  SYNC: 新增节点类型时需同步更新以下所有函数：
//   is_supported_node_type / is_block_node / is_inline_node / requires_at_least_one_content
//   以及 validate_content_type_constraints 中对应的子节点约束分支
fn is_supported_node_type(t: &str) -> bool {
    matches!(t,
        "doc" |
        "paragraph" | "heading" | "blockquote" | "code_block" | "horizontal_rule" |
        "bullet_list" | "ordered_list" | "task_list" | "list_item" | "task_item" |
        "table" | "table_row" | "table_cell" | "table_header" |
        "image" | "audio" | "video" | "attachment" |
        "collapse" | "collapse_title" | "collapse_content" |
        "note" | "note_title" | "note_content" |
        "latex_block" | "markdown" | "html" |
        "catalog" | "spaceupdate" | "page_tree" | "gantt" | "data2chart" | "calendar" |
        "plantuml" | "drawio" | "minder" | "xtable" |
        "open_iframe" | "open_link" | "open_card" |
        "appendix" | "not_support" | "control" | "doc_list_view" |
        "title" |
        "footnote_list" | "footnote_list_item" |
        "text" | "hard_break" |
        "mention" | "link" | "time" | "status" | "emoji" |
        "latex_inline" | "footnote"
    )
}

fn is_supported_mark_type(t: &str) -> bool {
    matches!(t,
        "strong" | "em" | "underline" | "strikethrough" | "code" |
        "color" | "backgroundcolor" | "font" | "sub" | "sup" | "quote"
    )
}

fn is_block_node(t: &str) -> bool {
    matches!(t,
        "paragraph" | "heading" | "blockquote" | "code_block" | "horizontal_rule" |
        "bullet_list" | "ordered_list" | "task_list" |
        "table" |
        "audio" | "video" | "attachment" |
        "collapse" | "note" |
        "latex_block" | "markdown" | "html" |
        "catalog" | "spaceupdate" | "page_tree" | "gantt" | "calendar" |
        "not_support" | "control" | "doc_list_view" |
        "open_card" | "open_iframe" |
        "footnote_list"
    )
}

fn is_inline_node(t: &str) -> bool {
    matches!(t,
        "text" | "hard_break" |
        "mention" | "link" | "time" | "status" | "emoji" |
        "latex_inline" | "footnote" |
        "data2chart" | "open_link" |
        "image" |
        "plantuml" | "drawio" | "minder"
    )
}

fn requires_at_least_one_content(t: &str) -> bool {
    matches!(t,
        "doc" | "bullet_list" | "ordered_list" | "task_list" |
        "blockquote" | "collapse_content" | "note_content" |
        "footnote_list" | "footnote_list_item" |
        "table" | "table_row"
    )
}

fn is_supported_code_language(lang: &str) -> bool {
    matches!(lang,
        "Plain Text" | "JavaScript" | "Java" | "JSON" | "Shell" | "HTML" | "PlantUML" |
        "Mermaid" | "C" | "C++" | "C#" | "CSS" | "Dart" | "Elm" | "Go" | "Groovy" |
        "HTTP" | "JSX" | "Kotlin" | "LaTeX" | "Lua" | "Markdown" | "Nginx" |
        "Objective-C" | "Perl" | "PHP" | "PowerShell" | "Python" | "R" | "Ruby" |
        "Sass" | "Scala" | "SQL" | "Stylus" | "TypeScript" | "Swift" |
        "Vue.js Component" | "XML" | "YAML" | "Mindmap"
    )
}

// ─── mark 校验 ────────────────────────────────────────────────────────────────

fn validate_mark(mark: &Value, path: &str, errors: &mut Vec<String>) {
    let Some(obj) = mark.as_object() else {
        errors.push(format!("{path}: mark 必须是非 null 的对象"));
        return;
    };
    let Some(t) = obj.get("type").and_then(|v| v.as_str()) else {
        errors.push(format!("{path}: mark 缺少 type 字段或 type 不是字符串"));
        return;
    };
    if !is_supported_mark_type(t) {
        errors.push(format!("{path}: 不支持的 mark 类型 \"{t}\""));
        return;
    }
    // 必填 attrs
    let required: &[&str] = match t {
        "color" | "backgroundcolor" => &["color"],
        "font" => &["dataSize"],
        "quote" => &["quoteId"],
        _ => &[],
    };
    if !required.is_empty() {
        match obj.get("attrs").and_then(|v| v.as_object()) {
            None => {
                errors.push(format!("{path}: mark \"{t}\" 必须包含 attrs 字段"));
            }
            Some(attrs) => {
                for &field in required {
                    if !attrs.contains_key(field) || attrs[field].is_null() {
                        errors.push(format!("{path}: mark \"{t}\" 的 attrs 缺少必填字段 \"{field}\""));
                    }
                }
            }
        }
    }
}

// ─── 子节点类型约束 ───────────────────────────────────────────────────────────

fn node_type(v: &Value) -> &str {
    v.get("type").and_then(|t| t.as_str()).unwrap_or("(unknown)")
}

/// 校验子节点全部是某一指定类型，否则报错
fn check_children_single_type(children: &[Value], expected: &str, parent: &str, path: &str, errors: &mut Vec<String>) {
    for (i, child) in children.iter().enumerate() {
        let t = node_type(child);
        if t != expected {
            errors.push(format!("{path}.content[{i}]: {parent} 的子节点必须是 {expected}，实际为 \"{t}\""));
        }
    }
}

/// 校验"双子节点容器"（如 collapse/note）：required_a + required_b 各需存在一个，且不能有其他子节点
fn validate_pair_container(
    parent_type: &str,
    children: &[Value],
    required_a: &str,
    required_b: &str,
    path: &str,
    errors: &mut Vec<String>,
) {
    let types: Vec<&str> = children.iter().map(|c| node_type(c)).collect();
    if !types.contains(&required_a) {
        errors.push(format!("{path}: {parent_type} 节点缺少 {required_a} 子节点"));
    }
    if !types.contains(&required_b) {
        errors.push(format!("{path}: {parent_type} 节点缺少 {required_b} 子节点"));
    }
    for (i, child) in children.iter().enumerate() {
        let t = node_type(child);
        if t != required_a && t != required_b {
            errors.push(format!("{path}.content[{i}]: {parent_type} 只能包含 {required_a} 和 {required_b}，实际为 \"{t}\""));
        }
    }
}

fn validate_content_type_constraints(
    parent_type: &str,
    children: &[Value],
    path: &str,
    errors: &mut Vec<String>,
) {
    fn get_type(v: &Value) -> &str {
        node_type(v)
    }

    match parent_type {
        "doc" => {
            // title 必须是第一个且唯一
            let title_count = children.iter().filter(|c| get_type(c) == "title").count();
            if title_count == 0 {
                errors.push(format!("{path}: doc 节点缺少 title 子节点（title 是文档标题，不是 heading）"));
            } else {
                if get_type(&children[0]) != "title" {
                    errors.push(format!(
                        "{path}.content[0]: doc 节点第一个子节点必须是 title，实际为 \"{}\"",
                        get_type(&children[0])
                    ));
                }
                if title_count > 1 {
                    errors.push(format!("{path}: doc 节点中 title 只能出现一次，当前出现了 {title_count} 次"));
                }
            }
            if children.len() < 2 {
                errors.push(format!("{path}: doc 节点在 title 之后必须至少有一个内容节点（paragraph/heading 等）"));
            }
            // footnote_list 最多一个，且必须是最后一个
            let fl_count = children.iter().filter(|c| get_type(c) == "footnote_list").count();
            if fl_count > 1 {
                errors.push(format!("{path}: doc 节点中 footnote_list 最多出现一次，当前出现了 {fl_count} 次"));
            }
            if fl_count == 1 {
                if children.last().map(|c| get_type(c)) != Some("footnote_list") {
                    errors.push(format!("{path}: footnote_list 必须是 doc 的最后一个子节点"));
                }
            }
            // 子节点类型合法性
            for (i, child) in children.iter().enumerate() {
                let t = get_type(child);
                let allowed = is_block_node(t) || matches!(t, "title" | "xtable" | "appendix" | "footnote_list");
                if !allowed {
                    let hint = match t {
                        "list_item" | "task_item" => "（list_item/task_item 必须包裹在 bullet_list/ordered_list/task_list 中）",
                        "table_row" => "（table_row 必须包裹在 table 中）",
                        "table_cell" | "table_header" => "（table_cell/table_header 必须依次包裹在 table > table_row 中）",
                        _ => "",
                    };
                    errors.push(format!("{path}.content[{i}]: doc 节点的子节点 \"{t}\" 不合法。doc 只能包含 block 节点、title、xtable、appendix、footnote_list。{hint}"));
                }
            }
        }
        "paragraph" | "heading" => {
            for (i, child) in children.iter().enumerate() {
                if let Some(obj) = child.as_object() {
                    let t = obj.get("type").and_then(|v| v.as_str()).unwrap_or("(unknown)");
                    if !is_inline_node(t) {
                        errors.push(format!(
                            "{path}.content[{i}]: {parent_type} 的子节点必须是 inline 节点，实际为 \"{t}\"（inline 类型：text/hard_break/mention/link/image/drawio/minder 等）"
                        ));
                    }
                } else {
                    errors.push(format!("{path}.content[{i}]: {parent_type} 的子节点必须是节点对象"));
                }
            }
        }
        "collapse_title" | "note_title" => {
            for (i, child) in children.iter().enumerate() {
                let t = get_type(child);
                if !is_inline_node(t) {
                    errors.push(format!("{path}.content[{i}]: {parent_type} 只能包含行内文本节点（text/hard_break/mention 等），实际为 \"{t}\""));
                }
            }
        }
        "blockquote" | "collapse_content" | "note_content" | "table_cell" | "table_header" => {
            for (i, child) in children.iter().enumerate() {
                let t = get_type(child);
                if !is_block_node(t) {
                    errors.push(format!("{path}.content[{i}]: {parent_type} 的子节点必须是 block 节点（paragraph/heading/table 等），实际为 \"{t}\""));
                }
            }
        }
        "list_item" | "task_item" => {
            for (i, child) in children.iter().enumerate() {
                let t = get_type(child);
                if !is_block_node(t) && t != "xtable" {
                    errors.push(format!("{path}.content[{i}]: {parent_type} 的子节点必须是 paragraph 或 block 节点，实际为 \"{t}\""));
                }
            }
        }
        "table" => {
            if children.is_empty() {
                errors.push(format!("{path}: 空 table 会导致渲染崩溃"));
            }
            for (i, child) in children.iter().enumerate() {
                let t = get_type(child);
                if t != "table_row" {
                    errors.push(format!("{path}.content[{i}]: table 的子节点必须是 table_row，实际为 \"{t}\""));
                }
            }
            // 行列数一致性（简化版：不检查 rowspan 覆盖，只检查每行 colspan 之和）
            let col_counts: Vec<u64> = children.iter()
                .filter(|c| get_type(c) == "table_row")
                .map(|row| {
                    row.get("content").and_then(|v| v.as_array()).map(|cells| {
                        cells.iter().map(|cell| {
                            cell.get("attrs").and_then(|a| a.get("colspan")).and_then(|v| v.as_u64()).unwrap_or(1)
                        }).sum::<u64>()
                    }).unwrap_or(0)
                })
                .collect();
            if !col_counts.is_empty() {
                let max_cols = *col_counts.iter().max().unwrap_or(&0);
                for (i, &count) in col_counts.iter().enumerate() {
                    if count < max_cols {
                        errors.push(format!(
                            "{path}.content[{i}]: table_row 列数（{count}）少于最大列数（{max_cols}），可能漏写了 {} 个 table_cell",
                            max_cols - count
                        ));
                    }
                }
            }
        }
        "table_row" => {
            for (i, child) in children.iter().enumerate() {
                let t = get_type(child);
                if t != "table_cell" && t != "table_header" {
                    errors.push(format!("{path}.content[{i}]: table_row 的子节点必须是 table_cell 或 table_header，实际为 \"{t}\""));
                }
            }
        }
        "bullet_list" | "ordered_list" => {
            for (i, child) in children.iter().enumerate() {
                let t = get_type(child);
                if t != "list_item" && t != "task_item" {
                    errors.push(format!("{path}.content[{i}]: {parent_type} 的子节点必须是 list_item 或 task_item，实际为 \"{t}\""));
                }
            }
        }
        "task_list" => {
            for (i, child) in children.iter().enumerate() {
                let t = get_type(child);
                if t != "task_item" && t != "list_item" {
                    errors.push(format!("{path}.content[{i}]: task_list 的子节点必须是 task_item 或 list_item，实际为 \"{t}\""));
                }
            }
        }
        "collapse" => validate_pair_container("collapse", children, "collapse_title", "collapse_content", path, errors),
        "note"     => validate_pair_container("note",     children, "note_title",    "note_content",    path, errors),
        "title" => {
            if children.len() != 1 {
                errors.push(format!("{path}: title 节点的 content 必须恰好有一个 text 子节点，当前有 {} 个", children.len()));
            } else {
                let child = &children[0];
                let t = get_type(child);
                if t != "text" {
                    errors.push(format!("{path}.content[0]: title 的子节点必须是 text，实际为 \"{t}\""));
                } else {
                    let has_marks = child.get("marks").and_then(|v| v.as_array()).map(|m| !m.is_empty()).unwrap_or(false);
                    if has_marks {
                        errors.push(format!("{path}.content[0]: title 的 text 节点不能携带 marks（文档标题须为纯文本）"));
                    }
                }
            }
        }
        "footnote_list"      => check_children_single_type(children, "footnote_list_item", "footnote_list", path, errors),
        "footnote_list_item" => check_children_single_type(children, "paragraph", "footnote_list_item", path, errors),
        "code_block"         => check_children_single_type(children, "text", "code_block", path, errors),
        "link" | "latex_inline" | "status" => check_children_single_type(children, "text", parent_type, path, errors),
        _ => {}
    }
}

// ─── 节点校验（递归） ────────────────────────────────────────────────────────

fn validate_node(node: &Value, path: &str, errors: &mut Vec<String>, depth: usize, parent_type: &str) {
    if depth > 100 {
        errors.push(format!("{path}: 节点嵌套过深（超过 100 层）"));
        return;
    }

    let Some(obj) = node.as_object() else {
        errors.push(format!("{path}: 节点必须是非 null 的对象"));
        return;
    };

    let Some(node_type) = obj.get("type").and_then(|v| v.as_str()) else {
        errors.push(format!("{path}: 节点缺少 type 字段或 type 不是字符串"));
        return;
    };

    if !is_supported_node_type(node_type) {
        errors.push(format!("{path}: 不支持的节点类型 \"{node_type}\""));
        return;
    }

    let get_attr = |key: &str| -> Option<&Value> {
        obj.get("attrs").and_then(|a| a.as_object()).and_then(|a| a.get(key))
    };

    // ── 各节点必填字段校验 ────────────────────────────────────────────────────

    match node_type {
        "image" => {
            let src = get_attr("src").and_then(|v| v.as_str()).unwrap_or("");
            if src.is_empty() {
                errors.push(format!("{path}: image 节点缺少必填字段 src（图片 URL 不能为空）"));
            }
            match get_attr("name") {
                None => errors.push(format!("{path}: image 节点的 name 字段不能为 null/undefined")),
                Some(v) if v.is_null() => errors.push(format!("{path}: image 节点的 name 字段不能为 null/undefined")),
                Some(v) if !v.is_string() => errors.push(format!("{path}: image 节点的 name 字段必须是字符串")),
                _ => {}
            }
        }
        "audio" => {
            let url = get_attr("url").and_then(|v| v.as_str()).unwrap_or("");
            if url.is_empty() {
                errors.push(format!("{path}: audio 节点缺少必填字段 url（音频 URL 不能为空）"));
            }
        }
        "video" => {
            let url = get_attr("url").and_then(|v| v.as_str()).unwrap_or("");
            if url.is_empty() {
                errors.push(format!("{path}: video 节点缺少必填字段 url（视频 URL 不能为空）"));
            }
        }
        "attachment" => {
            let src = get_attr("src").and_then(|v| v.as_str()).unwrap_or("");
            if src.is_empty() {
                errors.push(format!("{path}: attachment 节点缺少必填字段 src（附件 URL 不能为空）"));
            }
        }
        "mention" => {
            let uid = get_attr("uid").and_then(|v| v.as_str()).unwrap_or("");
            if uid.is_empty() {
                errors.push(format!("{path}: mention 节点缺少必填字段 uid（@用户的 uid 不能为空）"));
            }
        }
        "link" => {
            let href = get_attr("href").and_then(|v| v.as_str()).unwrap_or("");
            if href.is_empty() {
                errors.push(format!("{path}: link 节点缺少必填字段 href（链接 URL 不能为空）"));
            }
        }
        "emoji" => {
            let name = get_attr("name").and_then(|v| v.as_str()).unwrap_or("");
            if name.is_empty() {
                errors.push(format!("{path}: emoji 节点缺少必填字段 name"));
            }
        }
        "heading" => {
            let level = get_attr("level").and_then(|v| v.as_i64());
            match level {
                Some(l) if l >= 1 && l <= 6 => {}
                _ => errors.push(format!("{path}: heading 节点的 level 字段必须是 1-6 的整数，实际为 {:?}", level)),
            }
        }
        "table_cell" | "table_header" => {
            let colwidth = get_attr("colwidth");
            if let Some(cw) = colwidth {
                if !cw.is_null() && !cw.is_array() {
                    errors.push(format!("{path}: {node_type} 节点的 colwidth 字段必须是数组或 null"));
                }
            }
        }
        "catalog" => {
            let style = get_attr("style").and_then(|v| v.as_str()).unwrap_or("");
            if !style.is_empty() && !matches!(style, "none" | "number" | "circle" | "rect" | "point") {
                errors.push(format!("{path}: catalog 节点 attrs.style 值 \"{style}\" 不合法，合法值为 none/number/circle/rect/point"));
            }
        }
        "drawio" => {
            let src = get_attr("src").and_then(|v| v.as_str()).unwrap_or("");
            let mss = get_attr("mss").and_then(|v| v.as_str()).unwrap_or("");
            if src.is_empty() && mss.is_empty() {
                errors.push(format!("{path}: drawio 节点 src 和 mss 不能同时为空"));
            }
        }
        "minder" => {
            let src = get_attr("src").and_then(|v| v.as_str()).unwrap_or("");
            if src.is_empty() {
                errors.push(format!("{path}: minder 节点缺少必填字段 src（脑图数据地址不能为空）"));
            }
        }
        "open_link" => {
            let url = get_attr("url").and_then(|v| v.as_str()).unwrap_or("");
            let href = get_attr("href").and_then(|v| v.as_str()).unwrap_or("");
            if url.is_empty() && href.is_empty() {
                errors.push(format!("{path}: open_link 节点的 url（或旧字段 href）不能为空或 null"));
            }
        }
        "note" => {
            let note_type = get_attr("type").and_then(|v| v.as_str()).unwrap_or("");
            if !note_type.is_empty() && !matches!(note_type, "info" | "note" | "warning" | "tip") {
                errors.push(format!("{path}: note 节点 attrs.type 值 \"{note_type}\" 不合法，合法值为 info/note/warning/tip"));
            }
        }
        "code_block" => {
            let lang = get_attr("language").and_then(|v| v.as_str()).unwrap_or("");
            if lang.is_empty() {
                errors.push(format!("{path}: code_block.attrs.language 不能为空（缺省值应为 \"Plain Text\"）"));
            } else if !is_supported_code_language(lang) {
                errors.push(format!("{path}: code_block.attrs.language \"{lang}\" 不在支持的语言列表中（注意大小写严格匹配，如 \"Python\" 不能写成 \"python\"）"));
            }
            let theme = get_attr("theme").and_then(|v| v.as_str()).unwrap_or("");
            if theme.is_empty() {
                errors.push(format!("{path}: code_block.attrs.theme 不能为空（缺省值应为 \"xq-light\"）"));
            }
        }
        "text" => {
            match obj.get("text") {
                None => errors.push(format!("{path}: text 节点必须包含 text 字段（字符串）")),
                Some(v) => {
                    let s = v.as_str().unwrap_or("");
                    if s.is_empty() {
                        errors.push(format!("{path}: text 节点的 text 字段不能为空字符串"));
                    } else if s.contains('\n') && parent_type != "code_block" {
                        errors.push(format!("{path}: text 节点的 text 字段不能包含换行符（\\n），换行应使用 hard_break 节点代替"));
                    }
                }
            }
            if obj.contains_key("content") && !obj["content"].is_null() {
                errors.push(format!("{path}: text 节点不应包含 content 字段"));
            }
        }
        _ => {}
    }

    // ── marks 校验 ────────────────────────────────────────────────────────────

    if let Some(marks) = obj.get("marks") {
        if let Some(arr) = marks.as_array() {
            for (i, mark) in arr.iter().enumerate() {
                validate_mark(mark, &format!("{path}.marks[{i}]"), errors);
            }
        } else if !marks.is_null() {
            errors.push(format!("{path}.marks: marks 必须是数组"));
        }
    }

    // ── content 校验 ─────────────────────────────────────────────────────────

    if let Some(content) = obj.get("content") {
        match content.as_array() {
            None if !content.is_null() => {
                errors.push(format!("{path}.content: content 必须是数组"));
            }
            Some(children) => {
                if requires_at_least_one_content(node_type) && children.is_empty() {
                    errors.push(format!("{path}: 节点类型 \"{node_type}\" 要求 content 至少有一个子节点"));
                }
                for (i, child) in children.iter().enumerate() {
                    validate_node(child, &format!("{path}.content[{i}]"), errors, depth + 1, node_type);
                }
                validate_content_type_constraints(node_type, children, path, errors);
            }
            None => {} // null content，按下面处理
        }
    } else if requires_at_least_one_content(node_type) {
        match node_type {
            "doc" => errors.push(format!("{path}: doc 节点必须包含 content 数组")),
            "table" => errors.push(format!("{path}: table 节点必须包含至少一个 table_row（content 字段缺失会导致渲染崩溃）")),
            "table_row" => errors.push(format!("{path}: table_row 节点必须包含至少一个 table_cell 或 table_header")),
            _ => {}
        }
    }
}

// ─── 公开入口 ─────────────────────────────────────────────────────────────────

/// 对标 oaskills normalizeDocumentJson：在提交前补全缺失的默认值
/// 1. table_cell / table_header：numCell null → 0（或 colspan）
/// 2. open_link：type null → ""
/// 3. table：列数不足的行末尾追加空 table_cell
/// 注意：只补充缺失值，不覆盖已有合法值
pub fn normalize_document_json(doc: &mut Value) {
    normalize_node(doc);
}

fn normalize_node(node: &mut Value) {
    let Some(obj) = node.as_object_mut() else { return };
    let node_type = obj.get("type").and_then(|v| v.as_str()).unwrap_or("").to_string();

    // table_cell / table_header：numCell null → 0（或 colspan）
    if node_type == "table_cell" || node_type == "table_header" {
        if let Some(attrs) = obj.get_mut("attrs").and_then(|v| v.as_object_mut()) {
            let num_cell = attrs.get("numCell");
            if num_cell.is_none() || num_cell == Some(&Value::Null) {
                let colspan = attrs.get("colspan").and_then(|v| v.as_u64()).unwrap_or(1);
                attrs.insert("numCell".into(), serde_json::json!(if colspan > 1 { colspan } else { 0 }));
            }
        }
    }

    // open_link：type null → ""
    if node_type == "open_link" {
        if let Some(attrs) = obj.get_mut("attrs").and_then(|v| v.as_object_mut()) {
            let otype = attrs.get("type");
            if otype.is_none() || otype == Some(&Value::Null) {
                attrs.insert("type".into(), serde_json::json!(""));
            }
        }
    }

    // table：补齐每行列数
    if node_type == "table" {
        if let Some(content) = obj.get_mut("content").and_then(|v| v.as_array_mut()) {
            // 计算最大列数
            let max_cols = content.iter().map(|row| {
                row.get("content").and_then(|v| v.as_array()).map(|cells| {
                    cells.iter().map(|c| c.get("attrs").and_then(|a| a.get("colspan")).and_then(|v| v.as_u64()).unwrap_or(1)).sum::<u64>()
                }).unwrap_or(0)
            }).max().unwrap_or(0);

            for row in content.iter_mut() {
                if let Some(cells) = row.get_mut("content").and_then(|v| v.as_array_mut()) {
                    let row_cols: u64 = cells.iter().map(|c| {
                        c.get("attrs").and_then(|a| a.get("colspan")).and_then(|v| v.as_u64()).unwrap_or(1)
                    }).sum();
                    let missing = max_cols.saturating_sub(row_cols);
                    for _ in 0..missing {
                        cells.push(serde_json::json!({
                            "type": "table_cell",
                            "attrs": {
                                "colspan": 1, "rowspan": 1, "numCell": 0,
                                "bgColor": null, "color": null, "colwidth": null,
                                "textAlign": null, "verticalAlign": null,
                                "nodeId": Uuid::new_v4().to_string().replace('-', "")
                            },
                            "content": [{"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":null,"nodeId": uuid::Uuid::new_v4().to_string().replace('-', "")}}]
                        }));
                    }
                }
            }
        }
    }

    // 递归子节点
    if let Some(content) = obj.get_mut("content").and_then(|v| v.as_array_mut()) {
        for child in content.iter_mut() {
            normalize_node(child);
        }
    }
}

/// 校验学城 PM JSON 结构合法性（对标 oaskills validateDocumentJson）
pub fn validate_document_json(doc: &Value) -> ValidationResult {
    let mut errors = Vec::new();
    validate_node(doc, "doc", &mut errors, 0, "");
    ValidationResult { valid: errors.is_empty(), errors }
}

/// 把 PM JSON 或 HTML 转换错误格式化为人可读的建议
pub fn format_errors(errors: &[String]) -> String {
    if errors.is_empty() {
        return "✓ 文档结构合法".to_string();
    }
    let mut out = format!("文档结构有 {} 个问题：\n", errors.len());
    for (i, e) in errors.iter().enumerate() {
        out.push_str(&format!("  {}. {}\n", i + 1, e));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn ok(doc: serde_json::Value) {
        let r = validate_document_json(&doc);
        assert!(r.valid, "应该通过但有错误:\n{}", r.errors.join("\n"));
    }
    fn err(doc: serde_json::Value) -> Vec<String> {
        let r = validate_document_json(&doc);
        assert!(!r.valid, "应该失败但通过了");
        r.errors
    }

    fn base(extra: Vec<serde_json::Value>) -> serde_json::Value {
        let mut content = vec![
            json!({"type":"title","attrs":{"nodeId":"T"},"content":[{"type":"text","text":"标题"}]}),
        ];
        content.extend(extra);
        if content.len() < 2 {
            content.push(json!({"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":null,"nodeId":"P"}}));
        }
        json!({"type":"doc","content": content})
    }

    #[test] fn valid_minimal() { ok(base(vec![])); }

    #[test]
    fn missing_title() {
        let e = err(json!({"type":"doc","content":[
            {"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":null,"nodeId":"P"}}
        ]}));
        assert!(e.iter().any(|s| s.contains("缺少 title")));
    }

    #[test]
    fn video_needs_url_not_src() {
        // src 字段 → 报错
        let e = err(base(vec![
            json!({"type":"video","attrs":{"src":"https://cdn/v.mp4","name":"v"}})
        ]));
        assert!(e.iter().any(|s| s.contains("video") && s.contains("url")), "应报 url 缺失: {:?}", e);

        // url 字段 → 通过
        ok(base(vec![
            json!({"type":"video","attrs":{"url":"https://cdn/v.mp4","name":"v","nodeId":"V"}})
        ]));
    }

    #[test]
    fn image_name_must_be_string() {
        // name = null → 报错
        let e = err(base(vec![json!({"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":null,"nodeId":"P"},"content":[
            {"type":"image","attrs":{"src":"https://cdn/img","name":null}}
        ]})]));
        assert!(e.iter().any(|s| s.contains("name")));

        // name = "" → 通过
        ok(base(vec![json!({"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":null,"nodeId":"P"},"content":[
            {"type":"image","attrs":{"src":"https://cdn/img","name":""}}
        ]})]));
    }

    #[test]
    fn video_inside_paragraph_is_blocked() {
        let e = err(base(vec![json!({"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":null,"nodeId":"P"},"content":[
            {"type":"video","attrs":{"url":"https://cdn/v.mp4","name":"v"}}
        ]})]));
        assert!(e.iter().any(|s| s.contains("inline")), "video 不能在 paragraph 里: {:?}", e);
    }

    #[test]
    fn code_block_language_case_sensitive() {
        // 小写 → 报错
        let e = err(base(vec![
            json!({"type":"code_block","attrs":{"language":"python","theme":"xq-light","nodeId":"C"},"content":[{"type":"text","text":"x"}]})
        ]));
        assert!(e.iter().any(|s| s.contains("language")));

        // 正确大小写 → 通过
        ok(base(vec![
            json!({"type":"code_block","attrs":{"language":"Python","theme":"xq-light","nodeId":"C"},"content":[{"type":"text","text":"x"}]})
        ]));
    }

    #[test]
    fn task_list_needs_task_item() {
        ok(base(vec![json!({"type":"task_list","attrs":{"dataDiffId":null,"indent":0,"nodeId":"TL"},"content":[
            {"type":"task_item","attrs":{"checked":false,"dataListItemDiffId":null,"fontSize":null,"level":0,"nodeId":"TI"},
             "content":[{"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":null,"nodeId":"P2"}}]}
        ]})]));
    }

    #[test]
    fn note_type_enum() {
        // 非法 type → 报错
        let e = err(base(vec![json!({"type":"note","attrs":{"type":"error","nodeId":"N"},"content":[
            {"type":"note_title","attrs":{"align":"left","nodeId":"NT"},"content":[{"type":"text","text":"t"}]},
            {"type":"note_content","attrs":{"nodeId":"NC"},"content":[{"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":null,"nodeId":"NP"}}]}
        ]})]));
        assert!(e.iter().any(|s| s.contains("note") && s.contains("type")));

        // 合法 type → 通过
        ok(base(vec![json!({"type":"note","attrs":{"type":"info","nodeId":"N"},"content":[
            {"type":"note_title","attrs":{"align":"left","nodeId":"NT"},"content":[{"type":"text","text":"t"}]},
            {"type":"note_content","attrs":{"nodeId":"NC"},"content":[{"type":"paragraph","attrs":{"indent":0,"align":"","dataDiffId":null,"nodeId":"NP"}}]}
        ]})]));
    }
}
