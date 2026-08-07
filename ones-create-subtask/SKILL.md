---
name: ones-create-subtask
description: 在 ONES 平台上为需求创建子任务（开发任务）并设置标签。当用户要求在 ONES 上创建子任务、新建开发任务、为需求拆分任务、批量创建周任务时使用。触发词：创建子任务、新建任务、ONES 任务、拆分任务、周任务、开发任务。支持从学城排期文档自动解析并批量创建；解析后会校验单元格 colspan 与显式 Npd 是否一致，不一致时需确认「继续」或「取消」；创建前还会按人汇总 PD，若有人超过 5pd 则再次确认。自动继承需求标签，自动检测已存在任务避免重复创建，输出含状态的汇总表格和人力投入统计。

metadata:
  skillhub.creator: "wangshicheng05"
  skillhub.updater: "zhangce07"
  skillhub.version: "V8"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "2010"
  skillhub.high_sensitive: "false"
---

# ONES 创建子任务（排期文档驱动）

输入一个学城排期文档 URL，自动解析文档中排期表格的需求链接、开发人员、工作天数和日期，然后通过 ONES API 为每个需求批量创建子任务。支持已存在任务复用、标签继承、人力汇总统计，并将结果表格同步回用户提供的学城文档。

## 使用说明

只要给一个学城链接就行，其他无需补充。

例如  `/ones-create-subtask https://km.sankuai.com/collabpage/2754246640`

---

## 核心原则

1. **只使用用户提供的文档**：所有操作（读取排期数据、写入结果）都只针对用户明确提供的文档 URL，绝不自动跳转到其他文档（如侧边栏链接、子文档等）。如果在用户文档中找不到排期表格，应询问用户而不是自行寻找。
2. **不修改原文档已有内容**：只在指定区域插入/替换结果，不改动排期表格、注意事项等原有内容。
3. **模版文件保护**：需求排期模版 `https://km.sankuai.com/collabpage/2750103195` 和需求任务输出模版 `https://km.sankuai.com/collabpage/2750115624` **绝对不允许修改**。
4. **issueId 不得替换**：排期文档里解析出的 `issueId` 就是任务挂载目标，创建时 `parentId = t.issueId`，查重时也查这个 `issueId` 下的子任务。**绝对不能**在查询需求详情后把 `issueId` 替换成父需求 ID。

---

## 前置检查

### 检查 1：默认自动执行（无需询问）

当用户提供了学城排期文档 URL（形如 `https://km.sankuai.com/collabpage/xxxxx` 或 `https://km.sankuai.com/page/xxxxx`）时，**默认直接开始执行**，不再询问"要做什么"。执行流程为：

```
解析文档 → colspan/Npd 一致性检测（不一致则等待确认）→ 展示结果 → 查询 ONES → 迭代一致性检测（仅提示不阻塞）→ 准备任务列表 → PD 检测（有人 >5pd 则等待确认）→ 分批创建 → 写回文档 → 完成报告
```

> ⚠️ 如果用户明确说"确认后再继续"或"先给我看看"，则在解析完成后暂停等待确认。

**如果用户没有提供文档 URL**，询问用户提供文档链接，并可附上模板参考：

> 请提供你的排期文档链接（格式如 `https://km.sankuai.com/collabpage/xxxxx`）。
>
> 如果还没有排期文档，可参考模板 [排期表模板](https://km.sankuai.com/collabpage/2750103195) 复制一份，填写时注意：
> 1. **表格表头**：填写每日日期，如「周一 3.16」「周二 3.17」...
> 2. **人员列**：使用 `@姓名` mention 开发人员
> 3. **需求单元格**：填写 ONES 需求链接，colspan 表示工作天数
> 4. **分段排期**：同一需求可拆成多个单元格，系统自动合并天数

### 检查 2：是否为模版地址

如果用户提供的 URL 包含 `2750103195` 或 `2750115624`，提醒用户这是模版文件，请先复制一份再使用。

### 检查 3：子需求迭代与本周迭代一致性（第二步查询后自动执行）

第二步查询需求详情后，从 `issueMap` 中提取每个需求的 `iterationId`，与从迭代名称解析出的**本周 iterationId**（`weekIterationId`，第三步计算）对比。若存在需求迭代 ≠ 本周迭代的情况，在展示解析结果时列出不一致的需求，提醒用户这些需求尚未移到本周迭代。

此检查**不阻塞执行**（不需要等待用户确认），仅作为信息提示。不一致时，去重匹配逻辑（第四步）会自动使用**本周的 iterationId** 而非需求自身的 iterationId，避免误匹配到上周的旧任务。

---

## 标准排期模版结构说明

标准排期模版（参考 `https://km.sankuai.com/collabpage/2750731306`）的文档结构如下：

```
[标题] W11酒店交易排期
[注意事项] 排期表学诚模版注意事项...
[标题] 排期需求输入          ← 排期表格所在 section
[表格] 序号 | 人员 | 周一 | 周二 | 周三 | 周四 | 周五
[标题] 排期任务输出          ← 结果写入此标题之后
```

**表格结构特点：**
- 第 0 列：序号（空或数字）
- 第 1 列：开发人员（`@mention`）
- 第 2-6 列：周一到周五（表头只有「周一」「周二」等，**无日期数字**，`hasHeaderDates === false`）
- 单元格内可能有多个 ONES 需求链接，每个需求后跟 `Npd` 标注
- 日期需从迭代名称（如 `住宿-2026W11（0316-0322)`）中解析起始日期后按工作日偏移推算

---

## 完整执行流程

> 整个流程共 **3 次页面导航**（学城文档 → ONES → 学城文档）。
>
> **关键约束**：
> - 第二步 API 查询通过浏览器 evaluate 执行（需要 SSO Cookie），**不得用 Node.js / curl 直接请求**，Cookie 在 Node.js 环境中会失效（返回 401）。
> - 第四步批量创建**必须分批执行**，每批 ≤ 4 个任务，通过「写文件 + python3 传参」方式传入脚本，避免命令行转义问题和浏览器 evaluate 超时（20 个任务一次性执行会超时）。
> - **第一步解析完成后、第二步 navigate ONES 之前**：若返回的 `colspanDurationMismatches` **非空**（单元格 `colspan` 与显式 `Npd` 数值不一致），须向用户列出条目并等待「继续」或「取消」；「取消」终止全流程。「继续」后方可进入第二步。
> - **第三步完成后、第四步创建前**必须做每人 PD 汇总检测：若存在单人汇总 **大于 5pd**（数值上 `> 5`，等于 5 不触发），须向用户列出名单并等待回复「继续」或「取消」；仅当用户回复「继续」或无人超限时才可进入第四步。用户回复「取消」则终止全流程（不得执行创建与写回）。
> - 第一步解析完成后**默认自动继续执行**，向用户展示解析结果的同时继续后续流程；**但若存在 colspan/Npd 不一致，必须先完成该项确认**（见上条）。如果用户明确说"确认后再继续"则暂停等待确认。

### 第一步：打开排期文档，一次性完成预检 + 解析（默认自动继续）

使用 `browser-action` navigate 到用户提供的学城排期文档 URL：

```bash
~/.catpaw/bin/catdesk browser-action '{"action":"navigate","url":"https://km.sankuai.com/collabpage/xxxxx"}'
```

**用一个脚本同时完成**：预检（是否有 ONES 链接）+ 定位排期表格 + 提取所有任务数据 + 获取文档插入位置。

```javascript
(async () => {
  // ── 1. 预检：确认有 ONES 链接 ──────────────────────────────────────
  const tables = document.querySelectorAll('table');
  let scheduleTableIdx = -1;
  let maxOnesCount = 0;

  for (let t = 0; t < tables.length; t++) {
    const cnt = tables[t].querySelectorAll('span[data-type="ones"]').length;
    if (cnt > maxOnesCount) { maxOnesCount = cnt; scheduleTableIdx = t; }
  }
  if (maxOnesCount === 0) {
    return JSON.stringify({ hasOnesLinks: false });
  }

  // ── 2. 定位排期表格（ONES 链接最多的表格） ──────────────────────────
  const table = tables[scheduleTableIdx];
  const rows  = table.querySelectorAll('tr');

  // ── 3. 解析表头日期 ────────────────────────────────────────────────
  const headerCells = rows[0].querySelectorAll('th, td');
  const dates = Array.from(headerCells).map(c => c.textContent.trim());
  const hasHeaderDates = dates.some(d => /周[一二三四五]/.test(d) && /\d+\.\d+/.test(d));

  // ── 4. 逐行提取任务（支持 ct-mention / mention 两种 DOM 结构） ─────
  const rawTasks = [];
  const nonOnesItems = []; // 有 pd 标注但无 ONES 链接的单元格（如学城链接、纯文字等）
  for (let r = 1; r < rows.length; r++) {
    const cells = rows[r].querySelectorAll('td, th');
    if (cells.length < 2) continue;

    // 人员列：第 1 列（index 1），优先 <a data-type="ct-mention">，兼容 <span data-type="mention">
    const personCell  = cells[1];
    const mentionA    = personCell.querySelector('a[data-type="ct-mention"]');
    const mentionSpan = personCell.querySelector('span[data-type="mention"]');
    const mentionEl   = mentionA || mentionSpan;
    if (!mentionEl) continue;

    const personName  = (mentionA
      ? (mentionA.querySelector('.pk-mention')?.textContent || mentionA.textContent)
      : mentionSpan.getAttribute('data-name') || mentionSpan.textContent
    ).replace(/^@/, '').trim();
    const personUid   = mentionEl.getAttribute('data-uid') || mentionEl.getAttribute('data-mis-id') || '';
    const personEmpId = mentionEl.getAttribute('data-emp-id') || '';

    // 需求列：从第 2 列（index 2）开始
    let colOffset = 2;
    for (let c = 2; c < cells.length; c++) {
      const cell      = cells[c];
      const colspan   = parseInt(cell.getAttribute('colspan') || '1');
      const onesSpans = cell.querySelectorAll('span[data-type="ones"]');

      if (onesSpans.length === 0) {
        // 检测：有 Npd 标注但没有 ONES 链接，说明可能是非 ONES 链接的排期项（如学城文档链接、纯文字），需提示用户
        const cellText = cell.textContent.trim();
        const pdMatch  = cellText.match(/(\d+(?:\.\d+)?)pd/i);
        if (pdMatch && cellText.length > 0) {
          nonOnesItems.push({
            person: personName,
            rowIndex: r,
            colIndex: colOffset,
            colspan,
            cellText: cellText.substring(0, 80),
            duration: parseFloat(pdMatch[1])
          });
        }
        colOffset += colspan;
        continue;
      }

      if (onesSpans.length === 1) {
        const href     = onesSpans[0].getAttribute('data-href') || '';
        const cellText = cell.textContent.trim();
        const pdMatch  = cellText.match(/(\d+(?:\.\d+)?)pd/i);
        const duration = pdMatch ? parseFloat(pdMatch[1]) : colspan;
        // explicit：单元格内有 Npd 文本，可与 colspan 做一致性校验；colspan：无 Npd 时用列宽代待人天，不参与校验
        const pdSource = pdMatch ? 'explicit' : 'colspan';
        rawTasks.push({ person: personName, uid: personUid, empId: personEmpId, href, duration, colspan, colIndex: colOffset, rowIndex: r, pdSource });
      } else {
        // 多需求单元格：每个需求各自有 Npd 标注；按段占位，不参与「单格 colspan vs 单段 Npd」校验
        let subColOffset = colOffset;
        for (const onesSpan of onesSpans) {
          const href          = onesSpan.getAttribute('data-href') || '';
          const container     = onesSpan.closest('p') || onesSpan.parentElement;
          const containerText = container ? container.textContent : '';
          const pdMatch       = containerText.match(/(\d+(?:\.\d+)?)pd/i);
          const thisPd        = pdMatch ? parseFloat(pdMatch[1]) : 1;
          rawTasks.push({ person: personName, uid: personUid, empId: personEmpId, href, duration: thisPd, colspan: thisPd, colIndex: subColOffset, rowIndex: r, pdSource: 'multi' });
          subColOffset += thisPd;
        }
      }
      colOffset += colspan;
    }
  }

  // ── 4b. colspan 与显式 Npd 一致性（仅单需求且标注 Npd 时比较）─────────
  const EPS = 1e-6;
  const colspanDurationMismatches = rawTasks
    .filter(t => t.pdSource === 'explicit' && Math.abs(t.duration - t.colspan) > EPS)
    .map(t => {
      const m = t.href.match(/\/workItem\/requirement\/detail\/(\d+)/);
      return {
        person: t.person,
        uid: t.uid,
        rowIndex: t.rowIndex,
        href: t.href,
        issueId: m ? parseInt(m[1], 10) : null,
        colspan: t.colspan,
        duration: t.duration
      };
    });

  // ── 5. 同需求合并（同人 + 同 href → 累加天数，取最早/最晚列） ──────
  const merged = {};
  for (const t of rawTasks) {
    const k = `${t.uid}||${t.href}`;
    if (!merged[k]) {
      merged[k] = { ...t, startDateCol: t.colIndex, endDateCol: t.colIndex + t.colspan - 1 };
    } else {
      merged[k].duration    += t.duration;
      merged[k].startDateCol = Math.min(merged[k].startDateCol, t.colIndex);
      merged[k].endDateCol   = Math.max(merged[k].endDateCol, t.colIndex + t.colspan - 1);
    }
  }
  const tasks = Object.values(merged);

  // ── 6. 解析日期（有表头日期时直接读取） ────────────────────────────
  const parseDate = str => { const m = str.match(/(\d+)\.(\d+)/); return m ? { month: parseInt(m[1]), day: parseInt(m[2]) } : null; };
  for (const t of tasks) {
    if (hasHeaderDates) {
      t.startDate = parseDate(dates[t.startDateCol] || '');
      t.endDate   = parseDate(dates[t.endDateCol]   || '') || t.startDate;
    }
    // 无日期时由第三步从迭代名称推算
  }

  // ── 7. 提取 ONES projectId / issueId（直接用排期文档里的链接，不做任何替换） ──
  for (const t of tasks) {
    const m = t.href.match(/\/product\/(\d+)\/workItem\/requirement\/detail\/(\d+)/);
    if (m) { t.projectId = parseInt(m[1]); t.issueId = parseInt(m[2]); }
  }

  // ── 8. 获取文档插入位置 ────────────────────────────────────────────
  // 优先级：「排期任务输出」标题之后 > footnote_list 之前 > 文档末尾
  let insertPos = null, anchorEnd = null;
  if (window.editorInst?.manager?.editorView) {
    const doc      = window.editorInst.manager.editorView.state.doc;
    const topNodes = [];
    doc.forEach((node, offset) => {
      const text = node.textContent || '';
      if (anchorEnd === null && (text.includes('排期任务输出') || text.includes('以下是输出任务创建结果输出'))) {
        anchorEnd = offset + node.nodeSize;
      }
      topNodes.push({ type: node.type.name, offset, size: node.nodeSize });
    });
    if (anchorEnd === null) {
      const fn = topNodes.find(n => n.type === 'footnote_list');
      insertPos = fn ? fn.offset : doc.content.size;
    }
  }

  return JSON.stringify({ hasOnesLinks: true, dates, hasHeaderDates, tasks, colspanDurationMismatches, nonOnesItems, insertPos, anchorEnd });
})()
```

**如果 `hasOnesLinks: false`**：告知用户文档中未找到 ONES 需求链接，停止执行。

**`colspanDurationMismatches`（第一步随解析一并返回）**

- **生成规则**：仅针对「单元格内**只有一条** ONES 需求链接且正文中有显式 `Npd` 标注」的行：比较解析得到的 `duration`（来自 `Npd`）与单元格 `colspan`（`parseInt(colspan)`）。若 `Math.abs(duration - colspan) > 1e-6`，则记入 `colspanDurationMismatches`。
- **不参与本校验**：无 `Npd`、凭列宽推断人天（`pdSource === 'colspan'`）的单元格；同一单元格内**多条** ONES（`pdSource === 'multi'`），由多段 Npd 与分段占位处理，**不**与整格 `colspan` 逐条强校验（避免与现有多需求解析策略冲突）。

---

### 第一步之后：colspan 与 Npd 不一致时的确认（进入第二步前必做）

当解析结果中 **`colspanDurationMismatches.length > 0`** 时：

1. **必须暂停**，在**进入第二步（navigate ONES）之前**向用户展示所有不一致条目。
2. **提示内容须包含**：说明「单元格合并列数（colspan）与正文中标注的 Npd 不一致」，并给出表格或列表：`人员`、`表格行号 rowIndex`（表头为第 0 行时，数据行与脚本中 `rowIndex` 一致）、`colspan`、`标注 PD（duration）`、需求链接或 `issueId`。
3. **请用户回复「继续」或「取消」**：
   - **「继续」**：视为接受当前解析结果，**方可执行第二步**及后续流程。
   - **「取消」**：应立即终止**全流程**（不得执行第二、三、四、五步，不得创建 ONES、不得写回学城）。
4. 若用户回复模糊，须**追问**「请回复「继续」或「取消」」，不得默认继续。

示例话术：

```
⚠️ 以下排期单元格中，合并列数（colspan）与正文中的 Npd 标注不一致，请确认是否仍按当前解析创建 ONES 任务：

| 人员 | 行号 | colspan | 标注 PD | issueId / 链接 |
|------|------|---------|---------|----------------|
| 张三 | 3 | 3 | 2 | 93756967 |

请回复「继续」以继续后续流程，或回复「取消」以终止全流程（不创建、不写回）。
```

当 **`colspanDurationMismatches` 为空**时：**不**因此增加确认，按原逻辑继续（可与下方任务确认表合并展示）。

---

**⚠️ 解析完成后默认自动继续执行，同时向用户展示解析结果；若存在 colspan/Npd 不一致，必须先完成上方确认后，才可进入第二步。** 如果用户明确说"确认后再继续"则暂停等待对任务表的确认（与 colspan 确认可合并为同一次交互，但「取消」语义均需终止全流程）。

展示格式如下（Markdown 表格）：

```
解析到以下任务，请确认是否正确（如有需要可修正需求链接）：

| # | 人员 | 需求 issueId | 需求链接 | 天数 | 日期 | 备注 |
|---|------|-------------|---------|------|------|------|
| 1 | 张文粹 | 93756967 | [链接](https://...) | 1天 | 3.30 | |
| 2 | ... | ... | ... | ... | ... | |

⚠️ 以下链接为 task 类型（非 requirement），无法创建子任务，将跳过：
- 王宇：/workItem/task/detail/94036603

⚠️ 以下排期项包含 Npd 标注，但单元格内没有 ONES 需求链接（可能是学城文档链接、纯文字描述等），不会创建 ONES 任务，如需创建请补充 ONES 需求链接：
- 刘欣（行 7）：「PRD」定向升房权益... 2pd

确认无误后回复「继续」，或指出需要修正的条目。
```

**过滤规则**：只保留 href 中包含 `/workItem/requirement/detail/` 的链接（有 issueId）；`/workItem/task/detail/` 类型的链接**无法挂子任务，必须过滤掉**，并在确认表格中单独列出告知用户。**`nonOnesItems`（有 Npd 但无 ONES 链接的单元格）**：若数组非空，在上方 task 类型跳过提示之后追加此段，列出人员、行号、单元格内容摘要（取前 80 字符）、标注 PD，告知用户这些条目不会创建 ONES 任务，请确认是否需要补充 ONES 需求链接。若 `nonOnesItems` 为空则不展示此段。

---

### 第二步：navigate 到 ONES，查询需求详情和 subtypeId

navigate 到 `https://ones.sankuai.com`，等待页面加载（确保 Cookie 有效）。

> **必须通过浏览器 evaluate 执行**，不得用 Node.js 或 curl，因为 SSO Cookie 只在浏览器 session 中有效。

**用一个脚本并行完成**：需求详情查询 + subtypeId 查询。（已有子任务在第四步实时查，不在此查。）

```javascript
(async () => {
  const TASKS = /* 第一步解析出的 tasks 数组 */;

  const uniqueIssues   = [...new Map(TASKS.map(t => [t.issueId, t])).values()];
  const uniqueProjects = [...new Set(TASKS.map(t => t.projectId))];

  // ── 并行查询需求详情 ───────────────────────────────────────────────
  const issueDetails = await Promise.all(uniqueIssues.map(async t => {
    const r = await fetch(
      `https://ones.sankuai.com/api/proxy/issue/${t.issueId}?issueType=REQUIREMENT&projectId=${t.projectId}`,
      { headers: { Accept: 'application/json' } }
    );
    const d = await r.json();
    return {
      issueId:          t.issueId,
      name:             d.data?.name?.displayValue,
      iterationId:      d.data?.iterationId,       // { id, value, displayValue }
      iterationName:    d.data?.iterationId?.displayValue,
      labels:           d.data?.labels?.value,     // [{ id, displayValue }]
      customField23767: d.data?.customField23767,  // { id, value }
      priority:         d.data?.priority?.value
    };
  }));
  const issueMap = Object.fromEntries(issueDetails.map(d => [d.issueId, d]));

  // ── 并行查询 subtypeId（按 projectId 去重） ────────────────────────
  const subtypeResults = await Promise.all(uniqueProjects.map(async pid => {
    const r = await fetch(`https://ones.sankuai.com/api/proxy/projects/${pid}/subtype/list?objectType=DEVTASK&forCreate=true`);
    const d = await r.json();
    const items = d.data?.items || [];
    const def   = items.find(s => s.active && s.isDefault) || items.find(s => s.active);
    return { projectId: pid, subtypeId: def?.id };
  }));
  const subtypeMap = Object.fromEntries(subtypeResults.map(s => [s.projectId, s.subtypeId]));

  return JSON.stringify({ issueMap, subtypeMap });
})()
```

---

### 第三步：计算日期、准备任务列表（在 ONES 页面 evaluate 完成）

**不要在 AI 本地自行计算**，用一个脚本在 ONES 页面完成日期推算和任务列表组装，消除 AI 自由发挥的空间：

```javascript
(async () => {
  const TASKS       = /* 第一步解析出的 tasks 数组 */;
  const DATES       = /* 第一步解析出的 dates 数组（表头日期） */;
  const ISSUE_MAP   = /* 第二步的 issueMap */;
  const SUBTYPE_MAP = /* 第二步的 subtypeMap */;

  // ── 用排期表头日期匹配本周迭代（不依赖需求自身迭代） ─────────────
  // ISSUE_MAP 中各需求的 iterationName 含日期范围，如 "住宿-2026W29（0720-0726)"
  // DATES 表头如 ["", "", "周一 7.20", "周二 7.21", ...]
  // 排期第一天落在哪个迭代的日期范围内，哪个就是本周迭代

  // 收集所有不同迭代（去重）
  const allIterations = Object.values(ISSUE_MAP)
    .filter(v => v.iterationName && v.iterationId?.value)
    .map(v => ({ name: v.iterationName, id: v.iterationId.value }))
    .filter((v, i, arr) => arr.findIndex(x => x.id === v.id) === i);

  // 从表头日期提取第一个工作日的月和日
  let scheduleMonth = null, scheduleDay = null;
  if (DATES && DATES.length > 2) {
    const m = DATES[2].match(/(\d+)\.(\d+)/);
    if (m) { scheduleMonth = parseInt(m[1]); scheduleDay = parseInt(m[2]); }
  }

  // 匹配：排期第一天落在哪个迭代的日期范围内
  let matchedIteration = null;
  for (const iter of allIterations) {
    const dm = iter.name.match(/[（(](\d{2})(\d{2})-(\d{2})(\d{2})/);
    if (dm && scheduleMonth && scheduleDay) {
      const iterStartMd = parseInt(dm[1]) * 100 + parseInt(dm[2]);
      const iterEndMd   = parseInt(dm[3]) * 100 + parseInt(dm[4]);
      const schedMd     = scheduleMonth * 100 + scheduleDay;
      if (schedMd >= iterStartMd && schedMd <= iterEndMd) { matchedIteration = iter; break; }
    }
  }
  // fallback：取出现次数最多的迭代
  if (!matchedIteration) {
    const counts = {};
    for (const v of Object.values(ISSUE_MAP)) {
      const id = v.iterationId?.value;
      if (id) counts[id] = (counts[id] || 0) + 1;
    }
    const topId = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0];
    matchedIteration = allIterations.find(i => i.id == topId) || allIterations[0];
  }

  const iterationName = matchedIteration?.name || '';
  const year    = parseInt(iterationName.match(/(\d{4})W/)?.[1] || new Date().getFullYear());
  const weekNum = iterationName.match(/W(\d+)/)?.[1] || '0';

  // ── 从迭代名称解析起始日期（如 0316 → 3月16日） ───────────────────
  const iterDateMatch = iterationName.match(/[（(](\d{2})(\d{2})-/);
  const iterStartMonth = iterDateMatch ? parseInt(iterDateMatch[1]) : 1;
  const iterStartDay   = iterDateMatch ? parseInt(iterDateMatch[2]) : 1;

  // ── 工作日偏移函数（colIndex 2=周一, 3=周二, ...） ─────────────────
  const mm = n => String(n).padStart(2, '0');
  function colToDate(colIndex) {
    // colIndex 2 = 起始日（周一），每+1 加一个工作日
    const offset = colIndex - 2;
    const d = new Date(year, iterStartMonth - 1, iterStartDay);
    let count = 0;
    while (count < offset) {
      d.setDate(d.getDate() + 1);
      if (d.getDay() !== 0 && d.getDay() !== 6) count++;
    }
    while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() + 1);
    return { month: d.getMonth() + 1, day: d.getDate() };
  }

  // ── 提取本周的 iterationId ────────────────────────────────────────────
  // 使用排期表头日期匹配出的本周迭代（matchedIteration）
  const weekIterationId = matchedIteration?.id || Object.values(ISSUE_MAP)[0]?.iterationId?.value;

  // ── 组装任务列表 ───────────────────────────────────────────────────
  const allTasks = TASKS.map(t => {
    const issue = ISSUE_MAP[t.issueId] || {};

    // 日期：表头有日期时已在第一步解析，否则从 colIndex 推算
    const startDate = t.startDate || colToDate(t.startDateCol);
    const endDate   = t.endDate   || colToDate(t.endDateCol);
    const dateRange = (startDate.month === endDate.month && startDate.day === endDate.day)
      ? `${startDate.month}.${startDate.day}`
      : `${startDate.month}.${startDate.day}-${endDate.month}.${endDate.day}`;

    const expectStart = new Date(`${year}-${mm(startDate.month)}-${mm(startDate.day)}T00:00:00+08:00`).getTime();
    const expectClose = new Date(`${year}-${mm(endDate.month)}-${mm(endDate.day)}T23:59:59.999+08:00`).getTime();

    // 任务标题格式：W{周号}-{需求名称}
    const taskTitle = `W${weekNum}-${issue.name || t.issueId}`;

    return {
      // 来自排期文档（不得修改）
      issueId:    t.issueId,
      projectId:  t.projectId,
      uid:        t.uid,
      empId:      t.empId,
      person:     t.person,
      duration:   t.duration,
      // 计算得出
      taskTitle,
      dateRange,
      expectStart,
      expectClose,
      // 来自需求详情
      iterationId:      issue.iterationId?.value,
      // 本周迭代 ID（用于去重匹配，可能与需求自身迭代不同）
      weekIterationId,
      subtypeId:    SUBTYPE_MAP[t.projectId],
      pmisId:       issue.customField23767?.value,
      labelIds:     (issue.labels || []).map(l => l.id),
      labelNames:   (issue.labels || []).map(l => l.displayValue).join(', ')
    };
  });

  // ── 迭代一致性检测 ──────────────────────────────────────────────────
  const iterationMismatches = Object.entries(ISSUE_MAP)
    .filter(([_, v]) => v.iterationId?.value && v.iterationId?.value !== weekIterationId)
    .map(([issueId, v]) => ({
      issueId: parseInt(issueId),
      issueName: v.name,
      issueIterationId: v.iterationId?.value,
      issueIterationName: v.iterationName,
      weekIterationId,
      weekIterationName: matchedIteration?.name || ''
    }));

  return JSON.stringify({ allTasks, weekNum, weekIterationId, iterationMismatches });
})()
```

---

### 第三步与第四步之间：每人 PD 汇总与超限确认（创建 ONES 前必做）

在**第三步**得到 `allTasks` 之后、**进入第四步**批量创建之前，必须先按人员汇总即将创建的任务人天（PD），并据此决定是否暂停等待用户确认。

#### 统计口径

- **数据来源**：第三步输出的 `allTasks`（与即将调用 `fastIssue` 创建的任务集合一致；已过滤掉非 requirement 链接的任务不应出现在此列表中）。
- **汇总方式**：按 `uid`（MIS ID）分组，对同一人的所有任务的 `duration` **求和**，得到每人「本周排期总 PD」。
- **阈值**：若某人的汇总值 **严格大于 5**（即 `> 5`，**等于 5 不触发**），视为「超限」。

#### 分支行为

| 情况 | 行为 |
|------|------|
| 所有人的汇总 PD 均 **≤ 5** | **不**弹出确认，直接进入第四步（批量创建）。 |
| 存在至少一人汇总 PD **> 5** | **必须暂停**，向用户展示超限名单与数值，并等待用户明确回复。 |

#### 超限时的用户提示（必须包含）

当存在超限人员时，输出须包含：

1. **说明**：哪些开发人员本周排期汇总超过 5pd，并列出每人汇总 PD（保留一位小数或与排期一致）。
2. **操作指引**：请用户回复 **「继续」** 以仍按当前排期创建 ONES 子任务，或回复 **「取消」** 以终止本次流程（不会创建任何任务、不会写回学城）。

示例（Markdown 表格，实际人数与数值以解析结果为准）：

```
⚠️ 以下人员本周排期汇总超过 5 人天，请确认是否仍要创建 ONES 子任务：

| 开发人员 | 汇总 PD |
|---------|--------|
| 张三 | 6.5 |
| 李四 | 5.5 |

请回复「继续」以继续创建，或回复「取消」以终止全流程（不创建、不写回文档）。
```

#### 用户回复后的处理

- **「继续」**（或明确表示同意继续的同义表述）：进入 **第四步**，按原流程分批创建子任务。
- **「取消」**（或明确表示终止的同义表述）：**立即终止**全流程。不得执行第四步、第五步；不得 navigate 去执行创建或写回；可向用户简短确认「已按你的要求取消，未创建任何任务」。

> 若用户未表态或回复模糊，应**再次追问**「请回复「继续」或「取消」」，不得默认继续创建。

---

### 第四步：分批创建子任务 + 继承标签（文件传参 + 浏览器 evaluate）

**必须分批执行，每批 ≤ 4 个任务**，原因：
1. 浏览器 evaluate 有超时限制，20 个任务一次性执行会超时失败
2. 命令行直接传 JSON 会有转义问题，必须通过写文件 + python3 传参

#### 分批执行标准流程

**Step A：将当前批次的任务数据写入临时文件**

```javascript
// 写入 /workspace/_batchN.js（N 为批次号，从 1 开始）
// 文件内容为自执行脚本，直接内嵌任务数据
```

**Step B：通过 python3 传参执行**

```bash
cd /workspace && python3 -c "
import json
with open('_batchN.js', 'r') as f:
    code = f.read()
cmd = {'action': 'evaluate', 'script': code}
print(json.dumps(cmd))
" > _cmd.json && ~/.catpaw/bin/catdesk browser-action "$(cat _cmd.json)"
```

> 使用 `python3` 生成 JSON 命令文件，避免命令行转义问题，然后将 JSON 文件内容传给 browser-action。

**Step C：收集每批结果，全部批次完成后汇总**

**Step D：所有临时文件在写回文档后统一删除**（用 `delete_file` 工具逐个删除）

#### 分批脚本模板

每个 `_batchN.js` 文件的内容结构如下（直接内嵌当前批次的任务数组）：

**创建前实时查一次已有子任务**，用三层匹配做重复检测，防止重试时重复创建：

```javascript
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // ⚠️ 直接内嵌当前批次数据（≤4 个任务），不使用占位符
  const ALL_TASKS = [ /* 当前批次的 allTasks 子集，直接写死 */ ];
  const WEEK_NUM          = /* weekNum，如 "13" */;
  const WEEK_ITERATION_ID = /* 第三步输出的 weekIterationId，如 123665 */;

  // ── 实时查已有子任务（按 issueId 去重，includeOtherFatherAndSon=false） ──
  // 注意：必须用 includeOtherFatherAndSon=false，只查当前需求的直接子任务，
  // 否则会混入其他需求的关联任务，导致重复检测误判。
  const uniqueIssueIds = [...new Set(ALL_TASKS.map(t => t.issueId))];
  const freshExistingMap = {};
  for (const issueId of uniqueIssueIds) {
    const body = {
      issueId,
      query: [{ type: 'TERMS', fieldType: 'component_parent', field: 'parentId', valueList: [issueId], group: 1 }],
      displayFieldList: ['id', 'name', 'assigned', 'iterationId'],
      isParentsInTreeMode: true
    };
    const r = await fetch(
      'https://ones.sankuai.com/api/proxy/filter/query/listpage/issue?projectId=&type=DEVTASK&cn=1&sn=100&displayType=REQUIREMENT_SON_DEVTASK&expanded=false&state=ALL&issueAssociateType=REQUIREMENT_SON_DEVTASK&archiveSpaceFilter=false&includeOtherFatherAndSon=false',
      { method: 'POST', headers: { 'Content-Type': 'application/json;charset=UTF-8', Accept: 'application/json' }, body: JSON.stringify(body) }
    );
    const d = await r.json();
    freshExistingMap[issueId] = (d.data?.items || []).map(c => ({
      id: c.id?.value, name: c.name?.displayValue,
      assignedMisId: c.assigned?.value, iterationId: c.iterationId?.value
    }));
  }

  const results = [];
  for (const t of ALL_TASKS) {
    // ── 三层重复检测 ──────────────────────────────────────────────────
    // 负责人匹配（MIS ID 大小写不敏感）
    // 第一层：本周 iterationId 精确匹配（用 weekIterationId，不用需求自身 iterationId）
    // 第二层：iterationId 为 null 时用任务名前缀 WXX- 兜底
    // 第三层：任务名完全一致兜底
    const children = freshExistingMap[t.issueId] || [];
    let existingId = null, skipReason = null;
    for (const c of children) {
      if ((c.assignedMisId || '').toLowerCase() !== (t.uid || '').toLowerCase()) continue;
      // ⚠️ 用本周 iterationId 匹配，而非需求自身的 iterationId
      // 需求可能还停留在上周迭代，用需求的 iterationId 会误匹配到上周旧任务
      if (WEEK_ITERATION_ID && c.iterationId === WEEK_ITERATION_ID) { existingId = c.id; skipReason = '本周iterationId匹配'; break; }
      if (!c.iterationId && c.name?.startsWith('W' + WEEK_NUM + '-')) { existingId = c.id; skipReason = '任务名前缀匹配'; break; }
      if (c.name === t.taskTitle)                                      { existingId = c.id; skipReason = '任务名完全匹配'; break; }
    }
    if (existingId) {
      results.push({ ...t, newId: existingId, status: '已存在', skipReason, isSuccess: true });
      continue;
    }

    // ── 创建任务 ──────────────────────────────────────────────────────
    // parentId 必须用排期文档解析出的 t.issueId，不得替换为父需求 ID
    const createBody = {
      projectId:        t.projectId,
      type:             'DEVTASK',
      parentId:         t.issueId,   // ← 排期文档里的需求 ID，不得修改
      assigned:         t.uid,
      priority:         2,
      subtypeId:        t.subtypeId,
      customField23767: t.pmisId,
      name:             t.taskTitle,
      iterationId:      t.iterationId,
      expectTime:       t.duration,
      unit:             'date',
      expectStart:      t.expectStart,
      expectClose:      t.expectClose
    };
    const cr  = await fetch('https://ones.sankuai.com/api/proxy/fastIssue', {
      method: 'POST',
      headers: { Accept: 'application/json, text/plain, */*', 'Content-Type': 'application/json;charset=UTF-8' },
      body: JSON.stringify(createBody)
    });
    const cd  = await cr.json();
    const newId = cd.data?.id?.value;

    // 继承标签（创建成功后等 200ms 再 PUT）
    let labelCode = null;
    if (newId && t.labelIds?.length) {
      await sleep(200);
      const lr = await fetch(`https://ones.sankuai.com/api/proxy/issue/${newId}`, {
        method: 'PUT',
        headers: { Accept: 'application/json, text/plain, */*', 'Content-Type': 'application/json;charset=UTF-8' },
        body: JSON.stringify({ labels: t.labelIds })
      });
      labelCode = (await lr.json()).code;
    }

    // fastIssue 成功返回 201，也视为成功
    const isSuccess = (cd.code === 200 || cd.code === 201 || newId != null);
    results.push({ ...t, newId, status: isSuccess ? '新创建' : `创建失败(${cd.code})`, isSuccess, labelCode });
    await sleep(500);
  }

  return JSON.stringify(results);
})()
```

#### 分批示例（20 个任务 → 5 批）

```
批次 1：任务 1-4  → 写 _batch1.js → python3 传参执行 → 收集结果
批次 2：任务 5-8  → 写 _batch2.js → python3 传参执行 → 收集结果
批次 3：任务 9-12 → 写 _batch3.js → python3 传参执行 → 收集结果
批次 4：任务 13-16→ 写 _batch4.js → python3 传参执行 → 收集结果
批次 5：任务 17-20→ 写 _batch5.js → python3 传参执行 → 收集结果
汇总所有批次结果 → 进入第五步写回文档
```

---

### 第五步：写回学城文档（navigate 回文档，一次 evaluate 完成）

使用 `browser-action` navigate 回用户提供的学城排期文档 URL。

**编辑模式切换**：学城文档默认为只读模式，必须先切换到编辑模式。使用以下脚本完成编辑模式切换和等待：

```javascript
// 点击编辑按钮并等待编辑器就绪
(async () => {
  // 点击编辑模式按钮
  document.querySelector('.doc-mode-switch-item.edit')?.click();
  
  // 等待 isEditable 变为 true（最多等待 10 秒）
  await new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      if (window.editorInst?.manager?.editorView?.editable) {
        resolve('ready');
      } else if (attempts++ > 30) {
        reject('timeout');
      } else {
        setTimeout(check, 300);
      }
    };
    check();
  });
  return 'editor ready';
})()
```

> ⚠️ 注意：编辑按钮是 `<div class="doc-mode-switch-item edit">` 而非 `<button>`。

编辑器就绪后，**用一个脚本完成**：确定插入位置 + 构建所有节点 + 一次性插入。

通过「写文件 + python3 传参」方式执行：

```bash
cd /workspace && python3 -c "
import json
with open('_write_result.js', 'r') as f:
    code = f.read()
cmd = {'action': 'evaluate', 'script': code}
print(json.dumps(cmd))
" > _cmd.json && ~/.catpaw/bin/catdesk browser-action "$(cat _cmd.json)"
```

```javascript
(async () => {
  try {
    const manager = window.editorInst.manager;
    const view    = manager.editorView;
    const state   = view.state;
    const schema  = state.schema;
    const { table, table_row, table_cell, table_header, paragraph } = schema.nodes;
    const linkNode = schema.nodes.link; // link 是 node 不是 mark

    // ── 确定插入位置 ────────────────────────────────────────────────
    // 优先使用第一步已获取的 anchorEnd；若为 null 则用 insertPos；
    // 若两者都为 null，在此重新扫描文档
    let INSERT_POS = /* 第一步的 anchorEnd ?? insertPos */;
    if (INSERT_POS == null) {
      const doc = state.doc;
      let anchorEnd = null;
      const topNodes = [];
      doc.forEach((node, offset) => {
        const text = node.textContent || '';
        if (anchorEnd === null && (text.includes('排期任务输出') || text.includes('以下是输出任务创建结果输出'))) {
          anchorEnd = offset + node.nodeSize;
        }
        topNodes.push({ type: node.type.name, offset });
      });
      if (anchorEnd !== null) {
        INSERT_POS = anchorEnd;
      } else {
        const fn = topNodes.find(n => n.type === 'footnote_list');
        INSERT_POS = fn ? fn.offset : doc.content.size;
      }
    }

    // ── 辅助函数 ────────────────────────────────────────────────────
    const CW  = { person: 138, title: 282, work: 115, date: 160, status: 106, label: 140, taskId: 152 };
    const CW2 = { person: 177, count: 113, days: 103, newC: 94, exist: 125 };

    const mkCell = (text, isH, w) => {
      const nt = isH ? table_header : table_cell;
      const p  = paragraph.create(null, text ? [schema.text(text)] : []);
      return nt.create(w ? { colwidth: [w] } : {}, [p]);
    };
    const mkLinkCell = (text, href, w) => {
      const ln = linkNode.create({ href, title: '' }, [schema.text(text)]);
      return table_cell.create(w ? { colwidth: [w] } : {}, [paragraph.create(null, [ln])]);
    };
    const mkMentionCell = (name, uid, empId, isH, w) => {
      const nt          = isH ? table_header : table_cell;
      const mentionType = schema.nodes['ct-mention'] || schema.nodes['mention'];
      const inner       = mentionType ? mentionType.create({ name, uid, empId: empId || '' }) : schema.text('@' + name);
      return nt.create(w ? { colwidth: [w] } : {}, [paragraph.create(null, [inner])]);
    };
    const emptyPara = () => paragraph.create(null);

    // ── 构建详情表格 ────────────────────────────────────────────────
    const RESULTS = /* 第四步的 results 数组 */;

    // 按人员分组，标记每人第一条（用于 mention 显示）
    const seenPersons = new Set();
    const enriched = RESULTS.map(r => {
      const isFirst = !seenPersons.has(r.uid);
      seenPersons.add(r.uid);
      return { ...r, isFirstOfPerson: isFirst };
    });

    const headerRow = table_row.create(null, [
      mkCell('开发人员', true, CW.person), mkCell('任务标题', true, CW.title),
      mkCell('工作量',   true, CW.work),   mkCell('日期',     true, CW.date),
      mkCell('状态',     true, CW.status), mkCell('标签',     true, CW.label),
      mkCell('任务ID',   true, CW.taskId)
    ]);
    const dataRows = enriched.map(r => table_row.create(null, [
      r.isFirstOfPerson
        ? mkMentionCell(r.person, r.uid, r.empId, false, CW.person)
        : mkCell('', false, CW.person),
      mkCell(r.taskTitle,       false, CW.title),
      mkCell(r.duration + '天', false, CW.work),
      mkCell(r.dateRange,       false, CW.date),
      mkCell(r.status,          false, CW.status),
      mkCell(r.labelNames || '', false, CW.label),
      mkLinkCell(String(r.newId),
        `https://ones.sankuai.com/ones/product/${r.projectId}/workItem/devTask/detail/${r.newId}`,
        CW.taskId)
    ]));
    const detailTable = table.create(null, [headerRow, ...dataRows]);

    // ── 构建汇总表格 ────────────────────────────────────────────────
    const personMap = {};
    for (const r of enriched) {
      if (!personMap[r.uid]) personMap[r.uid] = { name: r.person, uid: r.uid, empId: r.empId, count: 0, days: 0, newCount: 0, existCount: 0 };
      personMap[r.uid].count++;
      personMap[r.uid].days += r.duration;
      if (r.status === '新创建') personMap[r.uid].newCount++; else personMap[r.uid].existCount++;
    }
    const PERSON_STATS = Object.values(personMap);
    const TOTAL      = enriched.length;
    const NEW_COUNT  = enriched.filter(r => r.status === '新创建').length;
    const EXIST_COUNT = TOTAL - NEW_COUNT;
    const TOTAL_DAYS  = enriched.reduce((s, r) => s + r.duration, 0);

    const pHdr = table_row.create(null, [
      mkCell('开发人员', true, CW2.person), mkCell('任务数',  true, CW2.count),
      mkCell('总人天',   true, CW2.days),   mkCell('新创建',  true, CW2.newC),
      mkCell('已存在',   true, CW2.exist)
    ]);
    const pRows = PERSON_STATS.map(p => table_row.create(null, [
      mkMentionCell(p.name, p.uid, p.empId, false, CW2.person),
      mkCell(String(p.count),      false, CW2.count),
      mkCell(p.days + '天',        false, CW2.days),
      mkCell(String(p.newCount),   false, CW2.newC),
      mkCell(String(p.existCount), false, CW2.exist)
    ]));
    const summaryTable = table.create(null, [pHdr, ...pRows]);

    const titlePara   = paragraph.create(null, [schema.text('任务创建结果')]);
    const summaryPara = paragraph.create(null, [schema.text(
      `人力投入汇总：总任务 ${TOTAL} 个（新创建 ${NEW_COUNT} 个，已存在 ${EXIST_COUNT} 个），总人力 ${TOTAL_DAYS} 人天，参与 ${PERSON_STATS.length} 人`
    )]);

    // ── 一次性插入所有节点（INSERT_POS 固定，只累加 offset） ──────────
    const nodesToInsert = [
      emptyPara(), titlePara, emptyPara(),
      detailTable, emptyPara(),
      summaryPara, emptyPara(),
      summaryTable, emptyPara()
    ];
    let tr = state.tr, offset = 0;
    for (const node of nodesToInsert) {
      tr = tr.insert(INSERT_POS + offset, node);
      offset += node.nodeSize;
    }
    view.dispatch(tr);
    return JSON.stringify({ success: true, insertedAt: INSERT_POS, totalOffset: offset });
  } catch (e) {
    return JSON.stringify({ error: e.message, stack: e.stack?.substring(0, 400) });
  }
})()
```

**重要**：`INSERT_POS` 在循环开始前固定，循环内只累加 `offset`，不重新查询文档位置（否则会 RangeError）。

**写回完成后**：用 `delete_file` 工具删除所有 `_batchN.js` 和 `_write_result.js` 临时文件。

---

## 注意事项

### 执行模式

- **默认自动执行**：用户只要提供学城链接，skill 会自动完成全流程（解析 → **colspan/Npd 一致性** → 查询 → **PD 检测** → 创建 → 写回）。**colspan/Npd** 仅在 `colspanDurationMismatches` 非空时等待「继续」/「取消」；**PD 检测**仅在「存在单人汇总 >5pd」时等待「继续」/「取消」；均无则不打断。
- **人工确认模式**：如果用户明确说"确认后再继续"或"先给我看看"，则在解析完成后暂停，展示结果表格等待用户确认。三种确认可合并展示但语义独立：解析确认关注「任务表是否正确」；colspan/Npd 确认关注「列宽与标注人天是否一致」；PD 上限确认关注「单人是否超过 5pd」。任一处用户选择「取消」均终止全流程。

### 核心约束

- **issueId 不得替换**：排期文档里解析出的 `issueId` 就是任务挂载目标（无论是父需求还是子需求），创建时 `parentId = t.issueId`，查重时也查这个 `issueId` 下的子任务。查询需求详情后看到 `parentId` 字段也不得替换——替换会导致任务挂错层级且查重查错层级。
- **task 类型链接必须过滤**：href 中包含 `/workItem/task/detail/` 的链接没有 `issueId`，无法挂子任务，**必须在第一步解析时过滤掉**，并在确认表格中单独列出告知用户。只保留 `/workItem/requirement/detail/` 类型。
- **解析后 colspan / Npd 一致性**：第一步返回 `colspanDurationMismatches`；若数组非空，须在第二步之前展示并等待「继续」或「取消」。「取消」终止全流程。仅「单需求 + 显式 Npd」且与 `colspan` 数值不符时入列；无 Npd、凭列宽推断及多需求单元格按文档规则排除。
- **创建前 PD 上限确认**：第三步得到 `allTasks` 后，按人汇总 `duration`；若任一人 **> 5pd**，必须先展示名单并等待用户「继续」或「取消」，「取消」则终止全流程。≤5pd 不触发确认。
- **分批执行（每批 ≤ 4 个）**：第四步批量创建必须分批，每批不超过 4 个任务，避免浏览器 evaluate 超时。
- **文件传参方式**：所有较长的脚本（第四步各批次、第五步写回）必须先写入工作区临时文件（`_batchN.js`、`_write_result.js`），再用 `python3` 生成 JSON 命令文件后执行，彻底避免命令行转义问题。
- **禁止 Node.js 直接请求 ONES API**：ONES 的 SSO Cookie 只在浏览器 session 中有效，Node.js 环境中 Cookie 会失效（返回 `{"status":401,"data":{"message":"auth failed"}}`），必须通过浏览器 evaluate 执行所有 API 请求。
- **编辑模式切换**：学城文档默认只读，编辑按钮是 `<div class="doc-mode-switch-item edit">` 而非 `<button>`，需用 `document.querySelector('.doc-mode-switch-item.edit')?.click()` 点击，然后等待 `isEditable === true`（通过轮询检测，最多 10 秒）。

### 技术细节

- **mention DOM 结构**：学城文档中人员 mention 的实际 DOM 是 `<a data-type="ct-mention" data-uid="misId" data-emp-id="empId">`，内部有 `<span class="pk-mention">@姓名</span>`。优先用 `a[data-type="ct-mention"]`，兼容旧格式 `span[data-type="mention"]`。
- **人员列位置**：排期表格中人员 mention 在第 **1** 列（index 1），第 0 列是序号列，需求链接从第 **2** 列（index 2）开始。
- **重复检测（三层）**：① `assignedMisId`（大小写不敏感）+ **本周 `weekIterationId`** 精确匹配（不用需求自身的 `iterationId`，因为需求可能还停留在上周迭代）；② `iterationId` 为 null 时用任务名前缀 `WXX-` 兜底；③ 任务名完全一致兜底。查询时必须用 `includeOtherFatherAndSon=false`。
- **第三步必须用脚本执行**：日期推算和任务列表组装必须在 ONES 页面 evaluate 中完成，不得由 AI 在本地自行计算，防止自由发挥出错。
- **link 是 node 不是 mark**：学城编辑器中 `link` 在 `schema.nodes` 里，创建链接用 `schema.nodes.link.create({ href, title: '' }, [schema.text(text)])`。
- **footnote_list 保护**：学城文档末尾的 `footnote_list` 节点不能被覆盖，插入位置必须在它之前。
- **fastIssue 返回 201**：创建成功返回 HTTP 201，判断成功用 `cd.code === 200 || cd.code === 201` 或直接检查 `newId` 是否有值。
- **批量创建限流**：每次创建后间隔 500ms，标签继承前等待 200ms。
- **迭代周号提取**：从 `iterationId.displayValue`（如 `住宿-2026W11（0316-0322)`）中用正则 `/W(\d+)/` 提取周号。
- **优先级映射**：P0=4, P1=3, P2=2（默认）, P3=1。
- **临时文件清理**：所有 `_batchN.js`、`_write_result.js`、`_cmd.json` 等临时文件在第五步完成后用 `delete_file` 工具逐个删除。

---

## API 端点汇总

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/proxy/issue/${issueId}?issueType=REQUIREMENT&projectId=${projectId}` | GET | 查询需求详情（标题、标签、迭代、PMIS） |
| `/api/proxy/projects/${projectId}/subtype/list?objectType=DEVTASK&forCreate=true` | GET | 查询子类型列表 |
| `/api/proxy/filter/query/listpage/issue?...&includeOtherFatherAndSon=false` | POST | 查询需求下已有子任务 |
| `/api/proxy/fastIssue` | POST | 创建子任务（成功返回 201） |
| `/api/proxy/issue/${newId}` | PUT | 继承标签 |

---

## 故障排查

### 案例 1：rawTasks 为空，但文档有 ONES 链接

**原因**：mention 元素识别失败，或人员列 index 不对。

**排查**：检查人员单元格的实际 DOM：
```javascript
const cell = document.querySelectorAll('table')[0].querySelectorAll('tr')[1].querySelectorAll('td')[1];
console.log(cell.innerHTML.substring(0, 300));
```
确认 mention 元素的 `data-type` 属性值（应为 `ct-mention`）和 `data-uid` 属性（应为 MIS ID）。

### 案例 2：插入结果时 RangeError

**原因**：在 insert 循环中重新查询了文档位置，导致 offset 计算错误。

**解决**：`INSERT_POS` 在循环开始前固定，循环内只累加 `offset`，不调用任何文档查询方法。

### 案例 3：标签继承失败（code 非 200）

**原因**：任务刚创建后立即 PUT 可能还未落库。

**解决**：创建后等待 200ms 再继承标签（已在第四步脚本中内置）。

### 案例 4：单元格内多需求解析不完整

**原因**：用 `cell.querySelector` 只取第一个，多需求单元格会丢失后续需求。

**解决**：用 `cell.querySelectorAll('span[data-type="ones"]')` 遍历所有，从各自 `closest('p')` 文本提取 pd 数，按 pd 数累加 subColOffset。

### 案例 5：每个需求都重复创建了两遍

**原因**：三种情况叠加触发：① 重试场景下 AI 跳过了重复检测直接创建；② `includeOtherFatherAndSon=true` 混入其他需求任务干扰判断；③ `iterationId` 为 null 导致单层匹配漏检。

**解决**：第四步脚本内置实时再查 + 三层匹配 + `includeOtherFatherAndSon=false`（均已修复）。

### 案例 6：任务挂在子需求下，但查重查的是父需求

**现象**：排期文档里写的是子需求链接，但 AI 把 `parentId` 和查重用的 `issueId` 都换成了父需求 ID，导致任务挂错层级且查重漏检，重复创建。

**根因**：AI 查询需求详情后看到返回数据里有 `parentId` 字段，误以为要用父需求来创建，自行做了替换。

**解决**：排期文档里解析出的 `issueId` 就是最终答案，`parentId` 和查重都直接用这个值，不做任何替换（已在核心原则和注意事项中明确禁止）。

### 案例 7：Node.js 直接请求 ONES API 返回 401

**现象**：用 Node.js `https.request` 调用 ONES API，返回 `{"status":401,"data":{"message":"auth failed"}}`，所有任务创建失败。

**根因**：ONES 使用 MOA SSO Cookie 认证，Cookie 只存在于浏览器 session 中，Node.js 进程无法访问，即使手动复制 Cookie 字符串也会因 session 绑定失效。

**解决**：所有 ONES API 请求必须通过浏览器 evaluate 执行，不得使用 Node.js / curl / Python requests 等方式。

### 案例 8：浏览器 evaluate 超时（任务数过多）

**现象**：将 20 个任务放在一个 evaluate 脚本中执行，返回 `Request timed out`。

**根因**：每个任务创建需要 500ms 间隔 + 网络请求时间，20 个任务约需 15-20 秒，超过浏览器 evaluate 超时限制。

**解决**：每批 ≤ 4 个任务，分批执行，每批约 3-5 秒，不会超时。

### 案例 9：命令行传参 JSON 转义失败

**现象**：直接在命令行拼接 JSON 脚本时，中文字符、引号、特殊符号导致 JSON 解析失败，报 `Invalid JSON command`。

**根因**：Shell 转义规则复杂，中文和嵌套引号在多层转义后容易出错。

**解决**：将脚本写入临时文件，用 `python3 -c "import json; print(json.dumps(open('path').read()))"` 自动处理所有转义，再嵌入命令执行：
```bash
~/.catpaw/bin/catdesk browser-action "{\"action\":\"evaluate\",\"script\":$(python3 -c "import json; print(json.dumps(open('/path/to/_batchN.js').read()))")}"
```

### 案例 10：学城文档编辑按钮找不到

**现象**：用 `document.querySelectorAll('button')` 找不到编辑按钮，导致无法进入编辑模式。

**根因**：学城文档的编辑模式切换按钮是 `<div>` 而非 `<button>`，class 为 `doc-mode-switch-item edit`。

**解决**：用 `document.querySelector('.doc-mode-switch-item.edit')?.click()` 点击，点击后等待 2 秒再确认 `isEditable === true`。

### 案例 11：去重误匹配到上周旧任务

**现象**：部分需求排在本周排期表，但需求自身的迭代还停留在上周。去重时脚本将这些需求下已有的上周子任务误判为"已存在"跳过，导致本周该创建的任务被漏掉。

**根因**：去重匹配逻辑用的是需求自身的 `iterationId`（来自 `issueMap`），而非本周的 `iterationId`。需求迭代还在 W28（0713-0719），已有子任务的迭代也是 W28，于是 `c.iterationId === t.iterationId` 判定为 true，误匹配到上周旧任务。

**解决**：第三步用**排期表头日期**（如"周一 7.20"）匹配 `ISSUE_MAP` 中各迭代的日期范围（如"0720-0726"），排期第一天落在哪个迭代范围内，哪个就是本周迭代（`weekIterationId`）。这样不依赖需求自身迭代，避免循环依赖。若表头无日期或匹配失败，fallback 取 `ISSUE_MAP` 中出现次数最多的迭代。第四步去重逻辑改用 `WEEK_ITERATION_ID` 匹配已有子任务的 `iterationId`。同时第三步输出 `iterationMismatches` 数组，提示哪些需求迭代与本周不一致。
