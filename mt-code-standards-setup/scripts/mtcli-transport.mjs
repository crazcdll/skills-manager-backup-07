import { execFile } from "node:child_process";
import { promisify } from "node:util";

import {
  MAX_RESPONSE_BYTES,
  RuleBundleError,
  canonicalJson,
} from "./resolve-effective-rules.mjs";

const execFileAsync = promisify(execFile);
export const DEFAULT_MTCLI_SERVICE = "mt-code-standards";
const RESOURCE = "bundles";
const TARGET_ENV = "prod";
const SCHEMA_ENV = "prod";
const TIMEOUT_MS = 180_000;
const OUTER_RESPONSE_BYTES = 12 * 1024 * 1024;
const SERVICE_PATTERN = /^[a-z][a-z0-9-]{0,62}$/u;
const TOKEN_ENV_NAMES = new Set([
  "RULE_OBSERVABILITY_USER_TOKEN",
  "NOCODE_AGENT_SSO_TOKEN",
  "MTSSO_ACCESS_TOKEN",
  "MTSSO_USER_ACCESS_TOKEN",
  "SSO_ACCESS_TOKEN",
  "USER_ACCESS_TOKEN",
  "SSO_USER_ID",
  "AGENT_SSO_CLIENT_ID",
  "AGENT_SSO_CLIENT_SECRET",
  "MTSSO_CLIENT_ID",
  "MTSSO_CLIENT_SECRET",
  "SSO_CLIENT_ID",
  "SSO_CLIENT_SECRET",
  "CATDESK_AUTH_TOKEN",
  "CATPAW_AUTH_TOKEN",
  "CODEX_AUTH_TOKEN",
  "CLAUDE_CODE_OAUTH_TOKEN",
  "ANTHROPIC_AUTH_TOKEN",
]);
const METHODS = Object.freeze({
  "/v1/effective-rule-bundles/resolve": "resolve",
  "/v1/l1-rule-bundles/bootstrap": "bootstrap",
});

const text = (value) => String(value ?? "").trim();
const isObject = (value) => Boolean(value) && typeof value === "object" && !Array.isArray(value);

const fail = (code, message) => {
  throw new RuleBundleError(code, message);
};

export const validateMtcliService = (value = DEFAULT_MTCLI_SERVICE) => {
  const service = text(value) || DEFAULT_MTCLI_SERVICE;
  if (!SERVICE_PATTERN.test(service)) {
    fail("RULE_BUNDLE_MTCLI_SERVICE_INVALID", "--mtcli-service 只能使用小写字母、数字和短横线，并且必须以字母开头");
  }
  return service;
};

export const mtcliChildEnvironment = (environment = process.env) => {
  const child = { ...environment, MTCLI_DISABLE_VERSION_CHECK: "1" };
  for (const name of Object.keys(child)) {
    if (
      TOKEN_ENV_NAMES.has(name)
      || /^RULE_OBSERVABILITY_/u.test(name)
      || /^(?:AGENT|NOCODE|MTSSO|SSO|CATDESK|CATPAW|CODEX|CLAUDE|ANTHROPIC).*(?:TOKEN|SECRET)$/u.test(name)
    ) delete child[name];
  }
  return child;
};

const commonArgs = (service, method) => [
  "--mtcli-schema-env", SCHEMA_ENV,
  "--mtcli-target-env", TARGET_ENV,
  "--output", "json",
  "--quiet",
  "--no-cache",
  service, RESOURCE, method,
];

export const mtcliInvocation = ({ service, request, dryRun }) => {
  const method = METHODS[request.resourcePath];
  if (!method) fail("RULE_BUNDLE_MTCLI_METHOD_INVALID", "mtcli 只允许调用规则包 resolve 或 bootstrap 方法");
  const params = JSON.stringify({
    "X-Rule-Auth-Source": request.headers["X-Rule-Auth-Source"],
    "X-Rule-Protocol-Version": request.headers["X-Rule-Protocol-Version"],
  });
  return [
    ...commonArgs(validateMtcliService(service), method),
    "--params", params,
    "--json", JSON.stringify(request.body),
    ...(dryRun ? ["--dry-run"] : []),
  ];
};

const parseJson = (raw, code, message) => {
  if (Buffer.byteLength(raw, "utf8") > OUTER_RESPONSE_BYTES) fail("RULE_BUNDLE_RESPONSE_TOO_LARGE", message);
  try {
    return JSON.parse(raw);
  } catch {
    fail(code, message);
  }
};

const normalizedHeaders = (value) => Object.fromEntries(Object.entries(isObject(value) ? value : {})
  .map(([key, entry]) => [key.toLowerCase(), text(entry)]));

export const validateMtcliDryRun = (payload, request) => {
  if (!isObject(payload) || payload.dry_run !== true) {
    fail("RULE_BUNDLE_MTCLI_DRY_RUN_INVALID", "mtcli dry-run 未返回可验证的请求计划，请刷新服务定义后重试");
  }
  let url;
  try {
    url = new URL(text(payload.url));
  } catch {
    fail("RULE_BUNDLE_MTCLI_DRY_RUN_INVALID", "mtcli dry-run 返回了非法目标地址，已停止拉取");
  }
  if (
    url.href !== request.url
    || url.search
    || url.hash
    || text(payload.method).toUpperCase() !== "POST"
    || text(payload.auth_type).toLowerCase() !== "sso"
    || text(payload.target_env) !== TARGET_ENV
    || !isObject(payload.query_params)
    || Object.keys(payload.query_params).length !== 0
    || canonicalJson(payload.body) !== canonicalJson(request.body)
  ) {
    fail("RULE_BUNDLE_MTCLI_DRY_RUN_INVALID", "mtcli 服务定义与受信任规则网关合同不一致，已停止拉取");
  }
  const headers = normalizedHeaders(payload.headers);
  // mtcli sets JSON Content-Type during HTTP execution, after producing dry-run output.
  if (Object.hasOwn(headers, "content-type")) {
    if (headers["content-type"] !== "application/json") {
      fail("RULE_BUNDLE_MTCLI_DRY_RUN_INVALID", "mtcli 服务定义必须使用 JSON 请求体，已停止拉取");
    }
    delete headers["content-type"];
  }
  const expectedHeaders = Object.entries(request.headers)
    .filter(([name]) => name.toLowerCase() !== "content-type");
  const expectedHeaderNames = expectedHeaders.map(([name]) => name.toLowerCase()).sort();
  const actualHeaderNames = Object.keys(headers).sort();
  if (canonicalJson(actualHeaderNames) !== canonicalJson(expectedHeaderNames)) {
    fail("RULE_BUNDLE_MTCLI_DRY_RUN_INVALID", "mtcli dry-run 包含合同外 Header，已停止拉取");
  }
  for (const [name, value] of expectedHeaders) {
    if (headers[name.toLowerCase()] !== value) {
      fail("RULE_BUNDLE_MTCLI_DRY_RUN_INVALID", "mtcli 服务定义缺少规则分发协议 Header，已停止拉取");
    }
  }
};

const mtcliResponse = (payload) => {
  if (isObject(payload) && typeof payload.success === "boolean"
    && Number.isInteger(payload.status_code) && Object.hasOwn(payload, "data")) {
    if (payload.success !== (payload.status_code >= 200 && payload.status_code < 300)) {
      fail("RULE_BUNDLE_MTCLI_RESPONSE_INVALID", "mtcli 响应状态与 HTTP 状态不一致");
    }
    const body = payload.data;
    const businessError = isObject(body?.error) && typeof body.error.code === "string";
    return {
      status: businessError && payload.status_code >= 200 && payload.status_code < 300
        ? 400
        : payload.status_code,
      body,
    };
  }
  fail("RULE_BUNDLE_MTCLI_RESPONSE_INVALID", "mtcli 未返回 success/status_code/data JSON 响应");
};

const executeMtcli = async ({ execute, args, environment, cwd }) => {
  try {
    return await execute("mtcli", args, {
      env: mtcliChildEnvironment(environment),
      timeout: TIMEOUT_MS,
      maxBuffer: OUTER_RESPONSE_BYTES,
      windowsHide: true,
      cwd,
    });
  } catch (cause) {
    if (cause?.code === "ENOENT") {
      fail("RULE_BUNDLE_MTCLI_NOT_FOUND", "未找到 mtcli，请先从公司 npm 源安装 @dp/mtcli 后重试");
    }
    if (cause?.code === "ERR_CHILD_PROCESS_STDIO_MAXBUFFER") {
      fail("RULE_BUNDLE_RESPONSE_TOO_LARGE", "mtcli 输出超过安全上限，已停止拉取");
    }
    if (cause?.killed || cause?.code === "ETIMEDOUT" || cause?.signal === "SIGTERM") {
      fail("RULE_BUNDLE_MTCLI_TIMEOUT", "mtcli 登录或规则服务调用超时，请确认登录状态和网络后重试");
    }
    const stdout = text(cause?.stdout);
    if (stdout) {
      const payload = parseJson(stdout, "RULE_BUNDLE_MTCLI_EXEC_FAILED", "mtcli 调用失败且未返回有效 JSON");
      return { stdout: JSON.stringify(payload) };
    }
    fail("RULE_BUNDLE_MTCLI_EXEC_FAILED", "mtcli 调用失败，请检查服务定义和登录状态；可先执行 mtcli auth sso login");
  }
};

export const createMtcliTransport = ({
  service = DEFAULT_MTCLI_SERVICE,
  environment = process.env,
  execute = execFileAsync,
  cwd = process.cwd(),
} = {}) => {
  const trustedService = validateMtcliService(service);
  return async (request) => {
    // mtcli carries the official audience-specific SSO cookie internally.
    // Keep the direct Setup transport's legacy header unchanged, while
    // marking mtcli requests so the gateway can validate the target ticket.
    const mtcliRequest = Object.freeze({
      ...request,
      headers: Object.freeze({
        ...request.headers,
        "X-Rule-Auth-Source": "mtcli-sso",
      }),
    });
    const dryRun = await executeMtcli({
      execute,
      args: mtcliInvocation({ service: trustedService, request: mtcliRequest, dryRun: true }),
      environment,
      cwd,
    });
    const dryRunPayload = parseJson(
      text(dryRun?.stdout),
      "RULE_BUNDLE_MTCLI_DRY_RUN_INVALID",
      "mtcli dry-run 未返回有效 JSON，请刷新 mt-code-standards 服务定义后重试",
    );
    validateMtcliDryRun(dryRunPayload, mtcliRequest);

    const executed = await executeMtcli({
      execute,
      args: mtcliInvocation({ service: trustedService, request: mtcliRequest, dryRun: false }),
      environment,
      cwd,
    });
    const payload = parseJson(
      text(executed?.stdout),
      "RULE_BUNDLE_RESPONSE_NOT_JSON",
      "mtcli 规则服务返回了非 JSON 内容",
    );
    const result = mtcliResponse(payload);
    const bodyBytes = Buffer.byteLength(JSON.stringify(result.body), "utf8");
    if (bodyBytes > MAX_RESPONSE_BYTES) {
      fail("RULE_BUNDLE_RESPONSE_TOO_LARGE", "mtcli 规则服务响应超过 4 MiB 安全上限");
    }
    return result;
  };
};
