use std::collections::HashMap;
use serde_json::{json, Value};
use uuid::Uuid;

fn nid() -> String {
    Uuid::new_v4().to_string().replace('-', "")
}

pub fn parse_attrs(attr_str: &str) -> HashMap<String, String> {
    let mut attrs = HashMap::new();
    let mut pos = 0;
    let s = attr_str.trim();
    while pos < s.len() {
        while pos < s.len() && s.as_bytes()[pos].is_ascii_whitespace() { pos += 1; }
        if pos >= s.len() { break; }
        let key_start = pos;
        while pos < s.len() && !s.as_bytes()[pos].is_ascii_whitespace() && s.as_bytes()[pos] != b'=' { pos += 1; }
        let key = &s[key_start..pos];
        while pos < s.len() && s.as_bytes()[pos].is_ascii_whitespace() { pos += 1; }
        if pos < s.len() && s.as_bytes()[pos] == b'=' {
            pos += 1;
            while pos < s.len() && s.as_bytes()[pos].is_ascii_whitespace() { pos += 1; }
            if pos >= s.len() { break; }
            let val = if s.as_bytes()[pos] == b'"' {
                pos += 1;
                let start = pos;
                while pos < s.len() && s.as_bytes()[pos] != b'"' { pos += 1; }
                let v = &s[start..pos];
                if pos < s.len() { pos += 1; }
                v
            } else if s.as_bytes()[pos] == b'\'' {
                pos += 1;
                let start = pos;
                while pos < s.len() && s.as_bytes()[pos] != b'\'' { pos += 1; }
                let v = &s[start..pos];
                if pos < s.len() { pos += 1; }
                v
            } else {
                let start = pos;
                while pos < s.len() && !s.as_bytes()[pos].is_ascii_whitespace() { pos += 1; }
                &s[start..pos]
            };
            attrs.insert(key.to_string(), val.to_string());
        } else {
            attrs.insert(key.to_string(), "true".to_string());
        }
    }
    attrs
}

pub fn unesc(s: &str) -> String {
    s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
     .replace("&quot;", "\"").replace("&#39;", "'").replace("&nbsp;", " ")
}

pub fn inline_block_pm_node(tag: &str, attrs: &HashMap<String, String>) -> Option<Value> {
    match tag {
        "img" => Some(json!({"type":"image","attrs":{"src":attrs.get("src").cloned().unwrap_or_default(),"name":attrs.get("alt").or_else(||attrs.get("name")).cloned().unwrap_or_default(),"width":attrs.get("width").and_then(|v|v.parse::<f64>().ok()),"height":attrs.get("height").and_then(|v|v.parse::<f64>().ok())}})),
        "km-drawio" => Some(json!({"type":"drawio","attrs":{"src":attrs.get("src").cloned().unwrap_or_default(),"width":attrs.get("width").and_then(|v|v.parse::<f64>().ok()),"height":attrs.get("height").and_then(|v|v.parse::<f64>().ok())}})),
        "km-video" => Some(json!({"type":"video","attrs":{"url":attrs.get("src").or_else(||attrs.get("url")).cloned().unwrap_or_default(),"name":attrs.get("name").cloned().unwrap_or_default(),"nodeId":nid()}})),
        "km-audio" => Some(json!({"type":"audio","attrs":{"url":attrs.get("src").or_else(||attrs.get("url")).cloned().unwrap_or_default(),"name":attrs.get("name").cloned().unwrap_or_default(),"nodeId":nid()}})),
        "km-xtable" => Some(json!({"type":"xtable","attrs":{"xtableId":attrs.get("xtable-id").or_else(||attrs.get("xtableId")).cloned().unwrap_or_default()}})),
        "km-minder" => Some(json!({"type":"minder","attrs":{}})),
        "km-attachment" => Some(json!({"type":"attachment","attrs":{"name":attrs.get("name").cloned().unwrap_or_default(),"src":attrs.get("src").cloned().unwrap_or_default(),"size":attrs.get("size").and_then(|v|v.parse::<f64>().ok())}})),
        "km-plantuml" => Some(json!({"type":"plantuml","attrs":{}})),
        "km-open-link" => {
            let href = attrs.get("href").cloned().unwrap_or_default();
            let otype = attrs.get("data-otype").cloned().unwrap_or_default();
            Some(json!({"type":"open_link","attrs":{"href":href,"nodeId":nid(),"type":otype}}))
        }
        "km-open-card" => {
            let href = attrs.get("href").cloned().unwrap_or_default();
            let otype = attrs.get("data-otype").cloned().unwrap_or_default();
            Some(json!({"type":"open_card","attrs":{"href":href,"nodeId":nid(),"type":otype}}))
        }
        _ => None,
    }
}

pub fn parse_inline(html: &str) -> Vec<Value> {
    let mut nodes: Vec<Value> = Vec::new();
    let mut pos = 0;
    let s = html;

    while pos < s.len() {
        if s.as_bytes()[pos] != b'<' {
            let end = s[pos..].find('<').map_or(s.len(), |i| pos + i);
            let text = unesc(&s[pos..end]);
            if !text.is_empty() { nodes.push(json!({"type":"text","text":text})); }
            pos = end;
            continue;
        }

        // <br/>
        if s[pos..].starts_with("<br") {
            let br_end = s[pos..].find('>').map_or(s.len(), |i| pos + i + 1);
            if br_end > pos && br_end <= s.len() {
                let tag = &s[pos..br_end];
                if tag.starts_with("<br") && (tag.ends_with("/>") || tag == "<br>") {
                    nodes.push(json!({"type":"hard_break"}));
                    pos = br_end;
                    continue;
                }
            }
        }

        let tag_end = s[pos..].find('>').map_or(s.len(), |i| pos + i);
        if tag_end >= s.len() { pos += 1; continue; }
        let full_tag = &s[pos..=tag_end];

        // 注释
        if full_tag.starts_with("<!--") {
            if let Some(close) = s[tag_end..].find("-->") {
                pos = tag_end + close + 3;
            } else {
                pos = s.len();
            }
            continue;
        }

        // 自闭合：<km-drawio .../>, <img .../> 等
        if full_tag.ends_with("/>") {
            let inner_str = full_tag[1..full_tag.len()-2].trim().to_string();
            let inner_ref = inner_str.as_str();
            let space = inner_ref.find(|c: char| c.is_ascii_whitespace());
            let (tag_name, attr_str) = if let Some(si) = space {
                (&inner_ref[..si], inner_ref[si..].trim())
            } else {
                (inner_ref, "")
            };
            let sa = parse_attrs(attr_str);
            let tn = tag_name.to_lowercase();
            if let Some(node) = inline_block_pm_node(&tn, &sa) {
                nodes.push(node);
            }
            pos = tag_end + 1;
            continue;
        }

        // 普通开标签：<strong>, <em>, <a>, <span> 等
        let inner = &full_tag[1..full_tag.len()-1];
        let space = inner.find(|c: char| c.is_ascii_whitespace());
        let (tag_name, attr_str) = if let Some(si) = space {
            (&inner[..si], inner[si..].trim())
        } else {
            (inner, "")
        };
        let attrs = parse_attrs(attr_str);
        let tag_lower = tag_name.to_lowercase();
        let close_tag = format!("</{}>", tag_lower);

        // 找对应闭合标签（深度感知）
        let mut depth = 1usize;
        let mut search = tag_end + 1;
        let mut inner_end = None;

        while search < s.len() && depth > 0 {
            let open_pos = s[search..].find(&format!("<{}", tag_lower));
            let close_pos = s[search..].find(&close_tag);
            if close_pos.is_none() { break; }
            let close_pos = close_pos.unwrap();
            if let Some(op) = open_pos {
                if op < close_pos {
                    let after_tag = search + op + 1 + tag_lower.len();
                    if after_tag < s.len() && matches!(s.as_bytes()[after_tag], b'>' | b' ' | b'/') {
                        depth += 1;
                        search += op + 1;
                        continue;
                    }
                }
            }
            depth -= 1;
            if depth == 0 { inner_end = Some(search + close_pos); }
            search += close_pos + 1;
        }

        if inner_end.is_none() { pos = tag_end + 1; continue; }
        let inner_end = inner_end.unwrap();
        let inner_html = &s[tag_end + 1..inner_end];
        let inner_nodes = parse_inline(inner_html);

        if tag_lower == "a" {
            // 服务端 PM schema 要求 link 是内联节点（type:link + content），
            // 不是文本上的 mark。title 取内部文本，保持与 md_to_pm 输出格式一致。
            let href = attrs.get("href").cloned().unwrap_or_default();
            let title: String = inner_nodes.iter()
                .filter_map(|n| n.get("text").and_then(|v| v.as_str()))
                .collect();
            nodes.push(json!({
                "type": "link",
                "attrs": { "href": href, "title": title },
                "content": inner_nodes
            }));
        } else if tag_lower == "km-mention" {
            // render.rs 把 mention 输出为 <km-mention uid="...">name</km-mention>
            // PM type 是 "mention"（非 "km-mention"），uid 和 name 都要保留
            let uid = attrs.get("uid").cloned().unwrap_or_default();
            let name: String = inner_nodes.iter()
                .filter_map(|n| n.get("text").and_then(|v| v.as_str()))
                .collect();
            nodes.push(json!({"type":"mention","attrs":{"uid":uid,"name":name}}));
        } else if let Some(mark) = tag_to_mark(&tag_lower, &attrs) {
            nodes.extend(add_mark(&inner_nodes, &mark));
        } else {
            nodes.extend(inner_nodes);
        }

        pos = inner_end + close_tag.len();
    }

    merge_adjacent_text(nodes).into_iter().filter(|n| {
        n.get("type").and_then(|v|v.as_str()) != Some("text") ||
        n.get("text").and_then(|v|v.as_str()).map_or(false, |t|!t.is_empty())
    }).collect()
}

fn tag_to_mark(tag: &str, attrs: &HashMap<String,String>) -> Option<Value> {
    match tag {
        "strong"|"b" => Some(json!({"type":"strong"})),
        "em"|"i" => Some(json!({"type":"em"})),
        "u" => Some(json!({"type":"underline"})),
        "del"|"s" => Some(json!({"type":"strikethrough"})),
        "code" => Some(json!({"type":"code"})),
        "sub" => Some(json!({"type":"sub"})),
        "sup" => Some(json!({"type":"sup"})),
        "a" => Some(json!({"type":"link","attrs":{"href":attrs.get("href").cloned().unwrap_or_default()}})),
        "span" => {
            if attrs.contains_key("color") {
                Some(json!({"type":"color","attrs":{"color":attrs["color"]}}))
            } else if attrs.contains_key("bg") {
                Some(json!({"type":"backgroundcolor","attrs":{"color":attrs["bg"]}}))
            } else { None }
        }
        _ => None,
    }
}

fn add_mark(nodes: &[Value], mark: &Value) -> Vec<Value> {
    nodes.iter().map(|n| {
        if n.get("type").and_then(|v|v.as_str()) != Some("text") { return n.clone(); }
        let mut node = n.clone();
        let mark_type = mark["type"].as_str().unwrap_or("");
        let marks = node.get("marks").and_then(|v|v.as_array()).map(|a|a.to_vec()).unwrap_or_default();
        if marks.iter().any(|m| m["type"] == mark_type) { return node; }
        let mut new_marks = vec![mark.clone()];
        new_marks.extend(marks);
        if let Some(obj) = node.as_object_mut() {
            obj.insert("marks".to_string(), json!(new_marks));
        }
        node
    }).collect()
}

fn merge_adjacent_text(nodes: Vec<Value>) -> Vec<Value> {
    let mut result: Vec<Value> = Vec::new();
    for n in nodes {
        if n.get("type").and_then(|v|v.as_str()) != Some("text") {
            result.push(n);
            continue;
        }
        if let Some(prev) = result.last_mut() {
            if prev.get("type") == n.get("type") && prev.get("marks") == n.get("marks") {
                let merged = format!("{}{}",
                    prev["text"].as_str().unwrap_or(""),
                    n["text"].as_str().unwrap_or(""));
                if let Some(obj) = prev.as_object_mut() {
                    obj.insert("text".to_string(), json!(merged));
                }
                continue;
            }
        }
        result.push(n);
    }
    result.into_iter().map(|n| {
        if n.get("type").and_then(|v|v.as_str()) != Some("text") { return n; }
        let marks = n.get("marks").and_then(|v|v.as_array());
        if marks.map_or(true, |a|a.is_empty()) {
            let mut obj = n.as_object().cloned().unwrap_or_default();
            obj.remove("marks");
            return json!(obj);
        }
        n
    }).collect()
}
// ── 测试 ──────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── parse_attrs ──────────────────────────────────────────────────────

    #[test]
    fn test_parse_attrs_double_quotes() {
        let attrs = parse_attrs(r#"id="n4" class="foo""#);
        assert_eq!(attrs.get("id").unwrap(), "n4");
        assert_eq!(attrs.get("class").unwrap(), "foo");
    }

    #[test]
    fn test_parse_attrs_color_and_bg() {
        let attrs = parse_attrs("color=\"#ff0000\" bg=\"#00ff00\"");
        assert_eq!(attrs.get("color").unwrap(), "#ff0000");
        assert_eq!(attrs.get("bg").unwrap(), "#00ff00");
    }

    #[test]
    fn test_parse_attrs_boolean() {
        let attrs = parse_attrs("checked disabled");
        assert_eq!(attrs.get("checked").unwrap(), "true");
        assert_eq!(attrs.get("disabled").unwrap(), "true");
    }

    #[test]
    fn test_parse_attrs_empty() {
        let attrs = parse_attrs("");
        assert!(attrs.is_empty());
    }

    #[test]
    fn test_parse_attrs_single_quotes() {
        let attrs = parse_attrs("href='https://example.com'");
        assert_eq!(attrs.get("href").unwrap(), "https://example.com");
    }

    // ── unesc ────────────────────────────────────────────────────────────

    #[test]
    fn test_unesc_amp_lt_gt() {
        assert_eq!(unesc("a &amp; b &lt;c&gt;"), "a & b <c>");
    }

    #[test]
    fn test_unesc_quot() {
        assert_eq!(unesc("&quot;hello&#39;"), "\"hello'");
    }

    #[test]
    fn test_unesc_nbsp() {
        assert_eq!(unesc("a&nbsp;b"), "a b");
    }

    #[test]
    fn test_unesc_empty() {
        assert_eq!(unesc(""), "");
    }

    // ── inline_block_pm_node ─────────────────────────────────────────────

    #[test]
    fn test_inline_block_img_to_image() {
        let mut attrs = HashMap::new();
        attrs.insert("src".into(), "a.png".into());
        attrs.insert("alt".into(), "pic".into());
        attrs.insert("width".into(), "100".into());
        attrs.insert("height".into(), "200".into());
        let node = inline_block_pm_node("img", &attrs).unwrap();
        assert_eq!(node["type"], "image");
        assert_eq!(node["attrs"]["src"], "a.png");
        assert_eq!(node["attrs"]["name"], "pic");
        assert_eq!(node["attrs"]["width"], 100.0);
        assert_eq!(node["attrs"]["height"], 200.0);
    }

    #[test]
    fn test_inline_block_drawio() {
        let mut attrs = HashMap::new();
        attrs.insert("src".into(), "https://cdn/f.svg".into());
        let node = inline_block_pm_node("km-drawio", &attrs).unwrap();
        assert_eq!(node["type"], "drawio");
        assert_eq!(node["attrs"]["src"], "https://cdn/f.svg");
    }

    #[test]
    fn test_inline_block_video() {
        let mut attrs = HashMap::new();
        attrs.insert("src".into(), "v.mp4".into());
        attrs.insert("name".into(), "demo.mp4".into());
        attrs.insert("size".into(), "5MB".into());
        let node = inline_block_pm_node("km-video", &attrs).unwrap();
        assert_eq!(node["type"], "video");
        // video PM JSON 必须用 url 字段（schema 要求）
        assert_eq!(node["attrs"]["url"], "v.mp4");
        assert_eq!(node["attrs"]["name"], "demo.mp4");
    }

    #[test]
    fn test_inline_block_video_url_fallback() {
        let mut attrs = HashMap::new();
        attrs.insert("url".into(), "v.mp4".into());
        let node = inline_block_pm_node("km-video", &attrs).unwrap();
        // url 属性透传到 PM JSON url 字段
        assert_eq!(node["attrs"]["url"], "v.mp4");
    }

    #[test]
    fn test_inline_block_attachment() {
        let mut attrs = HashMap::new();
        attrs.insert("name".into(), "file.pdf".into());
        attrs.insert("src".into(), "f.pdf".into());
        attrs.insert("size".into(), "1024".into());
        let node = inline_block_pm_node("km-attachment", &attrs).unwrap();
        assert_eq!(node["type"], "attachment");
        assert_eq!(node["attrs"]["name"], "file.pdf");
        assert_eq!(node["attrs"]["src"], "f.pdf");
        assert_eq!(node["attrs"]["size"], 1024.0);
    }

    #[test]
    fn test_inline_block_xtable() {
        let mut attrs = HashMap::new();
        attrs.insert("xtable-id".into(), "tbl001".into());
        let node = inline_block_pm_node("km-xtable", &attrs).unwrap();
        assert_eq!(node["type"], "xtable");
        assert_eq!(node["attrs"]["xtableId"], "tbl001");
    }

    #[test]
    fn test_inline_block_minder() {
        let attrs = HashMap::new();
        let node = inline_block_pm_node("km-minder", &attrs).unwrap();
        assert_eq!(node["type"], "minder");
    }

    #[test]
    fn test_inline_block_plantuml() {
        let attrs = HashMap::new();
        let node = inline_block_pm_node("km-plantuml", &attrs).unwrap();
        assert_eq!(node["type"], "plantuml");
    }

    #[test]
    fn test_inline_block_unknown_tag_returns_none() {
        let attrs = HashMap::new();
        assert!(inline_block_pm_node("unknown", &attrs).is_none());
    }

    // ── parse_inline: marks ────────────────────────────────────────────────

    #[test]
    fn test_parse_inline_strong() {
        let result = parse_inline("<strong>粗体</strong>");
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["text"], "粗体");
        assert!(result[0]["marks"][0]["type"].as_str().unwrap().contains("strong"));
    }

    #[test]
    fn test_parse_inline_em() {
        let result = parse_inline("<em>斜体</em>");
        assert_eq!(result[0]["marks"][0]["type"], "em");
    }

    #[test]
    fn test_parse_inline_mixed_text_and_mark() {
        let result = parse_inline("前缀<strong>粗体</strong>后缀");
        assert_eq!(result.len(), 3);
        assert_eq!(result[0]["text"], "前缀");
        assert_eq!(result[1]["text"], "粗体");
        assert_eq!(result[2]["text"], "后缀");
    }

    #[test]
    fn test_parse_inline_color_span() {
        let result = parse_inline(r##"<span color="#ff0000">红字</span>"##);
        assert_eq!(result[0]["marks"][0]["type"], "color");
        assert_eq!(result[0]["marks"][0]["attrs"]["color"], "#ff0000");
    }

    #[test]
    fn test_parse_inline_link() {
        // <a> 现在生成内联节点（type:link），而非文本上的 mark
        let result = parse_inline(r#"<a href="https://example.com">链接</a>"#);
        assert_eq!(result[0]["type"], "link");
        assert_eq!(result[0]["attrs"]["href"], "https://example.com");
        assert_eq!(result[0]["attrs"]["title"], "链接");
        assert_eq!(result[0]["content"][0]["text"], "链接");
    }

    #[test]
    fn test_parse_inline_nested_marks() {
        let result = parse_inline("<strong><em>粗斜体</em></strong>");
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["text"], "粗斜体");
        let types: Vec<&str> = result[0]["marks"].as_array().unwrap().iter()
            .map(|m| m["type"].as_str().unwrap()).collect();
        assert!(types.contains(&"strong"));
        assert!(types.contains(&"em"));
    }

    #[test]
    fn test_parse_inline_img_self_closing() {
        let result = parse_inline(r#"主题<img src="a.png" alt="pic"/>结尾"#);
        assert_eq!(result.len(), 3);
        assert_eq!(result[0]["text"], "主题");
        assert_eq!(result[1]["type"], "image");
        assert_eq!(result[1]["attrs"]["src"], "a.png");
        assert_eq!(result[2]["text"], "结尾");
    }

    #[test]
    fn test_parse_inline_drawio_self_closing() {
        let result = parse_inline(r#"<km-drawio src="https://cdn/f.svg"/>"#);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["type"], "drawio");
        assert_eq!(result[0]["attrs"]["src"], "https://cdn/f.svg");
    }

    #[test]
    fn test_parse_inline_adjacent_text_merge() {
        let result = parse_inline("<strong>A</strong><strong>B</strong>");
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["text"], "AB");
    }

    // ── parse_inline: remaining marks ──────────────────────────────────

    #[test]
    fn test_parse_inline_hard_break() {
        let result = parse_inline("前<br/>后");
        assert!(result.iter().any(|n| n["type"] == "hard_break"));
    }

    #[test]
    fn test_parse_inline_u() {
        let result = parse_inline("<u>下划线</u>");
        assert_eq!(result[0]["marks"][0]["type"], "underline");
    }

    #[test]
    fn test_parse_inline_del() {
        let result = parse_inline("<del>删除线</del>");
        assert_eq!(result[0]["marks"][0]["type"], "strikethrough");
    }

    #[test]
    fn test_parse_inline_code_mark() {
        let result = parse_inline("<code>inline code</code>");
        assert_eq!(result[0]["marks"][0]["type"], "code");
    }

    #[test]
    fn test_parse_inline_sub() {
        let result = parse_inline("<sub>下标</sub>");
        assert_eq!(result[0]["marks"][0]["type"], "sub");
    }

    #[test]
    fn test_parse_inline_sup() {
        let result = parse_inline("<sup>上标</sup>");
        assert_eq!(result[0]["marks"][0]["type"], "sup");
    }

    #[test]
    fn test_parse_inline_b_as_strong() {
        let result = parse_inline("<b>粗体</b>");
        assert_eq!(result[0]["marks"][0]["type"], "strong");
    }

    #[test]
    fn test_parse_inline_no_duplicate_marks() {
        let result = parse_inline("<strong><strong>粗体</strong></strong>");
        let strong_marks: Vec<_> = result[0]["marks"].as_array().unwrap().iter()
            .filter(|m| m["type"] == "strong").collect();
        assert_eq!(strong_marks.len(), 1, "should not duplicate same mark type");
    }

    #[test]
    fn test_parse_inline_span_no_color_passthrough() {
        let result = parse_inline("<span>普通文字</span>");
        assert_eq!(result[0]["text"], "普通文字");
        assert!(result[0].get("marks").map_or(true, |m| m.as_array().map_or(true, |a| a.is_empty())));
    }

    #[test]
    fn test_parse_inline_whitespace_only() {
        let result = parse_inline("  ");
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["text"], "  ");
    }

    #[test]
    fn test_parse_inline_plain_text_with_entity() {
        let result = parse_inline("a &amp; b");
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["text"], "a & b");
    }

    #[test]
    fn test_parse_inline_i_as_em() {
        let result = parse_inline("<i>斜体</i>");
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["text"], "斜体");
        assert_eq!(result[0]["marks"][0]["type"], "em");
    }

    #[test]
    fn test_parse_inline_s_as_strikethrough() {
        let result = parse_inline("<s>删除线</s>");
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["marks"][0]["type"], "strikethrough");
    }

    #[test]
    fn test_parse_inline_nested_strong_color() {
        let result = parse_inline(r##"<strong><span color="#f00">粗体红字</span></strong>"##);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["text"], "粗体红字");
        let has_strong = result[0]["marks"].as_array().unwrap().iter().any(|m| m["type"] == "strong");
        let has_color = result[0]["marks"].as_array().unwrap().iter().any(|m| m["type"] == "color");
        assert!(has_strong && has_color);
    }

    #[test]
    fn test_parse_inline_mixed_inline_block_and_text() {
        let result = parse_inline(r#"前置文字<km-drawio src="https://cdn/flow.svg"/>后置文字"#);
        assert_eq!(result.len(), 3);
        assert_eq!(result[0]["text"], "前置文字");
        assert_eq!(result[1]["type"], "drawio");
        assert_eq!(result[2]["text"], "后置文字");
    }

    #[test]
    fn test_parse_inline_img_width_height_numeric() {
        let result = parse_inline(r#"<img src="a.png" width="600" height="400"/>"#);
        assert_eq!(result[0]["attrs"]["width"].as_f64().unwrap(), 600.0);
        assert_eq!(result[0]["attrs"]["height"].as_f64().unwrap(), 400.0);
    }

    #[test]
    fn test_parse_inline_drawio_numeric_dimensions() {
        let result = parse_inline(r#"<km-drawio src="https://cdn/flow.svg" width="100" height="80"/>"#);
        assert_eq!(result[0]["attrs"]["width"].as_f64().unwrap(), 100.0);
        assert_eq!(result[0]["attrs"]["height"].as_f64().unwrap(), 80.0);
    }

    #[test]
    fn test_parse_inline_unknown_tag_passthrough() {
        let result = parse_inline("<div>内容</div>");
        assert_eq!(result.len(), 1);
        assert_eq!(result[0]["text"], "内容");
    }

    #[test]
    fn test_parse_attrs_special_chars_in_value() {
        let attrs = parse_attrs("href=\"https://example.com?a=1&b=2\" title=\"A & B\"");
        assert_eq!(attrs.get("href").map(|s| s.as_str()), Some("https://example.com?a=1&b=2"));
        assert_eq!(attrs.get("title").map(|s| s.as_str()), Some("A & B"));
    }

    #[test]
    fn test_parse_attrs_single_quotes_multi() {
        let attrs = parse_attrs("data-id='123' class='primary'");
        assert_eq!(attrs.get("data-id").map(|s| s.as_str()), Some("123"));
        assert_eq!(attrs.get("class").map(|s| s.as_str()), Some("primary"));
    }

    #[test]
    fn test_parse_attrs_unquoted_values() {
        let attrs = parse_attrs("width=100 height=200");
        assert_eq!(attrs.get("width").map(|s| s.as_str()), Some("100"));
        assert_eq!(attrs.get("height").map(|s| s.as_str()), Some("200"));
    }

    #[test]
    fn test_parse_attrs_hyphenated_names() {
        let attrs = parse_attrs("data-test-id=\"foo\" aria-label=\"bar\"");
        assert_eq!(attrs.get("data-test-id").map(|s| s.as_str()), Some("foo"));
        assert_eq!(attrs.get("aria-label").map(|s| s.as_str()), Some("bar"));
    }

    #[test]
    fn test_parse_attrs_underscore_names() {
        let attrs = parse_attrs("_private=\"x\" __test__=\"y\"");
        assert_eq!(attrs.get("_private").map(|s| s.as_str()), Some("x"));
        assert_eq!(attrs.get("__test__").map(|s| s.as_str()), Some("y"));
    }

    #[test]
    fn test_parse_attrs_duplicate_names() {
        let attrs = parse_attrs("id=\"first\" id=\"second\"");
        assert_eq!(attrs.get("id").map(|s| s.as_str()), Some("second"));
    }

    #[test]
    fn test_parse_attrs_empty_value() {
        let attrs = parse_attrs("data-empty=\"\"");
        assert_eq!(attrs.get("data-empty").map(|s| s.as_str()), Some(""));
    }

    #[test]
    fn test_parse_attrs_whitespace_preserved() {
        let attrs = parse_attrs("title=\"  spaced  \"");
        assert_eq!(attrs.get("title").map(|s| s.as_str()), Some("  spaced  "));
    }

    #[test]
    fn test_parse_attrs_multiple_boolean() {
        let attrs = parse_attrs("disabled readonly checked");
        assert_eq!(attrs.get("disabled").map(|s| s.as_str()), Some("true"));
        assert_eq!(attrs.get("readonly").map(|s| s.as_str()), Some("true"));
        assert_eq!(attrs.get("checked").map(|s| s.as_str()), Some("true"));
    }

    #[test]
    fn test_parse_attrs_boolean_and_values_mixed() {
        let attrs = parse_attrs("checked disabled href=\"https://x.com\"");
        assert_eq!(attrs.get("checked").map(|s| s.as_str()), Some("true"));
        assert_eq!(attrs.get("disabled").map(|s| s.as_str()), Some("true"));
        assert_eq!(attrs.get("href").map(|s| s.as_str()), Some("https://x.com"));
    }

    #[test]
    fn test_unesc_multiple_different_entities() {
        assert_eq!(unesc("&lt;div&gt; &amp; &quot;test&quot;"), "<div> & \"test\"");
    }

    #[test]
    fn test_unesc_continuous_same_entities() {
        assert_eq!(unesc("&amp;&amp;&amp;"), "&&&");
    }

    #[test]
    fn test_unesc_entity_and_text_mixed() {
        assert_eq!(unesc("hello&nbsp;&nbsp;world"), "hello  world");
    }

    #[test]
    fn test_unesc_apos_entity() {
        assert_eq!(unesc("It&#39;s fine"), "It's fine");
    }

    #[test]
    fn test_unesc_all_supported_entities() {
        assert_eq!(unesc("&amp;&lt;&gt;&quot;&#39;&nbsp;"), "&<>\"' ");
    }

    #[test]
    fn test_unesc_unknown_entities() {
        assert_eq!(unesc("&unknown; &notreal;"), "&unknown; &notreal;");
    }

    #[test]
    fn test_unesc_incomplete_entities() {
        assert_eq!(unesc("&amp"), "&amp");
        assert_eq!(unesc("&lt"), "&lt");
    }

    #[test]
    fn test_unesc_entity_followed_by_text() {
        assert_eq!(unesc("&amp;text"), "&text");
    }

    #[test]
    fn test_unesc_large_entity_string() {
        let input = "&amp;".repeat(1000);
        let output = unesc(&input);
        assert_eq!(output, "&".repeat(1000));
    }

    #[test]
    fn test_unesc_nested_entity_string() {
        assert_eq!(unesc("&quot;&lt;script&gt;&quot;"), "\"<script>\"");
    }

    #[test]
    fn test_parse_inline_three_level_nested_marks() {
        let result = parse_inline("<strong><em><u>nested</u></em></strong>");
        assert_eq!(result.len(), 1);
        let types: Vec<_> = result[0]["marks"].as_array().unwrap().iter().map(|m| m["type"].as_str().unwrap()).collect();
        assert!(types.contains(&"strong"));
        assert!(types.contains(&"em"));
        assert!(types.contains(&"underline"));
    }

    #[test]
    fn test_parse_inline_color_strong_combo() {
        let result = parse_inline("<span color=\"#ff0000\"><strong>红色粗体</strong></span>");
        let types: Vec<_> = result[0]["marks"].as_array().unwrap().iter().map(|m| m["type"].as_str().unwrap()).collect();
        assert!(types.contains(&"color"));
        assert!(types.contains(&"strong"));
    }

    #[test]
    fn test_parse_inline_bg_em_combo() {
        let result = parse_inline("<span bg=\"#ffff00\"><em>黄底斜体</em></span>");
        let types: Vec<_> = result[0]["marks"].as_array().unwrap().iter().map(|m| m["type"].as_str().unwrap()).collect();
        assert!(types.contains(&"backgroundcolor"));
        assert!(types.contains(&"em"));
    }

    #[test]
    fn test_parse_inline_link_strikethrough_combo() {
        // link 是外层节点，strikethrough 是其 content 内文本的 mark
        let result = parse_inline("<a href=\"https://x.com\"><del>已删除链接</del></a>");
        assert_eq!(result[0]["type"], "link");
        assert_eq!(result[0]["attrs"]["href"], "https://x.com");
        let inner_marks: Vec<_> = result[0]["content"][0]["marks"].as_array().unwrap()
            .iter().map(|m| m["type"].as_str().unwrap()).collect();
        assert!(inner_marks.contains(&"strikethrough"));
    }

    #[test]
    fn test_parse_inline_code_color_combo() {
        let result = parse_inline("<code><span color=\"#0000ff\">蓝色代码</span></code>");
        let types: Vec<_> = result[0]["marks"].as_array().unwrap().iter().map(|m| m["type"].as_str().unwrap()).collect();
        assert!(types.contains(&"code"));
        assert!(types.contains(&"color"));
    }

    #[test]
    fn test_parse_inline_sup_color_combo() {
        let result = parse_inline("<sup><span color=\"#ff00ff\">彩色上标</span></sup>");
        let types: Vec<_> = result[0]["marks"].as_array().unwrap().iter().map(|m| m["type"].as_str().unwrap()).collect();
        assert!(types.contains(&"sup"));
        assert!(types.contains(&"color"));
    }

    #[test]
    fn test_parse_inline_sub_bg_combo() {
        let result = parse_inline("<sub><span bg=\"#cccccc\">灰底下标</span></sub>");
        let types: Vec<_> = result[0]["marks"].as_array().unwrap().iter().map(|m| m["type"].as_str().unwrap()).collect();
        assert!(types.contains(&"sub"));
        assert!(types.contains(&"backgroundcolor"));
    }

    #[test]
    fn test_parse_inline_multiple_color_marks_not_repeated() {
        let result = parse_inline("<span color=\"#ff0000\"><span color=\"#00ff00\">green</span></span>");
        let color_marks: Vec<_> = result[0]["marks"].as_array().unwrap().iter()
            .filter(|m| m["type"] == "color").collect();
        assert_eq!(color_marks.len(), 1);
        assert_eq!(color_marks[0]["attrs"]["color"], "#00ff00");
    }

    #[test]
    fn test_parse_inline_b_i_s_alias_combo() {
        let result = parse_inline("<b><i><s>粗斜删</s></i></b>");
        let types: Vec<_> = result[0]["marks"].as_array().unwrap().iter().map(|m| m["type"].as_str().unwrap()).collect();
        assert!(types.contains(&"strong"));
        assert!(types.contains(&"em"));
        assert!(types.contains(&"strikethrough"));
    }

    // ── 对齐（textAlign）解析 ────────────────────────────────────────────

    #[test]
    fn test_parse_attrs_style_text_align_center() {
        let attrs = parse_attrs("style=\"text-align: center\"");
        assert_eq!(attrs.get("style").map(|s| s.as_str()), Some("text-align: center"),
            "style attribute should be captured as-is");
    }

    #[test]
    fn test_parse_attrs_style_text_align_right() {
        let attrs = parse_attrs("style=\"text-align: right\"");
        assert_eq!(attrs.get("style").map(|s| s.as_str()), Some("text-align: right"));
    }

    #[test]
    fn test_parse_attrs_align_center() {
        let attrs = parse_attrs("align=\"center\"");
        assert_eq!(attrs.get("align").map(|s| s.as_str()), Some("center"));
    }

    #[test]
    fn test_parse_attrs_style_multiple_properties() {
        let attrs = parse_attrs("style=\"text-align: center; color: red\"");
        assert_eq!(attrs.get("style").map(|s| s.as_str()), Some("text-align: center; color: red"),
            "multiple style properties should be captured");
    }

    #[test]
    fn test_parse_attrs_style_and_other_attrs() {
        let attrs = parse_attrs("href=\"https://x.com\" style=\"text-align: center\"");
        assert_eq!(attrs.get("href").map(|s| s.as_str()), Some("https://x.com"));
        assert_eq!(attrs.get("style").map(|s| s.as_str()), Some("text-align: center"));
    }
}
