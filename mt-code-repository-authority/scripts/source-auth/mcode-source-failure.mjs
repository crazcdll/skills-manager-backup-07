import { sanitizePublicErrorMessage } from "./upstream-error-message.mjs";
export const MCODE_SOURCE_ERROR_SCHEMA = "catx-mcode-source-error/v1";
export const MCODE_SOURCE_DIAGNOSTIC_REVISION = "mcode-reader-diagnostics/2026-09-21.1";

export const MCODE_SOURCE_FAILURE_CODES = Object.freeze(new Set([
  "mcode_auth_provider_unavailable",
  "mcode_auth_required",
  "mcode_auth_expired",
  "mcode_auth_refused",
  "mcode_auth_timeout",
  "mcode_identity_mismatch",
  "mcode_auth_cleanup_failed",
  "mcode_auth_failed",
  "mcode_access_denied",
  "mcode_source_not_found",
  "mcode_rate_limited",
  "mcode_service_failed",
  "mcode_source_timeout",
  "mcode_network_failed",
  "mcode_response_invalid",
  "mcode_revision_unresolved",
  "mcode_source_read_failed",
]));
const OPERATIONS = Object.freeze(new Set([
  "authenticate", "resolve_revision", "list_files", "read_file", "validate_input",
]));
const SHAPES = Object.freeze(new Set([
  "none", "object", "commits_page", "files_page", "file_lines",
]));
const KNOWN_SIGNALS = Object.freeze(new Set([
  "auth_provider_unavailable", "auth_required", "auth_refused", "auth_timeout",
  "identity_mismatch", "auth_cache_invalid", "auth_cleanup_failed", "auth_proxy_access_denied",
  "access_denied", "auth_failed", "http_not_found", "invalid_response", "network_failure",
  "rate_limited", "revision_unresolved", "service_failure", "timeout", "unknown_failure",
  "invalid_source_url", "invalid_revision", "invalid_actor", "unsafe_source_path",
  "invalid_auth_contract",
  "path_no_files", "no_supported_files", "file_limit_exceeded",
  "file_byte_limit_exceeded", "total_byte_limit_exceeded", "pagination_incomplete",
]));
const PROCESS_ERROR_CODES = Object.freeze(new Set([
  "none", "timeout", "not_found", "permission_denied", "signal", "other",
]));
const STDOUT_SHAPES = Object.freeze(new Set([
  "none", "gateway_token", "json_access_token", "json_without_access_token", "opaque_text",
]));
const KEYS = Object.freeze(new Set([
  "schema_version", "diagnostic_revision", "code", "operation", "http_status", "shape",
  "process_exit_code", "process_error_code", "stdout_shape",
  "node_version", "platform", "arch", "known_signals",
]));
const PLATFORMS = new Set(["aix", "android", "darwin", "freebsd", "haiku", "linux", "openbsd", "sunos", "win32"]);
const ARCHITECTURES = new Set(["arm", "arm64", "ia32", "loong64", "mips", "mipsel", "ppc", "ppc64", "riscv64", "s390", "s390x", "x64"]);

const exactKeys = (value) => value && typeof value === "object" && !Array.isArray(value) &&
  Object.keys(value).length === KEYS.size && Object.keys(value).every((key) => KEYS.has(key));

export const createMCodeSourceFailure = ({
  code,
  message = null,
  operation = "validate_input",
  httpStatus = null,
  shape = "none",
  processExitCode = null,
  processErrorCode = "none",
  stdoutShape = "none",
  knownSignals = [],
} = {}) => Object.freeze({
  schema_version: message ? "catx-mcode-source-error/v2" : MCODE_SOURCE_ERROR_SCHEMA,
  ...(message ? { message: sanitizePublicErrorMessage(message) } : {}),
  diagnostic_revision: MCODE_SOURCE_DIAGNOSTIC_REVISION,
  code: MCODE_SOURCE_FAILURE_CODES.has(code) ? code : "mcode_source_read_failed",
  operation: OPERATIONS.has(operation) ? operation : "validate_input",
  http_status: Number.isInteger(httpStatus) && httpStatus >= 100 && httpStatus <= 599 ? httpStatus : null,
  shape: SHAPES.has(shape) ? shape : "none",
  process_exit_code: Number.isInteger(processExitCode) && processExitCode >= 0 && processExitCode <= 255
    ? processExitCode
    : null,
  process_error_code: PROCESS_ERROR_CODES.has(processErrorCode) ? processErrorCode : "other",
  stdout_shape: STDOUT_SHAPES.has(stdoutShape) ? stdoutShape : "opaque_text",
  node_version: /^v\d+[.]\d+[.]\d+(?:[-+][0-9A-Za-z.-]+)?$/u.test(process.version) ? process.version : null,
  platform: PLATFORMS.has(process.platform) ? process.platform : null,
  arch: ARCHITECTURES.has(process.arch) ? process.arch : null,
  known_signals: [...new Set(knownSignals)].filter((value) => KNOWN_SIGNALS.has(value)).sort(),
});

export const serializeMCodeSourceFailure = (failure) => `${JSON.stringify(createMCodeSourceFailure({
  code: failure?.code,
  message: failure?.message,
  operation: failure?.operation,
  httpStatus: failure?.http_status,
  shape: failure?.shape,
  processExitCode: failure?.process_exit_code,
  processErrorCode: failure?.process_error_code,
  stdoutShape: failure?.stdout_shape,
  knownSignals: failure?.known_signals,
}))}\n`;

export const parseMCodeSourceFailure = (input) => {
  let value;
  try { value = JSON.parse(String(input ?? "").trim()); } catch { return null; }
  if (
    !(value?.schema_version === "catx-mcode-source-error/v2"
      ? value && typeof value === "object" && Object.keys(value).length === KEYS.size + 1 && Object.keys(value).every(key => KEYS.has(key) || key === "message")
        && (value.message === null || typeof value.message === "string" && sanitizePublicErrorMessage(value.message) === value.message)
      : exactKeys(value) && value.schema_version === MCODE_SOURCE_ERROR_SCHEMA) ||
    value.diagnostic_revision !== MCODE_SOURCE_DIAGNOSTIC_REVISION ||
    !MCODE_SOURCE_FAILURE_CODES.has(value.code) || !OPERATIONS.has(value.operation) ||
    !(value.http_status === null || (Number.isInteger(value.http_status) && value.http_status >= 100 && value.http_status <= 599)) ||
    !SHAPES.has(value.shape) ||
    !(value.process_exit_code === null || (Number.isInteger(value.process_exit_code) && value.process_exit_code >= 0 && value.process_exit_code <= 255)) ||
    !PROCESS_ERROR_CODES.has(value.process_error_code) || !STDOUT_SHAPES.has(value.stdout_shape) ||
    !(value.node_version === null || (typeof value.node_version === "string" && value.node_version.length <= 40 && /^v\d+[.]\d+[.]\d+(?:[-+][0-9A-Za-z.-]+)?$/u.test(value.node_version))) ||
    !(value.platform === null || PLATFORMS.has(value.platform)) ||
    !(value.arch === null || ARCHITECTURES.has(value.arch)) ||
    !Array.isArray(value.known_signals) || value.known_signals.some((signal) => !KNOWN_SIGNALS.has(signal)) ||
    new Set(value.known_signals).size !== value.known_signals.length
  ) return null;
  return Object.freeze({ ...value, known_signals: Object.freeze([...value.known_signals]) });
};

export class MCodeSourceFailureError extends Error {
  constructor(failure) {
    super(failure.code);
    this.name = "MCodeSourceFailureError";
    this.failure = failure;
  }
}

export const throwMCodeSourceFailure = (failure) => { throw new MCodeSourceFailureError(failure); };

export const failureForMCodeHttpStatus = (status, operation, shape) => {
  if (status === 401) return createMCodeSourceFailure({ code: "mcode_auth_failed", operation, httpStatus: status, shape, knownSignals: ["auth_failed"] });
  if (status === 403) return createMCodeSourceFailure({ code: "mcode_access_denied", operation, httpStatus: status, shape, knownSignals: ["access_denied"] });
  if (status === 404) return createMCodeSourceFailure({ code: "mcode_source_not_found", operation, httpStatus: status, shape, knownSignals: ["http_not_found"] });
  if (status === 429) return createMCodeSourceFailure({ code: "mcode_rate_limited", operation, httpStatus: status, shape, knownSignals: ["rate_limited"] });
  if (status >= 500) return createMCodeSourceFailure({ code: "mcode_service_failed", operation, httpStatus: status, shape, knownSignals: ["service_failure"] });
  return createMCodeSourceFailure({ code: "mcode_response_invalid", operation, httpStatus: status, shape, knownSignals: ["invalid_response"] });
};
