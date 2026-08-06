# Step 3 — 逐页逐文件覆盖

> **阻塞级别**：🔴 阻塞（改动清单未 100% 覆盖则不允许退出）

## 输入

Step 2 确认的页面清单 + 改动清单 + 需求清单。

## 过程

> ⚠️ 禁止一次性生成所有文件后结束！涉及多个 DUO 页面时必须对每个页面分别执行。

### 执行流程

```
For each page in 标记为「需改造」的 DUO 页面：
  L3.1: 改动项 → 文件映射，输出映射表
  L3.2: 按文件分组，确定每个文件需要覆盖的改动项
  L3.3: 按下方"7 步固定顺序"逐文件生成/修改代码（Step 3.1 ~ Step 3.7）
  L3.4: 该页面所有文件完成后，检查改动清单是否有待处理项
  L3.5: 如有遗漏项，立即补充实现
  L3.6: 输出该页面的覆盖报告
End For

最终回查：所有页面的改动清单全部覆盖
```

### 改动项 → 文件映射规则（MUST）

开始编码前，必须先输出映射表：

| 改动项 | 涉及文件 | 覆盖状态 |
|--------|---------|---------|

### 7 步固定执行顺序

| 步骤 | 文件 | 规则文件 | 触发条件 |
|------|------|---------|---------|
| 3.1 | pageBuildConfig.json | must-comply/R1-pageBuildConfig.md | 涉及页面配置、URL 参数、默认参数 |
| 3.2 | dataSourceMap.groovy | must-comply/R2-dataSourceMap.md + R-common-expression.md | 涉及接口入参、数据源、错误处理 |
| 3.3 | constData.groovy | must-comply/R3-constData.md | 涉及静态常量、埋点配置、lx 参数（⚠️ constData 只能在 struct 中使用，不可用于 reqProps） |
| 3.4 | struct.groovy | must-comply/R4-struct.md + R-common-events.md + case-study/CS-style.md | 涉及组件 props、events、样式、埋点 lx |
| 3.5 | logics.groovy | must-comply/R5-logics.md | 涉及生命周期回调、埋点、导航跳转 |
| 3.6 | dependencies.json + componentsMap.json | must-comply/R6-dependencies.md | 涉及新增/升级物料（无变更可跳过） |
| 3.7 | scripts/* | 无 | 涉及构建定制、MRN 配置、首屏模块路径（均为可选文件） |

### Step 3.6-pre — 本地物料发布先置门禁

> ⚠️ 历史踩坑：Agent 把本地未发布的版本号直接写入协议，CDN 拉取 404。

只要本次改动涉及"本地正在开发的物料"（packages/*/src/* 级别的修改），必须等物料真正发布到 Yooz 平台后，再通过 CLI/MCP 工具拉取实时版本信息，才能落到协议。

**执行流程**：

```
子步骤 a：识别是否包含本地物料改动
  → 如果否 → 跳过此门禁，进入 Step 3.6-gate
  → 如果是 → 列出所有本地改动的物料包名

子步骤 b：确认 demo 自测已完成
  → 未确认则 MUST 停止，交回给用户

子步骤 c：确认物料已发布到 Yooz
  → 需要以下证据之一：
    ① 用户显式确认"物料 X@Y.Z.W 已发布到 Yooz"
    ② CLI/MCP 查询 latestVersion >= 本地 package.json version
  → 无证据 → MUST 停止，记录"待物料发布"

子步骤 d：通过后才进入 Step 3.6-gate
```

### Step 3.6-gate — 物料 ID 查询与验证门禁

> ⚠️ 历史踩坑：Agent 自行编造 materialId（写成 600 而非 1332），跳过了物料查询步骤。

**执行流程**：

```
子步骤 A：列出待查询物料清单
  → 输出表格：序号 | npm包名 | 用途 | materialId(待查) | 版本id(待查)

子步骤 B：逐个调用 CLI/MCP 查询（MUST）
  → 优先级：CLI > MCP > materials.json > 标记不可用
  → CLI：duo yooz-read-detail -n "<包名>" 或 duo yooz-getby-packagename -p "<包名>"
  → MCP：mcp_tool_duo_ai_mcp_server_read_yooz_material_detail / get_material_by_package_name

子步骤 C：输出查询结果表（MUST，展示给用户）
  | npm包名 | materialId | 版本id | npmVersion | 数据来源 |

子步骤 D：用户确认后才可写入（MUST）
```

### 完成后的强制回查（MUST）

```
1. 列出改动清单中所有改动项的状态
2. 检查是否有待处理项
3. 如有遗漏 → 立即补充到对应文件中
4. 如无遗漏 → 输出「改动清单 100% 覆盖」确认
```

## 输出

- 每个页面的协议子文件（已修改/生成）
- 改动清单覆盖报告（100% 覆盖）
