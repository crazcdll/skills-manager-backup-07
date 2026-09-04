#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const DEFAULT_GATEWAY =
  "https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability";
const SUPPORTED_STAGES = new Set(["design", "coding", "cr"]);
const SUPPORTED_DOMAINS = new Set(["frontend", "backend", "shared"]);
const SUPPORTED_SCOPES = new Set(["auto", "organization", "repository"]);
export const SOURCE_PRECEDENCE = Object.freeze([
  "repository_direct",
  "organization_direct",
  "organization_inherited",
]);

export class RuleContextError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "RuleContextError";
    this.code = code;
  }
}

const text = (value) => String(value ?? "").trim();
const unique = (values) => [...new Set(values.map(text).filter(Boolean))];

export const normalizeMCodeRepositoryUrl = (value) => {
  const source = text(value);
  let match = source.match(
    /^https:\/\/dev[.]sankuai[.]com\/code\/repo-detail\/([^/]+)\/([^/?#]+)(?:\/file\/list)?(?:[?#].*)?$/,
  );
  if (!match) {
    match = source.match(/^ssh:\/\/git@git[.]sankuai[.]com\/([^/]+)\/([^/]+)[.]git$/);
  }
  if (!match || !/^[A-Za-z0-9._~-]+$/.test(match[1]) || !/^[A-Za-z0-9._-]+$/.test(match[2])) {
    throw new RuleContextError(
      "RULE_CONTEXT_REPOSITORY_INVALID",
      "只支持美团 Code 仓库详情地址或 ssh://git@git.sankuai.com/... 地址",
    );
  }
  const namespace = decodeURIComponent(match[1]);
  const repository = decodeURIComponent(match[2]);
  return Object.freeze({
    canonical_key: `${namespace.toLowerCase()}/${repository.toLowerCase()}`,
    web_url: `https://dev.sankuai.com/code/repo-detail/${namespace}/${repository}/file/list`,
  });
};

export const repositoryUrlFromGit = (repoRoot = process.cwd()) => {
  try {
    return execFileSync("git", ["remote", "get-url", "origin"], {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
};

const createHeaders = ({ token, authSource, noCodeEnv }) => ({
  "Authorization": `Bearer ${token}`,
  "Content-Type": "application/json",
  "X-Rule-Protocol-Version": "1.0",
  ...(authSource === "nocode-sso"
    ? { "X-Rule-Auth-Source": "nocode-sso", "X-NoCode-Env": noCodeEnv }
    : {}),
});

const requestJson = async (url, init, fetchImpl) => {
  const response = await fetchImpl(url, init);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new RuleContextError(
      body?.error?.code || `RULE_CONTEXT_HTTP_${response.status}`,
      body?.error?.message || "规则上下文服务调用失败",
    );
  }
  return body;
};

const ruleApplies = (rule, stages, techStacks, domain) => {
  if (text(rule.standard_domain || domain) !== domain) return false;
  const ruleStages = Array.isArray(rule.applicable_stages)
    ? rule.applicable_stages.map(text)
    : [];
  if (ruleStages.length && !stages.some((stage) => ruleStages.includes(stage))) return false;
  const stacks = Array.isArray(rule.tech_stacks)
    ? rule.tech_stacks.map((stack) => text(stack).toLowerCase())
    : ["general"];
  return stacks.some((stack) => ["*", "all", "general", "shared"].includes(stack))
    || stacks.some((stack) => techStacks.includes(stack));
};

const mergeSnapshots = (snapshots) => {
  const rules = new Map();
  const releases = new Map();
  const sources = new Map();
  snapshots.forEach((snapshot) => {
    (snapshot?.rules || []).forEach((rule) => {
      const key = text(rule.rule_uid || `${rule.rule_set_id}:${rule.rule_id}`);
      if (key) rules.set(key, rule);
    });
    (snapshot?.release_refs || []).forEach((release) => {
      const key = text(release.release_id);
      if (key) releases.set(key, release);
    });
    (snapshot?.source_chain || []).forEach((source) => {
      const key = text(source.rule_uid);
      if (key) sources.set(key, source);
    });
  });
  return {
    rules: [...rules.values()].sort((left, right) =>
      text(left.rule_uid).localeCompare(text(right.rule_uid), "en")),
    release_refs: [...releases.values()],
    source_chain: [...sources.values()],
  };
};

const currentOrganization = (workspace) => (
  workspace?.selected_organization || workspace?.organization || null
);

const currentOrgContext = (identity, workspace) => {
  const organization = currentOrganization(workspace);
  if (!organization?.organization_id || !organization?.full_path) {
    throw new RuleContextError(
      "RULE_CONTEXT_ORGANIZATION_UNRESOLVED",
      "当前用户组织尚未建立可信上下文，请先登录规则平台完成组织观察",
    );
  }
  if (identity?.identity_status !== "verified" || !identity?.mis_id) {
    throw new RuleContextError(
      "RULE_CONTEXT_IDENTITY_UNVERIFIED",
      "规则上下文必须绑定服务端核验过的当前用户",
    );
  }
  return Object.freeze({
    identity_status: "verified",
    runtime_type: "skill_user_session",
    mis: identity.mis_id,
    organization_id: organization.organization_id,
    org_id: organization.organization_id,
    org_name: organization.display_name,
    org_name_path: organization.full_path,
    source: organization.source_system || "observed_login",
    confidence_status: organization.confidence_status || "observed",
    resolved_at: new Date().toISOString(),
  });
};

const resolveRepository = (workspace, repositoryUrl) => {
  const target = normalizeMCodeRepositoryUrl(repositoryUrl);
  const repository = (workspace?.repositories || []).find((item) => {
    try {
      return normalizeMCodeRepositoryUrl(item.repository_url).canonical_key
        === target.canonical_key;
    } catch {
      return false;
    }
  });
  return repository ? { ...repository, canonical_key: target.canonical_key } : null;
};

const organizationRuleSetIds = (workspace, domain) => unique(
  (workspace?.subscriptions || [])
    .filter((subscription) => (
      subscription.scope_type === "organization"
      && new Set(["organization_direct", "organization_inherited"]).has(
        subscription.source_type,
      )
      && (!subscription.standard_domain || subscription.standard_domain === domain)
    ))
    .map((subscription) => subscription.rule_set_id),
);

export const resolveEffectiveRules = async ({
  gatewayUrl = DEFAULT_GATEWAY,
  token,
  authSource = "supabase-auth",
  noCodeEnv = "prod",
  scope = "auto",
  repositoryUrl = "",
  stages = ["cr"],
  domain = "frontend",
  techStacks = ["general"],
  fetchImpl = globalThis.fetch,
} = {}) => {
  if (!token) {
    throw new RuleContextError(
      "RULE_CONTEXT_AUTH_REQUIRED",
      "宿主未注入短期用户会话；禁止使用 Cookie、Git 作者或系统账号代替",
    );
  }
  if (!SUPPORTED_SCOPES.has(scope)) {
    throw new RuleContextError("RULE_CONTEXT_SCOPE_INVALID", "scope 仅支持 auto、organization、repository");
  }
  const normalizedStages = unique(stages).map((stage) => stage.toLowerCase());
  const normalizedStacks = unique(techStacks).map((stack) => stack.toLowerCase());
  if (!normalizedStages.length || normalizedStages.some((stage) => !SUPPORTED_STAGES.has(stage))) {
    throw new RuleContextError("RULE_CONTEXT_STAGE_INVALID", "stage 仅支持 design、coding、cr");
  }
  if (!SUPPORTED_DOMAINS.has(domain) || !normalizedStacks.length) {
    throw new RuleContextError("RULE_CONTEXT_FILTER_INVALID", "治理域或技术栈不完整");
  }
  const base = gatewayUrl.replace(/\/$/, "");
  const headers = createHeaders({ token, authSource, noCodeEnv });
  const [meBody, workspaceBody] = await Promise.all([
    requestJson(`${base}/v1/rule-observability/me`, { headers }, fetchImpl),
    requestJson(`${base}/v1/rule-observability/organization/workspace`, { headers }, fetchImpl),
  ]);
  const workspace = workspaceBody.workspace || {};
  const organization = currentOrgContext(meBody.identity, workspace);
  const repository = repositoryUrl ? resolveRepository(workspace, repositoryUrl) : null;
  const effectiveScope = scope === "auto"
    ? (repository ? "repository" : "organization")
    : scope;

  if (effectiveScope === "repository" && !repository) {
    throw new RuleContextError(
      "RULE_CONTEXT_REPOSITORY_NOT_REGISTERED",
      "当前仓库未登记到当前用户组织，无法读取仓库直订阅规则",
    );
  }

  let merged;
  if (effectiveScope === "repository") {
    const snapshots = await Promise.all(normalizedStages.map(async (stage) => {
      const body = await requestJson(`${base}/v2/effective-rules`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          targetOrganizationId: organization.organization_id,
          targetRepositoryId: repository.repository_id,
          stage,
          standardDomain: domain,
          techStacks: normalizedStacks,
        }),
      }, fetchImpl);
      return body.snapshot;
    }));
    merged = mergeSnapshots(snapshots);
  } else {
    const ids = organizationRuleSetIds(workspace, domain);
    const details = await Promise.all(ids.map(async (ruleSetId) => {
      const body = await requestJson(
        `${base}/v1/rule-observability/l2-rule-sets/${encodeURIComponent(ruleSetId)}`,
        { headers },
        fetchImpl,
      );
      return body.detail || body;
    }));
    merged = mergeSnapshots(details.map((detail) => ({
      rules: (detail?.rules || [])
        .filter((rule) => ruleApplies(rule, normalizedStages, normalizedStacks, domain))
        .map((rule) => ({
          ...rule,
          scope_level: "L2",
          rule_set_id: detail?.rule_set?.rule_set_id,
          release_id: detail?.rule_set?.current_release_id,
        })),
      release_refs: detail?.rule_set?.current_release_id ? [{
        release_id: detail.rule_set.current_release_id,
        rule_set_id: detail.rule_set.rule_set_id,
        scope_level: "L2",
        source_type: "organization_subscription",
      }] : [],
      source_chain: [],
    })));
  }

  return Object.freeze({
    schema_version: "skill-effective-rules/v1",
    scope_type: effectiveScope,
    organization,
    repository: repository ? {
      repository_id: repository.repository_id,
      repository_url: repository.repository_url,
      canonical_key: repository.canonical_key,
    } : null,
    stages: normalizedStages,
    standard_domain: domain,
    tech_stacks: normalizedStacks,
    rules: merged.rules,
    release_refs: merged.release_refs,
    source_chain: merged.source_chain,
    source_precedence: effectiveScope === "repository"
      ? SOURCE_PRECEDENCE
      : SOURCE_PRECEDENCE.slice(1),
    resolved_at: new Date().toISOString(),
  });
};

export const renderEffectiveRulesMarkdown = (result) => {
  const lines = [
    "# 当前组织 / 仓库有效编码规范",
    "",
    `> 作用域：${result.scope_type}；组织：${result.organization.org_name_path}`,
    `> 仓库：${result.repository?.repository_url || "组织级"}`,
    `> 阶段：${result.stages.join(", ")}；技术栈：${result.tech_stacks.join(", ")}`,
    "",
  ];
  const grouped = new Map();
  for (const rule of result.rules) {
    const key = `${rule.scope_level || "L2"} · ${rule.rule_set_id || "unknown"}`;
    grouped.set(key, [...(grouped.get(key) || []), rule]);
  }
  for (const [group, rules] of grouped) {
    lines.push(`## ${group}`, "");
    for (const rule of rules) {
      lines.push(
        `### ${rule.rule_id || rule.local_rule_id || rule.rule_uid} · ${rule.title}`,
        "",
        text(rule.requirement || rule.rule_description || "未提供规则要求"),
        "",
        `- 适用阶段：${(rule.applicable_stages || []).join(", ") || "未声明"}`,
        `- 技术栈：${(rule.tech_stacks || []).join(", ") || "general"}`,
        `- 来源：${rule.source_path || "未提供"}`,
        "",
      );
    }
  }
  return `${lines.join("\n").trim()}\n`;
};

const parseArgs = (argv) => {
  const result = { stages: [], techStacks: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    const value = argv[index + 1];
    if (key === "--scope") result.scope = value;
    else if (key === "--repository-url") result.repositoryUrl = value;
    else if (key === "--repo-root") result.repoRoot = value;
    else if (key === "--stage") result.stages.push(...text(value).split(","));
    else if (key === "--domain") result.domain = value;
    else if (key === "--tech-stacks") result.techStacks.push(...text(value).split(","));
    else if (key === "--gateway-url") result.gatewayUrl = value;
    else if (key === "--token-env") result.tokenEnv = value;
    else if (key === "--auth-source") result.authSource = value;
    else if (key === "--nocode-env") result.noCodeEnv = value;
    else if (key === "--format") result.format = value;
    else if (key === "--output") result.output = value;
    else throw new RuleContextError("RULE_CONTEXT_ARGUMENT_INVALID", `未知参数：${key}`);
    index += 1;
  }
  return result;
};

const main = async () => {
  const args = parseArgs(process.argv.slice(2));
  const repositoryUrl = args.repositoryUrl || repositoryUrlFromGit(args.repoRoot || process.cwd());
  const tokenEnv = args.tokenEnv || "RULE_OBSERVABILITY_USER_TOKEN";
  const resolved = await resolveEffectiveRules({
    gatewayUrl: args.gatewayUrl,
    token: process.env[tokenEnv],
    authSource: args.authSource,
    noCodeEnv: args.noCodeEnv,
    scope: args.scope || "auto",
    repositoryUrl,
    stages: args.stages.length ? args.stages : ["cr"],
    domain: args.domain || "frontend",
    techStacks: args.techStacks.length ? args.techStacks : ["general"],
  });
  const content = args.format === "markdown"
    ? renderEffectiveRulesMarkdown(resolved)
    : `${JSON.stringify(resolved, null, 2)}\n`;
  if (args.output) await writeFile(path.resolve(args.output), content, "utf8");
  else process.stdout.write(content);
};

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    const code = error instanceof RuleContextError ? error.code : "RULE_CONTEXT_UNEXPECTED";
    process.stderr.write(`${code}: ${error.message}\n`);
    process.exitCode = 2;
  });
}
