#!/usr/bin/env node
/* eslint-disable no-console */
/**
 * trade-fe-knowledge-editor · validate.js
 *
 * 对某个业务组（<group>）相关的 .md 文件做结构化校验。
 * 与 references/quality-gates.md 中的 G1-G14 规则一一对应。
 *
 * 使用前提：当前工作目录必须在 trade-fe-rule 仓库内（根目录或任意子目录均可）。
 *
 * 用法：
 *   cd <trade-fe-rule 仓库>
 *   node <path-to-skill>/scripts/validate.js <group> [--scope <kinds>] [--json | --pr-summary]
 *
 *   --scope        逗号分隔的文件 kind 列表，仅校验这些 kind 的文件（默认全量扫描）。
 *                  合法 kind：overview, glossary, business-rules, design-patterns,
 *                             service-maps, coding-standards, adr, domain-models,
 *                             domain-entities, domain-enums, domain-state-machines,
 *                             pitfalls, nfr, page-index, all
 *                  示例：--scope page-index,glossary
 *                       --scope domain-models          （等价于 entities+enums+state-machines 三项）
 *                       --scope all                    （显式全量，与省略 --scope 一致）
 *   --json         以 JSON 格式输出完整报告（适合程序解析）。
 *   --pr-summary   以 Markdown 格式输出 PR description 可嵌入的摘要
 *                  （auto 模式下由 auto-pr.sh 采集，拼接到 PR description 的"validate 校验结果"节）。
 *
 * 仓库根定位：从 process.cwd() 向上查找，直到遇到"同时存在 AGENTS.md / context-docs/ / spec/ 的目录"。
 * 若不在仓库内 → 报错退出 2，提示用户 cd 到仓库中。
 *
 * 退出码：
 *   0 = 所有文件通过（可能有 WARN）
 *   1 = 存在 ERROR
 *   2 = 参数错误 / 不在 trade-fe-rule 仓库内
 *
 * 依赖：Node 18+，零外部依赖（自实现简易 YAML frontmatter 解析）。
 */

'use strict';

const fs = require('fs');
const path = require('path');

const ALLOWED_GROUPS = ['food', 'gc', 'ticket', 'hotel', 'platform'];

/**
 * kind -> 相对路径（相对仓库根）映射。
 * 用 ${group} 作为占位符，在 listTargetFiles 里替换。
 * 一个 kind 可对应多个文件（如 domain-models）。
 */
const KIND_TO_PATHS = {
  'overview': ['context-docs/overviews/${group}.md'],
  'glossary': ['context-docs/glossary/${group}.md'],
  'business-rules': ['context-docs/business-rules/${group}.md'],
  'design-patterns': ['context-docs/design-patterns/${group}.md'],
  'service-maps': ['context-docs/service-maps/${group}.md'],
  'coding-standards': ['spec/coding-standards/${group}.md'],
  'adr': ['spec/adr/${group}.md'],
  'domain-models': [
    'spec/domain-models/${group}/entities.md',
    'spec/domain-models/${group}/enums.md',
    'spec/domain-models/${group}/state-machines.md',
  ],
  'domain-entities': ['spec/domain-models/${group}/entities.md'],
  'domain-enums': ['spec/domain-models/${group}/enums.md'],
  'domain-state-machines': ['spec/domain-models/${group}/state-machines.md'],
  'pitfalls': ['spec/pitfalls/${group}.md'],
  'nfr': ['spec/nfr/${group}.md'],
  'page-index': ['context-docs/page-assets/${group}/page-index.md'],
};

const ALL_KINDS = [
  'overview',
  'glossary',
  'business-rules',
  'design-patterns',
  'service-maps',
  'coding-standards',
  'adr',
  'domain-models',
  'pitfalls',
  'nfr',
  'page-index',
];

/** 判断目录是否是 trade-fe-rule 仓库根（需同时满足三个证据） */
function isRepoRoot(dir) {
  return (
    fs.existsSync(path.join(dir, 'AGENTS.md')) &&
    fs.existsSync(path.join(dir, 'context-docs')) &&
    fs.existsSync(path.join(dir, 'spec'))
  );
}

/** 从 startDir 起向上查找仓库根，找不到返回 null */
function findRepoRootUpward(startDir) {
  let dir = path.resolve(startDir);
  while (true) {
    if (isRepoRoot(dir)) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) return null; // 到达文件系统根
    dir = parent;
  }
}

/** 从当前工作目录向上查找 trade-fe-rule 仓库根，找不到返回 null */
function resolveRepoRoot() {
  return findRepoRootUpward(process.cwd());
}

// 以仓库 trade-fe-rule 实际落盘 category 为准（grep 统计）
const CATEGORY_ENUM = new Set([
  'adr',
  'business-flow',
  'business-rule',
  'coding-conventions',
  'design-pattern',
  'domain-model',
  'glossary',
  'meta',
  'nfr',
  'onboarding',
  'overview',
  'page-asset',
  'pitfall',
  'process',
  'service-map',
]);

const DOMAIN_ENUM = new Set([
  'mrn', 'max', 'miniprogram', 'h5', 'duo', 'general', 'ci-cd',
  'monitoring', 'knowledge-management',
  'food', 'gc', 'ticket', 'hotel', 'platform',
]);

const TODAY = new Date().toISOString().slice(0, 10);

/**
 * 解析 --scope 值为 kind 列表；未指定/'all' → 返回全量。
 * 非法 kind → 抛错，由调用方 exit 2。
 */
function resolveKinds(scopeArg) {
  if (!scopeArg || scopeArg === 'all') return ALL_KINDS.slice();
  const raw = scopeArg
    .split(',')
    .map(s => s.trim())
    .filter(Boolean);
  const invalid = raw.filter(k => !(k in KIND_TO_PATHS));
  if (invalid.length) {
    const err = new Error(
      `非法 --scope kind: ${invalid.join(', ')}\n` +
      `合法值: ${Object.keys(KIND_TO_PATHS).join(', ')}, all`
    );
    err.code = 'BAD_SCOPE';
    throw err;
  }
  return raw;
}

function listTargetFiles(group, repoRoot, kinds) {
  const rels = [];
  const seen = new Set();
  for (const kind of kinds) {
    for (const tmpl of KIND_TO_PATHS[kind]) {
      const rel = tmpl.replace('${group}', group);
      if (!seen.has(rel)) {
        seen.add(rel);
        rels.push(rel);
      }
    }
  }
  return rels
    .map(rel => ({ rel, abs: path.join(repoRoot, rel) }))
    .filter(f => fs.existsSync(f.abs));
}

/** 解析 frontmatter：识别 --- 分隔的 YAML 头，极简实现，仅支持 key: value、数组（- item）、布尔、日期字符串 */
function parseFrontmatter(text) {
  if (!text.startsWith('---')) return { fm: null, body: text, rawFm: '' };
  const end = text.indexOf('\n---', 3);
  if (end === -1) return { fm: null, body: text, rawFm: '' };
  const raw = text.slice(3, end).replace(/^\n/, '');
  const body = text.slice(end + 4).replace(/^\n/, '');
  const fm = {};
  const lines = raw.split('\n');
  let currentKey = null;
  for (const line of lines) {
    if (/^[A-Za-z_][A-Za-z0-9_-]*\s*:/.test(line)) {
      const idx = line.indexOf(':');
      const key = line.slice(0, idx).trim();
      const val = line.slice(idx + 1).trim();
      if (val === '') {
        fm[key] = [];
        currentKey = key;
      } else {
        fm[key] = parseScalar(val);
        currentKey = null;
      }
    } else if (/^\s*-\s+/.test(line) && currentKey && Array.isArray(fm[currentKey])) {
      fm[currentKey].push(parseScalar(line.replace(/^\s*-\s+/, '').trim()));
    }
  }
  return { fm, body, rawFm: raw };
}

function parseScalar(v) {
  if (v === 'true') return true;
  if (v === 'false') return false;
  // 去除两端引号
  return v.replace(/^['"]/, '').replace(/['"]$/, '');
}

/** 字符宽度计数：中文按 1 计（需求原文 ≤ 120 字） */
function charCount(s) {
  return [...s].length;
}

function validateOneFile(rel, abs, group) {
  const errors = [];
  const warnings = [];
  const text = fs.readFileSync(abs, 'utf-8');
  const lines = text.split('\n');

  // G1 文件行数（已取消硬上限与预警阈值，保留占位以便未来按需扩展；当前不产生任何 error/warning）

  const { fm, body } = parseFrontmatter(text);

  // G2/G3/G4/G5/G6 frontmatter
  if (!fm) {
    errors.push({ rule: 'G2', message: '缺失 YAML frontmatter（文件顶部必须以 --- 开始）' });
  } else {
    if (!fm.category) errors.push({ rule: 'G2', message: 'frontmatter.category 缺失' });
    else if (!CATEGORY_ENUM.has(fm.category)) {
      errors.push({ rule: 'G3', message: `category='${fm.category}' 不在允许集（见 metadata-spec.md）` });
    }
    if (!fm.description) errors.push({ rule: 'G2', message: 'frontmatter.description 缺失' });
    else if (charCount(fm.description) > 120) {
      warnings.push({ rule: 'G4', message: `description 长度 ${charCount(fm.description)} > 120，建议精简` });
    }
    if (!fm.domain) errors.push({ rule: 'G2', message: 'frontmatter.domain 缺失' });
    else if (!DOMAIN_ENUM.has(fm.domain)) {
      errors.push({ rule: 'G3', message: `domain='${fm.domain}' 不在允许集` });
    }
    if (!fm.tags || !Array.isArray(fm.tags) || fm.tags.length < 5) {
      warnings.push({ rule: 'G5', message: `tags 数量 ${Array.isArray(fm.tags) ? fm.tags.length : 0} < 5，建议补齐` });
    }
    if (!fm.last_updated) {
      warnings.push({ rule: 'G6', message: 'last_updated 缺失，建议设为今天 ' + TODAY });
    } else if (!/^\d{4}-\d{2}-\d{2}$/.test(fm.last_updated)) {
      errors.push({ rule: 'G6', message: `last_updated='${fm.last_updated}' 不符合 YYYY-MM-DD 格式` });
    } else if (fm.last_updated > TODAY) {
      errors.push({ rule: 'G6', message: `last_updated='${fm.last_updated}' 晚于今天` });
    }

    // G11 group 归属
    if (fm.domain && ![group, 'general', 'mrn', 'max', 'duo', 'miniprogram', 'h5'].includes(fm.domain)) {
      warnings.push({ rule: 'G11', message: `文件路径属于 ${group}，但 domain=${fm.domain}，请确认是否应当归属` });
    }
  }

  // G7 H1 存在
  const firstHeading = body.split('\n').find(l => /^#\s+/.test(l));
  if (!firstHeading) {
    errors.push({ rule: 'G7', message: '正文缺失 H1（# 开头的一级标题）' });
  }

  // G9 内部链接有效性（仅校验 related 字段 + 正文相对链接）
  if (fm && Array.isArray(fm.related)) {
    for (const rp of fm.related) {
      const target = path.resolve(path.dirname(abs), rp);
      if (!fs.existsSync(target)) {
        warnings.push({ rule: 'G9', message: `related 路径不存在: ${rp}` });
      }
    }
  }
  const linkRe = /\[[^\]]+\]\((\.{1,2}\/[^)]+\.md)\)/g;
  let m;
  while ((m = linkRe.exec(body)) !== null) {
    const target = path.resolve(path.dirname(abs), m[1]);
    if (!fs.existsSync(target)) {
      warnings.push({ rule: 'G9', message: `正文相对链接目标不存在: ${m[1]}` });
    }
  }

  // G10 有效内容行占比
  const totalLines = lines.length;
  let effective = 0;
  let inFence = false;
  for (const l of lines) {
    if (/^```/.test(l)) { inFence = !inFence; continue; }
    if (inFence) { effective += 1; continue; }
    const trimmed = l.trim();
    if (trimmed === '') continue;
    if (trimmed.startsWith('<!--') && trimmed.endsWith('-->')) continue;
    effective += 1;
  }
  const ratio = totalLines > 0 ? effective / totalLines : 0;
  if (ratio < 0.6) {
    warnings.push({ rule: 'G10', message: `有效内容行占比 ${(ratio * 100).toFixed(0)}% < 60%` });
  }

  // G14 coding-standards 中禁止裸 any
  if (rel.includes('spec/coding-standards/')) {
    const codeRe = /```(?:ts|tsx|typescript)[\s\S]*?```/g;
    let cm;
    while ((cm = codeRe.exec(body)) !== null) {
      if (/\bany\b/.test(cm[0]) && !/反例|错误写法|AP-|bad/.test(cm[0])) {
        warnings.push({ rule: 'G14', message: '代码块出现 `any`，若非反例请改为具体类型' });
        break;
      }
    }
  }

  return { path: rel, errors, warnings };
}

function validateGlobal(repoRoot) {
  const errors = [];
  const agentsPath = path.join(repoRoot, 'AGENTS.md');
  if (!fs.existsSync(agentsPath)) {
    errors.push({ rule: 'G12', message: '仓库根 AGENTS.md 不存在' });
  }
  return errors;
}

/**
 * 取 --scope 的值，支持 `--scope=a,b` 和 `--scope a,b` 两种形式。
 */
function extractScopeArg(args) {
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a.startsWith('--scope=')) return a.slice('--scope='.length);
    if (a === '--scope') return args[i + 1];
  }
  return null;
}

/**
 * 按 Markdown 格式输出给 PR description 用的摘要：
 *   ## validate.js 校验结果
 *   - 命令: node <path>/validate.js <group> --scope <kinds>
 *   - 仓库根: <repoRoot>
 *   - 范围: <scope>
 *   - 扫描文件: N
 *   - 汇总: errors=X warnings=Y
 *
 *   ✓ <relPath>: no issues
 *   ⚠ <relPath>: [G5] tags ... / [G1] ...
 */
function formatPrSummary(report) {
  const { group, repoRoot, scope, globalErrors, files, summary } = report;
  const scopeStr = Array.isArray(scope) ? scope.join(', ') : String(scope);
  const lines = [];
  lines.push('## validate.js 校验结果');
  lines.push('');
  lines.push(`- **group**: \`${group}\``);
  lines.push(`- **范围**: \`${scopeStr}\``);
  lines.push(`- **扫描文件**: ${summary.scannedFiles} 个`);
  lines.push(
    `- **汇总**: errors=${summary.errors} warnings=${summary.warnings} ${summary.errors === 0 ? '✅' : '❌'}`
  );
  if (globalErrors && globalErrors.length) {
    lines.push('');
    lines.push('### 全局错误');
    for (const e of globalErrors) lines.push(`- [ERROR][${e.rule}] ${e.message}`);
  }
  lines.push('');
  lines.push('### 按文件汇总');
  if (files.length === 0) {
    lines.push('- (无匹配文件)');
  } else {
    for (const f of files) {
      if (!f.errors.length && !f.warnings.length) {
        lines.push(`- ✅ \`${f.path}\`: no issues`);
      } else {
        const parts = [];
        for (const e of f.errors) parts.push(`[ERROR][${e.rule}] ${e.message}`);
        for (const w of f.warnings) parts.push(`[WARN][${w.rule}] ${w.message}`);
        lines.push(`- ${f.errors.length ? '❌' : '⚠️'} \`${f.path}\`: ${parts.join('; ')}`);
      }
    }
  }
  return lines.join('\n');
}

function main() {
  const args = process.argv.slice(2);
  const asJson = args.includes('--json');
  const asPrSummary = args.includes('--pr-summary');
  if (asJson && asPrSummary) {
    console.error('--json 与 --pr-summary 不能同时指定');
    process.exit(2);
  }
  const scopeArg = extractScopeArg(args);

  // 取第一个裸位置参数作为 group（需排除 --scope 的值）
  const scopeIdx = args.indexOf('--scope');
  const group = args.find((a, i) => {
    if (a.startsWith('--')) return false;
    if (scopeIdx !== -1 && i === scopeIdx + 1) return false; // 是 --scope 的值
    return true;
  });

  if (!group) {
    console.error('用法: node <path-to-skill>/scripts/validate.js <group> [--scope <kinds>] [--json]');
    console.error('合法 group: ' + ALLOWED_GROUPS.join(', '));
    console.error('合法 scope kind: ' + Object.keys(KIND_TO_PATHS).join(', ') + ', all');
    console.error('前提: 必须在 trade-fe-rule 仓库任意目录内执行');
    process.exit(2);
  }
  if (!ALLOWED_GROUPS.includes(group)) {
    console.error(`group='${group}' 不合法。合法值: ${ALLOWED_GROUPS.join(', ')}`);
    process.exit(2);
  }

  let kinds;
  try {
    kinds = resolveKinds(scopeArg);
  } catch (e) {
    if (e.code === 'BAD_SCOPE') {
      console.error(e.message);
      process.exit(2);
    }
    throw e;
  }

  const repoRoot = resolveRepoRoot();
  if (!repoRoot) {
    console.error('当前工作目录不在 trade-fe-rule 仓库内。');
    console.error('请先 cd 到仓库根或其任意子目录再执行。');
    console.error('仓库识别条件：目录同时存在 AGENTS.md / context-docs/ / spec/');
    process.exit(2);
  }

  const scoped = !!scopeArg && scopeArg !== 'all';
  // 范围锁定模式：不跑全局检查（G12 AGENTS.md 归属仓库 owner），避免越权
  const globalErrors = scoped ? [] : validateGlobal(repoRoot);
  const targetFiles = listTargetFiles(group, repoRoot, kinds);
  const fileReports = targetFiles.map(f => validateOneFile(f.rel, f.abs, group));

  const totalErrors = globalErrors.length + fileReports.reduce((s, r) => s + r.errors.length, 0);
  const totalWarnings = fileReports.reduce((s, r) => s + r.warnings.length, 0);
  const report = {
    group,
    repoRoot,
    scope: scoped ? kinds : 'all',
    globalErrors,
    files: fileReports,
    summary: { errors: totalErrors, warnings: totalWarnings, scannedFiles: fileReports.length },
  };

  if (asJson) {
    console.log(JSON.stringify(report, null, 2));
  } else if (asPrSummary) {
    console.log(formatPrSummary(report));
  } else {
    console.log(`\n[trade-fe-knowledge-editor · validate] group=${group}`);
    console.log(`仓库根: ${repoRoot}`);
    if (scoped) {
      console.log(`范围锁定 (--scope): ${kinds.join(', ')}`);
      console.log('（严格模式：仅校验以上 kind 命中的文件，不联动检测其他内容）');
    } else {
      console.log('范围: all （全量扫描）');
    }
    console.log(`扫描文件: ${fileReports.length} 个`);
    if (globalErrors.length) {
      console.log('\n== 全局错误 ==');
      globalErrors.forEach(e => console.log(`  [ERROR][${e.rule}] ${e.message}`));
    }
    for (const f of fileReports) {
      if (!f.errors.length && !f.warnings.length) continue;
      console.log(`\n-- ${f.path}`);
      f.errors.forEach(e => console.log(`  [ERROR][${e.rule}] ${e.message}`));
      f.warnings.forEach(w => console.log(`  [WARN ][${w.rule}] ${w.message}`));
    }
    console.log(`\n== 汇总 == errors=${totalErrors} warnings=${totalWarnings}`);
  }

  process.exit(totalErrors > 0 ? 1 : 0);
}

main();
