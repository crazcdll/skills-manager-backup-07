use std::io::{self, Read};
use serde_json::Value;
use km_ops::{auth, api, render, diff, patch, cli_utils, md, validate};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("{}", HELP);
        std::process::exit(1);
    }

    let cmd = &args[1];
    let cmd_args = &args[2..];

    if cmd == "--help" || cmd == "-h" {
        eprintln!("{}", HELP);
        std::process::exit(0);
    }

    if cmd_args.contains(&"--help".to_string()) {
        show_command_help(cmd);
        std::process::exit(0);
    }

    // --mis 仅 login 命令需要；其他命令自动从缓存/配置发现 MIS
    let mis = if cmd == "login" {
        cli_utils::flag(cmd_args, "--mis").or_else(auth::current_mis)
    } else {
        auth::current_mis()
    };

    match cmd.as_str() {
        "login" => {
            eprintln!("正在登录...");
            match auth::login(mis.as_deref()) {
                Ok(_) => {
                    let ttl = auth::token_ttl(mis.as_deref());
                    println!("登录成功，有效期 {} 小时", ttl / 3600);
                }
                Err(e) => die(&format!("登录失败: {}", e)),
            }
            return;
        }
        _ => {}
    }

    let token = match auth::get_token(mis.as_deref()) {
        Ok(t) => t,
        Err(e) => die(&format!("认证失败: {}", e)),
    };

    let client = api::KmClient::new(token, mis);

    match cmd.as_str() {
        "read" => cmd_read(&client, cmd_args),
        "info" => cmd_info(&client, cmd_args),
        "update" => cmd_update(&client, cmd_args),
        "recent" => cmd_recent(&client, cmd_args),
        "versions" => cmd_versions(&client, cmd_args),
        "create" => cmd_create(&client, cmd_args),
        "ls" => cmd_ls(&client, cmd_args),
        "search" => cmd_search(&client, cmd_args),
        "rm" => cmd_rm(&client, cmd_args),
        "mv" => cmd_mv(&client, cmd_args),
        "upload" => cmd_upload(&client, cmd_args),
        "restore" => cmd_restore(&client, cmd_args),
        "comments" => cmd_comments(&client, cmd_args),
        "comment" => cmd_comment(&client, cmd_args),
        "secret" => cmd_secret(&client, cmd_args),
        "copy" => cmd_copy(&client, cmd_args),
        "undelete" => cmd_undelete(&client, cmd_args),
        "mentioned" => cmd_mentioned(&client, cmd_args),
        "commented" => cmd_commented(&client, cmd_args),
        "square" => cmd_square(&client, cmd_args),
        "discussions" => cmd_discussions(&client, cmd_args),
        "reply-discussion" => cmd_reply_discussion(&client, cmd_args),
        "perms" => cmd_perms(&client, cmd_args),
        "grant" => cmd_grant(&client, cmd_args),
        "revoke" => cmd_revoke(&client, cmd_args),
        "download" => cmd_download(&client, cmd_args),
        "template" => cmd_template(cmd_args),
        _ => {
            eprintln!("未知命令: {}", cmd);
            eprintln!("{}", HELP);
            std::process::exit(1);
        }
    }
}

/// 提交前 normalize + 结构校验。有问题直接打印并退出，不提交。
fn normalize_and_validate_or_die(doc: &mut Value, hint: &str) {
    validate::normalize_document_json(doc);
    let vr = validate::validate_document_json(doc);
    if !vr.valid {
        eprintln!("[校验失败] PM JSON 结构不合法（共 {} 个问题）：", vr.errors.len());
        for e in vr.errors.iter().take(10) { eprintln!("  - {}", e); }
        die(hint);
    }
}

fn format_diff_output(diff_result: &diff::DiffResult, original_doc: &Value) -> String {
    let mut lines: Vec<String> = Vec::new();

    // 实际文档树：get_doc 返回 {body:{content:[...]}}，递归 diff 传入的是 {content:[...]}
    let doc_tree = original_doc.get("body").unwrap_or(original_doc);

    let node_html = |pm_node_id: Option<&str>| -> Option<String> {
        let id = pm_node_id?;
        let node = patch::find_by_node_id(doc_tree, id)?;
        let wrapper = serde_json::json!({"type": "doc", "content": [node.clone()]});
        let result = render::render(&wrapper);
        Some(result.html.trim().chars().take(120).collect())
    };

    let new_html = |tag: &str, inner: &str| -> String {
        if inner.is_empty() {
            format!("<{}/>", tag)
        } else {
            format!("<{}>{}</{}>", tag, inner.chars().take(120).collect::<String>(), tag)
        }
    };

    // deep container：内部递归 diff，展示细粒度变更（如 table 内 +<tr>）
    let deep_tags = ["table", "blockquote", "km-note", "km-collapse", "ul", "ol"];
    // 从 original_doc 取 old 节点：优先 nodeId，其次 old_idx
    let old_node_for = |c: &diff::ChangeOp| -> Option<Value> {
        if let Some(id) = c.pm_node_id.as_deref() {
            if let Some(n) = patch::find_by_node_id(doc_tree, id) {
                return Some(n.clone());
            }
        }
        // 用 old_idx 从顶层 content 取
        if let Some(idx) = c.old_idx {
            let content = doc_tree.get("content").and_then(|v| v.as_array())?;
            return content.get(idx).cloned();
        }
        None
    };
    for c in &diff_result.changed {
        // 对 deep container 递归展示内部 diff
        if deep_tags.contains(&c.tag.as_str()) {
            let old_node_opt = old_node_for(c);
            if let Some(old_node) = old_node_opt {
                let wrapper = serde_json::json!({"type": "doc", "content": [old_node.clone()]});
                let old_inner = render::render(&wrapper).html;
                let inner_diff = diff::diff(&old_inner, &c.inner_html, &old_node);
                let inner_total = inner_diff.changed.len() + inner_diff.deleted.len() + inner_diff.added.len();
                if inner_total > 0 {
                    let inner_doc = serde_json::json!({"type": "doc", "content": [old_node.clone()]});
                    let sub = format_diff_output(&inner_diff, &inner_doc);
                    for l in sub.lines() {
                        lines.push(format!("  {}", l));
                    }
                    continue;
                }
            }
        }
        // 非 deep container，或递归 diff 为空：原样展示整节点
        if let Some(old) = node_html(c.pm_node_id.as_deref()) {
            lines.push(format!("- {}", old));
        }
        lines.push(format!("+ {}", new_html(&c.tag, &c.inner_html)));
    }
    for id in &diff_result.deleted {
        match node_html(id.pm_node_id.as_deref()) {
            Some(html) => lines.push(format!("- {}", html)),
            None => lines.push("- (删除)".to_string()),
        }
    }
    for a in &diff_result.added {
        lines.push(format!("+ {}", new_html(&a.tag, &a.inner_html)));
    }

    if lines.is_empty() {
        lines.push("(无变化)".to_string());
    }
    lines.join("\n") + "\n"
}

fn cmd_read(client: &api::KmClient, args: &[String]) {
    if args.is_empty() {
        die("用法: km read <docid>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };

    let raw_json = args.contains(&"--raw-json".to_string());

    match client.get_doc(&id) {
        Ok(doc) => {
            if raw_json {
                let body = doc.get("body").cloned().unwrap_or(Value::Null);
                print!("{}", serde_json::to_string_pretty(&body).unwrap_or_default());
                return;
            }
            if doc.get("v1").and_then(|v| v.as_bool()).unwrap_or(false) {
                let raw = doc.get("rawHtml").and_then(|v| v.as_str()).unwrap_or("(空文档)");
                print!("{}", raw);
                return;
            }
            let body = doc.get("body").cloned().unwrap_or(Value::Null);
            let result = render::render(&body);
            print!("{}", result.html);
            // stderr 提示文档里的可下载资源
            let resources = extract_downloadable_resources(&result.html);
            if !resources.is_empty() {
                eprintln!("\n[提示] 文档含 {} 个可下载资源，用 km download <url> 下载：", resources.len());
                for (kind, url) in resources.iter().take(10) {
                    eprintln!("  [{}] {}", kind, url);
                }
                if resources.len() > 10 {
                    eprintln!("  ... 还有 {} 个", resources.len() - 10);
                }
            }
        }
        Err(e) => die(&format!("读取文档失败: {}", e)),
    }
}

fn cmd_info(client: &api::KmClient, args: &[String]) {
    if args.is_empty() {
        die("用法: km info <docid>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };

    let meta = match client.get_doc_meta(&id) {
        Ok(m) => m,
        Err(e) => die(&format!("读取元信息失败: {}", e)),
    };
    let stats = client.get_doc_stats(&id).unwrap_or(Value::Null);

    let cid = meta.get("contentId").and_then(|v| v.as_str()).unwrap_or(&id);
    println!("标题：{}", meta.get("title").and_then(|v| v.as_str()).unwrap_or(""));
    println!("ID：{}", cid);
    println!("链接：https://km.sankuai.com/collabpage/{}", cid);
    println!("创建者：{}", meta.get("creator").and_then(|v| v.as_str()).unwrap_or("-"));
    if let Some(owner) = meta.get("owner").and_then(|v| v.as_str()) {
        if !owner.is_empty() { println!("所有者：{}", owner); }
    }
    let created = meta.get("createdAt").and_then(|v| v.as_i64()).unwrap_or(0);
    let updated = meta.get("updatedAt").and_then(|v| v.as_i64()).unwrap_or(0);
    println!("创建时间：{}", if created > 0 { format_ts(created) } else { "-".to_string() });
    println!("更新时间：{}", if updated > 0 { format_ts(updated) } else { "-".to_string() });
    let parent = meta.get("parentId").and_then(|v| v.as_str()).unwrap_or("0");
    println!("父文档：{}", if parent == "0" { "（空间根目录）".to_string() } else { parent.to_string() });
    let view_count = stats.get("viewCount").and_then(|v| v.as_i64()).unwrap_or(0);
    let viewer_count = stats.get("viewerCount").and_then(|v| v.as_i64()).unwrap_or(0);
    let comment_count = stats.get("commentCount").and_then(|v| v.as_i64()).unwrap_or(0);
    let follower_count = stats.get("followerCount").and_then(|v| v.as_i64()).unwrap_or(0);
    println!("浏览：{} 次 / {} 人  评论：{} 条  关注：{} 人", view_count, viewer_count, comment_count, follower_count);
}

fn format_ts(ms: i64) -> String {
    let secs = ms / 1000;
    let y = 1970 + secs / 31_536_000;
    let rem = secs % 31_536_000;
    let m = rem / 2_592_000 + 1;
    let d = (rem % 2_592_000) / 86400 + 1;
    let h = (secs % 86400) / 3600;
    let min = (secs % 3600) / 60;
    format!("{}/{}/{} {:02}:{:02}", y, m, d, h, min)
}

fn cmd_update(client: &api::KmClient, args: &[String]) {
    let id_arg = args.iter().find(|a| !a.starts_with("--") && a.as_str() != "markdown" && a.as_str() != "html");
    let id = match id_arg {
        Some(a) => match api::extract_id(a) { Ok(id) => id, Err(e) => die(&e) },
        None => die("用法: km update <docid> [--dry-run]"),
    };
    let dry_run = args.contains(&"--dry-run".to_string());

    let old_doc = match client.get_doc(&id) {
        Ok(d) => d,
        Err(e) => die(&format!("读取文档失败: {}", e)),
    };

    if old_doc.get("v1").and_then(|v| v.as_bool()).unwrap_or(false) {
        die("该文档是 1.0 旧版格式，暂不支持更新");
    }

    let mut stdin_data = String::new();
    if io::stdin().read_to_string(&mut stdin_data).is_err() {
        die("读取 stdin 失败");
    }
    if stdin_data.trim().is_empty() {
        die("stdin 为空，请把 HTML 传入");
    }

    // update 只接受 HTML（增量 patch）；markdown 仅 create 支持
    let new_html = stdin_data;
    if !new_html.contains('<') {
        die("内容不含 HTML 标签。update 只接受 HTML；如需用 markdown 请用 km create --type markdown 新建");
    }
    // HTML 里的本地图片也上传替换
    let new_html = match client.replace_images(&id, &new_html) {
        Ok(s) => s,
        Err(e) => die(&format!("处理图片失败: {e}")),
    };

    let old_body = old_doc.get("body").cloned().unwrap_or(Value::Null);
    let old_result = render::render(&old_body);
    let diff_result = diff::diff(&old_result.html, &new_html, &old_body);

    let total_changed = diff_result.changed.len();
    let total_deleted = diff_result.deleted.len();
    let total_added = diff_result.added.len();

    if total_changed == 0 && total_deleted == 0 && total_added == 0 {
        eprintln!("内容无变化，跳过写入");
        return;
    }

    let mut patched = patch::apply_diff(&old_body, &diff_result);

    normalize_and_validate_or_die(&mut patched, "请修正 HTML 后重试（常见问题：video/audio 不能放在 <p> 里；<img> 必须有 src）");

    if dry_run {
        eprintln!("[dry-run] {} 修改，{} 删除，{} 新增", total_changed, total_deleted, total_added);
        print!("{}", format_diff_output(&diff_result, &old_doc));
        return;
    }

    if total_deleted > 0 {
        let ver = old_doc.get("stepVersion").and_then(|v| v.as_i64()).unwrap_or(0);
        eprintln!("[提示] 删除 {} 个节点，误操作可用 km restore {} {} 还原", total_deleted, id, ver);
    }

    let step_version = old_doc.get("stepVersion").and_then(|v| v.as_i64());
    match client.update_doc(&id, &patched, step_version) {
        Ok(url) => {
            eprintln!("已更新：{}", url);
            match client.get_doc(&id) {
                Ok(saved_doc) => {
                    let saved_body = saved_doc.get("body").cloned().unwrap_or(Value::Null);
                    let real_diff = diff::diff(&old_result.html, &render::render(&saved_body).html, &old_doc);
                    print!("{}", format_diff_output(&real_diff, &old_doc));
                }
                Err(_) => print!("{}", format_diff_output(&diff_result, &old_doc)),
            }
        }
        Err(e) => die(&format!("更新失败: {}", e)),
    }
}

fn cmd_recent(client: &api::KmClient, args: &[String]) {
    let parsed = cli_utils::parse_recent_args(args);
    let limit = parsed.limit as u32;

    let result = match parsed.sub.as_str() {
        "view" => client.recent_viewed(limit),
        "received" => client.received_docs(limit),
        _ => client.recent_edits(limit),
    };

    match result {
        Ok(data) => {
            let empty = vec![];
            let docs = data.as_array().unwrap_or(&empty);
            if docs.is_empty() {
                println!("没有找到文档");
                return;
            }
            for doc in docs {
                let id = doc.get("contentId").and_then(|v| v.as_str()).unwrap_or("?");
                let title = doc.get("title").and_then(|v| v.as_str()).unwrap_or("无标题");
                let default_url = format!("https://km.sankuai.com/collabpage/{}", id);
                let url = doc.get("url").and_then(|v| v.as_str()).unwrap_or(&default_url);
                if parsed.sub == "received" {
                    let sender = doc.get("sender").and_then(|v| v.as_str()).unwrap_or("");
                    println!("{}\t{}\t{}\t来自：{}", id, title, url, sender);
                } else {
                    println!("{}\t{}\t{}", id, title, url);
                }
            }
        }
        Err(e) => die(&format!("获取最近文档失败: {}", e)),
    }
}

fn cmd_versions(client: &api::KmClient, args: &[String]) {
    if args.is_empty() {
        die("用法: km versions <docid>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };

    match client.get_versions(&id) {
        Ok(data) => {
            let empty = vec![];
            let versions = cli_utils::parse_versions(data.as_array().unwrap_or(&empty));
            if versions.is_empty() {
                println!("（无历史版本）");
                return;
            }
            for v in versions {
                println!("v{}\tstep:{}\t{}\t{}\t{}", v.version, v.step_version, v.title, v.editors, v.note);
            }
        }
        Err(e) => die(&format!("获取版本历史失败: {}", e)),
    }
}

fn cmd_create(client: &api::KmClient, args: &[String]) {
    let mut stdin_data = String::new();
    let _ = io::stdin().read_to_string(&mut stdin_data);
    let create_input = cli_utils::parse_create_input(args, &stdin_data).unwrap_or_else(|e| die(&e));

    let (created_id, url) = match client.create_doc(&create_input.title, None, create_input.parent_id.as_deref()) {
        Ok((id, u)) => (id, u),
        Err(e) => die(&format!("创建失败: {}", e)),
    };

    let md_content = match client.replace_images(&created_id, &create_input.markdown) {
        Ok(s) => s,
        Err(e) => die(&format!("处理图片失败: {e}")),
    };
    let mut pm_json = md::md_to_pm(&md_content, &create_input.title);
    normalize_and_validate_or_die(&mut pm_json, "请修正 markdown 内容后重试");
    match client.get_doc(&created_id) {
        Ok(empty_doc) => {
            let sv = empty_doc.get("stepVersion").and_then(|v| v.as_i64());
            if let Err(e) = client.update_doc(&created_id, &pm_json, sv) {
                die(&format!("写入 markdown 失败: {}", e));
            }
        }
        Err(e) => die(&format!("读取新建文档失败: {}", e)),
    }

    eprintln!("已创建：{}", url);

    match client.get_doc(&created_id) {
        Ok(new_doc) => {
            let body = new_doc.get("body").cloned().unwrap_or(Value::Null);
            let result = render::render(&body);
            if !result.html.is_empty() {
                print!("{}", result.html);
            }
        }
        Err(e) => eprintln!("读取新建文档失败: {}", e),
    }
}

fn cmd_ls(client: &api::KmClient, args: &[String]) {
    // 不带参数：列出当前用户个人空间根目录的文档
    // 带参数：列出指定文档的子文档
    let result = if args.is_empty() {
        let space_id = match client.get_personal_space_id() {
            Ok(s) => s,
            Err(e) => die(&format!("获取个人空间失败: {e}")),
        };
        client.list_space_root(&space_id)
    } else {
        let id = match api::extract_id(&args[0]) {
            Ok(id) => id,
            Err(e) => die(&e),
        };
        client.list_children(&id)
    };

    match result {
        Ok(data) => {
            let empty = vec![];
            let children = data.as_array().unwrap_or(&empty);
            if children.is_empty() {
                println!("（无文档）");
            } else {
                for child in children {
                    // contentId 可能是数字或字符串
                    let cid = child.get("contentId")
                        .and_then(|v| v.as_i64().map(|n| n.to_string()).or_else(|| v.as_str().map(String::from)))
                        .unwrap_or_default();
                    let title = child.get("title").and_then(|v| v.as_str()).unwrap_or("");
                    let child_count = child.get("childCount").and_then(|v| v.as_i64()).unwrap_or(0);
                    if child_count > 0 {
                        println!("{}\t{}\t(子文档:{})", cid, title, child_count);
                    } else {
                        println!("{}\t{}", cid, title);
                    }
                }
            }
        }
        Err(e) => die(&format!("列出文档失败: {}", e)),
    }
}

fn cmd_search(client: &api::KmClient, args: &[String]) {
    let keyword = cli_utils::flag(args, "--keyword").or_else(|| {
        if args.is_empty() { None } else { Some(args.iter().filter(|a| !a.starts_with("--")).next().unwrap_or(&"".to_string()).clone()) }
    }).unwrap_or_default();
    if keyword.is_empty() {
        die("用法: km search --keyword <关键词>");
    }
    match client.search_docs(&keyword, 20) {
        Ok(data) => {
            let empty = vec![];
            let results = data.as_array().unwrap_or(&empty);
            if results.is_empty() {
                println!("无结果");
            } else {
                for r in results {
                    let id = api::content_id_to_string(r.get("contentId").unwrap_or(&Value::Null));
                    let title = r.get("title").and_then(|v| v.as_str()).unwrap_or("");
                    println!("{}\t{}", id, title);
                    if let Some(snippet) = r.get("snippet").and_then(|v| v.as_str()) {
                        println!("  {}", &snippet[..snippet.len().min(80)]);
                    }
                }
            }
        }
        Err(e) => die(&format!("搜索失败: {}", e)),
    }
}

fn cmd_rm(client: &api::KmClient, args: &[String]) {
    if args.is_empty() {
        die("用法: km rm <docid>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    match client.get_doc_meta(&id) {
        Ok(meta) => {
            let title = meta.get("title").and_then(|v| v.as_str()).unwrap_or(&id);
            eprint!("[警告] 确认删除「{}」({})?  [y/N] ", title, id);
            use std::io::Write;
            std::io::stderr().flush().ok();
            let mut buf = String::new();
            if io::stdin().read_line(&mut buf).is_ok() && buf.to_lowercase().starts_with('y') {
                match client.delete_doc(&id) {
                    Ok(_) => println!("已删除 {}", id),
                    Err(e) => die(&format!("删除失败: {}", e)),
                }
            } else {
                println!("取消");
            }
        }
        Err(e) => die(&format!("查询失败: {}", e)),
    }
}

fn cmd_mv(client: &api::KmClient, args: &[String]) {
    if args.len() < 2 {
        die("用法: km mv <docid> <parentid>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let parent_id = match api::extract_id(&args[1]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    match client.move_doc(&id, &parent_id) {
        Ok(_) => println!("已移动 {} 到 {} 下", id, parent_id),
        Err(e) => die(&format!("移动失败: {}", e)),
    }
}

fn cmd_upload(client: &api::KmClient, args: &[String]) {
    if args.len() < 2 {
        die("用法: km upload <docid> <file-path>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let path = &args[1];
    let bytes = std::fs::read(path).unwrap_or_else(|e| die(&format!("读文件失败: {e}")));
    let ext = path.split('.').last().unwrap_or("").to_lowercase();

    // 自动推断类型：svg/xml 靠内容检测，其他靠扩展名
    let kind = infer_upload_kind(&ext, &bytes);
    let result = match kind.as_str() {
        "drawio" => {
            // drawio svg（含 content/mxfile）直接上传；mxfile 源文件需包装（暂不支持）
            if !is_drawio_svg(&bytes) {
                die("drawio 源文件（mxfile/mxGraphModel）暂不支持，请上传 drawio SVG（含 content 属性，可由 km download 下载获得）");
            }
            client.upload_drawio(&id, bytes)
        }
        "image" => client.upload_image(&id, bytes, path),
        "video" | "audio" => client.upload_media(&id, bytes, path, &kind),
        _ => client.upload_attachment(&id, bytes, path),
    };
    match result {
        Ok((cdn_url, _w, _h)) => {
            let label = match kind.as_str() {
                "drawio" => "Drawio 流程图", "image" => "图片",
                "video" => "视频", "audio" => "音频", _ => "附件",
            };
            eprintln!("[{}] 上传成功：{}", label, cdn_url);
            // 输出可插入文档的 HTML 节点
            let node = match kind.as_str() {
                "drawio" => format!("<km-drawio src=\"{}\"/>", cdn_url),
                "image" => format!("<img src=\"{}\"/>", cdn_url),
                "video" => format!("<km-video src=\"{}\"/>", cdn_url),
                "audio" => format!("<km-audio src=\"{}\"/>", cdn_url),
                _ => format!("<km-attachment src=\"{}\"/>", cdn_url),
            };
            println!("{}", node);
            eprintln!("将此节点原样插入文档 HTML（不包在 <p> 里），再 km update 写回");
        }
        Err(e) => die(&format!("上传失败: {}", e)),
    }
}

/// 根据扩展名和文件内容推断上传类型
fn infer_upload_kind(ext: &str, bytes: &[u8]) -> String {
    match ext {
        "svg" | "xml" | "drawio" => {
            // 检测内容：有 content=mxfile 或直接是 mxfile/mxGraphModel → drawio
            if is_drawio_content(bytes) { "drawio".to_string() } else { "image".to_string() }
        }
        "jpg" | "jpeg" | "png" | "gif" | "webp" | "bmp" => "image".to_string(),
        "mp4" | "mov" | "avi" | "mkv" | "webm" => "video".to_string(),
        "mp3" | "aac" | "wav" | "ogg" | "flac" | "m4a" => "audio".to_string(),
        _ => "file".to_string(),
    }
}

/// 检测是否是 drawio svg（含 content 属性且内嵌 mxfile）
fn is_drawio_svg(bytes: &[u8]) -> bool {
    let s = String::from_utf8_lossy(bytes);
    s.contains("<svg") && s.contains("content=") && s.contains("mxfile")
}

/// 检测是否是 drawio 内容（drawio svg / mxfile / mxGraphModel / mxCell）
fn is_drawio_content(bytes: &[u8]) -> bool {
    let s = String::from_utf8_lossy(bytes);
    (s.contains("<svg") && s.contains("content=") && s.contains("mxfile"))
        || s.contains("<mxfile") || s.contains("<mxGraphModel") || s.contains("<mxCell")
}

fn cmd_restore(client: &api::KmClient, args: &[String]) {
    if args.len() < 2 {
        die("用法: km restore <docid> <stepVersion>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let sv = match args[1].parse::<i64>() {
        Ok(v) => v,
        Err(_) => die("stepVersion 必须是数字"),
    };
    match client.get_version_content(&id, sv) {
        Ok(data) => {
            let body = data.get("body").cloned().unwrap_or(Value::Null);
            if body.is_null() {
                die("该版本内容无法获取（可能是 1.0 文档）");
            }
            // restore 把旧版本内容写回当前文档，必须用当前最新的 stepVersion，
            // 而非要还原到的目标版本号 sv
            let cur_step = match client.get_doc(&id) {
                Ok(cur) => cur.get("stepVersion").and_then(|v| v.as_i64()),
                Err(_) => None,
            };
            let mut body = body;
            normalize_and_validate_or_die(&mut body, "历史版本内容有问题，还原已取消");
            match client.update_doc(&id, &body, cur_step) {
                Ok(url) => println!("已还原到版本 step:{}，请刷新页面：{}", sv, url),
                Err(e) => die(&format!("还原失败: {}", e)),
            }
        }
        Err(e) => die(&format!("获取版本失败: {}", e)),
    }
}

fn cmd_comments(client: &api::KmClient, args: &[String]) {
    if args.is_empty() {
        die("用法: km comments <docid>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let limit = cli_utils::flag(args, "--limit").and_then(|v| v.parse::<u32>().ok()).unwrap_or(20);
    match client.get_comments(&id, limit) {
        Ok(data) => {
            let result = cli_utils::parse_comments(&data);
            eprintln!("共 {} 条评论，显示前 {} 条", result.total, result.comments.len());
            for c in &result.comments {
                println!("[{}] {}: {}", c.id, c.author, c.text);
                for r in &c.replies {
                    println!("  └─ [{}] {}: {}", r.id, r.author, r.text);
                }
            }
        }
        Err(e) => die(&format!("获取评论失败: {}", e)),
    }
}

fn cmd_comment(client: &api::KmClient, args: &[String]) {
    if args.len() < 2 {
        die("用法: km comment <docid> \"内容\" [--reply <commentId>]");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let text = args[1].clone();
    let reply_id = cli_utils::flag(args, "--reply");
    match client.add_comment(&id, &text, reply_id.as_deref()) {
        Ok(cid) => println!("评论已发布（id: {}）", cid),
        Err(e) => die(&format!("发布失败: {}", e)),
    }
}

fn cmd_secret(client: &api::KmClient, args: &[String]) {
    if args.len() < 2 {
        die("用法: km secret <docid> <2|3|4>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let level = &args[1];
    match client.set_secret_level(&id, level) {
        Ok(_) => {
            let labels = [("2", "C2内部公开"), ("3", "C3内部敏感"), ("4", "C4内部机密")];
            let label = labels.iter().find(|(l, _)| l == level).map(|(_, n)| *n).unwrap_or("未知");
            println!("已设置密级: {}", label);
        }
        Err(e) => die(&format!("设置失败: {}", e)),
    }
}

fn cmd_copy(client: &api::KmClient, args: &[String]) {
    if args.is_empty() {
        die("用法: km copy <source-id> <new-title> [--to <parentid>]");
    }
    let source_id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let title = if args.len() > 1 { args[1].clone() } else { die("需要新标题") };
    let parent_id = cli_utils::flag(args, "--to");
    match client.create_from_template(&title, &source_id, parent_id.as_deref()) {
        Ok((_id, url)) => println!("已复制: {}", url),
        Err(e) => die(&format!("复制失败: {}", e)),
    }
}

fn cmd_undelete(client: &api::KmClient, args: &[String]) {
    if args.is_empty() {
        die("用法: km undelete <docid>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    match client.restore_doc(&id) {
        Ok(_) => println!("已恢复文档 {}", id),
        Err(e) => die(&format!("恢复失败: {}", e)),
    }
}

fn cmd_mentioned(client: &api::KmClient, args: &[String]) {
    let limit = args.get(0).and_then(|v| v.parse::<u32>().ok()).unwrap_or(20);
    match client.mentioned_docs(limit) {
        Ok(data) => {
            let empty = vec![];
            let docs = data.as_array().unwrap_or(&empty);
            if docs.is_empty() { println!("（无结果）"); return; }
            for d in docs {
                let id = d.get("contentId").and_then(|v| v.as_i64().map(|n| n.to_string()).or_else(|| v.as_str().map(String::from))).unwrap_or_default();
                let title = d.get("title").and_then(|v| v.as_str()).unwrap_or("");
                let url = d.get("url").and_then(|v| v.as_str()).unwrap_or("");
                let count = d.get("mentionCount").and_then(|v| v.as_i64()).unwrap_or(0);
                println!("{}\t{}\t{}\t@{}次", id, title, url, count);
            }
        }
        Err(e) => die(&format!("获取失败: {}", e)),
    }
}

fn cmd_commented(client: &api::KmClient, args: &[String]) {
    let limit = args.get(0).and_then(|v| v.parse::<u32>().ok()).unwrap_or(20);
    match client.commented_docs(limit) {
        Ok(data) => {
            let empty = vec![];
            let docs = data.as_array().unwrap_or(&empty);
            if docs.is_empty() { println!("（无结果）"); return; }
            for d in docs {
                let id = d.get("contentId").and_then(|v| v.as_i64().map(|n| n.to_string()).or_else(|| v.as_str().map(String::from))).unwrap_or_default();
                let title = d.get("title").and_then(|v| v.as_str()).unwrap_or("");
                let url = d.get("url").and_then(|v| v.as_str()).unwrap_or("");
                let count = d.get("commentCount").and_then(|v| v.as_i64()).unwrap_or(0);
                println!("{}\t{}\t{}\t评论{}次", id, title, url, count);
            }
        }
        Err(e) => die(&format!("获取失败: {}", e)),
    }
}

fn cmd_square(client: &api::KmClient, args: &[String]) {
    let kind = if args.is_empty() || args[0] == "recommend" { 2 } else { 3 };
    let limit = if args.is_empty() {
        20
    } else if args[0] == "recommend" || args[0] == "latest" {
        args.get(1).and_then(|v| v.parse::<u32>().ok()).unwrap_or(20)
    } else {
        args.get(0).and_then(|v| v.parse::<u32>().ok()).unwrap_or(20)
    };
    match client.knowledge_square(kind, limit) {
        Ok(data) => {
            let empty = vec![];
            let articles = data.as_array().unwrap_or(&empty);
            if articles.is_empty() { println!("（无结果）"); return; }
            for a in articles {
                let id = a.get("articleId").and_then(|v| v.as_i64().map(|n| n.to_string()).or_else(|| v.as_str().map(String::from))).unwrap_or_default();
                let title = a.get("title").and_then(|v| v.as_str()).unwrap_or("");
                let url = a.get("url").and_then(|v| v.as_str()).unwrap_or("");
                let creator = a.get("creator").and_then(|v| v.as_str()).unwrap_or("");
                println!("{}\t{}\t{}\t{}", id, title, url, creator);
            }
        }
        Err(e) => die(&format!("获取失败: {}", e)),
    }
}

fn cmd_discussions(client: &api::KmClient, args: &[String]) {
    if args.is_empty() {
        die("用法: km discussions <docid> [--limit 20]");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let limit = cli_utils::flag(args, "--limit").and_then(|v| v.parse::<u32>().ok()).unwrap_or(20);
    match client.get_discussions(&id, limit) {
        Ok(data) => {
            let empty_vec = vec![];
            let discussions = data.get("discussions")
                .and_then(|v| v.as_array())
                .unwrap_or_else(|| data.get("commentModels").and_then(|v| v.as_array()).unwrap_or(&empty_vec));
            let total = data.get("total").and_then(|v| v.as_i64())
                .or_else(|| data.get("firstLevelCommentCount").and_then(|v| v.as_i64()))
                .unwrap_or(discussions.len() as i64);
            eprintln!("共 {} 条划词评论，显示前 {} 条", total, discussions.len());
            for d in discussions {
                let did = d.get("discussionId").and_then(|v| v.as_str()).unwrap_or("");
                let resolved = d.get("resolved").and_then(|v| v.as_bool()).unwrap_or(false);
                let status = if resolved { "✓已解决" } else { "○未解决" };
                let quote: String = d.get("quoteContent").and_then(|v| v.as_str()).unwrap_or("").chars().take(40).collect();
                println!("[{}] {} 引用：\"{}\"", did, status, quote);
                if let Some(comments) = d.get("comments").and_then(|v| v.as_array()) {
                    for c in comments {
                        let cid = c.get("commentId").and_then(|v| v.as_str()).unwrap_or("");
                        let author = c.get("author").and_then(|v| v.as_str()).unwrap_or("");
                        let text: String = c.get("text").and_then(|v| v.as_str()).unwrap_or("").chars().take(80).collect();
                        println!("  [{}] {}：{}", cid, author, text);
                    }
                }
            }
        }
        Err(e) => die(&format!("获取失败: {}", e)),
    }
}

fn cmd_reply_discussion(client: &api::KmClient, args: &[String]) {
    if args.len() < 4 {
        die("用法: km reply-discussion <docid> <discussionId> <quoteId> <text>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let discussion_id = &args[1];
    let quote_id = &args[2];
    let text = args[3..].join(" ");
    match client.reply_discussion(&id, discussion_id, quote_id, &text) {
        Ok(cid) => println!("已回复（id: {}）", cid),
        Err(e) => die(&format!("回复失败: {}", e)),
    }
}

fn cmd_perms(client: &api::KmClient, args: &[String]) {
    if args.is_empty() {
        die("用法: km perms <docid> [--page 1]");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let page = cli_utils::flag(args, "--page").and_then(|v| v.parse::<u32>().ok()).unwrap_or(1);
    match client.query_permissions(&id, page) {
        Ok(data) => {
            let result = data.get("total").and_then(|v| v.as_i64()).unwrap_or(0);
            eprintln!("共 {} 条权限记录", result);
            let empty = vec![];
            let records = data.get("records").and_then(|v| v.as_array()).unwrap_or(&empty);
            let perm_label = |gt: i64| match gt {
                5 => "仅浏览",
                0 => "可浏览、评论",
                2 => "可编辑",
                3 => "可编辑、添加",
                1 => "可编辑、添加、删除",
                4 => "可管理",
                _ => "未知",
            };
            for r in records {
                let perm_id = r.get("permId").and_then(|v| v.as_i64().map(|n| n.to_string()).or_else(|| v.as_str().map(String::from))).unwrap_or_default();
                let gt = r.get("permGroupType").and_then(|v| v.as_i64()).unwrap_or(-1);
                // 被授权人：优先 mis，其次 mail/orgFullName/xmGroupName/permMainBody
                let subject = r.get("mis").and_then(|v| v.as_str())
                    .or_else(|| r.get("mail").and_then(|v| v.as_str()))
                    .or_else(|| r.get("orgFullName").and_then(|v| v.as_str()))
                    .or_else(|| r.get("xmGroupName").and_then(|v| v.as_str()))
                    .or_else(|| r.get("permMainBody").and_then(|v| v.as_str()))
                    .unwrap_or("");
                println!("[{}] {}\t{}", perm_id, perm_label(gt), subject);
            }
        }
        Err(e) => die(&format!("查询失败: {}", e)),
    }
}

fn cmd_grant(client: &api::KmClient, args: &[String]) {
    if args.len() < 2 {
        die("用法: km grant <docid> <perm> --mis <mis>|--group <xmGroupId>|--mail <mail>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let perm = &args[1];
    let mis = cli_utils::flag(args, "--mis");
    let group = cli_utils::flag(args, "--group");
    let mail = cli_utils::flag(args, "--mail");
    if mis.is_none() && group.is_none() && mail.is_none() {
        die("需要指定 --mis、--group 或 --mail");
    }
    match client.grant_permission(&id, perm, mis.as_deref(), group.as_deref(), mail.as_deref()) {
        Ok(_) => println!("已授权 {} 给 {} perm={}", id, mis.as_ref().or(group.as_ref()).or(mail.as_ref()).unwrap_or(&"unknown".to_string()), perm),
        Err(e) => die(&format!("授权失败: {}", e)),
    }
}

fn cmd_revoke(client: &api::KmClient, args: &[String]) {
    if args.len() < 2 {
        die("用法: km revoke <docid> <permId>");
    }
    let id = match api::extract_id(&args[0]) {
        Ok(id) => id,
        Err(e) => die(&e),
    };
    let perm_id = &args[1];
    match client.revoke_permission(&id, perm_id) {
        Ok(_) => println!("已取消权限 {}", perm_id),
        Err(e) => die(&format!("取消失败: {}", e)),
    }
}

/// km download <url> [--save <path>]：下载学城 CDN 资源（图片/drawio/视频/音频）
/// 文本类（svg/xml）→ stdout；二进制类 → --save 存文件，或不带 --save 输出 base64 data URL
fn cmd_download(client: &api::KmClient, args: &[String]) {
    let url = match args.iter().find(|a| !a.starts_with("--")) {
        Some(u) => u.clone(),
        None => die("用法: km download <url> [--save <path>]"),
    };
    let save = cli_utils::flag(args, "--save");
    let (bytes, content_type) = match client.download_resource(&url) {
        Ok(v) => v,
        Err(e) => die(&format!("下载失败: {}", e)),
    };
    let is_text = content_type.contains("svg") || content_type.contains("xml")
        || content_type.contains("text/plain") || content_type.contains("json");
    if let Some(path) = save {
        std::fs::write(&path, &bytes).unwrap_or_else(|e| die(&format!("写文件失败: {e}")));
        eprintln!("已保存 {} ({} 字节, {})", path, bytes.len(), content_type);
        return;
    }
    if is_text {
        print!("{}", String::from_utf8_lossy(&bytes));
    } else {
        // 二进制：输出 base64 data URL（便于 AI 多模态查看）
        use base64::Engine;
        let b64 = base64::engine::general_purpose::STANDARD.encode(&bytes);
        println!("data:{};base64,{}", content_type, b64);
        eprintln!("[提示] 二进制资源 {} 字节，已输出 base64 data URL；用 --save <path> 可存文件", bytes.len());
    }
}

/// km template [类型]：输出学城支持的 HTML 元素模板，供 AI/用户写 update HTML 时参考。
/// 模板格式与 km read 的 render 输出一致，确保 update diff 最稳。
fn cmd_template(args: &[String]) {
    let kind = args.iter().find(|a| !a.starts_with("--"));
    let templates: &[(&str, &str, &str)] = &[
        ("paragraph", "段落", "<p>普通段落文字</p>"),
        ("heading", "标题", "<h2>二级标题</h2>\n<h3>三级标题</h3>"),
        ("list", "无序列表", "<ul><li>项目一</li><li>项目二</li></ul>"),
        ("ordered-list", "有序列表", "<ol><li>第一步</li><li>第二步</li></ol>"),
        ("task-list", "任务列表", "<ul><li><input type=\"checkbox\" checked/>已完成</li><li><input type=\"checkbox\"/>未完成</li></ul>"),
        ("table", "表格", "<table><tr><th>列A</th><th>列B</th></tr><tr><td>值1</td><td>值2</td></tr></table>"),
        ("image", "图片", "<img src=\"https://km.sankuai.com/api/file/cdn/{cid}/{fid}?contentType=1\" alt=\"图片说明\" width=\"600\" height=\"400\"/>"),
        ("drawio", "Drawio 流程图", "<km-drawio src=\"https://km.sankuai.com/api/file/cdn/{cid}/{fid}?contentType=0\" width=\"500\" height=\"300\"/>"),
        ("video", "视频", "<km-video src=\"https://km.sankuai.com/api/file/cdn/{cid}/{fid}?contentType=video\" name=\"视频名\"/>"),
        ("audio", "音频", "<km-audio src=\"https://km.sankuai.com/api/file/cdn/{cid}/{fid}?contentType=1\" name=\"音频名\"/>"),
        ("attachment", "附件", "<km-attachment name=\"文件名.pdf\" src=\"https://km.sankuai.com/api/file/cdn/{cid}/{fid}?contentType=0\"/>"),
        ("code", "代码块", "<pre language=\"Python\"><code>print('hello')</code></pre>"),
        ("blockquote", "引用", "<blockquote><p>引用的文字内容</p></blockquote>"),
        ("hr", "分割线", "<hr/>"),
        ("note", "提示框", "<km-note type=\"info\"><summary>提示标题</summary><div><p>提示内容</p></div></km-note>"),
        ("collapse", "折叠块", "<km-collapse><summary>折叠标题</summary><div><p>折叠内容</p></div></km-collapse>"),
        ("mention", "@人", "<km-mention uid=\"mockuser01\">张三</km-mention>"),
        ("link", "链接", "<a href=\"https://km.sankuai.com/collabpage/1234567890\">链接文字</a>"),
        ("inline", "行内样式", "<strong>粗体</strong> <em>斜体</em> <del>删除线</del> <u>下划线</u> <code>行内代码</code>"),
    ];
    match kind {
        None => {
            die("用法: km template <类型>。运行 km template --help 查看可用类型");
        }
        Some(k) => {
            let k = k.as_str();
            match templates.iter().find(|(key, _, _)| *key == k) {
                Some((_, label, html)) => {
                    eprintln!("# {}", label);
                    println!("{}", html);
                }
                None => die(&format!("未知模板类型：{}。运行 km template --help 查看可用类型", k)),
            }
        }
    }
}

/// 从 HTML 中提取可下载的资源（图片/drawio/视频/音频/附件）及其 src URL
fn extract_downloadable_resources(html: &str) -> Vec<(&'static str, String)> {
    let mut out = Vec::new();
    // 标签 → 资源类型
    let tags: [(&str, &str); 5] = [
        ("<img", "图片"), ("<km-drawio", "Drawio"),
        ("<km-video", "视频"), ("<km-audio", "音频"),
        ("<km-attachment", "附件"),
    ];
    for (tag, kind) in tags {
        let kind: &'static str = kind;
        let mut search_from = 0;
        while let Some(pos) = html[search_from..].find(tag) {
            let abs = search_from + pos;
            // 找这个标签的结束 >
            if let Some(end) = html[abs..].find('>') {
                let segment = &html[abs..abs + end];
                // 找 src="..."
                if let Some(src_pos) = segment.to_lowercase().find("src=") {
                    let after = &segment[src_pos + 4..];
                    let url = if after.starts_with('"') {
                        after[1..].split('"').next().unwrap_or("")
                    } else if after.starts_with('\'') {
                        after[1..].split('\'').next().unwrap_or("")
                    } else {
                        after.split_whitespace().next().unwrap_or("")
                    };
                    if !url.is_empty() && url.starts_with("http") {
                        out.push((kind, url.to_string()));
                    }
                }
                search_from = abs + end;
            } else {
                break;
            }
        }
    }
    out
}

fn show_command_help(cmd: &str) {
    match cmd {
        "read" => eprintln!("用法: km read <docid>\n\n读取文档，输出 HTML\n\n输出包含元素 id 以支持编辑时的 diff 操作"),
        "info" => eprintln!("用法: km info <docid>\n\n查看文档元信息 + 统计数据（两个 API 并发）\n\n包括：标题、ID、链接、创建者、所有者、创建/更新时间、浏览/评论统计等"),
        "update" => eprintln!("用法: km update <docid> [--dry-run]\n\n从 stdin 读 HTML，进行 Tree Diff 后 patch 写回\n\nstdout 输出 diff 格式（~ 修改 / - 删除 / + 新增）\n--dry-run: 仅 diff，不写服务器"),
        "recent" => eprintln!("用法: km recent [edit|view|received] [limit]\n\n查看最近文档\n\nedit（默认）：最近编辑的文档\nview：最近查看的文档\nreceived：收到（大象分享）的文档"),
        "versions" => eprintln!("用法: km versions <docid>\n\n列出文档历史版本（最多 200 条）\n\n输出格式：v{{版本号}} step:{{stepVersion}} {{时间}} {{编辑者}} {{说明}}"),
        "login" => eprintln!("用法: km login [--mis <MIS号>]\n\n登录认证（token 过期自动续签，一般无需手动调用）"),
        "create" => eprintln!("用法: km create [--parent <父文档ID>] < /tmp/doc.md\n\n从 stdin 读取 Markdown 创建文档，创建完成后自动读回 HTML 输出到 stdout\n\n第一行必须是一级标题：# 文档标题\n该标题会作为学城文档标题；正文从第二行开始\n本地图片自动上传\n--parent: 可选，指定父文档 ID；不指定时创建到默认位置"),
        "ls" => eprintln!("用法: km ls [docid]\n\n无参数列出个人空间根目录文档，带 docid 列出该文档的子文档"),
        "search" => eprintln!("用法: km search --keyword <关键词>\n\n全站搜索文档"),
        "rm" => eprintln!("用法: km rm <docid>\n\n删除文档（需交互确认）\n\n说明：仅所有者可删除，删除后可用 km undelete 恢复"),
        "mv" => eprintln!("用法: km mv <docid> <parentid>\n\n移动文档到新父目录"),
        "upload" => eprintln!("用法: km upload <docid> <file-path>\n\n上传文件（自动识别类型：图片/drawio/视频/音频/附件），输出可插入 HTML 的节点"),
        "restore" => eprintln!("用法: km restore <docid> <stepVersion>\n\n还原到指定版本\n\n警告：操作不可撤销，会覆盖当前内容"),
        "comments" => eprintln!("用法: km comments <docid> [--limit 20]\n\n查看全文评论列表"),
        "comment" => eprintln!("用法: km comment <docid> \"内容\" [--reply <commentId>]\n\n发表全文评论或回复"),
        "secret" => eprintln!("用法: km secret <docid> <2|3|4>\n\n设置密级\n\n2: C2 内部公开  3: C3 内部敏感  4: C4 内部机密"),
        "copy" => eprintln!("用法: km copy <source-id> <new-title> [--to <parentid>]\n\n复制文档为新文档\n\n--to 未指定时，复制到当前用户个人空间根目录"),
        "undelete" => eprintln!("用法: km undelete <docid>\n\n恢复已删除文档"),
        "mentioned" => eprintln!("用法: km mentioned [limit]\n\n查看被@的文档"),
        "commented" => eprintln!("用法: km commented [limit]\n\n查看我评论过的文档"),
        "square" => eprintln!("用法: km square [recommend|latest] [limit]\n\n知识广场文章\n\nrecommend（默认）: 推荐文章  latest: 最新文章"),
        "discussions" => eprintln!("用法: km discussions <docid> [--limit 20]\n\n查看划词评论（引用某段文字的评论）"),
        "reply-discussion" => eprintln!("用法: km reply-discussion <docid> <discussionId> <quoteId> <text>\n\n回复划词评论"),
        "perms" => eprintln!("用法: km perms <docid> [--page 1]\n\n查看权限列表\n\n输出格式：[permId] {{权限类型}} {{被授权人/群/邮件组}}"),
        "grant" => eprintln!("用法: km grant <docid> <perm> --mis <mis>|--group <xmGroupId>|--mail <mail>\n\n授权文档（perm: BROWSE/EDIT/MANAGE）"),
        "revoke" => eprintln!("用法: km revoke <docid> <permId>\n\n取消权限（permId 来自 km perms）"),
        "template" => eprintln!("用法: km template <类型>\n\n输出学城 HTML 元素模板，供 update HTML 参考\n\n可用类型：paragraph, heading, list, ordered-list, task-list, table, image, drawio, video, audio, attachment, code, blockquote, hr, note, collapse, mention, link, inline"),
        _ => eprintln!("命令 {} 没有帮助信息", cmd),
    }
}

fn die(msg: &str) -> ! {
    eprintln!("{}", msg);
    std::process::exit(1);
}

const HELP: &str = r#"km - 学城文档 CLI（Rust 版）

文档 CRUD:
  km read <id>                                读取文档，输出 HTML
  km create [--parent <父文档ID>] < /tmp/doc.md  从 Markdown 创建文档
  km update <id> [--dry-run]                  更新文档（HTML 增量，图片自动上传）
  km info <id>                                查看文档元信息
  km ls [id]                                 列出文档（无参数=空间根目录，有 id=子文档）
  km search --keyword <关键词>                 搜索文档
  km rm <id>                                  删除文档
  km mv <id> <parentid>                      移动文档
  km copy <source-id> <new-title> [--to <parent>]  复制文档

媒体上传:
  km upload <id> <file-path>                     上传文件（自动识别类型）
  km download <url> [--save <path>]           下载 CDN 资源（图片/drawio/视频/音频）
  km template [类型]                          输出 HTML 元素模板（表格/图片/段落等）

版本与恢复:
  km versions <id>                            查看版本历史
  km restore <id> <stepVersion>               还原到指定版本
  km undelete <id>                            恢复已删除文档

评论与讨论:
  km comments <id> [--limit 20]               查看全文评论
  km comment <id> <text> [--reply <id>]      发表/回复评论
  km discussions <id> [--limit 20]            查看划词评论
  km reply-discussion <id> <discussionId> <quoteId> <text>  回复划词评论

文档权限:
  km secret <id> <2|3|4>                     设置密级
  km perms <id> [--page 1]                    查看权限列表
  km grant <id> <perm> --mis|--group|--mail <val>  授权
  km revoke <id> <permId>                     取消权限

最近访问:
  km recent [edit|view|received] [limit]      查看最近文档
  km mentioned [limit]                        被@的文档
  km commented [limit]                        我评论过的文档
  km square [recommend|latest] [limit]        知识广场文章

其他:
  km login [--mis <MIS号>]                    登录认证（可选，自动续签无需手动）

通用选项:
  --mis <mis>                                 指定 MIS 号（覆盖环境变量）
  --help, -h                                  显示帮助信息

环境变量:
  MAAS_USER_ID                                MIS 号（自动注入）
"#;
