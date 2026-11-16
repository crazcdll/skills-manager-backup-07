# 查询模式 —— 精确加载与溯源输出

## 总原则

- `AGENTS.md` 是**唯一路由依据**：先读它确定目标文件，再精确加载；禁止枚举、整读或猜测目录内容
- 资产查询是最高频场景；排查场景 = 资产查询 + 对应 SOP，二者可并行
- 输出必须可溯源（`文件:行号`），未命中必须走未命中模板，禁止编造
- **职责分工**：SKILL.md 的 P1–P5 表只负责区分「查询 or 更新」；本文件（依据 AGENTS.md）负责「查询时加载哪些文件」，两者不重复

## 第 0 步：公共前置（知识库同步）

见 `SKILL.md`「公共前置」：知识库固定目录 `~/.trade-fe-stability-knowledge`，不存在时自动 clone，存在时 `git fetch` 最新。若检出本地落后 `master`，提示用户同步后重查。

## 第 1 步：读路由

```bash
ls ~/.trade-fe-stability-knowledge/AGENTS.md   # 公共前置已保证存在
```

读取 `~/.trade-fe-stability-knowledge/AGENTS.md`，按其中「意图优先级」「加载场景包」执行。

## 第 2 步：意图分类与优先级（P1–P5，来自 AGENTS.md）

| 优先级 | 意图 | 目标目录 | 加载方式 |
|---|---|---|---|
| P1 | 资产查询：页面/Bundle/projectId → 查询参数 | `assets/` | Grep 精确匹配对应业务线文件 |
| P2 | 排查流程：告警、用户问题、变更关联 | `playbooks/` | 按信号类型 Read 对应 SOP |
| P3 | 工具查询：某个平台怎么查 | `guides/` | 精确 Read 对应工具手册 |
| P4 | 经验沉淀：历史事故、踩坑 | `pitfalls/` | Read 对应条目 |
| P5 | 其他 / 库结构了解 | `AGENTS.md` | Read 本文件 |

## 第 3 步：加载场景包（文件数上限）

| # | 场景 | 加载文件 | 上限 |
|---|---|---|---|
| 1 | 资产查询 | `assets/<domain>-assets.md`（按业务线） | 1 |
| 2 | 告警排查 | `playbooks/alert-triage.md` + 对应类型 SOP | 2 |
| 3 | 用户问题排查 | `playbooks/user-issue-sop.md` +（如涉及变更）`playbooks/change-correlation.md` | 2 |
| 4 | 工具查询 | `guides/<tool>.md` | 1 |
| 5 | 变更关联分析 | `playbooks/change-correlation.md` | 1 |
| 6 | 经验查询 | `pitfalls/pitfalls.md` 或 `pitfalls/incidents/<id>.md` | 1 |
| 7 | 综合 / 入口 | `AGENTS.md` | 1 |

## 第 4 步：精确读取规则

### assets/（P1，最高频）

- 业务线判断：餐/综/酒/景 → `food/gc/hotel/travel` 对应文件；无法判断时向用户确认，不猜测
- 用 Grep 精确匹配，禁止整读、轮询全部条目：

```bash
grep -n "asset_id\|bundle\|project_id\|<关键词>" ~/.trade-fe-stability-knowledge/assets/<domain>-assets.md
```

- 命中后读取该条目 YAML block 上下文（条目标题 + 块内容）即可，不读无关条目

### guides/ / playbooks/ / pitfalls/

- 按工具名 / 信号类型 / 标题直接 `Read` 对应文件
- 排查类 SOP 中出现命令时，以对应 `guides/<tool>.md` 为准（AGENTS.md 硬约束 4）

## 第 5 步：组装答案

### 输出格式（结论先行）

```
## 查询结果：<问题摘要>

**结论**：<首句直接回答>

### 命中
- **<字段>**：<值>（来源：`assets/gc-assets.md:28`）
...

### 过期提示
⚠️ 部分内容可能已过期（expires_at: <日期>），请向负责人确认（owner: <mis>）
```

### 规则

1. **结论先行**：首句直接给答案，再展开细节
2. 引用一律带 `文件:行号`（如 `guides/raptor.md:59`），便于溯源与校对
3. `expires_at` 早于当前日期的条目，按上格式追加过期提示（带 `owner`）
4. 参数类答案必须给出**来源**（资产文件 / 堆栈 / 告警链接 / 用户输入），禁止只给值
5. 命中的 asset 只作为查询参数来源（`constraint: reference`），不作为根因证据；如需继续排查，提示可读对应 `playbooks/` SOP

### 未命中输出模板

找不到相关内容时，输出：

```
在知识库中未找到关于「<用户问题>」的内容。
可能原因：
1. 内容尚未录入知识库
2. 属于其他业务线（你的问题属于餐/综/酒/景哪条业务线？）
3. 缺少可匹配的关键词（可提供 asset_id / bundle / projectId / 页面名再试）

已记录缺失信息，未编造任何参数。
如需补全，可走更新模式将内容录入知识库。
```
