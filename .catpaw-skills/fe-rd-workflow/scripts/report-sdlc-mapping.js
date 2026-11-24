#!/usr/bin/env node

/**
 * SDLC 任务 mapping 上报脚本（AI-SDLC 指标平台，非 Multica 上报方式）
 *
 * 文档依据：https://km.sankuai.com/collabpage/2777569481 「3.2.2 SDLC 任务 mapping 上报 → 非 Multica 的 SDLC 系统」
 * 依赖 Skill：sdlc-task-mapping-ingest（Friday Skillhub id=129649，run.sh CLI，方式一首选）
 *
 * 用法：
 *   1) 有 workflow-context.json（workflow 内阶段上报，首选）：
 *      node scripts/report-sdlc-mapping.js --context <workflow-context.json路径> [--dry-run] [--mode auto|cli|direct]
 *   2) 无 workflow-context.json（独立/补报模式，CLI 直传）：
 *      node scripts/report-sdlc-mapping.js --ones-url <ONES需求链接> \
 *        [--mis <mis>] [--session-id <会话ID>] [--agent-type catpaw|catdesk|codex] \
 *        [--stage-split design=2026-11-24T09:00:00+08:00~2026-11-24T11:30:00+08:00] \
 *        [--stage design --since <起始时间> --until <结束时间>] \
 *        [--task-name <任务名>] [--task-ext-id <自定义ID>] [--dry-run] [--mode auto|cli|direct]
 *      - 未传 --session-id 时自动从 ~/.catpaw/projects/ide-{path_hash}/ 取最近会话目录名
 *      - 未传 --agent-type / --session-source 时按运行环境探测（CatPaw IDE→catpaw、Desk→catdesk）
 *      - 阶段时间支持 ISO 字符串或毫秒/秒级时间戳，均转换为毫秒左闭右开 [startTime, endTime)
 *
 * 上报通道（双通道，对应文档 km 2777569481 两种上报方式）：
 *   - cli（方式一 Skill/CLI）：经 sdlc-task-mapping-ingest run.sh --stdin 上报，默认首选
 *   - direct（方式二 接口直报，备选）：ingest-get-token 换 token → sdlc-task-mapping-ingest
 *     Bearer 上报 envelope；--mode direct 指定，或 auto 模式下 run.sh 不可用时自动兑底
 *   - 两条通道上报同一 items 结构，服务端接口幂等可重复上报（单页≤50 items，本脚本仅上报 1 条）
 *
 * 设计原则：
 *   - 读取 workflow-context.json，组装单个 taskItem，通过 run.sh --stdin 上报（bare array 自动包装 envelope）
 *   - sdlcSourceType 固定为 FE_RD_WORKFLOW（服务端已注册枚举值，拼写必须与注册值完全一致）
 *   - agentType 非固定值：服务端以 (agentType, sessionId) 元组唯一标识 session，由上报方自行命名。
 *     本脚本按 session_links[].source 推导（catpaw_ide→catpaw、catpaw_desk→catdesk、codex→codex），
 *     缺失时按运行环境变量探测兑底，可用 env SDLC_MAPPING_AGENT_TYPE 显式覆盖
 *   - fe-rd-workflow 为「单 Session 多阶段」模式：上报 CatPaw 会话 + stageSplit 时间段（左闭右开 [start, end)）
 *   - sessionOp 使用 upsert：每次阶段完成时增量上报，避免 replace 抹掉此前已上报的 sessions
 *   - 失败不阻断主流程（exit 0），仅打印告警；成功后回写 runtime.sdlc_mapping.last_reported_at
 *   - --dry-run 透传给 run.sh，仅本地校验+生成 payload，不真实上传
 */

'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawnSync } = require('child_process');

// ─── 常量 ────────────────────────────────────────────────────────────────────

// ⚠️ 必须与服务端注册的 sdlcSourceType 枚举值完全一致（注册入口 km 2780681071）
const SDLC_SOURCE_TYPE = 'FE_RD_WORKFLOW';

// 上报 payload.source（仅审计用途）
const PAYLOAD_SOURCE = 'fe-rd-workflow-sync';

// ─── 接口直报（方式二备选通道，km 2777569481）────────────────────────────────
const TOKEN_URL = 'https://dbxctudbmbt20aw1jo.database.sankuai.com/functions/v1/ingest-get-token';
const INGEST_URL = 'https://dbxctudbmbt20aw1jo.database.sankuai.com/functions/v1/sdlc-task-mapping-ingest';
const TOKEN_PUBLIC_KEY = 'pk_ingest_a7f3d2e91b5c';
const TOKEN_SCENE = 'sdlc-task-mapping';

// sdlc-task-mapping-ingest run.sh 查找顺序
function findIngestRunSh() {
  if (process.env.SDLC_MAPPING_RUN_SH) return process.env.SDLC_MAPPING_RUN_SH;
  const candidates = [
    path.join(os.homedir(), '.claude', 'skills', 'sdlc-task-mapping-ingest', 'run.sh'),
    path.join(os.homedir(), '.codex', 'skills', 'sdlc-task-mapping-ingest', 'run.sh'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return null;
}

// ─── agentType 推导（非固定值，按会话来源/运行环境获取）────────────────────────

// session_links[].source → agentType 映射（source 由 generate-session-link.js 写入）
const SOURCE_TO_AGENT_TYPE = {
  catpaw_ide: 'catpaw',      // CatPaw IDE / CLI
  catpaw_desk: 'catdesk',    // CatDesk（CatPaw Desk 桌面端）
  catdesk: 'catdesk',
  catpaw: 'catpaw',
  codex: 'codex',            // Codex CLI（自动探测不到会话时由 Agent 手动写入）
  claude_code: 'claude_code',
  catx: 'catx',
};

// 运行环境探测（session_links[].source 缺失或为 'other' 时兑底）
function detectAgentTypeFromEnv() {
  if (process.env.CODEX_SANDBOX || process.env.CODEX_HOME) return 'codex';
  if (process.env.CLAUDECODE || process.env.CLAUDE_CODE_ENTRYPOINT) return 'claude_code';
  return 'catpaw';
}

function resolveAgentType(sessionSource) {
  // 显式覆盖优先（脚本调用方指定）
  if (process.env.SDLC_MAPPING_AGENT_TYPE) return process.env.SDLC_MAPPING_AGENT_TYPE;
  const mapped = SOURCE_TO_AGENT_TYPE[(sessionSource || '').toLowerCase()];
  if (mapped) return mapped;
  return detectAgentTypeFromEnv();
}

// fe-rd-workflow 子阶段 → SDLC 指标平台阶段（requirement/design/code/test）
// stageSplit 区间优先取子阶段时间戳；父阶段仅在无子阶段记录时兜底。
const STAGE_SPLIT_RULES = [
  { sdlcStage: 'requirement', keys: ['stage3.1'], fallback: 'stage3' },
  { sdlcStage: 'design',      keys: ['stage3.2', 'stage3.3'], fallback: null },
  { sdlcStage: 'code',        keys: ['stage4.1', 'stage4.2', 'stage4.3'], fallback: 'stage4' },
  { sdlcStage: 'test',        keys: ['stage5'], fallback: null },
];

// ─── 参数解析 ─────────────────────────────────────────────────────────────────

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = {
    context: null,
    dryRun: false,
    mode: 'auto',
    // 无 context 直报模式入参
    onesUrl: null,
    mis: null,
    sessionId: null,
    agentType: null,
    sessionSource: null,
    taskName: null,
    taskExtId: null,
    stage: null,
    since: null,
    until: null,
    stageSplits: [],
  };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--context' && args[i + 1]) parsed.context = args[++i];
    else if (args[i] === '--dry-run') parsed.dryRun = true;
    else if (args[i] === '--mode' && args[i + 1]) {
      const m = args[++i];
      if (!['auto', 'cli', 'direct'].includes(m)) {
        throw new Error(`--mode 仅支持 auto|cli|direct，收到: ${m}`);
      }
      parsed.mode = m;
    }
    else if (args[i] === '--ones-url' && args[i + 1]) parsed.onesUrl = args[++i];
    else if (args[i] === '--mis' && args[i + 1]) parsed.mis = args[++i];
    else if (args[i] === '--session-id' && args[i + 1]) parsed.sessionId = args[++i];
    else if (args[i] === '--agent-type' && args[i + 1]) parsed.agentType = args[++i];
    else if (args[i] === '--session-source' && args[i + 1]) parsed.sessionSource = args[++i];
    else if (args[i] === '--task-name' && args[i + 1]) parsed.taskName = args[++i];
    else if (args[i] === '--task-ext-id' && args[i + 1]) parsed.taskExtId = args[++i];
    else if (args[i] === '--stage' && args[i + 1]) parsed.stage = args[++i];
    else if (args[i] === '--since' && args[i + 1]) parsed.since = args[++i];
    else if (args[i] === '--until' && args[i + 1]) parsed.until = args[++i];
    else if (args[i] === '--stage-split' && args[i + 1]) parsed.stageSplits.push(args[++i]);
  }
  return parsed;
}

// ─── workflow-context.json 查找（与 report-stage.js 同规则）──────────────────

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

// ─── onesUrl / taskExtId 提取 ────────────────────────────────────────────────

/**
 * 从 ONES 链接提取需求 ID
 * 形如 https://ones.sankuai.com/ones/product/48148/workItem/requirement/detail/955001
 */
function extractOnesId(onesUrl) {
  const m = (onesUrl || '').match(/detail\/(\d+)/) || (onesUrl || '').match(/(\d{6,})/);
  return m ? m[1] : '';
}

// ─── stageSplit 组装（左闭右开 [startTime, endTime)，毫秒时间戳）──────────────

function buildStageSplit(stages) {
  const split = {};
  const get = (key) => (stages[key] ? stages[key] : null);

  for (const rule of STAGE_SPLIT_RULES) {
    const intervals = [];
    for (const key of rule.keys) {
      const st = get(key);
      if (!st) continue;
      const s = Date.parse(st.started_at);
      const e = Date.parse(st.completed_at);
      if (Number.isFinite(s) && Number.isFinite(e) && e > s) {
        intervals.push({ startTime: s, endTime: e });
      }
    }
    // 兜底：无任何子阶段时间戳时，用父阶段整段（仅 requirement/code 有兜底）
    if (intervals.length === 0 && rule.fallback) {
      const st = get(rule.fallback);
      if (st) {
        const s = Date.parse(st.started_at);
        const e = Date.parse(st.completed_at);
        if (Number.isFinite(s) && Number.isFinite(e) && e > s) {
          intervals.push({ startTime: s, endTime: e });
        }
      }
    }
    if (intervals.length > 0) split[rule.sdlcStage] = intervals;
  }
  return Object.keys(split).length > 0 ? split : undefined;
}

// ─── 无 context 直报模式：时间解析 / 环境与会话探测 / item 组装 ─────────────────

// SDLC 指标平台支持的阶段 key
const SDLC_STAGE_KEYS = ['requirement', 'design', 'code', 'test'];

/** 解析时间：支持毫秒时间戳(13位)、秒级时间戳(10位)、ISO 字符串 */
function parseTime(v) {
  if (v === null || v === undefined || v === '') return NaN;
  const s = String(v).trim();
  if (/^\d{13}$/.test(s)) return Number(s);
  if (/^\d{10}$/.test(s)) return Number(s) * 1000;
  return Date.parse(s);
}

/**
 * 从 CLI 入参组装 stageSplit（左闭右开，毫秒）
 *   --stage-split design=2026-11-24T09:00:00+08:00~2026-11-24T11:30:00+08:00（可重复）
 *   --stage design --since <start> --until <end>
 */
function buildStageSplitFromArgs(args) {
  const split = {};
  const push = (stage, startRaw, endRaw, origin) => {
    if (!SDLC_STAGE_KEYS.includes(stage)) {
      throw new Error(`阶段 key 非法: ${stage}（仅支持 ${SDLC_STAGE_KEYS.join('|')}），来源: ${origin}`);
    }
    const s = parseTime(startRaw);
    const e = parseTime(endRaw);
    if (!Number.isFinite(s) || !Number.isFinite(e)) {
      throw new Error(`阶段时间无法解析（${origin}）: start=${startRaw} end=${endRaw}`);
    }
    if (e <= s) {
      throw new Error(`阶段结束时间必须晚于开始时间（${origin}）: start=${startRaw} end=${endRaw}`);
    }
    if (!split[stage]) split[stage] = [];
    split[stage].push({ startTime: s, endTime: e });
  };

  for (const raw of args.stageSplits || []) {
    const m = String(raw).match(/^([A-Za-z]+)=(.+?)~(.+)$/);
    if (!m) {
      throw new Error(`--stage-split 格式应为 <stage>=<start>~<end>，收到: ${raw}`);
    }
    push(m[1].toLowerCase(), m[2], m[3], `--stage-split ${raw}`);
  }

  if (args.stage) {
    if (!args.since || !args.until) {
      throw new Error('--stage 需同时指定 --since 与 --until');
    }
    push(String(args.stage).toLowerCase(), args.since, args.until, '--stage/--since/--until');
  }

  return Object.keys(split).length > 0 ? split : undefined;
}

/** 判断运行环境：catpaw_desk / catpaw_ide */
function detectSessionSource() {
  const configContent = process.env.CATPAW_CONFIG_CONTENT;
  if (configContent) {
    try {
      const config = JSON.parse(configContent);
      if (config.source === 'CatPawDesk') return 'catpaw_desk';
      if (config.source === 'CatPawIDE' || config.source === 'CatPawCLI_IDE') return 'catpaw_ide';
    } catch {}
  }
  if (process.env.__CFBundleIdentifier === 'com.catpaw.cowork') return 'catpaw_desk';
  if (process.env.__CFBundleIdentifier) return 'catpaw_ide';
  if (process.env.CODEX_SANDBOX || process.env.CODEX_HOME) return 'codex';
  return 'catpaw_ide';
}

/** CatPaw Desk：通过 catdesk session current 获取会话 ID */
function getDeskConversationId() {
  try {
    const output = require('child_process').execSync('catdesk session current', {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 5000,
    }).trim();
    const data = JSON.parse(output);
    return data.conversationId || data.conversation_id || data.id || null;
  } catch {}
  return null;
}

/**
 * CatPaw IDE：从 ~/.catpaw/projects/ide-{path_hash}/ 取最近修改的会话目录名作为 conversationId
 * （与 generate-session-link.js 的兜底逻辑一致；无 context 时无法锚定，取最新会话并打印提示）
 */
function getIdeConversationId() {
  try {
    const projectsDir = path.join(os.homedir(), '.catpaw', 'projects');
    if (!fs.existsSync(projectsDir)) return null;

    const candidates = [];
    let p = process.cwd();
    const root = path.parse(p).root;
    while (p && p !== root) {
      candidates.push(p);
      const parent = path.dirname(p);
      if (parent === p) break;
      p = parent;
    }

    let targetDir = null;
    for (let i = candidates.length - 1; i >= 0; i--) {
      const hash = candidates[i].replace(/\//g, '-').replace(/^-/, '');
      const candidate = path.join(projectsDir, `ide-${hash}`);
      if (fs.existsSync(candidate)) { targetDir = candidate; break; }
    }
    if (!targetDir) return null;

    let latestId = null;
    let latestTime = 0;
    for (const entry of fs.readdirSync(targetDir, { withFileTypes: true })) {
      if (!entry.isDirectory() || entry.name.startsWith('.')) continue;
      try {
        const stat = fs.statSync(path.join(targetDir, entry.name));
        if (stat.mtimeMs > latestTime) { latestTime = stat.mtimeMs; latestId = entry.name; }
      } catch {}
    }
    return latestId || null;
  } catch {
    return null;
  }
}

// ─── sessions 组装 ───────────────────────────────────────────────────────────

/**
 * 从 runtime.session_links 组装 sessions。
 * agentType 非固定值：按每个 session 的 source 字段推导（catpaw_ide→catpaw、
 * catpaw_desk→catdesk、codex→codex），缺失时按运行环境探测兑底，避免跨环境 sessionId 碰撞。
 * fe-rd-workflow 为单会话跑全流程，stageSplit 挂到最新创建的会话（多会话续跑场景下，
 * 阶段时间归属最后活跃的那个会话；历史会话仍上报 sessionId 供平台归集 session 明细）。
 */
function buildSessions(context) {
  const links = (context.runtime && Array.isArray(context.runtime.session_links))
    ? context.runtime.session_links
    : [];
  if (links.length === 0) return { sessions: [], latestIndex: -1 };

  const sessions = links.map((l) => ({
    agentType: resolveAgentType(l.source),
    sessionId: l.conversation_id,
  }));

  // 找 created_at 最新的会话索引
  let latestIndex = 0;
  let latestTime = -Infinity;
  links.forEach((l, i) => {
    const t = Date.parse(l.created_at || '');
    if (Number.isFinite(t) && t > latestTime) {
      latestTime = t;
      latestIndex = i;
    }
  });
  return { sessions, latestIndex };
}

// ─── taskItem 组装 ───────────────────────────────────────────────────────────

function buildTaskItem(context, dryRun) {
  const input = (context && context.input) || {};
  const meta = (context && context.meta) || {};
  const outputs = (context && context.outputs) || {};
  const fedo = input.fedo_info || {};

  const mis = input.mis || '';
  const onesId = extractOnesId(fedo.ones_link);

  // onesUrl 为上报必填字段：优先 fedo_info.ones_link；缺失时阻断提示
  if (!fedo.ones_link) {
    return {
      error: 'workflow-context.input.fedo_info.ones_link 为空。onesUrl 是 SDLC mapping 上报的必填字段，'
        + '请在 Stage 1 输入检查时向用户收集 ONES 需求链接并写入 workflow-context.json 后重试。',
    };
  }

  // taskExtId：Task = ONES 需求 × 团队，取稳定 ID（ONES-{需求ID}）；无 ONES 时以学城需求文档兜底
  const taskExtId = onesId
    ? `ONES-${onesId}`
    : (input.km_parent_id ? `FE_RD_WORKFLOW-${input.km_parent_id}` : null);
  if (!taskExtId) {
    return { error: '无法推导 taskExtId（ones_link 与 km_parent_id 均缺失），跳过上报。' };
  }

  const { sessions, latestIndex } = buildSessions(context);
  const stageSplit = buildStageSplit((context.runtime && context.runtime.stages) || {});
  if (stageSplit && latestIndex >= 0) {
    sessions[latestIndex].stageSplit = stageSplit;
  }

  const item = {
    sdlcSourceType: SDLC_SOURCE_TYPE,
    taskExtId,
    onesUrl: fedo.ones_link,
    misList: mis ? [mis] : undefined,
    creator: mis || undefined,
    taskName: fedo.task_name || (input.km_parent_id
      ? `需求-${input.km_parent_id}` : 'fe-rd-workflow-task'),
    taskUrl: (outputs.fedo && outputs.fedo.task_url) || fedo.ones_link,
    sessionOp: 'upsert', // 增量更新，阶段推进过程中反复上报不抹除已有 sessions
    sessions,
  };
  // 清理 undefined 字段
  for (const k of Object.keys(item)) {
    if (item[k] === undefined) delete item[k];
  }
  return { item, hasSessions: sessions.length > 0 };
}

// ─── 无 context 直报模式：taskItem 组装 ────────────────────────────────────────

/**
 * 无 workflow-context.json 时，从 CLI 入参组装 taskItem（独立/补报模式）。
 * 必填：--ones-url；会话：--session-id 或自动探测；阶段：--stage-split / --stage+--since/--until。
 * 只组装输入的已有事实，不编造时间与会话。
 */
function buildStandaloneItem(args, context) {
  const input = (context && context.input) || {};
  const fedo = input.fedo_info || {};

  const onesUrl = args.onesUrl || fedo.ones_link;
  if (!onesUrl) {
    return {
      error: '未找到 workflow-context.json，且未提供 --ones-url。onesUrl 是 SDLC mapping 上报必填字段，'
        + '请补充：--ones-url <ONES需求链接> [--mis <mis>] [--stage-split design=<start>~<end>]',
    };
  }

  const onesId = extractOnesId(onesUrl);
  const taskExtId = args.taskExtId || (onesId ? `ONES-${onesId}` : null);
  if (!taskExtId) {
    return { error: '无法从 --ones-url 推导 taskExtId（非 ONES detail 链接时请显式传 --task-ext-id）' };
  }

  // 会话：显式 --session-id > 环境探测（Desk 用 catdesk session current，IDE 取最近会话目录）
  let sessionId = args.sessionId;
  let source = args.sessionSource;
  if (!sessionId) {
    if (!source) source = detectSessionSource();
    sessionId = source === 'catpaw_desk'
      ? (getDeskConversationId() || getIdeConversationId())
      : getIdeConversationId();
    if (sessionId) console.log(`🔍 [report-sdlc-mapping] 自动探测会话: ${sessionId}（source=${source}）`);
  }
  if (!sessionId) {
    return { error: '无法探测会话 ID，请显式传 --session-id <conversationId>（服务端以 (agentType, sessionId) 归集 session）' };
  }
  if (!source) source = detectSessionSource();

  const agentType = args.agentType || resolveAgentType(source);

  let stageSplit;
  try {
    stageSplit = buildStageSplitFromArgs(args);
  } catch (err) {
    return { error: `stageSplit 参数非法: ${err.message}` };
  }

  const mis = args.mis || input.mis || require('os').userInfo().username || '';

  const session = { agentType, sessionId };
  if (stageSplit) session.stageSplit = stageSplit;

  const item = {
    sdlcSourceType: SDLC_SOURCE_TYPE,
    taskExtId,
    onesUrl,
    misList: mis ? [mis] : undefined,
    creator: mis || undefined,
    taskName: args.taskName || fedo.task_name || `需求-${onesId || taskExtId}`,
    taskUrl: onesUrl,
    sessionOp: 'upsert',
    sessions: [session],
  };
  for (const k of Object.keys(item)) {
    if (item[k] === undefined) delete item[k];
  }
  return { item, hasSessions: true, standalone: true };
}

// ─── 调用 run.sh 上报 ────────────────────────────────────────────────────────

function callIngestRunSh(runShPath, items, dryRun) {
  const args = ['--stdin', '--source', PAYLOAD_SOURCE];
  if (dryRun) args.push('--dry-run');

  const payload = JSON.stringify(items);
  const result = spawnSync('bash', [runShPath, ...args], {
    input: payload,
    encoding: 'utf8',
    timeout: 60000,
  });

  const stdout = (result.stdout || '') + (result.stderr || '');
  return {
    ok: result.status === 0,
    status: result.status,
    output: stdout.trim().split('\n').filter(Boolean).slice(-5), // 只保留末尾几行（含 RESULT= 行）
  };
}

// ─── 接口直报（方式二备选通道，km 2777569481）─────────────────────────────────

/**
 * 原生 https POST JSON，返回 { status, body }；网络层异常返回 { status: -1, body: err.message }
 */
function httpsPostJson(url, headers, bodyObj, timeoutMs) {
  return new Promise((resolve) => {
    try {
      const urlObj = new URL(url);
      const body = JSON.stringify(bodyObj);
      const req = require('https').request({
        hostname: urlObj.hostname,
        path: urlObj.pathname + urlObj.search,
        method: 'POST',
        headers: Object.assign({
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
        }, headers),
        timeout: timeoutMs,
      }, (res) => {
        let data = '';
        res.on('data', (c) => { data += c; });
        res.on('end', () => resolve({ status: res.statusCode, body: data }));
      });
      req.on('timeout', () => { req.destroy(new Error('timeout')); });
      req.on('error', (err) => resolve({ status: -1, body: err.message }));
      req.write(body);
      req.end();
    } catch (err) {
      resolve({ status: -1, body: err.message });
    }
  });
}

/**
 * 方式二：接口直报：
 * 1) ingest-get-token（public_key + scene + mis）换 token，仅内存使用不落盘
 * 2) sdlc-task-mapping-ingest Bearer 上报 envelope（schema_version=1，接口幂等可重复上报；
 *    单页最多 50 items，本脚本仅上报 1 条无需分页）
 */
async function callIngestDirect(items, mis, dryRun) {
  const envelope = {
    schema_version: 1,
    source: PAYLOAD_SOURCE,
    batch_id: new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, 'Z') + '_fe-rd-workflow',
    items,
  };

  if (dryRun) {
    return {
      ok: true,
      status: 0,
      output: ['dry-run: envelope 已生成（接口直报未真实上传）', JSON.stringify(envelope)],
    };
  }

  // 1. 换 token（不落盘，仅本次请求内存使用）
  const tokenResp = await httpsPostJson(TOKEN_URL, null, {
    public_key: TOKEN_PUBLIC_KEY,
    scene: TOKEN_SCENE,
    mis,
  }, 15000);
  if (tokenResp.status !== 200) {
    return { ok: false, status: tokenResp.status, output: [`token 获取失败 http=${tokenResp.status}: ${String(tokenResp.body).slice(0, 200)}`] };
  }
  let token;
  try { token = JSON.parse(tokenResp.body).token; } catch {}
  if (!token) {
    return { ok: false, status: tokenResp.status, output: [`token 解析失败: ${String(tokenResp.body).slice(0, 200)}`] };
  }

  // 2. Bearer 上报
  const resp = await httpsPostJson(INGEST_URL, { Authorization: `Bearer ${token}` }, envelope, 30000);
  if (resp.status !== 200) {
    return { ok: false, status: resp.status, output: [`接口直报失败 http=${resp.status}: ${String(resp.body).slice(0, 200)}`] };
  }
  let parsed;
  try { parsed = JSON.parse(resp.body); } catch {}
  if (!parsed || parsed.ok !== true) {
    return { ok: false, status: resp.status, output: [`服务端返回 ok!=true: ${String(resp.body).slice(0, 300)}`] };
  }
  const up = parsed.upserted || {};
  return {
    ok: true,
    status: 0,
    output: [`服务端响应: ${JSON.stringify(parsed)}`, `upserted: tasks=${up.tasks != null ? up.tasks : '?'} sessions=${up.sessions != null ? up.sessions : '?'} sessions_unlinked=${up.sessions_unlinked != null ? up.sessions_unlinked : '?'}`],
  };
}

// ─── 回写 runtime.sdlc_mapping ───────────────────────────────────────────────

function writeSdlcMappingState(contextPath, state) {
  if (!contextPath) return;
  try {
    const ctx = JSON.parse(fs.readFileSync(contextPath, 'utf8'));
    if (!ctx.runtime) ctx.runtime = {};
    ctx.runtime.sdlc_mapping = Object.assign({}, ctx.runtime.sdlc_mapping, state);
    fs.writeFileSync(contextPath, JSON.stringify(ctx, null, 2), 'utf8');
    console.log('📝 [report-sdlc-mapping] 已回写 runtime.sdlc_mapping');
  } catch (err) {
    console.log(`⚠️ [report-sdlc-mapping] 回写 sdlc_mapping 失败: ${err.message}（不影响主流程）`);
  }
}

// ─── 主流程 ──────────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs();

  const contextPath = findWorkflowContext(args.context);
  let context = null;
  if (contextPath) {
    try {
      context = JSON.parse(fs.readFileSync(contextPath, 'utf8'));
    } catch (err) {
      if (!args.onesUrl) {
        console.error(`❌ [report-sdlc-mapping] 读取 workflow-context.json 失败: ${err.message}，上报阻断`);
        process.exit(1);
      }
      console.log(`⚠️ [report-sdlc-mapping] workflow-context.json 解析失败（${err.message}），改走 --ones-url 直报模式`);
    }
  }

  // 无 context（或显式传了 --ones-url）→ 走 CLI 直报模式
  const standalone = !context || Boolean(args.onesUrl);
  if (!contextPath && !args.onesUrl) {
    console.log('⚠️ [report-sdlc-mapping] 未找到 workflow-context.json，且未提供 --ones-url，无法上报。'
      + '直报用法：node scripts/report-sdlc-mapping.js --ones-url <ONES链接> [--mis <mis>]'
      + ' [--session-id <会话ID>] [--stage-split design=<start>~<end>] [--dry-run]');
    process.exit(1);
  }

  const runShPath = findIngestRunSh();
  // 通道选择：--mode cli|direct|auto（默认 auto = CLI 首选，run.sh 不可用或 CLI 失败时自动降级接口直报）
  const mis = args.mis || (context && context.input && context.input.mis) || require('os').userInfo().username || '';
  let useDirect = false;
  if (args.mode === 'direct') {
    useDirect = true;
    console.log('ℹ️ [report-sdlc-mapping] 指定 --mode direct，走方式二接口直报');
  } else if (!runShPath) {
    if (args.mode === 'cli') {
      console.log('⚠️ [report-sdlc-mapping] --mode cli 但未找到 sdlc-task-mapping-ingest run.sh'
        + '（~/.claude/skills 或 ~/.codex/skills 下），跳过 SDLC mapping 上报。'
        + '安装方式：mtskills install sdlc-task-mapping-ingest');
      process.exit(0);
    }
    useDirect = true;
    console.log('ℹ️ [report-sdlc-mapping] 未找到 sdlc-task-mapping-ingest run.sh，自动降级为方式二接口直报'
      + '（安装 CLI 后恢复首选：mtskills install sdlc-task-mapping-ingest）');
  }

  const built = standalone
    ? buildStandaloneItem(args, context)
    : buildTaskItem(context, args.dryRun);
  if (built.error) {
    console.log(`⚠️ [report-sdlc-mapping] ${built.error}`);
    process.exit(standalone && !contextPath ? 1 : 0);
  }
  if (!built.hasSessions) {
    console.log('ℹ️ [report-sdlc-mapping] runtime.session_links 为空（尚未生成 CatPaw 会话链接），本次跳过，待下次阶段上报时补报');
    process.exit(0);
  }
  if (built.standalone) {
    console.log('ℹ️ [report-sdlc-mapping] 无 workflow-context 直报模式：'
      + `taskExtId=${built.item.taskExtId} agentType=${built.item.sessions[0].agentType}`
      + `${built.item.sessions[0].stageSplit ? ` stageSplit=${Object.keys(built.item.sessions[0].stageSplit).join(',')}` : '（未提供阶段时间段）'}`);
  }

  let result;
  let channel;
  if (useDirect) {
    channel = 'direct';
    result = await callIngestDirect([built.item], mis, args.dryRun);
  } else {
    channel = 'cli';
    result = callIngestRunSh(runShPath, [built.item], args.dryRun);
    // auto 模式下 CLI 失败（非 dry-run）自动降级接口直报重试一次
    if (!result.ok && !args.dryRun && args.mode === 'auto') {
      console.log(`⚠️ [report-sdlc-mapping] CLI 通道失败（exit=${result.status}），自动降级为方式二接口直报重试`);
      for (const line of result.output) console.log(`   ${line}`);
      channel = 'direct';
      result = await callIngestDirect([built.item], mis, false);
    }
  }
  for (const line of result.output) console.log(`   ${line}`);

  if (result.ok) {
    console.log(`✅ [report-sdlc-mapping] SDLC mapping 上报${args.dryRun ? '（dry-run 校验通过，未真实上传）' : '完成'}`
      + ` [通道: ${channel}]: ${SDLC_SOURCE_TYPE} / ${built.item.taskExtId} / sessions=${built.item.sessions.length}`);
    writeSdlcMappingState(contextPath, {
      last_reported_at: new Date().toISOString(),
      last_result: args.dryRun ? 'dry-run' : `success(${channel})`,
      task_ext_id: built.item.taskExtId,
    });
  } else {
    console.log(`⚠️ [report-sdlc-mapping] ${channel === 'cli' ? `run.sh 退出码 ${result.status}` : `接口直报失败（status=${result.status}）`}，上报失败（不影响主流程，下个阶段完成时会重试）`);
    writeSdlcMappingState(contextPath, {
      last_attempted_at: new Date().toISOString(),
      last_result: `failed(channel=${channel},status=${result.status})`,
    });
  }
  process.exit(0);
}

main();
