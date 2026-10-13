import assert from "node:assert/strict";
import test from "node:test";

import {
  createMtcliTransport,
  mtcliChildEnvironment,
  mtcliInvocation,
  validateMtcliDryRun,
  validateMtcliService,
} from "./mtcli-transport.mjs";

const request = {
  gatewayUrl: "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-distribution",
  resourcePath: "/v1/effective-rule-bundles/resolve",
  url: "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-distribution/v1/effective-rule-bundles/resolve",
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Rule-Auth-Source": "mtcli-sso",
    "X-Rule-Protocol-Version": "1.0",
  },
  body: {
    repository_locator: "hfe/hotel-web",
    execution: {
      pull_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      execution_agent: "cli",
      execution_agent_source: "runner_explicit_v1",
      skill_name: "mt-code-standards",
      skill_version: "1.2.0",
    },
  },
  maxResponseBytes: 4 * 1024 * 1024,
};

const dryRun = (overrides = {}) => ({
  auth_type: "SSO",
  body: request.body,
  dry_run: true,
  headers: {
    "X-Rule-Auth-Source": "mtcli-sso",
    "X-Rule-Protocol-Version": "1.0",
  },
  method: "POST",
  query_params: {},
  target_env: "prod",
  timeout: 30,
  url: request.url,
  ...overrides,
});

test("builds fixed prod mtcli invocations for the registered service method", () => {
  const args = mtcliInvocation({ service: "mt-code-standards", request, dryRun: true });
  assert.deepEqual(args.slice(0, 12), [
    "--mtcli-schema-env", "prod", "--mtcli-target-env", "prod", "--output", "json", "--quiet",
    "--no-cache", "mt-code-standards", "bundles", "resolve", "--params",
  ]);
  assert.equal(args.at(-1), "--dry-run");
  assert.deepEqual(JSON.parse(args[args.indexOf("--json") + 1]), request.body);
  assert.deepEqual(JSON.parse(args[args.indexOf("--params") + 1]), {
    "X-Rule-Auth-Source": "mtcli-sso",
    "X-Rule-Protocol-Version": "1.0",
  });
});

test("validates service names and strips inherited identity credentials", () => {
  assert.equal(validateMtcliService(), "mt-code-standards");
  assert.throws(() => validateMtcliService("../other"), (error) => error.code === "RULE_BUNDLE_MTCLI_SERVICE_INVALID");
  const child = mtcliChildEnvironment({
    PATH: "/bin",
    SSO_USER_ID: "tester",
    RULE_OBSERVABILITY_USER_TOKEN: "token",
    AGENT_SSO_CLIENT_SECRET: "secret",
    CODEX_AUTH_TOKEN: "agent-token",
  });
  assert.deepEqual(child, { PATH: "/bin", MTCLI_DISABLE_VERSION_CHECK: "1" });
});

test("dry-run requires the exact trusted POST, SSO, body, headers and empty query", () => {
  assert.doesNotThrow(() => validateMtcliDryRun(dryRun(), request));
  assert.doesNotThrow(() => validateMtcliDryRun(dryRun({ headers: request.headers }), request));
  for (const payload of [
    dryRun({ url: `${request.url}?redirect=other` }),
    dryRun({ method: "GET" }),
    dryRun({ auth_type: "Access" }),
    dryRun({ target_env: "test" }),
    dryRun({ query_params: { debug: "1" } }),
    dryRun({ headers: { ...request.headers, Authorization: "Bearer static" } }),
    dryRun({ headers: { ...request.headers, Cookie: "sso=static" } }),
    dryRun({ headers: { ...request.headers, "Content-Type": "text/plain" } }),
    dryRun({ body: { repository_locator: "other/repo" } }),
  ]) {
    assert.throws(
      () => validateMtcliDryRun(payload, request),
      (error) => error.code === "RULE_BUNDLE_MTCLI_DRY_RUN_INVALID",
    );
  }
});

test("executes only after dry-run validation and unwraps the documented JSON envelope", async () => {
  const calls = [];
  const cwd = "/tmp/mtcli-cwd";
  const transport = createMtcliTransport({
    cwd,
    environment: { PATH: "/bin", RULE_OBSERVABILITY_USER_TOKEN: "hidden" },
    execute: async (command, args, options) => {
      calls.push({ command, args, options });
      if (args.includes("--dry-run")) return { stdout: JSON.stringify(dryRun()) };
      return {
        stdout: JSON.stringify({
          success: true,
          status_code: 200,
          data: { schema_version: "effective-rule-bundle/v2", status: "not_modified" },
        }),
      };
    },
  });
  assert.deepEqual(await transport(request), {
    status: 200,
    body: { schema_version: "effective-rule-bundle/v2", status: "not_modified" },
  });
  assert.equal(calls.length, 2);
  assert.equal(calls[0].command, "mtcli");
  assert.equal(calls[0].options.cwd, cwd);
  assert.equal(calls[0].options.env.RULE_OBSERVABILITY_USER_TOKEN, undefined);
});

test("pins the mtcli auth source without changing the direct request contract", async () => {
  const legacyRequest = {
    ...request,
    headers: { ...request.headers, "X-Rule-Auth-Source": "nocode-agent-sso" },
  };
  const params = [];
  const transport = createMtcliTransport({
    execute: async (_command, args) => {
      params.push(JSON.parse(args[args.indexOf("--params") + 1]));
      if (args.includes("--dry-run")) return { stdout: JSON.stringify(dryRun()) };
      return { stdout: JSON.stringify({ success: true, status_code: 200, data: {} }) };
    },
  });
  await transport(legacyRequest);
  assert.deepEqual(params, [
    { "X-Rule-Auth-Source": "mtcli-sso", "X-Rule-Protocol-Version": "1.0" },
    { "X-Rule-Auth-Source": "mtcli-sso", "X-Rule-Protocol-Version": "1.0" },
  ]);
  assert.equal(legacyRequest.headers["X-Rule-Auth-Source"], "nocode-agent-sso");
});

test("preserves service error codes from HTTP failures and 200 business errors", async () => {
  for (const statusCode of [404, 200]) {
    const transport = createMtcliTransport({ execute: async (_command, args) => {
      if (args.includes("--dry-run")) return { stdout: JSON.stringify(dryRun()) };
      const stdout = JSON.stringify({
        success: statusCode === 200,
        status_code: statusCode,
        data: { error: { code: "repository_not_registered", message: "missing" } },
        ...(statusCode === 404 ? { error: { code: "HTTP_404", message: "HTTP 404" } } : {}),
      });
      if (statusCode === 404) throw Object.assign(new Error("request failed"), { code: 3, stdout, stderr: "secret" });
      return { stdout };
    } });
    assert.deepEqual(await transport(request), {
      status: statusCode === 200 ? 400 : 404,
      body: { error: { code: "repository_not_registered", message: "missing" } },
    });
  }
});

test("reports mtcli absence, timeout, invalid JSON and unverified dry-run without leaking stderr", async () => {
  for (const [cause, code] of [
    [Object.assign(new Error("not found"), { code: "ENOENT", stderr: "secret" }), "RULE_BUNDLE_MTCLI_NOT_FOUND"],
    [Object.assign(new Error("timeout"), { code: "ETIMEDOUT", stderr: "secret" }), "RULE_BUNDLE_MTCLI_TIMEOUT"],
    [Object.assign(new Error("overflow"), { code: "ERR_CHILD_PROCESS_STDIO_MAXBUFFER", stdout: "secret" }), "RULE_BUNDLE_RESPONSE_TOO_LARGE"],
  ]) {
    const transport = createMtcliTransport({ execute: async () => { throw cause; } });
    await assert.rejects(transport(request), (error) => error.code === code && !error.message.includes("secret"));
  }
  const invalid = createMtcliTransport({ execute: async () => ({ stdout: "not-json" }) });
  await assert.rejects(invalid(request), (error) => error.code === "RULE_BUNDLE_MTCLI_DRY_RUN_INVALID");
  let called = 0;
  const unsafe = createMtcliTransport({ execute: async (_command, args) => {
    called += 1;
    return { stdout: JSON.stringify(args.includes("--dry-run")
      ? dryRun({ headers: { ...request.headers, Cookie: "secret" } })
      : { success: true, status_code: 200, data: {} }) };
  } });
  await assert.rejects(unsafe(request), (error) => error.code === "RULE_BUNDLE_MTCLI_DRY_RUN_INVALID");
  assert.equal(called, 1);
});
