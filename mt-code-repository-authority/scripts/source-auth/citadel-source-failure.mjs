import { extractPublicErrorMessage, sanitizePublicErrorMessage } from "./upstream-error-message.mjs";

export const CITADEL_SOURCE_ERROR_SCHEMA = "catx-citadel-source-error/v2";
const LEGACY_ERROR_SCHEMA = "catx-citadel-source-error/v1";
const LEGACY_DIAGNOSTIC_REVISION = "citadel-reader-diagnostics/2026-09-11.1";
export const CITADEL_SOURCE_DIAGNOSTIC_REVISION = "citadel-reader-diagnostics/2026-10-20.1";

export const CITADEL_SOURCE_FAILURE_CODES = Object.freeze(new Set([
  "citadel_cli_unavailable",
  "citadel_source_timeout",
  "citadel_auth_provider_unavailable",
  "citadel_identity_mismatch",
  "citadel_auth_expired",
  "citadel_auth_denied",
  "citadel_auth_required",
  "citadel_auth_failed",
  "citadel_network_failed",
  "citadel_document_access_denied",
  "citadel_secure_environment_required",
  "citadel_source_read_failed",
]));

const FAILURE_KEYS = Object.freeze(new Set([
  "schema_version",
  "diagnostic_revision",
  "code",
  "attempt",
  "exit",
  "signal",
  "spawn_code",
  "node_version",
  "platform",
  "arch",
  "known_signals",
]));
const FAILURE_KEYS_V2 = Object.freeze(new Set([...FAILURE_KEYS, "message"]));
const KNOWN_SIGNALS = Object.freeze(new Set([
  "auth_failed",
  "auth_required",
  "cli_missing",
  "document_access_denied",
  "empty_output",
  "http_403_unscoped",
  "invalid_error_payload",
  "invalid_input",
  "invalid_source_artifact",
  "invalid_source_json",
  "network_failure",
  "permission_denied_unscoped",
  "reader_start_failed",
  "secure_environment_required",
  "signal_terminated",
  "source_too_large",
  "spawn_failed",
  "timeout",
  "unknown_failure",
  "upgrade_prompt",
]));
const PROCESS_SIGNALS = Object.freeze(new Set([
  "SIGABRT", "SIGALRM", "SIGBUS", "SIGFPE", "SIGHUP", "SIGILL", "SIGINT",
  "SIGKILL", "SIGPIPE", "SIGQUIT", "SIGSEGV", "SIGTERM", "SIGTRAP", "SIGUSR1",
  "SIGUSR2",
]));
const SPAWN_CODES = Object.freeze(new Set(["EACCES", "ENOENT", "EPERM", "ETIMEDOUT"]));
const PLATFORMS = Object.freeze(new Set([
  "aix", "android", "darwin", "freebsd", "haiku", "linux", "openbsd", "sunos", "win32",
]));
const ARCHITECTURES = Object.freeze(new Set([
  "arm", "arm64", "ia32", "loong64", "mips", "mipsel", "ppc", "ppc64", "riscv64", "s390",
  "s390x", "x64",
]));

const exactKeys = (value, expected) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const actual = Object.keys(value);
  return actual.length === expected.size && actual.every((key) => expected.has(key));
};

const safeExit = (value) => Number.isInteger(value) && value >= -255 && value <= 255
  ? value
  : null;
const safeSignal = (value) => PROCESS_SIGNALS.has(value) ? value : null;
const safeSpawnCode = (value) => SPAWN_CODES.has(value) ? value : null;
const safeKnownSignals = (values) => [...new Set(Array.isArray(values) ? values : [])]
  .filter((value) => KNOWN_SIGNALS.has(value))
  .sort();

export const createCitadelSourceFailure = ({
  code,
  message = null,
  attempt = 0,
  exit = null,
  signal = null,
  spawnCode = null,
  knownSignals = [],
} = {}) => Object.freeze({
  schema_version: CITADEL_SOURCE_ERROR_SCHEMA,
  diagnostic_revision: CITADEL_SOURCE_DIAGNOSTIC_REVISION,
  code: CITADEL_SOURCE_FAILURE_CODES.has(code) ? code : "citadel_source_read_failed",
  message: sanitizePublicErrorMessage(message),
  attempt: Number.isInteger(attempt) && attempt >= 0 && attempt <= 3 ? attempt : 0,
  exit: safeExit(exit),
  signal: safeSignal(signal),
  spawn_code: safeSpawnCode(spawnCode),
  node_version: /^v\d+[.]\d+[.]\d+(?:[-+][0-9A-Za-z.-]+)?$/u.test(process.version)
    ? process.version
    : null,
  platform: PLATFORMS.has(process.platform) ? process.platform : null,
  arch: ARCHITECTURES.has(process.arch) ? process.arch : null,
  known_signals: safeKnownSignals(knownSignals),
});

export const serializeCitadelSourceFailure = (failure) => (
  `${JSON.stringify(createCitadelSourceFailure({
    code: failure?.code,
    message: failure?.message,
    attempt: failure?.attempt,
    exit: failure?.exit,
    signal: failure?.signal,
    spawnCode: failure?.spawn_code,
    knownSignals: failure?.known_signals,
  }))}\n`
);

export const parseCitadelSourceFailure = (input) => {
  let value;
  try { value = JSON.parse(String(input ?? "").trim()); } catch { return null; }
  const legacy = value?.schema_version === LEGACY_ERROR_SCHEMA;
  if (
    !exactKeys(value, legacy ? FAILURE_KEYS : FAILURE_KEYS_V2) ||
    value.schema_version !== (legacy ? LEGACY_ERROR_SCHEMA : CITADEL_SOURCE_ERROR_SCHEMA) ||
    value.diagnostic_revision !== (legacy ? LEGACY_DIAGNOSTIC_REVISION : CITADEL_SOURCE_DIAGNOSTIC_REVISION) ||
    (!legacy && value.message !== null && (typeof value.message !== "string" || sanitizePublicErrorMessage(value.message) !== value.message)) ||
    (legacy && value.code === "citadel_secure_environment_required") ||
    !CITADEL_SOURCE_FAILURE_CODES.has(value.code) ||
    !Number.isInteger(value.attempt) || value.attempt < 0 || value.attempt > 3 ||
    !(value.exit === null || safeExit(value.exit) === value.exit) ||
    !(value.signal === null || safeSignal(value.signal) === value.signal) ||
    !(value.spawn_code === null || safeSpawnCode(value.spawn_code) === value.spawn_code) ||
    !(value.node_version === null || (
      typeof value.node_version === "string" && value.node_version.length <= 40 &&
      /^v\d+[.]\d+[.]\d+(?:[-+][0-9A-Za-z.-]+)?$/u.test(value.node_version)
    )) ||
    !(value.platform === null || PLATFORMS.has(value.platform)) ||
    !(value.arch === null || ARCHITECTURES.has(value.arch)) ||
    !Array.isArray(value.known_signals) || value.known_signals.length > KNOWN_SIGNALS.size ||
    value.known_signals.some((signal) => !KNOWN_SIGNALS.has(signal)) ||
    new Set(value.known_signals).size !== value.known_signals.length
  ) return null;
  return Object.freeze({ ...value, message: legacy ? null : value.message, known_signals: Object.freeze([...value.known_signals]) });
};

const combinedOutput = (result) => `${result?.stdout ?? ""}\n${result?.stderr ?? ""}`;

const chineseDocumentAccessDenied = (value) => (
  /(?:无|没有)(?:查看|阅读|访问)(?:该|此|当前)?文档(?:的)?权限/u.test(value) ||
  /(?:无|没有)(?:该|此|当前)?文档(?:的)?(?:查看|阅读|访问)权限/u.test(value) ||
  /(?:文档|学城|知识库).{0,80}(?:(?:无|没有)(?:查看|阅读|访问)?(?:的)?权限|权限不足|拒绝访问)/u.test(value) ||
  /(?:(?:无|没有)(?:查看|阅读|访问)?(?:的)?权限|权限不足|拒绝访问).{0,80}(?:文档|学城|知识库)/u.test(value)
);

const documentAccessDenied = (value) => (
  /document.{0,80}(?:403|forbidden|access denied|permission denied)/iu.test(value) ||
  /(?:403|forbidden|access denied|permission denied).{0,80}document/iu.test(value) ||
  chineseDocumentAccessDenied(value)
);
const authRequired = (value) => (
  /\b(?:ric_feedback_required|MOA_NOT_LOGGED_IN)\b/u.test(value) ||
  /(?:authentication|authorization|auth|sso|ciba).{0,80}(?:required|missing|not logged in|login required)/iu.test(value) ||
  /(?:请|需要|必须).{0,20}(?:登录|认证|授权)/u.test(value) ||
  /(?:登录|认证|授权).{0,20}(?:过期|失效|未完成|缺失)/u.test(value)
);
const networkFailure = (value) => (
  /(?:fetch failed|network(?: request)? (?:failed|failure|error)|socket hang up|\b(?:ECONNRESET|ECONNREFUSED|ENETUNREACH|ENOTFOUND|EAI_AGAIN)\b|DNS lookup)/iu.test(value)
);
const authFailed = (value) => (
  /\b(?:sub_access_denied|act_access_denied|sub_act_access_denied|MOA_USER_REJECTED)\b/u.test(value) ||
  /\b401\s+(?:unauthorized|未授权)\b/iu.test(value) ||
  /\bunauthorized\b/iu.test(value) ||
  /(?:authentication|authorization|auth|sso|ciba).{0,80}(?:failed|failure|invalid|expired|denied)/iu.test(value) ||
  /(?:认证|鉴权|换票|登录|授权).{0,30}(?:失败|失效|过期|拒绝)/u.test(value)
);
const secureEnvironmentRequired = (value) => (
  /(?:C4|高密|安全屋|secure environment|secure house|密级).{0,160}(?:失败|拒绝|required|需要|only|仅|不可用|不支持|访问)/iu.test(value) ||
  /(?:失败|拒绝|required|需要|only|仅|不可用|不支持|访问).{0,160}(?:C4|高密|安全屋|secure environment|secure house|密级)/iu.test(value)
);

export const classifyCitadelCliFailure = (result, attempt) => {
  const spawnCode = safeSpawnCode(result?.error?.code);
  if (spawnCode === "ETIMEDOUT") {
    return createCitadelSourceFailure({
      code: "citadel_source_timeout", attempt, exit: result?.status,
      signal: result?.signal, spawnCode, knownSignals: ["timeout"],
    });
  }
  if (spawnCode === "ENOENT" || spawnCode === "EACCES" || spawnCode === "EPERM") {
    return createCitadelSourceFailure({
      code: "citadel_cli_unavailable", attempt, exit: result?.status,
      signal: result?.signal, spawnCode,
      knownSignals: [spawnCode === "ENOENT" ? "cli_missing" : "spawn_failed"],
    });
  }
  if (result?.error) {
    return createCitadelSourceFailure({
      code: "citadel_source_read_failed", attempt, exit: result?.status,
      signal: result?.signal, spawnCode, knownSignals: ["spawn_failed"],
    });
  }
  if (result?.signal) {
    return createCitadelSourceFailure({
      code: "citadel_source_read_failed", attempt, exit: result?.status,
      signal: result.signal, knownSignals: ["signal_terminated"],
    });
  }
  const output = combinedOutput(result);
  const publicMessage = extractPublicErrorMessage(result, { prefer: secureEnvironmentRequired });
  const terminalOutput = [publicMessage ?? "", ...output.split(/\r?\n/u)
    .filter((line) => !/(?:自动降级|降级到策略|fallback policy|falling back)/iu.test(line))]
    .join("\n");
  for (const [matches, code, knownSignal] of [
    [secureEnvironmentRequired, "citadel_secure_environment_required", "secure_environment_required"],
    [documentAccessDenied, "citadel_document_access_denied", "document_access_denied"],
    [networkFailure, "citadel_network_failed", "network_failure"],
    [authFailed, "citadel_auth_failed", "auth_failed"],
    [authRequired, "citadel_auth_required", "auth_required"],
  ]) {
    if (matches(terminalOutput)) return createCitadelSourceFailure({
      code, message: extractPublicErrorMessage(result, { prefer: matches }),
      attempt, exit: result?.status, knownSignals: [knownSignal],
    });
  }
  const knownSignals = [];
  if (/\b403\b/u.test(output)) knownSignals.push("http_403_unscoped");
  if (/\b(?:permission denied|access denied|forbidden)\b/iu.test(output)) {
    knownSignals.push("permission_denied_unscoped");
  }
  if (!knownSignals.length) knownSignals.push("unknown_failure");
  return createCitadelSourceFailure({
    code: "citadel_source_read_failed", attempt, exit: result?.status,
    knownSignals, message: publicMessage,
  });
};

export class CitadelSourceFailureError extends Error {
  constructor(failure) {
    super(failure.code);
    this.name = "CitadelSourceFailureError";
    this.failure = failure;
  }
}

export const throwCitadelSourceFailure = (failure) => {
  throw new CitadelSourceFailureError(failure);
};
