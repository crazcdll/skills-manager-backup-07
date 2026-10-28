import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import { access, mkdtemp, mkdir, readFile, writeFile, symlink } from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  canonicalJson,
  assertRuleResponseBudget,
  MAX_AGENTS_INDEX_RESPONSE_BYTES,
  RuleBundleError,
  canonicalRepositoryKey,
  detectRepositoryDomain,
  readLocalGitMis,
  sha256Hex,
  syncEffectiveRuleBundle,
  normalizePullExecution,
  validateRepositoryLocator,
} from "./resolve-effective-rules.mjs";

const response = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  text: async () => JSON.stringify(body),
});

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

const seedLegacyManifest = async (root, bundle, manifestVersion) => {
  const flat = manifestVersion >= 3;
  const localFiles = bundle.files.map((file) => {
    const parts = file.relative_path.split("/");
    const local = flat ? parts[0] === "l1" ? `company/${parts.at(-1)}` : `team/${parts.length > 2 ? parts[1] : parts.at(-1).replace(/[.]md$/iu, "")}/${parts.at(-1)}` : `${bundle.snapshot.repository.standard_domain}/${file.relative_path}`;
    return { ...file, local };
  });
  const manifest = {
    schema_version: `mt-effective-rule-bundle-manifest/v${manifestVersion}`,
    ...(manifestVersion >= 2 ? { resolver_version: bundle.schema_version } : {}),
    ...(flat ? { local_layout: "company-team/v1", managed_file_sources: Object.fromEntries(localFiles.map((file) => [file.local, file.relative_path])) } : {}),
    ...(manifestVersion >= 4 ? { stage: bundle.snapshot.stage ?? null, ...(bundle.snapshot.dependency_hash ? { dependency_hash: bundle.snapshot.dependency_hash } : {}) } : {}),
    repository: bundle.snapshot.repository,
    standard_domain: bundle.snapshot.repository.standard_domain,
    snapshot_id: bundle.snapshot.snapshot_id,
    manifest_hash: bundle.snapshot.manifest_hash,
    release_refs: bundle.snapshot.release_refs,
    total_bytes: bundle.snapshot.total_bytes,
    managed_files: localFiles.map((file) => file.local),
    managed_file_hashes: Object.fromEntries(localFiles.map((file) => [file.local, file.sha256])),
    managed_file_sizes: Object.fromEntries(localFiles.map((file) => [file.local, file.byte_size])),
  };
  for (const file of localFiles) {
    const output = path.join(root, ".mdp/rules", file.local);
    await mkdir(path.dirname(output), { recursive: true });
    await writeFile(output, file.content);
  }
  await writeFile(path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"), JSON.stringify(manifest));
  return manifest;
};

const createRepository = async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "mt-rule-bundle-test-"));
  await mkdir(path.join(root, ".git"));
  return root;
};

const createTrackedRepository = async (files) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "mt-rule-domain-test-"));
  execFileSync("git", ["init", "-q"], { cwd: root });
  for (const [relativePath, content] of Object.entries(files)) {
    const target = path.join(root, ...relativePath.split("/"));
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, content, "utf8");
  }
  execFileSync("git", ["add", ...Object.keys(files)], { cwd: root });
  return root;
};

test("reads only a valid MIS from the repository-local Git config", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "mt-rule-git-mis-"));
  execFileSync("git", ["init", "-q"], { cwd: root, stdio: "ignore" });
  assert.equal(readLocalGitMis(root), "");
  execFileSync("git", ["config", "--local", "user.mis", "ZhangCe07"], { cwd: root });
  assert.equal(readLocalGitMis(root), "zhangce07");
  execFileSync("git", ["config", "--local", "user.mis", "not a mis"], { cwd: root });
  assert.equal(readLocalGitMis(root), "");
  assert.equal(readLocalGitMis(path.join(root, "missing")), "");
});

test("accepts every supported locator and preserves query/hash suffixes", () => {
  const locators = [
    "https://dev.sankuai.com/code/repo-detail/hfe/hotel-web/file/list?branch=master#readme",
    "http://assets.sankuai.com/git/team/hotel-web?branch=master",
    "https://git.sankuai.com/hfe/hotel-web.git?ref=master",
    "ssh://git@git.sankuai.com/hfe/hotel-web.git?ref=master",
    "ssh://git@git.dianpingoa.com/hfe/hotel-web.git",
    "ssh://git@git.vip.sankuai.com:2198/hfe/hotel-web.git",
    "ssh://git@unknown.example.com/team/CaseSensitive.git",
    "ssh://git@gitserver/team/CaseSensitive.git",
    "ssh://git@[2001:db8::1]:2222/team/CaseSensitive.git",
    "git@git.sankuai.com:hfe/hotel-web.git#master",
    "git@unknown.example.com:team/CaseSensitive.git",
    "git@unknown.example.com:/srv/git/CaseSensitive.git",
    "hfe/hotel-web?ref=master",
    "hotel-web?ref=master",
  ];
  for (const locator of locators) assert.equal(validateRepositoryLocator(locator), locator);
});

test("public pull uses the anonymous repository route without an Authorization header", async () => {
  const root = await createRepository();
  let request;
  const receipt = await syncEffectiveRuleBundle({
    publicPull: true,
    repositoryLocator: "hfe/hotel-web",
    repoRoot: root,
    fetchImpl: async (url, init) => {
      request = { url, init };
      return response(bundleBody());
    },
  });
  assert.match(request.url, /\/v1\/public\/effective-rule-bundles\/resolve$/u);
  assert.equal(request.init.headers.Authorization, undefined);
  assert.equal(receipt.status, "installed");
  await assert.rejects(
    syncEffectiveRuleBundle({
      publicPull: true,
      bootstrap: true, mis: "aicr-agent", domain: "frontend",
      repositoryLocator: "hfe/new-web",
      repoRoot: root,
      fetchImpl: async () => response(bundleBody()),
    }),
    (error) => error.code === "RULE_BUNDLE_BOOTSTRAP_CONFLICT",
  );
});

test("public pull normalizes a Git origin and rejects non-canonical locators before network access", async () => {
  const root = await createRepository();
  let requestBody;
  await syncEffectiveRuleBundle({
    publicPull: true,
    repositoryLocator: "git@git.sankuai.com:HFE/Hotel-Web.git#main",
    repoRoot: root,
    fetchImpl: async (_url, init) => {
      requestBody = JSON.parse(init.body);
      return response(bundleBody());
    },
  });
  assert.equal(requestBody.repository_locator, "hfe/hotel-web");
  let calls = 0;
  await assert.rejects(
    syncEffectiveRuleBundle({
      publicPull: true,
      repositoryLocator: "hotel-web",
      repoRoot: root,
      fetchImpl: async () => { calls += 1; return response(bundleBody()); },
    }),
    (error) => error.code === "RULE_BUNDLE_PUBLIC_CANONICAL_REQUIRED",
  );
  assert.equal(calls, 0);
});

test("derives an exact canonical key only from namespace-qualified locators", () => {
  assert.equal(canonicalRepositoryKey("git@git.sankuai.com:HFE/Hotel-Web.git#main"), "hfe/hotel-web");
  assert.equal(canonicalRepositoryKey("ssh://git@git.dianpingoa.com/HFE/Hotel-Web.git"), "hfe/hotel-web");
  assert.equal(canonicalRepositoryKey("https://dev.sankuai.com/code/repo-detail/HFE/Hotel-Web/file/list"), "hfe/hotel-web");
  assert.equal(canonicalRepositoryKey("ssh://git@git.vip.sankuai.com:2198/HFE/Hotel-Web.git"), "");
  assert.equal(canonicalRepositoryKey("git@unknown.example.com:HFE/Hotel-Web.git"), "");
  assert.equal(canonicalRepositoryKey("https://git.sankuai.com/HFE/Hotel-Web.git"), "");
  assert.equal(canonicalRepositoryKey("https://tools.sankuai.com/git/HFE/Hotel-Web"), "");
  assert.equal(canonicalRepositoryKey("hotel-web"), "");
});

test("detects frontend, backend, mixed and unknown domains from Git-tracked evidence only", async () => {
  const frontend = await createTrackedRepository({ "src/App.tsx": "export default null;\n" });
  const backend = await createTrackedRepository({
    "pom.xml": "<project/>\n",
    "src/main/java/Test.java": "class Test {}\n",
  });
  const mixed = await createTrackedRepository({
    "src/App.vue": "<template/>\n",
    "build.gradle.kts": "plugins {}\n",
    "src/main/java/Test.java": "class Test {}\n",
  });
  const unknown = await createTrackedRepository({ "README.md": "docs\n" });
  await writeFile(path.join(unknown, "App.tsx"), "untracked\n", "utf8");
  assert.equal((await detectRepositoryDomain(frontend)).classification, "frontend");
  assert.equal((await detectRepositoryDomain(backend)).classification, "backend");
  assert.equal((await detectRepositoryDomain(mixed)).classification, "mixed");
  assert.equal((await detectRepositoryDomain(unknown)).classification, "unknown");
});

test("declares the NoCode production audience without retaining the obsolete audience", async () => {
  const skillSource = await readFile(new URL("../SKILL.md", import.meta.url), "utf8");
  const runnerSource = await readFile(new URL("./resolve-effective-rules.mjs", import.meta.url), "utf8");
  const obsoleteAudience = ["f32a", "546874"].join("");
  assert.match(skillSource, /923a237244/);
  assert.equal(`${skillSource}\n${runnerSource}`.includes(obsoleteAudience), false);
});

test("runs the base runner when its Skill directory is installed as a symbolic link", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-symlink-base-runner-"));
  const entry = path.join(root, "resolve-effective-rules.mjs");
  await symlink(fileURLToPath(new URL("./resolve-effective-rules.mjs", import.meta.url)), entry);
  const result = spawnSync(process.execPath, [entry, "--unexpected"], { encoding: "utf8" });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /RULE_BUNDLE_ARGUMENT_INVALID/);
});

test("rejects unsupported or unsafe locators before network access", () => {
  for (const locator of [
    "",
    "https://example.com/hfe/hotel-web",
    "https://sankuai.com",
    "ssh://user@git.sankuai.com/hfe/hotel-web.git",
    "ssh://git@git.sankuai.com",
    "ssh://git@git.sankuai.com:0/hfe/hotel-web.git",
    "git@git.sankuai.com:",
    "https://dev.sankuai.com/code/repo-detail/hfe/%2e%2e/file/list",
    "../hotel-web",
    "hotel\tweb",
    "hotel\nweb",
  ]) {
    assert.throws(
      () => validateRepositoryLocator(locator),
      (error) => error instanceof RuleBundleError && error.code === "RULE_BUNDLE_REPOSITORY_INVALID",
    );
  }
});

test("uses one bundle request and atomically installs L1 plus matching L2", async () => {
  const root = await createRepository();
  const calls = [];
  const body = bundleBody();
  const receipt = await syncEffectiveRuleBundle({
    token: "short-lived-user-token",
    repositoryLocator: "hfe/hotel-web?branch=master",
    repoRoot: root,
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return response(body);
    },
    execution: {
      pullId: "11111111-1111-4111-8111-111111111111",
      agent: "codex",
      source: "runner_explicit_v1",
      skillVersion: "v1-test",
    },
  });

  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.startsWith(
    "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-distribution/",
  ));
  assert.ok(calls[0].url.endsWith("/v1/effective-rule-bundles/resolve"));
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.headers["X-Rule-Auth-Source"], "nocode-agent-sso");
  assert.equal("Origin" in calls[0].init.headers, false);
  assert.equal("X-NoCode-Env" in calls[0].init.headers, false);
  const request = JSON.parse(calls[0].init.body);
  assert.deepEqual(request, {
    repository_locator: "hfe/hotel-web?branch=master",
    bundle_contract: "scope-domain-ruleset/v1",
    agents_index_contract: "rule-set-agents-index/v1",
    execution: {
      pull_id: "11111111-1111-4111-8111-111111111111",
      execution_agent: "codex",
      execution_agent_source: "runner_explicit_v1",
      skill_name: "mt-code-standards",
      skill_version: "v1-test",
    },
  });
  assert.equal(JSON.stringify(request).includes("short-lived-user-token"), false);
  assert.equal(receipt.status, "installed");
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/frontend-l1.md"), "utf8"), "# L1\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/team/fe/team-fe-l2/team-fe-l2.md"), "utf8"), "# L2\n");
  const manifest = JSON.parse(await readFile(
    path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"),
    "utf8",
  ));
  assert.equal(manifest.snapshot_id, body.snapshot.snapshot_id);
  assert.deepEqual(manifest.managed_files, [
    "company/fe/frontend-l1/frontend-l1.md",
    "team/fe/team-fe-l2/team-fe-l2.md",
  ]);
  assert.equal(JSON.stringify(manifest).includes("short-lived-user-token"), false);
  assert.equal(receipt.pull_id, "11111111-1111-4111-8111-111111111111");
  assert.equal(receipt.execution_agent, "codex");
});

test("requires an explicit known execution identity when supplied and defaults old callers safely", () => {
  const defaultExecution = normalizePullExecution();
  assert.equal(defaultExecution.agent, "unknown");
  assert.equal(defaultExecution.skillName, "mt-code-standards");
  for (const skillName of ["mt-code-standards", "mt-code-standards-setup"]) {
    assert.equal(normalizePullExecution({ skillName }).skillName, skillName);
  }
  assert.throws(
    () => normalizePullExecution({ pullId: "11111111-1111-4111-8111-111111111111", agent: "made-up", source: "runner_explicit_v1" }),
    (error) => error.code === "RULE_BUNDLE_EXECUTION_INVALID",
  );
  assert.throws(
    () => normalizePullExecution({ skillName: "unexpected-skill" }),
    (error) => error.code === "RULE_BUNDLE_EXECUTION_INVALID",
  );
});

test("sends an explicit stage and installs a verified v4 bundle with dependency context", async () => {
  const root = await createRepository();
  const body = bundleBody({ stage: "coding" });
  let request;
  const receipt = await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/hotel-web",
    repoRoot: root,
    stage: "coding",
    fetchImpl: async (_url, init) => {
      request = JSON.parse(init.body);
      return response(body);
    },
  });
  assert.equal(request.stage, "coding");
  assert.equal(receipt.stage, "coding");
  const manifest = JSON.parse(await readFile(
    path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"),
    "utf8",
  ));
  assert.equal(manifest.schema_version, "mt-effective-rule-bundle-manifest/v7");
  assert.equal(manifest.resolver_version, "effective-rule-bundle/v4");
  assert.equal(manifest.stage, "coding");
  assert.equal(manifest.dependency_hash, body.snapshot.dependency_hash);
});

test("does not reuse a snapshot across stages and removes files from the previous stage", async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  const coding = bundleBody({
    stage: "coding",
    files: [{ relative_path: "l1/java-l1-compact/compact.md", content: "# compact\n" }],
  });
  await syncEffectiveRuleBundle({ ...options, stage: "coding", fetchImpl: async () => response(coding) });
  const customPath = path.join(root, ".mdp/rules/project/custom.md");
  await mkdir(path.dirname(customPath), { recursive: true });
  await writeFile(customPath, "# custom\n", "utf8");
  const review = bundleBody({
    stage: "cr",
    files: [{ relative_path: "l1/java-l1/full.md", content: "# full\n" }],
  });
  let request;
  await syncEffectiveRuleBundle({
    ...options,
    stage: "cr",
    fetchImpl: async (_url, init) => {
      request = JSON.parse(init.body);
      return response(review);
    },
  });
  assert.equal("known_snapshot_id" in request, false);
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/compact.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/full.md"), "utf8"), "# full\n");
  assert.equal(await readFile(customPath, "utf8"), "# custom\n");
});

test("treats delivery policy changes as new staged snapshots even when files are unchanged", async () => {
  const root = await createRepository();
  const options = {
    token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root, stage: "coding",
  };
  const first = bundleBody({ stage: "coding", dependencyHash: sha256Hex("policy-a") });
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(first) });
  const second = bundleBody({ stage: "coding", dependencyHash: sha256Hex("policy-b") });
  let request;
  await syncEffectiveRuleBundle({
    ...options,
    fetchImpl: async (_url, init) => {
      request = JSON.parse(init.body);
      return response(second);
    },
  });
  assert.equal(request.known_snapshot_id, first.snapshot.snapshot_id);
  assert.notEqual(first.snapshot.snapshot_id, second.snapshot.snapshot_id);
  const manifest = JSON.parse(await readFile(
    path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"),
    "utf8",
  ));
  assert.equal(manifest.snapshot_id, second.snapshot.snapshot_id);
  assert.equal(manifest.dependency_hash, second.snapshot.dependency_hash);
});

test("rejects stage downgrade, stage mismatch and an explicit empty stage before installation", async () => {
  for (const invalidStage of ["", "review"]) {
    const root = await createRepository();
    let calls = 0;
    await assert.rejects(
      syncEffectiveRuleBundle({
        token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root,
        stage: invalidStage,
        fetchImpl: async () => { calls += 1; return response(bundleBody()); },
      }),
      (error) => error.code === "RULE_BUNDLE_STAGE_INVALID",
    );
    assert.equal(calls, 0);
  }
  const downgradeRoot = await createRepository();
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: downgradeRoot,
      stage: "coding", fetchImpl: async () => response(bundleBody({ version: 2, legacy: true })),
    }),
    (error) => error.code === "RULE_BUNDLE_LAYOUT_UNSUPPORTED",
  );
  const mismatchRoot = await createRepository();
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: mismatchRoot,
      stage: "coding", fetchImpl: async () => response(bundleBody({ stage: "cr" })),
    }),
    (error) => error.code === "RULE_BUNDLE_STAGE_MISMATCH",
  );
});

test("upgrades one registered repository to a combined dual-domain bundle without losing files", async () => {
  const root = await createRepository();
  const single = bundleBody();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(single) });
  const customPath = path.join(root, ".mdp/rules/project/custom.md");
  await mkdir(path.dirname(customPath), { recursive: true });
  await writeFile(customPath, "# custom\n", "utf8");

  const combined = bundleBody({
    refs: [
      { rule_set_id: "backend-l1", release_id: "backend-l1@1", scope_level: "L1" },
      ...releaseRefs,
      { rule_set_id: "team-java-l2", release_id: "team-java-l2@1", scope_level: "L2" },
    ],
    files: [
      { relative_path: "l1/backend-l1/common.md", content: "# Java L1\n" },
      { relative_path: "l1/frontend-l1/common.md", content: "# Frontend L1\n" },
      { relative_path: "l2/team-fe-l2/common.md", content: "# Frontend L2\n" },
      { relative_path: "l2/team-java-l2/common.md", content: "# Java L2\n" },
    ],
  });
  combined.snapshot.repository.standard_domains = ["backend", "frontend"];
  const result = await syncEffectiveRuleBundle({
    ...options,
    fetchImpl: async () => response(combined),
  });
  assert.equal(result.status, "installed");
  assert.notEqual(combined.snapshot.snapshot_id, single.snapshot.snapshot_id);
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const before = await readFile(manifestPath, "utf8");
  const manifest = JSON.parse(before);
  assert.equal(manifest.standard_domain, "frontend");
  assert.equal(manifest.managed_files.length, 4);
  assert.equal(new Set(manifest.managed_files).size, 4);
  assert.equal(manifest.managed_files.filter((file) => file.startsWith("company/")).length, 2);
  const contents = await Promise.all(manifest.managed_files.map((file) => (
    readFile(path.join(root, ".mdp/rules", file), "utf8")
  )));
  assert.deepEqual(contents.sort(), combined.files.map((file) => file.content).sort());
  assert.equal(await readFile(customPath, "utf8"), "# custom\n");
  let replayRequest;
  const replay = await syncEffectiveRuleBundle({
    ...options,
    fetchImpl: async (_url, init) => {
      replayRequest = JSON.parse(init.body);
      return response({ ...combined, status: "not_modified", files: [] });
    },
  });
  assert.equal(replayRequest.known_snapshot_id, combined.snapshot.snapshot_id);
  assert.equal(replay.status, "not_modified");
  assert.equal(await readFile(manifestPath, "utf8"), before);
});

test("replaces frontend managed rules after the same registered repository changes to backend", async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  const frontend = bundleBody();
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(frontend) });
  const customPath = path.join(root, ".mdp/rules/project/custom.md");
  await mkdir(path.dirname(customPath), { recursive: true });
  await writeFile(customPath, "# custom\n", "utf8");

  const backend = bundleBody({
    domain: "backend",
    refs: [
      { rule_set_id: "java-l1", release_id: "java-l1@current", scope_level: "L1" },
      { rule_set_id: "team-java-l2", release_id: "team-java-l2@current", scope_level: "L2" },
    ],
    files: [
      { relative_path: "l1/java-l1/java-current.md", content: "# Java L1\n" },
      { relative_path: "l2/team-java-l2/team-current.md", content: "# Java L2\n" },
    ],
  });
  const receipt = await syncEffectiveRuleBundle({
    ...options,
    fetchImpl: async () => response(backend),
  });
  assert.equal(receipt.repository.standard_domain, "backend");
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/frontend-l1.md")));
  await assert.rejects(readFile(path.join(root, ".mdp/rules/team/fe/team-fe-l2/team-fe-l2.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/java/java-l1/java-current.md"), "utf8"), "# Java L1\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/team/java/team-java-l2/team-current.md"), "utf8"), "# Java L2\n");
  assert.equal(await readFile(customPath, "utf8"), "# custom\n");

  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const installed = await readFile(manifestPath, "utf8");
  const manifest = JSON.parse(installed);
  assert.equal(manifest.standard_domain, "backend");
  assert.deepEqual(manifest.managed_files, [
    "company/java/java-l1/java-current.md",
    "team/java/team-java-l2/team-current.md",
  ]);

  let replayRequest;
  const replay = await syncEffectiveRuleBundle({
    ...options,
    fetchImpl: async (_url, init) => {
      replayRequest = JSON.parse(init.body);
      return response({ ...backend, status: "not_modified", files: [] });
    },
  });
  assert.equal(replayRequest.known_snapshot_id, backend.snapshot.snapshot_id);
  assert.equal(replay.status, "not_modified");
  assert.equal(await readFile(manifestPath, "utf8"), installed);
});

test("replaces an old dual-domain bundle with the selected backend rules only", async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  const dual = bundleBody({
    files: [
      { relative_path: "l1/frontend-l1/frontend-old.md", content: "# Frontend old\n" },
      { relative_path: "l1/java-l1/java-old.md", content: "# Java old\n" },
      { relative_path: "l2/team-fe-l2/frontend-team-old.md", content: "# Frontend team old\n" },
      { relative_path: "l2/team-java-l2/java-team-old.md", content: "# Java team old\n" },
    ],
    refs: [
      releaseRefs[0],
      { rule_set_id: "java-l1", release_id: "java-l1@old", scope_level: "L1" },
      releaseRefs[1],
      { rule_set_id: "team-java-l2", release_id: "team-java-l2@old", scope_level: "L2" },
    ],
  });
  dual.snapshot.repository.standard_domains = ["backend", "frontend"];
  const legacy = bundleBody({ version: 2, legacy: true, files: dual.files, refs: dual.snapshot.release_refs });
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  await seedLegacyManifest(root, legacy, 3);


  const backend = bundleBody({
    domain: "backend",
    files: [{ relative_path: "l1/java-l1/java-current.md", content: "# Java current\n" }],
    refs: [{ rule_set_id: "java-l1", release_id: "java-l1@current", scope_level: "L1" }],
  });
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(backend) });
  for (const removed of [
    "company/fe/frontend-l1/frontend-old.md",
    "company/java/java-l1/java-old.md",
    "team/fe/team-fe-l2/frontend-team-old.md",
    "team/java/team-java-l2/java-team-old.md",
  ]) {
    await assert.rejects(readFile(path.join(root, ".mdp/rules", removed)));
  }
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/java/java-l1/java-current.md"), "utf8"), "# Java current\n");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  assert.equal(manifest.schema_version, "mt-effective-rule-bundle-manifest/v7");
  assert.equal(manifest.standard_domain, "backend");
  assert.deepEqual(manifest.managed_files, ["company/java/java-l1/java-current.md"]);
});

test("changes legacy v1 and v2 domain-directory manifests to backend without leaving old managed files", async () => {
  for (const version of [1, 2]) {
    const root = await createRepository();
    const frontend = bundleBody({
      version, legacy: true,
      files: [{ relative_path: "l1/frontend-l1/old.md", content: `# Frontend v${version}\n` }],
      refs: [{ rule_set_id: "frontend-l1", release_id: `frontend-l1@v${version}`, scope_level: "L1" }],
    });
    const oldFile = frontend.files[0];
    const managedPath = `frontend/${oldFile.relative_path}`;
    const oldManifest = {
      schema_version: `mt-effective-rule-bundle-manifest/v${version}`,
      ...(version === 2 ? { resolver_version: "effective-rule-bundle/v2" } : {}),
      snapshot_id: frontend.snapshot.snapshot_id,
      manifest_hash: frontend.snapshot.manifest_hash,
      repository,
      standard_domain: "frontend",
      release_refs: frontend.snapshot.release_refs,
      total_bytes: frontend.snapshot.total_bytes,
      managed_files: [managedPath],
      managed_file_hashes: { [managedPath]: oldFile.sha256 },
      managed_file_sizes: { [managedPath]: oldFile.byte_size },
      installed_at: "2026-09-08T00:00:00.000Z",
    };
    const oldPath = path.join(root, ".mdp/rules", managedPath);
    await mkdir(path.dirname(oldPath), { recursive: true });
    await writeFile(oldPath, oldFile.content, "utf8");
    await writeFile(
      path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"),
      `${JSON.stringify(oldManifest, null, 2)}\n`,
      "utf8",
    );

    const backend = bundleBody({
        domain: "backend",
      files: [{ relative_path: "l1/java-l1/current.md", content: "# Java current\n" }],
      refs: [{ rule_set_id: "java-l1", release_id: "java-l1@current", scope_level: "L1" }],
    });
    let request;
    await syncEffectiveRuleBundle({
      token: "token",
      repositoryLocator: "hfe/hotel-web",
      repoRoot: root,
      fetchImpl: async (_url, init) => {
        request = JSON.parse(init.body);
        return response(backend);
      },
    });
    assert.equal("known_snapshot_id" in request, false);
    await assert.rejects(readFile(oldPath));
    assert.equal(await readFile(path.join(root, ".mdp/rules/company/java/java-l1/current.md"), "utf8"), "# Java current\n");
  }
});

test("keeps the frontend installation unchanged when a backend replacement is invalid or collides", async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(bundleBody()) });
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const frontendPath = path.join(root, ".mdp/rules/company/fe/frontend-l1/frontend-l1.md");
  const originalManifest = await readFile(manifestPath, "utf8");
  const originalFrontend = await readFile(frontendPath, "utf8");

  const invalid = bundleBody({
    domain: "backend",
    files: [{ relative_path: "l1/java-l1/java.md", content: "# Java\n" }],
    refs: [{ rule_set_id: "java-l1", release_id: "java-l1@current", scope_level: "L1" }],
  });
  invalid.files[0].content = "tampered\n";
  await assert.rejects(
    syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(invalid) }),
    (error) => error.code === "RULE_BUNDLE_FILE_HASH_MISMATCH",
  );
  assert.equal(await readFile(manifestPath, "utf8"), originalManifest);
  assert.equal(await readFile(frontendPath, "utf8"), originalFrontend);

  const collisionPath = path.join(root, ".mdp/rules/company/java/java-l1/java.md");
  await mkdir(path.dirname(collisionPath), { recursive: true });
  await writeFile(collisionPath, "# user owned\n", "utf8");
  const valid = bundleBody({
    domain: "backend",
    files: [{ relative_path: "l1/java-l1/java.md", content: "# Java\n" }],
    refs: [{ rule_set_id: "java-l1", release_id: "java-l1@current", scope_level: "L1" }],
  });
  await assert.rejects(
    syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(valid) }),
    (error) => error.code === "RULE_BUNDLE_LOCAL_COLLISION",
  );
  assert.equal(await readFile(manifestPath, "utf8"), originalManifest);
  assert.equal(await readFile(frontendPath, "utf8"), originalFrontend);
  assert.equal(await readFile(collisionPath, "utf8"), "# user owned\n");
});

test("automatically sends the exact git origin when no locator is supplied", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "mt-rule-bundle-git-test-"));
  execFileSync("git", ["init", "--quiet"], { cwd: root });
  const origin = "git@git.sankuai.com:hfe/hotel-web.git?branch=master";
  execFileSync("git", ["remote", "add", "origin", origin], { cwd: root });
  let request;
  await syncEffectiveRuleBundle({
    token: "token",
    repoRoot: root,
    fetchImpl: async (_url, init) => {
      request = JSON.parse(init.body);
      return response(bundleBody());
    },
  });
  assert.equal(request.repository_locator, origin);
});

test("runs without Git when repository is explicit and writes to the current directory", async () => {
  const currentDirectory = await mkdtemp(path.join(os.tmpdir(), "setup-no-git-"));
  let requested;
  const receipt = await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hotel-web",
    cwd: currentDirectory,
    fetchImpl: async (_url, init) => {
      requested = JSON.parse(init.body);
      return response(bundleBody());
    },
  });
  assert.equal(requested.repository_locator, "hotel-web");
  assert.equal(receipt.repository.canonical_key, "hfe/hotel-web");
  assert.equal(await readFile(path.join(currentDirectory, ".mdp/rules/company/fe/frontend-l1/frontend-l1.md"), "utf8"), "# L1\n");
});

test("uses output-dir before repo-root while repo-root remains the Git discovery source", async () => {
  const repositoryRoot = await createTrackedRepository({ "README.md": "test\n" });
  execFileSync("git", ["remote", "add", "origin", "git@git.sankuai.com:hfe/hotel-web.git"], { cwd: repositoryRoot });
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), "setup-output-"));
  await syncEffectiveRuleBundle({
    token: "token",
    repoRoot: repositoryRoot,
    outputDir: outputRoot,
    fetchImpl: async () => response(bundleBody()),
  });
  await access(path.join(outputRoot, ".mdp/rules/.mt-effective-rule-bundle.json"));
  await assert.rejects(access(path.join(repositoryRoot, ".mdp/rules/.mt-effective-rule-bundle.json")));
});

test("resolves relative repo-root and output-dir from the supplied cwd", async () => {
  const workingDirectory = await mkdtemp(path.join(os.tmpdir(), "setup-relative-base-"));
  const repositoryRoot = path.join(workingDirectory, "repository");
  await mkdir(repositoryRoot);
  execFileSync("git", ["init", "-q"], { cwd: repositoryRoot });
  await writeFile(path.join(repositoryRoot, "README.md"), "test\n", "utf8");
  execFileSync("git", ["add", "README.md"], { cwd: repositoryRoot });
  execFileSync("git", ["remote", "add", "origin", "git@git.sankuai.com:hfe/hotel-web.git"], { cwd: repositoryRoot });
  await syncEffectiveRuleBundle({
    token: "token",
    cwd: workingDirectory,
    repoRoot: "repository",
    outputDir: "generated rules",
    fetchImpl: async () => response(bundleBody()),
  });
  await access(path.join(workingDirectory, "generated rules/.mdp/rules/.mt-effective-rule-bundle.json"));
  await assert.rejects(access(path.join(repositoryRoot, ".mdp/rules/.mt-effective-rule-bundle.json")));
});

test("does not create the managed directory when an explicit repository is not registered", async () => {
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), "setup-not-found-"));
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token",
      repositoryLocator: "missing-repository",
      cwd: outputRoot,
      fetchImpl: async () => response({ error: { code: "repository_not_registered" } }, 404),
    }),
    (error) => error.code === "repository_not_registered",
  );
  await assert.rejects(access(path.join(outputRoot, ".mdp")));
});

test("keeps a verified snapshot incremental for a repository name locator", async () => {
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), "setup-name-incremental-"));
  const ready = bundleBody();
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hotel-web", cwd: outputRoot,
    fetchImpl: async () => response(ready),
  });
  let request;
  const receipt = await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hotel-web", cwd: outputRoot,
    fetchImpl: async (_url, init) => {
      request = JSON.parse(init.body);
      return response(bundleBody({ status: "not_modified" }));
    },
  });
  assert.equal(request.known_snapshot_id, ready.snapshot.snapshot_id);
  assert.equal(receipt.status, "not_modified");
});

test("refuses to replace another repository in the same output directory", async () => {
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), "setup-repository-conflict-"));
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hotel-web", cwd: outputRoot,
    fetchImpl: async () => response(bundleBody()),
  });
  const original = await readFile(path.join(outputRoot, ".mdp/rules/company/fe/frontend-l1/frontend-l1.md"), "utf8");
  const otherRepository = {
    repository_id: "repo:other-web",
    canonical_key: "hfe/other-web",
    standard_domain: "frontend",
  };
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token", repositoryLocator: "other-web", cwd: outputRoot,
      fetchImpl: async () => response(bundleBody({ repositoryIdentity: otherRepository })),
    }),
    (error) => error.code === "RULE_BUNDLE_REPOSITORY_CONFLICT",
  );
  assert.equal(await readFile(path.join(outputRoot, ".mdp/rules/company/fe/frontend-l1/frontend-l1.md"), "utf8"), original);
});

test("preserves unrelated local files outside the managed company and team paths", async () => {
  const root = await createRepository();
  const customPath = path.join(root, ".mdp/rules/project/custom.md");
  await mkdir(path.dirname(customPath), { recursive: true });
  await writeFile(customPath, "# local\n", "utf8");
  await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/hotel-web",
    repoRoot: root,
    fetchImpl: async () => response(bundleBody()),
  });
  assert.equal(await readFile(customPath, "utf8"), "# local\n");
});

test("sends a verified known snapshot and does not rewrite a not-modified bundle", async () => {
  const root = await createRepository();
  const ready = bundleBody();
  await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/hotel-web",
    repoRoot: root,
    fetchImpl: async () => response(ready),
  });
  const before = await readFile(path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"), "utf8");
  let request;
  const receipt = await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/hotel-web",
    repoRoot: root,
    fetchImpl: async (_url, init) => {
      request = JSON.parse(init.body);
      return response({ ...ready, status: "not_modified", files: [] });
    },
  });
  const after = await readFile(path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"), "utf8");
  assert.equal(request.known_snapshot_id, ready.snapshot.snapshot_id);
  assert.equal(receipt.status, "not_modified");
  assert.equal(after, before);
});

test("migrates a verified legacy domain tree to the named domain layout", async () => {
  const root = await createRepository();
  const ready = bundleBody({
    files: [
      { relative_path: "l1/frontend-l1/旧目录/基础规范.md", content: "# L1\n" },
      { relative_path: "l2/team-fe-l2/旧目录/团队规范.md", content: "# L2\n" },
    ],
  });
  const legacy = bundleBody({ version: 2, legacy: true, files: ready.files });
  const oldFiles = legacy.files;
  const legacyManaged = oldFiles.map((file) => `frontend/${file.relative_path}`);
  const oldManifest = {
    schema_version: "mt-effective-rule-bundle-manifest/v2",
    resolver_version: "effective-rule-bundle/v2",
    snapshot_id: legacy.snapshot.snapshot_id,
    manifest_hash: legacy.snapshot.manifest_hash,
    repository,
    standard_domain: "frontend",
    release_refs: legacy.snapshot.release_refs,
    total_bytes: legacy.snapshot.total_bytes,
    managed_files: legacyManaged,
    managed_file_hashes: Object.fromEntries(oldFiles.map((file) => [`frontend/${file.relative_path}`, file.sha256])),
    managed_file_sizes: Object.fromEntries(oldFiles.map((file) => [`frontend/${file.relative_path}`, file.byte_size])),
    installed_at: "2026-09-08T00:00:00.000Z",
  };
  for (const file of oldFiles) {
    const output = path.join(root, ".mdp/rules/frontend", file.relative_path);
    await mkdir(path.dirname(output), { recursive: true });
    await writeFile(output, file.content, "utf8");
  }
  const userFile = path.join(root, ".mdp/rules/frontend/个人补充.md");
  await writeFile(userFile, "keep\n", "utf8");
  await writeFile(
    path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"),
    `${JSON.stringify(oldManifest, null, 2)}\n`,
    "utf8",
  );
  let request;
  await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/hotel-web",
    repoRoot: root,
    fetchImpl: async (_url, init) => {
      request = JSON.parse(init.body);
      return response(ready);
    },
  });
  assert.equal("known_snapshot_id" in request, false);
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/基础规范.md"), "utf8"), "# L1\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/team/fe/team-fe-l2/团队规范.md"), "utf8"), "# L2\n");
  assert.equal(await readFile(userFile, "utf8"), "keep\n");
  await assert.rejects(readFile(path.join(root, ".mdp/rules/frontend/l1/frontend-l1/旧目录/基础规范.md")));
});

test("keeps one company file per L1 source inside its named rule set when basenames collide", async () => {
  const root = await createRepository();
  const ready = bundleBody({
    files: [
      { relative_path: "l1/frontend-l1/目录甲/README.md", content: "# 甲\n" },
      { relative_path: "l1/frontend-l1/目录乙/README.md", content: "# 乙\n" },
    ],
    refs: [{ rule_set_id: "frontend-l1", release_id: "frontend-l1@test", scope_level: "L1" }],
  });
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root,
    fetchImpl: async () => response(ready),
  });
  const manifest = JSON.parse(await readFile(path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"), "utf8"));
  assert.equal(manifest.managed_files.length, 2);
  assert.equal(manifest.managed_files.filter((file) => file.startsWith("company/")).length, 2);
  assert.equal(new Set(manifest.managed_files).size, 2);
  const baseContent = await readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/README.md"), "utf8");
  const suffixed = manifest.managed_files.find((file) => file !== "company/fe/frontend-l1/README.md");
  assert.match(suffixed, /^company\/fe\/frontend-l1\/README--[a-f0-9]{16}\.md$/);
  const suffixedContent = await readFile(path.join(root, ".mdp/rules", suffixed), "utf8");
  assert.deepEqual(new Set([baseContent, suffixedContent]), new Set(["# 甲\n", "# 乙\n"]));
});

test("preserves the installed bundle when a local managed file was changed", async () => {
  const root = await createRepository();
  const ready = bundleBody();
  await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/hotel-web",
    repoRoot: root,
    fetchImpl: async () => response(ready),
  });
  const managedPath = path.join(root, ".mdp/rules/company/fe/frontend-l1/frontend-l1.md");
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const manifestBefore = await readFile(manifestPath, "utf8");
  await writeFile(managedPath, "changed\n", "utf8");
  let requested = false;
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token",
      repositoryLocator: "hfe/hotel-web",
      repoRoot: root,
      fetchImpl: async () => {
        requested = true;
        return response(ready);
      },
    }),
    (error) => error.code === "RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED",
  );
  assert.equal(requested, false);
  assert.equal(await readFile(managedPath, "utf8"), "changed\n");
  assert.equal(await readFile(manifestPath, "utf8"), manifestBefore);
});

test("moves a canonical L2 release to its rule-set-name directory and replays without writes", async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  const legacy = bundleBody({
    files: [{ relative_path: "l1/frontend-l1/base.md", content: "# L1\n" }, {
      relative_path: "l2/legacy-team-l2/STYLE-01-old.md",
      content: "# Legacy L2\n",
    }],
  });
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(legacy) });

  const canonicalRefs = [releaseRefs[0], {
    rule_set_id: "rs-11111111-1111-4111-8111-111111111111",
    release_id: "rs-11111111-1111-4111-8111-111111111111@1",
    scope_level: "L2",
    rule_set_name: "billing-settlement-frontend",
    stored_rule_set_id: "legacy-team-l2",
    stored_release_id: "legacy-team-l2@1",
    version_policy: "auto_follow_latest",
    migration_id: "11111111-1111-4111-8111-111111111111",
  }];
  const canonical = bundleBody({
    refs: canonicalRefs,
    files: [{ relative_path: "l1/frontend-l1/base.md", content: "# L1\n" }, {
      relative_path: "l2/billing-settlement-frontend/STYLE-01-promise.md",
      content: "# Canonical L2\n",
    }],
  });
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(canonical) });

  const oldPath = path.join(root, ".mdp/rules/team/fe/legacy-team-l2/STYLE-01-old.md");
  const newPath = path.join(root, ".mdp/rules/team/fe/billing-settlement-frontend/STYLE-01-promise.md");
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  await assert.rejects(readFile(oldPath));
  assert.equal(await readFile(newPath, "utf8"), "# Canonical L2\n");
  const manifestBefore = await readFile(manifestPath, "utf8");
  assert.equal(JSON.parse(manifestBefore).release_refs[1].stored_release_id, "legacy-team-l2@1");
  const receipt = await syncEffectiveRuleBundle({
    ...options,
    fetchImpl: async (_url, init) => {
      const request = JSON.parse(init.body);
      assert.equal(request.known_snapshot_id, canonical.snapshot.snapshot_id);
      return response({ ...canonical, status: "not_modified", files: [] });
    },
  });
  assert.equal(receipt.status, "not_modified");
  assert.equal(await readFile(manifestPath, "utf8"), manifestBefore);
});

test("rejects a canonical L2 rule-set name that does not start with a letter", async () => {
  const root = await createRepository();
  const invalidRefs = [releaseRefs[0], {
    rule_set_id: "rs-11111111-1111-4111-8111-111111111111",
    release_id: "rs-11111111-1111-4111-8111-111111111111@1",
    scope_level: "L2",
    rule_set_name: "2billing-settlement",
  }];
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token",
      repositoryLocator: "hfe/hotel-web",
      repoRoot: root,
      fetchImpl: async () => response(bundleBody({ refs: invalidRefs })),
    }),
    (error) => error.code === "RULE_BUNDLE_RELEASE_REFS_INVALID",
  );
});

test("binds every canonical L2 file path to exactly one release reference", async () => {
  const canonicalRef = {
    rule_set_id: "rs-11111111-1111-4111-8111-111111111111",
    release_id: "rs-11111111-1111-4111-8111-111111111111@1",
    scope_level: "L2",
    rule_set_name: "billing-settlement-frontend",
  };
  const l1File = { relative_path: "l1/frontend-l1/base.md", content: "# L1\n" };
  for (const [files, refs, expectedCode] of [
    [
      [l1File, { relative_path: "l2/unrelated-directory/STYLE-01-safe.md", content: "# Wrong\n" }],
      [releaseRefs[0], canonicalRef],
      "RULE_BUNDLE_FILE_PATH_INVALID",
    ],
    [
      [l1File, { relative_path: "l2/team-fe-l2/legacy.md", content: "# Legacy\n" }],
      [releaseRefs[0], releaseRefs[1], canonicalRef],
      "RULE_BUNDLE_FILES_MISSING",
    ],
    [
      [l1File, { relative_path: "l2/team-fe-l2/shared.md", content: "# Shared\n" }],
      [releaseRefs[0], releaseRefs[1], { ...canonicalRef, rule_set_name: "team-fe-l2" }],
      "RULE_BUNDLE_RELEASE_REFS_INVALID",
    ],
  ]) {
    const root = await createRepository();
    const sortedRefs = [...refs].sort((left, right) => (
      left.rule_set_id.localeCompare(right.rule_set_id, "en")
      || left.release_id.localeCompare(right.release_id, "en")
      || left.scope_level.localeCompare(right.scope_level, "en")
    ));
    await assert.rejects(
      syncEffectiveRuleBundle({
        token: "token",
        repositoryLocator: "hfe/hotel-web",
        repoRoot: root,
        fetchImpl: async () => response(bundleBody({ files, refs: sortedRefs })),
      }),
      (error) => error.code === expectedCode,
    );
  }
});

test("installs mixed canonical and legacy L2 paths without truncating an 80-character name", async () => {
  const root = await createRepository();
  const maxLengthName = `a${"b".repeat(79)}`;
  const canonicalRef = {
    rule_set_id: "rs-11111111-1111-4111-8111-111111111111",
    release_id: "rs-11111111-1111-4111-8111-111111111111@1",
    scope_level: "L2",
    rule_set_name: maxLengthName,
  };
  const ready = bundleBody({
    refs: [releaseRefs[0], canonicalRef, releaseRefs[1]],
    files: [
      { relative_path: "l1/frontend-l1/base.md", content: "# L1\n" },
      { relative_path: "l2/team-fe-l2/legacy.md", content: "# Legacy\n" },
      { relative_path: `l2/${maxLengthName}/STYLE-01-safe.md`, content: "# Canonical\n" },
    ],
  });
  await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/hotel-web",
    repoRoot: root,
    fetchImpl: async () => response(ready),
  });
  assert.equal(
    await readFile(path.join(root, ".mdp/rules/team/fe", maxLengthName, "STYLE-01-safe.md"), "utf8"),
    "# Canonical\n",
  );
  assert.equal(
    await readFile(path.join(root, ".mdp/rules/team/fe/team-fe-l2/legacy.md"), "utf8"),
    "# Legacy\n",
  );
});

test("does not trust a self-consistent local manifest with a mismatched canonical L2 source path", async () => {
  const root = await createRepository();
  const canonicalRef = {
    rule_set_id: "rs-11111111-1111-4111-8111-111111111111",
    release_id: "rs-11111111-1111-4111-8111-111111111111@1",
    scope_level: "L2",
    rule_set_name: "billing-settlement-frontend",
  };
  const ready = bundleBody({
    refs: [releaseRefs[0], canonicalRef],
    files: [
      { relative_path: "l1/frontend-l1/base.md", content: "# L1\n" },
      { relative_path: "l2/billing-settlement-frontend/STYLE-01-safe.md", content: "# Canonical\n" },
    ],
  });
  await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/hotel-web",
    repoRoot: root,
    fetchImpl: async () => response(ready),
  });
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  const canonicalManagedPath = manifest.managed_files.find((managedPath) =>
    managedPath.startsWith("team/fe/billing-settlement-frontend/")
  );
  manifest.managed_file_sources[canonicalManagedPath] = "l2/unrelated-directory/STYLE-01-safe.md";
  const projection = manifest.managed_files.map((managedPath) => ({
    relative_path: manifest.managed_file_sources[managedPath],
    sha256: manifest.managed_file_hashes[managedPath],
    byte_size: manifest.managed_file_sizes[managedPath],
  })).sort((left, right) => left.relative_path < right.relative_path ? -1 : left.relative_path > right.relative_path ? 1 : 0);
  manifest.manifest_hash = sha256Hex(canonicalJson(projection));
  manifest.snapshot_id = sha256Hex(canonicalJson({
    resolver_version: manifest.resolver_version,
    repository_id: manifest.repository.repository_id,
    canonical_key: manifest.repository.canonical_key,
    standard_domain: manifest.repository.standard_domain,
    manifest_hash: manifest.manifest_hash,
    release_refs: manifest.release_refs,
  }));
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

  let requested = false;
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token",
      repositoryLocator: "hfe/hotel-web",
      repoRoot: root,
      fetchImpl: async () => {
        requested = true;
        return response({ ...ready, status: "not_modified", files: [] });
      },
    }),
    (error) => error.code === "RULE_BUNDLE_LOCAL_MANIFEST_INVALID",
  );
  assert.equal(requested, false);
});

test("rejects portable reserved canonical L2 names", async () => {
  for (const ruleSetName of ["con", "prn", "aux", "nul", "com1", "com9", "lpt1", "lpt9"]) {
    const root = await createRepository();
    const refs = [releaseRefs[0], {
      rule_set_id: "rs-11111111-1111-4111-8111-111111111111",
      release_id: "rs-11111111-1111-4111-8111-111111111111@1",
      scope_level: "L2",
      rule_set_name: ruleSetName,
    }];
    await assert.rejects(
      syncEffectiveRuleBundle({
        token: "token",
        repositoryLocator: "hfe/hotel-web",
        repoRoot: root,
        fetchImpl: async () => response(bundleBody({ refs })),
      }),
      (error) => error.code === "RULE_BUNDLE_RELEASE_REFS_INVALID",
    );
  }
});

test("keeps the previous bundle when staging cannot be created", async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  const initial = bundleBody();
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(initial) });
  const rulesRoot = path.join(root, ".mdp/rules");
  const manifestPath = path.join(rulesRoot, ".mt-effective-rule-bundle.json");
  const managedPath = path.join(rulesRoot, "company/fe/frontend-l1/frontend-l1.md");
  const manifestBefore = await readFile(manifestPath, "utf8");
  const managedBefore = await readFile(managedPath, "utf8");
  const next = bundleBody({
    files: [{ relative_path: "l1/frontend-l1/next.md", content: "# Next L1\n" }],
    refs: [{ rule_set_id: "frontend-l1", release_id: "frontend-l1@next", scope_level: "L1" }],
  });
  const originalMkdtemp = fs.promises.mkdtemp;
  let stagingMkdtempCalls = 0;
  fs.promises.mkdtemp = async (prefix, ...args) => {
    if (path.basename(prefix) === ".mt-bundle-stage-") {
      stagingMkdtempCalls += 1;
      const error = new Error("injected staging directory creation failure");
      error.code = "EACCES";
      throw error;
    }
    return originalMkdtemp(prefix, ...args);
  };
  syncBuiltinESMExports();
  try {
    await assert.rejects(syncEffectiveRuleBundle({
      ...options,
      fetchImpl: async () => response(next),
    }), (error) => (
      error?.code === "EACCES"
      && error.message === "injected staging directory creation failure"
    ));
    assert.equal(stagingMkdtempCalls, 1);
  } finally {
    fs.promises.mkdtemp = originalMkdtemp;
    syncBuiltinESMExports();
  }
  assert.equal(await readFile(manifestPath, "utf8"), manifestBefore);
  assert.equal(await readFile(managedPath, "utf8"), managedBefore);
  await assert.rejects(readFile(path.join(rulesRoot, "company/fe/frontend-l1/next.md")));
});

test("fails closed on content hash mismatch without creating managed files", async () => {
  const root = await createRepository();
  const invalid = bundleBody();
  invalid.files[0].content = "tampered\n";
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token",
      repositoryLocator: "hfe/hotel-web",
      repoRoot: root,
      fetchImpl: async () => response(invalid),
    }),
    (error) => error.code === "RULE_BUNDLE_FILE_HASH_MISMATCH",
  );
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/frontend-l1.md")));
});

test("rejects traversal paths and unmanaged target collisions", async () => {
  const root = await createRepository();
  const traversal = bundleBody({ files: [{ relative_path: "../outside.md", content: "bad" }] });
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token",
      repositoryLocator: "hfe/hotel-web",
      repoRoot: root,
      fetchImpl: async () => response(traversal),
    }),
    (error) => error.code === "RULE_BUNDLE_FILE_PATH_INVALID",
  );

  const collision = path.join(root, ".mdp/rules/company/fe/frontend-l1/frontend-l1.md");
  await mkdir(path.dirname(collision), { recursive: true });
  await writeFile(collision, "user-owned\n", "utf8");
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token",
      repositoryLocator: "hfe/hotel-web",
      repoRoot: root,
      fetchImpl: async () => response(bundleBody()),
    }),
    (error) => error.code === "RULE_BUNDLE_LOCAL_COLLISION",
  );
  assert.equal(await readFile(collision, "utf8"), "user-owned\n");
});

test("reports actionable not-registered and ambiguous repository errors", async () => {
  const root = await createRepository();
  for (const [code, expected] of [
    ["repository_locator_ambiguous", "namespace/repository"],
    ["repository_user_login_unverified", "https://quality-gate.nocode.sankuai.com/"],
  ]) {
    await assert.rejects(
      syncEffectiveRuleBundle({
        token: "token",
        repositoryLocator: "hotel-web",
        repoRoot: root,
        fetchImpl: async () => response({ error: { code, message: "failed" } }, 400),
      }),
      (error) => error.code === code && error.message.includes(expected),
    );
  }
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token",
      repositoryLocator: "hotel-web",
      repoRoot: root,
      fetchImpl: async () => response({ error: { code: "repository_not_registered" } }, 404),
    }),
    (error) => error.code === "repository_not_registered"
      && error.message.includes("没有找到已登记的仓库"),
  );
});

test("bootstraps published frontend L1 only after the server proves an exact repository is unregistered", async () => {
  const root = await createTrackedRepository({ "src/App.tsx": "export default null;\n" });
  const calls = [];
  const bootstrap = bootstrapBody();
  const receipt = await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/new-web",
    repoRoot: root,
    bootstrap: true, mis: "aicr-agent",
    fetchImpl: async (url, init) => {
      assert.equal(init.headers.Authorization, undefined);
      calls.push({ url, body: JSON.parse(init.body) });
      if (url.endsWith("/v1/effective-rule-bundles/resolve")) {
        return response({ error: { code: "repository_not_registered" } }, 404);
      }
      return response(bootstrap);
    },
  });
  assert.deepEqual(calls.map((call) => call.url.split("/").slice(-3).join("/")), [
    "public/l1-rule-bundles/bootstrap",
  ]);
  assert.deepEqual(calls[0].body, {
    repository_locator: "hfe/new-web",
    bundle_contract: "scope-domain-ruleset/v1",
    agents_index_contract: "rule-set-agents-index/v1",
    standard_domain: "frontend",
    mis: "aicr-agent",
    execution: calls[0].body.execution,
  });
  assert.equal(calls[0].body.execution.pull_id, receipt.pull_id);
  assert.equal(receipt.actor_source, "self_reported");
  assert.equal(receipt.declared_actor, "aicr-agent");
  assert.equal(receipt.schema_version, "mt-l1-bootstrap-install/v1");
  assert.equal(receipt.mode, "l1_bootstrap");
  assert.equal(receipt.domain_source, "git_tracked_evidence");
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/async.md"), "utf8"), "# L1\n");
  const manifest = JSON.parse(await readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json"), "utf8"));
  assert.equal(manifest.schema_version, "mt-l1-bootstrap-manifest/v4");
  await assert.rejects(readFile(path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json")));
  let replayRequest;
  const replay = await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/new-web",
    repoRoot: root,
    bootstrap: true, mis: "aicr-agent",
    fetchImpl: async (url, init) => {
      if (url.endsWith("/v1/effective-rule-bundles/resolve")) {
        return response({ error: { code: "repository_not_registered" } }, 404);
      }
      replayRequest = JSON.parse(init.body);
      return response(bootstrapBody({ status: "not_modified" }));
    },
  });
  assert.equal(replay.status, "not_modified");
  assert.equal(replayRequest.known_snapshot_id, manifest.snapshot_id);
});

test("forwards stage to bootstrap and requires a matching v3 bootstrap response", async () => {
  const root = await createTrackedRepository({ "pom.xml": "<project />\n", "src/App.java": "class App {}\n" });
  const requests = [];
  const body = bootstrapBody({ domain: "backend", stage: "design" });
  const receipt = await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/new-java",
    repoRoot: root,
    bootstrap: true, mis: "aicr-agent",
    stage: "design",
    fetchImpl: async (url, init) => {
      requests.push(JSON.parse(init.body));
      return url.endsWith("/v1/effective-rule-bundles/resolve")
        ? response({ error: { code: "repository_not_registered" } }, 404)
        : response(body);
    },
  });
  assert.equal(requests[0].stage, "design");
  assert.equal(requests.length, 1);
  assert.equal(receipt.stage, "design");
  const manifest = JSON.parse(await readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json"), "utf8"));
  assert.equal(manifest.schema_version, "mt-l1-bootstrap-manifest/v4");
  assert.equal(manifest.bundle_schema, "l1-bootstrap-bundle/v3");
  assert.equal(manifest.stage, "design");
  assert.equal(manifest.dependency_hash, body.snapshot.dependency_hash);
});

test("does not bootstrap a registered, hidden or unavailable repository", async () => {
  const root = await createTrackedRepository({ "src/App.jsx": "export default null;\n" });
  let calls = 0;
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token",
      repositoryLocator: "hfe/hidden-web",
      repoRoot: root,
      bootstrap: true, mis: "aicr-agent",
      fetchImpl: async (url) => {
        calls += 1;
        return url.endsWith("/v1/effective-rule-bundles/resolve")
          ? response({ error: { code: "repository_not_registered" } }, 404)
          : response({ error: { code: "repository_registered_or_unavailable" } }, 409);
      },
    }),
    (error) => error.code === "repository_registered_or_unavailable"
      && error.message.includes("禁止使用 L1 bootstrap"),
  );
  assert.equal(calls, 1);
  await assert.rejects(readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json")));
});

test("a formal effective bundle atomically replaces the isolated bootstrap manifest", async () => {
  const root = await createTrackedRepository({ "src/App.tsx": "export default null;\n" });
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hfe/new-web", repoRoot: root, bootstrap: true, mis: "aicr-agent",
    fetchImpl: async (url) => url.endsWith("/v1/effective-rule-bundles/resolve")
      ? response({ error: { code: "repository_not_registered" } }, 404)
      : response(bootstrapBody()),
  });
  const formal = bundleBody({ files: [{
    relative_path: "l1/frontend-l1/current.md", content: "# Current\n",
  }], refs: [{ rule_set_id: "frontend-l1", release_id: "frontend-l1@current", scope_level: "L1" }] });
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hfe/new-web", repoRoot: root,
    fetchImpl: async () => response(formal),
  });
  await assert.rejects(readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json")));
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/async.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/current.md"), "utf8"), "# Current\n");
  assert.equal(JSON.parse(await readFile(
    path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"), "utf8",
  )).schema_version, "mt-effective-rule-bundle-manifest/v7");
});

test("a dual-domain formal bundle replaces a backend bootstrap even when its primary domain is frontend", async () => {
  const root = await createTrackedRepository({
    "pom.xml": "<project/>\n",
    "src/main/java/Test.java": "class Test {}\n",
  });
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hfe/new-mixed", repoRoot: root, bootstrap: true, mis: "aicr-agent",
    fetchImpl: async (url) => url.endsWith("/v1/effective-rule-bundles/resolve")
      ? response({ error: { code: "repository_not_registered" } }, 404)
      : response(bootstrapBody({
        domain: "backend",
        files: [{ relative_path: "l1/java-l1/bootstrap-java.md", content: "# Bootstrap Java\n" }],
      })),
  });
  const formal = bundleBody({
    domain: "frontend",
    files: [
      { relative_path: "l1/frontend-l1/frontend-current.md", content: "# Frontend\n" },
      { relative_path: "l1/java-l1/java-current.md", content: "# Java\n" },
    ],
    refs: [
      { rule_set_id: "frontend-l1", release_id: "frontend-l1@current", scope_level: "L1" },
      { rule_set_id: "java-l1", release_id: "java-l1@current", scope_level: "L1" },
    ],
  });
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hfe/new-mixed", repoRoot: root,
    fetchImpl: async () => response(formal),
  });
  await assert.rejects(readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json")));
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/java/backend-l1/bootstrap-java.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/frontend-current.md"), "utf8"), "# Frontend\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/java/java-l1/java-current.md"), "utf8"), "# Java\n");
  const manifest = JSON.parse(await readFile(
    path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"), "utf8",
  ));
  assert.equal(manifest.standard_domain, "frontend");
  assert.equal(manifest.release_refs.length, 2);
});

test("mixed and unknown evidence require user confirmation while --domain is explicit", async () => {
  const mixed = await createTrackedRepository({
    "src/App.tsx": "export default null;\n",
    "pom.xml": "<project/>\n",
    "src/main/java/Test.java": "class Test {}\n",
  });
  const notRegistered = async (url) => url.endsWith("/v1/effective-rule-bundles/resolve")
    ? response({ error: { code: "repository_not_registered" } }, 404)
    : response(bootstrapBody({ domain: "backend", files: [{
      relative_path: "l1/backend-l1/java.md", content: "# Java\n",
    }] }));
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token", repositoryLocator: "team/mixed", repoRoot: mixed, bootstrap: true, mis: "aicr-agent", fetchImpl: notRegistered,
    }),
    (error) => error.code === "RULE_BUNDLE_DOMAIN_CONFIRMATION_REQUIRED"
      && error.message.includes('"classification"') === false
      && error.message.includes("src/App.tsx"),
  );
  const receipt = await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "team/mixed", repoRoot: mixed,
    domain: "backend", bootstrap: true, mis: "aicr-agent", fetchImpl: notRegistered,
  });
  assert.equal(receipt.standard_domain, "backend");
  assert.equal(receipt.domain_source, "user_explicit");
});

test("fails before network access without an official user token", async () => {
  const root = await createRepository();
  await assert.rejects(
    syncEffectiveRuleBundle({ token: "", repositoryLocator: "hfe/hotel-web", repoRoot: root }),
    (error) => error.code === "RULE_BUNDLE_AUTH_REQUIRED",
  );
});

test("never sends the user token to an alternate gateway", async () => {
  const root = await createRepository();
  let called = false;
  await assert.rejects(
    syncEffectiveRuleBundle({
      gatewayUrl: "https://example.com/functions/v1/rule-observability",
      token: "token",
      repositoryLocator: "hfe/hotel-web",
      repoRoot: root,
      fetchImpl: async () => {
        called = true;
        return response(bundleBody());
      },
    }),
    (error) => error.code === "RULE_BUNDLE_GATEWAY_INVALID",
  );
  assert.equal(called, false);
});

test("keeps the legacy distribution gateway during migration and rejects wrong-domain URLs", async () => {
  const root = await createRepository();
  const legacyCalls = [];
  await syncEffectiveRuleBundle({
    gatewayUrl: "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability",
    token: "token",
    repositoryLocator: "hfe/hotel-web",
    repoRoot: root,
    fetchImpl: async (url) => {
      legacyCalls.push(url);
      return response(bundleBody());
    },
  });
  assert.equal(legacyCalls.length, 1);
  assert.ok(legacyCalls[0].includes("/functions/v1/rule-observability/v1/"));

  for (const gatewayUrl of [
    "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-intake",
    "https://other.database.sankuai.com/functions/v1/rule-distribution",
    "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-distribution?redirect=rule-observability",
    "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-distribution#rule-observability",
    "https://db0y7dgg85gphojyva.database.sankuai.com:4444/functions/v1/rule-distribution",
  ]) {
    let called = false;
    await assert.rejects(syncEffectiveRuleBundle({
      gatewayUrl,
      token: "token",
      repositoryLocator: "hfe/hotel-web",
      repoRoot: await createRepository(),
      fetchImpl: async () => {
        called = true;
        return response(bundleBody());
      },
    }), (error) => error.code === "RULE_BUNDLE_GATEWAY_INVALID");
    assert.equal(called, false);
  }
});

test("updates ASCII source filenames to Chinese filenames and preserves user files", async () => {
  const root = await createRepository();
  const oldPath = "l1/frontend-l1/coding-standards/rules/async--.md";
  const newPath = "l1/frontend-l1/coding-standards/rules/ASYNC-异步与异常处理.MD";
  const content = "# 异步与异常处理\n保持正文。\n";
  const legacy = bundleBody({ files: [{ relative_path: oldPath, content }] });
  const next = bundleBody({ files: [{ relative_path: newPath, content }] });
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(legacy) });
  const userFile = path.join(root, ".mdp/rules/个人补充.md");
  await writeFile(userFile, "user notes\n", "utf8");
  let request;
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async (_url, init) => {
    request = JSON.parse(init.body);
    return response(next);
  } });
  assert.equal(request.known_snapshot_id, legacy.snapshot.snapshot_id);
  assert.notEqual(next.snapshot.snapshot_id, legacy.snapshot.snapshot_id);
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/ASYNC-异步与异常处理.MD"), "utf8"), content);
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/async--.md")));
  assert.equal(await readFile(userFile, "utf8"), "user notes\n");
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  assert.equal(manifest.schema_version, "mt-effective-rule-bundle-manifest/v7");
  assert.equal(manifest.resolver_version, "effective-rule-bundle/v4");
  assert.deepEqual(manifest.managed_files, ["company/fe/frontend-l1/ASYNC-异步与异常处理.MD"]);
  const replay = await syncEffectiveRuleBundle({ ...options, fetchImpl: async (_url, init) => {
    assert.equal(JSON.parse(init.body).known_snapshot_id, next.snapshot.snapshot_id);
    return response({ ...next, status: "not_modified", files: [] });
  } });
  assert.equal(replay.status, "not_modified");
});

test("blocks a user-owned case alias of a new Chinese filename before replacing legacy files", async () => {
  const root = await createRepository();
  const legacy = bundleBody();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(legacy) });
  const userFile = path.join(root, ".mdp/rules/company/fe/frontend-l1/async-异步.md");
  await writeFile(userFile, "user-owned\n", "utf8");
  const next = bundleBody({ files: [{ relative_path: "l1/ASYNC-异步.md", content: "server\n" }] });
  await assert.rejects(syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(next) }),
    (error) => error.code === "RULE_BUNDLE_LOCAL_COLLISION");
  assert.equal(await readFile(userFile, "utf8"), "user-owned\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/frontend-l1.md"), "utf8"), "# L1\n");
});

test("rejects unsafe paths, Unicode-equivalent duplicates and symlink targets", async () => {
  const options = { token: "token", repositoryLocator: "hfe/hotel-web" };
  for (const relative_path of ["../规范.md", "l1/CON.md", "l1/规范:异步.md", "l1/\u202e规范.md", "l1/规范\u0000.md", `l1/${"中".repeat(80)}.md`]) {
    const repoRoot = await createRepository();
    await assert.rejects(syncEffectiveRuleBundle({ ...options, repoRoot, fetchImpl: async () => response(bundleBody({ files: [{ relative_path, content: "x" }] })) }),
      (error) => error.code === "RULE_BUNDLE_FILE_PATH_INVALID");
  }
  const repoRoot = await createRepository();
  const duplicates = bundleBody({ files: ["l1/Café.md", "l1/Cafe\u0301.md"].map((relative_path) => ({ relative_path, content: "x" })) });
  await assert.rejects(syncEffectiveRuleBundle({ ...options, repoRoot, fetchImpl: async () => response(duplicates) }),
    (error) => error.code === "RULE_BUNDLE_FILE_DUPLICATE");
  const caseAliases = bundleBody({ files: ["l1/Straße.md", "l1/STRASSE.md"].map((relative_path) => ({ relative_path, content: "x" })) });
  await assert.rejects(syncEffectiveRuleBundle({ ...options, repoRoot, fetchImpl: async () => response(caseAliases) }),
    (error) => error.code === "RULE_BUNDLE_FILE_DUPLICATE");
  const directoryAliases = bundleBody({ files: ["l1/Rules/甲.md", "l1/rules/乙.md"].map((relative_path) => ({ relative_path, content: "x" })) });
  await assert.rejects(syncEffectiveRuleBundle({ ...options, repoRoot, fetchImpl: async () => response(directoryAliases) }),
    (error) => error.code === "RULE_BUNDLE_FILE_DUPLICATE");
  const outside = path.join(repoRoot, "outside.md");
  await writeFile(outside, "outside\n", "utf8");
  await mkdir(path.join(repoRoot, ".mdp/rules/company/fe/frontend-l1"), { recursive: true });
  await symlink(outside, path.join(repoRoot, ".mdp/rules/company/fe/frontend-l1/规范.md"));
  await assert.rejects(syncEffectiveRuleBundle({ ...options, repoRoot, fetchImpl: async () => response(bundleBody({ files: [{ relative_path: "l1/规范.md", content: "server" }] })) }),
    (error) => error.code === "RULE_BUNDLE_LOCAL_SYMLINK");
  assert.equal(await readFile(outside, "utf8"), "outside\n");
});

test("v4 rejects a missing or inconsistent resolver version and cannot reuse a v1 snapshot identity", async () => {
  const valid = bundleBody();
  const legacy = bundleBody({ version: 1, legacy: true });
  for (const resolver_version of [null, undefined, "effective-rule-bundle/v1"]) {
    const body = { ...valid, snapshot: { ...valid.snapshot, resolver_version } };
    await assert.rejects(syncEffectiveRuleBundle({ token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: await createRepository(), fetchImpl: async () => response(body) }),
      (error) => error.code === "RULE_BUNDLE_RESPONSE_INVALID");
  }
  const wrongIdentity = { ...valid, snapshot: { ...valid.snapshot, snapshot_id: legacy.snapshot.snapshot_id } };
  await assert.rejects(syncEffectiveRuleBundle({ token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: await createRepository(), fetchImpl: async () => response(wrongIdentity) }),
    (error) => error.code === "RULE_BUNDLE_SNAPSHOT_HASH_MISMATCH");
});

test("migrates a v1 reserved source filename to a safe named domain path", { skip: process.platform === "win32" }, async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  await seedLegacyManifest(root, bundleBody({ version: 1, legacy: true, files: [{ relative_path: "l1/con.md", content: "legacy\n" }] }), 1);
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(bundleBody({ files: [{ relative_path: "l1/_CON.md", content: "current\n" }] })) });
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/con.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/_CON.md"), "utf8"), "current\n");
});

test("named domain layout flattens source directories and preserves unrelated company files", async () => {
  const legacy = bundleBody({ files: [{ relative_path: "l1/rules/async--.md", content: "rule\n" }] });
  const next = bundleBody({ files: [{ relative_path: "l1/Rules/ASYNC-异步.md", content: "rule\n" }] });
  for (const withUserFile of [false, true]) {
    const root = await createRepository();
    const opts = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
    await syncEffectiveRuleBundle({ ...opts, fetchImpl: async () => response(legacy) });
    const userFile = path.join(root, ".mdp/rules/company/fe/frontend-l1/个人.md");
    if (withUserFile) await writeFile(userFile, "user\n");
    await syncEffectiveRuleBundle({ ...opts, fetchImpl: async () => response(next) });
    await assert.rejects(readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/async--.md")));
    assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/frontend-l1/ASYNC-异步.md"), "utf8"), "rule\n");
    if (withUserFile) assert.equal(await readFile(userFile, "utf8"), "user\n");
  }
});


test("backend v4 installs Java L1 and Spring L2 Chinese files under named java directories", async () => {
  const root = await createRepository();
  const files = [{ relative_path: "l1/java-l1/Java-日期处理.md", content: "# Java 日期处理\n" }, { relative_path: "l2/team-java-l2/Spring-依赖注入.md", content: "# Spring 依赖注入\n" }];
  const body = bundleBody({ domain: "backend", files, refs: [{ rule_set_id: "java-l1", release_id: "java-l1@test", scope_level: "L1" }, { rule_set_id: "team-java-l2", release_id: "team-java-l2@test", scope_level: "L2" }] });
  await syncEffectiveRuleBundle({ token: "token", repositoryLocator: "team/java-service", repoRoot: root, fetchImpl: async () => response(body) });
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/java/java-l1/Java-日期处理.md"), "utf8"), files[0].content);
  assert.equal(await readFile(path.join(root, ".mdp/rules/team/java/team-java-l2/Spring-依赖注入.md"), "utf8"), files[1].content);
  await assert.rejects(readFile(path.join(root, ".mdp/rules/frontend/Java-日期处理.md")));
});

const layoutOptions = (root, extra = {}) => ({ token: "token", mis: "aicr-agent", repositoryLocator: "hfe/hotel-web", repoRoot: root, ...extra });
const installBody = (root, body, extra = {}) => syncEffectiveRuleBundle({ ...layoutOptions(root), ...extra, fetchImpl: async () => response(body) });

test("v4 installs real Chinese rule-set names and each file's declared domain in a mixed repository", async () => {
  const root = await createRepository();
  const refs = [
    { rule_set_id: "company-fe-id", release_id: "fe@test", scope_level: "L1", standard_domain: "frontend", local_rule_set_name: "前端公司规范" },
    { rule_set_id: "company-java-id", release_id: "java@test", scope_level: "L1", standard_domain: "backend", local_rule_set_name: "Java公司规范" },
    { rule_set_id: "team-fe-id", release_id: "teamfe@test", scope_level: "L2", standard_domain: "frontend", local_rule_set_name: "交易团队规范" },
    { rule_set_id: "team-java-id", release_id: "teamjava@test", scope_level: "L2", standard_domain: "backend", local_rule_set_name: "交易团队规范" },
  ];
  const body = bundleBody({ refs, files: refs.map((ref) => ({ relative_path: `${ref.scope_level.toLowerCase()}/${ref.rule_set_id}/规则.md`, content: ref.rule_set_id })) });
  const receipt = await installBody(root, body);
  assert.equal(receipt.local_layout, "scope-domain-ruleset/v1");
  assert.deepEqual(receipt.managed_files, [
    "company/fe/前端公司规范/规则.md", "company/java/Java公司规范/规则.md",
    "team/fe/交易团队规范/规则.md", "team/java/交易团队规范/规则.md",
  ]);
  for (let index = 0; index < refs.length; index += 1) assert.equal(await readFile(path.join(root, ".mdp/rules", receipt.managed_files[index]), "utf8"), refs[index].rule_set_id);
});

test("rejects old service responses and preserves the already installed rules and manifest", async () => {
  const root = await createRepository();
  await installBody(root, bundleBody());
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const before = await readFile(manifestPath, "utf8");
  for (const version of [1, 2, 3]) {
    await assert.rejects(installBody(root, bundleBody({ version, legacy: true, ...(version === 3 ? { stage: "coding" } : {}) }), version === 3 ? { stage: "coding" } : {}), (error) => {
      assert.equal(error.code, "RULE_BUNDLE_LAYOUT_UNSUPPORTED");
      assert.match(error.message, /先升级服务端/);
      return true;
    });
    assert.equal(await readFile(manifestPath, "utf8"), before);
  }
});

test("migrates all four legacy formal manifest versions and protects project and unknown files", async () => {
  for (const manifestVersion of [1, 2, 3, 4]) {
    const root = await createRepository();
    const stage = manifestVersion === 4 ? "coding" : undefined;
    const files = [{ relative_path: "l1/frontend-l1/base.md", content: "unchanged\n" }];
    const refs = [releaseRefs[0]];
    const old = bundleBody({ version: manifestVersion === 1 ? 1 : manifestVersion === 4 ? 3 : 2, legacy: true, stage, files, refs });
    const previous = await seedLegacyManifest(root, old, manifestVersion);
    for (const file of ["project/fe/项目规范/local.md", "project/java/项目规范/local.md", "company/个人补充.md"]) {
      const target = path.join(root, ".mdp/rules", file);
      await mkdir(path.dirname(target), { recursive: true });
      await writeFile(target, "user\n");
    }
    const ready = bundleBody({ files, refs, stage });
    let request;
    await syncEffectiveRuleBundle({ ...layoutOptions(root, { stage }), fetchImpl: async (_url, init) => { request = JSON.parse(init.body); return response(ready); } });
    assert.equal(request.bundle_contract, "scope-domain-ruleset/v1");
    assert.equal(Object.hasOwn(request, "known_snapshot_id"), false);
    for (const oldPath of previous.managed_files) await assert.rejects(readFile(path.join(root, ".mdp/rules", oldPath)));
    const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
    const manifest = await readFile(manifestPath, "utf8");
    assert.equal(JSON.parse(manifest).schema_version, "mt-effective-rule-bundle-manifest/v7");
    for (const file of ["project/fe/项目规范/local.md", "project/java/项目规范/local.md", "company/个人补充.md"]) assert.equal(await readFile(path.join(root, ".mdp/rules", file), "utf8"), "user\n");
    await syncEffectiveRuleBundle({ ...layoutOptions(root, { stage }), fetchImpl: async (_url, init) => { assert.equal(JSON.parse(init.body).known_snapshot_id, ready.snapshot.snapshot_id); return response({ ...ready, status: "not_modified", files: [] }); } });
    assert.equal(await readFile(manifestPath, "utf8"), manifest);
  }
});

const seedBootstrapManifest = async (root, manifestVersion, { changed = false } = {}) => {
  const stage = manifestVersion === 2 ? "coding" : undefined;
  const refs = [releaseRefs[0]];
  const content = "old bootstrap\n";
  const source = "l1/frontend-l1/base.md";
  const file = { relative_path: source, sha256: sha256Hex(content), byte_size: Buffer.byteLength(content) };
  const manifestHash = sha256Hex(canonicalJson([file]));
  const bundleSchema = `l1-bootstrap-bundle/v${manifestVersion}`;
  const dependencyHash = sha256Hex("legacy bootstrap");
  const manifest = {
    schema_version: `mt-l1-bootstrap-manifest/v${manifestVersion}`, bundle_schema: bundleSchema,
    local_layout: "company-team/v1", standard_domain: "frontend", domain_source: "user_explicit",
    release_refs: refs, manifest_hash: manifestHash, total_bytes: file.byte_size,
    snapshot_id: sha256Hex(canonicalJson({ bootstrap_version: bundleSchema, standard_domain: "frontend", manifest_hash: manifestHash, release_refs: refs, ...(stage ? { stage, dependency_hash: dependencyHash } : {}) })),
    ...(stage ? { stage, dependency_hash: dependencyHash } : {}),
    managed_files: ["company/base.md"], managed_file_sources: { "company/base.md": source },
    managed_file_hashes: { "company/base.md": file.sha256 }, managed_file_sizes: { "company/base.md": file.byte_size },
  };
  const rules = path.join(root, ".mdp/rules");
  await mkdir(path.join(rules, "company"), { recursive: true });
  await writeFile(path.join(rules, "company/base.md"), changed ? "user modified\n" : content);
  await writeFile(path.join(rules, ".mt-l1-bootstrap.json"), JSON.stringify(manifest));
  return stage;
};

test("migrates both old bootstrap manifests to the named domain layout and replays without writes", async () => {
  for (const manifestVersion of [1, 2]) {
    const root = await createRepository();
    const stage = await seedBootstrapManifest(root, manifestVersion);
    const body = bootstrapBody({ stage, refs: [{ ...releaseRefs[0], local_rule_set_name: "公司前端规范" }] });
    let known;
    const fetchBootstrap = (ready) => async (url, init) => url.endsWith("/v1/effective-rule-bundles/resolve")
      ? response({ error: { code: "repository_not_registered" } }, 404)
      : (known = JSON.parse(init.body), response(ready));
    const options = layoutOptions(root, { bootstrap: true, domain: "frontend", stage });
    await syncEffectiveRuleBundle({ ...options, fetchImpl: fetchBootstrap(body) });
    assert.equal(Object.hasOwn(known, "known_snapshot_id"), false);
    assert.equal(known.bundle_contract, "scope-domain-ruleset/v1");
    await assert.rejects(readFile(path.join(root, ".mdp/rules/company/base.md")));
    assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/公司前端规范/async.md"), "utf8"), "# L1\n");
    const manifestPath = path.join(root, ".mdp/rules/.mt-l1-bootstrap.json");
    const before = await readFile(manifestPath, "utf8");
    assert.equal(JSON.parse(before).schema_version, "mt-l1-bootstrap-manifest/v4");
    await syncEffectiveRuleBundle({ ...options, fetchImpl: fetchBootstrap({ ...body, status: "not_modified", files: [] }) });
    assert.equal(known.known_snapshot_id, body.snapshot.snapshot_id);
    assert.equal(await readFile(manifestPath, "utf8"), before);
  }
});

test("refuses to replace altered bootstrap files during bootstrap migration or formal adoption", async () => {
  for (const formal of [false, true]) {
    const root = await createRepository();
    await seedBootstrapManifest(root, 1, { changed: true });
    let calls = 0;
    await assert.rejects(syncEffectiveRuleBundle({ ...layoutOptions(root, { bootstrap: !formal, domain: "frontend" }), fetchImpl: async () => { calls += 1; return response(formal ? bundleBody() : bootstrapBody()); } }), (error) => error.code === "RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED");
    assert.equal(calls, 0);
    assert.equal(await readFile(path.join(root, ".mdp/rules/company/base.md"), "utf8"), "user modified\n");
  }
});

test("rejects foreign-domain bootstrap releases before changing existing files", async () => {
  const root = await createRepository();
  const body = bootstrapBody({ domain: "frontend" });
  body.snapshot.release_refs[0].standard_domain = "backend";
  body.snapshot.snapshot_id = sha256Hex(canonicalJson({ bootstrap_version: body.schema_version, standard_domain: "frontend", manifest_hash: body.snapshot.manifest_hash, release_refs: body.snapshot.release_refs }));
  await assert.rejects(syncEffectiveRuleBundle({ ...layoutOptions(root, { bootstrap: true, domain: "frontend" }), fetchImpl: async (url) => url.endsWith("/v1/effective-rule-bundles/resolve") ? response({ error: { code: "repository_not_registered" } }, 404) : response(body) }), (error) => error.code === "RULE_BUNDLE_BOOTSTRAP_RESPONSE_INVALID");
  await assert.rejects(access(path.join(root, ".mdp/rules")));
});

test("requires each v4 file identity to bind to exactly one release and preserves an installed bundle", async () => {
  const root = await createRepository();
  await installBody(root, bundleBody());
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const before = await readFile(manifestPath, "utf8");
  for (const identity of [{ rule_set_id: "other" }, { release_id: "other" }, { rule_set_id: undefined, release_id: undefined }]) {
    const body = bundleBody();
    Object.assign(body.files[0], identity);
    await assert.rejects(installBody(root, body), (error) => error.code === "RULE_BUNDLE_FILE_RELEASE_INVALID");
    assert.equal(await readFile(manifestPath, "utf8"), before);
  }
});

test("rejects missing, unsafe or conflicting rule-set names instead of falling back to ids", async () => {
  const root = await createRepository();
  await installBody(root, bundleBody());
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const before = await readFile(manifestPath, "utf8");
  for (const local_rule_set_name of ["", "../outside", "hidden/name", ".hidden", "CON", "a.", "name ", "Café".normalize("NFD"), "a\u200bb", "a\ud800b", "a".repeat(201)]) {
    const body = bundleBody({ refs: [{ ...releaseRefs[0], local_rule_set_name }], files: [{ relative_path: "l1/frontend-l1/base.md", content: "x" }] });
    await assert.rejects(installBody(root, body), (error) => error.code === "RULE_BUNDLE_RULE_SET_NAME_INVALID");
    assert.equal(await readFile(manifestPath, "utf8"), before);
  }
  const refs = [
    { ...releaseRefs[0], local_rule_set_name: "Rules" },
    { rule_set_id: "other-fe", release_id: "other@test", scope_level: "L1", local_rule_set_name: "rules" },
  ];
  const body = bundleBody({ refs, files: refs.map((ref) => ({ relative_path: `l1/${ref.rule_set_id}/base.md`, content: ref.rule_set_id })) });
  await assert.rejects(installBody(root, body), (error) => error.code === "RULE_BUNDLE_RULE_SET_NAME_COLLISION");
  assert.equal(await readFile(manifestPath, "utf8"), before);
});

test("does not accept changed file identities or layout metadata hidden behind stale hashes", async () => {
  const root = await createRepository();
  for (const mutate of [
    (body) => { body.snapshot.release_refs[0].local_rule_set_name = "new-name"; },
    (body) => { body.snapshot.release_refs[0].standard_domain = "backend"; },
    (body) => { body.files[0].release_id = body.snapshot.release_refs[1].release_id; body.files[0].rule_set_id = body.snapshot.release_refs[1].rule_set_id; body.files[0].relative_path = "l2/team-fe-l2/extra.md"; },
  ]) {
    const body = bundleBody();
    mutate(body);
    await assert.rejects(installBody(root, body), (error) => ["RULE_BUNDLE_SNAPSHOT_HASH_MISMATCH", "RULE_BUNDLE_MANIFEST_HASH_MISMATCH"].includes(error.code));
  }
});

test("refuses a malformed existing manifest without making a network request", async () => {
  const root = await createRepository();
  const rules = path.join(root, ".mdp/rules");
  await mkdir(rules, { recursive: true });
  await writeFile(path.join(rules, ".mt-effective-rule-bundle.json"), "{broken");
  let called = false;
  await assert.rejects(syncEffectiveRuleBundle({ ...layoutOptions(root), fetchImpl: async () => { called = true; return response(bundleBody()); } }), (error) => error.code === "RULE_BUNDLE_LOCAL_MANIFEST_INVALID");
  assert.equal(called, false);
  assert.equal(await readFile(path.join(rules, ".mt-effective-rule-bundle.json"), "utf8"), "{broken");
});

test("rule-set name changes update the snapshot and move only previous managed files", async () => {
  const root = await createRepository();
  const files = [{ relative_path: "l1/frontend-l1/base.md", content: "same\n" }];
  const old = bundleBody({ refs: [{ ...releaseRefs[0], local_rule_set_name: "旧名称" }], files });
  await installBody(root, old);
  const user = path.join(root, ".mdp/rules/company/fe/旧名称/个人补充.md");
  await writeFile(user, "keep\n");
  const next = bundleBody({ refs: [{ ...releaseRefs[0], local_rule_set_name: "新名称" }], files });
  assert.equal(old.snapshot.manifest_hash, next.snapshot.manifest_hash);
  assert.notEqual(old.snapshot.snapshot_id, next.snapshot.snapshot_id);
  await installBody(root, next);
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/fe/旧名称/base.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/fe/新名称/base.md"), "utf8"), "same\n");
  assert.equal(await readFile(user, "utf8"), "keep\n");
});

test("missing release layout metadata and unknown domain fail before altering an existing installation", async () => {
  const root = await createRepository();
  await installBody(root, bundleBody());
  const manifest = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const before = await readFile(manifest, "utf8");
  for (const [field, value, code] of [
    ["local_rule_set_name", undefined, "RULE_BUNDLE_RULE_SET_NAME_INVALID"],
    ["standard_domain", undefined, "RULE_BUNDLE_RELEASE_DOMAIN_INVALID"],
    ["standard_domain", "unknown", "RULE_BUNDLE_RELEASE_DOMAIN_INVALID"],
  ]) {
    const body = bundleBody();
    body.snapshot.release_refs[0][field] = value;
    await assert.rejects(installBody(root, body), (error) => error.code === code);
    assert.equal(await readFile(manifest, "utf8"), before);
  }
});

test("rejects a legal name whose complete local path exceeds the UTF-8 path budget", async () => {
  const root = await createRepository();
  const body = bundleBody({ refs: [{ ...releaseRefs[0], local_rule_set_name: "规".repeat(66) }], files: [{ relative_path: "l1/frontend-l1/long-document-name-that-exceeds-budget.md", content: "x" }] });
  await assert.rejects(installBody(root, body), (error) => error.code === "RULE_BUNDLE_FILE_PATH_INVALID");
  await assert.rejects(access(path.join(root, ".mdp/rules")));
});

const indexTable = (reference) => `**编码规范**\r\n\r\n| 名称 | 触发场景 | 路径 |\r\n|---|---|---|\r\n| 测试规范 | 编码时 | \`${reference}\` |\r\n`;
const agentsEntry = (body, { content = indexTable('rules/async.md'), bindings, ruleSetId, sourcePath = 'l1/frontend-l1/async.md' } = {}) => {
  const ref = body.snapshot.release_refs.find((item) => !ruleSetId || item.rule_set_id === ruleSetId);
  return {
    rule_set_id: ref.rule_set_id, release_id: ref.release_id,
    index: { schema_version: 'rule-set-agents-index/v1', origin: 'git', source_path: 'AGENTS.md', content, content_hash: content === null ? null : `sha256:${sha256Hex(content)}`, warnings: [] },
    bindings: bindings || [{ reference: 'rules/async.md', document_id: 'async-doc', source_path: 'rules/async.md', bundle_relative_path: sourcePath }],
  };
};
const withAgents = (body, entries = [agentsEntry(body)]) => {
  body.agents_indexes = entries;
  const snapshot = body.snapshot;
  snapshot.agents_indexes_hash = sha256Hex(canonicalJson(entries));
  const projection = {
    ...(snapshot.bootstrap_version ? { bootstrap_version: snapshot.bootstrap_version, standard_domain: snapshot.standard_domain } : {
      ...(snapshot.resolver_version ? { resolver_version: snapshot.resolver_version } : {}),
      repository_id: snapshot.repository.repository_id, canonical_key: snapshot.repository.canonical_key, standard_domain: snapshot.repository.standard_domain,
    }),
    manifest_hash: snapshot.manifest_hash, agents_indexes_hash: snapshot.agents_indexes_hash,
    release_refs: snapshot.release_refs,
    ...(snapshot.stage ? { stage: snapshot.stage, dependency_hash: snapshot.dependency_hash } : {}),
  };
  snapshot.snapshot_id = sha256Hex(canonicalJson(projection));
  return body;
};
const indexManifest = (root, bootstrap = false) => readFile(path.join(root, '.mdp/rules', bootstrap ? '.mt-l1-bootstrap.json' : '.mt-effective-rule-bundle.json'), 'utf8').then(JSON.parse);
const indexPath = (root, id = 'frontend-l1') => path.join(root, '.mdp/rules/agents-index', id, 'AGENTS.md');

test('installs index beside rules with independent manifest and caches verified not_modified snapshots', async () => {
  const root = await createRepository();
  await writeFile(path.join(root, 'AGENTS.md'), '# User instructions\n');
  const base = bundleBody({ version: 2, files: [{ relative_path: 'l1/frontend-l1/async.md', content: '# Async\n' }], refs: [releaseRefs[0]] });
  const body = withAgents(base);
  const options = { token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root };
  const receipt = await syncEffectiveRuleBundle({ ...options, fetchImpl: async (_, init) => {
    assert.equal(JSON.parse(init.body).agents_index_contract, 'rule-set-agents-index/v1'); return response(body);
  } });
  assert.equal(await readFile(indexPath(root), 'utf8'), indexTable('.mdp/rules/company/fe/frontend-l1/async.md'));
  assert.equal(await readFile(path.join(root, 'AGENTS.md'), 'utf8'), '# User instructions\n');
  assert.deepEqual(receipt.managed_agents_indexes, ['agents-index/frontend-l1/AGENTS.md']);
  const manifest = await indexManifest(root);
  assert.equal(manifest.schema_version, 'mt-effective-rule-bundle-manifest/v7');
  assert.equal(manifest.total_bytes, base.snapshot.total_bytes);
  assert.equal(manifest.manifest_hash, base.snapshot.manifest_hash);
  assert.deepEqual(manifest.managed_files, ['company/fe/frontend-l1/async.md']);
  assert.equal(manifest.agents_indexes[0].index.content, indexTable('rules/async.md'));
  const replay = await syncEffectiveRuleBundle({ ...options, fetchImpl: async (_, init) => {
    assert.equal(JSON.parse(init.body).known_snapshot_id, body.snapshot.snapshot_id);
    return response({ ...body, status: 'not_modified', files: [] });
  } });
  assert.equal(replay.status, 'not_modified');
  assert.equal((await indexManifest(root)).installed_at, manifest.installed_at);
});

test('index-only changes update snapshot while maintaining regular manifest hashes and clean up removed indexes', async () => {
  const root = await createRepository();
  const options = { token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root };
  const base = () => bundleBody({ version: 2, files: [{ relative_path: 'l1/frontend-l1/async.md', content: '# Async\n' }], refs: [releaseRefs[0]] });
  const first = withAgents(base());
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(first) });
  const next = base(); withAgents(next, [agentsEntry(next, { content: 'custom raw\r\n' })]);
  assert.notEqual(first.snapshot.snapshot_id, next.snapshot.snapshot_id);
  assert.equal(first.snapshot.manifest_hash, next.snapshot.manifest_hash);
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(next) });
  assert.equal(await readFile(indexPath(root), 'utf8'), 'custom raw\r\n');
  const removed = withAgents(base(), []);
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(removed) });
  await assert.rejects(readFile(indexPath(root)), { code: 'ENOENT' });
  assert.deepEqual((await indexManifest(root)).managed_agents_indexes, []);
});

test('bad Markdown and filtered or unknown references are nonblocking while integrity damage is rejected', async () => {
  for (const content of [null, '', 'unstructured\r\n', indexTable('missing.md')]) {
    const root = await createRepository();
    const body = bundleBody({ refs: [releaseRefs[0]], files: [{ relative_path: 'l1/frontend-l1.md', content: '# Rule\n' }] });
    withAgents(body, [agentsEntry(body, { content, sourcePath: 'l1/frontend-l1.md' })]);
    const receipt = await syncEffectiveRuleBundle({ token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root, fetchImpl: async () => response(body) });
    assert.equal(receipt.status, 'installed');
    assert.ok(receipt.agents_index_warnings.length);
    if (content !== null) assert.equal(await readFile(indexPath(root), 'utf8'), content);
  }
  for (const corrupt of ['collection', 'content', 'snapshot']) {
    const root = await createRepository();
    const body = bundleBody({ refs: [releaseRefs[0]], files: [{ relative_path: 'l1/frontend-l1.md', content: '# Rule\n' }] });
    withAgents(body);
    if (corrupt === 'collection') body.agents_indexes[0].index.content += 'tampered';
    if (corrupt === 'content') { body.agents_indexes[0].index.content_hash = '0'.repeat(64); withAgents(body, body.agents_indexes); }
    if (corrupt === 'snapshot') body.snapshot.snapshot_id = '0'.repeat(64);
    await assert.rejects(syncEffectiveRuleBundle({ token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root, fetchImpl: async () => response(body) }), (error) => ['RULE_BUNDLE_AGENTS_INDEX_INVALID', 'RULE_BUNDLE_SNAPSHOT_HASH_MISMATCH'].includes(error.code));
    await assert.rejects(readFile(indexPath(root)), { code: 'ENOENT' });
  }
});

test('new manifest protects locally edited indexes and unknown target collisions before writing', async () => {
  for (const mode of ['edited', 'unknown', 'portable-alias']) {
    const root = await createRepository();
    const body = withAgents(bundleBody({ refs: [releaseRefs[0]], files: [{ relative_path: 'l1/frontend-l1/async.md', content: '# Rule\n' }] }));
    const options = { token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root, fetchImpl: async () => response(body) };
    if (mode === 'edited') await syncEffectiveRuleBundle(options);
    const target = mode === 'portable-alias' ? indexPath(root).replace('AGENTS.md', 'agents.MD') : indexPath(root);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, '# Local file\n');
    await assert.rejects(syncEffectiveRuleBundle(options), (error) => error.code === (mode === 'edited' ? 'RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED' : 'RULE_BUNDLE_LOCAL_COLLISION'));
    assert.equal(await readFile(target, 'utf8'), '# Local file\n');
  }
});

test('actual filename collision suffixes are used by index bindings', async () => {
  const root = await createRepository();
  const body = bundleBody({ version: 2, refs: [releaseRefs[0]], files: [
    { relative_path: 'l1/frontend-l1/one/async.md', content: '# One\n' },
    { relative_path: 'l1/frontend-l1/two/async.md', content: '# Two\n' },
  ] });
  withAgents(body, [agentsEntry(body, { sourcePath: 'l1/frontend-l1/two/async.md' })]);
  await syncEffectiveRuleBundle({ token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root, fetchImpl: async () => response(body) });
  const manifest = await indexManifest(root);
  const expected = Object.entries(manifest.managed_file_sources).find(([, source]) => source === 'l1/frontend-l1/two/async.md')[0];
  assert.match(expected, /async--/);
  assert.equal(await readFile(indexPath(root), 'utf8'), indexTable(`.mdp/rules/${expected}`));
});

test('staged indexes preserve filtered references and do not reuse another stage snapshot', async () => {
  const root = await createRepository();
  const options = { token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root };
  const staged = (stage) => {
    const body = bundleBody({ version: 3, stage, refs: [releaseRefs[0]], files: [{ relative_path: 'l1/frontend-l1/async.md', content: '# Rule\n' }] });
    return withAgents(body, [agentsEntry(body, { bindings: [{ reference: 'rules/async.md', document_id: 'filtered', source_path: 'rules/async.md', bundle_relative_path: null }] })]);
  };
  await syncEffectiveRuleBundle({ ...options, stage: 'coding', fetchImpl: async () => response(staged('coding')) });
  const receipt = await syncEffectiveRuleBundle({ ...options, stage: 'cr', fetchImpl: async (_, init) => {
    assert.equal(JSON.parse(init.body).known_snapshot_id, undefined); return response(staged('cr'));
  } });
  assert.equal(receipt.agents_index_warnings[0].code, 'agents_index_unmatched_reference');
  assert.equal(await readFile(indexPath(root), 'utf8'), indexTable('rules/async.md'));
});

test('migrates a legacy manifest then reports and upgrades missing index capability explicitly', async () => {
  const root = await createRepository();
  const options = { token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root };
  const old = bundleBody({ version: 2, refs: [releaseRefs[0]], files: [{ relative_path: 'l1/frontend-l1/async.md', content: '# Rule\n' }] });
  await seedLegacyManifest(root, bundleBody({ legacy: true, version: 2, refs: [releaseRefs[0]], files: [{ relative_path: 'l1/frontend-l1/async.md', content: '# Rule\n' }] }), 4);
  const legacy = await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(old) });
  assert.equal(legacy.agents_index_warnings[0].code, 'agents_index_contract_unavailable');
  assert.equal((await indexManifest(root)).schema_version, 'mt-effective-rule-bundle-manifest/v7');
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(withAgents(structuredClone(old))) });
  assert.equal((await indexManifest(root)).schema_version, 'mt-effective-rule-bundle-manifest/v7');
});

test('bootstrap index repeats safely and formal bundle atomically takes over its managed files', async () => {
  const root = await createTrackedRepository({ 'src/App.tsx': 'export default null;\n' });
  const bootstrap = withAgents(bootstrapBody());
  const options = { token: 'token', repositoryLocator: 'hfe/new-web', repoRoot: root, bootstrap: true, mis: "aicr-agent" };
  const fetchBootstrap = (body) => async (url, init) => {
    if (url.endsWith('/v1/effective-rule-bundles/resolve')) return response({ error: { code: 'repository_not_registered' } }, 404);
    assert.equal(JSON.parse(init.body).agents_index_contract, 'rule-set-agents-index/v1'); return response(body);
  };
  await syncEffectiveRuleBundle({ ...options, fetchImpl: fetchBootstrap(bootstrap) });
  assert.equal((await indexManifest(root, true)).schema_version, 'mt-l1-bootstrap-manifest/v4');
  assert.equal(await readFile(indexPath(root), 'utf8'), indexTable('.mdp/rules/company/fe/frontend-l1/async.md'));
  const replay = await syncEffectiveRuleBundle({ ...options, fetchImpl: fetchBootstrap({ ...bootstrap, status: 'not_modified', files: [] }) });
  assert.equal(replay.status, 'not_modified');
  const formal = bundleBody({ version: 2, refs: [releaseRefs[0]], files: [{ relative_path: 'l1/frontend-l1/async.md', content: '# Formal\n' }] });
  withAgents(formal, [agentsEntry(formal, { content: indexTable('rules/async.md') + '\r\n发布版本\r\n' })]);
  await syncEffectiveRuleBundle({ ...options, bootstrap: false, fetchImpl: async () => response(formal) });
  await assert.rejects(indexManifest(root, true), { code: 'ENOENT' });
  assert.equal((await indexManifest(root)).schema_version, 'mt-effective-rule-bundle-manifest/v7');
  assert.match(await readFile(indexPath(root), 'utf8'), /发布版本/);
});

test("bootstrap requires an explicit valid self-reported actor before any network or authentication", async () => {
  for (const mis of [undefined, "", " ", "AICR", "a".repeat(65), "bot\nadmin", "机器人"]) {
    let calls = 0;
    await assert.rejects(syncEffectiveRuleBundle({ bootstrap: true, mis, fetchImpl: async () => { calls++; } }),
      (error) => error.code === "RULE_BUNDLE_BOOTSTRAP_MIS_REQUIRED" && error.message.includes("不作为认证身份"));
    assert.equal(calls, 0);
  }
});

test("anonymous bootstrap rejects the legacy gateway before network access with migration guidance", async () => {
  const root = await createRepository();
  for (const suffix of ["", "/"]) {
    let calls = 0;
    await assert.rejects(syncEffectiveRuleBundle({
      gatewayUrl: `https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability${suffix}`,
      repositoryLocator: "team/new-web", repoRoot: root, domain: "frontend",
      bootstrap: true, publicPull: true, mis: "aicr-agent",
      token: "must-not-be-sent",
      fetchImpl: async () => { calls++; throw new Error("must not reach network"); },
    }), (error) => error.code === "RULE_BUNDLE_BOOTSTRAP_GATEWAY_UNSUPPORTED"
      && error.message.includes("请移除 --gateway-url") && error.message.includes("rule-distribution"));
    assert.equal(calls, 0);
  }
  await assert.rejects(readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json")), { code: "ENOENT" });
});

test('5 MiB indexes install, replay from verified cache and protect local edits over direct and adapter transports', async () => {
  const content = '# 大索引\r\n' + 'x'.repeat(5 * 1024 * 1024 - Buffer.byteLength('# 大索引\r\n'));
  for (const mode of ['direct', 'adapter', 'public']) {
    const root = await createRepository();
    const body = bundleBody({ version: 2, files: [{ relative_path: 'l1/frontend-l1/async.md', content: '# Async\n' }], refs: [releaseRefs[0]] });
    withAgents(body, [agentsEntry(body, { content, bindings: [] })]);
    let current = body;
    const options = { token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root,
      ...(mode === 'public' ? { publicPull: true, token: undefined } : {}),
      ...(mode === 'adapter' ? { requestTransport: async request => {
        assert.equal(request.maxResponseBytes, MAX_AGENTS_INDEX_RESPONSE_BYTES);
        return { status: 200, body: current };
      } } : { fetchImpl: async () => response(current) }),
    };
    assert.equal((await syncEffectiveRuleBundle(options)).status, 'installed');
    assert.equal(await readFile(indexPath(root), 'utf8'), content);
    current = { ...body, status: 'not_modified', files: [] };
    assert.equal((await syncEffectiveRuleBundle(options)).status, 'not_modified');
    await writeFile(indexPath(root), '# local edit');
    current = body;
    await assert.rejects(syncEffectiveRuleBundle(options), { code: 'RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED' });
    assert.equal(await readFile(indexPath(root), 'utf8'), '# local edit');
  }
});

test('large bootstrap indexes remain independent of ordinary rule file limits', async () => {
  const root = await createTrackedRepository({ 'src/App.tsx': 'export default null;\n' });
  const content = 'x'.repeat(5 * 1024 * 1024);
  const body = bootstrapBody();
  withAgents(body, [agentsEntry(body, { content, bindings: [] })]);
  const options = { token: 'token', repositoryLocator: 'hfe/new-web', repoRoot: root, bootstrap: true, mis: 'aicr-agent' };
  const fetchImpl = async url => url.endsWith('/v1/effective-rule-bundles/resolve')
    ? response({ error: { code: 'repository_not_registered' } }, 404) : response(body);
  assert.equal((await syncEffectiveRuleBundle({ ...options, fetchImpl })).status, 'installed');
  assert.equal(await readFile(indexPath(root), 'utf8'), content);
  const oversizedRule = bundleBody({ version: 2, files: [{ relative_path: 'l1/frontend-l1/async.md', content: 'x'.repeat(512 * 1024 + 1) }], refs: [releaseRefs[0]] });
  withAgents(oversizedRule, [agentsEntry(oversizedRule, { content, bindings: [] })]);
  await assert.rejects(syncEffectiveRuleBundle({ token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: await createRepository(), fetchImpl: async () => response(oversizedRule) }), { code: 'RULE_BUNDLE_FILE_TOO_LARGE' });
});

test('index negotiation preserves the 4 MiB non-index budget and the 64 MiB total cap', async () => {
  const large = { agents_indexes: [{ content: 'x'.repeat(5 * 1024 * 1024) }], snapshot: {} };
  assert.doesNotThrow(() => assertRuleResponseBudget(large, { allowAgentsIndexes: true }));
  assert.throws(() => assertRuleResponseBudget(large), { code: 'RULE_BUNDLE_RESPONSE_TOO_LARGE' });
  const overBase = { ...large, extra: 'x'.repeat(4 * 1024 * 1024) };
  assert.throws(() => assertRuleResponseBudget(overBase, { allowAgentsIndexes: true }), { code: 'RULE_BUNDLE_RESPONSE_TOO_LARGE' });
  assert.throws(() => assertRuleResponseBudget({ agents_indexes: ['x'.repeat(64 * 1024 * 1024)] }, { allowAgentsIndexes: true }), { code: 'RULE_BUNDLE_RESPONSE_TOO_LARGE' });
  for (const mode of ['direct', 'adapter']) {
    await assert.rejects(syncEffectiveRuleBundle({ token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: await createRepository(),
      ...(mode === 'adapter' ? { requestTransport: async () => ({ status: 200, body: overBase }) } : { fetchImpl: async () => response(overBase) }),
    }), { code: 'RULE_BUNDLE_RESPONSE_TOO_LARGE' });
  }
});


// Frozen pre-integration v5/v3 index manifest shape: its physical rules were
// company/team files even though this schema number was also used by the
// separate named-layout branch. Do not derive ownership by schema number alone.
const seedFlatIndexManifest = async (root, { bootstrap = false, stage } = {}) => {
  const source = 'l1/frontend-l1/async.md';
  const oldBody = withAgents(bundleBody({ legacy: true, version: stage ? 3 : 2, stage,
    refs: [releaseRefs[0]], files: [{ relative_path: source, content: '# Old rule\n' }] }));
  const manifest = await seedLegacyManifest(root, oldBody, 5);
  const rendered = indexTable('.mdp/rules/company/async.md');
  Object.assign(manifest, {
    agents_index_contract: 'rule-set-agents-index/v1',
    agents_indexes: oldBody.agents_indexes,
    agents_indexes_hash: oldBody.snapshot.agents_indexes_hash,
    managed_agents_indexes: ['agents-index/frontend-l1/AGENTS.md'],
    managed_agents_index_hashes: { 'agents-index/frontend-l1/AGENTS.md': sha256Hex(rendered) },
    managed_agents_index_sizes: { 'agents-index/frontend-l1/AGENTS.md': Buffer.byteLength(rendered) },
    agents_index_warnings: [],
  });
  if (bootstrap) {
    const version = stage ? 'l1-bootstrap-bundle/v2' : 'l1-bootstrap-bundle/v1';
    manifest.schema_version = 'mt-l1-bootstrap-manifest/v3';
    manifest.bundle_schema = version;
    manifest.domain_source = 'user_explicit';
    delete manifest.repository;
    delete manifest.resolver_version;
    manifest.snapshot_id = sha256Hex(canonicalJson({ bootstrap_version: version,
      standard_domain: manifest.standard_domain, manifest_hash: manifest.manifest_hash,
      agents_indexes_hash: manifest.agents_indexes_hash, release_refs: manifest.release_refs,
      ...(stage ? { stage, dependency_hash: manifest.dependency_hash } : {}),
    }));
    await fs.promises.rm(path.join(root, '.mdp/rules/.mt-effective-rule-bundle.json'));
  }
  const file = path.join(root, '.mdp/rules', bootstrap ? '.mt-l1-bootstrap.json' : '.mt-effective-rule-bundle.json');
  await mkdir(path.dirname(indexPath(root)), { recursive: true });
  await writeFile(indexPath(root), rendered);
  await writeFile(file, JSON.stringify(manifest));
  return { file, manifest, rendered };
};

test('migrates the historical flat indexed formal v5 and bootstrap v3 without losing indexes', async () => {
  for (const bootstrap of [false, true]) for (const stage of [undefined, 'coding']) {
    const root = await createRepository();
    const old = await seedFlatIndexManifest(root, { bootstrap, stage });
    const options = layoutOptions(root, { stage, ...(bootstrap ? { bootstrap: true, domain: 'frontend' } : {}) });
    const ready = withAgents(bootstrap ? bootstrapBody({ stage }) : bundleBody({ stage,
      refs: [releaseRefs[0]], files: [{ relative_path: 'l1/frontend-l1/async.md', content: '# New rule\n' }] }));
    let replay = false;
    const fetchImpl = async (url, init) => {
      if (bootstrap && url.endsWith('/v1/effective-rule-bundles/resolve')) return response({ error: { code: 'repository_not_registered' } }, 404);
      const request = JSON.parse(init.body);
      assert.equal(request.bundle_contract, 'scope-domain-ruleset/v1');
      assert.equal(request.agents_index_contract, 'rule-set-agents-index/v1');
      assert.equal(request.known_snapshot_id, replay ? ready.snapshot.snapshot_id : undefined);
      return response(replay ? { ...ready, status: 'not_modified', files: [] } : ready);
    };
    await syncEffectiveRuleBundle({ ...options, fetchImpl });
    const current = await indexManifest(root, bootstrap);
    assert.equal(current.schema_version, bootstrap ? 'mt-l1-bootstrap-manifest/v4' : 'mt-effective-rule-bundle-manifest/v7');
    assert.equal(current.local_layout, 'scope-domain-ruleset/v1');
    assert.equal(await readFile(indexPath(root), 'utf8'), indexTable('.mdp/rules/company/fe/frontend-l1/async.md'));
    assert.equal(current.agents_indexes[0].index.content, old.manifest.agents_indexes[0].index.content);
    await assert.rejects(readFile(path.join(root, '.mdp/rules/company/async.md')), { code: 'ENOENT' });
    const before = await readFile(old.file, 'utf8');
    replay = true;
    assert.equal((await syncEffectiveRuleBundle({ ...options, fetchImpl })).status, 'not_modified');
    assert.equal(await readFile(old.file, 'utf8'), before);
  }
});

test('migrates the historical named-layout formal v5 and bootstrap v3 even with an unchanged snapshot', async () => {
  for (const bootstrap of [false, true]) {
    const root = await createRepository();
    const body = bootstrap ? bootstrapBody() : bundleBody();
    const options = layoutOptions(root, bootstrap ? { bootstrap: true, domain: 'frontend' } : {});
    let forceReady = false;
    const fetchImpl = async (url, init) => {
      if (bootstrap && url.endsWith('/v1/effective-rule-bundles/resolve')) return response({ error: { code: 'repository_not_registered' } }, 404);
      if (forceReady) assert.equal(JSON.parse(init.body).known_snapshot_id, undefined);
      return response(body);
    };
    await syncEffectiveRuleBundle({ ...options, fetchImpl });
    const manifestFile = path.join(root, '.mdp/rules', bootstrap ? '.mt-l1-bootstrap.json' : '.mt-effective-rule-bundle.json');
    const prior = await indexManifest(root, bootstrap);
    prior.schema_version = bootstrap ? 'mt-l1-bootstrap-manifest/v3' : 'mt-effective-rule-bundle-manifest/v5';
    await writeFile(manifestFile, JSON.stringify(prior));
    forceReady = true;
    await syncEffectiveRuleBundle({ ...options, fetchImpl });
    assert.equal((await indexManifest(root, bootstrap)).schema_version, bootstrap ? 'mt-l1-bootstrap-manifest/v4' : 'mt-effective-rule-bundle-manifest/v7');
    assert.equal((await indexManifest(root, bootstrap)).snapshot_id, prior.snapshot_id);
  }
});

test('historical indexed manifests protect edited AGENTS and reject swapped layout metadata', async () => {
  for (const bootstrap of [false, true]) for (const mode of ['edited', 'layout-swapped']) {
    const root = await createRepository();
    const old = await seedFlatIndexManifest(root, { bootstrap });
    if (mode === 'edited') await writeFile(indexPath(root), '# user edit\n');
    else { old.manifest.local_layout = 'scope-domain-ruleset/v1'; await writeFile(old.file, JSON.stringify(old.manifest)); }
    let called = false;
    await assert.rejects(syncEffectiveRuleBundle({ ...layoutOptions(root, bootstrap ? { bootstrap: true, domain: 'frontend' } : {}),
      fetchImpl: async () => { called = true; return response(bundleBody()); },
    }), { code: mode === 'edited' ? 'RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED' : bootstrap ? 'RULE_BUNDLE_BOOTSTRAP_MANIFEST_INVALID' : 'RULE_BUNDLE_LOCAL_MANIFEST_INVALID' });
    assert.equal(called, false);
    assert.equal(await readFile(indexPath(root), 'utf8'), mode === 'edited' ? '# user edit\n' : old.rendered);
  }
});

test('rule-set renames rerender index links while preserving index source and the source manifest hash', async () => {
  const root = await createRepository();
  const bodyFor = (name) => withAgents(bundleBody({
    refs: [{ ...releaseRefs[0], local_rule_set_name: name }],
    files: [{ relative_path: 'l1/frontend-l1/async.md', content: '# Same rule\n' }],
  }));
  const first = bodyFor('原规范名称');
  const next = bodyFor('新规范名称');
  assert.equal(first.snapshot.manifest_hash, next.snapshot.manifest_hash);
  assert.equal(first.snapshot.agents_indexes_hash, next.snapshot.agents_indexes_hash);
  assert.notEqual(first.snapshot.snapshot_id, next.snapshot.snapshot_id);
  await installBody(root, first);
  await installBody(root, next);
  assert.equal(await readFile(indexPath(root), 'utf8'), indexTable('.mdp/rules/company/fe/新规范名称/async.md'));
  await assert.rejects(readFile(path.join(root, '.mdp/rules/company/fe/原规范名称/async.md')), { code: 'ENOENT' });
  assert.equal((await indexManifest(root)).agents_indexes[0].index.content, indexTable('rules/async.md'));
});

const placementRef = {
  rule_set_id: 'rs-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  rule_set_name: 'frontend-b907', release_id: 'placement-release', scope_level: 'L2',
};
const placementSource = 'l2/frontend-b907/CQ-001.md';
const placementLocal = 'team/fe/frontend-b907/CQ-001.md';
const placementIndex = 'team/fe/frontend-b907/AGENTS.md';
const placementBody = (content = indexTable('rules/CQ-001.md'), extraFiles = []) => {
  const body = bundleBody({ version: 2, refs: [placementRef], files: [
    { relative_path: placementSource, content: '# CQ\n' }, ...extraFiles,
  ] });
  return withAgents(body, [agentsEntry(body, { content, bindings: [{ reference: 'rules/CQ-001.md', document_id: 'cq', source_path: 'rules/CQ-001.md', bundle_relative_path: placementSource }] })]);
};
// Fixed v5 fixture follows the previous on-disk contract, without using the new renderer.
const writeV5Placement = async (root, body = placementBody()) => {
  body = withAgents(bundleBody({ legacy: true, version: 2, refs: body.snapshot.release_refs,
    files: body.files.map(({ rule_set_id, release_id, ...file }) => file),
  }), body.agents_indexes);
  const oldIndexPath = `agents-index/${placementRef.rule_set_id}/AGENTS.md`;
  const oldIndexContent = body.agents_indexes[0].index.content.replace('`rules/CQ-001.md`', '`.mdp/rules/team/frontend-b907/CQ-001.md`');
  const mapping = Object.fromEntries(body.files.map(file => [`team/frontend-b907/${path.posix.basename(file.relative_path)}`, file.relative_path]));
  const managed = Object.keys(mapping).sort();
  const bySource = new Map(body.files.map(file => [file.relative_path, file]));
  const manifest = {
    schema_version: 'mt-effective-rule-bundle-manifest/v5', local_layout: 'company-team/v1',
    resolver_version: body.schema_version, snapshot_id: body.snapshot.snapshot_id,
    manifest_hash: body.snapshot.manifest_hash, repository: body.snapshot.repository,
    standard_domain: body.snapshot.repository.standard_domain, stage: null,
    release_refs: body.snapshot.release_refs, total_bytes: body.snapshot.total_bytes,
    managed_files: managed, managed_file_sources: mapping,
    managed_file_hashes: Object.fromEntries(managed.map(name => [name, bySource.get(mapping[name]).sha256])),
    managed_file_sizes: Object.fromEntries(managed.map(name => [name, bySource.get(mapping[name]).byte_size])),
    agents_index_contract: 'rule-set-agents-index/v1', agents_indexes_hash: body.snapshot.agents_indexes_hash,
    agents_indexes: body.agents_indexes, managed_agents_indexes: [oldIndexPath],
    managed_agents_index_hashes: { [oldIndexPath]: sha256Hex(oldIndexContent) },
    managed_agents_index_sizes: { [oldIndexPath]: Buffer.byteLength(oldIndexContent) },
    agents_index_warnings: [], installed_at: '2026-10-20T00:00:00.000Z',
  };
  for (const name of managed) {
    const target = path.join(root, '.mdp/rules', name);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, bySource.get(mapping[name]).content);
  }
  const oldIndex = path.join(root, '.mdp/rules', oldIndexPath);
  await mkdir(path.dirname(oldIndex), { recursive: true });
  await writeFile(oldIndex, oldIndexContent);
  await writeFile(path.join(root, '.mdp/rules/.mt-effective-rule-bundle.json'), JSON.stringify(manifest));
  return { manifest, oldIndex, oldIndexContent };
};

test('L2 indexes install in the named rule-set directory and cache v7 without touching root instructions', async () => {
  const root = await createRepository();
  await writeFile(path.join(root, 'AGENTS.md'), '# User root instructions\n');
  const body = placementBody();
  const options = { token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root };
  const receipt = await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(body) });
  assert.deepEqual(receipt.managed_agents_indexes, [placementIndex]);
  assert.equal(await readFile(path.join(root, '.mdp/rules', placementIndex), 'utf8'), indexTable('.mdp/rules/team/fe/frontend-b907/CQ-001.md'));
  const manifest = await indexManifest(root);
  assert.equal(manifest.schema_version, 'mt-effective-rule-bundle-manifest/v7');
  assert.equal(await readFile(path.join(root, 'AGENTS.md'), 'utf8'), '# User root instructions\n');
  assert.equal((await syncEffectiveRuleBundle({ ...options, fetchImpl: async (_, init) => {
    assert.equal(JSON.parse(init.body).known_snapshot_id, manifest.snapshot_id);
    return response({ ...body, status: 'not_modified', files: [] });
  } })).status, 'not_modified');
  assert.equal((await indexManifest(root)).installed_at, manifest.installed_at);
});

test('authentic flat v5 indexes migrate through full ready and then cache the new named placement', async () => {
  const root = await createRepository(); const body = placementBody();
  const old = await writeV5Placement(root, body);
  const options = { token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root };
  const receipt = await syncEffectiveRuleBundle({ ...options, fetchImpl: async (_, init) => {
    assert.equal(JSON.parse(init.body).known_snapshot_id, undefined);
    return response(body);
  } });
  assert.equal(receipt.status, 'installed');
  assert.equal((await indexManifest(root)).schema_version, 'mt-effective-rule-bundle-manifest/v7');
  assert.equal(await readFile(path.join(root, '.mdp/rules', placementIndex), 'utf8'), indexTable('.mdp/rules/team/fe/frontend-b907/CQ-001.md'));
  await assert.rejects(access(old.oldIndex), { code: 'ENOENT' });
  await assert.rejects(access(path.dirname(old.oldIndex)), { code: 'ENOENT' });
  assert.equal(await readFile(path.join(root, '.mdp/rules', placementLocal), 'utf8'), '# CQ\n');
  const before = await readFile(path.join(root, '.mdp/rules/.mt-effective-rule-bundle.json'), 'utf8');
  assert.equal((await syncEffectiveRuleBundle({ ...options, fetchImpl: async (_, init) => {
    assert.equal(JSON.parse(init.body).known_snapshot_id, body.snapshot.snapshot_id);
    return response({ ...body, status: 'not_modified', files: [] });
  } })).status, 'not_modified');
  assert.equal(await readFile(path.join(root, '.mdp/rules/.mt-effective-rule-bundle.json'), 'utf8'), before);
});

test('v5 migration protects changed legacy indexes and user-owned target aliases before any replacement', async () => {
  for (const mode of ['changed-index', 'changed-rule', 'existing-target', 'case-alias']) {
    const root = await createRepository(); const body = placementBody();
    const old = await writeV5Placement(root, body);
    const manifestBefore = await readFile(path.join(root, '.mdp/rules/.mt-effective-rule-bundle.json'), 'utf8');
    const target = mode === 'changed-index' ? old.oldIndex : mode === 'changed-rule'
      ? path.join(root, '.mdp/rules/team/frontend-b907/CQ-001.md')
      : path.join(root, '.mdp/rules/team/fe/frontend-b907', mode === 'case-alias' ? 'agents.md' : 'AGENTS.md');
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, '# User changes\n');
    let requests = 0;
    await assert.rejects(syncEffectiveRuleBundle({ token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root, fetchImpl: async () => {
      requests++; return response(body);
    } }), { code: mode.startsWith('changed-') ? 'RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED' : 'RULE_BUNDLE_LOCAL_COLLISION' });
    if (mode.startsWith('changed-')) assert.equal(requests, 0);
    assert.equal(await readFile(target, 'utf8'), '# User changes\n');
    assert.equal(await readFile(path.join(root, '.mdp/rules/.mt-effective-rule-bundle.json'), 'utf8'), manifestBefore);
    assert.equal(await readFile(old.oldIndex, 'utf8'), mode === 'changed-index' ? '# User changes\n' : old.oldIndexContent);
  }
});

test('ordinary AGENTS filenames receive stable suffixes while the L2 index owns AGENTS.md', async () => {
  const root = await createRepository();
  const body = placementBody(undefined, [
    { relative_path: 'l2/frontend-b907/one/AGENTS.md', content: '# Ordinary upper\n' },
    { relative_path: 'l2/frontend-b907/two/agents.md', content: '# Ordinary lower\n' },
  ]);
  await syncEffectiveRuleBundle({ token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root, fetchImpl: async () => response(body) });
  const manifest = await indexManifest(root);
  const extra = manifest.managed_files.filter(name => name !== placementLocal);
  assert.equal(extra.length, 2);
  assert.ok(extra.every(name => /\/agents--[a-f0-9]{16}\.md$/iu.test(name)));
  assert.ok(!manifest.managed_files.some(name => name.toLowerCase() === placementIndex.toLowerCase()));
  assert.deepEqual(new Set(await Promise.all(extra.map(name => readFile(path.join(root, '.mdp/rules', name), 'utf8')))), new Set(['# Ordinary upper\n', '# Ordinary lower\n']));
  assert.equal((await syncEffectiveRuleBundle({ token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root, fetchImpl: async () => response({ ...body, status: 'not_modified', files: [] }) })).status, 'not_modified');
});

test('v5 ordinary AGENTS rule is safely renamed before its directory receives the index', async () => {
  const root = await createRepository();
  const body = placementBody(undefined, [{ relative_path: 'l2/frontend-b907/AGENTS.md', content: '# Ordinary rule\n' }]);
  await writeV5Placement(root, body);
  await syncEffectiveRuleBundle({ token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root, fetchImpl: async () => response(body) });
  const manifest = await indexManifest(root);
  const rulePath = manifest.managed_files.find(name => /AGENTS--/.test(name));
  assert.ok(rulePath);
  assert.equal(await readFile(path.join(root, '.mdp/rules', rulePath), 'utf8'), '# Ordinary rule\n');
  assert.equal(await readFile(path.join(root, '.mdp/rules', placementIndex), 'utf8'), indexTable('.mdp/rules/team/fe/frontend-b907/CQ-001.md'));
});

test('L2 directory names must be unique and match actual source directories', async () => {
  for (const mode of ['duplicate-name', 'unsafe-name', 'mismatched-identity']) {
    const root = await createRepository();
    const ref = { rule_set_id: 'legacy-team', rule_set_name: 'same-team', release_id: 'release-a', scope_level: 'L2' };
    const refs = mode === 'duplicate-name' ? [ref, { ...ref, rule_set_id: 'other-team', release_id: 'release-b' }] : [{ ...ref, ...(mode === 'unsafe-name' ? { rule_set_name: '../outside' } : {}) }];
    const body = bundleBody({ version: 2, refs, files: [{ relative_path: `l2/${'same-team'}/rule.md`, content: '# Rule\n' }] });
    withAgents(body, [agentsEntry(body, { ruleSetId: 'legacy-team', bindings: [] })]);
    if (mode === 'mismatched-identity') body.files[0].rule_set_id = 'unrelated-team';
    await assert.rejects(syncEffectiveRuleBundle({ token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root, fetchImpl: async () => response(body) }), error => ['RULE_BUNDLE_AGENTS_INDEX_INVALID', 'RULE_BUNDLE_RELEASE_REFS_INVALID', 'RULE_BUNDLE_FILE_PATH_INVALID', 'RULE_BUNDLE_FILE_RELEASE_INVALID', 'RULE_BUNDLE_RULE_SET_NAME_COLLISION'].includes(error.code));
    await assert.rejects(access(path.join(root, '.mdp/rules/.mt-effective-rule-bundle.json')), { code: 'ENOENT' });
  }
});

test('legacy L2 identities use their verified local name rather than an ID fallback', async () => {
  const root = await createRepository();
  const ref = { rule_set_id: 'legacy-team', release_id: 'legacy-release', scope_level: 'L2', standard_domain: 'frontend', local_rule_set_name: '历史团队规范' };
  const body = bundleBody({ version: 2, refs: [ref], files: [{ relative_path: 'l2/legacy-team/rule.md', content: '# Rule\n' }] });
  withAgents(body, [agentsEntry(body, { content: '# Legacy index', bindings: [] })]);
  const receipt = await syncEffectiveRuleBundle({ token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root, fetchImpl: async () => response(body) });
  assert.deepEqual(receipt.managed_agents_indexes, ['team/fe/历史团队规范/AGENTS.md']);
});

test('5 MiB v5 index migrates with a full ready response and subscription removal cleans only managed indexes', async () => {
  const root = await createRepository();
  const prefix = indexTable('rules/CQ-001.md');
  const content = prefix + '\r\n' + 'x'.repeat(5 * 1024 * 1024 - Buffer.byteLength(prefix) - 2);
  const body = placementBody(content); const old = await writeV5Placement(root, body);
  const options = { token: 'token', repositoryLocator: 'hfe/hotel-web', repoRoot: root };
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(body) });
  assert.equal(await readFile(path.join(root, '.mdp/rules', placementIndex), 'utf8'), old.oldIndexContent.replace('.mdp/rules/team/frontend-b907/', '.mdp/rules/team/fe/frontend-b907/'));
  const own = path.join(root, '.mdp/rules/team/fe/frontend-b907/own.md'); await writeFile(own, '# User');
  const next = withAgents(bundleBody({ version: 2, refs: [releaseRefs[0]], files: [{ relative_path: 'l1/frontend-l1/rule.md', content: '# L1\n' }] }), []);
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(next) });
  await assert.rejects(access(path.join(root, '.mdp/rules', placementIndex)), { code: 'ENOENT' });
  assert.equal(await readFile(own, 'utf8'), '# User');
});

// These two v6 manifests were produced by independent shipped/local lines.
// Flat v6 reserved the team-root index path; named v6 still stored a separate
// index and allowed an ordinary AGENTS.md rule at the team root.
const writeHistoricalV6Placement = async (root, sourceBody, placement) => {
  const body = placement === 'flat-team'
    ? withAgents(bundleBody({ legacy: true, version: 2, refs: sourceBody.snapshot.release_refs,
      files: sourceBody.files.map(({ rule_set_id, release_id, ...file }) => file),
    }), sourceBody.agents_indexes)
    : sourceBody;
  const ref = body.snapshot.release_refs[0];
  const prefix = placement === 'flat-team' ? `team/${ref.rule_set_name || ref.rule_set_id}`
    : `team/${ref.standard_domain === 'frontend' ? 'fe' : 'java'}/${ref.local_rule_set_name}`;
  const targetIndex = placement === 'flat-team' ? `${prefix}/AGENTS.md` : `agents-index/${ref.rule_set_id}/AGENTS.md`;
  const occupied = new Set(placement === 'flat-team' ? [targetIndex.toLowerCase()] : []);
  const rows = body.files.map(file => {
    let basename = path.posix.basename(file.relative_path);
    let target = `${prefix}/${basename}`;
    let attempt = 0;
    while (occupied.has(target.toLowerCase())) {
      const dot = basename.lastIndexOf('.');
      basename = `${basename.slice(0, dot)}--${sha256Hex(`${file.relative_path}\0${attempt++}`).slice(0, 16)}${basename.slice(dot)}`;
      target = `${prefix}/${basename}`;
    }
    occupied.add(target.toLowerCase());
    return { ...file, target };
  });
  const indexContent = body.agents_indexes[0].index.content.replace('`rules/CQ-001.md`', `\`.mdp/rules/${prefix}/CQ-001.md\``);
  const manifest = {
    schema_version: 'mt-effective-rule-bundle-manifest/v6',
    local_layout: placement === 'flat-team' ? 'company-team/v1' : 'scope-domain-ruleset/v1',
    resolver_version: body.schema_version, snapshot_id: body.snapshot.snapshot_id,
    manifest_hash: body.snapshot.manifest_hash, repository: body.snapshot.repository,
    standard_domain: body.snapshot.repository.standard_domain, stage: null,
    release_refs: body.snapshot.release_refs, total_bytes: body.snapshot.total_bytes,
    managed_files: rows.map(row => row.target).sort(),
    managed_file_sources: Object.fromEntries(rows.map(row => [row.target, row.relative_path])),
    ...(placement === 'separate' ? { managed_file_releases: Object.fromEntries(rows.map(row => [row.target, { rule_set_id: row.rule_set_id, release_id: row.release_id }])) } : {}),
    managed_file_hashes: Object.fromEntries(rows.map(row => [row.target, row.sha256])),
    managed_file_sizes: Object.fromEntries(rows.map(row => [row.target, row.byte_size])),
    agents_index_contract: 'rule-set-agents-index/v1', agents_indexes_hash: body.snapshot.agents_indexes_hash,
    agents_indexes: body.agents_indexes, managed_agents_indexes: [targetIndex],
    managed_agents_index_hashes: { [targetIndex]: sha256Hex(indexContent) },
    managed_agents_index_sizes: { [targetIndex]: Buffer.byteLength(indexContent) },
    agents_index_warnings: [], installed_at: '2026-10-26T00:00:00.000Z',
  };
  for (const row of [...rows.map(row => ({ path: row.target, content: row.content })), { path: targetIndex, content: indexContent }]) {
    const target = path.join(root, '.mdp/rules', row.path);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, row.content);
  }
  const manifestPath = path.join(root, '.mdp/rules/.mt-effective-rule-bundle.json');
  await writeFile(manifestPath, JSON.stringify(manifest));
  return { manifest, manifestPath, targetIndex, indexContent, prefix };
};
const chineseTeamBody = () => {
  const ref = { ...placementRef, standard_domain: 'frontend', local_rule_set_name: '中文团队规范' };
  const body = bundleBody({ refs: [ref], files: [
    { relative_path: placementSource, content: '# CQ\n' },
    { relative_path: 'l2/frontend-b907/AGENTS.md', content: '# Ordinary AGENTS rule\n' },
  ] });
  return withAgents(body, [agentsEntry(body, { content: indexTable('rules/CQ-001.md'), bindings: [
    { reference: 'rules/CQ-001.md', document_id: 'cq', source_path: 'rules/CQ-001.md', bundle_relative_path: placementSource },
  ] })]);
};

test('both historical v6 placements migrate with their own ordinary AGENTS collision algorithm', async () => {
  for (const placement of ['flat-team', 'separate']) {
    const root = await createRepository(); const body = chineseTeamBody();
    const old = await writeHistoricalV6Placement(root, body, placement);
    const oldOrdinary = old.manifest.managed_files.find(name => /AGENTS/.test(name));
    assert.ok(placement === 'flat-team' ? oldOrdinary.includes('AGENTS--') : oldOrdinary.endsWith('/AGENTS.md'));
    const options = layoutOptions(root);
    await syncEffectiveRuleBundle({ ...options, fetchImpl: async (_, init) => {
      assert.equal(JSON.parse(init.body).known_snapshot_id, undefined);
      return response(body);
    } });
    const manifest = await indexManifest(root);
    assert.equal(manifest.schema_version, 'mt-effective-rule-bundle-manifest/v7');
    assert.equal(manifest.local_layout, 'scope-domain-ruleset/v1');
    assert.deepEqual(manifest.managed_agents_indexes, ['team/fe/中文团队规范/AGENTS.md']);
    assert.equal(await readFile(path.join(root, '.mdp/rules/team/fe/中文团队规范/AGENTS.md'), 'utf8'), indexTable('.mdp/rules/team/fe/中文团队规范/CQ-001.md'));
    const newOrdinary = manifest.managed_files.find(name => /AGENTS--/.test(name));
    assert.ok(newOrdinary);
    assert.equal(await readFile(path.join(root, '.mdp/rules', newOrdinary), 'utf8'), '# Ordinary AGENTS rule\n');
    if (placement === 'separate') assert.equal(old.manifest.snapshot_id, manifest.snapshot_id, 'layout-only migration does not change source snapshot');
    await assert.rejects(access(path.join(root, '.mdp/rules', old.targetIndex)), { code: 'ENOENT' });
    const before = await readFile(old.manifestPath, 'utf8');
    assert.equal((await syncEffectiveRuleBundle({ ...options, fetchImpl: async (_, init) => {
      assert.equal(JSON.parse(init.body).known_snapshot_id, body.snapshot.snapshot_id);
      return response({ ...body, status: 'not_modified', files: [] });
    } })).status, 'not_modified');
    assert.equal(await readFile(old.manifestPath, 'utf8'), before);
  }
});

test('historical v6 indexes retain local edits and reject unknown named-root targets or symlink aliases', async () => {
  for (const placement of ['flat-team', 'separate']) for (const mode of ['edited-index', 'unknown-target', 'symlink']) {
    const root = await createRepository(); const source = chineseTeamBody();
    const body = withAgents(bundleBody({ refs: source.snapshot.release_refs, files: source.files.filter(file => !file.relative_path.endsWith('/AGENTS.md')) }), source.agents_indexes);
    const old = await writeHistoricalV6Placement(root, body, placement);
    const oldIndex = path.join(root, '.mdp/rules', old.targetIndex);
    const destination = path.join(root, '.mdp/rules/team/fe/中文团队规范/AGENTS.md');
    if (mode === 'edited-index') await writeFile(oldIndex, '# user index');
    else {
      // This fixture has no ordinary AGENTS rule, so any target alias is user-owned.
      const target = destination.replace('/AGENTS.md', '/agents.MD');
      await mkdir(path.dirname(target), { recursive: true });
      if (mode === 'symlink') {
        const outside = path.join(root, 'outside.md'); await writeFile(outside, '# external'); await symlink(outside, target);
      } else await writeFile(target, '# unknown');
    }
    const before = await readFile(old.manifestPath, 'utf8');
    await assert.rejects(syncEffectiveRuleBundle({ ...layoutOptions(root), fetchImpl: async () => response(body) }), error =>
      mode === 'edited-index' ? error.code === 'RULE_BUNDLE_LOCAL_MANAGED_FILE_CHANGED'
        : ['RULE_BUNDLE_LOCAL_COLLISION', 'RULE_BUNDLE_LOCAL_SYMLINK'].includes(error.code));
    assert.equal(await readFile(old.manifestPath, 'utf8'), before);
    assert.equal(await readFile(oldIndex, 'utf8'), mode === 'edited-index' ? '# user index' : old.indexContent);
  }
});

test('named L2 indexes use per-release domains and names while L1 remains separate', async () => {
  const refs = [
    { ...releaseRefs[0], standard_domain: 'frontend', local_rule_set_name: '公司规则' },
    { rule_set_id: 'fe-team', release_id: 'fe-team@1', scope_level: 'L2', standard_domain: 'frontend', local_rule_set_name: '同名团队' },
    { rule_set_id: 'java-team', release_id: 'java-team@1', scope_level: 'L2', standard_domain: 'backend', local_rule_set_name: '同名团队' },
  ].sort((left, right) => left.rule_set_id.localeCompare(right.rule_set_id, 'en'));
  const body = bundleBody({ refs, files: refs.map(ref => ({ relative_path: `${ref.scope_level.toLowerCase()}/${ref.rule_set_id}/rule.md`, content: ref.rule_set_id })) });
  withAgents(body, refs.map(ref => agentsEntry(body, { ruleSetId: ref.rule_set_id, content: '# Index', bindings: [] })));
  const root = await createRepository();
  const receipt = await installBody(root, body);
  assert.deepEqual([...receipt.managed_agents_indexes].sort(), ['agents-index/frontend-l1/AGENTS.md', 'team/fe/同名团队/AGENTS.md', 'team/java/同名团队/AGENTS.md']);
  const next = bundleBody({ refs: refs.map(ref => ref.rule_set_id === 'fe-team' ? { ...ref, local_rule_set_name: '改名团队' } : ref), files: body.files });
  withAgents(next, body.agents_indexes);
  await installBody(root, next);
  await assert.rejects(access(path.join(root, '.mdp/rules/team/fe/同名团队/AGENTS.md')), { code: 'ENOENT' });
  assert.equal(await readFile(path.join(root, '.mdp/rules/team/fe/改名团队/AGENTS.md'), 'utf8'), '# Index');
  assert.equal(await readFile(path.join(root, '.mdp/rules/team/java/同名团队/AGENTS.md'), 'utf8'), '# Index');
});
