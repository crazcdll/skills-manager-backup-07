import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmod, mkdtemp, readFile, symlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { parseCliArgs, runCli } from "./mt-code-standards.mjs";
import { canonicalJson, sha256Hex } from "../scripts/resolve-effective-rules.mjs";

const cli = fileURLToPath(new URL("./mt-code-standards.mjs", import.meta.url));
const packageInfo = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));

test("parses pull options and fixes the independent execution agent to cli", () => {
  assert.deepEqual(parseCliArgs([
    "pull", "--repository", "hotel-web", "--output-dir", "/tmp/output",
    "--transport", "direct", "--mis", "tester", "--json", "--non-interactive", "--execution-agent", "cli",
  ]), {
    action: "pull",
    options: {
      json: true,
      bootstrap: false,
      nonInteractive: true,
      transport: "direct",
      transportExplicit: true,
      mtcliService: "mt-code-standards",
      repositoryLocator: "hotel-web",
      outputDir: "/tmp/output",
      mis: "tester",
      agent: "cli",
    },
  });
  assert.throws(
    () => parseCliArgs(["pull", "--execution-agent", "codex"]),
    (error) => error.code === "RULE_BUNDLE_ARGUMENT_INVALID",
  );
});

test("parses the delivery stage for stage-aware backend pulls", () => {
  assert.deepEqual(parseCliArgs([
    "pull", "--repository", "hbar/java-service", "--domain", "backend", "--stage", "coding",
  ]), {
    action: "pull",
    options: {
      json: false,
      bootstrap: false,
      nonInteractive: false,
      transport: "public",
      transportExplicit: false,
      mtcliService: "mt-code-standards",
      repositoryLocator: "hbar/java-service",
      domain: "backend",
      stage: "coding",
    },
  });
});

test("help and version do not require authentication", () => {
  const help = spawnSync(process.execPath, [cli, "--help"], { encoding: "utf8", env: {} });
  assert.equal(help.status, 0);
  assert.match(help.stdout, /mt-code-standards pull/);
  assert.equal(help.stderr, "");
  const version = spawnSync(process.execPath, [cli, "--version"], { encoding: "utf8", env: {} });
  assert.equal(version.status, 0);
  assert.equal(version.stdout.trim(), packageInfo.version);
});

test("the installed bin symlink still executes the CLI", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "setup-cli-bin-"));
  const linked = path.join(directory, "mt-code-standards");
  await symlink(cli, linked);
  const result = spawnSync(process.execPath, [linked, "--version"], { encoding: "utf8", env: {} });
  assert.equal(result.status, 0);
  assert.equal(result.stdout.trim(), packageInfo.version);
});

test("parses mtcli transport options and rejects unsafe service names", () => {
  const parsed = parseCliArgs([
    "pull", "--repository", "hfe/hotel-web", "--transport", "mtcli",
    "--mtcli-service", "mt-code-standards",
  ]);
  assert.equal(parsed.options.transport, "mtcli");
  assert.equal(parsed.options.mtcliService, "mt-code-standards");
  assert.throws(
    () => parseCliArgs(["pull", "--transport", "mtcli", "--mtcli-service", "../../other"]),
    (error) => error.code === "RULE_BUNDLE_MTCLI_SERVICE_INVALID",
  );
});

test("parses public transport without accepting authentication options", () => {
  const parsed = parseCliArgs([
    "pull", "--repository", "hfe/hotel-web", "--transport", "public",
  ]);
  assert.equal(parsed.options.transport, "public");
  assert.equal(parsed.options.transportExplicit, true);
  for (const extra of [
    ["--mis", "tester"],
    ["--auth-agent", "cursor"],
    ["--bootstrap"],
  ]) {
    assert.throws(
      () => parseCliArgs(["pull", "--transport", "public", ...extra]),
      (error) => error.code === "RULE_BUNDLE_ARGUMENT_INVALID",
    );
  }
});

test("preflight rejects a missing repository before asking for MIS", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "setup-cli-no-git-"));
  const result = spawnSync(process.execPath, [
    cli, "pull", "--output-dir", directory, "--json", "--non-interactive",
  ], { encoding: "utf8", cwd: directory, env: {} });
  assert.equal(result.status, 2);
  const body = JSON.parse(result.stdout);
  assert.equal(body.error.code, "RULE_BUNDLE_REPOSITORY_REQUIRED");
  assert.equal(result.stderr, "");
});

test("non-interactive pull requires MIS only after request preflight succeeds", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "setup-cli-mis-"));
  const result = spawnSync(process.execPath, [
    cli, "pull", "--repository", "hotel-web", "--output-dir", directory, "--transport", "direct",
    "--json", "--non-interactive",
  ], { encoding: "utf8", cwd: directory, env: {} });
  assert.equal(result.status, 2);
  const body = JSON.parse(result.stdout);
  assert.equal(body.error.code, "RULE_BUNDLE_PORTABLE_MIS_REQUIRED");
  assert.equal(JSON.stringify(body).includes("token"), false);
  assert.equal(result.stderr, "");
});

test("default CLI pull uses the public endpoint without inheriting credentials", { concurrency: false }, async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "setup-cli-default-public-"));
  const content = "# Public L1\n";
  const files = [{
    relative_path: "l1/frontend-l1.md",
    content,
    sha256: sha256Hex(content),
    byte_size: Buffer.byteLength(content),
  }];
  const manifestHash = sha256Hex(canonicalJson(files.map(({ relative_path, sha256, byte_size }) => ({
    relative_path, sha256, byte_size,
  }))));
  const repository = {
    repository_id: "repo:hotel-web",
    canonical_key: "hfe/hotel-web",
    standard_domain: "frontend",
  };
  const releaseRefs = [{ rule_set_id: "frontend-l1", release_id: "frontend-l1@test", scope_level: "L1" }];
  const snapshotId = sha256Hex(canonicalJson({
    resolver_version: "effective-rule-bundle/v2",
    repository_id: repository.repository_id,
    canonical_key: repository.canonical_key,
    standard_domain: repository.standard_domain,
    manifest_hash: manifestHash,
    release_refs: releaseRefs,
  }));
  const output = [];
  const originalWrite = process.stdout.write;
  process.stdout.write = (chunk) => { output.push(String(chunk)); return true; };
  try {
    const status = await runCli({
      argv: ["pull", "--repository", "git@git.sankuai.com:HFE/Hotel-Web.git", "--output-dir", directory, "--json"],
      environment: {
        RULE_OBSERVABILITY_USER_TOKEN: "must-not-be-used",
        SSO_USER_ID: "must-not-be-used",
      },
      cwd: directory,
      fetchImpl: async (url, init) => {
        assert.match(url, /\/v1\/public\/effective-rule-bundles\/resolve$/u);
        assert.equal(init.headers.Authorization, undefined);
        assert.equal(JSON.parse(init.body).repository_locator, "hfe/hotel-web");
        return {
          ok: true,
          status: 200,
          text: async () => JSON.stringify({
            schema_version: "effective-rule-bundle/v2",
            status: "ready",
            snapshot: {
              resolver_version: "effective-rule-bundle/v2",
              snapshot_id: snapshotId,
              repository,
              manifest_hash: manifestHash,
              release_refs: releaseRefs,
              total_bytes: Buffer.byteLength(content),
            },
            files,
          }),
        };
      },
    });
    assert.equal(status, 0);
  } finally {
    process.stdout.write = originalWrite;
  }
  const result = JSON.parse(output.join(""));
  assert.equal(result.receipt.authentication_mode, "public_repository");
  assert.equal(result.receipt.authentication_route_reason, "default_public_transport");
  assert.equal(await readFile(path.join(directory, ".mdp/rules/company/frontend-l1.md"), "utf8"), content);
});

test("mtcli transport performs verified dry-run and installs without MIS or inherited user token", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "setup-cli-mtcli-"));
  const fakeBin = path.join(directory, "bin");
  const executable = path.join(fakeBin, "mtcli");
  await import("node:fs/promises").then(({ mkdir }) => mkdir(fakeBin));
  const content = "# L1 via mtcli\n";
  const files = [{
    relative_path: "l1/frontend-l1.md",
    content,
    sha256: sha256Hex(content),
    byte_size: Buffer.byteLength(content),
  }];
  const manifestHash = sha256Hex(canonicalJson(files.map(({ relative_path, sha256, byte_size }) => ({
    relative_path, sha256, byte_size,
  }))));
  const repository = {
    repository_id: "repo:hotel-web",
    canonical_key: "hfe/hotel-web",
    standard_domain: "frontend",
  };
  const releaseRefs = [{
    rule_set_id: "frontend-l1",
    release_id: "frontend-l1@test",
    scope_level: "L1",
  }];
  const snapshotId = sha256Hex(canonicalJson({
    resolver_version: "effective-rule-bundle/v2",
    repository_id: repository.repository_id,
    canonical_key: repository.canonical_key,
    standard_domain: repository.standard_domain,
    manifest_hash: manifestHash,
    release_refs: releaseRefs,
  }));
  const bundle = {
    schema_version: "effective-rule-bundle/v2",
    status: "ready",
    snapshot: {
      resolver_version: "effective-rule-bundle/v2",
      snapshot_id: snapshotId,
      repository,
      manifest_hash: manifestHash,
      release_refs: releaseRefs,
      total_bytes: Buffer.byteLength(content),
    },
    files,
  };
  const fakeSource = `#!/usr/bin/env node
const args = process.argv.slice(2);
if (process.env.RULE_OBSERVABILITY_USER_TOKEN || process.env.SSO_ACCESS_TOKEN) process.exit(41);
const value = (flag) => args[args.indexOf(flag) + 1];
const body = JSON.parse(value("--json"));
const headers = JSON.parse(value("--params"));
if (body.execution?.execution_agent !== "cli"
  || body.execution?.skill_name !== "mt-code-standards"
  || body.execution?.skill_version !== ${JSON.stringify(packageInfo.version)}) process.exit(42);
if (args.includes("--dry-run")) {
  process.stdout.write(JSON.stringify({
    auth_type: "SSO", body, dry_run: true, headers, method: "POST", query_params: {},
    target_env: "prod", timeout: 30,
    url: "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-distribution/v1/effective-rule-bundles/resolve"
  }));
} else process.stdout.write(JSON.stringify({ success: true, status_code: 200, data: ${JSON.stringify(bundle)} }));
`;
  await writeFile(executable, fakeSource, "utf8");
  await chmod(executable, 0o755);
  const result = spawnSync(process.execPath, [
    cli, "pull", "--repository", "hfe/hotel-web", "--output-dir", directory,
    "--transport", "mtcli", "--json", "--non-interactive",
  ], {
    encoding: "utf8",
    cwd: directory,
    env: {
      PATH: `${fakeBin}${path.delimiter}${process.env.PATH}`,
      RULE_OBSERVABILITY_USER_TOKEN: "must-not-reach-mtcli",
      SSO_ACCESS_TOKEN: "must-not-reach-mtcli",
    },
  });
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.receipt.authentication_mode, "mtcli_sso");
  assert.equal(output.receipt.execution_agent, "cli");
  assert.match(output.receipt.pull_id, /^[0-9a-f-]{36}$/u);
  assert.equal(
    await readFile(path.join(directory, ".mdp/rules/company/frontend-l1.md"), "utf8"),
    content,
  );
});
