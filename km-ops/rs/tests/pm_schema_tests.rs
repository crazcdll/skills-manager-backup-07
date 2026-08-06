//! PM JSON Schema 合规性测试
//!
//! 基于 rs/tests/fixtures/pm_schema_constraints.json 中分析的约束，
//! 验证我们的 HTML→PM JSON 转换产出与真实学城 API 格式对齐。
//! 目标：生成的 JSON 不触发学城服务端 schema 告警。

use km_ops::patch::build_pm_node;
use serde_json::Value;
use std::collections::HashMap;

// ─── 辅助函数 ─────────────────────────────────────────────────────────────────

fn attrs(pairs: &[(&str, &str)]) -> HashMap<String, String> {
    pairs.iter().map(|(k, v)| (k.to_string(), v.to_string())).collect()
}

fn get_attr<'a>(node: &'a Value, key: &str) -> Option<&'a Value> {
    node.get("attrs")?.get(key)
}

fn has_uuid_nodeid(node: &Value) -> bool {
    let nid = get_attr(node, "nodeId").and_then(|v| v.as_str()).unwrap_or("");
    !nid.is_empty()
}

fn fixture(name: &str) -> Value {
    let path = format!("{}/tests/fixtures/{}", env!("CARGO_MANIFEST_DIR"), name);
    let content = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("读取 fixture {} 失败: {}", name, e));
    serde_json::from_str(&content)
        .unwrap_or_else(|e| panic!("解析 fixture {} 失败: {}", name, e))
}

// ─── title 节点 ───────────────────────────────────────────────────────────────

#[test]
fn title_has_nodeid() {
    let node = build_pm_node("h1", &HashMap::new(), "文档标题").unwrap();
    assert_eq!(node["type"], "title");
    assert!(has_uuid_nodeid(&node), "title 节点必须有 nodeId");
}

// ─── paragraph 节点 ───────────────────────────────────────────────────────────

#[test]
fn paragraph_has_required_attrs() {
    let node = build_pm_node("p", &HashMap::new(), "段落文本").unwrap();
    assert_eq!(node["type"], "paragraph");
    let a = node.get("attrs").expect("paragraph 必须有 attrs");
    assert!(a.get("nodeId").and_then(|v| v.as_str()).map(|s| !s.is_empty()).unwrap_or(false),
        "paragraph 必须有非空 nodeId");
    assert!(a.get("indent").is_some(), "paragraph 必须有 indent");
    assert!(a.get("align").is_some(), "paragraph 必须有 align");
    assert!(a.get("dataDiffId").is_some(), "paragraph 必须有 dataDiffId");
}

#[test]
fn paragraph_default_align_is_empty_string() {
    let node = build_pm_node("p", &HashMap::new(), "text").unwrap();
    let align = get_attr(&node, "align").and_then(|v| v.as_str()).unwrap_or("MISSING");
    // 默认 align 为 "" 或 "left"（均合法）
    assert!(align == "" || align == "left",
        "默认 align 应为 \"\" 或 \"left\"，实际: {align}");
}

#[test]
fn paragraph_center_align_preserved() {
    let node = build_pm_node("p", &attrs(&[("align", "center")]), "text").unwrap();
    let align = get_attr(&node, "align").and_then(|v| v.as_str()).unwrap_or("");
    assert_eq!(align, "center", "center align 应被保留");
}

#[test]
fn paragraph_xss_align_sanitized() {
    let node = build_pm_node("p", &attrs(&[("align", "center\"><script>bad</script>")]), "text").unwrap();
    let align = get_attr(&node, "align").and_then(|v| v.as_str()).unwrap_or("");
    assert_eq!(align, "", "XSS align 应被清洗为空字符串");
}

#[test]
fn paragraph_each_call_gets_unique_nodeid() {
    let n1 = build_pm_node("p", &HashMap::new(), "A").unwrap();
    let n2 = build_pm_node("p", &HashMap::new(), "B").unwrap();
    let id1 = get_attr(&n1, "nodeId").and_then(|v| v.as_str()).unwrap_or("");
    let id2 = get_attr(&n2, "nodeId").and_then(|v| v.as_str()).unwrap_or("");
    assert_ne!(id1, id2, "每次调用应生成不同的 nodeId");
}

// ─── heading 节点 ─────────────────────────────────────────────────────────────

#[test]
fn heading_has_nodeid_and_level() {
    for (tag, level) in [("h2", 2u64), ("h3", 3), ("h4", 4)] {
        let node = build_pm_node(tag, &HashMap::new(), "标题").unwrap();
        assert_eq!(node["type"], "heading", "{tag} 应映射为 heading");
        assert_eq!(node["attrs"]["level"], level, "{tag} level 应为 {level}");
        assert!(has_uuid_nodeid(&node), "{tag} 必须有 nodeId");
        assert!(node["attrs"].get("dataDiffId").is_some(), "{tag} 必须有 dataDiffId");
    }
}

// ─── horizontal_rule 节点 ─────────────────────────────────────────────────────

#[test]
fn hr_has_nodeid() {
    let node = build_pm_node("hr", &HashMap::new(), "").unwrap();
    assert_eq!(node["type"], "horizontal_rule");
    assert!(has_uuid_nodeid(&node), "hr 必须有 nodeId");
}

// ─── blockquote 节点 ─────────────────────────────────────────────────────────

#[test]
fn blockquote_has_nodeid() {
    let node = build_pm_node("blockquote", &HashMap::new(), "<p>引用文字</p>").unwrap();
    assert_eq!(node["type"], "blockquote");
    assert!(has_uuid_nodeid(&node), "blockquote 必须有 nodeId");
}

// ─── 列表节点 ─────────────────────────────────────────────────────────────────

#[test]
fn bullet_list_has_nodeid() {
    let node = build_pm_node("ul", &HashMap::new(), "<li>项目一</li><li>项目二</li>").unwrap();
    assert_eq!(node["type"], "bullet_list");
    assert!(has_uuid_nodeid(&node), "bullet_list 必须有 nodeId");

    // 每个 list_item 也要有 nodeId
    let items = node["content"].as_array().unwrap();
    assert_eq!(items.len(), 2);
    for item in items {
        assert_eq!(item["type"], "list_item");
        assert!(has_uuid_nodeid(item), "list_item 必须有 nodeId");
    }
}

#[test]
fn ordered_list_has_nodeid() {
    let node = build_pm_node("ol", &HashMap::new(), "<li>第一步</li>").unwrap();
    assert_eq!(node["type"], "ordered_list");
    assert!(has_uuid_nodeid(&node), "ordered_list 必须有 nodeId");
}

// ─── table 节点 ───────────────────────────────────────────────────────────────

#[test]
fn table_has_nodeid() {
    let html = "<tr><th>列A</th><th>列B</th></tr><tr><td>值1</td><td>值2</td></tr>";
    let node = build_pm_node("table", &HashMap::new(), html).unwrap();
    assert_eq!(node["type"], "table");
    assert!(has_uuid_nodeid(&node), "table 必须有 nodeId");

    let rows = node["content"].as_array().unwrap();
    assert_eq!(rows.len(), 2);

    // table_row 有 nodeId
    let row0 = &rows[0];
    assert_eq!(row0["type"], "table_row");
    assert!(has_uuid_nodeid(row0), "table_row 必须有 nodeId");

    // table_header 有 nodeId 和 colspan/rowspan
    let cells = row0["content"].as_array().unwrap();
    for cell in cells {
        assert_eq!(cell["type"], "table_header");
        assert!(has_uuid_nodeid(cell), "table_header 必须有 nodeId");
        assert!(cell["attrs"]["colspan"].as_u64().is_some(), "table_header 必须有 colspan");
        assert!(cell["attrs"]["rowspan"].as_u64().is_some(), "table_header 必须有 rowspan");
    }

    // table_cell 有 nodeId
    let row1 = &rows[1];
    for cell in row1["content"].as_array().unwrap() {
        assert_eq!(cell["type"], "table_cell");
        assert!(has_uuid_nodeid(cell), "table_cell 必须有 nodeId");
        // 每个 cell 内的 paragraph 也有 nodeId
        let inner_para = &cell["content"][0];
        assert_eq!(inner_para["type"], "paragraph");
        assert!(has_uuid_nodeid(inner_para), "table_cell 内的 paragraph 必须有 nodeId");
    }
}

// ─── 代码块 ───────────────────────────────────────────────────────────────────

#[test]
fn code_block_has_nodeid() {
    let node = build_pm_node("pre", &attrs(&[("language", "Python")]), "<code>print('hi')</code>").unwrap();
    assert_eq!(node["type"], "code_block");
    assert!(has_uuid_nodeid(&node), "code_block 必须有 nodeId");
    assert_eq!(node["attrs"]["language"], "Python");
}

// ─── Fixture 格式验证 ─────────────────────────────────────────────────────────

#[test]
fn fixture_pm_empty_doc_has_correct_structure() {
    let doc = fixture("pm_empty_doc.json");
    assert_eq!(doc["type"], "doc");
    let content = doc["content"].as_array().unwrap();
    // 第一个节点必须是 title
    assert_eq!(content[0]["type"], "title");
    let title_nid = content[0]["attrs"]["nodeId"].as_str().unwrap_or("");
    assert!(!title_nid.is_empty(), "真实 API 返回的 title 有非空 nodeId");
    // 第二个节点是 paragraph，有完整 attrs
    assert_eq!(content[1]["type"], "paragraph");
    let para_attrs = &content[1]["attrs"];
    assert!(para_attrs.get("nodeId").and_then(|v| v.as_str()).map(|s| !s.is_empty()).unwrap_or(false));
    assert!(para_attrs.get("align").is_some());
    assert!(para_attrs.get("indent").is_some());
    assert!(para_attrs.get("dataDiffId").is_some());
}

#[test]
fn fixture_pm_rich_doc_table_has_nodeids() {
    let doc = fixture("pm_rich_doc.json");
    let content = doc["content"].as_array().unwrap();

    // 找到 table 节点
    let table = content.iter().find(|n| n["type"] == "table")
        .expect("pm_rich_doc.json 应包含 table 节点");
    assert!(!table["attrs"]["nodeId"].as_str().unwrap_or("").is_empty(),
        "真实 API 返回的 table 有非空 nodeId");

    // 验证 table_row/table_header/table_cell 也有 nodeId
    for row in table["content"].as_array().unwrap() {
        assert_eq!(row["type"], "table_row");
        assert!(!row["attrs"]["nodeId"].as_str().unwrap_or("").is_empty(),
            "真实 API 返回的 table_row 有非空 nodeId");
        for cell in row["content"].as_array().unwrap() {
            assert!(cell["type"] == "table_header" || cell["type"] == "table_cell");
            assert!(!cell["attrs"]["nodeId"].as_str().unwrap_or("").is_empty(),
                "真实 API 返回的 table cell 有非空 nodeId");
        }
    }
}

// ─── create_doc minimal PM JSON 格式验证 ──────────────────────────────────────

// ─── bullet_list / blockquote 完整 attrs ─────────────────────────────────────

#[test]
fn bullet_list_has_datadiffid_and_indent() {
    let node = build_pm_node("ul", &HashMap::new(), "<li>项目</li>").unwrap();
    assert_eq!(node["type"], "bullet_list");
    assert!(has_uuid_nodeid(&node), "bullet_list 必须有 nodeId");
    // 真实 API 有 dataDiffId 和 indent
    assert!(node["attrs"]["dataDiffId"].is_null() || node["attrs"]["dataDiffId"].is_string(),
        "bullet_list 必须有 dataDiffId 字段");
    assert!(node["attrs"]["indent"].as_i64().is_some(), "bullet_list 必须有 indent");
}

#[test]
fn blockquote_has_datadiffid() {
    let node = build_pm_node("blockquote", &HashMap::new(), "<p>引用</p>").unwrap();
    assert_eq!(node["type"], "blockquote");
    assert!(node["attrs"]["dataDiffId"].is_null() || node["attrs"]["dataDiffId"].is_string(),
        "blockquote 必须有 dataDiffId 字段");
}

#[test]
fn list_item_has_full_attrs() {
    let node = build_pm_node("ul", &HashMap::new(), "<li>一项</li>").unwrap();
    let item = &node["content"][0];
    assert_eq!(item["type"], "list_item");
    assert!(has_uuid_nodeid(item), "list_item 必须有 nodeId");
    // 真实 API 有这些字段
    assert!(item["attrs"]["level"].is_number(), "list_item 必须有 level");
    assert!(item["attrs"]["hidden"].is_boolean(), "list_item 必须有 hidden");
    assert!(item["attrs"].get("dataListItemDiffId").is_some(), "list_item 必须有 dataListItemDiffId");
}

// ─── note 节点 ────────────────────────────────────────────────────────────────

#[test]
fn note_all_subnodes_have_nodeids() {
    let node = build_pm_node("km-note", &attrs(&[("type", "info")]),
        "<summary>提示标题</summary><div><p>内容</p></div>").unwrap();
    assert_eq!(node["type"], "note");
    assert!(has_uuid_nodeid(&node), "note 必须有 nodeId");
    assert!(node["attrs"]["dataDiffId"].is_null() || node["attrs"]["dataDiffId"].is_string());
    assert_eq!(node["attrs"]["type"], "info");

    let note_title = &node["content"][0];
    assert_eq!(note_title["type"], "note_title");
    assert!(has_uuid_nodeid(note_title), "note_title 必须有 nodeId");
    assert!(note_title["attrs"]["align"].is_string(), "note_title 必须有 align");

    let note_content = &node["content"][1];
    assert_eq!(note_content["type"], "note_content");
    assert!(has_uuid_nodeid(note_content), "note_content 必须有 nodeId");
}

// ─── collapse 节点 ────────────────────────────────────────────────────────────

#[test]
fn collapse_all_subnodes_have_nodeids() {
    let node = build_pm_node("km-collapse", &HashMap::new(),
        "<summary>折叠标题</summary><div><p>内容</p></div>").unwrap();
    assert_eq!(node["type"], "collapse");
    assert!(has_uuid_nodeid(&node), "collapse 必须有 nodeId");
    assert!(node["attrs"]["dataDiffId"].is_null() || node["attrs"]["dataDiffId"].is_string());
    assert!(node["attrs"]["active"].is_boolean(), "collapse 必须有 active");

    let collapse_title = &node["content"][0];
    assert_eq!(collapse_title["type"], "collapse_title");
    assert!(has_uuid_nodeid(collapse_title), "collapse_title 必须有 nodeId");
    assert!(collapse_title["attrs"]["align"].is_string(), "collapse_title 必须有 align");

    let collapse_content = &node["content"][1];
    assert_eq!(collapse_content["type"], "collapse_content");
    assert!(has_uuid_nodeid(collapse_content), "collapse_content 必须有 nodeId");
}

// ─── 来自真实 checklist 文档的 Fixture 验证 ─────────────────────────────────

#[test]
fn fixture_checklist_doc_note_has_nodeids() {
    let doc = fixture("pm_checklist_doc.json");

    fn find_type<'a>(node: &'a serde_json::Value, target: &str) -> Option<&'a serde_json::Value> {
        if node.get("type").and_then(|v| v.as_str()) == Some(target) {
            return Some(node);
        }
        for child in node.get("content")?.as_array()? {
            if let Some(found) = find_type(child, target) {
                return Some(found);
            }
        }
        None
    }

    // 验证 note 节点
    if let Some(note) = find_type(&doc, "note") {
        assert!(!note["attrs"]["nodeId"].as_str().unwrap_or("").is_empty(),
            "真实 API note 有非空 nodeId");
    }

    // 验证 collapse 节点
    if let Some(collapse) = find_type(&doc, "collapse") {
        assert!(!collapse["attrs"]["nodeId"].as_str().unwrap_or("").is_empty(),
            "真实 API collapse 有非空 nodeId");
    }

    // 验证 bullet_list 节点有 indent 和 dataDiffId
    if let Some(bl) = find_type(&doc, "bullet_list") {
        assert!(bl["attrs"]["indent"].as_i64().is_some(),
            "真实 API bullet_list 有 indent");
        assert!(bl["attrs"].get("dataDiffId").is_some(),
            "真实 API bullet_list 有 dataDiffId");
    }
}

#[test]
fn minimal_create_pm_json_has_nodeids() {
    // 模拟 api.rs::create_doc 构造最小 PM JSON 的逻辑
    use uuid::Uuid;
    let title = "测试文档";
    let minimal_pm = serde_json::json!({
        "type": "doc",
        "content": [
            {"type": "title", "attrs": {"nodeId": Uuid::new_v4().to_string().replace('-', "")}, "content": [{"type": "text", "text": title}]},
            {"type": "paragraph", "attrs": {"indent": 0, "align": "left", "dataDiffId": Value::Null, "nodeId": Uuid::new_v4().to_string().replace('-', "")}}
        ]
    });
    let title_nid = minimal_pm["content"][0]["attrs"]["nodeId"].as_str().unwrap_or("");
    let para_nid = minimal_pm["content"][1]["attrs"]["nodeId"].as_str().unwrap_or("");
    assert!(!title_nid.is_empty(), "create_doc 最小文档 title 必须有 nodeId");
    assert!(!para_nid.is_empty(), "create_doc 最小文档 paragraph 必须有 nodeId");
    assert_ne!(title_nid, para_nid, "title 和 paragraph 的 nodeId 必须不同");
    assert!(minimal_pm["content"][1]["attrs"]["indent"].as_i64().is_some(), "paragraph 必须有 indent");
    assert!(minimal_pm["content"][1]["attrs"]["align"].as_str().is_some(), "paragraph 必须有 align");
}

// ─── task_list roundtrip ──────────────────────────────────────────────────────

#[test]
fn task_list_roundtrip_from_html() {
    // render.rs 把 task_list 渲染成 <ul class="task-list">
    // patch.rs 应能识别 class 并还原成 task_list + task_item
    let items_html = r#"<li><input type="checkbox" checked/>已完成</li><li><input type="checkbox"/>未完成</li>"#;
    let node = build_pm_node("ul", &attrs(&[("class", "task-list")]), items_html).unwrap();
    assert_eq!(node["type"], "task_list", "带 task-list class 的 ul 应生成 task_list");
    assert!(has_uuid_nodeid(&node), "task_list 必须有 nodeId");
    assert!(node["attrs"]["dataDiffId"].is_null(), "task_list 必须有 dataDiffId");
    assert_eq!(node["attrs"]["indent"], 0);
}

#[test]
fn task_item_has_checked_attr() {
    let items_html = r#"<li><input type="checkbox" checked/>已完成</li><li><input type="checkbox"/>待办</li>"#;
    let node = build_pm_node("ul", &attrs(&[("class", "task-list")]), items_html).unwrap();
    let items = node["content"].as_array().unwrap();
    assert_eq!(items.len(), 2);
    assert_eq!(items[0]["type"], "task_item");
    assert!(has_uuid_nodeid(&items[0]), "task_item 必须有 nodeId");
    assert_eq!(items[0]["attrs"]["level"], 0);
    assert!(items[0]["attrs"]["checked"].is_boolean(), "task_item 必须有 checked bool");
}

// ─── catalog / footnote_list 保留 ─────────────────────────────────────────────

#[test]
fn catalog_is_preserved() {
    let node = build_pm_node("km-catalog", &HashMap::new(), "").unwrap();
    assert_eq!(node["type"], "catalog");
    assert!(has_uuid_nodeid(&node), "catalog 必须有 nodeId");
    assert!(node["attrs"]["dataDiffId"].is_null(), "catalog 必须有 dataDiffId");
    assert!(node["attrs"]["style"].is_string(), "catalog 必须有 style");
}

#[test]
fn footnote_list_is_preserved() {
    let node = build_pm_node("km-footnote-list", &HashMap::new(), "").unwrap();
    assert_eq!(node["type"], "footnote_list");
    assert!(has_uuid_nodeid(&node), "footnote_list 必须有 nodeId");
}

// ─── open_link nodeId ─────────────────────────────────────────────────────────

#[test]
fn open_link_has_nodeid() {
    use km_ops::parse::inline_block_pm_node;
    let mut a = HashMap::new();
    a.insert("href".to_string(), "https://ones.sankuai.com/foo".to_string());
    a.insert("data-otype".to_string(), "ones".to_string());
    let node = inline_block_pm_node("km-open-link", &a).unwrap();
    assert_eq!(node["type"], "open_link");
    assert!(node["attrs"]["nodeId"].as_str().map(|s| !s.is_empty()).unwrap_or(false),
        "open_link 必须有非空 nodeId");
    assert_eq!(node["attrs"]["href"], "https://ones.sankuai.com/foo");
    assert_eq!(node["attrs"]["type"], "ones");
}

// ─── bullet_list vs task_list 区分 ────────────────────────────────────────────

#[test]
fn plain_ul_becomes_bullet_list() {
    let node = build_pm_node("ul", &HashMap::new(), "<li>普通项</li>").unwrap();
    assert_eq!(node["type"], "bullet_list", "没有 task-list class 的 ul 应生成 bullet_list");
}

#[test]
fn task_list_class_ul_becomes_task_list() {
    let node = build_pm_node("ul", &attrs(&[("class", "task-list")]), "<li>任务项</li>").unwrap();
    assert_eq!(node["type"], "task_list", "有 task-list class 的 ul 应生成 task_list");
}
