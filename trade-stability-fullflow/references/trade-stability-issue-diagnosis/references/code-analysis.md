# 代码分析公共流程

供 `trade-stability-complaint-diagnosis`（客诉/反馈排查）和 `trade-stability-alert-diagnosis`（告警排查）共同使用。

**包含两条线路**：
- **线路 B**：有 Diva 变更时，基于 commitUrl 做 diff 分析（仅分析引入的代码改动）
- **线路 C**：无 Diva 变更、但问题与前端代码相关时，clone master 最新代码做功能分析

---

## 线路 B：变更代码分析（有 Diva 变更时执行）

> ⚠️ 直接读取第二步变更扫描结果中的最可疑变更版本和 commitUrl，**不重新查询 Diva**。

**触发条件**：第二步变更扫描结果存在 Diva 变更。

**输入**（来自第二步变更扫描结果 + 第一步信息提取结果）：
- 最可疑变更的 commitUrl（格式：`aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC97b3JnfS97cmVwb30vY29tbWl0L3toYXNofWA=）
- bundle 名 + 仓库 SSH 地址（来自 dev-assets.md）
- 页面技术栈（DUO / MRN / MAX）

### B1. clone 或更新仓库

所有业务线仓库统一 clone 到对应目录（若已存在则更新）：`/Users/All_deal_project`

```bash
REPO_DIR="{clone目录}/{仓库名}"
if [ -d "$REPO_DIR" ]; then
  cd "$REPO_DIR" && git stash && git pull origin master
else
  cd "{clone目录}" && git clone {仓库SSH地址}
fi
```

> ⚠️ **SSH clone 失败时**：使用 intranet-browser skill 打开 `aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC97b3JnfS97cmVwb30vY29tbWl0L3toYXNofWA= 在线查看变更 diff。

### B2. 提取 commit hash 并分析变更

从 commitUrl 中直接提取 hash，然后查看该 commit 引入的变更：

```bash
# commitUrl 示例：aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC9oZmUvdHJhdmVsLXRpY2tldC1tYXgvY29tbWl0LzNmYWFmNTA4ZTY0Zg==
# → currentHash = 3faaf508e64f

cd "{clone目录}/{仓库名}"

# 查看该 commit 的变更概览
git show {currentHash} --stat

# 查看该 commit 的全量 diff
git show {currentHash}
```

> **说明**：`git show {hash}` 直接展示该 commit 相对于其 parent 的完整变更，无需计算 baseHash，也无需处理 merge commit 场景。
> 若为 FEDO 流水线产生的 merge commit，`git show` 会显示 merge 摘要但无 diff 内容，此时改用：
> ```bash
> # 对 merge commit 展示实际合入内容（-m 展示每个 parent 的 diff，取 index 1 即 feature 分支部分）
> git show -m {currentHash} | head -200
> ```

### B3. 针对技术栈做针对性分析

#### DUO 页面：重点看 componentsMap.json

> ⚠️ **强制执行顺序**：B2 → B3a → B3b → B3c，每步都必须执行，不得跳过。

**B3a. 查看 componentsMap.json 变更，识别变更组件**

```bash
# 查看该 commit 中 componentsMap.json 的变更（对 merge commit 用 -m）
git show -m {currentHash} -- componentsMap.json
```

识别变更的组件 ID（`id` 字段变化）和组件名（`name` 字段）：
```json
"slot编号": { "id": "旧ID → 新ID", "name": "组件名" }
```

> ⚠️ DUO 低代码页面的组件版本用 `id` 字段标识（整数），不是 `npmVersion`。每次保存组件都会生成新 id。

**B3b. 用 duo CLI 查询变更组件的仓库地址和版本历史**

```bash
# 检查 duo CLI（已有则跳过安装）
duo --version 2>/dev/null && echo "ok" || npm install -g @meishi/duo-cli --registry aHR0cDovL3IubnBtLnNhbmt1YWkuY29t

# 查询组件详情（含 git 仓库地址 + 所有历史版本 id）
duo yooz-read-detail --names {组件名}
```

返回值关键字段：

| 字段 | 说明 |
|------|------|
| `git` | 组件仓库 SSH 地址（如 `ssh://git@git.sankuai.com/nibfe/yooz-lowcode-public.git`） |
| `latestVersion` | 当前最新版本 id |
| `versions[].id` | 历史版本 id 列表（用于定位旧版本 id 对应的 commit） |
| `versions[].config` | 各版本的 props 定义（可直接对比新旧版本 props 差异） |

> ⚠️ **`versions[].config` 可直接对比**：若新旧版本 config 字段有差异（如新增/删除 prop），可直接从此处得出结论，无需 clone 仓库。

**B3c. clone 组件仓库，git diff 新旧版本**

```bash
# clone 组件仓库（统一放 /tmp 目录）
cd /tmp && git clone --depth=20 {git字段SSH地址} {仓库名} 2>&1 | tail -3

# 查看组件目录的变更历史，找到新版本 id 对应的 commit
cd /tmp/{仓库名} && git log --all --oneline -- {组件名}/

# 查看最近一次变更的完整 diff（对 merge commit 用 -m）
git show -m {commitHash} -- {组件名}/
```

重点关注：
- `props.json`：新增/删除/修改了哪些 prop（尤其是 `isRequired: true` 的必填项）
- `tree.json`：组件内部跳转逻辑、事件绑定、条件渲染变化
- `mock.json`：mock 数据变化（反映组件期望的数据结构）

**git 字段为空时**：通过 npm 包名查仓库：`aHR0cHM6Ly9ucG0uc2Fua3VhaS5jb20vdjIvcGtnL2RldGFpbD9uYW1lPXtucG3ljIXlkI19YA==

#### MRN / MAX 页面：直接分析全量 diff

```bash
# 先看全貌
git show {currentHash} --stat

# 对关键业务文件做全量 diff
git show {currentHash} -- src/pages/{页面目录}/

# 若文件很多，优先看页面入口文件
git show {currentHash} -- src/pages/{页面目录}/index.tsx
git show {currentHash} -- src/pages/{页面目录}/indexInner.tsx
```

**diff 分析重点**：
- 滚动容器属性（`bounces`、`scrollEnabled`、`refreshControl`、`mrnProps`、`nativeProps`）
- 生命周期/渲染逻辑（影响页面初始化的改动）
- 接口调用（参数变化、时序、新增/移除接口）
- 条件渲染逻辑（可能导致功能入口被隐藏）
- 新增/移除组件（可能与现有功能冲突）

**B 线结论判断**：
- **找到与问题描述强相关的变更** → 记录变更文件 + 代码行 + 改动内容，线路 B 得出结论
- **未找到相关变更** → 线路 B 无结论，等待线路 A 结果后进入汇总分析

---

## 线路 C：master 最新代码分析（无变更但问题与代码相关时执行）

> 适用场景：第二步无 Diva 变更，但问题描述判断与前端代码逻辑相关（功能缺失/交互异常/UI 渲染错误等），说明可能是 master 现有代码本身存在问题。

**触发条件**（符合任一条）：
- 无用户标识 + 无 Diva 变更 + 问题与前端代码相关
- 有用户标识但日志无结论 + 无 Diva 变更 + 问题与前端代码相关

**「问题与前端代码相关」判断标准**（符合任一条即触发）：
- 功能缺失（如「没有下拉刷新」「按钮消失」「某模块不展示」）
- 交互异常（如「点击无响应」「页面卡住」「跳转失败」）
- UI 渲染错误（如「页面白屏」「样式错乱」「布局异常」）
- 问题无后端接口报错嫌疑（纯前端交互/展示问题）

**输入**（来自第一步信息提取结果）：
- 仓库 SSH 地址（从 dev-assets.md 获取）
- bundle 名称
- 问题描述

### C1. clone 或更新仓库

目录规则与线路 B 相同（见 B1 目录表）：

```bash
REPO_DIR="{clone目录}/{仓库名}"
if [ -d "$REPO_DIR" ]; then
  cd "$REPO_DIR" && git stash && git pull origin master
else
  cd "{clone目录}" && git clone {仓库SSH地址}
fi
```

> ⚠️ **SSH clone 失败时**：使用 intranet-browser skill 打开 `aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC97b3JnfS97cmVwb30vdHJlZS9tYXN0ZXJg 在线查看代码。

### C2. 定位问题相关代码

根据问题描述提取关键词，搜索相关文件：

```bash
# 在 src 目录下搜索关键词（-l 只列文件名）
grep -r "{关键词1}\|{关键词2}" \
  --include="*.tsx" --include="*.ts" --include="*.js" \
  {clone目录}/{仓库名}/src -l

# 定位到文件后，读取具体内容
cat {clone目录}/{仓库名}/src/pages/{页面目录}/{主文件}
```

**常见问题关键词映射**：

| 问题描述 | 搜索关键词 |
|---------|-----------|
| 下拉刷新消失/不可用 | `refreshControl`、`onRefresh`、`PullToRefresh`、`scrollEnabled`、`bounces` |
| 按钮点击无响应 | `onPress`、`disabled`、`pointerEvents`、`touchableOpacity` |
| 页面白屏/渲染失败 | `componentDidCatch`、`ErrorBoundary`、`x-if`、`render` |
| 列表不展示/空数据 | `FlatList`、`ListView`、`emptyComponent`、`data=` |
| 页面跳转失败 | `navigate`、`push`、`replace`、`router` |
| 样式/布局异常 | `StyleSheet`、`mrnProps`、`nativeProps`、相关组件 style 属性 |
| 功能入口消失 | `x-if`、相关功能组件名、Horn key 名称 |

### C3. 分析代码逻辑

读取定位到的源文件，重点分析：

1. **功能是否存在** — 对应功能的代码是否被注释、删除，或 `x-if` 条件始终为 false
2. **条件控制逻辑** — 是否受 Horn 配置 / AB 实验 flag / 环境变量控制（重点搜索 `horn`、`hornKey`、`abTest`、`experiment`、`config`）
3. **透传原生属性** — `mrnProps` / `nativeProps` 中是否有影响原生行为的属性（如 `bounces: false` 会禁用 iOS 下拉弹性）
4. **明显代码缺陷** — 条件判断错误、类型错误、空指针、异步时序问题

**C 线结论判断**：
- **找到明确的代码问题**（逻辑缺陷、功能被移除/注释、条件判断有误）→ 记录文件路径 + 代码行 + 问题说明，线路 C 得出结论
- **发现受配置/实验控制** → 记录 Horn key 或实验名，建议检查线上配置状态（需配合 Horn/AB 查询验证），线路 C 得出结论
- **代码逻辑看起来正确，无明显问题** → 线路 C 无结论，进入汇总分析（推荐辅助工具扩大排查）
