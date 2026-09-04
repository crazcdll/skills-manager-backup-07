#!/usr/bin/env node
"use strict";

const { accessSync, constants, existsSync } = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const OA_SKILLS_PACKAGE = "@it/oa-skills@latest";
const CALENDAR_REGISTRY = "https://r.npm.sankuai.com";
const REQUIRED_FEATURES = [
  "status.strict",
  "raw.requiredPayload",
  "writes.noReplay",
  "time.strictIana",
  "search.pagination",
  "busy.verifiedPayload",
  "identity.numericValidated",
  "update.completeTimeRange",
  "reminder.positiveMinutes",
  "conflicts.timeZone",
  "busyAnalysis.currentScheduleId",
  "participantTimeZone.statusComplete",
  "reminder.personal",
  "freeBusy.canSet",
  "feedback.attendee",
  "meetingRoom.transfer.handoverEventId",
  "meetingRoom.recommend",
  "meetingRoom.merge",
  "schedule.recurrence",
  "schedule.recurrence.editBlocked",
  "schedule.groupchatAssociation",
];

function isWindows(platform = process.platform) {
  return platform === "win32";
}

function pathApi(platform = process.platform) {
  return isWindows(platform) ? path.win32 : path.posix;
}

function pathDelimiter(platform = process.platform) {
  return isWindows(platform) ? ";" : ":";
}

function isExecutable(filePath) {
  if (!filePath || !existsSync(filePath)) return false;
  if (isWindows()) return true;
  try {
    accessSync(filePath, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function resolveFromPath(command) {
  const pathEntries = (process.env.PATH || "").split(pathDelimiter()).filter(Boolean);
  const extensions = isWindows()
    ? (process.env.PATHEXT || ".COM;.EXE;.BAT;.CMD")
        .split(";")
        .filter(Boolean)
        .map((extension) => extension.toLowerCase())
    : [""];

  for (const directory of pathEntries) {
    for (const extension of extensions) {
      const candidate = pathApi().join(directory, `${command}${extension}`);
      if (isExecutable(candidate)) return candidate;
    }
  }
  return undefined;
}

function quoteWindowsCommandPart(value) {
  return `"${String(value).replace(/"/g, '""')}"`;
}

function buildWindowsCommand(executable, args) {
  const command = [executable, ...args].map(quoteWindowsCommandPart).join(" ");
  // cmd.exe /S /C strips the first and last quotes around its command string.
  // Keep an outer pair so the inner executable/argument quotes survive intact.
  return `"${command}"`;
}

function buildWindowsCmdInvocation(executable, args, comSpec = process.env.ComSpec || "cmd.exe") {
  return {
    command: comSpec,
    args: ["/d", "/s", "/c", buildWindowsCommand(executable, args)],
    windowsVerbatimArguments: true,
  };
}

function runExecutable(executable, args, options = {}) {
  const spawnOptions = {
    encoding: "utf8",
    ...options,
  };
  if (isWindows() && /\.(?:cmd|bat)$/i.test(executable)) {
    const invocation = buildWindowsCmdInvocation(executable, args);
    return spawnSync(
      invocation.command,
      invocation.args,
      { ...spawnOptions, windowsVerbatimArguments: invocation.windowsVerbatimArguments },
    );
  }
  return spawnSync(executable, args, spawnOptions);
}

function resolveNpm() {
  return resolveFromPath("npm") || (isWindows() ? "npm.cmd" : "npm");
}

function readNpmPrefix() {
  const result = runExecutable(resolveNpm(), ["prefix", "-g"]);
  if (result.status !== 0) return undefined;
  const prefix = String(result.stdout || "").trim();
  return prefix || undefined;
}

function npmPrefixCandidates(prefix, platform = process.platform) {
  if (!prefix) return [];
  const pathForPlatform = pathApi(platform);
  return isWindows(platform)
    ? [
        pathForPlatform.join(prefix, "oa-skills.cmd"),
        pathForPlatform.join(prefix, "oa-skills.exe"),
        pathForPlatform.join(prefix, "oa-skills"),
      ]
    : [pathForPlatform.join(prefix, "bin", "oa-skills")];
}

function resolveFromNpmPrefix(prefix) {
  const candidates = npmPrefixCandidates(prefix);
  return candidates.find(isExecutable);
}

function resolveCalendarCli({ preferNpmPrefix = false } = {}) {
  const fromPath = resolveFromPath("oa-skills");
  if (fromPath && !preferNpmPrefix) return { cliPath: fromPath, onPath: true };

  const npmPrefix = readNpmPrefix();
  const fromPrefix = resolveFromNpmPrefix(npmPrefix);
  if (fromPrefix) return { cliPath: fromPrefix, onPath: false, npmPrefix };
  if (fromPath) return { cliPath: fromPath, onPath: true, npmPrefix };
  return { npmPrefix };
}

function installCalendarCli() {
  const result = runExecutable(
    resolveNpm(),
    ["install", "-g", OA_SKILLS_PACKAGE, `--registry=${CALENDAR_REGISTRY}`],
    { stdio: "inherit" },
  );
  return result.status === 0;
}

function probeCalendarCli(cliPath) {
  const result = runExecutable(cliPath, ["calendar-mcp", "capabilities", "--raw"], {
    env: { ...process.env, NO_CHECK_VERSION: "true" },
  });
  if (result.status !== 0) {
    if (result.stderr) process.stderr.write(result.stderr);
    return false;
  }

  try {
    const payload = JSON.parse(String(result.stdout || ""));
    return (
      payload.schemaVersion === 1 &&
      REQUIRED_FEATURES.every((feature) => payload.features?.[feature] === true)
    );
  } catch (error) {
    process.stderr.write(`calendar-mcp capabilities 输出不是有效 JSON：${error.message}\n`);
    return false;
  }
}

function printReady(cli) {
  process.stdout.write(
    `${JSON.stringify({ status: "ready", cliPath: cli.cliPath, onPath: cli.onPath })}\n`,
  );
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
}

function main() {
  const mode = process.argv[2];
  if (mode !== "--check" && mode !== "--repair") {
    fail("用法：node ensure-oa-skills.cjs <--check|--repair>");
    return;
  }

  let cli = resolveCalendarCli();
  if (mode === "--check") {
    if (!cli.cliPath) {
      fail("未找到 oa-skills；请读取 runtime-and-safety.md 并执行 --repair，禁止搜索或猜测包名。");
      return;
    }
    printReady(cli);
    return;
  }

  let installAttempted = false;
  if (!cli.cliPath) {
    installAttempted = true;
    if (!installCalendarCli()) {
      fail(`安装 ${OA_SKILLS_PACKAGE} 失败；停止业务调用，不要更换包名。`);
      return;
    }
    cli = resolveCalendarCli({ preferNpmPrefix: true });
    if (!cli.cliPath) {
      fail(
        `已安装 ${OA_SKILLS_PACKAGE}，但从 PATH 和 npm global prefix 都无法解析 oa-skills；请修复 PATH 后重试，不要重复安装。`,
      );
      return;
    }
  }

  if (!probeCalendarCli(cli.cliPath)) {
    if (installAttempted) {
      fail("刚安装的 calendar-mcp CLI 能力仍不兼容；停止业务调用，不要重复安装或更换包名。");
      return;
    }
    installAttempted = true;
    if (!installCalendarCli()) {
      fail(`升级 ${OA_SKILLS_PACKAGE} 失败；停止业务调用，不要更换包名。`);
      return;
    }
    cli = resolveCalendarCli({ preferNpmPrefix: true });
    if (!cli.cliPath || !probeCalendarCli(cli.cliPath)) {
      fail("升级一次后 calendar-mcp CLI 能力仍不兼容；停止业务调用，不要重复安装或更换包名。");
      return;
    }
  }

  printReady(cli);
}

if (require.main === module) main();

module.exports = {
  buildWindowsCmdInvocation,
  buildWindowsCommand,
  npmPrefixCandidates,
  pathDelimiter,
};
