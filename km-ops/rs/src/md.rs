//! 标准 Markdown → 学城 ProseMirror JSON 转换器
//!
//! 参考 oa-skills 的 CitadelMdParser 架构（doc-md-converter.js），
//! 只实现标准 Markdown（CommonMark + GFM：表格、删除线、任务列表），
//! 不实现 CitadelMD 自定义宏（:::tag、:[tag]）等学城特有语法。
//!
//! 流程：md → PM JSON（直接构造，不经过 HTML），
//! 输出符合 collab_doc schema（title 有且仅有一个且在首位，footnote_list 在末尾）。

use serde_json::{json, Value};
use uuid::Uuid;

/// 将 markdown 字符串转为学城 PM JSON 文档。
/// 若 md 首行是 `# 标题`，提取为文档 title，并去掉首行避免重复标题。
pub fn md_to_pm(md: &str, title: &str) -> Value {
    let mut text = md;
    let mut doc_title: String = title.to_string();
    if let Some(first_line) = text.lines().next() {
        if let Some(h) = first_line_title(first_line) {
            doc_title = h;
            if let Some(pos) = text.find('\n') {
                text = &text[pos + 1..];
            } else {
                text = "";
            }
        }
    }

    let mut parser = MdParser::new(text);
    let mut content = parser.parse_blocks();

    // schema 清理：title 有且仅有一个，且在首位
    let mut title_node: Option<Value> = None;
    let mut rest: Vec<Value> = Vec::new();
    for node in content.drain(..) {
        if node.get("type").and_then(|v| v.as_str()) == Some("title") {
            if title_node.is_none() {
                title_node = Some(node);
            }
            // 多余 title 丢弃
        } else {
            rest.push(node);
        }
        // footnote_list 移到末尾（最多一个）
    }
    let mut footnote: Option<Value> = None;
    let mut body: Vec<Value> = Vec::new();
    for node in rest {
        if node.get("type").and_then(|v| v.as_str()) == Some("footnote_list") {
            if footnote.is_none() {
                footnote = Some(node);
            }
        } else {
            body.push(node);
        }
    }

    // 构造最终 doc
    let mut doc_content: Vec<Value> = Vec::new();
    // title：用 md 首行标题（已提取到 doc_title），或参数 title
    match title_node {
        Some(t) => doc_content.push(t),
        None => doc_content.push(json!({
            "type": "title",
            "attrs": { "nodeId": nid() },
            "content": [{ "type": "text", "text": doc_title }]
        })),
    }
    doc_content.extend(body);
    if let Some(f) = footnote {
        doc_content.push(f);
    }

    json!({ "type": "doc", "content": doc_content })
}

/// 从 Markdown 第一行提取文档标题。
pub fn title_from_md(md: &str) -> Option<String> {
    md.lines().next().and_then(first_line_title)
}

/// 从一行文本提取 `# 标题` 的标题文字（非一级标题行返回 None）
fn first_line_title(line: &str) -> Option<String> {
    let bytes = line.as_bytes();
    if !bytes.starts_with(b"# ") {
        return None;
    }
    let title = line[2..].trim();
    if title.is_empty() { None } else { Some(title.to_string()) }
}

fn nid() -> String {
    Uuid::new_v4().to_string().replace('-', "")
}

struct MdParser<'a> {
    lines: Vec<&'a str>,
    pos: usize,
}

impl<'a> MdParser<'a> {
    fn new(md: &'a str) -> Self {
        Self { lines: md.split('\n').collect(), pos: 0 }
    }

    fn peek(&self) -> Option<&'a str> {
        self.lines.get(self.pos).copied()
    }
    fn consume(&mut self) -> Option<&'a str> {
        let v = self.peek();
        if v.is_some() { self.pos += 1; }
        v
    }

    fn parse_blocks(&mut self) -> Vec<Value> {
        let mut nodes = Vec::new();
        while self.pos < self.lines.len() {
            let line = self.peek().unwrap_or("");
            if line.trim().is_empty() { self.pos += 1; continue; }
            // 跳过 CitadelMD 宏 :::tag（标准 markdown 不处理，原样当段落文本忽略）
            if line.starts_with(":::") {
                // 跳过整个宏块到单独的 ::: 行
                self.consume();
                while self.pos < self.lines.len() {
                    let l = self.consume().unwrap_or("");
                    if l.trim() == ":::" { break; }
                }
                continue;
            }
            if let Some(node) = self.parse_standard_block() {
                nodes.push(node);
            }
        }
        nodes
    }

    fn parse_standard_block(&mut self) -> Option<Value> {
        let line = self.peek()?.to_string();

        // 标题 #{1,6}
        if let Some((level, text)) = parse_heading(&line) {
            self.consume();
            return Some(json!({
                "type": "heading",
                "attrs": { "level": level, "align": "left", "id": nid(), "indent": 0, "dataDiffId": Value::Null, "nodeId": nid() },
                "content": parse_inline(&text)
            }));
        }

        // 代码块 ```
        if let Some(stripped) = line.strip_prefix("```") {
            self.consume();
            let lang = stripped.trim().trim_matches('"').trim();
            let lang = normalize_lang(lang);
            let mut code_lines = Vec::new();
            while self.pos < self.lines.len() {
                let l = self.peek().unwrap_or("");
                if l.starts_with("```") { self.consume(); break; }
                code_lines.push(self.consume().unwrap_or(""));
            }
            let code = if code_lines.is_empty() { " ".to_string() } else { code_lines.join("\n") };
            return Some(json!({
                "type": "code_block",
                "attrs": { "language": lang, "theme": "xq-light", "title": "代码块", "isExpand": true, "dataDiffId": Value::Null, "id": nid(), "lineWrapping": false, "isPreviewMode": false, "nodeId": nid() },
                "content": [{ "type": "text", "text": code }]
            }));
        }

        // 分割线 --- 或 ***
        let trimmed = line.trim();
        if (trimmed.starts_with("---") && trimmed.chars().all(|c| c == '-'))
            || (trimmed.starts_with("***") && trimmed.chars().all(|c| c == '*'))
        {
            self.consume();
            return Some(json!({ "type": "horizontal_rule", "attrs": { "dataDiffId": Value::Null, "nodeId": nid() } }));
        }

        // 折叠块 <details>...</details> → 转成学城 collapse 节点
        if line.trim() == "<details>" || line.trim().starts_with("<details ") {
            return self.parse_details_block();
        }

        // 引用块 >
        if line.starts_with("> ") || line.trim() == ">" {
            let mut quote_lines = Vec::new();
            while self.pos < self.lines.len() {
                let l = self.peek().unwrap_or("");
                if l.starts_with("> ") { quote_lines.push(l[2..].to_string()); self.consume(); }
                else if l.trim() == ">" { quote_lines.push(String::new()); self.consume(); }
                else { break; }
            }
            let joined = quote_lines.join("\n");
            let mut sub = MdParser::new(&joined);
            let mut inner = sub.parse_blocks();
            if inner.is_empty() { inner.push(empty_paragraph()); }
            return Some(json!({ "type": "blockquote", "attrs": { "nodeId": nid() }, "content": inner }));
        }

        // 有序列表
        if is_ordered_list_line(&line) {
            return self.parse_list(ListKind::Ordered, 0);
        }
        // 任务列表
        if is_task_list_line(&line) {
            return self.parse_list(ListKind::Task, 0);
        }
        // 无序列表
        if is_bullet_list_line(&line) {
            return self.parse_list(ListKind::Bullet, 0);
        }

        // 表格
        if line.starts_with('|') {
            return self.parse_table();
        }

        // 普通段落：合并连续非空、非块起始行
        let mut para_lines = Vec::new();
        while self.pos < self.lines.len() {
            let l = self.peek().unwrap_or("");
            if l.trim().is_empty() { break; }
            if is_block_start(l) { break; }
            para_lines.push(self.consume().unwrap_or("").to_string());
        }
        if para_lines.is_empty() { self.consume(); return None; }
        let para_text = para_lines.join("\n");
        let content = safe_paragraph_content(parse_inline(&para_text));
        let mut node = json!({
            "type": "paragraph",
            "attrs": { "indent": 0, "align": "left", "dataDiffId": Value::Null, "nodeId": nid() }
        });
        if let Some(c) = content { node["content"] = Value::Array(c); }
        Some(node)
    }

    /// 解析 <details>...</details> 折叠块，转成学城 collapse 节点。
    /// 语法：
    /// ```text
    /// <details>
    /// <summary>标题</summary>
    ///
    /// > 引用内容（任意 markdown 块）
    ///
    /// </details>
    /// ```
    /// summary 后的内容会递归解析为 collapse_content 的子节点。
    fn parse_details_block(&mut self) -> Option<Value> {
        // 消费 <details> 行
        self.consume();

        let mut summary_text = String::new();
        let mut body_lines: Vec<String> = Vec::new();

        while self.pos < self.lines.len() {
            let l = self.peek().unwrap_or("").to_string();
            if l.trim() == "</details>" {
                self.consume();
                break;
            }
            // 提取 <summary>...</summary>
            if let Some(stripped) = l.trim().strip_prefix("<summary>") {
                if let Some(text) = stripped.strip_suffix("</summary>") {
                    summary_text = text.trim().to_string();
                    self.consume();
                    continue;
                }
            }
            body_lines.push(l);
            self.consume();
        }

        // 递归解析 body（去掉首尾空行避免空段落）
        let body_str = body_lines.join("\n").trim().to_string();
        let mut content = if body_str.is_empty() {
            vec![empty_paragraph()]
        } else {
            let mut sub = MdParser::new(&body_str);
            let mut inner = sub.parse_blocks();
            if inner.is_empty() { inner.push(empty_paragraph()); }
            inner
        };

        let title = json!({
            "type": "collapse_title",
            "attrs": { "align": "left", "nodeId": nid() },
            "content": parse_inline(&summary_text)
        });

        // collapse_content 至少一个块节点
        if content.is_empty() { content.push(empty_paragraph()); }

        Some(json!({
            "type": "collapse",
            "attrs": { "active": false, "dataDiffId": Value::Null, "id": Uuid::new_v4().to_string(), "nodeId": nid() },
            "content": [
                title,
                { "type": "collapse_content", "attrs": { "nodeId": nid() }, "content": content }
            ]
        }))
    }

    fn parse_list(&mut self, kind: ListKind, depth: usize) -> Option<Value> {
        let mut items: Vec<Value> = Vec::new();
        let base_indent = indent_level(self.peek().unwrap_or(""));
        while self.pos < self.lines.len() {
            let line = self.peek().unwrap_or("").to_string();
            if line.trim().is_empty() { break; }
            let cur_indent = indent_level(&line);
            if cur_indent < base_indent { break; }

            // 更深缩进：子列表
            if cur_indent > base_indent && !items.is_empty() {
                let sub_kind = if is_ordered_list_line(&line) { ListKind::Ordered }
                    else if is_task_list_line(&line) { ListKind::Task }
                    else if is_bullet_list_line(&line) { ListKind::Bullet }
                    else { break; };
                let pos_before = self.pos;
                let sub = self.parse_list(sub_kind, depth + 1);
                if self.pos == pos_before { break; }
                if let Some(s) = sub {
                    if let Some(last) = items.last_mut() {
                        let arr = last.get_mut("content").and_then(|v| v.as_array_mut());
                        if let Some(a) = arr { a.push(s); }
                    }
                }
                continue;
            }

            // 当前 kind 的列表项
            let matches_kind = match kind {
                ListKind::Ordered => is_ordered_list_line(&line),
                ListKind::Task => is_task_list_line(&line),
                ListKind::Bullet => is_bullet_list_line(&line) && !is_task_list_line(&line),
            };
            if !matches_kind { break; }
            self.consume();

            let (text_content, checked) = match kind {
                ListKind::Ordered => {
                    let prefix_len = ordered_prefix_len(&line);
                    (line[prefix_len..].to_string(), false)
                }
                ListKind::Task => {
                    let m = parse_task_line(&line);
                    (m.0, m.1)
                }
                ListKind::Bullet => {
                    let prefix_len = bullet_prefix_len(&line);
                    (line[prefix_len..].to_string(), false)
                }
            };

            // 列表项内容：heading 或 paragraph
            let item_content = if let Some((level, htext)) = parse_heading(&text_content) {
                vec![json!({
                    "type": "heading",
                    "attrs": { "level": level, "align": "left", "indent": 0, "dataDiffId": Value::Null, "nodeId": nid() },
                    "content": parse_inline(&htext)
                })]
            } else {
                let c = safe_paragraph_content(parse_inline(&text_content));
                let mut p = json!({ "type": "paragraph", "attrs": { "indent": 0, "align": "left", "dataDiffId": Value::Null, "nodeId": nid() } });
                if let Some(cc) = c { p["content"] = Value::Array(cc); }
                vec![p]
            };

            let (item_type, item_attrs) = match kind {
                ListKind::Task => ("task_item", json!({ "checked": checked, "level": depth, "dataListItemDiffId": Value::Null, "fontSize": Value::Null, "nodeId": nid() })),
                _ => ("list_item", json!({ "level": depth, "hidden": false, "dataListItemDiffId": Value::Null, "fontSize": Value::Null, "nodeId": nid() })),
            };
            items.push(json!({ "type": item_type, "attrs": item_attrs, "content": item_content }));
        }

        let list_type = match kind {
            ListKind::Bullet => "bullet_list",
            ListKind::Ordered => "ordered_list",
            ListKind::Task => "task_list",
        };
        Some(json!({
            "type": list_type,
            "attrs": { "indent": 0, "dataDiffId": Value::Null, "nodeId": nid() },
            "content": items
        }))
    }

    fn parse_table(&mut self) -> Option<Value> {
        let mut rows: Vec<Value> = Vec::new();
        let mut is_first_row = true;
        while self.pos < self.lines.len() {
            let line = self.peek().unwrap_or("");
            if !line.starts_with('|') { break; }
            let line = self.consume().unwrap_or("").to_string();
            // 跳过分割行 | --- | --- |
            let t = line.trim();
            if is_separator_row(t) { is_first_row = false; continue; }
            // 按管道符分割，去掉首尾空段
            let cells: Vec<String> = line.split('|').skip(1)
                .map(|c| c.trim().to_string())
                .collect();
            let cells: Vec<String> = if cells.last().map(|c| c.is_empty()).unwrap_or(false) {
                cells[..cells.len()-1].to_vec()
            } else { cells };

            let cell_nodes: Vec<Value> = cells.iter().map(|cell_text| {
                let content = safe_paragraph_content(parse_inline(cell_text))
                    .unwrap_or_else(|| vec![json!({ "type": "paragraph", "attrs": { "indent": 0, "align": "left", "dataDiffId": Value::Null, "nodeId": nid() } })]);
                // content 里每个是 inline 节点，要包成 paragraph
                let para = json!({ "type": "paragraph", "attrs": { "indent": 0, "align": "left", "dataDiffId": Value::Null, "nodeId": nid() }, "content": content });
                let cell_type = if is_first_row { "table_header" } else { "table_cell" };
                json!({
                    "type": cell_type,
                    "attrs": { "colspan": 1, "rowspan": 1, "colwidth": Value::Null, "textAlign": Value::Null, "verticalAlign": Value::Null, "bgColor": Value::Null, "color": Value::Null, "numCell": Value::Null, "dataCellDiffId": Value::Null, "nodeId": nid() },
                    "content": [para]
                })
            }).collect();
            rows.push(json!({ "type": "table_row", "attrs": { "dataRowDiffId": Value::Null, "nodeId": nid() }, "content": cell_nodes }));
            is_first_row = false;
        }
        Some(json!({
            "type": "table",
            "attrs": { "dataDiffId": Value::Null, "borderColor": "#dddddd", "borderStyle": "solid", "borderWidth": 1, "responsive": true, "indent": 0, "nodeId": nid() },
            "content": rows
        }))
    }
}

// ── 行内解析 ──────────────────────────────────────────────────────────────────

/// 解析行内 markdown，返回 PM inline 节点数组
pub fn parse_inline(text: &str) -> Vec<Value> {
    if text.is_empty() { return vec![]; }
    let mut nodes = Vec::new();
    let mut remaining = text.to_string();
    while !remaining.is_empty() {
        // hard break "  \n"
        if remaining.starts_with("  \n") {
            nodes.push(json!({ "type": "hard_break" }));
            remaining = remaining[3..].to_string();
            continue;
        }
        // 单 \n → hard_break（text 节点不允许换行）
        if remaining.starts_with('\n') {
            nodes.push(json!({ "type": "hard_break" }));
            remaining = remaining[1..].to_string();
            continue;
        }
        // 标准 inline token
        if let Some((tok_nodes, consumed)) = parse_next_inline_token(&remaining) {
            nodes.extend(tok_nodes);
            remaining = remaining[consumed..].to_string();
            continue;
        }
        // 普通文本：前进到下一个特殊字符
        let cut = find_next_special(&remaining).min(remaining.len());
        if cut == 0 {
            // 第一个字符就是特殊字符但没匹配成 token，吃掉一个字符
            let ch_len = remaining.char_indices().nth(1).map(|(i, _)| i).unwrap_or(remaining.len());
            nodes.push(json!({ "type": "text", "text": &remaining[..ch_len] }));
            remaining = remaining[ch_len..].to_string();
        } else {
            nodes.push(json!({ "type": "text", "text": &remaining[..cut] }));
            remaining = remaining[cut..].to_string();
        }
    }
    if nodes.is_empty() { vec![json!({ "type": "text", "text": text })] } else { nodes }
}

/// 尝试解析下一个 inline token，返回 (nodes, consumed_bytes)
fn parse_next_inline_token(text: &str) -> Option<(Vec<Value>, usize)> {
    // ***粗斜体***
    if text.starts_with("***") {
        if let Some(end) = find_after(text, 3, "***") {
            let inner = &text[3..end];
            let nodes = apply_mark(apply_mark(parse_inline(inner), "strong"), "em");
            return Some((nodes, end + 3));
        }
    }
    // **粗体**
    if text.starts_with("**") {
        if let Some(end) = find_after(text, 2, "**") {
            let inner = &text[2..end];
            return Some((apply_mark(parse_inline(inner), "strong"), end + 2));
        }
    }
    // *斜体*
    if text.starts_with('*') {
        if let Some(end) = find_after(text, 1, "*") {
            let inner = &text[1..end];
            return Some((apply_mark(parse_inline(inner), "em"), end + 1));
        }
    }
    // `行内代码`
    if text.starts_with('`') {
        if let Some(end) = find_after(text, 1, "`") {
            let inner = &text[1..end];
            return Some((vec![json!({ "type": "text", "text": inner, "marks": [{ "type": "code" }] })], end + 1));
        }
    }
    // ~~删除线~~
    if text.starts_with("~~") {
        if let Some(end) = find_after(text, 2, "~~") {
            let inner = &text[2..end];
            return Some((apply_mark(parse_inline(inner), "strikethrough"), end + 2));
        }
    }
    // __下划线__
    if text.starts_with("__") {
        if let Some(end) = find_after(text, 2, "__") {
            let inner = &text[2..end];
            return Some((apply_mark(parse_inline(inner), "underline"), end + 2));
        }
    }
    // ![图片](src)
    if text.starts_with("![") {
        if let Some(end_bracket) = text.find("](") {
            let name = &text[2..end_bracket];
            if let Some(end_paren) = find_matching_paren(&text[end_bracket + 2..]) {
                let src = &text[end_bracket + 2..end_bracket + 2 + end_paren];
                let consumed = end_bracket + 2 + end_paren + 1;
                return Some((vec![json!({
                    "type": "image",
                    "attrs": { "src": src, "name": name, "width": 0, "height": 0, "small": "", "origin": "", "mss": "", "link": Value::Null, "border": false, "isFullWidth": false, "nodeId": nid() }
                })], consumed));
            }
        }
    }
    // [链接](url)
    if text.starts_with('[') {
        if let Some(end_bracket) = text.find("](") {
            let link_text = &text[1..end_bracket];
            if let Some(end_paren) = find_matching_paren(&text[end_bracket + 2..]) {
                let href = &text[end_bracket + 2..end_bracket + 2 + end_paren];
                let display = if link_text.trim().is_empty() {
                    if href.is_empty() { " ".to_string() } else { href.to_string() }
                } else { link_text.trim().to_string() };
                let consumed = end_bracket + 2 + end_paren + 1;
                return Some((vec![json!({
                    "type": "link",
                    "attrs": { "id": nid(), "href": href, "title": display, "autoUpdate": false, "nodeId": nid() },
                    "content": [{ "type": "text", "text": display }]
                })], consumed));
            }
        }
    }
    None
}

/// 在 `text[start..]` 之后查找 `needle` 的字节位置（绝对位置）
fn find_after(text: &str, start: usize, needle: &str) -> Option<usize> {
    text[start..].find(needle).map(|i| start + i)
}

/// 找未转义的右括号 ) 的位置（返回相对偏移）
fn find_matching_paren(s: &str) -> Option<usize> {
    s.find(')').map(|i| i)
}

/// 给一组 inline 节点叠加 mark（strong/em/...）
fn apply_mark(nodes: Vec<Value>, mark_type: &str) -> Vec<Value> {
    let mark = json!({ "type": mark_type });
    nodes.into_iter().map(|n| {
        let t = n.get("type").and_then(|v| v.as_str()).unwrap_or("");
        if t != "text" && t != "hard_break" { return n; }
        let mut m = n;
        let mut marks = m.get("marks").cloned().unwrap_or(Value::Array(vec![]));
        if let Value::Array(arr) = &mut marks {
            let mut new_arr = vec![mark.clone()];
            new_arr.append(arr);
            *arr = new_arr;
        }
        m["marks"] = marks;
        m
    }).collect()
}

/// 找下一个特殊字符序列的位置（用于普通文本前进）
fn find_next_special(text: &str) -> usize {
    let specials = ["**", "*", "`", "~~", "__", "[", "!["];
    let mut min = text.len();
    for s in &specials {
        if let Some(idx) = text.find(s) {
            if idx < min { min = idx; }
        }
    }
    min
}

// ── 辅助函数 ──────────────────────────────────────────────────────────────────

#[derive(Clone, Copy)]
enum ListKind { Bullet, Ordered, Task }

fn parse_heading(line: &str) -> Option<(u64, String)> {
    let bytes = line.as_bytes();
    if !bytes.starts_with(b"#") { return None; }
    let mut i = 0;
    while i < bytes.len() && bytes[i] == b'#' { i += 1; }
    if i == 0 || i > 6 { return None; }
    if i >= bytes.len() || bytes[i] != b' ' { return None; }
    Some((i as u64, line[i + 1..].trim().to_string()))
}

fn is_block_start(line: &str) -> bool {
    parse_heading(line).is_some()
        || line.starts_with("```")
        || line.starts_with(":::")
        || line.starts_with('>')
        || line.starts_with('|')
        || line.trim().starts_with("<details>")
        || line.trim().starts_with("<details ")
        || is_bullet_list_line(line)
        || is_ordered_list_line(line)
        || is_task_list_line(line)
        || {
            let t = line.trim();
            (t.starts_with("---") && t.chars().all(|c| c == '-'))
                || (t.starts_with("***") && t.chars().all(|c| c == '*'))
        }
}

fn is_ordered_list_line(line: &str) -> bool {
    let t = line.trim_start();
    let mut chars = t.chars();
    let mut has_digit = false;
    while let Some(c) = chars.next() {
        if c.is_ascii_digit() { has_digit = true; }
        else if c == '.' { return has_digit && chars.next() == Some(' '); }
        else { return false; }
    }
    false
}

fn is_task_list_line(line: &str) -> bool {
    let t = line.trim_start();
    t.starts_with("- [") && t.len() > 4 && (t.as_bytes()[3] == b' ' || t.as_bytes()[3] == b'x') && t.as_bytes()[4] == b']'
}

fn is_bullet_list_line(line: &str) -> bool {
    let t = line.trim_start();
    t.starts_with("- ") || t.starts_with("* ") || t.starts_with("+ ")
}

fn ordered_prefix_len(line: &str) -> usize {
    let t = line.trim_start();
    let lead = line.len() - t.len();
    let mut i = 0;
    let bytes = t.as_bytes();
    while i < bytes.len() && bytes[i].is_ascii_digit() { i += 1; }
    // . + space
    lead + i + 2
}

fn bullet_prefix_len(line: &str) -> usize {
    let t = line.trim_start();
    let lead = line.len() - t.len();
    lead + 2 // marker + space
}

fn parse_task_line(line: &str) -> (String, bool) {
    // - [x] text / - [ ] text
    let t = line.trim_start();
    let checked = t.as_bytes()[3] == b'x';
    // "- [x] " 跳过前缀
    let rest = &t[5..]; // 跳过 "- [x]"
    let rest = rest.strip_prefix(' ').unwrap_or(rest);
    (rest.to_string(), checked)
}

fn indent_level(line: &str) -> usize {
    line.chars().take_while(|c| *c == ' ').count()
}

fn is_separator_row(t: &str) -> bool {
    // | --- | :---: | ---: |
    if !t.starts_with('|') { return false; }
    let cells: Vec<&str> = t.split('|').skip(1).collect();
    // 过滤掉末尾空段（行末 | 产生），只看非空 cell 是否全是 -/:/空格
    let non_empty: Vec<&str> = cells.iter().map(|c| c.trim()).filter(|c| !c.is_empty()).collect();
    if non_empty.is_empty() { return false; }
    non_empty.iter().all(|c| c.chars().all(|ch| ch == '-' || ch == ':' || ch == ' '))
}

fn normalize_lang(raw: &str) -> String {
    let r = raw.trim();
    if r.is_empty() { return "Plain Text".to_string(); }
    let lower = r.to_lowercase();
    match lower.as_str() {
        "js" | "javascript" => "JavaScript".to_string(),
        "ts" | "typescript" => "TypeScript".to_string(),
        "py" | "python" => "Python".to_string(),
        "java" => "Java".to_string(),
        "go" | "golang" => "Go".to_string(),
        "rust" | "rs" => "Rust".to_string(),
        "c" => "C".to_string(),
        "cpp" | "c++" => "C++".to_string(),
        "shell" | "sh" | "bash" => "Shell".to_string(),
        "json" => "JSON".to_string(),
        "html" => "HTML".to_string(),
        "css" => "CSS".to_string(),
        "sql" => "SQL".to_string(),
        "yml" | "yaml" => "YAML".to_string(),
        "xml" => "XML".to_string(),
        "md" | "markdown" => "Markdown".to_string(),
        _ => r.to_string(),
    }
}

fn empty_paragraph() -> Value {
    json!({ "type": "paragraph", "attrs": { "indent": 0, "align": "left", "dataDiffId": Value::Null, "nodeId": nid() } })
}

fn safe_paragraph_content(nodes: Vec<Value>) -> Option<Vec<Value>> {
    let filtered: Vec<Value> = nodes.into_iter()
        .filter(|n| !(n.get("type").and_then(|v| v.as_str()) == Some("text")
            && n.get("text").and_then(|v| v.as_str()).map(|s| s.is_empty()).unwrap_or(false)))
        .collect();
    if filtered.is_empty() { None } else { Some(filtered) }
}

// ── 测试 ──────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_heading() {
        let pm = md_to_pm("# 标题\n\n正文", "标题");
        let content = pm["content"].as_array().unwrap();
        assert_eq!(content[0]["type"], "title");
        assert_eq!(content[0]["content"][0]["text"], "标题");
        assert!(content.iter().skip(1).all(|n| n["type"] != "heading" || n["attrs"]["level"] != 1));
    }

    #[test]
    fn test_title_from_md_requires_first_line_h1() {
        assert_eq!(title_from_md("# 技术方案\n正文").as_deref(), Some("技术方案"));
        assert_eq!(title_from_md("#   技术方案  \n正文").as_deref(), Some("技术方案"));
        assert_eq!(title_from_md("## 背景\n正文"), None);
        assert_eq!(title_from_md("\n# 技术方案"), None);
        assert_eq!(title_from_md("#   "), None);
    }

    #[test]
    fn test_paragraph() {
        let pm = md_to_pm("这是一段文字", "无标题文档");
        assert_eq!(pm["content"][0]["type"], "title");
        assert_eq!(pm["content"][1]["type"], "paragraph");
        assert_eq!(pm["content"][1]["content"][0]["text"], "这是一段文字");
    }

    #[test]
    fn test_bold_italic() {
        let pm = md_to_pm("**粗体** *斜体* ***粗斜体***", "t");
        let p = &pm["content"][1]; // paragraph
        let inline = p["content"].as_array().unwrap();
        // 粗体
        assert_eq!(inline[0]["marks"][0]["type"], "strong");
        assert_eq!(inline[0]["text"], "粗体");
    }

    #[test]
    fn test_code_inline() {
        let pm = md_to_pm("这是 `code` 内联代码", "t");
        let p = &pm["content"][1]["content"].as_array().unwrap();
        let code_node = p.iter().find(|n| n.get("marks").is_some()).unwrap();
        assert_eq!(code_node["marks"][0]["type"], "code");
        assert_eq!(code_node["text"], "code");
    }

    #[test]
    fn test_bullet_list() {
        let pm = md_to_pm("- 项一\n- 项二\n- 项三", "t");
        let list = &pm["content"][1];
        assert_eq!(list["type"], "bullet_list");
        assert_eq!(list["content"].as_array().unwrap().len(), 3);
    }

    #[test]
    fn test_ordered_list() {
        let pm = md_to_pm("1. 第一\n2. 第二\n3. 第三", "t");
        let list = &pm["content"][1];
        assert_eq!(list["type"], "ordered_list");
        assert_eq!(list["content"].as_array().unwrap().len(), 3);
    }

    #[test]
    fn test_task_list() {
        let pm = md_to_pm("- [x] 完成\n- [ ] 未完成", "t");
        let list = &pm["content"][1];
        assert_eq!(list["type"], "task_list");
        let items = list["content"].as_array().unwrap();
        assert_eq!(items[0]["attrs"]["checked"], true);
        assert_eq!(items[1]["attrs"]["checked"], false);
    }

    #[test]
    fn test_code_block() {
        let pm = md_to_pm("```rust\nfn main() {}\n```", "t");
        let cb = &pm["content"][1];
        assert_eq!(cb["type"], "code_block");
        assert_eq!(cb["attrs"]["language"], "Rust");
        assert_eq!(cb["content"][0]["text"], "fn main() {}");
    }

    #[test]
    fn test_table() {
        let pm = md_to_pm("| 列A | 列B |\n| --- | --- |\n| 值1 | 值2 |", "t");
        let table = &pm["content"][1];
        assert_eq!(table["type"], "table");
        let rows = table["content"].as_array().unwrap();
        assert_eq!(rows.len(), 2); // header + 1 row
        assert_eq!(rows[0]["content"][0]["type"], "table_header");
        assert_eq!(rows[1]["content"][0]["type"], "table_cell");
    }

    #[test]
    fn test_link() {
        let pm = md_to_pm("[美团](https://meituan.com)", "t");
        let link = &pm["content"][1]["content"][0];
        assert_eq!(link["type"], "link");
        assert_eq!(link["attrs"]["href"], "https://meituan.com");
        assert_eq!(link["content"][0]["text"], "美团");
    }

    #[test]
    fn test_image() {
        let pm = md_to_pm("![图片名](https://x.com/a.png)", "t");
        let img = &pm["content"][1]["content"][0];
        assert_eq!(img["type"], "image");
        assert_eq!(img["attrs"]["src"], "https://x.com/a.png");
        assert_eq!(img["attrs"]["name"], "图片名");
    }

    #[test]
    fn test_blockquote() {
        let pm = md_to_pm("> 引用内容\n> 第二行", "t");
        let bq = &pm["content"][1];
        assert_eq!(bq["type"], "blockquote");
        assert!(bq["content"].as_array().unwrap().len() > 0);
    }

    #[test]
    fn test_details_to_collapse() {
        let md = "<details>\n<summary>官方原文</summary>\n\n> 引用内容\n> 第二行\n\n</details>\n\n正文";
        let pm = md_to_pm(md, "t");
        let nodes = pm["content"].as_array().unwrap();
        // content[0] 是 title，content[1] 是 collapse
        let collapse = &nodes[1];
        assert_eq!(collapse["type"], "collapse");
        let inner = collapse["content"].as_array().unwrap();
        assert_eq!(inner[0]["type"], "collapse_title");
        assert_eq!(inner[0]["content"][0]["text"], "官方原文");
        assert_eq!(inner[1]["type"], "collapse_content");
        // collapse_content 内是 blockquote
        let cc = &inner[1]["content"];
        assert_eq!(cc[0]["type"], "blockquote");
    }

    #[test]
    fn test_hr() {
        let pm = md_to_pm("---\n\n正文", "t");
        let hr = &pm["content"][1];
        assert_eq!(hr["type"], "horizontal_rule");
    }

    #[test]
    fn test_nested_list() {
        let pm = md_to_pm("- 外层\n  - 内层1\n  - 内层2\n- 外层2", "t");
        let list = &pm["content"][1];
        assert_eq!(list["type"], "bullet_list");
        let items = list["content"].as_array().unwrap();
        assert_eq!(items.len(), 2);
        // 第一个 item 含子列表
        let first_content = items[0]["content"].as_array().unwrap();
        assert!(first_content.iter().any(|n| n["type"] == "bullet_list"));
    }
}
