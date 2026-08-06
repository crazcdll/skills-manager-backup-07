---
name: 通过citadel获取新架构目标版本清单
description: 用 oa-skills citadel 拉取学城 2738858921 解析目标版本，失败时以本 skill 的 data/fallback-target-versions.md 为兜底；禁止 web_fetch
---

## 目标

在改 **`dependencies.json` / `ohDependencies.json`** 前，产出一 **`target-versions.md`（`name` → 目标版本）**。学城**优先**；**Citadel 失败** 时用本仓库 **`data/fallback-target-versions.md`**（**勿** 翻外部技能文档）。**本 skill 不改 `componentsMap.json`**。

**禁止** 用 `web_fetch` 拉 `https://km.sankuai.com/collabpage/2738858921`。

## 执行

### 0. 先拿到用户 MIS

- **开始前先确认用户已提供 MIS 号。**
- **若未提供 MIS：立即暂停本流程**，直接提示：`请先提供 MIS 号，收到后再继续拉取学城文档。`
- 未拿到 MIS 前，**不要**继续执行 Citadel 命令。

### 1. 确保 `oa-skills` 可用

```bash
node -e "const cp=require('child_process'); const probe=process.platform==='win32'?'where oa-skills':'command -v oa-skills'; try{cp.execSync(probe,{stdio:'ignore',shell:true})}catch{cp.execSync('npm install -g @it/oa-skills --registry=http://r.npm.sankuai.com',{stdio:'inherit',shell:true})}"
```

使用用户提供的 MIS 执行 `oa-skills citadel getMarkdown --contentId 2738858921`，写入：

`.temp/trade-duo-standard-material-upgrade-npm-dependencies/file/km-2738858921-raw.md`

**失败时** 在 changelist 记原因，并提示：

```
⚠️ 文档拉取失败（原因：<具体原因>），已降级使用本 skill 内建兜底表 data/fallback-target-versions.md。
```

解析兜底：**严格按** @trade-duo-standard-material-upgrade-npm-dependencies/data/fallback-target-versions.md **表格**建立目标集，**不得凭记忆**改版本号。

### 2. 解析为 `target-versions.md`

从学城 raw 或兜底文件得到 `包名 -> 目标版本`。**规则**（与 `data/fallback-target-versions.md` 文末一致）：

- **固定三件套**：`react@19.1.1`、`react-redux@9.2.0`、`redux@5.0.1` 始终用固定表。
- **`@mtfe/msi` 与 `@mtfe/msi-mrn`** 同版。
- **忽略**：`@mrn` 笔误的 `msi-mrn`、已弃用包、标为无需升级/无版本行。

落盘：${{outputFile:.temp/trade-duo-standard-material-upgrade-npm-dependencies/file/target-versions.md}}

文首注明来源「学城 2738858921（Citadel）」或「降级：内建表」。

学城与内建表有差异时，列表说明（以**学城**为准，若学城已拉取）：

```
检测到与内建表不一致，以下以学城为准：
  @foo/bar: 内建 1.0.0 -> 学城 1.1.0
```

### 3. 初筛（只读）

不**改**仓内 JSON。可按 `target-versions.md` 在清单里**粗筛**待升级名，**可选** 写入 `upgrade-candidates.md`。

### 4. 完成条件

- 已有 `target-versions.md`；已标 **Citadel** 或 **降级**。  
- **未** 使用 `web_fetch` 拉 2738858921。

**下一步**：@trade-duo-standard-material-upgrade-npm-dependencies/SKILL.md 第 2～5 步（先 `dependencies` 后 `oh`）。
