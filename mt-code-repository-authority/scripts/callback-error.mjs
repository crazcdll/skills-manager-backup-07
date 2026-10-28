// Kept within this independently deployed Skill package; no cross-Skill runtime imports.
export const MAX_PUBLIC_ERROR_MESSAGE_LENGTH = 600;

export const sanitizePublicErrorMessage = (value) => {
  if (typeof value !== "string" || !value.trim() || value.length > 4096) return null;
  const message = value.replace(/\u001b\[[0-?]*[ -/]*[@-~]/gu, "").trim();
  // A multi-line error may contain a stack, HTTP headers or source text; reject it whole.
  if (/[\r\n\u0000-\u001f\u007f]|```|<\/?[A-Za-z][^>]*>|-----BEGIN|\b(?:SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+.+\s+SET|DELETE\s+FROM)\b|\bat\s+\S+\s*\([^)]*:\d+:\d+\)/iu.test(message)) return null;
  const redacted = message
    .replace(/\bBearer\s+[A-Za-z0-9._~+\/-]+=*/giu, "[已隐藏]")
    .replace(/\b(?:authorization|cookie|set-cookie)\s*[:=]\s*.+$/giu, "[已隐藏]")
    .replace(/\b(?:[A-Za-z0-9_-]*(?:token|secret|password|passwd|api[_-]?key|capability|credential)[A-Za-z0-9_-]*)["']?\s*[:=：]\s*(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;，；。]+)/giu, "[已隐藏]")
    .replace(/--[A-Za-z0-9_-]*(?:token|secret|password|passwd|api[_-]?key|capability|credential)[A-Za-z0-9_-]*\s+(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;，；。]+)/giu, "[已隐藏]")
    .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/gu, "[已隐藏]")
    .replace(/https?:\/\/[^\s]+/giu, "[链接已隐藏]")
    .replace(/(?:\/Users\/|\/home\/|\/private\/|\/tmp\/|[A-Za-z]:\\)[^\s,;，；。]+/gu, "[路径已隐藏]")
    .trim();
  if (!redacted || redacted === "[已隐藏]") return null;
  return redacted.length <= MAX_PUBLIC_ERROR_MESSAGE_LENGTH
    ? redacted
    : `${redacted.slice(0, MAX_PUBLIC_ERROR_MESSAGE_LENGTH - 1)}…`;
};


const publicCallbackMessage = (value) => {
  const message = sanitizePublicErrorMessage(value);
  return message && !/(?:SQLSTATE|PostgREST|permission denied for (?:table|schema|relation|sequence|function)|relation .{0,120} does not exist|duplicate key value violates|violates .{0,120} constraint)/iu.test(message) ? message : null;
};
const MAX_CALLBACK_ERROR_BYTES = 8 * 1024;
const MACHINE_CODE = /^[A-Za-z][A-Za-z0-9_]{1,99}$/u;
const REQUEST_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const hideSecrets = (value, secrets) => secrets.filter((secret) => typeof secret === "string" && secret)
  .reduce((text, secret) => text.replaceAll(secret, "[已隐藏]"), value);
const safeCode = (value, secrets) => typeof value === "string" && MACHINE_CODE.test(value) && hideSecrets(value, secrets) === value ? value : null;
const safeRequestId = (value, secrets) => typeof value === "string" && REQUEST_ID.test(value) && hideSecrets(value, secrets) === value ? value : null;

export const parseCallbackError = (response, secrets = []) => {
  if (typeof response?.contentType !== "string" || !/^application\/json(?:\s*;|$)/iu.test(response.contentType) ||
      typeof response.body !== "string" || Buffer.byteLength(response.body, "utf8") > MAX_CALLBACK_ERROR_BYTES) return {};
  let envelope;
  try { envelope = JSON.parse(response.body); } catch { return {}; }
  if (!envelope || typeof envelope !== "object" || Array.isArray(envelope)) return {};
  const error = envelope.error && typeof envelope.error === "object" && !Array.isArray(envelope.error) ? envelope.error : envelope;
  let message = null;
  for (const candidate of [error.message, error.msg, typeof envelope.error === "string" ? envelope.error : null]) {
    if (typeof candidate !== "string") continue;
    const sanitized = publicCallbackMessage(hideSecrets(candidate, secrets));
    if (sanitized && !/^(?:secret|token|password|credential)$/iu.test(sanitized)) { message = sanitized; break; }
  }
  return {
    message,
    upstreamCode: safeCode(error.code, secrets),
    requestId: safeRequestId(error.request_id ?? envelope.request_id, secrets),
  };
};

// Local diagnostics only. External callback payloads and successful ACKs keep their exact schemas.
export const callbackErrorDiagnostics = (error, secrets = []) => ({
  ...(publicCallbackMessage(typeof error?.message === "string" ? hideSecrets(error.message, secrets) : null) ? { diagnostic_message: publicCallbackMessage(hideSecrets(error.message, secrets)) } : {}),
  ...(safeCode(error?.upstreamCode, secrets) ? { upstream_code: error.upstreamCode } : {}),
  ...(safeRequestId(error?.requestId, secrets) ? { request_id: error.requestId } : {}),
});

export const readCallbackErrorResponse = async (response) => {
  const contentType = response.headers?.get?.("content-type") ?? "";
  const length = Number(response.headers?.get?.("content-length"));
  if (Number.isFinite(length) && length > MAX_CALLBACK_ERROR_BYTES) {
    await response.body?.cancel?.();
    return { contentType, body: "" };
  }
  if (!response.body?.getReader) return { contentType, body: "" };
  const reader = response.body.getReader();
  const chunks = [];
  let bytes = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > MAX_CALLBACK_ERROR_BYTES) { await reader.cancel(); return { contentType, body: "" }; }
      chunks.push(Buffer.from(value));
    }
    return { contentType, body: Buffer.concat(chunks).toString("utf8") };
  } finally { reader.releaseLock(); }
};
