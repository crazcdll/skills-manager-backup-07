use km_ops::myers::{
    hash_str, rich_hash, node_similarity, approx_similarity, parse_nodes, simple_diff,
    HtmlNode, DiffOpKind,
};
use std::collections::HashMap;

// ── HASH FUNCTIONS TESTS ──────────────────────────────────────────────────────

#[test]
fn test_hash_str_consistency() {
    // Same input always produces same hash
    let input = "consistent_test_string";
    assert_eq!(hash_str(input), hash_str(input));
    assert_eq!(hash_str(input), hash_str(input));
}


#[test]
fn test_hash_str_empty_string() {
    assert_eq!(hash_str(""), "0");
}

#[test]
fn test_hash_str_single_char() {
    // Single character should hash consistently
    let h = hash_str("a");
    assert!(!h.is_empty());
    assert_eq!(h, hash_str("a"));
}

#[test]
fn test_hash_str_unicode_characters() {
    // Unicode should be hashed consistently (as UTF-8 bytes)
    let hash1 = hash_str("你好");
    let hash2 = hash_str("你好");
    assert_eq!(hash1, hash2);
}

#[test]
fn test_hash_str_similar_strings_different_hashes() {
    // Slightly different strings should produce different hashes
    assert_ne!(hash_str("hello"), hash_str("hallo"));
    assert_ne!(hash_str("test"), hash_str("test1"));
}

#[test]
fn test_hash_str_whitespace_sensitive() {
    // Different whitespace should produce different hashes
    assert_ne!(hash_str("hello world"), hash_str("hello  world"));
    assert_ne!(hash_str("test"), hash_str(" test"));
}

#[test]
fn test_hash_str_case_sensitive() {
    // Case should matter
    assert_ne!(hash_str("Hello"), hash_str("hello"));
}

#[test]
fn test_hash_str_special_characters() {
    // Special characters should hash consistently
    let special = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`";
    assert_eq!(hash_str(special), hash_str(special));
}

#[test]
fn test_hash_str_long_string() {
    // Long strings should be hashable
    let long = "a".repeat(10000);
    let h = hash_str(&long);
    assert_eq!(h, hash_str(&long));
    assert!(!h.is_empty());
}

#[test]
fn test_rich_hash_drawio_same_src() {
    // Same drawio element should have same rich hash
    let mut attrs = HashMap::new();
    attrs.insert("src".to_string(), "https://cdn/diagram.svg".to_string());
    let h1 = rich_hash("km-drawio", &attrs);
    let h2 = rich_hash("km-drawio", &attrs);
    assert_eq!(h1, h2);
}

#[test]
fn test_rich_hash_drawio_different_src() {
    // Different src should produce different hash
    let mut attrs1 = HashMap::new();
    attrs1.insert("src".to_string(), "https://cdn/a.svg".to_string());

    let mut attrs2 = HashMap::new();
    attrs2.insert("src".to_string(), "https://cdn/b.svg".to_string());

    assert_ne!(rich_hash("km-drawio", &attrs1), rich_hash("km-drawio", &attrs2));
}

#[test]
fn test_rich_hash_video_multiple_attrs() {
    // km-video uses both src and url
    let mut attrs = HashMap::new();
    attrs.insert("src".to_string(), "video.mp4".to_string());
    attrs.insert("url".to_string(), "https://example.com/video".to_string());

    let h = rich_hash("km-video", &attrs);
    assert_eq!(h, rich_hash("km-video", &attrs));
}

#[test]
fn test_rich_hash_missing_attributes() {
    // Missing expected attributes should still hash
    let attrs = HashMap::new();
    let h = rich_hash("km-drawio", &attrs);
    assert_eq!(h, rich_hash("km-drawio", &attrs));
}

#[test]
fn test_rich_hash_non_rich_tag() {
    // Non-rich tags fallback to tag name hash
    let attrs = HashMap::new();
    assert_eq!(rich_hash("p", &attrs), hash_str("p"));
    assert_eq!(rich_hash("div", &attrs), hash_str("div"));
}

#[test]
fn test_rich_hash_img_tag() {
    // img is a rich tag with src attribute
    let mut attrs = HashMap::new();
    attrs.insert("src".to_string(), "image.png".to_string());

    let h1 = rich_hash("img", &attrs);

    let mut attrs2 = HashMap::new();
    attrs2.insert("src".to_string(), "other.png".to_string());
    let h2 = rich_hash("img", &attrs2);

    assert_ne!(h1, h2);
}

#[test]
fn test_rich_hash_attachment_name_and_src() {
    // km-attachment uses both name and src
    let mut attrs = HashMap::new();
    attrs.insert("src".to_string(), "file.pdf".to_string());
    attrs.insert("name".to_string(), "document".to_string());

    let h = rich_hash("km-attachment", &attrs);
    assert_eq!(h, rich_hash("km-attachment", &attrs));
}

#[test]
fn test_rich_hash_xtable_id() {
    // km-xtable uses xtable-id attribute
    let mut attrs = HashMap::new();
    attrs.insert("xtable-id".to_string(), "table-123".to_string());

    let h1 = rich_hash("km-xtable", &attrs);

    let mut attrs2 = HashMap::new();
    attrs2.insert("xtable-id".to_string(), "table-456".to_string());
    let h2 = rich_hash("km-xtable", &attrs2);

    assert_ne!(h1, h2);
}

// ── SIMILARITY CALCULATION TESTS ──────────────────────────────────────────────

#[test]
fn test_similarity_identical_nodes() {
    let a = HtmlNode {
        tag: "p".into(),
        attrs: HashMap::new(),
        inner_html: "same content".into(),
        hash: hash_str("p|same content"),
    };
    let b = a.clone();
    assert_eq!(node_similarity(&a, &b), 1.0);
}

#[test]
fn test_similarity_different_tags() {
    let a = HtmlNode {
        tag: "p".into(),
        attrs: HashMap::new(),
        inner_html: "hello".into(),
        hash: hash_str("p|hello"),
    };
    let b = HtmlNode {
        tag: "div".into(),
        attrs: HashMap::new(),
        inner_html: "hello".into(),
        hash: hash_str("div|hello"),
    };
    assert_eq!(node_similarity(&a, &b), 0.0);
}

#[test]
fn test_similarity_same_hash_implies_1_0() {
    let hash = hash_str("p|content");
    let a = HtmlNode {
        tag: "p".into(),
        attrs: HashMap::new(),
        inner_html: "content".into(),
        hash: hash.clone(),
    };
    let b = HtmlNode {
        tag: "p".into(),
        attrs: HashMap::new(),
        inner_html: "content".into(),
        hash,
    };
    assert_eq!(node_similarity(&a, &b), 1.0);
}

#[test]
fn test_similarity_heading_family_same_content() {
    // h2 and h3 both in heading family
    let a = HtmlNode {
        tag: "h2".into(),
        attrs: HashMap::new(),
        inner_html: "section title".into(),
        hash: hash_str("h2|section title"),
    };
    let b = HtmlNode {
        tag: "h3".into(),
        attrs: HashMap::new(),
        inner_html: "section title".into(),
        hash: hash_str("h3|section title"),
    };
    let sim = node_similarity(&a, &b);
    assert!(sim >= 0.8, "heading family with same content should be highly similar, got {}", sim);
}

#[test]
fn test_similarity_heading_family_similar_content() {
    // h1 and h2 with similar content
    let a = HtmlNode {
        tag: "h1".into(),
        attrs: HashMap::new(),
        inner_html: "Main Title".into(),
        hash: hash_str("h1|Main Title"),
    };
    let b = HtmlNode {
        tag: "h2".into(),
        attrs: HashMap::new(),
        inner_html: "Main Title".into(),
        hash: hash_str("h2|Main Title"),
    };
    let sim = node_similarity(&a, &b);
    assert!(sim > 0.8, "heading family similarity should be high");
}

#[test]
fn test_similarity_rich_node_same_tag() {
    // Rich nodes with same tag and hash
    let a = HtmlNode {
        tag: "km-drawio".into(),
        attrs: HashMap::new(),
        inner_html: "".into(),
        hash: hash_str("km-drawio|src1"),
    };
    let b = HtmlNode {
        tag: "km-drawio".into(),
        attrs: HashMap::new(),
        inner_html: "".into(),
        hash: hash_str("km-drawio|src1"),
    };
    assert_eq!(node_similarity(&a, &b), 1.0);
}

#[test]
fn test_similarity_rich_node_different_tag() {
    // Different rich tags
    let a = HtmlNode {
        tag: "km-drawio".into(),
        attrs: HashMap::new(),
        inner_html: "".into(),
        hash: hash_str("km-drawio"),
    };
    let b = HtmlNode {
        tag: "km-video".into(),
        attrs: HashMap::new(),
        inner_html: "".into(),
        hash: hash_str("km-video"),
    };
    assert_eq!(node_similarity(&a, &b), 0.0);
}

#[test]
fn test_similarity_rich_node_same_tag_different_hash() {
    // Same rich tag but different hash (different src)
    let a = HtmlNode {
        tag: "km-drawio".into(),
        attrs: HashMap::new(),
        inner_html: "".into(),
        hash: hash_str("km-drawio|src1"),
    };
    let b = HtmlNode {
        tag: "km-drawio".into(),
        attrs: HashMap::new(),
        inner_html: "".into(),
        hash: hash_str("km-drawio|src2"),
    };
    let sim = node_similarity(&a, &b);
    assert_eq!(sim, 0.9, "rich nodes with different hash should be 0.9");
}

#[test]
fn test_similarity_regular_nodes_text_comparison() {
    // Regular (non-rich, non-heading) nodes use approx_similarity
    let a = HtmlNode {
        tag: "p".into(),
        attrs: HashMap::new(),
        inner_html: "hello world".into(),
        hash: hash_str("p|hello world"),
    };
    let b = HtmlNode {
        tag: "p".into(),
        attrs: HashMap::new(),
        inner_html: "hello earth".into(),
        hash: hash_str("p|hello earth"),
    };
    let sim = node_similarity(&a, &b);
    assert!(sim > 0.0 && sim < 1.0, "similar text should have partial similarity");
}

#[test]
fn test_approx_similarity_identical() {
    assert_eq!(approx_similarity("hello", "hello"), 1.0);
}

#[test]
fn test_approx_similarity_both_empty() {
    assert_eq!(approx_similarity("", ""), 1.0);
}

#[test]
fn test_approx_similarity_one_empty() {
    assert_eq!(approx_similarity("hello", ""), 0.0);
    assert_eq!(approx_similarity("", "world"), 0.0);
}

#[test]
fn test_approx_similarity_prefix_match() {
    // Matching prefix increases similarity
    let sim = approx_similarity("hello world", "hello earth");
    assert!(sim > 0.4, "shared prefix should increase similarity, got {}", sim);
}

#[test]
fn test_approx_similarity_suffix_match() {
    // Matching suffix increases similarity
    let sim = approx_similarity("prefix test", "different test");
    assert!(sim > 0.2, "shared suffix should increase similarity, got {}", sim);
}

#[test]
fn test_approx_similarity_no_match() {
    // Completely different strings
    let sim = approx_similarity("aaa", "zzz");
    assert!(sim < 0.5, "completely different strings should have low similarity");
}

#[test]
fn test_approx_similarity_unicode_strings() {
    // Unicode strings should be compared as characters
    let sim = approx_similarity("你好世界", "你好");
    assert!(sim >= 0.5, "unicode prefix match should yield similarity >= 0.5");
}

#[test]
fn test_approx_similarity_single_char_match() {
    // Single character match
    let sim = approx_similarity("a", "a");
    assert_eq!(sim, 1.0);
}

#[test]
fn test_approx_similarity_length_difference() {
    // Large length difference
    let sim = approx_similarity("short", "this is a very long string");
    assert!(sim < 1.0, "different lengths should reduce similarity");
}

#[test]
fn test_approx_similarity_max_capped_at_1_0() {
    // Similarity should never exceed 1.0
    let sim = approx_similarity("hello", "hello");
    assert_eq!(sim, 1.0);
}

// ── DIFF OPERATIONS TESTS ────────────────────────────────────────────────────

#[test]
fn test_diff_identical_sequences() {
    let old = parse_nodes("<p>a</p><p>b</p>");
    let new = parse_nodes("<p>a</p><p>b</p>");
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 2);
    assert_eq!(ops[0].op, DiffOpKind::Keep);
    assert_eq!(ops[0].old_idx, Some(0));
    assert_eq!(ops[0].new_idx, Some(0));
    assert_eq!(ops[1].op, DiffOpKind::Keep);
    assert_eq!(ops[1].old_idx, Some(1));
    assert_eq!(ops[1].new_idx, Some(1));
}

#[test]
fn test_diff_insert_at_end() {
    let old = parse_nodes("<p>a</p>");
    let new = parse_nodes("<p>a</p><p>b</p>");
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 2);
    assert_eq!(ops[0].op, DiffOpKind::Keep);
    assert_eq!(ops[1].op, DiffOpKind::Insert);
    assert_eq!(ops[1].new_idx, Some(1));
}

#[test]
fn test_diff_delete_at_end() {
    let old = parse_nodes("<p>a</p><p>b</p>");
    let new = parse_nodes("<p>a</p>");
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 2);
    assert_eq!(ops[0].op, DiffOpKind::Keep);
    assert_eq!(ops[1].op, DiffOpKind::Delete);
    assert_eq!(ops[1].old_idx, Some(1));
}

#[test]
fn test_diff_multiple_inserts() {
    let old = parse_nodes("<p>a</p>");
    let new = parse_nodes("<p>a</p><p>b</p><p>c</p>");
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 3);
    assert_eq!(ops[0].op, DiffOpKind::Keep);
    assert_eq!(ops[1].op, DiffOpKind::Insert);
    assert_eq!(ops[2].op, DiffOpKind::Insert);
}

#[test]
fn test_diff_multiple_deletes() {
    let old = parse_nodes("<p>a</p><p>b</p><p>c</p>");
    let new = parse_nodes("<p>a</p>");
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 3);
    assert_eq!(ops[0].op, DiffOpKind::Keep);
    assert_eq!(ops[1].op, DiffOpKind::Delete);
    assert_eq!(ops[2].op, DiffOpKind::Delete);
}

#[test]
fn test_diff_empty_to_content() {
    let old = parse_nodes("");
    let new = parse_nodes("<p>first</p>");
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 1);
    assert_eq!(ops[0].op, DiffOpKind::Insert);
    assert_eq!(ops[0].new_idx, Some(0));
}

#[test]
fn test_diff_content_to_empty() {
    let old = parse_nodes("<p>content</p>");
    let new = parse_nodes("");
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 1);
    assert_eq!(ops[0].op, DiffOpKind::Delete);
    assert_eq!(ops[0].old_idx, Some(0));
}

#[test]
fn test_diff_mixed_operations() {
    let old = parse_nodes("<p>a</p><p>b</p><p>c</p>");
    let new = parse_nodes("<p>a</p><p>x</p><p>c</p><p>d</p>");
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 4);
    assert_eq!(ops[0].op, DiffOpKind::Keep);    // a stays
    assert_eq!(ops[1].op, DiffOpKind::Keep);    // b -> x position
    assert_eq!(ops[2].op, DiffOpKind::Keep);    // c stays
    assert_eq!(ops[3].op, DiffOpKind::Insert);  // d inserted
}

#[test]
fn test_diff_operations_preserve_indices() {
    let old = parse_nodes("<p>a</p><p>b</p>");
    let new = parse_nodes("<p>a</p><p>b</p><p>c</p>");
    let ops = simple_diff(&old, &new, 0.5);

    for op in &ops {
        match op.op {
            DiffOpKind::Keep => {
                assert!(op.old_idx.is_some());
                assert!(op.new_idx.is_some());
            }
            DiffOpKind::Delete => {
                assert!(op.old_idx.is_some());
                assert!(op.new_idx.is_none());
            }
            DiffOpKind::Insert => {
                assert!(op.old_idx.is_none());
                assert!(op.new_idx.is_some());
            }
        }
    }
}

// ── EDGE CASES & BOUNDARY CONDITIONS ──────────────────────────────────────────

#[test]
fn test_hash_str_very_large_number() {
    // Test with string containing very large numeric value
    let large = "999999999999999999999999";
    assert_eq!(hash_str(large), hash_str(large));
}

#[test]
fn test_similarity_very_long_matching_prefix() {
    // Very long matching prefix with short suffix difference
    let prefix = "a".repeat(1000);
    let sim = approx_similarity(&(prefix.clone() + "x"), &(prefix + "y"));
    assert!(sim > 0.99, "very long prefix match should yield high similarity");
}

#[test]
fn test_similarity_very_long_matching_suffix() {
    // Very long matching suffix with short prefix difference
    let suffix = "a".repeat(1000);
    let sim = approx_similarity(&("x".to_string() + &suffix), &("y".to_string() + &suffix));
    assert!(sim > 0.99, "very long suffix match should yield high similarity");
}

#[test]
fn test_diff_very_large_old_sequence() {
    // Large old sequence, empty new
    let old = parse_nodes(&"<p>item</p>".repeat(100));
    let new = parse_nodes("");
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 100);
    for op in ops {
        assert_eq!(op.op, DiffOpKind::Delete);
    }
}

#[test]
fn test_diff_very_large_new_sequence() {
    // Empty old sequence, large new
    let old = parse_nodes("");
    let new = parse_nodes(&"<p>item</p>".repeat(100));
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 100);
    for op in ops {
        assert_eq!(op.op, DiffOpKind::Insert);
    }
}

#[test]
fn test_hash_str_all_ascii_printable() {
    // All printable ASCII characters
    let ascii = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~";
    let h = hash_str(ascii);
    assert_eq!(h, hash_str(ascii));
}

#[test]
fn test_rich_hash_all_rich_tag_types() {
    // Test each rich tag type
    let tags = vec![
        "km-drawio",
        "km-video",
        "km-audio",
        "km-attachment",
        "km-xtable",
        "km-open-link",
        "km-open-card",
        "img",
    ];

    for tag in tags {
        let attrs = HashMap::new();
        let h = rich_hash(tag, &attrs);
        assert_eq!(h, rich_hash(tag, &attrs), "tag {} should produce consistent hash", tag);
    }
}

#[test]
fn test_diff_single_node_vs_many() {
    // Single node replaced by many
    let old = parse_nodes("<p>old</p>");
    let new = parse_nodes("<p>new1</p><p>new2</p><p>new3</p>");
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 3);
    assert_eq!(ops[0].op, DiffOpKind::Keep);
    assert_eq!(ops[1].op, DiffOpKind::Insert);
    assert_eq!(ops[2].op, DiffOpKind::Insert);
}

#[test]
fn test_diff_many_vs_single_node() {
    // Many nodes replaced by single
    let old = parse_nodes("<p>a</p><p>b</p><p>c</p>");
    let new = parse_nodes("<p>single</p>");
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 3);
    assert_eq!(ops[0].op, DiffOpKind::Keep);
    assert_eq!(ops[1].op, DiffOpKind::Delete);
    assert_eq!(ops[2].op, DiffOpKind::Delete);
}

#[test]
fn test_similarity_prefix_only() {
    // Text with only prefix match
    let sim = approx_similarity("prefixA", "prefixB");
    assert!(sim > 0.5);
}

#[test]
fn test_similarity_suffix_only() {
    // Text with only suffix match
    let sim = approx_similarity("Asuffix", "Bsuffix");
    assert!(sim > 0.5);
}

#[test]
fn test_approx_similarity_single_char_diff() {
    // One character difference in otherwise identical strings
    let sim = approx_similarity("testing", "testimg");
    assert!(sim > 0.8, "one char diff should have high similarity");
}

#[test]
fn test_hash_str_numeric_string() {
    // Pure numeric strings
    let h1 = hash_str("12345");
    let h2 = hash_str("12345");
    assert_eq!(h1, h2);
    assert_ne!(h1, hash_str("12346"));
}

#[test]
fn test_similarity_all_heading_types() {
    // Test similarity between all heading types
    let headings = vec!["h1", "h2", "h3", "h4", "h5", "h6"];

    for i in 0..headings.len() {
        for j in i..headings.len() {
            let a = HtmlNode {
                tag: headings[i].into(),
                attrs: HashMap::new(),
                inner_html: "same title".into(),
                hash: hash_str(&format!("{}|same title", headings[i])),
            };
            let b = HtmlNode {
                tag: headings[j].into(),
                attrs: HashMap::new(),
                inner_html: "same title".into(),
                hash: hash_str(&format!("{}|same title", headings[j])),
            };

            let sim = node_similarity(&a, &b);
            if headings[i] == headings[j] {
                assert_eq!(sim, 1.0, "same heading type should be 1.0");
            } else {
                assert!(sim >= 0.8, "different heading types with same content should be >= 0.8");
            }
        }
    }
}

#[test]
fn test_diff_rich_nodes() {
    // Diff with rich nodes (km-drawio, km-video, etc.)
    let old = parse_nodes(r#"<km-drawio src="a.svg"/><p>text</p>"#);
    let new = parse_nodes(r#"<km-drawio src="b.svg"/><p>text</p>"#);
    let ops = simple_diff(&old, &new, 0.5);

    assert_eq!(ops.len(), 2);
    assert_eq!(ops[0].op, DiffOpKind::Keep);
    assert_eq!(ops[1].op, DiffOpKind::Keep);
}

#[test]
fn test_hash_str_newline_and_tabs() {
    // Strings with newlines and tabs
    let h1 = hash_str("line1\nline2\tvalue");
    let h2 = hash_str("line1\nline2\tvalue");
    assert_eq!(h1, h2);
}

#[test]
fn test_approx_similarity_interleaved_chars() {
    // Characters interleaved rather than prefix/suffix
    let sim = approx_similarity("abcd", "aXbXcXdX");
    assert!(sim >= 0.0 && sim <= 1.0, "should handle interleaved chars");
}

#[test]
fn test_diff_threshold_parameter_not_used_in_simple_diff() {
    // The threshold parameter is not used in simple_diff
    // Different thresholds should produce same result
    let old = parse_nodes("<p>a</p>");
    let new = parse_nodes("<p>a</p><p>b</p>");

    let ops1 = simple_diff(&old, &new, 0.1);
    let ops2 = simple_diff(&old, &new, 0.9);

    assert_eq!(ops1, ops2, "threshold should not affect simple_diff result");
}

// ── 回归 take(200) bug：长节点末尾修改必须改变 hash ──────────────────────────
// 曾因 hash 只取 inner_html 前 200 字符，导致 >200 字符节点的末尾修改被判定为无变化。

#[test]
fn test_long_node_hash_changes_on_tail_edit() {
    // 构造一个 inner_html > 200 字符的 table 节点
    let long_cell = "<td><p>这是一段稍微长一点的单元格内容用于撑过两百字符门槛</p></td>";
    let base_inner: String = std::iter::repeat(long_cell).take(10).collect(); // 远超 200 字符
    assert!(base_inner.len() > 200, "测试前置：inner_html 应 >200 字符");

    let html_old = format!("<table>{}</table>", base_inner);
    // 在末尾追加一个新行（修改落在 200 字符之后）
    let html_new = format!("<table>{}<tr><td><p>新增行</p></td></tr></table>", base_inner);

    let old_nodes = parse_nodes(&html_old);
    let new_nodes = parse_nodes(&html_new);
    assert_eq!(old_nodes.len(), 1);
    assert_eq!(new_nodes.len(), 1);
    // 核心断言：末尾改动了，hash 必须不同（take(200) bug 会导致 hash 相同）
    assert_ne!(old_nodes[0].hash, new_nodes[0].hash,
        "长节点末尾修改未改变 hash（疑似 take(200) 回归）");
    assert_eq!(old_nodes[0].tag, "table");
    assert_eq!(new_nodes[0].tag, "table");
}
