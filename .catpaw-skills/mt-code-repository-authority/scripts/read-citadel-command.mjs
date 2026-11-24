#!/usr/bin/env node

import { spawnSync } from "node:child_process";

const token = process.env.CITADEL_SOURCE_TOKEN;
if (!/^AT_FOR_GW_BASE64_[A-Za-z0-9+/]+={0,2}$/u.test(String(token ?? ""))) {
  process.stderr.write("citadel_auth_failed\n");
  process.exitCode = 1;
} else {
  const env = { ...process.env };
  delete env.CITADEL_SOURCE_TOKEN;
  delete env.SSO_CIBA_TOKEN;
  const result = spawnSync("oa-skills", [
    ...process.argv.slice(2), "--token", token,
  ], { env, stdio: ["ignore", "pipe", "pipe"], maxBuffer: 20 * 1024 * 1024 });
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  process.exitCode = result.status ?? 1;
}
