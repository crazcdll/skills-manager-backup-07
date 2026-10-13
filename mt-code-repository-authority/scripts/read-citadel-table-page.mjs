import { realpath } from "node:fs/promises";
import { delimiter, dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const MIS = /^[a-z][a-z0-9._-]{0,63}$/u;
const SAFE_ERROR_CODES = new Set([
  "citadel_auth_required",
  "citadel_auth_rejected",
  "citadel_auth_timeout",
  "citadel_auth_expired",
  "citadel_auth_failed",
  "citadel_document_access_denied",
  "citadel_scan_timeout",
  "citadel_database_page_unavailable",
]);

const safeCitadelErrorCode = (error) => {
  const message = String(error instanceof Error ? error.message : error);
  if (SAFE_ERROR_CODES.has(message)) return message;
  if (/(?:MOA_USER_REJECTED|MOA_REJECT_COOLDOWN|(?:认证|授权).{0,30}(?:被?拒绝|冷却)|user.{0,20}rejected)/iu.test(message)) return "citadel_auth_rejected";
  if (/(?:expired_token|invalid_grant|token.{0,20}expired|auth(?:entication|orization)?.{0,30}expired|(?:认证|授权|令牌).{0,30}过期)/iu.test(message)) return "citadel_auth_expired";
  if (/(?:MOA_AUTH_TIMEOUT|AUTHORIZATION_TIMEOUT|auth(?:entication|orization)?.{0,30}timed?\s*out|(?:认证|授权)(?:请求|等待)?(?:已)?超时|等待.{0,20}(?:认证|授权|大象).{0,20}(?:已)?超时)/iu.test(message)) return "citadel_auth_timeout";
  if (/(?:403|forbidden|permission denied|access denied|没有.{0,12}(?:查看|阅读|访问)?.{0,12}权限|无.{0,12}(?:查看|阅读|访问)?.{0,12}权限|权限不足)/iu.test(message)) return "citadel_document_access_denied";
  if (/(?:access_denied|sub_access_denied|act_access_denied|sub_act_access_denied|401.{0,20}unauthorized|unauthorized|auth(?:entication|orization)?.{0,60}(?:failed|denied)|(?:认证|授权).{0,30}失败)/iu.test(message)) return "citadel_auth_failed";
  if (/(?:ETIMEDOUT|ECONNABORTED|request.{0,20}timed?\s*out|请求.{0,12}超时)/iu.test(message)) return "citadel_scan_timeout";
  if (/(?:MOA_NOT_LOGGED_IN|MOA_AUTH_REQUEST_PENDING|ric_feedback_required|authorization_pending|slow_down|auth(?:entication|orization)?.{0,60}required|需要.{0,12}(?:认证|授权)|请.{0,12}(?:认证|授权)|前往大象.{0,20}(?:确认|授权))/iu.test(message)) return "citadel_auth_required";
  return "citadel_database_page_unavailable";
};

export const readCitadelTablePage = async ({ tableId, columnIds, pageToken, actorMis, Client }) => {
  if (!/^\d{3,30}$/u.test(tableId) || !Number.isSafeInteger(Number(tableId)) || !Array.isArray(columnIds) || !columnIds.length || columnIds.some((id) => !/^\d{1,30}$/u.test(String(id)))) throw new Error("invalid table page parameters");
  if (!MIS.test(String(actorMis ?? ""))) throw new Error("invalid Citadel actor");
  const client = new Client({ skillName: "citadel-database", ssoStrategy: "sso-ciba", oidcFallback: false });
  if (typeof client.queryTableDataSinglePage !== "function") throw new Error("official Citadel single-page capability unavailable");
  try { await client.ensureAuth(actorMis); }
  catch (error) {
    const code = safeCitadelErrorCode(error);
    throw new Error(code === "citadel_database_page_unavailable" ? "citadel_auth_failed" : code);
  }
  // The CLI's automatic pagination writes rows to a file and can hide page errors.
  const result = await client.queryTableDataSinglePage({ tableId: Number(tableId), columnIds, pageSize: 100, pageToken: pageToken || undefined });
  if (!result || !Array.isArray(result.rows)) throw new Error("invalid official Citadel page result");
  return result;
};

const loadOfficialClient = async () => {
  for (const directory of (process.env.PATH || "").split(delimiter)) {
    if (!directory) continue;
    let entry;
    try { entry = await realpath(join(directory, "oa-skills")); } catch { continue; }
    const module = await import(pathToFileURL(join(dirname(entry), "citadel-database", "client.js")).href);
    if (typeof module.XTableClient !== "function") throw new Error("official Citadel client unavailable");
    return module.XTableClient;
  }
  throw new Error("oa-skills runtime unavailable");
};

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const [tableId, columns, pageToken, actorMis, ...extra] = process.argv.slice(2);
    if (!tableId || !columns || !actorMis || extra.length) throw new Error("invalid arguments");
    console.log = console.info = console.warn = console.error = () => {};
    const result = await readCitadelTablePage({ tableId, columnIds: JSON.parse(columns), pageToken, actorMis, Client: await loadOfficialClient() });
    process.stdout.write(`${JSON.stringify(result)}\n`);
  } catch (error) {
    process.stderr.write(`${safeCitadelErrorCode(error)}\n`);
    process.exitCode = 1;
  }
}
