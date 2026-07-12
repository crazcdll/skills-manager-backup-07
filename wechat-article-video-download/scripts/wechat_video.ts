#!/usr/bin/env node
/**
 * ============================================================================
 * 微信公众号文章视频下载器 (wechat-article-video-download)
 * ============================================================================
 *
 * 【做什么】
 *   传入一个微信公众号文章链接（mp.weixin.qq.com/s/...），
 *   列出文章里嵌入的所有视频；或者按序号下载其中某一个/全部。
 *
 * 【原理】
 *   微信文章的 HTML 里同时包含两类信息：
 *     1. <iframe class="video_iframe" data-mpvid="wxv_XXX"> —— 视频占位 iframe
 *     2. JS 数据块里包含 mpvideo.qpic.cn/<file_id>.fXXXXX.mp4?auth_key=...
 *        —— 真正的 MP4 直链（带临时鉴权 auth_key）
 *   只要带一个正常的浏览器 User-Agent 去 fetch，就能拿到完整 HTML，
 *   用正则把这两类信息抠出来配对，再 fetch 直链即可下载视频。
 *   不需要 headless 浏览器、不需要 yt-dlp、不需要任何第三方包。
 *
 * 【运行要求】
 *   Node.js 22+（依赖：原生 fetch、Readable.fromWeb、parseArgs、TS strip-types）
 *
 * 【命令行用法】
 *   wechat_video.ts list <url> [--json]
 *   wechat_video.ts download <url> <index|all> [--quality fXXXXX] [--output DIR]
 * ============================================================================
 */

// ---- 依赖：全部来自 Node.js 内置模块 ----
import { createHash } from "node:crypto";                           // 用于把 url 哈希成缓存文件名
import { mkdir, readFile, rename, stat, writeFile } from "node:fs/promises"; // 异步文件操作
import { createWriteStream } from "node:fs";                        // 流式写入（边下边写，不占内存）
import { homedir } from "node:os";                                  // 拿用户主目录，定位缓存目录
import { join } from "node:path";                                   // 跨平台拼接路径
import { parseArgs } from "node:util";                              // Node 内置的命令行参数解析器
import { Readable } from "node:stream";                             // 把 Web ReadableStream 转 Node 流
import { pipeline } from "node:stream/promises";                    // 用 Promise 串联流，自动处理背压和错误

// ============================================================================
// 常量配置
// ============================================================================

/**
 * 伪装的 User-Agent。
 * 微信对没有正常 UA 的请求会返回 "环境异常" 验证页，所以必须装成普通浏览器。
 * 用 macOS Chrome 是因为兼容性最广，几乎不会被拦。
 */
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

/**
 * 画质代码的优先级（从高到低）。
 * 注意命名反直觉：f10104 数字最大但实际是手机低清版（HEVC 480x270）。
 * 实测对应关系（约 10 分钟的视频）：
 *   f10002  H.264  ~960x544  ~80MB  ← 最高码率、文件最大
 *   f10102  HEVC   ~960x544  ~50MB  ← 同分辨率但 HEVC 编码更省体积
 *   f10004  H.264  ~846x480  ~30MB
 *   f10104  HEVC   ~480x270  ~13MB  ← 手机版最低清
 * `as const` 让 TS 推断成元组而不是 string[]，方便后面做联合类型。
 */
const QUALITY_PRIORITY = ["f10002", "f10102", "f10004", "f10104"] as const;
/** 画质代码的字符串字面量联合类型，从上面那个 const 元组派生而来 */
type QualityCode = (typeof QUALITY_PRIORITY)[number];

/** HTML 缓存目录：~/.cache/wechat-article-video-download/<hash>.html */
const CACHE_DIR = join(homedir(), ".cache", "wechat-article-video-download");

/** HTML 缓存有效期：10 分钟。够 list 之后接着 download 复用同一份 HTML，
 *  又不会因为 auth_key 过期太久而下载失败。 */
const CACHE_TTL_MS = 10 * 60 * 1000;

// ============================================================================
// 类型定义
// ============================================================================

/**
 * 一个视频在文章中的完整信息。
 *   index    —— 在文档中出现的顺序（1-based，给用户看的"第几个"）
 *   vid      —— 微信内部 ID（wxv_xxxxx）。如果 iframe 数和直链数对不上则为 null
 *   file_id  —— mpvideo.qpic.cn 上的实际文件名（不含扩展名）
 *   qualities —— 该视频提供的所有画质 → 对应直链 URL 的映射
 */
interface Video {
  index: number;
  vid: string | null;
  file_id: string;
  qualities: Record<string, string>;
}

// ============================================================================
// 工具函数
// ============================================================================

/**
 * 判断文件/目录是否存在（异步）。
 * Node 没有 stdlib 的 exists() 异步版本，所以用 stat 抛错的方式来判断。
 */
async function fileExists(p: string): Promise<boolean> {
  try {
    await stat(p);          // 文件存在就成功返回
    return true;
  } catch {
    return false;            // ENOENT 之类的错误统一当成"不存在"
  }
}

/**
 * 抓取文章 HTML，带本地缓存。
 *   url       —— 微信文章链接
 *   useCache  —— 是否优先用缓存（默认 true）。test 场景可传 false 强制刷新。
 *
 * 缓存策略：
 *   - 文件名 = sha256(url) 取前 16 位（够长避免碰撞，又不至于太长）
 *   - 文件 mtime 距今 < 10 分钟则直接用缓存
 *   - 否则发起网络请求，成功后写入缓存
 */
async function fetchHtml(url: string, useCache = true): Promise<string> {
  // 缓存目录可能首次不存在，recursive=true 等价于 mkdir -p，已存在不报错
  await mkdir(CACHE_DIR, { recursive: true });

  // 把 url 哈希成短 key，避免文件名里出现非法字符
  const key = createHash("sha256").update(url).digest("hex").slice(0, 16);
  const cacheFile = join(CACHE_DIR, `${key}.html`);

  // 命中缓存且未过期 → 直接读
  if (useCache && (await fileExists(cacheFile))) {
    const st = await stat(cacheFile);
    if (Date.now() - st.mtimeMs < CACHE_TTL_MS) {
      return await readFile(cacheFile, "utf8");
    }
  }

  // 走网络。带浏览器 UA + 中文 Accept-Language，模拟正常用户。
  const res = await fetch(url, {
    headers: {
      "User-Agent": UA,
      Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
  });

  // HTTP 层面失败（4xx/5xx）直接抛错
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} fetching article: ${res.statusText}`);
  }

  const body = await res.text();

  // 微信触发风控时会返回 HTTP 200 但内容是验证页，必须按内容判断
  if (body.includes("环境异常")) {
    throw new Error(
      "微信返回了风控验证页。链接可能已失效、被限制访问或当前网络被风控。",
    );
  }

  // 写缓存。注意：即使后续解析失败，也已经把 HTML 存下来了，方便排查
  await writeFile(cacheFile, body, "utf8");
  return body;
}

/**
 * 从 HTML 文本里解析出所有视频，按文档出现顺序返回。
 *
 * 解析思路：
 *   1. 把 HTML 里的转义字符（\x26amp; → &）还原，方便正则匹配
 *   2. 用正则 A 抓所有 <iframe data-mpvid="wxv_XXX"> —— 视频在正文里的占位
 *   3. 用正则 B 抓所有 mpvideo.qpic.cn/<file_id>.fXXXXX.mp4?... —— 真实直链
 *   4. 按 file_id 聚合：同一个视频会出现 4 个 URL（4 个画质档）
 *   5. 把 file_id 按"首次出现的字符位置"排序，得到文档顺序
 *   6. 把同序号的 iframe (wxv_) 和 file_id 配对
 */
function parseVideos(html: string): Video[] {
  // ---- 第 1 步：还原转义 ----
  // 微信把视频元数据嵌在 JS 字符串里，& 会被序列化成 \x26 / \x26amp; / &amp;
  // 三种都还原成 &，否则正则会匹配不到完整 URL
  const text = html
    .replaceAll("\\x26amp;", "&")
    .replaceAll("\\x26", "&")
    .replaceAll("&amp;", "&");

  // ---- 第 2 步：抓 iframe（拿到 wxv_ id 和它在文档中的位置）----
  // matchAll 返回的每个 match 带 .index（匹配起点的字符偏移），用来确定文档顺序
  const iframeRe = /<iframe[^>]*data-mpvid="(wxv_\d+)"/gi;
  const iframes: Array<{ pos: number; vid: string }> = [];
  for (const m of text.matchAll(iframeRe)) {
    iframes.push({ pos: m.index!, vid: m[1]! });
  }

  // ---- 第 3 步：抓 MP4 直链 ----
  // 同一个视频会出现 4 次（4 个画质档），所以要按 file_id 分组
  const mp4Re =
    /(https?:\/\/mpvideo\.qpic\.cn\/([a-z0-9]+)\.(f\d+)\.mp4\?[^"'<>\s\\]+)/gi;

  // 外层 Map：file_id → 该视频的画质表
  // 内层 Map：quality 代码（如 "f10002"）→ { 出现位置, 完整 URL }
  const fileQualities = new Map<string, Map<string, { pos: number; url: string }>>();

  for (const m of text.matchAll(mp4Re)) {
    const [, url, fid, q] = m;   // 全匹配 / file_id / quality
    const pos = m.index!;

    // 若 file_id 第一次出现，初始化内层 Map
    let bucket = fileQualities.get(fid!);
    if (!bucket) {
      bucket = new Map();
      fileQualities.set(fid!, bucket);
    }

    // 同一个 (file_id, quality) 可能在 HTML 里被嵌入多次（比如重复的 JSON 数据块）
    // 取最早出现的那个作为代表，确保 pos 是真正的"首次出现位置"
    const existing = bucket.get(q!);
    if (!existing || pos < existing.pos) {
      bucket.set(q!, { pos, url: url! });
    }
  }

  // ---- 第 4 步：按文档顺序对 file_id 排序 ----
  // 每个 file_id 的"位置"取它所有画质里最早出现的那个
  const fids = [...fileQualities.keys()].sort((a, b) => {
    const minA = Math.min(...[...fileQualities.get(a)!.values()].map((v) => v.pos));
    const minB = Math.min(...[...fileQualities.get(b)!.values()].map((v) => v.pos));
    return minA - minB;
  });

  // ---- 第 5 步：组装结果 ----
  // 按位置序号把 fids 和 iframes 一一配对（同一个视频两者顺序一致）
  // 如果数量对不上（极少见），多出来的 file_id 的 vid 会是 null
  return fids.map((fid, i) => {
    const qualities: Record<string, string> = {};
    for (const [q, { url }] of fileQualities.get(fid)!) {
      qualities[q] = url;
    }
    return {
      index: i + 1,                       // 1-based，给人看
      vid: iframes[i]?.vid ?? null,
      file_id: fid,
      qualities,
    };
  });
}

/**
 * 从一个视频的所有可用画质里挑一个。
 *   qualities  —— 该视频的画质表
 *   preferred  —— 用户指定的画质（--quality 参数），undefined 表示自动选
 *
 * 选择规则：
 *   1. 用户指定且确实存在 → 用指定的
 *   2. 否则按 QUALITY_PRIORITY 从高到低试，第一个存在的就用
 *   3. 都没匹配上（理论不会发生）→ 用 qualities 里的第一个
 */
function pickQuality(
  qualities: Record<string, string>,
  preferred: string | undefined,
): { quality: string; url: string } {
  // 优先尊重用户的明确指定
  if (preferred && qualities[preferred]) {
    return { quality: preferred, url: qualities[preferred] };
  }
  // 默认：按优先级取第一个存在的
  for (const q of QUALITY_PRIORITY) {
    if (qualities[q]) return { quality: q, url: qualities[q] };
  }
  // 兜底：极端情况下，比如微信改了画质代码命名
  const [q, url] = Object.entries(qualities)[0]!;
  return { quality: q, url };
}

/**
 * 把一个远程 URL 流式下载到本地文件。
 *   url    —— 视频直链
 *   dest   —— 最终保存路径
 *   label  —— 进度条上显示的标签（比如 "#5"）
 *
 * 流程：
 *   1. fetch 拿到 ReadableStream（注意不要 .blob() 也不要 .arrayBuffer()，
 *      否则会把整个 80MB 加载到内存）
 *   2. 用 Readable.fromWeb 把 Web ReadableStream 转成 Node Readable
 *   3. 监听 data 事件计字节数 + 节流打印进度
 *   4. pipeline 把流送到磁盘，全程边下边写
 *   5. 先写 .part 临时文件，下完再 rename，避免下载中断留下"看起来完整"的坏文件
 */
async function downloadFile(url: string, dest: string, label: string): Promise<void> {
  // 注意 Referer：微信视频 CDN 校验 Referer，必须设成 https://mp.weixin.qq.com/
  const res = await fetch(url, {
    headers: { "User-Agent": UA, Referer: "https://mp.weixin.qq.com/" },
  });
  if (!res.ok || !res.body) {
    throw new Error(`HTTP ${res.status} downloading ${label}: ${res.statusText}`);
  }

  // 用于进度百分比。微信 CDN 一般会带 Content-Length，没有就显示 ?
  const total = Number(res.headers.get("content-length") ?? 0);

  // 临时文件名加 .part 后缀，下载完成才 rename
  const tmp = `${dest}.part`;
  // 父目录可能不存在（比如 ./videos/）
  await mkdir(join(dest, ".."), { recursive: true });

  let downloaded = 0;     // 累计已下载字节
  let lastPrint = 0;      // 上次打印进度的时间戳（毫秒），用来节流
  const out = createWriteStream(tmp);

  // Web ReadableStream → Node Readable
  // 类型断言成 any 是因为 Node 的类型声明里 res.body 是 ReadableStream<Uint8Array>，
  // 但 Readable.fromWeb 的签名稍有差异，运行时完全兼容
  const reader = Readable.fromWeb(res.body as any);

  // 监听 data：每收到一块数据就累计字节、按节流打印进度（300ms 一次，避免刷屏）
  reader.on("data", (chunk: Buffer) => {
    downloaded += chunk.length;
    const now = Date.now();
    if (now - lastPrint > 300) {
      const mb = downloaded / 1024 / 1024;
      const pct = total ? ((downloaded / total) * 100).toFixed(1) : "?";
      // \r 让光标回到行首，下次输出会覆盖本行 —— 实现"原地刷新"的进度条
      process.stderr.write(`  [${label}] ${mb.toFixed(1)} MB  ${pct}%\r`);
      lastPrint = now;
    }
  });

  // pipeline 把 reader 的数据全部喂给 out，期间任意一方报错都会被传播
  // 用 stream/promises 版的 pipeline 是为了 await 上面这一切
  await pipeline(reader, out);

  // 下载完成才正式启用文件名 —— 如果上面任何一步失败，留下的就是 .part，
  // 用户和脚本都能立刻分辨"这文件没下完"
  await rename(tmp, dest);

  const mb = (downloaded / 1024 / 1024).toFixed(1);
  // \n 是为了把进度行的 \r 终结掉，免得后续输出叠在同一行
  process.stderr.write(`  [${label}] ${mb} MB  done  -> ${dest}\n`);
}

/**
 * 把视频列表打成人类友好的格式输出到 stdout。
 * （machine-readable 的 JSON 形式在 cmd_list 里直接 console.log，不走这里）
 */
function printList(videos: Video[]): void {
  console.log(`共找到 ${videos.length} 个视频（按文档顺序）:\n`);
  for (const v of videos) {
    const qs = Object.keys(v.qualities).sort().join(", ");
    console.log(`  [${v.index}] vid=${v.vid}`);
    console.log(`      file_id=${v.file_id}`);
    console.log(`      可用画质: ${qs}`);
    console.log();
  }
}

/**
 * 打印 usage 然后退出。`: never` 告诉 TS 此函数不会正常返回，
 * 让调用处后续代码不需要再判 null/undefined。
 */
function usage(exitCode = 0): never {
  console.error(
    `用法:
  wechat_video.ts list <url> [--json]
  wechat_video.ts download <url> <index|all> [--quality f10002|f10102|f10004|f10104] [--output DIR]`,
  );
  process.exit(exitCode);
}

// ============================================================================
// 主入口：解析命令行 → 分发子命令
// ============================================================================

async function main(): Promise<void> {
  // process.argv[0] 是 node 可执行文件路径，[1] 是脚本路径，从 [2] 开始才是用户参数
  const [cmd, ...rest] = process.argv.slice(2);
  if (!cmd) usage(2);

  // -------- 子命令 1：list --------
  if (cmd === "list") {
    // parseArgs 把 rest 切成 --xxx 选项 + 位置参数
    const { values, positionals } = parseArgs({
      args: rest,
      options: { json: { type: "boolean", default: false } },
      allowPositionals: true,
    });
    const url = positionals[0];
    if (!url) usage(2);

    const html = await fetchHtml(url);
    const videos = parseVideos(html);

    if (values.json) {
      // JSON 形态便于其它程序消费（比如 Claude 自己解析）
      console.log(JSON.stringify(videos, null, 2));
    } else {
      printList(videos);
    }
    return;
  }

  // -------- 子命令 2：download --------
  if (cmd === "download") {
    const { values, positionals } = parseArgs({
      args: rest,
      options: {
        quality: { type: "string" },                          // 可选：强制画质
        output: { type: "string", default: "./videos" },       // 可选：输出目录
      },
      allowPositionals: true,
    });
    const [url, indexArg] = positionals;
    if (!url || !indexArg) usage(2);

    const html = await fetchHtml(url);
    const videos = parseVideos(html);
    if (videos.length === 0) {
      console.error("文章中未找到任何视频。");
      process.exit(1);
    }

    // 决定要下哪些：单个 index 还是 all
    let targets: Video[];
    if (indexArg === "all") {
      targets = videos;
    } else {
      const n = Number(indexArg);
      // Number.isInteger 用来排除小数、NaN、Infinity
      if (!Number.isInteger(n) || n < 1 || n > videos.length) {
        console.error(`序号超出范围 (合法: 1..${videos.length})，输入: ${indexArg}`);
        process.exit(2);
      }
      targets = [videos[n - 1]!];
    }

    // 校验 --quality 取值合法
    if (values.quality && !QUALITY_PRIORITY.includes(values.quality as QualityCode)) {
      console.error(
        `无效的 --quality: ${values.quality}（允许值: ${QUALITY_PRIORITY.join(", ")}）`,
      );
      process.exit(2);
    }

    // 依次下载选中的视频。批量下载时串行，避免并发把鉴权窗口耗尽
    for (const v of targets) {
      const { quality, url: mp4Url } = pickQuality(v.qualities, values.quality);

      // 文件名前缀里塞上序号 + vid（或截短的 file_id），方便日后辨认
      // padStart 保证 video01_xxx / video02_xxx 排序时和数字序一致
      const vidPart = v.vid ?? v.file_id.slice(0, 12);
      const filename = `video${String(v.index).padStart(2, "0")}_${vidPart}_${quality}.mp4`;
      const dest = join(values.output as string, filename);

      console.error(`视频 #${v.index}  vid=${v.vid}  画质=${quality}`);
      await downloadFile(mp4Url, dest, `#${v.index}`);
    }
    return;
  }

  // cmd 不是 list 也不是 download
  usage(2);
}

// 入口。所有未捕获的异常（含网络/解析错误）在这里统一兜底，
// 退出码 3 区分于 usage 的 2，方便脚本调用方判断"是用错了"还是"真的出错了"
main().catch((err: unknown) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(3);
});
