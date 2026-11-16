import { randomUUID } from "node:crypto";
import { constants } from "node:fs";
import { lstat, mkdir, open, readdir, readFile, rm, rename } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import { DEFAULT_GATEWAY, validateGatewayUrl } from "./resolve-effective-rules.mjs";

// Same allowlisted business service as the download, never a new destination.
export const EVENT_URL = `${validateGatewayUrl(DEFAULT_GATEWAY)}/v1/public/rule-download-events`;
const PHASES = ["preflight", "auth", "request", "response_validation", "install"];
const AGENTS = ["catdesk", "catpaw", "claude", "codex", "agent_1024", "sandbox", "catx", "cli", "unknown"];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_AGE = 30 * 86400000;
const bounded = n => Math.max(0, Math.min(86400000, Math.round(n || 0)));
const label = value => typeof value === "string" && /^[A-Za-z0-9@._/+\-]{1,128}$/.test(value) && !/^(eyJ|sk-)/.test(value) ? value : null;

// Never copy options/errors: no paths, MIS, tokens, sources or error messages.
export const observationMetadata = (value = {}) => {
  const cli = value.client_type === "cli";
  const name = ["mt-code-standards", "mt-code-standards-setup"].includes(value.skill_name) ? value.skill_name : null;
  return {
    client_type: cli ? "cli" : "skill", client_name: cli ? (value.client_name === "@nibfe/mt-coding-standards" ? value.client_name : null) : name,
    client_version: label(value.client_version), skill_name: cli ? null : name,
    skill_version: cli ? null : label(value.skill_version),
    execution_agent: AGENTS.includes(value.execution_agent) ? value.execution_agent : "unknown",
    transport: ["public", "direct", "mtcli"].includes(value.transport) ? value.transport : "public",
    stage: ["design", "coding", "cr"].includes(value.stage) ? value.stage : null,
    standard_domain: ["frontend", "backend"].includes(value.standard_domain) ? value.standard_domain : null,
  };
};
export const sanitizeEvent = value => {
  if (!value || value.schema_version !== "rule-download-event/v1" || !UUID.test(value.event_id || "")
    || !UUID.test(value.run_id || "") || !["start", "finish"].includes(value.event_type)
    || !Number.isFinite(Date.parse(value.started_at)) || !Number.isFinite(Date.parse(value.occurred_at))) return null;
  const start = value.event_type === "start";
  if (start ? value.status !== null : !["installed", "not_modified", "failed", "cancelled"].includes(value.status)) return null;
  const failure = ["failed", "cancelled"].includes(value.status);
  return {
    schema_version: "rule-download-event/v1", event_id: value.event_id, run_id: value.run_id,
    event_type: value.event_type, started_at: new Date(value.started_at).toISOString(),
    occurred_at: new Date(value.occurred_at).toISOString(), ...observationMetadata(value),
    pull_id: UUID.test(value.pull_id || "") ? value.pull_id : null, status: value.status,
    failure_stage: failure && PHASES.includes(value.failure_stage) ? value.failure_stage : null,
    error_code: failure && /^[A-Za-z][A-Za-z0-9_]{0,99}$/.test(value.error_code || "") ? value.error_code : null,
    duration_ms: start ? null : bounded(value.duration_ms),
    phase_durations_ms: Object.fromEntries(PHASES.filter(p => Number.isFinite(value.phase_durations_ms?.[p]))
      .map(p => [p, bounded(value.phase_durations_ms[p])])),
    request_count: Math.max(0, Math.min(1000, Math.round(value.request_count || 0))),
  };
};
export const createEventQueue = ({ directory = path.join(homedir(), ".mt-code-standards", "download-events-v1"),
  fetchImpl = globalThis.fetch, now = Date.now, timeoutMs = 350, maxFiles = 100,
} = {}) => {
  const safeDirectory = async () => {
    const absolute = path.resolve(directory);
    let cursor = path.parse(absolute).root;
    for (const part of absolute.slice(cursor.length).split(path.sep)) {
      cursor = path.join(cursor, part);
      try { await mkdir(cursor, { mode: 0o700 }); } catch (e) { if (e.code !== "EEXIST") throw e; }
      const stat = await lstat(cursor);
      if (stat.isSymbolicLink() || !stat.isDirectory()) throw new Error("Unsafe observation directory");
    }
    return absolute;
  };
  const list = async () => (await readdir(await safeDirectory())).filter(n => /^[0-9a-f-]{36}\.json$/.test(n)).sort();
  const write = async (filename, value) => {
    const temp = path.join(directory, `${randomUUID()}.tmp`);
    const handle = await open(temp, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
    try { await handle.writeFile(JSON.stringify(value)); } finally { await handle.close(); }
    try { await rename(temp, filename); } finally { await rm(temp, { force: true }); }
  };
  return {
    async enqueue(event) {
      try {
        event = sanitizeEvent(event);
        if (!event || Buffer.byteLength(JSON.stringify(event)) > 16384) return;
        const files = await list();
        for (const name of files.slice(0, Math.max(0, files.length - maxFiles + 1))) await rm(path.join(directory, name), { force: true });
        await write(path.join(directory, `${event.event_id}.json`), { event, attempts: 0, next_at: 0 });
      } catch { /* Observation never changes the installation result. */ }
    },
    async flush() {
      try {
        let sent = 0;
        for (const name of await list()) {
          const filename = path.join(directory, name);
          const stat = await lstat(filename);
          if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 20000) continue;
          let item;
          try { item = JSON.parse(await readFile(filename, "utf8")); } catch { await rm(filename, { force: true }); continue; }
          item.event = sanitizeEvent(item.event);
          if (!item.event || item.event.event_id + ".json" !== name
            || !Number.isFinite(Date.parse(item.event.occurred_at))
            || now() - Date.parse(item.event.occurred_at) > MAX_AGE || item.attempts >= 8) {
            await rm(filename, { force: true }); continue;
          }
          if (item.next_at > now()) continue;
          if (sent++ >= 2) break;
          const controller = new AbortController();
          let timer;
          let acknowledged = false;
          try {
            const operation = async () => {
              const response = await fetchImpl(EVENT_URL, { method: "POST", redirect: "error", signal: controller.signal,
                headers: { "Content-Type": "application/json" }, body: JSON.stringify(item.event) });
              if (!response.ok) return false;
              const text = await response.text();
              if (text.length > 16384) return false;
              const decoded = JSON.parse(text);
              const receipt = decoded.data ?? decoded;
              return receipt.schema_version === "rule-download-event-receipt/v1"
                && receipt.event_id === item.event.event_id && ["recorded", "duplicate"].includes(receipt.status);
            };
            acknowledged = await Promise.race([operation(), new Promise(resolve => {
              timer = setTimeout(() => { controller.abort(); resolve(false); }, timeoutMs);
            })]);
          } catch { /* Keep bounded retry records for network/old-server failures. */ }
          finally { clearTimeout(timer); controller.abort(); }
          if (acknowledged) await rm(filename, { force: true });
          else await write(filename, { ...item, attempts: item.attempts + 1,
            next_at: now() + Math.min(3600000, 1000 * 2 ** item.attempts) });
        }
      } catch { /* Best effort, including a read-only home directory. */ }
    },
  };
};
export const createDownloadObservation = ({ metadata, queue = process.env.MT_CODE_STANDARDS_OBSERVATION === "off" ? { async enqueue() {}, async flush() {} } : createEventQueue(), now = Date.now } = {}) => {
  const runId = randomUUID();
  const started = now();
  let current = "preflight", last = started, requests = 0, pullId = null;
  let meta = observationMetadata(metadata);
  const durations = {};
  const tick = phase => {
    const at = now();
    durations[current] = bounded((durations[current] || 0) + at - last);
    last = at;
    if (PHASES.includes(phase)) current = phase;
  };
  const event = (type, receipt, error) => ({
    schema_version: "rule-download-event/v1", event_id: randomUUID(), run_id: runId,
    event_type: type, started_at: new Date(started).toISOString(), occurred_at: new Date(now()).toISOString(),
    ...meta, pull_id: UUID.test(receipt?.pull_id || pullId || "") ? receipt?.pull_id || pullId : null,
    status: type === "start" ? null : error ? (error.code === "RULE_BUNDLE_CIBA_REJECTED" ? "cancelled" : "failed") : receipt?.status === "not_modified" ? "not_modified" : "installed",
    failure_stage: error ? current : null,
    error_code: error ? (/^[A-Za-z][A-Za-z0-9_]{0,99}$/.test(error.code || "") ? error.code : "RULE_BUNDLE_UNEXPECTED") : null,
    duration_ms: type === "start" ? null : bounded(now() - started),
    phase_durations_ms: type === "start" ? {} : { ...durations }, request_count: Math.min(requests, 1000),
  });
  return {
    runId,
    update(value) { meta = observationMetadata({ ...meta, ...value }); },
    phase: tick,
    request(value) { tick("request"); requests++; if (UUID.test(value || "")) pullId = value; },
    async start() { try { await queue.enqueue(event("start")); await queue.flush(); } catch { /* isolated */ } },
    async finish(receipt, error) {
      tick();
      meta = observationMetadata({ ...meta, standard_domain: receipt?.standard_domain ?? meta.standard_domain,
        stage: receipt?.stage ?? meta.stage });
      try { await queue.enqueue(event("finish", receipt, error)); await queue.flush(); } catch { /* isolated */ }
    },
  };
};
