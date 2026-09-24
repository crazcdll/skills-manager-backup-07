import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, symlink } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { parseCliArgs } from "./mt-code-standards.mjs";

const cli = fileURLToPath(new URL("./mt-code-standards.mjs", import.meta.url));

test("parses pull options and fixes the independent execution agent to cli", () => {
  assert.deepEqual(parseCliArgs([
    "pull", "--repository", "hotel-web", "--output-dir", "/tmp/output",
    "--mis", "tester", "--json", "--non-interactive", "--execution-agent", "cli",
  ]), {
    action: "pull",
    options: {
      json: true,
      bootstrap: false,
      nonInteractive: true,
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
  assert.equal(version.stdout.trim(), "1.0.0");
});

test("the installed bin symlink still executes the CLI", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "setup-cli-bin-"));
  const linked = path.join(directory, "mt-code-standards");
  await symlink(cli, linked);
  const result = spawnSync(process.execPath, [linked, "--version"], { encoding: "utf8", env: {} });
  assert.equal(result.status, 0);
  assert.equal(result.stdout.trim(), "1.0.0");
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
    cli, "pull", "--repository", "hotel-web", "--output-dir", directory,
    "--json", "--non-interactive",
  ], { encoding: "utf8", cwd: directory, env: {} });
  assert.equal(result.status, 2);
  const body = JSON.parse(result.stdout);
  assert.equal(body.error.code, "RULE_BUNDLE_PORTABLE_MIS_REQUIRED");
  assert.equal(JSON.stringify(body).includes("token"), false);
  assert.equal(result.stderr, "");
});
