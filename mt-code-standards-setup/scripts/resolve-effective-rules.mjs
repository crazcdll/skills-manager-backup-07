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
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_GATEWAY =
  "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability";
const GATEWAY_HOSTNAME = "db0y7dgg85gphojyva.database.sankuai.com";
const GATEWAY_PATHNAME = "/functions/v1/rule-observability";
const LEGACY_BUNDLE_SCHEMA = "effective-rule-bundle/v1";
const BUNDLE_SCHEMA = "effective-rule-bundle/v2";
const LEGACY_LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v1";
const LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v2";
const FLAT_LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v3";
const FLAT_LOCAL_LAYOUT = "company-team/v1";
const RECEIPT_SCHEMA = "mt-effective-rule-bundle-install/v1";
const MANIFEST_NAME = ".mt-effective-rule-bundle.json";
const MAX_LOCATOR_BYTES = 8 * 1024;
const MAX_RESPONSE_BYTES = 4 * 1024 * 1024;
const MAX_FILE_BYTES = 512 * 1024;
const SHA256_PATTERN = /^[a-f0-9]{64}$/;
const DOMAINS = new Set(["frontend", "backend"]);
export const EXECUTION_AGENTS = new Set([
  "catdesk", "catpaw", "claude", "codex", "agent_1024", "sandbox", "catx", "unknown",
]);
const EXECUTION_AGENT_SOURCES = new Set([
  "runner_explicit_v1", "runner_heuristic_v1", "legacy_unknown_v1",
]);
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const pathKey = (value) => value.normalize("NFC").toUpperCase().toLowerCase().normalize("NFC");
const binaryPathOrder = (left, right) => left < right ? -1 : left > right ? 1 : 0;

export class RuleBundleError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "RuleBundleError";
    this.code = code;
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
  if (!source || Buffer.byteLength(source, "utf8") > MAX_LOCATOR_BYTES || /[\0\r\n]/.test(source)) {
    fail("RULE_BUNDLE_REPOSITORY_INVALID", "仓库地址为空、过长或包含非法字符");
  }
  const suffixIndex = source.search(/[?#]/);
  return suffixIndex < 0 ? source : source.slice(0, suffixIndex);
};

/**
 * Validate only the supported locator shapes. Repository identity is resolved
 * by the platform, so the original value (including query/hash) is preserved.
 */
export const validateRepositoryLocator = (value) => {
  const source = text(value);
  const main = locatorMainPart(source);
  if (/(?:^|[/:])[.]{1,2}(?:[/]|$)/.test(main)) {
    fail("RULE_BUNDLE_REPOSITORY_INVALID", "仓库地址不能包含相对路径片段");
  }
  const atom = "[A-Za-z0-9._~-]+";
  const repository = "[A-Za-z0-9._-]+";
  const patterns = [
    new RegExp(`^https://dev[.]sankuai[.]com/code/repo-detail/${atom}/${repository}(?:/file/list)?/?$`),
    new RegExp(`^https://git[.]sankuai[.]com/${atom}/${repository}(?:[.]git)?/?$`),
    new RegExp(`^ssh://git@git[.]sankuai[.]com/${atom}/${repository}(?:[.]git)?/?$`),
    new RegExp(`^git@git[.]sankuai[.]com:${atom}/${repository}(?:[.]git)?$`),
    new RegExp(`^${atom}/${repository}$`),
    new RegExp(`^${repository}$`),
  ];
  if (!patterns.some((pattern) => pattern.test(main))) {
    fail(
      "RULE_BUNDLE_REPOSITORY_INVALID",
      "仓库仅支持 Code HTTPS、ssh://、git@...:、namespace/repository 或唯一仓库名",
    );
  }
  return source;
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
  if (normalized.includes("forbidden") || normalized.includes("not_associated")) {
    return "当前用户所属组织未关联该仓库，禁止下载规则；请先完成组织与仓库关联";
  }
  return text(message) || "规则包服务调用失败";
};

const validateGatewayUrl = (value) => {
  let url;
  try {
    url = new URL(value);
  } catch {
    fail("RULE_BUNDLE_GATEWAY_INVALID", "规则包网关地址非法");
  }
  if (
    url.protocol !== "https:"
    || url.hostname !== GATEWAY_HOSTNAME
    || url.pathname.replace(/\/$/, "") !== GATEWAY_PATHNAME
    || url.username
    || url.password
    || url.search
    || url.hash
  ) {
    fail("RULE_BUNDLE_GATEWAY_INVALID", "规则包只允许调用受信任的业务研发平台网关");
  }
  return `${url.origin}${GATEWAY_PATHNAME}`;
};

export const normalizePullExecution = (value = {}) => {
  const pullId = text(value.pullId) || randomUUID();
  const agent = text(value.agent) || "unknown";
  const source = text(value.source) || "legacy_unknown_v1";
  const skillName = text(value.skillName) || "mt-code-standards-setup";
  const skillVersion = text(value.skillVersion) || null;
  if (!UUID_PATTERN.test(pullId) || !EXECUTION_AGENTS.has(agent)
    || !EXECUTION_AGENT_SOURCES.has(source) || skillName !== "mt-code-standards-setup"
    || (skillVersion && (skillVersion.length > 128 || /[\p{Cc}]/u.test(skillVersion)))) {
    fail("RULE_BUNDLE_EXECUTION_INVALID", "拉取执行环境信息不合法");
  }
  return Object.freeze({ pullId, agent, source, skillName, skillVersion });
};

const requestBundle = async ({ gatewayUrl, token, repositoryLocator, knownSnapshotId, execution, fetchImpl }) => {
  const trustedGateway = validateGatewayUrl(gatewayUrl);
  let response;
  try {
    response = await fetchImpl(`${trustedGateway}/v1/effective-rule-bundles/resolve`, {
      method: "POST",
      redirect: "error",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
        "X-Rule-Auth-Source": "nocode-agent-sso",
        "X-Rule-Protocol-Version": "1.0",
      },
      body: JSON.stringify({
        repository_locator: repositoryLocator,
        ...(knownSnapshotId ? { known_snapshot_id: knownSnapshotId } : {}),
        execution: {
          pull_id: execution.pullId,
          execution_agent: execution.agent,
          execution_agent_source: execution.source,
          skill_name: execution.skillName,
          skill_version: execution.skillVersion,
        },
      }),
    });
  } catch (error) {
    fail("RULE_BUNDLE_NETWORK_FAILED", `规则包服务不可用：${error.message}`);
  }
  const rawBody = await response.text().catch(() => "");
  if (Buffer.byteLength(rawBody, "utf8") > MAX_RESPONSE_BYTES) {
    fail("RULE_BUNDLE_RESPONSE_TOO_LARGE", "规则包响应超过 4 MiB 安全上限");
  }
  let body = {};
  try {
    body = rawBody ? JSON.parse(rawBody) : {};
  } catch {
    fail("RULE_BUNDLE_RESPONSE_NOT_JSON", "规则包服务返回了非 JSON 内容");
  }
  if (!response.ok) {
    const code = body?.error?.code || `RULE_BUNDLE_HTTP_${response.status}`;
    fail(code, friendlyServiceError(code, body?.error?.message));
  }
  return body;
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

const normalizeReleaseRefs = (releaseRefs) => {
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
    if (!ruleSetId || !releaseId || !["L1", "L2"].includes(scopeLevel)) {
      fail("RULE_BUNDLE_RELEASE_REFS_INVALID", "release 引用缺少 rule_set_id、release_id 或 scope_level");
    }
    if (manifestHash && !SHA256_PATTERN.test(manifestHash)) {
      fail("RULE_BUNDLE_RELEASE_REFS_INVALID", `release ${releaseId} 的 manifest_hash 非法`);
    }
    const key = `${ruleSetId}\0${releaseId}\0${scopeLevel}`;
    if (seen.has(key)) fail("RULE_BUNDLE_RELEASE_REFS_INVALID", `release 引用重复：${releaseId}`);
    seen.add(key);
    return {
      rule_set_id: ruleSetId,
      release_id: releaseId,
      scope_level: scopeLevel,
      ...(manifestHash ? { manifest_hash: manifestHash } : {}),
    };
  });
  return result.sort((left, right) => (
    left.rule_set_id.localeCompare(right.rule_set_id, "en")
    || left.release_id.localeCompare(right.release_id, "en")
    || left.scope_level.localeCompare(right.scope_level, "en")
  ));
};

const validateBundle = (body, knownSnapshotId) => {
  if (!isObject(body) || ![LEGACY_BUNDLE_SCHEMA, BUNDLE_SCHEMA].includes(body.schema_version)) {
    fail("RULE_BUNDLE_RESPONSE_INVALID", `规则包响应必须为 ${BUNDLE_SCHEMA}`);
  }
  if (!new Set(["ready", "not_modified"]).has(body.status) || !isObject(body.snapshot)) {
    fail("RULE_BUNDLE_RESPONSE_INVALID", "规则包缺少有效 status 或 snapshot");
  }
  const snapshot = body.snapshot;
  const versionTwo = body.schema_version === BUNDLE_SCHEMA;
  if (versionTwo ? snapshot.resolver_version !== BUNDLE_SCHEMA : snapshot.resolver_version != null) {
    fail("RULE_BUNDLE_RESPONSE_INVALID", "规则包生成版本与响应协议不一致");
  }
  const pathOrder = versionTwo ? binaryPathOrder : (left, right) => left.localeCompare(right, "en");
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
  const releaseRefs = normalizeReleaseRefs(snapshot.release_refs);
  if (!Number.isSafeInteger(snapshot.total_bytes) || snapshot.total_bytes < 0) {
    fail("RULE_BUNDLE_TOTAL_BYTES_INVALID", "规则包总字节数非法");
  }
  const snapshotProjection = {
    ...(versionTwo ? { resolver_version: BUNDLE_SCHEMA } : {}),
    repository_id: repository.repository_id,
    canonical_key: repository.canonical_key,
    standard_domain: repository.standard_domain,
    manifest_hash: snapshot.manifest_hash,
    release_refs: releaseRefs,
  };
  if (sha256Hex(canonicalJson(snapshotProjection)) !== snapshot.snapshot_id) {
    fail("RULE_BUNDLE_SNAPSHOT_HASH_MISMATCH", "规则包 snapshot_id 校验失败");
  }
  const files = Array.isArray(body.files) ? body.files : [];
  if (body.status === "not_modified") {
    if (!knownSnapshotId || snapshot.snapshot_id !== knownSnapshotId || files.length) {
      fail("RULE_BUNDLE_NOT_MODIFIED_INVALID", "not_modified 与本地已校验快照不一致");
    }
    return { status: body.status, snapshot: { ...snapshot, repository, release_refs: releaseRefs }, files: [] };
  }
  if (!files.length) fail("RULE_BUNDLE_FILES_MISSING", "ready 规则包没有文件");

  const seenPaths = new Set();
  const directories = new Map();
  const normalizedFiles = files.map((file) => {
    if (!isObject(file)) fail("RULE_BUNDLE_FILE_INVALID", "规则文件格式错误");
    const relativePath = normalizeRelativePath(file.relative_path, versionTwo);
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
    return { relative_path: relativePath, content, sha256: actualHash, byte_size: actualBytes };
  }).sort((left, right) => pathOrder(left.relative_path, right.relative_path));

  const totalBytes = normalizedFiles.reduce((sum, file) => sum + file.byte_size, 0);
  if (snapshot.total_bytes !== totalBytes) fail("RULE_BUNDLE_TOTAL_BYTES_MISMATCH", "规则包总字节数校验失败");
  const projection = normalizedFiles.map(({ relative_path, sha256, byte_size }) => ({
    relative_path,
    sha256,
    byte_size,
  }));
  const manifestHash = sha256Hex(canonicalJson(projection));
  if (manifestHash !== snapshot.manifest_hash) fail("RULE_BUNDLE_MANIFEST_HASH_MISMATCH", "规则包 manifest_hash 校验失败");
  return {
    status: body.status,
    snapshot: { ...snapshot, repository, release_refs: releaseRefs, total_bytes: totalBytes },
    files: normalizedFiles,
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

const isFlatLocalManifest = (manifest) => manifest?.schema_version === FLAT_LOCAL_MANIFEST_SCHEMA;

const manifestBundleSchema = (manifest) => {
  if (isFlatLocalManifest(manifest)) return manifest.resolver_version;
  return manifest?.schema_version === LOCAL_MANIFEST_SCHEMA
    ? BUNDLE_SCHEMA
    : LEGACY_BUNDLE_SCHEMA;
};

const manifestPhysicalPath = (manifest, managedPath) => {
  const bundleSchema = manifestBundleSchema(manifest);
  return normalizeRelativePath(managedPath, bundleSchema === BUNDLE_SCHEMA);
};

const manifestSourcePath = (manifest, managedPath) => {
  const bundleSchema = manifestBundleSchema(manifest);
  if (isFlatLocalManifest(manifest)) {
    return normalizeRelativePath(
      manifest.managed_file_sources[managedPath],
      bundleSchema === BUNDLE_SCHEMA,
    );
  }
  const prefix = `${manifest.standard_domain}/`;
  return normalizeRelativePath(managedPath.slice(prefix.length), bundleSchema === BUNDLE_SCHEMA);
};

const isFlatManagedPath = (value, bundleSchema) => {
  const pathValue = normalizeRelativePath(value, bundleSchema === BUNDLE_SCHEMA);
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

const localFilesForBundle = (bundle) => {
  const versionTwo = bundle.snapshot.resolver_version === BUNDLE_SCHEMA;
  const candidates = bundle.files.map((file) => {
    const sourcePath = normalizeRelativePath(file.relative_path, versionTwo);
    const parts = sourcePath.split("/");
    const scope = parts[0];
    const fileName = parts.at(-1);
    if ((scope !== "l1" && scope !== "l2") || !fileName) {
      fail("RULE_BUNDLE_FILE_PATH_INVALID", `规则文件层级非法：${sourcePath}`);
    }
    const inferredRuleSetId = parts.length > 2
      ? parts[1]
      : fileName.replace(/[.]md$/iu, "");
    const candidate = scope === "l1"
      ? `company/${fileName}`
      : `team/${inferredRuleSetId}/${fileName}`;
    return { ...file, source_relative_path: sourcePath, local_relative_path: candidate };
  });
  const occupied = new Set();
  return candidates.map((file) => {
    let localPath = file.local_relative_path;
    let attempt = 0;
    while (occupied.has(pathKey(localPath))) {
      const parts = localPath.split("/");
      const fileName = parts.at(-1);
      localPath = [...parts.slice(0, -1), suffixFileName(fileName, file.source_relative_path, attempt++)].join("/");
    }
    if (!isFlatManagedPath(localPath, versionTwo)) {
      fail("RULE_BUNDLE_FILE_PATH_INVALID", `规则本地路径非法：${localPath}`);
    }
    occupied.add(pathKey(localPath));
    return { ...file, local_relative_path: localPath };
  }).sort((left, right) => binaryPathOrder(left.local_relative_path, right.local_relative_path));
};

const validateLocalManifestStructure = (manifest) => {
  if (
    !manifest
    || ![LEGACY_LOCAL_MANIFEST_SCHEMA, LOCAL_MANIFEST_SCHEMA, FLAT_LOCAL_MANIFEST_SCHEMA].includes(manifest.schema_version)
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
  const bundleSchema = manifestBundleSchema(manifest);
  if (![LEGACY_BUNDLE_SCHEMA, BUNDLE_SCHEMA].includes(bundleSchema)) return false;
  if (!flat && (manifest.schema_version === LOCAL_MANIFEST_SCHEMA
    ? manifest.resolver_version !== BUNDLE_SCHEMA
    : manifest.resolver_version != null)) return false;
  if (flat && (
    manifest.local_layout !== FLAT_LOCAL_LAYOUT
    || !isObject(manifest.managed_file_sources)
  )) return false;
  const versionTwo = bundleSchema === BUNDLE_SCHEMA;
  const pathOrder = versionTwo ? binaryPathOrder : (left, right) => left.localeCompare(right, "en");
  const uniquePaths = new Set(manifest.managed_files);
  if (uniquePaths.size !== manifest.managed_files.length || !uniquePaths.size) return false;
  if (flat && Object.keys(manifest.managed_file_sources).length !== uniquePaths.size) return false;
  const projection = [];
  for (const managedPath of [...uniquePaths].sort(pathOrder)) {
    if (typeof managedPath !== "string") return false;
    if (!flat && !managedPath.startsWith(`${manifest.standard_domain}/`)) return false;
    if (flat && !isFlatManagedPath(managedPath, bundleSchema)) return false;
    const sourcePath = manifestSourcePath(manifest, managedPath);
    if (flat && !Object.hasOwn(manifest.managed_file_sources, managedPath)) return false;
    const fileHash = manifest.managed_file_hashes[managedPath];
    const fileSize = manifest.managed_file_sizes[managedPath];
    if (!SHA256_PATTERN.test(text(fileHash)) || !Number.isSafeInteger(fileSize) || fileSize < 0) return false;
    projection.push({ relative_path: sourcePath, sha256: fileHash, byte_size: fileSize });
  }
  if (sha256Hex(canonicalJson(projection)) !== manifest.manifest_hash) return false;
  if (projection.reduce((sum, file) => sum + file.byte_size, 0) !== manifest.total_bytes) return false;
  const releaseRefs = normalizeReleaseRefs(manifest.release_refs);
  const snapshotProjection = {
    ...(bundleSchema === BUNDLE_SCHEMA ? { resolver_version: BUNDLE_SCHEMA } : {}),
    repository_id: manifest.repository.repository_id,
    canonical_key: manifest.repository.canonical_key,
    standard_domain: manifest.repository.standard_domain,
    manifest_hash: manifest.manifest_hash,
    release_refs: releaseRefs,
  };
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
  return true;
};

const buildLocalManifest = (bundle) => {
  const domain = bundle.snapshot.repository.standard_domain;
  const localFiles = localFilesForBundle(bundle);
  const managedFiles = localFiles.map((file) => file.local_relative_path);
  return {
    schema_version: FLAT_LOCAL_MANIFEST_SCHEMA,
    local_layout: FLAT_LOCAL_LAYOUT,
    resolver_version: bundle.snapshot.resolver_version || LEGACY_BUNDLE_SCHEMA,
    snapshot_id: bundle.snapshot.snapshot_id,
    manifest_hash: bundle.snapshot.manifest_hash,
    repository: {
      repository_id: bundle.snapshot.repository.repository_id,
      canonical_key: bundle.snapshot.repository.canonical_key,
      standard_domain: domain,
    },
    standard_domain: domain,
    release_refs: bundle.snapshot.release_refs,
    total_bytes: bundle.snapshot.total_bytes,
    managed_files: managedFiles,
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

const installReadyBundle = async (repoRoot, bundle, previousManifest) => {
  const mdpRoot = path.join(repoRoot, ".mdp");
  const rulesRoot = path.join(repoRoot, ".mdp", "rules");
  const domain = bundle.snapshot.repository.standard_domain;
  await mkdir(mdpRoot, { recursive: true });
  await assertNoSymlink(mdpRoot, repoRoot);
  if (await exists(rulesRoot)) await assertNoSymlink(rulesRoot, mdpRoot);

  if (previousManifest?.standard_domain && previousManifest.standard_domain !== domain) {
    fail(
      "RULE_BUNDLE_DOMAIN_CHANGED",
      `本地已有 ${previousManifest.standard_domain} 规则包，仓库领域变为 ${domain}；请先在平台核对仓库领域`,
    );
  }
  const previousManaged = new Set(previousManifest?.managed_files || []);
  const previousPhysicalPaths = new Set(previousManifest
    ? [...previousManaged].map((name) => manifestPhysicalPath(previousManifest, name))
    : []);
  const previousManagedNfc = new Set([...previousPhysicalPaths].map((name) => name.normalize("NFC")));
  const localFiles = localFilesForBundle(bundle);
  const directoryCache = new Map();
  for (const file of localFiles) {
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
    for (const file of localFiles) {
      const outputPath = path.join(stagedRulesRoot, ...file.local_relative_path.split("/"));
      await assertNoSymlink(outputPath, stagedRulesRoot);
      await mkdir(path.dirname(outputPath), { recursive: true });
      await writeFile(outputPath, file.content, "utf8");
    }
    const manifest = buildLocalManifest(bundle);
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

const assertGitRepository = async (repoRoot) => {
  if (!await exists(path.join(repoRoot, ".git"))) {
    fail("RULE_BUNDLE_GIT_REQUIRED", "当前目录不是 Git 仓库根目录，请使用 --repo-root 指定目标仓库");
  }
};

export const syncEffectiveRuleBundle = async ({
  gatewayUrl = DEFAULT_GATEWAY,
  token,
  repositoryLocator = "",
  repoRoot = process.cwd(),
  execution,
  fetchImpl = globalThis.fetch,
} = {}) => {
  if (!token) {
    fail(
      "RULE_BUNDLE_AUTH_REQUIRED",
      "缺少 MTSSO 官方短期用户票据；禁止使用 Cookie、Git 作者、系统账号或把令牌写入文件",
    );
  }
  const absoluteRoot = path.resolve(repoRoot);
  const normalizedExecution = normalizePullExecution(execution);
  await assertGitRepository(absoluteRoot);
  const locator = validateRepositoryLocator(repositoryLocator || repositoryLocatorFromGit(absoluteRoot));
  const previousManifest = await readLocalManifest(absoluteRoot);
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
  // A verified legacy tree must be fetched once more so it can be migrated to
  // the flat company/team layout; only the current layout may receive a
  // not_modified response without rewriting local files.
  const knownSnapshotId = previousCurrent && isFlatLocalManifest(previousManifest)
    ? previousManifest.snapshot_id
    : "";
  const body = await requestBundle({
    gatewayUrl,
    token,
    repositoryLocator: locator,
    knownSnapshotId,
    execution: normalizedExecution,
    fetchImpl,
  });
  const bundle = validateBundle(body, knownSnapshotId);
  const manifest = bundle.status === "ready"
    ? await installReadyBundle(absoluteRoot, bundle, previousTrusted ? previousManifest : null)
    : previousManifest;
  return Object.freeze({
    schema_version: RECEIPT_SCHEMA,
    status: bundle.status === "ready" ? "installed" : "not_modified",
    repository: bundle.snapshot.repository,
    snapshot_id: bundle.snapshot.snapshot_id,
    release_refs: bundle.snapshot.release_refs,
    managed_files: manifest.managed_files,
    total_bytes: manifest.total_bytes,
    pull_id: normalizedExecution.pullId,
    execution_agent: normalizedExecution.agent,
  });
};

const parseArgs = (argv) => {
  const result = {};
  const valued = new Set([
    "--repository", "--repo-root", "--gateway-url", "--token-env", "--pull-id",
    "--execution-agent", "--execution-agent-source", "--skill-version",
  ]);
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!valued.has(key) || index + 1 >= argv.length) {
      fail("RULE_BUNDLE_ARGUMENT_INVALID", `未知或缺值参数：${key}`);
    }
    const value = argv[index + 1];
    if (key === "--repository") result.repositoryLocator = value;
    else if (key === "--repo-root") result.repoRoot = value;
    else if (key === "--gateway-url") result.gatewayUrl = value;
    else if (key === "--token-env") result.tokenEnv = value;
    else if (key === "--pull-id") result.pullId = value;
    else if (key === "--execution-agent") result.executionAgent = value;
    else if (key === "--execution-agent-source") result.executionAgentSource = value;
    else if (key === "--skill-version") result.skillVersion = value;
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
