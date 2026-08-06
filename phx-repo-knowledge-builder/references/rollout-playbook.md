# Repo Knowledge Rollout Playbook

## 目标

把仓库知识从“口头传承”变成“仓库内可检索、可维护、可交接”的知识系统。

## 设计原则

- 延续 `Agent + business + modules` 主结构
- 强绑定代码路径、接口路径、关键状态和字段
- 先做试点，再扩范围
- 先做导航和主链路，再做长尾补充
- 文档必须进入日常研发流程
- 复杂仓库默认不要停留在试点版
- 如果本地有同域成熟知识库，优先拿来做 benchmark
- 有 benchmark 时以 benchmark 为最低线，目标尽量做到 parity-plus

## 推荐结构

```text
knowledge/
  README.md
  Agent.md
  onboarding/
  business/
  modules/
  faq/
  adr/
  _templates/
```

## 各目录职责

### README.md

- 知识库首页
- 解释这套知识库是给谁看的
- 给出阅读路径和快速入口

### Agent.md

- 全局索引页
- 汇总模块、接口、字段、状态、跨端差异
- 负责“快速定位”

### onboarding/

- 新同学阅读路径
- 仓库地图
- 第一次改需求怎么入手

### business/

- 页面主链路
- Store 结构
- 接口
- 路由
- 公共工具
- 性能和主流程知识

### modules/

- 核心模块拆解
- 组件树
- 接口与字段
- 交互逻辑
- Store 连接
- 跨端差异

### faq/

- 高频问题
- 排障入口

### adr/

- 设计决策沉淀
- 历史取舍与约束

## 试点建议

第一阶段只覆盖：

- 1 个仓库
- 1 个核心页面
- 3 到 5 个核心模块
- 1 条最关键主链路

这适用于简单仓库，或用户明确说“先做试点”。

如果仓库复杂，应在试点完成后继续扩到标准版，不要把试点版包装成最终版。

## 最小可落地版本

```text
knowledge/
  README.md
  Agent.md
  onboarding/0-reading-path.md
  business/main-page.md
  business/api-interfaces.md
  business/store-state.md
  modules/<core-module>.md
  faq/troubleshooting.md
```

## 复杂仓库标准版

```text
knowledge/
  README.md
  Agent.md
  onboarding/
    0-reading-path.md
    1-repo-map.md
  business/
    main-page.md
    store-state.md
    api-interfaces.md
    routing.md
    utils-tools.md
    performance.md
    modules-desc.md
  modules/
    <6+ core modules>.md
  faq/
    troubleshooting.md
```

## 统一元信息

建议每篇文档头部都包含：

- 文档更新时间
- Owner
- 适用范围
- 关联代码
- 关联文档

## 维护机制

建议把下面检查项接入 PR 模板：

```md
## Knowledge Check

- [ ] 本次改动不影响 knowledge
- [ ] 已同步更新相关 knowledge 文档
- [ ] 已新增缺失的 knowledge 文档
```

## 推进顺序

1. 建结构和模板
2. 补首页和索引
3. 补主链路文档
4. 补 3 到 5 个核心模块
5. 补 onboarding
6. 补 FAQ
7. 补 ADR
8. 接入维护机制

## 复杂仓库额外步骤

在第 4 步和第 5 步之间，增加两件事：

1. 对标本地成熟 benchmark，补齐 `routing`、`utils-tools`、`performance`、`modules-desc`
2. 把至少一个复杂页面从“页面总览”继续拆到“子模块文档”

## 有 benchmark 时的额外步骤

1. 先运行文件级对比脚本
2. 把 benchmark 的高价值文档列成缺口清单
3. 先追平，再做超出项
4. 结束时明确说明当前结果是低于、持平还是高于 benchmark

## 生成后审阅

在初始化和首轮生成后，不要马上宣布完成，必须再做一次“内容审阅”：

1. 看生成的文档是否都贴合当前业务
2. 删除或合并不合理的文档
3. 把 benchmark 的模块名转换成当前仓库自然的模块边界
4. 确保最终结果是“结构对齐”，不是“复制对标仓库”

如果 benchmark 非常关键，建议把它固化成 profile，一起纳入 skill：

- source: 真实 benchmark 仓库 / 分支
- profile: 固定结构清单

优先以 profile 做稳定验收，再以 source 做抽样校验。

## 结束前验收

结束前至少回答 4 个问题：

1. 新同学是否能在 30 分钟内建立主链路认知
2. 需求改动是否能在 5 分钟内定位到入口文件和核心模块
3. 排障是否有明确入口
4. 当前结果是试点版、标准版还是成熟版
