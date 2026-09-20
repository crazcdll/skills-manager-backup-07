import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { deliverSourceResult, executeV3Task, extractCitadelTableIds, extractRepositoryCandidates, extractRepositoryCandidatesV2, mapLimit, scanCitadelSource, splitSourceEntries } from "./run-repository-authority-v3.mjs";
import { canonical, sha256 } from "./repository-authority-contract.mjs";
import { V3_SOURCE_RESULT_SCHEMA_V2, validateV3TaskArtifact } from "./repository-authority-v3-contract.mjs";
import { readCitadelTablePage } from "./read-citadel-table-page.mjs";

const result = (value) => ({ exitCode: 0, stdout: Buffer.from(JSON.stringify(value)) });
const scanSource = (options) => scanCitadelSource({
  actorMis: "actual_user",
  authEnvironment: { AUTH_CACHE_FILE: "/private/attempt/auth-cache.json", SSO_OIDC_FALLBACK: "false" },
  ...options,
});
const uuid = (number) => `11111111-1111-5111-8111-${String(number).padStart(12, "0")}`;
const batchTask = () => ({
  schema_version: "repository-authority-task/v2", skill_contract_version: "mt-code-repository-authority/v3",
  mode: "authority_shard", shard_id: uuid(1), generation: 1,
  actor: { mis: "actual_user", source: "verified-edge", execution_mis: "zhangce07" },
  execution: { deadline: new Date(Date.now() + 300_000).toISOString(), workers: 2, expected_result_schema: "repository-authority-runner-result/v1" },
  payload: [0, 1].map((index) => ({
    item_id: uuid(2 + index * 4), job_id: uuid(3 + index * 4), attempt_id: uuid(4 + index * 4), runner_invocation_id: uuid(5 + index * 4), request_hash: `sha256:${"a".repeat(64)}`,
    repository: { canonical_key: `team/repository-${index}`, canonical_https_url: `https://dev.sankuai.com/code/repo-detail/team/repository-${index}/file/list`, canonical_ssh_url: `ssh://git@git.sankuai.com/team/repository-${index}.git` },
    callback: { url: `https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability/internal/repository-authority/attempts/${uuid(4 + index * 4)}/result`, token: "t".repeat(43) },
  })),
});
const sourceTask = (expectedResultSchema = V3_SOURCE_RESULT_SCHEMA_V2) => ({
  schema_version: "repository-authority-task/v3", skill_contract_version: "mt-code-repository-authority/v4",
  mode: "source_scan", shard_id: uuid(20), generation: 2,
  actor: { mis: "actual_user", source: "verified-edge", execution_mis: "actual_user" },
  execution: { deadline: new Date(Date.now() + 300_000).toISOString(), workers: 2, expected_result_schema: expectedResultSchema },
  payload: {
    run_id: uuid(21), scan_revision: 2, citadel_url: "https://km.sankuai.com/collabpage/1280163608",
    callback: { url: `https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability/internal/repository-association/runs/${uuid(21)}/source-result`, token: "t".repeat(43) },
  },
});
const validateTask = (task) => { const taskBytes = Buffer.from(JSON.stringify(task)); return validateV3TaskArtifact({ taskBytes, expectedTaskArtifactHash: sha256(taskBytes) }); };

test("batch artifact validates independent capabilities and rejects duplicate attempts and foreign ports", () => {
  assert.equal(validateTask(batchTask()).items.length, 2);
  for (const mutate of [
    (task) => { task.payload[1].attempt_id = task.payload[0].attempt_id; task.payload[1].callback.url = task.payload[0].callback.url; },
    (task) => { task.payload[0].callback.url = task.payload[0].callback.url.replace(".com/", ".com:4444/"); },
    (task) => { task.execution.workers = 10; },
    (task) => { task.actor.execution_mis = "another_user"; },
  ]) { const task = batchTask(); mutate(task); assert.throws(() => validateTask(task)); }
});

test("shared runtime setup failure callbacks every repository and isolates one lost callback", async () => {
  const directory = await mkdtemp(join(tmpdir(), "repository-batch-v3-test-"));
  try {
    const taskPath = join(directory, "task.json");
    const outputPath = join(directory, "receipt.json");
    const bytes = Buffer.from(JSON.stringify(batchTask()));
    await writeFile(taskPath, bytes);
    const bodies = [];
    const receipt = await executeV3Task({ taskPath, outputPath, taskArtifactHash: sha256(bytes), runtimeRoot: join(directory, "runtime"), processRunner: async (command) => {
      assert.equal(command, "npm");
      return { exitCode: 1, stdout: Buffer.alloc(0), stderr: Buffer.from("permission denied") };
    }, callbackRequest: async ({ body }) => {
      const payload = JSON.parse(body); bodies.push(payload);
      assert.equal(payload.execution_status, "failed");
      assert.equal(payload.evidence.skill_contract_version, "mt-code-repository-authority/v3");
      if (payload.attempt_id === uuid(4)) return { status: 401, contentType: "application/json", body: "{}" };
      return { status: 200, contentType: "application/json", body: JSON.stringify({ schema_version: "repository-authority-callback-receipt/v1", status: "accepted", attempt_id: payload.attempt_id, runner_invocation_id: payload.runner_invocation_id, result_hash: sha256(body) }) };
    } });
    assert.equal(bodies.length, 2);
    assert.deepEqual(receipt.items.map((item) => item.status), ["callback_failed", "accepted"]);
    assert.equal(JSON.parse(await readFile(outputPath, "utf8")).items.length, 2);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test("extracts only complete MCode HTTPS and SSH URLs and merges outside the adapter", () => {
  const rows = extractRepositoryCandidates({ text: "repo-name https://dev.sankuai.com/code/repo-detail/hfe/board/file/list ssh://git@git.sankuai.com/hfe/standards.git" }, "document");
  assert.deepEqual(rows.map((item) => item.canonical_key), ["hfe/board", "hfe/standards"]);
});

test("source task selects the versioned result contract without changing the task envelope", () => {
  assert.equal(validateTask(sourceTask()).source.resultSchema, V3_SOURCE_RESULT_SCHEMA_V2);
  assert.equal(validateTask(sourceTask(V3_SOURCE_RESULT_SCHEMA_V2)).source.resultSchema, V3_SOURCE_RESULT_SCHEMA_V2);
  assert.throws(() => validateTask(sourceTask("repository-authority-source-scan-result/v1")), /source scan identity is invalid/u);
  const task = sourceTask("repository-association-source-scan-result/v3");
  assert.throws(() => validateTask(task), /source scan identity is invalid/u);
  const legacy = sourceTask();
  legacy.schema_version = "repository-authority-task/v2";
  legacy.skill_contract_version = "mt-code-repository-authority/v3";
  legacy.actor.execution_mis = "zhangce07";
  assert.throws(() => validateTask(legacy), /source scan task actor is invalid/u);
});

test("source attempts isolate and clean actor CIBA state after success, rejection, and timeout", async () => {
  const root = await mkdtemp(join(tmpdir(), "repository-source-auth-test-"));
  const cacheFiles = [];
  const previousToken = process.env.SSO_CIBA_TOKEN;
  process.env.SSO_CIBA_TOKEN = "shared-token-must-not-leak";
  const fetchImpl = async (_url, options) => {
    const body = JSON.parse(options.body);
    return Response.json({ data: {
      schema_version: "repository-association-source-scan-callback-receipt/v2",
      status: "accepted",
      run_id: body.run_id,
      shard_id: body.shard_id,
      generation: body.generation,
      chunk_index: body.chunk_index,
      result_hash: sha256(canonical(body)),
    } });
  };
  const runAttempt = async (outcome, ordinal) => {
    const task = sourceTask(V3_SOURCE_RESULT_SCHEMA_V2);
    task.shard_id = uuid(30 + ordinal);
    task.payload.run_id = uuid(40 + ordinal);
    task.payload.callback.url = `https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability/internal/repository-association/runs/${task.payload.run_id}/source-result`;
    const taskBytes = Buffer.from(JSON.stringify(task));
    const taskPath = join(root, `task-${ordinal}.json`);
    const outputPath = join(root, `result-${ordinal}.json`);
    await writeFile(taskPath, taskBytes);
    let calls = 0;
    const receipt = await executeV3Task({
      taskPath,
      outputPath,
      taskArtifactHash: sha256(taskBytes),
      runtimeRoot: join(root, `runtime-${ordinal}`),
      fetchImpl,
      processRunner: async (_command, args, options) => {
        calls += 1;
        assert.equal(options.env.SSO_CIBA_TOKEN, undefined);
        assert.equal(options.env.SSO_OIDC_FALLBACK, "false");
        const cacheFile = options.env.AUTH_CACHE_FILE;
        cacheFiles.push(cacheFile);
        assert.equal((await stat(join(cacheFile, ".."))).mode & 0o077, 0);
        if (outcome === "rejected") return { exitCode: 1, stdout: Buffer.from("MOA_USER_REJECTED"), stderr: Buffer.alloc(0) };
        if (outcome === "timeout") return { exitCode: 1, timedOut: true, stdout: Buffer.alloc(0), stderr: Buffer.alloc(0) };
        if (args[1] === "getSimpleMarkdown") return result({ content: "https://dev.sankuai.com/code/repo-detail/team/repository/file/list" });
        if (args[1] === "getDocumentJson") return result({ body: '{"content":[]}' });
        if (args[1] === "listTables") return result({ tableIds: [] });
        assert.fail(`unexpected command: ${args.join(" ")}`);
      },
    });
    assert.equal(receipt.callback_status, "accepted");
    assert.equal(calls, outcome === "success" ? 3 : 1);
    const cacheFile = cacheFiles.at(-1);
    await assert.rejects(stat(join(cacheFile, "..")), { code: "ENOENT" });
  };
  try {
    await runAttempt("success", 1);
    await runAttempt("rejected", 2);
    await runAttempt("timeout", 3);
    assert.equal(new Set(cacheFiles).size, 3);
  } finally {
    if (previousToken === undefined) delete process.env.SSO_CIBA_TOKEN;
    else process.env.SSO_CIBA_TOKEN = previousToken;
    await rm(root, { recursive: true, force: true });
  }
});

test("v2 extraction preserves address-shaped values for the Edge normalizer", () => {
  const extracted = extractRepositoryCandidatesV2({ text: [
    "https://dev.sankuai.com/code/repo-detail/HFE/Hotel-Web/file/list?branch=main#readme",
    "ssh://git@git.dianpingoa.com/HFE/Hotel-Web.git",
    "ssh://git@git.vip.sankuai.com:2198/HFE/Hotel-Web.git",
    "git@unknown.example.com:Team/CaseSensitive.git",
    "ssh://git@gitserver/Team/CaseSensitive.git",
    "ssh://git@[2001:db8::1]:2222/Team/CaseSensitive.git",
    "git@unknown.example.com:/srv/git/CaseSensitive.git",
    "https://external.example.com/team/repository",
    "repository-name",
  ].join(" ") }, "document");
  assert.deepEqual(extracted.candidates.map((item) => item.raw_value), [
    "https://dev.sankuai.com/code/repo-detail/HFE/Hotel-Web/file/list?branch=main#readme",
    "ssh://git@git.dianpingoa.com/HFE/Hotel-Web.git",
    "ssh://git@git.vip.sankuai.com:2198/HFE/Hotel-Web.git",
    "git@unknown.example.com:Team/CaseSensitive.git",
    "ssh://git@gitserver/Team/CaseSensitive.git",
    "ssh://git@[2001:db8::1]:2222/Team/CaseSensitive.git",
    "git@unknown.example.com:/srv/git/CaseSensitive.git",
    "https://external.example.com/team/repository",
  ]);
  assert.deepEqual(extracted.invalidItems, []);
});

test("v2 extraction excludes Markdown delimiters while retaining IPv6 authorities", () => {
  const url = "https://dev.sankuai.com/code/repo-detail/team/repo";
  const ipv6 = "ssh://git@[2001:db8::1]:2222/team/repo.git";
  const extracted = extractRepositoryCandidatesV2(`[${url}](${url}) <${url}> [SSH](${ipv6})`, "document");
  assert.deepEqual(extracted.candidates.map((item) => item.raw_value), [url, url, url, ipv6]);
  assert.deepEqual(extracted.invalidItems, []);
});

test("authority worker pool never runs more than two items", async () => {
  let active = 0;
  let maximum = 0;
  const result = await mapLimit(Array.from({ length: 11 }, (_, index) => index), 2, async (item) => {
    active += 1;
    maximum = Math.max(maximum, active);
    await new Promise((resolve) => setTimeout(resolve, 2));
    active -= 1;
    return item;
  });
  assert.equal(maximum, 2);
  assert.equal(result.length, 11);
});

test("extracts table ids only from documented table id fields", () => {
  assert.deepEqual(extractCitadelTableIds({ data: [{ tableId: 12345, rowCount: 99999 }, { table_id: "23456" }], contentId: "34567", tableIds: ["45678"], body: '{"content":[{"type":"xtable","attrs":{"xtableId":"56789"}}]}' }), ["12345", "23456", "45678", "56789"]);
});

test("source scan returns partial status and keeps repositories when one table page fails", async () => {
  const processRunner = async (_command, args) => {
    if (args[1] === "getSimpleMarkdown") return result({ content: "https://dev.sankuai.com/code/repo-detail/hfe/board/file/list" });
    if (args[1] === "getDocumentJson") return result({ body: '{"content":[]}' });
    if (args[1] === "listTables") return { exitCode: 0, stdout: Buffer.from(JSON.stringify({ tableIds: ["12345"] })), stderr: Buffer.alloc(0) };
    return { exitCode: 1, stdout: Buffer.alloc(0), stderr: Buffer.from("page unavailable") };
  };
  const scan = await scanSource({ source: { citadelUrl: "https://km.sankuai.com/page/123" }, processRunner, waitBetweenReads: async () => {} });
  assert.equal(scan.scan_status, "partially_scanned");
  assert.equal(scan.repositories.length, 1);
  assert.equal(scan.issues.length, 1);
});

test("v2 source scan separates invalid addresses from partial read errors", async () => {
  const processRunner = async (_command, args) => {
    if (args[1] === "getSimpleMarkdown") return result({ content: "https://dev.sankuai.com/code/repo-detail/team/board?branch=main https://external.example.com/team/nope" });
    if (args[1] === "getDocumentJson") return result({ body: '{"content":[]}' });
    if (args[1] === "listTables") return result({ tableIds: [] });
    assert.fail(`unexpected command: ${args.join(" ")}`);
  };
  const scan = await scanSource({
    source: { citadelUrl: "https://km.sankuai.com/page/123" },
    resultSchema: V3_SOURCE_RESULT_SCHEMA_V2,
    processRunner,
    waitBetweenReads: async () => {},
  });
  assert.equal(scan.scan_status, "completed");
  assert.deepEqual(scan.candidates.map((item) => item.raw_value), [
    "https://dev.sankuai.com/code/repo-detail/team/board?branch=main",
    "https://external.example.com/team/nope",
  ]);
  assert.deepEqual(scan.invalid_items, []);
  assert.deepEqual(scan.read_errors, []);
});

test("source scan stops before deadline and preserves completed reads", async () => {
  let at = 0;
  const processRunner = async (_command, args, options) => {
    assert.ok(options.timeout > 0);
    if (args[1] === "getSimpleMarkdown") return result({ content: "ssh://git@git.sankuai.com/hfe/board.git" });
    if (args[1] === "getDocumentJson") return result({ body: '{"content":[]}' });
    if (args[1] === "listTables") { at = 250_000; return { exitCode: 0, stdout: Buffer.from('{"tableIds":["12345","23456"]}') }; }
    assert.fail("table read must not begin after scan budget expires");
  };
  const scan = await scanSource({ source: { citadelUrl: "https://km.sankuai.com/page/123" }, deadline: 300_000, processRunner, now: () => at, waitBetweenReads: async () => {} });
  assert.equal(scan.scan_status, "partially_scanned");
  assert.equal(scan.repositories.length, 1);
  assert.equal(scan.issues[0].error_code, "citadel_scan_timeout");
});

test("Citadel reads all columns and preserves completed pages after a later page failure", async () => {
  let pageReads = 0;
  const processRunner = async (command, args) => {
    if (args[1] === "getSimpleMarkdown") return result({ content: "" });
    if (args[1] === "getDocumentJson") return result({ body: '{"content":[{"type":"xtable","attrs":{"xtableId":"12345"}}]}' });
    if (args[1] === "listTables") return result({ tables: [] });
    if (args[1] === "getTableMeta") return result({ columns: Array.from({ length: 12 }, (_, index) => ({ colId: index + 1 })) });
    assert.equal(command, process.execPath);
    assert.match(args[0], /read-citadel-table-page[.]mjs$/u);
    assert.equal(args[1], "12345");
    assert.equal(JSON.parse(args[2]).length, 12);
    assert.equal(args[4], "actual_user");
    pageReads += 1;
    if (pageReads === 1) {
      assert.equal(args[3], "");
      return result({ rows: [{ rowId: 9, cellData: [{ colId: 12, textCellValue: [{ type: "link", link: "ssh://git@git.sankuai.com/team/late-column.git" }] }, { colId: 2, fileCellValue: { url: "ssh://git@git.sankuai.com/team/attachment.git" } }] }], nextPageToken: "next" });
    }
    assert.equal(args[3], "next");
    return { exitCode: 1, stdout: Buffer.alloc(0) };
  };
  const scan = await scanSource({ source: { citadelUrl: "https://km.sankuai.com/page/123" }, processRunner, waitBetweenReads: async () => {} });
  assert.equal(pageReads, 2);
  assert.equal(scan.scan_status, "partially_scanned");
  assert.deepEqual(scan.repositories.map((repo) => repo.canonical_key), ["team/late-column"]);
  assert.deepEqual(scan.repositories[0].source_locations, ["database:12345:row:9:column:12"]);
  assert.equal(scan.issues[0].source, "database:12345:page:2");
});

test("v2 Citadel scan extracts hyperlinks from arbitrary table cell shapes", async () => {
  const processRunner = async (_command, args) => {
    if (args[1] === "getSimpleMarkdown") return result({ content: "" });
    if (args[1] === "getDocumentJson") return result({ body: '{"content":[{"type":"xtable","attrs":{"xtableId":"12345"}}]}' });
    if (args[1] === "listTables") return result({ tables: [] });
    if (args[1] === "getTableMeta") return result({ columns: [{ colId: 7 }] });
    return result({
      rows: [{ rowId: 9, cellData: [{ colId: 7, fileCellValue: { url: "ssh://git@git.vip.sankuai.com:2198/team/offline.git" } }] }],
      nextPageToken: "",
    });
  };
  const scan = await scanSource({
    source: { citadelUrl: "https://km.sankuai.com/page/123" },
    resultSchema: V3_SOURCE_RESULT_SCHEMA_V2,
    processRunner,
    waitBetweenReads: async () => {},
  });
  assert.deepEqual(scan.candidates, [{
    raw_value: "ssh://git@git.vip.sankuai.com:2198/team/offline.git",
    source_locations: ["database:12345:row:9:column:7"],
  }]);
});

test("official single-page adapter keeps authentication and paging errors explicit", async () => {
  class Client {
    constructor(config) { assert.deepEqual(config, { skillName: "citadel-database", ssoStrategy: "sso-ciba", oidcFallback: false }); }
    async ensureAuth(mis) { assert.equal(mis, "actual_user"); }
    async queryTableDataSinglePage(params) {
      assert.deepEqual(params, { tableId: 12345, columnIds: [1, 12], pageSize: 100, pageToken: undefined });
      return { rows: [], nextPageToken: "next" };
    }
  }
  assert.equal((await readCitadelTablePage({ tableId: "12345", columnIds: [1, 12], actorMis: "actual_user", Client })).nextPageToken, "next");
  class DeniedAuthClient extends Client { async ensureAuth() { throw new Error("citadel_document_access_denied"); } }
  await assert.rejects(readCitadelTablePage({ tableId: "12345", columnIds: [1], actorMis: "actual_user", Client: DeniedAuthClient }), /citadel_document_access_denied/u);
  class TimedOutAuthClient extends Client { async ensureAuth() { throw new Error("ETIMEDOUT"); } }
  await assert.rejects(readCitadelTablePage({ tableId: "12345", columnIds: [1], actorMis: "actual_user", Client: TimedOutAuthClient }), /citadel_scan_timeout/u);
  class FailedClient extends Client { async queryTableDataSinglePage() { throw new Error("permission denied"); } }
  await assert.rejects(readCitadelTablePage({ tableId: "12345", columnIds: [1], actorMis: "actual_user", Client: FailedClient }), /permission denied/u);
});

test("source scan pins actor CIBA and stops after authorization rejection", async () => {
  const calls = [];
  const scan = await scanSource({
    source: { citadelUrl: "https://km.sankuai.com/page/123" },
    resultSchema: V3_SOURCE_RESULT_SCHEMA_V2,
    processRunner: async (command, args, options) => {
      calls.push({ command, args, options });
      return { exitCode: 1, stdout: Buffer.from("HTTP 401 Unauthorized"), stderr: Buffer.alloc(0) };
    },
    waitBetweenReads: async () => {},
  });
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].args, [
    "citadel", "getSimpleMarkdown", "--contentId", "123",
    "--mis", "actual_user", "--sso-strategy", "sso-ciba", "--raw",
  ]);
  assert.equal(calls[0].options.env.AUTH_CACHE_FILE, "/private/attempt/auth-cache.json");
  assert.equal(scan.scan_status, "failed");
  assert.deepEqual(scan.read_errors, [{ source: "document", error_code: "citadel_auth_failed", retriable: false }]);
});

test("source scan fails closed without an isolated actor session", async () => {
  await assert.rejects(scanCitadelSource({
    source: { citadelUrl: "https://km.sankuai.com/page/123" },
    actorMis: "",
    authEnvironment: process.env,
    processRunner: async () => assert.fail("reader must not start"),
  }), /actor session is invalid/u);
});

test("source scan stops all later table reads after a page authorization denial", async () => {
  let pageReads = 0;
  const scan = await scanSource({
    source: { citadelUrl: "https://km.sankuai.com/page/123" },
    resultSchema: V3_SOURCE_RESULT_SCHEMA_V2,
    processRunner: async (_command, args) => {
      if (args[1] === "getSimpleMarkdown") return result({ content: "" });
      if (args[1] === "getDocumentJson") return result({ body: '{"content":[]}' });
      if (args[1] === "listTables") return result({ tableIds: ["12345", "23456"] });
      if (args[1] === "getTableMeta") return result({ columns: [{ colId: 1 }] });
      pageReads += 1;
      return { exitCode: 1, stdout: Buffer.alloc(0), stderr: Buffer.from("citadel_auth_failed") };
    },
    waitBetweenReads: async () => {},
  });
  assert.equal(pageReads, 1);
  assert.equal(scan.scan_status, "failed");
  assert.deepEqual(scan.read_errors, [{ source: "database:12345:page:1", error_code: "citadel_auth_failed", retriable: false }]);
});

test("source callback rejects wrong receipt hash and retries transport errors only", async () => {
  const context = { shardId: "shard", generation: 1, deadline: Date.now() + 60_000, source: { runId: "run", callback: { url: "https://example.invalid", token: "secret" } } };
  const result = { chunk_index: 0 };
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    if (calls === 1) return new Response("{}", { status: 503 });
    return Response.json({ data: { schema_version: "repository-authority-source-scan-callback-receipt/v1", status: "accepted", run_id: "run", shard_id: "shard", generation: 1, chunk_index: 0, result_hash: sha256(canonical(result)) } });
  };
  assert.equal((await deliverSourceResult({ context, result, fetchImpl, waitForRetry: async () => {} })).status, "accepted");
  assert.equal(calls, 2);
  await assert.rejects(deliverSourceResult({ context, result, fetchImpl: async () => Response.json({ status: "accepted", result_hash: "wrong" }) }), /receipt is invalid/u);
});

test("v2 source callback uses chunk-scoped idempotency and validates the v2 receipt", async () => {
  const context = { shardId: "shard", generation: 2, deadline: Date.now() + 60_000, source: { runId: "run", callback: { url: "https://example.invalid", token: "secret" } } };
  const payload = { schema_version: V3_SOURCE_RESULT_SCHEMA_V2, chunk_index: 7 };
  const receipt = await deliverSourceResult({
    context,
    result: payload,
    fetchImpl: async (_url, init) => {
      assert.equal(init.headers["Idempotency-Key"], "shard:2:7");
      return Response.json({ data: {
        schema_version: "repository-association-source-scan-callback-receipt/v2",
        status: "duplicate", run_id: "run", shard_id: "shard", generation: 2, chunk_index: 7,
        result_hash: sha256(canonical(payload)),
      } });
    },
  });
  assert.equal(receipt.status, "duplicate");
});

test("source callback chunks do not impose a total repository limit", () => {
  const entries = Array.from({ length: 12_001 }, (_, index) => ({ type: "repository", value: { canonical_key: `team/repo-${index}` } }));
  const chunks = splitSourceEntries(entries);
  assert.equal(chunks.flat().length, entries.length);
  assert.ok(chunks.every((chunk) => chunk.length <= 500));
});

test("a repository with many source locations is transmitted across bounded chunks without truncation", () => {
  const locations = Array.from({ length: 12_001 }, (_, index) => `database:12345:row:${index}:column:12`);
  const chunks = splitSourceEntries([{ type: "repository", value: { canonical_key: "team/repository", source_locations: locations } }]);
  assert.ok(chunks.length > 1);
  assert.deepEqual(chunks.flat().flatMap((entry) => entry.value.source_locations), locations);
  assert.ok(chunks.every((chunk) => Buffer.byteLength(JSON.stringify(chunk)) < 256 * 1024));
});

test("invalid complete URLs are issues while names are not expanded", () => {
  const issues = [];
  const candidates = extractRepositoryCandidates("board https://dev.sankuai.com/code/repo-detail/team/board/file/list/extra ssh://git@git.sankuai.com/team/standards.git", "document", issues);
  assert.deepEqual(candidates.map((item) => item.canonical_key), ["team/standards"]);
  assert.equal(issues[0].error_code, "invalid_repository_url");
});
