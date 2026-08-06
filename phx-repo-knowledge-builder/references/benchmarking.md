# Knowledge Benchmarking Guide

## 目标

当仓库存在可参考的成熟知识库时，benchmark 不是“灵感来源”，而是最低交付线。

## 使用时机

在以下场景优先启用 benchmark：

- 用户明确提到“对标某个仓库”
- 同业务域已有成熟 `knowledge/`
- 目标仓库复杂度和 benchmark 接近
- 用户希望做到“一致甚至更好”

## 基础原则

### 0. 最强约束模式：source + profile 双层基线

如果 benchmark 很重要，推荐不要只依赖“某个仓库分支”，而是采用双层基线：

- source
  - 真实 benchmark 仓库 / 分支
- profile
  - 从 source 抽取的稳定结构清单

这样做的好处：

- source 保证 benchmark 有真实上下文
- profile 保证校验稳定，不会因为 benchmark 日常迭代而漂移

如果只能二选一：

- 约束更强、更稳定：profile
- 更新更及时、更贴近真实：source

最佳实践仍然是二者同时保留。

### 1. 先对齐，再追求更好

先保证：

- `business/` 关键文档不缺
- `Agent.md` 的索引密度不弱于 benchmark
- `modules/` 的能力覆盖和颗粒度不弱于 benchmark

再补强：

- onboarding
- FAQ
- ADR
- 维护机制

### 2. 对齐的是能力，不是文件名

如果当前仓库业务形态与 benchmark 不完全相同，不要求机械复制文件名；要求对齐的是：

- 导航能力
- 主链路覆盖
- 模块拆分能力
- 代码映射深度
- 排障入口

实际操作中，benchmark profile 应优先保存两类信息：

- stable floor
  - `business/` 必备文档
  - `Agent.md` 必备能力
  - `modules/` 最少数量
- semantic capability groups
  - 例如“入口与初始化”“头部区域”“核心列表/货架”“筛选能力”“弹层与覆盖物”“下半区模块”“地图或关联推荐”

不要只保存 `modules/foo.md` 这种纯文件名清单，否则在目录结构不同的仓库里容易误导产出。

### 2.5 先看生成内容，再决定保留哪些文档

知识库建设不是“初始化骨架 + 补几个文件名”就结束。必须审阅已经生成的 markdown 内容：

- 文档是否对应当前仓库真实业务
- 文档名是否自然
- 内容是否只是 benchmark 的影子

如果某篇文档只是为了凑 benchmark 结构而存在，应删除、合并或改名。

### 3. 复杂仓库追求 parity-plus

建议目标不是 parity，而是 parity-plus：

- `business/`：不低于 benchmark
- `modules/`：能力覆盖不低于 benchmark，数量由实际业务决定
- `onboarding/faq/adr`：至少 1 个维度优于 benchmark

## 推荐流程

1. 用 `compare_knowledge.py` 先做文件级对比
2. 标出 benchmark 中的高价值文档
3. 再看 semantic capability groups 是否已覆盖
4. 先补缺失的 `business/`
5. 再补 `modules/` 的颗粒度差距
6. 审阅已生成文档内容，删掉不贴业务的文档
7. 最后补优于 benchmark 的部分

推荐命令：

```bash
python3 scripts/compare_knowledge.py --repo /path/to/repo --benchmark /path/to/benchmark_repo
python3 scripts/compare_knowledge.py --repo /path/to/repo --benchmark-profile references/benchmarks/your-profile.json
```

## 高价值文档优先级

benchmark 中如果有下面文档，默认视为高价值：

- `business/main-page.md`
- `business/store-state.md`
- `business/api-interfaces.md`
- `business/routing.md`
- `business/utils-tools.md`
- `business/performance.md`
- `business/modules-desc.md`
- `Agent.md`

## 结果表达建议

交付时建议明确写：

- benchmark：谁
- 当前状态：低于 / 持平 / 高于
- 已超出的维度：哪些
- 尚未对齐的维度：哪些

## 不应出现的情况

- benchmark 明显更完整，但回复里仍然说“知识库已完整建设”
- benchmark 有 10 篇以上模块文档，当前只有 3 到 5 篇仍声称“已对标”
- benchmark 有完整 `business/`，当前缺 `routing` / `performance` / `utils-tools`
- 目标仓库结构明显不同，却机械照抄 benchmark 的模块命名
- 生成了一批文档，但其中不少并不对应当前仓库真实业务
