//! 搜索结果解析的集成测试。
//!
//! 基于 tests/fixtures/search_response.json（学城搜索 API 真实返回脱敏样本）。
//! 这两个 bug 的回归保护：
//!   1. search_docs 只取 response["data"]（对象），未取 data["models"]，导致永远"无结果"
//!   2. cmd_search 用 as_str() 取 contentId，但 API 返回的是数字，导致结果不显示 ID

use km_ops::api::{content_id_to_string, extract_search_models};
use serde_json::Value;

/// 读取 tests/fixtures 下的 JSON fixture
fn fixture(name: &str) -> Value {
    let path = format!("{}/tests/fixtures/{}", env!("CARGO_MANIFEST_DIR"), name);
    let content = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("读取 fixture {} 失败: {}", name, e));
    serde_json::from_str(&content)
        .unwrap_or_else(|e| panic!("解析 fixture {} 失败: {}", name, e))
}

#[test]
fn extract_search_models_from_real_api_response() {
    // 真实 API 返回：{ status, data: { totalCount, models: [...] } }
    let resp = fixture("search_response.json");
    assert_eq!(resp["status"], 0);

    let models = extract_search_models(resp.get("data"));
    let arr = models.as_array().expect("models 应为数组");
    // fixture 里有 3 条
    assert_eq!(arr.len(), 3);
    // 第一条标题对得上
    assert_eq!(arr[0]["title"], "测试文档A");
}

#[test]
fn search_models_content_id_is_numeric_in_api_response() {
    // 回归保护：API 返回的 contentId 是数字而非字符串。
    // cmd_search 旧代码用 as_str() 取值，对数字返回 None，导致搜索结果不显示 ID。
    let resp = fixture("search_response.json");
    let models = extract_search_models(resp.get("data"));
    let first = &models.as_array().unwrap()[0];

    // contentId 在 JSON 里是数字类型
    assert!(first["contentId"].is_i64(), "contentId 应为数字类型");

    // content_id_to_string 能正确把数字 ID 转成字符串
    let id = content_id_to_string(&first["contentId"]);
    assert_eq!(id, "1000000001");
    assert!(!id.is_empty(), "ID 不能为空（这是原 bug 的表现）");
}

#[test]
fn extract_search_models_preserves_all_real_results() {
    // 确保从真实响应里能取出全部 models，并且每条都有可用的 contentId + title
    let resp = fixture("search_response.json");
    let models = extract_search_models(resp.get("data"));
    for m in models.as_array().unwrap() {
        let id = content_id_to_string(&m["contentId"]);
        let title = m["title"].as_str().unwrap_or("");
        assert!(!id.is_empty(), "每条结果都应有非空 ID");
        assert!(!title.is_empty(), "每条结果都应有非空标题");
    }
}
