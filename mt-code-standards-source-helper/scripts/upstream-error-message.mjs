// Only explicit error fields or individual error lines may cross the public-message boundary.
// Never serialize process output, response data, document content, SQL or stack traces.
export const MAX_PUBLIC_ERROR_MESSAGE_LENGTH = 600;
const FALLBACK_LINE = /(?:自动降级|降级到策略|fallback policy|falling back)/iu;
const ERROR_LINE = /(?:\berror\b|\bfailed\b|\bfailure\b|\bdenied\b|\bforbidden\b|\bunauthorized\b|\brequired\b|\b(?:ECONNRESET|ECONNREFUSED|ENETUNREACH|ENOTFOUND|EAI_AGAIN)\b|失败|错误|异常|拒绝|权限|请.{0,30}(?:重试|登录|认证|授权)|需要.{0,20}(?:认证|授权)|高密|安全屋)/iu;

export const sanitizePublicErrorMessage = (value) => {
  if (typeof value !== "string" || !value.trim() || value.length > 4096) return null;
  const message = value.replace(/\u001b\[[0-?]*[ -/]*[@-~]/gu, "").trim();
  // A multi-line error may contain a stack, HTTP headers or source text; reject it whole.
  if (/[\r\n\u0000-\u001f\u007f]|```|<\/?[A-Za-z][^>]*>|-----BEGIN|\b(?:SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+.+\s+SET|DELETE\s+FROM)\b|\bat\s+\S+\s*\([^)]*:\d+:\d+\)/iu.test(message)) return null;
  const redacted = message
    .replace(/AT_FOR_GW_BASE64_[A-Za-z0-9+/_=-]*/gu, "[已隐藏]")
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

const explicitMessage = (value, allowUnmarked = false) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  for (const candidate of [value.error?.message, value.error?.msg, typeof value.error === "string" ? value.error : null]) {
    const message = sanitizePublicErrorMessage(candidate);
    if (message) return message;
  }
  const successful = value.success === true || value.ok === true ||
    (Object.hasOwn(value, "code") && [0, "0", 200, "200", "OK", "SUCCESS"].includes(value.code));
  const failed = value.success === false || value.ok === false || Boolean(value.error) ||
    (Object.hasOwn(value, "code") && ![0, "0", 200, "200", "OK", "SUCCESS"].includes(value.code));
  if (!failed && (!allowUnmarked || successful)) return null;
  for (const candidate of [value.message, value.msg]) {
    const message = sanitizePublicErrorMessage(candidate);
    if (message) return message;
  }
  return null;
};

export const extractPublicErrorMessage = ({ stdout, stderr, error, status } = {}, { prefer = () => false } = {}) => {
  const messages = [];
  // Error-stream evidence takes precedence over a partially written successful response.
  for (const [index, output] of [stderr, stdout].entries()) {
    const text = String(output ?? "");
    if (text.length > 64 * 1024) continue;
    const lines = text.trim().split(/\r?\n/u);
    // Parse whole receipts and individual JSON error records, never nested response data.
    const candidates = [text, ...lines.filter((line) => line.trimStart().startsWith("{"))];
    for (const candidate of candidates) {
      try {
        const message = explicitMessage(JSON.parse(candidate), index === 0 || Number.isInteger(status) && status !== 0);
        if (message) messages.push(message);
      } catch { /* select only an explicit error line below */ }
    }
    for (const line of lines) {
      const trimmed = line.trim();
      // stdout can contain partial source text; only a marked CLI error is eligible.
      if (index === 1 && !/^(?:error\s*[:：]|REST\s+[^:：]{0,80}失败\s*[:：])/iu.test(trimmed)) continue;
      if (!ERROR_LINE.test(trimmed) || FALLBACK_LINE.test(trimmed) || /^(?:[#>*{\[]|\d+[.)]\s)/u.test(trimmed)) continue;
      const detail = trimmed.replace(/^(?:error\s*[:：]\s*|REST\s+[^:：]{0,80}失败\s*[:：]\s*)/iu, "");
      const message = sanitizePublicErrorMessage(detail);
      if (message) messages.push(message);
    }
  }
  const errorMessage = explicitMessage(error, true);
  if (errorMessage) messages.push(errorMessage);
  return messages.find(prefer) ?? messages[0] ?? null;
};
