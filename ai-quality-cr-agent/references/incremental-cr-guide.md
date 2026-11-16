# 增量 CR 详细指南:审查模式判定与降级

> 本文件是 SKILL.md Step 2C / Step 2F 的详细参考文档。SKILL.md 中只保留判定骨架,完整逻辑、正则、坑点、降级与边界情况在此文档中维护。

## 1. 能力概述

增量 CR 的目标:PR 更新后再次触发 CR 时,只审查**自上次 CR 以来新增的 commit**,而不是重复审查整个 PR。

实现方式:每次 CR 在 PR 全局评论末尾留下一行 `📦 基准 commit: {40位hash}`(由 `publish_results.py` 自动写入,记录的是**本轮的 TARGET_COMMIT**)。下次 CR 时扫描评论找到这个 hash,作为增量起点。

```
第 1 轮 CR(全量)   → 审查 PR 全部文件 → 评论留下 📦 基准 commit: A
   ↓ 开发者又推了 2 个 commit,最新 commit = B
第 2 轮 CR(增量)   → 读到基准 A,目标 B → 只审查 A..B 的变更 → 评论留下 📦 基准 commit: B
```

## 2. 模式判定完整逻辑

### 2.1 取 TARGET_COMMIT

```bash
$CODE_CLI pr-commits --url "$PR_URL" --limit 200
```

返回:
```json
{"total": 5, "commits": [{"id": "40位hash", "displayId": "短hash", "message": "...", "author": "..."}]}
```

- **`commits[0].id` 就是 PR 分支的最新 commit** → `TARGET_COMMIT`
- 列表按时间倒序,index 0 最新
- `--limit 200` 是默认上限,超过 200 条的 PR 见 §4 降级

### 2.2 取 BASE_COMMIT

```bash
$CODE_CLI pr-comments --url "$PR_URL"
```

从返回的评论列表中提取基准 commit:

**匹配方式:** 直接对所有评论跑下面的正则,命中即为候选,无需额外筛选条件。

**提取正则:**
```
基准 commit:\s*([0-9a-fA-F]{40})
```

> ⚠️ **故意不包含 `📦` emoji 和 `🤖 AI Code Review` 标题**。原因:
> - **emoji 不可靠**:可能因平台渲染差异、复制粘贴、编码转换丢失或变形,一旦丢失则增量能力静默失效
> - **“基准 commit:” + 40 位十六进制” 已足够独特**:人工不会手敲 40 位 hash,误匹配概率极低
> - **大小写兼容**:用 `[0-9a-fA-F]` 而非 `[0-9a-f]`,防止平台返回大写 hash 时失配
>
> 写入侧仍保留 `📦` 前缀(美观、便于人眼识别),但**读取侧不依赖它**——写入格式比读取条件严,是刻意的容错设计。

**取值规则:**
- 匹配到多条时,**按 `createdDate` 倒序取最新的一条**
- **不按评论作者筛选**

> ⚠️ **为什么不按作者筛选?** AI-CR 的评论由 bot 账号发出,bot 账号在不同环境/不同版本间可能变动(如从个人 token 切换到应用 token)。按作者筛选会在账号变更后彻底失效,而纯文本特征匹配足够独特且稳定。

### 2.3 判定表

| 情况 | CR_MODE | 说明 |
|------|---------|------|
| 用户明确要求全量(`FORCE_FULL=1`) | `full` | 忽略历史评论,BASE_COMMIT 置空 |
| 没找到基准 commit | `full` | 首次 CR,或上次评论被删除 |
| 找到,且 **== TARGET_COMMIT** | — | 提示「自上次 CR 以来无新 commit,如需重审请说明要全量 CR」,**终止流程** |
| 找到,且 **!= TARGET_COMMIT** | `incremental` | `BASE_COMMIT` = 该 hash |

## 3. 🚨 关键坑:基准 commit 的来源

> ### ⛔⛔ 绝对禁止用 `pr-changes` 返回的 `toHash` 作为增量基准
>
> **基准 commit 必须且只能取自 PR 自己的 commit 链(`pr-commits`)。**

### 3.1 原因

`pr-changes` 返回的 `toHash` 是 **PR 的合并点(merge base 侧的比较端点)**,它**不在 PR 分支的 commit 链上**。用它作为增量比较的端点,会把**目标分支(master)上其他人提交的变更**也纳入比较范围。

```
master:  ──●──●──●──●──●   ← 其他人的提交也在这条线上
              \         ↑
PR 分支:        ●──●──●   pr-changes.toHash 落在这附近(合并点)
                      ↑
                pr-commits[0].id ← 这才是 PR 分支真实的最新 commit
```

### 3.2 真实数据验证

在一个真实 PR 上实测对比:

| 取值方式 | 增量比较结果 |
|---------|------------|
| 全量 CR(基线,正确) | **12 个文件** |
| `pr-commits[0].id`(正确做法) | 与全量一致,增量范围正确 |
| `pr-changes.toHash`(错误做法) | **125 个文件** ❌ |

用错误 hash 算出的 125 个文件里,绝大部分是 master 上其他人的提交——不仅不是"增量",反而比全量还大 10 倍,CR 结果完全失真。

### 3.3 结论

- ✅ `TARGET_COMMIT` = `pr-commits` 返回的 `commits[0].id`
- ❌ 任何情况下都不要用 `pr-changes` 的 `toHash` / `fromHash`
- 若后续有人"优化"代码时改回 `toHash`,本节即为回滚依据

### 3.4 增量窗口合并提交检测（2026-09-16 实测发现）

**背景**：即使基准取自 PR 自己的 commit 链,只要增量窗口 `(since, sourceHead]` 内含**合并提交**(如开发中把 master 合入分支),`compare` 的两-commit 树 diff 也会把合入分支上其他人的变更一并计入,AI 会审到别人的代码。

**实测案例**：web/foodtrade-calc PR217 第4轮（fe1fd68→075dee7,窗口含合入 master 的 merge commit）,增量 compare 返回 29 个文件,其中 20 个是 master 侧别人的（NetCafeRecharge 系列）,CR 报了 2P0+3P1 全在别人文件上。另外 6 个含 merge 的 PR 独立复现同机理（泄漏 2~25 文件不等）。

**修复**（`get_pr_diff.py` 已内置,Agent 无需自己判断）：
- `code_cli pr-commits` 现已返回 `parents` 字段
- 增量判定前,从 head 沿 first-parent 回溯到 since 验证提交关系：
  - 途中遇到 `parents >= 2`（合并提交）→ 回退全量，播报「检测到增量窗口包含合并提交,已切换 PR 全量净差审查」
  - parents 缺失 / 无法走到 since / 列表截断 → 一律视为"无法确认窗口",回退全量
  - 窗口干净 → 照常增量（含"基准自身是 merge"的情况,只要其后无新合并）
- 全量 `pr-changes` 是 merge-base 净差语义（fromHash = merge 第二父,7 个 PR 实测锚点一致）,回退后天然干净

**边界语义**：检测范围是 `(since, sourceHead]` 开区间——基准自身是 merge 不拦截（PR209/PR217 第5轮实测干净）；窗口内含 merge 一律拦截（不判断合入的是哪个分支,parents≥2 只能证明发生合并）。

## 4. 自动降级场景

以下降级逻辑**已在 `get_pr_diff.py` 内部实现**,Agent 无需自己判断,只需读取 `/tmp/cr_mode_info.json` 拿实际生效的模式。

| 降级触发条件 | 脚本行为 | 最终模式 |
|------------|---------|---------|
| `--since` 格式非法(非 40 位十六进制) | 输出警告 | 降级 `full` |
| `--since` 的 commit **不在 PR commit 链上**(force push 冲掉 / 超出最近 200 条范围) | 输出警告 | 降级 `full` |
| compare API 调用异常 | 输出警告 | 降级 `full` |
| 增量范围内解析出的文件数为 0 | 输出警告 | 降级 `full` |
| **增量窗口内含合并提交** | 播报「检测到增量窗口包含合并提交，已切换 PR 全量净差审查」 | 降级 `full` |
| **窗口提交关系无法确认: parents 缺失/截断/走不到 since** | 播报「增量窗口提交关系无法确认」 | 降级 `full` |
| `--since` **== 最新 commit**(无新提交) | 输出提示 + **exit code 2** | 流程终止 |

> ⚠️ **exit code 2 必须被调用方识别**:这不是错误,而是"没有新东西可审"的正常信号。Agent 应终止本次 CR 并向用户提示,不要当作脚本崩溃去重试。

> ⚠️ **不要想当然沿用 Step 2C 的判定结果**:脚本可能在内部静默降级。执行 `get_pr_diff.py` 后**必须**重新读取 `/tmp/cr_mode_info.json`,以文件内容为准更新 `CR_MODE` / `BASE_COMMIT` / `TARGET_COMMIT` / `COMMIT_COUNT`。

> **范围冻结与发布校验**:为每轮生成独立工作目录,通过 `get_pr_diff.py --output <本轮diff> --mode-info <本轮范围JSON>` 保存配对产物(文件内含 org/repo/prId 绑定,供人工核对)。完成拉取后冻结实际模式与 base/target,后续委托复用同一份 diff。发布时传显式范围参数,或用 `--mode-info-file` 指向这份专属文件:
> - 发布器兑底规则:crMode 以文件为准(降级只会增量→全量,方向安全);hash/计数仅补齐未传项,不覆盖显式参数;降为全量时自动清空 base/计数。
> - 文件缺失或损坏则沿用命令行参数,不中断发布。多轮/多 PR 并行时必须用 `--mode-info-file` 指向本轮专属文件,防止读到别的轮次的共享文件导致范围串轮。
> - 增量建议提供完整 base/target hash 和正整数 commitCount;全量不传 baseCommit/commitCount。
> - 前端子审查不得重新拉当前全量 PR 却沿用增量标签;确需改变范围时重新审查并同步所有范围字段。

## 5. `/tmp/cr_mode_info.json` 字段说明

`get_pr_diff.py` 每次执行都会写入模式信息。`/tmp/cr_mode_info.json` 仅为兼容默认值;正式流程使用 `--mode-info` 指定本轮专属路径,避免并发覆盖。

```json
{
  "org": "example-org",
  "repo": "example-repo",
  "prId": "123",
  "crMode": "full",
  "baseCommit": null,
  "targetCommit": "4b1e3bd3a2f19c8e07d5b6a4c3e2f1908d7c6b5a",
  "fileCount": 12,
  "commitCount": null
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `org` / `repo` / `prId` | string | 本文件所属仓库及 PR,发布器校验身份绑定 |
| `crMode` | `"full"` \| `"incremental"` | **实际生效**的模式(已含降级结果) |
| `baseCommit` | string(40位) \| `null` | 增量基准 commit;全量模式为 `null` |
| `targetCommit` | string(40位) | 本次 CR 的目标 commit(= PR 分支最新 commit) |
| `fileCount` | int | 本次 diff 覆盖的文件数 |
| `commitCount` | int \| `null` | 增量范围内的新 commit 数;全量模式为 `null` |

映射到 SKILL 变量:

| JSON 字段 | SKILL 变量 |
|----------|-----------|
| `crMode` | `$CR_MODE` |
| `baseCommit` | `$BASE_COMMIT` |
| `targetCommit` | `$TARGET_COMMIT` |
| `commitCount` | `$COMMIT_COUNT` |

## 6. 增量对下游 Step 的影响

| Step | 是否需要感知模式 | 说明 |
|------|---------------|------|
| Step 3(三层上下文) | ❌ 否 | 基于 diff 中出现的文件,格式与全量一致 |
| Step 4-A/B/C/D | ❌ 否 | **`/tmp/pr_diff.txt` 的格式全量/增量完全一致**,审查逻辑无需改动 |
| Step 4-Merge / Review | ❌ 否 | 同上 |
| Step 7(发布) | ✅ 是 | 全量传 `--cr-mode full` 和已冻结的 `--target-commit`;增量另传 `--base-commit` / `--commit-count`；按最终模式执行待确认行内限额：full 最多 1 条，incremental 为 0，报告与全局摘要保留全部普通待确认项 |
| Step 8(采纳率) | ❌ 否 | 仍按历史评论扫描 |
| Step 9(报告/清理) | ✅ 是 | 报告加「审查范围」行;清理加 `/tmp/cr_mode_info.json` |

## 7. Step 7 范围标识产出位置

传入与本轮模式一致的范围参数后,`publish_results.py` 自动生成范围标识,**无需手工拼装文案**:

| 产出物 | 位置 | 形式 |
|-------|------|------|
| 学城文档 | 第一章「PR 概述」表格 | 新增一行 `审查范围 \| 🟩 增量（从 \`7394fa3d\` → \`4b1e3bd3\`，5 个新 commit）` |
| PR 全局评论 | 摘要区 | `**审查范围：** 🟩 增量（...）` |
| PR 全局评论 | **末尾固定行** | `📦 基准 commit: {40位 TARGET_COMMIT}` ← 下次增量 CR 的读取起点 |
| 大象群推送 | 消息体 | `范围: 🟩增量(5个新commit)`(紧凑格式) |

> 🚨 **PR 全局评论末尾的 `📦 基准 commit:` 行格式固定,禁止改动或删除**。它是下一轮增量 CR 唯一的状态载体——改了格式 = 增量能力永久失效(会一直降级全量)。

## 8. 边界情况处理表

| 场景 | 处理 |
|------|------|
| 首次 CR(无历史评论) | 全量 |
| 上次评论被人工删除 | 找不到基准 → 降级全量 |
| 无新 commit(base == target) | 提示后终止,`exit 2` |
| force push 冲掉基准 commit | commit 链校验拦截 → 降级全量 |
| 基准 commit 超出最近 200 条 | 同上,降级全量 |
| 用户明确要求全量 | `FORCE_FULL=1`,强制全量,跳过模式判定 |
| 多仓库 PR | **每个仓库独立判定**,各自独立的基准 commit,互不影响 |
| Step 7 评论发送失败 | CR 结果正常输出;因未留下基准 commit,下次自动降级全量(不阻断本次流程) |
| 历史遗留的错误基准 hash(如早期误用 `toHash`) | commit 链校验自动识别不在链上 → 降级全量,**无需人工清理** |

## 9. 用户如何强制全量

用户在触发时明确表达全量意图(如「全量 CR」「重新完整审一遍」「full review」)时:

1. 置 `FORCE_FULL=1`
2. 跳过 Step 2C 的评论扫描
3. `CR_MODE=full`,`BASE_COMMIT` 置空
4. Step 2F 调用 `get_pr_diff.py` **不传** `--since`

> 全量 CR 同样会在评论末尾写入 `📦 基准 commit: {TARGET_COMMIT}`,所以强制全量之后的下一轮仍可正常走增量。
