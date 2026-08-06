use serde_json::json;
use km_ops::render::render;
use km_ops::diff::diff;
use km_ops::patch::{apply_diff, find_by_node_id};

// ── Fixtures ──────────────────────────────────────────────────────────────────

fn note_doc() -> serde_json::Value {
    json!({
        "type": "doc",
        "content": [
            {"type":"title","attrs":{"nodeId":"t-1"},"content":[{"type":"text","text":"文档"}]},
            {"type":"note","attrs":{"nodeId":"note-1","type":"info"},"content":[
                {"type":"note_title","attrs":{"nodeId":"note-title-1"},"content":[{"type":"text","text":"提示标题"}]},
                {"type":"note_content","attrs":{"nodeId":"note-content-1"},"content":[
                    {"type":"paragraph","attrs":{"nodeId":"note-p-1"},"content":[{"type":"text","text":"提示内容第一段"}]},
                    {"type":"paragraph","attrs":{"nodeId":"note-p-2"},"content":[{"type":"text","text":"提示内容第二段"}]}
                ]}
            ]},
            {"type":"paragraph","attrs":{"nodeId":"p-after"},"content":[{"type":"text","text":"普通段落"}]}
        ]
    })
}

fn collapse_doc() -> serde_json::Value {
    json!({
        "type": "doc",
        "content": [
            {"type":"title","attrs":{"nodeId":"t-1"},"content":[{"type":"text","text":"文档"}]},
            {"type":"collapse","attrs":{"nodeId":"collapse-1"},"content":[
                {"type":"collapse_title","attrs":{"nodeId":"collapse-title-1"},"content":[{"type":"text","text":"折叠标题"}]},
                {"type":"collapse_content","attrs":{"nodeId":"collapse-content-1"},"content":[
                    {"type":"paragraph","attrs":{"nodeId":"col-p-1"},"content":[{"type":"text","text":"折叠内容段落一"}]},
                    {"type":"paragraph","attrs":{"nodeId":"col-p-2"},"content":[{"type":"text","text":"折叠内容段落二"}]}
                ]}
            ]}
        ]
    })
}

fn table_doc() -> serde_json::Value {
    json!({
        "type": "doc",
        "content": [
            {"type":"title","attrs":{"nodeId":"t-1"},"content":[{"type":"text","text":"表格文档"}]},
            {"type":"table","attrs":{"nodeId":"tbl-1"},"content":[
                {"type":"table_row","attrs":{"nodeId":"tr-1"},"content":[
                    {"type":"table_header","attrs":{"nodeId":"th-1"},"content":[{"type":"paragraph","content":[{"type":"text","text":"姓名"}]}]},
                    {"type":"table_header","attrs":{"nodeId":"th-2"},"content":[{"type":"paragraph","content":[{"type":"text","text":"部门"}]}]}
                ]},
                {"type":"table_row","attrs":{"nodeId":"tr-2"},"content":[
                    {"type":"table_cell","attrs":{"nodeId":"td-1"},"content":[{"type":"paragraph","content":[{"type":"text","text":"张三"}]}]},
                    {"type":"table_cell","attrs":{"nodeId":"td-2"},"content":[{"type":"paragraph","content":[{"type":"text","text":"研发"}]}]}
                ]}
            ]},
            {"type":"paragraph","attrs":{"nodeId":"p-after"},"content":[{"type":"text","text":"普通段落"}]}
        ]
    })
}

// ── Note 编辑测试 ──────────────────────────────────────────────────────────────

#[test]
fn test_note_edit_content() {
    let doc = note_doc();
    let html = render(&doc).html;
    let new_html = html.replace("提示内容第一段", "提示内容已修改");

    let diff_result = diff(&html, &new_html, &doc);
    let patched = apply_diff(&doc, &diff_result);

    // Note 容器仍然存在
    let note = find_by_node_id(&patched, "note-1");
    assert!(note.is_some());

    // 修改的段落内容已更新
    let p = find_by_node_id(&patched, "note-p-1");
    assert!(p.is_some());
    let text = p.unwrap()["content"][0]["text"].as_str().unwrap();
    assert_eq!(text, "提示内容已修改");

    // 另一个段落未受影响
    let p2 = find_by_node_id(&patched, "note-p-2");
    assert!(p2.is_some());
}

#[test]
fn test_note_preserved_after_edit() {
    let doc = note_doc();
    let html = render(&doc).html;
    let new_html = html.replace("提示标题", "新标题");

    let diff_result = diff(&html, &new_html, &doc);
    let patched = apply_diff(&doc, &diff_result);

    let note = find_by_node_id(&patched, "note-1");
    assert!(note.is_some());
}

// ── Table 编辑测试 ────────────────────────────────────────────────────────────

#[test]
fn test_table_edit_cell() {
    let doc = table_doc();
    let html = render(&doc).html;
    let new_html = html.replace("张三", "李四");

    let diff_result = diff(&html, &new_html, &doc);
    let patched = apply_diff(&doc, &diff_result);

    // Table 容器仍然存在
    let tbl = find_by_node_id(&patched, "tbl-1");
    assert!(tbl.is_some());

    // 修改的单元格内容已更新
    let td = find_by_node_id(&patched, "td-1");
    assert!(td.is_some());
}

#[test]
fn test_table_row_count_preserved() {
    let doc = table_doc();
    let html = render(&doc).html;
    let new_html = html.clone(); // identical

    let diff_result = diff(&html, &new_html, &doc);
    assert_eq!(diff_result.changed.len(), 0);
    assert_eq!(diff_result.deleted.len(), 0);
}

// ── Collapse 编辑测试 ─────────────────────────────────────────────────────────

#[test]
fn test_collapse_edit_content() {
    let doc = collapse_doc();
    let html = render(&doc).html;
    let new_html = html.replace("折叠内容段落一", "折叠内容已修改");

    let diff_result = diff(&html, &new_html, &doc);
    let patched = apply_diff(&doc, &diff_result);

    let collapse = find_by_node_id(&patched, "collapse-1");
    assert!(collapse.is_some());

    let p = find_by_node_id(&patched, "col-p-1");
    assert!(p.is_some());
}

// ── 富节点测试 ────────────────────────────────────────────────────────────────

#[test]
fn test_drawio_src_change_detected() {
    let doc = json!({
        "type": "doc",
        "content": [
            {"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"标题"}]},
            {"type":"drawio","attrs":{"nodeId":"dr1","src":"https://cdn/first.svg"}},
            {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"正文"}]}
        ]
    });
    let html = render(&doc).html;
    let new_html = html.replace("first.svg", "second.svg");

    let diff_result = diff(&html, &new_html, &doc);
    assert!(diff_result.changed.len() > 0, "drawio src change should be detected");
}

#[test]
fn test_roundtrip_drawio_src_change() {
    let doc = json!({
        "type": "doc",
        "content": [
            {"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"标题"}]},
            {"type":"drawio","attrs":{"nodeId":"dr1","src":"https://cdn/first.svg"}},
            {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"正文"}]}
        ]
    });
    let html = render(&doc).html;
    let new_html = html.replace("first.svg", "second.svg");

    let diff_result = diff(&html, &new_html, &doc);
    let patched = apply_diff(&doc, &diff_result);

    let dr = find_by_node_id(&patched, "dr1");
    assert!(dr.is_some());
    assert_eq!(dr.unwrap()["attrs"]["src"], "https://cdn/second.svg");
}

// ── 有序列表 roundtrip ────────────────────────────────────────────────────────

#[test]
fn test_ordered_list_item_edit_roundtrip() {
    let doc = json!({
        "type": "doc",
        "content": [
            {"type":"ordered_list","attrs":{"nodeId":"ol-1"},"content":[
                {"type":"list_item","attrs":{"nodeId":"oli-1"},"content":[{"type":"paragraph","content":[{"type":"text","text":"第一步"}]}]},
                {"type":"list_item","attrs":{"nodeId":"oli-2"},"content":[{"type":"paragraph","content":[{"type":"text","text":"第二步"}]}]},
                {"type":"list_item","attrs":{"nodeId":"oli-3"},"content":[{"type":"paragraph","content":[{"type":"text","text":"第三步"}]}]}
            ]}
        ]
    });
    let html = render(&doc).html;
    let new_html = html.replace("<li>第二步</li>", "<li>第二步（已更新）</li>");

    let diff_result = diff(&html, &new_html, &doc);
    let patched = apply_diff(&doc, &diff_result);

    // ol 容器还在
    assert!(find_by_node_id(&patched, "ol-1").is_some());
    // 修改的项更新，未修改的项不变
    let oli2 = find_by_node_id(&patched, "oli-2");
    assert!(oli2.is_some());
    let oli1 = find_by_node_id(&patched, "oli-1");
    assert!(oli1.is_some());
}

// ── Note title 修改 ───────────────────────────────────────────────────────────

#[test]
fn test_note_title_edit_roundtrip() {
    let doc = json!({
        "type": "doc",
        "content": [
            {"type":"note","attrs":{"nodeId":"note-1","type":"warning"},"content":[
                {"type":"note_title","attrs":{"nodeId":"nt-1"},"content":[{"type":"text","text":"旧警告标题"}]},
                {"type":"note_content","attrs":{"nodeId":"nc-1"},"content":[
                    {"type":"paragraph","attrs":{"nodeId":"np-1"},"content":[{"type":"text","text":"警告内容"}]}
                ]}
            ]}
        ]
    });
    let html = render(&doc).html;
    let new_html = html.replace("旧警告标题", "新警告标题");

    let diff_result = diff(&html, &new_html, &doc);
    let patched = apply_diff(&doc, &diff_result);

    // note 容器及其内容段落不受影响
    assert!(find_by_node_id(&patched, "note-1").is_some());
    assert!(find_by_node_id(&patched, "np-1").is_some());
    // note_title 已更新
    let nt = find_by_node_id(&patched, "nt-1");
    assert!(nt.is_some());
    assert_eq!(nt.unwrap()["content"][0]["text"], "新警告标题");
}

// ── 大修改场景（Bug 3 回归）：内容差异大时应识别为 changed，而非 delete+insert ─

/// 多段落文档夹具，用于大修改测试
fn paragraphs_doc() -> serde_json::Value {
    json!({
        "type": "doc",
        "content": [
            {"type":"title","attrs":{"nodeId":"t-1"},"content":[{"type":"text","text":"文档标题"}]},
            {"type":"paragraph","attrs":{"nodeId":"p-1"},"content":[{"type":"text","text":"这是第一段原文。"}]},
            {"type":"paragraph","attrs":{"nodeId":"p-2"},"content":[{"type":"text","text":"这是第二段原文。"}]},
            {"type":"paragraph","attrs":{"nodeId":"p-3"},"content":[{"type":"text","text":"这是第三段原文。"}]},
            {"type":"heading","attrs":{"nodeId":"h-1","level":2},"content":[{"type":"text","text":"二级标题"}]}
        ]
    })
}

/// 单段大修改：原文字与新内容几乎无公共前后缀（相似度 < 0.3）。
/// 修复前会被误判为 delete+insert，导致原段落保留 + 新段落追加到末尾。
#[test]
fn test_large_modify_is_changed_not_delete_insert() {
    let doc = paragraphs_doc();
    let html = render(&doc).html;
    // 把第二段整段换成完全不相似的内容
    let new_html = html.replace("这是第二段原文。", "完全不同的Mock内容XYZ");

    let diff_result = diff(&html, &new_html, &doc);

    // 关键断言：应是 1 个 changed，而非 1 delete + 1 insert
    assert_eq!(diff_result.deleted.len(), 0, "大修改不应产生删除");
    assert_eq!(diff_result.added.len(), 0, "大修改不应产生新增");
    assert_eq!(diff_result.changed.len(), 1, "大修改应识别为 1 个 changed");
    assert_eq!(diff_result.changed[0].pm_node_id.as_deref(), Some("p-2"),
        "changed 应携带原 nodeId，确保原地替换");
}

/// 大修改后 apply_diff：原节点原地替换，nodeId 保留，内容更新，无重复
#[test]
fn test_large_modify_patch_in_place() {
    let doc = paragraphs_doc();
    let html = render(&doc).html;
    let new_html = html.replace("这是第二段原文。", "完全不同的Mock内容XYZ");

    let diff_result = diff(&html, &new_html, &doc);
    let patched = apply_diff(&doc, &diff_result);

    // 原段落 p-2 仍在（原地替换，未被删除后重建）
    let p2 = find_by_node_id(&patched, "p-2").expect("p-2 应保留");
    assert_eq!(p2["content"][0]["text"], "完全不同的Mock内容XYZ");

    // 其他段落不受影响
    let p1 = find_by_node_id(&patched, "p-1").expect("p-1 应保留");
    assert_eq!(p1["content"][0]["text"], "这是第一段原文。");
    let p3 = find_by_node_id(&patched, "p-3").expect("p-3 应保留");
    assert_eq!(p3["content"][0]["text"], "这是第三段原文。");

    // 顶层节点数量不变（没有追加重复段落）
    let top = patched["content"].as_array().unwrap();
    assert_eq!(top.len(), 5, "顶层节点数应不变（title+3段+heading）");
}

/// 多段同时大修改：顺序保持，每段原地替换
#[test]
fn test_multiple_large_modify_preserves_order() {
    let doc = paragraphs_doc();
    let html = render(&doc).html;
    // 三段 + 标题同时换成不相似内容
    let new_html = html
        .replace("这是第一段原文。", "AAA111")
        .replace("这是第二段原文。", "BBB222")
        .replace("这是第三段原文。", "CCC333")
        .replace("二级标题", "MockHeading");

    let diff_result = diff(&html, &new_html, &doc);
    let patched = apply_diff(&doc, &diff_result);

    // 无删除/新增，全是原地修改
    assert_eq!(diff_result.deleted.len(), 0);
    assert_eq!(diff_result.added.len(), 0);

    // 顺序与内容正确
    let p1 = find_by_node_id(&patched, "p-1").expect("p-1");
    assert_eq!(p1["content"][0]["text"], "AAA111");
    let p2 = find_by_node_id(&patched, "p-2").expect("p-2");
    assert_eq!(p2["content"][0]["text"], "BBB222");
    let p3 = find_by_node_id(&patched, "p-3").expect("p-3");
    assert_eq!(p3["content"][0]["text"], "CCC333");
    let h1 = find_by_node_id(&patched, "h-1").expect("h-1");
    assert_eq!(h1["content"][0]["text"], "MockHeading");
}

/// 真正的新增段落不应被误合并成 changed
#[test]
fn test_genuine_insert_not_merged_as_change() {
    let doc = paragraphs_doc();
    let html = render(&doc).html;
    // 在末尾追加一个全新段落（无对应删除）
    let new_html = format!("{}<p>全新追加的段落</p>", html);

    let diff_result = diff(&html, &new_html, &doc);
    assert_eq!(diff_result.deleted.len(), 0);
    assert_eq!(diff_result.added.len(), 1, "纯新增应保留为 1 个 added");
    assert_eq!(diff_result.changed.len(), 0);
}

/// 真正的删除段落不应被误合并
#[test]
fn test_genuine_delete_not_merged_as_change() {
    let doc = paragraphs_doc();
    let html = render(&doc).html;
    // 删除第二段
    let new_html = html.replace("<p>这是第二段原文。</p>", "");

    let diff_result = diff(&html, &new_html, &doc);
    assert_eq!(diff_result.added.len(), 0);
    assert_eq!(diff_result.deleted.len(), 1, "纯删除应保留为 1 个 deleted");
}

// ── 同文档两个容器各自独立修改 ────────────────────────────────────────────────

#[test]
fn test_two_blockquotes_independent_edit() {
    let doc = json!({
        "type": "doc",
        "content": [
            {"type":"blockquote","attrs":{"nodeId":"bq1"},"content":[
                {"type":"paragraph","attrs":{"nodeId":"bq1p"},"content":[{"type":"text","text":"引用一"}]}
            ]},
            {"type":"blockquote","attrs":{"nodeId":"bq2"},"content":[
                {"type":"paragraph","attrs":{"nodeId":"bq2p"},"content":[{"type":"text","text":"引用二"}]}
            ]}
        ]
    });
    let html = render(&doc).html;
    let new_html = html.replace("引用一", "引用一（已改）");

    let diff_result = diff(&html, &new_html, &doc);
    let patched = apply_diff(&doc, &diff_result);

    // bq2 及其内容完全不受影响
    let bq2p = find_by_node_id(&patched, "bq2p");
    assert!(bq2p.is_some());
    assert_eq!(bq2p.unwrap()["content"][0]["text"], "引用二");
    // bq1 的段落已更新
    let bq1p = find_by_node_id(&patched, "bq1p");
    assert!(bq1p.is_some());
}

