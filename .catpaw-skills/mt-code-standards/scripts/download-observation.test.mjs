import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, readFile, readdir, writeFile, rm, realpath, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { pathToFileURL } from "node:url";
import { createDownloadObservation, createEventQueue, sanitizeEvent, EVENT_URL } from "./download-observation.mjs";
import { runSkill } from "./sync-effective-rules-with-sso.mjs";

const temp = async t => { const dir = await realpath(await mkdtemp(path.join(tmpdir(), "download-observation-test-"))); t.after(() => rm(dir, { recursive: true, force: true })); return dir; };
const collector = () => {
  const events = [];
  return { events, factory: args => createDownloadObservation({ ...args, queue: {
    async enqueue(e) { events.push(e); }, async flush() {},
  } }) };
};
const input = { schema_version: "rule-download-event/v1", event_id: randomUUID(), run_id: randomUUID(), event_type: "start",
  started_at: new Date().toISOString(), occurred_at: new Date().toISOString(), client_type: "skill", skill_name: "mt-code-standards-setup", skill_version: "1.2.0", client_version: "1.2.0", status: null };
const ack = (event, status = "recorded") => new Response(JSON.stringify({ ok: true, data: { schema_version: "rule-download-event-receipt/v1", event_id: event.event_id, status } }));

for (const name of ["mt-code-standards", "mt-code-standards-setup"]) test(`${name} uses actual distribution identity and stable direct metadata`, async t => {
  const dir = await temp(t); const file = path.join(dir, "SKILL.md");
  await writeFile(file, `---\nname: ${name}\nversion: "1.2.0"\n---\n`);
  const { events, factory } = collector();
  await runSkill({ skillUrl: pathToFileURL(file), argv: ["--transport", "direct", "--execution-agent", "codex", "--stage", "cr", "--domain", "backend"], environment: {}, observationFactory: factory,
    sync: async ({ observation }) => { observation.phase("auth"); observation.request(randomUUID()); observation.phase("install"); return { status: "not_modified" }; } });
  assert.equal(events.length, 2); assert.equal(events[0].skill_name, name);
  assert.equal(events[0].transport, "direct"); assert.equal(events[1].transport, "direct");
  assert.equal(events[0].execution_agent, "codex"); assert.equal(events[1].status, "not_modified");
  assert.equal(events[1].request_count, 1); assert.equal(events[1].standard_domain, "backend");
  assert.equal(events[0].run_id, events[1].run_id); assert.notEqual(events[0].event_id, events[1].event_id);
});
test("argument failure is counted before any auth or request and preserves original error", async () => {
  const { events, factory } = collector();
  await assert.rejects(runSkill({ argv: ["--unknown"], environment: {}, observationFactory: factory,
    sync: () => { throw Error("must not run"); } }), { code: "RULE_BUNDLE_ARGUMENT_INVALID" });
  assert.equal(events[1].failure_stage, "preflight"); assert.equal(events[1].request_count, 0);
  assert.equal(events[1].status, "failed");
});
for (const phase of ["auth", "request", "response_validation", "install"]) test(`failure in ${phase} preserves code without sensitive text`, async () => {
  const { events, factory } = collector(); const error = Object.assign(new Error("/private/file Bearer secret"), { code: "SAFE_ERROR" });
  await assert.rejects(runSkill({ argv: [], environment: {}, observationFactory: factory,
    sync: async ({ observation }) => { observation.phase(phase); throw error; } }), e => e === error);
  assert.equal(events[1].failure_stage, phase); assert.equal(events[1].error_code, "SAFE_ERROR");
  assert.ok(!JSON.stringify(events).includes("secret")); assert.ok(!JSON.stringify(events).includes("/private/file"));
});
test("real Runner DNS failure counts one request and retains existing exception", async t => {
  const dir = await temp(t); const { events, factory } = collector();
  await assert.rejects(runSkill({ argv: ["--repo-root", dir, "--domain", "frontend", "--stage", "coding"], environment: {}, observationFactory: factory,
    fetchImpl: async (_url, init) => { assert.equal(init.headers["X-Setup-Run-Id"], events[0].run_id); throw Error("ENOTFOUND"); } }), { code: "RULE_BUNDLE_NETWORK_FAILED" });
  assert.equal(events[1].failure_stage, "request"); assert.equal(events[1].request_count, 1);
});
test("real Runner malformed successful body is a validation failure", async t => {
  const dir = await temp(t); const { events, factory } = collector();
  await assert.rejects(runSkill({ argv: ["--repo-root", dir, "--domain", "frontend", "--stage", "coding"], environment: {}, observationFactory: factory,
    fetchImpl: async () => new Response('{}') }), { code: "RULE_BUNDLE_RESOLUTION_INVALID" });
  assert.equal(events[1].failure_stage, "response_validation");
});
test("missing terminal event stays absent, retry attempts share one run and pull", async () => {
  const { events, factory } = collector(); const o = factory({}); const pull = randomUUID();
  await o.start(); o.request(pull); o.phase("auth"); o.request(pull);
  assert.equal(events.length, 1); // abrupt process termination produces no fake finish
  await o.finish({ status: "installed", pull_id: pull });
  assert.equal(events[1].request_count, 2); assert.equal(events[1].pull_id, pull);
});
test("broken queue cannot replace a successful or failed operation", async () => {
  const observationFactory = args => createDownloadObservation({ ...args, queue: { enqueue() { throw Error("disk"); }, flush() { throw Error("network"); } } });
  assert.deepEqual(await runSkill({ argv: [], environment: {}, observationFactory, sync: async () => ({ status: "installed" }) }), { status: "installed" });
  const original = Object.assign(Error("original"), { code: "ORIGINAL" });
  await assert.rejects(runSkill({ argv: [], environment: {}, observationFactory, sync: async () => { throw original; } }), e => e === original);
});
test("queue 404/503 retries with original event id, strips tampered fields and accepts duplicate ACK", async t => {
  const directory = await temp(t); let clock = Date.now(); let status = 404; const sent = [];
  const q = createEventQueue({ directory, now: () => clock, fetchImpl: async (url, init) => {
    assert.equal(url, EVENT_URL); assert.equal(init.headers.Authorization, undefined);
    const e = JSON.parse(init.body); sent.push(e); return status === 200 ? ack(e, "duplicate") : new Response("", { status });
  } });
  await q.enqueue(input); await q.flush(); assert.equal(sent.length, 1);
  await q.flush(); assert.equal(sent.length, 1); // backoff
  const file = path.join(directory, `${input.event_id}.json`); const item = JSON.parse(await readFile(file));
  item.event.token = "secret"; item.event.path = "/private/user"; await writeFile(file, JSON.stringify(item));
  clock += 2000; status = 503; await q.flush(); clock += 5000; status = 200; await q.flush();
  assert.equal(sent.length, 3); assert.equal(sent[2].event_id, input.event_id);
  assert.ok(!JSON.stringify(sent).includes("secret")); assert.deepEqual(await readdir(directory), []);
});
test("queue timeout is bounded even if fetch ignores cancellation", async t => {
  const directory = await temp(t); const q = createEventQueue({ directory, timeoutMs: 10, fetchImpl: () => new Promise(() => {}) });
  await q.enqueue(input); const before = Date.now(); await q.flush(); assert.ok(Date.now() - before < 1000);
  assert.equal((await readdir(directory)).length, 1);
});
test("queue is bounded and does not follow symlinks", async t => {
  const root = await temp(t); const directory = path.join(root, "queue");
  const q = createEventQueue({ directory, maxFiles: 2, fetchImpl: () => { throw Error("must not call"); } });
  for (let i = 0; i < 5; i++) await q.enqueue({ ...input, event_id: randomUUID() });
  assert.equal((await readdir(directory)).length, 2);
  const link = path.join(root, "link"); await symlink(directory, link);
  await createEventQueue({ directory: link }).enqueue(input);
  assert.equal((await readdir(directory)).length, 2);
});
test("sanitizer rejects invalid schema and strips CLI skill attribution", () => {
  assert.equal(sanitizeEvent({ ...input, schema_version: "other" }), null);
  const event = sanitizeEvent({ ...input, client_type: "cli", client_name: "@nibfe/mt-coding-standards", token: "secret" });
  assert.equal(event.skill_name, null); assert.equal(event.skill_version, null); assert.equal(event.token, undefined);
});
for (const [upstream, code, status] of [
  ["sub_access_denied", "RULE_BUNDLE_SSO_ACCESS_DENIED", "failed"],
  ["MOA_USER_REJECTED", "RULE_BUNDLE_CIBA_REJECTED", "cancelled"],
]) test(`real direct auth ${upstream} terminates without a download attempt`, async t => {
  const dir = await temp(t); const { events, factory } = collector();
  await assert.rejects(runSkill({ argv: ["--repo-root", dir, "--domain", "frontend", "--stage", "coding", "--transport", "direct", "--execution-agent", "catpaw"],
    environment: {}, observationFactory: factory,
    execute: async () => ({ stdout: JSON.stringify({ error: upstream, error_description: "authorization failed" }) }),
    fetchImpl: () => { throw Error("must not download"); },
  }), { code });
  assert.equal(events[1].failure_stage, "auth"); assert.equal(events[1].request_count, 0);
  assert.equal(events[1].status, status); assert.equal(events[0].transport, "direct");
});
