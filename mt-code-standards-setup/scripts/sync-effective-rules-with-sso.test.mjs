import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, symlink } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { RuleBundleError, canonicalJson, sha256Hex } from "./resolve-effective-rules.mjs";
import {
  detectAuthAgent,
  detectExecutionAgent,
  EXTERNAL_AUTH_AGENTS,
  selectAuthenticationRoute,
  syncWithOfficialSso,
  tokenFromOfficialExchange,
} from "./sync-effective-rules-with-sso.mjs";

const bundle = () => {
  const files = [{ relative_path: "l1/frontend-l1.md", content: "# L1\n" }];
  const projection = files.map((file) => ({ ...file, sha256: sha256Hex(file.content), byte_size: Buffer.byteLength(file.content) }));
  const manifestHash = sha256Hex(canonicalJson(projection.map(({ relative_path, sha256, byte_size }) => ({ relative_path, sha256, byte_size }))));
  const refs = [{ rule_set_id: "frontend-l1", release_id: "frontend-l1@test", scope_level: "L1" }];
  const snapshotId = sha256Hex(canonicalJson({ resolver_version: "effective-rule-bundle/v2", repository_id: "repo:test", canonical_key: "hfe/test", standard_domain: "frontend", manifest_hash: manifestHash, release_refs: refs }));
  return { schema_version: "effective-rule-bundle/v2", status: "ready", snapshot: { resolver_version: "effective-rule-bundle/v2", snapshot_id: snapshotId, repository: { repository_id: "repo:test", canonical_key: "hfe/test", standard_domain: "frontend" }, release_refs: refs, manifest_hash: manifestHash, total_bytes: projection[0].byte_size }, files: projection };
};
const response = (body) => ({ ok: true, status: 200, text: async () => JSON.stringify(body) });
const errorResponse = (code, status) => ({
  ok: false, status, text: async () => JSON.stringify({ error: { code } }),
});
const commandFailure = ({ code = 1, stdout = "", stderr = "", message = "command failed" } = {}) => {
  const error = new Error(message);
  error.code = code;
  error.stdout = stdout;
  error.stderr = stderr;
  return error;
};

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
  assert.equal(receipt.authentication_route_reason, "injected_user_token_present");
  assert.equal(request.execution.execution_agent, "codex");
  assert.equal(request.execution.pull_id, "22222222-2222-4222-8222-222222222222");
  assert.equal(JSON.stringify(receipt).includes("official-token"), false);
  assert.equal(JSON.stringify(request).includes("official-token"), false);
  assert.equal(Object.hasOwn(request.execution, "auth_agent"), false);
  assert.equal(Object.hasOwn(request.execution, "authentication_route_reason"), false);
});

test("routes all supported explicit external auth agents directly to portable CIBA", async () => {
  assert.deepEqual([...EXTERNAL_AUTH_AGENTS], [
    "github-copilot", "cursor", "windsurf", "claude-code", "codex", "gemini-cli", "amazon-q", "kiro",
    "jetbrains-junie", "devin", "replit-agent", "cline", "roo-code", "aider", "trae", "qoder",
    "tongyi-lingma", "tencent-codebuddy", "baidu-comate", "codegeex",
  ]);
  for (const authAgent of EXTERNAL_AUTH_AGENTS) {
    const root = await mkdtemp(path.join(os.tmpdir(), "setup-external-auth-agent-"));
    await mkdir(path.join(root, ".git"));
    let officialCalls = 0;
    let portableCalls = 0;
    const receipt = await syncWithOfficialSso({
      environment: {},
      options: { authAgent, mis: "zhangce07", repoRoot: root, repositoryLocator: "hfe/test" },
      execute: async (command) => {
        if (command === "npx") officialCalls += 1;
        else portableCalls += 1;
        return { stdout: JSON.stringify({ token: `portable-${authAgent}` }) };
      },
      fetchImpl: async () => response(bundle()),
    });
    assert.equal(officialCalls, 0, authAgent);
    assert.equal(portableCalls, 1, authAgent);
    assert.equal(receipt.authentication_mode, "portable_sso_ciba", authAgent);
    assert.equal(receipt.authentication_route_reason, "explicit_external_auth_agent", authAgent);
  }
});

test("uses an injected token before validating an optional auth agent hint", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-injected-auth-agent-"));
  await mkdir(path.join(root, ".git"));
  const receipt = await syncWithOfficialSso({
    environment: { RULE_OBSERVABILITY_USER_TOKEN: "injected" },
    options: { authAgent: "vscode", repoRoot: root, repositoryLocator: "hfe/test" },
    fetchImpl: async () => response(bundle()),
  });
  assert.equal(receipt.authentication_mode, "injected_user_token");
  assert.equal(receipt.authentication_route_reason, "injected_user_token_present");
});

test("detects high-confidence Codex and Claude Code environments for direct portable CIBA", async () => {
  const cases = [
    [{ CODEX_SESSION_ID: "session" }, "codex"],
    [{ CLAUDE_CODE_ENTRYPOINT: "cli" }, "claude-code"],
    [{ CLAUDECODE: "1" }, "claude-code"],
  ];
  for (const [environmentSignal, expectedAgent] of cases) {
    const environment = { ...environmentSignal, SSO_USER_ID: "zhangce07" };
    assert.equal(detectAuthAgent(environment).authAgent, expectedAgent);
    assert.deepEqual(selectAuthenticationRoute({ environment }), {
      route: "portable", reason: "detected_external_auth_agent", authAgent: expectedAgent,
    });
    const root = await mkdtemp(path.join(os.tmpdir(), "setup-detected-auth-agent-"));
    await mkdir(path.join(root, ".git"));
    let officialCalls = 0;
    const receipt = await syncWithOfficialSso({
      environment,
      options: { repoRoot: root, repositoryLocator: "hfe/test" },
      execute: async (command) => {
        if (command === "npx") officialCalls += 1;
        return { stdout: JSON.stringify({ token: "portable-detected-ticket" }) };
      },
      fetchImpl: async () => response(bundle()),
    });
    assert.equal(officialCalls, 0);
    assert.equal(receipt.authentication_mode, "portable_sso_ciba");
  }
});

test("keeps unknown and explicitly internal execution agents on the official exchange", async () => {
  const cases = [
    [{}, {}, "official_exchange_default"],
    [{ CODEX_SESSION_ID: "nested" }, { agent: "catdesk" }, "explicit_internal_execution_agent"],
  ];
  for (const [environment, options, expectedReason] of cases) {
    const root = await mkdtemp(path.join(os.tmpdir(), "setup-official-route-"));
    await mkdir(path.join(root, ".git"));
    const commands = [];
    const receipt = await syncWithOfficialSso({
      environment,
      options: { ...options, repoRoot: root, repositoryLocator: "hfe/test" },
      execute: async (command) => {
        commands.push(command);
        return { stdout: JSON.stringify({ access_token: "official-ticket" }) };
      },
      fetchImpl: async () => response(bundle()),
    });
    assert.deepEqual(commands, ["npx"]);
    assert.equal(receipt.authentication_mode, "official_moa_exchange");
    assert.equal(receipt.authentication_route_reason, expectedReason);
  }
});

test("forwards an explicit bootstrap domain through the SSO wrapper", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-domain-forward-"));
  await mkdir(path.join(root, ".git"));
  const files = [{ relative_path: "l1/java-l1/java.md", content: "# Java\n" }];
  const projected = files.map((file) => ({
    ...file, sha256: sha256Hex(file.content), byte_size: Buffer.byteLength(file.content),
  }));
  const refs = [{ rule_set_id: "java-l1", release_id: "java-l1@test", scope_level: "L1" }];
  const manifestHash = sha256Hex(canonicalJson(projected.map(({
    relative_path, sha256, byte_size,
  }) => ({ relative_path, sha256, byte_size }))));
  const snapshotId = sha256Hex(canonicalJson({
    bootstrap_version: "l1-bootstrap-bundle/v1",
    standard_domain: "backend",
    manifest_hash: manifestHash,
    release_refs: refs,
  }));
  const requests = [];
  const receipt = await syncWithOfficialSso({
    environment: { RULE_OBSERVABILITY_USER_TOKEN: "official-token" },
    options: { repoRoot: root, repositoryLocator: "team/new-java", domain: "backend" },
    fetchImpl: async (url, init) => {
      requests.push(JSON.parse(init.body));
      return url.endsWith("/v1/effective-rule-bundles/resolve")
        ? errorResponse("repository_not_registered", 404)
        : response({
          schema_version: "l1-bootstrap-bundle/v1",
          status: "ready",
          snapshot: {
            bootstrap_version: "l1-bootstrap-bundle/v1", snapshot_id: snapshotId,
            standard_domain: "backend", release_refs: refs,
            manifest_hash: manifestHash, total_bytes: projected[0].byte_size,
          },
          files: projected,
        });
    },
  });
  assert.equal(requests[1].standard_domain, "backend");
  assert.equal(receipt.domain_source, "user_explicit");
});

test("accepts official JSON tokens and gateway placeholders and passes the explicit environment", async () => {
  const environment = { PATH: "/test/bin" };
  const calls = [];
  const execute = async (...args) => {
    calls.push(args);
    return { stdout: JSON.stringify({ access_token: "official-ticket" }) };
  };
  assert.deepEqual(await tokenFromOfficialExchange({ environment, execute }), { token: "official-ticket", mode: "official_moa_exchange" });
  assert.equal(calls[0][2].env, environment);
  assert.deepEqual(
    await tokenFromOfficialExchange({ environment, execute: async () => ({ stdout: "AT_FOR_GW_BASE64_placeholder" }) }),
    { token: "AT_FOR_GW_BASE64_placeholder", mode: "official_gateway_exchange" },
  );
});

test("stops for V13 exit 42 and legacy exit 1 access denials without portable fallback", async () => {
  for (const exitCode of [42, 1]) {
    let calls = 0;
    await assert.rejects(
      tokenFromOfficialExchange({
        environment: {}, mis: "zhangce07",
        execute: async () => {
          calls += 1;
          throw commandFailure({ code: exitCode, stdout: JSON.stringify({ error: "act_access_denied", error_description: "请由调用方管理员申请 UAC 代理权限" }) });
        },
      }),
      (error) => error instanceof RuleBundleError && error.code === "RULE_BUNDLE_SSO_ACCESS_DENIED" && error.message.includes("UAC 代理权限"),
    );
    assert.equal(calls, 1);
  }
});

test("treats exit-zero error JSON as failure", async () => {
  await assert.rejects(
    tokenFromOfficialExchange({ environment: {}, execute: async () => ({ stdout: JSON.stringify({ error: "sub_access_denied", error_description: "用户未授权" }) }) }),
    (error) => error instanceof RuleBundleError && error.code === "RULE_BUNDLE_SSO_ACCESS_DENIED",
  );
  await assert.rejects(
    tokenFromOfficialExchange({ environment: {}, execute: async () => ({ stdout: JSON.stringify({ code: "act_access_denied", error: { message: "调用方无代理权限" } }) }) }),
    (error) => error instanceof RuleBundleError && error.code === "RULE_BUNDLE_SSO_ACCESS_DENIED",
  );
});

test("classifies user action, pending, rejection, and cooldown as stop conditions", async () => {
  const cases = [
    [{ error: "ric_feedback_required", error_description: "请在大象完成风险确认" }, "RULE_BUNDLE_SSO_USER_ACTION_REQUIRED"],
    [{ code: "MOA_AUTH_REQUEST_PENDING" }, "RULE_BUNDLE_CIBA_CONFIRMATION_REQUIRED"],
    [{ success: false, error: { code: "MOA_NOT_LOGGED_IN" } }, "RULE_BUNDLE_CIBA_CONFIRMATION_REQUIRED"],
    [{ code: "MOA_USER_REJECTED" }, "RULE_BUNDLE_CIBA_REJECTED"],
    [{ code: "MOA_REJECT_COOLDOWN" }, "RULE_BUNDLE_CIBA_REJECTED"],
  ];
  for (const [payload, expectedCode] of cases) {
    await assert.rejects(
      tokenFromOfficialExchange({ environment: {}, execute: async () => ({ stdout: JSON.stringify(payload) }) }),
      (error) => error instanceof RuleBundleError && error.code === expectedCode,
    );
  }
});

test("uses portable CIBA once only for explicit official Agent configuration failure", async () => {
  const environment = { SSO_USER_ID: "zhangce07" };
  const calls = [];
  const credential = await tokenFromOfficialExchange({
    environment,
    execute: async (command, args, options) => {
      calls.push({ command, args, options });
      if (command === "npx") throw commandFailure({ stderr: "错误: 缺少 client_id" });
      return { stdout: JSON.stringify({ token: "portable-ticket" }) };
    },
  });
  assert.deepEqual(credential, { token: "portable-ticket", mode: "portable_sso_ciba" });
  assert.equal(calls.length, 2);
  assert.equal(calls[1].command, process.execPath);
  assert.deepEqual(calls[1].args.slice(-2), ["--mis", "zhangce07"]);
  assert.equal(calls[1].options.env, environment);
  assert.equal(calls[1].options.timeout, 150_000);
});

test("uses portable CIBA for an explicit local capability unavailable response", async () => {
  let calls = 0;
  const credential = await tokenFromOfficialExchange({
    environment: {},
    mis: "zhangce07",
    execute: async (command) => {
      calls += 1;
      if (command === "npx") {
        return { stdout: JSON.stringify({ success: false, error: { code: "MOA_UNSUPPORTED" } }) };
      }
      return { stdout: JSON.stringify({ token: "portable-capability-ticket" }) };
    },
  });
  assert.deepEqual(credential, { token: "portable-capability-ticket", mode: "portable_sso_ciba" });
  assert.equal(calls, 2);
});

test("does not use portable CIBA for permission, network, timeout, or invalid-response failures", async () => {
  const failures = [
    commandFailure({ code: 42, stdout: JSON.stringify({ error: "sub_act_access_denied" }) }),
    commandFailure({ code: 42, stderr: "missing client_id" }),
    commandFailure({ code: "ENOTFOUND", stderr: "network unavailable" }),
    commandFailure({ code: "ENOTFOUND", stderr: "network unavailable; missing client_id" }),
    commandFailure({ code: 1, stderr: "fetch failed: missing client_id" }),
    commandFailure({ code: 1, stderr: "网络请求失败：缺少 client_id" }),
    commandFailure({ code: "ETIMEDOUT", message: "timed out" }),
    Object.assign(commandFailure({ stderr: "missing client_id" }), { killed: true, signal: "SIGTERM" }),
  ];
  for (const failure of failures) {
    let calls = 0;
    await assert.rejects(
      tokenFromOfficialExchange({ environment: {}, mis: "zhangce07", execute: async () => { calls += 1; throw failure; } }),
      RuleBundleError,
    );
    assert.equal(calls, 1);
  }
  let invalidCalls = 0;
  await assert.rejects(
    tokenFromOfficialExchange({ environment: {}, mis: "zhangce07", execute: async () => { invalidCalls += 1; return { stdout: "not-json" }; } }),
    (error) => error.code === "RULE_BUNDLE_SSO_EXCHANGE_FAILED",
  );
  assert.equal(invalidCalls, 1);
});

test("requires MIS before starting portable CIBA", async () => {
  let calls = 0;
  await assert.rejects(
    tokenFromOfficialExchange({ environment: {}, execute: async () => { calls += 1; throw commandFailure({ stderr: "missing client_id" }); } }),
    (error) => error instanceof RuleBundleError && error.code === "RULE_BUNDLE_PORTABLE_MIS_REQUIRED",
  );
  assert.equal(calls, 1);
});

test("converts portable helper failures to stable errors without exposing helper output", async () => {
  let calls = 0;
  await assert.rejects(
    tokenFromOfficialExchange({
      environment: {},
      mis: "zhangce07",
      execute: async (command) => {
        calls += 1;
        if (command === "npx") throw commandFailure({ stderr: "missing client_id" });
        throw commandFailure({
          stdout: JSON.stringify({ error: { code: "PORTABLE_AUTH_PROVIDER_REQUIRED", message: "secret-token-value" } }),
          stderr: "Bearer secret-token-value",
        });
      },
    }),
    (error) => error.code === "RULE_BUNDLE_SSO_PORTABLE_PROVIDER_REQUIRED"
      && !error.message.includes("secret-token-value"),
  );
  assert.equal(calls, 2);
});

test("captures portable tokens without including them in the receipt", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-portable-receipt-"));
  await mkdir(path.join(root, ".git"));
  const receipt = await syncWithOfficialSso({
    environment: {},
    options: { mis: "zhangce07", repoRoot: root, repositoryLocator: "hfe/test", pullId: "33333333-3333-4333-8333-333333333333" },
    execute: async (command) => {
      if (command === "npx") throw commandFailure({ stderr: "缺少 client_id" });
      return { stdout: JSON.stringify({ token: "portable-secret-ticket" }) };
    },
    fetchImpl: async () => response(bundle()),
  });
  assert.equal(receipt.authentication_mode, "portable_sso_ciba");
  assert.equal(JSON.stringify(receipt).includes("portable-secret-ticket"), false);
});

test("refreshes an injected ticket only once after an explicit Edge unauthorized response", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-ciba-retry-"));
  await mkdir(path.join(root, ".git"));
  const calls = [];
  let exchangeCalls = 0;
  const receipt = await syncWithOfficialSso({
    environment: { RULE_OBSERVABILITY_USER_TOKEN: "expired-ticket", CATDESK_SESSION_ID: "current" },
    options: { repoRoot: root, repositoryLocator: "hfe/test", pullId: "44444444-4444-4444-8444-444444444444" },
    execute: async () => { exchangeCalls += 1; return { stdout: JSON.stringify({ access_token: "replacement-ticket" }) }; },
    fetchImpl: async (_url, init) => {
      calls.push(init.headers.Authorization);
      if (init.headers.Authorization === "Bearer expired-ticket") return { ok: false, status: 401, text: async () => JSON.stringify({ error: { code: "unauthorized" } }) };
      return response(bundle());
    },
  });
  assert.deepEqual(calls, ["Bearer expired-ticket", "Bearer replacement-ticket"]);
  assert.equal(exchangeCalls, 1);
  assert.equal(receipt.authentication_mode, "official_moa_exchange_after_injected_token_rejected");
  assert.equal(receipt.execution_agent, "catdesk");
});

test("keeps the external portable route when an injected ticket is rejected", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-external-ciba-retry-"));
  await mkdir(path.join(root, ".git"));
  const authorizations = [];
  const commands = [];
  const receipt = await syncWithOfficialSso({
    environment: {
      RULE_OBSERVABILITY_USER_TOKEN: "expired-ticket",
      CODEX_SESSION_ID: "current",
      SSO_USER_ID: "zhangce07",
    },
    options: { repoRoot: root, repositoryLocator: "hfe/test" },
    execute: async (command) => {
      commands.push(command);
      return { stdout: JSON.stringify({ token: "portable-replacement-ticket" }) };
    },
    fetchImpl: async (_url, init) => {
      authorizations.push(init.headers.Authorization);
      if (init.headers.Authorization === "Bearer expired-ticket") {
        return {
          ok: false, status: 401,
          text: async () => JSON.stringify({ error: { code: "unauthorized" } }),
        };
      }
      return response(bundle());
    },
  });
  assert.deepEqual(commands, [process.execPath]);
  assert.deepEqual(authorizations, ["Bearer expired-ticket", "Bearer portable-replacement-ticket"]);
  assert.equal(receipt.authentication_mode, "portable_sso_ciba_after_injected_token_rejected");
  assert.equal(
    receipt.authentication_route_reason,
    "detected_external_auth_agent_after_injected_token_rejected",
  );
});

test("does not refresh an injected ticket after another business rejection", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-no-business-retry-"));
  await mkdir(path.join(root, ".git"));
  let exchangeCalls = 0;
  await assert.rejects(
    syncWithOfficialSso({
      environment: { RULE_OBSERVABILITY_USER_TOKEN: "valid-user-ticket" },
      options: { repoRoot: root, repositoryLocator: "hfe/test" },
      execute: async () => { exchangeCalls += 1; return { stdout: JSON.stringify({ access_token: "unused" }) }; },
      fetchImpl: async () => ({
        ok: false,
        status: 403,
        text: async () => JSON.stringify({ error: { code: "repository_access_denied" } }),
      }),
    }),
    (error) => error.code === "repository_access_denied",
  );
  assert.equal(exchangeCalls, 0);
});

test("does not guess an execution agent and accepts platform-specific declarations", () => {
  assert.deepEqual(detectExecutionAgent({}), { agent: "unknown", source: "legacy_unknown_v1" });
  assert.deepEqual(detectExecutionAgent({ CATPAW_SESSION_ID: "x" }), { agent: "catpaw", source: "runner_heuristic_v1" });
  assert.deepEqual(detectExecutionAgent({ CLAUDE_CODE_ENTRYPOINT: "x" }), { agent: "claude", source: "runner_heuristic_v1" });
  assert.deepEqual(detectExecutionAgent({ AGENT_1024_SESSION: "x" }), { agent: "agent_1024", source: "runner_heuristic_v1" });
  assert.deepEqual(
    detectAuthAgent({ GITHUB_ACTIONS: "true", TERM_PROGRAM: "vscode" }),
    { authAgent: "unknown", source: "unknown_v1" },
  );
  assert.equal(
    selectAuthenticationRoute({
      environment: { CATDESK_SESSION_ID: "internal", CODEX_SESSION_ID: "nested" },
    }).route,
    "official",
  );
  assert.equal(
    selectAuthenticationRoute({
      environment: { CATCLAW_SESSION_ID: "internal", CLAUDE_CODE_ENTRYPOINT: "nested" },
    }).route,
    "official",
  );
});

test("runs the SSO wrapper when its Skill directory is installed as a symbolic link", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-symlink-runner-"));
  const entry = path.join(root, "sync-effective-rules-with-sso.mjs");
  await symlink(fileURLToPath(new URL("./sync-effective-rules-with-sso.mjs", import.meta.url)), entry);
  const result = spawnSync(process.execPath, [entry, "--unexpected"], { encoding: "utf8" });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /RULE_BUNDLE_ARGUMENT_INVALID/);
  const invalidAuthAgent = spawnSync(process.execPath, [entry, "--auth-agent", "vscode"], {
    encoding: "utf8",
    env: { ...process.env, RULE_OBSERVABILITY_USER_TOKEN: "" },
  });
  assert.equal(invalidAuthAgent.status, 2);
  assert.match(invalidAuthAgent.stderr, /RULE_BUNDLE_AUTH_AGENT_INVALID/);
});
