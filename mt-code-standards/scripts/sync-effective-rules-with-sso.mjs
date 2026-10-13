#!/usr/bin/env node

import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { randomUUID } from "node:crypto";
import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  RuleBundleError,
  EXECUTION_AGENTS,
  prepareSyncRequest,
  syncEffectiveRuleBundle,
} from "./resolve-effective-rules.mjs";

const execFileAsync = promisify(execFile);
const AUDIENCE = "923a237244";
const OFFICIAL_TIMEOUT_MS = 30_000;
const PORTABLE_TIMEOUT_MS = 150_000;
const ACCESS_DENIED_CODES = new Set(["sub_access_denied", "act_access_denied", "sub_act_access_denied"]);
const CIBA_PENDING_CODES = new Set(["MOA_NOT_LOGGED_IN", "MOA_AUTH_REQUEST_PENDING"]);
const CIBA_REJECTED_CODES = new Set(["MOA_USER_REJECTED", "MOA_REJECT_COOLDOWN"]);
const NETWORK_FAILURE_CODES = new Set([
  "ECONNABORTED", "ECONNREFUSED", "ECONNRESET", "EHOSTUNREACH", "ENETUNREACH", "ENOTFOUND", "EPIPE",
]);
const NETWORK_FAILURE_MARKERS = [
  /\b(?:ECONNABORTED|ECONNREFUSED|ECONNRESET|EHOSTUNREACH|ENETUNREACH|ENOTFOUND|EPIPE)\b/iu,
  /\b(?:network|fetch)\s+(?:error|failed|failure|unavailable)\b/iu,
  /\b(?:getaddrinfo|socket hang up|timed?\s*out|timeout)\b/iu,
  /(?:网络错误|网络不可用|网络请求失败|连接超时)/u,
];
const AGENT_SSO_CONFIGURATION_MARKERS = [
  "缺少 client_id", "missing client_id", "AGENT_SSO_CLIENT_ID", "client_id is required",
];
const LOCAL_CAPABILITY_MISSING_MARKERS = [
  "MOA_UNSUPPORTED", "MOA_NOT_SUPPORTED", "support_type: none", '"support_type":"none"',
  "所有换票路径均不可用", "未找到可用的换票能力", "mtsso-moa-local-exchange: not found",
];
export const EXTERNAL_AUTH_AGENTS = new Set([
  "github-copilot", "cursor", "windsurf", "claude-code", "codex", "gemini-cli", "amazon-q", "kiro",
  "jetbrains-junie", "devin", "replit-agent", "cline", "roo-code", "aider", "trae", "qoder",
  "tongyi-lingma", "tencent-codebuddy", "baidu-comate", "codegeex",
]);
const INTERNAL_EXECUTION_AGENTS = new Set(["catx", "catpaw", "catdesk", "agent_1024", "sandbox"]);
const INTERNAL_AUTH_ENV_PREFIXES = [
  "CATX_", "CATPAW_", "CATDESK_", "CATCLAW_", "AGENT_1024", "AGENT1024", "SANDBOX",
];

const text = (value) => String(value ?? "").trim();
const parseArgs = (argv) => {
  const result = {};
  const valued = new Set([
    "--repository", "--repo-root", "--output-dir", "--gateway-url", "--execution-agent", "--auth-agent", "--skill-version",
    "--pull-id", "--mis", "--domain", "--stage",
  ]);
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (key === "--bootstrap") {
      result.bootstrap = true;
      continue;
    }
    if (!valued.has(key) || index + 1 >= argv.length) {
      throw new RuleBundleError("RULE_BUNDLE_ARGUMENT_INVALID", `未知或缺值参数：${key}`);
    }
    const value = argv[index + 1];
    if (key === "--repository") result.repositoryLocator = value;
    else if (key === "--repo-root") result.repoRoot = value;
    else if (key === "--output-dir") result.outputDir = value;
    else if (key === "--gateway-url") result.gatewayUrl = value;
    else if (key === "--execution-agent") result.agent = value;
    else if (key === "--auth-agent") result.authAgent = value;
    else if (key === "--skill-version") result.skillVersion = value;
    else if (key === "--pull-id") result.pullId = value;
    else if (key === "--mis") result.mis = value;
    else if (key === "--domain") result.domain = value;
    else if (key === "--stage") result.stage = value;
    index += 1;
  }
  return result;
};

export const detectExecutionAgent = (environment = process.env) => {
  const has = (prefix) => Object.keys(environment).some((key) => key.startsWith(prefix));
  if (has("CATX_")) return { agent: "catx", source: "runner_heuristic_v1" };
  if (has("CATPAW_")) return { agent: "catpaw", source: "runner_heuristic_v1" };
  if (has("CATDESK_")) return { agent: "catdesk", source: "runner_heuristic_v1" };
  if (has("CLAUDE_CODE") || has("CLAUDECODE")) return { agent: "claude", source: "runner_heuristic_v1" };
  if (has("CODEX_")) return { agent: "codex", source: "runner_heuristic_v1" };
  if (has("AGENT_1024") || has("AGENT1024")) return { agent: "agent_1024", source: "runner_heuristic_v1" };
  if (has("SANDBOX")) return { agent: "sandbox", source: "runner_heuristic_v1" };
  return { agent: "unknown", source: "legacy_unknown_v1" };
};

export const detectAuthAgent = (environment = process.env) => {
  const has = (prefix) => Object.keys(environment).some((key) => key.startsWith(prefix));
  if (has("CLAUDE_CODE") || has("CLAUDECODE")) {
    return { authAgent: "claude-code", source: "environment_heuristic_v1" };
  }
  if (has("CODEX_")) return { authAgent: "codex", source: "environment_heuristic_v1" };
  return { authAgent: "unknown", source: "unknown_v1" };
};

export const selectAuthenticationRoute = ({
  environment = process.env, authAgent, executionAgent,
} = {}) => {
  const explicitAuthAgent = text(authAgent);
  if (text(environment.RULE_OBSERVABILITY_USER_TOKEN)) {
    return { route: "injected", reason: "injected_user_token_present", authAgent: explicitAuthAgent || "unknown" };
  }
  if (explicitAuthAgent && !EXTERNAL_AUTH_AGENTS.has(explicitAuthAgent)) {
    throw new RuleBundleError(
      "RULE_BUNDLE_AUTH_AGENT_INVALID",
      "认证 Agent 必须是受支持的外部编码 Agent 标识。",
    );
  }
  if (explicitAuthAgent) {
    return { route: "portable", reason: "explicit_external_auth_agent", authAgent: explicitAuthAgent };
  }
  if (INTERNAL_EXECUTION_AGENTS.has(text(executionAgent))) {
    return { route: "official", reason: "explicit_internal_execution_agent", authAgent: "unknown" };
  }
  if (Object.keys(environment).some((key) => INTERNAL_AUTH_ENV_PREFIXES.some((prefix) => key.startsWith(prefix)))) {
    return { route: "official", reason: "detected_internal_host", authAgent: "unknown" };
  }
  const detectedExecution = detectExecutionAgent(environment);
  if (INTERNAL_EXECUTION_AGENTS.has(detectedExecution.agent)) {
    return { route: "official", reason: "detected_internal_execution_agent", authAgent: "unknown" };
  }
  const detectedAuth = detectAuthAgent(environment);
  if (EXTERNAL_AUTH_AGENTS.has(detectedAuth.authAgent)) {
    return { route: "portable", reason: "detected_external_auth_agent", authAgent: detectedAuth.authAgent };
  }
  return { route: "official", reason: "official_exchange_default", authAgent: "unknown" };
};

const parseJson = (raw) => {
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  } catch { return null; }
};

const responseCode = (payload) => text(
  payload?.error?.code
  || (typeof payload?.error === "string" ? payload.error : "")
  || payload?.code,
);

const safeOfficialGuidance = (payload) => {
  const candidate = text(
    payload?.error_description || payload?.error?.description || payload?.error?.message || payload?.message,
  );
  return candidate
    .replace(/[\p{Cc}]+/gu, " ")
    .replace(/\b(access_token|client_secret|subject_token|authorization)\b\s*[:=]\s*\S+/giu, "$1=[redacted]")
    .replace(/\bBearer\s+\S+/giu, "Bearer [redacted]")
    .replace(/\bAT_FOR_GW_BASE64_\S+/gu, "[redacted-token]")
    .replace(/\beyJ[A-Za-z0-9_-]+[.][A-Za-z0-9_-]+(?:[.][A-Za-z0-9_-]+)?\b/gu, "[redacted-token]")
    .slice(0, 500);
};

const officialFailure = ({ payload, raw, exitCode, cause }) => {
  const code = responseCode(payload) || [
    ...ACCESS_DENIED_CODES, "ric_feedback_required", ...CIBA_PENDING_CODES, ...CIBA_REJECTED_CODES,
  ].find((item) => raw.includes(item));
  const guidance = safeOfficialGuidance(payload);
  if (ACCESS_DENIED_CODES.has(code)) {
    const suffix = guidance ? ` 官方指引：${guidance}` : " 请按官方 SSO/UAC 指引补齐用户或调用方代理授权。";
    throw new RuleBundleError("RULE_BUNDLE_SSO_ACCESS_DENIED", `SSO 代理访问被拒绝（${code}）。${suffix}`);
  }
  if (code === "ric_feedback_required") {
    const suffix = guidance ? ` 官方指引：${guidance}` : " 请完成人工确认后重试。";
    throw new RuleBundleError("RULE_BUNDLE_SSO_USER_ACTION_REQUIRED", `SSO 要求用户人工处理。${suffix}`);
  }
  if (CIBA_PENDING_CODES.has(code)) {
    throw new RuleBundleError(
      "RULE_BUNDLE_CIBA_CONFIRMATION_REQUIRED",
      "请在大象 App 确认 CIBA 授权卡片后重新拉取规则。",
    );
  }
  if (CIBA_REJECTED_CODES.has(code)) {
    throw new RuleBundleError("RULE_BUNDLE_CIBA_REJECTED", "大象 CIBA 授权被拒绝或仍在冷却期，请稍后重新确认。");
  }
  if (exitCode === 42) {
    throw new RuleBundleError(
      "RULE_BUNDLE_SSO_USER_ACTION_REQUIRED",
      "官方 SSO 返回需人工介入的退出码，但未返回可识别的错误 JSON；请按官方指引排查后重试。",
    );
  }
  if (cause?.killed || cause?.code === "ETIMEDOUT" || cause?.signal) {
    throw new RuleBundleError("RULE_BUNDLE_SSO_EXCHANGE_FAILED", "官方 SSO 换票超时或被中断；不会切换认证路径。");
  }
  if (NETWORK_FAILURE_CODES.has(cause?.code)) {
    throw new RuleBundleError("RULE_BUNDLE_SSO_EXCHANGE_FAILED", "官方 SSO 换票发生网络错误；不会切换认证路径。");
  }
  if (NETWORK_FAILURE_MARKERS.some((marker) => marker.test(raw))) {
    throw new RuleBundleError("RULE_BUNDLE_SSO_EXCHANGE_FAILED", "官方 SSO 换票响应包含网络失败信息；不会切换认证路径。");
  }
  if (AGENT_SSO_CONFIGURATION_MARKERS.some((marker) => raw.includes(marker))) return "portable";
  if (
    LOCAL_CAPABILITY_MISSING_MARKERS.some((marker) => raw.includes(marker))
    || /["']?support_type["']?\s*[:=]\s*["']?none/iu.test(raw)
    || cause?.code === "ENOENT"
  ) return "portable";
  throw new RuleBundleError("RULE_BUNDLE_SSO_EXCHANGE_FAILED", "官方 SSO 换票失败；不会因网络或非法响应切换身份路径。");
};

const portableErrorMap = new Map([
  ["PORTABLE_AUTH_PROVIDER_REQUIRED", "RULE_BUNDLE_SSO_PORTABLE_PROVIDER_REQUIRED"],
  ["PORTABLE_AUTH_NODE_REQUIRED", "RULE_BUNDLE_SSO_PORTABLE_PROVIDER_REQUIRED"],
  ["PORTABLE_AUTH_CLEANUP_FAILED", "RULE_BUNDLE_SSO_PORTABLE_CLEANUP_FAILED"],
  ["PORTABLE_AUTH_MIS_REQUIRED", "RULE_BUNDLE_PORTABLE_MIS_REQUIRED"],
  ["PORTABLE_AUTH_ACCESS_DENIED", "RULE_BUNDLE_SSO_ACCESS_DENIED"],
  ["PORTABLE_AUTH_USER_ACTION_REQUIRED", "RULE_BUNDLE_SSO_USER_ACTION_REQUIRED"],
  ["PORTABLE_AUTH_REJECTED", "RULE_BUNDLE_CIBA_REJECTED"],
  ["PORTABLE_AUTH_CONFIRMATION_REQUIRED", "RULE_BUNDLE_CIBA_CONFIRMATION_REQUIRED"],
]);
const portableErrorMessages = new Map([
  ["PORTABLE_AUTH_PROVIDER_REQUIRED", "便携 SSO provider 不可用；请安装或更新 @it/oa-skills（shared >= 1.2.0）。"],
  ["PORTABLE_AUTH_NODE_REQUIRED", "便携 SSO CIBA 要求 Node.js >= 18。"],
  ["PORTABLE_AUTH_CLEANUP_FAILED", "便携认证临时缓存清理失败；本次认证结果已作废。"],
  ["PORTABLE_AUTH_MIS_REQUIRED", "便携 SSO CIBA 需要通过 --mis 或 SSO_USER_ID 提供当前公司用户 MIS。"],
  ["PORTABLE_AUTH_ACCESS_DENIED", "SSO/UAC 拒绝代理访问目标应用，请按官方授权指引处理。"],
  ["PORTABLE_AUTH_USER_ACTION_REQUIRED", "SSO 要求用户完成人工确认，请按大象中的官方指引操作后重试。"],
  ["PORTABLE_AUTH_REJECTED", "用户已拒绝 CIBA 授权或仍处于冷却期，请稍后重新发起。"],
  ["PORTABLE_AUTH_CONFIRMATION_REQUIRED", "请在大象 App 完成 CIBA 授权确认后重新拉取规则。"],
]);

const tokenFromPortableProvider = async ({ mis, environment, execute }) => {
  const normalizedMis = text(mis || environment.SSO_USER_ID);
  if (!normalizedMis) {
    throw new RuleBundleError(
      "RULE_BUNDLE_PORTABLE_MIS_REQUIRED",
      "便携 CIBA 需要通过 --mis 或 SSO_USER_ID 提供当前公司用户 MIS。",
    );
  }
  const helper = fileURLToPath(new URL("./portable-user-auth.mjs", import.meta.url));
  let result;
  try {
    result = await execute(process.execPath, [helper, "--mis", normalizedMis], {
      env: environment,
      timeout: PORTABLE_TIMEOUT_MS,
      maxBuffer: 64 * 1024,
    });
  } catch (cause) {
    if (cause?.killed || cause?.code === "ETIMEDOUT" || cause?.signal === "SIGTERM") {
      throw new RuleBundleError(
        "RULE_BUNDLE_CIBA_CONFIRMATION_REQUIRED",
        "便携 CIBA 等待确认超时，请在大象 App 处理授权卡片后重新拉取规则。",
      );
    }
    const payload = parseJson(text(cause?.stdout));
    const providerCode = text(payload?.error?.code);
    const stableCode = portableErrorMap.get(providerCode) || "RULE_BUNDLE_SSO_PORTABLE_FAILED";
    const stableMessage = portableErrorMessages.get(providerCode) || "便携 SSO CIBA 未能取得用户票据。";
    throw new RuleBundleError(stableCode, stableMessage);
  }
  const payload = parseJson(text(result?.stdout));
  const token = text(payload?.token);
  if (!token || payload?.error) {
    throw new RuleBundleError("RULE_BUNDLE_SSO_PORTABLE_FAILED", "便携 SSO CIBA 返回了非法响应。");
  }
  return { token, mode: "portable_sso_ciba" };
};

export const tokenFromOfficialExchange = async ({
  environment = process.env,
  execute = execFileAsync,
  mis,
} = {}) => {
  const injected = text(environment.RULE_OBSERVABILITY_USER_TOKEN);
  if (injected) return { token: injected, mode: "injected_user_token" };
  let result;
  try {
    result = await execute("npx", [
      "mtsso-moa-local-exchange", "--audience", AUDIENCE,
    ], { env: environment, timeout: OFFICIAL_TIMEOUT_MS, maxBuffer: 64 * 1024 });
  } catch (cause) {
    const stdout = text(cause?.stdout);
    const raw = `${stdout}\n${text(cause?.stderr)}`;
    const fallback = officialFailure({ payload: parseJson(stdout), raw, exitCode: cause?.code, cause });
    if (fallback === "portable") return tokenFromPortableProvider({ mis, environment, execute });
  }
  const raw = text(result?.stdout);
  if (raw.startsWith("AT_FOR_GW_BASE64_")) return { token: raw, mode: "official_gateway_exchange" };
  const payload = parseJson(raw);
  if (!payload) {
    throw new RuleBundleError("RULE_BUNDLE_SSO_EXCHANGE_FAILED", "官方 SSO 换票返回了非 JSON 内容。");
  }
  if (payload.error || payload.code || payload.success === false) {
    const fallback = officialFailure({ payload, raw, exitCode: 0 });
    if (fallback === "portable") return tokenFromPortableProvider({ mis, environment, execute });
  }
  const token = text(payload.access_token);
  if (token) return { token, mode: "official_moa_exchange" };
  throw new RuleBundleError("RULE_BUNDLE_SSO_EXCHANGE_FAILED", "官方 SSO 换票未返回可用用户票据。");
};

const tokenFromSelectedRoute = async ({
  selection, environment, execute = execFileAsync, mis,
}) => {
  if (selection.route === "injected") {
    return { token: text(environment.RULE_OBSERVABILITY_USER_TOKEN), mode: "injected_user_token" };
  }
  if (selection.route === "portable") {
    return tokenFromPortableProvider({ mis, environment, execute });
  }
  return tokenFromOfficialExchange({ environment, execute, mis });
};

const selectRunnerAuthenticationRoute = ({ environment, options, executionAgent }) => {
  if (text(environment.RULE_OBSERVABILITY_USER_TOKEN) || !options.standaloneCli || options.authAgent) {
    return selectAuthenticationRoute({
      environment,
      authAgent: options.authAgent,
      executionAgent,
    });
  }
  return { route: "portable", reason: "standalone_cli", authAgent: "standalone-cli" };
};

export const syncWithOfficialSso = async ({
  options = {}, environment = process.env, execute, fetchImpl,
} = {}) => {
  const detected = detectExecutionAgent(environment);
  const explicitAgent = text(options.agent);
  if (explicitAgent && !EXECUTION_AGENTS.has(explicitAgent)) {
    throw new RuleBundleError("RULE_BUNDLE_EXECUTION_INVALID", "执行 Agent 必须是受支持的平台标识。");
  }
  await prepareSyncRequest({
    gatewayUrl: options.gatewayUrl,
    repositoryLocator: options.repositoryLocator,
    repoRoot: options.repoRoot,
    outputDir: options.outputDir,
    cwd: options.cwd,
    domain: options.domain,
    bootstrap: options.bootstrap,
    stage: options.stage,
    execution: {
      pullId: options.pullId,
      agent: explicitAgent || detected.agent,
      source: explicitAgent ? "runner_explicit_v1" : detected.source,
      skillVersion: options.skillVersion,
    },
  });
  let selection = selectRunnerAuthenticationRoute({
    environment,
    options,
    executionAgent: explicitAgent,
  });
  const pullId = options.pullId || randomUUID();
  const run = (credential) => syncEffectiveRuleBundle({
    gatewayUrl: options.gatewayUrl,
    token: credential.token,
    repositoryLocator: options.repositoryLocator,
    repoRoot: options.repoRoot,
    outputDir: options.outputDir,
    cwd: options.cwd,
    domain: options.domain,
    bootstrap: options.bootstrap,
    stage: options.stage,
    fetchImpl,
    execution: {
      pullId,
      agent: explicitAgent || detected.agent,
      source: explicitAgent ? "runner_explicit_v1" : detected.source,
      skillVersion: options.skillVersion,
    },
  });
  let credential = await tokenFromSelectedRoute({
    selection, environment, execute, mis: options.mis,
  });
  try {
    const receipt = await run(credential);
    return {
      ...receipt,
      authentication_mode: credential.mode,
      authentication_route_reason: selection.reason,
    };
  } catch (error) {
    if (credential.mode !== "injected_user_token" || error?.code !== "unauthorized") throw error;
    const retryEnvironment = { ...environment, RULE_OBSERVABILITY_USER_TOKEN: "" };
    selection = selectRunnerAuthenticationRoute({
      environment: retryEnvironment,
      options,
      executionAgent: explicitAgent,
    });
    credential = await tokenFromSelectedRoute({
      selection, environment: retryEnvironment, execute, mis: options.mis,
    });
    const receipt = await run(credential);
    return {
      ...receipt,
      authentication_mode: `${credential.mode}_after_injected_token_rejected`,
      authentication_route_reason: `${selection.reason}_after_injected_token_rejected`,
    };
  }
};

const main = async () => {
  const options = parseArgs(process.argv.slice(2));
  const receipt = await syncWithOfficialSso({ options });
  process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
};

const isDirectExecution = () => {
  if (!process.argv[1]) return false;
  try {
    return realpathSync(process.argv[1]) === fileURLToPath(import.meta.url);
  } catch {
    return false;
  }
};

if (isDirectExecution()) {
  main().catch((error) => {
    const code = error instanceof RuleBundleError ? error.code : "RULE_BUNDLE_UNEXPECTED";
    process.stderr.write(`${code}: ${error.message}\n`);
    process.exitCode = 2;
  });
}
