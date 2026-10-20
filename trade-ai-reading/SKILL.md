---
name: trade-ai-reading
description: "AI 阅读文章记录与总结 Skill。当用户发送一个文章链接（学城链接或外部链接如微信公众号、微博等）并说明该文章属于'工作'还是'非工作'时使用。执行流程：① 将标题、链接、分类记录到学城多维表格 2792863725；② 原文获取：学城链接直接用 citadel --copyFrom 全文复制（保留所有内容和格式），外部链接用 baoyu-url-to-markdown 抓取（尽量保留图片、音频、视频等多媒体和原格式）；③ 在 2792863725 下新建总结文档，包含标题/链接/简介/详细总结/原文，简介 15 字左右（≤30 字），详细总结 200 字左右（≤1000 字）；④ 将总结的简介回写到多维表格对应行的简介列。触发词：阅读记录、记录文章、总结文章、AI Reading、文章链接+分类（工作/非工作）。"

metadata:
  skillhub.creator: "zhangce07"
  skillhub.updater: "zhangce07"
  skillhub.version: "V2"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "154943"
  skillhub.high_sensitive: "false"
---

# trade-ai-reading：AI 阅读文章记录与总结

用户提供一个文章链接 + 分类（工作 / 非工作），完成「表格登记 → 抓取原文 → 建总结文档 → 回写简介」四步闭环。

## 固定资源（写死，勿让 AI 猜测）

| 资源 | ID / 说明 |
|------|-----------|
| 多维表格文档（父文档） | `contentId: 2792863725`，链接 https://km.sankuai.com/collabpage/2792863725 |
| 数据表 | `tableId: 2792608449`（文档内唯一数据表"数据表1"） |
| 表格列结构 | 链接=`colId 1`（文本）、分类=`colId 3`（单选：工作/非工作）、创建时间=`colId 6`（系统列，只读）、标题=`colId 7`（文本）、简介=`colId 514217165`（文本） |
| 总结文档模板 | `contentId: 2793112655`，模板结构为 H2 标题：标题 / 链接 / 简介 / 详细总结 / 原文 |

## 关键结论（已实测验证，直接遵循）

1. **创建时间列（colId 6，columnType 202 系统列）API 写入时自动生成**，禁止手动传值。已实测 addData 不传该列，行创建后 `createdTime` 自动填充。
2. 分类列（colId 3）是单选列，有效选项只有 `工作` 和 `非工作`，传其他值会报错。
3. 模板文档就是多维表格父文档下已有的子文档 `0-测试文章-20261020`（2793112655），新建文档时**复制它的结构（五个 H2 标题）**，而不是用 createDocument --templateId 机制。
4. **学城链接不用 baoyu，直接全文复制**：`createDocument --copyFrom <源文档ID>` 会完整复制源文档的全部内容（含图片、视频、音频、附件、宏、格式），然后在复制出的文档前部插入总结节即可，禁止用 getSimpleMarkdown/getDocumentXml 重建内容（会丢失样式和多媒体）。外部链接（微信公众号、微博等）才用 baoyu-url-to-markdown。

## 执行流程

收到「链接 + 分类」后严格按以下 5 步执行。若用户没说分类，先追问是"工作"还是"非工作"，不要自行猜测。

### 第 1 步：抓取原文（仅外部链接需要，学城链接跳过本步）

先判断链接类型：**学城链接直接进入第 4 步方式 A（全文复制）**，不做任何抓取。

**外部链接**（mp.weixin.qq.com、weibo.com 等）：

CatPaw/agent 嵌套沙箱环境中 Chrome 自身的 sandbox 无法初始化（报 `sandbox initialization failed` / GPU 进程崩溃），**必须先启动一个带 `--no-sandbox --disable-gpu` 的常驻 headless Chrome，再用 `--cdp-url` 复用**：

```bash
export PATH="$HOME/.bun/bin:$PATH"

# 1. 检查常驻 Chrome 是否已启动（调试端口存活即可复用；失败则重新启动）
# 2. 用工具后台任务（run_in_background）启动常驻 Chrome：
cd $HOME/.codex/skills/baoyu-url-to-markdown/scripts && exec bun -e '
import { launch } from "chrome-launcher";
const chrome = await launch({ userDataDir: process.env.HOME + "/Library/Application Support/baoyu-skills/chrome-profile", chromeFlags: ["--headless=new","--no-sandbox","--disable-gpu","--no-first-run","--remote-allow-origins=*","--disable-background-networking"] });
console.log("PORT=" + chrome.port);
setInterval(() => {}, 60000);
'
# 从任务输出文件读取 PORT（启动失败时先删 chrome-profile 下的 Singleton* 锁文件再重试）

# 3. 抓取（cd 到输出目录，媒体会下载到 ./imgs、./videos）
cd <输出目录> && $HOME/.codex/skills/baoyu-url-to-markdown/scripts/baoyu-fetch <url> \
  --cdp-url http://127.0.0.1:<PORT> --download-media --output article.md
```

- 若启动后台 Chrome 的 bun 脚本不存在或依赖缺失：`bun` 用 `curl -fsSL https://bun.sh/install | bash` 安装后 `export PATH="$HOME/.bun/bin:$PATH"`；依赖用 `cd <scripts目录> && bun install` 安装
- 遇到登录墙/CAPTCHA：改用 `--wait-for interaction`（需要可见 Chrome，可能弹出窗口让用户手动操作）
- 微信公众号文章走 generic adapter，直接成功；若 `ECONNRESET` 说明 Chrome 实例崩溃了，重启常驻 Chrome 再试
- 配置文件位置：`~/.baoyu-skills/baoyu-url-to-markdown/EXTEND.md`（download_media: 1）

**⚠️ 微信公众号等懒加载页面的图片补抓（必做）**：

微信正文图片用 `data-src` 懒加载，defuddle 转换器只能识别已渲染进 `src` 的图（通常只有 1-2 张），markdown 里的图片数会远少于原文。**抓取完成后必须校验并补抓**：

1. 抓取时加 `--debug-dir ./debug`（会保存 `page.html`——页面完整 DOM）
2. 从 `page.html` 提取全部真实图片 URL 并下载（qpic.cn 域名，需带 Referer/UA）：

```bash
python3 - << 'EOF'
import re, urllib.request, os
html = open('debug/page.html').read()
# 定位微信正文容器 js_content，提取 data-src 真实图片 URL
m = re.search(r'id="js_content"[^>]*>(.*?)(?:<script|$)', html, re.S)
body = m.group(1) if m else html
urls = list(dict.fromkeys(re.findall(r'data-src="(https?://[^"]+qpic\.cn/[^"]+)"', body)))
os.makedirs('imgs2', exist_ok=True)
for i, u in enumerate(urls):
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://mp.weixin.qq.com/'})
    with urllib.request.urlopen(req, timeout=30) as r, open(f'imgs2/img-{i+1:03d}.jpg', 'wb') as f:
        f.write(r.read())
print(f"共下载 {len(urls)} 张")
EOF
```

3. 校验方法：`debug/page.html` 中 `data-src` qpic.cn 图片数 与 markdown 中 `![` 数量对比；若 markdown 缺图多，用步骤 2 的全量图片
4. 用 HTML 中每张图片**前面的正文片段作锚点**，把 `![配图N](学城图片URL)` 插回 markdown 对应位置（非微信站点同理：markdown 图片数 < 页面 img 数时，从 page.html 提取 src/data-src 补齐）
5. 全部图片先 `uploadImageToDocument` 上传到目标文档，替换/插入 markdown 引用后，最后统一 `updateDocumentByMd`

**学城链接**（km.sankuai.com/collabpage/xxx）：跳过抓取，直接进入第 4 步方式 A。文章标题用 `getMarkdown` 输出第一行的「文档标题：《...》」获取。

### 第 2 步：登记到多维表格

```bash
oa-skills citadel-database addData --tableId 2792608449 \
  --columnIds "7,1,3" \
  --data '[["<文章标题>","<原文链接>","<工作|非工作>"]]'
```

- **列顺序必须与 columnIds 对应**：标题(7) → 链接(1) → 分类(3)
- **文本列直接传纯字符串**（实测富文本节点数组格式会报错：`文本列只支持字符串、数字、布尔值或富文本节点数组`——该报错信息有误导性，实际用纯字符串 `"文本"` 即可成功）
- **不要传创建时间列**，系统自动生成（已实测：addData 不传 colId 6，行创建后创建时间列自动填充）
- 记住返回的**行 ID**，第 5 步回写简介要用（addData 输出不带行 ID，需用 `queryTableData --max-pages 1` 查询获取）
- 文章标题从原文抓取结果中取（微信公众号文章取 markdown front-matter 的 `title` 字段或首个一级标题），不要自己编造

### 第 3 步：生成总结

基于抓取的原文生成两段内容：

- **简介**：15 字左右，不超过 30 字。一句话点明文章核心，不写"本文介绍了"之类的套话
- **详细总结**：200 字左右，不超过 1000 字。概括文章的主要观点、论证和结论

### 第 4 步：新建总结文档（按链接类型二选一）

在多维表格父文档 2792863725 下建子文档，标题统一用「<序号>-<文章标题>」格式（序号为当前最大序号 +1，用 `getChildContent --contentId 2792863725` 确定；首个正式文档从 1 开始）。

**方式 A：学城链接 —— 全文复制（推荐，内容零损失）**

```bash
# 1. 直接复制源文档（全文复制，保留所有图片/视频/音频/附件/宏/格式）
oa-skills citadel createDocument \
  --title "<序号>-<文章标题>" \
  --copyFrom <源文档contentId> \
  --parentId 2792863725
# 返回新文档 contentId

# 2. 取出新文档完整 CitadelMD（保留全部 nodeId 和宏）
oa-skills citadel getMarkdown --contentId <新文档ID> --output /tmp/reading-<序号>.md
```

然后在 `/tmp/reading-<序号>.md` 中，在 `:::title{...}` 节**之后、第一个内容节点之前**插入以下四个节（新增节点不带 nodeId，转换器会自动生成）：

```markdown

## 标题

<文章标题>

## 链接

[<原文链接>](<原文链接>)

## 简介

<15字左右简介>

## 详细总结

<200字左右详细总结>
```

最后回写（全文其余内容原样保留，禁止改动/删除复制出来的任何节点）：

```bash
oa-skills citadel updateDocumentByMd --contentId <新文档ID> --file /tmp/reading-<序号>.md
```

**方式 B：外部链接 —— 从模板创建 + 写入 markdown 原文**

用 --copyFrom 复制模板 2793112655 再更新内容（结构与模板完全一致）：

```bash
oa-skills citadel createDocument \
  --title "<序号>-<文章标题>" \
  --copyFrom 2793112655 \
  --parentId 2792863725
# 返回新文档 contentId

oa-skills citadel updateDocumentByMd --contentId <新文档ID> --file /tmp/reading-<序号>.md
```

内容 Markdown 模板（注意最前面必须有 `:::title` 节点，否则报「doc 节点缺少 title 子节点」；正文为 标题/链接/简介/详细总结 四个 H2 节 + 原文全文）：

```markdown
:::title
<序号>-<文章标题>
:::

## 标题

<文章标题>

## 链接

[<原文链接>](<原文链接>)

## 简介

<15字左右简介>

## 详细总结

<200字左右详细总结>

## 原文

<baoyu-fetch 抓取的原文 markdown 全文，尽量保留原格式，去掉 front-matter>
```

**方式 B 的多媒体处理**（方式 A 全文复制无需处理多媒体）：

- 外部文章图片已下载到 `imgs/`：上传到学城文档后引用。用 `oa-skills citadel uploadImageToDocument --contentId <新文档ID> --imageUrl <本地或远程图片URL> --alt <描述>` 得到学城图片 URL 和 Markdown 语法，将 markdown 中的本地相对路径替换为学城图片引用，最后统一 updateDocumentByMd
- 视频用 `uploadVideoToDocument`，音频用 `uploadAudioToDocument`，附件用 `uploadAttachmentToDocument`
- 学城原文的图片 URL 可直接保留引用，无需重新上传
- 图片较多时可挑重点图片上传（如头图、图表），正文段落全部保留

### 原文格式还原规范（仅方式 B 外部链接必做；方式 A 学城链接全文复制无需还原）

defuddle 转换会拍平原文样式，写入文档前必须按以下规范还原。还原依据是 `--debug-dir` 保存的 `page.html`（页面完整 DOM，含全部样式信息）：

1. **链接节可点击**：链接节的 URL 用 Markdown 链接语法 `[<url>](<url>)`，不要裸文本
2. **原文区标题去重**：微信文章顶部常有 2 个重复大标题（主标题 + "XX专栏 | ..." 栏目标题），只在原文区保留一个，且用 H5（`#####`）小字号，不要 H1/H2 大字号；文章自带的目录列表直接删除（正文标题已结构化，学城大纲不需要重复目录）
3. **小节标题恢复层级**（从 page.html 的 font-weight:bold + 编号规律判断，不是 h 标签）：
   - `一、二、三、` 中文序号章标题 → `###`
   - `1.1` / `2.3` 两级编号 → `####`
   - `2.3.1` / `4.2.1` 三级编号 → `#####`
4. **加粗还原**：微信用 `<span style="font-weight: bold">` 而非 `<strong>`，提取方法：

```bash
python3 - << 'EOF'
import re, html as H, json
page = open('debug/page.html').read()
m = re.search(r'id="js_content"[^>]*>(.*?)(?:<script|$)', page, re.S)
body = (m.group(1) if m else page).replace('\\x22','"').replace('&quot;','"')
raws = re.findall(r'<span[^>]*style="[^"]*font-weight:\s*bold[^"]*"[^>]*>(.*?)</span>', body, re.S)
bolds = []
for r in raws:
    t = H.unescape(re.sub(r'<[^>]+>', '', r)).strip()
    if t and len(t) >= 2 and re.search(r'[\u4e00-\u9fa5A-Za-z0-9]', t) and t not in bolds:
        bolds.append(t)
json.dump(bolds, open('strongs.json','w'), ensure_ascii=False)
print(len(bolds))
EOF
```

   应用规则（逐片段处理，跳过 `#` 开头的标题行和已含 `**` 的行）：① 整行等于片段 → 整行加粗；② 行首（含 `- ` 列表项前缀）匹配 → 加粗前缀（"标签："类片段全部如此）；③ 全文唯一出现且 ≤30 字 → 行内加粗
5. **列表与链接核对**：完成后核对数量——`page.html` 的 `<li>` 数 vs markdown `- ` 行数；`<a href>` 数 vs markdown `](http` 数。注意匹配时先去掉 `**` 标记、`pre\_tasks` 类转义符、`&amp;`/`&` 差异，避免误报缺失
6. **图片尺寸**：横向照片（宽 ≥ 高）`{width=500 height=按比例}`，竖向照片 `{height=500 width=按比例}`，正方形按横向处理。示例：`![配图1](url){width=500 height=147}`
7. **刻意不还原**：颜色（微信灰色正文/黄色高亮序号等主题装饰，学城有自己的主题色）、字号 px 值、行距 margin（由标题层级和学城排版接管）。斜体/删除线/下划线/引用块出现时才需处理

**文档标题命名规则**：见第 4 步开头，两种方式相同。

### 第 5 步：回写简介到表格

```bash
oa-skills citadel-database updateData --tableId 2792608449 \
  --rowIds "<第2步返回的行ID>" \
  --columnIds "514217165" \
  --data '[["<简介>"]]'
```

简介列同样直接传纯字符串。

## 验证

每步操作后检查命令输出确认成功；全部完成后向用户汇报：

- 表格新增行的链接（https://km.sankuai.com/xtable/2792863725?table=2792608449）
- 新建总结文档的链接（https://km.sankuai.com/collabpage/<新文档ID>）
- 简介回写结果

## 常见问题

- **baoyu-fetch 抓取失败**（网站反爬/需 JS 渲染）：加 `--wait-for interaction` 重试；仍失败则告知用户，询问是否可以接受仅用页面可获取的部分内容，或让用户粘贴原文
- **addData 报单选列错误**：确认分类值只传"工作"或"非工作"，与 colId 3 的 options 完全一致
- **认证失败**：`oa-skills citadel --clear-cache` 或 `oa-skills citadel-database --clear-cache` 后重试
- **本地媒体目录清理**：图片/视频上传到学城并确认文档渲染成功后，可删除本地 `url-to-markdown/` 下的媒体文件；markdown 中间文件也可清理

## 边界

- 只处理用户明确发来的文章链接；用户没说分类时先问
- 同一链接重复发送时正常新增一行（不去重，除非用户要求）
- 外部链接涉及登录态（如微博需登录）无法抓取时，提示用户改用 `--wait-for interaction` 或复制粘贴正文
