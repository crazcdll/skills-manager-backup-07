use km_ops::cli_utils::*;

// ── inferKind（文件类型推断）────────────────────────────────────────────────

#[test]
fn test_infer_kind_image() {
    assert_eq!(infer_kind("/tmp/photo.jpg"), "image");
    assert_eq!(infer_kind("/tmp/photo.jpeg"), "image");
    assert_eq!(infer_kind("/tmp/photo.PNG"), "image");
    assert_eq!(infer_kind("/tmp/logo.gif"), "image");
    assert_eq!(infer_kind("/tmp/icon.webp"), "image");
    assert_eq!(infer_kind("/tmp/icon.svg"), "image");
    assert_eq!(infer_kind("/tmp/icon.bmp"), "image");
}

#[test]
fn test_infer_kind_video() {
    assert_eq!(infer_kind("/tmp/video.mp4"), "video");
    assert_eq!(infer_kind("/tmp/video.mov"), "video");
    assert_eq!(infer_kind("/tmp/video.mkv"), "video");
    assert_eq!(infer_kind("/tmp/video.webm"), "video");
    assert_eq!(infer_kind("/tmp/video.avi"), "video");
}

#[test]
fn test_infer_kind_audio() {
    assert_eq!(infer_kind("/tmp/audio.mp3"), "audio");
    assert_eq!(infer_kind("/tmp/audio.aac"), "audio");
    assert_eq!(infer_kind("/tmp/audio.wav"), "audio");
    assert_eq!(infer_kind("/tmp/audio.ogg"), "audio");
    assert_eq!(infer_kind("/tmp/audio.flac"), "audio");
    assert_eq!(infer_kind("/tmp/audio.m4a"), "audio");
}

#[test]
fn test_infer_kind_file() {
    assert_eq!(infer_kind("/tmp/report.pdf"), "file");
    assert_eq!(infer_kind("/tmp/data.xlsx"), "file");
    assert_eq!(infer_kind("/tmp/archive.zip"), "file");
    assert_eq!(infer_kind("/tmp/doc.docx"), "file");
}

#[test]
fn test_infer_kind_no_extension() {
    assert_eq!(infer_kind("/tmp/noext"), "file");
    assert_eq!(infer_kind("filename"), "file");
}

// ── flag（CLI 参数提取）────────────────────────────────────────────────────

#[test]
fn test_flag_extract_existing() {
    let args = vec!["--type".to_string(), "image".to_string(), "--limit".to_string(), "10".to_string()];
    assert_eq!(flag(&args, "--type"), Some("image".to_string()));
    assert_eq!(flag(&args, "--limit"), Some("10".to_string()));
}

#[test]
fn test_flag_not_found() {
    let args = vec!["--type".to_string(), "image".to_string()];
    assert_eq!(flag(&args, "--limit"), None);
    assert_eq!(flag(&[], "--type"), None);
}

#[test]
fn test_flag_no_value() {
    let args = vec!["--type".to_string()];
    assert_eq!(flag(&args, "--type"), None);
}

#[test]
fn test_flag_dry_run_force_detect() {
    let args: Vec<String> = vec!["1000000002".into(), "--dry-run".into(), "--force".into()];
    assert!(args.contains(&"--dry-run".to_string()));
    assert!(args.contains(&"--force".to_string()));
    let id = args.iter().find(|a| !a.starts_with("--")).unwrap();
    assert_eq!(id, "1000000002");
}

// ── create 参数解析 ─────────────────────────────────────────────────────

#[test]
fn test_parse_create_input_markdown_title_only() {
    let parsed = parse_create_input(&[], "# 技术方案\n").unwrap();
    assert_eq!(parsed.title, "技术方案");
    assert_eq!(parsed.markdown, "# 技术方案");
    assert_eq!(parsed.parent_id, None);
}

#[test]
fn test_parse_create_input_with_parent() {
    let args = vec!["--parent".to_string(), "1461835105".to_string()];
    let parsed = parse_create_input(&args, "# 技术方案\n## 背景\n正文").unwrap();
    assert_eq!(parsed.title, "技术方案");
    assert_eq!(parsed.parent_id.as_deref(), Some("1461835105"));
}

#[test]
fn test_parse_create_input_rejects_missing_stdin() {
    let err = parse_create_input(&[], " \n").unwrap_err();
    assert!(err.contains("stdin"));
    assert!(err.contains("# 文档标题"));
}

#[test]
fn test_parse_create_input_rejects_missing_h1() {
    let err = parse_create_input(&[], "## 背景\n正文").unwrap_err();
    assert!(err.contains("第一行必须是一级标题"));
}

#[test]
fn test_parse_create_input_rejects_empty_h1() {
    let err = parse_create_input(&[], "#   \n正文").unwrap_err();
    assert!(err.contains("第一行必须是一级标题"));
}

#[test]
fn test_parse_create_input_rejects_parent_without_value() {
    let args = vec!["--parent".to_string()];
    let err = parse_create_input(&args, "# 技术方案\n").unwrap_err();
    assert!(err.contains("--parent"));
}

// ── strip_html ────────────────────────────────────────────────────────────

#[test]
fn test_strip_html_p_tag() {
    assert_eq!(strip_html("<p>这是段落</p>"), "这是段落");
}

#[test]
fn test_strip_html_nested() {
    assert_eq!(strip_html("<p><strong>粗体</strong>文字</p>"), "粗体文字");
}

#[test]
fn test_strip_html_entities() {
    assert_eq!(strip_html("&lt;script&gt;alert()&lt;/script&gt;"), "<script>alert()</script>");
    assert_eq!(strip_html("a &amp; b"), "a & b");
}

#[test]
fn test_strip_html_empty() {
    assert_eq!(strip_html(""), "");
}

#[test]
fn test_strip_html_plain_text() {
    assert_eq!(strip_html("普通文字"), "普通文字");
}

// ── esc_html ──────────────────────────────────────────────────────────────

#[test]
fn test_esc_html_special_chars() {
    assert_eq!(esc_html("<script>"), "&lt;script&gt;");
    assert_eq!(esc_html("a & b"), "a &amp; b");
    assert_eq!(esc_html("1 < 2 > 0"), "1 &lt; 2 &gt; 0");
}

#[test]
fn test_esc_html_safe_chars() {
    assert_eq!(esc_html("hello world"), "hello world");
    assert_eq!(esc_html("中文内容"), "中文内容");
}

#[test]
fn test_esc_html_empty() {
    assert_eq!(esc_html(""), "");
}

// ── upload result HTML format ─────────────────────────────────────────────

#[test]
fn test_upload_result_image_html() {
    let r = fake_upload_result("image", "https://km.sankuai.com/api/file/123/456", "photo.png",
        &[("width", "800"), ("height", "600")]);
    assert!(r.html.contains("<img src=\"https://km.sankuai.com/api/file/123/456\""));
    assert!(r.html.contains("width=\"800\""));
    assert!(r.html.contains("height=\"600\""));
    assert!(r.html.ends_with("/>") || r.html.contains("/>"));
}

#[test]
fn test_upload_result_video_html() {
    let r = fake_upload_result("video", "https://km.sankuai.com/api/file/cdn/123/456?contentType=video", "demo.mp4",
        &[("size", "10485760")]);
    assert!(r.html.contains("<km-video src=\""));
    assert!(r.html.contains("name=\"demo.mp4\""));
    assert!(r.html.contains("contentType=video"));
}

#[test]
fn test_upload_result_attachment_html() {
    let r = fake_upload_result("file", "https://km.sankuai.com/api/file/123/789", "report.pdf",
        &[("size", "1024")]);
    assert!(r.html.contains("<km-attachment src=\""));
    assert!(r.html.contains("name=\"report.pdf\""));
}

#[test]
fn test_upload_audio_html() {
    let r = fake_upload_result("audio", "https://cdn/a.mp3", "song.mp3", &[]);
    assert!(r.html.contains("<km-audio src=\""));
    assert!(r.html.contains("name=\"song.mp3\""));
}

// ── 历史版本数据解析 ──────────────────────────────────────────────────────

#[test]
fn test_parse_versions() {
    let raw = vec![
        serde_json::json!({"version":5,"stepVersion":42,"title":"2026/06/26","createTime":1782370000,"editors":[{"mis":"user000"}],"whatUpdate":"全量更新"}),
        serde_json::json!({"version":4,"stepVersion":38,"createTime":1782360000,"editors":[],"whatUpdate":""}),
    ];
    let versions = parse_versions(&raw);
    assert_eq!(versions.len(), 2);
    assert_eq!(versions[0].version, 5);
    assert_eq!(versions[0].step_version, 42);
    assert_eq!(versions[0].editors, "user000");
    assert_eq!(versions[0].note, "全量更新");
    assert_eq!(versions[1].title, "版本 4");
    assert_eq!(versions[1].editors, "");
}

#[test]
fn test_parse_versions_empty_editors() {
    let raw = vec![
        serde_json::json!({"version":1,"stepVersion":1,"createTime":0,"editors":null}),
    ];
    let versions = parse_versions(&raw);
    assert_eq!(versions[0].editors, "");
}

// ── 评论数据解析 ──────────────────────────────────────────────────────────

#[test]
fn test_parse_comments_with_replies() {
    let data = serde_json::json!({
        "firstLevelCommentCount": 1,
        "commentModels": [{
            "id": 100,
            "commentContent": "<p>顶层评论</p>",
            "commenter": "alice",
            "createTime": 1782370000,
            "subComments": [{"id":101,"commentContent":"<p>回复</p>","commenter":"bob","createTime":1782370001}]
        }]
    });
    let result = parse_comments(&data);
    assert_eq!(result.total, 1);
    assert_eq!(result.comments[0].text, "顶层评论");
    assert_eq!(result.comments[0].author, "alice");
    assert_eq!(result.comments[0].replies.len(), 1);
    assert_eq!(result.comments[0].replies[0].text, "回复");
}

#[test]
fn test_parse_comments_empty() {
    let data = serde_json::json!({"commentModels":[],"firstLevelCommentCount":0});
    let result = parse_comments(&data);
    assert_eq!(result.total, 0);
    assert_eq!(result.comments.len(), 0);
}

#[test]
fn test_parse_comments_null_subcomments() {
    let data = serde_json::json!({
        "commentModels": [{"id":1,"commentContent":"<p>评论</p>","commenter":"x","subComments":null}]
    });
    let result = parse_comments(&data);
    assert_eq!(result.comments[0].replies.len(), 0);
}

// ── 密级验证 ──────────────────────────────────────────────────────────────

#[test]
fn test_validate_secret_level_valid() {
    assert_eq!(validate_secret_level("2"), Ok(2));
    assert_eq!(validate_secret_level("3"), Ok(3));
    assert_eq!(validate_secret_level("4"), Ok(4));
}

#[test]
fn test_validate_secret_level_invalid() {
    assert!(validate_secret_level("1").is_err());
    assert!(validate_secret_level("5").is_err());
    assert!(validate_secret_level("C3").is_err());
    assert!(validate_secret_level("").is_err());
}

// ── recent 子命令解析 ─────────────────────────────────────────────────────

#[test]
fn test_parse_recent_no_args() {
    let result = parse_recent_args(&[]);
    assert_eq!(result.sub, "edit");
    assert_eq!(result.limit, 20);
}

#[test]
fn test_parse_recent_view_10() {
    let result = parse_recent_args(&["view".to_string(), "10".to_string()]);
    assert_eq!(result.sub, "view");
    assert_eq!(result.limit, 10);
}

#[test]
fn test_parse_recent_received_5() {
    let result = parse_recent_args(&["received".to_string(), "5".to_string()]);
    assert_eq!(result.sub, "received");
    assert_eq!(result.limit, 5);
}

#[test]
fn test_parse_recent_number_only() {
    let result = parse_recent_args(&["20".to_string()]);
    assert_eq!(result.sub, "edit");
    assert_eq!(result.limit, 20);
}

#[test]
fn test_parse_recent_edit() {
    let result = parse_recent_args(&["edit".to_string()]);
    assert_eq!(result.sub, "edit");
    assert_eq!(result.limit, 20);
}

#[test]
fn test_parse_recent_invalid_subcommand() {
    let result = parse_recent_args(&["invalid".to_string(), "10".to_string()]);
    assert_eq!(result.sub, "edit");
    assert_eq!(result.limit, 20);
}

// ── stepVersion 验证 ──────────────────────────────────────────────────────

#[test]
fn test_validate_step_version_zero() {
    assert_eq!(validate_step_version("0").unwrap(), 0);
}

#[test]
fn test_validate_step_version_normal() {
    assert_eq!(validate_step_version("72").unwrap(), 72);
}

#[test]
fn test_validate_step_version_invalid() {
    assert!(validate_step_version("abc").is_err());
}

#[test]
fn test_step_version_is_nan_fix() {
    let sv = 0;
    assert!(!sv.to_string().is_empty());
    assert_eq!(validate_step_version("0").unwrap(), 0);
}

// ── 上传节点 patch 全链路 ────────────────────────────────────────────────

use serde_json::json;
use km_ops::patch::apply_diff;

#[test]
fn test_upload_image_node_patched() {
    let doc = json!({
        "type": "doc",
        "content": [
            {"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"T"}]},
            {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"正文"}]}
        ]
    });
    let mock_diff = km_ops::diff::DiffResult {
        changed: vec![],
        deleted: vec![],
        added: vec![km_ops::diff::AddOp {
            tag: "img".into(),
            inner_html: "".into(),
            attrs: [("src".into(),"https://km.sankuai.com/api/file/123/456".into()),
                    ("alt".into(),"photo.png".into()),
                    ("width".into(),"100".into()),
                    ("height".into(),"100".into())].into_iter().collect(),
        }],
    };
    let patched = apply_diff(&doc, &mock_diff);
    assert_eq!(patched["content"].as_array().unwrap().len(), 3);
    let img = &patched["content"][2];
    assert_eq!(img["type"], "image");
    assert!(img["attrs"]["src"].as_str().unwrap().contains("km.sankuai.com"));
    assert_eq!(img["attrs"]["name"], "photo.png");
    assert_eq!(patched["content"][0]["attrs"]["nodeId"], "t");
    assert_eq!(patched["content"][1]["attrs"]["nodeId"], "p1");
}

use km_ops::render::render;
use km_ops::diff::diff;

fn insert_node_via_diff(html: &str, node_html: &str, doc: &serde_json::Value) -> (km_ops::diff::DiffResult, serde_json::Value) {
    let new_html = format!("{}\n{}", html, node_html);
    let d = diff(html, &new_html, doc);
    let patched = apply_diff(doc, &d);
    (d, patched)
}

#[test]
fn test_insert_image_via_update() {
    let base_doc = json!({"type":"doc","content":[
        {"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"T"}]},
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"正文"}]}
    ]});
    let r = render(&base_doc);
    let (d, patched) = insert_node_via_diff(
        &r.html,
        "<img src=\"https://km.sankuai.com/api/file/123/456\" alt=\"photo.png\" width=\"800\" height=\"600\"/>",
        &base_doc
    );
    assert_eq!(d.added.len(), 1);
    assert_eq!(patched["content"][2]["type"], "image");
    assert!(patched["content"][2]["attrs"]["src"].as_str().unwrap().contains("km.sankuai.com"));
}

#[test]
fn test_insert_attachment_via_update() {
    let base_doc = json!({"type":"doc","content":[
        {"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"T"}]},
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"正文"}]}
    ]});
    let r = render(&base_doc);
    let (d, patched) = insert_node_via_diff(
        &r.html,
        "<km-attachment src=\"https://km.sankuai.com/api/file/123/789\" name=\"report.pdf\" size=\"1024\"/>",
        &base_doc
    );
    assert_eq!(d.added.len(), 1);
    assert_eq!(patched["content"][2]["type"], "attachment");
    assert_eq!(patched["content"][2]["attrs"]["name"], "report.pdf");
}

#[test]
fn test_insert_video_via_update() {
    let base_doc = json!({"type":"doc","content":[
        {"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"T"}]},
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"正文"}]}
    ]});
    let r = render(&base_doc);
    let (d, patched) = insert_node_via_diff(
        &r.html,
        "<km-video src=\"https://km.sankuai.com/api/file/cdn/123/456?contentType=video\" name=\"demo.mp4\"/>",
        &base_doc
    );
    assert_eq!(d.added.len(), 1);
    assert_eq!(patched["content"][2]["type"], "video");
}

#[test]
fn test_insert_audio_via_update() {
    let base_doc = json!({"type":"doc","content":[
        {"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"T"}]},
        {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"正文"}]}
    ]});
    let r = render(&base_doc);
    let (d, patched) = insert_node_via_diff(
        &r.html,
        "<km-audio src=\"https://km.sankuai.com/api/file/cdn/123/789?contentType=audio\" name=\"song.mp3\"/>",
        &base_doc
    );
    assert_eq!(d.added.len(), 1);
    assert_eq!(patched["content"][2]["type"], "audio");
}

#[test]
fn test_terminal_node_inserted_before_footnote() {
    let doc = json!({
        "type": "doc",
        "content": [
            {"type":"title","attrs":{"nodeId":"t"},"content":[{"type":"text","text":"T"}]},
            {"type":"paragraph","attrs":{"nodeId":"p1"},"content":[{"type":"text","text":"正文"}]},
            {"type":"footnote_list","attrs":{"nodeId":"fn1"}}
        ]
    });
    let mock_diff = km_ops::diff::DiffResult {
        changed: vec![], deleted: vec![],
        added: vec![km_ops::diff::AddOp {
            tag: "p".into(), inner_html: "新段落".into(), attrs: Default::default(),
        }],
    };
    let patched = apply_diff(&doc, &mock_diff);
    let types: Vec<&str> = patched["content"].as_array().unwrap()
        .iter().map(|n| n["type"].as_str().unwrap_or("")).collect();
    let p_pos = types.iter().position(|&t| t == "paragraph").unwrap();
    let fn_pos = types.iter().position(|&t| t == "footnote_list").unwrap();
    assert!(p_pos < fn_pos);
    assert_eq!(types.last().copied(), Some("footnote_list"));
}
