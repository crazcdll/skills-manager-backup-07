#!/usr/bin/env bash
# =============================================================================
# stage-flow.sh — fe-rd-workflow 阶段流转控制脚本（唯一合法的状态流转入口）
#
# 设计目标：
#   阶段状态流转不再由 Agent 手改 workflow-context.json，全部经本脚本校验后写入：
#   - 校验阶段顺序（禁止跳步）、上报门禁（前一阶段 completed 但 reported_at 为空 → 阻断）
#   - 原子写入 workflow-context.json，并追加流转日志 stage-flow.log
#   - 每次操作后打印精确的阶段流转链路（状态、时间、门禁告警）
#
# 用法：
#   bash stage-flow.sh [--context <workflow-context.json路径>] show
#   bash stage-flow.sh [--context <...>] next                # 推进到下一个阶段
#   bash stage-flow.sh [--context <...>] start <stage_key>    # 进入某阶段
#   bash stage-flow.sh [--context <...>] complete <stage_key> # 完成某阶段
#   bash stage-flow.sh [--context <...>] skip <stage_key> --reason "原因"
#   bash stage-flow.sh [--context <...>] fail <stage_key> [--message "..."]
#   bash stage-flow.sh [--context <...>] gate                 # 仅校验上报门禁
#   bash stage-flow.sh [--context <...>] reset-from <stage_key> --reason "..."  # 用户确认重跑：该阶段及之后全部重置为 pending
#
#   --context 可省略，默认从 cwd 向上查找 .duo/*/workflow-context.json
#   exit 0 = 成功；exit 1 = 校验失败/门禁未通过
# =============================================================================
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  grep -E '^#   bash stage-flow|^#   --context|^#   exit' "$0" | sed 's/^# \{0,2\}//'
  exit 0
fi

exec node - "$@" <<'NODE_EOF'
'use strict';
const fs = require('fs');
const path = require('path');

// ─── 颜色 ──────────────────────────────────────────────────────────────────
// 非 TTY（管道/工具捕获）或 NO_COLOR 时禁色，避免转义符被剥离后残留 [0m 字样
const COLOR_OFF = !process.stdout.isTTY || process.env.NO_COLOR;
const C = COLOR_OFF
  ? { red: '', green: '', yellow: '', cyan: '', dim: '', bold: '', nc: '' }
  : {
      red: '\x1b[0;31m', green: '\x1b[0;32m', yellow: '\x1b[1;33m',
      cyan: '\x1b[0;36m', dim: '\x1b[2m', bold: '\x1b[1m', nc: '\x1b[0m',
    };
const ok = (m) => console.log(`${C.green}✅ [stage-flow]${C.nc} ${m}`);
const err = (m) => { console.error(`${C.red}❌ [stage-flow]${C.nc} ${m}`); process.exit(1); };
const warn = (m) => console.log(`${C.yellow}⚠️  [stage-flow]${C.nc} ${m}`);

// ─── 阶段定义（与 SKILL.md 阶段表一致） ─────────────────────────────────────
const STAGE_ORDER = [
  'stage1', 'stage2', 'stage2.0', 'stage2.1', 'stage2.2',
  'stage3', 'stage3.1', 'stage3.2', 'stage3.3',
  'stage4', 'stage4.1', 'stage4.2', 'stage4.3',
  'stage5', 'stage6', 'stage7',
];
const MAIN_STAGES = ['stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'stage6', 'stage7'];
const STAGE_META = {
  'stage1':   { name: '前置准备与环境检查' },
  'stage2':   { name: '仓库初始化', subs: ['stage2.0', 'stage2.1', 'stage2.2'] },
  'stage2.0': { name: '仓库克隆' },
  'stage2.1': { name: '创建/切换开发分支' },
  'stage2.2': { name: '创建标准目录结构' },
  'stage3':   { name: '需求分析与技术设计', subs: ['stage3.1', 'stage3.2', 'stage3.3'] },
  'stage3.1': { name: '需求分析' },
  'stage3.2': { name: '技术方案' },
  'stage3.3': { name: '任务拆解' },
  'stage4':   { name: '物料组件和页面协议开发', subs: ['stage4.1', 'stage4.2', 'stage4.3'] },
  'stage4.1': { name: '物料组件开发与发布' },
  'stage4.2': { name: '协议开发' },
  'stage4.3': { name: '业务逻辑实现' },
  'stage5':   { name: '验证测试' },
  'stage6':   { name: 'CI/CD 部署' },
  'stage7':   { name: '反馈总结' },
};
const PARENT = {};
for (const [k, v] of Object.entries(STAGE_META)) {
  (v.subs || []).forEach((s) => { PARENT[s] = k; });
}

// ─── 参数解析 ──────────────────────────────────────────────────────────────
function parseArgs(argv) {
  const p = { context: null, action: null, stage: null, reason: null, message: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--context' && argv[i + 1]) p.context = argv[++i];
    else if (a.startsWith('--context=')) p.context = a.slice(10);
    else if (a === '--reason' && argv[i + 1] != null) p.reason = argv[++i];
    else if (a.startsWith('--reason=')) p.reason = a.slice(9);
    else if (a === '--message' && argv[i + 1] != null) p.message = argv[++i];
    else if (a.startsWith('--message=')) p.message = a.slice(10);
    else if (['show', 'start', 'complete', 'skip', 'fail', 'next', 'gate', 'reset-from'].includes(a)) p.action = a;
    else if (!p.stage && /^stage[\d.]+$/.test(a)) p.stage = a;
    else err(`未知参数或非法阶段 key: ${a}（可用: ${STAGE_ORDER.join(', ')}）`);
  }
  if (!p.action) err('缺少操作命令，支持: show / next / start / complete / skip / fail / gate');
  return p;
}
const args = parseArgs(process.argv.slice(2));

// ─── 查找 workflow-context.json ─────────────────────────────────────────────
function findContext(explicit) {
  if (explicit) {
    for (const c of [explicit, path.resolve(process.cwd(), explicit)]) {
      if (fs.existsSync(c)) return path.resolve(c);
    }
    err(`未找到 workflow-context.json: ${explicit}`);
  }
  let dir = process.cwd();
  while (dir !== path.dirname(dir)) {
    const duo = path.join(dir, '.duo');
    if (fs.existsSync(duo)) {
      try {
        for (const e of fs.readdirSync(duo, { withFileTypes: true })) {
          if (e.isDirectory()) {
            const p = path.join(duo, e.name, 'workflow-context.json');
            if (fs.existsSync(p)) return p;
          }
        }
      } catch {}
    }
    dir = path.dirname(dir);
  }
  err('未找到 workflow-context.json（可使用 --context 显式指定路径）');
}
const ctxPath = findContext(args.context);

let ctx;
try { ctx = JSON.parse(fs.readFileSync(ctxPath, 'utf8')); }
catch (e) { err(`workflow-context.json 解析失败: ${e.message}`); }
if (!ctx.runtime || !ctx.runtime.stages) err('workflow-context.json 缺少 runtime.stages，非本 skill 管理的状态文件');

// ─── 基础工具 ───────────────────────────────────────────────────────────────
const now = () => new Date().toISOString();
const st = (k) => (ctx.runtime.stages[k] ? ctx.runtime.stages[k].status : 'missing');
const sg = (s) => ({
  pending: `${C.dim}⏳${C.nc}`, in_progress: `${C.cyan}▶️ ${C.nc}`,
  completed: `${C.green}✅${C.nc}`, skipped: `${C.dim}⏭️${C.nc}`,
  failed: `${C.red}❌${C.nc}`, missing: `${C.red}❓${C.nc}`,
}[s] || s);
function checkStageKey(k) {
  if (!STAGE_ORDER.includes(k)) err(`非法阶段 key: ${k}（可用: ${STAGE_ORDER.join(', ')}）`);
  if (st(k) === 'missing') err(`workflow-context.json 中缺少 ${k} 的状态定义`);
}
// 完成态门禁：completed 但 reported_at 为空
function gateViolations() {
  const v = [];
  for (const k of STAGE_ORDER) {
    const s = ctx.runtime.stages[k];
    if (s && s.status === 'completed' && !s.reported_at) v.push(k);
  }
  return v;
}
function assertPredecessorDone(k) {
  if (k === 'stage1') return; // 无前置
  if (PARENT[k]) {
    // 子阶段：父主阶段必须 in_progress（或 completed），前置兄弟阶段必须完成/跳过
    const p = PARENT[k];
    if (st(p) === 'in_progress') {
      const subs = STAGE_META[p].subs;
      const idx = subs.indexOf(k);
      if (idx > 0) {
        const prev = subs[idx - 1];
        if (st(prev) !== 'completed' && st(prev) !== 'skipped')
          err(`禁止跳步：${k} 前的兄弟阶段 ${prev} 当前为 ${st(prev)}，须先完成（complete ${prev}）`);
        if (st(prev) === 'completed' && !ctx.runtime.stages[prev].reported_at)
          err(`上报门禁未通过：${prev} 已完成但 reported_at 为空，须先执行 post_stage_hooks（report-stage.js）`);
      }
    } else if (st(p) !== 'completed') {
      err(`非法流转：进入子阶段 ${k} 前须先启动父阶段（start ${p}，当前为 ${st(p)}）`);
    }
  } else {
    // 主阶段：前一个主阶段必须 completed/skipped；completed 时须已上报
    const idx = MAIN_STAGES.indexOf(k);
    const prev = MAIN_STAGES[idx - 1];
    if (st(prev) !== 'completed' && st(prev) !== 'skipped')
      err(`禁止跳步：主阶段 ${k} 前的 ${prev} 当前为 ${st(prev)}，须先完成（complete ${prev}）`);
    if (st(prev) === 'completed' && !ctx.runtime.stages[prev].reported_at)
      err(`上报门禁未通过：${prev} 已完成但 reported_at 为空，须先执行 post_stage_hooks（report-stage.js / report-sdlc-mapping.js）`);
  }
}

// ─── 渲染流转链路 ────────────────────────────────────────────────────────────
function renderFlow(title) {
  console.log(`\n${C.cyan}━━━━ fe-rd-workflow 阶段流转${title ? ' · ' + title : ''} ━━━━${C.nc}`);
  const seg = STAGE_ORDER.map((k) => {
    const s = ctx.runtime.stages[k];
    let sym = st(k) === 'completed' && !s.reported_at ? `${C.yellow}⚠️${C.nc}` : sg(st(k));
    return `${k} ${sym}`;
  });
  // 主链路一行 + 子阶段缩进一行，避免过长
  const mainLine = [];
  for (const m of MAIN_STAGES) {
    let sym = st(m) === 'completed' && !ctx.runtime.stages[m].reported_at ? `${C.yellow}⚠️${C.nc}` : sg(st(m));
    mainLine.push(`${m} ${sym}`);
  }
  console.log(`主链: ${mainLine.join(' → ')}`);
  for (const m of ['stage2', 'stage3', 'stage4']) {
    const subs = (STAGE_META[m].subs || []).map((k) => `${k} ${sg(st(k))}`).join(' → ');
    console.log(`  ${m}子阶段: ${subs}`);
  }
  const cur = ctx.runtime.current_stage;
  console.log(`${C.bold}当前阶段:${C.nc} ${cur || '-'}${cur ? `（${st(cur)} · ${(STAGE_META[cur] || {}).name || ''}）` : ''}`);
  const gv = gateViolations();
  if (gv.length) warn(`门禁告警: ${gv.join(', ')} 已完成但 reported_at 为空，禁止进入下一阶段，须先执行 post_stage_hooks`);
}

function renderDetail() {
  console.log(`\n${C.bold}阶段明细${C.nc}（${ctxPath}）`);
  const pad = (s, n) => String(s == null ? '-' : s).padEnd(n);
  console.log(`${C.dim}${pad('key', 10)}${pad('状态', 12)}${pad('started_at', 27)}${pad('completed_at', 27)}${pad('reported_at', 27)}名称${C.nc}`);
  for (const k of STAGE_ORDER) {
    const s = ctx.runtime.stages[k];
    let status = s.status;
    if (s.status === 'completed' && !s.reported_at) status = 'completed⚠️';
    console.log(`${pad(k, 10)}${pad(status, 12)}${pad(s.started_at, 27)}${pad(s.completed_at, 27)}${pad(s.reported_at, 27)}${(STAGE_META[k] || {}).name || ''}`);
  }
}

// ─── 持久化 ──────────────────────────────────────────────────────────────────
function persist(logLine) {
  const tmp = ctxPath + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(ctx, null, 2) + '\n');
  fs.renameSync(tmp, ctxPath);
  if (logLine) {
    const logPath = path.join(path.dirname(ctxPath), 'stage-flow.log');
    fs.appendFileSync(logPath, logLine + '\n');
  }
}

// ─── 动作实现 ────────────────────────────────────────────────────────────────
function doStart(k) {
  checkStageKey(k);
  const from = st(k);
  if (from !== 'pending' && from !== 'failed')
    err(`非法流转: ${k} 当前为 ${from}，仅 pending/failed 可 start`);
  assertPredecessorDone(k);
  const s = ctx.runtime.stages[k];
  s.status = 'in_progress'; s.started_at = now();
  if (from === 'failed') s.completed_at = null; // 清除 fail 残留的 completed_at
  ctx.runtime.current_stage = k;
  persist(`${now()}\tstart\t${k}\t${from}→in_progress`);
  ok(`${k}（${STAGE_META[k].name}）: ${from} → in_progress，开始执行`);
}

function doComplete(k) {
  checkStageKey(k);
  const from = st(k);
  if (from !== 'in_progress') err(`非法流转: ${k} 当前为 ${from}，仅 in_progress 可 complete`);
  const subs = (STAGE_META[k] || {}).subs || [];
  if (subs.length) {
    const bad = subs.filter((x) => st(x) !== 'completed' && st(x) !== 'skipped');
    if (bad.length) err(`主阶段 ${k} 的子阶段未全部完成/跳过: ${bad.map((x) => `${x}=${st(x)}`).join(', ')}`);
  }
  const s = ctx.runtime.stages[k];
  s.status = 'completed'; s.completed_at = now();
  persist(`${now()}\tcomplete\t${k}\tin_progress→completed`);
  ok(`${k}（${STAGE_META[k].name}）: in_progress → completed`);
  const skillRoot = (ctx.runtime.post_stage_hooks || {}).skill_root || '<skill_root>';
  if (subs.length) {
    // 主阶段完成 → 触发 post_stage_hooks 提示
    console.log(`${C.yellow}🔔 必须立即执行 post_stage_hooks（直到 reported_at 被回写）:${C.nc}`);
    for (const a of ((ctx.runtime.post_stage_hooks || {}).actions || [])) {
      const cmd = a.command.replace('{completed_stage_key}', k).replace('{this_file_absolute_path}', ctxPath).replace('{skill_root}', skillRoot);
      console.log(`  ${C.bold}${cmd}${C.nc}`);
    }
  } else {
    console.log(`${C.yellow}🔔 请执行日志上报（自动补报子阶段）:${C.nc}\n  ${C.bold}node ${skillRoot}/scripts/report-stage.js --stage ${k} --context ${ctxPath}${C.nc}`);
  }
}

function doSkip(k, reason) {
  checkStageKey(k);
  if (!reason) err(`skip 必须提供 --reason "跳过原因"`);
  const from = st(k);
  if (from !== 'pending' && from !== 'in_progress')
    err(`非法流转: ${k} 当前为 ${from}，仅 pending/in_progress 可 skip`);
  const subs = (STAGE_META[k] || {}).subs || [];
  if (subs.length) {
    const busy = subs.filter((x) => st(x) === 'in_progress' || st(x) === 'failed');
    if (busy.length) err(`主阶段 ${k} 存在未了结的子阶段（in_progress/failed）: ${busy.join(', ')}，须先 complete/skip/fail`);
  }
  const s = ctx.runtime.stages[k];
  s.status = 'skipped'; s.completed_at = now();
  if (!ctx.skip_decisions) ctx.skip_decisions = {};
  ctx.skip_decisions[k] = reason;
  persist(`${now()}\tskip\t${k}\t${from}→skipped\t${reason}`);
  ok(`${k}（${STAGE_META[k].name}）: ${from} → skipped（原因: ${reason}）`);
}

function doFail(k, message) {
  checkStageKey(k);
  const from = st(k);
  const s = ctx.runtime.stages[k];
  s.status = 'failed'; s.completed_at = now();
  (ctx.errors = ctx.errors || []).push({ stage: k, timestamp: now(), message: message || '阶段执行失败', resolved: false });
  persist(`${now()}\tfail\t${k}\t${from}→failed\t${message || ''}`);
  ok(`${k}: ${from} → failed${message ? '（' + message + '）' : ''}，请处理后重试（start ${k}）或跳过（skip ${k} --reason ...）`);
}

function doNext() {
  const pendingStage = STAGE_ORDER.find((k) => st(k) === 'pending');
  if (!pendingStage) {
    const ip = STAGE_ORDER.filter((k) => st(k) === 'in_progress');
    renderFlow('next');
    if (ip.length) err(`无 pending 阶段可推进，当前 in_progress: ${ip.join(', ')}，请先 complete/skip/fail`);
    ok('全部阶段已了结（completed/skipped/failed），流程结束');
    return;
  }
  doStart(pendingStage);
}

// ─── 分发 ────────────────────────────────────────────────────────────────────────
function doResetFrom(k, reason) {
  if (!reason) err('reset-from 必须提供 --reason "重跑原因"');
  const idx = STAGE_ORDER.indexOf(k);
  if (idx < 0) err(`非法阶段 key: ${k}（可用: ${STAGE_ORDER.join(', ')}）`);
  const resetted = [];
  for (const key of STAGE_ORDER.slice(idx)) {
    const s = ctx.runtime.stages[key];
    if (!s) continue;
    const before = s.status;
    s.status = 'pending'; s.started_at = null; s.completed_at = null; s.reported_at = null;
    if (ctx.skip_decisions) delete ctx.skip_decisions[key];
    if (ctx.current_work_ask && ctx.current_work_ask[key]) ctx.current_work_ask[key] = 'pending';
    resetted.push(`${key}(${before}→pending)`);
  }
  ctx.runtime.current_stage = null;
  (ctx.errors = ctx.errors || []).push({ stage: k, timestamp: now(), message: `用户确认重跑：${reason}`, resolved: true });
  persist(`${now()}\treset-from\t${k}\t${resetted.join(',')}\t${reason}`);
  ok(`已按用户确认重置（原因: ${reason}）：${resetted.join(', ')}`);
  warn('⚠️ 重置后须按顺序重新执行：先重读对应 stageX 文档，再 start/complete 推进');
}
switch (args.action) {
  case 'show':
    renderFlow('show');
    renderDetail();
    break;
  case 'next':
    doNext();
    renderFlow('next');
    break;
  case 'start':
    if (!args.stage) err('start 需要阶段 key，如: start stage3.1');
    doStart(args.stage);
    renderFlow('start ' + args.stage);
    break;
  case 'complete':
    if (!args.stage) err('complete 需要阶段 key，如: complete stage3.1');
    doComplete(args.stage);
    renderFlow('complete ' + args.stage);
    break;
  case 'skip':
    if (!args.stage) err('skip 需要阶段 key，如: skip stage4.2 --reason "无协议改动"');
    doSkip(args.stage, args.reason);
    renderFlow('skip ' + args.stage);
    break;
  case 'fail':
    if (!args.stage) err('fail 需要阶段 key，如: fail stage5 --message "..."');
    doFail(args.stage, args.message);
    renderFlow('fail ' + args.stage);
    break;
  case 'gate': {
    const gv = gateViolations();
    renderFlow('gate');
    if (gv.length) err(`门禁未通过: ${gv.join(', ')} reported_at 为空，须先执行 post_stage_hooks`);
    ok('门禁校验通过：所有 completed 阶段均已完成上报');
    break;
  }
  case 'reset-from': {
    if (!args.stage) err('reset-from 需要阶段 key，如: reset-from stage2 --reason "用户确认重跑"');
    doResetFrom(args.stage, args.reason);
    renderFlow('reset-from ' + args.stage);
    break;
  }
}
NODE_EOF
