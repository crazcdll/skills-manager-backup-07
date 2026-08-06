---
name: trade-km-deep-mining
description: "学城文档深度挖掘工具。给定一个或多个学城(km.sankuai.com)文档链接，先校验起始文档权限（全部无权限则停止并提示申请，部分无权限则跳过继续），递归收集文档树的所有子文档（每个子文档都要查到，最多3层）和内容中引用的全部学城文档链接，生成树形目录 Markdown 报告（文件名默认取根文档标题），无权限文档尝试从引用它的链接文字回填标题，末尾附无权限文档表。当用户提到「学城文档挖掘」「km 文档树」「文档引用关系」「文档目录树」「km 文档分析」「整理文档结构」「学城文档整理」时激活。"
---

# 学城文档深度挖掘

给定一个或多个学城文档链接，递归探索文档树和全部引用关系，生成结构化的树形目录 Markdown 报告。

## 输入

用户提供：
- 一个或多个 `km.sankuai.com/collabpage/<id>` 或 `km.sankuai.com/page/<id>` 链接
- 输出目录（可选，默认使用当前工作目录）

## 核心规则

1. **起始文档权限前置校验（强制关卡）**：DFS 之前必须先校验用户提供的每个起始文档（depth=0）的权限。全部无权限 → 停止搜索，提示用户先申请权限；部分无权限 → 跳过这些起始文档，仅对有权限的继续搜索，并在报告中告知哪些起始文档未搜索
2. **子文档必须全部找到**：使用 DFS（深度优先搜索）递归获取子文档，每一层每一个文档都必须调用 `getChildContent`，最多 3 层（原文档为第 0 层，子文档第 1 层，孙文档第 2 层，曾孙文档第 3 层 → 到此为止）
3. **引用文档不能遗漏**：从文档正文内容中解析所有 `km.sankuai.com/(collabpage|page)/<digits>` 格式的链接，去重后**逐个**获取元信息
4. **引用文档不展开**：仅记录引用文档的标题和链接，不再递归获取其子文档或引用
5. **无权限不跳过记录**：遇到无权限文档仍记入树中，标题为"❌ 无权限"，并尝试从引用它的文档的链接文字中回填标题（显示为"❌ 无权限：<标题>"），汇总到最后表格并附链接
6. **输出文件命名**：默认使用根文档（起始文档）的标题作为输出文件名，不使用固定或随意命名

## � 反偷懒约束（必须遵守）

以下行为禁止，必须在每一步进行数量核验：

1. **不允许估计或猜测文档数量**——每个文档的 `getChildContent` 输出都会列出子文档数量和名称。必须逐一核对：输出的子文档列表是否完整返回，不能只看第一条就开始展开
2. **不允许跳过任何文档**——每获取一层子文档后，必须对**每个子文档**发起下一层的 `getChildContent` 调用（除非已达第3层或明确无权限），不能因为"看起来不多"就省略
3. **不允许用"大概/可能/应该"等词汇在报告中模糊描述**——如果某文档未获取元信息，标注为"⚠️ 获取失败"而非编造标题
4. **不允许提前终止批量任务**——在批量获取元信息时，必须遍历列表中**所有** ID，不能在中途停止或分批遗漏
5. **报告生成前必须做最终审计**——对比总预期文档数与实际已处理文档数，不一致必须追查原因

## 工具依赖

依赖 `oa-skills citadel` CLI，所有命令前需先确保 Node.js ≥ 18。

### 前置检查（每次 skill 激活时必须执行）

```bash
node -e "const cp=require('child_process'); const probe=process.platform==='win32'?'where oa-skills':'command -v oa-skills'; try{cp.execSync(probe,{stdio:'ignore',shell:true})}catch{cp.execSync('npm install -g @it/oa-skills --registry=http://r.npm.sankuai.com',{stdio:'inherit',shell:true})}"
```

然后所有 citadel 命令需要用以下前缀（Node.js 18）：

```bash
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm use 18 && oa-skills citadel <command>
```

## 工作流程

### Step 1: 解析输入 ✅ 入口

从用户提供的链接中提取 `contentId`：
- `km.sankuai.com/collabpage/1234567890` → `--contentId 1234567890`
- `km.sankuai.com/page/1234567890` → `--contentId 1234567890`
- 纯数字字符串 → 直接使用

确定输出目录路径（用户指定则使用，否则在当前工作目录下创建 `tree-directory/`）。

### Step 1.5: 起始文档权限预检 🚧 关卡（必须先执行，不可跳过）

在进行任何 DFS 递归之前，**必须先对用户提供的每一个起始文档（即最外层父文档，depth=0）逐个调用 `getDocumentMetaInfo` 校验权限**：

```bash
oa-skills citadel getDocumentMetaInfo --contentId <startId>
```

根据结果分为两类：
- **有权限**：记入 `validStarts` 列表，携带其标题
- **无权限**：记入 `invalidStarts` 列表，携带其链接（此时拿不到标题，标记为"❌ 无权限"）

判断规则：

1. **全部起始文档都无权限** → **立即停止**，不进行任何 DFS 递归或后续步骤。直接告知用户：
   > 你提供的 N 个起始文档均无访问权限，暂时无法挖掘。请先申请以下文档的权限后重试：
   > - [链接1]
   > - [链接2]
   >
   > （可选）是否需要我现在帮你批量申请权限？

   然后可参考 Step 5 的申请流程为这些起始文档发起权限申请，但不再继续挖掘。

2. **至少一个起始文档有权限** → 仅对 `validStarts` 中的文档继续执行 Step 2 的 DFS 递归；`invalidStarts` 中的文档**不参与搜索**，直接记入无权限汇总表（来源标注为"起始文档"），并在最终报告开头**额外提示**：
   > ⚠️ 以下 N 个起始文档无权限，未进行搜索：
   > - [标题/链接1]（无权限，未搜索）
   > - [标题/链接2]（无权限，未搜索）

**该步骤为强制关卡**：只要 `validStarts` 为空就必须终止流程，不能继续执行 Step 2 及之后步骤。

### Step 2: DFS 递归构建文档树 � 核心

使用 DFS（深度优先搜索），通过**递归函数**逐层处理。伪代码：

```
function processDocument(docId, depth, parentRefs, allVisited, allRefs):
    === 数量检查点 1：进入时计数 ===
    allVisited.add(docId)

    # 获取元信息
    meta = getDocumentMetaInfo(docId)
    title = meta.title or "❌ 无权限"  # 无权限时标题留待 Step 3.3 统一从 refAnchorTitles 回填

    if meta.failed:
        recordNoPermission(docId, parentRefs)
        return {id: docId, title, children: [], refs: []}

    # 获取内容并提取引用链接
    content = getSimpleMarkdown(docId)
    refIds = extractKmLinks(content)   # 正则匹配所有 km.sankuai.com/(collabpage|page)/(\d+)
    newRefs = refIds - allRefs         # 去重：排除已处理的引用 ID
    allRefs.addAll(newRefs)

    # 记录被谁引用
    for refId in newRefs:
        recordReference(docId, refId)

    # 核心：决定是否继续递归子文档
    if depth >= 3:                     # 第3层是最后层，不再获取子文档
        return {id: docId, title, children: [], refs: newRefs}

    # === 数量检查点 2：子文档必须全部获取 ===
    childList = getChildContent(docId)  # 返回子文档数组（可能为空）
    expectedChildCount = len(childList.children)

    children = []
    if expectedChildCount > 0:
        childIds = [c.contentId for c in childList.children]
        recordChildren(docId, childIds)  # 记录预期子文档列表

        for childId in childIds:
            if childId not in allVisited:  # 防止循环引用
                childResult = processDocument(childId, depth+1, parentRefs + [docId], allVisited, allRefs)
                children.append(childResult)

    # === 数量检查点 3：验证子文档是否全部展开 ===
    actualChildren = [c.id for c in children]
    missing = set(childIds) - set(actualChildren) - allVisited
    if missing:
        log_error(f"文档 {docId} 的子文档未完全展开: {missing}")
        # 重试缺失的子文档
        for missingId in missing:
            retryResult = processDocument(missingId, depth+1, parentRefs + [docId], allVisited, allRefs)
            children.append(retryResult)

    return {id: docId, title, children, refs: newRefs}
```

#### 2.1 获取文档元信息

对每个文档 ID 调用：
```bash
oa-skills citadel getDocumentMetaInfo --contentId <id>
```
**必须核对**：输出的标题、ID 是否与入参一致。失败（含"无权限"）时：
- 记录到 no_permission 列表（附父文档链路和 km 链接），并标记 `titleSource: unknown`（待后续从引用处回填）
- 树中显示为 `❌ 无权限 (<id>)`（若后续从引用处补到了标题，改为 `❌ 无权限：<推测标题> (<id>)`）
- 继续下一步该文档的引用提取（部分情况下无权限文档仍可能有内容输出），如果内容也无权限则跳过

#### 2.2 获取直接子文档

对每个文档 ID 调用：
```bash
oa-skills citadel getChildContent --contentId <id>
```
**必须核对**：
- 输出中"文档 X 的子文档列表（共 N 个）"的 N 是否与下面列出的子文档数量一致
- `childCount` 字段是否与列表长度匹配（如果文档中显示了 childCount）
- 逐个核对每个子文档的 contentId 和 title

#### 2.3 获取文档内容（提取引用链接）

对每个文档 ID 调用：
```bash
oa-skills citadel getSimpleMarkdown --contentId <id>
```
并将内容保存到临时文件：
```bash
oa-skills citadel getSimpleMarkdown --contentId <id> > /tmp/km_deep_<id>.md 2>&1
```

然后提取引用 ID（macOS 兼容，不使用 grep -P）：
```bash
cat /tmp/km_deep_<id>.md | node -e "const fs=require('fs');let d=fs.readFileSync(0,'utf8');const m=[...d.matchAll(/km\.sankuai\.com\/(collabpage|page)\/(\d+)/g)];const ids=[...new Set(m.map(x=>x[2]))];console.log(ids.join('\n'));"
```
每次提取后立即核对输出的 ID 数量与控制在 allRefs 集合中的数量（防止遗漏）。

**同时提取 Markdown 链接锚文本**（用于后续给无权限文档回填标题）：
```bash
cat /tmp/km_deep_<id>.md | node -e "const fs=require('fs');let d=fs.readFileSync(0,'utf8');const m=[...d.matchAll(/\[([^\]]+)\]\(https?:\/\/km\.sankuai\.com\/(?:collabpage|page)\/(\d+)[^)]*\)/g)];for(const x of m){console.log(x[2]+'\t'+x[1]);}"
```
将输出的 `<id>\t<锚文本>` 存入全局映射 `refAnchorTitles`（id → 首次出现的锚文本，同一 id 已存在则不覆盖）。这是无权限文档标题的候选来源，**引用处的链接文字通常就是原文档标题**。

#### 2.4 递归深度控制

| 层数 | 深度参数 | 操作 |
|------|----------|------|
| 原文档 | depth=0 | 获取元信息 + 内容 + 引用 + 子文档 |
| 子文档 | depth=1 | 获取元信息 + 内容 + 引用 + 子文档 |
| 孙文档 | depth=2 | 获取元信息 + 内容 + 引用 + 子文档 |
| 曾孙文档 | depth=3 | 获取元信息 + 内容 + 引用，**不再调用 getChildContent** |

**循环引用防护**：使用 `allVisited` 集合记录已处理的文档 ID，遇到重复 ID 时跳过（在树中标注 `[已展开]`）。

### Step 3: 收集引用文档元信息 �

递归完成后，`allRefs` 集合包含所有文档内容中引用的唯一文档 ID。

#### 3.1 去重

```python
# 减去已在文档树中的 ID
refs_to_fetch = allRefs - allVisited
```

#### 3.2 批量获取元信息（每个都必须执行）

**必须逐一调用**，不允许跳过。每个调用：
```bash
oa-skills citadel getDocumentMetaInfo --contentId <id>
```

**数量核验**：获取完成后，对比成功获得标题的 ID 数与 `refs_to_fetch` 数量，差值 = 无权限文档数。每个失败的都必须记录。

#### 3.3 为无权限文档回填标题（必须执行）

对 `no_permission` 列表中**每一个**标题未知（`❌ 无权限`）的文档 ID，查找 `refAnchorTitles` 映射：

```python
for doc in no_permission:
    if doc.id in refAnchorTitles:
        doc.guessedTitle = refAnchorTitles[doc.id]
        doc.titleSource = "从引用处的链接文字获取"
    else:
        doc.guessedTitle = None
        doc.titleSource = "无法获取（引用处也无链接文字或未被任何文档引用）"
```

**说明**：无权限文档虽然无法直接调用 `getDocumentMetaInfo` 拿到标题，但只要它被其他文档以 Markdown 链接形式引用过（如 `[XX方案设计](https://km.sankuai.com/collabpage/12345)`），链接文字 `XX方案设计` 通常就是该文档的真实标题，可作为可靠的标题来源。

回填后：
- 树中该节点显示从 `❌ 无权限 (id)` 更新为 `❌ 无权限：<guessedTitle> (id)`（若拿到了推测标题）
- 无权限汇总表新增"推测标题"列（详见 4.3）

### Step 4: 生成输出 📄

在输出目录下直接创建 Markdown 文件（不创建子目录），文档命名规范：
- **默认使用文档名**作为文件名（即根文档的标题）
  - 单个起始文档：直接使用该文档的标题
  - 多个起始文档（`validStarts` 有多个）：使用第一个有权限的起始文档的标题；如需体现全部根文档，可在标题后追加 `等N个文档`（如 `订单流程说明等3个文档.md`）
- 去除影响文件系统的字符（保留中文、字母、数字、空格、`-`、`_`）
- 若标题含 emoji，保留原样（macOS 支持），若有问题则去除 emoji
- 若文档名为空或获取失败，使用 `km文档树形目录_<主contentId>` 兜底
- 扩展名 `.md`

#### 4.1 输出文件结构

```markdown
# 文档树形目录

> 根文档：[标题](链接) (ID: xxx)
> 所有者：xxx | 最后编辑：xxx | 更新时间：YYYY/MM/DD
>
> �️ 共扫描 N 个文档，树深度 3 层，发现 M 个引用文档，其中 K 个无权限
>
> 说明：树中标注 📎 的为文档内容引用的文档（引用文档不继续展开）
> 标注 [已展开] 的为循环引用（之前已在树中出现过）
> 标注 ❌ 无权限：<标题> 的为无权限文档，标题来自引用它的文档中的链接文字（非官方标题，仅供参考）

> ⚠️（若存在起始文档无权限）以下 N 个起始文档无权限，未进行搜索：
> - [标题/链接1]（无权限，未搜索）
> - [标题/链接2]（无权限，未搜索）

---

```
标题 (id) [root]
├── 子文档1 (id)
│   ├── 孙文档1 (id)
│   │   ├── 曾文档1 (id)
│   │   │   └── � 引用文档标题 (id)
│   │   └── 📎 引用文档标题 (id)
│   ├── 孙文档2 (id)
│   └── 📎 引用文档标题 (id)
├── 子文档2 (id)
│   └── ❌ 无权限：推测标题 (id)
└── 📎 引用文档标题 (id)
```

---

## 统计汇总

| 维度 | 数量 |
|------|------|
| 根文档 | N |
| 子文档（第1层） | N |
| 孙文档（第2层） | N |
| 曾孙文档（第3层） | N |
| **文档树总计** | **N** |
| 引用文档（去重） | N |
| 其中：已在树中 | N |
| 其中：无权限 | N |

## 无权限文档汇总

共 **N** 个文档无访问权限：

| 文档 ID | 链接 | 推测标题 | 标题来源 | 来源层级 | 备注 |
|---------|------|---------|---------|---------|------|
| xxx | [链接](https://km.sankuai.com/collabpage/xxx) | XX方案设计 | 从引用处的链接文字获取 | 文档树第N层 | 获取元信息失败 |
| yyy | [链接](https://km.sankuai.com/collabpage/yyy) | — | 无法获取 | zzz文档内容引用 | 获取元信息失败 |
| zzz | [链接](https://km.sankuai.com/collabpage/zzz) | — | 无法获取 | 起始文档 | 未进行搜索 |

```

#### 4.2 树形结构绘制规则

- ASCII 树：`├──` / `└──` / `│` / `   `
- 节点格式：`文档标题 (contentId)`
- 根节点：标注 `[root]`
- 子文档节点：按 getChildContent 返回顺序排列
- 引用文档：统一放在其父节点所有子文档之后，前缀 `📎 `
- 无权限文档：若已通过引用处回填到标题，显示为 `❌ 无权限：<推测标题> (contentId)`；否则显示为 `❌ 无权限 (contentId)`
- 循环引用：显示为 `标题 (contentId) [已展开]`，不再展开其子节点
- 标题过长：截断至 40 字符 + `...`

#### 4.3 无权限文档汇总表

- 包含所有获取失败的文档 ID，含起始文档中无权限、未搜索的文档
- 提供可点击的 km.sankuai.com 链接
- **推测标题列**：查 `refAnchorTitles` 映射回填，取不到则显示 `—`
- **标题来源列**：`从引用处的链接文字获取` 或 `无法获取（引用处也无链接文字或未被任何文档引用）`
- 标注被哪个文档引用或所在层，起始文档无权限的标注为"起始文档"，备注为"未进行搜索"
- 按文档 ID 排序
- 区分"层树中无权限""引用文档无权限""起始文档无权限"三类

## � 最终审计步骤（报告写入前必须执行）

**报告写入文件之前**，逐项核对以下 checklist：

1. **子文档完整性**：遍历树中每个节点（深度 0-2），确认其 children 与该节点 `getChildContent` 返回的列表一一对应。如有缺失，必须补全后再生成报告。
2. **引用文档完整性**：确认所有已获取内容的文档都执行了引用链接提取，且提取出的 ID 都已尝试获取元信息。如有遗漏，补充执行。
3. **数量一致性**：
   - 报告中"文档树总计" = DFS 访问的节点数 + 根文档数
   - 报告中"引用文档（去重）" = allRefs 集合大小
   - 报告树中每个节点的子节点数 = 该节点的 getChildContent 返回数
4. **链接有效性**：确认无权限表格中的所有链接均为 `https://km.sankuai.com/collabpage/<数字ID>` 格式。
5. **格式正确性**：确认树缩进无错位、无权限表 ID 升序排列。
6. **起始文档权限关卡已执行**：确认 Step 1.5 已对所有起始文档完成权限校验；若存在无权限起始文档，确认报告开头有对应提示且这些文档未被搜索（不应出现子文档或引用记录）。
7. **无权限标题回填完整**：确认 `no_permission` 列表中每个文档都已尝试通过 `refAnchorTitles` 回填标题，无权限汇总表"推测标题"与"标题来源"两列均已填写（取不到时为 `—` / `无法获取`），不能留空。

**任何一项不通过，必须修复后再生成报告。不允许带着已知的数量不一致或遗漏写入输出文件。**

## 执行建议

1. **并行加速无冲突的步骤**：同一层的多个文档的元信息获取、内容获取可以放在同一 function_calls block 中并行执行
2. **批量限制**：并行获取时，每批不超过 10 个。处理完一批后再启动下一批，防止遗漏（每批都做计数核对）
3. **即时去重**：每提取一批引用 ID 后，立即更新 allRefs 集合并输出新增数量，便于追踪
4. **保存中间产物**：每个文档的内容保存到 `/tmp/km_deep_<id>.md`，便于后续重新提取引用
5. **引用链接多格式兼容**：除了 `km.sankuai.com/collabpage/<id>` 和 `km.sankuai.com/page/<id>` 之外，注意学城文档中可能使用缩短格式或带锚点（`#xxx`）的链接，提取时用正则 `\d+` 匹配数字部分即可
6. **遇到 API 错误重试**：单次 API 失败后等待 2 秒重试一次，仍失败则记录并继续

### Step 5: 批量申请权限

报告生成完毕后（或 Step 1.5 因起始文档全部无权限而提前终止时），执行以下流程：

**前置条件**：`no_permission` 列表非空（含起始文档无权限、文档树无权限、引用文档无权限三类；如有 0 个无权限文档则跳过此步骤）。

**说明**：若 Step 1.5 判定全部起始文档无权限而提前终止，此时 `no_permission` 列表只包含这些起始文档，仍可执行本步骤为其申请权限；申请完成后建议用户重新发起一次挖掘请求。

#### 5.1 询问用户

先向用户展示无权限文档数量和示例标题，然后询问：

> 发现 N 个无权限文档，是否需要我帮你批量申请权限？
>
> 将使用浏览器自动化填写"仅浏览"权限申请，申请理由统一为："前端开发工作需要查看文档，了解相关业务"

使用 `AskQuestion` 工具，提供选项："是，批量申请" / "不用，跳过"。

也可支持用户按 Ctrl+C 中断此步骤。

#### 5.2 为用户展示申请预览

若用户选择"是"，展示一个表格，列出即将申请的所有文档 ID 和链接，并提示：

> 将依次打开每个文档的权限申请页面并提交申请，每个申请需等待页面加载。过程中可随时中断。

#### 5.3 逐文档执行权限申请

对 `no_permission` 列表中的每个文档 ID，按以下流程执行：

```
① 导航到文档页面：
   catdesk browser-action '{"action":"navigate","url":"https://km.sankuai.com/collabpage/<id>"}'
   等待 2-3 秒加载

② 检查页面状态（评估页面内容）：
   catdesk browser-action '{"action":"evaluate","script":"(function(){return document.body.innerText.substring(0,800);})()"}'

   根据页面内容判断：
   a. 包含"已申请，等待审批" → 该文档已申请过，跳到下一个
   b. 包含"申请权限"表单 → 继续填写提交
   c. 包含"无权限"但无表单 → 可能是页面加载不完整，等待 2 秒后重试
   d. 正常文档内容（非无权限） → 该文档可能已有权限，从 no_permission 列表移除

③ 填写并提交权限申请：
   catdesk browser-action '{"action":"evaluate","script":"(function(){
     var radios = document.querySelectorAll(\"input[type=radio]\");
     if(radios.length > 0){
       radios[0].checked = true;
       radios[0].dispatchEvent(new Event(\"change\", {bubbles: true}));
     }
     var ta = document.querySelector(\"textarea\");
     if(ta){
       ta.value = \"前端开发工作需要查看文档，了解相关业务\";
       ta.dispatchEvent(new Event(\"change\", {bubbles: true}));
     }
     var btns = document.querySelectorAll(\"button\");
     for(var i=0; i<btns.length; i++){
       if(btns[i].innerText.includes(\"申请权限\")){
         btns[i].click();
         return \"submitted\";
       }
     }
     return \"no form\";
   })()"}'

④ 等待 2 秒后检查结果：
   catdesk browser-action '{"action":"evaluate","script":"(function(){return document.body.innerText.substring(0,500);})()"}'
   确认包含"已申请，等待审批"字样，表示申请成功

⑤ 如果页面跳转了或出现其他异常，记录失败，继续处理下一个

#### 5.4 汇总申请结果

处理完所有文档后，向用户展示汇总表：

| # | 文档 ID | 结果 |
|---|---------|------|
| 1 | 1228667120 | 已申请，等待审批 |
| 2 | 2178020974 | 已申请，等待审批 |
| 3 | 2353647004 | 之前已提交 |
| 4 | xxx | 失败：原因 |

#### 5.5 失败处理

- **页面加载超时**：重试一次（间隔 3 秒），仍失败则跳过
- **表单元素找不到**：跳过该文档，提示用户手动处理
- **用户中断（Ctrl+C）**：停止当前申请，输出已完成的结果

## 验证清单

完成后逐项确认：

1. ✅ 输出目录存在且包含 md 文件，文件名为根文档标题（默认行为，非固定文件名）
2. ✅ 起始文档权限前置校验已执行：全部无权限已停止并提示用户；部分无权限已在报告中告知哪些未搜索
3. ✅ 树形结构缩进正确（子节点比父节点多一层缩进）
4. ✅ 每层子文档数与该层文档的 getChildContent 返回数量一致
5. ✅ 文档树中所有呈现的 📎 引用文档都在 allRefs 集合中有对应元信息获取记录
6. ✅ 无权限文档均尝试从 `refAnchorTitles` 回填标题，汇总表包含推测标题与标题来源两列
7. ✅ 无权限文档表格包含可点击链接且按 ID 排序，含起始文档无权限项
8. ✅ 统计数据（树总计、引用总计、无权限数）与实际处理结果一致
9. ✅ 审计报告中的所有项目已通过
10. ✅ 权限申请步骤已执行并输出汇总

## 示例

### 示例 1：单个起始文档，有权限

**输入**：帮我挖掘 https://km.sankuai.com/collabpage/abc123 的文档结构，输出到 ./output

**执行流程**：
1. 提取 contentId = abc123
2. **Step 1.5 权限预检**：调用 getDocumentMetaInfo(abc123) → 有权限，标题 "示例文档" → validStarts = [abc123]，继续执行
3. 调用 DFS(abc123, depth=0):
   - 获取元信息 → 标题 "示例文档"
   - 获取内容并保存 → 提取引用 ID 及锚文本: [(def, "XX方案"), (ghi, "YY设计")]，写入 refAnchorTitles
   - 获取子文档 → [child1, child2]
   - 对 child1 递归 DFS(depth=1): 获取元信息、内容、引用、子文档
   - 对 child2 递归 DFS(depth=1): 同上
   - 对每个孙文档递归 DFS(depth=2): 获取元信息、内容、引用、子文档
   - 对每个曾孙文档递归 DFS(depth=3): 获取元信息、内容、引用，**不获取子文档**
4. 所有递归完成后，allRefs = {def, ghi, ...}，allVisited = {abc123, child1, child2, ...}
5. 对 refs_to_fetch = allRefs - allVisited 中的每个 ID 获取元信息，假设 ghi 无权限
6. 为无权限的 ghi 查 refAnchorTitles → 命中 "YY设计" → 树中显示为 `❌ 无权限：YY设计 (ghi)`
7. 执行最终审计，核对数量一致性
8. 写入 ./output/示例文档.md（文件名取自根文档标题）

### 示例 2：多个起始文档，部分无权限

**输入**：帮我挖掘 https://km.sankuai.com/collabpage/aaa 和 https://km.sankuai.com/collabpage/bbb 的文档结构

**执行流程**：
1. **Step 1.5 权限预检**：分别调用 getDocumentMetaInfo(aaa) 、getDocumentMetaInfo(bbb)
   - aaa → 有权限，标题 "A文档" → 加入 validStarts
   - bbb → 无权限 → 加入 invalidStarts
2. 判断：validStarts 非空 → 仅对 aaa 继续 DFS 递归，bbb 不参与搜索，直接记入 no_permission（来源=起始文档）
3. 完成 aaa 的完整 DFS 与引用收集
4. 生成报告，开头额外提示：“⚠️ 以下 1 个起始文档无权限，未进行搜索：[bbb 链接]”
5. 无权限汇总表中增加一行：`bbb | 链接 | — | 无法获取 | 起始文档 | 未进行搜索`
6. 写入 ./output/A文档.md

### 示例 3：全部起始文档无权限

**输入**：帮我挖掘 https://km.sankuai.com/collabpage/ccc 的文档结构

**执行流程**：
1. **Step 1.5 权限预检**：getDocumentMetaInfo(ccc) → 无权限 → invalidStarts = [ccc]，validStarts 为空
2. **立即停止**，不执行 Step 2 及之后任何步骤，不生成 md 报告
3. 回复用户：“你提供的起始文档均无访问权限，暂时无法挖掘。请先申请：[ccc 链接]”，并询问是否需要帮忙批量申请权限
4. 若用户同意，按 Step 5 流程为 ccc 发起权限申请
