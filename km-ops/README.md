# 面向 AI 设计的学城技能：km-ops

[km-ops](https://dev.sankuai.com/code/repo-detail/~WANGZEXI02/km-ops/file/list?path=&branch=refs%2Fheads%2Fmain)——别自创格式，别替它操心，出错时告诉它怎么改。


## 先看一个数字

还没开始干活，光加载技能本身就要先吃掉一大笔上下文——技能的 description 和 SKILL.md 每次激活都进上下文：

| 加载项 | 官方 oa-skills citadel | km-ops |
|---|---|---|
| description | 333 token | 50 token |
| SKILL.md 全文 | 9345 token（451 行） | 359 token（34 行） |
| **加载总开销** | **9678 token** | **409 token** |

官方是 km-ops 的 **24 倍**——还没干活，先吃掉近一万 token。这还只是固定开销；真要读文档，差距更大。

比如这个小文档：

```Plain Text
# 技术方案评审模板
## 背景
当前系统存在以下问题：
- 接口响应超时
- 数据库慢查询
## 方案
采用 Redis 缓存层，预期 P99 降低 40%。
```

就这么几行，两种工具读出来，喂给大模型的 token 数与成本（按 Claude Sonnet 4.6 输入价 $3/1M token）：

| 技能 | 输出格式 | 小文档（8 节点） | 大文档（1902 节点） |
|---|---|---|---|
| 官方 oa-skills citadel getDocumentXml | CitadelXML | 278 token · ¥0.006 | 68799 token · ¥1.49 |
| km read | 标准 HTML | 97 token · ¥0.002 | 38018 token · ¥0.82 |

小文档就差 **65%**。文档越大，被 nodeId 吃掉的比例越高——大文档单次读就贵出近一倍，**¥1.49 vs ¥0.82**。

钱花在哪了？看一眼官方输出的 CitadelXML 就懂了：

```xml
<km-doc>
<km-title nodeId="36a0c9217f3943d3b80a91802ddaed9c">技术方案评审模板</km-title>
<h2 nodeId="2e66b77b3ded41f69de5d4be4cca74c0">背景</h2>
<p nodeId="0f6c8584b13041579b2e10c544e2d9d0">当前系统存在以下问题：</p>
<ul nodeId="bcc3a3eec6444e49a1e206a15a593ca1">
<li nodeId="2382913bb44448379c983e93a6a4e3df">接口响应超时</li>
<li nodeId="af59635cebec4a0f88022d1ad7bab877">数据库慢查询</li>
</ul>
<h2 nodeId="0b98caa12d6d4f1b8fa606dd8ca3ef59">方案</h2>
<p nodeId="4f87e74992674389adb8ee6c9684e200">采用 Redis 缓存层，预期 P99 降低 40%。</p>
</km-doc>
```

每个节点都拖一个 nodeId="..."，32 位无分隔十六进制。这种串对 tokenizer 是灾难——没有语义，无法合并，被切成碎片：

```
36a0c9217f3943d3b80a91802ddaed9c
→ ['36','a','0','c','921','7','f','394','3','d','3','b','80','a','918','02','dd','aed','9','c']
→ 20 个 token，全是噪声
```

8 个 nodeId 就吞掉 **67%** 的 token，且对 AI 理解文档毫无帮助。km-ops 直接输出干净 HTML，一个 nodeId 都没有：

```html
<h1>技术方案评审模板</h1>
<h2>背景</h2>
<p>当前系统存在以下问题：</p>
<ul><li>接口响应超时</li><li>数据库慢查询</li></ul>
```

这是做 km-ops 的起点：**上下文不只是真金白银，更是模型的注意力。** 越长的上下文、越多的噪声 token，模型越容易「迷失在中间」——真正重要的信息被 nodeId 海洋淹没，推理质量随之下降。省 token 不只是省钱，更是把模型的注意力还给真正有意义的内容。

## 官方技能的坑

官方 oa-skills citadel 是个 451 行 SKILL.md 的庞然大物。

### 坑 1：依赖 Node.js，还要自动装 nvm

官方 SKILL.md 开篇就是一整节「Node.js 版本检查」：

<details>
<summary>官方原文</summary>

> 执行 citadel skill 时会自动检查 Node.js 版本是否符合要求（>= 18.0.0）。如果版本过低，系统会：
> 1. **自动检测并安装 nvm**（如未安装）
> 2. **通过 nvm 自动安装并切换到 Node.js 18 或更高版本**
> 3. **重新执行命令**，使用新的 Node.js 版本

</details>

一次操作，先折腾运行时。km-ops 是单二进制，bin/km-darwin-arm64 拷过去就能跑，零依赖。

### 坑 2：在技能里塞偏好记忆

官方在本地维护一个记忆文件，还写了完整的「读取 / 写入 / 使用」说明书：

<details>
<summary>官方原文</summary>

> **记忆文件路径**：`~/.cache/oa-skills/citadel-memory.md`
>
> **读取**：每次 skill 激活时执行：
> ```bash
> node -e "const fs=require('fs'),os=require('os'),path=require('path');const f=path.join(os.homedir(),'.cache','oa-skills','citadel-memory.md');try{process.stdout.write(fs.readFileSync(f,'utf8'))}catch{}"
> ```
> 若文件存在：将内容加载到上下文，后续操作按需查阅对应章节。
>
> **写入触发词（以下任意一类均触发）**：
> - 记住偏好：「记住这个」「以后都这样」「记住我的习惯」「下次自动...」
> - 记住位置：「以后都放这里」「记住这个目录」「默认创建在 XXX 下」
> - 记住模板：「记住这个模板」「这个模板叫做 XX」「以后用 XX 模板」
> - 记住密级：「以后默认设为 CX」「默认密级是 CX」
> - 清除偏好：「取消默认」「清除记忆」「忘掉这个」「不用记住了」
>
> **写入流程**：1. 文件不存在则先创建目录、写入初始模板；2. 用 AI 编辑对应章节；3. 只改目标章节；4. 告知用户「已记住你的偏好，下次操作时自动应用。」
>
> **使用**：创建文档未指定位置时查阅默认位置；说「用我的[别名]模板」时查阅常用模板；`createDocument` 成功后查阅默认密级。

</details>

这套记忆文件每次激活都进上下文，做的是和文档读写无关的事。而记忆本该是 Agent 执行器的职责——执行器自己会注入系统提示词、维护记忆，技能再揣一份，两套记忆冲突，AI 不知道该听谁的。km-ops 不做记忆，只做文档读写。

### 坑 3：URL → ID 规则写成一节说明书

官方用了一整节列举映射规则，原文如下：

<details>
<summary>官方原文</summary>

> 用户给 学城（km） 链接时直接提取，不要追问：
>
> - 文档链接：
>   - `km.sankuai.com/collabpage/1234567890` → `--contentId 1234567890`
>   - `km.sankuai.com/page/1234567890` → `--contentId 1234567890`
> - 模板中心链接（用于从模板创建/读取模板内容）：
>   - `km.sankuai.com/template-center/1234567890` → `--templateId 1234567890`
>   - `km.sankuai.com/template-center/1234567890?isRelease=1` → `--templateId 1234567890`（忽略 query 参数）
> - 用户直接给纯数字字符串 → 直接作为对应 ID
>
> 模板链接 `templateId` 提取规则（必须遵守）：
>
> 1. 若链接形如 `km.sankuai.com/template-center/<数字ID>`（可带 query/hash），提取 `<数字ID>` 作为 `templateId`。
> 2. 若用户直接给纯数字字符串，直接作为 `templateId`。
> 3. 只有在以上规则都无法提取时，才追问 `templateId`。

</details>

对 AI 来说这根本不需要说明书——km-ops 的所有命令第一个参数就是文档 ID，只认纯数字。SKILL.md 里一句提示就够：

```bash
# 文档链接 km.sankuai.com/collabpage/1461835105 中 ID 是 1461835105
```

URL 提 ID 这种事 AI 自己就会，不用教；就算 AI 偷懒直接传了 URL，脚本报错踢回去就行了。

### 坑 4：接口不直觉，需要「意图路由」

官方命令是 getDocumentXml、getSimpleMarkdown、getTemplateSimpleMarkdown、getTemplateXml、updateDocumentByXml……光「读文档」就有四五种姿势。于是 SKILL.md 不得不写一整节「意图路由」，用 6 条优先级规则教 AI：

<details>
<summary>官方原文</summary>

> ### 优先级规则（必须遵守）
>
> 1. 用户意图是"创建/新建/生成/复制文档"时，优先走 `createDocument`，不要因为出现 km 链接就先 `getSimpleMarkdown`。
> 2. 在创建意图里，链接只用于提取 ID：
>    - 目标目录链接（`collabpage/<id>` / `page/<id>`）→ `--parentId <id>`
>    - 模板中心链接（`template-center/<id>`）→ `--templateId <id>`
>    - 来源文档链接（`collabpage/<id>` / `page/<id>`）→ `--copyFrom <id>`
> 3. 用户意图是"查看模板内容"时，执行 `getTemplateSimpleMarkdown`，不要走 `getSimpleMarkdown`。
>    - 但如果用户意图是"基于模板修改内容再创建文档"（如"按模板改好内容后创建"、"基于模板填写后生成"），应使用 `getTemplateXml` 获取完整 XML，AI 修改后通过 `createDocument --file` 创建；不要用 `getTemplateSimpleMarkdown`（简化版会丢失 nodeId 等关键信息）。
> 4. 只有用户明确要求"阅读/查看/总结文档内容"且目标是文档正文时，才执行 `getSimpleMarkdown`。
> 5. **群权限管理**：如果是在大象群里创建文档，创建后需要执行两步授权：
>    - 为当前群授予浏览权限：`oa-skills citadel grant --url https://km.sankuai.com/collabpage/<id> --xm-group-ids <群ID> --perm "仅浏览"`
>    - 为群助理的管理员（mis）授予管理权限：`oa-skills citadel grant --url https://km.sankuai.com/collabpage/<id> --person <管理员mis> --perm "可管理"`
> 6. **创建后的授权收尾**：每次 `createDocument` 成功后，必须询问用户："文档已创建，是否需要为特定人员/群组授权？"；若当前场景是大象群，则自动执行两步授权；若是单聊或其他场景，则询问用户是否需要授权，按需执行。

</details>

接口一旦需要「路由说明」，就说明命名没做到顾名思义。km-ops 的原则是**一件事一种方式**：

```bash
km read 1461835105      # 读，就一个命令，输出 HTML
km create < doc.md      # 建，从 markdown
km update 1461835105 < doc.html  # 改，从 HTML
```

没有 getXxxByYyy 的排列组合，AI 不需要路由表。

### 坑 5：创建文档前一堆「必读」

官方 createDocument 前面挂着三块必读——内容格式要求、位置默认规则、内容传递方式：

<details>
<summary>官方原文</summary>

> ⚠️ **创建文档前的内容格式要求**（必读）：
> 1. **优先使用富文本原生节点**：用 `<p>`、`<h1>`～`<h6>`、`<ul>`、`<ol>`、`<table>` 等标准节点表达内容，**禁止使用 `<km-markdown>` 写入文档内容**——这样做不仅失去划词评论、选区编辑等学城完整能力，还更容易出错。
> 2. **普通 Markdown 文件（`.md`）可直接用 `--file` 传入**，系统自动转为富文本。
> 3. **根标签只能是 `<km-doc>`**，禁止使用 `<doc>`、`<document>`、`<body>` 等任何其他标签
> 4. **`<km-title>` 必须是第一个子节点，有且只有一个**
> 5. **禁止使用 `<div>`、`<section>`、`<thead>`、`<tbody>` 等 HTML 布局标签**（会被静默丢弃）
> 6. 详见 [references/doc-xml-syntax.md](references/doc-xml-syntax.md) 末尾的「AI 生成前的自检清单」
>
> ⚠️ **位置默认规则（必须遵守）**：
> - 用户**未明确指定**创建位置（未给 `--parentId` 或 `--spaceId`）时，**一律不加这两个参数**，由系统自动创建在当前用户个人空间根目录。
> - **禁止**从上下文中自动猜测或沿用任何文档 ID 作为 `--parentId`。只有用户明确说"在 XXX 文档下创建"或"创建为 XXX 的子文档"时，才传 `--parentId`。
>
> 📝 **内容传递方式（优先使用文件方式）**：
> - **文档内容较多时（超过几段正文），必须优先将内容写入本地文件，再通过 `--file` 参数传入**，避免在命令行中直接输出大段内容导致 AI 输出过大。
> - 只有内容极短（单行标题、简短说明等）且用户无额外需求时，才可直接用 `--content` 参数内联传入。

</details>

生怕 AI 一步踏错。但 AI 不需要预先背诵规则——**它真正出错时，把错误和修正方向报给它就够了。** km-ops 像编译器一样工作：创建时做结构校验，不合法就直接拒绝，并告诉你差在哪：

```
错误：内容不含 HTML 标签，疑似 markdown 格式。km update 只接受 HTML
```

不静默转换，不降级兜底。错了就报错，让 AI 决定下一步。预先必读是给人看的，运行时报错才是给 AI 看的。

## 设计原则

km-ops 的核心是一个 **HTML ↔ 学城 ProseMirror JSON 的编译层**。学城文档底层是带 nodeId 的 ProseMirror JSON——对 AI 来说又吵又贵。km-ops 像编译器一样，在两端做转换：

- **读**：把 JSON「反编译」成干净 HTML，nodeId 藏在内部映射里，不进上下文
- **写**：把 AI 改过的 HTML「编译」回 JSON——先 diff 算出改了哪些节点，再通过映射把变更定位回 nodeId，只 patch 变化部分
- **校验**：像编译器检查语法一样校验结构，不合法直接报错并给出修正方向

AI 永远只碰 HTML，nodeId 和 JSON 结构这些底层细节全由 km-ops 维护。下面是这条主线的具体展开。

### read：标准 HTML，无私有格式

```bash
$ km read 1461835105
```

```html
<h1>技术方案评审模板</h1>
<h2>背景</h2>
<p>当前系统存在以下问题：</p>
<ul><li>接口响应超时</li><li>数据库慢查询</li></ul>
<h2>方案</h2>
<p>采用 Redis 缓存层，预期 <strong>P99 降低 40%</strong>。</p>
```

没有 nodeId、没有 <km-doc>、没有 <km-title>、没有 <km-collapse>。就是标准 HTML，浏览器里什么样，这里就什么样。AI 不需要先学一套私有标签的术语表才能工作——这是前面省 token 的根。

马斯克给 SpaceX/Tesla 定过一条规矩：

> 不要给对象、软件或流程造缩写或无意义的词。任何需要解释才能懂的东西，都在阻碍沟通。我们不想让人为了正常工作还得先背一本术语表。

### update：增量 patch，改完立刻看到 diff

```bash
$ km update 1461835105 < /tmp/doc.html
```

update 不是整篇覆盖。它拿 AI 改过的新 HTML 和旧 HTML 做 **Myers diff**，算出节点级差异（增/删/改），再通过 read 时留下的映射定位回 nodeId，只 patch 变化的节点——AI 看不见 nodeId，却改得准，也不破坏未改动的部分。

改完自动回显 diff：

```Plain Text
- <h2>方案</h2>
+ <h2>优化方案（已上线）</h2>
- <p>接口响应超时</p>
+ <p>接口超时（已修复）</p>
```

这个 diff 不只是省一次「read 回看」——它是让 AI **不盲改**的反馈回路：写完立刻看到自己实际造成了什么变更，影响范围一目了然，错了当场能发现，而不是写完就走、把后果留给用户。

### template：学城元素的片段模板

学城有些元素不是标准 HTML（@人、折叠块、提示框），AI 不一定知道该怎么写。km template 输出这些元素的标准写法，和 km read 的输出完全一致——照着写进 update，diff 最干净：

```bash
# @人
$ km template mention
<km-mention uid="mockuser01">张三</km-mention>

# 折叠块
$ km template collapse
<km-collapse><summary>折叠标题</summary><div><p>折叠内容</p></div></km-collapse>

# 提示框（info/note/warning/tip）
$ km template note
<km-note type="info"><summary>提示标题</summary><div><p>提示内容</p></div></km-note>

# 任务列表
$ km template task-list
<ul><li><input type="checkbox" checked/>已完成</li><li><input type="checkbox"/>未完成</li></ul>

# 代码块
$ km template code
<pre language="Python"><code>print('hello')</code></pre>

# 表格
$ km template table
<table><tr><th>列A</th><th>列B</th></tr><tr><td>值1</td><td>值2</td></tr></table>
```

还有 image / link / blockquote / drawio / video / audio 等，运行 km template 看全部类型。

### 清晰报错，像编译器一样

不静默转换、不降级兜底。错了就拒绝，并告诉你错在哪、怎么改——像编译器报语法错误一样，每个报错都带修正方向：

```bash
# 传错格式：报错并给出正确命令
$ km update 1461835105 < /tmp/markdown.md
错误：内容不含 HTML 标签，疑似 markdown 格式。如需用 markdown 请用 km create 新建

# 图片缺必填字段：点明哪个节点缺什么
image 节点缺少必填字段 src（图片 URL 不能为空）

# 结构嵌套错：告诉正确嵌套方式
doc.content[2]: doc 节点的子节点 "list_item" 不合法。
（list_item/task_item 必须裹在 bullet_list/ordered_list/task_list 中）

# title 写错：区分 title 和 heading
doc 节点缺少 title 子节点（title 是文档标题，不是 heading）

# 媒体放错位置：给出结构提示
请修正 HTML 后重试（常见问题：video/audio 不能放在 <p> 里；<img> 必须有 src）
```

每个报错都是「是什么 + 为什么错 + 怎么改」三段式。这是前面「不写必读清单」的底气——AI 不需要预先背诵规则，真错了运行时告诉它怎么改，比预先背诵可靠得多。

### stdout 是数据，stderr 是建议

```bash
$ km read 1461835105 | km create   # stdout 管道，HTML 直接喂给下一步

$ km update 1461835105 < /tmp/doc.html
# stderr —— 提示与建议，不污染数据流
[提示] 删除 5 个节点，误操作可用 km restore 1461835105 42 还原

# stdout —— 纯 diff，可管道
- <h2>旧标题</h2>
+ <h2>新标题</h2>
```

stdout 永远是下一步能直接用的内容（HTML、diff、ID 列表）；成功提示、警告、进度全走 stderr。AI 拿 stdout 干活，人看 stderr 知道发生了什么。

### 一件事一种方式

```bash
# 列子文档
$ km ls 1461835105
1461835201	技术方案 v2
1461835202	压测报告

# 看元信息
$ km info 1461835105
标题：技术方案评审模板
创建者：zhangsan
创建时间：2025/3/15 14:30:00
浏览：1234 次 / 89 人  评论：12 条
```

命令顾名思义，不需要意图路由表。更多命令见 km --help。

### 本地图片自动上传，替换成 CDN 链接

写入时，HTML / Markdown 里的本地图片自动上传，src 换成学城 CDN：

```bash
$ km create < /tmp/doc.md          # markdown 里的本地图片会自动上传
$ km update 1461835105 < doc.html  # HTML 里的本地图片同样会自动上传
```

读取时，CDN 资源在 stderr 提示用 km download 取回，不污染 stdout：

```bash
$ km read 1461835105
# stdout —— 纯 HTML
<h1>架构说明</h1>
<img src="https://km.sankuai.com/api/file/cdn/.../arch.png"/>

# stderr —— 资源提示
[提示] 文档含 1 个可下载资源，用 km download <url> 下载：
```

本地能上、CDN 能下、远程 URL 不替你下载直接报错——每步都告诉你发生了什么。

## 写在后面

km-ops 的全部设计，收敛成三条思路：

**1. 人读起来轻松的东西，AI 读起来也轻松、做起来也好。**

不能许愿一份人读着都费劲的说明书，AI 还能执行得很好。最短的说明书就是例子——比起解释各种参数该怎么用，不如直接给可模仿的命令，AI 很擅长从例子里学，不擅长从参数表里背。官方技能的 SKILL.md 有 451 行、近一万字，人不会愿意先读一万字才能干事，AI 也不会；km-ops 的 SKILL.md 是 34 行全是例子的速查卡：km read 1461835105、km create < doc.md、km update 1461835105 < doc.html……看一眼就会，不用读说明。把说明书做到人愿意读，对 AI 自然也友好。

SKILL.md 只放最高频的「照猫画虎」例子，完整的参数说明都放 --help。因为 SKILL.md 是每次激活都要加载的高频上下文，只该装最常用的；--help 是低频按需查询，不进上下文、不耗 token。高频的短，低频的全，各归各位。

**2. 脚本能算的事，外包给脚本。**

怎么计算 diff、怎么 patch JSON——这些都是确定性计算，不该让 AI 在上下文里烧 token 推理。Myers diff 算节点差异、nodeId 映射定位回原节点，都在编译层完成。命令只认 ID，URL 提 ID 这种事 AI 自己就会，不用教；就算偷懒传了 URL，脚本报错踢回去就行。AI 只负责它擅长的：理解意图、生成内容、决定改哪里。机械的事交给脚本。

**3. 「不能做」的规则也外包给脚本，做错了再给修正方式。**

官方在创建前挂 6 条必读、在意图路由里写 6 条优先级——都是预防式的「先背下来别犯错」。但「不能做」的规则不该写进说明书让 AI 预先背，该外包给脚本运行时校验：做对了无事发生，做错了脚本不仅拒绝，还给出修正方向。就像编译器不只说「语法错误」，还会告诉你期望什么、怎么改。预防式说教是给人看的，运行时报错 + 修正提示才是给 AI 看的。

一句话：**把 AI 当成不怕麻烦、但怕不知道发生了什么的执行者。** 别替它操心、别给它噪声、出错时告诉它怎么改——它自己能把活干好。
