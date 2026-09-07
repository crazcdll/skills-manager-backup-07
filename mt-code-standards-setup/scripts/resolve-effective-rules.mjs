#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
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
import { pathToFileURL } from "node:url";

const DEFAULT_GATEWAY =
  "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability";
const GATEWAY_HOSTNAME = "db0y7dgg85gphojyva.database.sankuai.com";
const GATEWAY_PATHNAME = "/functions/v1/rule-observability";
const LEGACY_BUNDLE_SCHEMA = "effective-rule-bundle/v1";
const BUNDLE_SCHEMA = "effective-rule-bundle/v2";
const LEGACY_LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v1";
const LOCAL_MANIFEST_SCHEMA = "mt-effective-rule-bundle-manifest/v2";
const RECEIPT_SCHEMA = "mt-effective-rule-bundle-install/v1";
const MANIFEST_NAME = ".mt-effective-rule-bundle.json";
const MAX_LOCATOR_BYTES = 8 * 1024;
const MAX_RESPONSE_BYTES = 4 * 1024 * 1024;
const MAX_FILE_BYTES = 512 * 1024;
const SHA256_PATTERN = /^[a-f0-9]{64}$/;
const DOMAINS = new Set(["frontend", "backend"]);
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

const requestBundle = async ({ gatewayUrl, token, repositoryLocator, knownSnapshotId, fetchImpl }) => {
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

const validateLocalManifestStructure = (manifest) => {
  if (
    !manifest
    || ![LEGACY_LOCAL_MANIFEST_SCHEMA, LOCAL_MANIFEST_SCHEMA].includes(manifest.schema_version)
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
  const versionTwo = manifest.schema_version === LOCAL_MANIFEST_SCHEMA;
  if (versionTwo ? manifest.resolver_version !== BUNDLE_SCHEMA : manifest.resolver_version != null) return false;
  const pathOrder = versionTwo ? binaryPathOrder : (left, right) => left.localeCompare(right, "en");
  const expectedPrefix = `${manifest.standard_domain}/`;
  const uniquePaths = new Set(manifest.managed_files);
  if (uniquePaths.size !== manifest.managed_files.length || !uniquePaths.size) return false;
  const projection = [];
  for (const managedPath of [...uniquePaths].sort(pathOrder)) {
    if (typeof managedPath !== "string" || !managedPath.startsWith(expectedPrefix)) return false;
    const relativePath = normalizeRelativePath(managedPath.slice(expectedPrefix.length), versionTwo);
    const fileHash = manifest.managed_file_hashes[managedPath];
    const fileSize = manifest.managed_file_sizes[managedPath];
    if (!SHA256_PATTERN.test(text(fileHash)) || !Number.isSafeInteger(fileSize) || fileSize < 0) return false;
    projection.push({ relative_path: relativePath, sha256: fileHash, byte_size: fileSize });
  }
  if (sha256Hex(canonicalJson(projection)) !== manifest.manifest_hash) return false;
  if (projection.reduce((sum, file) => sum + file.byte_size, 0) !== manifest.total_bytes) return false;
  const releaseRefs = normalizeReleaseRefs(manifest.release_refs);
  const snapshotProjection = {
    ...(versionTwo ? { resolver_version: BUNDLE_SCHEMA } : {}),
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
  const expectedPrefix = `${manifest.standard_domain}/`;
  for (const managedPath of manifest.managed_files) {
    const relativePath = normalizeRelativePath(managedPath.slice(expectedPrefix.length), manifest.schema_version === LOCAL_MANIFEST_SCHEMA);
    const fullPath = path.join(rulesRoot, manifest.standard_domain, ...relativePath.split("/"));
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
  const managedFiles = bundle.files.map((file) => `${domain}/${file.relative_path}`);
  return {
    schema_version: bundle.snapshot.resolver_version === BUNDLE_SCHEMA ? LOCAL_MANIFEST_SCHEMA : LEGACY_LOCAL_MANIFEST_SCHEMA,
    ...(bundle.snapshot.resolver_version ? { resolver_version: bundle.snapshot.resolver_version } : {}),
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
    managed_file_hashes: Object.fromEntries(bundle.files.map((file) => [
      `${domain}/${file.relative_path}`,
      file.sha256,
    ])),
    managed_file_sizes: Object.fromEntries(bundle.files.map((file) => [
      `${domain}/${file.relative_path}`,
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
  const rulesRoot = path.join(repoRoot, ".mdp", "rules");
  const domain = bundle.snapshot.repository.standard_domain;
  const domainPath = path.join(rulesRoot, domain);
  const manifestPath = path.join(rulesRoot, MANIFEST_NAME);
  await mkdir(rulesRoot, { recursive: true });
  await assertNoSymlink(rulesRoot, repoRoot);
  await assertNoSymlink(domainPath, rulesRoot);

  if (previousManifest?.standard_domain && previousManifest.standard_domain !== domain) {
    fail(
      "RULE_BUNDLE_DOMAIN_CHANGED",
      `本地已有 ${previousManifest.standard_domain} 规则包，仓库领域变为 ${domain}；请先在平台核对仓库领域`,
    );
  }
  const previousManaged = new Set(previousManifest?.managed_files || []);
  const previousManagedNfc = new Set([...previousManaged].map((name) => name.normalize("NFC")));
  const previousRelativePaths = new Set([...previousManaged].map((name) => name.slice(domain.length + 1)));
  const directoryCache = new Map();
  for (const file of bundle.files) {
    const managedPath = `${domain}/${file.relative_path}`;
    const currentPath = path.join(domainPath, ...file.relative_path.split("/"));
    await assertNoSymlink(currentPath, rulesRoot);
    const existing = await existingPortablePath(domainPath, file.relative_path, directoryCache, previousRelativePaths);
    if (existing && !previousManagedNfc.has(`${domain}/${existing}`.normalize("NFC"))) {
      fail("RULE_BUNDLE_LOCAL_COLLISION", `规则目标路径已有非受管文件，未覆盖：${managedPath}`);
    }
  }

  const stageRoot = await mkdtemp(path.join(rulesRoot, ".mt-bundle-stage-"));
  const stageDomain = path.join(stageRoot, domain);
  const stagedManifest = path.join(stageRoot, MANIFEST_NAME);
  const backupDomain = path.join(rulesRoot, `.mt-bundle-backup-${domain}-${randomUUID()}`);
  const backupManifest = path.join(rulesRoot, `.mt-bundle-backup-manifest-${randomUUID()}.json`);
  let domainBackedUp = false;
  let domainInstalled = false;
  let manifestBackedUp = false;
  let manifestInstalled = false;
  try {
    if (await exists(domainPath)) await cp(domainPath, stageDomain, { recursive: true, errorOnExist: false });
    else await mkdir(stageDomain, { recursive: true });

    for (const managedPath of previousManaged) {
      if (!managedPath.startsWith(`${domain}/`)) continue;
      const relativePath = normalizeRelativePath(managedPath.slice(domain.length + 1), previousManifest.schema_version === LOCAL_MANIFEST_SCHEMA);
      const stagedOldPath = path.join(stageDomain, ...relativePath.split("/"));
      await assertNoSymlink(stagedOldPath, stageDomain);
      await rm(stagedOldPath, { force: true });
      await removeEmptyManagedParents(stagedOldPath, stageDomain);
    }
    for (const file of bundle.files) {
      const outputPath = path.join(stageDomain, ...file.relative_path.split("/"));
      await assertNoSymlink(outputPath, stageDomain);
      await mkdir(path.dirname(outputPath), { recursive: true });
      await writeFile(outputPath, file.content, "utf8");
    }
    const manifest = buildLocalManifest(bundle);
    await writeFile(stagedManifest, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

    if (await exists(domainPath)) {
      await rename(domainPath, backupDomain);
      domainBackedUp = true;
    }
    await rename(stageDomain, domainPath);
    domainInstalled = true;
    if (await exists(manifestPath)) {
      await rename(manifestPath, backupManifest);
      manifestBackedUp = true;
    }
    await rename(stagedManifest, manifestPath);
    manifestInstalled = true;
    await rm(backupDomain, { recursive: true, force: true }).catch(() => {});
    await rm(backupManifest, { force: true }).catch(() => {});
    return manifest;
  } catch (error) {
    try {
      if (manifestInstalled) await rm(manifestPath, { force: true });
      if (manifestBackedUp && await exists(backupManifest)) await rename(backupManifest, manifestPath);
      if (domainInstalled) await rm(domainPath, { recursive: true, force: true });
      if (domainBackedUp && await exists(backupDomain)) await rename(backupDomain, domainPath);
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
  fetchImpl = globalThis.fetch,
} = {}) => {
  if (!token) {
    fail(
      "RULE_BUNDLE_AUTH_REQUIRED",
      "缺少 MTSSO 官方短期用户票据；禁止使用 Cookie、Git 作者、系统账号或把令牌写入文件",
    );
  }
  const absoluteRoot = path.resolve(repoRoot);
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
  const knownSnapshotId = previousCurrent ? previousManifest.snapshot_id : "";
  const body = await requestBundle({
    gatewayUrl,
    token,
    repositoryLocator: locator,
    knownSnapshotId,
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
  });
};

const parseArgs = (argv) => {
  const result = {};
  const valued = new Set(["--repository", "--repo-root", "--gateway-url", "--token-env"]);
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
  });
  process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
};

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    const code = error instanceof RuleBundleError ? error.code : "RULE_BUNDLE_UNEXPECTED";
    process.stderr.write(`${code}: ${error.message}\n`);
    process.exitCode = 2;
  });
}
