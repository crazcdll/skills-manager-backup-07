use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::thread;
use std::time::Duration;

const DEFAULT_REFRESH_BUF_MS: i64 = 5 * 60 * 1000;
const DEFAULT_CACHE_TTL_MS: i64 = 10 * 60 * 1000;
const CITADEL_CLIENT: &str = "com.sankuai.it.ead.citadel";
const SUPABASE_BASE: &str = "https://supabase.sankuai.com";
const SSO_PRODUCT_HOST: &str = "https://ssosv.sankuai.com";
const SSO_TEST_HOST: &str = "https://ssosv.it.test.sankuai.com";
const SSO_CIBA_PATH: &str = "/sson/auth/oidc/v1/bc-authorize";
const SSO_TOKEN_PATH: &str = "/sson/auth/oidc/v1/token";

// CIBA 默认凭据
const CIBA_CLIENT_ID: &str = "c01e2e3a3e";
const CIBA_CLIENT_SECRET: &str = "f2d75b31a609457caf9725f3c590f102";
const CIBA_TEST_CLIENT_ID: &str = "3714a4c2fb";
const CIBA_TEST_CLIENT_SECRET: &str = "982fec62a4d943ef8be9f5643b445a07";
const CIBA_BOT_CLIENT_ID: &str = "e60c669cd4";
const CIBA_BOT_DESCRIPTION: &str =
    "citadel 正在向你发起授权，如非本人操作请不要同意(通过办公官方 Skills 鉴权服务触发)";

// MOA 无感登录：和 @it/oa-skills-shared 保持一致，调用官方 @mtfe/mtsso-auth-official CLI。
const NPM_REGISTRY: &str = "http://r.npm.sankuai.com";
const MOA_PROBE_CMD: &str = "mtsso-moa-feature-probe";
const MOA_EXCHANGE_CMD: &str = "mtsso-moa-local-exchange";
const MOA_PROBE_TIMEOUT_MS: u64 = 7000;
const MOA_EXCHANGE_TIMEOUT_MS: u64 = 30000;

/// 获取认证 token（对标 oa-skills 四级认证策略）
///
/// 优先级：
///   1. oa-skills 缓存（~/.cache/openclaw-auth/auth-cache.json）
///   2. MOA 无感登录（官方 mtsso 命令，无需用户交互）
///   3. Dumbo 飞象 App 换票
///   4. CatPaw Desk 换票
///   5. Supabase CIBA（Sandbox 环境）
///   6. SSO CIBA 大象审批（手机确认）
///
/// 缓存未命中时自动降级尝试后续策略。
/// 无法确定 MIS 号时会提示使用 km login --mis。
///
/// # Arguments
/// * `mis` - MIS 号，为 None 时自动查找（MAAS_USER_ID → clawdgw.json → openclaw.json → oa-skills 缓存 key 解析）
pub fn get_token(mis: Option<&str>) -> Result<String, String> {
    let user_id = mis
        .map(String::from)
        .or_else(load_default_user_id)
        .ok_or("无法确定 MIS 号，请先执行：km login --mis <MIS>")?;

    // 1. 统一策略缓存（MOA / 飞象 / CatPaw / Supabase）。
    if let Some(token) = read_unified_token_cache(&user_id) {
        return Ok(token);
    }

    eprintln!("[auth] 未命中缓存，尝试自动认证...");

    // 2. MOA 无感登录
    if !is_test_env() && probe_moa_seamless_support() {
        match get_moa_token() {
            Ok(token) => {
                let _ = write_unified_token_cache(&user_id, &token);
                return Ok(token);
            }
            Err(e) => eprintln!("[auth] MOA 无感登录失败: {}", e),
        }
    }

    // 3. 飞象 App 换票（Dumbo）
    if std::env::var("DUMBO_WORKSPACE_ROOT").is_ok()
        && let Ok(token) = dumbo_exchange()
    {
        let _ = write_unified_token_cache(&user_id, &token);
        return Ok(token);
    }

    // 4. CatPaw Desk 换票
    if is_catpaw_desk()
        && let Ok(sso_cfg) = read_catpaw_config()
        && let Ok(token) = catpaw_exchange(&sso_cfg)
    {
        let _ = write_unified_token_cache(&user_id, &token);
        return Ok(token);
    }

    // 5. Supabase CIBA 流程
    if !is_test_env() && is_claw_environment() {
        match get_supabase_ciba_token(&user_id) {
            Ok(token) => {
                let _ = write_unified_token_cache(&user_id, &token);
                return Ok(token);
            }
            Err(e) => eprintln!("[auth] Supabase CIBA 失败: {}", e),
        }
    }

    // 6. SSO CIBA 流程（最终兜底）。使用独立的 app / CIBA 两级缓存。
    if let Some(app_token) = read_sso_app_token_cache(&user_id) {
        return Ok(app_token);
    }
    if let Some(mut ciba) = read_ciba_token_cache(&user_id) {
        if ciba.expires_at <= chrono_now_ms() + refresh_buffer_ms()
            && let Some(refresh_token) = &ciba.refresh_token
            && let Ok(refreshed) = refresh_sso_ciba_token(refresh_token)
        {
            write_ciba_token_cache(&user_id, &refreshed)?;
            ciba = refreshed;
        }
        match exchange_sso_ciba_token(&ciba.token) {
            Ok(app_token) => {
                write_current_token_cache(&user_id, &app_token)?;
                return Ok(app_token.token);
            }
            Err(e) => eprintln!("[auth] CIBA 缓存换票失败，将重新授权: {e}"),
        }
    }

    eprintln!("[auth] 请在手机大象 App 确认登录...");
    match get_sso_ciba_token(&user_id) {
        Ok(tokens) => {
            write_ciba_token_cache(&user_id, &tokens.ciba)?;
            write_current_token_cache(&user_id, &tokens.app)?;
            Ok(tokens.app.token)
        }
        Err(e) => Err(format!("认证失败: {}", e)),
    }
}

/// 返回当前已认证用户的 MIS 号（供需要 mis 但命令行未传 --mis 的场景兜底）
pub fn current_mis() -> Option<String> {
    load_default_user_id()
}

fn load_default_user_id() -> Option<String> {
    // 优先级 1：MAAS_USER_ID 环境变量
    if let Ok(maas) = std::env::var("MAAS_USER_ID")
        && !maas.is_empty()
        && !is_placeholder(&maas)
    {
        return Some(maas);
    }

    // 优先级 2：~/.config/clawdgw.json
    let clawdgw = dirs_home().join(".config").join("clawdgw.json");
    if let Ok(data) = fs::read_to_string(&clawdgw)
        && let Ok(cfg) = serde_json::from_str::<Value>(&data)
        && let Some(user_id) = cfg.get("defaultUserId").and_then(Value::as_str)
        && !is_placeholder(user_id)
    {
        return Some(user_id.to_string());
    }

    // 优先级 3：~/.openclaw/openclaw.json
    let openclaw = dirs_home().join(".openclaw").join("openclaw.json");
    if let Ok(data) = fs::read_to_string(&openclaw)
        && let Ok(cfg) = serde_json::from_str::<Value>(&data)
        && let Some(user_id) = cfg
            .get("models")
            .and_then(|m| m.get("providers"))
            .and_then(|p| p.get("kubeplex-maas"))
            .and_then(|k| k.get("headers"))
            .and_then(|h| h.get("X-User-Id"))
            .and_then(Value::as_str)
        && !is_placeholder(user_id)
    {
        return Some(user_id.to_string());
    }

    // 优先级 4：oa-skills 共享缓存 key（保底，本机只有一个用户）
    if let Some(mis) = try_extract_mis_from_oa_cache() {
        return Some(mis);
    }

    None
}

/// 从 oa-skills 缓存 key 中解析 MIS（本机单用户保底）
fn try_extract_mis_from_oa_cache() -> Option<String> {
    let path = auth_cache_path();
    let data = fs::read_to_string(&path).ok()?;
    let cache: Value = serde_json::from_str(&data).ok()?;
    let tokens = cache.get("tokens")?.as_object()?;
    for key in tokens.keys() {
        if let Some(mis) = parse_mis_from_cache_key(key)
            && !is_placeholder(&mis)
        {
            return Some(mis);
        }
    }
    None
}

/// 从缓存 key 中提取 MIS 号
fn parse_mis_from_cache_key(key: &str) -> Option<String> {
    if let Some(rest) = key.strip_prefix("sso-ciba:") {
        return rest.split(':').next().map(String::from);
    }
    if let Some(rest) = key.strip_prefix("sso-unified:")
        && let Some((_, mis)) = rest.split_once(':')
    {
        return Some(mis.to_string());
    }
    None
}

pub fn is_placeholder(s: &str) -> bool {
    if s.is_empty() || s == "default" {
        return true;
    }
    let inner = s
        .strip_prefix("{{")
        .and_then(|value| value.strip_suffix("}}"))
        .or_else(|| {
            s.strip_prefix("${")
                .and_then(|value| value.strip_suffix('}'))
        });
    inner.is_some_and(|value| {
        !value.is_empty()
            && value
                .chars()
                .all(|character| character.is_ascii_alphanumeric() || character == '_')
    })
}

fn dirs_cache() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp"))
        .join(".cache")
}

fn auth_cache_path() -> PathBuf {
    std::env::var("AUTH_CACHE_FILE")
        .map(PathBuf::from)
        .unwrap_or_else(|_| dirs_cache().join("openclaw-auth").join("auth-cache.json"))
}

fn read_catpaw_config() -> Result<Value, String> {
    let path = dirs_home().join(".catpaw").join("sso_config.json");
    let data = fs::read_to_string(&path).map_err(|e| format!("读取 CatPaw 配置失败: {e}"))?;
    serde_json::from_str(&data).map_err(|e| format!("解析 CatPaw 配置失败: {e}"))
}

fn is_catpaw_desk() -> bool {
    let Ok(content) = std::env::var("CATPAW_CONFIG_CONTENT") else {
        return false;
    };
    serde_json::from_str::<Value>(&content)
        .ok()
        .and_then(|config| config.get("source")?.as_str().map(String::from))
        .as_deref()
        == Some("CatPawDesk")
}

fn catpaw_exchange(cfg: &Value) -> Result<String, String> {
    let ssoid = cfg
        .get("ssoid")
        .and_then(|v| v.as_str())
        .ok_or("CatPaw 配置缺少 ssoid")?;
    // misId 用于验证配置完整性，但换票时使用 ssoid 即可
    let _ = cfg
        .get("misId")
        .and_then(|v| v.as_str())
        .ok_or("CatPaw 配置缺少 misId")?;

    let client = reqwest::blocking::Client::new();
    let res = client
        .post(format!(
            "{SUPABASE_BASE}/api/sandbox/sso/exchange-token-by-client-ids"
        ))
        .header("Content-Type", "application/json")
        .json(&serde_json::json!({
            "accessToken": ssoid,
            "clientIds": [CITADEL_CLIENT],
        }))
        .send()
        .map_err(|e| format!("CatPaw 换票 HTTP 错误: {e}"))?;

    let body: Value = res
        .json()
        .map_err(|e| format!("CatPaw 换票响应解析失败: {e}"))?;
    let code = body.get("code").and_then(|v| v.as_i64()).unwrap_or(-1);
    if code != 0 {
        return Err(format!(
            "CatPaw 换票失败: {}",
            body.get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("未知错误")
        ));
    }

    let token = body
        .get("data")
        .and_then(|v| {
            if v.is_string() {
                v.as_str()
            } else {
                v.get(CITADEL_CLIENT).and_then(|v| v.as_str())
            }
        })
        .ok_or("CatPaw 换票响应中未找到 citadel token")?;

    Ok(token.to_string())
}

/// 检测 MOA 无感登录支持。
///
/// 行为对齐 @it/oa-skills-shared：
/// `npx --registry http://r.npm.sankuai.com mtsso-moa-feature-probe` 返回 JSON 且 `ok=true`
/// 才认为无感可用。
fn probe_moa_seamless_support() -> bool {
    match run_official_moa_command(
        MOA_PROBE_TIMEOUT_MS,
        &["--registry", NPM_REGISTRY, MOA_PROBE_CMD],
    ) {
        Ok(out) => match parse_json_object(&out.stdout) {
            Ok(json) if json.get("ok").and_then(|v| v.as_bool()) == Some(true) => {
                let status = json.get("status").and_then(|v| v.as_str()).unwrap_or("");
                let endpoint = json.get("endpoint").and_then(|v| v.as_str()).unwrap_or("");
                eprintln!("[auth] MOA 无感登录可用（status={status}, endpoint={endpoint}）");
                true
            }
            Ok(json) => {
                let reason = json
                    .get("reason")
                    .and_then(|v| v.as_str())
                    .unwrap_or("ok=false");
                eprintln!("[auth] MOA 无感登录不可用：{reason}");
                false
            }
            Err(e) => {
                eprintln!("[auth] MOA 无感登录不可用：probe 输出无法解析: {e}");
                false
            }
        },
        Err(e) => {
            eprintln!("[auth] MOA 无感登录不可用：{e}");
            false
        }
    }
}

/// MOA 无感登录获取 token。
///
/// 对齐官方 `callMoaLocalExchange`：
/// `npx --registry http://r.npm.sankuai.com mtsso-moa-local-exchange --audience <client> -e PROD`
fn get_moa_token() -> Result<String, String> {
    let out = run_official_moa_command(
        MOA_EXCHANGE_TIMEOUT_MS,
        &[
            "--registry",
            NPM_REGISTRY,
            MOA_EXCHANGE_CMD,
            "--audience",
            CITADEL_CLIENT,
            "-e",
            "PROD",
        ],
    )?;
    let json = parse_json_object(&out.stdout)?;
    if let Some(token) = json.get("access_token").and_then(|v| v.as_str()) {
        return Ok(token.to_string());
    }
    if let Some(err) = json.get("error") {
        return Err(format!(
            "{} 返回错误: {}",
            MOA_EXCHANGE_CMD,
            sanitize_auth_message(&err.to_string())
        ));
    }
    Err(format!("{} 响应中未找到 access_token", MOA_EXCHANGE_CMD))
}

struct CommandOutput {
    stdout: String,
}

fn run_official_moa_command(timeout_ms: u64, args: &[&str]) -> Result<CommandOutput, String> {
    use std::io::Read;
    use std::time::{Duration as StdDuration, Instant};

    let mut child = Command::new("npx")
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("启动 npx 失败: {e}"))?;

    let started = Instant::now();
    loop {
        if let Some(status) = child
            .try_wait()
            .map_err(|e| format!("等待 npx 失败: {e}"))?
        {
            let mut stdout = String::new();
            let mut stderr = String::new();
            if let Some(mut pipe) = child.stdout.take() {
                let _ = pipe.read_to_string(&mut stdout);
            }
            if let Some(mut pipe) = child.stderr.take() {
                let _ = pipe.read_to_string(&mut stderr);
            }
            if stdout.trim().is_empty() {
                return Err(format!(
                    "{} 未输出 JSON: {}",
                    args.get(2).copied().unwrap_or("npx"),
                    sanitize_auth_message(&stderr)
                ));
            }
            if !status.success() {
                return Err(format!(
                    "{} 执行失败: {}",
                    args.get(2).copied().unwrap_or("npx"),
                    sanitize_auth_message(if stderr.trim().is_empty() {
                        &stdout
                    } else {
                        &stderr
                    })
                ));
            }
            return Ok(CommandOutput { stdout });
        }
        if started.elapsed() >= StdDuration::from_millis(timeout_ms) {
            let _ = child.kill();
            let _ = child.wait();
            return Err(format!(
                "{} 超时（{}ms）",
                args.get(2).copied().unwrap_or("npx"),
                timeout_ms
            ));
        }
        std::thread::sleep(StdDuration::from_millis(50));
    }
}

fn parse_json_object(raw: &str) -> Result<Value, String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Err("空输出".to_string());
    }
    if let Ok(json) = serde_json::from_str::<Value>(trimmed) {
        return Ok(json);
    }
    let start = trimmed.find('{').ok_or("未找到 JSON 起始符")?;
    let end = trimmed.rfind('}').ok_or("未找到 JSON 结束符")?;
    serde_json::from_str::<Value>(&trimmed[start..=end]).map_err(|e| format!("JSON 解析失败: {e}"))
}

fn sanitize_auth_message(raw: &str) -> String {
    raw.split_whitespace()
        .map(|part| {
            let lower = part.to_ascii_lowercase();
            if lower.contains("token") || lower.contains("secret") || lower.contains("assertion") {
                "[REDACTED]".to_string()
            } else {
                part.to_string()
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

/// 飞象 App 换票（对标 JS auth.js getDumboToken()）
fn dumbo_exchange() -> Result<String, String> {
    let ctx = load_dumbo_user_context()?;
    let uid = ctx
        .get("uid")
        .and_then(|v| v.as_str())
        .ok_or("飞象用户上下文缺少 uid")?;
    let dx_sso_id = ctx
        .get("dxSsoId")
        .and_then(|v| v.as_str())
        .ok_or("飞象用户上下文缺少 dxSsoId")?;

    let client = reqwest::blocking::Client::new();
    let endpoint = if is_test_env() {
        "https://api.xm.test.neixin.cn/login/sso_token/exchange"
    } else {
        "https://api.neixin.cn/login/sso_token/exchange"
    };
    let res = client
        .post(endpoint)
        .header("Content-Type", "application/json")
        .header("dt", "4")
        .header("dx-sso", dx_sso_id)
        .header("u", uid)
        .json(&serde_json::json!({ "clientId": CITADEL_CLIENT }))
        .send()
        .map_err(|e| format!("飞象换票 HTTP 错误: {e}"))?;

    let body: Value = res
        .json()
        .map_err(|e| format!("飞象换票响应解析失败: {e}"))?;
    let rescode = body.get("rescode").and_then(|v| v.as_i64()).unwrap_or(-1);
    if rescode != 0 {
        return Err(format!(
            "飞象换票失败: {}",
            body.get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("未知错误")
        ));
    }

    let token = body
        .get("data")
        .and_then(|v| v.get("accessToken"))
        .and_then(|v| v.as_str())
        .ok_or("飞象换票响应中未找到 accessToken")?;

    Ok(token.to_string())
}

fn load_dumbo_user_context() -> Result<Value, String> {
    if std::env::var("DUMBO_WORKSPACE_ROOT").is_err() {
        return Err("需要 DUMBO_WORKSPACE_ROOT 环境变量".to_string());
    }
    let path = dirs_home()
        .join(".dumbo")
        .join(if is_test_env() { "test" } else { "online" })
        .join("runtime-context")
        .join("user-context.json");
    let data = fs::read_to_string(&path).map_err(|e| format!("读取飞象用户上下文失败: {}", e))?;
    let ctx = serde_json::from_str::<Value>(&data)
        .map_err(|e| format!("解析飞象用户上下文失败: {}", e))?;

    if ctx.get("uid").is_none() || ctx.get("dxSsoId").is_none() {
        return Err("飞象用户上下文缺少必要字段".to_string());
    }
    Ok(ctx)
}

#[derive(Clone)]
struct CachedToken {
    token: String,
    refresh_token: Option<String>,
    expires_at: i64,
    token_type: &'static str,
}

struct SsoTokens {
    ciba: CachedToken,
    app: CachedToken,
}

fn read_cache_entry(key: &str, check_expiring: bool) -> Option<CachedToken> {
    let path = auth_cache_path();
    let data = fs::read_to_string(path).ok()?;
    let cache: Value = serde_json::from_str(&data).ok()?;
    let entry = cache.get("tokens")?.get(key)?;
    let expires_at = entry.get("expiresAt")?.as_i64()?;
    let min_expiry = chrono_now_ms()
        + if check_expiring {
            refresh_buffer_ms()
        } else {
            0
        };
    if expires_at <= min_expiry {
        return None;
    }
    Some(CachedToken {
        token: entry.get("token")?.as_str()?.to_string(),
        refresh_token: entry
            .get("refreshToken")
            .and_then(Value::as_str)
            .map(String::from),
        expires_at,
        token_type: if entry.get("tokenType").and_then(Value::as_str) == Some("ciba") {
            "ciba"
        } else {
            "app"
        },
    })
}

fn read_unified_token_cache(mis: &str) -> Option<String> {
    read_cache_entry(
        &format!("sso-unified:{CITADEL_CLIENT}:{mis}{}", cache_env_suffix()),
        true,
    )
    .map(|entry| entry.token)
}

fn read_sso_app_token_cache(mis: &str) -> Option<String> {
    read_cache_entry(
        &format!("sso-ciba:{mis}:{CITADEL_CLIENT}{}", cache_env_suffix()),
        false,
    )
    .map(|entry| entry.token)
}

fn read_ciba_token_cache(mis: &str) -> Option<CachedToken> {
    read_cache_entry(&format!("sso-ciba:{mis}:ciba{}", cache_env_suffix()), false)
}

fn write_cache_entry(key: &str, entry: &CachedToken) -> Result<(), String> {
    let path = auth_cache_path();
    let cache_dir = path.parent().ok_or("缓存路径错误")?;
    fs::create_dir_all(cache_dir).map_err(|e| format!("创建缓存目录失败: {e}"))?;

    let mut cache: Value = if path.exists() {
        fs::read_to_string(&path)
            .ok()
            .and_then(|data| serde_json::from_str(&data).ok())
            .unwrap_or_else(|| serde_json::json!({"version": "1.0", "tokens": {}, "cookies": {}}))
    } else {
        serde_json::json!({"version": "1.0", "tokens": {}, "cookies": {}})
    };

    let mut value = serde_json::json!({
        "token": entry.token,
        "expiresAt": entry.expires_at,
        "createdAt": chrono_now_ms(),
        "tokenType": entry.token_type,
    });
    if let Some(refresh_token) = &entry.refresh_token {
        value["refreshToken"] = Value::String(refresh_token.clone());
    }
    cache["tokens"][key] = value;
    cache["updatedAt"] = serde_json::json!(chrono_now_ms());

    let json = serde_json::to_string_pretty(&cache).map_err(|e| format!("序列化缓存失败: {e}"))?;
    let temp_path = path.with_extension("json.tmp");
    fs::write(&temp_path, json).map_err(|e| format!("写入缓存临时文件失败: {e}"))?;
    fs::rename(&temp_path, &path).map_err(|e| format!("原子重命名缓存失败: {e}"))
}

fn write_ciba_token_cache(mis: &str, entry: &CachedToken) -> Result<(), String> {
    write_cache_entry(&format!("sso-ciba:{mis}:ciba{}", cache_env_suffix()), entry)
}

fn write_current_token_cache(mis: &str, entry: &CachedToken) -> Result<(), String> {
    write_cache_entry(
        &format!("sso-ciba:{mis}:{CITADEL_CLIENT}{}", cache_env_suffix()),
        entry,
    )
}

fn write_unified_token_cache(mis: &str, token: &str) -> Result<(), String> {
    write_cache_entry(
        &format!("sso-unified:{CITADEL_CLIENT}:{mis}{}", cache_env_suffix()),
        &CachedToken {
            token: token.to_string(),
            refresh_token: None,
            expires_at: chrono_now_ms() + cache_ttl_ms(),
            token_type: "app",
        },
    )
}

/// 清除指定 MIS 的缓存（401 响应时调用）（对标 oa-skills TokenCache.delete / clearByUserId）
pub fn invalidate_cache(mis: &str) -> Result<(), String> {
    remove_cache_entries(mis, false)
}

/// 查询指定 MIS 的 token 剩余生命周期（秒）（对标 JS auth.js tokenTTL()）
///
/// # Arguments
/// * `mis` - MIS 号，为 None 时自动查找
///
/// # Returns
/// token 剩余秒数，找不到则返回 0
pub fn token_ttl(mis: Option<&str>) -> i64 {
    let user_id = mis.map(String::from).or_else(load_default_user_id);
    let Some(uid) = user_id else {
        return 0;
    };

    if let Some(entry) = read_cache_entry(
        &format!("sso-ciba:{uid}:{CITADEL_CLIENT}{}", cache_env_suffix()),
        false,
    ) {
        return ((entry.expires_at - chrono_now_ms()) / 1000).max(0);
    }
    if let Some(entry) = read_cache_entry(
        &format!("sso-unified:{CITADEL_CLIENT}:{uid}{}", cache_env_suffix()),
        false,
    ) {
        return ((entry.expires_at - chrono_now_ms()) / 1000).max(0);
    }

    0
}

/// 登录认证（清除缓存并重新认证）
///
/// # Arguments
/// * `mis` - MIS 号，为 None 时自动查找
pub fn login(mis: Option<&str>) -> Result<String, String> {
    let user_id = mis
        .map(String::from)
        .or_else(load_default_user_id)
        .ok_or("无法确定 MIS 号，请执行：km login --mis <MIS>")?;
    clear_user_auth_cache(&user_id)?;
    get_token(Some(&user_id))
}

fn clear_user_auth_cache(mis: &str) -> Result<(), String> {
    remove_cache_entries(mis, true)
}

fn remove_cache_entries(mis: &str, include_ciba: bool) -> Result<(), String> {
    let path = auth_cache_path();
    let Ok(data) = fs::read_to_string(&path) else {
        return Ok(());
    };
    let mut cache: Value =
        serde_json::from_str(&data).map_err(|e| format!("解析认证缓存失败: {e}"))?;
    let Some(Value::Object(tokens)) = cache.get_mut("tokens") else {
        return Ok(());
    };
    let unified_key = format!("sso-unified:{CITADEL_CLIENT}:{mis}{}", cache_env_suffix());
    let app_key = format!("sso-ciba:{mis}:{CITADEL_CLIENT}{}", cache_env_suffix());
    let product_unified_key = format!("sso-unified:{CITADEL_CLIENT}:{mis}");
    let test_unified_key = format!("{product_unified_key}:test");
    let ciba_prefix = format!("sso-ciba:{mis}:");
    tokens.retain(|key, _| {
        let all_unified = key == &product_unified_key || key == &test_unified_key;
        key != &unified_key
            && key != &app_key
            && !(include_ciba && (key.starts_with(&ciba_prefix) || all_unified))
    });
    cache["updatedAt"] = serde_json::json!(chrono_now_ms());
    let json =
        serde_json::to_string_pretty(&cache).map_err(|e| format!("序列化认证缓存失败: {e}"))?;
    let temp_path = path.with_extension("json.tmp");
    fs::write(&temp_path, json).map_err(|e| format!("写入认证缓存失败: {e}"))?;
    fs::rename(temp_path, path).map_err(|e| format!("更新认证缓存失败: {e}"))
}

/// 解析或自动查找 MIS 号（对标 JS auth.js resolveUserId()）
///
/// # Arguments
/// * `override_mis` - 显式指定的 MIS 号，为 None 时自动查找
///
/// # Returns
/// 解析得到的 MIS 号
pub fn resolve_user_id(override_mis: Option<&str>) -> Option<String> {
    override_mis.map(String::from).or_else(load_default_user_id)
}

fn is_claw_environment() -> bool {
    if std::env::var("SANDBOX_ID").is_ok() {
        return true;
    }
    let path = dirs_home()
        .join(".openclaw")
        .join("config")
        .join("sandbox.json");
    path.exists()
}

fn dirs_home() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp"))
}

fn chrono_now_ms() -> i64 {
    use std::time::SystemTime;
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

fn duration_from_env(name: &str, default_ms: i64) -> i64 {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse::<i64>().ok())
        .filter(|value| *value > 0)
        .map(|seconds| seconds * 1000)
        .unwrap_or(default_ms)
}

fn refresh_buffer_ms() -> i64 {
    duration_from_env("AUTH_REFRESH_BUFFER", DEFAULT_REFRESH_BUF_MS)
}

fn cache_ttl_ms() -> i64 {
    duration_from_env("AUTH_CACHE_TTL", DEFAULT_CACHE_TTL_MS)
}

fn is_test_env() -> bool {
    std::env::var("SSO_ACCESS_ENV").is_ok_and(|value| value.eq_ignore_ascii_case("test"))
}

fn sso_host() -> &'static str {
    if is_test_env() {
        return SSO_TEST_HOST;
    }
    SSO_PRODUCT_HOST
}

fn ciba_credentials() -> (&'static str, &'static str) {
    if is_test_env() {
        return (CIBA_TEST_CLIENT_ID, CIBA_TEST_CLIENT_SECRET);
    }
    (CIBA_CLIENT_ID, CIBA_CLIENT_SECRET)
}

fn cache_env_suffix() -> &'static str {
    if is_test_env() { ":test" } else { "" }
}

/// Supabase CIBA 流程：auth → poll → exchange
fn get_supabase_ciba_token(user_id: &str) -> Result<String, String> {
    let client = reqwest::blocking::Client::new();

    let identifier =
        get_sandbox_identifier().ok_or("未找到 SANDBOX_ID 或 ~/.openclaw/config/sandbox.json")?;

    // 步骤 1：发起 CIBA auth
    eprintln!("[auth] 发起 Supabase CIBA 认证...");
    let auth_body = serde_json::json!({
        "identifier": identifier,
        "misId": user_id,
    });
    let auth_res = client
        .post(format!("{SUPABASE_BASE}/api/sandbox/sso/ciba-auth"))
        .json(&auth_body)
        .send()
        .map_err(|e| format!("CIBA auth HTTP 错误: {e}"))?;

    let auth_data: Value = auth_res
        .json()
        .map_err(|e| format!("CIBA auth 响应解析失败: {e}"))?;
    let code = auth_data.get("code").and_then(|v| v.as_i64()).unwrap_or(-1);
    if code != 0 {
        return Err(format!(
            "CIBA auth 失败: {}",
            auth_data
                .get("data")
                .and_then(|v| v.get("errorDescription"))
                .and_then(|v| v.as_str())
                .unwrap_or("unknown")
        ));
    }

    let auth_req_id = auth_data
        .get("data")
        .and_then(|v| v.get("authReqId").or_else(|| v.get("existingAuthReqId")))
        .and_then(|v| v.as_str())
        .ok_or("未获取到 authReqId")?;

    // 步骤 2：轮询获取 accessToken（最多 36 次，每次 5s，共 3 分钟）
    eprintln!("[auth] 请在大象 App 确认授权...");
    let mut access_token = None;
    for i in 0..36 {
        thread::sleep(Duration::from_secs(5));
        eprint!("\r[auth] 等待确认... {}s", (i + 1) * 5);

        let poll_body = serde_json::json!({ "authReqId": auth_req_id });
        let poll_res = client
            .post(format!("{SUPABASE_BASE}/api/sandbox/sso/ciba-token"))
            .json(&poll_body)
            .send()
            .map_err(|e| format!("轮询 HTTP 错误: {e}"))?;

        let poll_data: Value = poll_res
            .json()
            .map_err(|e| format!("轮询响应解析失败: {e}"))?;
        if poll_data.get("code").and_then(|v| v.as_i64()).unwrap_or(-1) == 0 {
            if let Some(token) = poll_data
                .get("data")
                .and_then(|v| v.get("accessToken"))
                .and_then(|v| v.as_str())
            {
                access_token = Some(token.to_string());
                break;
            }
        } else {
            // 轮询仍在进行，继续下一次
            eprint!(".");
        }
    }
    eprintln!();

    let access_token = access_token.ok_or("CIBA 认证超时：未在规定时间内确认")?;

    // 步骤 3：换票获取 citadel token
    let exch_body = serde_json::json!({
        "accessToken": access_token,
        "clientIds": [CITADEL_CLIENT],
        "identifier": identifier,
    });
    let exch_res = client
        .post(format!(
            "{SUPABASE_BASE}/api/sandbox/sso/exchange-token-by-client-ids"
        ))
        .json(&exch_body)
        .send()
        .map_err(|e| format!("换票 HTTP 错误: {e}"))?;

    let exch_data: Value = exch_res
        .json()
        .map_err(|e| format!("换票响应解析失败: {e}"))?;
    if exch_data.get("code").and_then(|v| v.as_i64()).unwrap_or(-1) != 0 {
        return Err(format!(
            "换票失败: {}",
            exch_data
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown")
        ));
    }

    let token = exch_data
        .get("data")
        .and_then(|v| {
            if v.is_string() {
                v.as_str()
            } else {
                v.get(CITADEL_CLIENT).and_then(|v| v.as_str())
            }
        })
        .ok_or("换票响应中未找到 citadel token")?;

    Ok(token.to_string())
}

/// SSO CIBA 流程：bc-authorize → poll /token → token-exchange → 获取 citadel token
/// 对标 JS auth.js getSsoCibaToken()
fn get_sso_ciba_token(user_id: &str) -> Result<SsoTokens, String> {
    let client = reqwest::blocking::Client::new();
    let token_url = format!("{}{}", sso_host(), SSO_TOKEN_PATH);

    // 步骤 1：发起 CIBA 认证（bc-authorize）
    eprintln!("[auth] 发起 SSO CIBA 认证...");
    let ciba_url = format!("{}{}", sso_host(), SSO_CIBA_PATH);
    let (client_id, _) = ciba_credentials();

    let init_body = [
        ("client_id", client_id.to_string()),
        (
            "client_assertion_type",
            "urn:ietf:params:oauth:client-assertion-type:jwt-bearer".to_string(),
        ),
        ("client_assertion", make_client_assertion(&ciba_url)?),
        ("login_hint", user_id.to_string()),
        ("scope", "profile offline_access".to_string()),
        ("notify_by", "custom_bot".to_string()),
        (
            "custom_bot_ext",
            serde_json::json!({
                "bot_client_id": CIBA_BOT_CLIENT_ID,
                "bot_client_name": "citadel",
                "bot_client_type": "Skill/CLI",
                "description": CIBA_BOT_DESCRIPTION,
            })
            .to_string(),
        ),
    ];

    let init_res = client
        .post(&ciba_url)
        .form(&init_body)
        .send()
        .map_err(|e| format!("CIBA 发起 HTTP 错误: {e}"))?;

    let init_data: Value = init_res
        .json()
        .map_err(|e| format!("CIBA 发起响应解析失败: {e}"))?;

    let (auth_req_id, expiry) = if let Some(error) = init_data.get("error").and_then(|v| v.as_str())
    {
        if error == "authorization_pending" {
            let id = init_data
                .get("extra_info")
                .and_then(|v| v.get("existing_auth_req_id"))
                .and_then(|v| v.as_str())
                .ok_or("未获取到 existing_auth_req_id")?;
            eprintln!("[auth] 检测到已有活跃认证请求，继续等待确认");
            (id.to_string(), 120i64)
        } else {
            return Err(format!(
                "CIBA 发起失败: {} - {}",
                error,
                init_data
                    .get("error_description")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
            ));
        }
    } else {
        let id = init_data
            .get("auth_req_id")
            .and_then(|v| v.as_str())
            .ok_or("未获取到 auth_req_id")?;
        let exp = init_data
            .get("expires_in")
            .and_then(|v| v.as_i64())
            .unwrap_or(120);
        (id.to_string(), exp)
    };

    // 步骤 2：轮询获取 CIBA token
    eprintln!("[auth] 请在大象 App 确认授权（超时 {}s）", expiry);
    let poll_interval_ms = {
        let interval = init_data
            .get("interval")
            .and_then(|v| v.as_i64())
            .unwrap_or(5);
        (interval.max(3) * 1000) as u64
    };
    let timeout_ms = (expiry.min(120) * 1000) as u64;
    let start = std::time::Instant::now();
    let mut ciba_entry = None;

    loop {
        if start.elapsed().as_millis() as u64 >= timeout_ms {
            break;
        }
        thread::sleep(Duration::from_millis(poll_interval_ms));
        let elapsed = start.elapsed().as_secs();
        eprint!("\r[auth] 等待确认... {}s", elapsed);

        let poll_body = [
            ("client_id", client_id.to_string()),
            (
                "client_assertion_type",
                "urn:ietf:params:oauth:client-assertion-type:jwt-bearer".to_string(),
            ),
            ("client_assertion", make_client_assertion(&token_url)?),
            (
                "grant_type",
                "urn:openid:params:grant-type:ciba".to_string(),
            ),
            ("auth_req_id", auth_req_id.clone()),
        ];

        let poll_res = client
            .post(&token_url)
            .form(&poll_body)
            .send()
            .map_err(|e| format!("轮询 HTTP 错误: {e}"))?;

        let poll_data: Value = poll_res
            .json()
            .map_err(|e| format!("轮询响应解析失败: {e}"))?;

        if let Some(token) = poll_data.get("access_token").and_then(|v| v.as_str()) {
            let expires_in = poll_data
                .get("expires_in")
                .and_then(Value::as_i64)
                .unwrap_or(3600);
            ciba_entry = Some(CachedToken {
                token: token.to_string(),
                refresh_token: poll_data
                    .get("refresh_token")
                    .and_then(Value::as_str)
                    .map(String::from),
                expires_at: chrono_now_ms() + expires_in * 1000,
                token_type: "ciba",
            });
            break;
        }

        // 检查错误
        if let Some(error) = poll_data.get("error").and_then(Value::as_str)
            && error != "authorization_pending"
            && error != "slow_down"
        {
            eprintln!();
            return Err(format!(
                "CIBA 认证失败: {} - {}",
                error,
                poll_data
                    .get("error_description")
                    .and_then(Value::as_str)
                    .unwrap_or("")
            ));
        }
    }
    eprintln!();

    let ciba = ciba_entry.ok_or("CIBA 认证超时：未在规定时间内确认")?;
    let app = exchange_sso_ciba_token(&ciba.token)?;
    Ok(SsoTokens { ciba, app })
}

fn exchange_sso_ciba_token(ciba_token: &str) -> Result<CachedToken, String> {
    let client = reqwest::blocking::Client::new();
    let token_url = format!("{}{}", sso_host(), SSO_TOKEN_PATH);
    let (client_id, _) = ciba_credentials();
    let exch_body = [
        ("client_id", client_id.to_string()),
        (
            "client_assertion_type",
            "urn:ietf:params:oauth:client-assertion-type:jwt-bearer".to_string(),
        ),
        ("client_assertion", make_client_assertion(&token_url)?),
        (
            "grant_type",
            "urn:ietf:params:oauth:grant-type:token-exchange".to_string(),
        ),
        ("subject_token", ciba_token.to_string()),
        (
            "subject_token_type",
            "urn:ietf:params:oauth:token-type:access_token".to_string(),
        ),
        ("audience", CITADEL_CLIENT.to_string()),
    ];

    let exch_res = client
        .post(&token_url)
        .form(&exch_body)
        .send()
        .map_err(|e| format!("token-exchange HTTP 错误: {e}"))?;

    let exch_data: Value = exch_res
        .json()
        .map_err(|e| format!("token-exchange 响应解析失败: {e}"))?;

    if let Some(error) = exch_data.get("error").and_then(|v| v.as_str()) {
        return Err(format!(
            "token-exchange 失败: {} - {}",
            error,
            exch_data
                .get("error_description")
                .and_then(|v| v.as_str())
                .unwrap_or("")
        ));
    }

    let token = exch_data
        .get("access_token")
        .and_then(|v| v.as_str())
        .ok_or("token-exchange 响应中未找到 access_token")?;
    let expires_in = exch_data
        .get("expires_in")
        .and_then(Value::as_i64)
        .unwrap_or(3600);
    Ok(CachedToken {
        token: token.to_string(),
        refresh_token: exch_data
            .get("refresh_token")
            .and_then(Value::as_str)
            .map(String::from),
        expires_at: chrono_now_ms() + expires_in * 1000,
        token_type: "app",
    })
}

fn refresh_sso_ciba_token(refresh_token: &str) -> Result<CachedToken, String> {
    let token_url = format!("{}{}", sso_host(), SSO_TOKEN_PATH);
    let (client_id, _) = ciba_credentials();
    let body = [
        ("client_id", client_id.to_string()),
        (
            "client_assertion_type",
            "urn:ietf:params:oauth:client-assertion-type:jwt-bearer".to_string(),
        ),
        ("client_assertion", make_client_assertion(&token_url)?),
        ("grant_type", "refresh_token".to_string()),
        ("refresh_token", refresh_token.to_string()),
    ];
    let response = reqwest::blocking::Client::new()
        .post(&token_url)
        .form(&body)
        .send()
        .map_err(|e| format!("刷新 CIBA token HTTP 错误: {e}"))?;
    let data: Value = response
        .json()
        .map_err(|e| format!("刷新 CIBA token 响应解析失败: {e}"))?;
    let token = data
        .get("access_token")
        .and_then(Value::as_str)
        .ok_or("刷新 CIBA token 失败")?;
    let expires_in = data
        .get("expires_in")
        .and_then(Value::as_i64)
        .unwrap_or(3600);
    Ok(CachedToken {
        token: token.to_string(),
        refresh_token: Some(
            data.get("refresh_token")
                .and_then(Value::as_str)
                .unwrap_or(refresh_token)
                .to_string(),
        ),
        expires_at: chrono_now_ms() + expires_in * 1000,
        token_type: "ciba",
    })
}

/// 构造 JWT client_assertion（HS256，对标 JS auth.js makeClientAssertion()）
fn make_client_assertion(endpoint: &str) -> Result<String, String> {
    use base64::{Engine, engine::general_purpose::URL_SAFE_NO_PAD};
    use hmac::{Hmac, Mac};
    use sha2::Sha256;
    use std::time::{SystemTime, UNIX_EPOCH};

    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| format!("获取时间戳失败: {}", e))?
        .as_secs() as i64;
    let iat = now - 30; // clock skew
    let exp = now + 86400;

    let (client_id, client_secret) = ciba_credentials();
    let header = serde_json::json!({ "alg": "HS256", "typ": "JWT" });
    let payload = serde_json::json!({
        "sub": client_id,
        "iss": client_id,
        "aud": [endpoint],
        "exp": exp,
        "iat": iat,
        "jti": uuid::Uuid::new_v4().to_string(),
    });

    let header_b64 = URL_SAFE_NO_PAD.encode(header.to_string());
    let payload_b64 = URL_SAFE_NO_PAD.encode(payload.to_string());
    let msg = format!("{}.{}", header_b64, payload_b64);

    let mut mac = Hmac::<Sha256>::new_from_slice(client_secret.as_bytes())
        .map_err(|e| format!("HMAC 初始化失败: {}", e))?;
    mac.update(msg.as_bytes());
    let sig = URL_SAFE_NO_PAD.encode(mac.finalize().into_bytes());

    Ok(format!("{}.{}.{}", header_b64, payload_b64, sig))
}

fn get_sandbox_identifier() -> Option<String> {
    if let Ok(identifier) = std::env::var("IDENTIFIER") {
        return Some(identifier);
    }
    if let Ok(sandbox_id) = std::env::var("SANDBOX_ID") {
        return Some(sandbox_id);
    }
    let path = dirs_home()
        .join(".openclaw")
        .join("config")
        .join("sandbox.json");
    if let Ok(data) = fs::read_to_string(path)
        && let Ok(json) = serde_json::from_str::<Value>(&data)
    {
        return json
            .get("identifier")
            .and_then(Value::as_str)
            .map(String::from);
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_placeholder() {
        assert!(is_placeholder(""));
        assert!(is_placeholder("{{defaultUserId}}"));
        assert!(is_placeholder("${defaultUserId}"));
        assert!(!is_placeholder("12345"));
        assert!(!is_placeholder("sanmao"));
        // 边界情况
        assert!(!is_placeholder("{{}}")); // 太短
        assert!(!is_placeholder("${}")); // 太短
        assert!(is_placeholder("{{a}}")); // 最小有效长度
        assert!(is_placeholder("${a}")); // 最小有效长度
    }

    #[test]
    fn test_is_placeholder_empty_string() {
        // Empty string is a placeholder
        assert!(is_placeholder(""));
    }

    #[test]
    fn test_is_placeholder_template_syntax() {
        // Template syntax recognized as placeholder
        assert!(is_placeholder("{{userId}}"));
        assert!(is_placeholder("${userId}"));
    }

    #[test]
    fn test_is_placeholder_normal_values() {
        // Normal values not placeholders
        assert!(!is_placeholder("normal_user_123"));
        assert!(!is_placeholder("1234567890"));
    }

    #[test]
    fn test_parse_mis_from_shared_cache_keys() {
        assert_eq!(
            parse_mis_from_cache_key("sso-ciba:wangzexi02:ciba"),
            Some("wangzexi02".to_string())
        );
        assert_eq!(
            parse_mis_from_cache_key("sso-ciba:wangzexi02:com.sankuai.it.ead.citadel"),
            Some("wangzexi02".to_string())
        );
        assert_eq!(
            parse_mis_from_cache_key("sso-unified:com.sankuai.it.ead.citadel:wangzexi02"),
            Some("wangzexi02".to_string())
        );
    }

    // —— 以下为真实环境集成测试，默认 ignored，手动触发：
    //   cargo test --lib -- --ignored moa_real
    // 需要本地 MOA 桌面客户端在运行。
    #[test]
    #[ignore]
    fn moa_real_probe() {
        let ok = probe_moa_seamless_support();
        eprintln!("probe_moa_seamless_support() = {ok}");
    }

    #[test]
    #[ignore]
    fn moa_real_full_token() {
        if !probe_moa_seamless_support() {
            eprintln!("官方 MOA probe 判定不可用，跳过 full token 测试");
            return;
        }
        match get_moa_token() {
            Ok(tok) => {
                eprintln!("MOA token 长度: {}", tok.len());
                assert!(tok.len() > 20, "token 过短");
            }
            Err(e) => panic!("get_moa_token 失败: {e}"),
        }
    }
}
