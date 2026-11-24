import { spawnSync } from "node:child_process";
import { sanitizePublicErrorMessage } from "./upstream-error-message.mjs";
import { createCitadelSourceFailure, CitadelSourceFailureError } from "./citadel-source-failure.mjs";
import { createMCodeSourceFailure, MCodeSourceFailureError } from "./mcode-source-failure.mjs";

export const SOURCE_USER_SSO_SCHEMA = "catx-source-user-sso/v1";
export const CITADEL_AUDIENCE = "com.sankuai.it.ead.citadel";
export const CODE_AUDIENCE = "f32a546874";
const AUDIENCES = new Set([CITADEL_AUDIENCE, CODE_AUDIENCE]);
const MAX_AUTH_BYTES = 64 * 1024;
const MESSAGES = Object.freeze({
  provider_unavailable: "当前 CatX 环境不支持本人凭据网关换票，请联系平台管理员检查运行环境。",
  auth_required: "当前登录授权需要重新确认，请重新登录平台后重新分析。",
  auth_expired: "本次来源读取凭据已过期或被撤销，请重新登录平台后重新分析。",
  auth_denied: "当前用户或应用没有代理访问权限，请按身份服务提示处理后重新分析。",
  identity_mismatch: "来源读取身份与任务提交人不一致，已停止读取，请联系平台管理员检查凭据绑定。",
  auth_failed: "来源读取身份认证失败，请重新登录平台后重新分析。",
  network_failed: "来源身份核验网络请求失败，请稍后重新分析。",
  timeout: "来源身份核验超时，请稍后重新分析。",
});

export const expectedSourceAudiences = (sourceType, referencedKm = false) => sourceType === "km"
  ? [CITADEL_AUDIENCE]
  : sourceType === "git" ? [...(referencedKm ? [CITADEL_AUDIENCE] : []), CODE_AUDIENCE] : [];

export const validSourceUserSsoContract = (auth, sourceType, referencedKm) => Boolean(
  auth && typeof auth === "object" && !Array.isArray(auth)
  && Object.keys(auth).length === 2 && Object.keys(auth).every((key) => ["schema_version", "audiences"].includes(key))
  && auth.schema_version === SOURCE_USER_SSO_SCHEMA
  && JSON.stringify(auth.audiences) === JSON.stringify(expectedSourceAudiences(sourceType, referencedKm))
  && expectedSourceAudiences(sourceType, referencedKm).length,
);

class SourceUserSsoError extends Error {
  constructor(kind, message = null) {
    super(sanitizePublicErrorMessage(message) || MESSAGES[kind]);
    this.name = "SourceUserSsoError";
    this.kind = kind;
  }
}
const fail = (kind, message) => { throw new SourceUserSsoError(kind, message); };
const remaining = (deadline, maximum = 25_000) => {
  const value = Math.min(maximum, deadline - Date.now());
  if (!(value > 0)) fail("timeout");
  return value;
};
const parse = (text) => {
  if (typeof text !== "string" || Buffer.byteLength(text) > MAX_AUTH_BYTES) return null;
  try { return JSON.parse(text); } catch { return null; }
};
const serviceFailure = (body) => {
  const code = body?.code || (typeof body?.error === "object" ? body.error?.code : body?.error);
  let message = body?.message || body?.error_description || body?.error?.message;
  // Even malformed/error responses can echo an opaque token without a field label.
  if (typeof message === "string") {
    for (const value of [body?.access_token, body?.refresh_token, body?.token]) {
      if (typeof value === "string" && value.length >= 8) message = message.replaceAll(value, "[已隐藏]");
    }
  }
  if (code === "ric_feedback_required") fail("auth_required", message);
  if (["sub_access_denied", "act_access_denied", "sub_act_access_denied"].includes(code)) fail("auth_denied", message);
  if (["invalid_grant", "expired_token", "token_expired"].includes(code)) fail("auth_expired", message);
  if (["unauthorized_client", "invalid_client"].includes(code)) fail("provider_unavailable", message);
  fail("auth_failed", message);
};
const readBoundedJson = async (response) => {
  if (!response.body?.getReader) return null;
  const reader = response.body.getReader();
  const chunks = []; let size = 0;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_AUTH_BYTES) { await reader.cancel(); return null; }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return parse(Buffer.concat(chunks).toString("utf8"));
};

// A source Session must be bound to the actor's api_sso Vault by the platform.
// Requiring the official gateway route prevents silent local-MOA/CIBA fallback.
export const authenticateSourceUser = async ({ actorMis, audience, deadline, env = process.env,
  runCli = spawnSync, fetchImpl = fetch }) => {
  if (!/^[a-z][a-z0-9._-]{0,63}$/u.test(String(actorMis)) || !AUDIENCES.has(audience)) fail("auth_failed");
  const safeEnv = { ...env, SSO_OIDC_FALLBACK: "false" };
  delete safeEnv.SSO_CIBA_TOKEN;
  const invoke = (name, args = []) => runCli("npx", ["--yes", name, ...args], {
    encoding: "utf8", timeout: remaining(deadline), maxBuffer: MAX_AUTH_BYTES,
    env: safeEnv, stdio: ["ignore", "pipe", "pipe"],
  });
  const probe = invoke("mtsso-moa-feature-probe");
  const feature = parse(probe.stdout);
  if (probe.error?.code === "ETIMEDOUT") fail("timeout");
  if (probe.error || probe.signal || probe.status !== 0 || feature?.support_type !== "gateway_intercept_feature" || feature.ok === false) fail("provider_unavailable");
  const exchange = invoke("mtsso-moa-local-exchange", ["--audience", audience]);
  const body = parse(exchange.stdout);
  if (exchange.error?.code === "ETIMEDOUT") fail("timeout");
  if (exchange.error || exchange.signal) fail("provider_unavailable");
  if (exchange.status !== 0) serviceFailure(body);
  if (body?.error || body?.code) serviceFailure(body);
  const token = typeof body?.access_token === "string" ? body.access_token : String(exchange.stdout || "").trim();
  if (!/^AT_FOR_GW_BASE64_[A-Za-z0-9+/]+={0,2}$/u.test(token) || token.length > 16 * 1024) fail("provider_unavailable");
  // Never decode, rewrite or log the gateway placeholder.
  let response, identity;
  try {
    response = await fetchImpl(`https://ssosv.sankuai.com/websso/whoami?client_id=${encodeURIComponent(audience)}`, {
      headers: { Authorization: `Bearer ${token}` }, redirect: "error",
      signal: AbortSignal.timeout(remaining(deadline, 20_000)),
    });
    identity = await readBoundedJson(response);
  } catch (error) {
    if (error instanceof SourceUserSsoError) throw error;
    fail(error?.name === "TimeoutError" || error?.name === "AbortError" ? "timeout" : "network_failed");
  }
  if (response.status === 401) fail("auth_expired");
  if (response.status === 403) serviceFailure(identity);
  if (response.status !== 200 || String(identity?.code) !== "200") serviceFailure(identity);
  if (identity?.data?.subject !== actorMis) fail("identity_mismatch");
  remaining(deadline);
  return token;
};

export const sourceUserSsoFailure = (error, target) => {
  const kind = error instanceof SourceUserSsoError ? error.kind : "auth_failed";
  const message = error instanceof SourceUserSsoError ? error.message : MESSAGES.auth_failed;
  if (target === "citadel") {
    const code = { provider_unavailable: "citadel_auth_provider_unavailable", identity_mismatch: "citadel_identity_mismatch", auth_expired: "citadel_auth_expired", auth_required: "citadel_auth_required", auth_denied: "citadel_auth_denied", network_failed: "citadel_network_failed", timeout: "citadel_source_timeout" }[kind] || "citadel_auth_failed";
    return new CitadelSourceFailureError(createCitadelSourceFailure({code, message, knownSignals: ["auth_failed"]}));
  }
  const code = { provider_unavailable: "mcode_auth_provider_unavailable", identity_mismatch: "mcode_identity_mismatch", auth_expired: "mcode_auth_expired", auth_required: "mcode_auth_required", network_failed: "mcode_network_failed", timeout: "mcode_auth_timeout" }[kind] || "mcode_auth_failed";
  return new MCodeSourceFailureError(createMCodeSourceFailure({code, message, operation: "authenticate", knownSignals: [kind === "auth_denied" ? "auth_proxy_access_denied" : "auth_failed"]}));
};
