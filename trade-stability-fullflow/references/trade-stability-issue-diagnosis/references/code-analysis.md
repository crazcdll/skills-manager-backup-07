# 代码分析公共流程

供 `trade-stability-complaint-diagnosis`（客诉/反馈排查）和 `trade-stability-alert-diagnosis`（告警排查）共同使用。

**包含两条线路**：
- **线路 B**：有 Diva 变更时，基于前序步骤提供的 `commitUrl` 获取并分析该 commit 的完整 diff。
- **线路 C**：无 Diva 变更、且日志或问题现象指向前端时，分析默认分支的当前代码；不以当前代码替代线上版本结论。

> 本文是代码分析的唯一执行规范。告警、APP、小程序和 H5 排查文档只负责决定是否启动线路 B/C、提供上下文和汇总结论，不得重复维护 Git 命令、diff 范围或技术栈分支规则。

---

## 线路 B：变更代码分析（有 Diva 变更时执行）

> ⚠️ 直接读取第二步变更扫描结果中的最可疑变更版本和 commitUrl，**不重新查询 Diva**。

**触发条件**：第二步变更扫描结果存在 Diva 变更。

**输入**（来自第二步变更扫描结果 + 第一步信息提取结果）：
- 最可疑变更的 commitUrl（格式：`aHR0cHM6Ly9kZXYuc2Fua3VhaS5jb20vY29kZS9yZXBvLWRldGFpbC97b3JnfS97cmVwb30vY29tbWl0L3toYXNofWA=）
- bundle 名 + 仓库 SSH 地址（来自 dev-assets.md）
- 问题描述与告警/日志定位信息（如异常堆栈、文件路径、函数名）

### B1. 准备只读分析副本

所有业务线仓库统一放在 `/Users/All_deal_project`。已有仓库仅拉取远端对象，**不得执行 `git stash`、`git pull`、切换分支或修改用户工作区**。

```bash
BASE_DIR="/Users/All_deal_project"
REPO_DIR="$BASE_DIR/{仓库名}"
mkdir -p "$BASE_DIR"

if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" fetch --quiet origin
else
  git clone --no-checkout {仓库SSH地址} "$REPO_DIR"
fi
```

> ⚠️ SSH clone 或 fetch 失败时，使用内网代码平台打开前序步骤提供的 `commitUrl` 查看完整 diff；不得重新查询 Diva。

### B2. 获取 commit 的完整 diff（不区分技术栈）

从 `commitUrl` 提取 `currentHash`，先检查变更概览，再获取完整补丁：

```bash
git -C "$REPO_DIR" show --stat --oneline {currentHash}
git -C "$REPO_DIR" show --format=fuller --find-renames --find-copies {currentHash}
```

若普通 `git show` 仅显示 merge 摘要、未输出文件补丁，再执行：

```bash
git -C "$REPO_DIR" show -m --format=fuller --find-renames --find-copies {currentHash}
```

> 不得使用 `head` 截断 diff；`-m` 会输出相对各 parent 的 diff，分析时须标明采用的 parent，避免将重复补丁误判为多项独立变更。

### B3. 全量 diff 分析

#### B3a. 从全量 diff 识别风险改动

按全部变更文件逐项检查，并结合问题描述、异常堆栈、日志中的文件名/函数名确定关联度：

- **空值与类型安全**：对象属性访问、可选链删除、类型断言、默认值与错误处理是否导致空指针或未捕获异常。
- **异步与生命周期**：Promise、定时器、订阅、回调、请求竞态，以及组件卸载或状态刷新后是否仍访问失效数据。
- **数据与接口契约**：接口参数、响应字段、序列化转换、缓存结构、mock 或默认数据是否发生不兼容变化。
- **状态与条件逻辑**：状态初始化、状态更新顺序、条件渲染、开关逻辑、权限/实验配置是否改变功能路径。
- **交互与导航**：事件绑定、禁用条件、跳转参数、重复提交保护、加载态与错误态处理是否被修改。
- **依赖与构建产物**：依赖版本、公共组件、配置、入口注册、资源路径、打包脚本的变更是否影响运行时。
- **删除或重构**：删除的保护逻辑、重命名路径、抽离的公共方法是否遗留调用点。

#### B3b. 输出全量 diff 结论

对每个与问题相关的改动记录：文件路径、旧/新代码位置、变更摘要、与日志或现象的关联证据、风险等级。无关文件可汇总说明，但不得因技术栈或文件类型跳过读取。

**diff 分析结论**：
- **找到强相关改动** → 记录文件路径、行号、变更内容及关联证据，判定该变更为根因候选。
- **存在风险改动但证据不足** → 标记为待验证，给出验证方式（复现、日志比对、回滚/灰度对照）。
- **全量 diff 未发现关联** → 明确记录已完成全量 diff 分析，线路 B 无结论，等待其他排查证据。

---

## 线路 C：默认分支代码分析（无变更但问题与代码相关时执行）

> 适用场景：第二步无 Diva 变更，但问题描述判断与前端代码逻辑相关（功能缺失/交互异常/UI 渲染错误等），说明可能是 master 现有代码本身存在问题。

**触发条件**（符合任一条）：
- 无用户标识 + 无 Diva 变更 + 问题与前端代码相关
- 有用户标识但日志无结论 + 无 Diva 变更 + 问题与前端代码相关

**「问题与前端代码相关」判断标准**（符合任一条即触发）：
- 功能缺失（如「没有下拉刷新」「按钮消失」「某模块不展示」）
- 交互异常（如「点击无响应」「页面卡住」「跳转失败」）
- UI 渲染错误（如「页面白屏」「样式错乱」「布局异常」）
- 日志或 SourceMap 已指向明确的业务代码位置，但未发现关联发布变更
- 问题无后端接口报错嫌疑（纯前端交互/展示问题）

**输入**（来自第一步信息提取结果）：
- 仓库 SSH 地址（从 dev-assets.md 获取）
- bundle 名称
- 问题描述

### C1. 准备默认分支代码

复用线路 B 的只读仓库副本；若尚未准备，执行 B1。通过远端默认分支读取文件，不修改本地工作区：

```bash
DEFAULT_BRANCH=$(git -C "$REPO_DIR" symbolic-ref --quiet --short refs/remotes/origin/HEAD | sed 's@^origin/@@')
DEFAULT_BRANCH=${DEFAULT_BRANCH:-master}
git -C "$REPO_DIR" show "origin/$DEFAULT_BRANCH:{问题相关文件路径}"
```

> ⚠️ 默认分支只用于发现当前潜在缺陷、配置控制或遗漏保护；它不是问题时刻的线上版本，不能单独作为“变更引入”的证据。

### C2. 定位问题相关代码

根据问题描述提取关键词，搜索相关文件：

```bash
# 在 src 目录下搜索关键词（-l 只列文件名）
git -C "$REPO_DIR" grep -nE "{关键词1}|{关键词2}" "origin/$DEFAULT_BRANCH" -- ':(exclude)node_modules'

# 定位到文件后，读取远端默认分支内容
git -C "$REPO_DIR" show "origin/$DEFAULT_BRANCH:{问题相关文件路径}"
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

1. **功能与调用链** — 功能是否被删除、注释或被条件分支绕过；日志/SourceMap 指向的调用是否仍可达。
2. **条件与配置控制** — 是否受 Horn、AB 实验、权限或环境配置影响；发现配置项时记录名称并要求线上配置验证。
3. **状态与异步安全** — 条件判断、类型约束、空值保护、请求时序、定时器和订阅清理是否存在明显缺陷。
4. **运行时兼容性** — 检查跨端或容器相关属性，但只以实际代码和问题证据为准，不按技术栈预设检查分支。

**C 线结论判断**：
- **找到明确的代码问题**（逻辑缺陷、功能被移除/注释、条件判断有误）→ 记录文件路径、代码位置、问题说明与验证条件，线路 C 得出结论
- **发现受配置/实验控制** → 记录 Horn key 或实验名，建议检查线上配置状态（需配合 Horn/AB 查询验证），线路 C 得出结论
- **代码逻辑看起来正确，无明显问题** → 线路 C 无结论，进入汇总分析（推荐辅助工具扩大排查）
