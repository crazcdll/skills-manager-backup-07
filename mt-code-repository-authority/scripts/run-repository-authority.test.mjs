import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";

import {
  AuthorityUnresolvedError,
  CALLBACK_RECEIPT_SCHEMA,
  RESULT_SCHEMA,
  SKILL_CONTRACT_VERSION,
  YUNTU_VERSION,
  buildRunnerResult,
  canonical,
  emptyTimings,
  normalizeCodeCliRepository,
  normalizeYuntuOrganization,
  sha256,
  validateRunnerResult,
  validateTaskArtifact,
} from "./repository-authority-contract.mjs";
import {
  AuthorityRunnerError,
  acquireMetricsToken,
  deliverAuthorityCallback,
  ensureYuntuRuntime,
  executeAuthorityTask,
  queryRepositoryOwner,
  queryYuntuOrganization,
  validateCallbackReceipt,
} from "./run-repository-authority.mjs";

const FIXTURES = join(dirname(new URL(import.meta.url).pathname), "fixtures");
const NOW = Date.parse("2099-01-01T00:00:00.000Z");
const GATEWAY_TOKEN = `AT_FOR_GW_BASE64_${"A".repeat(48)}`;

const fixture = async (name) => JSON.parse(
  await readFile(join(FIXTURES, name), "utf8"),
);

const taskArtifact = async (overrides = {}) => {
  const base = await fixture("task.valid.json");
  const task = {
    ...base,
    ...overrides,
    actor: { ...base.actor, ...(overrides.actor ?? {}) },
    repository: { ...base.repository, ...(overrides.repository ?? {}) },
    execution: {
      ...base.execution,
      ...(overrides.execution ?? {}),
      callback: {
        ...base.execution.callback,
        ...(overrides.execution?.callback ?? {}),
      },
    },
  };
  const bytes = Buffer.from(JSON.stringify(task), "utf8");
  return { task, bytes, hash: sha256(bytes) };
};

const resultContext = async () => {
  const artifact = await taskArtifact();
  return validateTaskArtifact({
    taskBytes: artifact.bytes,
    expectedTaskArtifactHash: artifact.hash,
    now: NOW,
  });
};

const makeInstallation = async (runtimeRoot) => {
  const installRoot = join(runtimeRoot, `yuntu-${YUNTU_VERSION}`);
  const packageRoot = join(installRoot, "node_modules", "@ee", "yuntu-cli");
  await mkdir(join(packageRoot, "dist"), { recursive: true });
  await writeFile(join(packageRoot, "package.json"), JSON.stringify({
    name: "@ee/yuntu-cli",
    version: YUNTU_VERSION,
  }));
  await writeFile(join(packageRoot, "dist", "index.js"), "#!/usr/bin/env node\n");
  return { installRoot, executablePath: join(packageRoot, "dist", "index.js") };
};

const okProcess = (stdout = "") => ({
  exitCode: 0,
  stdout: Buffer.from(stdout),
  stderr: Buffer.alloc(0),
  timedOut: false,
  spawnCode: null,
});

const failedProcess = ({ stderr = "", exitCode = 1, timedOut = false, spawnCode = null } = {}) => ({
  exitCode,
  stdout: Buffer.alloc(0),
  stderr: Buffer.from(stderr),
  timedOut,
  spawnCode,
});

test("validates a hash-bound task and preserves a personal repository namespace", async () => {
  const artifact = await taskArtifact();
  const context = validateTaskArtifact({
    taskBytes: artifact.bytes,
    expectedTaskArtifactHash: artifact.hash,
    now: NOW,
  });
  assert.equal(context.repository.canonicalKey, "~zhangce07/l2-rules-test");
  assert.equal(context.taskArtifactHash, artifact.hash);
  assert.equal(context.actorMis, "zhangce07");
  assert.throws(() => validateTaskArtifact({
    taskBytes: artifact.bytes,
    expectedTaskArtifactHash: artifact.hash,
    now: Date.parse(artifact.task.execution.deadline),
  }), (error) => error.errorCode === "deadline_exceeded");
});

test("rejects task hash mismatch, callback exfiltration and business target fields", async () => {
  const artifact = await taskArtifact();
  assert.throws(() => validateTaskArtifact({
    taskBytes: artifact.bytes,
    expectedTaskArtifactHash: `sha256:${"b".repeat(64)}`,
    now: NOW,
  }), (error) => error.errorCode === "task_hash_mismatch");

  const foreignCallback = await taskArtifact({
    execution: { callback: { url: artifact.task.execution.callback.url.replace(
      "db0y7dgg85gphojyva.database.sankuai.com",
      "example.com",
    ) } },
  });
  assert.throws(() => validateTaskArtifact({
    taskBytes: foreignCallback.bytes,
    expectedTaskArtifactHash: foreignCallback.hash,
    now: NOW,
  }), /callback URL/);

  const withTargetOrganization = Buffer.from(JSON.stringify({
    ...artifact.task,
    target_organization_id: "must-not-reach-runner",
  }));
  assert.throws(() => validateTaskArtifact({
    taskBytes: withTargetOrganization,
    expectedTaskArtifactHash: sha256(withTargetOrganization),
    now: NOW,
  }), /task fields/);
});

test("normalizes the ee-code owner without accepting another repository", async () => {
  const raw = await fixture("code-cli.repository.json");
  assert.deepEqual(normalizeCodeCliRepository(raw, "~zhangce07/l2-rules-test"), {
    ownerMis: "zhangce07",
    ownerDisplayName: "仓库负责人",
    defaultBranch: "master",
  });
  assert.throws(() => normalizeCodeCliRepository(
    { ...raw, path_with_namespace: "other/repository" },
    "~zhangce07/l2-rules-test",
  ), (error) => error.errorCode === "repository_identity_mismatch");
  assert.throws(() => normalizeCodeCliRepository(
    { ...raw, owner: null },
    "~zhangce07/l2-rules-test",
  ), AuthorityUnresolvedError);
});

test("pairs Yuntu ID and name paths and rejects mismatched or unsafe identities", async () => {
  const raw = await fixture("yuntu.organization.json");
  const organization = normalizeYuntuOrganization(raw, "zhangce07");
  assert.equal(organization.sourceOrganizationId, "100006");
  assert.equal(organization.displayName, "前端组");
  assert.equal(organization.chain.length, 6);
  assert.equal(organization.chain.at(-1).source_organization_id, "100006");
  assert.throws(() => normalizeYuntuOrganization({
    ...raw,
    misId: "another-user",
  }, "zhangce07"), (error) => error.errorCode === "organization_identity_mismatch");
  assert.throws(() => normalizeYuntuOrganization({
    ...raw,
    orgIdPath: "/100001/100002/100003/100004/100006/",
  }, "zhangce07"), (error) => error.errorCode === "organization_path_invalid");
  assert.throws(() => normalizeYuntuOrganization({
    ...raw,
    orgId: Number.MAX_SAFE_INTEGER + 1,
  }, "zhangce07"), (error) => error.errorCode === "organization_result_invalid");
  assert.throws(() => normalizeYuntuOrganization({
    ...raw,
    orgName: "前端/组",
  }, "zhangce07"), (error) => error.errorCode === "organization_path_invalid");
  assert.throws(
    () => normalizeYuntuOrganization(null, "zhangce07"),
    (error) => error instanceof AuthorityUnresolvedError &&
      error.errorCode === "organization_not_found",
  );
});

test("builds the exact confirmed, unresolved and failed result shapes", async () => {
  const context = await resultContext();
  const timings = {
    runtime_install_ms: 10,
    repository_lookup_ms: 20,
    metrics_token_exchange_ms: 30,
    yuntu_lookup_ms: 40,
    identity_enrichment_ms: null,
    total_ms: 100,
  };
  const confirmed = buildRunnerResult({
    context,
    executionStatus: "succeeded",
    resolutionStatus: "confirmed",
    repository: { canonical_key: context.repository.canonicalKey, default_branch: "master" },
    owner: {
      mis: "zhangce07",
      display_name: "仓库负责人",
      iam_emp_id: null,
      identity_enrichment_status: "not_requested",
    },
    organization: {
      source_system: "yuntu_org",
      source_organization_id: "2",
      display_name: "前端组",
      full_path: "美团点评/前端组",
      chain: [
        { source_organization_id: "1", display_name: "美团点评" },
        { source_organization_id: "2", display_name: "前端组" },
      ],
    },
    versions: { eeCodeCliVersion: "0.1.27", yuntuCliVersion: YUNTU_VERSION },
    verifiedAt: "2099-01-01T00:01:00.000Z",
    timings,
    error: null,
  });
  assert.equal(validateRunnerResult(confirmed), confirmed);
  assert.deepEqual(Object.keys(confirmed), [
    "schema_version", "attempt_id", "runner_invocation_id", "request_hash",
    "task_artifact_hash", "execution_status", "resolution_status", "repository",
    "owner", "organization", "evidence", "error",
  ]);

  const unresolved = buildRunnerResult({
    context,
    executionStatus: "succeeded",
    resolutionStatus: "unresolved",
    repository: { canonical_key: context.repository.canonicalKey, default_branch: null },
    owner: null,
    organization: null,
    versions: { eeCodeCliVersion: "unknown", yuntuCliVersion: YUNTU_VERSION },
    verifiedAt: "2099-01-01T00:01:00.000Z",
    timings: { ...emptyTimings(), total_ms: 1 },
    error: { phase: "repository_lookup", error_code: "repository_owner_not_found", retriable: false },
  });
  assert.equal(unresolved.resolution_status, "unresolved");

  const failed = buildRunnerResult({
    context,
    executionStatus: "failed",
    resolutionStatus: null,
    repository: { canonical_key: context.repository.canonicalKey, default_branch: null },
    owner: null,
    organization: null,
    versions: { eeCodeCliVersion: "unknown", yuntuCliVersion: "unavailable" },
    verifiedAt: "2099-01-01T00:01:00.000Z",
    timings: { ...emptyTimings(), total_ms: 1 },
    error: { phase: "runtime_install", error_code: "runtime_install_failed", retriable: true },
  });
  assert.equal(failed.execution_status, "failed");
});

test("uses the exact ee-code argv without shell expansion", async () => {
  const context = await resultContext();
  const calls = [];
  const raw = await fixture("code-cli.repository.json");
  const result = await queryRepositoryOwner({
    context,
    now: () => NOW,
    processRunner: async (command, args) => {
      calls.push({ command, args });
      return calls.length === 1
        ? okProcess("code-cli version 0.1.27\n")
        : okProcess(JSON.stringify(raw));
    },
  });
  assert.equal(result.ownerMis, "zhangce07");
  assert.deepEqual(calls[1], {
    command: "code-cli",
    args: ["repo", "-R", "~zhangce07/l2-rules-test", "view", "--json"],
  });
});

test("accepts only an official Metrics token response or CatX gateway placeholder", async () => {
  const context = await resultContext();
  let tokenCommand;
  assert.equal(await acquireMetricsToken({
    context,
    now: () => NOW,
    processRunner: async (command, args) => {
      tokenCommand = { command, args };
      return okProcess(GATEWAY_TOKEN);
    },
  }), GATEWAY_TOKEN);
  assert.deepEqual(tokenCommand, {
    command: "mtsso-moa-local-exchange",
    args: ["--audience", "Metrics"],
  });
  assert.equal(await acquireMetricsToken({
    context,
    now: () => NOW,
    processRunner: async () => okProcess(JSON.stringify({ access_token: "x".repeat(64) })),
  }), "x".repeat(64));
  await assert.rejects(() => acquireMetricsToken({
    context,
    now: () => NOW,
    processRunner: async () => ({
      ...failedProcess({ exitCode: 42 }),
      stdout: Buffer.from(JSON.stringify({ code: "ric_feedback_required" })),
    }),
  }), (error) => error.errorCode === "metrics_user_authorization_required" && !error.retriable);
});

test("passes the Metrics token only to the Yuntu process and parses JSON only", async (t) => {
  const context = await resultContext();
  const raw = await fixture("yuntu.organization.json");
  const installRoot = await mkdtemp(join(tmpdir(), "authority-yuntu-query-"));
  t.after(() => rm(installRoot, { recursive: true, force: true }));
  let invocation;
  const organization = await queryYuntuOrganization({
    context,
    runtime: {
      installRoot,
      executablePath: "/safe/yuntu/dist/index.js",
      version: YUNTU_VERSION,
    },
    owner: { ownerMis: "zhangce07" },
    metricsToken: GATEWAY_TOKEN,
    now: () => NOW,
    processRunner: async (command, args, options) => {
      invocation = { command, args, options };
      return okProcess(JSON.stringify(raw));
    },
  });
  assert.equal(invocation.command, process.execPath);
  assert.deepEqual(invocation.args, [
    "/safe/yuntu/dist/index.js", "--output", "json", "--color", "off",
    "user", "org", "zhangce07",
  ]);
  assert.equal(invocation.options.env.YUNTU_ACCESS_TOKEN, GATEWAY_TOKEN);
  assert.equal(invocation.options.env.AGENT_SSO_CLIENT_SECRET, undefined);
  assert.equal(organization.displayName, "前端组");
  await assert.rejects(() => queryYuntuOrganization({
    context,
    runtime: {
      installRoot,
      executablePath: "/safe/yuntu/dist/index.js",
      version: YUNTU_VERSION,
    },
    owner: { ownerMis: "zhangce07" },
    metricsToken: GATEWAY_TOKEN,
    now: () => NOW,
    processRunner: async () => okProcess(`说明文字\n${JSON.stringify(raw)}`),
  }), AuthorityRunnerError);
});

test("installs a pinned private Yuntu runtime and retries one transient failure", async (t) => {
  const runtimeRoot = await mkdtemp(join(tmpdir(), "authority-runtime-"));
  t.after(() => rm(runtimeRoot, { recursive: true, force: true }));
  const context = { ...(await resultContext()), deadline: Date.now() + 5 * 60_000 };
  let calls = 0;
  const runtime = await ensureYuntuRuntime({
    context,
    runtimeRoot,
    now: Date.now,
    waitForRetry: async () => undefined,
    processRunner: async (command, args, options) => {
      calls += 1;
      assert.equal(command, "npm");
      assert.ok(args.includes("@ee/yuntu-cli@1.0.15"));
      assert.ok(args.includes("--registry=http://r.npm.sankuai.com"));
      assert.equal(options.env.AGENT_SSO_CLIENT_SECRET, undefined);
      assert.match(options.env.XDG_CONFIG_HOME, /authority-runtime-/);
      assert.equal(options.env.HOME, undefined);
      if (calls === 1) return failedProcess({ stderr: "ETIMEDOUT", timedOut: true });
      const stage = args[args.indexOf("--prefix") + 1];
      const packageRoot = join(stage, "node_modules", "@ee", "yuntu-cli");
      await mkdir(join(packageRoot, "dist"), { recursive: true });
      await writeFile(join(packageRoot, "package.json"), JSON.stringify({
        name: "@ee/yuntu-cli", version: YUNTU_VERSION,
      }));
      await writeFile(join(packageRoot, "dist", "index.js"), "#!/usr/bin/env node\n");
      return okProcess();
    },
  });
  assert.equal(calls, 2);
  assert.equal(runtime.version, YUNTU_VERSION);
  assert.match(runtime.executablePath, /yuntu-1[.]0[.]15/);
});

test("does not retry a non-transient Yuntu package failure", async (t) => {
  const runtimeRoot = await mkdtemp(join(tmpdir(), "authority-runtime-fail-"));
  t.after(() => rm(runtimeRoot, { recursive: true, force: true }));
  const context = { ...(await resultContext()), deadline: Date.now() + 5 * 60_000 };
  let calls = 0;
  await assert.rejects(() => ensureYuntuRuntime({
    context,
    runtimeRoot,
    now: Date.now,
    waitForRetry: async () => assert.fail("non-transient install must not wait for retry"),
    processRunner: async () => {
      calls += 1;
      return failedProcess({ stderr: "E404 package version not found" });
    },
  }), (error) => error.errorCode === "runtime_install_failed" && !error.retriable);
  assert.equal(calls, 1);
});

test("delivers one hash-bound callback and accepts duplicate receipts", async () => {
  const context = await resultContext();
  const result = {
    schema_version: RESULT_SCHEMA,
    marker: "test-only",
  };
  let captured;
  const delivered = await deliverAuthorityCallback({
    context,
    result,
    now: () => NOW,
    request: async (request) => {
      captured = request;
      return {
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({
          schema_version: CALLBACK_RECEIPT_SCHEMA,
          status: "duplicate",
          attempt_id: context.attemptId,
          runner_invocation_id: context.runnerInvocationId,
          result_hash: sha256(request.body),
        }),
      };
    },
  });
  assert.equal(captured.idempotencyKey, `${context.attemptId}:${context.runnerInvocationId}`);
  assert.equal(captured.token, context.callback.token);
  assert.equal(JSON.parse(captured.body).marker, "test-only");
  assert.equal(delivered.receipt.status, "duplicate");
  assert.doesNotMatch(captured.body, new RegExp(context.callback.token));
});

test("retries only transient callback responses with the same body and idempotency key", async () => {
  const context = await resultContext();
  const result = { schema_version: RESULT_SCHEMA, marker: "retry" };
  const requests = [];
  const waits = [];
  const delivered = await deliverAuthorityCallback({
    context,
    result,
    now: () => NOW,
    waitForRetry: async (duration) => waits.push(duration),
    request: async (request) => {
      requests.push(request);
      if (requests.length === 1) {
        return { status: 503, contentType: "application/json", body: "{}" };
      }
      return {
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          schema_version: CALLBACK_RECEIPT_SCHEMA,
          status: "accepted",
          attempt_id: context.attemptId,
          runner_invocation_id: context.runnerInvocationId,
          result_hash: sha256(request.body),
        }),
      };
    },
  });
  assert.equal(delivered.receipt.status, "accepted");
  assert.equal(requests.length, 2);
  assert.equal(requests[0].body, requests[1].body);
  assert.equal(requests[0].idempotencyKey, requests[1].idempotencyKey);
  assert.deepEqual(waits, [250]);
});

test("canonical callback bytes and hashes ignore object insertion order", async () => {
  const context = await resultContext();
  const bodies = [];
  const request = async (callback) => {
    bodies.push(callback.body);
    return {
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        schema_version: CALLBACK_RECEIPT_SCHEMA,
        status: bodies.length === 1 ? "accepted" : "duplicate",
        attempt_id: context.attemptId,
        runner_invocation_id: context.runnerInvocationId,
        result_hash: sha256(callback.body),
      }),
    };
  };
  const first = await deliverAuthorityCallback({
    context,
    result: {
      z: "末尾",
      a: { y: 2, x: "中文" },
      list: [{ b: 2, a: 1 }],
    },
    now: () => NOW,
    request,
  });
  const second = await deliverAuthorityCallback({
    context,
    result: {
      list: [{ a: 1, b: 2 }],
      a: { x: "中文", y: 2 },
      z: "末尾",
    },
    now: () => NOW,
    request,
  });
  assert.equal(bodies[0], bodies[1]);
  assert.equal(first.resultHash, second.resultHash);
  assert.equal(first.resultHash, sha256(canonical({
    z: "末尾",
    a: { y: 2, x: "中文" },
    list: [{ b: 2, a: 1 }],
  })));
});

test("rejects a callback receipt for another invocation", async () => {
  assert.throws(() => validateCallbackReceipt({
    schema_version: CALLBACK_RECEIPT_SCHEMA,
    status: "accepted",
    attempt_id: "22222222-2222-4222-8222-222222222222",
    runner_invocation_id: "44444444-4444-4444-8444-444444444444",
    result_hash: `sha256:${"a".repeat(64)}`,
  }, {
    attemptId: "22222222-2222-4222-8222-222222222222",
    runnerInvocationId: "33333333-3333-4333-8333-333333333333",
    resultHash: `sha256:${"a".repeat(64)}`,
  }), /did not match/);
});

test("runs the complete confirmed flow and never places credentials in the result", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "authority-flow-"));
  t.after(() => rm(temporary, { recursive: true, force: true }));
  const runtimeRoot = join(temporary, "runtime");
  await makeInstallation(runtimeRoot);
  const code = await fixture("code-cli.repository.json");
  const yuntu = await fixture("yuntu.organization.json");
  const base = await taskArtifact({
    execution: { deadline: new Date(Date.now() + 5 * 60_000).toISOString() },
  });
  const taskPath = join(temporary, "task.json");
  const outputPath = join(temporary, "result.json");
  await writeFile(taskPath, base.bytes);
  let callbackBody;
  let invocation = 0;
  const execution = await executeAuthorityTask({
    taskPath,
    taskArtifactHash: base.hash,
    outputPath,
    runtimeRoot,
    processRunner: async (command) => {
      invocation += 1;
      if (command === "code-cli" && invocation === 1) return okProcess("0.1.27\n");
      if (command === "code-cli") return okProcess(JSON.stringify(code));
      if (command === "mtsso-moa-local-exchange") return okProcess(GATEWAY_TOKEN);
      if (command === process.execPath) return okProcess(JSON.stringify(yuntu));
      assert.fail(`unexpected command ${command}`);
    },
    callbackRequest: async (request) => {
      callbackBody = request.body;
      return {
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          schema_version: CALLBACK_RECEIPT_SCHEMA,
          status: "accepted",
          attempt_id: base.task.attempt_id,
          runner_invocation_id: base.task.runner_invocation_id,
          result_hash: sha256(request.body),
        }),
      };
    },
  });
  assert.equal(execution.result.execution_status, "succeeded");
  assert.equal(execution.result.resolution_status, "confirmed");
  assert.equal(execution.result.owner.identity_enrichment_status, "not_requested");
  assert.equal(execution.result.organization.source_system, "yuntu_org");
  assert.deepEqual(JSON.parse(await readFile(outputPath, "utf8")), execution.result);
  assert.equal(callbackBody, canonical(execution.result));
  assert.doesNotMatch(callbackBody, new RegExp(GATEWAY_TOKEN));
  assert.doesNotMatch(callbackBody, new RegExp(base.task.execution.callback.token));
});

test("rechecks ee-code after Yuntu and leaves an owner change unresolved", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "authority-owner-change-"));
  t.after(() => rm(temporary, { recursive: true, force: true }));
  const runtimeRoot = join(temporary, "runtime");
  await makeInstallation(runtimeRoot);
  const code = await fixture("code-cli.repository.json");
  const yuntu = await fixture("yuntu.organization.json");
  const base = await taskArtifact({
    execution: { deadline: new Date(Date.now() + 5 * 60_000).toISOString() },
  });
  const taskPath = join(temporary, "task.json");
  const outputPath = join(temporary, "result.json");
  await writeFile(taskPath, base.bytes);
  let codeViews = 0;
  let callbackResult;
  const execution = await executeAuthorityTask({
    taskPath,
    taskArtifactHash: base.hash,
    outputPath,
    runtimeRoot,
    processRunner: async (command, args) => {
      if (command === "code-cli" && args[0] === "--version") {
        return okProcess("0.1.27\n");
      }
      if (command === "code-cli") {
        codeViews += 1;
        return okProcess(JSON.stringify(codeViews === 1
          ? code
          : { ...code, owner: { mis: "newowner", name: "新负责人" } }));
      }
      if (command === "mtsso-moa-local-exchange") return okProcess(GATEWAY_TOKEN);
      if (command === process.execPath) return okProcess(JSON.stringify(yuntu));
      assert.fail(`unexpected command ${command}`);
    },
    callbackRequest: async (request) => {
      callbackResult = JSON.parse(request.body);
      return {
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          schema_version: CALLBACK_RECEIPT_SCHEMA,
          status: "accepted",
          attempt_id: base.task.attempt_id,
          runner_invocation_id: base.task.runner_invocation_id,
          result_hash: sha256(request.body),
        }),
      };
    },
  });
  assert.equal(codeViews, 2);
  assert.equal(execution.result.execution_status, "succeeded");
  assert.equal(execution.result.resolution_status, "unresolved");
  assert.equal(callbackResult.error.phase, "repository_lookup");
  assert.equal(callbackResult.error.error_code, "repository_owner_changed");
  assert.equal(callbackResult.owner.mis, "zhangce07");
  assert.equal(callbackResult.organization, null);
  assert.ok(Number.isSafeInteger(callbackResult.evidence.timings_ms.repository_lookup_ms));
});

test("finalizes a valid task with a failed callback payload when ee-code cannot run", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "authority-failure-"));
  t.after(() => rm(temporary, { recursive: true, force: true }));
  const runtimeRoot = join(temporary, "runtime");
  await makeInstallation(runtimeRoot);
  const base = await taskArtifact({
    execution: { deadline: new Date(Date.now() + 5 * 60_000).toISOString() },
  });
  const taskPath = join(temporary, "task.json");
  const outputPath = join(temporary, "result.json");
  await writeFile(taskPath, base.bytes);
  let callbackResult;
  const execution = await executeAuthorityTask({
    taskPath,
    taskArtifactHash: base.hash,
    outputPath,
    runtimeRoot,
    processRunner: async () => failedProcess({ spawnCode: "ENOENT", exitCode: null }),
    callbackRequest: async (request) => {
      callbackResult = JSON.parse(request.body);
      return {
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          schema_version: CALLBACK_RECEIPT_SCHEMA,
          status: "accepted",
          attempt_id: base.task.attempt_id,
          runner_invocation_id: base.task.runner_invocation_id,
          result_hash: sha256(request.body),
        }),
      };
    },
  });
  assert.equal(execution.result.execution_status, "failed");
  assert.equal(execution.result.resolution_status, null);
  assert.equal(callbackResult.error.error_code, "code_cli_unavailable");
  assert.equal(callbackResult.owner, null);
  assert.equal(callbackResult.organization, null);
});

test("still delivers the callback when the diagnostic output path cannot be written", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "authority-output-failure-"));
  t.after(() => rm(temporary, { recursive: true, force: true }));
  const runtimeRoot = join(temporary, "runtime");
  await makeInstallation(runtimeRoot);
  const base = await taskArtifact({
    execution: { deadline: new Date(Date.now() + 5 * 60_000).toISOString() },
  });
  const taskPath = join(temporary, "task.json");
  const blockedParent = join(temporary, "not-a-directory");
  await writeFile(taskPath, base.bytes);
  await writeFile(blockedParent, "file");
  let callbackCount = 0;
  const execution = await executeAuthorityTask({
    taskPath,
    taskArtifactHash: base.hash,
    outputPath: join(blockedParent, "result.json"),
    runtimeRoot,
    processRunner: async () => failedProcess({ spawnCode: "ENOENT", exitCode: null }),
    callbackRequest: async (request) => {
      callbackCount += 1;
      return {
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          schema_version: CALLBACK_RECEIPT_SCHEMA,
          status: "accepted",
          attempt_id: base.task.attempt_id,
          runner_invocation_id: base.task.runner_invocation_id,
          result_hash: sha256(request.body),
        }),
      };
    },
  });
  assert.equal(callbackCount, 1);
  assert.equal(execution.outputWritten, false);
  assert.equal(execution.result.execution_status, "failed");
});

test("finalizes a missing repository owner as succeeded but unresolved", async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), "authority-unresolved-"));
  t.after(() => rm(temporary, { recursive: true, force: true }));
  const runtimeRoot = join(temporary, "runtime");
  await makeInstallation(runtimeRoot);
  const base = await taskArtifact({
    execution: { deadline: new Date(Date.now() + 5 * 60_000).toISOString() },
  });
  const taskPath = join(temporary, "task.json");
  const outputPath = join(temporary, "result.json");
  await writeFile(taskPath, base.bytes);
  let callbackResult;
  let commandCount = 0;
  const execution = await executeAuthorityTask({
    taskPath,
    taskArtifactHash: base.hash,
    outputPath,
    runtimeRoot,
    processRunner: async () => {
      commandCount += 1;
      return commandCount === 1
        ? okProcess("0.1.27\n")
        : okProcess(JSON.stringify({
          path_with_namespace: "~zhangce07/l2-rules-test",
          default_branch: "master",
          owner: null,
        }));
    },
    callbackRequest: async (request) => {
      callbackResult = JSON.parse(request.body);
      return {
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          schema_version: CALLBACK_RECEIPT_SCHEMA,
          status: "accepted",
          attempt_id: base.task.attempt_id,
          runner_invocation_id: base.task.runner_invocation_id,
          result_hash: sha256(request.body),
        }),
      };
    },
  });
  assert.equal(commandCount, 2);
  assert.equal(execution.result.execution_status, "succeeded");
  assert.equal(execution.result.resolution_status, "unresolved");
  assert.equal(callbackResult.error.error_code, "repository_owner_not_found");
  assert.equal(callbackResult.organization, null);
});
