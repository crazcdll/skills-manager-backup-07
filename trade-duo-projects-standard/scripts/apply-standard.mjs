#!/usr/bin/env node
/**
 * 可选自动化：在「无法完整走 k-hub + 学城人工步骤」时，按 k-hub《整合版》表格对 DUO 仓库清单做三端一致性改写。
 * 权威版本仍以学城 https://km.sankuai.com/collabpage/2747476284 为准；表格更新时请同步修改 ../data/km-5241-raw.md。
 *
 * 用法（在 trade-skills 仓库根目录执行）：
 *   cd trade-duo-projects-standard/scripts && npm install
 *   node apply-standard.mjs --repo ../../.temp/trade-duo-projects-standard/work/<repo-name>
 *
 *   --repo <path>        必填，DUO 仓库根目录（含 dependencies.json）
 *   --km <path>          可选，标准表 Markdown，默认 ../data/km-5241-raw.md
 *   --result-dir <path>  可选，报告输出目录，默认 <cwd>/.temp/trade-duo-projects-standard/result
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import semver from 'semver';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function parseArgs() {
  const argv = process.argv.slice(2);
  const out = { repo: null, km: null, resultDir: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--repo') out.repo = path.resolve(argv[++i] || '');
    else if (a === '--km') out.km = path.resolve(argv[++i] || '');
    else if (a === '--result-dir') out.resultDir = path.resolve(argv[++i] || '');
    else if (a === '--help' || a === '-h') out.help = true;
  }
  return out;
}

const args = parseArgs();
if (args.help || !args.repo) {
  console.error(`Usage: node apply-standard.mjs --repo <duo-repo-root> [--km <km.md>] [--result-dir <dir>]`);
  process.exit(args.help ? 0 : 1);
}

const REPO = args.repo;
const KM = args.km || path.join(__dirname, '../data/km-5241-raw.md');
const resultDir =
  args.resultDir || path.resolve(process.cwd(), '.temp/trade-duo-projects-standard/result');

function stripStd(v) {
  return String(v ?? '').trim().replace(/\*\*/g, '');
}

function normalizeForCompare(v) {
  const s = stripStd(v);
  if (!s || s === '全部版本' || s === '-') return null;
  const c = semver.coerce(s);
  if (c) return c.version;
  const c2 = semver.coerce(s.replace(/^\^/, ''));
  return c2 ? c2.version : null;
}

function cmpGt(stdRaw, curRaw) {
  const vs = normalizeForCompare(stdRaw);
  const vc = normalizeForCompare(curRaw);
  if (!vs || !vc) return false;
  return semver.gt(vs, vc);
}

function pickStdOrCur(stdRaw, curRaw) {
  const s = stripStd(stdRaw);
  if (!s || s === '全部版本') return curRaw;
  return cmpGt(s, curRaw) ? s : curRaw;
}

function replaceVerInUrl(url, oldVer, newVer) {
  if (!url || !oldVer || !newVer || oldVer === newVer) return url;
  const o = String(oldVer).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return url.replace(new RegExp(`/${o}/`, 'g'), `/${newVer}/`);
}

function parseKmTable(md) {
  const map = new Map();
  for (const line of md.split('\n')) {
    if (!line.trim().startsWith('|')) continue;
    const parts = line.split('|').map((p) => p.trim());
    if (parts.length < 4) continue;
    const name = parts[1];
    const ver = parts[2];
    const tri = parts[3] || '';
    if (name === '依赖名称' || !name || name.includes('---')) continue;
    map.set(name, { stdVersion: ver, threeOk: tri.includes('✅') });
  }
  return map;
}

function resolveStdForPackage(name, table) {
  if (table.has(name)) return table.get(name);
  if (/^@max\/leez-/.test(name)) {
    return table.get('@max/leez-dependencies 等leez相关依赖') || null;
  }
  if (/^@hfe\/max-/.test(name)) {
    return table.get('@hfe/max-* 系列组件（button、image、text、view 等）') || null;
  }
  return null;
}

function maxVer(verA, verB) {
  const ca = normalizeForCompare(verA);
  const cb = normalizeForCompare(verB);
  if (!ca) return stripStd(verB);
  if (!cb) return stripStd(verA);
  return semver.gt(ca, cb) ? stripStd(verA) : stripStd(verB);
}

if (!fs.existsSync(KM)) {
  console.error(`KM file not found: ${KM}`);
  process.exit(1);
}
const table = parseKmTable(fs.readFileSync(KM, 'utf8'));

const depPath = path.join(REPO, 'dependencies.json');
const ohPath = path.join(REPO, 'ohDependencies.json');
const cmPath = path.join(REPO, 'componentsMap.json');

for (const p of [depPath, ohPath, cmPath]) {
  if (!fs.existsSync(p)) {
    console.error(`Missing required file: ${p}`);
    process.exit(1);
  }
}

let deps = JSON.parse(fs.readFileSync(depPath, 'utf8'));
const ohOrig = JSON.parse(fs.readFileSync(ohPath, 'utf8'));
let cm = JSON.parse(fs.readFileSync(cmPath, 'utf8'));

const changelist = [];

const ohNext = [];
for (const item of ohOrig) {
  const meta = resolveStdForPackage(item.name, table);
  if (!meta) {
    ohNext.push(item);
    changelist.push(`[oh 表未收录] ${item.name}@${item.version} — 保持`);
    continue;
  }
  const { stdVersion, threeOk } = meta;

  if (threeOk) {
    const migrated = pickStdOrCur(stdVersion, item.version);
    const idx = deps.findIndex((d) => d.name === item.name);
    if (idx >= 0) {
      const cur = deps[idx];
      const nextV = maxVer(migrated, cur.version);
      if (nextV !== cur.version) {
        const oldV = cur.version;
        cur.version = nextV;
        cur.url = replaceVerInUrl(cur.url, oldV, nextV);
        changelist.push(`[deps 升级/合并] ${item.name}: ${oldV} -> ${nextV}（oh 迁出）`);
      }
    } else {
      const nu = {
        name: item.name,
        version: migrated,
        type: item.type,
        url: replaceVerInUrl(item.url, item.version, migrated),
      };
      deps.push(nu);
      changelist.push(`[deps 新增] ${item.name}@${migrated}（oh 迁出）`);
    }
    changelist.push(`[oh 迁出] ${item.name}（三端兼容 ✅）`);
    continue;
  }

  const stay = pickStdOrCur(stdVersion, item.version);
  if (stay !== item.version) {
    const oldV = item.version;
    ohNext.push({ ...item, version: stay, url: replaceVerInUrl(item.url, oldV, stay) });
    changelist.push(`[oh 升级] ${item.name}: ${oldV} -> ${stay}`);
  } else {
    ohNext.push(item);
    if (stripStd(stdVersion) && !cmpGt(stdVersion, item.version)) {
      changelist.push(`[oh 跳过版本] ${item.name} 标准不高于当前`);
    }
  }
}

fs.writeFileSync(ohPath, JSON.stringify(ohNext, null, 2) + '\n');

for (const item of deps) {
  const meta = resolveStdForPackage(item.name, table);
  if (!meta) continue;
  const { stdVersion } = meta;
  const s = stripStd(stdVersion);
  if (!s || s === '全部版本') continue;
  if (!cmpGt(s, item.version)) continue;
  const oldV = item.version;
  item.version = s;
  item.url = replaceVerInUrl(item.url, oldV, s);
  changelist.push(`[deps 升级] ${item.name}: ${oldV} -> ${s}`);
}

fs.writeFileSync(depPath, JSON.stringify(deps, null, 2) + '\n');
deps = JSON.parse(fs.readFileSync(depPath, 'utf8'));
const ohFinal = JSON.parse(fs.readFileSync(ohPath, 'utf8'));

function listVersion(name) {
  const d = deps.find((x) => x.name === name);
  if (d) return d.version;
  const o = ohFinal.find((x) => x.name === name);
  return o ? o.version : null;
}

let blockCommit = false;
const cmNotes = [];

for (const [, entry] of Object.entries(cm)) {
  const npm = entry.npm;
  if (!npm) continue;
  const Vlist = listVersion(npm);
  if (!Vlist) continue;
  const Vcm = entry.npmVersion;
  const vc = normalizeForCompare(Vcm);
  const vl = normalizeForCompare(Vlist);
  if (!vc || !vl) {
    cmNotes.push(`[componentsMap 跳过] ${npm}: 不可解析 Vcm=${Vcm} Vlist=${Vlist}`);
    continue;
  }
  if (semver.lt(vl, vc)) {
    blockCommit = true;
    cmNotes.push(`【降级风险】${npm}: 清单=${Vlist} < 物料 npmVersion=${Vcm}`);
    continue;
  }
  if (semver.gt(vl, vc)) {
    const oldNv = entry.npmVersion;
    entry.npmVersion = Vlist;
    if (Array.isArray(entry.web)) {
      entry.web = entry.web.map((u) => replaceVerInUrl(u, oldNv, Vlist));
    }
    cmNotes.push(`[componentsMap] ${npm}: ${oldNv} -> ${Vlist}`);
  }
}

fs.mkdirSync(resultDir, { recursive: true });
if (blockCommit) {
  fs.writeFileSync(path.join(resultDir, 'block-commit.flag'), 'downgrade-risk-in-step04\n');
}

const reportBody = `# trade-duo-standard-same-npm-dependencies（脚本自动化）执行记录

来源：\`${path.relative(process.cwd(), KM)}\`（k-hub 整合版快照；学城以 2747476284 为准请人工复核）。

## 变更

${changelist.map((l) => `- ${l}`).join('\n')}

## componentsMap

${cmNotes.map((l) => `- ${l}`).join('\n')}
`;

fs.writeFileSync(path.join(resultDir, 'trade-packages-changelist.md'), reportBody);
fs.writeFileSync(path.join(resultDir, 'changelist.md'), reportBody);

if (blockCommit) {
  console.error('BLOCK_COMMIT: downgrade risk in componentsMap');
  process.exit(2);
}

fs.writeFileSync(cmPath, JSON.stringify(cm, null, 2) + '\n');
console.log('done', { repo: REPO, resultDir });
