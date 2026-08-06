// cli_utils.rs — 与 JS new-commands.test.js 对应的工具函数

/// 根据扩展名推断上传类型
pub fn infer_kind(file_path: &str) -> &str {
    let ext = file_path.split('.').last().unwrap_or("").to_lowercase();
    match ext.as_str() {
        "jpg" | "jpeg" | "png" | "gif" | "webp" | "svg" | "bmp" => "image",
        "mp4" | "mov" | "avi" | "mkv" | "webm" => "video",
        "mp3" | "aac" | "wav" | "ogg" | "flac" | "m4a" => "audio",
        _ => "file",
    }
}

/// 从 args 数组里取 --flag value
pub fn flag(args: &[String], name: &str) -> Option<String> {
    let i = args.iter().position(|a| a == name)?;
    args.get(i + 1).cloned()
}

#[derive(Debug, PartialEq, Eq)]
pub struct CreateInput {
    pub title: String,
    pub markdown: String,
    pub parent_id: Option<String>,
}

/// 解析 create 参数。
///
/// create 只接受 stdin Markdown，第一行必须是 `# 文档标题`。
/// `--parent` 可选；旧的 `--title` / `--type` 不再支持。
pub fn parse_create_input(args: &[String], stdin: &str) -> Result<CreateInput, String> {
    if args.iter().any(|a| a == "--title" || a == "--type") {
        return Err("用法: km create [--parent <父文档ID>] < /tmp/doc.md\n\ncreate 只接受 Markdown，第一行必须是一级标题：# 文档标题".to_string());
    }
    if stdin.trim().is_empty() {
        return Err("create 需要从 stdin 传入 Markdown，第一行必须是一级标题：# 文档标题".to_string());
    }
    let title = crate::md::title_from_md(stdin)
        .ok_or_else(|| "create 只接受 Markdown，第一行必须是一级标题：# 文档标题".to_string())?;
    let parent_id = if args.iter().any(|a| a == "--parent") {
        Some(flag(args, "--parent").ok_or_else(|| "用法: km create [--parent <父文档ID>] < /tmp/doc.md".to_string())?)
    } else {
        None
    };
    Ok(CreateInput {
        title,
        markdown: stdin.trim().to_string(),
        parent_id,
    })
}

/// 剥离 HTML 标签并反转义实体
pub fn strip_html(html: &str) -> String {
    let mut result = String::new();
    let mut in_tag = false;
    for ch in html.chars() {
        if ch == '<' {
            in_tag = true;
        } else if ch == '>' {
            in_tag = false;
        } else if !in_tag {
            result.push(ch);
        }
    }
    result = result.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&");
    result.trim().to_string()
}

/// HTML 转义 < > &
pub fn esc_html(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

/// 模拟上传结果
pub struct UploadResult {
    pub url: String,
    pub html: String,
}

pub fn fake_upload_result(kind: &str, url: &str, name: &str, extras: &[(&str, &str)]) -> UploadResult {
    let get = |k: &str| -> String {
        extras.iter().find(|(key, _)| *key == k).map(|(_, v)| v.to_string()).unwrap_or_default()
    };
    match kind.to_lowercase().as_str() {
        "image" => {
            let w = get("width");
            let h = get("height");
            let html = if w.is_empty() && h.is_empty() {
                format!("<img src=\"{url}\" alt=\"{name}\"/>")
            } else {
                format!("<img src=\"{url}\" alt=\"{name}\" width=\"{w}\" height=\"{h}\"/>")
            };
            UploadResult { url: url.into(), html }
        }
        "video" => {
            let size = get("size");
            let html = format!("<km-video src=\"{url}\" name=\"{name}\" size=\"{size}\"/>");
            UploadResult { url: url.into(), html }
        }
        "audio" => {
            let size = get("size");
            let html = format!("<km-audio src=\"{url}\" name=\"{name}\" size=\"{size}\"/>");
            UploadResult { url: url.into(), html }
        }
        _ => {
            let size = get("size");
            let html = format!("<km-attachment src=\"{url}\" name=\"{name}\" size=\"{size}\"/>");
            UploadResult { url: url.into(), html }
        }
    }
}

// ── 历史版本解析 ──────────────────────────────────────────────────────

#[derive(Debug, PartialEq)]
pub struct VersionInfo {
    pub version: i64,
    pub step_version: i64,
    pub title: String,
    pub created_at: i64,
    pub editors: String,
    pub note: String,
}

pub fn parse_versions(raw: &[serde_json::Value]) -> Vec<VersionInfo> {
    raw.iter().map(|v| {
        let version = v.get("version").and_then(|x| x.as_i64()).unwrap_or(0);
        let step_version = v.get("stepVersion").and_then(|x| x.as_i64()).unwrap_or(0);
        let title = v.get("title").and_then(|x| x.as_str()).unwrap_or("").to_string();
        let title = if title.is_empty() { format!("版本 {version}") } else { title };
        let created_at = v.get("createTime").and_then(|x| x.as_i64()).unwrap_or(0);
        let editors = v.get("editors").and_then(|x| x.as_array()).map(|arr| {
            arr.iter().filter_map(|e| e.get("mis").or_else(|| e.get("name")).and_then(|s| s.as_str()))
                .collect::<Vec<&str>>().join(", ")
        }).unwrap_or_default();
        let note = v.get("whatUpdate").and_then(|x| x.as_str()).unwrap_or("").to_string();
        VersionInfo { version, step_version, title, created_at, editors, note }
    }).collect()
}

// ── 评论解析 ──────────────────────────────────────────────────────────

#[derive(Debug, PartialEq)]
pub struct ReplyInfo {
    pub id: String,
    pub text: String,
    pub author: String,
}

#[derive(Debug, PartialEq)]
pub struct CommentInfo {
    pub id: String,
    pub text: String,
    pub author: String,
    pub replies: Vec<ReplyInfo>,
}

#[derive(Debug, PartialEq)]
pub struct CommentsResult {
    pub total: i64,
    pub comments: Vec<CommentInfo>,
}

pub fn parse_comments(data: &serde_json::Value) -> CommentsResult {
    let list = data.get("commentModels").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let total = data.get("firstLevelCommentCount").and_then(|v| v.as_i64()).unwrap_or(list.len() as i64);
    let comments = list.iter().map(|c| {
        let id = c.get("id").and_then(|v| v.as_i64()).unwrap_or(0).to_string();
        let text = strip_html(c.get("commentContent").and_then(|v| v.as_str()).unwrap_or(""));
        let author = c.get("commenter").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let replies = c.get("subComments").and_then(|v| v.as_array()).cloned().unwrap_or_default().iter().map(|r| {
            ReplyInfo {
                id: r.get("id").and_then(|v| v.as_i64()).unwrap_or(0).to_string(),
                text: strip_html(r.get("commentContent").and_then(|v| v.as_str()).unwrap_or("")),
                author: r.get("commenter").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            }
        }).collect();
        CommentInfo { id, text, author, replies }
    }).collect();
    CommentsResult { total, comments }
}

// ── 密级验证 ──────────────────────────────────────────────────────────

pub fn validate_secret_level(level: impl Into<String>) -> Result<i64, String> {
    let s: String = level.into();
    let lvl: i64 = s.parse().map_err(|_| "密级必须是数字".to_string())?;
    if ![2, 3, 4].contains(&lvl) {
        Err("密级必须是 2、3 或 4".to_string())
    } else {
        Ok(lvl)
    }
}

// ── recent 子命令解析 ──────────────────────────────────────────────────

#[derive(Debug, PartialEq)]
pub struct RecentArgs {
    pub sub: String,
    pub limit: i64,
}

pub fn parse_recent_args(args: &[String]) -> RecentArgs {
    let sub_is_first = !args.is_empty() && ["edit", "view", "received"].contains(&args[0].as_str());
    let sub = if sub_is_first {
        args[0].clone()
    } else {
        "edit".to_string()
    };
    let limit_raw = if sub_is_first {
        args.get(1).cloned().unwrap_or_default()
    } else {
        args.first().cloned().unwrap_or_default()
    };
    let limit = limit_raw.parse::<i64>().unwrap_or(20).max(1);
    RecentArgs { sub, limit }
}

// ── stepVersion 验证 ───────────────────────────────────────────────────

pub fn validate_step_version(arg: &str) -> Result<i64, String> {
    arg.parse::<i64>().map_err(|_| "stepVersion 必须是数字".to_string())
}
