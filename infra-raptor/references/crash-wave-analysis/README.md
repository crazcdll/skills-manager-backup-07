# crash-wave-analysis — 稳定性指标波动分析

对 Crash、ANR、FOOM 等稳定性指标进行多维度波动分析，定位问题根因。

---

## 能做什么

- 按版本分布、时间趋势、组件分布、栈顶聚类、设备型号、前后台分布、多维交叉等维度逐步分析
- 结合发版事件（通过 `raptorfe crash events list` 获取），判断波动是否与版本发布相关
- 输出标准化分析报告 + 根因定位 + 优化建议
- 可选调用 infra-app-stability 进行深度堆栈分析

## 触发示例

```
分析一下美团 iOS 最近 14 天的 Crash 波动
帮我看看外卖 Android 这周 ANR 趋势，有没有异常
分析一下 FOOM 最近的情况
（粘贴 Raptor crash 页面链接）帮我分析一下这个
```

## 与其他子技能的区别

| 场景 | 使用哪个子技能 |
|------|--------------|
| 收到告警消息，需要根因分析 | `infra-app-stability` → `root-cause` |
| 只是查询数据（次数/率） | `raptorfe-allquery` |
| 只是画趋势图 | `component-crash-chart` |
| 主动分析一段时间内的波动趋势 | **本技能** |

## 依赖

- `raptorfe` CLI：`npm install -g @mtfe/raptorfe-cli --registry https://r.npm.sankuai.com/`
