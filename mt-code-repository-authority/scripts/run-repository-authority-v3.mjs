#!/usr/bin/env node

import { chmod, mkdir, mkdtemp, readFile, rename, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { setTimeout as wait } from "node:timers/promises";
import { fileURLToPath } from "node:url";

import {
  AuthorityContractError,
  AuthorityUnresolvedError,
  buildRunnerResult,
  canonical,
  emptyTimings,
  sha256,
} from "./repository-authority-contract.mjs";
import {
  AuthorityRunnerError,
  acquireMetricsToken,
  deliverAuthorityCallback,
  ensureYuntuRuntime,
  queryRepositoryOwner,
  queryYuntuOrganization,
  runProcess,
} from "./run-repository-authority.mjs";
import {
  V3_LOCAL_RECEIPT_SCHEMA,
  V3_LEGACY_SKILL_CONTRACT,
  V3_MODE_AUTHORITY,
  V3_MODE_SOURCE_SCAN,
  V3_SOURCE_RESULT_SCHEMA,
  V3_SOURCE_RESULT_SCHEMA_V2,
  V3_WORKERS,
  validateV3TaskArtifact,
} from "./repository-authority-v3-contract.mjs";

const REPOSITORY_URL = /(?:https:\/\/(?:dev|git)[.]sankuai[.]com|ssh:\/\/git@git[.]sankuai[.]com)[^\s<>"'\[\]()|，。；]+/giu;
const REPOSITORY_ADDRESS = /(?:ssh:\/\/git@\[[0-9a-f:.]+\]|https?:\/\/|ssh:\/\/|git@)[^\s<>"'\[\]()|，。；]+/giu;
const elapsed = (start, now) => Math.max(0, Math.round(now() - start));
const TABLE_PAGE_READER = fileURLToPath(new URL("./read-citadel-table-page.mjs", import.meta.url));
const ACTOR_MIS = /^[a-z][a-z0-9._-]{0,63}$/u;
const errorShape = (error) => ({ phase: String(error?.phase || "runner"), error_code: String(error?.errorCode || "runner_failed"), retriable: error?.retriable === true });

const createCitadelAuthSession = async () => {
  const directory = await mkdtemp(join(tmpdir(), "repository-citadel-auth-"));
  await chmod(directory, 0o700);
  const env = { ...process.env, AUTH_CACHE_FILE: join(directory, "auth-cache.json"), SSO_OIDC_FALLBACK: "false" };
  delete env.SSO_CIBA_TOKEN;
  return { env, cleanup: () => rm(directory, { recursive: true, force: true }) };
};

const writeAtomic = async (path, value) => {
  const temp = `${path}.${process.pid}.tmp`;
  await mkdir(dirname(path), { recursive: true, mode: 0o700 });
  await writeFile(temp, `${JSON.stringify(value)}\n`, { encoding: "utf8", mode: 0o600 });
  await rename(temp, path);
};

export const mapLimit = async (items, limit, mapper) => {
  const results = new Array(items.length);
  let cursor = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      const index = cursor++;
      results[index] = await mapper(items[index], index);
    }
  });
  await Promise.all(workers);
  return results;
};

export const executeAuthorityItem = async ({ context, runtime, setupError = null, processRunner = runProcess, callbackRequest, now = Date.now }) => {
  const timings = emptyTimings();
  const started = now();
  const versions = { eeCodeCliVersion: "unknown", yuntuCliVersion: runtime?.version ?? "unavailable" };
  let repository = { canonical_key: context.repository.canonicalKey, default_branch: null };
  let owner = null;
  let organization = null;
  let executionStatus = "failed";
  let resolutionStatus = null;
  let failure = null;
  try {
    if (setupError) throw setupError;
    let at = now();
    const first = await queryRepositoryOwner({ context, processRunner, now });
    timings.repository_lookup_ms = elapsed(at, now);
    versions.eeCodeCliVersion = first.eeCodeCliVersion;
    repository = { canonical_key: context.repository.canonicalKey, default_branch: first.defaultBranch };
    owner = { mis: first.ownerMis, display_name: first.ownerDisplayName, iam_emp_id: null, identity_enrichment_status: "not_requested" };
    at = now();
    const token = await acquireMetricsToken({ context, processRunner, now });
    timings.metrics_token_exchange_ms = elapsed(at, now);
    at = now();
    const yuntu = await queryYuntuOrganization({ context, runtime, owner: first, metricsToken: token, processRunner, now });
    timings.yuntu_lookup_ms = elapsed(at, now);
    at = now();
    const current = await queryRepositoryOwner({ context, processRunner, now, readVersion: false });
    timings.repository_lookup_ms += elapsed(at, now);
    if (current.ownerMis !== first.ownerMis || current.defaultBranch !== first.defaultBranch) {
      throw new AuthorityUnresolvedError("repository state changed while authority was being resolved", { phase: "repository_lookup", errorCode: "repository_state_changed" });
    }
    owner.display_name = owner.display_name ?? yuntu.name;
    organization = { source_system: "yuntu_org", source_organization_id: yuntu.sourceOrganizationId, display_name: yuntu.displayName, full_path: yuntu.fullPath, chain: yuntu.chain };
    executionStatus = "succeeded";
    resolutionStatus = "confirmed";
  } catch (error) {
    failure = error instanceof AuthorityRunnerError || error instanceof AuthorityContractError ? error : new AuthorityRunnerError("repository authority Runner failed");
    if (failure instanceof AuthorityUnresolvedError) {
      executionStatus = "succeeded";
      resolutionStatus = "unresolved";
    } else {
      owner = null;
    }
  }
  timings.total_ms = elapsed(started, now);
  const result = buildRunnerResult({ context, executionStatus, resolutionStatus, repository, owner, organization, versions, verifiedAt: new Date(now()).toISOString(), timings, error: failure ? errorShape(failure) : null, skillContractVersion: V3_LEGACY_SKILL_CONTRACT });
  const delivered = await deliverAuthorityCallback({ context, result, request: callbackRequest, now });
  return { item_id: context.itemId, status: delivered.receipt.status, execution_status: executionStatus, resolution_status: resolutionStatus, result_hash: delivered.resultHash };
};

const jsonFrom = (buffer) => {
  try { return JSON.parse(Buffer.from(buffer ?? "").toString("utf8")); } catch { return null; }
};
const sourceLocationAtom = (value) => String(value ?? "unknown")
  .replace(/[\u0000-\u001f\u007f-\u009f]/gu, "")
  .slice(0, 120) || "unknown";
const strings = (value, output = []) => {
  if (typeof value === "string") output.push(value);
  else if (Array.isArray(value)) value.forEach((item) => strings(item, output));
  else if (value && typeof value === "object") Object.values(value).forEach((item) => strings(item, output));
  return output;
};
export const extractCitadelTableIds = (value) => {
  const ids = new Set();
  const add = (candidate) => {
    const normalized = String(candidate ?? "").trim();
    if (/^\d{3,30}$/u.test(normalized)) ids.add(normalized);
  };
  const visit = (candidate) => {
    if (Array.isArray(candidate)) {
      candidate.forEach(visit);
      return;
    }
    if (!candidate || typeof candidate !== "object") return;
    Object.entries(candidate).forEach(([key, nested]) => {
      if (key === "tableId" || key === "table_id" || key === "xtableId") add(nested);
      else if (key === "tableIds" || key === "table_ids") {
        if (Array.isArray(nested)) nested.forEach(add);
      } else if (key === "body" && typeof nested === "string") visit(jsonFrom(nested));
      else visit(nested);
    });
  };
  visit(value);
  return [...ids];
};
export const extractRepositoryCandidates = (value, location, issues = []) => {
  const candidates = [];
  strings(value).forEach((text) => {
    for (const match of text.matchAll(REPOSITORY_URL)) {
      const raw = match[0].replace(/[,;\]]+$/u, "");
      let url;
      try { url = new URL(raw); } catch { continue; }
      const parts = url.protocol === "https:" && url.hostname === "dev.sankuai.com"
        ? url.pathname.match(/^\/code\/repo-detail\/(~?[a-z0-9._-]{1,120})\/([a-z0-9._-]{1,120})(?:\/file\/list)?\/?$/iu)
        : url.pathname.match(/^\/(~?[a-z0-9._-]{1,120})\/([a-z0-9._-]{1,120}?)\/?$/iu);
      if (!parts || url.search || url.hash || url.port || url.password || (url.protocol === "ssh:" ? url.username !== "git" : !!url.username)) {
        issues.push({ source: location, raw_value: raw.slice(0, 2000), error_code: "invalid_repository_url" });
        continue;
      }
      const canonicalKey = `${parts[1]}/${parts[2].replace(/[.]git$/iu, "")}`.toLowerCase();
      candidates.push({ canonical_key: canonicalKey, canonical_https_url: `https://dev.sankuai.com/code/repo-detail/${canonicalKey}/file/list`, canonical_ssh_url: `ssh://git@git.sankuai.com/${canonicalKey}.git`, source_locations: [location] });
    }
  });
  return candidates;
};

export const extractRepositoryCandidatesV2 = (value, location) => {
  const candidates = [];
  const invalidItems = [];
  strings(value).forEach((source) => {
    for (const match of source.matchAll(REPOSITORY_ADDRESS)) {
      const raw = match[0].replace(/[,;]+$/u, "");
      const item = { raw_value: raw.slice(0, 2000), source_locations: [location] };
      if (raw.length <= 2000) candidates.push(item);
      else invalidItems.push({ ...item, error_code: "repository_address_too_long" });
    }
  });
  return { candidates, invalidItems };
};

export const scanCitadelSource = async ({ source, actorMis, authEnvironment, resultSchema = V3_SOURCE_RESULT_SCHEMA, deadline = Date.now() + 14 * 60 * 1000, processRunner = runProcess, now = Date.now, waitBetweenReads = wait }) => {
  if (
    !ACTOR_MIS.test(String(actorMis ?? "")) ||
    typeof authEnvironment?.AUTH_CACHE_FILE !== "string" ||
    !authEnvironment.AUTH_CACHE_FILE.startsWith("/") ||
    authEnvironment.SSO_OIDC_FALLBACK !== "false" ||
    Object.hasOwn(authEnvironment, "SSO_CIBA_TOKEN")
  ) throw new AuthorityContractError("source scan Citadel actor session is invalid");
  const contentId = new URL(source.citadelUrl).pathname.split("/").filter(Boolean).at(-1);
  const issues = [];
  const found = [];
  const invalidItems = [];
  const readErrors = [];
  const addReadError = (sourceLocation, errorCode, retriable = true) => {
    if (resultSchema === V3_SOURCE_RESULT_SCHEMA_V2) readErrors.push({ source: sourceLocation, error_code: errorCode, retriable });
    else issues.push({ source: sourceLocation, error_code: errorCode });
  };
  const extract = (value, location) => {
    if (resultSchema === V3_SOURCE_RESULT_SCHEMA_V2) {
      const extracted = extractRepositoryCandidatesV2(value, location);
      found.push(...extracted.candidates);
      invalidItems.push(...extracted.invalidItems);
    } else {
      found.push(...extractRepositoryCandidates(value, location, issues));
    }
  };
  const read = async (args, maxBuffer, command = "oa-skills") => {
    const remaining = deadline - now() - 60_000;
    if (remaining <= 1000) return { exitCode: 1, timedOut: true, stdout: Buffer.alloc(0) };
    await waitBetweenReads(300 + Math.floor(Math.random() * 200));
    try { return await processRunner(command, args, { env: authEnvironment, maxBuffer, timeout: Math.min(remaining, 150_000) }); }
    catch { return { exitCode: 1, stdout: Buffer.alloc(0), stderr: Buffer.alloc(0) }; }
  };
  const authArgs = ["--mis", actorMis, "--sso-strategy", "sso-ciba", "--raw"];
  const terminalFailureCode = (result) => {
    if (result?.timedOut === true) return "citadel_scan_timeout";
    const output = `${Buffer.from(result?.stdout ?? "").toString("utf8")}\n${Buffer.from(result?.stderr ?? "").toString("utf8")}`;
    if (/(?:citadel_scan_timeout|timed?\s*out|timeout|ETIMEDOUT|超时)/iu.test(output)) return "citadel_scan_timeout";
    if (/(?:citadel_auth_required|authorization_pending|slow_down|cooldown|auth(?:entication|orization)?.{0,60}required|需要.{0,12}(?:认证|授权)|请.{0,12}(?:认证|授权))/iu.test(output)) return "citadel_auth_required";
    if (/(?:citadel_auth_failed|MOA_USER_REJECTED|access_denied|expired_token|invalid_grant|401.{0,20}unauthorized|unauthorized|auth(?:entication|orization)?.{0,60}(?:failed|denied|expired)|(?:认证|授权).{0,30}(?:失败|拒绝|过期))/iu.test(output)) return "citadel_auth_failed";
    if (/(?:citadel_document_access_denied|403|forbidden|permission denied|access denied|没有.{0,12}(?:查看|阅读|访问)?.{0,12}权限|无.{0,12}(?:查看|阅读|访问)?.{0,12}权限|权限不足)/iu.test(output)) return "citadel_document_access_denied";
    return null;
  };
  const terminalFailure = (sourceLocation, errorCode) => {
    const retriable = errorCode === "citadel_scan_timeout";
    return resultSchema === V3_SOURCE_RESULT_SCHEMA_V2
      ? { scan_status: "failed", candidates: [], invalid_items: [], read_errors: [{ source: sourceLocation, error_code: errorCode, retriable }] }
      : { scan_status: "failed", repositories: [], issues: [{ source: sourceLocation, error_code: errorCode }] };
  };
  const markdown = await read(["citadel", "getSimpleMarkdown", "--contentId", contentId, ...authArgs], 4 * 1024 * 1024);
  const markdownTerminal = markdown.exitCode !== 0 ? terminalFailureCode(markdown) : null;
  if (markdownTerminal) return terminalFailure("document", markdownTerminal);
  const markdownPayload = markdown.exitCode === 0 ? jsonFrom(markdown.stdout) : null;
  if (markdownPayload) extract(markdownPayload, "document");
  else addReadError("document", "citadel_document_unavailable");
  const document = await read(["citadel", "getDocumentJson", "--contentId", contentId, ...authArgs], 4 * 1024 * 1024);
  const documentTerminal = document.exitCode !== 0 ? terminalFailureCode(document) : null;
  if (documentTerminal) return terminalFailure("document-references", documentTerminal);
  const documentPayload = document.exitCode === 0 ? jsonFrom(document.stdout) : null;
  if (!documentPayload) addReadError("document-references", "citadel_document_references_unavailable");
  else if (typeof documentPayload.body === "string" && !jsonFrom(documentPayload.body) && /xtable/iu.test(documentPayload.body)) {
    addReadError("document-references", "citadel_legacy_references_unavailable");
  }
  const tables = await read(["citadel-database", "listTables", "--contentId", contentId, ...authArgs], 1024 * 1024);
  const tablesTerminal = tables.exitCode !== 0 ? terminalFailureCode(tables) : null;
  if (tablesTerminal) return terminalFailure("database-list", tablesTerminal);
  const tablePayload = tables.exitCode === 0 ? jsonFrom(tables.stdout) : null;
  const tableIds = [...new Set([...extractCitadelTableIds(tablePayload), ...extractCitadelTableIds(documentPayload)])];
  if (tables.exitCode !== 0 || !tablePayload) addReadError("database-list", "citadel_database_list_unavailable");
  for (const tableId of tableIds) {
    if (deadline - now() <= 61_000) { addReadError(`database:${tableId}`, "citadel_scan_timeout"); break; }
    if (!Number.isSafeInteger(Number(tableId))) { addReadError(`database:${tableId}`, "citadel_database_meta_unavailable", false); continue; }
    const meta = await read(["citadel-database", "getTableMeta", "--tableId", tableId, ...authArgs], 1024 * 1024);
    const metaTerminal = meta.exitCode !== 0 ? terminalFailureCode(meta) : null;
    if (metaTerminal) return terminalFailure(`database:${tableId}`, metaTerminal);
    const columnIds = jsonFrom(meta.stdout)?.columns?.map((column) => column.colId);
    if (meta.exitCode !== 0 || !Array.isArray(columnIds) || !columnIds.length || columnIds.some((id) => !/^\d{1,30}$/u.test(String(id)))) {
      addReadError(`database:${tableId}`, "citadel_database_meta_unavailable");
      continue;
    }
    let pageToken = "";
    let page = 0;
    const visited = new Set();
    do {
      page += 1;
      if (deadline - now() <= 61_000) { addReadError(`database:${tableId}:page:${page}`, "citadel_scan_timeout"); break; }
      const rows = await read([TABLE_PAGE_READER, tableId, JSON.stringify(columnIds), pageToken, actorMis], 16 * 1024 * 1024, process.execPath);
      const rowsTerminal = rows.exitCode !== 0 ? terminalFailureCode(rows) : null;
      if (rowsTerminal) return terminalFailure(`database:${tableId}:page:${page}`, rowsTerminal);
      const payload = rows.exitCode === 0 ? jsonFrom(rows.stdout) : null;
      if (!payload || !Array.isArray(payload.rows) || payload.rows.some((row) => !row || !Array.isArray(row.cellData) || row.cellData.some((cell) => !cell || typeof cell !== "object"))) {
        addReadError(`database:${tableId}:page:${page}`, "citadel_database_page_unavailable");
        break;
      }
      payload.rows.forEach((row) => row.cellData?.forEach((cell) => {
        const location = `database:${tableId}:row:${sourceLocationAtom(row.rowId)}:column:${sourceLocationAtom(cell.colId)}`;
        if (resultSchema === V3_SOURCE_RESULT_SCHEMA_V2) extract(cell, location);
        else for (const key of ["textCellValue", "selectCellValue", "multipleSelectCellValue"]) extract(cell[key], location);
      }));
      pageToken = String(payload.nextPageToken ?? "");
      if (pageToken && visited.has(pageToken)) {
        addReadError(`database:${tableId}:page:${page}`, "citadel_database_pagination_invalid", false);
        break;
      }
      if (pageToken) visited.add(pageToken);
    } while (pageToken);
  }
  const merged = new Map();
  found.forEach((item) => {
    const identity = resultSchema === V3_SOURCE_RESULT_SCHEMA_V2 ? item.raw_value : item.canonical_key;
    const existing = merged.get(identity);
    if (existing) existing.source_locations = [...new Set([...existing.source_locations, ...item.source_locations])];
    else merged.set(identity, item);
  });
  if (resultSchema !== V3_SOURCE_RESULT_SCHEMA_V2) {
    return { scan_status: issues.length ? (merged.size ? "partially_scanned" : "failed") : "completed", repositories: [...merged.values()], issues };
  }
  const mergedInvalid = new Map();
  invalidItems.forEach((item) => {
    const identity = `${item.error_code}\0${item.raw_value}`;
    const existing = mergedInvalid.get(identity);
    if (existing) existing.source_locations = [...new Set([...existing.source_locations, ...item.source_locations])];
    else mergedInvalid.set(identity, item);
  });
  return {
    scan_status: readErrors.length ? (merged.size || mergedInvalid.size ? "partially_scanned" : "failed") : "completed",
    candidates: [...merged.values()],
    invalid_items: [...mergedInvalid.values()],
    read_errors: readErrors,
  };
};

export const deliverSourceResult = async ({ context, result, fetchImpl = fetch, waitForRetry = wait, now = Date.now }) => {
  const resultHash = sha256(canonical(result));
  const isV2 = result.schema_version === V3_SOURCE_RESULT_SCHEMA_V2;
  const receiptSchema = isV2
    ? "repository-association-source-scan-callback-receipt/v2"
    : "repository-authority-source-scan-callback-receipt/v1";
  let lastError = null;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (context.deadline - now() <= 1_000) {
      throw new AuthorityRunnerError("source callback deadline has expired", { phase: "callback", errorCode: "callback_deadline_exceeded" });
    }
    try {
      const idempotencyKey = isV2
        ? `${context.shardId}:${context.generation}:${result.chunk_index}`
        : `${context.shardId}:${context.generation}`;
      const response = await fetchImpl(context.source.callback.url, { method: "POST", redirect: "error", signal: AbortSignal.timeout(Math.min(15_000, context.deadline - now() - 500)), headers: { Authorization: `Bearer ${context.source.callback.token}`, "Content-Type": "application/json", "Idempotency-Key": idempotencyKey }, body: canonical(result) });
      if (response.ok) {
        const envelope = await response.json();
        const receipt = envelope.data ?? envelope;
        if (receipt.schema_version !== receiptSchema || !["accepted", "duplicate"].includes(receipt.status) || receipt.run_id !== context.source.runId || receipt.shard_id !== context.shardId || receipt.generation !== context.generation || receipt.chunk_index !== result.chunk_index || receipt.result_hash !== resultHash) throw new AuthorityRunnerError("source callback receipt is invalid", { phase: "callback", errorCode: "callback_receipt_invalid" });
        return receipt;
      }
      lastError = new AuthorityRunnerError("source callback failed", { phase: "callback", errorCode: response.status === 401 || response.status === 403 ? "callback_unauthorized" : "callback_delivery_failed", retriable: response.status === 408 || response.status === 425 || response.status === 429 || response.status >= 500 });
    } catch (error) {
      lastError = error instanceof AuthorityRunnerError ? error : new AuthorityRunnerError("source callback failed", { phase: "callback", errorCode: "callback_network_error", retriable: true });
    }
    if (!lastError.retriable || attempt === 2) break;
    await waitForRetry(500 * (attempt + 1));
  }
  throw lastError ?? new AuthorityRunnerError("source callback failed", { phase: "callback", errorCode: "callback_delivery_failed" });
};

export const executeV3Task = async ({ taskPath, taskArtifactHash, outputPath, runtimeRoot, processRunner = runProcess, callbackRequest, fetchImpl, now = Date.now }) => {
  const context = validateV3TaskArtifact({ taskBytes: await readFile(taskPath), expectedTaskArtifactHash: taskArtifactHash, now: now() });
  let receipt;
  if (context.mode === V3_MODE_AUTHORITY) {
    const runtimeContext = { ...context.items[0], actorMis: context.actorMis, deadline: context.deadline };
    let runtime = null;
    let setupError = null;
    try { runtime = await ensureYuntuRuntime({ context: runtimeContext, runtimeRoot, processRunner, now }); }
    catch (error) { setupError = error; }
    const items = await mapLimit(context.items, V3_WORKERS, async (item) => {
      try { return await executeAuthorityItem({ context: { ...item, actorMis: context.actorMis, deadline: context.deadline }, runtime, setupError, processRunner, callbackRequest, now }); }
      catch (error) { return { item_id: item.itemId, status: "callback_failed", error: errorShape(error) }; }
    });
    receipt = { schema_version: V3_LOCAL_RECEIPT_SCHEMA, mode: context.mode, shard_id: context.shardId, generation: context.generation, items };
  } else if (context.mode === V3_MODE_SOURCE_SCAN) {
    const resultSchema = context.source.resultSchema ?? V3_SOURCE_RESULT_SCHEMA;
    const authSession = await createCitadelAuthSession();
    let scan;
    try {
      scan = await scanCitadelSource({ source: context.source, actorMis: context.actorMis, authEnvironment: authSession.env, resultSchema, deadline: context.deadline, processRunner, now });
    } finally {
      await authSession.cleanup();
    }
    const result = { schema_version: resultSchema, run_id: context.source.runId, shard_id: context.shardId, generation: context.generation, scan_revision: context.source.scanRevision, execution_mis: context.actorMis, ...scan };
    let callback;
    const entries = resultSchema === V3_SOURCE_RESULT_SCHEMA_V2
      ? [
          ...scan.candidates.map((value) => ({ type: "candidate", value })),
          ...scan.invalid_items.map((value) => ({ type: "invalid", value })),
          ...scan.read_errors.map((value) => ({ type: "read_error", value })),
        ]
      : [...scan.repositories.map((value) => ({ type: "repository", value })), ...scan.issues.map((value) => ({ type: "issue", value }))];
    const chunks = splitSourceEntries(entries);
    for (let index = 0; index < chunks.length; index += 1) {
      const chunkPayload = resultSchema === V3_SOURCE_RESULT_SCHEMA_V2
        ? {
            candidates: chunks[index].filter((entry) => entry.type === "candidate").map((entry) => entry.value),
            invalid_items: chunks[index].filter((entry) => entry.type === "invalid").map((entry) => entry.value),
            read_errors: chunks[index].filter((entry) => entry.type === "read_error").map((entry) => entry.value),
          }
        : {
            repositories: chunks[index].filter((entry) => entry.type === "repository").map((entry) => entry.value),
            issues: chunks[index].filter((entry) => entry.type === "issue").map((entry) => entry.value),
          };
      callback = await deliverSourceResult({ context, result: { ...result, chunk_index: index, is_final: index === chunks.length - 1, ...chunkPayload }, fetchImpl, now });
    }
    receipt = { schema_version: V3_LOCAL_RECEIPT_SCHEMA, mode: context.mode, shard_id: context.shardId, generation: context.generation, callback_status: callback.status, scan_status: scan.scan_status };
  }
  await writeAtomic(outputPath, receipt);
  return receipt;
};

export const splitSourceEntries = (entries) => {
  const maxBytes = 240 * 1024;
  const boundedEntries = function* () {
    for (const entry of entries) {
      if (!Array.isArray(entry.value?.source_locations) || Buffer.byteLength(JSON.stringify(entry)) <= maxBytes) { yield entry; continue; }
      const base = Buffer.byteLength(JSON.stringify({ ...entry, value: { ...entry.value, source_locations: [] } }));
      let locations = [];
      let size = base;
      for (const location of entry.value.source_locations) {
        const added = Buffer.byteLength(JSON.stringify(location)) + 1;
        if (base + added > maxBytes) throw new AuthorityContractError("source location is too large");
        if (locations.length && size + added > maxBytes) {
          yield { ...entry, value: { ...entry.value, source_locations: locations } };
          locations = []; size = base;
        }
        locations.push(location); size += added;
      }
      if (locations.length) yield { ...entry, value: { ...entry.value, source_locations: locations } };
    }
  };
  const chunks = [];
  let current = [];
  let bytes = 0;
  for (const entry of boundedEntries()) {
    const size = Buffer.byteLength(JSON.stringify(entry));
    if (current.length && (current.length >= 500 || bytes + size > maxBytes)) { chunks.push(current); current = []; bytes = 0; }
    current.push(entry); bytes += size;
  }
  if (current.length || !chunks.length) chunks.push(current);
  return chunks;
};

const args = (argv) => {
  const allowed = new Set(["--task", "--task-artifact-hash", "--output"]);
  if (argv.length !== 6 || argv.some((value, index) => index % 2 === 0 && !allowed.has(value)) || new Set(argv.filter((_, index) => index % 2 === 0)).size !== 3) {
    throw new AuthorityRunnerError("Runner arguments are invalid");
  }
  const values = Object.fromEntries(Array.from({ length: argv.length / 2 }, (_, index) => [argv[index * 2], argv[index * 2 + 1]]));
  if (!values["--task"] || !values["--task-artifact-hash"] || !values["--output"]) throw new AuthorityRunnerError("Runner arguments are invalid");
  return { taskPath: resolve(values["--task"]), taskArtifactHash: values["--task-artifact-hash"], outputPath: resolve(values["--output"]) };
};

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  try { process.stdout.write(`${JSON.stringify(await executeV3Task(args(process.argv.slice(2))))}\n`); }
  catch (error) { process.stderr.write(`${JSON.stringify(errorShape(error))}\n`); process.exitCode = 1; }
}
