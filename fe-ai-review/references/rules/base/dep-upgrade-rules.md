# 依赖升级风险扫描（By AI）

> 当 diff 中 `package.json` 存在组件版本变化时，执行本规则。由 subagent 负责执行，结果合并到主审查发现项。

## 触发条件

变更范围中 `package.json`（含 monorepo 子包）出现版本号变化，且满足以下任一：

- **内部/业务组件**（`@meishi/*`、`@mtfe/*`、`@max/*`、`@nibfe/*`、`@hfe/*`、项目自有 scope）：任何版本变化
- **三方组件**（`react`、`lodash`、`axios` 等）：仅 major 版本升级（如 `17.x → 18.x`）

不触发的情况：
- 仅 lockfile 变化但 `package.json` 未改
- devDependencies 中的纯工具链升级（`eslint`、`typescript`、`jest` 等）

## 执行方式

以 **subagent** 并行执行，与主 Agent 的代码审查同时进行（类似 Step 4 复查机制）。subagent 产出结构化发现项后，主 Agent 在 Step 5 合并。

## 执行步骤

### 1. 提取升级清单

解析 `package.json` diff，列出所有版本变化的包：

```
包名 | 旧版本 | 新版本 | 变化类型
@mtfe/xxx | 0.0.2-rc.12 | 0.0.2-rc.23 | prerelease
@meishi/yyy | 1.2.0 | 2.0.0 | major
react | 17.0.2 | 18.2.0 | major
```

变化类型判定：major / minor / patch / prerelease。

### 2. 获取新旧版本代码

对每个需要扫描的包，通过 `npm pack` 下载到临时目录：

```bash
mkdir -p /tmp/dep-upgrade-scan/{pkg-name}/{old,new}
npm pack <pkg>@<old-version> --pack-destination /tmp/dep-upgrade-scan/{pkg-name}/
npm pack <pkg>@<new-version> --pack-destination /tmp/dep-upgrade-scan/{pkg-name}/
tar -xzf /tmp/dep-upgrade-scan/{pkg-name}/<old-tarball> -C /tmp/dep-upgrade-scan/{pkg-name}/old/
tar -xzf /tmp/dep-upgrade-scan/{pkg-name}/<new-tarball> -C /tmp/dep-upgrade-scan/{pkg-name}/new/
```

> `npm pack` 失败（registry 不可达、包不存在）→ 降级到仅扫描新版代码 + 项目使用方式，标注"旧版不可获取，无法做精确对比"。

### 3. 提取 API 签名

按优先级从包产物中提取导出 API / Props 信息：

1. **优先**：读取 `.d.ts` 类型定义（`index.d.ts` 或 `package.json` 的 `types`/`typings` 字段指向的文件）
2. **其次**：读取入口 `.tsx` / `.ts` 源码（`package.json` 的 `main` 字段），从组件函数参数解构、interface/type 声明中提取 props 结构
3. **补充**：读取 `CHANGELOG.md`，定位两个版本号之间的 Breaking Changes 段落

三个来源都要尝试，综合判断。任一来源缺失不阻塞流程，标注已尝试的来源和实际读取到的来源。

### 4. 对比分析

对比新旧两版 API 签名，识别以下变更类型：

| 变更类型 | 风险等级 | 说明 |
|----------|----------|------|
| 必填参数新增 | P0 | 旧使用方式必然缺失该参数 |
| 参数被删除 | P0 | 旧使用方式传入无效参数，可能被静默忽略或报错 |
| 参数重命名 | P0 | 等同"删除旧 + 新增新"，旧使用方式失效 |
| 参数类型收窄/替换 | P1 | 传入的值可能不再兼容 |
| 嵌套结构拍平/重组 | P1 | 如 `trackInfo.cid` → `cid`，使用方式需跟进调整 |
| 默认值变更 | P1 | 不传时行为发生变化 |
| 导出方法/常量被删除 | P0 | 使用方引用断裂 |
| 组件整体重构 | P1 | 文件数/结构大幅变化，需整体评估 |
| 参数标记 deprecated | P2 | 当前仍可用，但后续版本可能移除 |
| 可选参数新增 | 无风险 | 不影响旧使用方式 |

### 5. 内部实现变更分析（仅业务组件）

对**业务组件**（非原子 UI 库 `@hfe/*`、`@max/leez-*`、非 utils 工具库、非三方包），在 API 签名对比之外，还需简要分析内部实现的变更。方法：对比新旧版本的核心源文件（入口组件、数据层、请求层），关注以下维度：

| 维度 | 关注点 | 影响 |
|------|--------|------|
| 请求/接口 | 请求路径、参数、响应格式是否变化 | 可能影响数据展示正确性 |
| 数据处理 | 数据格式化、过滤、排序逻辑是否变化 | 可能改变 UI 表现 |
| 埋点/曝光 | CID/BID/场景名/曝光配置是否变化 | 影响数据统计口径 |
| 兜底/容错 | 空数据兜底、异常捕获、降级策略是否变化 | 影响异常场景表现 |
| 依赖链 | 新增/移除 peer dependency、底层组件更换 | 可能引入构建问题或行为不一致 |
| 可配置项处理 | props 虽签名不变，但内部对该 prop 的处理逻辑变了 | 同样的传参产生不同行为 |

分析粒度：不需逐行细审，聚焦**可能影响使用方业务表现**的变更点。产出简要说明（3~8 条要点），纳入报告的「变更内容理解」部分。

### 6. 扫描项目使用方式

拿到变更点后，在项目中定位对升级包的实际使用：

```bash
# 搜索 import 语句
grep -r "from ['\"]<pkg>" --include="*.tsx" --include="*.ts" --include="*.jsx" --include="*.js" .

# 搜索 require
grep -r "require(['\"]<pkg>" --include="*.tsx" --include="*.ts" --include="*.jsx" --include="*.js" .
```

对每个使用位置，检查：
- 是否传入了已被删除/重命名的参数
- 传入值的类型是否与新版兼容
- 是否使用了已被删除的导出方法/常量
- 解构方式是否与新版结构一致

### 7. 输出发现项

每条发现项格式：

```
🔴/🟠/🟡 **[依赖升级·{变更类型}]** `{使用文件}:L{行号}` → `{包名}` {旧版} → {新版}：{风险描述}。建议：{修复建议}。
```

示例：

```
🔴 **[依赖升级·参数重组]** `src/pages/Home.tsx:L42` → `@mtfe/max-cross-recommendation` rc.12 → rc.23：
旧版通过 `trackInfo={{ channelName, cid }}` 传入追踪信息，新版改为顶层 props `cid` 和 `channelName`。当前使用方式将导致追踪信息丢失。
建议：将 `trackInfo` 拆分为独立的 `cid` 和 `channelName` props。
```

### 8. 清理临时文件

扫描完成后删除临时目录：

```bash
rm -rf /tmp/dep-upgrade-scan/
```

## 降级策略

| 场景 | 处理 |
|------|------|
| `npm pack` 旧版失败 | 仅分析新版代码 + 项目使用方式，置信度标注"低"，建议人工确认 |
| `npm pack` 新版失败 | 从当前 `node_modules` 读取（如已 install）；仍失败则跳过该包 |
| 包内无 `.d.ts` 也无可读源码 | 标注"无法分析该包 API 变化"，降为 Open Questions |
| 升级包数量过多（> 10 个） | 优先处理 major 升级和内部业务组件；其余仅列清单不做深入分析 |

## 与主审查的关系

- 本规则产出的发现项**合并到 Step 5 分组**，与代码审查发现项混排，按 P 级别统一排序
- 审查概要的「变更摘要」中体现"本次升级了 N 个业务组件"
- 准备章节「识别的变更范围」中列出升级清单表格
- 升级涉及的组件内部改动（如新增了哪些能力、修复了哪些 bug）也应体现在「变更内容理解」中——帮助审查者理解本次升级的动机和影响范围
