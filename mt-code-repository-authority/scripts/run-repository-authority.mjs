#!/usr/bin/env node

import { execFile } from "node:child_process";
import {
  mkdir,
  readFile,
  realpath,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { request as httpsRequest } from "node:https";
import { dirname, join, resolve, sep } from "node:path";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { setTimeout as wait } from "node:timers/promises";

import {
  AuthorityContractError,
  AuthorityUnresolvedError,
  CALLBACK_RECEIPT_SCHEMA,
  HASH,
  MAX_PROVIDER_BYTES,
  MAX_RESULT_BYTES,
  RESULT_SCHEMA,
  SKILL_CONTRACT_VERSION,
  YUNTU_AUDIENCE,
  YUNTU_PACKAGE,
  YUNTU_REGISTRY,
  YUNTU_VERSION,
  buildRunnerResult,
  canonical,
  emptyTimings,
  exactObject,
  normalizeCodeCliRepository,
  normalizeYuntuOrganization,
  parseUtf8Json,
  sha256,
  validateTaskArtifact,
} from "./repository-authority-contract.mjs";

const execFileAsync = promisify(execFile);
const DEFAULT_RUNTIME_ROOT = "/mnt/session/runtime/mt-code-repository-authority";
const INSTALL_TIMEOUT_MS = 120_000;
const INSTALL_LOCK_TIMEOUT_MS = 30_000;
const PROVIDER_TIMEOUT_MS = 30_000;
const TOKEN_TIMEOUT_MS = 30_000;
const CALLBACK_TIMEOUT_MS = 12_000;
const CALLBACK_RESPONSE_MAX_BYTES = 8 * 1024;
const CALLBACK_RETRY_DELAYS_MS = [250, 750];
const RETRYABLE_CALLBACK_STATUS = new Set([408, 425, 429]);
const TRANSIENT_OUTPUT = /(?:EAI_AGAIN|ETIMEDOUT|ECONNRESET|ECONNREFUSED|ENETUNREACH|network|socket hang up|\b429\b|\b5\d\d\b)/i;
const ANSI_ESCAPE = /\u001b\[[0-?]*[ -/]*[@-~]/g;

export class AuthorityRunnerError extends Error {
  constructor(message, {
    phase = "runner",
    errorCode = "runner_failed",
    retriable = false,
  } = {}) {
    super(message);
    this.name = "AuthorityRunnerError";
    this.phase = phase;
    this.errorCode = errorCode;
    this.retriable = retriable;
  }
}

const asRunnerError = (error) => {
  if (error instanceof AuthorityRunnerError || error instanceof AuthorityContractError) {
    return error;
  }
  return new AuthorityRunnerError("repository authority Runner failed", {
    phase: "runner",
    errorCode: "runner_failed",
  });
};

const boundedText = (value, maxBytes = MAX_PROVIDER_BYTES) => {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(value ?? "");
  if (bytes.byteLength > maxBytes) {
    throw new AuthorityRunnerError("subprocess output exceeded the bounded size", {
      phase: "runner",
      errorCode: "provider_output_too_large",
    });
  }
  return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
};

export const runProcess = async (command, args, {
  cwd,
  env = process.env,
  timeout = PROVIDER_TIMEOUT_MS,
  maxBuffer = MAX_PROVIDER_BYTES,
} = {}) => {
  try {
    const result = await execFileAsync(command, args, {
      cwd,
      env,
      timeout,
      maxBuffer,
      encoding: "buffer",
      windowsHide: true,
      shell: false,
    });
    return {
      exitCode: 0,
      stdout: Buffer.from(result.stdout ?? ""),
      stderr: Buffer.from(result.stderr ?? ""),
      timedOut: false,
      spawnCode: null,
    };
  } catch (error) {
    return {
      exitCode: Number.isInteger(error?.code) ? error.code : null,
      stdout: Buffer.from(error?.stdout ?? ""),
      stderr: Buffer.from(error?.stderr ?? ""),
      timedOut: error?.killed === true || error?.signal === "SIGTERM",
      spawnCode: typeof error?.code === "string" ? error.code : null,
    };
  }
};

const deadlineTimeout = (context, desiredMs, now = Date.now()) => {
  const remaining = context.deadline - now - 1_000;
  if (remaining <= 0) {
    throw new AuthorityRunnerError("repository authority deadline has expired", {
      phase: "deadline",
      errorCode: "deadline_exceeded",
    });
  }
  return Math.max(1, Math.min(desiredMs, remaining));
};

const isSafeDescendant = (parent, child) => {
  const normalizedParent = `${resolve(parent)}${sep}`;
  return resolve(child).startsWith(normalizedParent);
};

const safeProcessEnvironment = () => {
  const result = {};
  for (const key of [
    "PATH", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "TZ",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS",
  ]) {
    if (typeof process.env[key] === "string") result[key] = process.env[key];
  }
  return result;
};

const environmentWithoutYuntuToken = () => {
  const result = { ...process.env };
  delete result.YUNTU_ACCESS_TOKEN;
  delete result.YUNTU_OPERATOR;
  return result;
};

const readYuntuInstallation = async (installRoot) => {
  const packageRoot = join(installRoot, "node_modules", "@ee", "yuntu-cli");
  const packageJsonPath = join(packageRoot, "package.json");
  const executablePath = join(packageRoot, "dist", "index.js");
  let packageJson;
  try {
    packageJson = JSON.parse(await readFile(packageJsonPath, "utf8"));
    const executableStats = await stat(executablePath);
    const resolvedInstallRoot = await realpath(installRoot);
    const resolvedExecutable = await realpath(executablePath);
    if (
      packageJson?.name !== YUNTU_PACKAGE || packageJson?.version !== YUNTU_VERSION ||
      !executableStats.isFile() || !isSafeDescendant(resolvedInstallRoot, resolvedExecutable)
    ) return null;
  } catch {
    return null;
  }
  return { installRoot, executablePath, version: packageJson.version };
};

const installFailureIsTransient = (result) => {
  if (result.timedOut) return true;
  if (result.spawnCode === "ENOENT") return false;
  const summary = `${boundedText(result.stdout)}\n${boundedText(result.stderr)}`;
  return TRANSIENT_OUTPUT.test(summary);
};

export const ensureYuntuRuntime = async ({
  context,
  runtimeRoot = DEFAULT_RUNTIME_ROOT,
  processRunner = runProcess,
  waitForRetry = wait,
  now = Date.now,
}) => {
  const installRoot = join(runtimeRoot, `yuntu-${YUNTU_VERSION}`);
  const existing = await readYuntuInstallation(installRoot);
  if (existing) return existing;
  await mkdir(runtimeRoot, { recursive: true, mode: 0o700 });
  const privateConfigRoot = join(runtimeRoot, ".config");
  const npmCache = join(runtimeRoot, ".npm-cache");
  await mkdir(privateConfigRoot, { recursive: true, mode: 0o700 });
  await mkdir(npmCache, { recursive: true, mode: 0o700 });
  const lockPath = join(runtimeRoot, `yuntu-${YUNTU_VERSION}.install-lock`);
  let ownsLock = false;
  try {
    try {
      await mkdir(lockPath, { mode: 0o700 });
      ownsLock = true;
    } catch (error) {
      if (error?.code !== "EEXIST") throw error;
    }
    if (!ownsLock) {
      const waitStarted = now();
      while (now() - waitStarted < INSTALL_LOCK_TIMEOUT_MS) {
        const installed = await readYuntuInstallation(installRoot);
        if (installed) return installed;
        await waitForRetry(250);
      }
      throw new AuthorityRunnerError("Yuntu runtime installation lock did not resolve", {
        phase: "runtime_install",
        errorCode: "runtime_install_locked",
        retriable: true,
      });
    }

    const afterLock = await readYuntuInstallation(installRoot);
    if (afterLock) return afterLock;
    try {
      await stat(installRoot);
      throw new AuthorityRunnerError("Yuntu runtime directory is incomplete", {
        phase: "runtime_install",
        errorCode: "runtime_install_corrupt",
      });
    } catch (error) {
      if (error instanceof AuthorityRunnerError) throw error;
      if (error?.code !== "ENOENT") throw error;
    }

    let lastResult = null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const stage = join(runtimeRoot, `.yuntu-${YUNTU_VERSION}-${process.pid}-${attempt}`);
      if (!isSafeDescendant(runtimeRoot, stage)) {
        throw new AuthorityRunnerError("Yuntu staging path is unsafe", {
          phase: "runtime_install",
          errorCode: "runtime_install_path_invalid",
        });
      }
      await rm(stage, { recursive: true, force: true });
      await mkdir(stage, { recursive: true, mode: 0o700 });
      const result = await processRunner("npm", [
        "install",
        "--prefix", stage,
        "--no-save",
        "--no-audit",
        "--no-fund",
        "--omit=dev",
        "--ignore-scripts",
        `--registry=${YUNTU_REGISTRY}`,
        `${YUNTU_PACKAGE}@${YUNTU_VERSION}`,
      ], {
        env: {
          ...safeProcessEnvironment(),
          XDG_CONFIG_HOME: privateConfigRoot,
          npm_config_cache: npmCache,
          npm_config_userconfig: join(privateConfigRoot, "npmrc"),
        },
        timeout: deadlineTimeout(context, INSTALL_TIMEOUT_MS, now()),
        maxBuffer: MAX_PROVIDER_BYTES,
      });
      lastResult = result;
      if (result.exitCode === 0) {
        const staged = await readYuntuInstallation(stage);
        if (!staged) {
          await rm(stage, { recursive: true, force: true });
          throw new AuthorityRunnerError("installed Yuntu runtime failed version validation", {
            phase: "runtime_install",
            errorCode: "runtime_version_mismatch",
          });
        }
        await rename(stage, installRoot);
        const installed = await readYuntuInstallation(installRoot);
        if (!installed) {
          throw new AuthorityRunnerError("Yuntu runtime failed post-install validation", {
            phase: "runtime_install",
            errorCode: "runtime_version_mismatch",
          });
        }
        return installed;
      }
      await rm(stage, { recursive: true, force: true });
      const transient = installFailureIsTransient(result);
      if (!transient || attempt === 1) break;
      await waitForRetry(500);
    }
    throw new AuthorityRunnerError("Yuntu runtime installation failed", {
      phase: "runtime_install",
      errorCode: lastResult?.timedOut
        ? "runtime_install_timeout"
        : lastResult?.spawnCode === "ENOENT"
        ? "npm_unavailable"
        : "runtime_install_failed",
      retriable: lastResult ? installFailureIsTransient(lastResult) : false,
    });
  } finally {
    if (ownsLock) await rm(lockPath, { recursive: true, force: true }).catch(() => undefined);
  }
};

const cleanVersion = (raw) => {
  const text = boundedText(raw, 8 * 1024).replace(ANSI_ESCAPE, "").trim();
  const line = text.split(/\r?\n/u).map((item) => item.trim()).find(Boolean) ?? "";
  return line && line.length <= 120 && !/[\u0000-\u001f\u007f-\u009f]/u.test(line)
    ? line
    : "unknown";
};

export const queryRepositoryOwner = async ({
  context,
  processRunner = runProcess,
  now = Date.now,
  readVersion = true,
}) => {
  let eeCodeCliVersion = "unknown";
  if (readVersion) {
    const versionResult = await processRunner("code-cli", ["--version"], {
      env: environmentWithoutYuntuToken(),
      timeout: deadlineTimeout(context, 10_000, now()),
      maxBuffer: 8 * 1024,
    });
    eeCodeCliVersion = versionResult.exitCode === 0
      ? cleanVersion(versionResult.stdout)
      : "unknown";
  }
  const result = await processRunner("code-cli", [
    "repo", "-R", context.repository.canonicalKey, "view", "--json",
  ], {
    env: environmentWithoutYuntuToken(),
    timeout: deadlineTimeout(context, PROVIDER_TIMEOUT_MS, now()),
    maxBuffer: MAX_PROVIDER_BYTES,
  });
  if (result.exitCode !== 0) {
    throw new AuthorityRunnerError("ee-code repository lookup failed", {
      phase: "repository_lookup",
      errorCode: result.timedOut
        ? "repository_lookup_timeout"
        : result.spawnCode === "ENOENT"
        ? "code_cli_unavailable"
        : "repository_lookup_failed",
      retriable: result.timedOut || TRANSIENT_OUTPUT.test(
        `${boundedText(result.stdout)}\n${boundedText(result.stderr)}`,
      ),
    });
  }
  try {
    const raw = parseUtf8Json(result.stdout, "ee-code output", MAX_PROVIDER_BYTES);
    return {
      ...normalizeCodeCliRepository(raw, context.repository.canonicalKey),
      eeCodeCliVersion,
    };
  } catch (error) {
    if (error instanceof AuthorityUnresolvedError) throw error;
    if (error instanceof AuthorityContractError) {
      throw new AuthorityRunnerError("ee-code repository result is invalid", {
        phase: "repository_lookup",
        errorCode: error.errorCode.startsWith("repository_")
          ? error.errorCode
          : "repository_result_invalid",
      });
    }
    throw error;
  }
};

const validAccessToken = (value) => typeof value === "string" &&
  value.length >= 16 && value.length <= 8192 && !/\s|[\u0000-\u001f\u007f]/u.test(value);

const safeMtssoErrorCode = (stdout) => {
  try {
    const parsed = JSON.parse(boundedText(stdout, 64 * 1024).trim());
    const code = typeof parsed?.code === "string"
      ? parsed.code
      : typeof parsed?.error === "string"
      ? parsed.error
      : parsed?.error?.code;
    return typeof code === "string" && /^[a-z][a-z0-9_]{1,99}$/.test(code)
      ? code
      : null;
  } catch {
    return null;
  }
};

export const acquireMetricsToken = async ({
  context,
  processRunner = runProcess,
  now = Date.now,
}) => {
  const result = await processRunner("mtsso-moa-local-exchange", [
    "--audience", YUNTU_AUDIENCE,
  ], {
    env: environmentWithoutYuntuToken(),
    timeout: deadlineTimeout(context, TOKEN_TIMEOUT_MS, now()),
    maxBuffer: 64 * 1024,
  });
  if (result.exitCode !== 0) {
    const officialCode = safeMtssoErrorCode(result.stdout);
    const requiresUserAction = result.exitCode === 42 || new Set([
      "sub_access_denied", "act_access_denied", "sub_act_access_denied",
      "ric_feedback_required",
    ]).has(officialCode);
    throw new AuthorityRunnerError("Metrics user ticket exchange failed", {
      phase: "metrics_token_exchange",
      errorCode: requiresUserAction
        ? "metrics_user_authorization_required"
        : result.timedOut
        ? "metrics_token_exchange_timeout"
        : result.spawnCode === "ENOENT"
        ? "mtsso_cli_unavailable"
        : "metrics_token_exchange_failed",
      retriable: !requiresUserAction && (result.timedOut || TRANSIENT_OUTPUT.test(
        `${boundedText(result.stdout, 64 * 1024)}\n${boundedText(result.stderr, 64 * 1024)}`,
      )),
    });
  }
  const stdout = boundedText(result.stdout, 64 * 1024).trim();
  if (stdout.startsWith("AT_FOR_GW_BASE64_") && validAccessToken(stdout)) return stdout;
  let parsed;
  try {
    parsed = JSON.parse(stdout);
  } catch {
    throw new AuthorityRunnerError("Metrics ticket output is not valid JSON", {
      phase: "metrics_token_exchange",
      errorCode: "metrics_token_response_invalid",
    });
  }
  const token = parsed?.access_token;
  if (!validAccessToken(token)) {
    throw new AuthorityRunnerError("Metrics ticket response has no usable access token", {
      phase: "metrics_token_exchange",
      errorCode: "metrics_token_response_invalid",
    });
  }
  return token;
};

const yuntuEnvironment = ({ token, actorMis, privateConfigRoot }) => {
  const result = safeProcessEnvironment();
  result.XDG_CONFIG_HOME = privateConfigRoot;
  result.YUNTU_ACCESS_TOKEN = token;
  result.YUNTU_OPERATOR = actorMis;
  result.YUNTU_ENVIRONMENT = "production";
  return result;
};

export const queryYuntuOrganization = async ({
  context,
  runtime,
  owner,
  metricsToken,
  processRunner = runProcess,
  now = Date.now,
}) => {
  const privateConfigRoot = join(dirname(runtime.installRoot), ".config");
  await mkdir(privateConfigRoot, { recursive: true, mode: 0o700 });
  const result = await processRunner(process.execPath, [
    runtime.executablePath,
    "--output", "json",
    "--color", "off",
    "user", "org", owner.ownerMis,
  ], {
    env: yuntuEnvironment({
      token: metricsToken,
      actorMis: context.actorMis,
      privateConfigRoot,
    }),
    timeout: deadlineTimeout(context, PROVIDER_TIMEOUT_MS, now()),
    maxBuffer: MAX_PROVIDER_BYTES,
  });
  if (result.exitCode !== 0) {
    throw new AuthorityRunnerError("Yuntu organization lookup failed", {
      phase: "yuntu_lookup",
      errorCode: result.timedOut ? "yuntu_lookup_timeout" : "yuntu_lookup_failed",
      retriable: result.timedOut || TRANSIENT_OUTPUT.test(
        `${boundedText(result.stdout)}\n${boundedText(result.stderr)}`,
      ),
    });
  }
  try {
    const raw = parseUtf8Json(result.stdout, "Yuntu output", MAX_PROVIDER_BYTES);
    return normalizeYuntuOrganization(raw, owner.ownerMis);
  } catch (error) {
    if (error instanceof AuthorityUnresolvedError) throw error;
    if (error instanceof AuthorityContractError) {
      throw new AuthorityRunnerError("Yuntu organization result is invalid", {
        phase: "yuntu_lookup",
        errorCode: error.errorCode.startsWith("organization_")
          ? error.errorCode
          : "yuntu_result_invalid",
      });
    }
    throw error;
  }
};

const writeJsonAtomic = async (outputPath, value) => {
  const output = resolve(outputPath);
  await mkdir(dirname(output), { recursive: true, mode: 0o700 });
  const temporary = `${output}.tmp-${process.pid}`;
  const body = `${canonical(value)}\n`;
  if (Buffer.byteLength(body, "utf8") > MAX_RESULT_BYTES) {
    throw new AuthorityRunnerError("result output exceeded 64 KiB", {
      phase: "result_validation",
      errorCode: "result_too_large",
    });
  }
  await writeFile(temporary, body, { encoding: "utf8", mode: 0o600 });
  await rename(temporary, output);
};

const boundedHttpsRequest = ({ url, token, idempotencyKey, body, timeoutMs }) =>
  new Promise((accept, reject) => {
    const request = httpsRequest(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "Content-Length": String(Buffer.byteLength(body, "utf8")),
        "Idempotency-Key": idempotencyKey,
      },
    }, (response) => {
      const chunks = [];
      let bytes = 0;
      response.on("data", (chunk) => {
        bytes += chunk.length;
        if (bytes > CALLBACK_RESPONSE_MAX_BYTES) {
          request.destroy(new AuthorityRunnerError("callback response is too large", {
            phase: "callback",
            errorCode: "callback_response_invalid",
          }));
          return;
        }
        chunks.push(chunk);
      });
      response.on("end", () => accept({
        status: Number(response.statusCode ?? 0),
        contentType: String(response.headers["content-type"] ?? ""),
        body: Buffer.concat(chunks).toString("utf8"),
      }));
      response.on("aborted", () => reject(new AuthorityRunnerError(
        "callback response was aborted",
        { phase: "callback", errorCode: "callback_network_error", retriable: true },
      )));
      response.on("error", () => reject(new AuthorityRunnerError(
        "callback response failed",
        { phase: "callback", errorCode: "callback_network_error", retriable: true },
      )));
    });
    request.setTimeout(timeoutMs, () => request.destroy(new AuthorityRunnerError(
      "callback request timed out",
      { phase: "callback", errorCode: "callback_timeout", retriable: true },
    )));
    request.on("error", (error) => reject(
      error instanceof AuthorityRunnerError
        ? error
        : new AuthorityRunnerError("callback request failed", {
          phase: "callback",
          errorCode: "callback_network_error",
          retriable: true,
        }),
    ));
    request.end(body);
  });

export const validateCallbackReceipt = (receipt, expected) => {
  exactObject(receipt, new Set([
    "schema_version", "status", "attempt_id", "runner_invocation_id", "result_hash",
  ]), "callback receipt");
  if (
    receipt.schema_version !== CALLBACK_RECEIPT_SCHEMA ||
    !new Set(["accepted", "duplicate"]).has(receipt.status) ||
    receipt.attempt_id !== expected.attemptId ||
    receipt.runner_invocation_id !== expected.runnerInvocationId ||
    receipt.result_hash !== expected.resultHash
  ) {
    throw new AuthorityRunnerError("callback receipt did not match the result", {
      phase: "callback",
      errorCode: "callback_response_invalid",
    });
  }
  return receipt;
};

export const deliverAuthorityCallback = async ({
  context,
  result,
  request = boundedHttpsRequest,
  waitForRetry = wait,
  now = Date.now,
}) => {
  const body = canonical(result);
  const resultHash = sha256(body);
  const expected = {
    attemptId: context.attemptId,
    runnerInvocationId: context.runnerInvocationId,
    resultHash,
  };
  let lastError = null;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const remaining = context.deadline - now();
    if (remaining <= 1_000) {
      throw new AuthorityRunnerError("callback deadline has expired", {
        phase: "callback",
        errorCode: "callback_deadline_exceeded",
      });
    }
    try {
      const response = await request({
        url: context.callback.url,
        token: context.callback.token,
        idempotencyKey: `${context.attemptId}:${context.runnerInvocationId}`,
        body,
        timeoutMs: Math.min(CALLBACK_TIMEOUT_MS, remaining - 500),
      });
      let retryableStatus = RETRYABLE_CALLBACK_STATUS.has(response.status) ||
        response.status >= 500;
      if (response.status >= 200 && response.status < 300 &&
          response.contentType.toLowerCase().includes("application/json")) {
        let receipt;
        try {
          receipt = JSON.parse(response.body);
        } catch {
          throw new AuthorityRunnerError("callback response is not JSON", {
            phase: "callback",
            errorCode: "callback_response_invalid",
          });
        }
        return { receipt: validateCallbackReceipt(receipt, expected), resultHash };
      }
      lastError = new AuthorityRunnerError("callback was not accepted", {
        phase: "callback",
        errorCode: response.status === 401 || response.status === 403
          ? "callback_unauthorized"
          : response.status === 409
          ? "callback_conflict"
          : "callback_delivery_failed",
        retriable: retryableStatus,
      });
    } catch (error) {
      lastError = asRunnerError(error);
    }
    if (!lastError.retriable || attempt === 2) break;
    await waitForRetry(CALLBACK_RETRY_DELAYS_MS[attempt]);
  }
  throw lastError ?? new AuthorityRunnerError("callback delivery failed", {
    phase: "callback",
    errorCode: "callback_delivery_failed",
  });
};

const elapsed = (started, now) => Math.max(0, Math.round(now() - started));

const runTimed = async (timings, field, now, operation) => {
  const started = now();
  try {
    return await operation();
  } finally {
    timings[field] = elapsed(started, now);
  }
};

const errorPayload = (error) => ({
  phase: String(error.phase || "runner"),
  error_code: String(error.errorCode || "runner_failed"),
  retriable: error.retriable === true,
});

export const executeAuthorityTask = async ({
  taskPath,
  taskArtifactHash,
  outputPath,
  runtimeRoot = DEFAULT_RUNTIME_ROOT,
  processRunner = runProcess,
  callbackRequest = boundedHttpsRequest,
  waitForRetry = wait,
  now = Date.now,
}) => {
  const taskBytes = await readFile(taskPath);
  const context = validateTaskArtifact({
    taskBytes,
    expectedTaskArtifactHash: taskArtifactHash,
    now: now(),
  });
  const timings = emptyTimings();
  const totalStarted = now();
  const versions = { eeCodeCliVersion: "unknown", yuntuCliVersion: "unavailable" };
  let repository = {
    canonical_key: context.repository.canonicalKey,
    default_branch: null,
  };
  let owner = null;
  let organization = null;
  let executionStatus = "failed";
  let resolutionStatus = null;
  let failure = null;

  try {
    const runtime = await runTimed(
      timings,
      "runtime_install_ms",
      now,
      () => ensureYuntuRuntime({
        context, runtimeRoot, processRunner, waitForRetry, now,
      }),
    );
    versions.yuntuCliVersion = runtime.version;

    const repositoryOwner = await runTimed(
      timings,
      "repository_lookup_ms",
      now,
      () => queryRepositoryOwner({ context, processRunner, now }),
    );
    versions.eeCodeCliVersion = repositoryOwner.eeCodeCliVersion;
    repository = {
      canonical_key: context.repository.canonicalKey,
      default_branch: repositoryOwner.defaultBranch,
    };
    owner = {
      mis: repositoryOwner.ownerMis,
      display_name: repositoryOwner.ownerDisplayName,
      iam_emp_id: null,
      identity_enrichment_status: "not_requested",
    };

    const metricsToken = await runTimed(
      timings,
      "metrics_token_exchange_ms",
      now,
      () => acquireMetricsToken({ context, processRunner, now }),
    );

    const yuntu = await runTimed(
      timings,
      "yuntu_lookup_ms",
      now,
      () => queryYuntuOrganization({
        context,
        runtime,
        owner: repositoryOwner,
        metricsToken,
        processRunner,
        now,
      }),
    );
    const recheckStarted = now();
    let currentRepositoryOwner;
    try {
      currentRepositoryOwner = await queryRepositoryOwner({
        context,
        processRunner,
        now,
        readVersion: false,
      });
    } catch (error) {
      if (error instanceof AuthorityUnresolvedError) {
        throw new AuthorityUnresolvedError(
          "repository owner changed while authority was being resolved",
          {
            phase: "repository_lookup",
            errorCode: "repository_owner_changed",
          },
        );
      }
      throw error;
    } finally {
      timings.repository_lookup_ms += elapsed(recheckStarted, now);
    }
    if (currentRepositoryOwner.ownerMis !== repositoryOwner.ownerMis) {
      throw new AuthorityUnresolvedError(
        "repository owner changed while authority was being resolved",
        {
          phase: "repository_lookup",
          errorCode: "repository_owner_changed",
        },
      );
    }
    if (currentRepositoryOwner.defaultBranch !== repositoryOwner.defaultBranch) {
      throw new AuthorityUnresolvedError(
        "repository state changed while authority was being resolved",
        {
          phase: "repository_lookup",
          errorCode: "repository_state_changed",
        },
      );
    }
    owner.display_name = owner.display_name ?? yuntu.name;
    organization = {
      source_system: "yuntu_org",
      source_organization_id: yuntu.sourceOrganizationId,
      display_name: yuntu.displayName,
      full_path: yuntu.fullPath,
      chain: yuntu.chain,
    };
    executionStatus = "succeeded";
    resolutionStatus = "confirmed";
  } catch (error) {
    const normalized = asRunnerError(error);
    if (normalized instanceof AuthorityUnresolvedError) {
      executionStatus = "succeeded";
      resolutionStatus = "unresolved";
      organization = null;
      failure = normalized;
    } else {
      executionStatus = "failed";
      resolutionStatus = null;
      owner = null;
      organization = null;
      failure = normalized;
    }
  }

  timings.total_ms = elapsed(totalStarted, now);
  const result = buildRunnerResult({
    context,
    executionStatus,
    resolutionStatus,
    repository,
    owner,
    organization,
    versions,
    verifiedAt: new Date(now()).toISOString(),
    timings,
    error: failure ? errorPayload(failure) : null,
  });
  let outputWritten = true;
  try {
    await writeJsonAtomic(outputPath, result);
  } catch {
    outputWritten = false;
  }
  const callback = await deliverAuthorityCallback({
    context,
    result,
    request: callbackRequest,
    waitForRetry,
    now,
  });
  return { context, result, callback, outputWritten };
};

const parseArgs = (argv) => {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!new Set(["--task", "--task-artifact-hash", "--output"]).has(key) || !value) {
      throw new AuthorityRunnerError("Runner arguments are invalid", {
        phase: "task_validation",
        errorCode: "runner_arguments_invalid",
      });
    }
    if (values[key]) {
      throw new AuthorityRunnerError("Runner argument is duplicated", {
        phase: "task_validation",
        errorCode: "runner_arguments_invalid",
      });
    }
    values[key] = value;
  }
  if (!values["--task"] || !values["--output"] ||
      !HASH.test(String(values["--task-artifact-hash"] ?? ""))) {
    throw new AuthorityRunnerError("Required Runner arguments are missing", {
      phase: "task_validation",
      errorCode: "runner_arguments_invalid",
    });
  }
  return {
    taskPath: resolve(values["--task"]),
    taskArtifactHash: values["--task-artifact-hash"],
    outputPath: resolve(values["--output"]),
  };
};

const isMain = process.argv[1] &&
  resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));

if (isMain) {
  try {
    const execution = await executeAuthorityTask(parseArgs(process.argv.slice(2)));
    process.stdout.write(`${JSON.stringify({
      schema_version: "repository-authority-local-receipt/v1",
      status: execution.callback.receipt.status,
      execution_status: execution.result.execution_status,
      resolution_status: execution.result.resolution_status,
      attempt_id: execution.context.attemptId,
      result_hash: execution.callback.resultHash,
      output_written: execution.outputWritten,
    })}\n`);
  } catch (error) {
    const normalized = asRunnerError(error);
    process.stderr.write(`${JSON.stringify({
      schema_version: "repository-authority-local-error/v1",
      phase: normalized.phase,
      error_code: normalized.errorCode,
      retriable: normalized.retriable === true,
    })}\n`);
    process.exitCode = 1;
  }
}

export const CONTRACT = Object.freeze({
  task: "repository-authority-task/v1",
  result: RESULT_SCHEMA,
  callbackReceipt: CALLBACK_RECEIPT_SCHEMA,
  skill: SKILL_CONTRACT_VERSION,
  yuntu: `${YUNTU_PACKAGE}@${YUNTU_VERSION}`,
  audience: YUNTU_AUDIENCE,
});
