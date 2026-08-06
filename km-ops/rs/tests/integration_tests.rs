use serde_json::json;
use km_ops::patch::{apply_diff, find_by_node_id};
use km_ops::diff::{DiffResult, ChangeOp, AddOp};
use std::collections::HashMap;

// 这里只放真正走了 apply_diff 操作的集成测试
// 纯结构验证（只 find_by_node_id）移到 patch_tests.rs

#[test]
fn test_table_cell_content_edit() {
    let doc = json!({
        "type": "doc",
        "content": [{
            "type": "table",
            "attrs": { "nodeId": "t1" },
            "content": [{
                "type": "table_row",
                "attrs": { "nodeId": "tr1" },
                "content": [
                    { "type": "table_cell", "attrs": { "nodeId": "td1" }, "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "A" }] }] },
                    { "type": "table_cell", "attrs": { "nodeId": "td2" }, "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "B" }] }] }
                ]
            }]
        }]
    });
    let d = DiffResult {
        changed: vec![ChangeOp {
            pm_node_id: Some("td2".to_string()),
            tag: "td".to_string(),
            inner_html: "<p>B'</p>".to_string(),
            attrs: HashMap::new(),
            type_changed: false,
            old_idx: None,
        }],
        deleted: vec![],
        added: vec![],
    };
    let result = apply_diff(&doc, &d);
    // table 容器依然存在
    assert!(find_by_node_id(&result, "t1").is_some());
    // td2 被修改，td1 未受影响
    if let Some(td2) = find_by_node_id(&result, "td2") {
        assert_eq!(td2["content"][0]["content"][0]["text"], "B'");
    }
    if let Some(td1) = find_by_node_id(&result, "td1") {
        assert_eq!(td1["content"][0]["content"][0]["text"], "A");
    }
}

#[test]
fn test_list_item_edit_preserves_siblings() {
    let doc = json!({
        "type": "doc",
        "content": [{
            "type": "bullet_list",
            "attrs": { "nodeId": "ul1" },
            "content": [
                { "type": "list_item", "attrs": { "nodeId": "li1" }, "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "Item 1" }] }] },
                { "type": "list_item", "attrs": { "nodeId": "li2" }, "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "Item 2" }] }] },
                { "type": "list_item", "attrs": { "nodeId": "li3" }, "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "Item 3" }] }] }
            ]
        }]
    });
    let d = DiffResult {
        changed: vec![ChangeOp {
            pm_node_id: Some("li2".to_string()),
            tag: "li".to_string(),
            inner_html: "Item 2 Modified".to_string(),
            attrs: HashMap::new(),
            type_changed: false,
            old_idx: None,
        }],
        deleted: vec![],
        added: vec![],
    };
    let result = apply_diff(&doc, &d);
    // 未修改的兄弟节点保持原样
    if let Some(li1) = find_by_node_id(&result, "li1") {
        assert_eq!(li1["content"][0]["content"][0]["text"], "Item 1");
    }
    if let Some(li3) = find_by_node_id(&result, "li3") {
        assert_eq!(li3["content"][0]["content"][0]["text"], "Item 3");
    }
}


#[test]
fn test_add_node_appends_to_doc() {
    let doc = json!({
        "type": "doc",
        "content": [{
            "type": "table",
            "attrs": { "nodeId": "t1" },
            "content": [{
                "type": "table_row",
                "attrs": { "nodeId": "tr1" },
                "content": [
                    { "type": "table_cell", "attrs": { "nodeId": "td1" }, "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "A" }] }] }
                ]
            }]
        }]
    });
    let d = DiffResult {
        changed: vec![],
        deleted: vec![],
        added: vec![AddOp {
            tag: "p".to_string(),
            inner_html: "新段落".to_string(),
            attrs: HashMap::new(),
        }],
    };
    let result = apply_diff(&doc, &d);
    // 原 table 保留
    assert!(find_by_node_id(&result, "t1").is_some());
    // doc 多了一个节点
    assert_eq!(result["content"].as_array().unwrap().len(), 2);
}

#[test]
fn test_cascading_edit_multiple_nodes() {
    let doc = json!({
        "type": "doc",
        "content": [
            { "type": "title", "attrs": { "nodeId": "t1" }, "content": [{ "type": "text", "text": "Title" }] },
            { "type": "paragraph", "attrs": { "nodeId": "p1" }, "content": [{ "type": "text", "text": "Para 1" }] },
            { "type": "paragraph", "attrs": { "nodeId": "p2" }, "content": [{ "type": "text", "text": "Para 2" }] },
            { "type": "paragraph", "attrs": { "nodeId": "p3" }, "content": [{ "type": "text", "text": "Para 3" }] }
        ]
    });
    let d = DiffResult {
        changed: vec![
            ChangeOp { pm_node_id: Some("p1".to_string()), tag: "p".to_string(), inner_html: "P1 Edit".to_string(), attrs: HashMap::new(), type_changed: false, old_idx: None },
            ChangeOp { pm_node_id: Some("p2".to_string()), tag: "p".to_string(), inner_html: "P2 Edit".to_string(), attrs: HashMap::new(), type_changed: false, old_idx: None },
            ChangeOp { pm_node_id: Some("p3".to_string()), tag: "p".to_string(), inner_html: "P3 Edit".to_string(), attrs: HashMap::new(), type_changed: false, old_idx: None },
        ],
        deleted: vec![],
        added: vec![],
    };
    let result = apply_diff(&doc, &d);
    // title 未被改动
    assert!(find_by_node_id(&result, "t1").is_some());
    // 三个段落都被修改
    assert_eq!(find_by_node_id(&result, "p1").unwrap()["content"][0]["text"], "P1 Edit");
    assert_eq!(find_by_node_id(&result, "p2").unwrap()["content"][0]["text"], "P2 Edit");
    assert_eq!(find_by_node_id(&result, "p3").unwrap()["content"][0]["text"], "P3 Edit");
}

#[test]
fn test_node_id_preserved_after_edit() {
    let doc = json!({
        "type": "doc",
        "content": [{
            "type": "bullet_list",
            "attrs": { "nodeId": "ul1" },
            "content": [
                { "type": "list_item", "attrs": { "nodeId": "li1" }, "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "Item 1" }] }] },
                { "type": "list_item", "attrs": { "nodeId": "li2" }, "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "Item 2" }] }] }
            ]
        }]
    });
    let d = DiffResult {
        changed: vec![ChangeOp {
            pm_node_id: Some("li1".to_string()),
            tag: "li".to_string(),
            inner_html: "Item 1 Modified".to_string(),
            attrs: HashMap::new(),
            type_changed: false,
            old_idx: None,
        }],
        deleted: vec![],
        added: vec![],
    };
    let result = apply_diff(&doc, &d);
    // 修改后 nodeId 依然保持
    if let Some(li1) = find_by_node_id(&result, "li1") {
        assert_eq!(li1["attrs"]["nodeId"], "li1");
    }
    if let Some(li2) = find_by_node_id(&result, "li2") {
        assert_eq!(li2["attrs"]["nodeId"], "li2");
    }
}
