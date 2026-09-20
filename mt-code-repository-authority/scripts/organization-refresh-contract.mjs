import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import {
  HASH,
  MIS,
  UUID,
  CALLBACK_HOST,
  canonical,
  sha256,
} from "./repository-authority-contract.mjs";

export const TASK_SCHEMA = "organization-refresh-task/v1";
export const RESULT_SCHEMA = "organization-refresh-item-result/v1";
export const RECEIPT_SCHEMA = "organization-refresh-callback-receipt/v1";
export const LOCAL_RECEIPT_SCHEMA = "organization-refresh-local-receipt/v1";
export const SKILL_CONTRACT_VERSION = "mt-code-repository-authority/v2";
export const MAX_ITEMS = 10;
export const MAX_TASK_BYTES = 64 * 1024;
export const MAX_RESULT_BYTES = 64 * 1024;
export const MAX_TASK_TTL_MS = 25 * 60 * 1000;

const CALLBACK_TOKEN = /^[A-Za-z0-9_-]{43,256}$/;

export class OrganizationRefreshContractError extends Error {
  constructor(message, { phase = "task_validation", errorCode = "task_invalid", retriable = false } = {}) {
    super(message);
    this.name = "OrganizationRefreshContractError";
    this.phase = phase;
    this.errorCode = errorCode;
    this.retriable = retriable;
  }
}

const exactKeys = (value, expected, label) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new OrganizationRefreshContractError(`${label} must be an object`);
  }
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (canonical(actual) !== canonical(wanted)) {
    throw new OrganizationRefreshContractError(`${label} fields are invalid`);
  }
};

const callbackForAttempt = (value, attemptId) => {
  exactKeys(value, ["url", "token"], "callback");
  let url;
  try {
    url = new URL(value.url);
  } catch {
    throw new OrganizationRefreshContractError("callback URL is invalid");
  }
  if (
    url.protocol !== "https:" || url.hostname !== CALLBACK_HOST || url.port ||
    url.username || url.password || url.search || url.hash ||
    url.pathname !== `/functions/v1/rule-observability/internal/organization-refresh/attempts/${attemptId}/result` ||
    !CALLBACK_TOKEN.test(String(value.token ?? ""))
  ) throw new OrganizationRefreshContractError("callback capability is invalid");
  return { url: url.toString(), token: value.token };
};

export const validateTask = (raw, taskArtifactHash, now = Date.now()) => {
  exactKeys(raw, [
    "schema_version", "skill_contract_version", "run_id", "generation",
    "mode", "actor", "execution", "items",
  ], "task");
  exactKeys(raw.actor, ["mis", "source"], "actor");
  exactKeys(raw.execution, ["deadline", "expected_result_schema"], "execution");
  const deadline = Date.parse(raw.execution.deadline);
  if (
    raw.schema_version !== TASK_SCHEMA ||
    raw.skill_contract_version !== SKILL_CONTRACT_VERSION ||
    !UUID.test(String(raw.run_id ?? "")) ||
    !Number.isSafeInteger(raw.generation) || raw.generation < 1 ||
    !new Set(["dry_run", "apply"]).has(raw.mode) ||
    !MIS.test(String(raw.actor.mis ?? "")) || raw.actor.source !== "verified-edge" ||
    raw.execution.expected_result_schema !== RESULT_SCHEMA ||
    !Number.isFinite(deadline) || deadline <= now + 1_000 || deadline > now + MAX_TASK_TTL_MS ||
    !Array.isArray(raw.items) || raw.items.length < 1 || raw.items.length > MAX_ITEMS ||
    !HASH.test(String(taskArtifactHash ?? ""))
  ) throw new OrganizationRefreshContractError("task contract is invalid");

  const attempts = new Set();
  const itemIds = new Set();
  const invocations = new Set();
  const principals = new Set();
  const items = raw.items.map((item) => {
    exactKeys(item, [
      "item_id", "attempt_id", "runner_invocation_id", "principal_mis",
      "request_hash", "callback",
    ], "task item");
    if (
      !UUID.test(String(item.item_id ?? "")) ||
      !UUID.test(String(item.attempt_id ?? "")) ||
      !UUID.test(String(item.runner_invocation_id ?? "")) ||
      !MIS.test(String(item.principal_mis ?? "")) ||
      !HASH.test(String(item.request_hash ?? "")) ||
      attempts.has(item.attempt_id) || itemIds.has(item.item_id) ||
      invocations.has(item.runner_invocation_id) || principals.has(item.principal_mis)
    ) throw new OrganizationRefreshContractError("task item identity is invalid");
    attempts.add(item.attempt_id);
    itemIds.add(item.item_id);
    invocations.add(item.runner_invocation_id);
    principals.add(item.principal_mis);
    return {
      itemId: item.item_id,
      attemptId: item.attempt_id,
      runnerInvocationId: item.runner_invocation_id,
      principalMis: item.principal_mis,
      requestHash: item.request_hash,
      callback: callbackForAttempt(item.callback, item.attempt_id),
    };
  });
  return {
    runId: raw.run_id,
    generation: raw.generation,
    mode: raw.mode,
    actorMis: raw.actor.mis,
    deadline,
    items,
  };
};

export const readAndValidateTask = async (taskPath, taskArtifactHash, now = Date.now()) => {
  const bytes = await readFile(resolve(taskPath));
  if (bytes.byteLength < 2 || bytes.byteLength > MAX_TASK_BYTES || sha256(bytes) !== taskArtifactHash) {
    throw new OrganizationRefreshContractError("task artifact hash is invalid", {
      errorCode: "task_artifact_hash_mismatch",
    });
  }
  let parsed;
  try {
    parsed = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new OrganizationRefreshContractError("task artifact is not UTF-8 JSON");
  }
  return validateTask(parsed, taskArtifactHash, now);
};

export const buildResult = ({ context, item, executionStatus, organization, verifiedAt, error }) => {
  const result = {
    schema_version: RESULT_SCHEMA,
    run_id: context.runId,
    generation: context.generation,
    item_id: item.itemId,
    attempt_id: item.attemptId,
    runner_invocation_id: item.runnerInvocationId,
    principal_mis: item.principalMis,
    request_hash: item.requestHash,
    execution_status: executionStatus,
    organization,
    verified_at: verifiedAt,
    versions: { yuntu_cli_version: "1.0.15" },
    error,
  };
  const bytes = Buffer.byteLength(canonical(result), "utf8");
  if (bytes > MAX_RESULT_BYTES) {
    throw new OrganizationRefreshContractError("result is too large", {
      phase: "result_validation", errorCode: "result_too_large",
    });
  }
  return result;
};

export const normalizeRefreshOrganization = (organization) => ({
  source_organization_id: organization.sourceOrganizationId,
  display_name: organization.displayName,
  full_path: organization.fullPath,
  chain: organization.chain,
});

export const validateReceipt = (raw, expected) => {
  exactKeys(raw, [
    "schema_version", "status", "result_status", "attempt_id",
    "runner_invocation_id", "result_hash",
  ], "callback receipt");
  if (
    raw.schema_version !== RECEIPT_SCHEMA ||
    !new Set(["accepted", "duplicate"]).has(raw.status) ||
    !new Set(["observed", "failed"]).has(raw.result_status) ||
    raw.attempt_id !== expected.attemptId ||
    raw.runner_invocation_id !== expected.runnerInvocationId ||
    raw.result_hash !== expected.resultHash ||
    raw.result_status !== expected.resultStatus
  ) throw new OrganizationRefreshContractError("callback receipt is invalid", {
    phase: "callback", errorCode: "callback_response_invalid",
  });
  return raw;
};

export { canonical, sha256 };
