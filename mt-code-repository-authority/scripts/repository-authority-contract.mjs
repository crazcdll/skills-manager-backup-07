import { createHash } from "node:crypto";

export const TASK_SCHEMA = "repository-authority-task/v1";
export const RESULT_SCHEMA = "repository-authority-runner-result/v1";
export const CALLBACK_RECEIPT_SCHEMA = "repository-authority-callback-receipt/v1";
export const SKILL_CONTRACT_VERSION = "mt-code-repository-authority/v1";
export const YUNTU_PACKAGE = "@ee/yuntu-cli";
export const YUNTU_VERSION = "1.0.15";
export const YUNTU_REGISTRY = "http://r.npm.sankuai.com";
export const YUNTU_AUDIENCE = "Metrics";
export const CALLBACK_HOST = "db0y7dgg85gphojyva.database.sankuai.com";

export const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
export const HASH = /^sha256:[0-9a-f]{64}$/;
export const MIS = /^[a-z][a-z0-9._-]{0,63}$/;
export const CALLBACK_TOKEN = /^[A-Za-z0-9_-]{43,256}$/;
export const CANONICAL_REPOSITORY = /^~?[a-z0-9._-]+\/[a-z0-9._-]+$/;
export const MAX_TASK_BYTES = 64 * 1024;
export const MAX_RESULT_BYTES = 64 * 1024;
export const MAX_PROVIDER_BYTES = 256 * 1024;
export const MAX_TASK_TTL_MS = 15 * 60 * 1000;

const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f-\u009f]/u;

const stable = (value) => Array.isArray(value)
  ? value.map(stable)
  : value && typeof value === "object"
    ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]))
    : value;

export const canonical = (value) => JSON.stringify(stable(value));

export const sha256 = (value) => {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(String(value), "utf8");
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
};

export class AuthorityContractError extends Error {
  constructor(message, {
    phase = "result_validation",
    errorCode = "result_invalid",
    retriable = false,
  } = {}) {
    super(message);
    this.name = "AuthorityContractError";
    this.phase = phase;
    this.errorCode = errorCode;
    this.retriable = retriable;
  }
}

export class AuthorityUnresolvedError extends AuthorityContractError {
  constructor(message, options = {}) {
    super(message, { retriable: false, ...options });
    this.name = "AuthorityUnresolvedError";
  }
}

export const exactObject = (value, keys, label) => {
  if (
    !value || typeof value !== "object" || Array.isArray(value) ||
    Object.keys(value).length !== keys.size ||
    Object.keys(value).some((key) => !keys.has(key))
  ) {
    throw new AuthorityContractError(`${label} fields are invalid`, {
      phase: "task_validation",
      errorCode: "task_invalid",
    });
  }
  return value;
};

const requiredText = (value, label, maxLength, pattern) => {
  if (typeof value !== "string") {
    throw new AuthorityContractError(`${label} is invalid`);
  }
  const normalized = value.trim();
  if (
    !normalized || normalized.length > maxLength ||
    CONTROL_CHARACTERS.test(normalized) || (pattern && !pattern.test(normalized))
  ) {
    throw new AuthorityContractError(`${label} is invalid`);
  }
  return normalized;
};

const organizationName = (value, label) => {
  const normalized = requiredText(value, label, 160);
  if (normalized.includes("/")) {
    throw new AuthorityContractError(`${label} contains the path delimiter`, {
      phase: "organization_lookup",
      errorCode: "organization_path_invalid",
    });
  }
  return normalized;
};

const positiveId = (value, label) => {
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || value <= 0) {
      throw new AuthorityContractError(`${label} is not a safe positive integer`, {
        phase: "organization_lookup",
        errorCode: "organization_result_invalid",
      });
    }
    return String(value);
  }
  const normalized = requiredText(value, label, 32, /^[1-9][0-9]{0,31}$/);
  return normalized;
};

export const parseUtf8Json = (bytes, label, maxBytes) => {
  if (!Buffer.isBuffer(bytes) || bytes.byteLength < 2 || bytes.byteLength > maxBytes) {
    throw new AuthorityContractError(`${label} size is invalid`, {
      phase: label === "task" ? "task_validation" : "result_validation",
      errorCode: label === "task" ? "task_invalid" : "provider_output_invalid",
    });
  }
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new AuthorityContractError(`${label} is not valid UTF-8`, {
      phase: label === "task" ? "task_validation" : "result_validation",
      errorCode: label === "task" ? "task_invalid" : "provider_output_invalid",
    });
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new AuthorityContractError(`${label} is not valid JSON`, {
      phase: label === "task" ? "task_validation" : "result_validation",
      errorCode: label === "task" ? "task_invalid" : "provider_output_invalid",
    });
  }
};

const validateCallbackUrl = (raw, attemptId) => {
  let url;
  try {
    url = new URL(raw);
  } catch {
    throw new AuthorityContractError("callback URL is invalid", {
      phase: "task_validation",
      errorCode: "task_invalid",
    });
  }
  const expectedPath =
    `/functions/v1/rule-observability/internal/repository-authority/attempts/${attemptId}/result`;
  if (
    url.protocol !== "https:" || url.hostname !== CALLBACK_HOST ||
    (url.port && url.port !== "443") || url.username || url.password ||
    url.search || url.hash || url.pathname !== expectedPath
  ) {
    throw new AuthorityContractError("callback URL is outside the allowed endpoint", {
      phase: "task_validation",
      errorCode: "task_invalid",
    });
  }
  return url.toString();
};

export const validateTaskArtifact = ({
  taskBytes,
  expectedTaskArtifactHash,
  now = Date.now(),
}) => {
  if (!HASH.test(String(expectedTaskArtifactHash ?? ""))) {
    throw new AuthorityContractError("task artifact hash is invalid", {
      phase: "task_validation",
      errorCode: "task_hash_invalid",
    });
  }
  const actualHash = sha256(taskBytes);
  if (actualHash !== expectedTaskArtifactHash) {
    throw new AuthorityContractError("task artifact hash does not match", {
      phase: "task_validation",
      errorCode: "task_hash_mismatch",
    });
  }
  const task = exactObject(
    parseUtf8Json(taskBytes, "task", MAX_TASK_BYTES),
    new Set([
      "schema_version", "skill_contract_version", "job_id", "attempt_id",
      "runner_invocation_id", "request_hash", "actor", "repository", "execution",
    ]),
    "task",
  );
  if (
    task.schema_version !== TASK_SCHEMA ||
    task.skill_contract_version !== SKILL_CONTRACT_VERSION ||
    !UUID.test(String(task.job_id ?? "")) ||
    !UUID.test(String(task.attempt_id ?? "")) ||
    !UUID.test(String(task.runner_invocation_id ?? "")) ||
    !HASH.test(String(task.request_hash ?? ""))
  ) {
    throw new AuthorityContractError("task identity is invalid", {
      phase: "task_validation",
      errorCode: "task_invalid",
    });
  }
  const actor = exactObject(task.actor, new Set(["mis", "source"]), "task actor");
  const actorMis = requiredText(actor.mis, "actor.mis", 64, MIS).toLowerCase();
  if (actor.source !== "verified-edge") {
    throw new AuthorityContractError("task actor source is invalid", {
      phase: "task_validation",
      errorCode: "task_invalid",
    });
  }
  const repository = exactObject(
    task.repository,
    new Set(["canonical_key", "canonical_https_url", "canonical_ssh_url"]),
    "task repository",
  );
  const canonicalKey = requiredText(
    repository.canonical_key,
    "repository.canonical_key",
    201,
    CANONICAL_REPOSITORY,
  ).toLowerCase();
  const expectedHttps =
    `https://dev.sankuai.com/code/repo-detail/${canonicalKey}/file/list`;
  const expectedSsh = `ssh://git@git.sankuai.com/${canonicalKey}.git`;
  if (
    repository.canonical_key !== canonicalKey ||
    repository.canonical_https_url !== expectedHttps ||
    repository.canonical_ssh_url !== expectedSsh
  ) {
    throw new AuthorityContractError("repository canonical fields do not agree", {
      phase: "task_validation",
      errorCode: "task_invalid",
    });
  }
  const execution = exactObject(
    task.execution,
    new Set(["deadline", "expected_result_schema", "callback"]),
    "task execution",
  );
  const deadline = Date.parse(String(execution.deadline ?? ""));
  if (
    !Number.isFinite(deadline) || deadline <= now ||
    deadline - now > MAX_TASK_TTL_MS ||
    execution.expected_result_schema !== RESULT_SCHEMA
  ) {
    throw new AuthorityContractError("task deadline or result schema is invalid", {
      phase: "task_validation",
      errorCode: deadline <= now ? "deadline_exceeded" : "task_invalid",
    });
  }
  const callback = exactObject(
    execution.callback,
    new Set(["url", "token"]),
    "task callback",
  );
  if (!CALLBACK_TOKEN.test(String(callback.token ?? ""))) {
    throw new AuthorityContractError("callback capability is invalid", {
      phase: "task_validation",
      errorCode: "task_invalid",
    });
  }
  return {
    task,
    taskArtifactHash: actualHash,
    jobId: task.job_id,
    attemptId: task.attempt_id,
    runnerInvocationId: task.runner_invocation_id,
    requestHash: task.request_hash,
    actorMis,
    repository: {
      canonicalKey,
      canonicalHttpsUrl: expectedHttps,
      canonicalSshUrl: expectedSsh,
    },
    deadline,
    callback: {
      url: validateCallbackUrl(callback.url, task.attempt_id),
      token: callback.token,
    },
  };
};

const optionalRepositoryIdentity = (payload) => {
  const values = [
    payload.canonical_key,
    payload.canonicalKey,
    payload.path_with_namespace,
    payload.pathWithNamespace,
    payload.full_name,
    payload.fullName,
  ].filter((value) => typeof value === "string" && value.trim());
  const normalized = [...new Set(values.map((value) => value.trim().toLowerCase()))];
  return normalized;
};

export const normalizeCodeCliRepository = (raw, expectedCanonicalKey) => {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new AuthorityContractError("ee-code output is not an object", {
      phase: "repository_lookup",
      errorCode: "repository_result_invalid",
    });
  }
  const payload = raw.data && typeof raw.data === "object" && !Array.isArray(raw.data)
    ? raw.data
    : raw;
  const identities = optionalRepositoryIdentity(payload);
  if (identities.length > 1 || (identities.length === 1 && identities[0] !== expectedCanonicalKey)) {
    throw new AuthorityContractError("ee-code returned another repository", {
      phase: "repository_lookup",
      errorCode: "repository_identity_mismatch",
    });
  }
  if (!payload.owner || typeof payload.owner !== "object" || Array.isArray(payload.owner)) {
    throw new AuthorityUnresolvedError("repository owner is unavailable", {
      phase: "repository_lookup",
      errorCode: "repository_owner_not_found",
    });
  }
  const ownerMisValue = payload.owner.mis ?? payload.owner.misId ?? payload.owner.mis_id;
  if (ownerMisValue === null || ownerMisValue === undefined || String(ownerMisValue).trim() === "") {
    throw new AuthorityUnresolvedError("repository owner MIS is unavailable", {
      phase: "repository_lookup",
      errorCode: "repository_owner_not_found",
    });
  }
  const ownerMis = requiredText(
    String(ownerMisValue).toLowerCase(),
    "owner.mis",
    64,
    MIS,
  );
  const displayValue = payload.owner.name ?? payload.owner.display_name ??
    payload.owner.displayName ?? null;
  const ownerDisplayName = typeof displayValue === "string" && displayValue.trim()
    ? requiredText(displayValue, "owner.display_name", 160)
    : null;
  const branchValues = [payload.default_branch, payload.defaultBranch]
    .filter((value) => typeof value === "string" && value.trim())
    .map((value) => value.trim());
  if (new Set(branchValues).size > 1) {
    throw new AuthorityContractError("ee-code default branch is ambiguous", {
      phase: "repository_lookup",
      errorCode: "repository_result_invalid",
    });
  }
  const defaultBranch = branchValues[0] ?? null;
  if (
    defaultBranch !== null &&
    (defaultBranch.length > 200 || !/^[A-Za-z0-9][A-Za-z0-9/._-]{0,199}$/.test(defaultBranch))
  ) {
    throw new AuthorityContractError("ee-code default branch is invalid", {
      phase: "repository_lookup",
      errorCode: "repository_result_invalid",
    });
  }
  return { ownerMis, ownerDisplayName, defaultBranch };
};

const splitSlashPath = (raw, label) => {
  const path = requiredText(raw, label, 1500);
  if (!path.startsWith("/") || !path.endsWith("/") || path.includes("//")) {
    throw new AuthorityContractError(`${label} must be an absolute slash path`, {
      phase: "organization_lookup",
      errorCode: "organization_path_invalid",
    });
  }
  const segments = path.slice(1, -1).split("/");
  if (
    segments.length < 1 || segments.length > 32 ||
    segments.some((segment) => !segment.trim() || segment !== segment.trim() ||
      segment.length > 160 || CONTROL_CHARACTERS.test(segment))
  ) {
    throw new AuthorityContractError(`${label} segments are invalid`, {
      phase: "organization_lookup",
      errorCode: "organization_path_invalid",
    });
  }
  return segments;
};

export const normalizeYuntuOrganization = (raw, expectedMis) => {
  if (raw === null) {
    throw new AuthorityUnresolvedError("Yuntu did not find an organization", {
      phase: "organization_lookup",
      errorCode: "organization_not_found",
    });
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new AuthorityContractError("Yuntu output is not an object", {
      phase: "organization_lookup",
      errorCode: "organization_result_invalid",
    });
  }
  if (!Object.keys(raw).length) {
    throw new AuthorityUnresolvedError("Yuntu did not find an organization", {
      phase: "organization_lookup",
      errorCode: "organization_not_found",
    });
  }
  const mis = requiredText(String(raw.misId ?? "").toLowerCase(), "misId", 64, MIS);
  if (mis !== expectedMis) {
    throw new AuthorityContractError("Yuntu returned another employee", {
      phase: "organization_lookup",
      errorCode: "organization_identity_mismatch",
    });
  }
  const name = requiredText(raw.name, "name", 160);
  const orgId = positiveId(raw.orgId, "orgId");
  const orgName = organizationName(raw.orgName, "orgName");
  const names = splitSlashPath(raw.fullPath, "fullPath");
  const ids = splitSlashPath(raw.orgIdPath, "orgIdPath")
    .map((value, index) => positiveId(value, `orgIdPath[${index}]`));
  if (
    names.length !== ids.length || new Set(ids).size !== ids.length ||
    ids.at(-1) !== orgId || names.at(-1) !== orgName
  ) {
    throw new AuthorityContractError("Yuntu organization paths do not agree", {
      phase: "organization_lookup",
      errorCode: "organization_path_invalid",
    });
  }
  return {
    mis,
    name,
    sourceOrganizationId: orgId,
    displayName: orgName,
    fullPath: names.join("/"),
    chain: ids.map((sourceOrganizationId, index) => ({
      source_organization_id: sourceOrganizationId,
      display_name: names[index],
    })),
  };
};

export const emptyTimings = () => ({
  runtime_install_ms: null,
  repository_lookup_ms: null,
  metrics_token_exchange_ms: null,
  yuntu_lookup_ms: null,
  identity_enrichment_ms: null,
  total_ms: null,
});

const normalizeTimings = (value) => {
  const timings = exactObject(
    value,
    new Set([
      "runtime_install_ms", "repository_lookup_ms", "metrics_token_exchange_ms",
      "yuntu_lookup_ms", "identity_enrichment_ms", "total_ms",
    ]),
    "timings_ms",
  );
  for (const [key, item] of Object.entries(timings)) {
    if (item !== null && (!Number.isSafeInteger(item) || item < 0 || item > 15 * 60 * 1000)) {
      throw new AuthorityContractError(`timings_ms.${key} is invalid`);
    }
  }
  return timings;
};

export const buildRunnerResult = ({
  context,
  executionStatus,
  resolutionStatus,
  repository,
  owner,
  organization,
  versions,
  verifiedAt,
  timings,
  error,
}) => {
  const result = {
    schema_version: RESULT_SCHEMA,
    attempt_id: context.attemptId,
    runner_invocation_id: context.runnerInvocationId,
    request_hash: context.requestHash,
    task_artifact_hash: context.taskArtifactHash,
    execution_status: executionStatus,
    resolution_status: resolutionStatus,
    repository,
    owner,
    organization,
    evidence: {
      skill_contract_version: SKILL_CONTRACT_VERSION,
      ee_code_cli_version: versions.eeCodeCliVersion,
      yuntu_cli_version: versions.yuntuCliVersion,
      account_mapping_contract_version: null,
      verified_at: verifiedAt,
      timings_ms: normalizeTimings(timings),
    },
    error,
  };
  validateRunnerResult(result);
  const bytes = Buffer.from(JSON.stringify(result), "utf8");
  if (bytes.byteLength > MAX_RESULT_BYTES) {
    throw new AuthorityContractError("runner result is too large", {
      phase: "result_validation",
      errorCode: "result_invalid",
    });
  }
  return result;
};

export const validateRunnerResult = (result) => {
  exactObject(result, new Set([
    "schema_version", "attempt_id", "runner_invocation_id", "request_hash",
    "task_artifact_hash", "execution_status", "resolution_status", "repository",
    "owner", "organization", "evidence", "error",
  ]), "runner result");
  if (
    result.schema_version !== RESULT_SCHEMA ||
    !UUID.test(String(result.attempt_id ?? "")) ||
    !UUID.test(String(result.runner_invocation_id ?? "")) ||
    !HASH.test(String(result.request_hash ?? "")) ||
    !HASH.test(String(result.task_artifact_hash ?? ""))
  ) throw new AuthorityContractError("runner result identity is invalid");
  const repository = exactObject(
    result.repository,
    new Set(["canonical_key", "default_branch"]),
    "result repository",
  );
  requiredText(repository.canonical_key, "repository.canonical_key", 201, CANONICAL_REPOSITORY);
  if (
    repository.default_branch !== null &&
    (typeof repository.default_branch !== "string" ||
      !/^[A-Za-z0-9][A-Za-z0-9/._-]{0,199}$/.test(repository.default_branch))
  ) throw new AuthorityContractError("repository.default_branch is invalid");
  const evidence = exactObject(result.evidence, new Set([
    "skill_contract_version", "ee_code_cli_version", "yuntu_cli_version",
    "account_mapping_contract_version", "verified_at", "timings_ms",
  ]), "result evidence");
  if (
    evidence.skill_contract_version !== SKILL_CONTRACT_VERSION ||
    typeof evidence.ee_code_cli_version !== "string" ||
    typeof evidence.yuntu_cli_version !== "string" ||
    !(evidence.account_mapping_contract_version === null ||
      (typeof evidence.account_mapping_contract_version === "string" &&
        evidence.account_mapping_contract_version.trim() &&
        evidence.account_mapping_contract_version.length <= 120)) ||
    !Number.isFinite(Date.parse(String(evidence.verified_at ?? "")))
  ) throw new AuthorityContractError("result evidence is invalid");
  normalizeTimings(evidence.timings_ms);
  if (result.execution_status === "succeeded") {
    if (!new Set(["confirmed", "unresolved"]).has(result.resolution_status)) {
      throw new AuthorityContractError("successful result resolution is invalid");
    }
    if (result.resolution_status === "confirmed") {
      const owner = exactObject(result.owner, new Set([
        "mis", "display_name", "iam_emp_id", "identity_enrichment_status",
      ]), "result owner");
      requiredText(owner.mis, "owner.mis", 64, MIS);
      requiredText(owner.display_name, "owner.display_name", 160);
      const identityStatus = owner.identity_enrichment_status;
      if (!new Set(["not_requested", "resolved", "unavailable"])
        .has(identityStatus) ||
        (identityStatus === "resolved"
          ? typeof owner.iam_emp_id !== "string" ||
            !/^[A-Za-z0-9._:-]{1,128}$/.test(owner.iam_emp_id)
          : owner.iam_emp_id !== null) ||
        (identityStatus === "not_requested"
          ? evidence.account_mapping_contract_version !== null
          : evidence.account_mapping_contract_version === null)) {
        throw new AuthorityContractError("owner identity enrichment is invalid");
      }
      const organization = exactObject(result.organization, new Set([
        "source_system", "source_organization_id", "display_name", "full_path", "chain",
      ]), "result organization");
      if (organization.source_system !== "yuntu_org") {
        throw new AuthorityContractError("organization source is invalid");
      }
      positiveId(organization.source_organization_id, "source_organization_id");
      organizationName(organization.display_name, "organization.display_name");
      requiredText(organization.full_path, "organization.full_path", 1500);
      if (!Array.isArray(organization.chain) || !organization.chain.length ||
          organization.chain.length > 32) {
        throw new AuthorityContractError("organization chain is invalid");
      }
      const chain = organization.chain.map((item, index) => {
        exactObject(item, new Set(["source_organization_id", "display_name"]), `chain[${index}]`);
        return {
          source_organization_id: positiveId(item.source_organization_id, `chain[${index}].id`),
          display_name: organizationName(item.display_name, `chain[${index}].name`),
        };
      });
      if (
        new Set(chain.map((item) => item.source_organization_id)).size !== chain.length ||
        chain.at(-1).source_organization_id !== organization.source_organization_id ||
        chain.at(-1).display_name !== organization.display_name ||
        chain.map((item) => item.display_name).join("/") !== organization.full_path ||
        result.error !== null
      ) throw new AuthorityContractError("confirmed organization is inconsistent");
    } else {
      if (result.organization !== null || result.error === null) {
        throw new AuthorityContractError("unresolved result is incomplete");
      }
      if (result.owner !== null) {
        const owner = exactObject(result.owner, new Set([
          "mis", "display_name", "iam_emp_id", "identity_enrichment_status",
        ]), "unresolved owner");
        requiredText(owner.mis, "owner.mis", 64, MIS);
        if (owner.display_name !== null) requiredText(owner.display_name, "owner.display_name", 160);
        const identityStatus = owner.identity_enrichment_status;
        if (!new Set(["not_requested", "resolved", "unavailable"])
          .has(identityStatus) ||
          (identityStatus === "resolved"
            ? typeof owner.iam_emp_id !== "string" ||
              !/^[A-Za-z0-9._:-]{1,128}$/.test(owner.iam_emp_id)
            : owner.iam_emp_id !== null) ||
          (identityStatus === "not_requested"
            ? evidence.account_mapping_contract_version !== null
            : evidence.account_mapping_contract_version === null)) {
          throw new AuthorityContractError("unresolved owner enrichment is invalid");
        }
      }
    }
  } else if (result.execution_status === "failed") {
    if (
      result.resolution_status !== null || result.owner !== null ||
      result.organization !== null || result.error === null
    ) throw new AuthorityContractError("failed result is inconsistent");
  } else {
    throw new AuthorityContractError("execution_status is invalid");
  }
  if (result.error !== null) {
    const error = exactObject(
      result.error,
      new Set(["phase", "error_code", "retriable"]),
      "result error",
    );
    requiredText(error.phase, "error.phase", 64, /^[a-z][a-z0-9_]{1,63}$/);
    requiredText(error.error_code, "error.error_code", 100, /^[a-z][a-z0-9_]{1,99}$/);
    if (typeof error.retriable !== "boolean") {
      throw new AuthorityContractError("error.retriable is invalid");
    }
  }
  return result;
};
