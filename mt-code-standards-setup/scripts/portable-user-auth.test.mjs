import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { access, mkdtemp, mkdir, rm, stat, symlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { getPortableUserToken, minimumVersionSatisfied, resolveCurrentNodeNpmRoot } from "./portable-user-auth.mjs";

const fakeProviderRoot = async (version = "1.2.0") => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-portable-provider-"));
  const shared = path.join(root, "@it", "oa-skills", "node_modules", "@it", "oa-skills-shared");
  await mkdir(shared, { recursive: true });
  await writeFile(path.join(shared, "package.json"), JSON.stringify({ version }));
  return root;
};

test("requires oa-skills-shared 1.2.0 or newer", () => {
  assert.equal(minimumVersionSatisfied("1.1.14"), false);
  assert.equal(minimumVersionSatisfied("1.2.0-beta.1"), false);
  assert.equal(minimumVersionSatisfied("1.2.0"), true);
  assert.equal(minimumVersionSatisfied("2.0.0"), true);
});

test("resolves npm root through the npm CLI belonging to the current Node", async () => {
  const globalRoot = await resolveCurrentNodeNpmRoot(process.env);
  assert.equal(path.isAbsolute(globalRoot), true);
  assert.equal(globalRoot.includes(path.join("lib", "node_modules")), true);
});

test("uses fixed portable CIBA options and removes its isolated cache directory", async () => {
  const root = await fakeProviderRoot();
  const temporaryDirectory = await mkdtemp(path.join(os.tmpdir(), "setup-portable-cache-"));
  let initialization;
  const token = await getPortableUserToken({
    mis: "zhangce07", environment: {}, npmRootResolver: async () => root,
    moduleLoader: async () => ({
      initSsoAuth: async (...args) => {
        initialization = args;
        return {
          authenticate: async () => { await writeFile(args[2].cacheFile, "temporary-secret"); return { token: "portable-token" }; },
          clearCache() {},
        };
      },
    }),
    makeTemporaryDirectory: async () => temporaryDirectory,
  });
  assert.equal(token, "portable-token");
  assert.equal(initialization[0], "mt-code-standards-setup");
  assert.equal(initialization[1], "zhangce07");
  assert.equal(initialization[2].targetClientId, "923a237244");
  assert.equal(initialization[2].ssoStrategy, "sso-ciba");
  assert.equal(path.dirname(initialization[2].cacheFile), temporaryDirectory);
  await assert.rejects(access(temporaryDirectory));
});

test("sets the temporary auth directory to mode 0700 before authentication", async () => {
  const root = await fakeProviderRoot();
  const temporaryDirectory = await mkdtemp(path.join(os.tmpdir(), "setup-portable-mode-"));
  await getPortableUserToken({
    mis: "zhangce07", npmRootResolver: async () => root,
    moduleLoader: async () => ({
      initSsoAuth: async (_skill, _mis, options) => ({
        authenticate: async () => {
          assert.equal((await stat(path.dirname(options.cacheFile))).mode & 0o777, 0o700);
          return { token: "portable-token" };
        },
      }),
    }),
    makeTemporaryDirectory: async () => temporaryDirectory,
  });
});

test("returns a structured provider requirement for an old shared package", async () => {
  const root = await fakeProviderRoot("1.1.14");
  await assert.rejects(
    getPortableUserToken({ mis: "zhangce07", npmRootResolver: async () => root }),
    (error) => error.code === "PORTABLE_AUTH_PROVIDER_REQUIRED" && error.message.includes("1.1.14"),
  );
});

test("invalidates a token when the isolated cache directory cannot be removed", async () => {
  const root = await fakeProviderRoot();
  const temporaryDirectory = await mkdtemp(path.join(os.tmpdir(), "setup-portable-cleanup-"));
  await assert.rejects(
    getPortableUserToken({
      mis: "zhangce07",
      npmRootResolver: async () => root,
      moduleLoader: async () => ({
        initSsoAuth: async () => ({ authenticate: async () => ({ token: "must-not-escape" }) }),
      }),
      makeTemporaryDirectory: async () => temporaryDirectory,
      removeTemporaryDirectory: async () => { throw new Error("simulated cleanup failure"); },
    }),
    (error) => error.code === "PORTABLE_AUTH_CLEANUP_FAILED" && !error.message.includes("must-not-escape"),
  );
  await rm(temporaryDirectory, { recursive: true, force: true });
});

test("the helper CLI reports structured errors without starting CIBA", () => {
  const helper = fileURLToPath(new URL("./portable-user-auth.mjs", import.meta.url));
  const result = spawnSync(process.execPath, [helper], { encoding: "utf8", env: {} });
  assert.equal(result.status, 2);
  assert.deepEqual(JSON.parse(result.stdout), {
    error: {
      code: "PORTABLE_AUTH_MIS_REQUIRED",
      message: "便携 SSO CIBA 需要当前公司用户 MIS；请通过 --mis 或 SSO_USER_ID 提供登录提示。",
    },
  });
  assert.equal(result.stderr, "");
});

test("the helper CLI runs through a symbolic link", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "setup-portable-symlink-"));
  const helper = path.join(root, "portable-user-auth.mjs");
  await symlink(fileURLToPath(new URL("./portable-user-auth.mjs", import.meta.url)), helper);
  const result = spawnSync(process.execPath, [helper], { encoding: "utf8", env: {} });
  assert.equal(result.status, 2);
  assert.equal(JSON.parse(result.stdout).error.code, "PORTABLE_AUTH_MIS_REQUIRED");
});
