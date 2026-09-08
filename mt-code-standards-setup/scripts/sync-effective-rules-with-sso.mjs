#!/usr/bin/env node

import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { randomUUID } from "node:crypto";
import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  RuleBundleError,
  EXECUTION_AGENTS,
  syncEffectiveRuleBundle,
} from "./resolve-effective-rules.mjs";

const execFileAsync = promisify(execFile);
const AUDIENCE = "923a237244";
const CIBA_CODES = new Set([
  "MOA_NOT_LOGGED_IN", "MOA_AUTH_REQUEST_PENDING", "ric_feedback_required",
]);
const AGENT_SSO_CONFIGURATION_MARKERS = ["缺少 client_id", "missing client_id", "AGENT_SSO_CLIENT_ID"];

const text = (value) => String(value ?? "").trim();
const parseArgs = (argv) => {
  const result = {};
  const valued = new Set([
    "--repository", "--repo-root", "--gateway-url", "--execution-agent", "--skill-version",
    "--pull-id",
  ]);
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!valued.has(key) || index + 1 >= argv.length) {
      throw new RuleBundleError("RULE_BUNDLE_ARGUMENT_INVALID", `未知或缺值参数：${key}`);
    }
    const value = argv[index + 1];
    if (key === "--repository") result.repositoryLocator = value;
    else if (key === "--repo-root") result.repoRoot = value;
    else if (key === "--gateway-url") result.gatewayUrl = value;
    else if (key === "--execution-agent") result.agent = value;
    else if (key === "--skill-version") result.skillVersion = value;
    else if (key === "--pull-id") result.pullId = value;
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

const errorCode = (raw) => {
  try {
    const parsed = JSON.parse(raw);
    return text(parsed?.code || parsed?.error?.code || parsed?.error);
  } catch { return ""; }
};

export const tokenFromOfficialExchange = async ({
  environment = process.env,
  execute = execFileAsync,
} = {}) => {
  const injected = text(environment.RULE_OBSERVABILITY_USER_TOKEN);
  if (injected) return { token: injected, mode: "injected_user_token" };
  try {
    const { stdout } = await execute("npx", [
      "mtsso-moa-local-exchange", "--audience", AUDIENCE,
    ], { timeout: 30_000, maxBuffer: 64 * 1024 });
    const raw = text(stdout);
    if (raw.startsWith("AT_FOR_GW_BASE64_")) return { token: raw, mode: "official_gateway_exchange" };
    const parsed = JSON.parse(raw);
    const token = text(parsed?.access_token);
    if (token) return { token, mode: "official_moa_exchange" };
  } catch (cause) {
    const raw = `${text(cause?.stdout)}\n${text(cause?.stderr)}`;
    const code = errorCode(text(cause?.stdout)) || [...CIBA_CODES].find((item) => raw.includes(item));
    if (AGENT_SSO_CONFIGURATION_MARKERS.some((marker) => raw.includes(marker))) {
      throw new RuleBundleError(
        "RULE_BUNDLE_SSO_AGENT_CONFIG_REQUIRED",
        "当前 Agent 未配置官方 SSO client_id，无法发起大象 CIBA 确认。",
      );
    }
    if (CIBA_CODES.has(code)) {
      throw new RuleBundleError(
        "RULE_BUNDLE_CIBA_CONFIRMATION_REQUIRED",
        "请在大象 App 确认 CIBA 授权卡片后重新拉取规则。",
      );
    }
    if (raw.includes("MOA_USER_REJECTED") || raw.includes("MOA_REJECT_COOLDOWN")) {
      throw new RuleBundleError("RULE_BUNDLE_CIBA_REJECTED", "大象 CIBA 授权被拒绝或仍在冷却期，请稍后重新确认。");
    }
    throw new RuleBundleError("RULE_BUNDLE_SSO_EXCHANGE_FAILED", "未能取得官方用户票据，请检查当前 Agent 的 SSO 适配。");
  }
  throw new RuleBundleError("RULE_BUNDLE_SSO_EXCHANGE_FAILED", "官方换票未返回可用用户票据。");
};

export const syncWithOfficialSso = async ({
  options = {}, environment = process.env, execute, fetchImpl,
} = {}) => {
  const detected = detectExecutionAgent(environment);
  const explicitAgent = text(options.agent);
  if (explicitAgent && !EXECUTION_AGENTS.has(explicitAgent)) {
    throw new RuleBundleError("RULE_BUNDLE_EXECUTION_INVALID", "执行 Agent 必须是受支持的平台标识。");
  }
  const pullId = options.pullId || randomUUID();
  const run = (credential) => syncEffectiveRuleBundle({
    gatewayUrl: options.gatewayUrl,
    token: credential.token,
    repositoryLocator: options.repositoryLocator,
    repoRoot: options.repoRoot,
    fetchImpl,
    execution: {
      pullId,
      agent: explicitAgent || detected.agent,
      source: explicitAgent ? "runner_explicit_v1" : detected.source,
      skillVersion: options.skillVersion,
    },
  });
  let credential = await tokenFromOfficialExchange({ environment, execute });
  try {
    const receipt = await run(credential);
    return { ...receipt, authentication_mode: credential.mode };
  } catch (error) {
    if (credential.mode !== "injected_user_token" || error?.code !== "unauthorized") throw error;
    credential = await tokenFromOfficialExchange({
      environment: { ...environment, RULE_OBSERVABILITY_USER_TOKEN: "" },
      execute,
    });
    const receipt = await run(credential);
    return { ...receipt, authentication_mode: `${credential.mode}_after_injected_token_rejected` };
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
