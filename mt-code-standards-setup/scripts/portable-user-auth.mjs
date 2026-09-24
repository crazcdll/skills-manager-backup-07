#!/usr/bin/env node

import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { realpathSync } from "node:fs";
import { access, chmod, mkdtemp, readFile, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const execFileAsync = promisify(execFile);
const AUDIENCE = "923a237244";
const MINIMUM_SHARED_VERSION = "1.2.0";

class PortableAuthError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "PortableAuthError";
    this.code = code;
  }
}

const text = (value) => String(value ?? "").trim();
const versionParts = (value) => text(value).split("-", 1)[0].split(".").map((part) => Number(part));
const localRequire = createRequire(import.meta.url);

export const minimumVersionSatisfied = (actual, minimum = MINIMUM_SHARED_VERSION) => {
  const left = versionParts(actual);
  const right = versionParts(minimum);
  if (left.some((part) => !Number.isInteger(part)) || left.length < 3) return false;
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const difference = (left[index] || 0) - (right[index] || 0);
    if (difference !== 0) return difference > 0;
  }
  return !text(actual).includes("-") || text(minimum).includes("-");
};

export const resolveCurrentNodeNpmRoot = async (environment = process.env) => {
  const executableDirectory = path.dirname(process.execPath);
  const candidates = [
    path.resolve(executableDirectory, "..", "lib", "node_modules", "npm", "bin", "npm-cli.js"),
    path.resolve(executableDirectory, "node_modules", "npm", "bin", "npm-cli.js"),
  ];
  let npmCli = "";
  for (const candidate of candidates) {
    try {
      await access(candidate);
      npmCli = candidate;
      break;
    } catch {}
  }
  if (!npmCli) throw new Error("current Node npm CLI unavailable");
  const { stdout } = await execFileAsync(process.execPath, [npmCli, "root", "-g"], {
    encoding: "utf8",
    env: environment,
    timeout: 10_000,
    maxBuffer: 64 * 1024,
  });
  return text(stdout);
};

export const resolveLocalSharedAuth = async () => {
  let entry;
  try {
    entry = localRequire.resolve("@it/oa-skills-shared/auth");
  } catch (cause) {
    if (cause?.code === "MODULE_NOT_FOUND") return null;
    throw new PortableAuthError(
      "PORTABLE_AUTH_PROVIDER_REQUIRED",
      "无法解析本地 @it/oa-skills-shared/auth 入口。",
    );
  }
  let cursor = path.dirname(entry);
  while (true) {
    try {
      const packageJson = JSON.parse(await readFile(path.join(cursor, "package.json"), "utf8"));
      if (packageJson?.name === "@it/oa-skills-shared") {
        return { specifier: "@it/oa-skills-shared/auth", version: text(packageJson.version) };
      }
    } catch {}
    const parent = path.dirname(cursor);
    if (parent === cursor) break;
    cursor = parent;
  }
  throw new PortableAuthError(
    "PORTABLE_AUTH_PROVIDER_REQUIRED",
    "本地 @it/oa-skills-shared 缺少可验证的 package.json。",
  );
};

const loadSharedAuth = async ({ environment, npmRootResolver, moduleLoader, localSharedResolver }) => {
  const localShared = await localSharedResolver();
  if (localShared) {
    if (!minimumVersionSatisfied(localShared.version)) {
      throw new PortableAuthError(
        "PORTABLE_AUTH_PROVIDER_REQUIRED",
        `本地 @it/oa-skills-shared 版本过低（当前 ${localShared.version || "unknown"}，要求 >= ${MINIMUM_SHARED_VERSION}）。`,
      );
    }
    try {
      const authModule = await moduleLoader(localShared.specifier);
      if (typeof authModule?.initSsoAuth !== "function") throw new Error("initSsoAuth unavailable");
      return authModule.initSsoAuth;
    } catch {
      throw new PortableAuthError(
        "PORTABLE_AUTH_PROVIDER_REQUIRED",
        "本地 @it/oa-skills-shared 未提供可用的 initSsoAuth。",
      );
    }
  }
  let globalRoot;
  try {
    globalRoot = await npmRootResolver(environment);
  } catch {
    throw new PortableAuthError(
      "PORTABLE_AUTH_PROVIDER_REQUIRED",
      "无法定位当前 Node.js 的全局 npm 依赖；请安装或更新 @it/oa-skills。",
    );
  }
  if (!globalRoot) {
    throw new PortableAuthError(
      "PORTABLE_AUTH_PROVIDER_REQUIRED",
      "当前 Node.js 的全局 npm 依赖目录为空；请安装或更新 @it/oa-skills。",
    );
  }

  const sharedRoot = path.join(globalRoot, "@it", "oa-skills", "node_modules", "@it", "oa-skills-shared");
  let packageJson;
  try {
    packageJson = JSON.parse(await readFile(path.join(sharedRoot, "package.json"), "utf8"));
  } catch {
    throw new PortableAuthError(
      "PORTABLE_AUTH_PROVIDER_REQUIRED",
      "未找到 @it/oa-skills-shared；请安装或更新 @it/oa-skills（要求内置 shared >= 1.2.0）。",
    );
  }
  if (!minimumVersionSatisfied(packageJson.version)) {
    throw new PortableAuthError(
      "PORTABLE_AUTH_PROVIDER_REQUIRED",
      `@it/oa-skills-shared 版本过低（当前 ${text(packageJson.version) || "unknown"}，要求 >= ${MINIMUM_SHARED_VERSION}）。`,
    );
  }

  try {
    const moduleUrl = pathToFileURL(path.join(sharedRoot, "dist", "esm", "auth", "index.js")).href;
    const authModule = await moduleLoader(moduleUrl);
    if (typeof authModule?.initSsoAuth !== "function") throw new Error("initSsoAuth unavailable");
    return authModule.initSsoAuth;
  } catch {
    throw new PortableAuthError(
      "PORTABLE_AUTH_PROVIDER_REQUIRED",
      "@it/oa-skills-shared 未提供可用的 initSsoAuth；请更新 @it/oa-skills。",
    );
  }
};

const classifyProviderFailure = (cause) => {
  const raw = text(cause?.message || cause);
  if (/sub_access_denied|act_access_denied|sub_act_access_denied/iu.test(raw)) {
    return new PortableAuthError(
      "PORTABLE_AUTH_ACCESS_DENIED",
      "SSO/UAC 拒绝代理访问目标应用，请由用户或调用方管理员按官方授权指引处理。",
    );
  }
  if (/ric_feedback_required/iu.test(raw)) {
    return new PortableAuthError(
      "PORTABLE_AUTH_USER_ACTION_REQUIRED",
      "SSO 要求用户完成人工确认，请按大象中的官方指引操作后重试。",
    );
  }
  if (/reject|rejected|拒绝|cooldown|冷却/iu.test(raw)) {
    return new PortableAuthError(
      "PORTABLE_AUTH_REJECTED",
      "用户已拒绝 CIBA 授权或仍处于冷却期，请稍后重新发起。",
    );
  }
  if (/authorization_pending|CIBA 认证超时|等待确认|未在规定时间内确认/iu.test(raw)) {
    return new PortableAuthError(
      "PORTABLE_AUTH_CONFIRMATION_REQUIRED",
      "请在大象 App 完成 CIBA 授权确认后重新拉取规则。",
    );
  }
  return new PortableAuthError(
    "PORTABLE_AUTH_FAILED",
    "便携 SSO CIBA 未能取得用户票据；请检查网络和公司用户登录状态后重试。",
  );
};

export const getPortableUserToken = async ({
  mis,
  environment = process.env,
  npmRootResolver = resolveCurrentNodeNpmRoot,
  moduleLoader = (specifier) => import(specifier),
  localSharedResolver = resolveLocalSharedAuth,
  makeTemporaryDirectory = () => mkdtemp(path.join(os.tmpdir(), "mt-code-standards-auth-")),
  removeTemporaryDirectory = (directory) => rm(directory, { recursive: true, force: true }),
} = {}) => {
  const normalizedMis = text(mis || environment.SSO_USER_ID);
  if (!normalizedMis) {
    throw new PortableAuthError(
      "PORTABLE_AUTH_MIS_REQUIRED",
      "便携 SSO CIBA 需要当前公司用户 MIS；请通过 --mis 或 SSO_USER_ID 提供登录提示。",
    );
  }
  if (Number(process.versions.node.split(".")[0]) < 18) {
    throw new PortableAuthError("PORTABLE_AUTH_NODE_REQUIRED", "便携 SSO CIBA 要求 Node.js >= 18。");
  }

  const initSsoAuth = await loadSharedAuth({
    environment, npmRootResolver, moduleLoader, localSharedResolver,
  });
  const temporaryDirectory = await makeTemporaryDirectory();
  let provider;
  try {
    await chmod(temporaryDirectory, 0o700);
    provider = await initSsoAuth("mt-code-standards-setup", normalizedMis, {
      targetClientId: AUDIENCE,
      ssoStrategy: "sso-ciba",
      cacheFile: path.join(temporaryDirectory, "auth-cache.json"),
      command: "sync-effective-rules-with-sso",
    });
    const result = await provider.authenticate();
    const token = text(result?.token);
    if (!token) {
      throw new PortableAuthError("PORTABLE_AUTH_INVALID_RESPONSE", "便携 SSO CIBA 未返回可用用户票据。");
    }
    return token;
  } catch (cause) {
    if (cause instanceof PortableAuthError) throw cause;
    throw classifyProviderFailure(cause);
  } finally {
    try { provider?.clearCache?.(); } catch {}
    try {
      await removeTemporaryDirectory(temporaryDirectory);
    } catch {
      throw new PortableAuthError(
        "PORTABLE_AUTH_CLEANUP_FAILED",
        "便携认证临时缓存目录清理失败；为避免残留票据，本次认证结果已作废。",
      );
    }
  }
};

const parseArgs = (argv) => {
  let mis = "";
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] !== "--mis" || index + 1 >= argv.length) {
      throw new PortableAuthError("PORTABLE_AUTH_ARGUMENT_INVALID", "便携认证仅接受 --mis <MIS> 参数。");
    }
    mis = argv[index + 1];
    index += 1;
  }
  return { mis };
};

const main = async () => {
  try {
    const { mis } = parseArgs(process.argv.slice(2));
    const token = await getPortableUserToken({ mis });
    process.stdout.write(`${JSON.stringify({ token })}\n`);
  } catch (error) {
    const code = error instanceof PortableAuthError ? error.code : "PORTABLE_AUTH_UNEXPECTED";
    const message = error instanceof PortableAuthError ? error.message : "便携认证发生未预期错误。";
    process.stdout.write(`${JSON.stringify({ error: { code, message } })}\n`);
    process.exitCode = 2;
  }
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
  await main();
}
