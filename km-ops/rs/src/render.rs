use std::collections::HashMap;

use serde_json::Value;

// ── render 入口 ────────────────────────────────────────────────────────────────

pub struct RenderResult {
    pub html: String,
    pub pm_node_ids: Vec<Option<String>>,
}

pub fn render(pm_doc: &Value) -> RenderResult {
    let roots = if pm_doc.get("type").and_then(|v| v.as_str()) == Some("doc") {
        pm_doc.get("content").and_then(|v| v.as_array()).map(|a| a.as_slice()).unwrap_or(&[])
    } else {
        std::slice::from_ref(pm_doc)
    };

    let results: Vec<_> = roots.iter().filter_map(|n| node_result(n)).collect();
    let html = results.iter().map(|r| r.html.as_str()).collect::<Vec<_>>().join("\n");
    let pm_node_ids: Vec<_> = results.iter().map(|r| r.pm_node_id.clone()).collect();

    RenderResult { html, pm_node_ids }
}

// ── 节点结果 ──────────────────────────────────────────────────────────────────

struct NodeResult {
    html: String,
    pm_node_id: Option<String>,
}

fn node_result(pm_node: &Value) -> Option<NodeResult> {
    let node_type = pm_node.get("type")?.as_str()?;
    let node_id = pm_node.get("attrs").and_then(|a| a.get("nodeId")).and_then(|v| v.as_str()).map(String::from);
    let children = pm_node.get("content").and_then(|v| v.as_array()).map(|a| a.as_slice()).unwrap_or(&[]);

    match node_type {
        "title" => {
            let inner = inline_content(children);
            Some(leaf_aligned("h1", &inner, node_id, &align_style_attr(pm_node)))
        }
        "heading" => {
            let lv = pm_node.get("attrs").and_then(|a| a.get("level")).and_then(|v| v.as_u64()).unwrap_or(1);
            let inner = inline_content(children);
            Some(leaf_aligned(&format!("h{lv}"), &inner, node_id, &align_style_attr(pm_node)))
        }
        "paragraph" => {
            let inner = inline_content(children);
            Some(leaf_aligned("p", &inner, node_id, &align_style_attr(pm_node)))
        }
        "blockquote" => {
            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            Some(leaf("blockquote", &inner, node_id))
        }
        // 富节点
        "image" => {
            let src = pm_node.get("attrs").and_then(|a| a.get("src")).and_then(|v| v.as_str()).unwrap_or("");
            let alt = pm_node.get("attrs").and_then(|a| a.get("name")).and_then(|v| v.as_str()).unwrap_or("");
            let w = pm_node.get("attrs").and_then(|a| a.get("width")).and_then(|v| v.as_u64()).map(|w| format!(" width=\"{w}\"")).unwrap_or_default();
            let h = pm_node.get("attrs").and_then(|a| a.get("height")).and_then(|v| v.as_u64()).map(|h| format!(" height=\"{h}\"")).unwrap_or_default();
            let html = format!("<img src=\"{src}\" alt=\"{alt}\"{w}{h}/>");
            let mut attrs = HashMap::new();
            attrs.insert("src".to_string(), src.to_string());
            Some(NodeResult { html, pm_node_id: node_id })
        }
        "drawio" => {
            let src = pm_node.get("attrs").and_then(|a| a.get("src")).and_then(|v| v.as_str()).unwrap_or("");
            let w = pm_node.get("attrs").and_then(|a| a.get("width")).and_then(|v| v.as_u64()).map(|w| format!(" width=\"{w}\"")).unwrap_or_default();
            let h = pm_node.get("attrs").and_then(|a| a.get("height")).and_then(|v| v.as_u64()).map(|h| format!(" height=\"{h}\"")).unwrap_or_default();
            let html = format!("<km-drawio src=\"{src}\"{w}{h}/>");
            Some(NodeResult { html, pm_node_id: node_id })
        }
        "xtable" => {
            let xtid = pm_node.get("attrs").and_then(|a| a.get("xtableId")).and_then(|v| v.as_str()).unwrap_or("");
            let html = format!("<km-xtable xtable-id=\"{xtid}\"/>");
            Some(NodeResult { html, pm_node_id: node_id })
        }
        "minder" => Some(NodeResult { html: "<km-minder/>".into(), pm_node_id: node_id }),
        "video" => {
            let url = pm_node.get("attrs").and_then(|a| a.get("url").or_else(|| a.get("src"))).and_then(|v| v.as_str()).unwrap_or("");
            let name = pm_node.get("attrs").and_then(|a| a.get("name")).and_then(|v| v.as_str()).unwrap_or("");
            let html = format!("<km-video src=\"{url}\" name=\"{name}\"/>");
            Some(NodeResult { html, pm_node_id: node_id })
        }
        "audio" => {
            let url = pm_node.get("attrs").and_then(|a| a.get("url").or_else(|| a.get("src"))).and_then(|v| v.as_str()).unwrap_or("");
            let name = pm_node.get("attrs").and_then(|a| a.get("name")).and_then(|v| v.as_str()).unwrap_or("");
            let html = format!("<km-audio src=\"{url}\" name=\"{name}\"/>");
            Some(NodeResult { html, pm_node_id: node_id })
        }
        "attachment" => {
            let name = pm_node.get("attrs").and_then(|a| a.get("name")).and_then(|v| v.as_str()).unwrap_or("");
            let src = pm_node.get("attrs").and_then(|a| a.get("src")).and_then(|v| v.as_str()).unwrap_or("");
            let html = format!("<km-attachment name=\"{name}\" src=\"{src}\"/>");
            Some(NodeResult { html, pm_node_id: node_id })
        }
        "plantuml" => Some(NodeResult { html: "<km-plantuml/>".into(), pm_node_id: node_id }),
        "catalog" => Some(NodeResult { html: "<km-catalog/>".into(), pm_node_id: node_id }),
        "footnote_list" => Some(NodeResult { html: "<km-footnote-list/>".into(), pm_node_id: node_id }),
        "hr" | "horizontal_rule" => Some(NodeResult { html: "<hr/>".into(), pm_node_id: node_id }),
        "code_block" => {
            let lang = pm_node.get("attrs").and_then(|a| a.get("language")).and_then(|v| v.as_str()).unwrap_or("");
            let code: String = children.iter().filter_map(|c| c.get("text").and_then(|v| v.as_str())).map(esc).collect();
            let html = format!("<pre language=\"{lang}\"><code>{code}</code></pre>");
            Some(NodeResult { html, pm_node_id: node_id })
        }
        "bullet_list" | "list" => {
            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            Some(leaf("ul", &inner, node_id))
        }
        "ordered_list" => {
            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            Some(leaf("ol", &inner, node_id))
        }
        "task_list" => {
            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            Some(NodeResult { html: format!("<ul class=\"task-list\">{inner}</ul>"), pm_node_id: node_id })
        }
        "list_item" | "task_item" => {
            let checked = pm_node.get("attrs").and_then(|a| a.get("checked")).and_then(|v| v.as_bool());
            let checkbox = if let Some(true) = checked {
                "<input type=\"checkbox\" checked/>"
            } else if let Some(false) = checked {
                "<input type=\"checkbox\"/>"
            } else {
                ""
            };

            // If the single child is a paragraph, render its inline content directly
            if children.len() == 1 {
                if let Some(first_child) = children.first() {
                    if first_child.get("type").and_then(|v| v.as_str()) == Some("paragraph") {
                        if let Some(para_children_vec) = first_child.get("content").and_then(|v| v.as_array()) {
                            let inner = inline_content(para_children_vec.as_slice());
                            let html = if checkbox.is_empty() {
                                format!("<li>{inner}</li>")
                            } else {
                                format!("<li>{checkbox}{inner}</li>")
                            };
                            return Some(NodeResult { html, pm_node_id: node_id });
                        }
                    }
                }
            }
            // Otherwise, render children as block elements
            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            let html = if checkbox.is_empty() {
                format!("<li>{inner}</li>")
            } else {
                format!("<li>{checkbox}{inner}</li>")
            };
            Some(NodeResult { html, pm_node_id: node_id })
        }
        "table" => {
            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            Some(leaf("table", &inner, node_id))
        }
        "table_row" => {
            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            Some(leaf("tr", &inner, node_id))
        }
        "table_cell" | "table_header" => {
            let tag = if node_type == "table_header" { "th" } else { "td" };
            let attrs_obj = pm_node.get("attrs");
            let rowspan = attrs_obj.and_then(|a| a.get("rowspan")).and_then(|v| v.as_u64()).map(|rs| format!(" rowspan=\"{rs}\"")).unwrap_or_default();
            let colspan = attrs_obj.and_then(|a| a.get("colspan")).and_then(|v| v.as_u64()).map(|cs| format!(" colspan=\"{cs}\"")).unwrap_or_default();

            // colwidth: 可能是单值 [96] 或多值 [99,99,122]（跨列合并）
            // data-colwidth 存所有值，style width 取各列之和
            let colwidth_arr: Vec<u64> = attrs_obj
                .and_then(|a| a.get("colwidth")).and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|v| v.as_u64()).collect())
                .unwrap_or_default();
            let data_colwidth = if colwidth_arr.is_empty() { String::new() } else {
                let vals: Vec<String> = colwidth_arr.iter().map(|v| v.to_string()).collect();
                format!(" data-colwidth=\"{}\"", vals.join(","))
            };
            let width_px: u64 = colwidth_arr.iter().sum();

            // bgColor / verticalAlign / color (字体色)
            let bg_color   = attrs_obj.and_then(|a| a.get("bgColor")).and_then(|v| v.as_str()).filter(|s| !s.is_empty());
            let vert_align = attrs_obj.and_then(|a| a.get("verticalAlign")).and_then(|v| v.as_str()).filter(|s| !s.is_empty());
            let font_color = attrs_obj.and_then(|a| a.get("color")).and_then(|v| v.as_str()).filter(|s| !s.is_empty());

            let mut style_parts: Vec<String> = Vec::new();
            if width_px > 0  { style_parts.push(format!("width:{width_px}px")); }
            if let Some(bg)  = bg_color   { style_parts.push(format!("background-color:{bg}")); }
            if let Some(va)  = vert_align { style_parts.push(format!("vertical-align:{va}")); }
            if let Some(fc)  = font_color { style_parts.push(format!("color:{fc}")); }
            let style = if style_parts.is_empty() { String::new() }
                        else { format!(" style=\"{}\"", style_parts.join(";")) };

            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            let html = format!("<{tag}{colspan}{rowspan}{data_colwidth}{style}>{inner}</{tag}>");
            Some(NodeResult { html, pm_node_id: node_id })
        }
        "note" => {
            let note_type = pm_node.get("attrs").and_then(|a| a.get("type")).and_then(|v| v.as_str()).unwrap_or("info");
            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            let html = format!("<km-note type=\"{note_type}\">{inner}</km-note>");
            Some(NodeResult { html, pm_node_id: node_id })
        }
        "note_title" => {
            let inner = inline_content(children);
            let style = align_style_attr(pm_node);
            Some(NodeResult { html: format!("<summary{style}>{inner}</summary>"), pm_node_id: node_id })
        }
        "note_content" => {
            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            Some(NodeResult { html: format!("<div>{inner}</div>"), pm_node_id: node_id })
        }
        "collapse" | "collapse_block" => {
            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            let html = format!("<km-collapse>{inner}</km-collapse>");
            Some(NodeResult { html, pm_node_id: node_id })
        }
        "collapse_title" => {
            let inner = inline_content(children);
            let style = align_style_attr(pm_node);
            Some(NodeResult { html: format!("<summary{style}>{inner}</summary>"), pm_node_id: node_id })
        }
        "collapse_content" => {
            let inner: String = children.iter().filter_map(|c| node_result(c)).map(|r| r.html).collect();
            Some(NodeResult { html: format!("<div>{inner}</div>"), pm_node_id: node_id })
        }
        _ => {
            Some(NodeResult { html: String::new(), pm_node_id: node_id })
        }
    }
}

fn leaf(tag: &str, inner_html: &str, pm_node_id: Option<String>) -> NodeResult {
    NodeResult {
        html: format!("<{tag}>{inner_html}</{tag}>"),
        pm_node_id,
    }
}

/// 读取 PM 节点 attrs.align，返回注入到开标签的 style 片段（含前导空格）。
/// "" / "left" / 缺省 视为默认左对齐，不输出 style。
fn align_style_attr(pm_node: &Value) -> String {
    let align = pm_node.get("attrs").and_then(|a| a.get("align")).and_then(|v| v.as_str()).unwrap_or("");
    match align {
        "" | "left" => String::new(),
        // 白名单放行合法对齐值；未知值视为默认，避免脏数据注入破坏 HTML
        "center" | "right" | "justify" | "start" | "end" => format!(" style=\"text-align: {align}\""),
        _ => String::new(),
    }
}

/// 带对齐 style 的 leaf：输出 <tag style="...">inner</tag>
fn leaf_aligned(tag: &str, inner_html: &str, pm_node_id: Option<String>, style: &str) -> NodeResult {
    NodeResult {
        html: format!("<{tag}{style}>{inner_html}</{tag}>"),
        pm_node_id,
    }
}

// ── 行内内容渲染 ──────────────────────────────────────────────────────────────

fn inline_content(nodes: &[Value]) -> String {
    nodes.iter().map(|n| {
        let node_type = n.get("type").and_then(|v| v.as_str()).unwrap_or("");
        match node_type {
            "text" => {
                let text = n.get("text").and_then(|v| v.as_str()).unwrap_or("");
                let marks = n.get("marks").and_then(|v| v.as_array());
                apply_marks(&esc(text), marks)
            }
            "hard_break" => "<br/>".to_string(),
            "mention" => {
                let uid = n.get("attrs").and_then(|a| a.get("uid")).and_then(|v| v.as_str()).unwrap_or("");
                let name = n.get("attrs").and_then(|a| a.get("name")).and_then(|v| v.as_str()).unwrap_or("");
                format!("<km-mention uid=\"{uid}\">{name}</km-mention>")
            }
            "link" => {
                let href = n.get("attrs").and_then(|a| a.get("href")).and_then(|v| v.as_str()).unwrap_or("");
                let inner = n.get("content").and_then(|v| v.as_array()).map(|a| inline_content(a)).unwrap_or_default();
                format!("<a href=\"{href}\">{inner}</a>")
            }
            "open_link" => {
                let href = n.get("attrs").and_then(|a| a.get("href")).and_then(|v| v.as_str()).unwrap_or("");
                let otype = n.get("attrs").and_then(|a| a.get("type")).and_then(|v| v.as_str()).unwrap_or("");
                format!("<km-open-link href=\"{href}\" data-otype=\"{otype}\"/>")
            }
            "open_card" => {
                let href = n.get("attrs").and_then(|a| a.get("href")).and_then(|v| v.as_str()).unwrap_or("");
                let otype = n.get("attrs").and_then(|a| a.get("type")).and_then(|v| v.as_str()).unwrap_or("");
                format!("<km-open-card href=\"{href}\" data-otype=\"{otype}\"/>")
            }
            // 自闭合 inline block
            "image" | "drawio" | "video" | "audio" | "xtable" | "minder" | "attachment" | "plantuml" => {
                inline_block(n)
            }
            _ => String::new(),
        }
    }).collect()
}

fn inline_block(pm_node: &Value) -> String {
    let node_type = pm_node.get("type").and_then(|v| v.as_str()).unwrap_or("");
    let attrs = pm_node.get("attrs");
    match node_type {
        "image" => {
            let src = attrs.and_then(|a| a.get("src")).and_then(|v| v.as_str()).unwrap_or("");
            let alt = attrs.and_then(|a| a.get("name")).and_then(|v| v.as_str()).unwrap_or("");
            let w = attrs.and_then(|a| a.get("width")).and_then(|v| v.as_u64()).map(|w| format!(" width=\"{w}\"")).unwrap_or_default();
            let h = attrs.and_then(|a| a.get("height")).and_then(|v| v.as_u64()).map(|h| format!(" height=\"{h}\"")).unwrap_or_default();
            format!("<img src=\"{src}\" alt=\"{alt}\"{w}{h}/>")
        }
        "drawio" => {
            let src = attrs.and_then(|a| a.get("src")).and_then(|v| v.as_str()).unwrap_or("");
            format!("<km-drawio src=\"{src}\"/>")
        }
        "video" => {
            let url = attrs.and_then(|a| a.get("url").or_else(|| a.get("src"))).and_then(|v| v.as_str()).unwrap_or("");
            let name = attrs.and_then(|a| a.get("name")).and_then(|v| v.as_str()).unwrap_or("");
            format!("<km-video src=\"{url}\" name=\"{name}\"/>")
        }
        "audio" => {
            let url = attrs.and_then(|a| a.get("url").or_else(|| a.get("src"))).and_then(|v| v.as_str()).unwrap_or("");
            let name = attrs.and_then(|a| a.get("name")).and_then(|v| v.as_str()).unwrap_or("");
            format!("<km-audio src=\"{url}\" name=\"{name}\"/>")
        }
        _ => String::new(),
    }
}

// ── 行内标记 ──────────────────────────────────────────────────────────────────

fn apply_marks(text: &str, marks: Option<&Vec<Value>>) -> String {
    let Some(marks) = marks else { return text.to_string() };
    let mut result = text.to_string();
    for m in marks {
        let mark_type = m.get("type").and_then(|v| v.as_str()).unwrap_or("");
        match mark_type {
            "strong" => result = format!("<strong>{result}</strong>"),
            "em" => result = format!("<em>{result}</em>"),
            "underline" => result = format!("<u>{result}</u>"),
            "strikethrough" => result = format!("<del>{result}</del>"),
            "code" => result = format!("<code>{result}</code>"),
            "sub" => result = format!("<sub>{result}</sub>"),
            "sup" => result = format!("<sup>{result}</sup>"),
            "color" => {
                let color = m.get("attrs").and_then(|a| a.get("color")).and_then(|v| v.as_str()).unwrap_or("");
                result = format!("<span color=\"{color}\">{result}</span>")
            }
            "backgroundcolor" => {
                let color = m.get("attrs").and_then(|a| a.get("color")).and_then(|v| v.as_str()).unwrap_or("");
                result = format!("<span bg=\"{color}\">{result}</span>")
            }
            "link" => {
                let href = m.get("attrs").and_then(|a| a.get("href")).and_then(|v| v.as_str()).unwrap_or("");
                result = format!("<a href=\"{href}\">{result}</a>")
            }
            _ => {}
        }
    }
    result
}

/// HTML 转义
fn esc(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}


// ── 测试 ──────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    // ── 基础渲染 ──────────────────────────────────────────────────────────

    #[test]
    fn test_render_title() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "title", "content": [{ "type": "text", "text": "文档标题" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<h1>文档标题</h1>"));
    }

    #[test]
    fn test_render_heading() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "heading", "attrs": { "level": 2 }, "content": [{ "type": "text", "text": "二级标题" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<h2>二级标题</h2>"));
    }

    #[test]
    fn test_render_paragraph() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "正文内容" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<p>正文内容</p>"));
    }

    // ── 行内标记 ──────────────────────────────────────────────────────────

    #[test]
    fn test_render_strong() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "粗体", "marks": [{ "type": "strong" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<strong>粗体</strong>"));
    }

    #[test]
    fn test_render_em() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "斜体", "marks": [{ "type": "em" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<em>斜体</em>"));
    }

    #[test]
    fn test_render_color_mark() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "红字", "marks": [{ "type": "color", "attrs": { "color": "#ff0000" } }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<span color=\"#ff0000\""));
    }

    // ── 富节点 ────────────────────────────────────────────────────────────

    #[test]
    fn test_render_drawio_standalone() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "drawio", "attrs": { "src": "https://cdn/a.svg" } }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<km-drawio src=\"https://cdn/a.svg\""));
    }

    #[test]
    fn test_render_video_standalone() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "video", "attrs": { "url": "https://cdn/v.mp4", "name": "demo.mp4" } }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<km-video src=\"https://cdn/v.mp4\""));
    }

    // ── inline_content ───────────────────────────────────────────────────

    #[test]
    fn test_inline_content_drawio_inside_paragraph() {
        let nodes = vec![
            json!({"type": "text", "text": "前置"}),
            json!({"type": "drawio", "attrs": {"src": "https://cdn/flow.svg"}}),
            json!({"type": "text", "text": "后置"}),
        ];
        let html = inline_content(&nodes);
        assert!(html.contains("前置"));
        assert!(html.contains("km-drawio"));
        assert!(html.contains("后置"));
    }

    #[test]
    fn test_apply_marks_multiple() {
        let marks = vec![
            json!({"type": "strong"}),
            json!({"type": "em"}),
        ];
        let result = apply_marks("粗斜体", Some(&marks));
        assert!(result.contains("<strong>"));
        assert!(result.contains("<em>"));
    }

    #[test]
    fn test_mark_backgroundcolor() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "高亮", "marks": [{ "type": "backgroundcolor", "attrs": { "color": "#ffff00" } }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<span bg="));
    }

    #[test]
    fn test_mark_strikethrough() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "删除线", "marks": [{ "type": "strikethrough" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<del>"));
    }

    #[test]
    fn test_mark_code_inline() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "const x", "marks": [{ "type": "code" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<code>"));
    }

    #[test]
    fn test_render_audio_standalone() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "audio", "attrs": { "url": "https://cdn/a.mp3", "name": "music.mp3" } }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<km-audio"));
    }

    #[test]
    fn test_render_attachment() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "attachment", "attrs": { "name": "file.pdf", "src": "https://cdn/doc.pdf" } }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<km-attachment"));
    }

    #[test]
    fn test_render_blockquote() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "blockquote", "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "引用" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<blockquote>"));
    }

    #[test]
    fn test_render_horizontal_rule() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "hr" }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<hr"));
    }

    #[test]
    fn test_code_block_with_language() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "code_block", "attrs": { "language": "Rust" }, "content": [{ "type": "text", "text": "fn main() {}" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<pre language=\"Rust\""));
        assert!(result.html.contains("fn main()"));
    }

    // ── 标记组合测试 ──────────────────────────────────────────────────────

    #[test]
    fn test_mark_strong_and_em() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "粗斜体", "marks": [{ "type": "strong" }, { "type": "em" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<strong>") && result.html.contains("<em>"));
    }

    #[test]
    fn test_mark_strong_em_underline() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "文本", "marks": [{ "type": "strong" }, { "type": "em" }, { "type": "underline" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<strong>") && result.html.contains("<em>") && result.html.contains("<u>"));
    }

    #[test]
    fn test_mark_color_and_backgroundcolor() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "彩文字", "marks": [{ "type": "color", "attrs": { "color": "#ff0000" } }, { "type": "backgroundcolor", "attrs": { "color": "#ffff00" } }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<span color=\"#ff0000\""));
        assert!(result.html.contains("<span bg=\"#ffff00\""));
    }

    #[test]
    fn test_mark_code_and_strong() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "const", "marks": [{ "type": "code" }, { "type": "strong" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<code>") && result.html.contains("<strong>"));
    }

    #[test]
    fn test_mark_strikethrough_and_color() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "删", "marks": [{ "type": "strikethrough" }, { "type": "color", "attrs": { "color": "#888888" } }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<del>") && result.html.contains("<span color="));
    }

    #[test]
    fn test_mark_sub_and_sup() {
        // 测试上标和下标不应同时出现，但测试单独的功能
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "H₂O", "marks": [{ "type": "sub" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<sub>"));
    }

    #[test]
    fn test_mark_sup_alone() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "x²", "marks": [{ "type": "sup" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<sup>"));
    }

    #[test]
    fn test_mark_all_combinations_strong_em_underline_color_bg() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "全格式", "marks": [
                    { "type": "strong" },
                    { "type": "em" },
                    { "type": "underline" },
                    { "type": "color", "attrs": { "color": "#0000ff" } },
                    { "type": "backgroundcolor", "attrs": { "color": "#00ff00" } }
                ] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<strong>") && result.html.contains("<em>") && result.html.contains("<u>"));
        assert!(result.html.contains("<span color=\"#0000ff\"") && result.html.contains("<span bg=\"#00ff00\""));
    }

    #[test]
    fn test_mark_code_strikethrough_sub_sup() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "复杂", "marks": [
                    { "type": "code" },
                    { "type": "strikethrough" },
                    { "type": "sub" },
                    { "type": "sup" }
                ] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<code>") && result.html.contains("<del>") &&
                result.html.contains("<sub>") && result.html.contains("<sup>"));
    }

    // ── 节点类型测试 ──────────────────────────────────────────────────────

    #[test]
    fn test_render_hr_variant_horizontal_rule() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "horizontal_rule" }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<hr"));
    }

    #[test]
    fn test_render_code_block_without_language() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "code_block", "attrs": {}, "content": [{ "type": "text", "text": "plain code" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<pre language=\"\"") && result.html.contains("plain code"));
    }

    #[test]
    fn test_render_code_block_with_special_chars() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "code_block", "attrs": { "language": "js" }, "content": [{ "type": "text", "text": "<div> & </div>" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("&lt;div&gt;") && result.html.contains("&amp;"));
    }

    #[test]
    fn test_render_blockquote_with_multiple_paragraphs() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "blockquote", "content": [
                    { "type": "paragraph", "content": [{ "type": "text", "text": "第一行" }] },
                    { "type": "paragraph", "content": [{ "type": "text", "text": "第二行" }] }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<blockquote>") && result.html.contains("<p>第一行</p>") &&
                result.html.contains("<p>第二行</p>") && result.html.contains("</blockquote>"));
    }

    #[test]
    fn test_render_blockquote_with_marks() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "blockquote", "content": [
                    { "type": "paragraph", "content": [{ "type": "text", "text": "引用", "marks": [{ "type": "em" }] }] }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<blockquote>") && result.html.contains("<em>引用</em>"));
    }

    #[test]
    fn test_render_multiple_hr() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "hr" },
                { "type": "paragraph", "content": [{ "type": "text", "text": "中间" }] },
                { "type": "hr" }
            ]
        });
        let result = render(&doc);
        assert_eq!(result.html.matches("<hr").count(), 2);
    }

    // ── 字符转义测试 ──────────────────────────────────────────────────────

    #[test]
    fn test_esc_xss_script_tag() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "<script>alert('xss')</script>" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("&lt;script&gt;") && !result.html.contains("<script>"));
        assert!(result.html.contains("&lt;/script&gt;"));
    }

    #[test]
    fn test_esc_ampersand_entity() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "A & B" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("A &amp; B"));
        assert!(!result.html.contains("A & B"));
    }

    #[test]
    fn test_esc_multiple_ampersands() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "A & B & C" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("A &amp; B &amp; C"));
    }

    #[test]
    fn test_esc_angle_brackets() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "<hello> & <world>" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("&lt;hello&gt; &amp; &lt;world&gt;"));
    }

    #[test]
    fn test_esc_quotes_in_text() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "He said \"hello\"" }] }
            ]
        });
        let result = render(&doc);
        // 引号本身不转义，但不应有问题
        assert!(result.html.contains("He said"));
    }

    #[test]
    fn test_esc_combined_entities() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "5 < 10 & 10 > 5" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("5 &lt; 10 &amp; 10 &gt; 5"));
    }

    // ── 空值和边界情况测试 ────────────────────────────────────────────────

    #[test]
    fn test_empty_text_node() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<p></p>"));
    }

    #[test]
    fn test_empty_paragraph() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<p></p>"));
    }

    #[test]
    fn test_empty_marks_array() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "文本", "marks": [] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("文本"));
        assert!(!result.html.contains("<strong>") && !result.html.contains("<em>"));
    }

    #[test]
    fn test_missing_marks_attribute() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "无标记" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("无标记"));
    }

    #[test]
    fn test_code_block_empty() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "code_block", "attrs": { "language": "Rust" }, "content": [] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<pre language=\"Rust\"><code></code></pre>"));
    }

    #[test]
    fn test_hard_break_in_paragraph() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [
                    { "type": "text", "text": "行1" },
                    { "type": "hard_break" },
                    { "type": "text", "text": "行2" }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("行1<br/>行2"));
    }

    #[test]
    fn test_blockquote_empty() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "blockquote", "content": [] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<blockquote></blockquote>"));
    }

    #[test]
    fn test_mention_with_uid_and_name() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [
                    { "type": "mention", "attrs": { "uid": "user123", "name": "@张三" } }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<km-mention uid=\"user123\">@张三</km-mention>"));
    }

    #[test]
    fn test_mention_empty_name() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [
                    { "type": "mention", "attrs": { "uid": "user456", "name": "" } }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<km-mention uid=\"user456\"></km-mention>"));
    }

    #[test]
    fn test_link_with_content() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [
                    { "type": "link", "attrs": { "href": "https://example.com" }, "content": [{ "type": "text", "text": "链接" }] }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<a href=\"https://example.com\">链接</a>"));
    }

    #[test]
    fn test_link_empty_content() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [
                    { "type": "link", "attrs": { "href": "https://example.com" }, "content": [] }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<a href=\"https://example.com\"></a>"));
    }

    #[test]
    fn test_node_id_extraction() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "nodeId": "para123" }, "content": [{ "type": "text", "text": "内容" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.pm_node_ids.contains(&Some("para123".to_string())));
    }

    #[test]
    fn test_multiple_node_ids() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [{ "type": "text", "text": "内容1" }] },
                { "type": "paragraph", "attrs": { "nodeId": "p2" }, "content": [{ "type": "text", "text": "内容2" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.pm_node_ids.contains(&Some("p1".to_string())));
        assert!(result.pm_node_ids.contains(&Some("p2".to_string())));
    }

    #[test]
    fn test_unknown_mark_type_ignored() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "文本", "marks": [{ "type": "unknown_mark" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("文本"));
        assert!(!result.html.contains("<unknown"));
    }

    #[test]
    fn test_mixed_known_unknown_marks() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "文本", "marks": [{ "type": "strong" }, { "type": "unknown" }, { "type": "em" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<strong>") && result.html.contains("<em>"));
    }

    #[test]
    fn test_render_single_node_without_doc_wrapper() {
        let node = json!({ "type": "paragraph", "content": [{ "type": "text", "text": "单节点" }] });
        let result = render(&node);
        assert!(result.html.contains("<p>单节点</p>"));
    }

    #[test]
    fn test_color_mark_missing_attrs() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "文本", "marks": [{ "type": "color" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<span color=\"\""));
    }

    #[test]
    fn test_backgroundcolor_mark_missing_attrs() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "文本", "marks": [{ "type": "backgroundcolor" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<span bg=\"\""));
    }

    #[test]
    fn test_underline_mark() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "下划线", "marks": [{ "type": "underline" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<u>下划线</u>"));
    }

    #[test]
    fn test_unicode_text_preserved() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "你好世界🌍" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("你好世界🌍"));
    }

    #[test]
    fn test_unicode_in_marks() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "日本語", "marks": [{ "type": "strong" }] }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<strong>日本語</strong>"));
    }

    #[test]
    fn test_image_inline_in_paragraph() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [
                    { "type": "text", "text": "看图：" },
                    { "type": "image", "attrs": { "src": "https://example.com/image.jpg", "name": "example" } }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("看图：") && result.html.contains("<img src=\"https://example.com/image.jpg\""));
    }

    #[test]
    fn test_xtable_standalone() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "xtable", "attrs": { "xtableId": "table123" } }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<km-xtable xtable-id=\"table123\""));
    }

    #[test]
    fn test_minder_standalone() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "minder" }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<km-minder"));
    }

    #[test]
    fn test_plantuml_standalone() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "plantuml" }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<km-plantuml"));
    }

    #[test]
    fn test_catalog_standalone() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "catalog" }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<km-catalog"));
    }

    #[test]
    fn test_footnote_list_standalone() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "footnote_list" }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<km-footnote-list"));
    }

    #[test]
    fn test_link_mark_on_text() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [
                    { "type": "text", "text": "链接文本", "marks": [{ "type": "link", "attrs": { "href": "https://example.com" } }] }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("<a href=\"https://example.com\">链接文本</a>"));
    }

    #[test]
    fn test_color_with_hex_values() {
        let colors = vec!["#000000", "#ffffff", "#ff00ff", "#123abc"];
        for color in colors {
            let doc = json!({
                "type": "doc",
                "content": [
                    { "type": "paragraph", "content": [
                        { "type": "text", "text": "文本", "marks": [{ "type": "color", "attrs": { "color": color } }] }
                    ] }
                ]
            });
            let result = render(&doc);
            assert!(result.html.contains(&format!("<span color=\"{color}\"")));
        }
    }

    #[test]
    fn test_nested_marks_order() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [
                    { "type": "text", "text": "嵌套", "marks": [
                        { "type": "strong" },
                        { "type": "em" },
                        { "type": "color", "attrs": { "color": "#ff0000" } }
                    ] }
                ] }
            ]
        });
        let result = render(&doc);
        // 验证所有标记都存在，并且按照应用顺序嵌套
        assert!(result.html.contains("<strong>"));
        assert!(result.html.contains("<em>"));
        assert!(result.html.contains("<span color=\"#ff0000\""));
    }

    #[test]
    fn test_heading_levels_1_to_6() {
        for level in 1..=6 {
            let doc = json!({
                "type": "doc",
                "content": [
                    { "type": "heading", "attrs": { "level": level }, "content": [{ "type": "text", "text": &format!("标题{}", level) }] }
                ]
            });
            let result = render(&doc);
            assert!(result.html.contains(&format!("<h{}>标题{}</h{}>", level, level, level)));
        }
    }

    #[test]
    fn test_whitespace_preservation() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "  前   中   后  " }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("  前   中   后  "));
    }

    #[test]
    fn test_special_html_chars_in_link() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [
                    { "type": "link", "attrs": { "href": "https://example.com?a=1&b=2" }, "content": [{ "type": "text", "text": "链接" }] }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("href=\"https://example.com?a=1&b=2\""));
    }

    #[test]
    fn test_image_with_dimensions() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "image", "attrs": { "src": "https://example.com/img.jpg", "name": "img", "width": 200, "height": 150 } }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("width=\"200\"") && result.html.contains("height=\"150\""));
    }

    #[test]
    fn test_image_without_dimensions() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "image", "attrs": { "src": "https://example.com/img.jpg", "name": "img" } }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("src=\"https://example.com/img.jpg\""));
        assert!(!result.html.contains("width="));
    }

    #[test]
    fn test_drawio_with_dimensions() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "drawio", "attrs": { "src": "https://cdn/diagram.xml", "width": 800, "height": 600 } }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("width=\"800\"") && result.html.contains("height=\"600\""));
    }

    #[test]
    fn test_result_contains_pm_node_ids() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "nodeId": "n1" }, "content": [{ "type": "text", "text": "p1" }] },
                { "type": "paragraph", "content": [{ "type": "text", "text": "p2" }] }
            ]
        });
        let result = render(&doc);
        assert_eq!(result.pm_node_ids.len(), 2);
        assert_eq!(result.pm_node_ids[0], Some("n1".to_string()));
        assert_eq!(result.pm_node_ids[1], None);
    }

    #[test]
    fn test_esc_function_standalone() {
        assert_eq!(esc("<script>"), "&lt;script&gt;");
        assert_eq!(esc("A & B"), "A &amp; B");
        assert_eq!(esc("5 < 10"), "5 &lt; 10");
        assert_eq!(esc("a > b"), "a &gt; b");
        assert_eq!(esc("<>&"), "&lt;&gt;&amp;");
    }

    // ── 对齐（align）渲染 ── 已用真实学城文档验证 schema：
    //    paragraph / heading 的 attrs.align 取值 "center"/"left"/"start"/""
    //    image / drawio 自身无 align，居中靠外层 paragraph.align="center" 包裹

    #[test]
    fn test_render_paragraph_align_center() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "align": "center" }, "content": [{ "type": "text", "text": "居中段落" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("text-align"), "paragraph align=center: should render text-align style");
    }

    #[test]
    fn test_render_paragraph_align_right() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "align": "right" }, "content": [{ "type": "text", "text": "右对齐" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("text-align"), "paragraph align=right: should render text-align style");
    }

    #[test]
    fn test_render_paragraph_align_left_omitted() {
        // left / "" / 无 align 都是默认左对齐，不应输出 style
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "align": "left" }, "content": [{ "type": "text", "text": "左对齐" }] }
            ]
        });
        let result = render(&doc);
        assert!(!result.html.contains("text-align"), "align=left should not emit style");
    }

    #[test]
    fn test_render_paragraph_align_empty_omitted() {
        // 真实文档里默认段落 align=""，不应输出 style
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "align": "" }, "content": [{ "type": "text", "text": "默认段落" }] }
            ]
        });
        let result = render(&doc);
        assert!(!result.html.contains("text-align"), "align empty should not emit style");
    }

    #[test]
    fn test_render_heading_align_center() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "heading", "attrs": { "level": 2, "align": "center" }, "content": [{ "type": "text", "text": "居中标题" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("text-align"), "heading align=center: should render text-align style");
    }

    #[test]
    fn test_render_paragraph_no_align_no_style() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "content": [{ "type": "text", "text": "普通段落" }] }
            ]
        });
        let result = render(&doc);
        assert!(!result.html.contains("text-align"), "no align should not add style");
    }

    #[test]
    fn test_render_image_wrapped_in_centered_paragraph() {
        // 真实结构：image 是 inline，居中靠外层 paragraph.align=center
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "align": "center" }, "content": [
                    { "type": "image", "attrs": { "src": "a.png", "name": "pic", "width": 200, "height": 100 } }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("text-align"), "image wrapped in align=center paragraph: should render text-align");
        assert!(result.html.contains("<img"), "inner image must still render");
    }

    #[test]
    fn test_render_paragraph_align_center_with_marks() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "align": "center" }, "content": [
                    { "type": "text", "text": "居中", "marks": [{ "type": "strong" }] },
                    { "type": "text", "text": "文字" }
                ] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("text-align"), "paragraph align+marks: should render text-align style");
        assert!(result.html.contains("<strong>居中</strong>"), "marks must be preserved alongside text-align");
    }

    #[test]
    fn test_render_paragraph_align_unknown_value_no_style() {
        // 脏/未知 align 值不得拼进 style，避免注入破坏 HTML 结构
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "align": "center\"><script>" }, "content": [{ "type": "text", "text": "x" }] }
            ]
        });
        let result = render(&doc);
        assert!(!result.html.contains("text-align"), "unknown align must not emit style");
        assert!(!result.html.contains("<script>"), "dirty align must not inject markup");
    }

    #[test]
    fn test_render_paragraph_align_justify() {
        let doc = json!({
            "type": "doc",
            "content": [
                { "type": "paragraph", "attrs": { "align": "justify" }, "content": [{ "type": "text", "text": "两端对齐" }] }
            ]
        });
        let result = render(&doc);
        assert!(result.html.contains("style=\"text-align: justify\""), "justify should render");
    }

    #[test]
    fn test_render_note_title_align_center() {
        // 真实 schema：note_title 有 attrs.align，居中应输出到 <summary> 上
        let doc = json!({
            "type": "doc",
            "content": [{
                "type": "note", "attrs": {"type":"info"},
                "content": [
                    { "type": "note_title", "attrs": { "align": "center" }, "content": [{ "type": "text", "text": "提示" }] },
                    { "type": "note_content", "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "x" }] }] }
                ]
            }]
        });
        let result = render(&doc);
        assert!(result.html.contains("<summary style=\"text-align: center\">提示</summary>"),
            "note_title align should render on summary, got: {}", result.html);
    }

    #[test]
    fn test_render_collapse_title_align_right() {
        let doc = json!({
            "type": "doc",
            "content": [{
                "type": "collapse", "attrs": {},
                "content": [
                    { "type": "collapse_title", "attrs": { "align": "right" }, "content": [{ "type": "text", "text": "展开" }] },
                    { "type": "collapse_content", "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "y" }] }] }
                ]
            }]
        });
        let result = render(&doc);
        assert!(result.html.contains("<summary style=\"text-align: right\">展开</summary>"),
            "collapse_title align should render on summary, got: {}", result.html);
    }
}
