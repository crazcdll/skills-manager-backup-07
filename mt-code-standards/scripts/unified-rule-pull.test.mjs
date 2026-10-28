import assert from "node:assert/strict";
import { realpathSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, writeFile, access } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import test from "node:test";
import { pathToFileURL } from "node:url";
import { canonicalJson, sha256Hex, assertRuleResponseBudget, prepareUnifiedSyncRequest, syncUnifiedRuleBundle, syncEffectiveRuleBundle } from "./resolve-effective-rules.mjs";
import { readSkillMetadata, syncWithOfficialSso } from "./sync-effective-rules-with-sso.mjs";
import { buildSetupSkillPackage } from "./publish-setup-skill.mjs";
const repository = {
  repository_id: "repo:hotel-web",
  canonical_key: "hfe/hotel-web",
  standard_domain: "frontend",
};

const releaseRefs = [{
  rule_set_id: "frontend-l1",
  release_id: "frontend-l1@2026-09-04",
  scope_level: "L1",
}, {
  rule_set_id: "team-fe-l2",
  release_id: "team-fe-l2@1",
  scope_level: "L2",
}];

const bundleBody = ({
  files = [{ relative_path: "l1/frontend-l1.md", content: "# L1\n" }, {
    relative_path: "l2/team-fe-l2.md",
    content: "# L2\n",
  }],
  domain = "frontend",
  refs = releaseRefs,
  status = "ready",
  version = 4,
  legacy = false,
  repositoryIdentity = repository,
  stage,
  dependencyHash = sha256Hex("delivery-dependency"),
} = {}) => {
  version = legacy ? version : 4;
  refs = version === 4 ? refs.map((ref) => ({
    ...ref,
    standard_domain: ref.standard_domain ?? (/(?:java|backend)/u.test(ref.rule_set_id) ? "backend" : domain),
    local_rule_set_name: ref.local_rule_set_name ?? ref.rule_set_name ?? ref.rule_set_id,
  })) : refs.map(({ standard_domain, local_rule_set_name, ...ref }) => ref);
  const normalizedFiles = files.map((file) => ({
    ...(version === 4 ? (() => {
      const scope = file.relative_path.split("/")[0];
      const segment = file.relative_path.split("/")[1];
      const ref = refs.find((item) => item.scope_level.toLowerCase() === scope && (item.rule_set_id === segment || item.rule_set_name === segment)) ?? refs.find((item) => item.scope_level.toLowerCase() === scope) ?? refs[0];
      return { rule_set_id: ref.rule_set_id, release_id: ref.release_id };
    })() : {}),
    ...file,
    sha256: file.sha256 || sha256Hex(file.content),
    byte_size: file.byte_size ?? Buffer.byteLength(file.content, "utf8"),
  })).sort((left, right) => version >= 2
    ? (left.relative_path < right.relative_path ? -1 : left.relative_path > right.relative_path ? 1 : 0)
    : left.relative_path.localeCompare(right.relative_path, "en"));
  const projection = normalizedFiles.map(({ relative_path, rule_set_id, release_id, sha256, byte_size }) => ({
    ...(version === 4 ? { rule_set_id, release_id } : {}),
    relative_path,
    sha256,
    byte_size,
  }));
  const manifestHash = sha256Hex(canonicalJson(projection));
  const repo = { ...repositoryIdentity, standard_domain: domain };
  const snapshotProjection = {
    ...(version >= 2 ? { resolver_version: `effective-rule-bundle/v${version}` } : {}),
    repository_id: repo.repository_id,
    canonical_key: repo.canonical_key,
    standard_domain: repo.standard_domain,
    manifest_hash: manifestHash,
    release_refs: refs,
    ...((version === 3 || version === 4) && stage ? { stage, dependency_hash: dependencyHash } : {}),
  };
  return {
    schema_version: `effective-rule-bundle/v${version}`,
    status,
    snapshot: {
      ...(version >= 2 ? { resolver_version: `effective-rule-bundle/v${version}` } : {}),
      snapshot_id: sha256Hex(canonicalJson(snapshotProjection)),
      repository: repo,
      manifest_hash: manifestHash,
      release_refs: refs,
      total_bytes: normalizedFiles.reduce((sum, file) => sum + file.byte_size, 0),
      ...((version === 3 || version === 4) && stage ? { stage, dependency_hash: dependencyHash } : {}),
    },
    files: status === "ready" ? normalizedFiles : [],
  };
};

const bootstrapBody = ({
  files = [{ relative_path: "l1/frontend-l1/async.md", content: "# L1\n" }],
  domain = "frontend",
  refs = [{ rule_set_id: `${domain}-l1`, release_id: `${domain}-l1@test`, scope_level: "L1" }],
  status = "ready",
  stage,
  dependencyHash = sha256Hex("bootstrap-delivery-dependency"),
} = {}) => {
  refs = refs.map((ref) => ({ ...ref, standard_domain: domain, local_rule_set_name: ref.local_rule_set_name ?? ref.rule_set_id }));
  const normalizedFiles = files.map((file) => ({
    rule_set_id: refs[0].rule_set_id, release_id: refs[0].release_id,
    ...file,
    sha256: file.sha256 || sha256Hex(file.content),
    byte_size: file.byte_size ?? Buffer.byteLength(file.content, "utf8"),
  })).sort((left, right) => left.relative_path < right.relative_path ? -1 : 1);
  const manifestHash = sha256Hex(canonicalJson(normalizedFiles.map(({
    relative_path, rule_set_id, release_id, sha256, byte_size,
  }) => ({ relative_path, rule_set_id, release_id, sha256, byte_size }))));
  const version = 3;
  const schema = `l1-bootstrap-bundle/v${version}`;
  const snapshotId = sha256Hex(canonicalJson({
    bootstrap_version: schema,
    standard_domain: domain,
    manifest_hash: manifestHash,
    release_refs: refs,
    ...(stage ? { stage, dependency_hash: dependencyHash } : {}),
  }));
  return {
    schema_version: schema,
    status,
    snapshot: {
      bootstrap_version: schema,
      snapshot_id: snapshotId,
      standard_domain: domain,
      release_refs: refs,
      manifest_hash: manifestHash,
      total_bytes: normalizedFiles.reduce((sum, file) => sum + file.byte_size, 0),
      ...(stage ? { stage, dependency_hash: dependencyHash } : {}),
    },
    files: status === "ready" ? normalizedFiles : [],
  };
};


const rootDir = async () => realpathSync(await mkdtemp(path.join(os.tmpdir(), "unified-rule-pull-")));
const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(body) });
const resolveEnvelope = (request, bundle, reason) => {
  const kind = bundle.schema_version === "effective-rule-bundle/v4" ? "effective" : "l1";
  return { schema_version: "rule-bundle-resolution/v1", request_id: "request-unified-test", pull_id: request.execution.pull_id,
    bundle_kind: kind, delivery_mode: bundle.snapshot.release_refs.some(r => r.scope_level === "L2") ? "l1_l2" : "l1_only",
    selection_reason: reason || (kind === "effective" ? "repository_effective" : request.repository_locator ? "repository_not_registered" : "repository_identity_unavailable"),
    standard_domain: bundle.snapshot.repository?.standard_domain || bundle.snapshot.standard_domain,
    stage: request.stage, target: { canonical_key: request.repository_locator, ...request.target }, bundle };
};
const server = (bundle, observe = () => {}, reason) => async (url, init) => {
  const request = JSON.parse(init.body); observe(request, url, init);
  return response(resolveEnvelope(request, typeof bundle === "function" ? bundle(request) : bundle, reason));
};
const pull = (root, options = {}) => syncUnifiedRuleBundle({ repoRoot: root, publicPull: true, domain: "frontend", stage: "coding", ...options });

test("directory fallback is the Git source root, never output-dir", async () => {
  const root = await rootDir(); const child = path.join(root, "packages", "one"); const output = await rootDir();
  await mkdir(child, { recursive: true }); execFileSync("git", ["init", "-q"], { cwd: root });
  const prepared = await prepareUnifiedSyncRequest({ cwd: child, outputDir: output, domain: "frontend", stage: "coding" });
  assert.equal(prepared.repositoryLocator, null); assert.equal(prepared.sourceRoot, root);
  assert.deepEqual(prepared.target, { display_name: root, source: "local_directory" }); assert.equal(prepared.targetRoot, output);
});

test("missing domain and stage are reported together without network or writes", async () => {
  const root = await rootDir(); let calls = 0;
  await assert.rejects(pull(root, { domain: undefined, stage: undefined, fetchImpl: async () => { calls++; } }), e => {
    assert.deepEqual(e.issues.map(i => i.field).sort(), ["stage", "standard_domain"]); return e.code === "rule_parameters_invalid";
  });
  assert.equal(calls, 0); await assert.rejects(access(path.join(root, ".mdp")));
});

test("explicit malformed repository does not silently become a directory pull", async () => {
  const root = await rootDir();
  await assert.rejects(pull(root, { repositoryLocator: "not a repository", fetchImpl: async () => { assert.fail("network"); } }));
});

test("a directory pulls L1 with one anonymous request and unknown metadata stays null", async () => {
  const root = await rootDir(); let calls = 0;
  const result = await pull(root, { fetchImpl: server(bootstrapBody({ stage: "coding" }), (request, url, init) => {
    calls++; assert.match(url, /\/v1\/public\/rule-bundles\/resolve$/u); assert.equal(init.headers.Authorization, undefined);
    assert.equal(request.repository_locator, null); assert.equal(request.execution.skill_name, null);
    assert.equal(request.execution.skill_version, null); assert.equal(request.execution.client_name, null);
    assert.equal(request.target.display_name, root); assert.equal(request.scope, "effective"); assert.equal(request.declared_actor, undefined);
  }) });
  assert.equal(calls, 1); assert.equal(result.status, "installed"); assert.equal(result.delivery_mode, "l1_only");
  const manifest = JSON.parse(await readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json"), "utf8"));
  assert.equal(manifest.schema_version, "mt-l1-bootstrap-manifest/v5"); assert.equal(manifest.resolution.target.canonical_key, null);
  assert.match(manifest.resolution_hash, /^[a-f0-9]{64}$/u);
});

test("same context sends a validated kind-bound snapshot and accepts not_modified", async () => {
  const root = await rootDir(); const ready = bootstrapBody({ stage: "coding" });
  await pull(root, { fetchImpl: server(ready) });
  const result = await pull(root, { fetchImpl: server({ ...ready, status: "not_modified", files: [] }, request => {
    assert.deepEqual(request.known_snapshot, { bundle_kind: "l1", snapshot_id: ready.snapshot.snapshot_id });
  }) });
  assert.equal(result.status, "not_modified");
});

test("tampering bound resolution context is rejected before sending a request", async () => {
  const root = await rootDir(); await pull(root, { fetchImpl: server(bootstrapBody({ stage: "coding" })) });
  const filename = path.join(root, ".mdp/rules/.mt-l1-bootstrap.json"); const manifest = JSON.parse(await readFile(filename, "utf8"));
  manifest.resolution.target.display_name = "/another/project"; await writeFile(filename, JSON.stringify(manifest));
  await assert.rejects(pull(root, { fetchImpl: async () => assert.fail("network") }), e => e.code === "RULE_BUNDLE_BOOTSTRAP_MANIFEST_INVALID");
});

test("formal to L1 to formal atomically removes old L2, preserves project and unknown files", async () => {
  const root = await rootDir(); const repositoryLocator = repository.canonical_key;
  await pull(root, { repositoryLocator, fetchImpl: server(bundleBody({ stage: "coding" })) });
  const rules = path.join(root, ".mdp/rules");
  await mkdir(path.join(rules, "project")); await writeFile(path.join(rules, "project/local.md"), "project"); await writeFile(path.join(rules, "unknown.md"), "unknown");
  const result = await pull(root, { repositoryLocator, fetchImpl: server(bootstrapBody({ stage: "coding" }), request => assert.equal(request.known_snapshot.bundle_kind, "effective"), "l2_not_accessible") });
  assert.equal(result.removed_l2_files, 1); await assert.rejects(access(path.join(rules, "team/fe/team-fe-l2/team-fe-l2.md")));
  await assert.rejects(access(path.join(rules, ".mt-effective-rule-bundle.json")));
  assert.equal(await readFile(path.join(rules, "project/local.md"), "utf8"), "project"); assert.equal(await readFile(path.join(rules, "unknown.md"), "utf8"), "unknown");
  const upgraded = await pull(root, { repositoryLocator, fetchImpl: server(bundleBody({ stage: "coding" })) });
  assert.equal(upgraded.delivery_mode, "l1_l2"); await assert.rejects(access(path.join(rules, ".mt-l1-bootstrap.json")));
  assert.equal(JSON.parse(await readFile(path.join(rules, ".mt-effective-rule-bundle.json"), "utf8")).schema_version, "mt-effective-rule-bundle-manifest/v8");
});

test("legacy formal manifest migrates safely to L1 only for the same canonical identity", async () => {
  const root = await rootDir();
  await syncEffectiveRuleBundle({ repoRoot: root, repositoryLocator: repository.canonical_key, publicPull: true, stage: "coding", fetchImpl: async () => response(bundleBody({ stage: "coding" })) });
  await assert.rejects(pull(root, { fetchImpl: async () => assert.fail("network") }), e => e.code === "RULE_BUNDLE_REPOSITORY_CONFLICT");
  const receipt = await pull(root, { repositoryLocator: repository.canonical_key, fetchImpl: server(bootstrapBody({ stage: "coding" }), request => assert.equal(request.known_snapshot, undefined)) });
  assert.equal(receipt.removed_l2_files, 1);
});

test("modified managed L2 blocks downgrade and leaves all files intact", async () => {
  const root = await rootDir(); const options = { repositoryLocator: repository.canonical_key };
  const receipt = await pull(root, { ...options, fetchImpl: server(bundleBody({ stage: "coding" })) });
  const name = receipt.managed_files.find(p => p.startsWith("team/")); const filename = path.join(root, ".mdp/rules", name);
  await writeFile(filename, "user edit");
  await assert.rejects(pull(root, { ...options, fetchImpl: async () => assert.fail("network") }), e => e.code === "RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED");
  assert.equal(await readFile(filename, "utf8"), "user edit");
});

test("mismatched envelope, unexpected L2 and wrong pull id are rejected without writing", async () => {
  for (const mutate of [e => { e.pull_id = "other"; }, e => { e.delivery_mode = "l1_l2"; }, e => { e.stage = "cr"; }, e => { e.target.canonical_key = "other/repo"; }]) {
    const root = await rootDir();
    await assert.rejects(pull(root, { fetchImpl: async (_url, init) => { const e = resolveEnvelope(JSON.parse(init.body), bootstrapBody({ stage: "coding" })); mutate(e); return response(e); } }), e => e.code === "RULE_BUNDLE_RESOLUTION_INVALID");
    await assert.rejects(access(path.join(root, ".mdp")));
  }
});

test("service diagnostics retain field issues and request id, never retry as bootstrap", async () => {
  const root = await rootDir(); let calls = 0;
  await assert.rejects(pull(root, { fetchImpl: async () => { calls++; return response({ error: { code: "l1_release_not_found", message: "前端编码阶段 L1 尚未发布", issues: [{ field: "standard_domain", code: "not_found", message: "请检查前端规范发布状态" }], request_id: "request-123", retryable: false } }, 503); } }), e => {
    assert.equal(e.message, "前端编码阶段 L1 尚未发布"); assert.equal(e.request_id, "request-123"); assert.equal(e.issues[0].field, "standard_domain"); return e.code === "l1_release_not_found";
  }); assert.equal(calls, 1);
});

test("an old service is reported as unsupported without falling back to old routes", async () => {
  const root = await rootDir(); let calls = 0;
  await assert.rejects(pull(root, { fetchImpl: async () => { calls++; return response({ error: { code: "not_found", message: "Route not found" } }, 404); } }), e => e.code === "resolution_contract_not_supported"); assert.equal(calls, 1);
});

test("frontend and backend support every explicit stage, without source-code inference", async () => {
  for (const domain of ["frontend", "backend"]) for (const stage of ["design", "coding", "cr"]) {
    const root = await rootDir(); const result = await pull(root, { domain, stage, fetchImpl: server(bootstrapBody({ domain, stage })) });
    assert.equal(result.standard_domain, domain); assert.equal(result.stage, stage);
  }
});

test("a scope/stage change does not reuse the previous known snapshot", async () => {
  const root = await rootDir(); await pull(root, { fetchImpl: server(bootstrapBody({ stage: "coding" })) });
  await pull(root, { stage: "cr", bootstrap: true, fetchImpl: server(bootstrapBody({ stage: "cr" }), request => {
    assert.equal(request.scope, "l1"); assert.equal(request.known_snapshot, undefined);
  }, "explicit_l1") });
});

test("metadata comes from the actual setup distribution, not receiver directory or a default name", async () => {
  const staged = buildSetupSkillPackage();
  try {
    const module = await import(pathToFileURL(path.join(staged.packageRoot, "scripts/sync-effective-rules-with-sso.mjs")).href);
    const metadata = await module.readSkillMetadata(); assert.equal(metadata.skillName, "mt-code-standards-setup"); assert.equal(metadata.skillVersion, "1.2.0");
    const root = await rootDir(); let request;
    await module.syncWithOfficialSso({ options: { repoRoot: root, domain: "frontend", stage: "coding" }, environment: {}, fetchImpl: server(bootstrapBody({ stage: "coding" }), body => { request = body; }) });
    assert.equal(request.execution.skill_name, "mt-code-standards-setup"); assert.equal(request.execution.client_name, "mt-code-standards-setup");
    assert.equal((await readSkillMetadata(path.join(root, "missing.md"))).skillName, null);
  } finally { staged.cleanup(); }
});

test("unchanged contents refresh a changed display name and selection reason atomically", async () => {
  const root = await rootDir(); const repositoryLocator = "team/new"; const ready = bootstrapBody({ stage: "coding" });
  await pull(root, { repositoryLocator, fetchImpl: server(ready) });
  const result = await pull(root, { repositoryLocator, fetchImpl: async (_url, init) => {
    const request = JSON.parse(init.body); const envelope = resolveEnvelope(request, { ...ready, status: "not_modified", files: [] }, "l2_not_accessible");
    envelope.target = { canonical_key: repositoryLocator, display_name: "已登记的新名称", source: "platform" };
    return response(envelope);
  } });
  assert.equal(result.status, "not_modified");
  const manifest = JSON.parse(await readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json"), "utf8"));
  assert.equal(manifest.resolution.target.display_name, "已登记的新名称"); assert.equal(manifest.resolution.selection_reason, "l2_not_accessible");
  assert.equal(manifest.resolution_hash, sha256Hex(canonicalJson({ resolution: manifest.resolution, snapshot_id: manifest.snapshot_id })));
  await pull(root, { repositoryLocator, fetchImpl: server(ready) });
});

test("L1 envelope cannot relabel a different-domain package", async () => {
  const root = await rootDir();
  await assert.rejects(pull(root, { fetchImpl: async (_url, init) => {
    const envelope = resolveEnvelope(JSON.parse(init.body), bootstrapBody({ domain: "backend", stage: "coding" }));
    envelope.standard_domain = "frontend";
    return response(envelope);
  } }), e => e.code === "RULE_BUNDLE_RESOLUTION_INVALID");
  await assert.rejects(access(path.join(root, ".mdp")));
});


test("unified envelope preserves separate rule and agents-index response budgets", () => {
  const indexes = [{ content: "a".repeat(5 * 1024 * 1024) }];
  assert.doesNotThrow(() => assertRuleResponseBudget({ schema_version: "rule-bundle-resolution/v1", bundle: { files: [], agents_indexes: indexes } }, { allowAgentsIndexes: true }));
  assert.throws(() => assertRuleResponseBudget({ schema_version: "rule-bundle-resolution/v1", bundle: { files: [{ content: "x".repeat(4 * 1024 * 1024) }], agents_indexes: [] } }, { allowAgentsIndexes: true }), e => e.code === "RULE_BUNDLE_RESPONSE_TOO_LARGE");
});


test("server-resolved L1 domain retains its real provenance in the new manifest", async () => {
  const root = await rootDir(); const options = { repositoryLocator: "team/project", domain: undefined, bootstrap: true };
  const ready = bootstrapBody({ stage: "coding" });
  const result = await pull(root, { ...options, fetchImpl: server(ready, request => assert.equal(request.standard_domain, undefined), "explicit_l1") });
  assert.equal(result.domain_source, "repository_configuration");
  const manifest = JSON.parse(await readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json"), "utf8"));
  assert.equal(manifest.domain_source, "repository_configuration"); assert.equal(manifest.resolution.domain_source, "repository_configuration");
  const cached = await pull(root, { ...options, fetchImpl: server({ ...ready, status: "not_modified", files: [] }, () => {}, "explicit_l1") });
  assert.equal(cached.status, "not_modified");
});


test("explicit empty repository never inherits origin through the Skill wrapper", async () => {
  const root = await rootDir();
  execFileSync("git", ["init", "-q"], { cwd: root });
  execFileSync("git", ["remote", "add", "origin", "ssh://git@git.sankuai.com/team/actual.git"], { cwd: root });
  const discovered = await prepareUnifiedSyncRequest({ repoRoot: root, domain: "frontend", stage: "coding" });
  assert.equal(discovered.repositoryLocator, "team/actual");
  for (const repositoryLocator of ["", "   "]) {
    let calls = 0;
    await assert.rejects(syncWithOfficialSso({ options: { repoRoot: root, repositoryLocator, domain: "frontend", stage: "coding" }, environment: {}, fetchImpl: async () => { calls++; assert.fail("network"); } }), error => {
      assert.equal(error.issues[0].field, "repository_locator"); return error.code === "repository_locator_invalid";
    });
    assert.equal(calls, 0);
  }
});


test("unrecognized discovered origins use directory L1 without contacting the origin host", async () => {
  for (const origin of ["https://github.com/example/project.git", "ssh://git@git.example.net/team/project.git"]) {
    const root = await rootDir();
    execFileSync("git", ["init", "-q"], { cwd: root });
    execFileSync("git", ["remote", "add", "origin", origin], { cwd: root });
    let calls = 0;
    const result = await syncWithOfficialSso({ options: { repoRoot: root, domain: "frontend", stage: "coding" }, environment: {}, fetchImpl: server(bootstrapBody({ stage: "coding" }), (request, url) => {
      calls++; assert.equal(new URL(url).hostname, "db0y7dgg85gphojyva.database.sankuai.com");
      assert.match(url, /\/v1\/public\/rule-bundles\/resolve$/u);
      assert.equal(request.repository_locator, null); assert.deepEqual(request.target, { display_name: root, source: "local_directory" });
      assert.equal(JSON.stringify(request).includes(origin), false);
    }) });
    assert.equal(calls, 1); assert.equal(result.delivery_mode, "l1_only"); assert.equal(result.selection_reason, "repository_identity_unavailable");
    await assert.rejects(syncWithOfficialSso({ options: { repoRoot: await rootDir(), repositoryLocator: origin, domain: "frontend", stage: "coding" }, environment: {}, fetchImpl: async () => assert.fail("explicit unsupported origin must not send a request") }), error => error.code === "repository_locator_invalid");
  }
});
