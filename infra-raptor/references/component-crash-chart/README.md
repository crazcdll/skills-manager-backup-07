# component-crash-chart

> 一句话出图——自动查询组件 Crash / ANR 数据并生成趋势图

**版本：** v2.1.0 | **作者：** nieyunlong

---

## 功能概览

支持六种模式，覆盖美团 / 点评 / 外卖，Android / iOS / HarmonyOS 全平台：

| 模式 | 说明 | 示例话术 |
|------|------|---------|
| 📊 小时级 | 当天每小时 crash 分布（自动同时段环比） | `dsp crash 图` |
| 📅 N天趋势 | 历史走势 + 发版时间线 | `pike crash 7天图` |
| 🔍 多版本对比 | 找出哪个版本引入了问题 | `pike crash 版本对比 auto` |
| 📈 小时级同比 | 修复上线后对比前几天效果 | `pike crash 同比昨天` |
| 🐌 ANR 图 | 当天每小时 ANR 分布，自动同时段环比 | `raptor anr 图` |
| 🔧 修复推送 | 定时生成并推送到大象 | `pike crash 图 notify nieyunlong` |

---

## 快速开始

直接用自然语言描述即可，无需记命令格式：

```
dsp crash 图
鸿蒙 pike crash 15天图
点评 android babel crash 版本对比 auto
外卖 iOS horn crash 同比昨天
android dsp crash 4天同比
raptor anr 图              ← 新增 ANR 支持
android raptor anr 7天图
```

---

## 平台/App 说明

| App       | Android        | iOS          | HarmonyOS    |
|-----------|----------------|--------------|--------------|
| 美团      | 默认（不加前缀）| `ios`        | `鸿蒙`/`harmony` |
| 点评      | `点评`/`dp`    | `点评 ios`   | `点评鸿蒙`   |
| 外卖      | `外卖`/`wm`    | `外卖 ios`   | `外卖鸿蒙`   |

---

## 前置依赖

### 1. mcporter
OpenClaw 自动安装，无需手动处理。

### 2. MCP Server（自动注册，无需鉴权）

skill 启动时自动检查并注册以下 MCP server，**无需任何手动配置**：

| 服务 | 用途 |
|---|---|
| crash_time_data（[Friday id=1339](https://friday.sankuai.com/mcp/mcp-server-detail?activeTab=overview&id=1339)） | 崩溃量时序数据 |
| crash_detail（[Friday id=1176](https://friday.sankuai.com/mcp/mcp-server-detail?activeTab=overview&id=1176)） | 版本采样 / crash 堆栈 |

两个接入点均**无需 token 鉴权**，首次运行自动配置。

### 3. S3Plus 上传（可选）
图片优先通过 S3Plus 发送，若上传失败会回退到本地文件路径。

---

## 目录结构

```
component-crash-chart/
├── SKILL.md          # skill 主配置（供 OpenClaw 读取）
├── README.md         # 本文件
├── CHANGELOG.md      # 版本历史
├── scripts/
│   └── generate_chart.py   # 核心图表生成脚本
└── references/       # 参考资料
```

---

## 版本历史

详见 CHANGELOG.md

- v2.1.0：新增 ANR 图表支持（`--type anr`）；修复当天数据不完整时环比结论不准确问题（改用同时段对比）
- v2.0.0：移除 SSO/token 鉴权，改用无鉴权 MCP 接入点（crash_time_data + crash_detail）
- v1.6.4：mis 自动从 sso-auth-cli cache.json 读取，无需硬编码
- v1.6.3：修复 sso-auth-cli 换票 stdout 为空问题，改用 --cookie 模式
- v1.6.2：换票升级为三级 fallback，支持 CIBA 大象授权
- v1.6.1：新增 token 自动 fallback（读取 sso-auth-cli cache）
- v1.6.0：支持分钟级模式
- v1.5.x：多版本对比、同比模式

---

## 常见问题

Q: 数据为空？
A: 确认组件名称拼写，Raptor 侧可能该时段无 crash 数据。

Q: 图片发不出来？
A: S3 上传失败时 skill 会回复本地路径，可手动下载。
