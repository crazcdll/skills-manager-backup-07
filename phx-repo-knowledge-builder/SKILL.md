---
name: phx-repo-knowledge-builder
description: 为任意代码仓库评估、初始化和升级 `knowledge/` 知识库。适用于“建设仓库知识库”“初始化 knowledge 目录”“按 Agent + business + modules 结构落地知识库”“评估现有 knowledge 并补齐 README/onboarding/faq/adr/维护机制”“对标成熟知识库补齐 routing/performance/utils/modules-desc 与模块深挖”“以 benchmark 仓库为下限并争取优于对标仓库”等场景。

metadata:
  skillhub.creator: "lvxiaobing"
  skillhub.updater: "lvxiaobing"
  skillhub.version: "V2"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "26556"
  skillhub.high_sensitive: "false"
---

# Repo Knowledge Builder

为业务仓库建设可维护的工程知识库。这个 skill 继承 `Agent + business + modules` 的结构化思路，同时补齐 `README`、`onboarding`、`faq`、`adr` 和维护机制，目标是让知识库既能快速导航，也能长期维护。

## 何时使用

在以下场景使用这个 skill：

- 用户要为某个仓库新建 `knowledge/`
- 用户要按统一标准补齐现有知识库
- 用户要评估现有 `knowledge/` 的成熟度并给出整改方案
- 用户要做知识库试点，希望先产出最小可落地版本
- 用户要把知识库建设方法沉淀成统一规范

如果用户只是问单个模块怎么实现，不需要启用这个 skill。

## 核心能力

1. 评估现有知识库质量，给出评分、缺口和优先级
2. 初始化 `knowledge/` 目录和标准模板
3. 根据仓库复杂度自动选择最小骨架或标准骨架
4. 指导补齐高价值文档：`README`、`Agent`、`business`、`modules`
5. 对标同域成熟知识库，补齐缺失的深度与结构
6. 明确把 benchmark 仓库作为最低验收线，并争取在导航性、模块覆盖、维护性上超出 benchmark
7. 生成后审阅实际产出的 markdown 内容，删除不贴业务的文档，避免 copy benchmark
8. 补齐长期能力：`onboarding`、`faq`、`adr`、PR 维护约定

## 工作流

严格按顺序执行，除非用户明确只要其中一步。

### Step 0: Git 分支准备

无论用户是否明确提到分支，开始建设知识库前都必须先检查一次 git 状态。

Step 0 分两层：

1. 永远执行的检查
2. 条件触发的切分支

#### 0.1 永远执行的检查

开始任何 `knowledge/` 初始化或补齐工作前，必须先执行：

```bash
git status --short
git branch --show-current
```

并在心里明确 3 件事：

- 当前是不是 git 仓库
- 当前分支是不是 `feature/*`
- 工作区是否有未提交改动

如果当前已经在合适的 `feature/*` 分支上，且用户没有要求切到别的分支，那么只需把这个判断作为上下文记录下来，可以直接继续后续知识库工作。

#### 0.2 条件触发的切分支

如果用户明确要求“基于 `master` 切到一个新分支再建设知识库”，先完成分支准备，再进入知识库工作流。

如果用户没有明确指定分支，但当前分支不是 `feature/*`，则默认也应做分支准备，而不是直接在 `master`、`release/*` 或其他长期分支上落知识库改动。

分支命名要求：

- 知识库建设分支必须使用 `feature/` 前缀
- 如果用户只给了裸名字，例如 `add_knowledge`，自动规范化为 `feature/add_knowledge`
- 如果用户给了完整分支名，例如 `feature/add_knowledge`，直接使用

默认策略：

- 如果工作区存在未提交改动，先 `stash`
- 再切到 `master`
- 再创建或切换到用户指定的 `feature/<name>`
- 完成分支切换后，再开始建设 `knowledge/`

如果用户没有指定分支名，而当前又不在 `feature/*` 分支上，则默认分支名可以使用：

- `feature/<repo-name>-knowledge`

例如仓库名是 `filter`，默认可使用：

- `feature/filter-knowledge`

建议顺序：

1. 检查当前仓库是否是 git 仓库
2. 检查当前分支、工作区是否干净、是否存在未提交改动
3. 如果工作区存在未提交改动：
   - 先执行 `git stash push -u`
   - 在回复中明确告诉用户已经 stash，并保留 stash 标识
4. 如果当前分支已经是合适的 `feature/*` 且用户未要求切换：
   - 记录该事实
   - 直接继续知识库工作
5. 如果用户明确指定从 `master` 出发：
   - 先切到 `master`
   - 再创建或切换到用户指定的 `feature/<name>`
6. 如果用户未指定分支，但当前不在 `feature/*`：
   - 默认切到 `master`
   - 创建或切换到 `feature/<repo-name>-knowledge`
7. 完成分支切换后，再开始初始化或补齐 `knowledge/`

推荐命令示例：

```bash
git status --short
git branch --show-current
git stash push -u -m "repo-knowledge-builder: before knowledge setup"
git checkout master
git checkout -b feature/your-branch-name
```

如果目标分支已存在：

```bash
git checkout feature/your-branch-name
```

注意事项：

- 切分支前必须先看工作区状态，避免用户已有未提交改动导致冲突
- 即使最终不切分支，也必须先做 branch/status 检查
- 如果工作区有改动，默认先 `stash`，不要直接带着改动切到新分支
- `stash` 后要在回复里告诉用户 stash 已创建，建议带上 `stash@{n}` 或命令输出中的标识
- 新分支名统一使用 `feature/` 前缀，不接受其他前缀作为默认规范
- 不要使用破坏性 git 命令
- 如果用户已经在目标分支上，不需要重复创建
- 如果用户明确不希望 stash，则不要擅自执行，改为先说明风险

### Step 1: 检查仓库现状

先检查目标仓库是否已有 `knowledge/`：

- 若没有，走“初始化”路径
- 若已有，先判断是“轻量补齐”还是“结构升级”

至少确认这些信息：

- 仓库根目录
- 是否已有 `knowledge/`
- 核心页面或核心业务链路是什么
- 先做试点还是一次性铺开
- 是否需要先切换到 `master` 派生的 `feature/<name>`

同时必须判断仓库复杂度。以下信号命中 2 项及以上，视为“复杂仓库”：

- 存在多个页面入口或多个 `AppRegistry.registerComponent`
- `pages/` 下有 3 个及以上一级页面目录
- `store/reducers/` 下有 5 个及以上业务切片
- 同时存在 `service/`、`datasource/`、`utils/` 等分层
- 存在明显多端差异、地图链路、预加载/预渲染或复杂 AB 分支

如果本地存在同域成熟知识库，优先把它作为 benchmark。至少对齐：

- `business/` 的目录完整度
- `Agent.md` 的索引密度
- `modules/` 的拆分颗粒度
- 接口 / 字段 / Store / 跨端差异的绑定深度

对齐 benchmark 时，优先对齐“能力组”，不要机械复制文件名。至少检查：

- 入口与初始化
- 页面壳与覆盖物
- 头部或顶部摘要区域
- 主列表 / 货架 / 主结果区
- 筛选 / 导航 / 切换能力
- 弹层 / bullet / dialog
- 下半区内容或关联推荐
- 地图 / POI / 位置联动（如果业务存在）

特别注意：

- benchmark 只用于约束整体结构、成熟度和模块拆分能力
- 不要把 benchmark 当成“文档名清单”去复制
- 不要为了追平 benchmark 数量而生成与当前业务无关的文档
- 每一篇生成出来的 `.md` 都必须能回答“它对应当前仓库哪块真实业务”

如果已知 benchmark 路径，必须显式做一次对比，优先使用：

```bash
python3 <skill_dir>/scripts/compare_knowledge.py \
  --repo /path/to/repo \
  --benchmark /path/to/benchmark_repo
```

如果 benchmark 是固定分支且希望避免漂移，优先使用 benchmark profile：

```bash
python3 <skill_dir>/scripts/compare_knowledge.py \
  --repo /path/to/repo \
  --benchmark-profile <skill_dir>/references/benchmarks/rn_hotel_poidetail-feature-m-hub-update.json
```

对比结果必须至少覆盖：

- `knowledge/` 文件总量
- `business/` 子目录完整度
- `modules/` 文档数量
- benchmark 中存在而当前仓库缺失的高价值文档
- 当前仓库相对 benchmark 的差距和目标补齐清单
- 生成后的文档里，哪些保留、哪些应该裁剪或合并

### Step 1.5: Benchmark 对齐

如果存在 benchmark 仓库，不要只把它当“参考”。必须遵守下面规则：

- benchmark 是最低线，不是灵感来源
- 当前仓库的 `business/` 文档完整度不能低于 benchmark
- 当前仓库的 `modules/` 颗粒度和能力覆盖不能弱于 benchmark
- `modules/` 的具体数量根据当前仓库真实业务来定，不要求机械达到 benchmark 的文件数
- 如果仓库复杂度相近，建议整体模块覆盖和可定位性做到 benchmark 的 parity-plus，而不是文档名 parity-plus
- 如果当前仓库没有 benchmark 中某些业务模块，不要求机械对齐文件名，但要求在等价模块层面补足
- 最终回复中必须说明：
  - benchmark 是谁
  - 当前结果与 benchmark 相比是持平、低于还是高于
  - 还差哪些点

如果你已经知道一个长期使用的标杆仓库，优先把它同时固化成 benchmark profile。推荐模式：

- benchmark source
  - 本地仓库或固定分支
- benchmark profile
  - 从 benchmark source 抽出的稳定结构清单

默认推荐 benchmark：

- `rn_hotel_poidetail@feature/m-hub-update`
- profile: `references/benchmarks/rn_hotel_poidetail-feature-m-hub-update.json`

### Step 2: 选择落地模式

优先采用下面两种模式之一：

- `auto`
  - 默认模式
  - 简单仓库走 `minimum`
  - 复杂仓库自动升级到 `standard`
- `minimum`
  - 适合试点
  - 只创建最小可落地版本
- `standard`
  - 适合正式建设
  - 创建完整骨架

默认使用 `auto`。

只有在下面情况才允许最终停在 `minimum`：

- 用户明确说“先做试点”
- 仓库本身简单
- 当前时间窗口很紧，且你在回复里明确说明这是“试点版”

如果仓库被判定为复杂仓库，而用户说的是“构建本仓库知识库”“帮我建设知识库”“补齐仓库 knowledge”，默认目标应至少达到 `standard` 级别，而不是停在 `minimum`。

### Step 3: 初始化目录和模板

优先使用捆绑脚本初始化骨架：

```bash
python3 <skill_dir>/scripts/init_knowledge.py --repo /path/to/repo --mode auto
python3 <skill_dir>/scripts/init_knowledge.py --repo /path/to/repo --mode minimum
python3 <skill_dir>/scripts/init_knowledge.py --repo /path/to/repo --mode standard
```

若用户已经指定了首批核心模块，可一并生成模块文档：

```bash
python3 <skill_dir>/scripts/init_knowledge.py \
  --repo /path/to/repo \
  --mode auto \
  --module goods-shelf \
  --module poi-header
```

脚本默认不覆盖已有文件；只有在明确确认或你确信需要覆盖时，才使用：

```bash
python3 <skill_dir>/scripts/init_knowledge.py --repo /path/to/repo --mode standard --force
```

### Step 4: 先补最高价值内容

初始化后，不要试图一次写完整个仓库。优先补下面这些内容：

1. `knowledge/README.md`
2. `knowledge/Agent.md`
3. `knowledge/business/main-page.md`
4. `knowledge/business/api-interfaces.md`
5. `knowledge/business/store-state.md`
6. 3 到 5 篇核心 `knowledge/modules/*.md`
7. `knowledge/onboarding/0-reading-path.md`
8. `knowledge/faq/troubleshooting.md`

如果用户时间紧，只要完成前 6 项，也能形成可用试点。

但对于复杂仓库，这一步做完还不够。复杂仓库在首轮交付前，至少还要补：

9. `knowledge/onboarding/1-repo-map.md`
10. `knowledge/business/routing.md`
11. `knowledge/business/utils-tools.md`
12. `knowledge/business/performance.md`
13. `knowledge/business/modules-desc.md`
14. 至少 6 篇模块文档；如果某个页面目录下已有明显的 `container/` 分层，不能只写 1 篇总文档

如果本地存在成熟 benchmark，模块颗粒度至少要接近 benchmark 的 70% 到 80%，不要只停留在“页面级总文档”。

如果用户明确要求“和对标仓库一致，最好优于他们”，则不能接受 70% 到 80% 这种试点颗粒度，目标直接提升为：

- `business/` 目录不低于 benchmark
- `modules/` 的能力覆盖不低于 benchmark
- 在 onboarding、FAQ、ADR、维护机制中至少有 1 到 2 个维度优于 benchmark

### Step 5: 用真实代码填文档

这个 skill 的模板只负责起骨架，真正有价值的部分必须基于仓库代码和实际目录填写。

填写时遵守这些规则：

- 必须绑定真实代码路径
- 必须绑定真实接口路径、状态字段、组件入口
- 不写空泛概念，不抄业务背景废话
- 优先写“如何定位和修改”，其次才是“模块是什么”

对于关键文档，至少满足下面约束：

- `Agent.md`
  - 必须有模块索引表
  - 必须有核心接口速查
  - 必须有关键状态或 Store 速查
- `business/main-page.md`
  - 必须写清入口注册、初始化链路、关键入参、主要副作用
- `business/store-state.md`
  - 必须写清 reducer 切片职责和关键字段
- `business/api-interfaces.md`
  - 必须写清请求入口、参数转换、关键接口动作
- `modules/*.md`
  - 必须写主容器路径
  - 必须写接口与数据来源；如果无独立接口，要明确写“无独立接口，数据来自 X”
  - 必须写关键字段
  - 必须写交互逻辑
  - 必须写 Store 连接或局部状态来源
  - 必须写至少 1 条易错点或排障点

如果 benchmark 的模块文档包含这些内容，也应尽量对齐甚至超出：

- 组件树结构
- 接口参数或字段路径示例
- 关键 Redux / saga / action 速查
- 跨端差异速查表
- 页面从上到下的模块编排顺序

如果目录结构不同，优先保证“等价模块能力”对齐，而不是“文件名”对齐。

### Step 5.5: 生成结果审阅与裁剪

初始化和首轮生成之后，必须回头检查已经生成的 markdown 内容，而不是只看目录是否齐了。

至少执行下面 4 件事：

1. 看每篇文档是否绑定了当前仓库真实代码路径
2. 看文档名和内容是否真的对应当前业务模块
3. 删除、合并或重命名那些只是为了“对标”而生成、但当前仓库并不需要的文档
4. 在最终回复里说明：
   - 哪些文档是直接保留的
   - 哪些文档是按业务改名或拆分的
   - 哪些 benchmark 文档在当前仓库中没有等价物，因此没有照搬

这里的原则是：

- 结构对齐
- 能力对齐
- 内容按实际业务生成
- 明确禁止 copy benchmark

### Step 6: 补长期维护能力

如果用户要把知识库做成长期资产，继续补：

- `knowledge/onboarding/`
- `knowledge/faq/`
- `knowledge/adr/`
- PR 模板中的 knowledge 检查项

复杂仓库在补长期能力前，先做一次自检评分：

- 按 `references/evaluation-rubric.md` 自评
- 说明当前结果属于：
  - 试点版
  - 标准版
  - 成熟版
- 如果自评低于 8 分，不要把结果表述成“完整建设完成”
- 如果 benchmark 存在且当前结果仍低于 benchmark，不要表述成“已完成对标”

建议在 PR 模板中加入：

```md
## Knowledge Check

- [ ] 本次改动不影响 knowledge
- [ ] 已同步更新相关 knowledge 文档
- [ ] 已新增缺失的 knowledge 文档
```

## 输出标准

一个合格的仓库知识库至少要满足：

- 有清晰首页和总索引
- 有主链路文档
- 有模块级文档
- 新人知道先看什么
- 线上排障有入口
- 文档有 Owner、更新时间、适用范围

对于复杂仓库，交付前再加 4 条硬门槛：

- `business/` 中必须存在 `routing.md`、`utils-tools.md`、`performance.md`、`modules-desc.md`
- `modules/` 至少 6 篇，且不能全是页面总览
- `Agent.md` 必须能起到“5 分钟定位代码入口”的作用
- 结束时必须给出当前成熟度判断，而不是只说“已完成”

如果 benchmark 存在，再加 3 条硬门槛：

- benchmark 中的关键 `business/` 文档不能在当前仓库缺失
- `modules/` 能力覆盖弱于 benchmark 时，默认不能宣称“已对齐”
- 如果声称“优于 benchmark”，必须明确多出的维度，例如 onboarding、FAQ、ADR、维护机制或模块颗粒度

详细评分标准见：

- `references/evaluation-rubric.md`
- `references/benchmarking.md`

建设思路和目录职责见：

- `references/rollout-playbook.md`

## 推荐目录结构

标准结构如下：

```text
knowledge/
  README.md
  Agent.md
  onboarding/
    0-reading-path.md
    1-repo-map.md
    2-first-task-guide.md
  business/
    main-page.md
    store-state.md
    api-interfaces.md
    routing.md
    utils-tools.md
    performance.md
    modules-desc.md
  modules/
    <core-module>.md
  faq/
    common-questions.md
    troubleshooting.md
  adr/
    0001-knowledge-structure.md
    0002-core-architecture-choice.md
  _templates/
    business-template.md
    module-template.md
    faq-template.md
    adr-template.md
```

## 模板资源

模板文件位于：

- `assets/templates/README.template.md`
- `assets/templates/Agent.template.md`
- `assets/templates/onboarding-0-reading-path.template.md`
- `assets/templates/onboarding-1-repo-map.template.md`
- `assets/templates/onboarding-2-first-task-guide.template.md`
- `assets/templates/business-main-page.template.md`
- `assets/templates/business-api-interfaces.template.md`
- `assets/templates/business-store-state.template.md`
- `assets/templates/business-routing.template.md`
- `assets/templates/business-utils-tools.template.md`
- `assets/templates/business-performance.template.md`
- `assets/templates/business-modules-desc.template.md`
- `assets/templates/module.template.md`
- `assets/templates/faq-common-questions.template.md`
- `assets/templates/faq-troubleshooting.template.md`
- `assets/templates/adr-0001-knowledge-structure.template.md`
- `assets/templates/adr-0002-core-architecture-choice.template.md`
- `assets/templates/business-template.md`
- `assets/templates/faq-template.md`
- `assets/templates/adr-template.md`

## 评估现有知识库时的重点

优先看下面 6 件事：

1. 有没有首页和索引
2. 有没有主链路文档
3. 有没有模块级文档
4. 文档是否绑定代码和接口
5. 有没有 onboarding 和 FAQ
6. 有没有维护机制

不要把“文档数量多”误判成“知识库建设好”。

## 失败处理

如果遇到以下情况，按下面方式处理：

- 仓库没有明显主链路
  - 先选一个核心页面做试点，不要试图覆盖全仓
- 仓库代码太旧或目录混乱
  - 先做 `README + Agent + main-page + 3 个核心模块`
- 文档已经存在但风格混乱
  - 不要全量重写，先补首页、索引、模板和元信息
- 用户希望一步到位写全
  - 提醒先试点，先覆盖最值钱的部分

## 完成后应交付什么

至少交付其中一种：

- 一套可直接落地的 `knowledge/` 骨架
- 一份基于真实仓库的知识库整改结果
- 一份现状评分和补齐优先级建议

如果用户要求实战落地，默认不仅给建议，还要直接创建目录和模板文件。

## 分支工作示例

当用户说：

- “用这个 skill 帮我在某个仓库里从 master 拉一个 feature 分支，然后开始建设 knowledge”
- “先切到 feature/add_knowledge，再按试点方案初始化知识库”
- “先把我当前改动 stash，再从 master 开 feature 分支建设知识库”

默认执行顺序应为：

1. 检查 git 状态
2. 如有未提交改动，先执行 `git stash push -u`
3. 切到 `master`
4. 创建或切到 `feature/<name>`
5. 初始化 `knowledge/`
6. 基于真实代码补首页、索引和主链路文档
