#!/usr/bin/env node
/**
 * mtunion-product-ai-guide 统一入口脚本
 * 
 * 跨平台（macOS / Windows）统一调度，AI 只需执行:
 *   node run.js <command> [options]
 * 
 * 子命令:
 *   init                          环境初始化（Python检查 + npm检查 + pt-passport安装）
 *   get-device-token              获取设备标识
 *   get-token                     获取缓存的用户Token
 *   auth-get-code                 获取授权链接
 *   auth-poll-token               轮询授权结果
 *   qrcode <url>                  获取二维码图片URL（服务端生成）
 *   hotword --city-id <id>        热搜词查询
 *   search --keyword <kw> --lat <lat> --lng <lng> --token <t> --city-id <id> [--page N] [--page-size N] [--query-id Q] [--request-id R] [--max-distance-km D]
 *   location --token <t>          获取用户近期位置
 *   location-by-address --address <addr>  根据地址获取经纬度
 *   order --product-id <pid> --poi-id <pid> --token <t> --city-id <id> --uuid <u> [--lat <lat>] [--lng <lng>] [--quantity N]
 *   logout                        退出登录
 *   clear-device-token            清除设备标识
 * 
 * 所有命令输出 JSON 到 stdout，错误信息输出到 stderr。
 */

const { execSync, execFileSync, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const https = require('https');

// ── 全局常量 ─────────────────────────────────────────────────
const SCRIPTS_DIR = __dirname;
const SKILL_DIR = path.dirname(SCRIPTS_DIR);
const CLIENT_ID = '578aafab312b44f1b76b0529b06bb0c6';
const PT_PASSPORT_BIN = path.join(SCRIPTS_DIR, 'node_modules', '.bin', 'pt-passport');
const PYTHON = findPython();

// ── Token 存储路径（统一使用 ~/.xiaomei-workspace/）───────────
const AUTH_DIR = path.join(require('os').homedir(), '.xiaomei-workspace');
if (!fs.existsSync(AUTH_DIR)) { fs.mkdirSync(AUTH_DIR, { recursive: true }); }
const CHILD_ENV = Object.assign({}, process.env, {
  PT_PASSPORT_AUTH_FILE: path.join(AUTH_DIR, 'mt_passport_auth.json'),
  XIAOMEI_AUTH_FILE: path.join(AUTH_DIR, 'auth_tokens.json')
});

// ── 工具函数 ─────────────────────────────────────────────────

function findPython() {
  // 优先 python3，fallback python
  for (const cmd of ['python3', 'python']) {
    try {
      const ver = execSync(`${cmd} --version`, { encoding: 'utf-8', timeout: 10000, stdio: 'pipe' }).trim();
      if (ver && !ver.startsWith('Python 2.')) return cmd;
    } catch (_) { /* ignore */ }
  }
  return 'python3'; // 兜底，让 init 命令去报具体错误
}

function out(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

function fail(error, extra) {
  out(Object.assign({ ok: false, error }, extra || {}));
  process.exit(1);
}

/** 执行 Python 脚本，返回解析后的 JSON */
function runPython(scriptName, args) {
  const scriptPath = path.join(SCRIPTS_DIR, scriptName);
  const cmdArgs = [scriptPath, ...args];
  try {
    const result = spawnSync(PYTHON, cmdArgs, {
      encoding: 'utf-8',
      timeout: 30000,
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: SCRIPTS_DIR,
      env: CHILD_ENV
    });
    const stdout = (result.stdout || '').trim();
    if (result.status !== 0) {
      // 尝试解析 stderr 或 stdout 中的 JSON 错误
      try { return JSON.parse(stdout); } catch (_) {}
      return { ok: false, error: 'SCRIPT_ERROR', message: (result.stderr || stdout || 'Unknown error').trim() };
    }
    try { return JSON.parse(stdout); } catch (_) {
      return { ok: false, error: 'PARSE_ERROR', message: 'Invalid JSON from script', raw: stdout };
    }
  } catch (e) {
    return { ok: false, error: 'EXEC_ERROR', message: e.message };
  }
}

/** 执行 pt-passport CLI 命令，返回原始 stdout */
function runPassport(args) {
  try {
    const result = spawnSync(PT_PASSPORT_BIN, args, {
      encoding: 'utf-8',
      timeout: 120000, // poll-token 可能需要较长时间
      stdio: ['pipe', 'pipe', 'pipe'],
      env: CHILD_ENV,
      shell: true
    });
    return {
      exitCode: result.status,
      stdout: (result.stdout || '').trim(),
      stderr: (result.stderr || '').trim()
    };
  } catch (e) {
    return { exitCode: 1, stdout: '', stderr: e.message };
  }
}

/** 解析 --key value 形式的命令行参数 */
function parseArgs(argv) {
  const args = {};
  const positional = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
      const key = argv[i].slice(2);
      // 如果下一个参数不是 --开头，则当作值
      if (i + 1 < argv.length && !argv[i + 1].startsWith('--')) {
        args[key] = argv[++i];
      } else {
        args[key] = 'true';
      }
    } else {
      positional.push(argv[i]);
    }
  }
  return { args, positional };
}

// ── CLIGuard 签名集成 ─────────────────────────────────────────

/**
 * 加载 cliguard.js 模块
 * 优先从 vendor/cliguard/js/ 加载，fallback 到 ~/.cliguard/cliguard-updates/
 */
function loadCliguard() {
  const vendorPath = path.join(SCRIPTS_DIR, 'vendor', 'cliguard', 'js', 'cliguard.js');
  const updatePath = path.join(
    require('os').homedir(), '.cliguard', 'cliguard-updates', 'core', 'cliguard.js'
  );

  if (fs.existsSync(vendorPath)) {
    return require(vendorPath);
  }
  if (fs.existsSync(updatePath)) {
    return require(updatePath);
  }
  return null;
}

/**
 * 对 URL 注入公共参数（csecplatform, csecversion 等）
 */
function addCommonParams(urlStr) {
  try {
    const cliguard = loadCliguard();
    if (!cliguard || typeof cliguard.addCommonParams !== 'function') {
      return urlStr;
    }
    const result = cliguard.addCommonParams(urlStr);
    return (result && result.url) ? result.url : urlStr;
  } catch (e) {
    process.stderr.write('[run.js:addCommonParams] warning: ' + e.message + '\n');
    return urlStr;
  }
}

/**
 * 生成 AIGuard 签名 headers
 */
function makeSignHeaders(method, urlStr, bodyHash) {
  try {
    const cliguard = loadCliguard();
    if (!cliguard || typeof cliguard.signRequest !== 'function') {
      return {};
    }
    return cliguard.signRequest(method.toUpperCase(), urlStr, bodyHash || '') || {};
  } catch (e) {
    process.stderr.write('[run.js:makeSignHeaders] warning: ' + e.message + '\n');
    return {};
  }
}

// ── HTTPS 请求工具 ────────────────────────────────────────────

/**
 * 发起 HTTPS POST 请求（Promise 版）
 */
function httpsPost(urlStr, bodyObj, extraHeaders) {
  return new Promise(function (resolve, reject) {
    const bodyStr = JSON.stringify(bodyObj);
    const bodyBuf = Buffer.from(bodyStr, 'utf-8');

    // 计算 body hash（取前 16200 字节，与 Python SDK 一致）
    const hashSlice = bodyBuf.slice(0, 16200);
    const bodyHash = crypto.createHash('md5').update(hashSlice).digest('hex');

    // 注入公参
    const signedUrl = addCommonParams(urlStr);

    // 生成签名 headers
    const sigHeaders = makeSignHeaders('POST', signedUrl, bodyHash);

    const parsed = new URL(signedUrl);
    const options = {
      hostname: parsed.hostname,
      port: parsed.port || 443,
      path: parsed.pathname + parsed.search,
      method: 'POST',
      headers: Object.assign({
        'Content-Type': 'application/json',
        'Content-Length': bodyBuf.length,
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'X-Requested-With': 'XMLHttpRequest'
      }, sigHeaders, extraHeaders || {})
    };

    const req = https.request(options, function (res) {
      const chunks = [];
      res.on('data', function (chunk) { chunks.push(chunk); });
      res.on('end', function () {
        const body = Buffer.concat(chunks).toString('utf-8');
        try {
          resolve({ status: res.statusCode, data: JSON.parse(body) });
        } catch (_) {
          resolve({ status: res.statusCode, data: null, raw: body });
        }
      });
    });

    req.on('error', function (e) { reject(e); });
    req.setTimeout(15000, function () {
      req.destroy();
      reject(new Error('TIMEOUT'));
    });

    req.write(bodyBuf);
    req.end();
  });
}

// ── 子命令实现 ───────────────────────────────────────────────

const commands = {};

// ── 状态文件路径 ──────────────────────────────────────────────
const STATE_FILE = path.join(AUTH_DIR, '.state.json');

/** 读取本地状态文件，返回对象（文件不存在时返回空对象） */
function readState() {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
  } catch (_) {
    return {};
  }
}

/** 写入本地状态文件（合并更新） */
function writeState(patch) {
  const current = readState();
  const updated = Object.assign({}, current, patch);
  fs.writeFileSync(STATE_FILE, JSON.stringify(updated, null, 2), 'utf-8');
}

/**
 * init — 环境初始化
 */
commands.init = function () {
  // 1. 路径验证
  if (!fs.existsSync(SCRIPTS_DIR) || !fs.statSync(SCRIPTS_DIR).isDirectory()) {
    fail('PATH_NOT_FOUND');
  }

  // 2. Python 检查
  let pyVer = '';
  try {
    pyVer = execSync(`${PYTHON} --version`, { encoding: 'utf-8', timeout: 10000, stdio: 'pipe' }).trim();
  } catch (_) { /* ignore */ }

  if (!pyVer) fail('PYTHON_NOT_FOUND');
  if (pyVer.startsWith('Python 2.')) fail('PYTHON_VERSION_2');

  // 3. Node.js 版本检查
  const nodeMajor = parseInt(process.versions.node.split('.')[0], 10);
  if (nodeMajor < 18) {
    fail('NODE_VERSION_LOW', { current: String(nodeMajor), required: '>=18' });
  }

  // 4. npm 检查
  try {
    execSync('npm --version', { encoding: 'utf-8', timeout: 10000, stdio: 'pipe' });
  } catch (_) {
    fail('NPM_NOT_FOUND');
  }

  // 5. pt-passport CLI 安装/更新（本地安装）
  const tgzFiles = fs.readdirSync(SCRIPTS_DIR)
    .filter(f => f.startsWith('mtuser-pt-passport-') && f.endsWith('.tgz'))
    .sort()
    .map(f => path.join(SCRIPTS_DIR, f));

  if (tgzFiles.length === 0) fail('TGZ_NOT_FOUND');

  const tgzFile = tgzFiles[tgzFiles.length - 1];
  const bundleVersion = path.basename(tgzFile).replace('mtuser-pt-passport-', '').replace('.tgz', '');

  let localVersion = '';
  try {
    const res = spawnSync(PT_PASSPORT_BIN, ['--version'], { encoding: 'utf-8', timeout: 10000, stdio: 'pipe', shell: true });
    localVersion = (res.stdout || '').trim().split('\n').pop();
  } catch (_) { /* not installed */ }

  if (localVersion !== bundleVersion) {
    try {
      execSync(`npm install "${tgzFile}" --prefix "${SCRIPTS_DIR}" --save-exact --force`, { encoding: 'utf-8', timeout: 60000, stdio: 'pipe' });
    } catch (_) {
      fail('INSTALL_FAILED');
    }
  }

  // 6. 读取本地状态，返回 tos_accepted
  const state = readState();
  out({ ok: true, scripts_dir: SCRIPTS_DIR, skill_dir: SKILL_DIR, tos_accepted: state.tos_accepted === true });
};

/**
 * get-device-token — 获取设备标识
 */
commands['get-device-token'] = function () {
  const result = runPython('auth.py', ['get-device-token']);
  if (result.success && result.device_token) {
    out({ ok: true, device_token: result.device_token });
  } else if (result.device_token) {
    out({ ok: true, device_token: result.device_token });
  } else {
    fail('DEVICE_TOKEN_FAILED', { detail: result });
  }
};

/**
 * get-token — 获取缓存的用户 Token
 */
commands['get-token'] = function () {
  const res = runPassport(['get-token', '--client_id', CLIENT_ID]);
  if (res.exitCode === 0 && res.stdout) {
    out({ ok: true, token: res.stdout });
  } else {
    out({ ok: false, error: 'NO_TOKEN', message: 'Token not found or expired' });
  }
};

/**
 * auth-get-code — 获取授权链接
 */
commands['auth-get-code'] = function () {
  const res = runPassport(['auth', 'get-code', '--client_id', CLIENT_ID]);
  const stdout = res.stdout;

  // Token: <token> — 缓存命中
  const tokenMatch = stdout.match(/Token:\s*(.+)/);
  if (tokenMatch) {
    out({ ok: true, type: 'token', token: tokenMatch[1].trim() });
    return;
  }

  // AUTH_LINK: <url>
  const linkMatch = stdout.match(/AUTH_LINK:\s*(.+)/);
  if (linkMatch) {
    out({ ok: true, type: 'auth_link', url: linkMatch[1].trim() });
    return;
  }

  // ❌ 错误
  const errorMatch = stdout.match(/❌\s*code=(\d+)\s*message=(.*)/);
  if (errorMatch) {
    out({ ok: false, error: 'AUTH_ERROR', code: errorMatch[1], message: errorMatch[2].trim() });
    return;
  }

  out({ ok: false, error: 'UNKNOWN', raw: stdout, stderr: res.stderr });
};

/**
 * auth-poll-token — 轮询授权结果
 */
commands['auth-poll-token'] = function () {
  const res = runPassport(['auth', 'poll-token', '--client_id', CLIENT_ID]);
  const stdout = res.stdout;

  const tokenMatch = stdout.match(/Token:\s*(.+)/);
  if (res.exitCode === 0 && tokenMatch) {
    out({ ok: true, token: tokenMatch[1].trim() });
    return;
  }

  const errorMatch = stdout.match(/❌\s*code=(\d+)\s*message=(.*)/);
  if (errorMatch) {
    out({ ok: false, error: 'POLL_ERROR', code: errorMatch[1], message: errorMatch[2].trim() });
    return;
  }

  out({ ok: false, error: 'POLL_FAILED', raw: stdout, stderr: res.stderr });
};

/**
 * qrcode — 通过服务端接口获取二维码图片 URL
 * 用法: node run.js qrcode <url>
 * 调用 https://click.meituan.com/cps/ai/product/getQrCodeImage
 * POST, body: { originalUrl: url }, 含 cliguard 签名
 */
commands.qrcode = function (argv) {
  const url = argv[0] || '';

  if (!url) {
    out({ ok: false, type: 'skip' });
    return;
  }

  if (url.indexOf('npay.meituan.com') !== -1) {
    out({ ok: false, type: 'skip', message: '支付二维码已由order命令返回payQrCodeImage字段，请直接展示该图片，禁止调用qrcode命令' });
    return;
  }

  const apiUrl = 'https://click.meituan.com/cps/ai/product/getQrCodeImage';
  const body = { originalUrl: url, clientSource: 'qclaw' };

  httpsPost(apiUrl, body)
    .then(function (resp) {
      const data = resp.data;
      if (data && data.data) {
        out({ ok: true, type: 'image', imageUrl: data.data });
      } else {
        out({ ok: false, type: 'skip', message: 'No image returned', raw: data });
      }
    })
    .catch(function (e) {
      out({ ok: false, type: 'skip', message: e.message });
    });
};

/**
 * hotword — 热搜词查询
 * 用法: node run.js hotword --city-id <id>
 */
commands.hotword = function (argv) {
  const { args } = parseArgs(argv);
  if (!args['city-id']) fail('MISSING_PARAM', { param: 'city-id' });
  const result = runPython('hotword.py', ['--city-id', args['city-id']]);
  out(Object.assign({ ok: !!result.success }, result));
};

/**
 * search — 商品搜索
 */
commands.search = function (argv) {
  const { args } = parseArgs(argv);
  const required = ['keyword', 'lat', 'lng', 'token', 'city-id'];
  for (const r of required) {
    if (!args[r]) fail('MISSING_PARAM', { param: r });
  }

  const pyArgs = [
    '--keyword', args['keyword'],
    '--lat', args['lat'],
    '--lng', args['lng'],
    '--token', args['token'],
    '--city-id', args['city-id']
  ];

  if (args['page']) { pyArgs.push('--page', args['page']); }
  if (args['page-size']) { pyArgs.push('--page-size', args['page-size']); }
  if (args['query-id']) { pyArgs.push('--query-id', args['query-id']); }
  if (args['request-id']) { pyArgs.push('--request-id', args['request-id']); }
  if (args['max-distance-km']) { pyArgs.push('--max-distance-km', args['max-distance-km']); }

  const result = runPython('product_search.py', pyArgs);
  out(Object.assign({ ok: !!result.success }, result));
};

/**
 * location — 获取用户近期位置
 */
commands.location = function (argv) {
  const { args } = parseArgs(argv);
  if (!args['token']) fail('MISSING_PARAM', { param: 'token' });
  const result = runPython('get_user_recent_location.py', ['--token', args['token']]);
  out(Object.assign({ ok: !!result.success }, result));
};

/**
 * location-by-address — 根据地址获取经纬度
 */
commands['location-by-address'] = function (argv) {
  const { args } = parseArgs(argv);
  if (!args['address']) fail('MISSING_PARAM', { param: 'address' });
  const result = runPython('get_location_by_address.py', ['--address', args['address']]);
  out(Object.assign({ ok: !!result.success }, result));
};

/**
 * order — 下单
 */
commands.order = function (argv) {
  const { args } = parseArgs(argv);
  const required = ['product-id', 'poi-id', 'token', 'city-id', 'uuid'];
  for (const r of required) {
    if (!args[r]) fail('MISSING_PARAM', { param: r });
  }

  const pyArgs = [
    '--product-id', args['product-id'],
    '--poi-id', args['poi-id'],
    '--token', args['token'],
    '--city-id', args['city-id'],
    '--uuid', args['uuid']
  ];

  if (args['lat']) { pyArgs.push('--lat', args['lat']); }
  if (args['lng']) { pyArgs.push('--lng', args['lng']); }
  if (args['quantity']) { pyArgs.push('--quantity', args['quantity']); }

  const result = runPython('order.py', pyArgs);
  out(Object.assign({ ok: !!result.success }, result));
};

/**
 * tos-accept — 记录用户已接受服务协议
 */
commands['tos-accept'] = function () {
  writeState({ tos_accepted: true });
  out({ ok: true });
};

/**
 * logout — 退出登录
 */
commands.logout = function () {
  const result = runPython('auth.py', ['logout']);
  out(Object.assign({ ok: !!result.success }, result));
};

/**
 * clear-device-token — 清除设备标识
 */
commands['clear-device-token'] = function () {
  const result = runPython('auth.py', ['clear-device-token']);
  out(Object.assign({ ok: !!result.success }, result));
};

// ── 入口 ─────────────────────────────────────────────────────

const allArgs = process.argv.slice(2);
const command = allArgs[0];
const commandArgs = allArgs.slice(1);

if (!command || command === '--help' || command === '-h') {
  console.log(`Usage: node run.js <command> [options]

Commands:
  init                     Environment setup (returns tos_accepted field)
  tos-accept               Mark TOS as accepted (writes to local .state.json)
  get-device-token         Get device token
  get-token                Get cached user token
  auth-get-code            Get auth link
  auth-poll-token          Poll auth result
  qrcode <url>             Get QR code image URL (server-side)
  hotword --city-id <id>   Hot search words
  search --keyword <kw> --lat <lat> --lng <lng> --token <t> --city-id <id>
  location --token <t>     Get recent location
  location-by-address --address <addr>
  order --product-id <pid> --poi-id <pid> --token <t> --city-id <id> --uuid <u>
  logout                   Logout
  clear-device-token       Clear device token`);
  process.exit(0);
}

if (!commands[command]) {
  fail('UNKNOWN_COMMAND', { command, available: Object.keys(commands) });
}

commands[command](commandArgs);
