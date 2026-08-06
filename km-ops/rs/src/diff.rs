use std::collections::HashMap;
use serde_json::Value;
use crate::myers::HtmlNode;

// ── 数据结构 ──────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct DeleteOp {
    pub pm_node_id: Option<String>,
    pub old_idx: Option<usize>,
}

#[derive(Debug, Clone)]
pub struct DiffResult {
    pub changed: Vec<ChangeOp>,
    pub deleted: Vec<DeleteOp>,
    pub added: Vec<AddOp>,
}

#[derive(Debug, Clone)]
pub struct ChangeOp {
    pub pm_node_id: Option<String>,
    pub tag: String,
    pub inner_html: String,
    pub attrs: HashMap<String, String>,
    pub type_changed: bool,
    /// Position in the source PM JSON content array (for nodeId-less matching)
    pub old_idx: Option<usize>,
}

#[derive(Debug, Clone)]
pub struct AddOp {
    pub tag: String,
    pub inner_html: String,
    pub attrs: HashMap<String, String>,
}

// ── Tree Diff ─────────────────────────────────────────────────────────────────

pub fn diff(old_html: &str, new_html: &str, source_tree: &Value) -> DiffResult {
    let old_nodes = crate::myers::parse_nodes(old_html);
    let new_nodes = crate::myers::parse_nodes(new_html);

    let ops = crate::myers::lcs_diff(&old_nodes, &new_nodes, 0.3);
    ops_to_diff_result(&ops, &old_nodes, &new_nodes, source_tree)
}

/// 朴素的按位置对齐 diff（占位实现，当前未启用；实际走 myers::lcs_diff）。
/// 保留以备后续移植参考。
#[allow(dead_code)]
fn tree_diff(source_tree: &Value, new_nodes: &[HtmlNode]) -> DiffResult {
    let children = source_tree.get("content").and_then(|v| v.as_array()).map(|a| a.as_slice()).unwrap_or(&[]);
    let mut changed = Vec::new();
    let mut deleted = Vec::new();
    let mut added = Vec::new();

    let max_len = children.len().max(new_nodes.len());
    for i in 0..max_len {
        match (children.get(i), new_nodes.get(i)) {
            (Some(src), Some(new)) => {
                let src_tag = src.get("type").and_then(|v| v.as_str()).unwrap_or("");
                if src_tag != new.tag || src.get("hash").and_then(|v| v.as_str()) != Some(&new.hash) {
                    changed.push(ChangeOp {
                        pm_node_id: src.get("attrs").and_then(|a| a.get("nodeId")).and_then(|v| v.as_str()).map(String::from),
                        tag: new.tag.clone(),
                        inner_html: new.inner_html.clone(),
                        attrs: new.attrs.clone(),
                        type_changed: src_tag != new.tag,
                        old_idx: Some(i),
                    });
                }
            }
            (Some(src), None) => {
                deleted.push(DeleteOp {
                    pm_node_id: src.get("attrs").and_then(|a| a.get("nodeId")).and_then(|v| v.as_str()).map(String::from),
                    old_idx: None,
                });
            }
            (None, Some(new)) => {
                added.push(AddOp {
                    tag: new.tag.clone(),
                    inner_html: new.inner_html.clone(),
                    attrs: new.attrs.clone(),
                });
            }
            (None, None) => unreachable!(),
        }
    }

    DiffResult { changed, deleted, added }
}

/// 把相邻的 Delete(old_i)+Insert(new_j) 且 tag 相同的对合并成 Keep(old_i, new_j)。
/// 这样「同位置同类型的内容替换」会被识别为 changed（原地修改），而非 delete+insert。
/// 也处理 Delete 序列后跟 Insert 序列、按顺序配对同 tag 的情况。
fn merge_replace_pairs(ops: &[crate::myers::DiffOp], old_nodes: &[HtmlNode], new_nodes: &[HtmlNode]) -> Vec<crate::myers::DiffOp> {
    use crate::myers::DiffOpKind;
    let mut result: Vec<crate::myers::DiffOp> = Vec::with_capacity(ops.len());
    let mut i = 0;
    while i < ops.len() {
        // 收集连续的 Delete
        let del_start = i;
        while i < ops.len() && ops[i].op == DiffOpKind::Delete { i += 1; }
        let dels = &ops[del_start..i];
        // 收集紧随的连续 Insert
        let ins_start = i;
        while i < ops.len() && ops[i].op == DiffOpKind::Insert { i += 1; }
        let ins = &ops[ins_start..i];

        if dels.is_empty() && ins.is_empty() {
            // 既非 Delete 也非 Insert，直接保留（Keep 等）
            result.push(ops[del_start].clone());
            i = del_start + 1;
            continue;
        }

        // 按顺序配对同 tag 的 Delete+Insert → Keep
        let mut di = 0;
        let mut ii = 0;
        while di < dels.len() && ii < ins.len() {
            let old_idx = dels[di].old_idx.unwrap();
            let new_idx = ins[ii].new_idx.unwrap();
            if old_nodes[old_idx].tag == new_nodes[new_idx].tag {
                // 同 tag：合并为 Keep（hash 不同会在后续变 changed）
                result.push(crate::myers::DiffOp { op: DiffOpKind::Keep, old_idx: Some(old_idx), new_idx: Some(new_idx) });
                di += 1; ii += 1;
            } else if old_nodes[old_idx].tag.starts_with('h') && new_nodes[new_idx].tag.starts_with('h') {
                // 标题家族互换（h2→h3 等）也合并为 Keep，type_changed 会标记
                result.push(crate::myers::DiffOp { op: DiffOpKind::Keep, old_idx: Some(old_idx), new_idx: Some(new_idx) });
                di += 1; ii += 1;
            } else {
                // tag 不同，无法配对：先输出 Delete
                result.push(dels[di].clone());
                di += 1;
            }
        }
        // 剩余未配对的
        while di < dels.len() { result.push(dels[di].clone()); di += 1; }
        while ii < ins.len() { result.push(ins[ii].clone()); ii += 1; }
    }
    result
}

fn ops_to_diff_result(ops: &[crate::myers::DiffOp], old_nodes: &[HtmlNode], new_nodes: &[HtmlNode], source_tree: &Value) -> DiffResult {
    let src_content = source_tree.get("content").and_then(|v| v.as_array());
    let mut changed = Vec::new();
    let mut deleted = Vec::new();
    let mut added = Vec::new();

    // 后处理：把相邻的 Delete(old_i)+Insert(new_j) 且 tag 相同的，合并成 Keep。
    // 这样「同位置同类型的内容替换」会被识别为 changed（原地修改，保留 nodeId），
    // 而非 delete+insert（原节点删除 + 新节点追加到末尾，导致顺序错乱）。
    let ops = merge_replace_pairs(ops, old_nodes, new_nodes);

    for op in ops {
        match op.op {
            crate::myers::DiffOpKind::Keep => {
                let old = &old_nodes[op.old_idx.unwrap()];
                let new = &new_nodes[op.new_idx.unwrap()];
                if old.hash != new.hash {
                    let pm_node_id = src_content
                        .and_then(|arr| arr.get(op.old_idx.unwrap()))
                        .and_then(|n| n.get("attrs"))
                        .and_then(|a| a.get("nodeId"))
                        .and_then(|v| v.as_str())
                        .map(String::from);
                    changed.push(ChangeOp {
                        pm_node_id,
                        tag: new.tag.clone(),
                        inner_html: new.inner_html.clone(),
                        attrs: new.attrs.clone(),
                        type_changed: old.tag != new.tag,
                        old_idx: op.old_idx,
                    });
                }
            }
            crate::myers::DiffOpKind::Delete => {
                let pm_node_id = src_content
                    .and_then(|arr| arr.get(op.old_idx.unwrap()))
                    .and_then(|n| n.get("attrs"))
                    .and_then(|a| a.get("nodeId"))
                    .and_then(|v| v.as_str())
                    .map(String::from);
                deleted.push(DeleteOp {
                    pm_node_id,
                    old_idx: op.old_idx,
                });
            }
            crate::myers::DiffOpKind::Insert => {
                let new = &new_nodes[op.new_idx.unwrap()];
                added.push(AddOp {
                    tag: new.tag.clone(),
                    inner_html: new.inner_html.clone(),
                    attrs: new.attrs.clone(),
                });
            }
        }
    }

    DiffResult { changed, deleted, added }
}

// ── 测试 ──────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::myers::{parse_nodes, simple_diff, DiffOpKind, node_similarity};

    #[test]
    fn test_diff_no_changes() {
        let html = "<p>hello</p>";
        let result = diff(html, html, &serde_json::json!({}));
        assert_eq!(result.changed.len(), 0);
        assert_eq!(result.deleted.len(), 0);
        assert_eq!(result.added.len(), 0);
    }

    #[test]
    fn test_diff_insert() {
        let old = "<p>a</p>";
        let new = "<p>a</p><p>b</p>";
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.changed.len(), 0);
        assert_eq!(result.deleted.len(), 0);
        assert_eq!(result.added.len(), 1);
        assert_eq!(result.added[0].tag, "p");
    }

    #[test]
    fn test_diff_modify() {
        let old = "<p>hello</p>";
        let new = "<p>world</p>";
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.changed.len(), 1);
        assert_eq!(result.changed[0].inner_html, "world");
    }

    #[test]
    fn test_diff_drawio_src_change() {
        let old = r#"<km-drawio src="a.svg"/>"#;
        let new = r#"<km-drawio src="b.svg"/>"#;
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.changed.len(), 1);
    }

    #[test]
    fn test_diff_empty() {
        let result = diff("", "", &serde_json::json!({}));
        assert_eq!(result.changed.len(), 0);
    }

    #[test]
    fn test_parse_nodes_simple() {
        let html = "<h2>标题</h2>\n<p>内容</p>";
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 2);
        assert_eq!(nodes[0].tag, "h2");
        assert_eq!(nodes[0].inner_html, "标题");
        assert_eq!(nodes[1].tag, "p");
        assert_eq!(nodes[1].inner_html, "内容");
    }

    #[test]
    fn test_parse_nodes_nested_ul_li() {
        let html = "<ul><li>项一</li><li>项二</li></ul>";
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "ul");
        assert!(nodes[0].inner_html.contains("项一"));
        assert!(nodes[0].inner_html.contains("项二"));
    }

    #[test]
    fn test_parse_nodes_nested_same_tag() {
        let html = "<ul><li><ul><li>深层</li></ul></li></ul>";
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "ul");
        assert!(nodes[0].inner_html.contains("深层"));
    }

    #[test]
    fn test_parse_nodes_self_closing() {
        let html = "<km-drawio/>";
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "km-drawio");
        assert_eq!(nodes[0].inner_html, "");
    }

    #[test]
    fn test_parse_nodes_multiple_top_level() {
        let html = "<h1>标题</h1>\n<p>段落一</p>\n<p>段落二</p>";
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 3);
        assert_eq!(nodes[0].tag, "h1");
        assert_eq!(nodes[1].tag, "p");
        assert_eq!(nodes[2].tag, "p");
    }

    #[test]
    fn test_parse_nodes_attrs() {
        let html = r#"<pre language="TypeScript"><code>x</code></pre>"#;
        let nodes = parse_nodes(html);
        assert_eq!(nodes[0].attrs.get("language").map(|v| v.as_str()), Some("TypeScript"));
    }

    #[test]
    fn test_simple_diff_identical() {
        let nodes = parse_nodes("<h1>标题</h1>\n<p>内容</p>");
        let ops = simple_diff(&nodes, &nodes, 0.5);
        assert!(ops.iter().all(|op| op.op == DiffOpKind::Keep));
        assert_eq!(ops.len(), 2);
    }

    #[test]
    fn test_simple_diff_empty() {
        let ops = simple_diff(&[], &[], 0.5);
        assert_eq!(ops.len(), 0);
    }

    #[test]
    fn test_simple_diff_single_insert() {
        let old = parse_nodes("<h1>唯一标题</h1>");
        let new = parse_nodes("<h1>唯一标题</h1>\n<h2>新增章节</h2>");
        let ops = simple_diff(&old, &new, 0.5);
        assert!(ops.iter().any(|op| op.op == DiffOpKind::Insert));
    }

    #[test]
    fn test_simple_diff_single_delete() {
        let old = parse_nodes("<h1>标题</h1>\n<h2>章节</h2>");
        let new = parse_nodes("<h2>章节</h2>");
        let ops = simple_diff(&old, &new, 0.5);
        assert!(ops.iter().any(|op| op.op == DiffOpKind::Delete));
        assert_eq!(ops.iter().filter(|op| op.op == DiffOpKind::Delete).count(), 1);
    }

    // ── parseNodes variations ──────────────────────────────────────────────────

    #[test]
    fn test_parse_nodes_with_whitespace_and_newlines() {
        let html = "  \n<h1>标题</h1>  \n  <p>内容</p>\n  ";
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 2);
        assert_eq!(nodes[0].tag, "h1");
        assert_eq!(nodes[1].tag, "p");
    }

    #[test]
    fn test_parse_nodes_with_attributes_and_quotes() {
        let html = r#"<div class="container" id="main" data-value="test">content</div>"#;
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "div");
        assert!(nodes[0].attrs.contains_key("class"));
        assert_eq!(nodes[0].inner_html, "content");
    }

    #[test]
    fn test_parse_nodes_deeply_nested_structures() {
        let html = "<ul><li><ul><li><ul><li>deep</li></ul></li></ul></li></ul>";
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "ul");
        assert!(nodes[0].inner_html.contains("deep"));
    }

    #[test]
    fn test_parse_nodes_mixed_self_closing_and_regular() {
        let html = "<p>text</p><hr/><img src=\"test.png\"/><p>more</p>";
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 4);
        assert_eq!(nodes[0].tag, "p");
        assert_eq!(nodes[1].tag, "hr");
        assert_eq!(nodes[2].tag, "img");
        assert_eq!(nodes[3].tag, "p");
    }

    #[test]
    fn test_parse_nodes_with_html_comments() {
        let html = "<!-- comment --><p>text</p><!-- another -->";
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "p");
    }

    #[test]
    fn test_parse_nodes_video_with_multiple_attrs() {
        let html = r#"<km-video src="video.mp4" url="backup.mp4" autoplay="true"/>"#;
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "km-video");
        assert_eq!(nodes[0].attrs.get("src").map(|s| s.as_str()), Some("video.mp4"));
    }

    #[test]
    fn test_parse_nodes_xtable_with_id() {
        let html = r#"<km-xtable xtable-id="12345"/>"#;
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "km-xtable");
        assert_eq!(nodes[0].attrs.get("xtable-id").map(|s| s.as_str()), Some("12345"));
    }

    #[test]
    fn test_parse_nodes_code_block_with_language() {
        let html = "<pre language=\"python\"><code>def hello():\n    pass</code></pre>";
        let nodes = parse_nodes(html);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "pre");
        assert_eq!(nodes[0].attrs.get("language").map(|s| s.as_str()), Some("python"));
    }

    // ── nodeSimilarity thresholds ──────────────────────────────────────────────

    #[test]
    fn test_similarity_heading_same_content_different_levels() {
        let h1 = parse_nodes("<h1>章节</h1>");
        let h2 = parse_nodes("<h2>章节</h2>");
        let sim = node_similarity(&h1[0], &h2[0]);
        assert!(sim >= 0.8 && sim <= 1.0, "heading same content should have high similarity");
    }

    #[test]
    fn test_similarity_heading_different_content_same_level() {
        let h1_a = parse_nodes("<h1>标题A</h1>");
        let h1_b = parse_nodes("<h1>标题B</h1>");
        let sim = node_similarity(&h1_a[0], &h1_b[0]);
        assert!(sim > 0.0 && sim < 1.0, "different heading content should have medium similarity");
    }

    #[test]
    fn test_similarity_paragraph_with_minor_change() {
        let p1 = parse_nodes("<p>这是一段长文本内容</p>");
        let p2 = parse_nodes("<p>这是一段长文本内容修改</p>");
        let sim = node_similarity(&p1[0], &p2[0]);
        assert!(sim > 0.5, "minor change should have similarity > 0.5");
    }

    #[test]
    fn test_similarity_paragraph_completely_replaced() {
        let p1 = parse_nodes("<p>first content</p>");
        let p2 = parse_nodes("<p>completely different</p>");
        let sim = node_similarity(&p1[0], &p2[0]);
        assert!(sim >= 0.0 && sim < 0.5, "completely different should have low similarity");
    }

    #[test]
    fn test_similarity_rich_node_drawio_different_src() {
        let drawio1 = parse_nodes(r#"<km-drawio src="a.svg"/>"#);
        let drawio2 = parse_nodes(r#"<km-drawio src="b.svg"/>"#);
        let sim = node_similarity(&drawio1[0], &drawio2[0]);
        assert_eq!(sim, 0.9, "different src rich nodes should have 0.9 similarity");
    }

    #[test]
    fn test_similarity_rich_node_same_tag_returns_high() {
        let xtable1 = parse_nodes(r#"<km-xtable xtable-id="id1"/>"#);
        let xtable2 = parse_nodes(r#"<km-xtable xtable-id="id2"/>"#);
        let sim = node_similarity(&xtable1[0], &xtable2[0]);
        assert_eq!(sim, 0.9, "rich nodes with same tag should have 0.9 similarity");
    }

    // 注：multiple_inserts / multiple_deletes / mixed_operations 三个 simple_diff 场景
    // 已由 tests/myers_tests.rs 同名集成测试完整覆盖（断言 op 序列而非仅计数），此处不再重复。

    #[test]
    fn test_diff_threshold_high_0_9() {
        let old = parse_nodes("<p>a</p>");
        let new = parse_nodes("<p>b</p>");
        let ops = simple_diff(&old, &new, 0.9);
        // simple_diff ignores threshold in current implementation, always position-based
        assert_eq!(ops.len(), 1);
    }

    #[test]
    fn test_diff_threshold_low_0_1() {
        let old = parse_nodes("<p>x</p><p>y</p>");
        let new = parse_nodes("<p>x</p><p>y</p><p>z</p>");
        let ops = simple_diff(&old, &new, 0.1);
        assert_eq!(ops.len(), 3);
    }

    // ── complex diffs ──────────────────────────────────────────────────────────

    #[test]
    fn test_diff_complex_document_structure_change() {
        let old = "<h1>Title</h1><ul><li>item1</li><li>item2</li></ul>";
        let new = "<h1>Title</h1><ol><li>item1</li><li>item2</li><li>item3</li></ol>";
        let result = diff(old, new, &serde_json::json!({}));
        assert!(result.changed.len() > 0 || result.added.len() > 0);
    }

    #[test]
    fn test_diff_complex_with_multiple_rich_elements() {
        let old = r#"<h1>title</h1><km-drawio src="a.svg"/><p>text</p>"#;
        let new = r#"<h1>title</h1><km-drawio src="b.svg"/><km-video src="v.mp4"/><p>text</p>"#;
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.added.len(), 1);
    }

    #[test]
    fn test_diff_entire_content_replacement() {
        let old = "<p>old content</p>";
        let new = "<div>completely new structure</div>";
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.changed.len(), 1);
        assert_eq!(result.changed[0].tag, "div");
    }

    // ── type changes ───────────────────────────────────────────────────────────

    #[test]
    fn test_diff_type_change_paragraph_to_heading() {
        let old = "<p>convert me</p>";
        let new = "<h2>convert me</h2>";
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.changed.len(), 1);
        assert!(result.changed[0].type_changed);
        assert_eq!(result.changed[0].tag, "h2");
    }

    #[test]
    fn test_diff_type_change_heading_to_paragraph() {
        let old = "<h1>demote</h1>";
        let new = "<p>demote</p>";
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.changed.len(), 1);
        assert!(result.changed[0].type_changed);
    }

    #[test]
    fn test_diff_type_change_block_to_rich_element() {
        let old = "<p>replace</p>";
        let new = "<km-drawio src=\"diagram.svg\"/>";
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.changed.len(), 1);
        assert!(result.changed[0].type_changed);
        assert_eq!(result.changed[0].tag, "km-drawio");
    }

    #[test]
    fn test_diff_type_change_multiple_in_sequence() {
        let old = "<h1>1</h1><p>2</p><h2>3</h2>";
        let new = "<p>1</p><h1>2</h1><p>3</p>";
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.changed.len(), 3);
        assert!(result.changed.iter().all(|c| c.type_changed));
    }

    #[test]
    fn test_diff_type_not_changed_when_same_tag() {
        let old = "<p>content1</p>";
        let new = "<p>content2</p>";
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.changed.len(), 1);
        assert!(!result.changed[0].type_changed);
    }

    #[test]
    fn test_diff_tree_with_children_array() {
        let source_tree = serde_json::json!({
            "tag": "div",
            "children": [
                { "tag": "h1", "pmNodeId": "id1", "hash": "old_hash1" },
                { "tag": "p", "pmNodeId": "id2", "hash": "old_hash2" }
            ]
        });
        let old = "<h1>old</h1><p>old</p>";
        let new = "<h1>new</h1><p>new</p>";
        let result = diff(old, new, &source_tree);
        assert_eq!(result.changed.len(), 2);
    }

    #[test]
    fn test_diff_tree_deletion_with_pm_node_id() {
        let source_tree = serde_json::json!({
            "type": "doc",
            "content": [
                { "type": "title", "attrs": {"nodeId": "id1"}, "content": [{"type": "text", "text": "Title"}] },
                { "type": "paragraph", "attrs": {"nodeId": "id2"}, "content": [{"type": "text", "text": "Para"}] }
            ]
        });
        let new = "<h1>Title</h1>";
        let result = diff("<h1>Title</h1><p>Para</p>", new, &source_tree);
        assert_eq!(result.deleted.len(), 1);
    }

    #[test]
    fn test_diff_flat_adds_operations() {
        let old = "<p>a</p>";
        let new = "<p>a</p><p>b</p><p>c</p>";
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.added.len(), 2);
        assert_eq!(result.added[0].tag, "p");
        assert_eq!(result.added[1].tag, "p");
    }

    #[test]
    fn test_diff_flat_deletes_operations() {
        let old = "<h1>1</h1><p>2</p><h2>3</h2>";
        let new = "<h1>1</h1>";
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.deleted.len(), 2);
    }

    #[test]
    fn test_diff_changed_operation_with_attrs() {
        let old = r#"<p>old</p>"#;
        let new = r#"<p data-value="new">new</p>"#;
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.changed.len(), 1);
        assert_eq!(result.changed[0].inner_html, "new");
        assert_eq!(result.changed[0].attrs.get("data-value").map(|s| s.as_str()), Some("new"));
    }

    #[test]
    fn test_diff_added_operation_preserves_attrs() {
        let old = "<h1>title</h1>";
        let new = r#"<h1>title</h1><img src="image.png" alt="description"/>"#;
        let result = diff(old, new, &serde_json::json!({}));
        assert_eq!(result.added.len(), 1);
        assert_eq!(result.added[0].tag, "img");
        assert_eq!(result.added[0].attrs.get("src").map(|s| s.as_str()), Some("image.png"));
    }

    #[test]
    fn test_diff_empty_vs_content() {
        let result = diff("", "<h1>new</h1><p>content</p>", &serde_json::json!({}));
        assert_eq!(result.added.len(), 2);
        assert_eq!(result.deleted.len(), 0);
    }

    #[test]
    fn test_diff_content_vs_empty() {
        let result = diff("<h1>old</h1><p>content</p>", "", &serde_json::json!({}));
        assert_eq!(result.deleted.len(), 2);
        assert_eq!(result.added.len(), 0);
    }

    // ── merge_replace_pairs 单元测试（Bug 3 核心）────────────────────────
    use crate::myers::{DiffOp, HtmlNode, hash_str};
    use std::collections::HashMap;

    fn mk_node(tag: &str, inner: &str) -> HtmlNode {
        let attrs = HashMap::new();
        HtmlNode {
            tag: tag.to_string(),
            attrs,
            inner_html: inner.to_string(),
            hash: hash_str(&format!("{tag}|{inner}")),
        }
    }
    fn mk_op(op: DiffOpKind, old_idx: Option<usize>, new_idx: Option<usize>) -> DiffOp {
        DiffOp { op, old_idx, new_idx }
    }

    #[test]
    fn test_merge_delete_insert_same_tag_becomes_keep() {
        // [Keep p0] [Delete p1] [Insert newP] [Keep p2]
        // p1 与 newP 同 tag("p") → 合并为 Keep
        let old = vec![mk_node("p", "a"), mk_node("p", "b"), mk_node("p", "c")];
        let new = vec![mk_node("p", "a"), mk_node("p", "B"), mk_node("p", "c")];
        let ops = vec![
            mk_op(DiffOpKind::Keep, Some(0), Some(0)),
            mk_op(DiffOpKind::Delete, Some(1), None),
            mk_op(DiffOpKind::Insert, None, Some(1)),
            mk_op(DiffOpKind::Keep, Some(2), Some(2)),
        ];
        let merged = merge_replace_pairs(&ops, &old, &new);
        // Delete+Insert 合并成 Keep
        assert_eq!(merged.len(), 3);
        assert_eq!(merged[1].op, DiffOpKind::Keep);
        assert_eq!(merged[1].old_idx, Some(1));
        assert_eq!(merged[1].new_idx, Some(1));
    }

    #[test]
    fn test_merge_delete_insert_different_tag_not_merged() {
        // Delete(p) + Insert(h2) tag 不同 → 不合并
        let old = vec![mk_node("p", "a")];
        let new = vec![mk_node("h2", "B")];
        let ops = vec![
            mk_op(DiffOpKind::Delete, Some(0), None),
            mk_op(DiffOpKind::Insert, None, Some(0)),
        ];
        let merged = merge_replace_pairs(&ops, &old, &new);
        // 仍为 Delete + Insert
        assert_eq!(merged.len(), 2);
        assert_eq!(merged[0].op, DiffOpKind::Delete);
        assert_eq!(merged[1].op, DiffOpKind::Insert);
    }

    #[test]
    fn test_merge_heading_family_swap() {
        // Delete(h2) + Insert(h3) 同属标题家族 → 合并为 Keep（type_changed 标记）
        let old = vec![mk_node("h2", "标题")];
        let new = vec![mk_node("h3", "新标题")];
        let ops = vec![
            mk_op(DiffOpKind::Delete, Some(0), None),
            mk_op(DiffOpKind::Insert, None, Some(0)),
        ];
        let merged = merge_replace_pairs(&ops, &old, &new);
        assert_eq!(merged.len(), 1);
        assert_eq!(merged[0].op, DiffOpKind::Keep);
    }

    #[test]
    fn test_merge_unbalanced_delete_insert() {
        // 2 Delete + 1 Insert：第一个配对合并，剩余 Delete 保留
        let old = vec![mk_node("p", "a"), mk_node("p", "b"), mk_node("p", "c")];
        let new = vec![mk_node("p", "X")];
        let ops = vec![
            mk_op(DiffOpKind::Delete, Some(0), None),
            mk_op(DiffOpKind::Delete, Some(1), None),
            mk_op(DiffOpKind::Insert, None, Some(0)),
        ];
        let merged = merge_replace_pairs(&ops, &old, &new);
        // 1 Keep(配对) + 1 Delete(剩余)
        assert_eq!(merged.len(), 2);
        assert_eq!(merged[0].op, DiffOpKind::Keep);
        assert_eq!(merged[1].op, DiffOpKind::Delete);
    }

    #[test]
    fn test_merge_pure_keep_untouched() {
        // 只有 Keep，不触发合并逻辑
        let old = vec![mk_node("p", "a")];
        let new = vec![mk_node("p", "a")];
        let ops = vec![mk_op(DiffOpKind::Keep, Some(0), Some(0))];
        let merged = merge_replace_pairs(&ops, &old, &new);
        assert_eq!(merged.len(), 1);
        assert_eq!(merged[0].op, DiffOpKind::Keep);
    }
}
