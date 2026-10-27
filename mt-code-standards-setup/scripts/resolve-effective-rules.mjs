#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { realpathSync } from "node:fs";
import {
  access,
  cp,
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rmdir,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { isIP } from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AGENTS_INDEX_CONTRACT, validateAgentsIndexes, renderAgentsIndexes, agentsManifestFields, validateAgentsManifest, agentsIndexDestinations } from "./agents-index.mjs";

const DEFAULT_GATEWAY =
  "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-distribution";
const GATEWAY_HOSTNAME = "db0y7dgg85gphojyva.database.sankuai.com";
const GATEWAY_PATHNAME = "/functions/v1/rule-distribution";
const LEGACY_GATEWAY_PATHNAME = "/functions/v1/rule-observability";
const LEGACY_BUNDLE_SCHEMA = "effective-rule-bundle/v1";
const BUNDLE_SCHEMA = "effective-rule-bundle/v2";
const STAGED_BUNDLE_SCHEMA = "effective-rule-bundle/v3";
const LAYOUT_BUNDLE_SCHEMA = "effective-rule-bundle/v4";
export const LOCAL_LAYOUT = "scope-domain-ruleset/v1";
const LEGACY_LAYOUT_LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v5";
const PREVIOUS_LAYOUT_LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v6";
const LAYOUT_LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v7";
const LAYOUT_BOOTSTRAP_BUNDLE_SCHEMA = "l1-bootstrap-bundle/v3";
const LEGACY_LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA = "mt-l1-bootstrap-manifest/v3";
const LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA = "mt-l1-bootstrap-manifest/v4";
const LEGACY_LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v1";
const LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v2";
const LEGACY_FLAT_LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v3";
const FLAT_LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v4";
const LEGACY_AGENTS_LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v5";
const AGENTS_LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v6";
const AGENTS_BOOTSTRAP_MANIFEST_SCHEMA = "mt-l1-bootstrap-manifest/v3";
const FLAT_LOCAL_LAYOUT = "company-team/v1";
const RECEIPT_SCHEMA = "mt-effective-rule-bundle-install/v1";
const MANIFEST_NAME = ".mt-effective-rule-bundle.json";
const BOOTSTRAP_BUNDLE_SCHEMA = "l1-bootstrap-bundle/v1";
const STAGED_BOOTSTRAP_BUNDLE_SCHEMA = "l1-bootstrap-bundle/v2";
const LEGACY_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA = "mt-l1-bootstrap-manifest/v1";
const BOOTSTRAP_LOCAL_MANIFEST_SCHEMA = "mt-l1-bootstrap-manifest/v2";
const BOOTSTRAP_RECEIPT_SCHEMA = "mt-l1-bootstrap-install/v1";
const BOOTSTRAP_MANIFEST_NAME = ".mt-l1-bootstrap.json";
const MAX_LOCATOR_BYTES = 8 * 1024;
export const MAX_RESPONSE_BYTES = 4 * 1024 * 1024;
export const MAX_AGENTS_INDEX_RESPONSE_BYTES = 64 * 1024 * 1024;
const MAX_FILE_BYTES = 512 * 1024;
const SHA256_PATTERN = /^[a-f0-9]{64}$/;
const DOMAINS = new Set(["frontend", "backend"]);
const DELIVERY_STAGES = new Set(["design", "coding", "cr"]);
export const EXECUTION_AGENTS = new Set([
  "catdesk", "catpaw", "claude", "codex", "agent_1024", "sandbox", "catx", "cli", "unknown",
]);
const EXECUTION_AGENT_SOURCES = new Set([
  "runner_explicit_v1", "runner_heuristic_v1", "legacy_unknown_v1",
]);
const EXECUTION_SKILL_NAMES = new Set(["mt-code-standards", "mt-code-standards-setup"]);
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const RULE_SET_NAME_PATTERN = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;
const CANONICAL_L2_RULE_SET_ID_PATTERN =
  /^rs-[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const PORTABLE_RESERVED_SEGMENT_PATTERN = /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$/;
const pathKey = (value) => value.normalize("NFC").toUpperCase().toLowerCase().normalize("NFC");
const binaryPathOrder = (left, right) => left < right ? -1 : left > right ? 1 : 0;

export class RuleBundleError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "RuleBundleError";
    this.code = code;
    for (const key of ["issues", "request_id", "retryable"]) {
      if (details[key] !== undefined) this[key] = details[key];
    }
  }
}

const text = (value) => String(value ?? "").trim();
const isObject = (value) => Boolean(value) && typeof value === "object" && !Array.isArray(value);

export const sha256Hex = (value) => createHash("sha256").update(value).digest("hex");

export const canonicalJson = (value) => {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  return `{${Object.keys(value).sort().map((key) => (
    `${JSON.stringify(key)}:${canonicalJson(value[key])}`
  )).join(",")}}`;
};

const fail = (code, message) => {
  throw new RuleBundleError(code, message);
};

const normalizeDeliveryStage = (value) => {
  if (value == null) return "";
  const stage = text(value);
  if (!stage) {
    fail("RULE_BUNDLE_STAGE_INVALID", "--stage 仅支持 design、coding 或 cr");
  }
  if (!DELIVERY_STAGES.has(stage)) {
    fail("RULE_BUNDLE_STAGE_INVALID", "--stage 仅支持 design、coding 或 cr");
  }
  return stage;
};

const exists = async (target) => {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
};

const locatorMainPart = (value) => {
  const source = text(value);
  if (!source || Buffer.byteLength(source, "utf8") > MAX_LOCATOR_BYTES || /[\s\u0000-\u001f\u007f-\u009f]/u.test(source)) {
    fail("RULE_BUNDLE_REPOSITORY_INVALID", "仓库地址为空、过长或包含非法字符");
  }
  const suffixIndex = source.search(/[?#]/);
  return suffixIndex < 0 ? source : source.slice(0, suffixIndex);
};

const validRepositoryHost = (hostname) => {
  const unwrapped = hostname.startsWith("[") && hostname.endsWith("]") ? hostname.slice(1, -1) : hostname;
  return Boolean(isIP(unwrapped))
    || /^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:[.][A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$/u.test(hostname);
};

/**
 * Validate only the supported locator shapes. Repository identity is resolved
 * by the platform, so the original value (including query/hash) is preserved.
 */
export const validateRepositoryLocator = (value) => {
  const main = locatorMainPart(value);
  const source = text(value);
  if (/(?:^|[/:])[.]{1,2}(?:[/]|$)/.test(main) || /%(?:2e|2f|5c)/iu.test(main)) {
    fail("RULE_BUNDLE_REPOSITORY_INVALID", "仓库地址不能包含相对路径片段");
  }
  const atom = "[A-Za-z0-9._~-]+";
  const repository = "[A-Za-z0-9._-]+";
  const shorthand = new RegExp(`^(?:${atom}/${repository}|${repository})$`);
  const scp = main.match(/^git@([A-Za-z0-9.-]+):([^\s]+)$/u);
  let valid = shorthand.test(main);
  if (scp) {
    valid = validRepositoryHost(scp[1])
      && /^(?=.*[A-Za-z0-9])\/?[^\s?#:]+(?:\/[^\s?#:]+)*\/?$/u.test(scp[2]);
  } else if (/^[A-Za-z][A-Za-z0-9+.-]*:\/\//u.test(main)) {
    try {
      const url = new URL(main);
      const hasRepositoryPath = url.pathname.split("/").some((part) => part && part !== "." && part !== "..");
      if (url.protocol === "http:" || url.protocol === "https:") {
        const hostname = url.hostname.toLowerCase();
        valid = (hostname === "sankuai.com" || hostname.endsWith(".sankuai.com"))
          && !url.username && !url.password && (!url.port || Number(url.port) > 0) && hasRepositoryPath;
      } else if (url.protocol === "ssh:") {
        valid = url.username === "git" && !url.password && validRepositoryHost(url.hostname)
          && (!url.port || Number(url.port) > 0) && hasRepositoryPath;
      }
    } catch {
      valid = false;
    }
  }
  if (!valid) {
    fail(
      "RULE_BUNDLE_REPOSITORY_INVALID",
      "仓库仅支持 sankuai.com 的 HTTP(S)、合法 ssh://git@... 或 git@host:path 地址；兼容 namespace/repository 和唯一仓库名",
    );
  }
  return source;
};

export const canonicalRepositoryKey = (value) => {
  const source = validateRepositoryLocator(value);
  const main = locatorMainPart(source).replace(/\/$/u, "");
  const patterns = [
    /^git@(?:git[.]sankuai[.]com|git[.]dianpingoa[.]com):([^/]+)\/([^/]+?)(?:[.]git)?$/iu,
    /^https?:\/\/dev[.]sankuai[.]com\/code\/repo-detail\/([^/]+)\/([^/]+?)(?:\/file\/list)?$/iu,
    /^ssh:\/\/git@(?:git[.]sankuai[.]com|git[.]dianpingoa[.]com)\/([^/]+)\/([^/]+?)(?:[.]git)?$/iu,
    /^([^/:]+)\/([^/]+)$/u,
  ];
  for (const pattern of patterns) {
    const match = main.match(pattern);
    if (match) return `${match[1].toLowerCase()}/${match[2].replace(/[.]git$/iu, "").toLowerCase()}`;
  }
  return "";
};

const safeEvidencePaths = (paths) => [...new Set(paths)].sort(binaryPathOrder).slice(0, 5);

export const detectRepositoryDomain = async (repoRoot) => {
  let tracked;
  try {
    tracked = execFileSync("git", ["ls-files", "-z", "--cached"], {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
      maxBuffer: 4 * 1024 * 1024,
    }).split("\0").filter(Boolean);
  } catch {
    fail("RULE_BUNDLE_DOMAIN_EVIDENCE_UNAVAILABLE", "无法读取 Git 已跟踪文件，不能安全判断仓库领域");
  }
  const safeTracked = tracked.filter((file) => (
    !path.posix.isAbsolute(file) && !file.includes("\\") &&
    !file.split("/").some((part) => !part || part === "." || part === "..") &&
    !/[\p{Cc}\p{Cf}]/u.test(file)
  ));
  const frontendSources = safeTracked.filter((file) => /[.](?:tsx|jsx|vue)$/iu.test(file));
  const packageFiles = safeTracked.filter((file) => /(?:^|\/)package[.]json$/u.test(file));
  const frontendPackages = [];
  const frontendMarkers = new Set([
    "react", "react-dom", "react-native", "vue", "@vue/runtime-dom", "next", "nuxt",
    "vite", "webpack", "@tarojs/taro", "@dcloudio/uni-app",
  ]);
  for (const packageFile of packageFiles.slice(0, 50)) {
    try {
      const packagePath = path.join(repoRoot, ...packageFile.split("/"));
      const info = await lstat(packagePath);
      if (!info.isFile() || info.isSymbolicLink()) continue;
      const raw = await readFile(packagePath, "utf8");
      if (Buffer.byteLength(raw, "utf8") > 1024 * 1024) continue;
      const parsed = JSON.parse(raw);
      const dependencies = { ...parsed?.dependencies, ...parsed?.devDependencies };
      const markers = Object.keys(dependencies).filter((name) => frontendMarkers.has(name)).sort();
      if (markers.length) frontendPackages.push({ path: packageFile, markers: markers.slice(0, 5) });
    } catch {
      // Invalid package metadata is not positive domain evidence.
    }
  }
  const backendDescriptors = safeTracked.filter((file) => (
    /(?:^|\/)pom[.]xml$/u.test(file) ||
    /(?:^|\/)(?:build|settings)[.]gradle(?:[.]kts)?$/u.test(file)
  ));
  const backendSources = safeTracked.filter((file) => /[.]java$/iu.test(file));
  const frontend = frontendSources.length > 0 || frontendPackages.length > 0;
  const backend = backendDescriptors.length > 0 && backendSources.length > 0;
  const evidence = {
    tracked_file_count: safeTracked.length,
    frontend: {
      source_files: safeEvidencePaths(frontendSources),
      package_manifests: frontendPackages.slice(0, 5),
    },
    backend: {
      build_files: safeEvidencePaths(backendDescriptors),
      source_files: safeEvidencePaths(backendSources),
    },
  };
  return {
    classification: frontend && backend ? "mixed" : frontend ? "frontend" : backend ? "backend" : "unknown",
    evidence,
  };
};

export const repositoryLocatorFromGit = (repoRoot = process.cwd()) => {
  try {
    return execFileSync("git", ["remote", "get-url", "origin"], {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
};

export const repositoryRootFromGit = (sourceDirectory = process.cwd()) => {
  try {
    return execFileSync("git", ["rev-parse", "--show-toplevel"], {
      cwd: sourceDirectory,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
};

const MIS_PATTERN = /^[a-z][a-z0-9._-]{0,63}$/iu;

/**
 * Read only the repository-local Git MIS hint. This is never an identity or
 * authorization fact; the server still derives the actor from the SSO ticket.
 */
export const readLocalGitMis = (repoRoot = "") => {
  const sourceDirectory = text(repoRoot) || process.cwd();
  const gitRoot = repositoryRootFromGit(sourceDirectory);
  if (!gitRoot) return "";
  try {
    const value = execFileSync("git", ["config", "--local", "--get", "user.mis"], {
      cwd: gitRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim().toLowerCase();
    return MIS_PATTERN.test(value) ? value : "";
  } catch {
    return "";
  }
};

const friendlyServiceError = (code, message) => {
  const normalized = text(code).toLowerCase();
  if (normalized.includes("ambiguous") || normalized === "42702") {
    return "仓库名匹配到多个已登记仓库，请提供 namespace/repository、HTTPS 或 SSH 地址后重试";
  }
  if (
    normalized.includes("not_registered")
    || normalized.includes("not_found")
    || normalized === "p0002"
  ) {
    return "没有找到已登记的仓库，禁止下载规则；请先在规范平台登记仓库，或提供另一个已登记仓库";
  }
  if (normalized.includes("user_login_unverified")) {
    return "当前账号尚未登录业务研发平台完成组织核验，请先访问并登录：https://quality-gate.nocode.sankuai.com/";
  }
  if (normalized.includes("forbidden") || normalized.includes("not_associated")) {
    return "当前用户所属组织未关联该仓库，禁止下载规则；请先完成组织与仓库关联";
  }
  return text(message) || "规则包服务调用失败";
};

export const validateGatewayUrl = (value) => {
  let url;
  try {
    url = new URL(value);
  } catch {
    fail("RULE_BUNDLE_GATEWAY_INVALID", "规则包网关地址非法");
  }
  const pathname = url.pathname.replace(/\/$/, "");
  if (
    url.protocol !== "https:"
    || url.hostname !== GATEWAY_HOSTNAME
    || !new Set([GATEWAY_PATHNAME, LEGACY_GATEWAY_PATHNAME]).has(pathname)
    || (url.port && url.port !== "443")
    || url.username
    || url.password
    || url.search
    || url.hash
  ) {
    fail("RULE_BUNDLE_GATEWAY_INVALID", "规则包只允许调用受信任的业务研发平台网关");
  }
  return `${url.origin}${pathname}`;
};

const canonicalizeOutputRoot = async (target) => {
  let cursor = path.resolve(target);
  const missing = [];
  while (!await exists(cursor)) {
    missing.unshift(path.basename(cursor));
    const parent = path.dirname(cursor);
    if (parent === cursor) fail("RULE_BUNDLE_OUTPUT_INVALID", "无法定位输出目录的现有父目录");
    cursor = parent;
  }
  const canonicalParent = realpathSync(cursor);
  return path.join(canonicalParent, ...missing);
};

export const prepareSyncRequest = async ({
  gatewayUrl = DEFAULT_GATEWAY,
  repositoryLocator = "",
  repoRoot = "",
  outputDir = "",
  cwd = process.cwd(),
  domain = "",
  bootstrap = false,
  stage,
  execution,
} = {}) => {
  const workingDirectory = path.resolve(cwd);
  const explicitRepoRoot = text(repoRoot);
  const explicitOutputDir = text(outputDir);
  const sourceDirectory = explicitRepoRoot
    ? path.resolve(workingDirectory, explicitRepoRoot)
    : workingDirectory;
  const targetRoot = await canonicalizeOutputRoot(
    explicitOutputDir
      ? path.resolve(workingDirectory, explicitOutputDir)
      : sourceDirectory,
  );
  const explicitLocator = text(repositoryLocator);
  let gitRoot = "";
  let locator = explicitLocator;
  if (!locator || bootstrap) gitRoot = repositoryRootFromGit(sourceDirectory);
  if (!locator) {
    if (!gitRoot) {
      fail(
        "RULE_BUNDLE_REPOSITORY_REQUIRED",
        "当前目录不在 Git 仓库中，请使用 --repository 提供唯一仓库名、namespace/repository 或仓库地址",
      );
    }
    locator = repositoryLocatorFromGit(gitRoot);
    if (!locator) {
      fail("RULE_BUNDLE_REPOSITORY_REQUIRED", "Git 仓库没有 origin，请使用 --repository 明确指定仓库");
    }
  }
  const normalizedLocator = validateRepositoryLocator(locator);
  const normalizedDomain = text(domain);
  if (normalizedDomain && !DOMAINS.has(normalizedDomain)) {
    fail("RULE_BUNDLE_DOMAIN_INVALID", "--domain 仅支持 frontend 或 backend");
  }
  const normalizedStage = normalizeDeliveryStage(stage);
  if (bootstrap && !canonicalRepositoryKey(normalizedLocator)) {
    fail(
      "RULE_BUNDLE_BOOTSTRAP_CANONICAL_REQUIRED",
      "L1 bootstrap 必须提供精确 namespace/repository 或可归一化为该形式的 Git URL，不能使用裸仓库名",
    );
  }
  if (bootstrap && !normalizedDomain && !gitRoot) {
    fail(
      "RULE_BUNDLE_DOMAIN_CONFIRMATION_REQUIRED",
      "非 Git 目录执行 L1 bootstrap 时必须使用 --domain frontend|backend 明确仓库领域",
    );
  }
  const normalizedGateway = validateGatewayUrl(gatewayUrl);
  if (bootstrap && new URL(normalizedGateway).pathname === LEGACY_GATEWAY_PATHNAME) {
    fail(
      "RULE_BUNDLE_BOOTSTRAP_GATEWAY_UNSUPPORTED",
      "旧 rule-observability 网关不支持免 SSO 的 L1 引导安装；请移除 --gateway-url 使用默认 rule-distribution 网关，或将受信任网关路径改为 /functions/v1/rule-distribution。",
    );
  }
  return Object.freeze({
    gatewayUrl: normalizedGateway,
    repositoryLocator: normalizedLocator,
    sourceRoot: gitRoot || sourceDirectory,
    targetRoot,
    domain: normalizedDomain,
    stage: normalizedStage,
    bootstrap: Boolean(bootstrap),
    execution: normalizePullExecution(execution),
  });
};

export const normalizePullExecution = (value = {}) => {
  const pullId = text(value.pullId) || randomUUID();
  const agent = text(value.agent) || "unknown";
  const source = text(value.source) || "legacy_unknown_v1";
  const skillName = text(value.skillName) || "mt-code-standards";
  const skillVersion = text(value.skillVersion) || null;
  if (!UUID_PATTERN.test(pullId) || !EXECUTION_AGENTS.has(agent)
    || !EXECUTION_AGENT_SOURCES.has(source)
    || !EXECUTION_SKILL_NAMES.has(skillName)
    || (skillVersion && (skillVersion.length > 128 || /[\p{Cc}]/u.test(skillVersion)))) {
    fail("RULE_BUNDLE_EXECUTION_INVALID", "拉取执行环境信息不合法");
  }
  return Object.freeze({ pullId, agent, source, skillName, skillVersion });
};

// Index attachments have an independent budget; negotiating them never enlarges
// the existing rule/body budget. Validate integrity separately before any write.
export const assertRuleResponseBudget = (body, { allowAgentsIndexes = false, serviceLabel = "规则包服务" } = {}) => {
  const totalLimit = allowAgentsIndexes ? MAX_AGENTS_INDEX_RESPONSE_BYTES : MAX_RESPONSE_BYTES;
  if (Buffer.byteLength(JSON.stringify(body), "utf8") > totalLimit) {
    fail("RULE_BUNDLE_RESPONSE_TOO_LARGE", `${serviceLabel}响应超过 ${totalLimit / 1024 / 1024} MiB 安全上限`);
  }
  const withIndexes = allowAgentsIndexes && isObject(body) && Array.isArray(body.agents_indexes);
  let baseBody = withIndexes ? Object.fromEntries(Object.entries(body).filter(([key]) => key !== "agents_indexes")) : body;
  if (allowAgentsIndexes && body?.schema_version === "rule-bundle-resolution/v1" && isObject(body.bundle)) {
    assertRuleResponseBudget(body.bundle, { allowAgentsIndexes: true, serviceLabel });
    baseBody = { ...body, bundle: Object.fromEntries(Object.entries(body.bundle).filter(([key]) => key !== "agents_indexes")) };
  }
  if (Buffer.byteLength(JSON.stringify(baseBody), "utf8") > MAX_RESPONSE_BYTES) {
    fail("RULE_BUNDLE_RESPONSE_TOO_LARGE", `${serviceLabel}非索引响应超过 4 MiB 安全上限`);
  }
};

const serviceRequest = async ({
  gatewayUrl,
  token,
  resourcePath,
  body,
  fetchImpl,
  requestTransport,
  serviceLabel,
  publicRequest = false,
}) => {
  const trustedGateway = validateGatewayUrl(gatewayUrl);
  const allowAgentsIndexes = body?.agents_index_contract === AGENTS_INDEX_CONTRACT;
  const maxResponseBytes = allowAgentsIndexes ? MAX_AGENTS_INDEX_RESPONSE_BYTES : MAX_RESPONSE_BYTES;
  const request = Object.freeze({
    gatewayUrl: trustedGateway,
    resourcePath,
    url: `${trustedGateway}${resourcePath}`,
    method: "POST",
    headers: Object.freeze({
      "Content-Type": "application/json",
      ...(publicRequest ? {} : { "X-Rule-Auth-Source": "nocode-agent-sso" }),
      "X-Rule-Protocol-Version": "1.0",
    }),
    body,
    maxResponseBytes,
  });
  if (requestTransport) {
    let result;
    try {
      result = await requestTransport(request);
    } catch (error) {
      if (error instanceof RuleBundleError) throw error;
      fail("RULE_BUNDLE_NETWORK_FAILED", `${serviceLabel}不可用：${error.message}`);
    }
    const status = Number(result?.status);
    if (!Number.isInteger(status) || status < 100 || status > 599 || !("body" in (result || {}))) {
      fail("RULE_BUNDLE_RESPONSE_INVALID", `${serviceLabel} transport 返回了非法响应`);
    }
    let encoded;
    try {
      encoded = JSON.stringify(result.body);
    } catch {
      fail("RULE_BUNDLE_RESPONSE_NOT_JSON", `${serviceLabel}返回了非 JSON 内容`);
    }
    if (Buffer.byteLength(encoded, "utf8") > maxResponseBytes) {
      fail("RULE_BUNDLE_RESPONSE_TOO_LARGE", `${serviceLabel}响应超过 ${maxResponseBytes / 1024 / 1024} MiB 安全上限`);
    }
    assertRuleResponseBudget(result.body, { allowAgentsIndexes, serviceLabel });
    return { status, ok: status >= 200 && status < 300, body: result.body };
  }
  let response;
  try {
    response = await fetchImpl(request.url, {
      method: request.method,
      redirect: "error",
      headers: publicRequest ? request.headers : {
        ...request.headers,
        "Authorization": `Bearer ${token}`,
      },
      body: JSON.stringify(request.body),
    });
  } catch (error) {
    fail("RULE_BUNDLE_NETWORK_FAILED", `${serviceLabel}不可用：${error.message}`);
  }
  const rawBody = await response.text().catch(() => "");
  if (Buffer.byteLength(rawBody, "utf8") > maxResponseBytes) {
    fail("RULE_BUNDLE_RESPONSE_TOO_LARGE", `${serviceLabel}响应超过 ${maxResponseBytes / 1024 / 1024} MiB 安全上限`);
  }
  let parsed = {};
  try {
    parsed = rawBody ? JSON.parse(rawBody) : {};
  } catch {
    fail("RULE_BUNDLE_RESPONSE_NOT_JSON", `${serviceLabel}返回了非 JSON 内容`);
  }
  assertRuleResponseBudget(parsed, { allowAgentsIndexes, serviceLabel });
  return { status: response.status, ok: response.ok, body: parsed };
};

const requestBundle = async ({
  gatewayUrl, token, repositoryLocator, knownSnapshotId, stage, execution, fetchImpl, requestTransport,
  publicRequest = false,
}) => {
  const result = await serviceRequest({
    gatewayUrl,
    token,
    resourcePath: publicRequest
      ? "/v1/public/effective-rule-bundles/resolve"
      : "/v1/effective-rule-bundles/resolve",
    body: {
      repository_locator: repositoryLocator,
      bundle_contract: LOCAL_LAYOUT,
      agents_index_contract: AGENTS_INDEX_CONTRACT,
      ...(stage ? { stage } : {}),
      ...(knownSnapshotId ? { known_snapshot_id: knownSnapshotId } : {}),
      execution: {
        pull_id: execution.pullId,
        execution_agent: execution.agent,
        execution_agent_source: execution.source,
        skill_name: execution.skillName,
        skill_version: execution.skillVersion,
      },
    },
    fetchImpl,
    requestTransport,
    serviceLabel: "规则包服务",
    publicRequest,
  });
  if (!result.ok) {
    const code = result.body?.error?.code || `RULE_BUNDLE_HTTP_${result.status}`;
    fail(code, friendlyServiceError(code, result.body?.error?.message));
  }
  return result.body;
};

const requestBootstrapBundle = async ({
  gatewayUrl, canonicalKey, standardDomain, knownSnapshotId, stage, mis, execution, fetchImpl, requestTransport,
}) => {
  const result = await serviceRequest({
    gatewayUrl,
    publicRequest: true,
    resourcePath: "/v1/public/l1-rule-bundles/bootstrap",
    body: {
        repository_locator: canonicalKey,
        bundle_contract: LOCAL_LAYOUT,
        agents_index_contract: AGENTS_INDEX_CONTRACT,
        standard_domain: standardDomain,
        mis,
        execution: {
          pull_id: execution.pullId,
          execution_agent: execution.agent,
          execution_agent_source: execution.source,
          skill_name: execution.skillName,
          skill_version: execution.skillVersion,
        },
        ...(stage ? { stage } : {}),
        ...(knownSnapshotId ? { known_snapshot_id: knownSnapshotId } : {}),
    },
    fetchImpl,
    requestTransport,
    serviceLabel: "L1 bootstrap 服务",
  });
  if (!result.ok) {
    const code = result.body?.error?.code || `RULE_BUNDLE_HTTP_${result.status}`;
    const message = code === "repository_registered_or_unavailable"
      ? "仓库已登记或当前不可用，禁止使用 L1 bootstrap；请处理仓库关联、权限或登记状态后重试正式规则包"
      : text(result.body?.error?.message) || "L1 bootstrap 服务调用失败";
    fail(code, message);
  }
  return result.body;
};

const normalizeRelativePath = (value, versionTwo = true) => {
  const relativePath = text(value);
  if (
    !relativePath
    || relativePath.length > 240
    || (versionTwo && Buffer.byteLength(relativePath, "utf8") > 240)
    || /[\p{Cc}\p{Cf}\uD800-\uDFFF]/u.test(relativePath)
    || relativePath.includes("\\")
    || path.posix.isAbsolute(relativePath)
    || !/[.]md$/iu.test(relativePath)
  ) {
    fail("RULE_BUNDLE_FILE_PATH_INVALID", `规则文件路径非法：${relativePath || "<empty>"}`);
  }
  const segments = relativePath.split("/");
  if (segments.some((segment) => !segment || segment === "." || segment === ".." || segment.startsWith(".")
      || /[<>:"|?*]/u.test(segment) || /[. ]$/u.test(segment)
      || (versionTwo && /^(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:[.]|$)/iu.test(segment))
      || (versionTwo && Buffer.byteLength(segment, "utf8") > 200))) {
    fail("RULE_BUNDLE_FILE_PATH_INVALID", `规则文件路径非法：${relativePath}`);
  }
  return relativePath;
};

const normalizeLocalRuleSetName = (value) => {
  if (typeof value !== "string" || !value || value !== value.trim() || value !== value.normalize("NFC")
    || value.startsWith(".") || /[\/\\<>:"|?*\p{Cc}\p{Cf}\uD800-\uDFFF]/u.test(value) || /[. ]$/u.test(value)
    || /^(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:[.]|$)/iu.test(value)
    || Buffer.byteLength(value, "utf8") > 200) {
    fail("RULE_BUNDLE_RULE_SET_NAME_INVALID", "规则集名称缺失或不能安全作为目录名，请联系规则集维护者修正规则集名称");
  }
  return value;
};

const normalizeReleaseRefs = (releaseRefs, layout = false) => {
  if (!Array.isArray(releaseRefs) || !releaseRefs.length) {
    fail("RULE_BUNDLE_RELEASE_REFS_INVALID", "规则包缺少已发布 release 引用");
  }
  const seen = new Set();
  const result = releaseRefs.map((value) => {
    if (!isObject(value)) fail("RULE_BUNDLE_RELEASE_REFS_INVALID", "release 引用格式错误");
    const ruleSetId = text(value.rule_set_id);
    const releaseId = text(value.release_id);
    const scopeLevel = text(value.scope_level);
    const manifestHash = value.manifest_hash == null ? "" : text(value.manifest_hash);
    const ruleSetName = value.rule_set_name == null ? "" : text(value.rule_set_name);
    const storedRuleSetId = value.stored_rule_set_id == null ? "" : text(value.stored_rule_set_id);
    const storedReleaseId = value.stored_release_id == null ? "" : text(value.stored_release_id);
    const versionPolicy = value.version_policy == null ? "" : text(value.version_policy);
    const migrationId = value.migration_id == null ? "" : text(value.migration_id);
    if (!ruleSetId || !releaseId || !["L1", "L2"].includes(scopeLevel)) {
      fail("RULE_BUNDLE_RELEASE_REFS_INVALID", "release 引用缺少 rule_set_id、release_id 或 scope_level");
    }
    if (manifestHash && !SHA256_PATTERN.test(manifestHash)) {
      fail("RULE_BUNDLE_RELEASE_REFS_INVALID", `release ${releaseId} 的 manifest_hash 非法`);
    }
    if (ruleSetName && (
      scopeLevel !== "L2" || ruleSetName.length < 3 || ruleSetName.length > 80 ||
      !RULE_SET_NAME_PATTERN.test(ruleSetName) || PORTABLE_RESERVED_SEGMENT_PATTERN.test(ruleSetName)
    )) {
      fail("RULE_BUNDLE_RELEASE_REFS_INVALID", `release ${releaseId} 的 rule_set_name 非法`);
    }
    if (scopeLevel === "L2" && CANONICAL_L2_RULE_SET_ID_PATTERN.test(ruleSetId) && !ruleSetName) {
      fail("RULE_BUNDLE_RELEASE_REFS_INVALID", `canonical release ${releaseId} 缺少 rule_set_name`);
    }
    const hasStoredIdentity = value.stored_rule_set_id != null || value.stored_release_id != null
      || value.version_policy != null || value.migration_id != null;
    if (hasStoredIdentity && (
      scopeLevel !== "L2" || !storedRuleSetId || !storedReleaseId ||
      !["pinned", "manual_upgrade", "auto_follow_latest"].includes(versionPolicy) ||
      (migrationId && !UUID_PATTERN.test(migrationId))
    )) {
      fail("RULE_BUNDLE_RELEASE_REFS_INVALID", `release ${releaseId} 的订阅身份元数据非法`);
    }
    const key = `${ruleSetId}\0${releaseId}\0${scopeLevel}`;
    if (seen.has(key)) fail("RULE_BUNDLE_RELEASE_REFS_INVALID", `release 引用重复：${releaseId}`);
    seen.add(key);
    const localName = layout ? normalizeLocalRuleSetName(value.local_rule_set_name) : "";
    if (layout && !DOMAINS.has(value.standard_domain)) {
      fail("RULE_BUNDLE_RELEASE_DOMAIN_INVALID", `release ${releaseId} 缺少有效的规则集领域`);
    }
    return {
      ...(layout ? { standard_domain: value.standard_domain, local_rule_set_name: localName } : {}),
      rule_set_id: ruleSetId,
      release_id: releaseId,
      scope_level: scopeLevel,
      ...(manifestHash ? { manifest_hash: manifestHash } : {}),
      ...(ruleSetName ? { rule_set_name: ruleSetName } : {}),
      ...(hasStoredIdentity ? {
        stored_rule_set_id: storedRuleSetId,
        stored_release_id: storedReleaseId,
        version_policy: versionPolicy,
        ...(migrationId ? { migration_id: migrationId } : {}),
      } : {}),
    };
  });
  return result.sort((left, right) => (
    left.rule_set_id.localeCompare(right.rule_set_id, "en")
    || left.release_id.localeCompare(right.release_id, "en")
    || left.scope_level.localeCompare(right.scope_level, "en")
  ));
};

const assertCanonicalL2PathBindings = (releaseRefs, relativePaths) => {
  const canonicalL2Refs = releaseRefs.filter((ref) =>
    ref.scope_level === "L2" && CANONICAL_L2_RULE_SET_ID_PATTERN.test(ref.rule_set_id)
  );
  if (!canonicalL2Refs.length) return;
  const l2DirectoryOwners = new Map();
  for (const ref of releaseRefs.filter((item) => item.scope_level === "L2")) {
    const directory = ref.rule_set_name || ref.rule_set_id;
    const key = pathKey(directory);
    const owners = l2DirectoryOwners.get(key) || [];
    owners.push(ref);
    l2DirectoryOwners.set(key, owners);
  }
  if ([...l2DirectoryOwners.values()].some((owners) => owners.length !== 1)) {
    fail("RULE_BUNDLE_RELEASE_REFS_INVALID", "L2 release 引用目录归属不唯一");
  }
  const matchedCanonicalRefs = new Set();
  for (const relativePath of relativePaths.filter((item) => item.startsWith("l2/"))) {
    const directory = relativePath.split("/")[1] || "";
    const owners = l2DirectoryOwners.get(pathKey(directory));
    if (!owners || owners.length !== 1
      || (owners[0].rule_set_name && owners[0].rule_set_name !== directory)) {
      fail("RULE_BUNDLE_FILE_PATH_INVALID", `L2 文件目录没有唯一 release 引用：${relativePath}`);
    }
    if (owners[0].rule_set_name) matchedCanonicalRefs.add(owners[0].rule_set_id);
  }
  for (const ref of canonicalL2Refs) {
    if (!matchedCanonicalRefs.has(ref.rule_set_id)) {
      fail("RULE_BUNDLE_FILES_MISSING", `canonical release ${ref.release_id} 没有匹配规则文件`);
    }
  }
};

const validateBundle = (body, knownSnapshotId, expectedStage = "", requireLayout = false) => {
  const layout = body?.schema_version === LAYOUT_BUNDLE_SCHEMA;
  if (requireLayout && !layout) fail("RULE_BUNDLE_LAYOUT_UNSUPPORTED", "规则包服务尚未支持 scope-domain-ruleset/v1 新目录合同，请先升级服务端；本地规则未修改");
  const expectedSchema = requireLayout ? LAYOUT_BUNDLE_SCHEMA : expectedStage ? STAGED_BUNDLE_SCHEMA : BUNDLE_SCHEMA;
  const acceptedSchemas = expectedStage
    ? [STAGED_BUNDLE_SCHEMA, LAYOUT_BUNDLE_SCHEMA]
    : [LEGACY_BUNDLE_SCHEMA, BUNDLE_SCHEMA, LAYOUT_BUNDLE_SCHEMA];
  if (!isObject(body) || !acceptedSchemas.includes(body.schema_version)) {
    fail("RULE_BUNDLE_RESPONSE_INVALID", `规则包响应必须为 ${expectedSchema}`);
  }
  if (!new Set(["ready", "not_modified"]).has(body.status) || !isObject(body.snapshot)) {
    fail("RULE_BUNDLE_RESPONSE_INVALID", "规则包缺少有效 status 或 snapshot");
  }
  const snapshot = body.snapshot;
  const currentVersion = body.schema_version !== LEGACY_BUNDLE_SCHEMA;
  if (currentVersion ? snapshot.resolver_version !== body.schema_version : snapshot.resolver_version != null) {
    fail("RULE_BUNDLE_RESPONSE_INVALID", "规则包生成版本与响应协议不一致");
  }
  if (expectedStage) {
    if (snapshot.stage !== expectedStage || !SHA256_PATTERN.test(text(snapshot.dependency_hash))) {
      fail("RULE_BUNDLE_STAGE_MISMATCH", "规则包阶段或依赖哈希与请求不一致");
    }
  } else if (snapshot.stage != null || snapshot.dependency_hash != null) {
    fail("RULE_BUNDLE_RESPONSE_INVALID", "旧版规则包响应不得携带阶段上下文");
  }
  const pathOrder = currentVersion ? binaryPathOrder : (left, right) => left.localeCompare(right, "en");
  const repository = snapshot.repository;
  if (
    !isObject(repository)
    || !text(repository.repository_id)
    || !text(repository.canonical_key)
    || !DOMAINS.has(repository.standard_domain)
  ) {
    fail("RULE_BUNDLE_REPOSITORY_INVALID", "规则包仓库身份或领域无效");
  }
  if (!SHA256_PATTERN.test(text(snapshot.snapshot_id)) || !SHA256_PATTERN.test(text(snapshot.manifest_hash))) {
    fail("RULE_BUNDLE_HASH_INVALID", "规则包 snapshot_id 或 manifest_hash 非法");
  }
  const releaseRefs = normalizeReleaseRefs(snapshot.release_refs, layout);
  if (!Number.isSafeInteger(snapshot.total_bytes) || snapshot.total_bytes < 0) {
    fail("RULE_BUNDLE_TOTAL_BYTES_INVALID", "规则包总字节数非法");
  }
  const hasAgentsIndexes = validateAgentsIndexes(body, releaseRefs, fail);
  const snapshotProjection = {
    ...(currentVersion ? { resolver_version: body.schema_version } : {}),
    repository_id: repository.repository_id,
    canonical_key: repository.canonical_key,
    standard_domain: repository.standard_domain,
    manifest_hash: snapshot.manifest_hash,
    ...(snapshot.agents_indexes_hash ? { agents_indexes_hash: snapshot.agents_indexes_hash } : {}),
    release_refs: releaseRefs,
    ...(expectedStage ? {
      stage: expectedStage,
      dependency_hash: snapshot.dependency_hash,
    } : {}),
  };
  if (sha256Hex(canonicalJson(snapshotProjection)) !== snapshot.snapshot_id) {
    fail("RULE_BUNDLE_SNAPSHOT_HASH_MISMATCH", "规则包 snapshot_id 校验失败");
  }
  const files = Array.isArray(body.files) ? body.files : [];
  if (body.status === "not_modified") {
    if (!knownSnapshotId || snapshot.snapshot_id !== knownSnapshotId || files.length) {
      fail("RULE_BUNDLE_NOT_MODIFIED_INVALID", "not_modified 与本地已校验快照不一致");
    }
    return { status: body.status, snapshot: { ...snapshot, repository, release_refs: releaseRefs }, files: [], ...(hasAgentsIndexes ? { agents_indexes: body.agents_indexes } : {}) };
  }
  if (!files.length) fail("RULE_BUNDLE_FILES_MISSING", "ready 规则包没有文件");

  const seenPaths = new Set();
  const directories = new Map();
  const normalizedFiles = files.map((file) => {
    if (!isObject(file)) fail("RULE_BUNDLE_FILE_INVALID", "规则文件格式错误");
    const relativePath = normalizeRelativePath(file.relative_path, currentVersion);
    const collisionKey = pathKey(relativePath);
    if (seenPaths.has(collisionKey)) fail("RULE_BUNDLE_FILE_DUPLICATE", `规则文件路径重复：${relativePath}`);
    seenPaths.add(collisionKey);
    const parts = relativePath.split("/");
    for (let end = 1; end < parts.length; end += 1) {
      const directory = parts.slice(0, end).join("/");
      const key = pathKey(directory);
      if (directories.has(key) && directories.get(key) !== directory) fail("RULE_BUNDLE_FILE_DUPLICATE", `规则目录存在大小写或 Unicode 重名：${directory}`);
      directories.set(key, directory);
    }
    const content = typeof file.content === "string" ? file.content : null;
    const declaredHash = text(file.sha256);
    const byteSize = Number(file.byte_size);
    if (content == null || !SHA256_PATTERN.test(declaredHash) || !Number.isSafeInteger(byteSize) || byteSize < 0) {
      fail("RULE_BUNDLE_FILE_INVALID", `规则文件元数据非法：${relativePath}`);
    }
    const actualBytes = Buffer.byteLength(content, "utf8");
    const actualHash = sha256Hex(content);
    if (actualBytes > MAX_FILE_BYTES) {
      fail("RULE_BUNDLE_FILE_TOO_LARGE", `规则文件超过 512 KiB 安全上限：${relativePath}`);
    }
    if (actualBytes !== byteSize || actualHash !== declaredHash) {
      fail("RULE_BUNDLE_FILE_HASH_MISMATCH", `规则文件内容校验失败：${relativePath}`);
    }
    let identity = {};
    if (layout) {
      const owners = releaseRefs.filter((ref) => ref.rule_set_id === file.rule_set_id && ref.release_id === file.release_id);
      if (owners.length !== 1 || relativePath.split("/")[0] !== owners[0].scope_level.toLowerCase()) {
        fail("RULE_BUNDLE_FILE_RELEASE_INVALID", `规则文件没有唯一匹配的 release：${relativePath}`);
      }
      identity = { rule_set_id: file.rule_set_id, release_id: file.release_id };
    }
    return { relative_path: relativePath, ...identity, content, sha256: actualHash, byte_size: actualBytes };
  }).sort((left, right) => pathOrder(left.relative_path, right.relative_path));

  if (currentVersion) {
    assertCanonicalL2PathBindings(releaseRefs, normalizedFiles.map((file) => file.relative_path));
  }

  const totalBytes = normalizedFiles.reduce((sum, file) => sum + file.byte_size, 0);
  if (snapshot.total_bytes !== totalBytes) fail("RULE_BUNDLE_TOTAL_BYTES_MISMATCH", "规则包总字节数校验失败");
  const projection = normalizedFiles.map(({ relative_path, rule_set_id, release_id, sha256, byte_size }) => ({
    relative_path,
    ...(layout ? { rule_set_id, release_id } : {}),
    sha256,
    byte_size,
  }));
  const manifestHash = sha256Hex(canonicalJson(projection));
  if (manifestHash !== snapshot.manifest_hash) fail("RULE_BUNDLE_MANIFEST_HASH_MISMATCH", "规则包 manifest_hash 校验失败");
  return {
    status: body.status,
    snapshot: { ...snapshot, repository, release_refs: releaseRefs, total_bytes: totalBytes },
    files: normalizedFiles,
    ...(hasAgentsIndexes ? { agents_indexes: body.agents_indexes } : {}),
  };
};

const validateBootstrapBundle = (body, knownSnapshotId, expectedStage = "", requireLayout = false) => {
  const layout = body?.schema_version === LAYOUT_BOOTSTRAP_BUNDLE_SCHEMA;
  if (requireLayout && !layout) fail("RULE_BUNDLE_LAYOUT_UNSUPPORTED", "L1 bootstrap 服务尚未支持 scope-domain-ruleset/v1 新目录合同，请先升级服务端；本地规则未修改");
  const expectedSchema = layout ? LAYOUT_BOOTSTRAP_BUNDLE_SCHEMA : expectedStage ? STAGED_BOOTSTRAP_BUNDLE_SCHEMA : BOOTSTRAP_BUNDLE_SCHEMA;
  if (!isObject(body) || body.schema_version !== expectedSchema
    || !new Set(["ready", "not_modified"]).has(body.status) || !isObject(body.snapshot)) {
    fail("RULE_BUNDLE_BOOTSTRAP_RESPONSE_INVALID", `L1 bootstrap 响应必须为 ${expectedSchema}`);
  }
  const snapshot = body.snapshot;
  if (snapshot.bootstrap_version !== expectedSchema
    || !DOMAINS.has(snapshot.standard_domain)
    || !SHA256_PATTERN.test(text(snapshot.snapshot_id))
    || !SHA256_PATTERN.test(text(snapshot.manifest_hash))) {
    fail("RULE_BUNDLE_BOOTSTRAP_RESPONSE_INVALID", "L1 bootstrap 快照字段非法");
  }
  if (expectedStage) {
    if (snapshot.stage !== expectedStage || !SHA256_PATTERN.test(text(snapshot.dependency_hash))) {
      fail("RULE_BUNDLE_STAGE_MISMATCH", "L1 bootstrap 阶段或依赖哈希与请求不一致");
    }
  } else if (snapshot.stage != null || snapshot.dependency_hash != null) {
    fail("RULE_BUNDLE_BOOTSTRAP_RESPONSE_INVALID", "旧版 L1 bootstrap 响应不得携带阶段上下文");
  }
  const releaseRefs = normalizeReleaseRefs(snapshot.release_refs, layout);
  if (releaseRefs.some((release) => release.scope_level !== "L1" || (layout && release.standard_domain !== snapshot.standard_domain))) {
    fail("RULE_BUNDLE_BOOTSTRAP_RESPONSE_INVALID", "L1 bootstrap 响应包含非 L1 或其他领域的 release");
  }
  const hasAgentsIndexes = validateAgentsIndexes(body, releaseRefs, fail);
  const snapshotProjection = {
    bootstrap_version: expectedSchema,
    standard_domain: snapshot.standard_domain,
    manifest_hash: snapshot.manifest_hash,
    ...(snapshot.agents_indexes_hash ? { agents_indexes_hash: snapshot.agents_indexes_hash } : {}),
    release_refs: releaseRefs,
    ...(expectedStage ? {
      stage: expectedStage,
      dependency_hash: snapshot.dependency_hash,
    } : {}),
  };
  if (sha256Hex(canonicalJson(snapshotProjection)) !== snapshot.snapshot_id) {
    fail("RULE_BUNDLE_SNAPSHOT_HASH_MISMATCH", "L1 bootstrap snapshot_id 校验失败");
  }
  if (body.status === "not_modified") {
    if (!knownSnapshotId || snapshot.snapshot_id !== knownSnapshotId
      || !Array.isArray(body.files) || body.files.length) {
      fail("RULE_BUNDLE_NOT_MODIFIED_INVALID", "L1 bootstrap not_modified 与本地快照不一致");
    }
    return {
      status: body.status,
      snapshot: { ...snapshot, release_refs: releaseRefs },
      files: [],
      ...(hasAgentsIndexes ? { agents_indexes: body.agents_indexes } : {}),
    };
  }
  const syntheticRepository = {
    repository_id: `l1-bootstrap:${snapshot.standard_domain}`,
    canonical_key: `l1-bootstrap/${snapshot.standard_domain}`,
    standard_domain: snapshot.standard_domain,
  };
  const syntheticBundleSchema = layout ? LAYOUT_BUNDLE_SCHEMA : expectedStage ? STAGED_BUNDLE_SCHEMA : BUNDLE_SCHEMA;
  const syntheticProjection = {
    resolver_version: syntheticBundleSchema,
    repository_id: syntheticRepository.repository_id,
    canonical_key: syntheticRepository.canonical_key,
    standard_domain: syntheticRepository.standard_domain,
    manifest_hash: snapshot.manifest_hash,
    ...(snapshot.agents_indexes_hash ? { agents_indexes_hash: snapshot.agents_indexes_hash } : {}),
    release_refs: releaseRefs,
    ...(expectedStage ? {
      stage: expectedStage,
      dependency_hash: snapshot.dependency_hash,
    } : {}),
  };
  const validated = validateBundle({
    schema_version: syntheticBundleSchema,
    status: "ready",
    snapshot: {
      resolver_version: syntheticBundleSchema,
      snapshot_id: sha256Hex(canonicalJson(syntheticProjection)),
      repository: syntheticRepository,
      release_refs: releaseRefs,
      manifest_hash: snapshot.manifest_hash,
      ...(snapshot.agents_indexes_hash ? { agents_indexes_hash: snapshot.agents_indexes_hash } : {}),
      total_bytes: snapshot.total_bytes,
      ...(expectedStage ? {
        stage: expectedStage,
        dependency_hash: snapshot.dependency_hash,
      } : {}),
    },
    files: body.files,
    ...(hasAgentsIndexes ? { agents_indexes: body.agents_indexes } : {}),
  }, "", expectedStage);
  if (validated.files.some((file) => !file.relative_path.startsWith("l1/"))) {
    fail("RULE_BUNDLE_BOOTSTRAP_RESPONSE_INVALID", "L1 bootstrap 响应包含非 L1 文件");
  }
  return {
    status: "ready",
    snapshot: { ...snapshot, release_refs: releaseRefs },
    files: validated.files,
    ...(hasAgentsIndexes ? { agents_indexes: body.agents_indexes } : {}),
  };
};

const assertNoSymlink = async (target, stopAt) => {
  let cursor = path.resolve(target);
  const boundary = path.resolve(stopAt);
  while (cursor.startsWith(`${boundary}${path.sep}`) || cursor === boundary) {
    if (await exists(cursor)) {
      const info = await lstat(cursor);
      if (info.isSymbolicLink()) fail("RULE_BUNDLE_LOCAL_SYMLINK", `受管路径不能是符号链接：${cursor}`);
    }
    if (cursor === boundary) break;
    cursor = path.dirname(cursor);
  }
};

const readLocalManifest = async (repoRoot) => {
  const rulesRoot = path.join(repoRoot, ".mdp", "rules");
  const manifestPath = path.join(rulesRoot, MANIFEST_NAME);
  if (!await exists(manifestPath)) return null;
  await assertNoSymlink(manifestPath, rulesRoot);
  try {
    const value = JSON.parse(await readFile(manifestPath, "utf8"));
    return isObject(value) ? value : null;
  } catch {
    return null;
  }
};

const readBootstrapManifest = async (repoRoot) => {
  const rulesRoot = path.join(repoRoot, ".mdp", "rules");
  const manifestPath = path.join(rulesRoot, BOOTSTRAP_MANIFEST_NAME);
  if (!await exists(manifestPath)) return { exists: false, value: null };
  await assertNoSymlink(manifestPath, rulesRoot);
  try {
    const value = JSON.parse(await readFile(manifestPath, "utf8"));
    return { exists: true, value: isObject(value) ? value : null };
  } catch {
    return { exists: true, value: null };
  }
};

const isNamedLocalManifest = (manifest) => manifest?.local_layout === LOCAL_LAYOUT
  && [LEGACY_LAYOUT_LOCAL_MANIFEST_SCHEMA, PREVIOUS_LAYOUT_LOCAL_MANIFEST_SCHEMA, LAYOUT_LOCAL_MANIFEST_SCHEMA, UNIFIED_LOCAL_SCHEMA].includes(manifest.schema_version);
const isNamedBootstrapManifest = (manifest) => manifest?.local_layout === LOCAL_LAYOUT
  && [LEGACY_LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA, LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA, UNIFIED_L1_LOCAL_SCHEMA].includes(manifest.schema_version);
const hasAgentsManifestFields = (manifest) => ["agents_index_contract", "agents_indexes_hash", "agents_indexes",
  "managed_agents_indexes", "managed_agents_index_hashes", "managed_agents_index_sizes", "agents_index_warnings"]
  .some((key) => Object.hasOwn(manifest, key));
const manifestIndexPlacement = (manifest) => [LAYOUT_LOCAL_MANIFEST_SCHEMA, UNIFIED_LOCAL_SCHEMA].includes(manifest.schema_version) && isNamedLocalManifest(manifest)
  ? "named-team"
  : manifest.schema_version === AGENTS_LOCAL_MANIFEST_SCHEMA && manifest.local_layout === FLAT_LOCAL_LAYOUT
    ? "flat-team" : "separate";
const validateOptionalAgentsManifest = (manifest, required = false) =>
  required || hasAgentsManifestFields(manifest)
    ? validateAgentsManifest(manifest, { indexPlacement: manifestIndexPlacement(manifest) }) : true;

const isFlatLocalManifest = (manifest) => [
  LEGACY_FLAT_LOCAL_MANIFEST_SCHEMA,
  FLAT_LOCAL_MANIFEST_SCHEMA,
  LEGACY_AGENTS_LOCAL_MANIFEST_SCHEMA,
  AGENTS_LOCAL_MANIFEST_SCHEMA,
  LAYOUT_LOCAL_MANIFEST_SCHEMA,
  UNIFIED_LOCAL_SCHEMA,
].includes(manifest?.schema_version);

const manifestBundleSchema = (manifest) => {
  if (isFlatLocalManifest(manifest)) return manifest.resolver_version;
  return manifest?.schema_version === LOCAL_MANIFEST_SCHEMA
    ? BUNDLE_SCHEMA
    : LEGACY_BUNDLE_SCHEMA;
};

const manifestPhysicalPath = (manifest, managedPath) => {
  const bundleSchema = manifestBundleSchema(manifest);
  return normalizeRelativePath(managedPath, bundleSchema !== LEGACY_BUNDLE_SCHEMA);
};

const manifestSourcePath = (manifest, managedPath) => {
  const bundleSchema = manifestBundleSchema(manifest);
  if (isFlatLocalManifest(manifest)) {
    return normalizeRelativePath(
      manifest.managed_file_sources[managedPath],
      bundleSchema !== LEGACY_BUNDLE_SCHEMA,
    );
  }
  const prefix = `${manifest.standard_domain}/`;
  return normalizeRelativePath(managedPath.slice(prefix.length), bundleSchema !== LEGACY_BUNDLE_SCHEMA);
};

const isFlatManagedPath = (value, bundleSchema) => {
  const currentVersion = typeof bundleSchema === "boolean"
    ? bundleSchema
    : bundleSchema !== LEGACY_BUNDLE_SCHEMA;
  const pathValue = normalizeRelativePath(value, currentVersion);
  const parts = pathValue.split("/");
  return (parts[0] === "company" && parts.length === 2)
    || (parts[0] === "team" && parts.length === 3);
};

const suffixFileName = (fileName, sourcePath, attempt = 0) => {
  const lastDot = fileName.lastIndexOf(".");
  const stem = lastDot > 0 ? fileName.slice(0, lastDot) : fileName;
  const extension = lastDot > 0 ? fileName.slice(lastDot) : "";
  return `${stem}--${sha256Hex(`${sourcePath}\0${attempt}`).slice(0, 16)}${extension}`;
};

const isLayoutManagedPath = (value) => {
  const pathValue = normalizeRelativePath(value, true);
  const parts = pathValue.split("/");
  return parts.length === 4 && ["company", "team"].includes(parts[0])
    && ["fe", "java"].includes(parts[1]) && normalizeLocalRuleSetName(parts[2]) === parts[2];
};

const localFilesForBundle = (bundle, { indexPlacement = "named-team" } = {}) => {
  const layout = bundle.snapshot.resolver_version === LAYOUT_BUNDLE_SCHEMA;
  const versionTwo = bundle.snapshot.resolver_version !== LEGACY_BUNDLE_SCHEMA;
  const directoryOwners = new Map();
  const refs = normalizeReleaseRefs(bundle.snapshot.release_refs, layout);
  if (layout) for (const ref of refs) {
    const dir = `${ref.scope_level === "L1" ? "company" : "team"}/${ref.standard_domain === "frontend" ? "fe" : "java"}/${ref.local_rule_set_name}`;
    const key = pathKey(dir);
    if (directoryOwners.has(key)) fail("RULE_BUNDLE_RULE_SET_NAME_COLLISION", `同层级和领域的规则集目录名称冲突：${ref.local_rule_set_name}`);
    directoryOwners.set(key, ref.rule_set_id);
  }
  const candidates = bundle.files.map((file) => {
    const sourcePath = normalizeRelativePath(file.relative_path, versionTwo);
    const parts = sourcePath.split("/");
    const scope = parts[0];
    const fileName = parts.at(-1);
    if ((scope !== "l1" && scope !== "l2") || !fileName) fail("RULE_BUNDLE_FILE_PATH_INVALID", `规则文件层级非法：${sourcePath}`);
    const owners = layout ? refs.filter((ref) => ref.rule_set_id === file.rule_set_id && ref.release_id === file.release_id) : [];
    if (layout && (owners.length !== 1 || owners[0].scope_level.toLowerCase() !== scope)) fail("RULE_BUNDLE_FILE_RELEASE_INVALID", `规则文件没有唯一匹配的 release：${sourcePath}`);
    const owner = owners[0];
    const inferredRuleSetId = parts.length > 2 ? parts[1] : fileName.replace(/[.]md$/iu, "");
    const candidate = layout
      ? `${scope === "l1" ? "company" : "team"}/${owner.standard_domain === "frontend" ? "fe" : "java"}/${owner.local_rule_set_name}/${fileName}`
      : scope === "l1" ? `company/${fileName}` : `team/${inferredRuleSetId}/${fileName}`;
    return { ...file, source_relative_path: sourcePath, local_relative_path: candidate };
  });
  const reservedIndexPaths = agentsIndexDestinations(bundle.agents_indexes, refs, { indexPlacement });
  if (indexPlacement !== "separate") for (const entry of bundle.agents_indexes || []) {
    const ref = refs.find(item => item.rule_set_id === entry.rule_set_id && item.release_id === entry.release_id);
    if (ref?.scope_level !== "L2") continue;
    const expectedDirectory = path.posix.dirname(reservedIndexPaths.get(entry.rule_set_id));
    const sourceDirectories = new Set([ref.rule_set_name || ref.rule_set_id, ref.rule_set_id]);
    for (const file of candidates.filter(item => item.source_relative_path.startsWith("l2/"))) {
      const parts = file.source_relative_path.split("/");
      const sourceDirectory = parts.length > 2 ? parts[1] : parts[1].replace(/[.]md$/iu, "");
      const owned = layout ? file.rule_set_id === ref.rule_set_id && file.release_id === ref.release_id : sourceDirectories.has(sourceDirectory);
      if (owned && path.posix.dirname(file.local_relative_path) !== expectedDirectory) {
        fail("RULE_BUNDLE_FILE_PATH_INVALID", "L2 索引所属规则集目录与实际规则文件不一致");
      }
    }
  }
  const occupied = new Set([...reservedIndexPaths.values()].map(pathKey));
  return candidates.map((file) => {
    let localPath = file.local_relative_path;
    let attempt = 0;
    while (occupied.has(pathKey(localPath))) {
      const parts = localPath.split("/");
      localPath = [...parts.slice(0, -1), suffixFileName(parts.at(-1), file.source_relative_path, attempt++)].join("/");
    }
    if (!(layout ? isLayoutManagedPath(localPath) : isFlatManagedPath(localPath, versionTwo))) fail("RULE_BUNDLE_FILE_PATH_INVALID", `规则本地路径非法：${localPath}`);
    occupied.add(pathKey(localPath));
    return { ...file, local_relative_path: localPath };
  }).sort((left, right) => binaryPathOrder(left.local_relative_path, right.local_relative_path));
};

const validateLocalManifestStructure = (manifest) => {
  if (manifest?.schema_version === UNIFIED_LOCAL_SCHEMA) return validateResolutionManifest(manifest)
    && validateLocalManifestStructure({ ...manifest, schema_version: LAYOUT_LOCAL_MANIFEST_SCHEMA });
  if (
    !manifest
    || ![
      LEGACY_LOCAL_MANIFEST_SCHEMA,
      LOCAL_MANIFEST_SCHEMA,
      LEGACY_FLAT_LOCAL_MANIFEST_SCHEMA,
      FLAT_LOCAL_MANIFEST_SCHEMA,
      LEGACY_AGENTS_LOCAL_MANIFEST_SCHEMA,
      AGENTS_LOCAL_MANIFEST_SCHEMA,
      LAYOUT_LOCAL_MANIFEST_SCHEMA,
    ].includes(manifest.schema_version)
    || !SHA256_PATTERN.test(text(manifest.snapshot_id))
    || !SHA256_PATTERN.test(text(manifest.manifest_hash))
    || !DOMAINS.has(manifest.standard_domain)
    || !isObject(manifest.repository)
    || manifest.repository.standard_domain !== manifest.standard_domain
    || !text(manifest.repository.repository_id)
    || !text(manifest.repository.canonical_key)
    || !Array.isArray(manifest.managed_files)
    || !isObject(manifest.managed_file_hashes)
    || !isObject(manifest.managed_file_sizes)
  ) return false;
  const flat = isFlatLocalManifest(manifest);
  const layout = isNamedLocalManifest(manifest);
  if (manifest.schema_version === LAYOUT_LOCAL_MANIFEST_SCHEMA && !layout) return false;
  const bundleSchema = manifestBundleSchema(manifest);
  if (![LEGACY_BUNDLE_SCHEMA, BUNDLE_SCHEMA, STAGED_BUNDLE_SCHEMA, LAYOUT_BUNDLE_SCHEMA].includes(bundleSchema)) return false;
  if (!layout && bundleSchema === LAYOUT_BUNDLE_SCHEMA) return false;
  if (!flat && (manifest.schema_version === LOCAL_MANIFEST_SCHEMA
    ? manifest.resolver_version !== BUNDLE_SCHEMA
    : manifest.resolver_version != null)) return false;
  if (flat && (
    manifest.local_layout !== (layout ? LOCAL_LAYOUT : FLAT_LOCAL_LAYOUT)
    || !isObject(manifest.managed_file_sources)
    || (layout && (!isObject(manifest.managed_file_releases) || bundleSchema !== LAYOUT_BUNDLE_SCHEMA))
  )) return false;
  const stage = [FLAT_LOCAL_MANIFEST_SCHEMA, LEGACY_AGENTS_LOCAL_MANIFEST_SCHEMA, AGENTS_LOCAL_MANIFEST_SCHEMA, LAYOUT_LOCAL_MANIFEST_SCHEMA].includes(manifest.schema_version)
    ? normalizeDeliveryStage(manifest.stage)
    : "";
  if (bundleSchema === STAGED_BUNDLE_SCHEMA || (layout && stage)) {
    if (!stage || !SHA256_PATTERN.test(text(manifest.dependency_hash))) return false;
  } else if (stage || manifest.dependency_hash != null) return false;
  if (manifest.schema_version === LEGACY_FLAT_LOCAL_MANIFEST_SCHEMA
    && bundleSchema === STAGED_BUNDLE_SCHEMA) return false;
  const versionTwo = bundleSchema !== LEGACY_BUNDLE_SCHEMA;
  const pathOrder = versionTwo ? binaryPathOrder : (left, right) => left.localeCompare(right, "en");
  const uniquePaths = new Set(manifest.managed_files);
  if (uniquePaths.size !== manifest.managed_files.length || !uniquePaths.size) return false;
  if (flat && Object.keys(manifest.managed_file_sources).length !== uniquePaths.size) return false;
  const projection = [];
  for (const managedPath of [...uniquePaths].sort(pathOrder)) {
    if (typeof managedPath !== "string") return false;
    if (!flat && !managedPath.startsWith(`${manifest.standard_domain}/`)) return false;
    if (flat && !(layout ? isLayoutManagedPath(managedPath) : isFlatManagedPath(managedPath, bundleSchema))) return false;
    const sourcePath = manifestSourcePath(manifest, managedPath);
    if (flat && !Object.hasOwn(manifest.managed_file_sources, managedPath)) return false;
    const fileHash = manifest.managed_file_hashes[managedPath];
    const fileSize = manifest.managed_file_sizes[managedPath];
    if (!SHA256_PATTERN.test(text(fileHash)) || !Number.isSafeInteger(fileSize) || fileSize < 0) return false;
    const identity = layout ? manifest.managed_file_releases[managedPath] : {};
    if (layout && (!isObject(identity) || !text(identity.rule_set_id) || !text(identity.release_id))) return false;
    projection.push({ relative_path: sourcePath, ...(layout ? { rule_set_id: identity.rule_set_id, release_id: identity.release_id } : {}), sha256: fileHash, byte_size: fileSize });
  }
  // Flattening and collision suffixes can change local filename order. The
  // server manifest hash always uses the original source paths.
  if (flat) projection.sort((left, right) => pathOrder(left.relative_path, right.relative_path));
  if (sha256Hex(canonicalJson(projection)) !== manifest.manifest_hash) return false;
  if (projection.reduce((sum, file) => sum + file.byte_size, 0) !== manifest.total_bytes) return false;
  const releaseRefs = normalizeReleaseRefs(manifest.release_refs, layout);
  if (versionTwo) {
    try {
      assertCanonicalL2PathBindings(releaseRefs, projection.map((file) => file.relative_path));
    } catch {
      return false;
    }
  }
  const indexPlacement = manifestIndexPlacement(manifest);
  if (layout || indexPlacement === "flat-team") {
    if (layout && Object.keys(manifest.managed_file_releases).length !== uniquePaths.size) return false;
    const derived = localFilesForBundle({ snapshot: { resolver_version: bundleSchema, release_refs: releaseRefs },
      files: projection, agents_indexes: manifest.agents_indexes }, { indexPlacement });
    if (canonicalJson(Object.fromEntries(derived.map(file => [file.local_relative_path, file.source_relative_path])))
      !== canonicalJson(manifest.managed_file_sources)) return false;
  }
  const snapshotProjection = {
    ...(bundleSchema !== LEGACY_BUNDLE_SCHEMA ? { resolver_version: bundleSchema } : {}),
    repository_id: manifest.repository.repository_id,
    canonical_key: manifest.repository.canonical_key,
    standard_domain: manifest.repository.standard_domain,
    manifest_hash: manifest.manifest_hash,
    ...(manifest.agents_indexes_hash ? { agents_indexes_hash: manifest.agents_indexes_hash } : {}),
    release_refs: releaseRefs,
    ...(stage ? { stage, dependency_hash: manifest.dependency_hash } : {}),
  };
  const indexCapable = layout
    ? [PREVIOUS_LAYOUT_LOCAL_MANIFEST_SCHEMA, LAYOUT_LOCAL_MANIFEST_SCHEMA].includes(manifest.schema_version)
    : [LEGACY_AGENTS_LOCAL_MANIFEST_SCHEMA, AGENTS_LOCAL_MANIFEST_SCHEMA].includes(manifest.schema_version);
  if (indexCapable ? !validateOptionalAgentsManifest(manifest, !layout) : hasAgentsManifestFields(manifest)) return false;
  return sha256Hex(canonicalJson(snapshotProjection)) === manifest.snapshot_id;
};

const validateLocalManifestFiles = async (repoRoot, manifest) => {
  if (!validateLocalManifestStructure(manifest)) return false;
  const rulesRoot = path.join(repoRoot, ".mdp", "rules");
  for (const managedPath of manifest.managed_files) {
    const relativePath = manifestPhysicalPath(manifest, managedPath);
    const fullPath = path.join(rulesRoot, ...relativePath.split("/"));
    await assertNoSymlink(fullPath, rulesRoot);
    if (!await exists(fullPath)) return false;
    const content = await readFile(fullPath);
    if (
      sha256Hex(content) !== manifest.managed_file_hashes[managedPath]
      || content.byteLength !== manifest.managed_file_sizes[managedPath]
    ) return false;
  }
  return validateLocalAgentsIndexFiles(rulesRoot, manifest);
};

const validateLocalAgentsIndexFiles = async (rulesRoot, manifest) => {
  for (const name of manifest.managed_agents_indexes || []) {
    const fullPath = path.join(rulesRoot, ...name.split("/"));
    await assertNoSymlink(fullPath, rulesRoot);
    if (!await exists(fullPath)) return false;
    const content = await readFile(fullPath);
    if (sha256Hex(content) !== manifest.managed_agents_index_hashes[name]
      || content.byteLength !== manifest.managed_agents_index_sizes[name]) return false;
  }
  return true;
};

const validateBootstrapManifestStructure = (manifest) => {
  if (manifest?.schema_version === UNIFIED_L1_LOCAL_SCHEMA) return validateResolutionManifest(manifest)
    && ["user_explicit", "repository_configuration"].includes(manifest.domain_source)
    && manifest.domain_source === manifest.resolution.domain_source
    && validateBootstrapManifestStructure({ ...manifest, schema_version: LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA, domain_source: "user_explicit" });
  if (!manifest || ![
    LEGACY_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA,
    BOOTSTRAP_LOCAL_MANIFEST_SCHEMA,
    AGENTS_BOOTSTRAP_MANIFEST_SCHEMA,
    LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA,
  ].includes(manifest.schema_version)
    || ![BOOTSTRAP_BUNDLE_SCHEMA, STAGED_BOOTSTRAP_BUNDLE_SCHEMA, LAYOUT_BOOTSTRAP_BUNDLE_SCHEMA].includes(manifest.bundle_schema)
    || manifest.local_layout !== (isNamedBootstrapManifest(manifest) ? LOCAL_LAYOUT : FLAT_LOCAL_LAYOUT)
    || !SHA256_PATTERN.test(text(manifest.snapshot_id))
    || !SHA256_PATTERN.test(text(manifest.manifest_hash))
    || !DOMAINS.has(manifest.standard_domain)
    || !["git_tracked_evidence", "user_explicit"].includes(manifest.domain_source)
    || !Array.isArray(manifest.managed_files) || !manifest.managed_files.length
    || !isObject(manifest.managed_file_sources)
    || !isObject(manifest.managed_file_hashes)
    || !isObject(manifest.managed_file_sizes)) return false;
  const layout = isNamedBootstrapManifest(manifest);
  if (manifest.schema_version === LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA && !layout) return false;
  if (!layout && manifest.bundle_schema === LAYOUT_BOOTSTRAP_BUNDLE_SCHEMA) return false;
  if (layout && (manifest.bundle_schema !== LAYOUT_BOOTSTRAP_BUNDLE_SCHEMA || !isObject(manifest.managed_file_releases))) return false;
  const stage = [BOOTSTRAP_LOCAL_MANIFEST_SCHEMA, AGENTS_BOOTSTRAP_MANIFEST_SCHEMA, LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA].includes(manifest.schema_version)
    ? normalizeDeliveryStage(manifest.stage)
    : "";
  if (manifest.bundle_schema === STAGED_BOOTSTRAP_BUNDLE_SCHEMA || (layout && stage)) {
    if (!stage || !SHA256_PATTERN.test(text(manifest.dependency_hash))) return false;
  } else if (stage || manifest.dependency_hash != null) return false;
  if (manifest.schema_version === LEGACY_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA
    && manifest.bundle_schema !== BOOTSTRAP_BUNDLE_SCHEMA) return false;
  const uniquePaths = new Set(manifest.managed_files);
  if (uniquePaths.size !== manifest.managed_files.length
    || Object.keys(manifest.managed_file_sources).length !== uniquePaths.size) return false;
  const projection = [];
  for (const managedPath of [...uniquePaths].sort(binaryPathOrder)) {
    if (typeof managedPath !== "string" || !(layout ? isLayoutManagedPath(managedPath) : isFlatManagedPath(managedPath, BUNDLE_SCHEMA))
      || !managedPath.startsWith("company/")
      || !Object.hasOwn(manifest.managed_file_sources, managedPath)) return false;
    const sourcePath = normalizeRelativePath(manifest.managed_file_sources[managedPath], true);
    if (!sourcePath.startsWith("l1/")) return false;
    const fileHash = text(manifest.managed_file_hashes[managedPath]);
    const fileSize = manifest.managed_file_sizes[managedPath];
    if (!SHA256_PATTERN.test(fileHash) || !Number.isSafeInteger(fileSize) || fileSize < 0) return false;
    const identity = layout ? manifest.managed_file_releases[managedPath] : {};
    if (layout && (!isObject(identity) || !text(identity.rule_set_id) || !text(identity.release_id))) return false;
    projection.push({ relative_path: sourcePath, ...(layout ? { rule_set_id: identity.rule_set_id, release_id: identity.release_id } : {}), sha256: fileHash, byte_size: fileSize });
  }
  projection.sort((left, right) => binaryPathOrder(left.relative_path, right.relative_path));
  if (sha256Hex(canonicalJson(projection)) !== manifest.manifest_hash
    || projection.reduce((sum, file) => sum + file.byte_size, 0) !== manifest.total_bytes) return false;
  const releaseRefs = normalizeReleaseRefs(manifest.release_refs, layout);
  if (releaseRefs.some((release) => release.scope_level !== "L1" || (layout && release.standard_domain !== manifest.standard_domain))) return false;
  if (layout) {
    if (Object.keys(manifest.managed_file_releases).length !== uniquePaths.size) return false;
    const derived = localFilesForBundle({ snapshot: { resolver_version: LAYOUT_BUNDLE_SCHEMA, release_refs: releaseRefs }, files: projection }, { indexPlacement: "separate" });
    if (derived.some((file) => !uniquePaths.has(file.local_relative_path) || manifest.managed_file_sources[file.local_relative_path] !== file.relative_path)) return false;
  }
  const indexCapable = manifest.schema_version === LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA
    || (manifest.schema_version === AGENTS_BOOTSTRAP_MANIFEST_SCHEMA && !layout);
  if (indexCapable ? !validateOptionalAgentsManifest(manifest, !layout) : hasAgentsManifestFields(manifest)) return false;
  return sha256Hex(canonicalJson({
    bootstrap_version: manifest.bundle_schema,
    standard_domain: manifest.standard_domain,
    manifest_hash: manifest.manifest_hash,
    ...(manifest.agents_indexes_hash ? { agents_indexes_hash: manifest.agents_indexes_hash } : {}),
    release_refs: releaseRefs,
    ...(stage ? { stage, dependency_hash: manifest.dependency_hash } : {}),
  })) === manifest.snapshot_id;
};

const validateBootstrapManifestFiles = async (repoRoot, manifest) => {
  if (!validateBootstrapManifestStructure(manifest)) return false;
  const rulesRoot = path.join(repoRoot, ".mdp", "rules");
  for (const managedPath of manifest.managed_files) {
    const fullPath = path.join(rulesRoot, ...managedPath.split("/"));
    await assertNoSymlink(fullPath, rulesRoot);
    if (!await exists(fullPath)) return false;
    const content = await readFile(fullPath);
    if (sha256Hex(content) !== manifest.managed_file_hashes[managedPath]
      || content.byteLength !== manifest.managed_file_sizes[managedPath]) return false;
  }
  return validateLocalAgentsIndexFiles(rulesRoot, manifest);
};

const buildLocalManifest = (bundle) => {
  const domain = bundle.snapshot.repository.standard_domain;
  const localFiles = localFilesForBundle(bundle);
  const managedFiles = localFiles.map((file) => file.local_relative_path);
  return {
    schema_version: LAYOUT_LOCAL_MANIFEST_SCHEMA,
    local_layout: LOCAL_LAYOUT,
    resolver_version: bundle.snapshot.resolver_version || LEGACY_BUNDLE_SCHEMA,
    snapshot_id: bundle.snapshot.snapshot_id,
    manifest_hash: bundle.snapshot.manifest_hash,
    repository: {
      repository_id: bundle.snapshot.repository.repository_id,
      canonical_key: bundle.snapshot.repository.canonical_key,
      standard_domain: domain,
    },
    standard_domain: domain,
    stage: bundle.snapshot.stage || null,
    ...(bundle.snapshot.dependency_hash
      ? { dependency_hash: bundle.snapshot.dependency_hash }
      : {}),
    release_refs: bundle.snapshot.release_refs,
    total_bytes: bundle.snapshot.total_bytes,
    managed_files: managedFiles,
    managed_file_releases: Object.fromEntries(localFiles.map((file) => [
      file.local_relative_path, { rule_set_id: file.rule_set_id, release_id: file.release_id },
    ])),
    managed_file_sources: Object.fromEntries(localFiles.map((file) => [
      file.local_relative_path,
      file.source_relative_path,
    ])),
    managed_file_hashes: Object.fromEntries(localFiles.map((file) => [
      file.local_relative_path,
      file.sha256,
    ])),
    managed_file_sizes: Object.fromEntries(localFiles.map((file) => [
      file.local_relative_path,
      file.byte_size,
    ])),
    ...agentsManifestFields(bundle, localFiles, { indexPlacement: "named-team" }),
    installed_at: new Date().toISOString(),
  };
};

const buildBootstrapManifest = (bundle, domainSource, domainEvidence) => {
  const localFiles = localFilesForBundle({
    ...bundle,
    snapshot: {
      ...bundle.snapshot,
      resolver_version: LAYOUT_BUNDLE_SCHEMA,
      repository: { standard_domain: bundle.snapshot.standard_domain },
    },
  }, { indexPlacement: "separate" });
  const managedFiles = localFiles.map((file) => file.local_relative_path);
  return {
    schema_version: LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA,
    bundle_schema: bundle.snapshot.bootstrap_version,
    local_layout: LOCAL_LAYOUT,
    snapshot_id: bundle.snapshot.snapshot_id,
    manifest_hash: bundle.snapshot.manifest_hash,
    standard_domain: bundle.snapshot.standard_domain,
    stage: bundle.snapshot.stage || null,
    ...(bundle.snapshot.dependency_hash
      ? { dependency_hash: bundle.snapshot.dependency_hash }
      : {}),
    domain_source: domainSource,
    domain_evidence: domainEvidence,
    release_refs: bundle.snapshot.release_refs,
    total_bytes: bundle.snapshot.total_bytes,
    managed_files: managedFiles,
    managed_file_releases: Object.fromEntries(localFiles.map((file) => [
      file.local_relative_path, { rule_set_id: file.rule_set_id, release_id: file.release_id },
    ])),
    managed_file_sources: Object.fromEntries(localFiles.map((file) => [
      file.local_relative_path, file.source_relative_path,
    ])),
    managed_file_hashes: Object.fromEntries(localFiles.map((file) => [
      file.local_relative_path, file.sha256,
    ])),
    managed_file_sizes: Object.fromEntries(localFiles.map((file) => [
      file.local_relative_path, file.byte_size,
    ])),
    ...agentsManifestFields(bundle, localFiles, { indexPlacement: "separate" }),
    installed_at: new Date().toISOString(),
  };
};

// Resolve portable aliases before writing, including on case-sensitive systems.
// Never traverse a symlink or choose between multiple normalization-equivalent names.
const directoryContainsOnlyManagedFiles = async (directory, relativePath, managed, cache, normalize) => {
  const prefix = `${normalize(relativePath)}/`;
  if (![...managed].some((name) => normalize(name).startsWith(prefix))) return false;
  if (!cache.has(directory)) cache.set(directory, await readdir(directory, { withFileTypes: true }));
  for (const entry of cache.get(directory)) {
    const child = `${relativePath}/${entry.name}`;
    if (entry.isDirectory()) {
      if (!await directoryContainsOnlyManagedFiles(path.join(directory, entry.name), child, managed, cache, normalize)) return false;
    } else if (!entry.isFile() || ![...managed].some((name) => normalize(name) === normalize(child))) {
      return false;
    }
  }
  return true;
};

const existingPortablePath = async (domainPath, relativePath, cache, previousManaged) => {
  let parent = domainPath;
  const actual = [];
  const parts = relativePath.split("/");
  for (const [index, part] of parts.entries()) {
    if (!await exists(parent)) return null;
    if (!cache.has(parent)) cache.set(parent, await readdir(parent, { withFileTypes: true }));
    const matches = cache.get(parent).filter((entry) => pathKey(entry.name) === pathKey(part));
    if (matches.length > 1) fail("RULE_BUNDLE_LOCAL_COLLISION", `规则路径存在大小写或 Unicode 重名：${relativePath}`);
    if (!matches.length) return null;
    const entry = matches[0];
    if (entry.isSymbolicLink()) fail("RULE_BUNDLE_LOCAL_SYMLINK", `受管路径不能是符号链接：${relativePath}`);
    if (index < parts.length - 1 && !entry.isDirectory()) fail("RULE_BUNDLE_LOCAL_COLLISION", `规则目录位置已有文件：${relativePath}`);
    if (entry.isDirectory() && entry.name !== part) {
      const nativeAlias = await exists(path.join(parent, part));
      if (entry.name.normalize("NFC") !== part.normalize("NFC") || !nativeAlias) {
        const normalize = nativeAlias ? (value) => value.normalize("NFC") : (value) => value;
        if (!await directoryContainsOnlyManagedFiles(path.join(parent, entry.name), [...actual, entry.name].join("/"), previousManaged, cache, normalize)) {
          fail("RULE_BUNDLE_LOCAL_COLLISION", `目录改名涉及非受管文件，未覆盖：${relativePath}`);
        }
      }
    }
    actual.push(entry.name);
    parent = path.join(parent, entry.name);
  }
  return actual.join("/");
};

const removeEmptyManagedParents = async (filePath, boundary) => {
  let parent = path.dirname(filePath);
  while (parent !== boundary && parent.startsWith(`${boundary}${path.sep}`)) {
    try { await rmdir(parent); } catch (error) {
      if (["ENOTEMPTY", "EEXIST"].includes(error.code)) return;
      if (error.code !== "ENOENT") throw error;
    }
    parent = path.dirname(parent);
  }
};

const agentsReceipt = (manifest) => ({
  managed_agents_indexes: manifest.managed_agents_indexes || [],
  agents_index_warnings: manifest.agents_indexes_hash ? manifest.agents_index_warnings : [{
    code: "agents_index_contract_unavailable",
    message: "服务未返回 AGENTS.md 索引合同，本次未交付规则集索引",
  }],
});

const installReadyBundle = async (repoRoot, bundle, previousManifest, bootstrapManifest = null, resolution = null) => {
  const mdpRoot = path.join(repoRoot, ".mdp");
  const rulesRoot = path.join(repoRoot, ".mdp", "rules");
  const domain = bundle.snapshot.repository.standard_domain;
  await mkdir(mdpRoot, { recursive: true });
  await assertNoSymlink(mdpRoot, repoRoot);
  if (await exists(rulesRoot)) await assertNoSymlink(rulesRoot, mdpRoot);

  // Domain changes are valid only for a verified formal bundle that resolves to
  // the exact repository already recorded in the trusted local manifest.
  if (previousManifest && (
    previousManifest.repository.repository_id !== bundle.snapshot.repository.repository_id
    || previousManifest.repository.canonical_key !== bundle.snapshot.repository.canonical_key
  )) {
    fail(
      "RULE_BUNDLE_REPOSITORY_CONFLICT",
      `输出目录已有仓库 ${previousManifest.repository.canonical_key} 的规则包，不能由 ${bundle.snapshot.repository.canonical_key} 覆盖`,
    );
  }
  const previousManaged = new Set(previousManifest?.managed_files || []);
  const previousPhysicalPaths = new Set([
    ...(previousManifest
      ? [...previousManaged].map((name) => manifestPhysicalPath(previousManifest, name))
      : []),
    ...(bootstrapManifest?.managed_files || []),
    ...(previousManifest?.managed_agents_indexes || []),
    ...(bootstrapManifest?.managed_agents_indexes || []),
  ]);
  const previousManagedNfc = new Set([...previousPhysicalPaths].map((name) => name.normalize("NFC")));
  const localFiles = localFilesForBundle(bundle);
  const indexFiles = renderAgentsIndexes(bundle.agents_indexes, localFiles, bundle.snapshot.release_refs, { indexPlacement: "named-team" }).files;
  const directoryCache = new Map();
  for (const file of [...localFiles, ...indexFiles]) {
    const currentPath = path.join(rulesRoot, ...file.local_relative_path.split("/"));
    await assertNoSymlink(currentPath, rulesRoot);
    const existing = await existingPortablePath(
      rulesRoot,
      file.local_relative_path,
      directoryCache,
      previousPhysicalPaths,
    );
    if (existing && !previousManagedNfc.has(existing.normalize("NFC"))) {
      fail("RULE_BUNDLE_LOCAL_COLLISION", `规则目标路径已有非受管文件，未覆盖：${file.local_relative_path}`);
    }
  }

  const stageRoot = await mkdtemp(path.join(mdpRoot, ".mt-bundle-stage-"));
  const stagedRulesRoot = path.join(stageRoot, "rules");
  const stagedManifest = path.join(stagedRulesRoot, MANIFEST_NAME);
  const backupRulesRoot = path.join(mdpRoot, `.mt-bundle-backup-${randomUUID()}`);
  let rulesBackedUp = false;
  let rulesInstalled = false;
  try {
    if (await exists(rulesRoot)) await cp(rulesRoot, stagedRulesRoot, { recursive: true, errorOnExist: false });
    else await mkdir(stagedRulesRoot, { recursive: true });

    for (const managedPath of previousManaged) {
      const relativePath = manifestPhysicalPath(previousManifest, managedPath);
      const stagedOldPath = path.join(stagedRulesRoot, ...relativePath.split("/"));
      await assertNoSymlink(stagedOldPath, stagedRulesRoot);
      await rm(stagedOldPath, { force: true });
      await removeEmptyManagedParents(stagedOldPath, stagedRulesRoot);
    }
    for (const managedPath of bootstrapManifest?.managed_files || []) {
      const stagedOldPath = path.join(stagedRulesRoot, ...managedPath.split("/"));
      await assertNoSymlink(stagedOldPath, stagedRulesRoot);
      await rm(stagedOldPath, { force: true });
      await removeEmptyManagedParents(stagedOldPath, stagedRulesRoot);
    }
    for (const name of [...(previousManifest?.managed_agents_indexes || []), ...(bootstrapManifest?.managed_agents_indexes || [])]) {
      const oldPath = path.join(stagedRulesRoot, ...name.split("/"));
      await assertNoSymlink(oldPath, stagedRulesRoot);
      await rm(oldPath, { force: true });
      await removeEmptyManagedParents(oldPath, stagedRulesRoot);
    }
    await rm(path.join(stagedRulesRoot, BOOTSTRAP_MANIFEST_NAME), { force: true });
    for (const file of [...localFiles, ...indexFiles]) {
      const outputPath = path.join(stagedRulesRoot, ...file.local_relative_path.split("/"));
      await assertNoSymlink(outputPath, stagedRulesRoot);
      await mkdir(path.dirname(outputPath), { recursive: true });
      await writeFile(outputPath, file.content, "utf8");
    }
    const manifest = { ...buildLocalManifest(bundle), ...(resolution ? { schema_version: UNIFIED_LOCAL_SCHEMA, resolution, resolution_hash: resolutionDigest(resolution, bundle.snapshot.snapshot_id) } : {}) };
    await writeFile(stagedManifest, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

    if (await exists(rulesRoot)) {
      await rename(rulesRoot, backupRulesRoot);
      rulesBackedUp = true;
    }
    await rename(stagedRulesRoot, rulesRoot);
    rulesInstalled = true;
    await rm(backupRulesRoot, { recursive: true, force: true }).catch(() => {});
    return manifest;
  } catch (error) {
    try {
      if (rulesInstalled) await rm(rulesRoot, { recursive: true, force: true });
      if (rulesBackedUp && await exists(backupRulesRoot)) await rename(backupRulesRoot, rulesRoot);
    } catch (rollbackError) {
      fail(
        "RULE_BUNDLE_LOCAL_ROLLBACK_FAILED",
        `规则包安装失败且回滚失败：${error.message}；${rollbackError.message}`,
      );
    }
    throw error;
  } finally {
    await rm(stageRoot, { recursive: true, force: true }).catch(() => {});
  }
};

const installBootstrapBundle = async ({
  repoRoot, bundle, previousManifest, domainSource, domainEvidence, formalManifest = null, resolution = null,
}) => {
  const mdpRoot = path.join(repoRoot, ".mdp");
  const rulesRoot = path.join(mdpRoot, "rules");
  await mkdir(mdpRoot, { recursive: true });
  await assertNoSymlink(mdpRoot, repoRoot);
  if (await exists(rulesRoot)) await assertNoSymlink(rulesRoot, mdpRoot);
  if (previousManifest?.standard_domain
    && previousManifest.standard_domain !== bundle.snapshot.standard_domain) {
    fail(
      "RULE_BUNDLE_DOMAIN_CHANGED",
      `本地 L1 bootstrap 领域为 ${previousManifest.standard_domain}，本次判断为 ${bundle.snapshot.standard_domain}`,
    );
  }
  const localFiles = localFilesForBundle({
    ...bundle,
    snapshot: {
      ...bundle.snapshot,
      resolver_version: LAYOUT_BUNDLE_SCHEMA,
      repository: { standard_domain: bundle.snapshot.standard_domain },
    },
  }, { indexPlacement: "separate" });
  const indexFiles = renderAgentsIndexes(bundle.agents_indexes, localFiles, bundle.snapshot.release_refs, { indexPlacement: "separate" }).files;
  const previousManaged = new Set([...(previousManifest?.managed_files || []), ...(previousManifest?.managed_agents_indexes || []),
    ...(formalManifest?.managed_files || []).map(name => manifestPhysicalPath(formalManifest, name)),
    ...(formalManifest?.managed_agents_indexes || []),
  ]);
  const previousManagedKeys = new Set([...previousManaged].map(pathKey));
  const directoryCache = new Map();
  for (const file of [...localFiles, ...indexFiles]) {
    const currentPath = path.join(rulesRoot, ...file.local_relative_path.split("/"));
    await assertNoSymlink(currentPath, rulesRoot);
    const existing = await existingPortablePath(
      rulesRoot,
      file.local_relative_path,
      directoryCache,
      previousManaged,
    );
    if (existing && !previousManagedKeys.has(pathKey(existing))) {
      fail("RULE_BUNDLE_LOCAL_COLLISION", `L1 bootstrap 目标路径已有非受管文件，未覆盖：${file.local_relative_path}`);
    }
  }

  const stageRoot = await mkdtemp(path.join(mdpRoot, ".mt-bootstrap-stage-"));
  const stagedRulesRoot = path.join(stageRoot, "rules");
  const backupRulesRoot = path.join(mdpRoot, `.mt-bootstrap-backup-${randomUUID()}`);
  let rulesBackedUp = false;
  let rulesInstalled = false;
  try {
    if (await exists(rulesRoot)) await cp(rulesRoot, stagedRulesRoot, { recursive: true, errorOnExist: false });
    else await mkdir(stagedRulesRoot, { recursive: true });
    for (const managedPath of previousManaged) {
      const stagedOldPath = path.join(stagedRulesRoot, ...managedPath.split("/"));
      await assertNoSymlink(stagedOldPath, stagedRulesRoot);
      await rm(stagedOldPath, { force: true });
      await removeEmptyManagedParents(stagedOldPath, stagedRulesRoot);
    }
    for (const file of [...localFiles, ...indexFiles]) {
      const outputPath = path.join(stagedRulesRoot, ...file.local_relative_path.split("/"));
      await assertNoSymlink(outputPath, stagedRulesRoot);
      await mkdir(path.dirname(outputPath), { recursive: true });
      await writeFile(outputPath, file.content, "utf8");
    }
    const manifest = { ...buildBootstrapManifest(bundle, domainSource, domainEvidence), ...(resolution ? { schema_version: UNIFIED_L1_LOCAL_SCHEMA, resolution, resolution_hash: resolutionDigest(resolution, bundle.snapshot.snapshot_id) } : {}) };
    if (formalManifest) await rm(path.join(stagedRulesRoot, MANIFEST_NAME), { force: true });
    await writeFile(
      path.join(stagedRulesRoot, BOOTSTRAP_MANIFEST_NAME),
      `${JSON.stringify(manifest, null, 2)}\n`,
      "utf8",
    );
    if (await exists(rulesRoot)) {
      await rename(rulesRoot, backupRulesRoot);
      rulesBackedUp = true;
    }
    await rename(stagedRulesRoot, rulesRoot);
    rulesInstalled = true;
    await rm(backupRulesRoot, { recursive: true, force: true }).catch(() => {});
    return manifest;
  } catch (error) {
    try {
      if (rulesInstalled) await rm(rulesRoot, { recursive: true, force: true });
      if (rulesBackedUp && await exists(backupRulesRoot)) await rename(backupRulesRoot, rulesRoot);
    } catch (rollbackError) {
      fail(
        "RULE_BUNDLE_LOCAL_ROLLBACK_FAILED",
        `L1 bootstrap 安装失败且回滚失败：${error.message}；${rollbackError.message}`,
      );
    }
    throw error;
  } finally {
    await rm(stageRoot, { recursive: true, force: true }).catch(() => {});
  }
};


export const UNIFIED_RESOLVE_SCHEMA = "rule-bundle-resolve/v1";
export const UNIFIED_RESPONSE_SCHEMA = "rule-bundle-resolution/v1";
const UNIFIED_LOCAL_SCHEMA = "mt-effective-rule-bundle-manifest/v8";
const UNIFIED_L1_LOCAL_SCHEMA = "mt-l1-bootstrap-manifest/v5";
const SELECTION_REASONS = new Set(["repository_identity_unavailable", "repository_not_registered", "l2_not_accessible", "no_effective_l2", "repository_effective", "explicit_l1"]);
const safeMetadata = (value, max = 128) => typeof value === "string" && value.trim().length <= max
  && !/[\p{Cc}\p{Cf}]/u.test(value) ? value.trim() || null : null;

export const normalizeUnifiedExecution = (value = {}) => {
  const result = {
    pull_id: text(value.pullId) || randomUUID(),
    execution_agent: text(value.agent) || "unknown",
    execution_agent_source: text(value.source) || "legacy_unknown_v1",
    client_type: value.clientType === "cli" ? "cli" : "skill",
    client_name: safeMetadata(value.clientName),
    client_version: safeMetadata(value.clientVersion),
    skill_name: EXECUTION_SKILL_NAMES.has(value.skillName) ? value.skillName : null,
    skill_version: safeMetadata(value.skillVersion),
  };
  if (!UUID_PATTERN.test(result.pull_id) || !EXECUTION_AGENTS.has(result.execution_agent)
    || !EXECUTION_AGENT_SOURCES.has(result.execution_agent_source)) {
    fail("RULE_BUNDLE_EXECUTION_INVALID", "pull_id、execution_agent 或 execution_agent_source 不合法");
  }
  if (result.client_type === "cli") { result.skill_name = null; result.skill_version = null; }
  return Object.freeze(result);
};

export const prepareUnifiedSyncRequest = async ({ gatewayUrl = DEFAULT_GATEWAY, repositoryLocator,
  repoRoot = "", outputDir = "", cwd = process.cwd(), domain = "", stage, bootstrap = false, execution,
} = {}) => {
  const sourceDirectory = path.resolve(cwd, text(repoRoot) || ".");
  const sourceRoot = repositoryRootFromGit(sourceDirectory) || sourceDirectory;
  const targetRoot = await canonicalizeOutputRoot(path.resolve(cwd, text(outputDir) || text(repoRoot) || "."));
  if (repositoryLocator !== undefined && !text(repositoryLocator)) {
    throw new RuleBundleError("repository_locator_invalid", "显式仓库地址不能为空；请提供完整仓库地址，或省略 --repository 自动定位。", {
      issues: [{ field: "repository_locator", code: "invalid", message: "显式 --repository 不能为空或仅包含空白" }], retryable: false,
    });
  }
  const rawLocator = repositoryLocator === undefined ? repositoryLocatorFromGit(sourceRoot) : text(repositoryLocator);
  let canonicalKey = null;
  if (rawLocator) {
    // An automatically discovered remote is only an identity hint. Never send
    // requests to its host or reinterpret a foreign path as an MCode identity.
    try { canonicalKey = canonicalRepositoryKey(rawLocator) || null; }
    catch { canonicalKey = null; }
    if (!canonicalKey && repositoryLocator !== undefined) throw new RuleBundleError("repository_locator_invalid",
      "仓库地址必须是 namespace/repository 或可归一化的线上 MCode Git 地址。", {
        issues: [{ field: "repository_locator", code: "invalid", message: "请提供完整 namespace/repository 或线上 Git 地址" }], retryable: false,
      });
  }
  const issues = [];
  if (!DELIVERY_STAGES.has(stage)) issues.push({ field: "stage", code: stage == null ? "required" : "invalid", message: "请指定 --stage design、coding 或 cr" });
  const normalizedDomain = text(domain);
  if (normalizedDomain && !DOMAINS.has(normalizedDomain)) issues.push({ field: "standard_domain", code: "invalid", message: "--domain 仅支持 frontend 或 backend" });
  if (!canonicalKey && !normalizedDomain) issues.push({ field: "standard_domain", code: "required", message: "无法确定仓库领域，请指定 --domain frontend 或 backend" });
  if (issues.length) throw new RuleBundleError("rule_parameters_invalid", issues.map(item => item.message).join("；"), { issues, retryable: false });
  const gateway = validateGatewayUrl(gatewayUrl);
  if (new URL(gateway).pathname !== GATEWAY_PATHNAME) throw new RuleBundleError("resolution_contract_not_supported", "统一拉取需要 rule-distribution 网关，请升级服务配置。", { retryable: false });
  return Object.freeze({ gatewayUrl: gateway, repositoryLocator: canonicalKey, sourceRoot, targetRoot,
    domain: normalizedDomain || null, stage, scope: bootstrap ? "l1" : "effective",
    target: { display_name: canonicalKey || sourceRoot, source: canonicalKey ? "repository_locator" : "local_directory" },
    execution: normalizeUnifiedExecution(execution),
  });
};

const resolutionContext = (body, scope, domainSource) => ({
  schema_version: UNIFIED_RESPONSE_SCHEMA, bundle_kind: body.bundle_kind, delivery_mode: body.delivery_mode,
  selection_reason: body.selection_reason, standard_domain: body.standard_domain, stage: body.stage,
  target: body.target, scope, domain_source: domainSource,
});
const resolutionDigest = (resolution, snapshotId) => sha256Hex(canonicalJson({ resolution, snapshot_id: snapshotId }));
const validateResolutionManifest = (manifest) => {
  const r = manifest.resolution;
  return isObject(r) && r.schema_version === UNIFIED_RESPONSE_SCHEMA
    && ["effective", "l1"].includes(r.bundle_kind) && ["l1_only", "l1_l2"].includes(r.delivery_mode)
    && SELECTION_REASONS.has(r.selection_reason) && ["effective", "l1"].includes(r.scope)
    && ["user_explicit", "repository_configuration"].includes(r.domain_source)
    && r.standard_domain === manifest.standard_domain && r.stage === manifest.stage
    && isObject(r.target) && ["platform", "repository_locator", "local_directory"].includes(r.target.source)
    && typeof r.target.display_name === "string" && !!r.target.display_name
    && (r.target.canonical_key === null || typeof r.target.canonical_key === "string")
    && (r.bundle_kind === "effective" ? manifest.repository?.canonical_key === r.target.canonical_key : r.delivery_mode === "l1_only")
    && (manifest.release_refs.some(ref => ref.scope_level === "L2") ? r.delivery_mode === "l1_l2" : r.delivery_mode === "l1_only")
    && manifest.resolution_hash === resolutionDigest(r, manifest.snapshot_id);
};

const serviceErrorDetails = (error) => {
  // Only bounded diagnostic fields cross the CLI boundary; never propagate raw
  // database bodies, credentials, stack traces, or HTML.
  const clean = value => safeMetadata(value, 1000)
    ?.replace(/\bBearer\s+\S+|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)?/gu, "[redacted]")
    .replace(/\b(?:access_token|client_secret|authorization|password)\s*[:=]\s*\S+/giu, "[redacted]");
  const result = { retryable: error?.retryable === true };
  if (/^[A-Za-z0-9._:-]{1,128}$/u.test(error?.request_id || "") && !/^(eyJ|sk-)/u.test(error.request_id)) result.request_id = error.request_id;
  if (Array.isArray(error?.issues)) result.issues = error.issues.slice(0, 20).flatMap(issue => {
    const field = safeMetadata(issue?.field, 100);
    const message = clean(issue?.message);
    return field && /^[a-zA-Z0-9_.[\]-]+$/u.test(field) && message
      ? [{ field, code: /^[a-z][a-z0-9_]{0,99}$/u.test(issue.code || "") ? issue.code : "invalid", message }] : [];
  });
  return { ...result, message: clean(error?.message) };
};

export const syncUnifiedRuleBundle = async ({ gatewayUrl, token, repositoryLocator, repoRoot, outputDir, cwd,
  domain, stage, bootstrap = false, execution, publicPull = false, mis, fetchImpl = globalThis.fetch, requestTransport,
} = {}) => {
  const prepared = await prepareUnifiedSyncRequest({ gatewayUrl, repositoryLocator, repoRoot, outputDir, cwd, domain, stage, bootstrap, execution });
  if (!publicPull && !token && !requestTransport) fail("RULE_BUNDLE_AUTH_REQUIRED", "认证拉取需要有效用户票据");
  const declaredActor = publicPull ? text(mis) : "";
  if (declaredActor && !/^[a-z][a-z0-9._-]{0,63}$/u.test(declaredActor)) throw new RuleBundleError("declared_actor_invalid", "自报调用方格式错误：应为 1–64 位小写字母、数字、点、下划线或连字符，以字母开头。", { retryable: false });
  const root = prepared.targetRoot;
  const formalExists = await exists(path.join(root, ".mdp", "rules", MANIFEST_NAME));
  const formal = await readLocalManifest(root);
  const baselineState = await readBootstrapManifest(root);
  const baseline = baselineState.value;
  if (formalExists && !await Promise.resolve().then(() => validateLocalManifestStructure(formal)).catch(() => false)) fail("RULE_BUNDLE_LOCAL_MANIFEST_INVALID", "本地正式规则清单非法，未修改现有文件");
  if (baselineState.exists && !await Promise.resolve().then(() => validateBootstrapManifestStructure(baseline)).catch(() => false)) fail("RULE_BUNDLE_BOOTSTRAP_MANIFEST_INVALID", "本地 L1 规则清单非法，未修改现有文件");
  if ((formal && !await validateLocalManifestFiles(root, formal).catch(() => false))
    || (baseline && !await validateBootstrapManifestFiles(root, baseline).catch(() => false))) fail("RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED", "本地受管文件缺失或已修改，未覆盖文件");
  if (formal && baseline) fail("RULE_BUNDLE_LOCAL_MANIFEST_INVALID", "本地同时存在两份规则清单，请先处理冲突");
  const previous = formal || baseline;
  const previousCanonical = formal?.repository.canonical_key || baseline?.resolution?.target.canonical_key;
  if (previousCanonical && previousCanonical !== prepared.repositoryLocator) fail("RULE_BUNDLE_REPOSITORY_CONFLICT", "当前请求无法确认与本地规则相同的仓库身份，未覆盖现有规则");
  if (!previousCanonical && baseline?.resolution?.target.source === "local_directory"
    && baseline.resolution.target.display_name !== prepared.sourceRoot) fail("RULE_BUNDLE_REPOSITORY_CONFLICT", "本地规则属于其他来源目录，未覆盖现有规则");
  const known = previous && validateResolutionManifest(previous)
    && previous.stage === stage && (!prepared.domain || previous.standard_domain === prepared.domain)
    && previous.resolution.scope === prepared.scope
    && previous.resolution.target.canonical_key === prepared.repositoryLocator
    ? { bundle_kind: previous.resolution.bundle_kind, snapshot_id: previous.snapshot_id } : null;
  const body = {
    schema_version: UNIFIED_RESOLVE_SCHEMA, repository_locator: prepared.repositoryLocator,
    ...(prepared.domain ? { standard_domain: prepared.domain } : {}), stage,
    scope: prepared.scope, bundle_contract: LOCAL_LAYOUT, agents_index_contract: AGENTS_INDEX_CONTRACT,
    target: prepared.target, execution: prepared.execution,
    ...(known ? { known_snapshot: known } : {}),
    ...(declaredActor ? { declared_actor: declaredActor } : {}),
  };
  const result = await serviceRequest({ gatewayUrl: prepared.gatewayUrl, token,
    resourcePath: publicPull ? "/v1/public/rule-bundles/resolve" : "/v1/rule-bundles/resolve",
    body, fetchImpl, requestTransport, serviceLabel: "统一规范服务", publicRequest: publicPull });
  if (!result.ok) {
    const error = result.body?.error;
    const details = serviceErrorDetails(error);
    const unsupported = result.status === 404 && (!error?.code || error.code === "not_found");
    const code = unsupported ? "resolution_contract_not_supported"
      : /^[a-z][a-z0-9_]{0,99}$/u.test(error?.code || "") ? error.code : `RULE_BUNDLE_HTTP_${result.status}`;
    throw new RuleBundleError(code, unsupported ? "当前服务尚不支持统一规范拉取，请升级 rule-distribution；本地规则未修改。"
      : details.message || "规则服务返回异常，请凭请求编号排查。", details);
  }
  const resolved = result.body;
  if (!isObject(resolved) || resolved.schema_version !== UNIFIED_RESPONSE_SCHEMA
    || !["effective", "l1"].includes(resolved.bundle_kind)
    || !["l1_only", "l1_l2"].includes(resolved.delivery_mode)
    || !SELECTION_REASONS.has(resolved.selection_reason)
    || resolved.pull_id !== prepared.execution.pull_id
    || !/^[A-Za-z0-9._:-]{1,128}$/u.test(resolved.request_id || "")
    || !DOMAINS.has(resolved.standard_domain) || resolved.stage !== stage
    || (prepared.domain && resolved.standard_domain !== prepared.domain)
    || !isObject(resolved.target) || resolved.target.canonical_key !== prepared.repositoryLocator
    || !["platform", "repository_locator", "local_directory"].includes(resolved.target.source)
    || !safeMetadata(resolved.target.display_name, 4096)
    || (resolved.target.source === "local_directory" && resolved.target.display_name !== prepared.sourceRoot)) {
    fail("RULE_BUNDLE_RESOLUTION_INVALID", "统一规范响应身份、领域、阶段或请求标识不一致，本地规则未修改");
  }
  assertRuleResponseBudget(resolved.bundle, { allowAgentsIndexes: true, serviceLabel: "统一规范内包" });
  const matchingKnown = known?.bundle_kind === resolved.bundle_kind ? known.snapshot_id : "";
  const bundle = resolved.bundle_kind === "effective"
    ? validateBundle(resolved.bundle, matchingKnown, stage, true)
    : validateBootstrapBundle(resolved.bundle, matchingKnown, stage, true);
  const refs = bundle.snapshot.release_refs;
  if (!refs.some(ref => ref.scope_level === "L1")
    || (refs.some(ref => ref.scope_level === "L2") ? "l1_l2" : "l1_only") !== resolved.delivery_mode
    || (prepared.scope === "l1" && resolved.delivery_mode !== "l1_only")
    || (resolved.bundle_kind === "l1" && (resolved.delivery_mode !== "l1_only" || bundle.snapshot.standard_domain !== resolved.standard_domain))
    || (resolved.bundle_kind === "effective" && (bundle.snapshot.repository.canonical_key !== resolved.target.canonical_key
      || bundle.snapshot.repository.standard_domain !== resolved.standard_domain))) fail("RULE_BUNDLE_RESOLUTION_INVALID", "分发模式与实际规则包不一致，本地规则未修改");
  const context = resolutionContext(resolved, prepared.scope, prepared.domain ? "user_explicit" : "repository_configuration");
  let manifest;
  if (bundle.status === "not_modified") {
    if (!previous || previous.resolution.bundle_kind !== context.bundle_kind
      || previous.resolution.delivery_mode !== context.delivery_mode
      || previous.resolution.standard_domain !== context.standard_domain
      || previous.resolution.stage !== context.stage || previous.resolution.scope !== context.scope
      || previous.resolution.target.canonical_key !== context.target.canonical_key) {
      fail("RULE_BUNDLE_NOT_MODIFIED_INVALID", "缓存分发身份、模式、领域或阶段不一致，本地规则未修改");
    }
    manifest = previous;
    if (canonicalJson(previous.resolution) !== canonicalJson(context)) {
      manifest = { ...previous, ...(baseline ? { domain_source: context.domain_source } : {}), resolution: context, resolution_hash: resolutionDigest(context, previous.snapshot_id) };
      const rulesRoot = path.join(root, ".mdp", "rules");
      const filename = path.join(rulesRoot, formal ? MANIFEST_NAME : BOOTSTRAP_MANIFEST_NAME);
      const temporary = path.join(rulesRoot, `.mt-resolution-${randomUUID()}.tmp`);
      await assertNoSymlink(filename, rulesRoot);
      try {
        await writeFile(temporary, `${JSON.stringify(manifest, null, 2)}\n`, { encoding: "utf8", flag: "wx" });
        await rename(temporary, filename);
      } finally { await rm(temporary, { force: true }); }
    }
  } else if (resolved.bundle_kind === "effective") {
    manifest = await installReadyBundle(root, bundle, formal, baseline, context);
  } else {
    manifest = await installBootstrapBundle({ repoRoot: root, bundle, previousManifest: baseline,
      formalManifest: formal, domainSource: context.domain_source, domainEvidence: {}, resolution: context });
  }
  return Object.freeze({ local_layout: LOCAL_LAYOUT,
    status: bundle.status === "ready" ? "installed" : "not_modified",
    ...context, schema_version: "mt-rule-bundle-install/v1", request_id: resolved.request_id,
    pull_id: prepared.execution.pull_id, execution_agent: prepared.execution.execution_agent,
    snapshot_id: manifest.snapshot_id, release_refs: refs, managed_files: manifest.managed_files,
    ...agentsReceipt(manifest), total_bytes: manifest.total_bytes,
    removed_l2_files: formal && resolved.delivery_mode === "l1_only"
      ? formal.managed_files.filter(name => name.startsWith("team/")).length : 0,
  });
};

export const syncEffectiveRuleBundle = async ({
  gatewayUrl = DEFAULT_GATEWAY,
  token,
  repositoryLocator = "",
  repoRoot = "",
  outputDir = "",
  cwd = process.cwd(),
  domain = "",
  bootstrap = false,
  stage,
  execution,
  fetchImpl = globalThis.fetch,
  requestTransport,
  publicPull = false,
  mis,
} = {}) => {
  const declaredActor = text(mis);
  if (bootstrap && !/^[a-z][a-z0-9._-]{0,63}$/.test(declaredActor)) {
    fail("RULE_BUNDLE_BOOTSTRAP_MIS_REQUIRED", "L1 引导安装需要 --mis 自报调用方（个人 MIS 或机器人名称，如 aicr-agent；1–64 位小写字母、数字、点、下划线或连字符，以字母开头）。该值不作为认证身份。");
  }
  const prepared = await prepareSyncRequest({
    gatewayUrl, repositoryLocator, repoRoot, outputDir, cwd, domain, bootstrap, stage, execution,
  });
  if (!bootstrap && !publicPull && !token && !requestTransport) {
    fail(
      "RULE_BUNDLE_AUTH_REQUIRED",
      "缺少 MTSSO 官方短期用户票据；禁止使用 Cookie、Git 作者、系统账号或把令牌写入文件",
    );
  }
  const publicCanonicalKey = publicPull ? canonicalRepositoryKey(prepared.repositoryLocator) : "";
  if (publicPull && !publicCanonicalKey) {
    fail(
      "RULE_BUNDLE_PUBLIC_CANONICAL_REQUIRED",
      "public 模式必须提供精确 namespace/repository 或可归一化为该形式的线上 MCode Git 地址，不能使用裸仓库名",
    );
  }
  const absoluteRoot = prepared.targetRoot;
  const deliveryStage = prepared.stage;
  const normalizedExecution = prepared.execution;
  const locator = publicPull ? publicCanonicalKey : prepared.repositoryLocator;
  const previousManifestExists = await exists(path.join(absoluteRoot, ".mdp", "rules", MANIFEST_NAME));
  const previousManifest = await readLocalManifest(absoluteRoot);
  const bootstrapState = await readBootstrapManifest(absoluteRoot);
  let bootstrapManifest = null;
  if (bootstrapState.exists) {
    try {
      if (validateBootstrapManifestStructure(bootstrapState.value)) {
        bootstrapManifest = bootstrapState.value;
      }
    } catch {
      bootstrapManifest = null;
    }
    if (!bootstrapManifest) {
      fail("RULE_BUNDLE_BOOTSTRAP_MANIFEST_INVALID", "本地 L1 bootstrap manifest 非法，禁止静默覆盖");
    }
    if (!await validateBootstrapManifestFiles(absoluteRoot, bootstrapManifest).catch(() => false)) {
      fail("RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED", "本地 L1 bootstrap 受管文件缺失或已修改，禁止覆盖");
    }
  }
  if (bootstrapManifest && !await validateBootstrapManifestFiles(absoluteRoot, bootstrapManifest).catch(() => false)) {
    fail("RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED", "本地受管 L1 bootstrap 文件缺失或已被修改，禁止覆盖；请先恢复受管文件后重试");
  }
  const previousTrusted = (() => {
    try {
      return validateLocalManifestStructure(previousManifest);
    } catch {
      return false;
    }
  })();
  const previousCurrent = previousTrusted
    ? await validateLocalManifestFiles(absoluteRoot, previousManifest).catch(() => false)
    : false;
  if (previousManifestExists && !previousTrusted) {
    fail(
      "RULE_BUNDLE_LOCAL_MANIFEST_INVALID",
      "本地正式规则包 manifest 非法，禁止静默覆盖；请先恢复或移走现有 .mdp/rules 目录",
    );
  }
  if (previousTrusted && !previousCurrent) {
    fail(
      "RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED",
      "本地受管规则文件缺失或已被修改，禁止覆盖；请先恢复受管文件或移走现有 .mdp/rules 目录",
    );
  }
  // A verified legacy tree must be fetched once more so it can be migrated to
  // the scope/domain/rule-set-name layout; only the current layout may receive a
  // not_modified response without rewriting local files.
  const previousStage = previousManifest?.schema_version === LAYOUT_LOCAL_MANIFEST_SCHEMA
    ? text(previousManifest.stage)
    : "";
  const knownSnapshotId = previousCurrent && previousManifest?.schema_version === LAYOUT_LOCAL_MANIFEST_SCHEMA
    && previousStage === deliveryStage
    ? previousManifest.snapshot_id
    : "";
  if (prepared.bootstrap) {
    const canonicalKey = canonicalRepositoryKey(locator);
    if (!canonicalKey) {
      fail(
        "RULE_BUNDLE_BOOTSTRAP_CANONICAL_REQUIRED",
        "仓库未登记时必须提供精确 namespace/repository 或可归一化为该形式的 Git URL，不能用裸仓库名执行 L1 bootstrap",
      );
    }
    if (await exists(path.join(absoluteRoot, ".mdp", "rules", MANIFEST_NAME))) {
      fail(
        "RULE_BUNDLE_BOOTSTRAP_CONFLICT",
        "本地已有正式规则包 manifest，禁止以 L1 bootstrap 静默覆盖；请先处理仓库登记或关联状态",
      );
    }
    const explicitDomain = prepared.domain;
    const detected = explicitDomain
      ? { classification: explicitDomain, evidence: { explicit_domain: explicitDomain } }
      : await detectRepositoryDomain(prepared.sourceRoot);
    if (!DOMAINS.has(detected.classification)) {
      fail(
        "RULE_BUNDLE_DOMAIN_CONFIRMATION_REQUIRED",
        `无法唯一判断仓库领域（${detected.classification}）；请根据以下 Git 已跟踪证据询问用户，并使用 --domain frontend|backend 重试：${JSON.stringify(detected.evidence)}`,
      );
    }
    const bootstrapCurrent = bootstrapManifest
      ? await validateBootstrapManifestFiles(absoluteRoot, bootstrapManifest).catch(() => false)
      : false;
    const bootstrapStage = bootstrapManifest?.schema_version === LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA
      ? text(bootstrapManifest.stage)
      : "";
    const bootstrapKnownSnapshotId = bootstrapCurrent && bootstrapManifest?.schema_version === LAYOUT_BOOTSTRAP_LOCAL_MANIFEST_SCHEMA && bootstrapStage === deliveryStage
      ? bootstrapManifest.snapshot_id
      : "";
    const bootstrapBody = await requestBootstrapBundle({
      gatewayUrl,
      mis: declaredActor,
      execution: normalizedExecution,
      canonicalKey,
      standardDomain: detected.classification,
      knownSnapshotId: bootstrapKnownSnapshotId,
      stage: deliveryStage,
      fetchImpl,
      requestTransport,
    });
    const bootstrapBundle = validateBootstrapBundle(
      bootstrapBody,
      bootstrapKnownSnapshotId,
      deliveryStage,
      true,
    );
    const installedManifest = bootstrapBundle.status === "ready"
      ? await installBootstrapBundle({
        repoRoot: absoluteRoot,
        bundle: bootstrapBundle,
        previousManifest: bootstrapManifest,
        domainSource: explicitDomain ? "user_explicit" : "git_tracked_evidence",
        domainEvidence: detected.evidence,
      })
      : bootstrapManifest;
    return Object.freeze({
      schema_version: BOOTSTRAP_RECEIPT_SCHEMA,
      local_layout: LOCAL_LAYOUT,
      status: bootstrapBundle.status === "ready" ? "installed" : "not_modified",
      mode: "l1_bootstrap",
      declared_actor: declaredActor,
      actor_source: "self_reported",
      standard_domain: bootstrapBundle.snapshot.standard_domain,
      domain_source: installedManifest.domain_source,
      snapshot_id: bootstrapBundle.snapshot.snapshot_id,
      release_refs: bootstrapBundle.snapshot.release_refs,
      managed_files: installedManifest.managed_files,
      ...agentsReceipt(installedManifest),
      total_bytes: installedManifest.total_bytes,
      pull_id: normalizedExecution.pullId,
      execution_agent: normalizedExecution.agent,
      ...(deliveryStage ? { stage: deliveryStage } : {}),
    });
  }
  const body = await requestBundle({
    gatewayUrl, token, repositoryLocator: locator, knownSnapshotId,
    stage: deliveryStage, execution: normalizedExecution, fetchImpl, requestTransport,
    publicRequest: publicPull,
  });
  const bundle = validateBundle(body, knownSnapshotId, deliveryStage, true);
  if (previousTrusted && (
    previousManifest.repository.repository_id !== bundle.snapshot.repository.repository_id
    || previousManifest.repository.canonical_key !== bundle.snapshot.repository.canonical_key
  )) {
    fail(
      "RULE_BUNDLE_REPOSITORY_CONFLICT",
      `输出目录已有仓库 ${previousManifest.repository.canonical_key} 的规则包，不能由 ${bundle.snapshot.repository.canonical_key} 覆盖`,
    );
  }
  const manifest = bundle.status === "ready"
    ? await installReadyBundle(
      absoluteRoot,
      bundle,
      previousTrusted ? previousManifest : null,
      bootstrapManifest,
    )
    : previousManifest;
  return Object.freeze({
    schema_version: RECEIPT_SCHEMA,
    local_layout: LOCAL_LAYOUT,
    status: bundle.status === "ready" ? "installed" : "not_modified",
    repository: bundle.snapshot.repository,
    snapshot_id: bundle.snapshot.snapshot_id,
    release_refs: bundle.snapshot.release_refs,
    managed_files: manifest.managed_files,
    ...agentsReceipt(manifest),
    total_bytes: manifest.total_bytes,
    pull_id: normalizedExecution.pullId,
    execution_agent: normalizedExecution.agent,
    ...(deliveryStage ? { stage: deliveryStage } : {}),
  });
};

const parseArgs = (argv) => {
  const result = {};
  const valued = new Set([
    "--repository", "--repo-root", "--output-dir", "--gateway-url", "--token-env", "--pull-id",
    "--execution-agent", "--execution-agent-source", "--skill-version", "--domain", "--stage", "--mis",
  ]);
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (key === "--bootstrap") {
      result.bootstrap = true;
      continue;
    }
    if (!valued.has(key) || index + 1 >= argv.length) {
      fail("RULE_BUNDLE_ARGUMENT_INVALID", `未知或缺值参数：${key}`);
    }
    const value = argv[index + 1];
    if (key === "--repository") result.repositoryLocator = value;
    else if (key === "--repo-root") result.repoRoot = value;
    else if (key === "--output-dir") result.outputDir = value;
    else if (key === "--gateway-url") result.gatewayUrl = value;
    else if (key === "--token-env") result.tokenEnv = value;
    else if (key === "--mis") result.mis = value;
    else if (key === "--pull-id") result.pullId = value;
    else if (key === "--execution-agent") result.executionAgent = value;
    else if (key === "--execution-agent-source") result.executionAgentSource = value;
    else if (key === "--skill-version") result.skillVersion = value;
    else if (key === "--domain") result.domain = value;
    else if (key === "--stage") result.stage = value;
    index += 1;
  }
  return result;
};

const main = async () => {
  const args = parseArgs(process.argv.slice(2));
  const tokenEnv = args.tokenEnv || "RULE_OBSERVABILITY_USER_TOKEN";
  const receipt = await syncEffectiveRuleBundle({
    gatewayUrl: args.gatewayUrl,
    token: process.env[tokenEnv],
    repositoryLocator: args.repositoryLocator,
    repoRoot: args.repoRoot,
    outputDir: args.outputDir,
    domain: args.domain,
    bootstrap: args.bootstrap,
    mis: args.mis,
    stage: args.stage,
    execution: {
      pullId: args.pullId,
      agent: args.executionAgent,
      source: args.executionAgentSource,
      skillVersion: args.skillVersion,
    },
  });
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
