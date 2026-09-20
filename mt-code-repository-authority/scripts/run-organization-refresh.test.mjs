import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { deliverRefreshCallback, executeOrganizationRefresh } from "./run-organization-refresh.mjs";
import { canonical, sha256, validateTask } from "./organization-refresh-contract.mjs";

const ids = [
  "10000000-0000-4000-8000-000000000001",
  "10000000-0000-4000-8000-000000000002",
  "10000000-0000-4000-8000-000000000003",
  "10000000-0000-4000-8000-000000000004",
  "10000000-0000-4000-8000-000000000005",
];

test("organization refresh processes items sequentially and reports partial provider failure", async (t) => {
  const directory = await mkdtemp(join(tmpdir(), "organization-refresh-runner-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const taskPath = join(directory, "task.json");
  const outputPath = join(directory, "receipt.json");
  const deadline = new Date(Date.now() + 60_000).toISOString();
  const items = ["alice", "bob"].map((principal, index) => ({
    item_id: ids[index + 1],
    attempt_id: ids[index + 3],
    runner_invocation_id: `20000000-0000-4000-8000-00000000000${index + 1}`,
    principal_mis: principal,
    request_hash: `sha256:${String(index + 1).repeat(64)}`,
    callback: {
      url: `https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability/internal/organization-refresh/attempts/${ids[index + 3]}/result`,
      token: "a".repeat(43 + index),
    },
  }));
  const task = {
    schema_version: "organization-refresh-task/v1",
    skill_contract_version: "mt-code-repository-authority/v2",
    run_id: ids[0], generation: 7, mode: "dry_run",
    actor: { mis: "zhangce07", source: "verified-edge" },
    execution: { deadline, expected_result_schema: "organization-refresh-item-result/v1" },
    items,
  };
  const taskJson = canonical(task);
  await writeFile(taskPath, taskJson);
  const observed = [];
  const callbacks = [];
  const output = await executeOrganizationRefresh({
    taskPath, taskArtifactHash: sha256(taskJson), outputPath,
  }, {
    ensureRuntime: async () => ({ executablePath: "/tmp/yuntu" }),
    acquireToken: async () => "metrics-token",
    queryOrganization: async ({ owner }) => {
      observed.push(owner.ownerMis);
      if (owner.ownerMis === "bob") throw Object.assign(new Error("unavailable"), {
        phase: "organization_lookup", errorCode: "organization_lookup_failed", retriable: true,
      });
      return {
        sourceOrganizationId: "101", displayName: "前端组", fullPath: "美团/前端组",
        chain: [
          { source_organization_id: "1", display_name: "美团" },
          { source_organization_id: "101", display_name: "前端组" },
        ],
      };
    },
    callbackRequest: async ({ body }) => {
      const result = JSON.parse(body);
      callbacks.push(result);
      return {
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          schema_version: "organization-refresh-callback-receipt/v1",
          status: "accepted",
          result_status: result.execution_status === "succeeded" ? "observed" : "failed",
          attempt_id: result.attempt_id,
          runner_invocation_id: result.runner_invocation_id,
          result_hash: sha256(canonical(result)),
        }),
      };
    },
  });
  assert.deepEqual(observed, ["alice", "bob"]);
  assert.deepEqual(callbacks.map((item) => item.execution_status), ["succeeded", "failed"]);
  assert.equal(output.callback_failures, 0);
  assert.deepEqual(JSON.parse(await readFile(outputPath, "utf8")), output);
});

test("organization refresh rejects a receipt with the wrong business status", async (t) => {
  const directory = await mkdtemp(join(tmpdir(), "organization-refresh-receipt-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const taskPath = join(directory, "task.json");
  const outputPath = join(directory, "receipt.json");
  const item = {
    item_id: ids[1], attempt_id: ids[3], runner_invocation_id: ids[4], principal_mis: "alice",
    request_hash: `sha256:${"a".repeat(64)}`,
    callback: {
      url: `https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability/internal/organization-refresh/attempts/${ids[3]}/result`,
      token: "b".repeat(43),
    },
  };
  const task = {
    schema_version: "organization-refresh-task/v1", skill_contract_version: "mt-code-repository-authority/v2",
    run_id: ids[0], generation: 1, mode: "apply",
    actor: { mis: "zhangce07", source: "verified-edge" },
    execution: { deadline: new Date(Date.now() + 60_000).toISOString(), expected_result_schema: "organization-refresh-item-result/v1" },
    items: [item],
  };
  const taskJson = canonical(task);
  await writeFile(taskPath, taskJson);
  await assert.rejects(executeOrganizationRefresh({ taskPath, taskArtifactHash: sha256(taskJson), outputPath }, {
    ensureRuntime: async () => ({}), acquireToken: async () => "token",
    queryOrganization: async () => ({
      sourceOrganizationId: "101", displayName: "前端组", fullPath: "美团/前端组",
      chain: [{ source_organization_id: "101", display_name: "前端组" }],
    }),
    callbackRequest: async ({ body }) => {
      const result = JSON.parse(body);
      return { status: 200, contentType: "application/json", body: JSON.stringify({
        schema_version: "organization-refresh-callback-receipt/v1", status: "accepted",
        result_status: "failed", attempt_id: result.attempt_id,
        runner_invocation_id: result.runner_invocation_id, result_hash: sha256(canonical(result)),
      }) };
    },
    waitForRetry: async () => {},
  }), /callbacks failed/);
});

const taskFixture = () => ({
  schema_version: "organization-refresh-task/v1",
  skill_contract_version: "mt-code-repository-authority/v2",
  run_id: ids[0], generation: 1, mode: "dry_run",
  actor: { mis: "zhangce07", source: "verified-edge" },
  execution: { deadline: new Date(Date.now() + 60_000).toISOString(), expected_result_schema: "organization-refresh-item-result/v1" },
  items: ["alice", "bob"].map((principal, index) => ({
    item_id: ids[index + 1], attempt_id: ids[index + 3],
    runner_invocation_id: `20000000-0000-4000-8000-00000000000${index + 1}`,
    principal_mis: principal, request_hash: `sha256:${"a".repeat(64)}`,
    callback: {
      url: `https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability/internal/organization-refresh/attempts/${ids[index + 3]}/result`,
      token: "capability".repeat(8),
    },
  })),
});

const callbackReceipt = (body, status = "accepted") => {
  const result = JSON.parse(body);
  return { status: 200, contentType: "application/json", body: JSON.stringify({
    schema_version: "organization-refresh-callback-receipt/v1", status,
    result_status: result.execution_status === "succeeded" ? "observed" : "failed",
    attempt_id: result.attempt_id, runner_invocation_id: result.runner_invocation_id,
    result_hash: sha256(canonical(result)),
  }) };
};

test("task rejects duplicated identities, extra principals, expired deadlines and foreign callbacks", () => {
  for (const mutate of [
    (task) => { task.items[1].item_id = task.items[0].item_id; },
    (task) => { task.items[1].runner_invocation_id = task.items[0].runner_invocation_id; },
    (task) => { task.items[0].unexpected_mis = "mallory"; },
    (task) => { task.execution.deadline = new Date(Date.now() - 1).toISOString(); },
    (task) => { task.items[0].callback.url = "https://other.example/collect"; },
    (task) => { task.items = Array.from({ length: 11 }, () => task.items[0]); },
  ]) {
    const task = taskFixture();
    mutate(task);
    assert.throws(() => validateTask(task, sha256(canonical(task))));
  }
});

test("shared authentication failure reports every item without lookup or leaking credentials", async (t) => {
  const directory = await mkdtemp(join(tmpdir(), "organization-refresh-auth-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const task = taskFixture();
  const serialized = canonical(task);
  const taskPath = join(directory, "task.json");
  await writeFile(taskPath, serialized);
  const callbacks = [];
  await executeOrganizationRefresh({ taskPath, taskArtifactHash: sha256(serialized), outputPath: join(directory, "receipt.json") }, {
    ensureRuntime: async () => ({}),
    acquireToken: async () => { throw Object.assign(new Error("sensitive-token-in-stderr"), {
      phase: "metrics_token_exchange", errorCode: "metrics_user_authorization_required", retriable: false,
    }); },
    queryOrganization: async () => { assert.fail("lookup must not run after authentication failure"); },
    callbackRequest: async ({ body }) => { callbacks.push(JSON.parse(body)); return callbackReceipt(body); },
  });
  assert.equal(callbacks.length, 2);
  assert.ok(callbacks.every((result) => result.execution_status === "failed" && result.error.retriable === false));
  assert.ok(!JSON.stringify(callbacks).includes("sensitive-token-in-stderr"));
});

test("real Yuntu output adapter rejects a different employee and accepts the next item", async (t) => {
  const directory = await mkdtemp(join(tmpdir(), "organization-refresh-provider-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const serialized = canonical(taskFixture());
  const taskPath = join(directory, "task.json");
  await writeFile(taskPath, serialized);
  const results = [];
  await executeOrganizationRefresh({ taskPath, taskArtifactHash: sha256(serialized), outputPath: join(directory, "receipt.json") }, {
    ensureRuntime: async () => ({ installRoot: join(directory, "runtime"), executablePath: "/mock/yuntu.mjs" }),
    acquireToken: async () => "private-metrics-token",
    processRunner: async (_command, args, options) => {
      assert.equal(options.env.YUNTU_ACCESS_TOKEN, "private-metrics-token");
      assert.ok(!args.includes("private-metrics-token"));
      const mis = args.at(-1);
      return { exitCode: 0, stdout: Buffer.from(JSON.stringify({
        misId: mis === "alice" ? "mallory" : mis, name: "Employee",
        orgId: 101, orgName: "Team", fullPath: "/Company/Team/", orgIdPath: "/2/101/",
      })), stderr: Buffer.alloc(0) };
    },
    callbackRequest: async ({ body }) => { results.push(JSON.parse(body)); return callbackReceipt(body); },
  });
  assert.equal(results[0].error.error_code, "organization_identity_mismatch");
  assert.equal(results[1].execution_status, "succeeded");
  assert.deepEqual(results[1].organization.chain, [
    { source_organization_id: "2", display_name: "Company" },
    { source_organization_id: "101", display_name: "Team" },
  ]);
});

test("lost callback receipt resends identical bytes and accepts a duplicate, without a new lookup", async () => {
  const context = validateTask(taskFixture(), `sha256:${"a".repeat(64)}`);
  const item = context.items[0];
  const result = { execution_status: "failed", attempt_id: item.attemptId, runner_invocation_id: item.runnerInvocationId };
  const bodies = [];
  const receipt = await deliverRefreshCallback({ context, item, result,
    waitForRetry: async () => {},
    request: async ({ body }) => {
      bodies.push(body);
      if (bodies.length === 1) throw new Error("response lost after commit");
      return callbackReceipt(body, "duplicate");
    },
  });
  assert.equal(receipt.status, "duplicate");
  assert.equal(bodies.length, 2);
  assert.equal(bodies[0], bodies[1]);
});
