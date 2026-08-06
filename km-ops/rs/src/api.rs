use serde_json::{json, Value};
use crate::auth;


use uuid::Uuid;

const BASE: &str = "https://km.sankuai.com";

/// 在目录树中查找 target contentId 的路径（从根到目标，含目标自身）
fn find_path(nodes: &[Value], target: i64) -> Option<Vec<i64>> {
    for node in nodes {
        let cur = node.get("content").and_then(|c| c.get("contentId")).and_then(|v| v.as_i64());
        if let Some(id) = cur {
            if id == target {
                return Some(vec![id]);
            }
            if let Some(children) = node.get("children").and_then(|v| v.as_array()) {
                if let Some(mut sub) = find_path(children, target) {
                    let mut path = vec![id];
                    path.append(&mut sub);
                    return Some(path);
                }
            }
        }
    }
    None
}

/// 目录树中是否包含 target contentId（递归子树）
fn contains_id(nodes: &[Value], target: i64) -> bool {
    for node in nodes {
        let cur = node.get("content").and_then(|c| c.get("contentId")).and_then(|v| v.as_i64());
        if cur == Some(target) {
            return true;
        }
        if let Some(children) = node.get("children").and_then(|v| v.as_array()) {
            if contains_id(children, target) {
                return true;
            }
        }
    }
    false
}

/// 权限类型映射（对齐 oa-skills PermissionTypeMap）
/// view/仅浏览=5, comment/可浏览=0, edit/可编辑=2, manage/可管理=4 等
fn perm_group_type(perm: &str) -> Result<i64, String> {
    match perm {
        "view" | "仅浏览" => Ok(5),
        "comment" | "可浏览" | "可浏览、评论" => Ok(0),
        "edit" | "可编辑" => Ok(2),
        "可编辑、添加" => Ok(3),
        "可编辑、添加、删除" => Ok(1),
        "manage" | "可管理" => Ok(4),
        other if other.chars().all(|c| c.is_ascii_digit()) => other.parse::<i64>().map_err(|_| format!("不支持的权限类型: {other}")),
        other => Err(format!("不支持的权限类型: {other}")),
    }
}

/// 学城 HTTP 客户端
pub struct KmClient {
    pub token: String,
    pub mis: Option<String>,
    client: reqwest::blocking::Client,
}

impl KmClient {
    pub fn new(token: String, mis: Option<String>) -> Self {
        Self { token, mis, client: reqwest::blocking::Client::new() }
    }

    fn fetch(&self, url: &str, method: &str, body: Option<Value>) -> Result<Value, String> {
        let mut req = self.client.request(
            method.parse().unwrap_or(reqwest::Method::GET),
            url,
        ).header("access-token", &self.token)
         .header("Content-Type", "application/json; charset=utf-8")
         .header("x-requested-with", "XMLHttpRequest");

        if let Some(b) = body {
            req = req.json(&b);
        }

        let res = req.send().map_err(|e| format!("HTTP error: {e}"))?;
        let status = res.status();
        let body: Value = res.json().unwrap_or_default();

        if !status.is_success() {
            if status.as_u16() == 401 {
                // 清除缓存并提示重新认证
                if let Some(mis) = &self.mis {
                    let _ = auth::invalidate_cache(mis);
                    return Err(
                        "Token 已失效（401）：已清除本地缓存，请重新运行命令（系统将自动重新认证）".into()
                    );
                }
                return Err("Token 已失效（401）：请重新认证".into());
            }
            return Err(format!("HTTP {} {}", status.as_u16(), url));
        }

        let code = body.get("status").or_else(|| body.get("code")).and_then(|v| v.as_i64()).unwrap_or(0);
        if code != 0 {
            // API 返回 401 也清除缓存
            if code == 401 {
                if let Some(mis) = &self.mis {
                    let _ = auth::invalidate_cache(mis);
                    return Err(format!(
                        "Token 已失效（API 401）：已清除本地缓存，请重新运行命令（系统将自动重新认证）"
                    ));
                }
                return Err("Token 已失效（API 401）：请重新认证".into());
            }
            return Err(format!("API error code={code}: {}", body.get("msg").or_else(|| body.get("message")).and_then(|v| v.as_str()).unwrap_or("unknown")));
        }

        Ok(body)
    }

    /// 读取文档 PM JSON
    pub fn get_doc(&self, content_id: &str) -> Result<Value, String> {
        let body = self.fetch(&format!("{BASE}/api/docs/recent/safeRoom/{content_id}?versionCheck=1"), "GET", None)?;
        let data = body.get("data").ok_or("No data in response")?;
        let raw_body = data.get("body").ok_or("No body in data")?;
        let (pm_json, is_v1) = if raw_body.is_string() {
            let parsed = serde_json::from_str::<Value>(raw_body.as_str().unwrap_or("")).ok();
            match parsed {
                Some(v) if v.is_object() => (v, false),
                _ => (Value::Null, true),
            }
        } else {
            (raw_body.clone(), false)
        };

        let mut doc = json!({
            "contentId": data.get("contentId").and_then(|v| v.as_str()).unwrap_or(content_id),
            "title": data.get("title").and_then(|v| v.as_str()).unwrap_or(""),
            "body": pm_json,
            "stepVersion": data.get("stepVersion").or_else(|| data.get("_stepVersion")),
            "v1": is_v1,
        });
        if is_v1 {
            doc["rawHtml"] = raw_body.clone();
        }
        Ok(doc)
    }

    /// 更新文档
    /// 对齐 oaskills updateDocument：只发 content，不发 stepVersion
    pub fn update_doc(&self, content_id: &str, pm_json: &Value, _step_version: Option<i64>) -> Result<String, String> {
        let body_obj = json!({
            "content": serde_json::to_string(pm_json).unwrap_or_default(),
        });
        self.fetch(&format!("{BASE}/api/pages/updateCollaborationContent/{content_id}"), "POST", Some(body_obj))?;
        Ok(format!("https://km.sankuai.com/collabpage/{content_id}"))
    }

    /// 获取最近文档列表
    pub fn get_recent(&self, kind: &str, limit: u32) -> Result<Value, String> {
        let body = self.fetch(
            &format!("{BASE}/api/docs/recent?type={kind}&limit={limit}"),
            "GET",
            None
        )?;
        Ok(body.get("data").cloned().unwrap_or(Value::Null))
    }

    /// 获取文档版本历史
    pub fn get_versions(&self, content_id: &str) -> Result<Value, String> {
        // 对齐 oa-skills：GET /api/docs/{contentId}/versions，版本列表在 data.models
        let body = self.fetch(
            &format!("{BASE}/api/docs/{content_id}/versions?limit=200&renamedFilter=false&type=1"),
            "GET",
            None
        )?;
        let data = body.get("data").cloned().unwrap_or(Value::Null);
        // data 结构为 {total, models:[...]}，取 models
        Ok(data.get("models").cloned().unwrap_or(Value::Array(vec![])))
    }

    pub fn get_doc_meta(&self, content_id: &str) -> Result<Value, String> {
        let body = self.fetch(&format!("{BASE}/api/pages/new/{content_id}?queryType=0"), "GET", None)?;
        Ok(body.get("data").cloned().unwrap_or(Value::Null))
    }

    pub fn get_doc_stats(&self, content_id: &str) -> Result<Value, String> {
        let body = self.fetch(&format!("{BASE}/api/docs/stats?contentId={content_id}&editDuration=true"), "GET", None)?;
        Ok(body.get("data").cloned().unwrap_or(Value::Null))
    }

    /// 获取文档所属空间 ID
    /// GET /api/pages/{contentId}/spaceId  （对齐 oa-skills getSpaceId）
    pub fn get_space_id(&self, content_id: &str) -> Result<String, String> {
        let body = self.fetch(&format!("{BASE}/api/pages/{content_id}/spaceId"), "GET", None)?;
        // data 直接是 spaceId（数字或字符串）
        body.get("data")
            .and_then(|v| v.as_i64().map(|n| n.to_string()).or_else(|| v.as_str().map(String::from)))
            .filter(|s| !s.is_empty())
            .ok_or_else(|| "无法获取 spaceId".into())
    }

    /// 获取当前用户的个人空间 spaceId
    /// GET /api/spaces/spaceid?spaceKey=~{mis}  （对齐 oa-skills getSpaceIdByMis）
    pub fn get_personal_space_id(&self) -> Result<String, String> {
        let mis = self.mis.as_ref().ok_or("无法确定 MIS 号")?;
        let body = self.fetch(&format!("{BASE}/api/spaces/spaceid?spaceKey=~{mis}"), "GET", None)?;
        body.get("data")
            .and_then(|v| v.as_i64().map(|n| n.to_string()).or_else(|| v.as_str().map(String::from)))
            .filter(|s| !s.is_empty())
            .ok_or_else(|| "无法获取个人空间 spaceId".into())
    }

    /// 列出空间根目录下的文档
    /// GET /api/spaces/child/safeRoom/{spaceId}  （对齐 oa-skills getSpaceRootDocs）
    pub fn list_space_root(&self, space_id: &str) -> Result<Value, String> {
        let body = self.fetch(&format!("{BASE}/api/spaces/child/safeRoom/{space_id}"), "GET", None)?;
        Ok(extract_list(body.get("data")))
    }

    /// 列出文档的子文档
    /// 1. GET /api/pages/{contentId}/spaceId
    /// 2. GET /api/pages/child/safeRoom/{spaceId}/{contentId}  （对齐 oa-skills getChildContent）
    pub fn list_children(&self, content_id: &str) -> Result<Value, String> {
        let space_id = self.get_space_id(content_id)?;
        let body = self.fetch(&format!("{BASE}/api/pages/child/safeRoom/{space_id}/{content_id}"), "GET", None)?;
        Ok(extract_list(body.get("data")))
    }

    pub fn search_docs(&self, keyword: &str, limit: u32) -> Result<Value, String> {
        // 对齐 oa-skills searchContent 的固定参数
        let body = json!({
            "keyword": keyword,
            "offset": 0,
            "limit": limit,
            "entryPoint": "km_skill",
            "uQueryId": Uuid::new_v4().to_string(),
            "newSpaceType": 1,
            "refreshFlag": 0,
            "enableMultiLingual": false,
            "searchTitle": false,
            "tabType": "all",
            "spaceType": -1,
            "secretLevels": [2, 3, 4]
        });
        let response = self.fetch(&format!("{BASE}/api/citadelsearch/saferoom/content"), "POST", Some(body))?;
        Ok(extract_search_models(response.get("data")))
    }

    pub fn delete_doc(&self, content_id: &str) -> Result<(), String> {
        let space_id = self.get_space_id(content_id)?;
        // 走 fetch 复用响应错误码检查（对齐 oa-skills deleteDocument）
        self.fetch(&format!("{BASE}/api/pages/{space_id}/{content_id}"), "DELETE", None)?;
        Ok(())
    }

    /// 获取文档在目录树中的路径（从空间根到自身的 contentId 序列）
    /// 对齐 oa-skills getDocumentPath：GET /api/pages/catelog/{contentId}
    pub fn get_document_path(&self, content_id: &str) -> Result<Vec<i64>, String> {
        let body = self.fetch(&format!("{BASE}/api/pages/catelog/{content_id}"), "GET", None)?;
        let nodes = body.get("data").and_then(|v| v.as_array()).ok_or("无法获取文档目录")?;
        let target = content_id.parse::<i64>().map_err(|_| "contentId 不是数字")?;
        let path = find_path(nodes, target).ok_or_else(|| "无法在目录树中找到该文档的路径".to_string())?;
        Ok(path)
    }

    /// 移动文档到新父文档下
    /// 对齐 oa-skills moveDocument：POST /api/pages/{spaceId}/{contentId}
    /// body: { type:1, newParentId, newSpaceId, contentPath, movePermType:2 }
    pub fn move_doc(&self, content_id: &str, new_parent_id: &str) -> Result<(), String> {
        let space_id = self.get_space_id(content_id)?;
        let new_space_id = self.get_space_id(new_parent_id)?;
        let content_path = self.get_document_path(content_id)?;
        let body = json!({
            "type": 1,
            "newParentId": new_parent_id.parse::<i64>().unwrap_or(0),
            "newSpaceId": new_space_id.parse::<i64>().unwrap_or(0),
            "contentPath": content_path,
            "movePermType": 2,
        });
        self.fetch(&format!("{BASE}/api/pages/{space_id}/{content_id}"), "POST", Some(body))?;

        // 移动后校验：用 catelog 目录树确认文档确实在新父文档下，不静默成功
        // （recent/safeRoom 的 parentId 字段不可靠，根目录和有父都可能返回 0/None）
        let tree = self.fetch(&format!("{BASE}/api/pages/catelog/{new_parent_id}"), "GET", None)?;
        let target = content_id.parse::<i64>().unwrap_or(0);
        let found = tree.get("data").and_then(|v| v.as_array()).map(|nodes| contains_id(nodes, target)).unwrap_or(false);
        if !found {
            return Err(format!("移动未生效：服务端返回成功，但文档 {content_id} 未出现在新父文档 {new_parent_id} 的目录树下"));
        }
        Ok(())
    }

    pub fn recent_edits(&self, limit: u32) -> Result<Value, String> {
        let body = self.fetch(&format!("{BASE}/api/pages/latestEdit/safeRoom?offSet=0&limit={limit}"), "GET", None)?;
        Ok(body.get("data").cloned().unwrap_or(Value::Array(vec![])))
    }

    pub fn recent_viewed(&self, limit: u32) -> Result<Value, String> {
        let body = self.fetch(&format!("{BASE}/api/operationHistory/safeRoom?pageNo=1&pageSize={limit}&operationTypes=3&creator="), "GET", None)?;
        Ok(body.get("data").cloned().unwrap_or(Value::Array(vec![])))
    }

    pub fn received_docs(&self, limit: u32) -> Result<Value, String> {
        let query_id = Uuid::new_v4().to_string();
        let body = self.fetch(&format!("{BASE}/api/data/userRelated/received/safeRoom?offset=0&limit={limit}&queryId={query_id}"), "GET", None)?;
        Ok(body.get("data").cloned().unwrap_or(Value::Array(vec![])))
    }

    pub fn create_doc(&self, title: &str, pm_json: Option<&str>, parent_id: Option<&str>) -> Result<(String, String), String> {
        // 如果没有提供 pm_json，创建最小的 PM JSON（对标 oaskills injectTitleIfMissing）
        let minimal_pm = json!({
            "type": "doc",
            "content": [
                {"type": "title", "attrs": {"nodeId": Uuid::new_v4().to_string().replace('-', "")}, "content": [{"type": "text", "text": title}]},
                {"type": "paragraph", "attrs": {"indent": 0, "align": "left", "dataDiffId": Value::Null, "nodeId": Uuid::new_v4().to_string().replace('-', "")}}
            ]
        });

        let content_json = if let Some(json) = pm_json {
            json.to_string()
        } else {
            serde_json::to_string(&minimal_pm).unwrap_or_default()
        };

        let mut body_obj = json!({
            "title": title,
            "content": content_json
        });

        if let Some(pid) = parent_id {
            body_obj["parentId"] = Value::String(pid.to_string());
        }

        let response = self.fetch(&format!("{BASE}/api/pages/addCollaborationContent"), "POST", Some(body_obj))?;

        // 响应格式：{"data": <contentId>, "status": 0}
        let id_str = if let Some(data) = response.get("data") {
            if let Some(id_val) = data.as_i64() {
                id_val.to_string()
            } else if let Some(id_val) = data.as_str() {
                id_val.to_string()
            } else {
                return Err(format!("无法获取 contentId，data 格式不对: {}", data));
            }
        } else {
            return Err(format!("响应缺少 data 字段: {}", response));
        };

        if id_str.is_empty() || id_str == "0" {
            return Err("创建文档失败：服务器未返回有效 contentId".into());
        }

        let url = format!("https://km.sankuai.com/collabpage/{}", id_str);
        Ok((id_str, url))
    }

    /// 上传 drawio SVG 到文档，返回 CDN URL（contentType=0）及宽高。
    /// drawio svg 直接以 image/svg+xml 上传到 /api/file/upload/{cid}，
    /// 返回的 attachment URL 转成 /api/file/cdn/{cid}/{aid}?contentType=0（对齐 oa-skills）
    pub fn upload_drawio(&self, content_id: &str, svg_bytes: Vec<u8>) -> Result<(String, u64, u64), String> {
        let part = reqwest::blocking::multipart::Part::bytes(svg_bytes)
            .file_name(format!("diagram-{}.svg", std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH).map(|d| d.as_millis()).unwrap_or(0)))
            .mime_str("image/svg+xml;charset=utf-8").map_err(|e| format!("mime 错误: {e}"))?;
        let form = reqwest::blocking::multipart::Form::new().part("file", part);
        let req = self.client.post(&format!("{BASE}/api/file/upload/{content_id}"))
            .header("access-token", &self.token)
            .header("x-requested-with", "XMLHttpRequest")
            .multipart(form);
        let res = req.send().map_err(|e| format!("上传 drawio 失败: {e}"))?;
        let body: Value = res.json().unwrap_or_default();
        let code = body.get("status").or_else(|| body.get("code")).and_then(|v| v.as_i64()).unwrap_or(0);
        if code != 0 {
            return Err(format!("上传 drawio 失败: {}", body.get("msg").or_else(|| body.get("message")).and_then(|v| v.as_str()).unwrap_or("unknown")));
        }
        let data = body.get("data").ok_or("上传 drawio 失败：响应缺少 data")?;
        let raw_url = data.get("url").and_then(|v| v.as_str()).ok_or("上传 drawio 失败：响应缺少 url")?;
        let parts: Vec<&str> = raw_url.rsplitn(3, '/').collect();
        if parts.len() < 2 {
            return Err(format!("上传 drawio 失败：无法解析 URL {raw_url}"));
        }
        let cdn_url = format!("{BASE}/api/file/cdn/{}/{}?contentType=0&isNewContent=false", parts[1], parts[0]);
        Ok((cdn_url, 0, 0))
    }

    /// 上传图片二进制到文档，返回 CDN URL（及宽高）。
    /// uploadphoto 返回 origin.url 格式 /api/file/{cid}/{fid}，
    /// 必须转成 /api/file/cdn/{cid}/{fid}?contentType=0&isNewContent=false，
    /// 否则学城 image 节点 schema 校验异常（对齐 oa-skills uploadImageToDocument）。
    pub fn upload_image(&self, content_id: &str, bytes: Vec<u8>, filename: &str) -> Result<(String, u64, u64), String> {
        let mime = mime_for(filename).unwrap_or("application/octet-stream");
        let part = reqwest::blocking::multipart::Part::bytes(bytes)
            .file_name(filename.to_string())
            .mime_str(mime).unwrap_or_else(|_| reqwest::blocking::multipart::Part::bytes(vec![]).file_name(filename.to_string()));
        let form = reqwest::blocking::multipart::Form::new().part("file", part);
        let req = self.client.post(&format!("{BASE}/api/file/uploadphoto/{content_id}"))
            .header("access-token", &self.token)
            .header("x-requested-with", "XMLHttpRequest")
            .multipart(form);
        let res = req.send().map_err(|e| format!("上传图片失败: {e}"))?;
        let body: Value = res.json().unwrap_or_default();
        let code = body.get("status").or_else(|| body.get("code")).and_then(|v| v.as_i64()).unwrap_or(0);
        if code != 0 {
            return Err(format!("上传图片失败: {}", body.get("msg").or_else(|| body.get("message")).and_then(|v| v.as_str()).unwrap_or("unknown")));
        }
        let origin = body.get("data").and_then(|d| d.get("origin")).ok_or("上传图片失败：响应缺少 origin")?;
        let raw_url = origin.get("url").and_then(|v| v.as_str()).ok_or("上传图片失败：响应缺少 url")?;
        let width = origin.get("width").and_then(|v| v.as_u64()).unwrap_or(0);
        let height = origin.get("height").and_then(|v| v.as_u64()).unwrap_or(0);
        // /api/file/{cid}/{fid} → /api/file/cdn/{cid}/{fid}?contentType=0&isNewContent=false
        let parts: Vec<&str> = raw_url.rsplitn(3, '/').collect();
        // parts[0]=fileId, parts[1]=contentId
        if parts.len() < 2 {
            return Err(format!("上传图片失败：无法解析 URL {raw_url}"));
        }
        let cdn_url = format!("{BASE}/api/file/cdn/{}/{}?contentType=0&isNewContent=false", parts[1], parts[0]);
        Ok((cdn_url, width, height))
    }

    /// 上传视频/音频，返回 CDN URL。endpoint=uploadMedia，contentType=video/audio
    pub fn upload_media(&self, content_id: &str, bytes: Vec<u8>, filename: &str, kind: &str) -> Result<(String, u64, u64), String> {
        let mime = match kind {
            "video" => "video/mp4",
            "audio" => "audio/mpeg",
            _ => "application/octet-stream",
        };
        let part = reqwest::blocking::multipart::Part::bytes(bytes)
            .file_name(filename.to_string())
            .mime_str(mime).unwrap_or_else(|_| reqwest::blocking::multipart::Part::bytes(vec![]).file_name(filename.to_string()));
        let form = reqwest::blocking::multipart::Form::new().part("file", part);
        let req = self.client.post(&format!("{BASE}/api/file/uploadMedia/{content_id}"))
            .header("access-token", &self.token)
            .header("x-requested-with", "XMLHttpRequest")
            .multipart(form);
        let res = req.send().map_err(|e| format!("上传失败: {e}"))?;
        let body: Value = res.json().unwrap_or_default();
        let code = body.get("status").or_else(|| body.get("code")).and_then(|v| v.as_i64()).unwrap_or(0);
        if code != 0 {
            return Err(format!("上传失败: {}", body.get("msg").or_else(|| body.get("message")).and_then(|v| v.as_str()).unwrap_or("unknown")));
        }
        let data = body.get("data").ok_or("上传失败：响应缺少 data")?;
        let raw_url = data.get("url").and_then(|v| v.as_str()).ok_or("上传失败：响应缺少 url")?;
        let parts: Vec<&str> = raw_url.rsplitn(3, '/').collect();
        if parts.len() < 2 { return Err(format!("上传失败：无法解析 URL {raw_url}")); }
        let ct = if kind == "video" { "video" } else { "1" }; // audio contentType=1
        let cdn_url = format!("{BASE}/api/file/cdn/{}/{}?contentType={ct}&isNewContent=false", parts[1], parts[0]);
        Ok((cdn_url, 0, 0))
    }

    /// 上传普通附件，返回 CDN URL。endpoint=upload
    pub fn upload_attachment(&self, content_id: &str, bytes: Vec<u8>, filename: &str) -> Result<(String, u64, u64), String> {
        let part = reqwest::blocking::multipart::Part::bytes(bytes)
            .file_name(filename.to_string());
        let form = reqwest::blocking::multipart::Form::new().part("file", part);
        let req = self.client.post(&format!("{BASE}/api/file/upload/{content_id}"))
            .header("access-token", &self.token)
            .header("x-requested-with", "XMLHttpRequest")
            .multipart(form);
        let res = req.send().map_err(|e| format!("上传失败: {e}"))?;
        let body: Value = res.json().unwrap_or_default();
        let code = body.get("status").or_else(|| body.get("code")).and_then(|v| v.as_i64()).unwrap_or(0);
        if code != 0 {
            return Err(format!("上传失败: {}", body.get("msg").or_else(|| body.get("message")).and_then(|v| v.as_str()).unwrap_or("unknown")));
        }
        let data = body.get("data").ok_or("上传失败：响应缺少 data")?;
        let raw_url = data.get("url").and_then(|v| v.as_str()).ok_or("上传失败：响应缺少 url")?;
        let parts: Vec<&str> = raw_url.rsplitn(3, '/').collect();
        if parts.len() < 2 { return Err(format!("上传失败：无法解析 URL {raw_url}")); }
        let cdn_url = format!("{BASE}/api/file/cdn/{}/{}?contentType=0&isNewContent=false", parts[1], parts[0]);
        Ok((cdn_url, 0, 0))
    }

    /// 扫描文本中的图片引用，把本地文件路径上传并替换成学城 CDN URL。
    /// 同时处理 markdown `![name](src)` 和 HTML `<img src="...">`。
    /// 规则：
    ///   - 学城 CDN URL（/api/file/cdn/）→ 直接用
    ///   - 本地路径（非 http）→ 读文件上传；读不到则 throw
    ///   - 其他 http(s) 远程 URL → throw，提示先下载到本地
    pub fn replace_images(&self, content_id: &str, text: &str) -> Result<String, String> {
        let mut out = String::with_capacity(text.len());
        let bytes = text.as_bytes();
        let mut i = 0;
        while i < bytes.len() {
            // markdown 图片 ![name](src)
            if text[i..].starts_with("![") {
                if let Some(end_name) = find_byte(&text[i..], b']') {
                    let after = &text[i + end_name + 1..];
                    if after.starts_with('(') {
                        if let Some(end_paren) = find_byte(after, b')') {
                            let name = &text[i + 2..i + end_name];
                            let src = &after[1..end_paren];
                            let new_src = self.resolve_image_src(content_id, src)?;
                            out.push_str(&format!("![{name}]({new_src})"));
                            i = i + end_name + 1 + end_paren + 1;
                            continue;
                        }
                    }
                }
            }
            // HTML img <img ... src="..." ...>
            if text[i..].to_lowercase().starts_with("<img") {
                if let Some(end_tag) = find_byte(&text[i..], b'>') {
                    let tag = &text[i..i + end_tag + 1];
                    if let Some(new_tag) = self.replace_img_src(content_id, tag)? {
                        out.push_str(&new_tag);
                        i += end_tag + 1;
                        continue;
                    }
                }
            }
            // 普通字符
            let ch_len = text[i..].char_indices().nth(1).map(|(j, _)| j).unwrap_or(text.len() - i);
            out.push_str(&text[i..i + ch_len]);
            i += ch_len;
        }
        Ok(out)
    }

    /// 处理单个图片 src，返回应替换的 URL
    fn resolve_image_src(&self, content_id: &str, src: &str) -> Result<String, String> {
        let lower = src.to_lowercase();
        if lower.starts_with("http://") || lower.starts_with("https://") {
            // 学城 CDN URL 直接用
            if src.contains("/api/file/cdn/") {
                return Ok(src.to_string());
            }
            // 其他远程 URL → throw
            return Err(format!(
                "不支持远程图片 URL，请先下载到本地后用本地路径引用：{src}"
            ));
        }
        // 本地路径：展开 ~
        let expanded = expand_tilde(src);
        let path = std::path::Path::new(&expanded);
        let bytes = std::fs::read(path).map_err(|e| {
            format!("图片读取失败（md 不应引用不存在的本地路径）：{src} — {e}")
        })?;
        let filename = path.file_name().and_then(|n| n.to_str()).unwrap_or("image.png");
        let (cdn_url, _w, _h) = self.upload_image(content_id, bytes, filename)?;
        eprintln!("[图片] 已上传：{} → {}", src, cdn_url);
        Ok(cdn_url)
    }

    /// 替换 <img ...> 标签里的 src
    fn replace_img_src(&self, content_id: &str, tag: &str) -> Result<Option<String>, String> {
        let lower = tag.to_lowercase();
        let src_key_pos = match lower.find("src=") {
            Some(p) => p,
            None => return Ok(None), // 无 src，不处理
        };
        let after_src = &tag[src_key_pos + 4..];
        let (quote, rest) = if after_src.starts_with('"') { ('"', &after_src[1..]) }
            else if after_src.starts_with('\'') { ('\'', &after_src[1..]) }
            else { return Ok(None); }; // 无引号 src 不处理
        let end = match rest.find(quote) {
            Some(p) => p,
            None => return Ok(None),
        };
        let src = &rest[..end];
        let new_src = self.resolve_image_src(content_id, src)?;
        let new_tag = format!("{}{}{}{}", &tag[..src_key_pos + 4], quote, new_src, &rest[end..]);
        Ok(Some(new_tag))
    }

    pub fn get_version_content(&self, content_id: &str, step_version: i64) -> Result<Value, String> {
        let body = self.fetch(&format!("{BASE}/api/docs/recent/safeRoom/{content_id}?stepVersion={step_version}&versionCheck=1"), "GET", None)?;
        let data = body.get("data").ok_or("无 data")?;
        let raw_body = data.get("body").ok_or("无 body")?;
        let pm_json: Value = if raw_body.is_string() {
            serde_json::from_str(raw_body.as_str().unwrap_or("")).unwrap_or(Value::Null)
        } else {
            raw_body.clone()
        };
        Ok(json!({
            "contentId": data.get("contentId"),
            "title": data.get("title"),
            "body": pm_json,
            "stepVersion": step_version
        }))
    }

    pub fn get_comments(&self, content_id: &str, limit: u32) -> Result<Value, String> {
        let body = self.fetch(&format!("{BASE}/api/comment/safeRoom/{content_id}?offset=0&limit={limit}&sortType=1&parentCommentId=&commentId=&contentType=0"), "GET", None)?;
        Ok(body.get("data").cloned().unwrap_or(Value::Null))
    }

    pub fn add_comment(&self, content_id: &str, text: &str, parent_id: Option<&str>) -> Result<String, String> {
        let parent_cid = parent_id.and_then(|p| p.parse::<i64>().ok()).unwrap_or(0);
        let body = json!({
            "commentType": 1,
            "commentContent": format!("<p>{}</p>", text),
            "parentCommentId": parent_cid,
            "extension": {
                "linkedContent": [],
                "mentionList": [],
                "images": []
            },
            "contentType": 0
        });
        let response = self.fetch(&format!("{BASE}/api/comment/{content_id}"), "POST", Some(body))?;
        // data 可能直接是 commentId（数字），也可能是 {commentId} 对象
        response.get("data").and_then(|d| {
            d.get("commentId").and_then(|v| v.as_i64().map(|n| n.to_string()).or_else(|| v.as_str().map(String::from)))
                .or_else(|| d.as_i64().map(|n| n.to_string()))
                .or_else(|| d.as_str().map(String::from))
        }).ok_or_else(|| "无 commentId".into())
    }

    pub fn set_secret_level(&self, content_id: &str, level: &str) -> Result<(), String> {
        let level_num = level.parse::<i64>().map_err(|_| "密级必须是数字".to_string())?;
        if ![2, 3, 4].contains(&level_num) {
            return Err("密级必须是 2、3 或 4".to_string());
        }
        let body = json!({ "secretLevel": level_num });
        self.fetch(&format!("{BASE}/api/pages/secret/{content_id}"), "POST", Some(body))?;
        Ok(())
    }

    pub fn create_from_template(&self, title: &str, copy_from: &str, parent_id: Option<&str>) -> Result<(String, String), String> {
        let space_id = self.get_space_id(copy_from)?;
        let parent = parent_id.unwrap_or("0");
        let body = json!({
            "parentId": parent,
            "type": 3,
            "copyFromContentId": copy_from,
            "title": title,
            "width": 0
        });
        let response = self.fetch(&format!("{BASE}/api/docs/{space_id}/add"), "POST", Some(body))?;
        let data = response.get("data").ok_or("无 data")?;
        // contentId 可能是数字或字符串，也可能嵌套在对象里
        let id = data.get("contentId")
            .and_then(|v| v.as_i64().map(|n| n.to_string()).or_else(|| v.as_str().map(String::from)))
            .or_else(|| data.as_i64().map(|n| n.to_string()))
            .or_else(|| data.as_str().map(String::from))
            .ok_or("无 contentId")?;
        let url = format!("https://km.sankuai.com/collabpage/{id}");
        Ok((id, url))
    }

    pub fn restore_doc(&self, content_id: &str) -> Result<(), String> {
        let space_id = self.get_space_id(content_id)?;
        self.fetch(&format!("{BASE}/api/restore/restore/{space_id}/{content_id}"), "POST", Some(json!({})))?;
        Ok(())
    }

    pub fn mentioned_docs(&self, limit: u32) -> Result<Value, String> {
        let body = self.fetch(&format!("{BASE}/api/data/userRelated/mentioned/safeRoom?offset=0&limit={limit}"), "GET", None)?;
        Ok(body.get("data").cloned().unwrap_or(Value::Array(vec![])))
    }

    pub fn commented_docs(&self, limit: u32) -> Result<Value, String> {
        let body = self.fetch(&format!("{BASE}/api/data/userRelated/commented/safeRoom?offset=0&limit={limit}"), "GET", None)?;
        Ok(body.get("data").cloned().unwrap_or(Value::Array(vec![])))
    }

    pub fn knowledge_square(&self, kind: u32, limit: u32) -> Result<Value, String> {
        let body = self.fetch(&format!("{BASE}/api/community/articles/feed?type={kind}&limit={limit}"), "GET", None)?;
        Ok(body.get("data").cloned().unwrap_or(Value::Array(vec![])))
    }

    pub fn get_discussions(&self, content_id: &str, limit: u32) -> Result<Value, String> {
        let body = json!({
            "contentId": content_id.parse::<i64>().unwrap_or(0),
            "pageNo": 1,
            "pageSize": limit,
            "quoteIds": []
        });
        let response = self.fetch(&format!("{BASE}/api/comment/discussion/list/safeRoom"), "POST", Some(body))?;
        Ok(response.get("data").cloned().unwrap_or(Value::Null))
    }

    pub fn reply_discussion(&self, content_id: &str, discussion_id: &str, quote_id: &str, text: &str) -> Result<String, String> {
        let content_json = json!({
            "type": "doc",
            "content": [{
                "type": "paragraph",
                "content": [{"type": "text", "text": text}]
            }]
        });
        let body = json!({
            "content": serde_json::to_string(&content_json).unwrap_or_default(),
            "contentText": text,
            "mentionList": [],
            "images": [],
            "discussionId": discussion_id,
            "quoteId": quote_id,
            "contentId": content_id.parse::<i64>().unwrap_or(0)
        });
        let response = self.fetch(&format!("{BASE}/api/comment/discussion/comment/create"), "POST", Some(body))?;
        response.get("data").and_then(|d| d.get("commentId")).and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .ok_or_else(|| "无 commentId".into())
    }

    /// 查询文档权限列表（对齐 oa-skills listPermissions）
    /// 遍历所有 userGroupType (0-5) 分页拉取合并，misId 为鉴权必填。
    pub fn query_permissions(&self, content_id: &str, _page: u32) -> Result<Value, String> {
        let mis = self.mis.as_deref().unwrap_or("");
        let mut all = Vec::new();
        for ugt in 0..=5 {
            let mut page_no = 1u32;
            let page_size = 50u32;
            loop {
                let url = format!("{BASE}/api/permission/content/{content_id}/query?userGroupType={ugt}&pageSize={page_size}&pageNo={page_no}&misId={mis}");
                let body = match self.fetch(&url, "GET", None) {
                    Ok(b) => b,
                    Err(_) => break, // 某些 userGroupType 查询失败不中断整体
                };
                let data = body.get("data").cloned().unwrap_or(Value::Null);
                let records = data.get("records").and_then(|v| v.as_array()).cloned().unwrap_or_default();
                let total = data.get("total").and_then(|v| v.as_i64()).unwrap_or(0) as u32;
                let len = records.len() as u32;
                let fetched = (page_no - 1) * page_size + len;
                all.extend(records);
                if len == 0 || fetched >= total || len < page_size {
                    break;
                }
                page_no += 1;
            }
        }
        Ok(json!({ "total": all.len(), "records": all }))
    }

    pub fn grant_permission(&self, content_id: &str, perm: &str, mis: Option<&str>, group: Option<&str>, mail: Option<&str>) -> Result<(), String> {
        let perm_group_type = perm_group_type(perm)?;
        // userGroupType 映射（对齐 oa-skills USER_GROUP_TYPES）
        let mut body_obj = json!({
            "contentId": content_id.parse::<i64>().unwrap_or(0),
            "permGroupType": perm_group_type,
        });
        if let Some(m) = mis {
            body_obj["userGroupType"] = json!(1); // PERSON
            body_obj["mis"] = Value::Array(vec![Value::String(m.to_string())]);
        } else if let Some(g) = group {
            body_obj["userGroupType"] = json!(4); // XM
            body_obj["xmGroupIds"] = Value::Array(vec![Value::String(g.to_string())]);
        } else if let Some(ma) = mail {
            body_obj["userGroupType"] = json!(3); // MAIL
            body_obj["mails"] = Value::Array(vec![Value::String(ma.to_string())]);
        }
        self.fetch(&format!("{BASE}/api/permission/content/{content_id}/add"), "POST", Some(body_obj))?;
        Ok(())
    }

    pub fn revoke_permission(&self, content_id: &str, perm_id: &str) -> Result<(), String> {
        let body = json!({
            "permId": perm_id,
            "permissionCategory": "USER"
        });
        self.fetch(&format!("{BASE}/api/permission/content/{content_id}/delete"), "POST", Some(body))?;
        Ok(())
    }

    /// 下载学城 CDN 资源（图片/drawio/视频/音频），返回二进制 + content-type。
    /// 所有 CDN URL 都可直接 GET + access-token 下载。
    pub fn download_resource(&self, url: &str) -> Result<(Vec<u8>, String), String> {
        let req = self.client.get(url).header("access-token", &self.token);
        let res = req.send().map_err(|e| format!("下载失败: {e}"))?;
        if !res.status().is_success() {
            return Err(format!("下载失败: HTTP {}", res.status()));
        }
        let content_type = res.headers().get("content-type")
            .and_then(|v| v.to_str().ok())
            .unwrap_or("application/octet-stream")
            .split(';').next().unwrap_or("application/octet-stream").trim().to_string();
        let bytes = res.bytes().map_err(|e| format!("读取内容失败: {e}"))?.to_vec();
        Ok((bytes, content_type))
    }

    pub fn fetch_drawio(&self, url: &str) -> Result<String, String> {
        let (bytes, _) = self.download_resource(url)?;
        String::from_utf8(bytes).map_err(|e| format!("Drawio 内容非 UTF-8 文本: {e}"))
    }
}

/// 在字符串中查找某个字节，返回相对偏移

fn mime_for(filename: &str) -> Option<&'static str> {
    let ext = filename.rsplit('.').next()?.to_lowercase();
    match ext.as_str() {
        "png" => Some("image/png"),
        "jpg" | "jpeg" => Some("image/jpeg"),
        "gif" => Some("image/gif"),
        "webp" => Some("image/webp"),
        "svg" => Some("image/svg+xml"),
        "bmp" => Some("image/bmp"),
        _ => Some("application/octet-stream"),
    }
}

fn find_byte(s: &str, b: u8) -> Option<usize> {
    s.as_bytes().iter().position(|&x| x == b)
}

/// 展开 ~ 为 home 目录（跨平台）
fn expand_tilde(path: &str) -> String {
    if path == "~" || path.starts_with("~/") {
        if let Some(home) = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")) {
            let home = home.to_string_lossy().to_string();
            if path == "~" { return home; }
            return format!("{}{}", home, &path[1..]);
        }
    }
    path.to_string()
}

/// 从学城列表接口的 data 字段提取文档数组。
/// data 可能是直接的 array，也可能是 {originCount, list:[...]} 或 {list:[...]} 结构。
fn extract_list(data: Option<&Value>) -> Value {
    match data {
        Some(Value::Array(_)) => data.cloned().unwrap_or(Value::Array(vec![])),
        Some(obj) => obj.get("list")
            .or_else(|| obj.get("records"))
            .cloned()
            .unwrap_or(Value::Array(vec![])),
        None => Value::Array(vec![]),
    }
}

/// 从学城搜索接口的 data 字段提取结果数组。
/// 搜索 API 的 data 是对象 {totalCount, models:[...]}（非数组），
/// 历史上也兼容直接返回数组的情况。
pub fn extract_search_models(data: Option<&Value>) -> Value {
    match data {
        Some(Value::Array(arr)) => Value::Array(arr.clone()),
        Some(Value::Object(obj)) => obj.get("models")
            .cloned()
            .unwrap_or(Value::Array(vec![])),
        _ => Value::Array(vec![]),
    }
}

/// 从搜索/列表结果项中提取 contentId 字符串。
/// contentId 在学城搜索 API 中是数字（如 2769065161），
/// 在部分列表接口中是字符串，两者都需兼容。
pub fn content_id_to_string(v: &Value) -> String {
    v.as_i64().map(|n| n.to_string())
        .or_else(|| v.as_str().map(String::from))
        .unwrap_or_default()
}

/// 提取文档 ID：只接受纯数字。传入 URL 等非纯数字一律报错，
/// 提示 AI 自己从链接里提取数字 ID。
pub fn extract_id(input: &str) -> Result<String, String> {
    let s = input.trim();
    if s.chars().all(|c| c.is_ascii_digit()) && !s.is_empty() {
        return Ok(s.to_string());
    }
    Err(format!("文档 ID 必须是纯数字，收到：\"{input}\"。如果传入的是学城链接，请先提取其中的数字 ID"))
}

#[cfg(test)]
mod tests {
    use super::{contains_id, content_id_to_string, extract_list, extract_search_models, find_path, perm_group_type};
    use serde_json::{json, Value};

    #[test]
    fn test_extract_list_from_origincount_list() {
        // /api/pages/child 返回 {originCount, list}
        let data = json!({ "originCount": 2, "list": [{"contentId": 1}, {"contentId": 2}] });
        let v = extract_list(Some(&data));
        let arr = v.as_array().unwrap();
        assert_eq!(arr.len(), 2);
    }

    #[test]
    fn test_extract_list_from_list_only() {
        // /api/spaces/child 返回 {list}
        let data = json!({ "list": [{"contentId": 10}] });
        let v = extract_list(Some(&data));
        assert_eq!(v.as_array().unwrap().len(), 1);
    }

    #[test]
    fn test_extract_list_from_bare_array() {
        // 直接是 array 的兼容
        let data = json!([1, 2, 3]);
        let v = extract_list(Some(&data));
        assert_eq!(v.as_array().unwrap().len(), 3);
    }

    #[test]
    fn test_extract_list_empty() {
        // data 为空对象
        let data = json!({});
        let v = extract_list(Some(&data));
        assert!(v.as_array().unwrap().is_empty());
        // data 为 None
        let v = extract_list(None);
        assert!(v.as_array().unwrap().is_empty());
    }

    // ---- extract_search_models：search_docs 结果提取（修复“全站搜索返回无结果”的 bug）----

    #[test]
    fn test_extract_search_models_from_object() {
        // 搜索 API 实际返回：data 是对象 {totalCount, models:[...]}
        // contentId 在真实 API 中是大数字（如 2769065161），这里用 i32 范围内的值测试结构，
        // 大数字 ID 的行为由 tests/search_tests.rs 配合 fixture 覆盖
        let data = json!({
            "totalCount": 2,
            "models": [
                {"contentId": 1461835105, "title": "构建前端容器的反馈回路"},
                {"contentId": 100200, "title": "系统思考"}
            ]
        });
        let v = extract_search_models(Some(&data));
        let arr = v.as_array().unwrap();
        assert_eq!(arr.len(), 2);
        assert_eq!(arr[0]["title"], "构建前端容器的反馈回路");
    }

    #[test]
    fn test_extract_search_models_from_bare_array() {
        // 兼容老接口直接返回数组的情况
        let data = json!([
            {"contentId": 1, "title": "a"},
            {"contentId": 2, "title": "b"}
        ]);
        let v = extract_search_models(Some(&data));
        assert_eq!(v.as_array().unwrap().len(), 2);
    }

    #[test]
    fn test_extract_search_models_object_without_models() {
        // 对象但没有 models 字段 -> 空数组，不 panic
        let data = json!({ "totalCount": 0 });
        let v = extract_search_models(Some(&data));
        assert!(v.as_array().unwrap().is_empty());
    }

    #[test]
    fn test_extract_search_models_empty_and_none() {
        // data 为空对象
        assert!(extract_search_models(Some(&json!({}))).as_array().unwrap().is_empty());
        // data 为 None
        assert!(extract_search_models(None).as_array().unwrap().is_empty());
    }

    // ---- content_id_to_string：兼容 contentId 为数字或字符串（修复搜索结果不显示 ID 的 bug）----

    #[test]
    fn test_content_id_to_string_numeric() {
        // 搜索 API 的 contentId 是数字（i32 范围内用 json! 宏测试）
        assert_eq!(content_id_to_string(&json!(1461835105)), "1461835105");
        assert_eq!(content_id_to_string(&json!(0)), "0");
        // 大数字（超过 i32）通过字符串 fixture 在 tests/search_tests.rs 覆盖
    }

    #[test]
    fn test_content_id_to_string_string() {
        // 列表 API 的 contentId 可能是字符串
        assert_eq!(content_id_to_string(&json!("1461835105")), "1461835105");
    }

    #[test]
    fn test_content_id_to_string_empty_and_invalid() {
        assert_eq!(content_id_to_string(&Value::Null), "");
        assert_eq!(content_id_to_string(&json!(true)), "");
        assert_eq!(content_id_to_string(&json!({})), "");
    }

    // ---- find_path / contains_id：move_doc 移动后校验的核心 ----

    fn sample_tree() -> serde_json::Value {
        // 空间根 -> A(100200) -> 子1(100201), 子2(100202)
        //         -> B(100300)
        json!([
            {"content": {"contentId": 100200, "title": "A"}, "children": [
                {"content": {"contentId": 100201, "title": "子1"}},
                {"content": {"contentId": 100202, "title": "子2"}}
            ]},
            {"content": {"contentId": 100300, "title": "B"}}
        ])
    }

    #[test]
    fn test_find_path_root_node() {
        let tree = sample_tree();
        let nodes = tree.as_array().unwrap();
        // 直接是顶层节点
        assert_eq!(find_path(nodes, 100300), Some(vec![100300]));
    }

    #[test]
    fn test_find_path_nested_node() {
        let tree = sample_tree();
        let nodes = tree.as_array().unwrap();
        // 嵌套子节点：路径应含父链
        assert_eq!(find_path(nodes, 100201), Some(vec![100200, 100201]));
    }

    #[test]
    fn test_find_path_not_found() {
        let tree = sample_tree();
        let nodes = tree.as_array().unwrap();
        assert_eq!(find_path(nodes, 999999), None);
    }

    #[test]
    fn test_contains_id_present() {
        let tree = sample_tree();
        let nodes = tree.as_array().unwrap();
        assert!(contains_id(nodes, 100201));   // 深层
        assert!(contains_id(nodes, 100200));    // 顶层
    }

    #[test]
    fn test_contains_id_absent() {
        let tree = sample_tree();
        let nodes = tree.as_array().unwrap();
        assert!(!contains_id(nodes, 888888));
    }

    // ---- perm_group_type：grant_permission 的权限类型映射 ----

    #[test]
    fn test_perm_group_type_aliases() {
        assert_eq!(perm_group_type("view").unwrap(), 5);
        assert_eq!(perm_group_type("仅浏览").unwrap(), 5);
        assert_eq!(perm_group_type("comment").unwrap(), 0);
        assert_eq!(perm_group_type("可浏览、评论").unwrap(), 0);
        assert_eq!(perm_group_type("edit").unwrap(), 2);
        assert_eq!(perm_group_type("可编辑").unwrap(), 2);
        assert_eq!(perm_group_type("可编辑、添加").unwrap(), 3);
        assert_eq!(perm_group_type("可编辑、添加、删除").unwrap(), 1);
        assert_eq!(perm_group_type("manage").unwrap(), 4);
        assert_eq!(perm_group_type("可管理").unwrap(), 4);
    }

    #[test]
    fn test_perm_group_type_numeric() {
        // 纯数字字符串直接当数字用
        assert_eq!(perm_group_type("5").unwrap(), 5);
        assert_eq!(perm_group_type("0").unwrap(), 0);
    }

    #[test]
    fn test_perm_group_type_invalid() {
        assert!(perm_group_type("foobar").is_err());
        assert!(perm_group_type("").is_err());
    }

    // 注：extract_id 的解析/reject 场景已由 tests/auth_utils_tests.rs 全面覆盖，此处不再重复。
}
