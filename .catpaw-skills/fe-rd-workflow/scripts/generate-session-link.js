#!/usr/bin/env node

/**
 * 生成 CatPaw 会话分享链接并写入 workflow-context.json
 *
 * 用法：
 *   node scripts/generate-session-link.js --context <workflow-context.json路径>
 *
 * 设计原则：
 *   - 全程不阻塞：任何环节失败都静默退出（exit 0），不影响调用方
 *   - 去重：按 conversation_id 判断，已存在则跳过
 *   - 自动判断执行环境（CatPaw Desk / CatPaw IDE），使用对应方式获取 conversationId
 *   - 由 report-stage.js 内部触发，不作为独立 hook
 *   - CatPaw Desk：conversationId 直接拼接 /conversation/share/ 前缀，无需网络请求
 *   - CatPaw IDE：调用 POST /api/conversation/share 接口获取分享链接，失败则跳过
 *   - 未匹配到环境、或获取链接失败，则跳过不写入
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const https = require('https');

// ─── 常量 ────────────────────────────────────────────────────────────────────

const SHARE_URL_PREFIX = 'https://catpaw.sankuai.com/conversation/share/';
const SHARE_API_URL = 'https://catpaw.sankuai.com/api/conversation/share';

// ─── 参数解析 ─────────────────────────────────────────────────────────────────

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = { context: null };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--context' && args[i + 1]) parsed.context = args[++i];
  }
  return parsed;
}

// ─── 环境检测 ─────────────────────────────────────────────────────────────────

/**
 * 判断当前执行环境是 CatPaw Desk 还是 CatPaw IDE
 *
 * 判断依据（按优先级）：
 *   1. 环境变量 CATPAW_CONFIG_CONTENT 中 source 字段为 "CatPawDesk" / "CatPawIDE"
 *   2. 环境变量 __CFBundleIdentifier 为 "com.catpaw.cowork"（Desk）
 *   3. catdesk 命令可用（which catdesk 成功）→ Desk
 *   4. 以上均不满足 → 返回 null，跳过会话链接生成
 *
 * @returns {'catpaw_desk' | 'catpaw_ide' | null}
 */
function detectEnvironment() {
  // 方式 1：从 CATPAW_CONFIG_CONTENT 解析 source
  const configContent = process.env.CATPAW_CONFIG_CONTENT;
  if (configContent) {
    try {
      const config = JSON.parse(configContent);
      if (config.source === 'CatPawDesk') return 'catpaw_desk';
      if (config.source === 'CatPawIDE' || config.source === 'CatPawCLI_IDE') return 'catpaw_ide';
    } catch {}
  }

  // 方式 2：macOS Bundle 标识
  if (process.env.__CFBundleIdentifier === 'com.catpaw.cowork') {
    return 'catpaw_desk';
  }

  // 方式 3：尝试 IDE 目录结构（~/.catpaw/projects/ide-xxx/），能匹配到则认为是 IDE
  // 注意：不能用 `which catdesk` 判断，因为用户可能同时安装了 catdesk 和 IDE
  try {
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    const projectsDir = path.join(homeDir, '.catpaw', 'projects');
    if (fs.existsSync(projectsDir)) {
      const cwd = process.cwd();
      const pathHash = cwd.replace(/\//g, '-').replace(/^-/, '');
      const ideProjectDir = path.join(projectsDir, `ide-${pathHash}`);
      if (fs.existsSync(ideProjectDir)) return 'catpaw_ide';
    }
  } catch {}

  // 无法识别环境，返回 null
  return null;
}

// ─── 获取 conversationId ──────────────────────────────────────────────────────

/**
 * CatPaw Desk：通过 catdesk session current 获取当前会话 ID
 */
function getConversationFromDesk() {
  try {
    const output = execSync('catdesk session current', {
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
 * CatPaw IDE：从 ~/.catpaw/projects/ide-{path_hash}/{conversationId}/ 目录结构中提取
 *
 * 优先级：
 *   1. workflow-context.json 的 session_links[0].conversation_id（已写入则直接用，不再扫描）
 *   2. 首次兜底：扫描 ide- 目录，取最近修改的会话（写入后下次不再走此逻辑）
 */
function getConversationFromIDE() {
  try {
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    const projectsDir = path.join(homeDir, '.catpaw', 'projects');

    // 优先：session_links[0] 已有锚定值，直接返回，跳过扫描
    const _cp = parseArgs().context;
    if (_cp) {
      try {
        const ctx = JSON.parse(fs.readFileSync(path.resolve(_cp), 'utf8'));
        const firstId = ctx.runtime && ctx.runtime.session_links && ctx.runtime.session_links[0] && ctx.runtime.session_links[0].conversation_id;
        if (firstId) return firstId;
      } catch {}
    }

    // 首次兜底：扫描 ide- 目录，从 project_root 逐级向上匹配，取最短（最顶层）存在的目录
    if (!fs.existsSync(projectsDir)) return null;

    function findIdeDir(absPath) {
      const candidates = [];
      let p = absPath;
      const root = path.parse(p).root;
      while (p && p !== root) {
        candidates.push(p);
        const parent = path.dirname(p);
        if (parent === p) break;
        p = parent;
      }
      for (let i = candidates.length - 1; i >= 0; i--) {
        const hash = candidates[i].replace(/\//g, '-').replace(/^-/, '');
        const candidate = path.join(projectsDir, `ide-${hash}`);
        if (fs.existsSync(candidate)) return candidate;
      }
      return null;
    }

    let targetDir = null;
    if (_cp) {
      try {
        const ctx = JSON.parse(fs.readFileSync(path.resolve(_cp), 'utf8'));
        const projectRoot = ctx.meta && ctx.meta.project_root;
        if (projectRoot) targetDir = findIdeDir(projectRoot);
      } catch {}
    }
    if (!targetDir) targetDir = findIdeDir(process.cwd());
    if (!targetDir) return null;

    const convDirs = fs.readdirSync(targetDir, { withFileTypes: true })
      .filter(d => d.isDirectory() && !d.name.startsWith('.'));
    let latestId = null, latestTime = 0;
    for (const conv of convDirs) {
      try {
        const stat = fs.statSync(path.join(targetDir, conv.name));
        if (stat.mtimeMs > latestTime) { latestTime = stat.mtimeMs; latestId = conv.name; }
      } catch {}
    }
    return latestId || null;
  } catch {}
  return null;
}


/**
 * 根据检测到的环境获取 conversationId
 */
function getConversationInfo(env) {
  if (env === 'catpaw_desk') {
    const id = getConversationFromDesk();
    if (id) return { conversationId: id, source: 'catpaw_desk' };
    // Desk 环境但 catdesk 命令失败，尝试 IDE 方式兜底
    const ideId = getConversationFromIDE();
    if (ideId) return { conversationId: ideId, source: 'catpaw_desk' };
  } else {
    const id = getConversationFromIDE();
    if (id) return { conversationId: id, source: 'catpaw_ide' };
  }
  return null;
}

// ─── 写入 workflow-context.json ───────────────────────────────────────────────

function writeSessionLink(contextPath, entry) {
  try {
    const raw = fs.readFileSync(contextPath, 'utf8');
    const ctx = JSON.parse(raw);

    if (!ctx.runtime) ctx.runtime = {};
    if (!Array.isArray(ctx.runtime.session_links)) ctx.runtime.session_links = [];

    // 去重：已有相同 conversation_id 则跳过
    const exists = ctx.runtime.session_links.some(
      item => item.conversation_id === entry.conversation_id
    );
    if (exists) {
      console.log(`⏭️ [session-link] 会话 ${entry.conversation_id} 已存在，跳过`);
      return;
    }

    ctx.runtime.session_links.push(entry);
    fs.writeFileSync(contextPath, JSON.stringify(ctx, null, 2), 'utf8');
    console.log(`✅ [session-link] 已写入会话链接: ${entry.share_url}`);
  } catch (err) {
    console.log(`⚠️ [session-link] 写入失败: ${err.message}`);
  }
}

// ─── 调用接口生成分享链接 ──────────────────────────────────────────────────────

/**
 * 通过 catdesk auth token 获取 accessToken
 */
function getAccessToken() {
  try {
    const output = execSync('catdesk auth token', {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 5000,
    }).trim();
    const data = JSON.parse(output);
    return data.accessToken || data.access_token || null;
  } catch {}
  return null;
}

/**
 * 调用 POST /api/conversation/share 接口获取真实分享链接
 * 失败时返回 null，由调用方降级处理
 *
 * @param {string} conversationId
 * @param {string} accessToken
 * @returns {Promise<string|null>}
 */
function callShareApi(conversationId, accessToken) {
  return new Promise((resolve) => {
    const body = JSON.stringify({ conversationId });
    const url = new URL(SHARE_API_URL);
    const options = {
      hostname: url.hostname,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
        'Authorization': `Bearer ${accessToken}`,
      },
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          const shareUrl = json.data && json.data.conversationShareUrl;
          resolve(shareUrl || null);
        } catch {
          resolve(null);
        }
      });
    });

    req.on('error', () => resolve(null));
    req.setTimeout(8000, () => { req.destroy(); resolve(null); });
    req.write(body);
    req.end();
  });
}

/**
 * 获取分享链接
 *
 * - Desk：直接拼接，无需网络请求
 * - IDE：调用接口获取，失败返回 null
 *
 * @param {string} conversationId
 * @param {'catpaw_desk' | 'catpaw_ide'} env
 * @returns {Promise<string|null>}
 */
async function fetchShareUrl(conversationId, env) {
  if (env === 'catpaw_desk') {
    return `${SHARE_URL_PREFIX}${conversationId}`;
  }

  // IDE 环境：调用接口获取有效分享链接
  const token = getAccessToken();
  if (!token) {
    console.log('⚠️ [session-link] 无法获取 accessToken，跳过');
    return null;
  }
  const apiUrl = await callShareApi(conversationId, token);
  if (!apiUrl) {
    console.log('⚠️ [session-link] 接口调用失败，跳过');
    return null;
  }
  console.log('🔗 [session-link] 已通过接口生成分享链接');
  return apiUrl;
}

// ─── 主流程 ───────────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs();

  if (!args.context) {
    console.log('⚠️ [session-link] 缺少 --context 参数，跳过');
    process.exit(0);
  }

  const contextPath = path.resolve(args.context);
  if (!fs.existsSync(contextPath)) {
    console.log('⚠️ [session-link] workflow-context.json 不存在，跳过');
    process.exit(0);
  }

  // 1. 检测执行环境
  const env = detectEnvironment();
  if (!env) {
    console.log('⚠️ [session-link] 无法识别 CatPaw 执行环境（非 Desk 也非 IDE），跳过');
    process.exit(0);
  }
  console.log(`🔍 [session-link] 检测到环境: ${env}`);

  // 2. 获取 conversationId
  const convInfo = getConversationInfo(env);
  if (!convInfo) {
    console.log('⚠️ [session-link] 无法获取 conversationId，跳过');
    process.exit(0);
  }

  // 3. 检查是否已存在（提前短路）
  try {
    const ctx = JSON.parse(fs.readFileSync(contextPath, 'utf8'));
    const links = (ctx.runtime && ctx.runtime.session_links) || [];
    if (links.some(item => item.conversation_id === convInfo.conversationId)) {
      console.log(`⏭️ [session-link] 会话 ${convInfo.conversationId} 已存在，跳过`);
      process.exit(0);
    }
  } catch {}

  // 4. 生成分享链接
  //    Desk：直接拼接；IDE：调用接口，失败则跳过
  const shareUrl = await fetchShareUrl(convInfo.conversationId, env);
  if (!shareUrl) {
    process.exit(0);
  }

  // 5. 写入 workflow-context.json
  writeSessionLink(contextPath, {
    conversation_id: convInfo.conversationId,
    share_url: shareUrl,
    created_at: new Date().toISOString(),
    source: convInfo.source,
  });

  process.exit(0);
}

main().catch(() => process.exit(0));

