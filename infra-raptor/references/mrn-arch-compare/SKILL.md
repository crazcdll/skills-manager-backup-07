---
name: mrn-arch-compare
version: "1.0.0"
description: >
  MRN 包新老架构性能数据对比：按用户给出的 bundle 包名，查询同一包在 MRN 新架构（arch_type=new）与老架构（arch_type=old）下的
  C/F/R 分数、RCF 总分、秒开率、页面加载 PV、C 首屏耗时 TP90，输出新老架构对比表格与胜率洞察，并附官方看板链接。
  触发方式：用户提到「对比 MRN xx 包新老架构性能数据 / 新老架构 RCF 对比 / 新架构 vs 老架构」等表述。
  注意：这是新老架构【对比查询】，不是 RCF 波动根因分析（那个走 rcf-raptor-anylisize），也不是简单查数据（走 raptorfe-allquery）。

metadata:
  skillhub.creator: "huangwenqing05"
  skillhub.updater: "huangwenqing05"
---

# MRN 新老架构性能对比查询

## 🔧 前置依赖

本 skill 使用 `raptorfe` CLI（内置鉴权，无需手动传 token）。

> **🌏 环境适配（境内 / 境外）**：下文默认 `raptorfe`（境内）。若用户提到「海外 / 境外 / overseas」或给出 `raptor.mws.keetapp.com` 链接，所有命令一律改用 `raptorfeov`（模块、子命令、参数完全一致），页面链接同步换成 keetapp 域名。完整约束见父技能 `SKILL.md` 的「环境识别」章节。
>
> **前置预检（每次激活时执行）：**
> ```bash
> command -v raptorfe >/dev/null 2>&1 || npm install -g @mtfe/raptorfe-cli @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
> ```

---

## 📖 背景：MRN 新老架构与数据口径

MRN 业务包按渲染架构分两类（维度 `arch_type`）：

- `new`：新架构；`old`：老架构。响应中还会出现 `scout.others` / `scout.null` 等哨兵分组——**必须过滤掉，只取 new/old 两行**，否则表格出现脏数据。
- RCF 总分 = R 分数 × 0.2 + C 分数 × 0.5 + F 分数 × 0.3（与看板 `RCF_WEIGHTS` 一致）。

四组查询与看板（`raptor.mws.sankuai.com/mrn-dashboard/layout/arch-compare`，源码 `bfe/cat-fe-static`）完全同构：

| 组 | base 指标 | 附带复合指标 | 请求方式 | 能拿到的数据 |
|---|---|---|---|---|
| C | `98466`（ffp_mrn，atom） | `c17949`（C 分数）、`c10296`（秒开率） | **单请求 + `--tag-names arch_type`** | C 分数、秒开率、首屏耗时 TP90、totalCount |
| PV | `225015`（MRNPageLoadSuccess，atom） | 无 | 单请求 + `--tag-names arch_type` | PV（`sum` 字段，折算全量） |
| F | `mobile.fps.scroll.avg.v2.n`（命名 atom） | `c17952`（F 分数） | **按架构拆 2 个请求**（filters 里 `arch_type:["new"/"old"]`） | F 分数 |
| R | `metricx.response.duration`（命名 atom） | `c17948`（R 分数） | **按架构拆 2 个请求** | R 分数 |

**为什么 C/PV 单请求、F/R 拆请求（重要，勿「优化」掉）：**

1. 看板源码注释实锤：命名 atom 指标（F/R）**带 tagNames 会丢 TP 分位**，所以 F/R 只能走 filters 拆分路径。
2. CLI 的 `dimension-analyse --tag-names` 为必填参数——F/R 拆分请求统一传 `--tag-names arch_type`（与 filters 的 arch_type 值一致，响应仍是单行，不影响结果；实测 2026-11-26）。
3. **F/R 的 TP 分位数在 CLI 通道拿不到真实值**：走 `get-trend` 拿到的 TP90 是聚合路径假 TP（三个不同 bundle 返回几乎相同的 TP90，实锤 2026-11-26：R TP90 48.02/48.05/48.02，F TP90 24.85/24.83/24.88，而 avg 各不相同）——看板靠请求体里的 `currentMrnOrg`（CLI 未暴露）才能按 bundle 算真实 TP。**因此 F/R 的 TP 列裁掉不输出**，C 组 TP90（走 98466 分组路径，与看板同路径）正常输出。
4. **PV 口径**：看板「页面加载次数」显示的是 `sum` 字段（折算全量，如 5.755M），不是 `totalCount`（采样数，如 180140）；输出用 `sum`，除以 1e6 保留 1 位小数写成 M（<1e6 用 K）。

**半截响应（已知坑，源码注释记录过被误判成功）**：后端偶发返回缺分数/PV 的不完整响应。**输出前必须校验**：每个 bundle 的 new/old 两行、C/F/R 分数与 PV 齐全；缺项时重试一次（实测重试即恢复），仍缺则显式报「该 bundle 数据不完整」并标注缺哪项，**不要输出残表冒充完整结果**。

---

## 🎯 适用场景

**适用**：
- 用户给出 MRN 包名，要求对比新老架构性能：如「对比 MRN rn_hotel_rn-hotel-mainlist 包新老架构性能数据」「xx 包新架构 RCF 比老架构怎么样」
- 用户发 arch-compare 看板链接 + 查询诉求（解析 `bn=` 与 `ar=` 参数后执行）

**不适用（路由到别处）**：
- 分析 RCF 分数波动根因 → `rcf-raptor-anylisize`
- 只查某个指标数值（不带新老对比语义）→ `raptorfe-allquery`
- MRN 告警分析 → `raptorperf-alert-analyzer`

---

## 第一步：确认对比参数

开始前确认以下信息，缺少时主动询问，不要猜：

| 参数 | 必填 | 缺省规则 |
|---|---|---|
| bundle 包名（1 个或多个） | ✅ | 必须由用户提供（如 `rn_hotel_rn-hotel-mainlist`）；包名通常为 `rn_{业务线}_{页面名}` 形态 |
| 日期 | ✅ | 默认昨天（单日）；用户给范围则起止各查 |
| 新/老架构时间窗 | — | 默认同窗；用户明确要「分时段对比」（新架构看近期、老架构看历史）时才分开 |

用户发看板链接时，解析 URL：`bn=` 为逗号分隔的包名，`ar=新起~新止~老起~老止` 为两个时间窗（四个日期相同即同窗）。

## 第二步：执行查询（每个 bundle × 6 个请求）

> 以下命令均已实测（2026-11-26，raptorfe 2.0.3-beta.0）。`--filters` 中的 JSON 双引号按 shell 规则转义。

**C 组（单请求，带出 C 分数/秒开率/TP90）：**

```bash
raptorfe perf metric dimension-analyse \
  --metrics-name 98466 --metrics-type atom \
  --tag-names arch_type --agg DAY \
  --start-time <起> --end-time <止> \
  --filters '{"bundle_name":["<包名>"]}' \
  --other-metrics c17949,c10296 \
  --format json
```

**PV 组（单请求）：**

```bash
raptorfe perf metric dimension-analyse \
  --metrics-name 225015 --metrics-type atom \
  --tag-names arch_type --agg DAY \
  --start-time <起> --end-time <止> \
  --filters '{"bundle_name":["<包名>"]}' \
  --format json
```

**F 组（按架构拆 2 个请求，`arch` 依次取 `new` / `old`）：**

```bash
raptorfe perf metric dimension-analyse \
  --metrics-name mobile.fps.scroll.avg.v2.n --metrics-type atom \
  --tag-names arch_type --agg DAY \
  --start-time <起> --end-time <止> \
  --filters '{"techStack":["mrn"],"bundle_name":["<包名>"],"arch_type":["<arch>"]}' \
  --other-metrics c17952 \
  --format json
```

**R 组（按架构拆 2 个请求，同上）：**

```bash
raptorfe perf metric dimension-analyse \
  --metrics-name metricx.response.duration --metrics-type atom \
  --tag-names arch_type --agg DAY \
  --start-time <起> --end-time <止> \
  --filters '{"techStack":["mrn"],"bundle_name":["<包名>"],"arch_type":["<arch>"]}' \
  --other-metrics c17948 \
  --format json
```

**分时段对比（新老时间窗不同）时**：C/PV 也无法用一个按 arch_type 分组的请求覆盖两个窗口，**必须按新/老各自时间窗拆成两次请求**（filters 同样带 `arch_type`），与 F/R 一致——否则老架构数据会用错时间窗。

**解析规则**：
- C/PV 响应 `data` 是多行（new/old/scout.*），**只取 `valueMap.arch_type` 为 `new`/`old` 的行**；
- C 分数取 `valueMap.c17949`、秒开率 `c10296`、TP90 取 `TP90`、PV 取 `sum`；
- F/R 响应是单行，分数分别取 `c17952` / `c17948`；
- **完整性校验**：按「背景」节的规则校验后再输出。

## 第三步：输出对比表格

每个 bundle 一段，形如（2026-11-25 实测数据示例）：

**rn_hotel_rn-hotel-mainlist（2026-11-25）**

| 架构 | C 分数 | 首屏耗时 TP90 | 秒开率 | F 分数 | R 分数 | RCF 总分 | 页面加载次数 |
|---|---|---|---|---|---|---|---|
| 新架构 | 41.00 | 1896.1ms | 69.8% | 64.96 | 96.58 | 59.30 | 5.755M |
| 老架构 | 43.60 | 2177.5ms | 73.9% | 76.53 | 97.93 | 64.34 | 373.352K |

> 说明：F/R 的 TP 分位列 CLI 通道无真实值（聚合假 TP），已裁掉；C TP90 与看板同路径。

数字格式：分数保留 2 位小数；秒开率按百分比保留 1 位小数；TP90 保留 1 位小数带 ms；PV 对齐看板 `formatPv` 的 3 位小数（`sum`/1e6 或 /1e3，如 5.755M），<1e6 用 K（如 373.352K）。

## 第四步：胜率与洞察（精确复刻看板规则）

**胜率定义（勿改成「≥ 即胜」）**：逐个对比单元，`新架构分数 > 老架构分数` 才记新架构获胜，**持平或更低不计获胜**；胜率 = 新架构获胜单元数 ÷ 全部对比单元数。分别给出 C 分数胜率、F 分数胜率、R 分数胜率、RCF 总分胜率；单项分数缺失的单元按 0 参与比较并在表格标注。

**洞察规则（看板 RULE_CONFIG 同款）**：**输出顺序为硬性要求——必须严格按 priority 数值升序输出：1 C 大幅改善 → 3 样本量偏小 → 4 C 回退 → 5 F 承压 → 6 R 下降，不得按其他顺序（如 4→5→6 之外的乱序）排列**：
1. **C 分数大幅改善**（优先级 1）：新 - 老 > 0 的 Top3 bundle，列出涨幅；
2. **样本量偏小**（优先级 3）：任一架构 PV（sum 折算后）< 100，输出「样本量偏小，结论需谨慎」警告，并指明是哪个架构；
3. **C 分数回退**（优先级 4）：新 - 老 < 0 的 bundle，列出回退幅度，提示「需结合版本变更排查」；
4. **F 分数承压**（优先级 5）：F 分数差 < -5（阈值 `F_STRESS_THRESHOLD`）时提示承压；< -10（`F_STRESS_SEVERE`）提示严重承压；
5. **R 分数下降**（优先级 6）：R 分数差 < -1（`R_DROP_THRESHOLD`）时提示。

## 第五步：附看板链接

输出末尾附官方看板链接（用户可直接跳转看完整数据含 F/R TP）：

```
https://raptor.mws.sankuai.com/mrn-dashboard/layout/arch-compare?bn=<逗号分隔包名>&ar=<新起>~<新止>~<老起>~<老止>
```

境外环境换 `raptor.mws.keetapp.com` 域名。

---

## ⚠️ 已知限制（如实告知用户，不掩盖）

1. **F/R TP 分位**：CLI 通道拿不到逐 bundle 真实 TP（需 `currentMrnOrg`，CLI 未暴露；get-trend 返回的是聚合假 TP），已裁掉该列，需要精确 TP 请点看板链接；
2. **scout 分组**：响应中 `arch_type` 为 `scout.others`/`scout.null` 的行是哨兵数据，一律过滤；
3. **半截响应**：偶发缺项，重试可恢复；重试仍缺则明确报数据不完整；
4. C TP90 与看板可能有 1~3ms 的浮点保留位差（CLI 未带 `pointTwo=false` 等精度参数），属展示精度差异，不影响结论。
