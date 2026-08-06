#!/usr/bin/env node

/**
 * 阶段完成上报脚本
 *
 * 用法：
 *   node scripts/report-stage.js --stage <stage_key> [--context <workflow-context.json路径>]
 *
 * 参数：
 *   --stage    当前完成的阶段 key（必填）
 *              支持 fe-rd-workflow 内部 key: stage1 ~ stage7
 *              也支持 report 接口 key: env_check | repo_init | design | coding | review | launch | feedback
 *   --context  workflow-context.json 路径（可选，默认从 cwd 向上查找 .duo 目录）
 *
 * 必传字段（三个，自动获取）：
 *   title           优先使用 workflow-context.input.km_parent_id，拼成 "{mis号}-需求链接https://km.sankuai.com/collabpage/{id}"
 *                   其次从 workflow-context.input.prd_link 中解析 contentId，拼成 "需求-{id}-{userName}"
 *                   最后降级为 "fe-rd-workflow-{userName}"
 *   submitter_mis   优先取 workflow-context.input.mis
 *                   其次从 git config user.email 解析（取 @ 前部分）
 *   completed_stage 由 --stage 参数映射得到
 *
 * 可选字段：从 workflow-context.json 中尽力读取，有则上报，无则忽略。
 *
 * 设计原则：
 *   - workflow-context.json 必须存在，找不到则阻断（exit 1）。
 *   - 有 workflow-context.json 时：自动扫描并补报前序未上报阶段，上报成功后回写 reported_at。
 *   - workflow-context.json 中各 stage 的 reported_at 默认为 null，上报成功后由脚本回写为 ISO 时间戳。
 */

'use strict';

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { execSync } = require('child_process');

// ─── 常量 ────────────────────────────────────────────────────────────────────

const REPORT_API = 'https://yooz.sankuai.com/node/api/data/monitor/report';

const STAGE_MAP = {
  stage1: 'env_check',
  stage2: 'repo_init',
  'stage2.0': 'repo_init',
  'stage2.1': 'repo_init',
  'stage2.2': 'repo_init',
  stage3: 'design',
  'stage3.1': 'design',
  'stage3.2': 'design',
  'stage3.3': 'design',
  stage4: 'coding',
  'stage4.1': 'coding',
  'stage4.2': 'coding',
  'stage4.3': 'coding',
  stage5: 'review',
  stage6: 'launch',
  stage7: 'feedback',
};

const VALID_REPORT_STAGES = new Set([
  'env_check', 'repo_init', 'design', 'coding', 'review', 'launch', 'feedback',
]);

// ─── 参数解析 ─────────────────────────────────────────────────────────────────

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = { stage: null, context: null };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--stage' && args[i + 1])    parsed.stage   = args[++i];
    if (args[i] === '--context' && args[i + 1])  parsed.context = args[++i];
  }
  return parsed;
}

// ─── workflow-context.json 查找 ───────────────────────────────────────────────

function findWorkflowContext(explicitPath) {
  if (explicitPath) {
    const abs = path.resolve(explicitPath);
    if (fs.existsSync(abs)) return abs;
    const rel = path.resolve(process.cwd(), explicitPath);
    if (fs.existsSync(rel)) return rel;
    return null;
  }
  let dir = process.cwd();
  while (dir !== path.dirname(dir)) {
    const duoDir = path.join(dir, '.duo');
    if (fs.existsSync(duoDir)) {
      try {
        const entries = fs.readdirSync(duoDir, { withFileTypes: true });
        for (const entry of entries) {
          if (entry.isDirectory()) {
            const p = path.join(duoDir, entry.name, 'workflow-context.json');
            if (fs.existsSync(p)) return p;
          }
        }
      } catch {}
    }
    dir = path.dirname(dir);
  }
  return null;
}

// ─── 自动获取 submitter_mis ───────────────────────────────────────────────────

function getMisFromGit() {
  try {
    const email = execSync('git config user.email', { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
    // 取 @ 前部分作为 MIS
    return email.split('@')[0] || '';
  } catch {
    return '';
  }
}

function getGitUserName() {
  try {
    return execSync('git config --global user.name', { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
  } catch {
    return '';
  }
}

// ─── 触发会话链接生成（上报前同步执行，超时 8s 静默失败不阻塞）───────────────

/**
 * 同步尝试生成会话链接（确保上报时 session_links 已就位）
 * 超时 8s，失败静默不阻塞主流程
 */
function tryGenerateSessionLinkSync(contextPath) {
  try {
    const scriptPath = path.join(__dirname, 'generate-session-link.js');
    if (!fs.existsSync(scriptPath)) return;
    execSync(`node "${scriptPath}" --context "${contextPath}"`, {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 8000,
    });
  } catch {}
}

// ─── 从 context 中获取 session_link（所有会话 JSON 字符串）────────────────────

function getSessionLinkPayload(context) {
  if (!context || !context.runtime || !Array.isArray(context.runtime.session_links)) return undefined;
  const links = context.runtime.session_links;
  if (links.length === 0) return undefined;
  // 将所有会话数据序列化为 JSON 字符串上报
  return JSON.stringify(links);
}

// ─── 构建上报 payload ─────────────────────────────────────────────────────────

function buildPayload(context, reportStage) {
  const input   = (context && context.input)   || {};
  const meta    = (context && context.meta)    || {};
  const outputs = (context && context.outputs) || {};
  const fedo    = input.fedo_info || {};

  // ── 必传：title ──────────────────────────────────────────────────────────
  // 优先级：km_parent_id（用户输入的学城链接）> prd_link contentId > 兜底
  const gitUserName = getGitUserName();
  const mis = input.mis || getMisFromGit();
  const extractId = (url) => { const m = (url || '').match(/collabpage\/(\d+)/); return m ? m[1] : ''; };
  let title;
  if (input.km_parent_id) {
    const kmUrl = `https://km.sankuai.com/collabpage/${input.km_parent_id}`;
    title = `${mis}-需求链接${kmUrl}`;
  } else {
    const idFromPrd = extractId(input.prd_link);
    title = idFromPrd ? `需求-${idFromPrd}-${gitUserName}` : `fe-rd-workflow-${gitUserName}`;
  }


  // ── 必传：submitter_mis ──────────────────────────────────────────────────
  const submitter_mis = input.mis || getMisFromGit();

  // ── 必传：completed_stage ────────────────────────────────────────────────
  const completed_stage = reportStage;

  // ── 可选字段：尽力从 workflow-context 中读取 ─────────────────────────────
  const payload = { title, submitter_mis, completed_stage };

  const optional = {
    skill_name:       'fe-rd-workflow',
    skill_type:       '产研协作',
    workflow_version: meta.version        || undefined,
    agent_mode:       meta.mode           || undefined,
    project_name:     fedo.project_name   || undefined,
    team:             fedo.team           || undefined,
    team_id:          fedo.team_id        || undefined,
    ones_link:        fedo.ones_link      || undefined,
    fedo_link:        (outputs.fedo && outputs.fedo.task_url) || undefined,
    session_link:     getSessionLinkPayload(context),
  };

  // 只把有值的可选字段写入 payload
  for (const [k, v] of Object.entries(optional)) {
    if (v !== undefined && v !== '') payload[k] = v;
  }

  return payload;
}

// ─── HTTP POST ────────────────────────────────────────────────────────────────

function postReport(payload) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(payload);
    const url  = new URL(REPORT_API);
    const options = {
      hostname: url.hostname,
      port:     url.port || (url.protocol === 'https:' ? 443 : 80),
      path:     url.pathname,
      method:   'POST',
      headers: {
        'Content-Type':   'application/json',
        'Content-Length': Buffer.byteLength(data),
      },
      timeout: 10000,
    };
    const client = url.protocol === 'https:' ? https : http;
    const req = client.request(options, (res) => {
      let body = '';
      res.on('data', chunk => { body += chunk; });
      res.on('end', () => {
        try { resolve(JSON.parse(body)); }
        catch { resolve({ raw: body }); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('请求超时')); });
    req.write(data);
    req.end();
  });
}

// ─── 上报成功后回写 reported_at 到 workflow-context.json ─────────────────────

function writeReportedAt(contextPath, stageKey) {
  if (!contextPath) return;
  try {
    const raw = fs.readFileSync(contextPath, 'utf8');
    const ctx = JSON.parse(raw);
    // 确保路径存在
    if (!ctx.runtime) ctx.runtime = {};
    if (!ctx.runtime.stages) ctx.runtime.stages = {};
    if (!ctx.runtime.stages[stageKey]) ctx.runtime.stages[stageKey] = {};
    ctx.runtime.stages[stageKey].reported_at = new Date().toISOString();
    fs.writeFileSync(contextPath, JSON.stringify(ctx, null, 2), 'utf8');
    console.log(`📝 [report-stage] 已写入 reported_at: runtime.stages.${stageKey}.reported_at`);
  } catch (err) {
    // 写入失败静默，不阻断流程
    console.log(`⚠️ [report-stage] 写入 reported_at 失败: ${err.message}（不影响主流程）`);
  }
}

// ─── 补报：找出当前阶段之前所有已完成但未上报的父级阶段 ────────────────────────

/**
 * 父级阶段的有序列表（只扫描这些，子 stage 不单独上报）
 * 顺序即优先级，越靠前越先补报
 */
const PARENT_STAGE_ORDER = ['stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'stage6', 'stage7'];

/**
 * 返回需要补报的阶段列表（有序，不含当前阶段本身）
 * 条件：status 为 completed 或 skipped，且 reported_at 为 null/undefined
 */
function collectMissedStages(context, currentStageKey) {
  if (!context || !context.runtime || !context.runtime.stages) return [];

  const stages = context.runtime.stages;
  const currentIndex = PARENT_STAGE_ORDER.indexOf(currentStageKey);
  // 如果当前 stage 不在父级列表（如 stage4.1），取最近的父级作为截止位
  const cutoff = currentIndex >= 0 ? currentIndex : PARENT_STAGE_ORDER.length;

  const missed = [];
  for (let i = 0; i < cutoff; i++) {
    const key = PARENT_STAGE_ORDER[i];
    const stageData = stages[key];
    if (!stageData) continue;
    const isFinished = stageData.status === 'completed' || stageData.status === 'skipped';
    const isReported = stageData.reported_at != null;
    if (isFinished && !isReported) {
      missed.push(key);
    }
  }
  return missed;
}

// ─── 上报单个阶段（供补报和正常上报复用）─────────────────────────────────────

async function reportOne(stageKey, context, contextPath) {
  const reportStage = STAGE_MAP[stageKey] || stageKey;
  if (!VALID_REPORT_STAGES.has(reportStage)) return;

  const payload = buildPayload(context, reportStage);
  if (!payload.submitter_mis) return;

  try {
    const result = await postReport(payload);
    if (result && result.code === 0) {
      console.log(`✅ [report-stage] 已上报: ${reportStage} (${stageKey})`);
      writeReportedAt(contextPath, stageKey);
      // 回写后刷新内存中的 context，避免下次补报时重复
      if (contextPath) {
        try {
          const updated = JSON.parse(fs.readFileSync(contextPath, 'utf8'));
          Object.assign(context, updated);
        } catch {}
      }
    } else {
      console.log(`⚠️ [report-stage] 上报响应异常 (${stageKey}): ${JSON.stringify(result).slice(0, 200)}`);
    }
  } catch (err) {
    console.log(`⚠️ [report-stage] 上报失败 (${stageKey}): ${err.message}（不影响主流程）`);
  }
}

// ─── 主流程 ───────────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs();

  if (!args.stage) {
    console.log('⚠️ [report-stage] 缺少 --stage 参数，跳过上报');
    process.exit(0);
  }

  // 映射 stage key
  const reportStage = STAGE_MAP[args.stage] || args.stage;
  if (!VALID_REPORT_STAGES.has(reportStage)) {
    console.log(`⚠️ [report-stage] 无效的 stage "${args.stage}"，跳过上报`);
    process.exit(0);
  }

  // 读取 workflow-context.json（必须存在，找不到则阻断）
  let context = null;
  const contextPath = findWorkflowContext(args.context);
  if (!contextPath) {
    console.error('❌ [report-stage] 未找到 workflow-context.json，请确认已在项目 .duo 目录下初始化该文件，上报阻断');
    process.exit(1);
  }
  try {
    context = JSON.parse(fs.readFileSync(contextPath, 'utf8'));
  } catch (err) {
    console.error(`❌ [report-stage] 读取 workflow-context.json 失败: ${err.message}，上报阻断`);
    process.exit(1);
  }

  // ── 补报：自动上报当前阶段之前所有已完成但未上报的父级阶段 ──────────────
  // context 此时必定不为 null（前面已阻断）
  {
    const missed = collectMissedStages(context, args.stage);
    if (missed.length > 0) {
      console.log(`🔍 [report-stage] 检测到 ${missed.length} 个前序阶段未上报，自动补报: ${missed.join(', ')}`);
      for (const missedKey of missed) {
        await reportOne(missedKey, context, contextPath);
      }
    }
  }

  // ── 同步生成会话链接（确保上报时 session_links 已就位）────────────────────
  tryGenerateSessionLinkSync(contextPath);
  // 重新读取 context 以获取最新的 session_links
  try {
    context = JSON.parse(fs.readFileSync(contextPath, 'utf8'));
  } catch {}

  // ── 上报当前阶段 ─────────────────────────────────────────────────────────
  const payload = buildPayload(context, reportStage);

  // 校验必传字段
  if (!payload.submitter_mis) {
    console.log('⚠️ [report-stage] 无法获取 submitter_mis（workflow-context 与 git config 均无），跳过上报');
    process.exit(0);
  }

  // 检查当前阶段是否已上报（幂等保护）
  const currentStageData = context && context.runtime && context.runtime.stages && context.runtime.stages[args.stage];
  if (currentStageData && currentStageData.reported_at) {
    console.log(`ℹ️ [report-stage] 当前阶段 ${args.stage} 已上报于 ${currentStageData.reported_at}，跳过重复上报`);
    process.exit(0);
  }

  try {
    const result = await postReport(payload);
    if (result && result.code === 0) {
      console.log(`✅ [report-stage] 已上报: ${reportStage} (${args.stage})`);
      // 上报成功后，将 reported_at 回写到 workflow-context.json
      writeReportedAt(contextPath, args.stage);
    } else {
      console.log(`⚠️ [report-stage] 上报响应异常: ${JSON.stringify(result).slice(0, 200)}`);
    }
  } catch (err) {
    console.log(`⚠️ [report-stage] 上报失败: ${err.message}（不影响主流程）`);
  }

  process.exit(0);
}

main();
