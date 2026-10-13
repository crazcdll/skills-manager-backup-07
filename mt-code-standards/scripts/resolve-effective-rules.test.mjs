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
  version = 1,
  repositoryIdentity = repository,
  stage,
  dependencyHash = sha256Hex("delivery-dependency"),
} = {}) => {
  const normalizedFiles = files.map((file) => ({
    ...file,
    sha256: file.sha256 || sha256Hex(file.content),
    byte_size: file.byte_size ?? Buffer.byteLength(file.content, "utf8"),
  })).sort((left, right) => version >= 2
    ? (left.relative_path < right.relative_path ? -1 : left.relative_path > right.relative_path ? 1 : 0)
    : left.relative_path.localeCompare(right.relative_path, "en"));
  const projection = normalizedFiles.map(({ relative_path, sha256, byte_size }) => ({
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
    ...(version === 3 ? { stage, dependency_hash: dependencyHash } : {}),
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
      ...(version === 3 ? { stage, dependency_hash: dependencyHash } : {}),
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
  const normalizedFiles = files.map((file) => ({
    ...file,
    sha256: file.sha256 || sha256Hex(file.content),
    byte_size: file.byte_size ?? Buffer.byteLength(file.content, "utf8"),
  })).sort((left, right) => left.relative_path < right.relative_path ? -1 : 1);
  const manifestHash = sha256Hex(canonicalJson(normalizedFiles.map(({
    relative_path, sha256, byte_size,
  }) => ({ relative_path, sha256, byte_size }))));
  const version = stage ? 2 : 1;
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
      bootstrap: true,
      repositoryLocator: "hfe/new-web",
      repoRoot: root,
      fetchImpl: async () => response(bundleBody()),
    }),
    (error) => error.code === "RULE_BUNDLE_PUBLIC_BOOTSTRAP_UNSUPPORTED",
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
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/frontend-l1.md"), "utf8"), "# L1\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/team/team-fe-l2/team-fe-l2.md"), "utf8"), "# L2\n");
  const manifest = JSON.parse(await readFile(
    path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"),
    "utf8",
  ));
  assert.equal(manifest.snapshot_id, body.snapshot.snapshot_id);
  assert.deepEqual(manifest.managed_files, [
    "company/frontend-l1.md",
    "team/team-fe-l2/team-fe-l2.md",
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

test("sends an explicit stage and installs a verified v3 bundle with dependency context", async () => {
  const root = await createRepository();
  const body = bundleBody({ version: 3, stage: "coding" });
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
  assert.equal(manifest.schema_version, "mt-effective-rule-bundle-manifest/v4");
  assert.equal(manifest.resolver_version, "effective-rule-bundle/v3");
  assert.equal(manifest.stage, "coding");
  assert.equal(manifest.dependency_hash, body.snapshot.dependency_hash);
});

test("does not reuse a snapshot across stages and removes files from the previous stage", async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  const coding = bundleBody({
    version: 3,
    stage: "coding",
    files: [{ relative_path: "l1/java-l1-compact/compact.md", content: "# compact\n" }],
  });
  await syncEffectiveRuleBundle({ ...options, stage: "coding", fetchImpl: async () => response(coding) });
  const customPath = path.join(root, ".mdp/rules/project/custom.md");
  await mkdir(path.dirname(customPath), { recursive: true });
  await writeFile(customPath, "# custom\n", "utf8");
  const review = bundleBody({
    version: 3,
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
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/compact.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/full.md"), "utf8"), "# full\n");
  assert.equal(await readFile(customPath, "utf8"), "# custom\n");
});

test("treats delivery policy changes as new staged snapshots even when files are unchanged", async () => {
  const root = await createRepository();
  const options = {
    token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root, stage: "coding",
  };
  const first = bundleBody({ version: 3, stage: "coding", dependencyHash: sha256Hex("policy-a") });
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(first) });
  const second = bundleBody({ version: 3, stage: "coding", dependencyHash: sha256Hex("policy-b") });
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
      stage: "coding", fetchImpl: async () => response(bundleBody({ version: 2 })),
    }),
    (error) => error.code === "RULE_BUNDLE_RESPONSE_INVALID",
  );
  const mismatchRoot = await createRepository();
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: mismatchRoot,
      stage: "coding", fetchImpl: async () => response(bundleBody({ version: 3, stage: "cr" })),
    }),
    (error) => error.code === "RULE_BUNDLE_STAGE_MISMATCH",
  );
});

test("upgrades one registered repository to a combined dual-domain bundle without losing files", async () => {
  const root = await createRepository();
  const single = bundleBody({ version: 2 });
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(single) });
  const customPath = path.join(root, ".mdp/rules/project/custom.md");
  await mkdir(path.dirname(customPath), { recursive: true });
  await writeFile(customPath, "# custom\n", "utf8");

  const combined = bundleBody({
    version: 2,
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
  const frontend = bundleBody({ version: 2 });
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(frontend) });
  const customPath = path.join(root, ".mdp/rules/project/custom.md");
  await mkdir(path.dirname(customPath), { recursive: true });
  await writeFile(customPath, "# custom\n", "utf8");

  const backend = bundleBody({
    version: 2,
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
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/frontend-l1.md")));
  await assert.rejects(readFile(path.join(root, ".mdp/rules/team/team-fe-l2/team-fe-l2.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/java-current.md"), "utf8"), "# Java L1\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/team/team-java-l2/team-current.md"), "utf8"), "# Java L2\n");
  assert.equal(await readFile(customPath, "utf8"), "# custom\n");

  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const installed = await readFile(manifestPath, "utf8");
  const manifest = JSON.parse(installed);
  assert.equal(manifest.standard_domain, "backend");
  assert.deepEqual(manifest.managed_files, [
    "company/java-current.md",
    "team/team-java-l2/team-current.md",
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
    version: 2,
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
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(dual) });
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const legacyFlatManifest = JSON.parse(await readFile(manifestPath, "utf8"));
  legacyFlatManifest.schema_version = "mt-effective-rule-bundle-manifest/v3";
  await writeFile(manifestPath, `${JSON.stringify(legacyFlatManifest, null, 2)}\n`, "utf8");

  const backend = bundleBody({
    version: 2,
    domain: "backend",
    files: [{ relative_path: "l1/java-l1/java-current.md", content: "# Java current\n" }],
    refs: [{ rule_set_id: "java-l1", release_id: "java-l1@current", scope_level: "L1" }],
  });
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(backend) });
  for (const removed of [
    "company/frontend-old.md",
    "company/java-old.md",
    "team/team-fe-l2/frontend-team-old.md",
    "team/team-java-l2/java-team-old.md",
  ]) {
    await assert.rejects(readFile(path.join(root, ".mdp/rules", removed)));
  }
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/java-current.md"), "utf8"), "# Java current\n");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  assert.equal(manifest.schema_version, "mt-effective-rule-bundle-manifest/v4");
  assert.equal(manifest.standard_domain, "backend");
  assert.deepEqual(manifest.managed_files, ["company/java-current.md"]);
});

test("changes legacy v1 and v2 domain-directory manifests to backend without leaving old managed files", async () => {
  for (const version of [1, 2]) {
    const root = await createRepository();
    const frontend = bundleBody({
      version,
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
      version: 2,
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
    assert.equal(await readFile(path.join(root, ".mdp/rules/company/current.md"), "utf8"), "# Java current\n");
  }
});

test("keeps the frontend installation unchanged when a backend replacement is invalid or collides", async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(bundleBody({ version: 2 })) });
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const frontendPath = path.join(root, ".mdp/rules/company/frontend-l1.md");
  const originalManifest = await readFile(manifestPath, "utf8");
  const originalFrontend = await readFile(frontendPath, "utf8");

  const invalid = bundleBody({
    version: 2,
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

  const collisionPath = path.join(root, ".mdp/rules/company/java.md");
  await writeFile(collisionPath, "# user owned\n", "utf8");
  const valid = bundleBody({
    version: 2,
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
  assert.equal(await readFile(path.join(currentDirectory, ".mdp/rules/company/frontend-l1.md"), "utf8"), "# L1\n");
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
  const ready = bundleBody({ version: 2 });
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hotel-web", cwd: outputRoot,
    fetchImpl: async () => response(ready),
  });
  let request;
  const receipt = await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hotel-web", cwd: outputRoot,
    fetchImpl: async (_url, init) => {
      request = JSON.parse(init.body);
      return response(bundleBody({ version: 2, status: "not_modified" }));
    },
  });
  assert.equal(request.known_snapshot_id, ready.snapshot.snapshot_id);
  assert.equal(receipt.status, "not_modified");
});

test("refuses to replace another repository in the same output directory", async () => {
  const outputRoot = await mkdtemp(path.join(os.tmpdir(), "setup-repository-conflict-"));
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hotel-web", cwd: outputRoot,
    fetchImpl: async () => response(bundleBody({ version: 2 })),
  });
  const original = await readFile(path.join(outputRoot, ".mdp/rules/company/frontend-l1.md"), "utf8");
  const otherRepository = {
    repository_id: "repo:other-web",
    canonical_key: "hfe/other-web",
    standard_domain: "frontend",
  };
  await assert.rejects(
    syncEffectiveRuleBundle({
      token: "token", repositoryLocator: "other-web", cwd: outputRoot,
      fetchImpl: async () => response(bundleBody({ version: 2, repositoryIdentity: otherRepository })),
    }),
    (error) => error.code === "RULE_BUNDLE_REPOSITORY_CONFLICT",
  );
  assert.equal(await readFile(path.join(outputRoot, ".mdp/rules/company/frontend-l1.md"), "utf8"), original);
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

test("migrates a verified domain tree to the flat company and team layout", async () => {
  const root = await createRepository();
  const ready = bundleBody({
    version: 2,
    files: [
      { relative_path: "l1/frontend-l1/旧目录/基础规范.md", content: "# L1\n" },
      { relative_path: "l2/team-fe-l2/旧目录/团队规范.md", content: "# L2\n" },
    ],
  });
  const oldFiles = ready.files;
  const legacyManaged = oldFiles.map((file) => `frontend/${file.relative_path}`);
  const oldManifest = {
    schema_version: "mt-effective-rule-bundle-manifest/v2",
    resolver_version: "effective-rule-bundle/v2",
    snapshot_id: ready.snapshot.snapshot_id,
    manifest_hash: ready.snapshot.manifest_hash,
    repository,
    standard_domain: "frontend",
    release_refs: ready.snapshot.release_refs,
    total_bytes: ready.snapshot.total_bytes,
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
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/基础规范.md"), "utf8"), "# L1\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/team/team-fe-l2/团队规范.md"), "utf8"), "# L2\n");
  assert.equal(await readFile(userFile, "utf8"), "keep\n");
  await assert.rejects(readFile(path.join(root, ".mdp/rules/frontend/l1/frontend-l1/旧目录/基础规范.md")));
});

test("keeps one flat company file per L1 source when source basenames collide", async () => {
  const root = await createRepository();
  const ready = bundleBody({
    version: 2,
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
  const baseContent = await readFile(path.join(root, ".mdp/rules/company/README.md"), "utf8");
  const suffixed = manifest.managed_files.find((file) => file !== "company/README.md");
  assert.match(suffixed, /^company\/README--[a-f0-9]{16}\.md$/);
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
  const managedPath = path.join(root, ".mdp/rules/company/frontend-l1.md");
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
    version: 2,
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
    version: 2,
    refs: canonicalRefs,
    files: [{ relative_path: "l1/frontend-l1/base.md", content: "# L1\n" }, {
      relative_path: "l2/billing-settlement-frontend/STYLE-01-promise.md",
      content: "# Canonical L2\n",
    }],
  });
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(canonical) });

  const oldPath = path.join(root, ".mdp/rules/team/legacy-team-l2/STYLE-01-old.md");
  const newPath = path.join(root, ".mdp/rules/team/billing-settlement-frontend/STYLE-01-promise.md");
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
      fetchImpl: async () => response(bundleBody({ version: 2, refs: invalidRefs })),
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
        fetchImpl: async () => response(bundleBody({ version: 2, files, refs: sortedRefs })),
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
    version: 2,
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
    await readFile(path.join(root, ".mdp/rules/team", maxLengthName, "STYLE-01-safe.md"), "utf8"),
    "# Canonical\n",
  );
  assert.equal(
    await readFile(path.join(root, ".mdp/rules/team/team-fe-l2/legacy.md"), "utf8"),
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
    version: 2,
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
    managedPath.startsWith("team/billing-settlement-frontend/")
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
        fetchImpl: async () => response(bundleBody({ version: 2, refs })),
      }),
      (error) => error.code === "RULE_BUNDLE_RELEASE_REFS_INVALID",
    );
  }
});

test("keeps the previous bundle when staging cannot be created", async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  const initial = bundleBody({ version: 2 });
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(initial) });
  const rulesRoot = path.join(root, ".mdp/rules");
  const manifestPath = path.join(rulesRoot, ".mt-effective-rule-bundle.json");
  const managedPath = path.join(rulesRoot, "company/frontend-l1.md");
  const manifestBefore = await readFile(manifestPath, "utf8");
  const managedBefore = await readFile(managedPath, "utf8");
  const next = bundleBody({
    version: 2,
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
  await assert.rejects(readFile(path.join(rulesRoot, "company/next.md")));
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
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/frontend-l1.md")));
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

  const collision = path.join(root, ".mdp/rules/company/frontend-l1.md");
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
    bootstrap: true,
    fetchImpl: async (url, init) => {
      calls.push({ url, body: JSON.parse(init.body) });
      if (url.endsWith("/v1/effective-rule-bundles/resolve")) {
        return response({ error: { code: "repository_not_registered" } }, 404);
      }
      return response(bootstrap);
    },
  });
  assert.deepEqual(calls.map((call) => call.url.split("/").slice(-3).join("/")), [
    "v1/effective-rule-bundles/resolve",
    "v1/l1-rule-bundles/bootstrap",
  ]);
  assert.deepEqual(calls[1].body, {
    repository_locator: "hfe/new-web",
    standard_domain: "frontend",
  });
  assert.equal(receipt.schema_version, "mt-l1-bootstrap-install/v1");
  assert.equal(receipt.mode, "l1_bootstrap");
  assert.equal(receipt.domain_source, "git_tracked_evidence");
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/async.md"), "utf8"), "# L1\n");
  const manifest = JSON.parse(await readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json"), "utf8"));
  assert.equal(manifest.schema_version, "mt-l1-bootstrap-manifest/v2");
  await assert.rejects(readFile(path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json")));
  let replayRequest;
  const replay = await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/new-web",
    repoRoot: root,
    bootstrap: true,
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

test("forwards stage to bootstrap and requires a matching v2 bootstrap response", async () => {
  const root = await createTrackedRepository({ "pom.xml": "<project />\n", "src/App.java": "class App {}\n" });
  const requests = [];
  const body = bootstrapBody({ domain: "backend", stage: "design" });
  const receipt = await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/new-java",
    repoRoot: root,
    bootstrap: true,
    stage: "design",
    fetchImpl: async (url, init) => {
      requests.push(JSON.parse(init.body));
      return url.endsWith("/v1/effective-rule-bundles/resolve")
        ? response({ error: { code: "repository_not_registered" } }, 404)
        : response(body);
    },
  });
  assert.equal(requests[0].stage, "design");
  assert.equal(requests[1].stage, "design");
  assert.equal(receipt.stage, "design");
  const manifest = JSON.parse(await readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json"), "utf8"));
  assert.equal(manifest.schema_version, "mt-l1-bootstrap-manifest/v2");
  assert.equal(manifest.bundle_schema, "l1-bootstrap-bundle/v2");
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
      bootstrap: true,
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
  assert.equal(calls, 2);
  await assert.rejects(readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json")));
});

test("a formal effective bundle atomically replaces the isolated bootstrap manifest", async () => {
  const root = await createTrackedRepository({ "src/App.tsx": "export default null;\n" });
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hfe/new-web", repoRoot: root, bootstrap: true,
    fetchImpl: async (url) => url.endsWith("/v1/effective-rule-bundles/resolve")
      ? response({ error: { code: "repository_not_registered" } }, 404)
      : response(bootstrapBody()),
  });
  const formal = bundleBody({ version: 2, files: [{
    relative_path: "l1/frontend-l1/current.md", content: "# Current\n",
  }], refs: [{ rule_set_id: "frontend-l1", release_id: "frontend-l1@current", scope_level: "L1" }] });
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hfe/new-web", repoRoot: root,
    fetchImpl: async () => response(formal),
  });
  await assert.rejects(readFile(path.join(root, ".mdp/rules/.mt-l1-bootstrap.json")));
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/async.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/current.md"), "utf8"), "# Current\n");
  assert.equal(JSON.parse(await readFile(
    path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"), "utf8",
  )).schema_version, "mt-effective-rule-bundle-manifest/v4");
});

test("a dual-domain formal bundle replaces a backend bootstrap even when its primary domain is frontend", async () => {
  const root = await createTrackedRepository({
    "pom.xml": "<project/>\n",
    "src/main/java/Test.java": "class Test {}\n",
  });
  await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "hfe/new-mixed", repoRoot: root, bootstrap: true,
    fetchImpl: async (url) => url.endsWith("/v1/effective-rule-bundles/resolve")
      ? response({ error: { code: "repository_not_registered" } }, 404)
      : response(bootstrapBody({
        domain: "backend",
        files: [{ relative_path: "l1/java-l1/bootstrap-java.md", content: "# Bootstrap Java\n" }],
      })),
  });
  const formal = bundleBody({
    version: 2,
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
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/bootstrap-java.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/frontend-current.md"), "utf8"), "# Frontend\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/java-current.md"), "utf8"), "# Java\n");
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
      token: "token", repositoryLocator: "team/mixed", repoRoot: mixed, bootstrap: true, fetchImpl: notRegistered,
    }),
    (error) => error.code === "RULE_BUNDLE_DOMAIN_CONFIRMATION_REQUIRED"
      && error.message.includes('"classification"') === false
      && error.message.includes("src/App.tsx"),
  );
  const receipt = await syncEffectiveRuleBundle({
    token: "token", repositoryLocator: "team/mixed", repoRoot: mixed,
    domain: "backend", bootstrap: true, fetchImpl: notRegistered,
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

test("upgrades v1 ASCII files to v2 Chinese filenames and preserves user files", async () => {
  const root = await createRepository();
  const oldPath = "l1/frontend-l1/coding-standards/rules/async--.md";
  const newPath = "l1/frontend-l1/coding-standards/rules/ASYNC-异步与异常处理.MD";
  const content = "# 异步与异常处理\n保持正文。\n";
  const legacy = bundleBody({ files: [{ relative_path: oldPath, content }] });
  const next = bundleBody({ version: 2, files: [{ relative_path: newPath, content }] });
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
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/ASYNC-异步与异常处理.MD"), "utf8"), content);
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/async--.md")));
  assert.equal(await readFile(userFile, "utf8"), "user notes\n");
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  assert.equal(manifest.schema_version, "mt-effective-rule-bundle-manifest/v4");
  assert.equal(manifest.resolver_version, "effective-rule-bundle/v2");
  assert.deepEqual(manifest.managed_files, ["company/ASYNC-异步与异常处理.MD"]);
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
  const userFile = path.join(root, ".mdp/rules/company/async-异步.md");
  await writeFile(userFile, "user-owned\n", "utf8");
  const next = bundleBody({ version: 2, files: [{ relative_path: "l1/ASYNC-异步.md", content: "server\n" }] });
  await assert.rejects(syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(next) }),
    (error) => error.code === "RULE_BUNDLE_LOCAL_COLLISION");
  assert.equal(await readFile(userFile, "utf8"), "user-owned\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/frontend-l1.md"), "utf8"), "# L1\n");
});

test("rejects unsafe v2 paths, Unicode-equivalent duplicates and symlink targets", async () => {
  const options = { token: "token", repositoryLocator: "hfe/hotel-web" };
  for (const relative_path of ["../规范.md", "l1/CON.md", "l1/规范:异步.md", "l1/\u202e规范.md", "l1/规范\u0000.md", `l1/${"中".repeat(80)}.md`]) {
    const repoRoot = await createRepository();
    await assert.rejects(syncEffectiveRuleBundle({ ...options, repoRoot, fetchImpl: async () => response(bundleBody({ version: 2, files: [{ relative_path, content: "x" }] })) }),
      (error) => error.code === "RULE_BUNDLE_FILE_PATH_INVALID");
  }
  const repoRoot = await createRepository();
  const duplicates = bundleBody({ version: 2, files: ["l1/Café.md", "l1/Cafe\u0301.md"].map((relative_path) => ({ relative_path, content: "x" })) });
  await assert.rejects(syncEffectiveRuleBundle({ ...options, repoRoot, fetchImpl: async () => response(duplicates) }),
    (error) => error.code === "RULE_BUNDLE_FILE_DUPLICATE");
  const caseAliases = bundleBody({ version: 2, files: ["l1/Straße.md", "l1/STRASSE.md"].map((relative_path) => ({ relative_path, content: "x" })) });
  await assert.rejects(syncEffectiveRuleBundle({ ...options, repoRoot, fetchImpl: async () => response(caseAliases) }),
    (error) => error.code === "RULE_BUNDLE_FILE_DUPLICATE");
  const directoryAliases = bundleBody({ version: 2, files: ["l1/Rules/甲.md", "l1/rules/乙.md"].map((relative_path) => ({ relative_path, content: "x" })) });
  await assert.rejects(syncEffectiveRuleBundle({ ...options, repoRoot, fetchImpl: async () => response(directoryAliases) }),
    (error) => error.code === "RULE_BUNDLE_FILE_DUPLICATE");
  const outside = path.join(repoRoot, "outside.md");
  await writeFile(outside, "outside\n", "utf8");
  await mkdir(path.join(repoRoot, ".mdp/rules/company"), { recursive: true });
  await symlink(outside, path.join(repoRoot, ".mdp/rules/company/规范.md"));
  await assert.rejects(syncEffectiveRuleBundle({ ...options, repoRoot, fetchImpl: async () => response(bundleBody({ version: 2, files: [{ relative_path: "l1/规范.md", content: "server" }] })) }),
    (error) => error.code === "RULE_BUNDLE_LOCAL_SYMLINK");
  assert.equal(await readFile(outside, "utf8"), "outside\n");
});

test("v2 rejects a missing or inconsistent resolver version and cannot reuse a v1 snapshot identity", async () => {
  const valid = bundleBody({ version: 2 });
  const legacy = bundleBody();
  for (const resolver_version of [null, undefined, "effective-rule-bundle/v1"]) {
    const body = { ...valid, snapshot: { ...valid.snapshot, resolver_version } };
    await assert.rejects(syncEffectiveRuleBundle({ token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: await createRepository(), fetchImpl: async () => response(body) }),
      (error) => error.code === "RULE_BUNDLE_RESPONSE_INVALID");
  }
  const wrongIdentity = { ...valid, snapshot: { ...valid.snapshot, snapshot_id: legacy.snapshot.snapshot_id } };
  await assert.rejects(syncEffectiveRuleBundle({ token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: await createRepository(), fetchImpl: async () => response(wrongIdentity) }),
    (error) => error.code === "RULE_BUNDLE_SNAPSHOT_HASH_MISMATCH");
});

test("reserved-name upgrades keep the flat local path contract", { skip: process.platform === "win32" }, async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(bundleBody({ files: [{ relative_path: "l1/con.md", content: "legacy\n" }] })) });
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(bundleBody({ version: 2, files: [{ relative_path: "l1/_CON.md", content: "current\n" }] })) });
  await assert.rejects(readFile(path.join(root, ".mdp/rules/company/con.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/_CON.md"), "utf8"), "current\n");
});

test("flat layout removes source directories and preserves unrelated company files", async () => {
  const legacy = bundleBody({ files: [{ relative_path: "l1/rules/async--.md", content: "rule\n" }] });
  const next = bundleBody({ version: 2, files: [{ relative_path: "l1/Rules/ASYNC-异步.md", content: "rule\n" }] });
  for (const withUserFile of [false, true]) {
    const root = await createRepository();
    const opts = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
    await syncEffectiveRuleBundle({ ...opts, fetchImpl: async () => response(legacy) });
    const userFile = path.join(root, ".mdp/rules/company/个人.md");
    if (withUserFile) await writeFile(userFile, "user\n");
    await syncEffectiveRuleBundle({ ...opts, fetchImpl: async () => response(next) });
    await assert.rejects(readFile(path.join(root, ".mdp/rules/company/async--.md")));
    assert.equal(await readFile(path.join(root, ".mdp/rules/company/ASYNC-异步.md"), "utf8"), "rule\n");
    if (withUserFile) assert.equal(await readFile(userFile, "utf8"), "user\n");
  }
});


test("backend v2 installs Java L1 and Spring L2 Chinese files under the backend directory", async () => {
  const root = await createRepository();
  const files = [{ relative_path: "l1/java-l1/Java-日期处理.md", content: "# Java 日期处理\n" }, { relative_path: "l2/team-java-l2/Spring-依赖注入.md", content: "# Spring 依赖注入\n" }];
  const body = bundleBody({ version: 2, domain: "backend", files, refs: [{ rule_set_id: "java-l1", release_id: "java-l1@test", scope_level: "L1" }, { rule_set_id: "team-java-l2", release_id: "team-java-l2@test", scope_level: "L2" }] });
  await syncEffectiveRuleBundle({ token: "token", repositoryLocator: "team/java-service", repoRoot: root, fetchImpl: async () => response(body) });
  assert.equal(await readFile(path.join(root, ".mdp/rules/company/Java-日期处理.md"), "utf8"), files[0].content);
  assert.equal(await readFile(path.join(root, ".mdp/rules/team/team-java-l2/Spring-依赖注入.md"), "utf8"), files[1].content);
  await assert.rejects(readFile(path.join(root, ".mdp/rules/frontend/Java-日期处理.md")));
});
