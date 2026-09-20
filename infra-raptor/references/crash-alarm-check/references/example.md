# 端到端示例：从告警消息到根因结论

## 输入：告警消息

```
【P3 新增Crash告警】
策略名称：路由和外链_Android_新增Crash_P3-非QQ进程
时间范围：2026-03-24 14:00 ~ 14:10
聚类列表：https://raptor.sankuai.com/crash/list?filter=default_component%2Cdsp%26message%2Cabc123hash
```

## 第零步：环境检查

```bash
raptorfe --version || npm install -g @mtfe/raptorfe-cli --registry https://r.npm.sankuai.com/
```

## 第一步：解析告警

- **等级**：P3
- **子类型**：**新增异常**（策略名含「新增Crash」）→ 后续走 **3A 分支**
- **策略**：路由和外链_Android_新增Crash_P3-非QQ进程
- **时间**：2026-03-24 14:00 ~ 14:10
- **组件**：`dsp`（从 filter 参数解析）
- **Project**：`android_platform_monitor`（Android → 查映射表）
- **Type**：`crash`

## 第二步：拉取聚类列表

```bash
raptorfe crash cluster list \
  --project android_platform_monitor \
  --type crash \
  --start "2026-03-24 14:00:00" \
  --end "2026-03-24 14:10:00" \
  --filter "default_component:dsp" \
  --page-size 10
```

返回：
```
| id (UUID)          | message (hash) | count | firstTS | exceptionType |
|--------------------|----------------|-------|---------|---------------|
| abc123-uuid-4567   | abc123hash     | 5     | 1711286400 | IllegalArgumentException |
```

→ 确认 `message=abc123hash`，`firstTS` = 2026-03-24（今日首次出现），确认为**新增异常**

## 第三步：粗粒度趋势分析 → 走 3A 新增异常分支

由于是**新增异常**（3A 分支），跳过标准 7 维增长归因，直接做快速判断：

1. **聚类拆分检查**：`abc123hash` 与历史聚类 hash 无相似前缀 → 非拆分，是真新问题
2. **版本分布检查**：需在第四步维度分布中确认是否集中在新版本
3. **→ 直接进入第四步 + 第五步**

## 第四步：细粒度维度分布 + DAU 偏差

```bash
raptorfe crash reason-ranking get \
  --project android_platform_monitor \
  --type crash \
  --filter "default_component:dsp" \
  --filter "message:abc123hash" \
  --start "2026-03-24 14:00:00" \
  --end "2026-03-24 14:10:00"
```

关键发现：
- `appVersion` Top1：**12.8.405**（占比 100%，5/5）→ 高度集中在新版
- `lastPage` Top1：外链唤起页
- `exceptionType`：IllegalArgumentException（100%）

DAU 偏差：由于是新增异常且仅影响单一版本，偏差计算意义不大。重点确认 12.8.405 是否为近期发布版本。

## 第五步：堆栈深度分析

```bash
# 第一条：最高频堆栈
raptorfe crash detail get \
  --project android_platform_monitor \
  --id abc123-uuid-4567 \
  --ts 1711286400
```

关键字段摘取：
```
androidLog:
  java.lang.IllegalArgumentException: No view found for id 0x7f0123 (com.sankuai.meituan:id/dsp_container)
    for fragment DspFragment{abc123}
    at android.app.FragmentManagerImpl.moveToState(FragmentManager.java:1018)
    at com.sankuai.meituan.dsp.DspManager.show(DspManager.java:88)
    at com.sankuai.meituan.router.OutlinkHandler.open(OutlinkHandler.java:214)
appVersion: 12.8.405
lastPageTrack: 首页 → 搜索结果页 → 外链唤起
crashTime: 2026-03-24 14:05:23
default_component: dsp
loganId: logan_xxxxxx
```

> 由于新增异常仅 5 条且全部为同一聚类，此处分析 1 条堆栈即可（实际生产中若有多条不同聚类则需 ≥5 条）

## 第六步：输出报告

---

# 「路由和外链_Android_新增Crash_P3-非QQ进程」AI分析结果

## 结论
🔴 **新增 Crash，需要关注**。当前时间段（03-24 14:00~14:10）Crash 影响用户 5 台，为当日首次出现的新增异常，上周无此 Crash。[Raptor链接]

## 影响范围
03-24 14:00～14:10 共影响用户 5 台，Crash 量 5

## 变化趋势
新增异常，03-24 首次出现，无可比基线。

## 问题原因
DspManager 尝试将 DspFragment commit 到 `dsp_container` 容器，但当前 Activity 布局中该容器 View 不存在（可能因页面跳转时 Activity 已进入销毁流程，布局已被回收）。属于典型的 Fragment 生命周期与 Activity 状态不同步问题。

## App版本分析
Crash 100% 集中在 12.8.405 版本，高度疑似该版本引入的新问题。

## 崩溃页面分析
Crash 集中在外链唤起页面（占比 100%），触发路径为「首页 → 搜索结果页 → 外链唤起 DSP 浮层」。

## 系统版本分析
样本量较小（5 台），系统版本分布无明显异常。

---

## 🔥 增长归因详细分析

### 基本信息
| 项目 | 详情 |
|------|------|
| 告警类型 | Crash |
| 告警等级 | P3 |
| 触发规则 | 新增异常 |
| 当前值 | 5 台 |
| 平台 | Android |
| APP | 美团 |
| 时间范围 | 2026-03-24 14:00 ~ 14:10 |
| 涉及组件 | dsp |

### 趋势对比
| 日期 | 影响设备数 | Crash量 | 环比变化 | 备注 |
|------|-----------|--------|---------|------|
| 03-23 | 0 | 0 | — | 不存在 |
| 03-24 | 5 | 5 | 🆕 新增 | ⚠️ 首次出现 |

### 归因排查清单
| 排查维度 | 结果 | 结论 |
|---------|------|------|
| 🅰️ 线上放量/灰度扩围 | 新增异常，不适用 | — |
| 🅱️ App版本发布/升级迁移 | 100% 集中于 12.8.405 | ✅ 高度疑似版本引入 |
| 🅲 操作系统版本更新 | 分布正常 | ❌ 排除 |
| 🅳 配置下发变更 | releasechange 无关联变更 | ❌ 排除 |
| 🅴 运营活动/流量来源 | 无关联活动 | ❌ 排除 |
| 🅵 热修复/补丁下发 | 近期无热修复 | ❌ 排除 |
| 🅶 SDK升级/三方库更新 | 堆栈全为业务代码 | ❌ 排除 |

### 🎯 增长主因
新增异常，12.8.405 版本首次引入的代码问题。

### 增长性质
🆕 **新增异常** — 非增长归因范畴，属于新引入 Bug。

---

## 维度分布详情

### APP 版本 Top5
| 版本 | Crash量 | Crash占比 | 判断 |
|------|--------|----------|------|
| 12.8.405 | 5 | 100% | 🔴 高度集中 |

### 崩溃页面 Top5
| 页面 | Crash量 | 占比 | 判断 |
|------|--------|------|------|
| 外链唤起 | 5 | 100% | 唯一触发场景 |

### 异常类型分布
| 异常类型 | 数量 | 占比 |
|---------|------|------|
| IllegalArgumentException | 5 | 100% |

---

## 影响范围评估
- **严重程度**：🟡 中（P3，影响 5 台）
- **版本偏差结论**：版本引入型（100% 集中于 12.8.405）
- **页面集中度**：Top1 页面占比 100%，高度集中
- **归属组件**：dsp
- **是否为历史问题**：否（新增）

---

## 堆栈深度分析（共分析 1 条）

### 堆栈 #1（唯一聚类，占比 100%）
- **异常类型**：`IllegalArgumentException`
- **崩溃点**：`FragmentManagerImpl.moveToState(FragmentManager.java:1018)` — 找不到 dsp_container View
- **调用链**：`OutlinkHandler.open()` → `DspManager.show()` → `FragmentManagerImpl.moveToState()` → 💥
- **环境信息**：前台，Activity 处于过渡状态
- **分析**：DspManager 在 Activity 生命周期不稳定时尝试 commit Fragment，目标容器 View 已被回收

### 堆栈共性总结
- [x] 仅 1 个聚类，所有样本崩溃点一致 → 确定性根因

---

## 根因分析与建议

### 根因判断
12.8.405 版本在 `DspManager.show()` 中 commit DspFragment 时未校验 Activity 生命周期状态，当用户快速跳转导致 Activity 进入销毁流程后，布局中的 `dsp_container` View 已被回收，此时 commit Fragment 抛出 `IllegalArgumentException`。这是典型的「Fragment 生命周期与 Activity 状态不同步」问题。

### 根因模式
| 模式 | 判定 | 依据 |
|------|------|------|
| 版本引入型 | ✅ 是 | 100% 集中于 12.8.405 |
| 页面集中型 | ✅ 是 | 100% 在外链唤起场景 |
| 机型相关型 | 否 | 样本不足但无明显机型聚集 |
| 并发相关型 | 否 | 主线程同步调用 |
| 配置触发型 | 否 | 无配置关联 |
| 历史问题放大 | 否 | 新增异常 |

### 最终结论与建议
**[需要修复]** — 新增 Crash，根因明确，修复成本低。

### 排查建议（优先级排序）
1. **[P1 尽快处理]** `DspManager.show()` 调用前增加 `activity.isFinishing() || activity.isDestroyed()` 判断，避免在无效 Activity 上 commit Fragment。责任人建议：路由/外链模块负责人。
2. **[P2 观察跟进]** 发布修复后观察后续 3 天是否还有同类 Crash（可能存在类似模式的遗漏场景）。
3. **[P3 长期优化]** 审计 dsp 模块所有 Fragment 操作，统一增加生命周期守卫。
