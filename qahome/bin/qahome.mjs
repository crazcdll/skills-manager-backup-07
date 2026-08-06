#!/usr/bin/env node
/**
 * qahome CLI — QAHome 质量保障平台命令行工具
 *
 * 用法:
 *   qahome sms <手机号>          查询最新登录验证码
 *   qahome sms <手机号> --raw    返回原始 JSON
 *   qahome config set-mis <mis>  配置 MIS 号
 *   qahome config show           查看当前配置
 *   qahome --help                显示帮助
 */

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

import { execSync } from "child_process";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { homedir } from "os";

// Node 版本检查
if (parseInt(process.versions.node) < 18) {
  console.error(`❌ 需要 Node.js 18+，当前版本: ${process.versions.node}`);
  process.exit(1);
}

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── 配置文件（存于用户家目录，各用户独立）────────────────────────────────────
const CONFIG_PATH = resolve(homedir(), ".catpaw", "skills", "qahome-config.json");

function readConfig() {
  try {
    return JSON.parse(readFileSync(CONFIG_PATH, "utf8"));
  } catch {
    return {};
  }
}

function writeConfig(data) {
  const dir = dirname(CONFIG_PATH);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(CONFIG_PATH, JSON.stringify(data, null, 2), "utf8");
}

// ── SSO 鉴权 + HTTP 请求（复用 ciba-request.mjs 的核心逻辑）──────────────────
const QAHOME_CLIENT_ID = "b399154e46";
const SMS_QUERY_URL    = "https://qahome.sankuai.com/smsqueue/query";

function getSsoToken(mis) {
  const NPX = process.platform === "win32" ? "npx.cmd" : "npx";
  const cmd = `${NPX} --yes --registry=http://r.npm.sankuai.com @dp/sso-auth-cli@latest --cookie "${QAHOME_CLIENT_ID}" --mis ${mis}`;
  let output;
  try {
    output = execSync(cmd, { encoding: "utf8", shell: true });
  } catch (err) {
    throw new Error(`SSO 认证失败: ${err.message}\n${err.stdout ?? ""}`);
  }
  const match = output.trim().match(/=\s*(AT_\S+)/);
  if (!match) throw new Error(`sso-auth-cli 未返回有效 token，原始输出：\n${output}`);
  return match[1];
}

async function querySms(mobileNo, mis, smsType = null) {
  const token = getSsoToken(mis);
  const resp = await fetch(SMS_QUERY_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "access-token": token,
    },
    body: JSON.stringify(smsType ? { mobileNo, id: "", smsType } : { mobileNo, id: "" }),
  });
  const text = await resp.text();
  try { return JSON.parse(text); }
  catch { throw new Error(`接口返回非 JSON：${text}`); }
}

// ── 手机号脱敏（仅用于展示）─────────────────────────────────────────────────
function maskMobile(mobile) {
  // 接口返回的 mobileNo 已脱敏；若用户输入的原始号码需脱敏展示
  const s = String(mobile).replace(/^\+86/, "");
  if (s.length === 11) return `${s.slice(0, 3)}****${s.slice(7)}`;
  return s.replace(/\d{4}(\d{4})$/, "****$1"); // 降级处理
}

// ── 子命令：sms ───────────────────────────────────────────────────────────────
async function cmdSms(argv) {
  const rawFlag = argv.includes("--raw");
  const typeIdx = argv.indexOf("--type");
  const smsType = typeIdx !== -1 && argv[typeIdx + 1] ? argv[typeIdx + 1] : null;
  const mobile  = argv.find(a => /^\+?[\d]{11,13}$/.test(a));

  if (!mobile) {
    console.error("❌ 请提供手机号，如：qahome sms 13800138000");
    process.exit(1);
  }

  // 规范化：去掉 +86 前缀，只传 11 位
  const mobileNo = mobile.replace(/^\+86/, "");
  if (!/^\d{11}$/.test(mobileNo)) {
    console.error("❌ 手机号格式不正确，请传入 11 位纯数字（或带 +86 前缀）");
    process.exit(1);
  }

  // 读取 MIS
  const config = readConfig();
  if (!config.mis) {
    console.error("❌ 未配置 MIS 号，请先运行：qahome config set-mis <你的MIS>");
    process.exit(1);
  }

  console.error(`🔐 正在获取 SSO token（MIS: ${config.mis}）...`);

  let data;
  try {
    data = await querySms(mobileNo, config.mis, smsType);
  } catch (err) {
    // 网络超时或服务异常提示
    const msg = err.message ?? "";
    if (msg.includes("fetch") || msg.includes("ECONNREFUSED") || msg.includes("timeout")) {
      console.error("❌ 网络不通或 qahome 服务异常，请检查网络，30s 后可重试");
    } else {
      console.error(`❌ ${msg}`);
    }
    process.exit(1);
  }

  if (rawFlag) {
    console.log(JSON.stringify(data, null, 2));
    return;
  }

  // 错误处理
  if (data.resultCode !== 0) {
    console.error(`❌ 接口返回错误（resultCode: ${data.resultCode}）：${data.message ?? ""}`);
    console.error("   请确认手机号是否为 11 位纯数字，或该号码是否有短信记录");
    process.exit(1);
  }

  if (!data.result || data.result.length === 0) {
    console.log(`📭 未查询到该手机号的短信，请确认号码是否正确，或该号码暂无短信记录。`);
    return;
  }

  // 取最新一条（接口已按 addTime 倒序）
  const latest = data.result[0];
  // 优先匹配「数字+（」格式（如「2576（登录验证码...）」），兼容4~6位；fallback 到纯6位
  const match  = latest.message?.match(/(\d{4,6})(?=（)/) ?? latest.message?.match(/\d{6}/);

  // 脱敏：使用接口返回的已脱敏 mobileNo，fallback 到手动脱敏
  const displayMobile = latest.mobileNo || maskMobile(mobileNo);

  console.log("");
  if (match) {
    console.log(`📱 手机号 ${displayMobile} 最新验证码：${match[1] ?? match[0]}`);
  } else {
    console.log(`📱 手机号 ${displayMobile} 短信（未找到验证码）`);
  }
  console.log(`⏰ 短信时间：${latest.addTimeFormat ?? "-"}`);
  console.log(`📄 短信内容：${latest.message ?? "-"}`);
  console.log("");
}

// ── 子命令：config ────────────────────────────────────────────────────────────
function cmdConfig(argv) {
  const sub = argv[0];

  if (sub === "set-mis") {
    const mis = argv[1];
    if (!mis) {
      console.error("❌ 请提供 MIS 号，如：qahome config set-mis zhangsan");
      process.exit(1);
    }
    const config = readConfig();
    config.mis = mis;
    writeConfig(config);
    console.log(`✅ MIS 已保存：${mis}  →  ${CONFIG_PATH}`);
    return;
  }

  if (sub === "show") {
    const config = readConfig();
    if (Object.keys(config).length === 0) {
      console.log(`⚙️  暂无配置（${CONFIG_PATH}）`);
      console.log("   运行 qahome config set-mis <你的MIS> 完成初始化");
    } else {
      console.log(`⚙️  当前配置（${CONFIG_PATH}）：`);
      console.log(`   mis: ${config.mis ?? "(未设置)"}`);
    }
    return;
  }

  console.error("❌ 未知子命令，可用：set-mis <mis> | show");
  process.exit(1);
}

// ── 帮助 ──────────────────────────────────────────────────────────────────────
function printHelp() {
  console.log(`
QAHome CLI — 质量保障平台命令行工具

用法:
  qahome <命令> [参数]

命令:
  sms <手机号>                      查询该手机号所有类型的最新短信（不限类型）
  sms <手机号> --type <smsType>     指定短信类型查询
  sms <手机号> --raw      返回接口原始 JSON（调试用）
  config set-mis <mis>    配置 MIS 号（首次使用必须先配置）
  config show             查看当前配置
  --help, -h              显示此帮助

示例:
  qahome config set-mis zhangsan
  qahome sms 13800138000
  qahome sms 13800138000 --type 19862
  qahome sms +8613800138000
  qahome sms 13800138000 --raw

⚠️  仅限美团内网使用，查询对象为测试专用手机号。
`.trim());
}

// ── 主入口 ────────────────────────────────────────────────────────────────────
async function main() {
  const [cmd, ...rest] = process.argv.slice(2);

  if (!cmd || cmd === "--help" || cmd === "-h") {
    printHelp();
    process.exit(0);
  }

  if (cmd === "sms") {
    await cmdSms(rest);
    return;
  }

  if (cmd === "config") {
    cmdConfig(rest);
    return;
  }

  console.error(`❌ 未知命令：${cmd}`);
  console.error("   运行 qahome --help 查看可用命令");
  process.exit(1);
}

main().catch(err => {
  console.error(`❌ 未预期错误：${err.message}`);
  process.exit(1);
});

