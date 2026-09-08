import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, writeFile, symlink } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  canonicalJson,
  RuleBundleError,
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
} = {}) => {
  const normalizedFiles = files.map((file) => ({
    ...file,
    sha256: file.sha256 || sha256Hex(file.content),
    byte_size: file.byte_size ?? Buffer.byteLength(file.content, "utf8"),
  })).sort((left, right) => version === 2
    ? (left.relative_path < right.relative_path ? -1 : left.relative_path > right.relative_path ? 1 : 0)
    : left.relative_path.localeCompare(right.relative_path, "en"));
  const projection = normalizedFiles.map(({ relative_path, sha256, byte_size }) => ({
    relative_path,
    sha256,
    byte_size,
  }));
  const manifestHash = sha256Hex(canonicalJson(projection));
  const repo = { ...repository, standard_domain: domain };
  const snapshotProjection = {
    ...(version === 2 ? { resolver_version: "effective-rule-bundle/v2" } : {}),
    repository_id: repo.repository_id,
    canonical_key: repo.canonical_key,
    standard_domain: repo.standard_domain,
    manifest_hash: manifestHash,
    release_refs: refs,
  };
  return {
    schema_version: `effective-rule-bundle/v${version}`,
    status,
    snapshot: {
      ...(version === 2 ? { resolver_version: "effective-rule-bundle/v2" } : {}),
      snapshot_id: sha256Hex(canonicalJson(snapshotProjection)),
      repository: repo,
      manifest_hash: manifestHash,
      release_refs: refs,
      total_bytes: normalizedFiles.reduce((sum, file) => sum + file.byte_size, 0),
    },
    files: status === "ready" ? normalizedFiles : [],
  };
};

const createRepository = async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "mt-rule-bundle-test-"));
  await mkdir(path.join(root, ".git"));
  return root;
};

test("accepts every supported locator and preserves query/hash suffixes", () => {
  const locators = [
    "https://dev.sankuai.com/code/repo-detail/hfe/hotel-web/file/list?branch=master#readme",
    "https://git.sankuai.com/hfe/hotel-web.git?ref=master",
    "ssh://git@git.sankuai.com/hfe/hotel-web.git?ref=master",
    "git@git.sankuai.com:hfe/hotel-web.git#master",
    "hfe/hotel-web?ref=master",
    "hotel-web?ref=master",
  ];
  for (const locator of locators) assert.equal(validateRepositoryLocator(locator), locator);
});

test("declares the NoCode production audience without retaining the obsolete audience", async () => {
  const skillSource = await readFile(new URL("../SKILL.md", import.meta.url), "utf8");
  const runnerSource = await readFile(new URL("./resolve-effective-rules.mjs", import.meta.url), "utf8");
  const obsoleteAudience = ["f32a", "546874"].join("");
  assert.match(skillSource, /audience:\s*\n\s*- 923a237244/);
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
  for (const locator of ["", "https://example.com/hfe/hotel-web", "../hotel-web", "hotel\nweb"]) {
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
      skill_name: "mt-code-standards-setup",
      skill_version: "v1-test",
    },
  });
  assert.equal(JSON.stringify(request).includes("short-lived-user-token"), false);
  assert.equal(receipt.status, "installed");
  assert.equal(await readFile(path.join(root, ".mdp/rules/frontend/l1/frontend-l1.md"), "utf8"), "# L1\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/frontend/l2/team-fe-l2.md"), "utf8"), "# L2\n");
  const manifest = JSON.parse(await readFile(
    path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json"),
    "utf8",
  ));
  assert.equal(manifest.snapshot_id, body.snapshot.snapshot_id);
  assert.deepEqual(manifest.managed_files, [
    "frontend/l1/frontend-l1.md",
    "frontend/l2/team-fe-l2.md",
  ]);
  assert.equal(JSON.stringify(manifest).includes("short-lived-user-token"), false);
  assert.equal(receipt.pull_id, "11111111-1111-4111-8111-111111111111");
  assert.equal(receipt.execution_agent, "codex");
});

test("requires an explicit known execution identity when supplied and defaults old callers safely", () => {
  assert.equal(normalizePullExecution().agent, "unknown");
  assert.throws(
    () => normalizePullExecution({ pullId: "11111111-1111-4111-8111-111111111111", agent: "made-up", source: "runner_explicit_v1" }),
    (error) => error.code === "RULE_BUNDLE_EXECUTION_INVALID",
  );
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

test("preserves unrelated local files inside the managed domain directory", async () => {
  const root = await createRepository();
  const customPath = path.join(root, ".mdp/rules/frontend/project/custom.md");
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

test("does not trust a stale manifest when a local managed file was changed", async () => {
  const root = await createRepository();
  const ready = bundleBody();
  await syncEffectiveRuleBundle({
    token: "token",
    repositoryLocator: "hfe/hotel-web",
    repoRoot: root,
    fetchImpl: async () => response(ready),
  });
  await writeFile(path.join(root, ".mdp/rules/frontend/l1/frontend-l1.md"), "changed\n", "utf8");
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
  await assert.rejects(readFile(path.join(root, ".mdp/rules/frontend/l1/frontend-l1.md")));
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

  const collision = path.join(root, ".mdp/rules/frontend/l1/frontend-l1.md");
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
    ["repository_not_registered", "先在规范平台登记仓库"],
    ["repository_locator_ambiguous", "namespace/repository"],
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

test("upgrades v1 ASCII files to v2 Chinese filenames and preserves user files", async () => {
  const root = await createRepository();
  const oldPath = "l1/frontend-l1/coding-standards/rules/async--.md";
  const newPath = "l1/frontend-l1/coding-standards/rules/ASYNC-异步与异常处理.MD";
  const content = "# 异步与异常处理\n保持正文。\n";
  const legacy = bundleBody({ files: [{ relative_path: oldPath, content }] });
  const next = bundleBody({ version: 2, files: [{ relative_path: newPath, content }] });
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(legacy) });
  const userFile = path.join(root, ".mdp/rules/frontend/个人补充.md");
  await writeFile(userFile, "user notes\n", "utf8");
  let request;
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async (_url, init) => {
    request = JSON.parse(init.body);
    return response(next);
  } });
  assert.equal(request.known_snapshot_id, legacy.snapshot.snapshot_id);
  assert.notEqual(next.snapshot.snapshot_id, legacy.snapshot.snapshot_id);
  assert.equal(await readFile(path.join(root, ".mdp/rules/frontend", newPath), "utf8"), content);
  await assert.rejects(readFile(path.join(root, ".mdp/rules/frontend", oldPath)));
  assert.equal(await readFile(userFile, "utf8"), "user notes\n");
  const manifestPath = path.join(root, ".mdp/rules/.mt-effective-rule-bundle.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  assert.equal(manifest.schema_version, "mt-effective-rule-bundle-manifest/v2");
  assert.equal(manifest.resolver_version, "effective-rule-bundle/v2");
  assert.deepEqual(manifest.managed_files, [`frontend/${newPath}`]);
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
  const userFile = path.join(root, ".mdp/rules/frontend/l1/async-异步.md");
  await writeFile(userFile, "user-owned\n", "utf8");
  const next = bundleBody({ version: 2, files: [{ relative_path: "l1/ASYNC-异步.md", content: "server\n" }] });
  await assert.rejects(syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(next) }),
    (error) => error.code === "RULE_BUNDLE_LOCAL_COLLISION");
  assert.equal(await readFile(userFile, "utf8"), "user-owned\n");
  assert.equal(await readFile(path.join(root, ".mdp/rules/frontend/l1/frontend-l1.md"), "utf8"), "# L1\n");
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
  await mkdir(path.join(repoRoot, ".mdp/rules/frontend/l1"), { recursive: true });
  await symlink(outside, path.join(repoRoot, ".mdp/rules/frontend/l1/规范.md"));
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

test("v1 manifest retains its original path contract during a reserved-name upgrade", { skip: process.platform === "win32" }, async () => {
  const root = await createRepository();
  const options = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(bundleBody({ files: [{ relative_path: "l1/con.md", content: "legacy\n" }] })) });
  await syncEffectiveRuleBundle({ ...options, fetchImpl: async () => response(bundleBody({ version: 2, files: [{ relative_path: "l1/_CON.md", content: "current\n" }] })) });
  await assert.rejects(readFile(path.join(root, ".mdp/rules/frontend/l1/con.md")));
  assert.equal(await readFile(path.join(root, ".mdp/rules/frontend/l1/_CON.md"), "utf8"), "current\n");
});

test("directory case upgrades preserve unmanaged siblings and only rename fully managed directories", async () => {
  const legacy = bundleBody({ files: [{ relative_path: "l1/rules/async--.md", content: "rule\n" }] });
  const next = bundleBody({ version: 2, files: [{ relative_path: "l1/Rules/ASYNC-异步.md", content: "rule\n" }] });
  for (const withUserFile of [false, true]) {
    const root = await createRepository();
    const opts = { token: "token", repositoryLocator: "hfe/hotel-web", repoRoot: root };
    await syncEffectiveRuleBundle({ ...opts, fetchImpl: async () => response(legacy) });
    const userFile = path.join(root, ".mdp/rules/frontend/l1/rules/个人.md");
    if (withUserFile) await writeFile(userFile, "user\n");
    const install = () => syncEffectiveRuleBundle({ ...opts, fetchImpl: async () => response(next) });
    if (withUserFile) {
      await assert.rejects(install(), (error) => error.code === "RULE_BUNDLE_LOCAL_COLLISION");
      assert.equal(await readFile(userFile, "utf8"), "user\n");
      assert.equal(await readFile(path.join(root, ".mdp/rules/frontend/l1/rules/async--.md"), "utf8"), "rule\n");
    } else {
      await install();
      assert.equal(await readFile(path.join(root, ".mdp/rules/frontend/l1/Rules/ASYNC-异步.md"), "utf8"), "rule\n");
    }
  }
});


test("backend v2 installs Java L1 and Spring L2 Chinese files under the backend directory", async () => {
  const root = await createRepository();
  const files = [{ relative_path: "l1/java-l1/Java-日期处理.md", content: "# Java 日期处理\n" }, { relative_path: "l2/team-java-l2/Spring-依赖注入.md", content: "# Spring 依赖注入\n" }];
  const body = bundleBody({ version: 2, domain: "backend", files, refs: [{ rule_set_id: "java-l1", release_id: "java-l1@test", scope_level: "L1" }, { rule_set_id: "team-java-l2", release_id: "team-java-l2@test", scope_level: "L2" }] });
  await syncEffectiveRuleBundle({ token: "token", repositoryLocator: "team/java-service", repoRoot: root, fetchImpl: async () => response(body) });
  for (const file of files) assert.equal(await readFile(path.join(root, ".mdp/rules/backend", file.relative_path), "utf8"), file.content);
  await assert.rejects(readFile(path.join(root, ".mdp/rules/frontend", files[0].relative_path)));
});
