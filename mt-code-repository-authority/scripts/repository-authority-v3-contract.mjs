import {
  CALLBACK_HOST,
  CALLBACK_TOKEN,
  CANONICAL_REPOSITORY,
  HASH,
  MIS,
  MAX_TASK_BYTES,
  MAX_TASK_TTL_MS,
  UUID,
  AuthorityContractError,
  exactObject,
  parseUtf8Json,
  sha256,
} from "./repository-authority-contract.mjs";

export const V3_TASK_SCHEMA = "repository-authority-task/v3";
export const V3_SKILL_CONTRACT = "mt-code-repository-authority/v4";
export const V3_LEGACY_TASK_SCHEMA = "repository-authority-task/v2";
export const V3_LEGACY_SKILL_CONTRACT = "mt-code-repository-authority/v3";
export const V3_MODE_AUTHORITY = "authority_shard";
export const V3_MODE_SOURCE_SCAN = "source_scan";
export const V3_LOCAL_RECEIPT_SCHEMA = "repository-authority-local-receipt/v2";
export const V3_SOURCE_RESULT_SCHEMA = "repository-authority-source-scan-result/v1";
export const V3_SOURCE_RESULT_SCHEMA_V2 = "repository-association-source-scan-result/v2";
export const V3_MAX_ITEMS = 10;
export const V3_WORKERS = 2;

const CONTROL = /[\u0000-\u001f\u007f-\u009f]/u;
const requiredText = (value, label, maxLength, pattern) => {
  if (typeof value !== "string") throw new AuthorityContractError(`${label} is invalid`);
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength || CONTROL.test(normalized) || (pattern && !pattern.test(normalized))) {
    throw new AuthorityContractError(`${label} is invalid`);
  }
  return normalized;
};

const callback = (value, attemptId) => {
  const item = exactObject(value, new Set(["url", "token"]), "callback");
  if (!CALLBACK_TOKEN.test(String(item.token ?? ""))) throw new AuthorityContractError("callback token is invalid");
  let url;
  try { url = new URL(item.url); } catch { throw new AuthorityContractError("callback URL is invalid"); }
  const expected = `/functions/v1/rule-observability/internal/repository-authority/attempts/${attemptId}/result`;
  if (url.protocol !== "https:" || url.hostname !== CALLBACK_HOST || url.port || url.pathname !== expected || url.search || url.hash || url.username || url.password) {
    throw new AuthorityContractError("callback URL is outside the allowed endpoint");
  }
  return { url: url.toString(), token: item.token };
};

const authorityItem = (value, taskArtifactHash) => {
  const item = exactObject(value, new Set([
    "item_id", "job_id", "attempt_id", "runner_invocation_id", "request_hash",
    "repository", "callback",
  ]), "authority item");
  for (const key of ["item_id", "job_id", "attempt_id", "runner_invocation_id"]) {
    if (!UUID.test(String(item[key] ?? ""))) throw new AuthorityContractError(`authority item ${key} is invalid`);
  }
  if (!HASH.test(String(item.request_hash ?? ""))) throw new AuthorityContractError("authority item request_hash is invalid");
  const repository = exactObject(item.repository, new Set([
    "canonical_key", "canonical_https_url", "canonical_ssh_url",
  ]), "authority repository");
  const canonicalKey = requiredText(repository.canonical_key, "canonical_key", 201, CANONICAL_REPOSITORY).toLowerCase();
  const httpsUrl = `https://dev.sankuai.com/code/repo-detail/${canonicalKey}/file/list`;
  const sshUrl = `ssh://git@git.sankuai.com/${canonicalKey}.git`;
  if (repository.canonical_key !== canonicalKey || repository.canonical_https_url !== httpsUrl || repository.canonical_ssh_url !== sshUrl) {
    throw new AuthorityContractError("repository canonical fields do not agree");
  }
  return {
    itemId: item.item_id,
    jobId: item.job_id,
    attemptId: item.attempt_id,
    runnerInvocationId: item.runner_invocation_id,
    requestHash: item.request_hash,
    taskArtifactHash,
    repository: { canonicalKey, canonicalHttpsUrl: httpsUrl, canonicalSshUrl: sshUrl },
    callback: callback(item.callback, item.attempt_id),
  };
};

export const validateV3TaskArtifact = ({ taskBytes, expectedTaskArtifactHash, now = Date.now() }) => {
  if (!HASH.test(String(expectedTaskArtifactHash ?? "")) || sha256(taskBytes) !== expectedTaskArtifactHash) {
    throw new AuthorityContractError("task artifact hash does not match");
  }
  const task = exactObject(
    parseUtf8Json(taskBytes, "task", MAX_TASK_BYTES),
    new Set(["schema_version", "skill_contract_version", "mode", "shard_id", "generation", "actor", "execution", "payload"]),
    "task",
  );
  const currentContract = task.schema_version === V3_TASK_SCHEMA && task.skill_contract_version === V3_SKILL_CONTRACT;
  const legacyContract = task.schema_version === V3_LEGACY_TASK_SCHEMA && task.skill_contract_version === V3_LEGACY_SKILL_CONTRACT;
  if ((!currentContract && !legacyContract) || !UUID.test(String(task.shard_id ?? "")) || !Number.isSafeInteger(task.generation) || task.generation < 1) {
    throw new AuthorityContractError("task identity is invalid");
  }
  const actor = exactObject(task.actor, new Set(["mis", "source", "execution_mis"]), "actor");
  const actorMis = requiredText(actor.mis, "actor.mis", 64, MIS).toLowerCase();
  if (actor.source !== "verified-edge") throw new AuthorityContractError("task actor is invalid");
  const execution = exactObject(task.execution, new Set(["deadline", "workers", "expected_result_schema"]), "execution");
  const deadline = Date.parse(String(execution.deadline ?? ""));
  if (!Number.isFinite(deadline) || deadline <= now || deadline - now > MAX_TASK_TTL_MS || execution.workers !== V3_WORKERS) {
    throw new AuthorityContractError("task execution is invalid");
  }
  if (task.mode === V3_MODE_AUTHORITY) {
    if (!legacyContract || actor.execution_mis !== "zhangce07") throw new AuthorityContractError("authority task actor is invalid");
    if (execution.expected_result_schema !== "repository-authority-runner-result/v1" || !Array.isArray(task.payload) || task.payload.length < 1 || task.payload.length > V3_MAX_ITEMS) {
      throw new AuthorityContractError("authority shard payload is invalid");
    }
    const items = task.payload.map((item) => authorityItem(item, expectedTaskArtifactHash));
    if (["itemId", "jobId", "attemptId", "runnerInvocationId"].some((key) => new Set(items.map((item) => item[key])).size !== items.length) || new Set(items.map((item) => item.repository.canonicalKey)).size !== items.length) {
      throw new AuthorityContractError("authority shard contains duplicates");
    }
    return { task, mode: task.mode, shardId: task.shard_id, generation: task.generation, actorMis, deadline, items };
  }
  if (task.mode === V3_MODE_SOURCE_SCAN) {
    if (!currentContract || actor.execution_mis !== actorMis) throw new AuthorityContractError("source scan task actor is invalid");
    const payload = exactObject(task.payload, new Set(["run_id", "scan_revision", "citadel_url", "callback"]), "source scan payload");
    if (
      !UUID.test(String(payload.run_id ?? "")) || payload.scan_revision !== task.generation
      || execution.expected_result_schema !== V3_SOURCE_RESULT_SCHEMA_V2
    ) {
      throw new AuthorityContractError("source scan identity is invalid");
    }
    const url = new URL(requiredText(payload.citadel_url, "citadel_url", 1000));
    if (url.protocol !== "https:" || url.hostname !== "km.sankuai.com" || url.port || url.username || url.password || url.search || url.hash || !/^\/(?:page|collabpage)\/\d+\/?$/u.test(url.pathname)) {
      throw new AuthorityContractError("citadel URL is invalid");
    }
    const sourceCallback = exactObject(payload.callback, new Set(["url", "token"]), "source callback");
    if (!CALLBACK_TOKEN.test(String(sourceCallback.token ?? ""))) throw new AuthorityContractError("source callback token is invalid");
    let callbackUrl;
    try { callbackUrl = new URL(sourceCallback.url); } catch { throw new AuthorityContractError("source callback URL is invalid"); }
    const expectedPath = `/functions/v1/rule-observability/internal/repository-association/runs/${payload.run_id}/source-result`;
    if (callbackUrl.protocol !== "https:" || callbackUrl.hostname !== CALLBACK_HOST || callbackUrl.port || callbackUrl.pathname !== expectedPath || callbackUrl.search || callbackUrl.hash || callbackUrl.username || callbackUrl.password) {
      throw new AuthorityContractError("source callback URL is outside the allowed endpoint");
    }
    return {
      task,
      mode: task.mode,
      shardId: task.shard_id,
      generation: task.generation,
      actorMis,
      deadline,
      source: {
        runId: payload.run_id,
        scanRevision: payload.scan_revision,
        citadelUrl: url.toString(),
        resultSchema: execution.expected_result_schema,
        callback: { url: callbackUrl.toString(), token: sourceCallback.token },
      },
    };
  }
  throw new AuthorityContractError("task mode is invalid");
};
