use km_ops::api::extract_id;
use km_ops::diff::diff;
use km_ops::patch::build_pm_node;
use km_ops::render::render;
use serde_json::json;

// ── extract_id（测真实 api::extract_id）────────────────────────────────────
// 设计：只接受纯数字 ID。URL / 空串 / 非数字一律拒绝，AI 传错就报错踢回去。

#[test]
fn test_extract_id_pure_digits() {
    assert_eq!(extract_id("1234567890"), Ok("1234567890".to_string()));
}

#[test]
fn test_extract_id_trims_surrounding_spaces() {
    assert_eq!(extract_id("  1234567890  "), Ok("1234567890".to_string()));
}

#[test]
fn test_extract_id_rejects_url() {
    // URL 不解析，一律拒绝，提示 AI 自己提 ID
    assert!(extract_id("https://km.sankuai.com/collabpage/1234567890").is_err());
    assert!(extract_id("km.sankuai.com/page/1234567890").is_err());
    assert!(extract_id("https://example.com/foo").is_err());
}

#[test]
fn test_extract_id_rejects_empty_and_whitespace() {
    assert!(extract_id("").is_err());
    assert!(extract_id("   ").is_err());
}

#[test]
fn test_extract_id_rejects_non_digit() {
    assert!(extract_id("abc").is_err());
    assert!(extract_id("12a34").is_err());
}

// ── buildPmNode 未知 tag ─────────────────────────────────────────────────

#[test]
fn test_build_pm_node_unknown_tag_rejected() {
    assert!(build_pm_node("section", &Default::default(), "内容").is_none());
    assert!(build_pm_node("div", &Default::default(), "内容").is_none());
    assert!(build_pm_node("section", &Default::default(), "").is_none());
    assert!(build_pm_node("div", &Default::default(), "   ").is_none());
    // video (not km-video) should NOT be accepted
    assert!(build_pm_node("video", &Default::default(), "").is_none());
}

#[test]
fn test_build_pm_node_empty_inner_legal_tag() {
    assert!(build_pm_node("p", &Default::default(), "").is_some());
    assert!(build_pm_node("hr", &Default::default(), "").is_some());
}

#[test]
fn test_build_pm_node_rich_tags() {
    let mut attrs = std::collections::HashMap::new();
    attrs.insert("name".into(), "file.pdf".into());
    assert_eq!(
        build_pm_node("km-attachment", &attrs, "").unwrap()["type"],
        "attachment"
    );

    let mut va = std::collections::HashMap::new();
    va.insert("src".into(), "https://...".into());
    assert_eq!(build_pm_node("km-video", &va, "").unwrap()["type"], "video");
    assert_eq!(build_pm_node("km-audio", &va, "").unwrap()["type"], "audio");
    assert_eq!(
        build_pm_node("km-drawio", &va, "").unwrap()["type"],
        "drawio"
    );
}

// ── render.js 边界 ────────────────────────────────────────────────────────

#[test]
fn test_render_no_attrs_no_panic() {
    let doc = json!({
        "type": "doc",
        "content": [
            {"type":"title","content":[{"type":"text","text":"T"}]},
            {"type":"paragraph","content":[{"type":"text","text":"内容"}]}
        ]
    });
    let result = render(&doc);
    assert!(result.html.contains("T"));
    assert!(result.html.contains("内容"));
}

#[test]
fn test_render_null_content() {
    let doc = json!({
        "type": "doc",
        "content": [
            {"type":"title","attrs":{"nodeId":"x"},"content":null}
        ]
    });
    let _ = render(&doc); // must not panic
}

#[test]
fn test_render_deep_marks() {
    let doc = json!({
        "type": "doc",
        "content": [
            {"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"T"}]},
            {"type":"paragraph","attrs":{"nodeId":"p"},"content":[{
                "type":"text","text":"复合样式",
                "marks": [
                    {"type":"strong"},{"type":"em"},{"type":"underline"},
                    {"type":"color","attrs":{"color":"#f00"}},
                    {"type":"backgroundcolor","attrs":{"color":"#ff0"}}
                ]
            }]}
        ]
    });
    let html = render(&doc).html;
    assert!(html.contains("复合样式"));
    assert!(html.contains("<strong>"));
    assert!(html.contains("<em>"));
}

// ── diff.js 边界 ──────────────────────────────────────────────────────────

#[test]
fn test_diff_empty_html_no_panic() {
    let _ = diff("", "", &json!({"children":[]}));
    let _ = diff("", "<p>新内容</p>", &json!({"children":[]}));
    let _ = diff("<p>旧内容</p>", "", &json!({"children":[]}));
}

#[test]
fn test_diff_large_document_performance() {
    let mut content =
        vec![json!({"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"T"}]})];
    for i in 0..200 {
        content.push(json!({"type":"paragraph","attrs":{"nodeId":format!("p{i}")},"content":[{"type":"text","text":format!("段落{i}")}]}));
    }
    let doc = json!({"type":"doc","content":content});
    let result = render(&doc);
    let new_html = result.html.replace("<p>段落0</p>", "<p>段落0已修改</p>");
    let d = diff(&result.html, &new_html, &doc);
    let total_ops = d.changed.len() + d.deleted.len() + d.added.len();
    assert!(total_ops > 0);
}

// ═══════════════════════════════════════════════════════════════════════════
// AUTH.RS PLACEHOLDER TESTS
// ═══════════════════════════════════════════════════════════════════════════

use km_ops::auth;

// ── Placeholder Detection Edge Cases ────────────────────────────────────────

#[test]
fn test_is_placeholder_whitespace_only() {
    // Whitespace is not considered placeholder
    assert!(!auth::is_placeholder("   "));
    assert!(!auth::is_placeholder("\t"));
    assert!(!auth::is_placeholder("\n"));
}

#[test]
fn test_is_placeholder_template_with_spaces() {
    assert!(!auth::is_placeholder("{{ userId }}"));
    assert!(!auth::is_placeholder("${ userId }"));
}

#[test]
fn test_is_placeholder_nested_braces() {
    assert!(!auth::is_placeholder("{{nested{{}}}}"));
    assert!(!auth::is_placeholder("${nested{}}"));
}

#[test]
fn test_is_placeholder_mismatched_braces() {
    // Mismatched braces not detected as placeholder
    assert!(!auth::is_placeholder("{{userId}"));
    assert!(!auth::is_placeholder("{userId}}"));
    assert!(!auth::is_placeholder("${userId"));
    assert!(!auth::is_placeholder("$userId}"));
}

#[test]
fn test_is_placeholder_single_brace() {
    // Single braces not enough
    assert!(!auth::is_placeholder("{userId}"));
    assert!(!auth::is_placeholder("$userId"));
}

#[test]
fn test_is_placeholder_minimum_length_edge() {
    // Exactly 4 chars for {{}} format
    assert!(auth::is_placeholder("{{a}}"));
    assert!(auth::is_placeholder("{{1}}"));
    assert!(!auth::is_placeholder("{{}}"));

    // Exactly 3 chars for ${} format
    assert!(auth::is_placeholder("${a}"));
    assert!(auth::is_placeholder("${1}"));
    assert!(!auth::is_placeholder("${}"));
}

#[test]
fn test_is_placeholder_numeric_content() {
    // Numeric content in template syntax
    assert!(auth::is_placeholder("{{123}}"));
    assert!(auth::is_placeholder("${456}"));
}
