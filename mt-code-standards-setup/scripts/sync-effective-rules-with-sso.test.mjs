import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, symlink } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { RuleBundleError, canonicalJson, sha256Hex } from "./resolve-effective-rules.mjs";
import { detectExecutionAgent, syncWithOfficialSso, tokenFromOfficialExchange } from "./sync-effective-rules-with-sso.mjs";

const bundle = () => {
  const files = [{ relative_path: "l1/frontend-l1.md", content: "# L1\n" }];
  const projection = files.map((file) => ({ ...file, sha256: sha256Hex(file.content), byte_size: Buffer.byteLength(file.content) }));
  const manifestHash = sha256Hex(canonicalJson(projection.map(({ relative_path, sha256, byte_size }) => ({ relative_path, sha256, byte_size }))));
  const refs = [{ rule_set_id: "frontend-l1", release_id: "frontend-l1@test", scope_level: "L1" }];
  const snapshotId = sha256Hex(canonicalJson({ resolver_version: "effective-rule-bundle/v2", repository_id: "repo:test", canonical_key: "hfe/test", standard_domain: "frontend", manifest_hash: manifestHash, release_refs: refs }));
  return { schema_version: "effective-rule-bundle/v2", status: "ready", snapshot: { resolver_version: "effective-rule-bundle/v2", snapshot_id: snapshotId, repository: { repository_id: "repo:test", canonical_key: "hfe/test", standard_domain: "frontend" }, release_refs: refs, manifest_hash: manifestHash, total_bytes: projection[0].byte_size }, files: projection };
};
const response = (body) => ({ ok: true, status: 200, text: async () => JSON.stringify(body) });

test("uses the injected official token first and records the detected Codex agent", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-ciba-test-"));
  await mkdir(path.join(root, ".git"));
  let request;
  const receipt = await syncWithOfficialSso({
    environment: { RULE_OBSERVABILITY_USER_TOKEN: "official-token", CODEX_SESSION_ID: "current" },
    options: { repoRoot: root, repositoryLocator: "hfe/test", pullId: "22222222-2222-4222-8222-222222222222" },
    fetchImpl: async (_url, init) => { request = JSON.parse(init.body); return response(bundle()); },
  });
  assert.equal(receipt.authentication_mode, "injected_user_token");
  assert.equal(request.execution.execution_agent, "codex");
  assert.equal(request.execution.pull_id, "22222222-2222-4222-8222-222222222222");
});

test("uses the official exchange fallback and treats CIBA confirmation as a stop condition", async () => {
  const exchange = async () => ({ stdout: JSON.stringify({ access_token: "ciba-token" }) });
  assert.deepEqual(await tokenFromOfficialExchange({ environment: {}, execute: exchange }), { token: "ciba-token", mode: "official_moa_exchange" });
  await assert.rejects(
    tokenFromOfficialExchange({ environment: {}, execute: async () => { const error = new Error("pending"); error.stdout = JSON.stringify({ code: "MOA_AUTH_REQUEST_PENDING" }); throw error; } }),
    (error) => error instanceof RuleBundleError && error.code === "RULE_BUNDLE_CIBA_CONFIRMATION_REQUIRED",
  );
  await assert.rejects(
    tokenFromOfficialExchange({ environment: {}, execute: async () => { const error = new Error("rejected"); error.stdout = JSON.stringify({ code: "MOA_USER_REJECTED" }); throw error; } }),
    (error) => error instanceof RuleBundleError && error.code === "RULE_BUNDLE_CIBA_REJECTED",
  );
  await assert.rejects(
    tokenFromOfficialExchange({ environment: {}, execute: async () => { const error = new Error("missing client id"); error.stderr = "错误: 缺少 client_id"; throw error; } }),
    (error) => error instanceof RuleBundleError && error.code === "RULE_BUNDLE_SSO_AGENT_CONFIG_REQUIRED",
  );
});

test("falls back to CIBA/MOA once only when an injected user ticket is rejected", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-ciba-retry-"));
  await mkdir(path.join(root, ".git"));
  const calls = [];
  const receipt = await syncWithOfficialSso({
    environment: { RULE_OBSERVABILITY_USER_TOKEN: "expired-ticket", CATDESK_SESSION_ID: "current" },
    options: { repoRoot: root, repositoryLocator: "hfe/test", pullId: "44444444-4444-4444-8444-444444444444" },
    execute: async () => ({ stdout: JSON.stringify({ access_token: "ciba-fallback-ticket" }) }),
    fetchImpl: async (_url, init) => {
      calls.push(init.headers.Authorization);
      if (init.headers.Authorization === "Bearer expired-ticket") {
        return { ok: false, status: 401, text: async () => JSON.stringify({ error: { code: "unauthorized" } }) };
      }
      return response(bundle());
    },
  });
  assert.deepEqual(calls, ["Bearer expired-ticket", "Bearer ciba-fallback-ticket"]);
  assert.equal(receipt.authentication_mode, "official_moa_exchange_after_injected_token_rejected");
  assert.equal(receipt.execution_agent, "catdesk");
});

test("does not guess an execution agent and accepts platform-specific declarations", () => {
  assert.deepEqual(detectExecutionAgent({}), { agent: "unknown", source: "legacy_unknown_v1" });
  assert.deepEqual(detectExecutionAgent({ CATPAW_SESSION_ID: "x" }), { agent: "catpaw", source: "runner_heuristic_v1" });
  assert.deepEqual(detectExecutionAgent({ CLAUDE_CODE_ENTRYPOINT: "x" }), { agent: "claude", source: "runner_heuristic_v1" });
  assert.deepEqual(detectExecutionAgent({ AGENT_1024_SESSION: "x" }), { agent: "agent_1024", source: "runner_heuristic_v1" });
});

test("runs the SSO wrapper when its Skill directory is installed as a symbolic link", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-symlink-runner-"));
  const entry = path.join(root, "sync-effective-rules-with-sso.mjs");
  await symlink(fileURLToPath(new URL("./sync-effective-rules-with-sso.mjs", import.meta.url)), entry);
  const result = spawnSync(process.execPath, [entry, "--unexpected"], { encoding: "utf8" });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /RULE_BUNDLE_ARGUMENT_INVALID/);
});
