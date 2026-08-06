use std::collections::HashMap;

// ── 数据结构 ──────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct HtmlNode {
    pub tag: String,
    pub attrs: HashMap<String, String>,
    pub inner_html: String,
    pub hash: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DiffOp {
    pub op: DiffOpKind,
    pub old_idx: Option<usize>,
    pub new_idx: Option<usize>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum DiffOpKind {
    Keep,
    Delete,
    Insert,
}

// ── 哈希 ──────────────────────────────────────────────────────────────────────

pub fn hash_str(s: &str) -> String {
    let mut h: i32 = 0;
    for &b in s.as_bytes() {
        h = h.wrapping_mul(31).wrapping_add(b as i32);
    }
    // 36 进制，与 JS 的 toString(36) 一致
    let mut result = String::new();
    let mut n = h as u32;
    if n == 0 {
        return "0".to_string();
    }
    while n > 0 {
        let d = (n % 36) as u8;
        // 用 ASCII 码计算 36 进制字符，避免硬编码字符表（消除扫描器高熵字符串误报）
        let c = if d < 10 { b'0' + d } else { b'a' + d - 10 };
        result.insert(0, c as char);
        n /= 36;
    }
    // 处理负数：JS 的 |0 截断为 32 位有符号
    if h < 0 {
        result.insert(0, '-');
    }
    result
}

/// 富节点类型 → 需参与 hash 计算的属性列表
const RICH_HASH_KEYS: &[(&str, &[&str])] = &[
    ("km-drawio", &["src"]),
    ("km-video", &["src", "url"]),
    ("km-audio", &["src", "url"]),
    ("km-attachment", &["src", "name"]),
    ("km-xtable", &["xtable-id"]),
    ("km-open-link", &["url"]),
    ("km-open-card", &["url"]),
    ("img", &["src"]),
];

/// 规范化对齐值，用于参与节点 hash。与 patch::extract_align 保持一致：
/// 优先 align 属性，其次 style 的 text-align；默认/左对齐返回空串。
fn normalize_align_for_hash(attrs: &HashMap<String, String>) -> String {
    let mut align: Option<String> = attrs.get("align").map(|s| s.trim().to_lowercase());
    if align.as_deref().map_or(true, |s| s.is_empty()) {
        if let Some(style) = attrs.get("style") {
            for decl in style.split(';') {
                let decl = decl.trim();
                if let Some(rest) = decl.strip_prefix("text-align") {
                    let val = rest.trim_start_matches([' ', ':']).trim().to_lowercase();
                    align = if val.is_empty() { None } else { Some(val) };
                    break;
                }
            }
        } else {
            align = None;
        }
    }
    match align.as_deref() {
        None | Some("") | Some("left") => String::new(),
        Some(v) => v.to_string(),
    }
}

pub fn rich_hash(tag: &str, attrs: &HashMap<String, String>) -> String {
    for (t, keys) in RICH_HASH_KEYS {
        if *t == tag {
            let parts: Vec<String> = keys.iter().map(|k| attrs.get(*k).cloned().unwrap_or_default()).collect();
            return hash_str(&format!("{}|{}", tag, parts.join("|")));
        }
    }
    hash_str(tag)
}

// ── HTML 节点解析 ─────────────────────────────────────────────────────────────
// 占位：待从 JS 移植

// 自闭合 HTML 元素（不找闭合标签）
const SELF_CLOSING_HTML: &[&str] = &["hr", "br", "img", "input"];

pub fn parse_nodes(html: &str) -> Vec<HtmlNode> {
    let mut nodes = Vec::new();
    let s = html.trim();
    let mut pos = 0;

    while pos < s.len() {
        // 跳过空白
        while pos < s.len() && s.as_bytes()[pos].is_ascii_whitespace() { pos += 1; }
        if pos >= s.len() { break; }

        // 注释
        if s[pos..].starts_with("<!--") {
            if let Some(end) = s[pos..].find("-->") {
                pos += end + 3;
            } else {
                pos = s.len();
            }
            continue;
        }

        if s.as_bytes()[pos] != b'<' {
            // 按完整 UTF-8 字符推进，避免越过多字节字符边界
            pos += s[pos..].chars().next().map(|c| c.len_utf8()).unwrap_or(1);
            continue;
        }

        let tag_end = s[pos..].find('>').map_or(s.len(), |i| pos + i);
        if tag_end >= s.len() { break; }
        let full_open = &s[pos..=tag_end];

        // 自闭合标签：<hr/> <km-drawio/> <img .../> 等
        if full_open.ends_with("/>") {
            let inner_str = full_open[1..full_open.len()-2].trim().to_string();
            let inner_ref = inner_str.as_str();
            let space = inner_ref.find(|c: char| c.is_ascii_whitespace());
            let (tag, attr_str) = if let Some(si) = space {
                (&inner_ref[..si], inner_ref[si..].trim())
            } else {
                (inner_ref, "")
            };
            let t = tag.to_lowercase();
            let a = crate::parse::parse_attrs(attr_str);
            nodes.push(HtmlNode {
                tag: t.clone(),
                attrs: a.clone(),
                inner_html: String::new(),
                hash: rich_hash(&t, &a),
            });
            pos = tag_end + 1;
            continue;
        }

        // 普通开标签
        let inner = &full_open[1..full_open.len()-1];
        let space = inner.find(|c: char| c.is_ascii_whitespace());
        let (tag, attr_str) = if let Some(si) = space {
            (&inner[..si], inner[si..].trim())
        } else {
            (inner, "")
        };
        let tag_lower = tag.to_lowercase();
        let attrs = crate::parse::parse_attrs(attr_str);
        let after_open = tag_end + 1;

        // 自闭合 HTML 元素
        if SELF_CLOSING_HTML.contains(&tag_lower.as_str()) {
            nodes.push(HtmlNode {
                tag: tag_lower.clone(),
                attrs: attrs.clone(),
                inner_html: String::new(),
                hash: rich_hash(&tag_lower, &attrs),
            });
            pos = tag_end + 1;
            continue;
        }

        let close_tag = format!("</{}>", tag_lower);

        // 找对应闭合标签（深度感知）
        let mut depth: usize = 1;
        let mut search = after_open;
        let mut inner_end = None;

        while search < s.len() && depth > 0 {
            let open_pos = s[search..].find(&format!("<{}", tag_lower));
            let close_pos = s[search..].find(&close_tag);

            if close_pos.is_none() { break; }
            let close_pos = close_pos.unwrap();

            if let Some(op) = open_pos {
                if op < close_pos {
                    let after_tag = search + op + 1 + tag_lower.len();
                    if after_tag < s.len() && matches!(s.as_bytes()[after_tag], b'>' | b' ' | b'/') {
                        depth += 1;
                        search += op + 1;
                        continue;
                    }
                }
            }

            depth -= 1;
            if depth == 0 { inner_end = Some(search + close_pos); }
            search += close_pos + 1;
        }

        if inner_end.is_none() { pos = tag_end + 1; continue; }
        let inner_end = inner_end.unwrap();
        let inner_html = s[after_open..inner_end].to_string();

        // 对齐语义参与 hash：p/h2-h6 的对齐变更必须能被 diff 检测到，
        // 否则「只改居中、不改文字」会被判成无变化而跳过写入
        let align_part = if matches!(tag_lower.as_str(), "p" | "h2" | "h3" | "h4" | "h5" | "h6" | "summary") {
            normalize_align_for_hash(&attrs)
        } else {
            String::new()
        };
        let hash_input = if align_part.is_empty() {
            format!("{}|{}", tag_lower, &inner_html)
        } else {
            format!("{}|{}|{}", tag_lower, &inner_html, align_part)
        };
        nodes.push(HtmlNode {
            hash: hash_str(&hash_input),
            tag: tag_lower,
            inner_html,
            attrs,
        });

        pos = inner_end + close_tag.len();
    }

    nodes
}

// ── 节点相似度 ────────────────────────────────────────────────────────────────

const HEADING_TAGS: &[&str] = &["h1", "h2", "h3", "h4", "h5", "h6"];
const RICH_TAGS: &[&str] = &["km-drawio", "km-xtable", "km-minder", "km-video", "km-audio", "km-attachment", "hr", "img"];

fn is_heading(tag: &str) -> bool {
    HEADING_TAGS.contains(&tag)
}

fn is_rich(tag: &str) -> bool {
    RICH_TAGS.contains(&tag)
}

pub fn node_similarity(a: &HtmlNode, b: &HtmlNode) -> f64 {
    // 同一标题家族
    if is_heading(&a.tag) && is_heading(&b.tag) {
        if a.hash == b.hash && a.tag == b.tag { return 1.0; }
        return approx_similarity(&a.inner_html, &b.inner_html);
    }
    if a.tag != b.tag { return 0.0; }
    if a.hash == b.hash { return 1.0; }
    if is_rich(&a.tag) { return 0.9; }
    approx_similarity(&a.inner_html, &b.inner_html)
}

pub fn approx_similarity(a: &str, b: &str) -> f64 {
    if a.is_empty() && b.is_empty() { return 1.0; }
    if a.is_empty() || b.is_empty() { return 0.0; }
    let max_len = a.chars().count().max(b.chars().count()) as f64;
    if max_len == 0.0 { return 1.0; }

    let prefix = a.chars().zip(b.chars()).take_while(|(x, y)| x == y).count() as f64;
    let suffix = a.chars().rev().zip(b.chars().rev()).take_while(|(x, y)| x == y).count() as f64;

    ((prefix + suffix) / max_len).min(1.0)
}

// ── Myers diff ────────────────────────────────────────────────────────────────
// 占位：待从 JS 移植

// ── LCS diff（基于相似度的最长公共子序列 diff）───────────────────────────────

pub fn lcs_diff(old_nodes: &[HtmlNode], new_nodes: &[HtmlNode], threshold: f64) -> Vec<DiffOp> {
    let m = old_nodes.len();
    let n = new_nodes.len();
    if m == 0 && n == 0 { return vec![]; }

    // DP table: lcs[i][j] = LCS length of old[i..] and new[j..]
    let mut dp = vec![vec![0usize; n + 1]; m + 1];
    for i in (0..m).rev() {
        for j in (0..n).rev() {
            if node_similarity(&old_nodes[i], &new_nodes[j]) >= threshold {
                dp[i][j] = 1 + dp[i + 1][j + 1];
            } else {
                dp[i][j] = dp[i + 1][j].max(dp[i][j + 1]);
            }
        }
    }

    // If no matches found, fall back to positional diff
    if dp[0][0] == 0 {
        return simple_diff(old_nodes, new_nodes, threshold);
    }

    // Reconstruct ops (prefer Delete over Insert on tie to produce stable "move" detection)
    let mut ops = Vec::new();
    let mut i = 0;
    let mut j = 0;
    while i < m || j < n {
        let can_match = i < m && j < n
            && node_similarity(&old_nodes[i], &new_nodes[j]) >= threshold
            && dp[i][j] == 1 + dp[i + 1][j + 1];

        if can_match {
            ops.push(DiffOp { op: DiffOpKind::Keep, old_idx: Some(i), new_idx: Some(j) });
            i += 1; j += 1;
        } else if i >= m {
            ops.push(DiffOp { op: DiffOpKind::Insert, old_idx: None, new_idx: Some(j) });
            j += 1;
        } else if j >= n {
            ops.push(DiffOp { op: DiffOpKind::Delete, old_idx: Some(i), new_idx: None });
            i += 1;
        } else if dp[i + 1][j] >= dp[i][j + 1] {
            ops.push(DiffOp { op: DiffOpKind::Delete, old_idx: Some(i), new_idx: None });
            i += 1;
        } else {
            ops.push(DiffOp { op: DiffOpKind::Insert, old_idx: None, new_idx: Some(j) });
            j += 1;
        }
    }
    ops
}

// ── 简单 diff（位置对应，未来升级 Myers）──────────────────────────────────────

pub fn simple_diff(old_nodes: &[HtmlNode], new_nodes: &[HtmlNode], _threshold: f64) -> Vec<DiffOp> {
    let mut ops = Vec::new();
    let max_len = old_nodes.len().max(new_nodes.len());

    for i in 0..max_len {
        match (old_nodes.get(i), new_nodes.get(i)) {
            (Some(_), Some(_)) => {
                // 同位置永远 match，后续由 hash 差异决定是 keep 还是 changed
                ops.push(DiffOp { op: DiffOpKind::Keep, old_idx: Some(i), new_idx: Some(i) });
            }
            (Some(_), None) => {
                ops.push(DiffOp { op: DiffOpKind::Delete, old_idx: Some(i), new_idx: None });
            }
            (None, Some(_)) => {
                ops.push(DiffOp { op: DiffOpKind::Insert, old_idx: None, new_idx: Some(i) });
            }
            (None, None) => unreachable!(),
        }
    }
    ops
}

// ── 测试 ──────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── hash_str ──────────────────────────────────────────────────────────

    #[test]
    fn test_hash_str_same_input_same_output() {
        assert_eq!(hash_str("hello"), hash_str("hello"));
    }

    #[test]
    fn test_hash_str_different_input_different_output() {
        assert_ne!(hash_str("hello"), hash_str("world"));
    }

    // ── rich_hash ─────────────────────────────────────────────────────────

    #[test]
    fn test_rich_hash_no_key_attrs_falls_back_to_tag() {
        let attrs = HashMap::new();
        assert_eq!(rich_hash("km-minder", &attrs), hash_str("km-minder"));
    }

    // ── node_similarity ───────────────────────────────────────────────────

    #[test]
    fn test_similarity_heading_family_h2_to_h3() {
        let a = HtmlNode { tag: "h2".into(), attrs: HashMap::new(), inner_html: "标题".into(), hash: hash_str("h2|标题") };
        let b = HtmlNode { tag: "h3".into(), attrs: HashMap::new(), inner_html: "标题".into(), hash: hash_str("h3|标题") };
        // 标题家族：tag 不同但内容相同 → 高相似度
        assert!(node_similarity(&a, &b) > 0.8);
    }

    // ── approx_similarity ─────────────────────────────────────────────────

    #[test]
    fn test_approx_similarity_completely_different() {
        let sim = approx_similarity("hello", "world");
        assert!(sim < 0.5, "完全不同的文本相似度应 < 0.5, got {sim}");
    }


    // ── parse_nodes ───────────────────────────────────────────────────────

    #[test]
    fn test_parse_nodes_single_p() {
        let nodes = parse_nodes("<p>hello</p>");
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "p");
        assert_eq!(nodes[0].inner_html, "hello");
    }

    #[test]
    fn test_parse_nodes_self_closing_drawio() {
        let nodes = parse_nodes(r#"<km-drawio src="https://cdn/a.svg"/>"#);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "km-drawio");
        assert_eq!(nodes[0].inner_html, "");
        assert_eq!(nodes[0].attrs.get("src").unwrap(), "https://cdn/a.svg");
    }

    #[test]
    fn test_parse_nodes_self_closing_img() {
        let nodes = parse_nodes(r#"<img src="a.png" alt="pic"/>"#);
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].tag, "img");
    }

    #[test]
    fn test_parse_nodes_multiple_blocks() {
        let nodes = parse_nodes("<h1>Title</h1><p>body</p>");
        assert_eq!(nodes.len(), 2);
        assert_eq!(nodes[0].tag, "h1");
        assert_eq!(nodes[1].tag, "p");
    }

    #[test]
    fn test_parse_nodes_rich_hash_differs_by_src() {
        let a = parse_nodes(r#"<km-drawio src="a.svg"/>"#);
        let b = parse_nodes(r#"<km-drawio src="b.svg"/>"#);
        assert_ne!(a[0].hash, b[0].hash, "different src should produce different hash");
    }

    #[test]
    fn test_parse_nodes_summary_hash_includes_align() {
        // note_title/collapse_title 渲染为 <summary>，对齐必须参与 hash，
        // 否则「只改居中」会被 diff 判成无变化
        let a = parse_nodes(r#"<summary style="text-align: center">标题</summary>"#);
        let b = parse_nodes("<summary>标题</summary>");
        assert_ne!(a[0].hash, b[0].hash,
            "aligned summary must hash differently from default summary");
        // 相同对齐 + 相同内容 → 相同 hash
        let c = parse_nodes(r#"<summary style="text-align: center">标题</summary>"#);
        assert_eq!(a[0].hash, c[0].hash, "same align+content must hash equal");
    }

    // ── myers_diff ───────────────────────────────────────────────────────

    #[test]
    fn test_similarity_same_content_different_hash_high_similarity() {
        let a = HtmlNode {
            tag: "p".into(),
            attrs: HashMap::new(),
            inner_html: "这是一段很长的内容".into(),
            hash: hash_str("p|这是一段很长的内容"),
        };
        let b = HtmlNode {
            tag: "p".into(),
            attrs: HashMap::new(),
            inner_html: "这是一段很长的内容，稍有修改".into(),
            hash: hash_str("p|这是一段很长的内容，稍有修改"),
        };
        let sim = node_similarity(&a, &b);
        assert!(sim > 0.5, "similar content should have high similarity");
    }

    #[test]
    fn test_similarity_different_content_low_similarity() {
        let a = HtmlNode {
            tag: "p".into(),
            attrs: HashMap::new(),
            inner_html: "AAAA".into(),
            hash: hash_str("p|AAAA"),
        };
        let b = HtmlNode {
            tag: "p".into(),
            attrs: HashMap::new(),
            inner_html: "ZZZZ".into(),
            hash: hash_str("p|ZZZZ"),
        };
        let sim = node_similarity(&a, &b);
        assert!(sim < 0.5, "completely different content should have low similarity");
    }

}
