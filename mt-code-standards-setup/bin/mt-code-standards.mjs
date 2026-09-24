#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import process from "node:process";
import { createInterface } from "node:readline/promises";
import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { RuleBundleError, prepareSyncRequest } from "../scripts/resolve-effective-rules.mjs";
import { EXTERNAL_AUTH_AGENTS, syncWithOfficialSso } from "../scripts/sync-effective-rules-with-sso.mjs";

const packageInfo = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));

const HELP = `mt-code-standards ${packageInfo.version}

用法：
  mt-code-standards pull [选项]
  mt-code-standards --help
  mt-code-standards --version

pull 选项：
  --repository <名称或地址>  唯一仓库名、namespace/repository、HTTPS 或 SSH 地址
  --output-dir <目录>        输出基目录；规则写入 <目录>/.mdp/rules（默认当前目录）
  --repo-root <目录>         兼容参数：Git 探测目录；未提供 --output-dir 时也作为输出基目录
  --mis <MIS>               当前公司用户 MIS；也可使用 SSO_USER_ID
  --gateway-url <URL>       受信任的规则分发网关（高级选项）
  --pull-id <UUID>          本次拉取幂等 ID（高级选项）
  --auth-agent <标识>       保留原 Setup Runner 的认证宿主提示
  --skill-version <版本>    覆盖审计中的 Skill 版本（高级选项）
  --bootstrap               未登记仓库显式拉取公开 L1（需精确仓库地址）
  --domain <领域>            bootstrap 领域：frontend 或 backend
  --stage <阶段>             规则阶段：design、coding 或 cr
  --non-interactive         禁止 MIS 交互提示
  --json                     输出机器可读 JSON
  --help                     显示帮助

身份由用户 CIBA 票据确认，服务端记录可信用户 MIS、仓库、规则和“独立 CLI”执行环境。
`;

const argumentError = (message) => new RuleBundleError("RULE_BUNDLE_ARGUMENT_INVALID", message);

export const parseCliArgs = (argv) => {
  if (!argv.length || argv.includes("--help") || argv.includes("-h")) return { action: "help" };
  if (argv.length === 1 && ["--version", "-v"].includes(argv[0])) return { action: "version" };
  if (argv[0] !== "pull") throw argumentError(`未知命令：${argv[0]}`);
  const options = { json: false, bootstrap: false, nonInteractive: false };
  const valued = new Set([
    "--repository", "--output-dir", "--repo-root", "--mis", "--domain", "--stage",
    "--gateway-url", "--pull-id", "--auth-agent", "--skill-version", "--execution-agent",
  ]);
  for (let index = 1; index < argv.length; index += 1) {
    const key = argv[index];
    if (key === "--json") { options.json = true; continue; }
    if (key === "--bootstrap") { options.bootstrap = true; continue; }
    if (key === "--non-interactive") { options.nonInteractive = true; continue; }
    if (!valued.has(key) || index + 1 >= argv.length || argv[index + 1].startsWith("--")) {
      throw argumentError(`未知或缺值参数：${key}`);
    }
    const value = argv[index + 1];
    if (key === "--repository") options.repositoryLocator = value;
    else if (key === "--output-dir") options.outputDir = value;
    else if (key === "--repo-root") options.repoRoot = value;
    else if (key === "--mis") options.mis = value;
    else if (key === "--domain") options.domain = value;
    else if (key === "--stage") options.stage = value;
    else if (key === "--gateway-url") options.gatewayUrl = value;
    else if (key === "--pull-id") options.pullId = value;
    else if (key === "--auth-agent") {
      if (!EXTERNAL_AUTH_AGENTS.has(value)) throw argumentError(`不支持的认证宿主标识：${value}`);
      options.authAgent = value;
    }
    else if (key === "--skill-version") options.skillVersion = value;
    else if (key === "--execution-agent") {
      if (value !== "cli") throw argumentError("独立 CLI 的 --execution-agent 只能是 cli");
      options.agent = value;
    }
    index += 1;
  }
  return { action: "pull", options };
};

const promptForMis = async (environment, nonInteractive = false) => {
  const configured = String(environment.SSO_USER_ID || "").trim();
  if (configured) return configured;
  if (nonInteractive || !process.stdin.isTTY || !process.stderr.isTTY) {
    throw new RuleBundleError(
      "RULE_BUNDLE_PORTABLE_MIS_REQUIRED",
      "独立 CLI 需要通过 --mis 或 SSO_USER_ID 提供当前公司用户 MIS。",
    );
  }
  const prompt = createInterface({ input: process.stdin, output: process.stderr });
  try {
    const value = (await prompt.question("当前公司用户 MIS：")).trim();
    if (!value) {
      throw new RuleBundleError("RULE_BUNDLE_PORTABLE_MIS_REQUIRED", "MIS 不能为空。");
    }
    return value;
  } finally {
    prompt.close();
  }
};

const printError = (error, json) => {
  const code = error instanceof RuleBundleError ? error.code : "RULE_BUNDLE_UNEXPECTED";
  const message = error instanceof RuleBundleError ? error.message : "规则拉取发生未预期错误。";
  if (json) process.stdout.write(`${JSON.stringify({ ok: false, error: { code, message } })}\n`);
  else process.stderr.write(`${code}: ${message}\n`);
};

export const runCli = async ({
  argv = process.argv.slice(2),
  environment = process.env,
  prepare = prepareSyncRequest,
  sync = syncWithOfficialSso,
} = {}) => {
  let parsed;
  try {
    parsed = parseCliArgs(argv);
    if (parsed.action === "help") { process.stdout.write(HELP); return 0; }
    if (parsed.action === "version") { process.stdout.write(`${packageInfo.version}\n`); return 0; }
    const options = parsed.options;
    const skillVersion = options.skillVersion || packageInfo.version;
    await prepare({
      gatewayUrl: options.gatewayUrl,
      repositoryLocator: options.repositoryLocator,
      repoRoot: options.repoRoot,
      outputDir: options.outputDir,
      domain: options.domain,
      stage: options.stage,
      bootstrap: options.bootstrap,
      execution: { pullId: options.pullId, agent: "cli", source: "runner_explicit_v1", skillVersion },
    });
    const injectedToken = String(environment.RULE_OBSERVABILITY_USER_TOKEN || "").trim();
    const configuredMis = String(options.mis || environment.SSO_USER_ID || "").trim();
    const mis = configuredMis || (injectedToken
      ? ""
      : await promptForMis(environment, options.nonInteractive));
    const receipt = await sync({
      environment,
      options: {
        ...options,
        mis,
        agent: "cli",
        standaloneCli: true,
        skillVersion,
      },
    });
    const result = { ok: true, receipt };
    process.stdout.write(`${JSON.stringify(parsed.options.json ? result : receipt, null, parsed.options.json ? 0 : 2)}\n`);
    return 0;
  } catch (error) {
    printError(error, parsed?.options?.json === true || argv.includes("--json"));
    return 2;
  }
};

const isDirectExecution = () => {
  if (!process.argv[1]) return false;
  try {
    return realpathSync(process.argv[1]) === fileURLToPath(import.meta.url);
  } catch {
    return false;
  }
};

if (isDirectExecution()) {
  process.exitCode = await runCli();
}
