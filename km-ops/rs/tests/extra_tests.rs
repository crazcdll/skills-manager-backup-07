use serde_json::json;
use km_ops::render::render;
use km_ops::diff::{diff, DiffResult, DeleteOp, AddOp};
use km_ops::patch::{apply_diff, find_by_node_id};
use std::collections::HashMap;

// ── diff 边缘 ──────────────────────────────────────────────────────────────

#[test]
fn test_diff_empty_to_single_p() {
    let d = diff("", "<p>hello</p>", &json!({"children":[]}));
    assert_eq!(d.added.len(), 1);
}

#[test]
fn test_diff_whitespace_stripped() {
    let d = diff("  <p>a</p>  ", "<p>a</p>", &json!({"children":[]}));
    assert_eq!(d.changed.len(), 0);
    assert_eq!(d.deleted.len(), 0);
}

#[test]
fn test_diff_identical_hr() {
    let d = diff("<hr/>", "<hr/>", &json!({"children":[]}));
    assert_eq!(d.changed.len(), 0);
}

#[test]
fn test_diff_img_to_drawio() {
    let d = diff("<img src=\"a.png\"/>", "<km-drawio src=\"a.svg\"/>", &json!({"children":[]}));
    assert!(d.changed.len() + d.deleted.len() + d.added.len() > 0);
}

#[test]
fn test_diff_heading_h2_to_h2_same() {
    let d = diff("<h2>标题</h2>", "<h2>标题</h2>", &json!({"children":[]}));
    assert_eq!(d.changed.len(), 0);
}

#[test]
fn test_diff_heading_h2_to_h3() {
    let d = diff("<h2>标题</h2>", "<h3>标题</h3>", &json!({"children":[]}));
    assert!(d.changed.len() + d.deleted.len() + d.added.len() > 0);
}

#[test]
fn test_diff_repeated_tags() {
    let d = diff("<p>a</p><p>b</p><p>c</p>", "<p>a</p><p>bb</p><p>c</p>", &json!({"children":[]}));
    assert!(d.changed.len() > 0 || (d.deleted.len() > 0 && d.added.len() > 0));
}

#[test]
fn test_diff_new_video_detected() {
    let d = diff("<p>a</p>", "<p>a</p>\n<km-video src=\"v.mp4\" name=\"d\"/>", &json!({"children":[]}));
    assert!(d.added.len() > 0);
}

#[test]
fn test_diff_attachment_detected() {
    let d = diff("<p>a</p>", "<p>a</p>\n<km-attachment name=\"f.pdf\" src=\"url\"/>", &json!({"children":[]}));
    assert!(d.added.len() > 0);
}

// ── patch 细节 ─────────────────────────────────────────────────────────────


#[test]
fn test_apply_diff_delete_and_add() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"keep1"}]},
        {"type":"paragraph","attrs":{"nodeId":"p2"},"content":[{"type":"text","text":"keep2"}]}
    ]});
    let d = DiffResult {
        changed: vec![],
        deleted: vec![DeleteOp { pm_node_id: Some("p2".into()), old_idx: None }],
        added: vec![AddOp { tag: "p".into(), inner_html: "new".into(), attrs: HashMap::new() }],
    };
    let patched = apply_diff(&doc, &d);
    let r1 = find_by_node_id(&patched, "p1");
    assert!(r1.is_some());
}


#[test]
fn test_find_by_node_id_deep_container() {
    let doc = json!({"type":"doc","content":[
        {"type":"note","attrs":{"nodeId":"n1","type":"info"},"content":[
            {"type":"note_content","attrs":{"nodeId":"nc"},"content":[
                {"type":"paragraph","attrs":{"nodeId":"np"},"content":[{"type":"text","text":"deep"}]}
            ]}
        ]}
    ]});
    assert!(find_by_node_id(&doc, "np").is_some());
    assert!(find_by_node_id(&doc, "n1").is_some());
}

// ── parse 边界 ─────────────────────────────────────────────────────────────

use km_ops::parse::parse_inline;

#[test]
fn test_parse_inline_plain_text() {
    let result = parse_inline("hello world");
    assert_eq!(result[0]["type"], "text");
    assert_eq!(result[0]["text"], "hello world");
}

#[test]
fn test_parse_inline_strong_tag() {
    let result = parse_inline("<strong>bold</strong>");
    assert_eq!(result[0]["marks"][0]["type"], "strong");
    assert_eq!(result[0]["text"], "bold");
}

#[test]
fn test_parse_inline_empty_string() {
    let result = parse_inline("");
    assert_eq!(result.len(), 0);
}

#[test]
fn test_parse_inline_self_closing_br() {
    let result = parse_inline("<br/>");
    assert_eq!(result.len(), 1);
    assert_eq!(result[0]["type"], "hard_break");
}

#[test]
fn test_parse_inline_multiple_tags() {
    let result = parse_inline("a<strong>b</strong>c");
    assert_eq!(result.len(), 3);
    assert_eq!(result[0]["text"], "a");
    assert_eq!(result[1]["text"], "b");
    assert_eq!(result[2]["text"], "c");
}

// ── container 细节 ─────────────────────────────────────────────────────────

fn list_doc() -> serde_json::Value {
    json!({
        "type": "doc",
        "content": [
            {"type":"title","attrs":{"nodeId":"t-1"},"content":[{"type":"text","text":"列表"}]},
            {"type":"bullet_list","attrs":{"nodeId":"ul-1"},"content":[
                {"type":"list_item","attrs":{"nodeId":"li-a"},"content":[{"type":"paragraph","content":[{"type":"text","text":"A"}]}]},
                {"type":"list_item","attrs":{"nodeId":"li-b"},"content":[{"type":"paragraph","content":[{"type":"text","text":"B"}]}]}
            ]}
        ]
    })
}

#[test]
fn test_container_list_render_has_ul() {
    let html = render(&list_doc()).html;
    assert!(html.contains("<ul>"));
    assert!(html.contains("<li>A</li>"));
    assert!(html.contains("<li>B</li>"));
}

#[test]
fn test_container_ol_render() {
    let doc = json!({
        "type":"doc","content":[
            {"type":"ordered_list","attrs":{"nodeId":"ol-1"},"content":[
                {"type":"list_item","attrs":{"nodeId":"li-1"},"content":[{"type":"paragraph","content":[{"type":"text","text":"第一"}]}]},
                {"type":"list_item","attrs":{"nodeId":"li-2"},"content":[{"type":"paragraph","content":[{"type":"text","text":"第二"}]}]}
            ]}
        ]
    });
    let html = render(&doc).html;
    assert!(html.contains("<ol>"));
    assert!(html.contains("<li>第一</li>"));
}

#[test]
fn test_container_task_list_render() {
    let doc = json!({
        "type":"doc","content":[
            {"type":"task_list","attrs":{"nodeId":"tlist"},"content":[
                {"type":"task_item","attrs":{"nodeId":"ti-1","checked":true},"content":[{"type":"paragraph","content":[{"type":"text","text":"已完成"}]}]},
                {"type":"task_item","attrs":{"nodeId":"ti-2","checked":false},"content":[{"type":"paragraph","content":[{"type":"text","text":"未完成"}]}]}
            ]}
        ]
    });
    let html = render(&doc).html;
    // task_list 输出带 class 以便 patch 区分 bullet_list
    assert!(html.contains("<ul class=\"task-list\">"), "task_list 应渲染为 <ul class=\"task-list\">");
    assert!(html.contains("checked"));
}

#[test]
fn test_container_delete_li_by_nodeid() {
    let doc = list_doc();
    let d = DiffResult {
        changed: vec![], added: vec![],
        deleted: vec![DeleteOp { pm_node_id: Some("li-a".into()), old_idx: None }],
    };
    let patched = apply_diff(&doc, &d);
    assert!(find_by_node_id(&patched, "li-a").is_none());
    assert!(find_by_node_id(&patched, "li-b").is_some());
}

#[test]
fn test_container_safety_edit_li_preserves_nodeids() {
    let doc = list_doc();
    let result = render(&doc);
    let new_html = result.html.replace("<li>A</li>", "<li>A修改</li>");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    assert!(find_by_node_id(&patched, "li-a").is_some());
    assert!(find_by_node_id(&patched, "li-b").is_some());
}

// ── 综合集成 roundtrip ─────────────────────────────────────────────────────

#[test]
fn test_deep_note_edit_roundtrip() {
    let doc = json!({
        "type":"doc","content":[
            {"type":"note","attrs":{"nodeId":"n1","type":"info"},"content":[
                {"type":"note_title","attrs":{"nodeId":"nt"},"content":[{"type":"text","text":"标题"}]},
                {"type":"note_content","attrs":{"nodeId":"nc"},"content":[
                    {"type":"paragraph","attrs":{"nodeId":"np"},"content":[{"type":"text","text":"内容"}]}
                ]}
            ]}
        ]
    });
    let result = render(&doc);
    let new_html = result.html.replace("内容", "新内容");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    let np = find_by_node_id(&patched, "np").unwrap();
    assert_eq!(np["content"][0]["text"], "新内容");
    assert!(find_by_node_id(&patched, "n1").is_some());
}

#[test]
fn test_table_cell_edit_roundtrip() {
    let doc = json!({
        "type":"doc","content":[
            {"type":"table","attrs":{"nodeId":"tbl"},"content":[
                {"type":"table_row","attrs":{"nodeId":"tr"},"content":[
                    {"type":"table_cell","attrs":{"nodeId":"td1"},"content":[{"type":"paragraph","content":[{"type":"text","text":"A"}]}]},
                    {"type":"table_cell","attrs":{"nodeId":"td2"},"content":[{"type":"paragraph","content":[{"type":"text","text":"B"}]}]}
                ]}
            ]}
        ]
    });
    let result = render(&doc);
    let new_html = result.html.replace("<p>A</p>", "<p>Z</p>");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    let td1 = find_by_node_id(&patched, "td1").unwrap();
    assert_eq!(td1["content"][0]["content"][0]["text"], "Z");
}

#[test]
fn test_h3_heading_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"heading","attrs":{"level":3,"nodeId":"h"},"content":[{"type":"text","text":"旧标题"}]}
    ]});
    let result = render(&doc);
    let new_html = result.html.replace("<h3>旧标题</h3>", "<h3>新标题</h3>");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    let h = find_by_node_id(&patched, "h").unwrap();
    assert_eq!(h["content"][0]["text"], "新标题");
}

#[test]
fn test_doc_title_edit_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"旧标题"}]},
        {"type":"paragraph","attrs":{"nodeId":"p"},"content":[{"type":"text","text":"正文"}]}
    ]});
    let result = render(&doc);
    let new_html = result.html.replace("<h1>旧标题</h1>", "<h1>新标题</h1>");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    let t = find_by_node_id(&patched, "t").unwrap();
    assert_eq!(t["content"][0]["text"], "新标题");
}

#[test]
fn test_rich_drawio_delete_detected() {
    let doc = json!({"type":"doc","content":[
        {"type":"drawio","attrs":{"nodeId":"dr","src":"url"}},
        {"type":"paragraph","attrs":{"nodeId":"p"},"content":[{"type":"text","text":"x"}]}
    ]});
    let result = render(&doc);
    let new_html = result.html.replace("<km-drawio src=\"url\"/>", "");
    let d = diff(&result.html, &new_html, &doc);
    assert!(d.deleted.len() > 0);
}

#[test]
fn test_blockquote_edit_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"blockquote","attrs":{"nodeId":"bq"},"content":[
            {"type":"paragraph","attrs":{"nodeId":"bp"},"content":[{"type":"text","text":"引用"}]}
        ]}
    ]});
    let result = render(&doc);
    let new_html = result.html.replace("引用", "新引用");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    let bp = find_by_node_id(&patched, "bp").unwrap();
    assert_eq!(bp["content"][0]["text"], "新引用");
}

#[test]
fn test_code_block_renders() {
    let doc = json!({"type":"doc","content":[
        {"type":"code_block","attrs":{"nodeId":"cb","language":"rust"},"content":[
            {"type":"text","text":"fn main() {}"}
        ]}
    ]});
    let result = render(&doc);
    assert!(result.html.contains("<pre"));
    assert!(result.html.contains("<code>fn main"));
    assert!(result.html.contains("language=\"rust\""));
}

#[test]
fn test_horizontal_rule_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"horizontal_rule","attrs":{"nodeId":"hr1"}},
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"after"}]}
    ]});
    let result = render(&doc);
    assert!(result.html.contains("<hr/>"));
    let d = diff(&result.html, &result.html, &doc);
    assert_eq!(d.changed.len(), 0);
}

#[test]
fn test_mixed_rich_nodes_doc() {
    let doc = json!({"type":"doc","content":[
        {"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"混搭文档"}]},
        {"type":"drawio","attrs":{"nodeId":"dr1","src":"https://cdn/a.svg"}},
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"段落"}]},
        {"type":"video","attrs":{"nodeId":"v1","src":"https://cdn/v.mp4","name":"demo"}}
    ]});
    let result = render(&doc);
    assert!(result.html.contains("km-drawio"));
    assert!(result.html.contains("km-video"));
    let d = diff(&result.html, &result.html, &doc);
    assert_eq!(d.changed.len(), 0);
}

#[test]
fn test_mixed_list_and_table() {
    let doc = json!({"type":"doc","content":[
        {"type":"heading","attrs":{"level":2,"nodeId":"h"},"content":[{"type":"text","text":"标题"}]},
        {"type":"bullet_list","attrs":{"nodeId":"ul"},"content":[
            {"type":"list_item","attrs":{"nodeId":"li1"},"content":[{"type":"paragraph","content":[{"type":"text","text":"项目"}]}]}
        ]},
        {"type":"table","attrs":{"nodeId":"tbl"},"content":[
            {"type":"table_row","attrs":{"nodeId":"tr"},"content":[
                {"type":"table_cell","attrs":{"nodeId":"td"},"content":[{"type":"paragraph","content":[{"type":"text","text":"单元格"}]}]}
            ]}
        ]}
    ]});
    let result = render(&doc);
    assert!(result.html.contains("<ul>"));
    assert!(result.html.contains("<table>"));
    let d = diff(&result.html, &result.html, &doc);
    assert_eq!(d.changed.len(), 0);
}

#[test]
fn test_attachment_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"attachment","attrs":{"nodeId":"att1","name":"file.pdf","src":"https://url/f.pdf","size":1024}}
    ]});
    let result = render(&doc);
    assert!(result.html.contains("km-attachment"));
    assert!(result.html.contains("file.pdf"));
}

#[test]
fn test_image_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"image","attrs":{"nodeId":"img1","src":"https://cdn/pic.png","name":"pic"}}
    ]});
    let result = render(&doc);
    assert!(result.html.contains("<img"));
    assert!(result.html.contains("pic.png"));
}

#[test]
fn test_xtable_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"xtable","attrs":{"nodeId":"xt","xtableId":"tbl-1"}}
    ]});
    let result = render(&doc);
    assert!(result.html.contains("km-xtable"));
}

#[test]
fn test_minder_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"minder","attrs":{"nodeId":"m1"}}
    ]});
    let result = render(&doc);
    assert!(result.html.contains("km-minder"));
}

// ── 额外边缘测试 ────────────────────────────────────────────────────────────

#[test]
fn test_empty_doc_render() {
    let doc = json!({"type":"doc","content":[]});
    let result = render(&doc);
    assert_eq!(result.html, "");
}

#[test]
fn test_paragraph_with_unicode() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p"},"content":[{"type":"text","text":"你好世界 🌍"}]}
    ]});
    assert!(render(&doc).html.contains("你好世界"));
}

#[test]
fn test_paragraph_with_entities() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p"},"content":[{"type":"text","text":"1 < 2 & 3 > 0"}]}
    ]});
    let html = render(&doc).html;
    assert!(html.contains("&lt;"));
}

#[test]
fn test_title_with_mark_combination() {
    let doc = json!({"type":"doc","content":[
        {"type":"title","attrs":{"nodeId":"t"},"content":[
            {"type":"text","text":"粗","marks":[{"type":"strong"}]},
            {"type":"text","text":"斜","marks":[{"type":"em"}]}
        ]}
    ]});
    let html = render(&doc).html;
    assert!(html.contains("<strong>"));
    assert!(html.contains("<em>"));
}

#[test]
fn test_list_three_levels_preserved() {
    let ul = json!({"type":"doc","content":[
        {"type":"bullet_list","attrs":{"nodeId":"ul"},"content":[
            {"type":"list_item","attrs":{"nodeId":"li1"},"content":[{"type":"paragraph","content":[{"type":"text","text":"第一层"}]}]},
            {"type":"list_item","attrs":{"nodeId":"li2"},"content":[{"type":"paragraph","content":[{"type":"text","text":"第二层"}]}]},
            {"type":"list_item","attrs":{"nodeId":"li3"},"content":[{"type":"paragraph","content":[{"type":"text","text":"第三层"}]}]}
        ]}
    ]});
    let result = render(&ul);
    assert!(result.html.contains("<li>第一层</li>"));
    assert!(result.html.contains("<li>第二层</li>"));
    assert!(result.html.contains("<li>第三层</li>"));
}

#[test]
fn test_table_with_colspan() {
    let doc = json!({"type":"doc","content":[
        {"type":"table","attrs":{"nodeId":"tbl"},"content":[
            {"type":"table_row","attrs":{"nodeId":"tr"},"content":[
                {"type":"table_cell","attrs":{"nodeId":"td","colspan":2},"content":[
                    {"type":"paragraph","content":[{"type":"text","text":"跨列"}]}
                ]}
            ]}
        ]}
    ]});
    assert!(render(&doc).html.contains("colspan=\"2\""));
}

#[test]
fn test_table_with_rowspan() {
    let doc = json!({"type":"doc","content":[
        {"type":"table","attrs":{"nodeId":"tbl"},"content":[
            {"type":"table_row","attrs":{"nodeId":"tr"},"content":[
                {"type":"table_cell","attrs":{"nodeId":"td","rowspan":3},"content":[
                    {"type":"paragraph","content":[{"type":"text","text":"跨行"}]}
                ]}
            ]}
        ]}
    ]});
    assert!(render(&doc).html.contains("rowspan=\"3\""));
}

#[test]
fn test_audio_with_src_and_name() {
    let doc = json!({"type":"doc","content":[
        {"type":"audio","attrs":{"nodeId":"a","url":"song.mp3","name":"bgm"}}
    ]});
    let html = render(&doc).html;
    assert!(html.contains("km-audio"));
    assert!(html.contains("song.mp3"));
    assert!(html.contains("bgm"));
}

#[test]
fn test_diff_title_content_change() {
    let old = "<h1>旧标题</h1>";
    let new = "<h1>新标题</h1>";
    let d = diff(old, new, &json!({"children":[]}));
    assert!(d.changed.len() > 0 || (d.deleted.len() > 0 && d.added.len() > 0));
}

#[test]
fn test_diff_delete_paragraph() {
    let old = "<p>keep</p><p>delete</p>";
    let new = "<p>keep</p>";
    let d = diff(old, new, &json!({"children":[]}));
    assert!(d.deleted.len() > 0 || d.changed.len() > 0);
}

#[test]
fn test_diff_insert_paragraph() {
    let old = "<p>a</p>";
    let new = "<p>a</p><p>b</p>";
    let d = diff(old, new, &json!({"children":[]}));
    assert!(d.added.len() > 0);
}

#[test]
fn test_mention_inline() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p"},"content":[
            {"type":"mention","attrs":{"uid":"user123","name":"张三"}}
        ]}
    ]});
    let html = render(&doc).html;
    assert!(html.contains("km-mention"));
    assert!(html.contains("user123"));
    assert!(html.contains("张三"));
}

#[test]
fn test_link_inline() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p"},"content":[
            {"type":"link","attrs":{"href":"https://example.com"},"content":[{"type":"text","text":"点击"}]}
        ]}
    ]});
    let html = render(&doc).html;
    assert!(html.contains("<a href=\"https://example.com\">"));
    assert!(html.contains("点击"));
}

#[test]
fn test_inline_block_video_in_paragraph() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p"},"content":[
            {"type":"text","text":"前"},
            {"type":"video","attrs":{"src":"v.mp4","name":"demo"}},
            {"type":"text","text":"后"}
        ]}
    ]});
    let html = render(&doc).html;
    assert!(html.contains("km-video"));
    assert!(html.contains("前"));
    assert!(html.contains("后"));
}

#[test]
fn test_build_pm_node_h1_h2_h3() {
    assert!(km_ops::patch::build_pm_node("h1", &HashMap::new(), "标题").unwrap()["type"] == "title");
    assert!(km_ops::patch::build_pm_node("h2", &HashMap::new(), "标题").unwrap()["type"] == "heading");
    assert!(km_ops::patch::build_pm_node("h3", &HashMap::new(), "标题").unwrap()["attrs"]["level"] == 3);
}

#[test]
fn test_render_pm_node_ids_match_docs() {
    let doc = json!({"type":"doc","content":[
        {"type":"title","attrs":{"nodeId":"id1"},"content":[{"type":"text","text":"x"}]},
        {"type":"paragraph","attrs":{"nodeId":"id2"},"content":[{"type":"text","text":"y"}]},
        {"type":"drawio","attrs":{"nodeId":"id3","src":"s.svg"}}
    ]});
    let ids = render(&doc).pm_node_ids;
    assert_eq!(ids[0], Some("id1".into()));
    assert_eq!(ids[1], Some("id2".into()));
    assert_eq!(ids[2], Some("id3".into()));
}

#[test]
fn test_diff_km_attachment_roundtrip() {
    let old = "<km-attachment name=\"a.pdf\" src=\"url1\"/>";
    let new = "<km-attachment name=\"b.pdf\" src=\"url2\"/>";
    let d = diff(old, new, &json!({"children":[]}));
    assert!(d.changed.len() + d.deleted.len() + d.added.len() > 0);
}

#[test]
fn test_render_plantuml() {
    let doc = json!({"type":"doc","content":[
        {"type":"plantuml","attrs":{"nodeId":"pu"}}
    ]});
    assert!(render(&doc).html.contains("km-plantuml"));
}

#[test]
fn test_render_empty_title() {
    let doc = json!({"type":"doc","content":[
        {"type":"title","attrs":{"nodeId":"t"},"content":[]}
    ]});
    assert!(render(&doc).html.contains("<h1>"));
}

#[test]
fn test_diff_self_closing_rich_tags() {
    let old = r#"<km-drawio src="a.svg"/>"#;
    let new = r#"<km-drawio src="b.svg"/>"#;
    let d = diff(old, new, &json!({"children":[]}));
    assert!(d.changed.len() + d.deleted.len() + d.added.len() > 0);
}

#[test]
fn test_apply_diff_idempotent_no_ops() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p"},"content":[{"type":"text","text":"x"}]}
    ]});
    let d = DiffResult { changed: vec![], deleted: vec![], added: vec![] };
    let patched = apply_diff(&doc, &d);
    assert_eq!(patched, doc);
}

// ── 补充边界 roundtrip ─────────────────────────────────────────────────────────

#[test]
fn test_top_level_insert_paragraph_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"第一段"}]}
    ]});
    let result = render(&doc);
    let new_html = format!("{}<p>新段落</p>", result.html);
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    assert!(find_by_node_id(&patched, "p1").is_some());
    let content = patched["content"].as_array().unwrap();
    assert_eq!(content.len(), 2);
    assert_eq!(content[1]["content"][0]["text"], "新段落");
}

#[test]
fn test_top_level_delete_paragraph_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"保留"}]},
        {"type":"paragraph","attrs":{"nodeId":"p2"},"content":[{"type":"text","text":"删除"}]}
    ]});
    let result = render(&doc);
    let new_html = result.html.replace("<p>删除</p>", "");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    assert!(find_by_node_id(&patched, "p1").is_some());
    assert!(find_by_node_id(&patched, "p2").is_none());
}

#[test]
fn test_type_change_paragraph_to_heading_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"升级标题"}]}
    ]});
    let result = render(&doc);
    let new_html = result.html.replace("<p>升级标题</p>", "<h2>升级标题</h2>");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    let content = patched["content"].as_array().unwrap();
    assert_eq!(content[0]["type"], "heading");
    assert_eq!(content[0]["attrs"]["level"], 2);
}

#[test]
fn test_code_block_edit_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"code_block","attrs":{"nodeId":"cb","language":"rust"},"content":[
            {"type":"text","text":"fn main() {}"}
        ]}
    ]});
    let result = render(&doc);
    let new_html = result.html.replace("fn main() {}", "fn main() { println!(\"hello\"); }");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    let cb = find_by_node_id(&patched, "cb").unwrap();
    assert_eq!(cb["content"][0]["text"], "fn main() { println!(\"hello\"); }");
}

#[test]
fn test_list_item_insert_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"bullet_list","attrs":{"nodeId":"ul"},"content":[
            {"type":"list_item","attrs":{"nodeId":"li1"},"content":[
                {"type":"paragraph","content":[{"type":"text","text":"项目一"}]}
            ]}
        ]}
    ]});
    let result = render(&doc);
    let new_html = result.html.replace("<li>项目一</li>", "<li>项目一</li><li>项目二</li>");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    let ul = find_by_node_id(&patched, "ul").unwrap();
    assert_eq!(ul["content"].as_array().unwrap().len(), 2);
}

#[test]
fn test_multiple_nodes_changed_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"旧文本一"}]},
        {"type":"paragraph","attrs":{"nodeId":"p2"},"content":[{"type":"text","text":"旧文本二"}]},
        {"type":"paragraph","attrs":{"nodeId":"p3"},"content":[{"type":"text","text":"不变"}]}
    ]});
    let result = render(&doc);
    let new_html = result.html
        .replace("<p>旧文本一</p>", "<p>新文本一</p>")
        .replace("<p>旧文本二</p>", "<p>新文本二</p>");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    assert_eq!(find_by_node_id(&patched, "p1").unwrap()["content"][0]["text"], "新文本一");
    assert_eq!(find_by_node_id(&patched, "p2").unwrap()["content"][0]["text"], "新文本二");
    assert_eq!(find_by_node_id(&patched, "p3").unwrap()["content"][0]["text"], "不变");
}

#[test]
fn test_inline_mark_add_roundtrip() {
    let doc = json!({"type":"doc","content":[
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[
            {"type":"text","text":"普通文字"}
        ]}
    ]});
    let result = render(&doc);
    let new_html = result.html.replace("<p>普通文字</p>", "<p><strong>普通文字</strong></p>");
    let d = diff(&result.html, &new_html, &doc);
    let patched = apply_diff(&doc, &d);
    let p1 = find_by_node_id(&patched, "p1").unwrap();
    assert_eq!(p1["content"][0]["marks"][0]["type"], "strong");
    assert_eq!(p1["content"][0]["text"], "普通文字");
}
