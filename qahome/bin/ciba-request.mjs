#!/usr/bin/env node
/**
 * 统一 SSO 认证 HTTP 请求脚本（零本地依赖）
 * 认证通过 @dp/sso-auth-cli（npx，无需安装）自动处理：OIDC → Token Exchange → CIBA
 *
 * 用法:
 *   node ciba-request.mjs <METHOD> --url <URL> --mis <MIS> --client-id <ID> [选项]
 *   node ciba-request.mjs GET  --url https://dpqe.sankuai.com/xxx --mis dongchu.tang
 *   node ciba-request.mjs POST --url https://coe.mws.sankuai.com/xxx --mis dongchu.tang  # mws 域名自动匹配
 */

// 跳过 SSL 验证（必须最早设置，覆盖所有子进程）
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

import { execSync } from "child_process";

// Node.js 版本检查
if (parseInt(process.versions.node) < 18) {
  console.error(`❌ 需要 Node.js 18+，当前版本: ${process.versions.node}`);
  process.exit(1);
}

// ── 内置站点配置（clientId 已知，无需调用方传入）────────────────────────────
// clientId 从对应站点 SSO 重定向 URL 的 client_id 参数中获取
// type "header" → access-token 请求头
// type "cookie" → Cookie: yun_portal_ssoid（mws 平台站点）
const BUILTIN_SITE_MAP = {
  "dpqe.sankuai.com":      { target: "04463f3f52", type: "header" },
  "gaodi.sankuai.com":     { target: "9b31356757", type: "header" },
  "coe.mws.sankuai.com":   { target: "ebcef721ab", type: "cookie" },
  "qahome.sankuai.com":    { target: "b399154e46", type: "header" },
};

function getSiteInfo(url, clientIdOverride) {
  try {
    const { hostname } = new URL(url);

    // 内置已知站点
    if (BUILTIN_SITE_MAP[hostname]) return BUILTIN_SITE_MAP[hostname];

    const isMws =
      hostname === "mws.sankuai.com" ||
      hostname.endsWith(".mws.sankuai.com") ||
      hostname === "mws.keetapp.com" ||
      hostname.endsWith(".mws.keetapp.com");

    // 未知站点：优先用 --client-id，否则报错
    const target = clientIdOverride ?? null;
    return { target, type: isMws ? "cookie" : "header" };
  } catch {
    return { target: clientIdOverride ?? null, type: "header" };
  }
}

// ── 通过 @dp/sso-auth-cli 获取 SSO token ─────────────────────────────────────
function getSsoToken(ssoTarget, mis) {
  const NPX = process.platform === "win32" ? "npx.cmd" : "npx";
  const misArgs = mis ? ` --mis ${mis}` : "";
  const cmd = `${NPX} --yes --registry=http://r.npm.sankuai.com @dp/sso-auth-cli@latest --cookie "${ssoTarget}"${misArgs}`;
  let output;
  try {
    output = execSync(cmd, { encoding: "utf8", shell: true });
  } catch (err) {
    throw new Error(`sso-auth-cli 执行失败: ${err.message}\n${err.stdout ?? ""}`);
  }
  const match = output.trim().match(/=\s*(AT_\S+)/);
  if (!match) throw new Error(`sso-auth-cli 未返回有效 token，原始输出：\n${output}`);
  return match[1];
}

// ── 带认证的 HTTP 请求 ────────────────────────────────────────────────────────
async function request(url, method, body, extraHeaders, mis, clientId) {
  const { target, type } = getSiteInfo(url, clientId);

  if (!target) {
    throw new Error(`未知站点，请通过 --client-id 传入 SSO clientId（从该站点 SSO 重定向 URL 的 client_id 参数获取）`);
  }

  // 仅使用 sso-auth-cli；认证优先级由其内部 authMode 缓存与调度控制
  const token = getSsoToken(target, mis);

  const authHeaders = type === "cookie"
    ? { Cookie: `yun_portal_ssoid=${token}` }
    : { "access-token": token };

  const headers = { ...authHeaders, ...extraHeaders };
  if (body && !headers["Content-Type"] && !headers["content-type"]) {
    headers["Content-Type"] = "application/json";
  }

  return fetch(url, { method, headers, ...(body ? { body } : {}) });
}

// ── 参数解析 ──────────────────────────────────────────────────────────────────
function parseArgs(argv) {
  const METHODS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE"]);
  const args = {
    method: null, url: null,
    mis: process.env.CIBA_MIS ?? null,
    clientId: null,
    body: null, headers: {}, help: false,
  };

  let i = 0;
  while (i < argv.length) {
    const a = argv[i];
    if (a === "--help" || a === "-h")        { args.help = true; }
    else if (a === "--mis")                  { args.mis = argv[++i]; }
    else if (a === "--url")                  { args.url = argv[++i]; }
    else if (a === "--client-id")            { args.clientId = argv[++i]; }
    else if (a === "--body" || a === "-d")   { args.body = argv[++i]; }
    else if (a === "--header" || a === "-H") {
      const h = argv[++i];
      const idx = h.indexOf(":");
      if (idx > 0) args.headers[h.slice(0, idx).trim()] = h.slice(idx + 1).trim();
    }
    else if (!a.startsWith("--") && METHODS.has(a.toUpperCase())) {
      args.method = a.toUpperCase();
    }
    i++;
  }
  return args;
}

function printHelp() {
  const builtinEntries = Object.entries(BUILTIN_SITE_MAP)
    .map(([host, { target, type }]) =>
      `  ${host.padEnd(28)} → ${target}  → ${type === "cookie" ? "Cookie: yun_portal_ssoid" : "access-token header"}`)
    .join("\n");

  console.log(`
统一 SSO 认证 HTTP 请求工具

用法:
  node ciba-request.mjs <METHOD> --url <URL> --mis <MIS> [选项]

参数:
  METHOD                     HTTP 方法 (GET/POST/PUT/PATCH/DELETE)

选项:
  --url <url>                请求 URL（必填）
  --mis <mis>                用户 MIS ID（也可通过 CIBA_MIS 环境变量）
  --client-id <id>           SSO clientId（未知站点必填；从目标站点 SSO 重定向 URL 的 client_id 参数获取）
  --body <json>              请求 Body（JSON 字符串）
  --header, -H <key:value>   附加请求头（可多次传入）
  --help                     显示帮助

认证策略（由 sso-auth-cli 内部 authMode 调度）:
  默认 OIDC → Token Exchange → CIBA；
  当 authMode 为 ciba / ciba-exchange 时优先走 CIBA

内置站点（无需 --client-id）:
${builtinEntries}

其他站点（需通过 --client-id 传入 SSO clientId）:
  node ciba-request.mjs GET --url https://xxx.sankuai.com/api --mis dongchu.tang --client-id <id>

示例:
  node ciba-request.mjs GET  --url https://dpqe.sankuai.com/api --mis dongchu.tang
  node ciba-request.mjs POST --url https://coe.mws.sankuai.com/api --mis dongchu.tang --body '{}'
  node ciba-request.mjs GET  --url https://dpqe.sankuai.com/api --mis dongchu.tang > /tmp/result.json
`.trim());
}

// ── 主入口 ────────────────────────────────────────────────────────────────────
async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (args.help)    { printHelp(); process.exit(0); }
  if (!args.method) { console.error("❌ 缺少 HTTP 方法（GET/POST/PUT/PATCH/DELETE）"); process.exit(1); }
  if (!args.url)    { console.error("❌ 缺少 --url 参数"); process.exit(1); }
  if (!args.mis)    { console.error("❌ 缺少 --mis 参数（或设置 CIBA_MIS 环境变量）"); process.exit(1); }

  try {
    const resp = await request(args.url, args.method, args.body, args.headers, args.mis, args.clientId);
    const text = await resp.text();
    try { console.log(JSON.stringify(JSON.parse(text), null, 2)); }
    catch { console.log(text); }
    if (!resp.ok) process.exit(1);
  } catch (err) {
    console.error(`❌ ${err.message}`);
    process.exit(1);
  }
}

main();

