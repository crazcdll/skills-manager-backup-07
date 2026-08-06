---
name: trade-standard-spec-459-same-npm-dependencies-catpaw
description: 交易/酒旅跨端项目（Android/iOS/鸿蒙）npm 依赖三端一致性改造。针对含 package.json + oh-package.json 的工程（非 DUO 框架），通过 k-hub 知识库查询标准版本，将三端兼容依赖统一写入 package.json，仅鸿蒙兼容的保留在 oh-package.json，并清理 yarn.lock 重复依赖。当用户提到「三端一致」「package.json 和 oh-package.json 依赖改造」「鸿蒙/安卓/iOS 依赖对齐」「npm 标准化」「yarn.lock 去重」时自动触发。不适用于 DUO 框架（dependencies.json/ohDependencies.json），DUO 项目请使用 trade-duo-standard-same-npm-dependencies。
---

# 交易/酒旅跨端项目 npm 三端一致性改造

面向同时支持 **Android / iOS / 鸿蒙** 的跨端项目，基于 `package.json` + `oh-package.json` 进行依赖标准化改造：
1. 将三端兼容依赖版本写入 `package.json`，从 `oh-package.json` 中删除。
2. 仅兼容鸿蒙、不兼容 Android/iOS 的依赖保留在 `oh-package.json` 中（并对齐标准版本）。
3. 清理 `yarn.lock` 中因本次改动引入的重复依赖，必要时更新 `resolutions`。

> 🔔 **DUO 框架**（修改 `dependencies.json` / `ohDependencies.json`）请改用 **`trade-duo-standard-same-npm-dependencies`**。

---

## 前置条件：k-hub MCP（强制）

步骤 01 **必须**通过 **k-hub MCP** 查询酒旅 npm 三端一致性改造知识库；**执行前须确认 k-hub 已在本机配置并连通**。

若未配置、调用失败或鉴权失败：**不得**继续后续步骤；须向用户给出以下配置说明并**终止流程**，待配置完成后**重新发起**。

```json
{
  "mcpServers": {
    "k-hub": {
      "url": "https://block.sankuai.com/mcp/api/knowledge-hub-mcp?kbInfo=435@0.0.0&useRag=true&userToken=d60f7b23-d52e-4cba-9262-d74ad6e2ea2d"
    }
  }
}
```

保存后**重载 MCP 或重启 IDE**，确认 `k-hub` 连接成功。

**执行方（Agent）在未检测到 k-hub 或调用失败时**：不得伪造知识库查询结果；须原样给出上述 JSON 配置说明，提示用户添加并重新发起；不得用 Citadel / 浏览器等方式替代 k-hub 继续执行；**立即终止流程**。

---

## 结果输出目录

本 skill 所有产物写入项目根目录下的 `.spec/` 目录（**执行前先创建**）：

| 产物 | 路径 | 说明 |
|------|------|------|
| 鸿蒙依赖对照表 | `.spec/file/tabelOhPackage-dep.md` | oh-package.json 依赖 × 知识库版本 |
| 通用依赖对照表 | `.spec/file/tabelCommonPackage-dep.md` | package.json 依赖 × 三端兼容版本 |
| 改动清单 | `.spec/result/changelist.md` | 每步变更记录与原因 |
| 去重报告 | `.spec/result/deduplicate.md` | yarn.lock 重复依赖检测结果 |

---

## 🚀 流程执行指南

在 **k-hub 已就绪**的前提下，请按顺序一次性完成全部 6 个步骤，中途不得停顿或等待用户确认（除非步骤文档明确要求澄清）。

每步开始前**先查看对应的 step 文档**（`@` 引用），再执行，再继续下一步。

### 📝 步骤清单

#### 第 1 步：梳理 package.json 和 oh-package.json 中依赖的基本情况

- **描述**：查询 k-hub 知识库标准版本，生成鸿蒙依赖对照表与通用依赖对照表，作为后续步骤的权威依据。
- **Step**：@trade-standard-npm-same-version/steps/01-梳理依赖基本情况.md
- **后续步骤**：执行第 2 步（更新 oh-package.json）

#### 第 2 步：更新 oh-package.json

- **描述**：遍历 `oh-package.json` 中的依赖：三端兼容的从中删除并迁入 `package.json`；仅鸿蒙兼容的保留并对齐标准版本。
- **Step**：@trade-standard-npm-same-version/steps/02-更新oh-package-json.md
- **后续步骤**：执行第 3 步（更新 package.json）

#### 第 3 步：更新 package.json

- **描述**：将 `package.json` 中已有依赖对齐三端兼容版本；步骤 2 迁入的依赖也写入此处。
- **Step**：@trade-standard-npm-same-version/steps/03-更新package-json.md
- **后续步骤**：执行第 4 步（double check 与重复依赖检测）

#### 第 4 步：double check 与重复依赖检测

- **描述**：校验 `package.json` 与 `oh-package.json` 的改动完整性，检测重复依赖，验证 `metro.config.js` 配置。
- **Step**：@trade-standard-npm-same-version/steps/04-double-check与重复依赖检测.md
- **后续步骤**：执行第 5 步（yarn.lock 重复依赖过滤）

#### 第 5 步：yarn.lock 重复依赖过滤

- **描述**：运行 `yarn install` 更新锁文件，使用 `yarn-deduplicate` 与内置检测脚本清理重复依赖，必要时补充 `resolutions`。
- **Step**：@trade-standard-npm-same-version/steps/05-yarn-lock重复依赖过滤.md
- **后续步骤**：执行第 6 步（提示）

#### 第 6 步：提示

- **描述**：提示用户重点关注的内容，输出改造总结，将 `.spec/` 加入 `.gitignore`。
- **Step**：@trade-standard-npm-same-version/steps/06-提示.md
- **后续步骤**：流程完成

---

## ⚠️ 执行规则（必须遵守）

1. **k-hub 不可用时立即终止**：步骤 01 调用 k-hub 失败，给出配置说明后**终止全流程**，不执行步骤 2～6。
2. **严格名称匹配**：查询依赖版本时必须完全匹配包名，禁止模糊匹配。
3. **版本只升不降**：仅当知识库标准版本（semver）严格大于当前版本时才更新；否则保留当前版本并在 changelist 中注明。
4. **不得伪造**：禁止编造知识库内容或凭借猜测填写版本号。
5. **结果落盘**：所有产物必须写入 `.spec/` 对应路径，不得仅口头输出。
6. **顺序执行**：必须按 1→6 依次执行，不得跳步。

---

## 常见问题

| 现象 | 处理 |
|------|------|
| k-hub 不可用 | 按「前置条件」节给出配置说明，终止流程 |
| 依赖未在知识库中 | 不做改动，changelist 中提示用户人工核查 |
| `yarn install` 失败 | 检查 npm registry 配置（`mnpm` / `rnpm`） |
| `yarn-deduplicate` 未安装 | `mnpm install -g yarn-deduplicate` |
| `metro.config.js` 不存在 | 步骤 4 中按模板补充 `resolverMainFields` 配置 |
