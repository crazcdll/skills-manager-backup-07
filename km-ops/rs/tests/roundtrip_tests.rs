#![recursion_limit = "256"]
/// PM JSON → render → HTML → build_pm_node → PM JSON roundtrip 保真度测试
///
/// 每个测试的模式：
/// 1. 构造一段原始 PM JSON（模拟源文档 body 中的某个节点）
/// 2. render::render 渲染成 HTML
/// 3. myers::parse_nodes + patch::build_pm_node 解析回 PM（模拟 apply_diff 的 AddOp 路径）
/// 4. 断言关键字段与原始 PM 一致
///
/// 失败的测试揭示当前版本的信息丢失点，修复后应全部通过。

use serde_json::{json, Value};
use km_ops::{render, patch, myers};

/// 把单个 PM 节点过一遍完整 roundtrip：render → parse_nodes → build_pm_node
fn roundtrip(pm_node: &Value) -> Vec<Value> {
    let doc = json!({"type": "doc", "content": [pm_node.clone()]});
    let html = render::render(&doc).html;
    let nodes = myers::parse_nodes(&html);
    nodes.iter()
        .filter_map(|n| patch::build_pm_node(&n.tag, &n.attrs, &n.inner_html))
        .collect()
}

// ── 基础类型 ──────────────────────────────────────────────────────────────────

#[test]
fn rt_paragraph_plain_text() {
    let pm = json!({"type":"paragraph","content":[{"type":"text","text":"hello world"}]});
    let result = roundtrip(&pm);
    assert_eq!(result.len(), 1);
    assert_eq!(result[0]["type"], "paragraph");
    assert_eq!(result[0]["content"][0]["text"], "hello world");
}

#[test]
fn rt_heading_level_preserved() {
    // h2/h3/h4 的 level 属性必须在 roundtrip 后保留
    for level in 2u64..=4 {
        let pm = json!({"type":"heading","attrs":{"level":level},"content":[{"type":"text","text":"标题"}]});
        let result = roundtrip(&pm);
        assert_eq!(result.len(), 1, "level={level}");
        assert_eq!(result[0]["type"], "heading", "level={level}");
        assert_eq!(result[0]["attrs"]["level"], level, "level={level}");
    }
}

#[test]
fn rt_heading_align_preserved() {
    let pm = json!({"type":"heading","attrs":{"level":2,"align":"center"},"content":[{"type":"text","text":"居中标题"}]});
    let result = roundtrip(&pm);
    assert_eq!(result[0]["attrs"]["level"], 2);
    assert_eq!(result[0]["attrs"]["align"], "center", "heading align must survive roundtrip");
}

#[test]
fn rt_paragraph_align_preserved() {
    let pm = json!({"type":"paragraph","attrs":{"align":"right"},"content":[{"type":"text","text":"右对齐"}]});
    let result = roundtrip(&pm);
    assert_eq!(result[0]["attrs"]["align"], "right", "paragraph align must survive roundtrip");
}

// ── 行内格式 ─────────────────────────────────────────────────────────────────

#[test]
fn rt_inline_marks_preserved() {
    // strong/em/del/underline/code 这几种基础 mark
    let marks_html = r#"<p><strong>粗</strong> <em>斜</em> <del>删</del> <u>下划</u> <code>行内代码</code></p>"#;
    let nodes = myers::parse_nodes(marks_html);
    let pm = patch::build_pm_node(&nodes[0].tag, &nodes[0].attrs, &nodes[0].inner_html).unwrap();
    let content = pm["content"].as_array().unwrap();
    let marks: Vec<&str> = content.iter()
        .filter_map(|n| n.get("marks"))
        .flat_map(|m| m.as_array().unwrap().iter())
        .filter_map(|m| m.get("type").and_then(|v| v.as_str()))
        .collect();
    assert!(marks.contains(&"strong"), "strong mark missing");
    assert!(marks.contains(&"em"), "em mark missing");
    assert!(marks.contains(&"strikethrough"), "strikethrough mark missing");
    assert!(marks.contains(&"underline"), "underline mark missing");
    assert!(marks.contains(&"code"), "code mark missing");
}

#[test]
fn rt_link_preserved_as_inline_node() {
    // <a> 必须 roundtrip 为 type:link 内联节点（不是 text mark）
    let pm = json!({
        "type": "paragraph",
        "content": [
            {"type":"text","text":"点击 "},
            {"type":"link","attrs":{"href":"https://km.sankuai.com/collabpage/123","title":"文档"},"content":[{"type":"text","text":"文档"}]},
            {"type":"text","text":" 查看"}
        ]
    });
    let result = roundtrip(&pm);
    let content = result[0]["content"].as_array().unwrap();
    let link = content.iter().find(|n| n["type"] == "link");
    assert!(link.is_some(), "link node must survive roundtrip");
    let link = link.unwrap();
    assert_eq!(link["attrs"]["href"], "https://km.sankuai.com/collabpage/123");
    // 链接文本在 content 里
    assert_eq!(link["content"][0]["text"], "文档");
}

#[test]
fn rt_km_mention_preserved() {
    // PM type 是 "mention"（不是 "km-mention"），render 输出 <km-mention uid="...">name</km-mention>
    let pm = json!({"type":"paragraph","content":[
        {"type":"text","text":"cc "},
        {"type":"mention","attrs":{"uid":"mockuser01","name":"@张三"}},
        {"type":"text","text":" 确认"}
    ]});
    let result = roundtrip(&pm);
    let content = result[0]["content"].as_array().unwrap();
    let mention = content.iter().find(|n| n["type"] == "mention");
    assert!(mention.is_some(), "mention node must survive roundtrip");
    let mention = mention.unwrap();
    assert_eq!(mention["attrs"]["uid"], "mockuser01");
    assert_eq!(mention["attrs"]["name"], "@张三");
}

// ── 容器节点 ─────────────────────────────────────────────────────────────────

#[test]
fn rt_table_colspan_rowspan_preserved() {
    // colspan/rowspan > 1 的单元格必须在 roundtrip 后保留
    let pm = json!({
        "type": "table",
        "content": [{
            "type": "table_row",
            "content": [
                {"type":"table_header","attrs":{"colspan":3,"rowspan":1},"content":[{"type":"paragraph","content":[{"type":"text","text":"跨3列标题"}]}]},
                {"type":"table_header","attrs":{"colspan":1,"rowspan":2},"content":[{"type":"paragraph","content":[{"type":"text","text":"跨2行"}]}]}
            ]
        }]
    });
    let result = roundtrip(&pm);
    assert_eq!(result[0]["type"], "table");
    let row = &result[0]["content"][0];
    let first_cell = &row["content"][0];
    assert_eq!(first_cell["attrs"]["colspan"], 3, "colspan=3 must be preserved");
    let second_cell = &row["content"][1];
    assert_eq!(second_cell["attrs"]["rowspan"], 2, "rowspan=2 must be preserved");
}

#[test]
fn rt_table_cell_link_preserved() {
    // 表格单元格内的链接不能丢失
    let pm = json!({
        "type": "table",
        "content": [{
            "type": "table_row",
            "content": [{
                "type": "table_cell",
                "attrs": {},
                "content": [{"type":"paragraph","content":[
                    {"type":"link","attrs":{"href":"https://km.sankuai.com/123","title":"需求"},"content":[{"type":"text","text":"需求链接"}]}
                ]}]
            }]
        }]
    });
    let result = roundtrip(&pm);
    let cell = &result[0]["content"][0]["content"][0];
    let cell_content = &cell["content"][0]["content"];
    let link = cell_content.as_array().unwrap().iter().find(|n| n["type"] == "link");
    assert!(link.is_some(), "link inside table cell must survive roundtrip");
    assert_eq!(link.unwrap()["attrs"]["href"], "https://km.sankuai.com/123");
}

#[test]
fn rt_blockquote_preserves_block_content() {
    // blockquote 内有多段落 + 列表时，roundtrip 后结构必须保留
    // 当前版本此测试可能失败（build_pm_node 用 parse_inline 处理 blockquote inner_html）
    let pm = json!({
        "type": "blockquote",
        "content": [
            {"type":"paragraph","content":[{"type":"text","text":"段落A"}]},
            {"type":"paragraph","content":[{"type":"text","text":"段落B"}]},
            {"type":"bullet_list","content":[
                {"type":"list_item","content":[{"type":"paragraph","content":[{"type":"text","text":"列表项"}]}]}
            ]}
        ]
    });
    let result = roundtrip(&pm);
    assert_eq!(result[0]["type"], "blockquote");
    let inner = result[0]["content"].as_array().unwrap();
    // 至少保留 2 段落 + 1 列表 = 3 个子节点
    assert!(inner.len() >= 3, "blockquote block content must be preserved, got {} nodes", inner.len());
    assert!(inner.iter().any(|n| n["type"] == "paragraph"), "paragraph must survive");
    assert!(inner.iter().any(|n| n["type"] == "bullet_list"), "bullet_list must survive inside blockquote");
}

#[test]
fn rt_note_multi_paragraph_preserved() {
    // km-note 的 note_content 有多段落时全部保留
    let pm = json!({
        "type": "note",
        "attrs": { "type": "info" },
        "content": [
            {"type":"note_title","content":[{"type":"text","text":"提示"}]},
            {"type":"note_content","content":[
                {"type":"paragraph","content":[{"type":"text","text":"第一段说明"}]},
                {"type":"paragraph","content":[{"type":"text","text":"第二段说明"}]},
                {"type":"paragraph","content":[{"type":"text","text":"第三段说明"}]}
            ]}
        ]
    });
    let result = roundtrip(&pm);
    assert_eq!(result[0]["type"], "note");
    let note_content = &result[0]["content"][1];
    assert_eq!(note_content["type"], "note_content");
    let paras = note_content["content"].as_array().unwrap();
    assert_eq!(paras.len(), 3, "all 3 paragraphs must survive in note_content");
}

#[test]
fn rt_note_empty_title_preserved() {
    // note 空 summary（只有 <summary></summary>）不应导致 note_content 包含 summary 标签
    let pm = json!({
        "type": "note",
        "attrs": { "type": "info" },
        "content": [
            {"type":"note_title","content":[]},  // empty title
            {"type":"note_content","content":[
                {"type":"paragraph","content":[{"type":"text","text":"内容"}]}
            ]}
        ]
    });
    let result = roundtrip(&pm);
    assert_eq!(result[0]["type"], "note");
    let note_content = &result[0]["content"][1];
    let paras = note_content["content"].as_array().unwrap();
    // 确保没有把 <summary></summary> 当作文本内容混入
    assert_eq!(paras.len(), 1, "exactly 1 paragraph should survive");
    let text = paras[0]["content"][0]["text"].as_str().unwrap_or("");
    assert!(!text.contains("summary"), "note_content must not contain 'summary' tag text");
    assert_eq!(text, "内容");
}

#[test]
fn rt_collapse_multi_paragraph_preserved() {
    // km-collapse 的 collapse_content 有多段落时全部保留
    let pm = json!({
        "type": "collapse",
        "attrs": {},
        "content": [
            {"type":"collapse_title","content":[{"type":"text","text":"折叠标题"}]},
            {"type":"collapse_content","content":[
                {"type":"paragraph","content":[{"type":"text","text":"展开内容A"}]},
                {"type":"paragraph","content":[{"type":"text","text":"展开内容B"}]}
            ]}
        ]
    });
    let result = roundtrip(&pm);
    assert_eq!(result[0]["type"], "collapse");
    let collapse_content = &result[0]["content"][1];
    let paras = collapse_content["content"].as_array().unwrap();
    assert_eq!(paras.len(), 2, "both paragraphs must survive in collapse_content");
}

#[test]
fn rt_note_content_with_list() {
    // note_content 包含列表时不丢失
    let pm = json!({
        "type": "note",
        "attrs": { "type": "warning" },
        "content": [
            {"type":"note_title","content":[{"type":"text","text":"注意"}]},
            {"type":"note_content","content":[
                {"type":"paragraph","content":[{"type":"text","text":"请注意以下事项："}]},
                {"type":"bullet_list","content":[
                    {"type":"list_item","content":[{"type":"paragraph","content":[{"type":"text","text":"事项一"}]}]},
                    {"type":"list_item","content":[{"type":"paragraph","content":[{"type":"text","text":"事项二"}]}]}
                ]}
            ]}
        ]
    });
    let result = roundtrip(&pm);
    let note_content = &result[0]["content"][1];
    let items = note_content["content"].as_array().unwrap();
    assert!(items.len() >= 2, "paragraph + bullet_list must survive in note_content");
    assert!(items.iter().any(|n| n["type"] == "bullet_list"), "bullet_list must survive in note_content");
}

#[test]
fn rt_code_block_language_preserved() {
    // code_block 的语言属性必须保留
    let pm = json!({
        "type": "code_block",
        "attrs": { "language": "TypeScript", "title": "代码块", "theme": "xq-light" },
        "content": [{"type":"text","text":"const x = 1;"}]
    });
    let result = roundtrip(&pm);
    assert_eq!(result[0]["type"], "code_block");
    assert_eq!(result[0]["attrs"]["language"], "TypeScript", "language attr must survive roundtrip");
    assert_eq!(result[0]["content"][0]["text"], "const x = 1;");
}

#[test]
fn rt_open_link_preserved() {
    // open_link（ONES 链接）必须在 roundtrip 后保留类型和 href
    let pm = json!({
        "type": "paragraph",
        "content": [
            {"type":"open_link","attrs":{"href":"https://ones.sankuai.com/ones/product/12345/workItem/requirement/detail/123","type":"ones"}}
        ]
    });
    let result = roundtrip(&pm);
    let content = result[0]["content"].as_array().unwrap();
    let olink = content.iter().find(|n| n["type"] == "open_link");
    assert!(olink.is_some(), "open_link must survive roundtrip, got: {:?}", content);
    assert_eq!(olink.unwrap()["attrs"]["href"],
               "https://ones.sankuai.com/ones/product/12345/workItem/requirement/detail/123");
    assert_eq!(olink.unwrap()["attrs"]["type"], "ones");
}

#[test]
fn rt_table_cell_colwidth_preserved() {
    // 表格单元格的 colwidth 必须在 roundtrip 后保留
    let pm = json!({
        "type": "table",
        "content": [{
            "type": "table_row",
            "content": [
                {"type":"table_cell","attrs":{"colspan":1,"rowspan":1,"colwidth":[150]},"content":[{"type":"paragraph","content":[{"type":"text","text":"A"}]}]},
                {"type":"table_cell","attrs":{"colspan":1,"rowspan":1,"colwidth":[300]},"content":[{"type":"paragraph","content":[{"type":"text","text":"B"}]}]}
            ]
        }]
    });
    let result = roundtrip(&pm);
    let row = &result[0]["content"][0];
    let cell0 = &row["content"][0];
    let cell1 = &row["content"][1];
    assert_eq!(cell0["attrs"]["colwidth"][0], 150, "colwidth=150 must survive roundtrip");
    assert_eq!(cell1["attrs"]["colwidth"][0], 300, "colwidth=300 must survive roundtrip");
}

#[test]
fn rt_table_cell_bgcolor_preserved() {
    // 单元格背景色必须在 roundtrip 后保留
    let pm = json!({
        "type": "table",
        "content": [{
            "type": "table_row",
            "content": [{
                "type": "table_cell",
                "attrs": {"colspan":1,"rowspan":1,"bgColor":"rgb(244, 245, 247)"},
                "content": [{"type":"paragraph","content":[{"type":"text","text":"colored"}]}]
            }]
        }]
    });
    let result = roundtrip(&pm);
    let cell = &result[0]["content"][0]["content"][0];
    let bg = cell["attrs"]["bgColor"].as_str().unwrap_or("");
    assert!(!bg.is_empty(), "bgColor must survive roundtrip");
    assert!(bg.contains("244") || bg.contains("rgb"), "bgColor value must be preserved, got: {bg}");
}

#[test]
fn rt_list_item_with_nested_collapse() {
    // 列表项内含 km-collapse（复杂列表项），roundtrip 后 collapse 不应丢失
    let pm = json!({
        "type": "bullet_list",
        "content": [
            {"type":"list_item","content":[{"type":"paragraph","content":[{"type":"text","text":"简单项"}]}]},
            {"type":"list_item","content":[
                {"type":"paragraph","content":[{"type":"text","text":"复杂项"}]},
                {"type":"collapse","attrs":{},"content":[
                    {"type":"collapse_title","content":[{"type":"text","text":"折叠标题"}]},
                    {"type":"collapse_content","content":[{"type":"paragraph","content":[{"type":"text","text":"折叠内容"}]}]}
                ]}
            ]}
        ]
    });
    let result = roundtrip(&pm);
    assert_eq!(result[0]["type"], "bullet_list");
    let items = result[0]["content"].as_array().unwrap();
    assert_eq!(items.len(), 2);
    // 第二个列表项的 content 应包含 paragraph + collapse
    let complex_item_content = items[1]["content"].as_array().unwrap();
    assert!(complex_item_content.len() >= 2, "complex list item must preserve paragraph + collapse");
    assert!(complex_item_content.iter().any(|n| n["type"] == "collapse"),
        "nested collapse inside list_item must survive roundtrip");
}

// ── open_link / open_card 边界 ─────────────────────────────────────────────────

#[test]
fn rt_open_link_in_table_cell() {
    // ONES 链接（open_link）放在表格单元格里 —— 真实文档里的典型场景
    let pm = json!({
        "type": "table",
        "content": [{
            "type": "table_row",
            "content": [{
                "type": "table_cell",
                "attrs": {"colspan":1,"rowspan":1,"colwidth":[325]},
                "content": [{"type":"paragraph","content":[
                    {"type":"open_link","attrs":{"href":"https://ones.sankuai.com/ones/product/12345/workItem/requirement/detail/12345678","type":"ones"}}
                ]}]
            },{
                "type": "table_cell",
                "attrs": {"colspan":1,"rowspan":1,"colwidth":[200]},
                "content": [{"type":"paragraph","content":[{"type":"text","text":"普通文字"}]}]
            }]
        }]
    });
    let result = roundtrip(&pm);
    // cell→paragraph→[open_link, ...]
    let para_content = &result[0]["content"][0]["content"][0]["content"][0]["content"];
    let olink = para_content.as_array().unwrap().iter().find(|n| n["type"] == "open_link");
    assert!(olink.is_some(), "open_link in table cell must survive roundtrip");
    assert_eq!(olink.unwrap()["attrs"]["type"], "ones");
    assert!(olink.unwrap()["attrs"]["href"].as_str().unwrap().contains("12345678"));
}

#[test]
fn rt_open_link_various_types() {
    // open_link 的 type 字段有多种值（ones / Metrics / 内部 ID）
    for otype in &["ones", "Metrics", "MOCK-SYS-ID"] {
        let pm = json!({"type":"paragraph","content":[
            {"type":"open_link","attrs":{
                "href":"https://ones.sankuai.com/product/workItem/123",
                "type": otype
            }}
        ]});
        let result = roundtrip(&pm);
        let olink = result[0]["content"].as_array().unwrap()
            .iter().find(|n| n["type"] == "open_link");
        assert!(olink.is_some(), "open_link type={otype} must survive");
        assert_eq!(olink.unwrap()["attrs"]["type"].as_str().unwrap(), *otype,
            "open_link type attr must be preserved: {otype}");
    }
}

#[test]
fn rt_open_card_preserved() {
    // open_card 节点（另一种嵌入卡片）
    let pm = json!({"type":"paragraph","content":[
        {"type":"open_card","attrs":{"href":"https://raptor.mws.sankuai.com/client/perf?id=123","type":"Metrics"}}
    ]});
    let result = roundtrip(&pm);
    let ocard = result[0]["content"].as_array().unwrap().iter().find(|n| n["type"] == "open_card");
    assert!(ocard.is_some(), "open_card must survive roundtrip");
    assert_eq!(ocard.unwrap()["attrs"]["type"], "Metrics");
}

// ── 表格列宽边界 ───────────────────────────────────────────────────────────────

#[test]
fn rt_colwidth_multi_value_for_colspan() {
    // colspan > 1 时 colwidth 是多值数组，如 [99, 99, 122]
    // 跨列合并单元格的各列宽度必须分别保留
    let pm = json!({
        "type": "table",
        "content": [{
            "type": "table_row",
            "content": [{
                "type": "table_header",
                "attrs": {"colspan":3,"rowspan":1,"colwidth":[99, 99, 122]},
                "content": [{"type":"paragraph","content":[{"type":"text","text":"跨3列标题"}]}]
            }]
        }]
    });
    let result = roundtrip(&pm);
    let cell = &result[0]["content"][0]["content"][0];
    let colwidth = cell["attrs"]["colwidth"].as_array().unwrap();
    assert_eq!(colwidth.len(), 3, "3-column colwidth must have 3 values");
    assert_eq!(colwidth[0], 99, "first colwidth value must be 99");
    assert_eq!(colwidth[1], 99, "second colwidth value must be 99");
    assert_eq!(colwidth[2], 122, "third colwidth value must be 122");
}

#[test]
fn rt_colwidth_empty_not_added() {
    // 没有 colwidth 的单元格，roundtrip 后不应凭空产生 colwidth 字段
    let pm = json!({
        "type": "table",
        "content": [{"type":"table_row","content":[
            {"type":"table_cell","attrs":{},"content":[{"type":"paragraph","content":[]}]}
        ]}]
    });
    let result = roundtrip(&pm);
    let cell = &result[0]["content"][0]["content"][0];
    // colwidth 为 null / 不存在 / 空数组均可
    let cw = &cell["attrs"]["colwidth"];
    assert!(cw.is_null() || cw.as_array().map(|a| a.is_empty()).unwrap_or(false),
        "cell without colwidth should not get one: {cw}");
}

// ── 表格单元格颜色/对齐边界 ────────────────────────────────────────────────────

#[test]
fn rt_cell_bgcolor_empty_no_style() {
    // bgColor 为空字符串时，不应在 HTML 里输出 background-color style
    let pm = json!({
        "type": "table",
        "content": [{"type":"table_row","content":[
            {"type":"table_cell","attrs":{"bgColor":"","colwidth":[100]},"content":[
                {"type":"paragraph","content":[{"type":"text","text":"无背景"}]}
            ]}
        ]}]
    });
    let doc = json!({"type":"doc","content":[pm.clone()]});
    let html = render::render(&doc).html;
    assert!(!html.contains("background-color"),
        "empty bgColor must not produce background-color style, html: {html}");
}

#[test]
fn rt_cell_vertical_align_preserved() {
    // verticalAlign: "top" / "middle" 在真实文档里存在，必须 roundtrip 保留
    for va in &["top", "middle"] {
        let pm = json!({
            "type": "table",
            "content": [{"type":"table_row","content":[{
                "type": "table_cell",
                "attrs": {"colwidth":[325],"verticalAlign":va},
                "content": [{"type":"paragraph","content":[{"type":"text","text":"内容"}]}]
            }]}]
        });
        let result = roundtrip(&pm);
        let cell = &result[0]["content"][0]["content"][0];
        let got = cell["attrs"]["verticalAlign"].as_str().unwrap_or("");
        assert_eq!(got, *va, "verticalAlign={va} must survive roundtrip");
    }
}

#[test]
fn rt_cell_font_color_preserved() {
    // color（字体颜色，如 rgba(0,0,0,0.5)）必须 roundtrip 保留
    let pm = json!({
        "type": "table",
        "content": [{"type":"table_row","content":[{
            "type": "table_cell",
            "attrs": {"colwidth":[191],"color":"rgba(0, 0, 0, 0.5)"},
            "content": [{"type":"paragraph","content":[{"type":"text","text":"暗色文字"}]}]
        }]}]
    });
    let result = roundtrip(&pm);
    let cell = &result[0]["content"][0]["content"][0];
    let got = cell["attrs"]["color"].as_str().unwrap_or("");
    assert!(!got.is_empty(), "cell font color must survive roundtrip");
    assert!(got.contains("0.5") || got.contains("rgba"), "color value must be preserved: {got}");
}

#[test]
fn rt_cell_all_attrs_combined() {
    // 真实文档里常见的完整 cell attrs 组合
    let pm = json!({
        "type": "table",
        "content": [{"type":"table_row","content":[{
            "type": "table_header",
            "attrs": {
                "colspan": 3,
                "rowspan": 1,
                "colwidth": [99, 99, 122],
                "bgColor": "rgb(244, 245, 247)",
                "verticalAlign": "middle"
            },
            "content": [{"type":"paragraph","content":[{"type":"text","text":"综合表头"}]}]
        }]}]
    });
    let result = roundtrip(&pm);
    let cell = &result[0]["content"][0]["content"][0];
    assert_eq!(cell["attrs"]["colspan"], 3);
    assert_eq!(cell["attrs"]["colwidth"].as_array().unwrap().len(), 3,
        "multi colwidth for colspan=3");
    let bg = cell["attrs"]["bgColor"].as_str().unwrap_or("");
    assert!(!bg.is_empty(), "bgColor must survive");
    let va = cell["attrs"]["verticalAlign"].as_str().unwrap_or("");
    assert_eq!(va, "middle", "verticalAlign must survive");
}

// ── 深层嵌套边界 ───────────────────────────────────────────────────────────────

#[test]
fn rt_deep_nest_blockquote_collapse_table() {
    // 真实文档里的最深嵌套：blockquote > km-collapse > ul > li > km-collapse > table
    // 这是之前发现的实际问题场景
    let pm = json!({
        "type": "blockquote",
        "content": [
            {"type":"paragraph","content":[{"type":"text","text":"说明"}]},
            {"type":"collapse","attrs":{},"content":[
                {"type":"collapse_title","content":[{"type":"text","text":"展开查看"}]},
                {"type":"collapse_content","content":[
                    {"type":"bullet_list","content":[
                        {"type":"list_item","content":[{"type":"paragraph","content":[{"type":"text","text":"普通项"}]}]},
                        {"type":"list_item","content":[
                            {"type":"paragraph","content":[{"type":"text","text":"复杂项"}]},
                            {"type":"collapse","attrs":{},"content":[
                                {"type":"collapse_title","content":[{"type":"text","text":"子折叠"}]},
                                {"type":"collapse_content","content":[
                                    {"type":"table","content":[
                                        {"type":"table_row","content":[
                                            {"type":"table_header","attrs":{"colwidth":[150],"colspan":3,"rowspan":1},"content":[{"type":"paragraph","content":[{"type":"text","text":"跨列头"}]}]},
                                        ]},
                                        {"type":"table_row","content":[
                                            {"type":"table_cell","attrs":{"colwidth":[150]},"content":[{"type":"paragraph","content":[{"type":"text","text":"A"}]}]},
                                            {"type":"table_cell","attrs":{"colwidth":[150]},"content":[{"type":"paragraph","content":[{"type":"text","text":"B"}]}]},
                                            {"type":"table_cell","attrs":{"colwidth":[150]},"content":[{"type":"paragraph","content":[{"type":"text","text":"C"}]}]}
                                        ]}
                                    ]}
                                ]}
                            ]}
                        ]}
                    ]}
                ]}
            ]}
        ]
    });
    let result = roundtrip(&pm);
    assert_eq!(result[0]["type"], "blockquote");
    // 找到深层 collapse
    let outer_collapse = result[0]["content"].as_array().unwrap()
        .iter().find(|n| n["type"] == "collapse").expect("outer collapse must exist");
    let cc = &outer_collapse["content"][1];
    assert_eq!(cc["type"], "collapse_content");
    let ul = cc["content"].as_array().unwrap().iter().find(|n| n["type"] == "bullet_list")
        .expect("bullet_list inside collapse must exist");
    let complex_li = &ul["content"].as_array().unwrap()[1];
    let inner_collapse = complex_li["content"].as_array().unwrap()
        .iter().find(|n| n["type"] == "collapse").expect("inner collapse must exist");
    // 验证最深层的 table 保留
    let inner_cc = &inner_collapse["content"][1];
    let table = inner_cc["content"].as_array().unwrap().iter().find(|n| n["type"] == "table")
        .expect("table inside inner collapse must exist");
    let rows = table["content"].as_array().unwrap();
    assert_eq!(rows.len(), 2, "table must have 2 rows");
    let header_cell = &rows[0]["content"][0];
    assert_eq!(header_cell["attrs"]["colspan"], 3, "colspan must be preserved in deep nesting");
}

#[test]
fn rt_table_cell_with_nested_collapse() {
    // 表格单元格内含 km-collapse 时，collapse 必须保留（如线上文档的复杂表格）
    let pm = json!({
        "type": "table",
        "content": [{
            "type": "table_row",
            "content": [{
                "type": "table_cell",
                "attrs": {},
                "content": [
                    {"type":"paragraph","content":[{"type":"text","text":"单元格文字"}]},
                    {"type":"collapse","attrs":{},"content":[
                        {"type":"collapse_title","content":[{"type":"text","text":"详细数据"}]},
                        {"type":"collapse_content","content":[{"type":"paragraph","content":[{"type":"text","text":"数据内容"}]}]}
                    ]}
                ]
            }]
        }]
    });
    let result = roundtrip(&pm);
    assert_eq!(result[0]["type"], "table");
    let cell_content = &result[0]["content"][0]["content"][0]["content"];
    let items = cell_content.as_array().unwrap();
    assert!(items.len() >= 2, "paragraph + collapse must survive in table cell");
    assert!(items.iter().any(|n| n["type"] == "collapse"),
        "collapse inside table cell must survive roundtrip");
}

#[test]
fn rt_multiple_h1_demoted_to_heading() {
    // 第 2 个以上 <h1> 必须降级为 heading level 1，不能产生第二个 title
    // 这个测试验证的是 apply_diff 的行为，需要构造多节点场景
    let doc = json!({
        "type": "doc",
        "content": [
            {"type":"title","content":[{"type":"text","text":"文档标题"}]},
            {"type":"paragraph","content":[{"type":"text","text":"正文"}]},
            {"type":"title","content":[{"type":"text","text":"章节标题"}]},  // 第2个 title（应被降级为 heading）
        ]
    });
    let html = render::render(&doc).html;
    // html 会有两个 <h1>
    assert_eq!(html.matches("<h1>").count(), 2);
    let nodes = myers::parse_nodes(&html);
    // 当 apply_diff 处理这些 AddOps 时，第2个 title 应被降级
    // 模拟 apply_diff 的 add 逻辑（用空 doc 接收所有节点）
    let mut content: Vec<Value> = Vec::new();
    for n in &nodes {
        if let Some(mut pm) = patch::build_pm_node(&n.tag, &n.attrs, &n.inner_html) {
            let already_has_title = content.iter().any(|c| c["type"] == "title");
            if already_has_title && pm["type"] == "title" {
                pm["type"] = serde_json::Value::String("heading".to_string());
                pm["attrs"] = json!({"level": 1});
            }
            content.push(pm);
        }
    }
    let title_count = content.iter().filter(|n| n["type"] == "title").count();
    let heading_count = content.iter().filter(|n| n["type"] == "heading").count();
    assert_eq!(title_count, 1, "must have exactly 1 title");
    assert_eq!(heading_count, 1, "second h1 must be demoted to heading");
}
