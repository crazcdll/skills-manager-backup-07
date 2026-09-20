#!/usr/bin/env node

import { request as httpsRequest } from "node:https";
import { mkdir, rename, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as wait } from "node:timers/promises";

import {
  acquireMetricsToken,
  ensureYuntuRuntime,
  queryYuntuOrganization,
} from "./run-repository-authority.mjs";
import {
  LOCAL_RECEIPT_SCHEMA,
  OrganizationRefreshContractError,
  buildResult,
  canonical,
  normalizeRefreshOrganization,
  readAndValidateTask,
  sha256,
  validateReceipt,
} from "./organization-refresh-contract.mjs";

const CALLBACK_TIMEOUT_MS = 12_000;
const MAX_CALLBACK_BYTES = 8 * 1024;
const RETRY_DELAYS_MS = [250, 750];

const errorFields = (error) => ({
  phase: String(error?.phase || "organization_lookup").slice(0, 80),
  error_code: String(error?.errorCode || "organization_lookup_failed").slice(0, 100),
  retriable: error?.retriable === true,
});

const postJson = ({ url, token, idempotencyKey, body, timeoutMs }) => new Promise((accept, reject) => {
  let settled = false;
  let deadlineTimer;
  const finish = (operation, value) => {
    if (settled) return;
    settled = true;
    if (deadlineTimer) clearTimeout(deadlineTimer);
    operation(value);
  };
  const request = httpsRequest(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "Content-Length": String(Buffer.byteLength(body, "utf8")),
      "Idempotency-Key": idempotencyKey,
    },
  }, (response) => {
    const chunks = [];
    let bytes = 0;
    response.on("data", (chunk) => {
      bytes += chunk.length;
      if (bytes > MAX_CALLBACK_BYTES) {
        request.destroy(new Error("callback_response_too_large"));
      } else chunks.push(chunk);
    });
    response.on("aborted", () => finish(reject, new Error("callback_response_aborted")));
    response.on("error", (error) => finish(reject, error));
    response.on("end", () => finish(accept, {
      status: response.statusCode ?? 0,
      contentType: String(response.headers["content-type"] ?? ""),
      body: Buffer.concat(chunks).toString("utf8"),
    }));
  });
  deadlineTimer = setTimeout(() => request.destroy(new Error("callback_timeout")), timeoutMs);
  request.on("error", (error) => finish(reject, error));
  request.end(body);
});

export const deliverRefreshCallback = async ({ context, item, result, request = postJson, waitForRetry = wait, now = Date.now }) => {
  const body = canonical(result);
  const resultHash = sha256(body);
  const expected = {
    attemptId: item.attemptId,
    runnerInvocationId: item.runnerInvocationId,
    resultHash,
    resultStatus: result.execution_status === "succeeded" ? "observed" : "failed",
  };
  let lastError;
  for (let index = 0; index < 3; index += 1) {
    const remaining = context.deadline - now();
    if (remaining <= 1_000) throw new OrganizationRefreshContractError("callback deadline expired", {
      phase: "callback", errorCode: "callback_deadline_exceeded",
    });
    try {
      const response = await request({
        url: item.callback.url,
        token: item.callback.token,
        idempotencyKey: `${item.attemptId}:${item.runnerInvocationId}`,
        body,
        timeoutMs: Math.min(CALLBACK_TIMEOUT_MS, remaining - 500),
      });
      if (response.status >= 200 && response.status < 300 && response.contentType.includes("application/json")) {
        return validateReceipt(JSON.parse(response.body), expected);
      }
      const retriable = response.status === 408 || response.status === 425 || response.status === 429 || response.status >= 500;
      lastError = new OrganizationRefreshContractError("callback was rejected", {
        phase: "callback",
        errorCode: response.status === 401 || response.status === 403
          ? "callback_unauthorized" : response.status === 409
          ? "callback_conflict" : "callback_delivery_failed",
        retriable,
      });
    } catch (error) {
      lastError = error instanceof OrganizationRefreshContractError ? error
        : new OrganizationRefreshContractError("callback request failed", {
          phase: "callback", errorCode: "callback_network_error", retriable: true,
        });
    }
    if (!lastError.retriable || index === 2) break;
    await waitForRetry(RETRY_DELAYS_MS[index]);
  }
  throw lastError;
};

const writeJsonAtomic = async (path, value) => {
  const output = resolve(path);
  await mkdir(dirname(output), { recursive: true, mode: 0o700 });
  const temporary = `${output}.tmp-${process.pid}`;
  await writeFile(temporary, `${canonical(value)}\n`, { mode: 0o600 });
  await rename(temporary, output);
};

export const executeOrganizationRefresh = async ({ taskPath, taskArtifactHash, outputPath }, dependencies = {}) => {
  const now = dependencies.now ?? Date.now;
  const context = await readAndValidateTask(taskPath, taskArtifactHash, now());
  const providerContext = { actorMis: context.actorMis, deadline: context.deadline };
  let runtime;
  let metricsToken;
  let sharedFailure = null;
  try {
    runtime = await (dependencies.ensureRuntime ?? ensureYuntuRuntime)({
      context: providerContext,
      ...(dependencies.runtimeRoot ? { runtimeRoot: dependencies.runtimeRoot } : {}),
      ...(dependencies.processRunner ? { processRunner: dependencies.processRunner } : {}),
      ...(dependencies.now ? { now } : {}),
    });
    metricsToken = await (dependencies.acquireToken ?? acquireMetricsToken)({
      context: providerContext,
      ...(dependencies.processRunner ? { processRunner: dependencies.processRunner } : {}),
      ...(dependencies.now ? { now } : {}),
    });
  } catch (error) {
    sharedFailure = error;
  }

  const summaries = [];
  let callbackFailures = 0;
  for (const item of context.items) {
    let result;
    try {
      if (sharedFailure) throw sharedFailure;
      const organization = await (dependencies.queryOrganization ?? queryYuntuOrganization)({
        context: providerContext,
        runtime,
        owner: { ownerMis: item.principalMis },
        metricsToken,
        ...(dependencies.processRunner ? { processRunner: dependencies.processRunner } : {}),
        ...(dependencies.now ? { now } : {}),
      });
      result = buildResult({
        context,
        item,
        executionStatus: "succeeded",
        organization: normalizeRefreshOrganization(organization),
        verifiedAt: new Date(now()).toISOString(),
        error: null,
      });
    } catch (error) {
      result = buildResult({
        context,
        item,
        executionStatus: "failed",
        organization: null,
        verifiedAt: new Date(now()).toISOString(),
        error: errorFields(error),
      });
    }
    try {
      const receipt = await deliverRefreshCallback({
        context, item, result,
        ...(dependencies.callbackRequest ? { request: dependencies.callbackRequest } : {}),
        ...(dependencies.waitForRetry ? { waitForRetry: dependencies.waitForRetry } : {}),
        now,
      });
      summaries.push({
        principal_mis: item.principalMis,
        attempt_id: item.attemptId,
        execution_status: result.execution_status,
        callback_status: receipt.status,
        result_status: receipt.result_status,
      });
    } catch (error) {
      callbackFailures += 1;
      summaries.push({
        principal_mis: item.principalMis,
        attempt_id: item.attemptId,
        execution_status: result.execution_status,
        callback_status: "failed",
        result_status: null,
        callback_error: errorFields(error),
      });
    }
  }
  const output = {
    schema_version: LOCAL_RECEIPT_SCHEMA,
    run_id: context.runId,
    generation: context.generation,
    item_count: summaries.length,
    callback_failures: callbackFailures,
    items: summaries,
  };
  await writeJsonAtomic(outputPath, output);
  if (callbackFailures > 0) throw new OrganizationRefreshContractError("one or more callbacks failed", {
    phase: "callback", errorCode: "partial_callback_failure", retriable: true,
  });
  return output;
};

export const parseArgs = (argv) => {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!new Set(["--task", "--task-artifact-hash", "--output"]).has(key) || !value || values[key]) {
      throw new OrganizationRefreshContractError("runner arguments are invalid", { errorCode: "runner_arguments_invalid" });
    }
    values[key] = value;
  }
  if (!values["--task"] || !values["--output"] || !/^sha256:[0-9a-f]{64}$/.test(values["--task-artifact-hash"] ?? "")) {
    throw new OrganizationRefreshContractError("runner arguments are invalid", { errorCode: "runner_arguments_invalid" });
  }
  return {
    taskPath: resolve(values["--task"]),
    taskArtifactHash: values["--task-artifact-hash"],
    outputPath: resolve(values["--output"]),
  };
};

const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isMain) {
  try {
    const output = await executeOrganizationRefresh(parseArgs(process.argv.slice(2)));
    process.stdout.write(`${JSON.stringify(output)}\n`);
  } catch (error) {
    process.stderr.write(`${JSON.stringify({
      schema_version: "organization-refresh-local-error/v1",
      ...errorFields(error),
    })}\n`);
    process.exitCode = 1;
  }
}
