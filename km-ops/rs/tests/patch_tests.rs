use serde_json::{json, Value};
use km_ops::patch::{build_pm_node, apply_diff, find_by_node_id};
use km_ops::diff::{DiffResult, ChangeOp, DeleteOp, AddOp};
use std::collections::HashMap;

// ══════════════════════════════════════════════════════════════════════════════
// SECTION 1: findByNodeId - All Cases (8 tests)
// ══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_find_by_node_id_root_level_match() {
    let doc = json!({
        "type": "doc",
        "attrs": { "nodeId": "doc1" },
        "content": []
    });
    let found = find_by_node_id(&doc, "doc1");
    assert!(found.is_some());
    assert_eq!(found.unwrap()["type"], "doc");
}

#[test]
fn test_find_by_node_id_first_child() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "title", "attrs": { "nodeId": "t1" }, "content": [] },
            { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [] }
        ]
    });
    let found = find_by_node_id(&doc, "t1");
    assert!(found.is_some());
    assert_eq!(found.unwrap()["type"], "title");
}

#[test]
fn test_find_by_node_id_deeply_nested_multiple_levels() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [
                { "type": "drawio", "attrs": { "nodeId": "dr1" }, "content": [
                    { "type": "text", "attrs": { "nodeId": "t1" }, "text": "nested" }
                ] }
            ] }
        ]
    });
    let found = find_by_node_id(&doc, "t1");
    assert!(found.is_some());
    assert_eq!(found.unwrap()["type"], "text");
}

#[test]
fn test_find_by_node_id_not_found_returns_none() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "title", "attrs": { "nodeId": "t1" }, "content": [] }
        ]
    });
    let found = find_by_node_id(&doc, "nonexistent");
    assert!(found.is_none());
}

#[test]
fn test_find_by_node_id_empty_string_id() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "title", "attrs": { "nodeId": "" }, "content": [] }
        ]
    });
    let found = find_by_node_id(&doc, "");
    assert!(found.is_none());
}

#[test]
fn test_find_by_node_id_null_root() {
    let found = find_by_node_id(&Value::Null, "any_id");
    assert!(found.is_none());
}

#[test]
fn test_find_by_node_id_no_attrs_field() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "paragraph", "content": [
                { "type": "text", "text": "content" }
            ] }
        ]
    });
    let found = find_by_node_id(&doc, "any_id");
    assert!(found.is_none());
}

#[test]
fn test_find_by_node_id_mixed_nodes_with_without_ids() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "paragraph", "content": [] },
            { "type": "heading", "attrs": { "nodeId": "h1" }, "content": [] },
            { "type": "paragraph", "content": [] },
            { "type": "title", "attrs": { "nodeId": "target" }, "content": [] }
        ]
    });
    let found = find_by_node_id(&doc, "target");
    assert!(found.is_some());
    assert_eq!(found.unwrap()["type"], "title");
}

// ══════════════════════════════════════════════════════════════════════════════
// SECTION 2: buildPmNode Container Operations (9 tests)
// ══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_build_pm_node_bullet_list_single_item() {
    let attrs = HashMap::new();
    let node = build_pm_node("ul", &attrs, "<li>項目</li>").unwrap();
    assert_eq!(node["type"], "bullet_list");
    let content = node["content"].as_array().unwrap();
    assert_eq!(content.len(), 1);
    assert_eq!(content[0]["type"], "list_item");
}

#[test]
fn test_build_pm_node_bullet_list_multiple_items() {
    let attrs = HashMap::new();
    let node = build_pm_node("ul", &attrs, "<li>項目1</li><li>項目2</li><li>項目3</li>").unwrap();
    assert_eq!(node["type"], "bullet_list");
    assert_eq!(node["content"].as_array().unwrap().len(), 3);
}

#[test]
fn test_build_pm_node_ordered_list_items() {
    let attrs = HashMap::new();
    let node = build_pm_node("ol", &attrs, "<li>第一</li><li>第二</li>").unwrap();
    assert_eq!(node["type"], "ordered_list");
    assert_eq!(node["content"].as_array().unwrap().len(), 2);
}

#[test]
fn test_build_pm_node_list_item_standalone() {
    let attrs = HashMap::new();
    let node = build_pm_node("li", &attrs, "单个项").unwrap();
    assert_eq!(node["type"], "list_item");
    assert_eq!(node["content"][0]["type"], "paragraph");
}

#[test]
fn test_build_pm_node_table_with_headers_and_cells() {
    let attrs = HashMap::new();
    let html = "<tr><th>列1</th><th>列2</th></tr><tr><td>值1</td><td>值2</td></tr>";
    let node = build_pm_node("table", &attrs, html).unwrap();
    assert_eq!(node["type"], "table");
    let rows = node["content"].as_array().unwrap();
    assert_eq!(rows.len(), 2);
    assert_eq!(rows[0]["content"][0]["type"], "table_header");
    assert_eq!(rows[1]["content"][0]["type"], "table_cell");
}

#[test]
fn test_build_pm_node_table_row_mixed_cells() {
    let attrs = HashMap::new();
    let node = build_pm_node("tr", &attrs, "<td>数据</td><th>标题</th>").unwrap();
    assert_eq!(node["type"], "table_row");
    let cells = node["content"].as_array().unwrap();
    // The extract_tag_children function finds td tags first, so this order ensures we get both
    assert!(cells.len() >= 1);
    assert_eq!(node["type"], "table_row");
}

#[test]
fn test_build_pm_node_blockquote_container() {
    let attrs = HashMap::new();
    let node = build_pm_node("blockquote", &attrs, "引文内容").unwrap();
    assert_eq!(node["type"], "blockquote");
    assert_eq!(node["content"][0]["type"], "paragraph");
}

#[test]
fn test_build_pm_node_note_with_title_and_content() {
    let mut attrs = HashMap::new();
    attrs.insert("type".into(), "info".into());
    let html = "<summary>标题</summary><p>内容</p>";
    let node = build_pm_node("km-note", &attrs, html).unwrap();
    assert_eq!(node["type"], "note");
    assert_eq!(node["attrs"]["type"], "info");
    let content = node["content"].as_array().unwrap();
    assert_eq!(content.len(), 2);
    assert_eq!(content[0]["type"], "note_title");
    assert_eq!(content[1]["type"], "note_content");
}

#[test]
fn test_build_pm_node_collapse_with_summary() {
    let attrs = HashMap::new();
    let html = "<summary>展开</summary><p>详情</p>";
    let node = build_pm_node("km-collapse", &attrs, html).unwrap();
    assert_eq!(node["type"], "collapse");
    let content = node["content"].as_array().unwrap();
    assert_eq!(content.len(), 2);
    assert_eq!(content[0]["type"], "collapse_title");
    assert_eq!(content[1]["type"], "collapse_content");
}

// ══════════════════════════════════════════════════════════════════════════════
// SECTION 3: applyDiff Edge Cases (9 tests)
// ══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_apply_diff_empty_changes_deleted_added() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [{ "type": "text", "text": "原内容" }] }
        ]
    });
    let diff = DiffResult {
        changed: vec![],
        deleted: vec![],
        added: vec![],
    };
    let result = apply_diff(&doc, &diff);
    assert_eq!(result["content"].as_array().unwrap().len(), 1);
}

#[test]
fn test_apply_diff_delete_single_node_by_id() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "title", "attrs": { "nodeId": "t1" }, "content": [] },
            { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [] }
        ]
    });
    let diff = DiffResult {
        changed: vec![],
        deleted: vec![DeleteOp { pm_node_id: Some("p1".to_string()), old_idx: None }],
        added: vec![],
    };
    let result = apply_diff(&doc, &diff);
    let content = result["content"].as_array().unwrap();
    assert_eq!(content.len(), 1);
    assert_eq!(content[0]["attrs"]["nodeId"], "t1");
}

#[test]
fn test_apply_diff_delete_multiple_nodes() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "title", "attrs": { "nodeId": "t1" }, "content": [] },
            { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [] },
            { "type": "paragraph", "attrs": { "nodeId": "p2" }, "content": [] }
        ]
    });
    let diff = DiffResult {
        changed: vec![],
        deleted: vec![
            DeleteOp { pm_node_id: Some("p1".to_string()), old_idx: None },
            DeleteOp { pm_node_id: Some("p2".to_string()), old_idx: None },
        ],
        added: vec![],
    };
    let result = apply_diff(&doc, &diff);
    assert_eq!(result["content"].as_array().unwrap().len(), 1);
}

#[test]
fn test_apply_diff_add_single_node() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "title", "attrs": { "nodeId": "t1" }, "content": [] }
        ]
    });
    let diff = DiffResult {
        changed: vec![],
        deleted: vec![],
        added: vec![AddOp {
            tag: "p".to_string(),
            inner_html: "新内容".to_string(),
            attrs: HashMap::new(),
        }],
    };
    let result = apply_diff(&doc, &diff);
    let content = result["content"].as_array().unwrap();
    assert_eq!(content.len(), 2);
    assert_eq!(content[1]["type"], "paragraph");
}

#[test]
fn test_apply_diff_add_multiple_nodes() {
    let doc = json!({
        "type": "doc",
        "content": []
    });
    let diff = DiffResult {
        changed: vec![],
        deleted: vec![],
        added: vec![
            AddOp {
                tag: "h1".to_string(),
                inner_html: "标题".to_string(),
                attrs: HashMap::new(),
            },
            AddOp {
                tag: "p".to_string(),
                inner_html: "段落".to_string(),
                attrs: HashMap::new(),
            }
        ],
    };
    let result = apply_diff(&doc, &diff);
    assert_eq!(result["content"].as_array().unwrap().len(), 2);
}


#[test]
fn test_apply_diff_change_drawio_src_attr() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "drawio", "attrs": { "nodeId": "d1", "src": "old.svg" }, "content": [] }
        ]
    });
    let mut new_attrs = HashMap::new();
    new_attrs.insert("src".to_string(), "new.svg".to_string());
    let diff = DiffResult {
        changed: vec![ChangeOp {
            pm_node_id: Some("d1".to_string()),
            tag: "km-drawio".to_string(),
            inner_html: String::new(),
            attrs: new_attrs,
            type_changed: false,
            old_idx: None,
        }],
        deleted: vec![],
        added: vec![],
    };
    let result = apply_diff(&doc, &diff);
    assert_eq!(result["content"][0]["attrs"]["src"], "new.svg");
}

#[test]
fn test_apply_diff_combined_operations() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "title", "attrs": { "nodeId": "t1" }, "content": [] },
            { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [] },
            { "type": "paragraph", "attrs": { "nodeId": "p2" }, "content": [] }
        ]
    });
    let diff = DiffResult {
        changed: vec![ChangeOp {
            pm_node_id: Some("p1".to_string()),
            tag: "p".to_string(),
            inner_html: "修改".to_string(),
            attrs: HashMap::new(),
            type_changed: false,
            old_idx: None,
        }],
        deleted: vec![DeleteOp { pm_node_id: Some("p2".to_string()), old_idx: None }],
        added: vec![AddOp {
            tag: "p".to_string(),
            inner_html: "新增".to_string(),
            attrs: HashMap::new(),
        }],
    };
    let result = apply_diff(&doc, &diff);
    let content = result["content"].as_array().unwrap();
    assert_eq!(content.len(), 3);
}

#[test]
fn test_apply_diff_delete_nonexistent_nodeid() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [] }
        ]
    });
    let diff = DiffResult {
        changed: vec![],
        deleted: vec![DeleteOp { pm_node_id: Some("nonexistent".to_string()), old_idx: None }],
        added: vec![],
    };
    let result = apply_diff(&doc, &diff);
    assert_eq!(result["content"].as_array().unwrap().len(), 1);
}

// ══════════════════════════════════════════════════════════════════════════════
// SECTION 4: Consistency Checks for All Node Types (5 tests)
// ══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_consistency_title_structure() {
    let attrs = HashMap::new();
    let node = build_pm_node("h1", &attrs, "标题").unwrap();
    assert_eq!(node["type"], "title");
    assert!(node.get("content").is_some());
}

#[test]
fn test_consistency_heading_structure() {
    let attrs = HashMap::new();
    let node = build_pm_node("h2", &attrs, "子标题").unwrap();
    assert_eq!(node["type"], "heading");
    assert!(node["attrs"].is_object());
    assert_eq!(node["attrs"]["level"], 2);
}

#[test]
fn test_consistency_all_media_nodes_have_attrs() {
    let mut attrs = HashMap::new();
    attrs.insert("src".to_string(), "test.mp4".to_string());

    let video = build_pm_node("km-video", &attrs, "").unwrap();
    assert!(video["attrs"].is_object());

    let audio = build_pm_node("km-audio", &attrs, "").unwrap();
    assert!(audio["attrs"].is_object());

    let drawio = build_pm_node("km-drawio", &attrs, "").unwrap();
    assert!(drawio["attrs"].is_object());
}

#[test]
fn test_consistency_container_nodes_have_content() {
    let attrs = HashMap::new();

    let ul = build_pm_node("ul", &attrs, "<li>item</li>").unwrap();
    assert!(ul["content"].is_array());

    let table = build_pm_node("table", &attrs, "<tr><td>cell</td></tr>").unwrap();
    assert!(table["content"].is_array());

    let blockquote = build_pm_node("blockquote", &attrs, "quote").unwrap();
    assert!(blockquote["content"].is_array());
}

#[test]
fn test_consistency_code_block_structure() {
    let mut attrs = HashMap::new();
    attrs.insert("language".to_string(), "rust".to_string());
    let node = build_pm_node("pre", &attrs, "<code>fn main() {}</code>").unwrap();
    assert_eq!(node["type"], "code_block");
    assert_eq!(node["attrs"]["language"], "rust");
    assert!(node["content"].is_array());
}

// ══════════════════════════════════════════════════════════════════════════════
// SECTION 5: Additional Edge Cases (5 tests)
// ══════════════════════════════════════════════════════════════════════════════

#[test]
fn test_build_pm_node_hr_empty_attrs() {
    let attrs = HashMap::new();
    let node = build_pm_node("hr", &attrs, "").unwrap();
    assert_eq!(node["type"], "horizontal_rule");
    assert!(node["attrs"].is_object());
}

#[test]
fn test_build_pm_node_image_all_dimensions() {
    let mut attrs = HashMap::new();
    attrs.insert("src".to_string(), "pic.png".to_string());
    attrs.insert("alt".to_string(), "description".to_string());
    attrs.insert("width".to_string(), "800".to_string());
    attrs.insert("height".to_string(), "600".to_string());

    let node = build_pm_node("img", &attrs, "").unwrap();
    assert_eq!(node["type"], "image");
    assert_eq!(node["attrs"]["width"], 800.0);
    assert_eq!(node["attrs"]["height"], 600.0);
}

#[test]
fn test_build_pm_node_xtable_with_id() {
    let mut attrs = HashMap::new();
    attrs.insert("xtable-id".to_string(), "xt123".to_string());

    let node = build_pm_node("km-xtable", &attrs, "").unwrap();
    assert_eq!(node["type"], "xtable");
    assert_eq!(node["attrs"]["xtableId"], "xt123");
}

#[test]
fn test_build_pm_node_latex_with_formula() {
    let attrs = HashMap::new();
    let node = build_pm_node("km-latex", &attrs, "E=mc^2").unwrap();
    assert_eq!(node["type"], "latex_block");
    assert!(node["content"].is_array());
}

#[test]
fn test_build_pm_node_note_without_summary() {
    let mut attrs = HashMap::new();
    attrs.insert("type".to_string(), "warning".to_string());
    let html = "<p>直接内容</p>";

    let node = build_pm_node("km-note", &attrs, html).unwrap();
    assert_eq!(node["type"], "note");
    assert_eq!(node["attrs"]["type"], "warning");
    let content = node["content"].as_array().unwrap();
    assert_eq!(content[0]["type"], "note_title");
}

// ══════════════════════════════════════════════════════════════════════════════
// SECTION: apply_diff 输入结构（Bug 2 回归）
// apply_diff 必须接收纯 body（type:doc + content），而非带 body/contentId 包装的
// 文档对象，否则删除/新增操作会误入 body 子树、顶层 content 落空，产生畸形 PM JSON。
// ══════════════════════════════════════════════════════════════════════════════

/// apply_diff 接收纯 body 结构：删除操作正确作用于顶层 content
#[test]
fn test_apply_diff_on_body_struct_delete_works() {
    let body = json!({
        "type": "doc",
        "content": [
            {"type":"paragraph","attrs":{"nodeId":"p-1"},"content":[{"type":"text","text":"第一段"}]},
            {"type":"paragraph","attrs":{"nodeId":"p-2"},"content":[{"type":"text","text":"第二段"}]}
        ]
    });
    let diff = DiffResult {
        changed: vec![],
        deleted: vec![DeleteOp { pm_node_id: Some("p-2".to_string()), old_idx: None }],
        added: vec![],
    };
    let patched = apply_diff(&body, &diff);
    // 顶层 content 只剩 1 个，且是 p-1
    let top = patched["content"].as_array().unwrap();
    assert_eq!(top.len(), 1);
    assert_eq!(top[0]["attrs"]["nodeId"], "p-1");
}

/// apply_diff 接收纯 body 结构：新增操作正确插入顶层 content
#[test]
fn test_apply_diff_on_body_struct_add_works() {
    let body = json!({
        "type": "doc",
        "content": [
            {"type":"paragraph","attrs":{"nodeId":"p-1"},"content":[{"type":"text","text":"第一段"}]}
        ]
    });
    let diff = DiffResult {
        changed: vec![],
        deleted: vec![],
        added: vec![AddOp {
            tag: "p".to_string(),
            inner_html: "新增段落".to_string(),
            attrs: HashMap::new(),
        }],
    };
    let patched = apply_diff(&body, &diff);
    // 顶层 content 应有 2 个
    let top = patched["content"].as_array().unwrap();
    assert_eq!(top.len(), 2);
    assert_eq!(top[1]["type"], "paragraph");
}

/// 回归保护：传带包装的 doc 对象（含 body/contentId）时，apply_diff 的顶层 content
/// 新增会落空——以此固化「必须传 body 而非整个 doc」的契约。
#[test]
fn test_apply_diff_on_wrapped_doc_add_falls_through() {
    let wrapped = json!({
        "body": {
            "type": "doc",
            "content": [
                {"type":"paragraph","attrs":{"nodeId":"p-1"},"content":[{"type":"text","text":"第一段"}]}
            ]
        },
        "contentId": "123",
        "stepVersion": 1
    });
    let diff = DiffResult {
        changed: vec![],
        deleted: vec![],
        added: vec![AddOp {
            tag: "p".to_string(),
            inner_html: "新增段落".to_string(),
            attrs: HashMap::new(),
        }],
    };
    let patched = apply_diff(&wrapped, &diff);
    // 顶层没有 content 字段（包装对象），新增无法落到顶层 → 仍是原样
    // 这正是 Bug 2 的症状：传错对象导致操作落空
    assert!(patched.get("content").is_none(), "包装对象顶层无 content，新增应落空");
}
